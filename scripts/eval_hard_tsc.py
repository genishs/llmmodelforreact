# -*- coding: utf-8 -*-
"""
tsc 하드평가 — 어댑터가 생성한 .tsx를 실제 `tsc --noEmit`로 컴파일해 타입에러 수로 채점.

자동 하베스트(eval_harness.py)가 100% 천장이라 강한 어댑터 변별이 불가 → 진짜 컴파일러로
"모델이 작성한 TypeScript 자체의 정합성"을 측정한다. 샌드박스(tsc_eval/)는 react/@types/react를
실제 설치 + `declare module '*'` 폴백 → 외래 모듈 노이즈 제거, JSX/훅/interface/제네릭만 채점.

각 태스크(전부 TS 생성):
  - syntax_ok : 구문/파싱 에러(TS1xxx) 없음 → 1, 있음 → 0
  - errors    : 해당 파일의 tsc 에러 총수 (낮을수록 좋음)
  - clean     : errors==0 → 1
  - score(0..1): 1.0 if clean else max(0, 1 - errors/CAP)   (CAP=5)
전체: clean 컴파일 수 / 총에러 / 점수% + JSON 저장.

실행:
  python scripts/eval_hard_tsc.py --adapter models/qwen-react-lora-7b-r32-round2 --label r32round2-tsc
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
BASE = str(ROOT / "models" / "base" / "qwen2.5-coder-7b")
EGOV = Path("d:/Documents/workspace/TwinSpace-platform/egovGeoportal/src")
SANDBOX = ROOT / "tsc_eval"
CASES = SANDBOX / "cases"
TSC = ROOT / "node_modules" / "typescript" / "bin" / "tsc"
CAP = 5  # 에러 CAP: 5개 이상이면 점수 0

FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>", "<|im_start|>"]

TS_CONV = "이 React 컴포넌트를 TypeScript(.tsx)로 변환해줘. props 타입을 interface로 정의하고 모든 함수/상태에 타입을 붙여줘. 코드만 출력해."

# 버그수정 태스크용 inline 입력(strict 위반 다수 — 모델이 고쳐 컴파일되게 해야 함)
BUGGY_TS = """import React, { useState } from 'react';

interface User { id: number; name: string; age: number; }

function UserCard({ user }) {
  const [count, setCount] = useState('0');
  const handleClick = () => setCount(count + 1);
  const isAdult: string = user.age >= 18;
  const label: number = user.name;
  return (
    <div onClick={handleClick}>
      {user.name} ({count}) {label}
      {isAdult && <span>Adult</span>}
    </div>
  );
}

