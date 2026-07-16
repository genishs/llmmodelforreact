# -*- coding: utf-8 -*-
"""
score_v2.py — 하니스 v2 채점기 (순수 함수 · GPU 0 · 모델 미적재).

저장된 생성물 `eval_results/gen/<label>__<task>.tsx` 와 원본 `.jsx` 만 읽어 재점수한다.
모델 로드 0 / 생성 0 / GPU 0. TypeScript 컴파일러 파싱은 Node 프론트엔드
`scripts/score_v2_extract.cjs` 에 위임하고, 이 파일은 **점수 산술만** 담당한다(감사 가능).

────────────────────────────────────────────────────────────────────────
왜 v2 (v1 `max(0, 1-err/5)` 이 무효 판정된 이유):
  1. seed 분산 Δ20.0pp (동일 데이터·설정, seed만 바꿔 88.6→68.6).
  2. 백틱 아티팩트: 안 닫힌 백틱 → 파서가 EOF까지 삼켜 에러 은폐 → 더 망가질수록 점수↑.
  3. 충실도 미측정: `return <div/>` 스텁이 만점 가능.
  4. 태스크 7개뿐 → 하나가 0.8 흔들리면 11.4pp 요동.

v2 점수식(상수는 선험적 고정 — 과거 결론 보존 피팅 금지):
  trunc    : max_new 도달 & EOS 없음 (생성기 플래그 — eval_results/<label>.json 의 per-task truncated).
             플래그 없는 아카이브는 truncation 이 파스 실패(not syn_ok)로 발현되어 동일 분기로 라우팅됨.
  syn_ok   : 구문 진단(getSyntacticDiagnostics) == 0
  syn_frac : 첫 구문진단 위치 / 파일길이  [0..1]
  type_err : 타입 진단(getSemanticDiagnostics, TS2347 제외) 수 — syn_ok 일 때만 정의
  fidelity : 원본 .jsx 대비 = sqrt(ident_keep * jsx_keep)
             ident_keep = |원본 식별자집합 ∩ 생성 식별자집합| / |원본 식별자집합|   (집합 = 어휘 보존)
             jsx_keep   = Σ min(원본태그수, 생성태그수) / Σ 원본태그수               (다중집합 = 구조 완성도)

  if trunc or not syn_ok:  score = 0.20 * syn_frac
  else:                    score = fidelity * (0.30 + 0.70 * exp(-type_err/4))

하위호환: pct_v1(현행 공식 재현) · pct_v2 를 병기해 크로스워크.
--only 버그 수정: 결과 키를 (label, taskset_id) 로 (v1 은 label 단독이라 부분측정이 전체를 덮어씀).

실행:
  python scripts/score_v2.py --labels r6base-heldout7-mn4096,14b-rocm-bf16-mlp-seq1024
  python scripts/score_v2.py --label r6base-heldout7-mn4096 --only ho-admin-medit  # 단일태스크
결과: comms/scores-4060-v2.jsonl (append, 불변 원장과 분리) + 표 출력.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SANDBOX = ROOT / "tsc_eval"
ARCHIVE_DIR = ROOT / "eval_results" / "gen"
EXTRACT_JS = ROOT / "scripts" / "score_v2_extract.cjs"

HARNESS_VER = "V2-tscAPI-fidelity-synfrac-r1"

# 점수식 상수 — 선험적 고정. 과거 결론 보존 피팅 금지(순환논증 방지).
C_TRUNC_SYN = 0.20    # trunc/구문붕괴 시 syn_frac 계수
C_BASE = 0.30         # syn_ok 시 바닥(타입에러 무한대여도 이만큼)
C_TYPE = 0.70         # 타입 청결도 가중
TAU = 4.0             # exp(-type_err/TAU)

# ── 태스크 → 원본 egov 상대경로 (eval_hard_tsc.py 의 HELDOUT_TASKS/TASKS 미러.
#    torch/transformers 를 끌어오지 않으려 인라인. 아카이브 동결 상태라 드리프트 위험 낮음) ──
HELDOUT_SRC = {
    "ho-select":      "components/EgovSelect.jsx",
    "ho-gallery":     "components/EgovImageGallery.jsx",
    "ho-about-org":   "pages/about/EgovAboutOrganization.jsx",
    "ho-attachfile":  "components/EgovAttachFile.jsx",
    "ho-admin-dae":   "pages/admin/dataaccess/EgovAdminDataAccessEdit.jsx",
    "ho-admin-mlist": "pages/admin/members/EgovAdminMemberList.jsx",
    "ho-admin-medit": "pages/admin/members/EgovAdminMemberEdit.jsx",
}
HARD11_SRC = {  # hard-11 중 egov 실파일 변환 2개만 fidelity 기준을 가짐(나머지는 합성/인라인 → NA)
    "egov-paging-ts":   "components/EgovPaging.jsx",
    "egov-download-ts": "pages/support/download/EgovDownloadDetail.jsx",
}
HELDOUT_TASKS = list(HELDOUT_SRC.keys())
HARD11_TASKS = [  # eval_hard_tsc.TASKS 순서
    "counter-ts", "usedebounce-ts", "tanstack-ts", "form-ts",
    "egov-paging-ts", "egov-download-ts",
    "reducer-union-ts", "datatable-generic-ts", "auth-context-ts",
    "usefetch-union-ts", "bugfix-types-ts",
]


def resolve_egov():
    """egov 실파일 소스 루트(eval_hard_tsc._resolve_egov 미러)."""
    cands = []
    if os.environ.get("EGOV_SRC"):
        cands.append(Path(os.environ["EGOV_SRC"]))
    cands += [
        ROOT.parent.parent / "twinspace_platform" / "egovGeoportal" / "src",
        Path("/run/media/user/새 볼륨/Documents/workspace/twinspace_platform/egovGeoportal/src"),
        Path("d:/Documents/workspace/TwinSpace-platform/egovGeoportal/src"),
    ]
    for c in cands:
        if c.exists():
            return c
    return cands[-1]


EGOV = resolve_egov()


def taskset_of(task):
    if task in HELDOUT_SRC:
        return "heldout7"
    if task in HARD11_TASKS:
        return "hard11"
    return "other"


def src_path_for(task):
    """task 의 원본 .jsx 절대경로(있으면). 없으면 None(→ fidelity NA)."""
    rel = HELDOUT_SRC.get(task) or HARD11_SRC.get(task)
    if not rel:
        return None
    p = EGOV / rel
    return p if p.exists() else None


def load_trunc_flags(label):
    """생성기가 기록한 per-task truncated 플래그. eval_results/<label>.json 에서 읽음(없으면 {})."""
    jp = ROOT / "eval_results" / f"{label}.json"
    flags = {}
    if jp.exists():
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            for t in data.get("tasks", []):
                if "truncated" in t:
                    flags[t["task"]] = bool(t["truncated"])
        except Exception:
            pass
    return flags


# ─────────────────────────── 순수 점수식 ───────────────────────────
def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def compute_fidelity(src_idents, src_jsx, gen_idents, gen_jsx):
    """sqrt(ident_keep * jsx_keep). 원본 없으면 (None, None, None)=NA."""
    if src_idents is None:
        return None, None, None
    src_set = set(src_idents)
    gen_set = set(gen_idents)
    ident_keep = (len(src_set & gen_set) / len(src_set)) if src_set else 1.0
    src_ctr, gen_ctr = Counter(src_jsx or []), Counter(gen_jsx or [])
    denom = sum(src_ctr.values())
    if denom:
        covered = sum(min(c, gen_ctr.get(t, 0)) for t, c in src_ctr.items())
        jsx_keep = covered / denom
    else:
        jsx_keep = 1.0
    fidelity = math.sqrt(ident_keep * jsx_keep)
    return ident_keep, jsx_keep, fidelity


def score_v1(errors, file_len):
    """현행 eval_hard_tsc 공식 재현: clean→1.0, empty(≤30자)→0.0, else max(0,1-err/5)."""
    if file_len <= 30:
        return 0.0
    if errors == 0:
        return 1.0
    return max(0.0, 1.0 - errors / 5.0)


def score_v2(fact, trunc):
    """fact = extractor per-file 결과. (row dict, score) 반환."""
    file_len = fact["file_len"]
    syn = fact["syn"]
    sem = fact["sem"]
    syn_ok = (len(syn) == 0)
    syn_first = fact["syn_first"]
    syn_frac = clamp01(syn_first / file_len) if (syn_first is not None and file_len > 0) else 1.0
    type_err = len(sem) if syn_ok else None

    ident_keep, jsx_keep, fidelity = compute_fidelity(
        fact["src_idents"], fact["src_jsx"], fact["gen_idents"], fact["gen_jsx"])
    has_src = fidelity is not None
    fid_eff = fidelity if has_src else 1.0
    # NA-fidelity(합성/인라인) 태스크가 빈 스텁이면 fidelity 로 못 잡으므로 별도 0 처리.
    if not has_src and file_len <= 30:
        fid_eff = 0.0

    if trunc or not syn_ok:
        sv2 = C_TRUNC_SYN * syn_frac
    else:
        sv2 = fid_eff * (C_BASE + C_TYPE * math.exp(-(type_err or 0) / TAU))

    # v1(tsc CLI) 재현: CLI 는 구문에러가 있는 파일의 semantic 검사를 건너뛴다(실측 — 이게 백틱버그의
    # 정확한 메커니즘: 안 닫힌 백틱 1개=구문에러 1개로만 세어져 뒤의 쓰레기가 전부 은폐됨).
    # ∴ errors_v1 = len(syn) if syn else len(sem)  (r6base=88.6%·r4mlp=71.4% 저장값과 완전 일치 검증됨)
    errors_v1 = len(syn) if syn else len(sem)
    sv1 = score_v1(errors_v1, file_len)

    row = dict(
        task=fact["task"],
        syn_ok=syn_ok,
        syn_frac=round(syn_frac, 4),
        type_err=type_err,
        ident_keep=(round(ident_keep, 4) if ident_keep is not None else None),
        jsx_keep=(round(jsx_keep, 4) if jsx_keep is not None else None),
        fidelity=(round(fidelity, 4) if fidelity is not None else None),
        trunc=bool(trunc),
        file_len=file_len,
        errors_v1=errors_v1,
        syn_codes=[f"TS{s['code']}" for s in syn],
        sem_codes=[f"TS{c}" for c in sem],
        score_v1=round(sv1, 4),
        score_v2=round(sv2, 4),
    )
    return row, sv1, sv2


# ─────────────────────────── 드라이버 ───────────────────────────
def run_extractor(entries):
    """entries: [{task,label,gen,src}]. → extractor JSON."""
    manifest = {
        "tsconfig": str(SANDBOX / "tsconfig.json"),
        "shims": str(SANDBOX / "shims.d.ts"),
        "files": entries,
    }
    tmp = ROOT / "eval_results" / f"_v2_manifest_{os.getpid()}.json"
    tmp.write_text(json.dumps(manifest), encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(EXTRACT_JS), str(tmp)],
                              capture_output=True, text=True, cwd=str(ROOT))
    finally:
        tmp.unlink(missing_ok=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + "\n" + proc.stderr + "\n")
        raise SystemExit(f"extractor failed (rc={proc.returncode})")
    return json.loads(proc.stdout)


def score_label(label, only=None):
    """한 라벨의 저장 생성물을 재점수. (label,taskset_id) 별로 rows 그룹 반환."""
    prefix = f"{label}__"
    found = sorted(ARCHIVE_DIR.glob(f"{prefix}*.tsx"))
    if not found:
        print(f"[skip] {label}: 아카이브 없음 ({ARCHIVE_DIR}/{prefix}*.tsx)")
        return []
    trunc_flags = load_trunc_flags(label)
    have_flags = bool(trunc_flags)

    entries, meta = [], []
    for p in found:
        task = p.name[len(prefix):-4]
        if only and task not in only:
            continue
        sp = src_path_for(task)
        entries.append({"task": task, "label": label,
                        "gen": str(p), "src": (str(sp) if sp else None)})
        meta.append((task, taskset_of(task), have_flags))
    if not entries:
        return []

    ext = run_extractor(entries)
    facts = {f["task"]: f for f in ext["results"]}
    ts_version = ext["ts_version"]

    # (taskset_id) 별 그룹핑 — --only 덮어쓰기 버그 수정의 키
    groups = {}
    for task, tsid, have in meta:
        fact = facts[task]
        trunc = trunc_flags.get(task, False)
        row, sv1, sv2 = score_v2(fact, trunc)
        row["trunc_source"] = "flag" if (task in trunc_flags) else ("none" if not have else "flag")
        groups.setdefault(tsid, []).append((row, sv1, sv2))

    out_rows = []
    for tsid, items in groups.items():
        rows = [r for r, _, _ in items]
        n = len(rows)
        pct_v1 = round(100 * sum(s for _, s, _ in items) / n, 1)
        pct_v2 = round(100 * sum(s for _, _, s in items) / n, 1)
        out_rows.append(dict(
            label=label, taskset_id=tsid, harness_ver=HARNESS_VER,
            ts_version=ts_version, node="4060",
            n_tasks=n, only=(sorted(only) if only else None),
            pct_v1=pct_v1, pct_v2=pct_v2,
            trunc_flags_available=any(m[2] for m in meta),
            ts=time.strftime("%Y-%m-%dT%H:%M:%S"),
            tasks=rows,
        ))
    return out_rows


def print_rows(out_rows):
    for r in out_rows:
        print(f"\n══ {r['label']}  [{r['taskset_id']}]  n={r['n_tasks']}"
              f"{'  only='+','.join(r['only']) if r['only'] else ''} ══")
        print(f"   {'task':16s} {'v1':>5s} {'v2':>5s}  {'synOK':5s} {'synFr':>5s} "
              f"{'typeE':>5s} {'ident':>5s} {'jsx':>5s} {'fidel':>5s} trunc  codes")
        for t in r["tasks"]:
            te = "-" if t["type_err"] is None else str(t["type_err"])
            ik = "-" if t["ident_keep"] is None else f"{t['ident_keep']:.2f}"
            jk = "-" if t["jsx_keep"] is None else f"{t['jsx_keep']:.2f}"
            fd = "-" if t["fidelity"] is None else f"{t['fidelity']:.2f}"
            codes = ",".join((t["syn_codes"] + t["sem_codes"])[:5])
            print(f"   {t['task']:16s} {t['score_v1']:5.2f} {t['score_v2']:5.2f}  "
                  f"{('Y' if t['syn_ok'] else 'N'):^5s} {t['syn_frac']:5.2f} "
                  f"{te:>5s} {ik:>5s} {jk:>5s} {fd:>5s} {('T' if t['trunc'] else '.'):^5s}  {codes}")
        print(f"   ── pct_v1={r['pct_v1']}%   pct_v2={r['pct_v2']}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", action="append", default=[], help="라벨(반복 가능)")
    ap.add_argument("--labels", default="", help="쉼표구분 라벨 목록")
    ap.add_argument("--only", default="", help="쉼표구분 task 이름만 채점(부분측정)")
    ap.add_argument("--out", default=str(ROOT / "comms" / "scores-4060-v2.jsonl"),
                    help="결과 jsonl(append). 과거 원장과 분리된 v2 전용.")
    ap.add_argument("--no-write", action="store_true", help="jsonl 미기록(검증용)")
    args = ap.parse_args()

    labels = list(args.label) + [s.strip() for s in args.labels.split(",") if s.strip()]
    if not labels:
        ap.error("라벨을 --label 또는 --labels 로 지정하세요")
    only = set(s.strip() for s in args.only.split(",") if s.strip()) or None

    all_rows = []
    for label in labels:
        all_rows += score_label(label, only=only)
    print_rows(all_rows)

    if not args.no_write and all_rows:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open("a", encoding="utf-8") as fh:
            for r in all_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nappended {len(all_rows)} row(s) → {outp}")


if __name__ == "__main__":
    main()
