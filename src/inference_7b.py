# -*- coding: utf-8 -*-
"""
학습된 7B LoRA 어댑터 추론 검증 (DirectML).

train_directml.py의 스트리밍 로더를 재사용해 7B fp16 베이스를 VRAM에 올리고,
학습된 어댑터(models/qwen-react-lora-7b-v1)를 적용해 React 프롬프트로 생성한다.
(기존 inference.py/model_loader.py는 1.5B를 호스트 RAM에 fp32로 올리는 방식이라 7B 불가)

실행:
  python src/inference_7b.py                 # 기본 프롬프트 3종
  python src/inference_7b.py "질문..." ...    # 사용자 프롬프트
  python src/inference_7b.py --base           # 어댑터 없이 베이스만(대조군)
"""
import os
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import torch
import torch_directml
from transformers import AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType, set_peft_model_state_dict
import safetensors.torch as st

from train_directml import stream_load_to_device, load_config, log

DEFAULT_PROMPTS = [
    "Write a React counter component using useState.",
    "useEffect로 윈도우 리사이즈를 감지하는 커스텀 훅을 만들어줘.",
    "Create a custom hook useDebounce(value, delay) in TypeScript.",
]


def build_prompt(instruction):
    return f"### Instruction:\n{instruction}\n\n### Response:\n"


def main():
    args = [a for a in sys.argv[1:]]
    use_base = "--base" in args
    args = [a for a in args if a != "--base"]
    prompts = args if args else DEFAULT_PROMPTS

    config = load_config()
    base = config["model"]["base_model"]
    adapter_dir = config["training"]["output_dir"]
    device = torch_directml.device()
    dtype = torch.float16

    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    log(f"베이스 7B fp16 스트리밍 적재: {base}")
    model = stream_load_to_device(base, device, dtype)

    lc = config["lora"]
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=lc["r"], lora_alpha=lc["lora_alpha"],
        target_modules=lc["target_modules"], lora_dropout=lc["lora_dropout"],
        bias=lc["bias"],
    ))
    model = model.to(device)

    if not use_base:
        sd_path = os.path.join(adapter_dir, "adapter_model.safetensors")
        sd = {k: v.to(dtype) for k, v in st.load_file(sd_path).items()}
        res = set_peft_model_state_dict(model, sd)
        missing = getattr(res, "unexpected_keys", None)
        log(f"학습 어댑터 적용: {sd_path} ({len(sd)} 텐서)"
            + (f" | unexpected={missing}" if missing else ""))
        model = model.to(device)
    else:
        log("베이스 모델만(어댑터 미적용) — 대조군")

    model.eval()
    model.config.use_cache = True

    for i, instr in enumerate(prompts, 1):
        inputs = tok(build_prompt(instr), return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=160, do_sample=True,
                temperature=0.7, top_p=0.9, repetition_penalty=1.1,
                pad_token_id=tok.eos_token_id,
            )
        gen = out[0][inputs["input_ids"].shape[1]:]
        text = tok.decode(gen, skip_special_tokens=True).strip()
        dt = time.time() - t0
        print(f"\n{'='*70}\n[{i}] {instr}\n{'-'*70}\n{text}\n"
              f"({len(gen)} tok / {dt:.1f}s = {len(gen)/dt:.1f} tok/s)", flush=True)


if __name__ == "__main__":
    main()
