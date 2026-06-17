# -*- coding: utf-8 -*-
"""
어댑터 비교 검증 (CUDA) — AMD-DirectML 학습 어댑터 vs CUDA-QLoRA 학습 어댑터.

같은 4060에서 같은 7B 4비트 베이스에 어댑터만 바꿔 끼워 같은 프롬프트로 생성한다.
→ 하드웨어/베이스/디코딩이 동일하므로 차이는 '학습된 어댑터'에서만 온다.
결정적 비교를 위해 greedy(do_sample=False) 디코딩.

실행:
  python scripts/compare_adapters.py --adapter models/qwen-react-lora-7b-v4    --label AMD-DirectML
  python scripts/compare_adapters.py --adapter models/qwen-react-lora-7b-qlora --label CUDA-QLoRA
"""
import argparse
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
BASE = str(ROOT / "models" / "base" / "qwen2.5-coder-7b")

PROMPTS = [
    ("EN-simple", "Write a React counter component using useState."),
    ("KR-hook", "useEffect로 윈도우 리사이즈를 감지하는 커스텀 훅을 만들어줘."),
    ("TS-generic", "Create a custom hook useDebounce(value, delay) in TypeScript."),
    ("KR-complex", "TanStack Query로 무한 스크롤되는 상품 목록 컴포넌트를 TypeScript로 만들어줘. 로딩/에러 상태도 처리해줘."),
]

FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>"]


def build_prompt(instr):
    return f"### Instruction:\n{instr}\n\n### Response:\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-new", type=int, default=320)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(model, str(ROOT / args.adapter))
    model.eval()

    # 특수토큰 누수 대응(model_loader와 동일): <|im_start|> 등 특수/FIM 토큰 '생성 자체'를
    # suppress하고 min_new_tokens로 즉시-eos 붕괴 차단. eos만 정지용으로 유지.
    eos_id = tok.eos_token_id
    suppress = set(int(i) for i in (tok.all_special_ids or []))
    for t in FIM + ["<|im_start|>"]:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            suppress.add(int(tid))
    suppress.discard(int(eos_id))
    suppress_tokens = sorted(suppress)

    print(f"\n{'='*70}\n[{args.label}] adapter={args.adapter}\n{'='*70}", flush=True)
    total_tok, total_t = 0, 0.0
    for name, instr in PROMPTS:
        inputs = {k: v.to(model.device) for k, v in
                  tok(build_prompt(instr), return_tensors="pt").items()}
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=args.max_new, min_new_tokens=24, do_sample=False,
                pad_token_id=tok.eos_token_id, eos_token_id=eos_id,
                suppress_tokens=suppress_tokens, repetition_penalty=1.1)
        dt = time.time() - t0
        gen = out[0][inputs["input_ids"].shape[1]:]
        n = gen.shape[0]
        text = tok.decode(gen, skip_special_tokens=True)
        for m in FIM:
            i = text.find(m)
            if i != -1:
                text = text[:i]
        total_tok += n
        total_t += dt
        print(f"\n----- [{name}] ({n} tok, {n/dt:.1f} tok/s) -----\n{text.strip()}", flush=True)

    print(f"\n[{args.label}] 평균 {total_tok/total_t:.1f} tok/s "
          f"(총 {total_tok} tok / {total_t:.1f}s)", flush=True)
    print(f"VRAM peak {torch.cuda.max_memory_allocated()/1e9:.2f} GB", flush=True)


if __name__ == "__main__":
    main()
