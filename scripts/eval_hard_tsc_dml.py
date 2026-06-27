# -*- coding: utf-8 -*-
"""
tsc 하드평가 — DirectML/fp16 트윈 (4060 eval_hard_tsc.py의 8060 버전).

★ 채점 로직(TASKS·strip_fences·gen_setup·run_tsc·egov_inputs_meta·CAP·scoring)을
   eval_hard_tsc.py에서 그대로 import해 점수 기준을 100% 동일하게 유지한다.
   차이는 모델 로딩뿐:
   - 4060: 4bit nf4 + device_map=auto (eval_hard_tsc.py)
   - 8060: fp16 스트리밍 적재 (이 파일) — 실서빙과 같은 정밀도, DirectML
   egov 실파일 경로도 이 장비(장비#1)로 오버라이드. EOL=LF 정규화는 EHT 로직 그대로.

실행:
  python scripts/eval_hard_tsc_dml.py --adapter models/qwen-react-lora-7b-r3 --label 8060-r3-tsc
결과: eval_results/<label>.json + 표 출력
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import torch
import torch_directml
from transformers import AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType, set_peft_model_state_dict
import safetensors.torch as st

from train_directml import stream_load_to_device, load_config
import eval_hard_tsc as EHT   # 채점 로직·태스크·tsc 실행 재사용(동일 기준)

# 이 장비(장비#1)의 egovGeoportal 경로로 오버라이드 (EHT.TASKS의 egov 입력에 사용)
EHT.EGOV = Path("C:/Users/user/Documents/workspace/twinspace_platform/egovGeoportal/src")
BASE = str(ROOT / "models" / "base" / "qwen2.5-coder-7b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-new", type=int, default=2048)  # EHT와 동일: 1024는 egov-download 잘림 → 부당감점
    ap.add_argument("--only", default="",
                    help="쉼표구분 태스크명만 실행(빈값=전체). 예: --only egov-download-ts")
    ap.add_argument("--heldout", action="store_true",
                    help="확장 held-out eval셋(egov 4파일 변환, EHT.HELDOUT_TASKS)으로 측정")
    ap.add_argument("--base", default="",
                    help="베이스 모델 경로 오버라이드(예: 14B). 빈값=기본 7B(BASE).")
    args = ap.parse_args()

    base = args.base if args.base else BASE

    base_tasks = EHT.HELDOUT_TASKS if args.heldout else EHT.TASKS
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    tasks = [t for t in base_tasks if (not only or t[0] in only)]
    ARCHIVE = EHT.ARCHIVE_DIR  # ★버그2 수정: run_tsc(per-file)가 여기서 단독컴파일 소스를 읽음
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    EHT.CASES.mkdir(parents=True, exist_ok=True)
    # ★ 격리(4060 함정#1 회피): cases/의 모든 .tsx 제거 → 자기 파일만 단독 컴파일.
    for f in EHT.CASES.glob("*.tsx"):
        f.unlink()

    config = load_config()
    device = torch_directml.device(); dtype = torch.float16
    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print(f"[로드] fp16 스트리밍 + 어댑터 {args.adapter} (base={base})", flush=True)
    model = stream_load_to_device(base, device, dtype)
    lc = config["lora"]
    acfg = json.loads((ROOT / args.adapter / "adapter_config.json").read_text())
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=acfg.get("r", lc["r"]),
        lora_alpha=acfg.get("lora_alpha", lc["lora_alpha"]),
        target_modules=acfg.get("target_modules", lc["target_modules"]),
        lora_dropout=lc["lora_dropout"], bias=lc["bias"]))
    sd = {k: v.to(dtype) for k, v in
          st.load_file(str(ROOT / args.adapter / "adapter_model.safetensors")).items()}
    set_peft_model_state_dict(model, sd)
    model = model.to(device); model.eval(); model.config.use_cache = True

    eos_id, suppress_tokens = EHT.gen_setup(tok)

    files = []  # (task, filename, in_len, nchars, truncated)
    for name, instr, inp, inline in tasks:
        if inp:
            # ★ EOL 정규화(LF) — EHT와 동일. 모델이 보는 raw 바이트를 4060과 통일.
            code = (EHT.EGOV / inp).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{code}\n\n### Response:\n"
        elif inline:
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{inline}\n\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{instr}\n\n### Response:\n"
        inputs = {k: v.to(device) for k, v in tok(prompt, return_tensors="pt").items()}
        in_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new, min_new_tokens=24,
                                 do_sample=False, pad_token_id=eos_id, eos_token_id=eos_id,
                                 suppress_tokens=suppress_tokens, repetition_penalty=1.1)
        new_tokens = out.shape[1] - in_len
        gen_ids = out[0][in_len:]
        # 잘림 판정(EHT 동일): eos 없이 max_new 도달 = 생성 잘림
        truncated = bool(int(eos_id) not in gen_ids.tolist() and new_tokens >= args.max_new)
        gen = tok.decode(gen_ids, skip_special_tokens=True)
        src = EHT.strip_fences(gen)
        fname = f"{args.label}__{name}.tsx"
        (EHT.CASES / fname).write_text(src, encoding="utf-8")
        (ARCHIVE / fname).write_text(src, encoding="utf-8")  # 영구보존
        files.append((name, fname, in_len, len(src), truncated))
        print(f"  generated [{name:18s}] {len(src):5d} chars "
              f"(in={in_len}tok new={new_tokens}{' TRUNC!' if truncated else ''})", flush=True)

    print("  running tsc (파일별 단독컴파일, 버그2 수정) ...", flush=True)
    per_file = EHT.run_tsc([f[1] for f in files])  # ★버그2 수정: fnames 전달, 파일별 단독컴파일

    import re
    rows, grand = [], 0.0
    for name, fname, in_len, nchars, truncated in files:
        # ★ 채점식은 EHT.main()과 동일 (CAP·clean·score 기준 일치)
        codes = per_file.get(fname, [])
        errors = len(codes)
        syntax_err = [c for c in codes if re.match(r"TS1\d{3}$", c)]
        syntax_ok = 0 if syntax_err else 1
        clean = 1 if errors == 0 and nchars > 30 else 0
        empty = 1 if nchars <= 30 else 0
        score = 1.0 if clean else max(0.0, 1 - errors / EHT.CAP)
        if empty:
            score = 0.0; syntax_ok = 0
        rows.append(dict(task=name, errors=errors, syntax_ok=syntax_ok, clean=clean,
                         score=round(score, 2), chars=nchars, truncated=truncated, codes=codes))
        grand += score
        flag = "CLEAN" if clean else ("EMPTY" if empty else ("SYNTAX!" if not syntax_ok else f"{errors}err"))
        print(f"[{name:18s}] {flag:8s} score={score:.2f}  errs={errors} "
              f"{'TRUNC ' if truncated else ''}{','.join(codes[:6])}", flush=True)

    maxp = len(files)
    pct = round(100 * grand / maxp, 1)
    n_clean = sum(r["clean"] for r in rows)
    tot_err = sum(r["errors"] for r in rows)
    egov_meta = EHT.egov_inputs_meta(base_tasks)
    print(f"\n[{args.label}] CLEAN {n_clean}/{maxp} compiles | total_errors={tot_err} | "
          f"SCORE {grand:.2f}/{maxp} = {pct}%", flush=True)
    print(f"  egov inputs(LF): {egov_meta}", flush=True)

    outdir = ROOT / "eval_results"; outdir.mkdir(exist_ok=True)
    (outdir / f"{args.label}.json").write_text(
        json.dumps({"label": args.label, "adapter": args.adapter, "kind": "tsc_hard",
                    "base": "fp16-directml", "clean_compiles": n_clean, "total_errors": tot_err,
                    "score": round(grand, 2), "max": maxp, "pct": pct,
                    "egov_inputs": egov_meta, "tasks": rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved → eval_results/{args.label}.json", flush=True)


if __name__ == "__main__":
    main()