export default UserCard;
"""

# (name, instruction, egov 상대경로 or "", inline 입력 or "")  — 전부 TS 생성/수정 태스크
TASKS = [
    # --- 합성 기본 4 (짧음) ---
    ("counter-ts", "Write a typed React counter component in TypeScript with a Props interface (initial: number). Output code only.", "", ""),
    ("usedebounce-ts", "Create a generic custom hook useDebounce<T>(value: T, delay: number): T in TypeScript. Output code only.", "", ""),
    ("tanstack-ts", "TanStack Query의 useInfiniteQuery로 무한 스크롤 상품 목록 컴포넌트를 TypeScript로 만들어줘. Product interface와 페이지 응답 타입을 정의하고 로딩/에러를 처리해줘. 코드만 출력.", "", ""),
    ("form-ts", "Build a typed controlled login form component in TypeScript. Define a FormState interface and type all event handlers (React.ChangeEvent, React.FormEvent). Output code only.", "", ""),
    # --- egov 실파일 변환 2 ---
    ("egov-paging-ts", TS_CONV, "components/EgovPaging.jsx", ""),
    ("egov-download-ts", TS_CONV, "pages/support/download/EgovDownloadDetail.jsx", ""),
    # --- 장문/복잡 5 (제네릭·판별유니온·컨텍스트·버그수정) ---
    ("reducer-union-ts", "TypeScript로 todo 리스트의 useReducer를 작성해줘. Action을 판별유니온(discriminated union)으로 정의하고(ADD/REMOVE/TOGGLE, 각 payload 타입 다름), reducer의 switch가 모든 케이스를 타입안전하게 처리하도록. State와 Action 타입을 export. 코드만 출력.", "", ""),
    ("datatable-generic-ts", "Build a reusable generic <DataTable<T>> React component in TypeScript. Props: rows: T[] and columns: { key: keyof T; header: string; render?: (value: T[keyof T], row: T) => React.ReactNode }[]. Render a table with typed cells. Output code only.", "", ""),
    ("auth-context-ts", "TypeScript로 타입이 완전한 React AuthContext를 만들어줘. User 타입, AuthContextValue 인터페이스(user: User | null, login, logout), Provider 컴포넌트, 그리고 Provider 밖에서 쓰면 throw하는 useAuth() 훅. createContext의 기본값과 null 가드까지 타입안전하게. 코드만 출력.", "", ""),
    ("usefetch-union-ts", "Create a generic custom hook useFetch<T>(url: string) in TypeScript that returns a discriminated union state: { status: 'loading' } | { status: 'error'; error: Error } | { status: 'success'; data: T }. Use useState and useEffect. Output code only.", "", ""),
    ("bugfix-types-ts", "다음 TypeScript 컴포넌트는 strict 모드에서 타입에러가 여러 개 있어. 모든 타입에러를 고쳐서 컴파일되게 만들어줘(props에 interface 추가 포함). 수정된 전체 코드만 출력해.", "", BUGGY_TS),
]


def build_model(adapter):
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(model, str(ROOT / adapter))
    model.eval()
    return tok, model


def gen_setup(tok):
    eos_id = tok.eos_token_id
    suppress = set(int(i) for i in (tok.all_special_ids or []))
    for t in FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            suppress.add(int(tid))
    suppress.discard(int(eos_id))
    return eos_id, sorted(suppress)


def strip_fences(text):
    """```tsx ... ``` 펜스 제거 + FIM 절단."""
    for m in FIM:
        j = text.find(m)
        if j != -1:
            text = text[:j]
    # 코드펜스 안만 추출(있으면)
    fence = re.search(r"```(?:tsx?|typescript|jsx?)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    # 펜스 없으면 그대로(앞쪽 설명문 제거 시도: 첫 import/interface/const/export부터)
    m = re.search(r"^(import |interface |type |const |export |function )", text, re.MULTILINE)
    return text[m.start():].strip() if m else text.strip()


def run_tsc():
    """샌드박스 전체 컴파일 → {파일명: [에러코드들]} 반환."""
    proc = subprocess.run(
        ["node", str(TSC), "-p", str(SANDBOX / "tsconfig.json"), "--pretty", "false"],
        cwd=str(SANDBOX), capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    per_file = {}
    for line in out.splitlines():
        m = re.match(r"cases[/\\]([^()]+)\((\d+),(\d+)\):\s*error\s+(TS\d+)", line.strip())
        if m:
            fname, code = m.group(1), m.group(4)
            per_file.setdefault(fname, []).append(code)
    return per_file


def egov_inputs_meta():
    """eval에 쓰인 egov 입력 파일의 sha256 → 노드 간 '같은 코드' 핸드셰이크용."""
    import hashlib
    meta = {}
    for _, _, inp, _inline in TASKS:
        if inp:
            raw = (EGOV / inp).read_bytes()
            norm = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")  # 모델이 보는 LF-정규화 입력
            meta[inp] = {"sha256_lf": hashlib.sha256(norm).hexdigest()[:16],
                         "bytes_lf": len(norm), "bytes_raw": len(raw)}
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-new", type=int, default=1024)
    args = ap.parse_args()

    CASES.mkdir(parents=True, exist_ok=True)
    # ★ 격리: cases/의 모든 .tsx 제거(디렉터리 전체 컴파일이라 다른 라벨이 남으면 결과 오염됨).
    #   각 라벨은 자기 6개 파일만 단독 컴파일되어야 점수가 신뢰 가능.
    for f in CASES.glob("*.tsx"):
        f.unlink()

    tok, model = build_model(args.adapter)
    eos_id, suppress_tokens = gen_setup(tok)

    files = []  # (task, filename)
    for name, instr, inp, inline in TASKS:
        if inp:
            # ★ EOL 정규화(LF): git hash-object는 autocrlf로 EOL을 숨기지만 모델은 raw 바이트를
            #   토크나이즈하므로 CRLF/LF가 입력에 반영됨. 양 노드 LF로 통일해야 진짜 바이트 동일.
            code = (EGOV / inp).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{code}\n\n### Response:\n"
        elif inline:
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{inline}\n\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{instr}\n\n### Response:\n"
        inputs = {k: v.to(model.device) for k, v in tok(prompt, return_tensors="pt").items()}
        in_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new, min_new_tokens=24,
                                 do_sample=False, pad_token_id=eos_id, eos_token_id=eos_id,
                                 suppress_tokens=suppress_tokens, repetition_penalty=1.1)
        gen = tok.decode(out[0][in_len:], skip_special_tokens=True)
        src = strip_fences(gen)
        fname = f"{args.label}__{name}.tsx"
        (CASES / fname).write_text(src, encoding="utf-8")
        files.append((name, fname, in_len, len(src)))
        print(f"  generated [{name:18s}] {len(src):5d} chars (in={in_len}tok)", flush=True)

    print("  running tsc ...", flush=True)
    per_file = run_tsc()

    rows, grand = [], 0.0
    for name, fname, in_len, nchars in files:
        codes = per_file.get(fname, [])
        errors = len(codes)
        syntax_ok = 0 if any(c.startswith("TS1") and c < "TS2000" for c in codes) else 1
        # TS1xxx = 구문/파싱 에러
        syntax_err = [c for c in codes if re.match(r"TS1\d{3}$", c)]
        syntax_ok = 0 if syntax_err else 1
        clean = 1 if errors == 0 and nchars > 30 else 0
        empty = 1 if nchars <= 30 else 0
        score = 1.0 if clean else max(0.0, 1 - errors / CAP)
        if empty:
            score = 0.0
            syntax_ok = 0
        rows.append(dict(task=name, errors=errors, syntax_ok=syntax_ok, clean=clean,
                         score=round(score, 2), chars=nchars, codes=codes))
        grand += score
        flag = "CLEAN" if clean else ("EMPTY" if empty else ("SYNTAX!" if not syntax_ok else f"{errors}err"))
        print(f"[{name:18s}] {flag:8s} score={score:.2f}  errs={errors} {','.join(codes[:6])}", flush=True)

    maxp = len(TASKS)
    pct = round(100 * grand / maxp, 1)
    n_clean = sum(r["clean"] for r in rows)
    tot_err = sum(r["errors"] for r in rows)
    egov_meta = egov_inputs_meta()
    print(f"\n[{args.label}] CLEAN {n_clean}/{maxp} compiles | total_errors={tot_err} | "
          f"SCORE {grand:.2f}/{maxp} = {pct}%", flush=True)
    print(f"  egov inputs: {egov_meta}", flush=True)

    outdir = ROOT / "eval_results"
    outdir.mkdir(exist_ok=True)
    (outdir / f"{args.label}.json").write_text(
        json.dumps({"label": args.label, "adapter": args.adapter, "kind": "tsc_hard",
                    "clean_compiles": n_clean, "total_errors": tot_err,
                    "score": round(grand, 2), "max": maxp, "pct": pct,
                    "egov_inputs": egov_meta, "tasks": rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved → eval_results/{args.label}.json", flush=True)


if __name__ == "__main__":
    main()
