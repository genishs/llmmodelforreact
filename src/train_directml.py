# -*- coding: utf-8 -*-
"""
DirectML(AMD GPU) 직접 학습 스크립트 — 7B LoRA fine-tuning.

기존 train.py는 CPU 전용(통합 16GB VRAM 시절 작성). 이 스크립트는 VRAM 48GB
환경을 위해:
  1) 모델을 meta(빈 가중치)로 만든 뒤 safetensors 텐서를 하나씩 fp32로 변환해
     DirectML VRAM에 직접 올린다(host RAM 피크 = 가장 큰 텐서 1개분).
  2) HF Trainer 대신 DirectML을 인식하는 커스텀 학습 루프를 쓴다.

실행:
  python src/train_directml.py --smoke 2      # 스모크: 2 step만, 저장 안 함
  python src/train_directml.py                # 본런 (config 기준)
"""

import os
import sys
import io
import time
import glob
import json
import argparse
import datetime as dt

import yaml
import torch
import psutil

# Windows 콘솔 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

import torch_directml
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    get_cosine_schedule_with_warmup,
)
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, TaskType
from accelerate import init_empty_weights
from accelerate.utils import set_module_tensor_to_device
from safetensors import safe_open
from torch.utils.data import DataLoader

RAM_GUARD_GB = 0.5  # 로딩 중 가용 RAM이 이 밑으로 떨어지면 중단(프리징 방지)


def log(msg):
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def ram_avail_gb():
    return psutil.virtual_memory().available / 1024**3


def load_config(path="./config/training_config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def stream_load_to_device(model_path, device, dtype):
    """safetensors 텐서를 지정 dtype으로 변환해 DirectML 디바이스에 직접 적재.

    DirectML은 bf16 미지원 → 호스트에서 fp16/fp32 변환 후 디바이스로 이동.
    DirectML 실사용 VRAM 천장 ~31GB → 7B는 fp16(14GB)으로 적재해야 활성값 여유 확보.
    safe_open을 텐서 단위로 열고 닫아 mmap 워킹셋을 텐서 1개분으로 한정
    (shard 통째 매핑 시 host RAM 소진 → 스왑 프리징 방지).
    """
    import gc
    cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(cfg, torch_dtype=dtype)
    model.tie_weights()  # 묶인 가중치(예: lm_head=embed) 연결

    # 텐서 → shard 매핑 (index 있으면 사용, 없으면 단일 파일)
    idx = os.path.join(model_path, "model.safetensors.index.json")
    if os.path.exists(idx):
        with open(idx, "r", encoding="utf-8") as f:
            wmap = json.load(f)["weight_map"]
        items = [(n, os.path.join(model_path, s)) for n, s in wmap.items()]
    else:
        shard = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))[0]
        with safe_open(shard, framework="pt", device="cpu") as f:
            items = [(n, shard) for n in f.keys()]

    log(f"  {len(items)} tensors 스트리밍 적재 시작 (host RAM 가용 {ram_avail_gb():.1f}GB)")
    loaded, t0 = 0, time.time()
    for name, shard in items:
        if ram_avail_gb() < RAM_GUARD_GB:
            raise MemoryError(
                f"가용 RAM {ram_avail_gb():.2f}GB < {RAM_GUARD_GB}GB 가드. "
                f"다른 앱을 닫고 재시도하세요(스왑 프리징 방지)."
            )
        with safe_open(shard, framework="pt", device="cpu") as f:
            t = f.get_tensor(name).to(dtype)  # host 변환 (텐서 1개분 피크)
        set_module_tensor_to_device(model, name, device, value=t)
        del t
        loaded += 1
        if loaded % 50 == 0:
            gc.collect()
            log(f"  {loaded}/{len(items)} tensors | RAM 가용 {ram_avail_gb():.1f}GB")

    remaining = [n for n, p in model.named_parameters() if p.is_meta]
    if remaining:
        raise RuntimeError(f"적재 안 된 meta 텐서 {len(remaining)}개: {remaining[:5]}")
    log(f"  적재 완료: {loaded} tensors, {time.time()-t0:.1f}s, RAM 가용 {ram_avail_gb():.1f}GB")
    return model


def build(model_path, device, config, dtype, grad_ckpt):
    log(f"모델 로드: {model_path} (dtype={dtype})")
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = stream_load_to_device(model_path, device, dtype)

    lc = config["lora"]
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lc["r"], lora_alpha=lc["lora_alpha"],
        target_modules=lc["target_modules"],
        lora_dropout=lc["lora_dropout"], bias=lc["bias"],
    )
    model = get_peft_model(model, lora_config)
    model = model.to(device)  # LoRA 신규 파라미터를 디바이스로
    model.config.use_cache = False

    # gradient checkpointing: DirectML에서는 재계산이 캐싱 할당자에 버퍼를 더 쌓아
    # 오히려 VRAM 증가를 가속 → 기본 비활성.
    if grad_ckpt:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()

    model.print_trainable_parameters()
    return model, tok


