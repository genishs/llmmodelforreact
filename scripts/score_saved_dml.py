# -*- coding: utf-8 -*-
"""
저장된 생성본(eval_results/gen/<label>__*.tsx) 오프라인 채점 — 모델 미적재.
용도: 14B DML eval이 마지막 대형 태스크(ho-admin-medit 22KB)에서 OS SIGKILL로
죽어 결과 json이 안 나왔을 때, 이미 생성·저장된 태스크들만 같은 채점기준(EHT)으로
점수화해 살린다. 채점 로직은 eval_hard_tsc(EHT)를 그대로 import해 100% 동일.

실행: python scripts/score_saved_dml.py --label 8060-14b-v1-seq256e2 [--exclude ho-admin-medit]
결과: eval_results/<label>.partial.json + 표 출력
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import eval_hard_tsc as EHT  # noqa: E402  동일 채점기준


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--exclude", default="", help="쉼표구분 제외 태스크명")
    ap.add_argument("--base-tag", default="fp16-directml")
    args = ap.parse_args()

    excl = {s.strip() for s in args.exclude.split(",") if s.strip()}
    gen = EHT.ARCHIVE_DIR
    prefix = f"{args.label}__"
    found = sorted(gen.glob(f"{prefix}*.tsx"))
    files = []  # (task, fname, nchars)
    for p in found:
        task = p.name[len(prefix):-4]  # strip prefix + ".tsx"
        if task in excl:
            continue
        nchars = len(p.read_text(encoding="utf-8"))
        files.append((task, p.name, nchars))
    if not files:
        print(f"[오류] {gen}/{prefix}*.tsx 생성본 없음"); sys.exit(2)

    print(f"[채점] {len(files)}개 저장본 (제외: {sorted(excl) or '없음'})", flush=True)
    per_file = EHT.run_tsc([f[1] for f in files])

    rows, grand = [], 0.0
    for task, fname, nchars in files:
        codes = per_file.get(fname, [])
        errors = len(codes)
        syntax_err = [c for c in codes if re.match(r"TS1\d{3}$", c)]
        syntax_ok = 0 if syntax_err else 1
        clean = 1 if errors == 0 and nchars > 30 else 0
        empty = 1 if nchars <= 30 else 0
        score = 1.0 if clean else max(0.0, 1 - errors / EHT.CAP)
        if empty:
            score = 0.0; syntax_ok = 0
        rows.append(dict(task=task, errors=errors, syntax_ok=syntax_ok, clean=clean,
                         score=round(score, 2), chars=nchars, codes=codes))
        grand += score
        flag = "CLEAN" if clean else ("EMPTY" if empty else ("SYNTAX!" if not syntax_ok else f"{errors}err"))
        print(f"[{task:18s}] {flag:8s} score={score:.2f}  errs={errors} {','.join(codes[:6])}", flush=True)

    maxp = len(files)
    pct = round(100 * grand / maxp, 1)
    n_clean = sum(r["clean"] for r in rows)
    tot_err = sum(r["errors"] for r in rows)
    print(f"\n[{args.label} | PARTIAL {maxp}태스크] CLEAN {n_clean}/{maxp} | "
          f"total_errors={tot_err} | SCORE {grand:.2f}/{maxp} = {pct}%", flush=True)

    out = ROOT / "eval_results" / f"{args.label}.partial.json"
    out.write_text(json.dumps(
        {"label": args.label, "kind": "tsc_hard", "base": args.base_tag,
         "partial": True, "excluded": sorted(excl),
         "clean_compiles": n_clean, "total_errors": tot_err,
         "score": round(grand, 2), "max": maxp, "pct": pct, "tasks": rows},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved → eval_results/{args.label}.partial.json", flush=True)


if __name__ == "__main__":
    main()
