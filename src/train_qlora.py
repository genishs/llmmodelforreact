# -*- coding: utf-8 -*-
"""
CUDA 4비트 QLoRA 학습 — RTX 4060 8GB 등 NVIDIA GPU용.

DirectML(train_directml.py)·CPU(train.py)와 달리, CUDA에서는 bitsandbytes 4비트
양자화로 7B를 ~5GB에 올려 8GB GPU에서도 LoRA 학습 가능. 가중치가 4비트라 VRAM
여유가 생겨 **seq 1024(잘림 없이)** 학습이 가능 — 기존 DirectML(seq 256/384, 51% 잘림)의
품질 한계를 푼다.

실행:
  python src/train_qlora.py --seq 1024 --out ./models/qwen-react-lora-7b-qlora

사전: requirements-cuda.txt 설치(bitsandbytes 포함), 베이스 7B 다운로드,
      data/processed/*.jsonl 생성(build_dataset_v2.py).
"""
import argparse
import gc

import yaml
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    TrainerCallback,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig,
)
from datasets import load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType,
)


class EmptyCacheCallback(TrainerCallback):
    """매 optimizer step 후 CUDA 캐시를 비운다.

    8GB GPU에서 7B는 실제 작업셋(~6GB)은 들어가지만, PyTorch 캐싱 할당자의
    reserved 메모리가 단편화로 step마다 누적돼 8GB를 넘기면 공유메모리로 스필하며
    step 시간이 10초→170초로 급락한다. step마다 회수해 ceiling 아래로 유지한다.
    """

    def on_step_end(self, args, state, control, **kwargs):
        gc.collect()
        torch.cuda.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="./config/training_config.yaml")
    ap.add_argument("--seq", type=int, default=1024, help="max_seq_length(4비트라 1024 권장)")
    ap.add_argument("--out", default="./models/qwen-react-lora-7b-qlora")
    ap.add_argument("--rank", type=int, default=0, help="LoRA rank 오버라이드(0=config)")
    ap.add_argument("--alpha", type=int, default=0, help="LoRA alpha 오버라이드(0=rank*2)")
    ap.add_argument("--target", choices=["qkvo", "qkvo_mlp"], default="qkvo",
                    help="qkvo=기존(q,k,v,o), qkvo_mlp=+MLP(gate,up,down) 용량 확대")
    ap.add_argument("--max-steps", type=int, default=0,
                    help="0=full. >0이면 그만큼만 학습(스모크용, 저장 생략)")
    args = ap.parse_args()
    smoke = args.max_steps > 0

    assert torch.cuda.is_available(), "CUDA가 필요합니다(NVIDIA GPU). bitsandbytes 4비트는 CUDA 전용."
    print(f"[CUDA] {torch.cuda.get_device_name(0)}")

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    base = cfg["model"]["base_model"]

    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # Ada(4060)는 bf16 지원. 안전하게 fp16 compute. bf16 쓰려면 아래 2곳을 bfloat16/True로.
    compute_dtype = torch.float16
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base, quantization_config=bnb, device_map="auto", trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    # prepare_model_for_kbit_training은 4비트가 아닌 파라미터를 fp32로 업캐스트한다.
    # 7B의 embed_tokens·lm_head(각 152k×3584)가 fp32면 둘이 ~4.4GB(fp16의 2배)로,
    # 8GB GPU에서 4비트 베이스와 합쳐 한계를 넘겨 공유메모리 스필 → step당 수십 초로 급락.
    # 이 둘은 LoRA 대상이 아니어서 학습되지 않으므로 fp16으로 되돌려 ~2.2GB를 회수한다.
    for name, p in model.named_parameters():
        if p.dtype == torch.float32 and ("embed_tokens" in name or "lm_head" in name):
            p.data = p.data.to(compute_dtype)
    model.config.use_cache = False

    lc = cfg["lora"]
    rank = args.rank or lc["r"]
    alpha = args.alpha or (rank * 2)
    targets = (lc["target_modules"] if args.target == "qkvo" else
               ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    print(f"[LoRA] r={rank} alpha={alpha} target={args.target}({len(targets)} modules)")
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=rank, lora_alpha=alpha,
        target_modules=targets, lora_dropout=lc["lora_dropout"], bias=lc["bias"],
    ))
    model.print_trainable_parameters()

    d = cfg["data"]

    # EOS 위생: 학습 텍스트 끝에 eos를 붙여 '응답 종료'를 학습시킨다. 없으면 모델이 정지를
    # 못 배워 오버런(카운터가 안 멈춤)·`###` 다음섹션 누수가 생긴다. 데이터 최대 713<768이라
    # eos가 truncation에 잘릴 일 없음.
    def tok_fn(ex):
        texts = [t + tok.eos_token for t in ex["text"]]
        return tok(texts, truncation=True, max_length=args.seq, padding=False)

    train_ds = load_dataset("json", data_files=d["train_file"], split="train").map(
        tok_fn, batched=True, remove_columns=["text"])
    val_ds = load_dataset("json", data_files=d["val_file"], split="train").map(
        tok_fn, batched=True, remove_columns=["text"])
    print(f"학습 {len(train_ds)} / 검증 {len(val_ds)}, seq={args.seq}")

    t = cfg["training"]
    targs = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=t["num_train_epochs"],
        per_device_train_batch_size=t["per_device_train_batch_size"],
        gradient_accumulation_steps=t["gradient_accumulation_steps"],
        learning_rate=float(t["learning_rate"]),
        warmup_ratio=t["warmup_ratio"],
        lr_scheduler_type=t["lr_scheduler_type"],
        logging_steps=t["logging_steps"],
        save_steps=t["save_steps"],
        save_total_limit=t["save_total_limit"],
        fp16=True, bf16=False,                 # bf16 쓰려면 fp16=False, bf16=True
        gradient_checkpointing=True,
        # LoRA는 학습 파라미터가 작아(여기선 10M) 옵티마이저 상태가 수십 MB뿐 → CPU 페이징
        # (paged_*)이 불필요하고, 8GB GPU에서 매 step 느려지는 원인이 됨. 8bit in-VRAM 사용.
        optim="adamw_8bit",
        per_device_eval_batch_size=1,          # 기본 8이면 eval에서 VRAM 급증 → 8GB 초과 스필
        dataloader_num_workers=0,
        eval_strategy=("no" if smoke else "steps"), eval_steps=t["save_steps"],
        max_steps=(args.max_steps if smoke else -1),
        save_strategy=("no" if smoke else "steps"),
        report_to="none",
    )
    trainer = Trainer(
        model=model, args=targs,
        train_dataset=train_ds, eval_dataset=val_ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tok, mlm=False),
        callbacks=[EmptyCacheCallback()],
    )
    trainer.train()
    if smoke:
        print(f"[스모크 완료] max_steps={args.max_steps}, 저장 생략. "
              f"VRAM peak {torch.cuda.max_memory_allocated()/1e9:.2f} GB")
        return
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    print(f"[완료] 저장: {args.out}")


if __name__ == "__main__":
    main()
