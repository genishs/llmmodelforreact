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

import yaml
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="./config/training_config.yaml")
    ap.add_argument("--seq", type=int, default=1024, help="max_seq_length(4비트라 1024 권장)")
    ap.add_argument("--out", default="./models/qwen-react-lora-7b-qlora")
    args = ap.parse_args()

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
    model.config.use_cache = False

    lc = cfg["lora"]
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=lc["r"], lora_alpha=lc["lora_alpha"],
        target_modules=lc["target_modules"], lora_dropout=lc["lora_dropout"], bias=lc["bias"],
    ))
    model.print_trainable_parameters()

    d = cfg["data"]

    def tok_fn(ex):
        return tok(ex["text"], truncation=True, max_length=args.seq, padding=False)

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
        optim="paged_adamw_8bit",              # QLoRA 권장 옵티마이저(VRAM 절약)
        dataloader_num_workers=0,
        eval_strategy="steps", eval_steps=t["save_steps"],
        report_to="none",
    )
    trainer = Trainer(
        model=model, args=targs,
        train_dataset=train_ds, eval_dataset=val_ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tok, mlm=False),
    )
    trainer.train()
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    print(f"[완료] 저장: {args.out}")


if __name__ == "__main__":
    main()
