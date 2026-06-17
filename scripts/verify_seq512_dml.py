# -*- coding: utf-8 -*-
"""
8060S(DirectML, fp16) 단독 검증 — seq512 어댑터가 옛 AMD-v4의 붕괴 항목을 해소했는지 확인.

4060 비교 문서(training-benchmark-7b-cuda.md)가 'AMD-v4 깨짐'으로 기록한 바로 그 항목을
같은 프롬프트 포맷·greedy 디코딩·FIM 억제로 돌린다(베이스만 fp16 vs 4비트로 다름).

  1) useDebounce<T>  — TS 제네릭 (AMD-v4: 'type not assignable to never' 깨짐)
  2) TanStack 무한스크롤 (KR, 복잡)  — (AMD-v4: 지시문만 되풀이, 코드 0줄)
  3) EgovPaging.jsx 실파일 → TS 변환  — (AMD-v4: 빈 출력 0자)

실행:
  python scripts/verify_seq512_dml.py
  python scripts/verify_seq512_dml.py --adapter models/qwen-react-lora-7b-seq512
"""
import os
import sys
import io
import time
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import torch
import torch_directml
from transformers import AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType, set_peft_model_state_dict
import safetensors.torch as st

from train_directml import stream_load_to_device, load_config

ROOT = Path(__file__).resolve().parent.parent
FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>"]
EGOV = Path("C:/Users/user/Documents/workspace/twinspace_platform/egovGeoportal/src/components/EgovPaging.jsx")


def build_prompt(instruction, code=""):
    if code:
        return f"### Instruction:\n{instruction}\n\n### Input:\n{code}\n\n### Response:\n"
    return f"### Instruction:\n{instruction}\n\n### Response:\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="models/qwen-react-lora-7b-seq512")
    ap.add_argument("--max-new", type=int, default=400)
    args = ap.parse_args()

    config = load_config()
    base = config["model"]["base_model"]
    device = torch_directml.device()
    dtype = torch.float16

    egov_code = EGOV.read_text(encoding="utf-8") if EGOV.exists() else ""
    tests = [
        ("TS 제네릭 useDebounce<T>",
         "Create a custom React hook useDebounce<T>(value: T, delay: number): T in TypeScript.", ""),
        ("복잡 KR: TanStack 무한스크롤",
         "TanStack Query의 useInfiniteQuery로 무한 스크롤 상품 목록을 구현해줘. "
         "Product 타입과 로딩/에러 처리를 포함해줘.", ""),
        ("실파일 EgovPaging.jsx → TS",
         "이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘.", egov_code),
    ]

    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print(f"[로드] 베이스 7B fp16 스트리밍: {base}", flush=True)
    model = stream_load_to_device(base, device, dtype)
    lc = config["lora"]
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=lc["r"], lora_alpha=lc["lora_alpha"],
        target_modules=lc["target_modules"], lora_dropout=lc["lora_dropout"], bias=lc["bias"]))
    sd_path = str(ROOT / args.adapter / "adapter_model.safetensors")
    sd = {k: v.to(dtype) for k, v in st.load_file(sd_path).items()}
    set_peft_model_state_dict(model, sd)
    model = model.to(device)
    model.eval()
    model.config.use_cache = True
    print(f"[로드] 어댑터 적용: {args.adapter} ({len(sd)} 텐서)", flush=True)

    stop_ids = [tok.eos_token_id]
    for t in FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            stop_ids.append(tid)
    stop_ids = list(dict.fromkeys(stop_ids))

    for name, instr, code in tests:
        inputs = tok(build_prompt(instr, code), return_tensors="pt")
        in_len = inputs["input_ids"].shape[1]
        inputs = {k: v.to(device) for k, v in inputs.items()}
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id, eos_token_id=stop_ids,
                                 repetition_penalty=1.1)
        gen = out[0][in_len:]
        text = tok.decode(gen, skip_special_tokens=True)
        for m in FIM:
            j = text.find(m)
            if j != -1:
                text = text[:j]
        text = text.strip()
        dt = time.time() - t0
        print(f"\n{'='*72}\n[{name}]  input_tokens={in_len}\n{'-'*72}")
        print(text if text else "(빈 출력 0자)")
        print(f"\n--> {len(gen)} tok / {dt:.1f}s = {len(gen)/max(dt,1e-9):.1f} tok/s", flush=True)


if __name__ == "__main__":
    main()
