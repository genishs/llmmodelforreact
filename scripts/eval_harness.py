# -*- coding: utf-8 -*-
"""
고정 평가 하베스트 — 어댑터 품질을 객관 점수로 비교(경쟁용).

같은 4060·4비트 베이스·greedy·서빙과 동일한 디코딩(특수토큰 suppress + min_new_tokens).
합성 4종 + egovGeoportal 실파일 2종(JS→TS). 각 태스크를 5개 자동 체크로 채점:
  nonempty(0/1) + no_special_leak(0/1) + no_hash_leak(0/1) + balanced(0/1) + expected(0..1)
→ 태스크당 최대 5점, 전체 합/백분율 출력 + JSON 저장.

실행:
  python scripts/eval_harness.py --adapter models/qwen-react-lora-7b-qlora --label rank16
결과: eval_results/<label>.json + 표 출력
"""
import argparse
import json
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
BASE = str(ROOT / "models" / "base" / "qwen2.5-coder-7b")
EGOV = Path("d:/Documents/workspace/TwinSpace/egovGeoportal/src")
FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>", "<|im_start|>"]

TS_CONV = "이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘."

# 각 태스크: name, instruction, input(파일 상대경로 or ""), expects(키워드 리스트)
TASKS = [
    ("counter-EN", "Write a React counter component using useState.", "",
     ["useState", "onClick", "export default"]),
    ("useWindowSize-KR", "useEffect로 윈도우 리사이즈를 감지하는 커스텀 훅을 만들어줘.", "",
     ["useEffect", "addEventListener", "removeEventListener", "export default"]),
    ("useDebounce-TS", "Create a custom hook useDebounce(value, delay) in TypeScript.", "",
     ["useDebounce", "<T>", "useEffect", "clearTimeout"]),
    ("tanstack-KR", "TanStack Query로 무한 스크롤되는 상품 목록 컴포넌트를 TypeScript로 만들어줘. 로딩/에러 상태도 처리해줘.", "",
     ["useInfiniteQuery", "interface", "fetchNextPage"]),
    ("egov-paging-TS", TS_CONV, "components/EgovPaging.jsx",
     ["interface", "moveToPage", "Math.ceil", "export default"]),
    ("egov-download-TS", TS_CONV, "pages/support/download/EgovDownloadDetail.jsx",
     ["interface", "export default"]),
]


def balanced(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    st = []
    for ch in s:
        if ch in "([{":
            st.append(ch)
        elif ch in pairs:
            if not st or st[-1] != pairs[ch]:
                return 0
            st.pop()
    return 1 if not st else 0


def score_output(no_special, clean, expects):
    nonempty = 1 if len(clean.strip()) >= 30 else 0
    no_hash = 1 if "###" not in clean else 0
    bal = balanced(clean) if nonempty else 0
    hit = sum(1 for k in expects if k in clean)
    exp = hit / len(expects) if expects else 1.0
    total = nonempty + no_special + no_hash + bal + exp
    return dict(nonempty=nonempty, no_special=no_special, no_hash=no_hash,
                balanced=bal, expected=round(exp, 2), total=round(total, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-new", type=int, default=1024)  # 긴 실파일 변환 잘림 방지(짧은건 eos로 조기정지)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(model, str(ROOT / args.adapter))
    model.eval()

    eos_id = tok.eos_token_id
    suppress = set(int(i) for i in (tok.all_special_ids or []))
    for t in FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            suppress.add(int(tid))
    suppress.discard(int(eos_id))
    suppress_tokens = sorted(suppress)
    special_noeos = set(int(i) for i in (tok.all_special_ids or [])) - {int(eos_id)}

    rows, grand = [], 0.0
    for name, instr, inp, expects in TASKS:
        if inp:
            code = (EGOV / inp).read_text(encoding="utf-8")
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{code}\n\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{instr}\n\n### Response:\n"
        inputs = {k: v.to(model.device) for k, v in tok(prompt, return_tensors="pt").items()}
        in_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new, min_new_tokens=24,
                                 do_sample=False, pad_token_id=eos_id, eos_token_id=eos_id,
                                 suppress_tokens=suppress_tokens, repetition_penalty=1.1)
        gen = out[0][in_len:]
        # 특수토큰 누수 = eos 외 특수토큰이 생성에 섞였는가(토큰 ID 기반; eos 정상종료는 제외)
        leak = any(int(t) in special_noeos for t in gen.tolist())
        no_special = 0 if leak else 1
        clean = tok.decode(gen, skip_special_tokens=True)
        for m in FIM:
            j = clean.find(m)
            if j != -1:
                clean = clean[:j]
        sc = score_output(no_special, clean, expects)
        sc["task"] = name
        sc["in_tok"] = in_len
        rows.append(sc)
        grand += sc["total"]
        print(f"[{name:16s}] total={sc['total']:.2f}  "
              f"ne={sc['nonempty']} sp={sc['no_special']} hash={sc['no_hash']} "
              f"bal={sc['balanced']} exp={sc['expected']}  (in={in_len}tok)", flush=True)

    maxp = len(TASKS) * 5
    pct = round(100 * grand / maxp, 1)
    print(f"\n[{args.label}] TOTAL {grand:.2f}/{maxp} = {pct}%", flush=True)

    outdir = ROOT / "eval_results"
    outdir.mkdir(exist_ok=True)
    (outdir / f"{args.label}.json").write_text(
        json.dumps({"label": args.label, "adapter": args.adapter,
                    "total": grand, "max": maxp, "pct": pct, "tasks": rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved → eval_results/{args.label}.json", flush=True)


if __name__ == "__main__":
    main()