def make_loader(data_file, tok, max_len, batch_size, shuffle):
    ds = load_dataset("json", data_files=data_file, split="train")

    def tok_fn(ex):
        # 고정 길이 패딩: 모든 배치를 동일 크기로 → DirectML 할당자 버퍼 재사용
        # (동적 패딩 시 배치마다 크기가 달라 VRAM이 step마다 증가 → OOM)
        return tok(ex["text"], truncation=True, max_length=max_len,
                   padding="max_length")

    ds = ds.map(tok_fn, batched=True, remove_columns=ds.column_names)
    collator = DataCollatorForLanguageModeling(tokenizer=tok, mlm=False)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, collate_fn=collator)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0,
                    help="스모크 모드: 지정 step 수만 돌리고 저장 없이 종료")
    ap.add_argument("--config", default="./config/training_config.yaml")
    ap.add_argument("--dtype", choices=["fp16", "fp32"], default="fp16",
                    help="가중치 dtype (DirectML ~31GB 천장 → 7B는 fp16 권장)")
    ap.add_argument("--seq", type=int, default=0, help="max_seq_length 오버라이드(0=config)")
    ap.add_argument("--scale", type=float, default=128.0,
                    help="fp16 손실 스케일(언더플로 방지)")
    ap.add_argument("--grad-ckpt", action="store_true",
                    help="gradient checkpointing(DirectML에서는 비권장)")
    args = ap.parse_args()

    config = load_config(args.config)
    dtype = torch.float16 if args.dtype == "fp16" else torch.float32
    use_scale = dtype == torch.float16
    SCALE = args.scale if use_scale else 1.0

    device = torch_directml.device()
    log(f"디바이스: DirectML ({torch_directml.device_name(0)}) | dtype={args.dtype} "
        f"| loss_scale={SCALE if use_scale else 'off'}")
    log(f"시작 RAM 가용 {ram_avail_gb():.1f}GB / CPU {psutil.cpu_percent()}%")

    tcfg = config["training"]
    dcfg = config["data"]
    model_path = config["model"]["base_model"]

    model, tok = build(model_path, device, config, dtype, args.grad_ckpt)

    bs = tcfg["per_device_train_batch_size"]
    accum = tcfg["gradient_accumulation_steps"]
    max_len = args.seq if args.seq > 0 else dcfg["max_seq_length"]

    train_loader = make_loader(dcfg["train_file"], tok, max_len, bs, shuffle=True)

    trainable = [p for p in model.parameters() if p.requires_grad]
    optim = torch.optim.AdamW(trainable, lr=float(tcfg["learning_rate"]), eps=1e-4)

    smoke = args.smoke > 0
    epochs = 1 if smoke else int(tcfg["num_train_epochs"])
    total_steps = (len(train_loader) // accum) * epochs
    sched = get_cosine_schedule_with_warmup(
        optim, int(total_steps * tcfg["warmup_ratio"]), max(total_steps, 1)
    )

    log(f"{'[스모크]' if smoke else '[본런]'} epochs={epochs} "
        f"batches/epoch={len(train_loader)} accum={accum} "
        f"optim_steps≈{total_steps if not smoke else args.smoke}")

    model.train()
    run_start = time.time()
    step, micro = 0, 0
    step_times = []
    t_step = time.time()
    stop = False

    skipped = 0
    for ep in range(epochs):
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = model(**batch)
            (out.loss * SCALE / accum).backward()
            micro += 1

            if micro % accum == 0:
                # fp16 그래디언트 언스케일 + inf/nan 검사
                bad = False
                for p in trainable:
                    if p.grad is not None:
                        if SCALE != 1.0:
                            p.grad.div_(SCALE)
                        if not torch.isfinite(p.grad).all():
                            bad = True
                if bad:
                    skipped += 1  # 스케일 오버플로 → 이 step 건너뜀
                else:
                    optim.step()
                optim.zero_grad()
                sched.step()
                step += 1
                dt_step = time.time() - t_step
                step_times.append(dt_step)
                log(f"step {step} | loss {out.loss.item():.4f} | "
                    f"{dt_step:.1f}s/step | RAM가용 {ram_avail_gb():.1f}GB | "
                    f"CPU {psutil.cpu_percent()}%{' | SKIP(nan)' if bad else ''}")
                t_step = time.time()
                if smoke and step >= args.smoke:
                    stop = True
                    break
        if stop:
            break
    if skipped:
        log(f"  (참고: nan/inf로 건너뛴 step {skipped}개)")

    elapsed = time.time() - run_start
    avg = sum(step_times) / len(step_times) if step_times else 0
    log(f"종료: {step} steps, 총 {elapsed:.1f}s, 평균 {avg:.1f}s/step")

    if smoke:
        log("[스모크 완료] 저장 생략. backward 정상 동작 확인됨." if step > 0
            else "[스모크 실패] step 미완료.")
        return

    # 저장: DirectML 텐서는 safetensors가 storage 조회 불가(OpaqueTensorImpl)이므로
    # PEFT save_pretrained가 실패한다. 어댑터 가중치를 CPU/fp32로 옮겨 직접 저장.
    out_dir = tcfg["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    from peft import get_peft_model_state_dict
    import safetensors.torch as st
    sd_cpu = {k: v.detach().to("cpu").float()
              for k, v in get_peft_model_state_dict(model).items()}
    adapter_name = list(model.peft_config.keys())[0]
    model.peft_config[adapter_name].save_pretrained(out_dir)  # adapter_config.json
    st.save_file(sd_cpu, os.path.join(out_dir, "adapter_model.safetensors"))
    tok.save_pretrained(out_dir)
    log(f"[본런 완료] 저장: {out_dir} (어댑터 {len(sd_cpu)} 텐서, CPU/fp32)")


if __name__ == "__main__":
    main()
