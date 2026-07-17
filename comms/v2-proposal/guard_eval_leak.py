# -*- coding: utf-8 -*-
"""
guard_eval_leak.py — 학습셋 ↔ eval 태스크셋 오염 차단 가드 (PROPOSAL / 미적용).

배경: build_dataset_v2 의 SYNTH_GLOB='./data/handcrafted_synth*.jsonl' 은
      handcrafted_admin_round6.jsonl 을 매칭하지 않는다. 그런데 admin_round6 에는
      EgovAdminNoticeDetail/PasswordUpdate 실파일이 학습타깃으로, EgovAdminAppStatList 는
      '입력=실파일, 출력=EgovAdminMenuStatList 로 리네임' 위장 형태로 들어 있다.
      → 파일명/식별자 스캔만으로는 리네임 위장을 못 잡는다. content-hash 가 필수.

3중 검사 (belt-and-suspenders):
  (1) instruction 의 (X.jsx) 파일명 참조
  (2) output 에 정의된 컴포넌트 식별자(function/const X)
  (3) LF정규화 SHA256(input) == eval 원본 파일 해시   ← 리네임 위장까지 포획

기본 스캔대상 = data/*.jsonl 전체(UNION). 특정 라운드만 학습해도, 영구 held-out 은
'과거·미래 모든 학습 데이터의 합집합' 에 대해 클린이어야 하므로 union 검사가 정답.

사용:
  from guard_eval_leak import assert_no_eval_leak
  assert_no_eval_leak(eval_srcs=[...절대경로 .jsx...])          # build_dataset_v2.main() 진입부
  # 또는 CLI:  python scripts/guard_eval_leak.py --taskset scripts/tasksets_v2.json
"""
import glob
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_GLOB = str(ROOT / "data" / "*.jsonl")
_NAME_IN_INSTR = re.compile(r"\(([A-Za-z][A-Za-z0-9]*)\.jsx\)")
_COMP_IN_OUT = re.compile(r"(?:function|const)\s+([A-Z][A-Za-z0-9]+)\s*[(:=]")


def _lf(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _sha(s: str) -> str:
    return hashlib.sha256(_lf(s).encode("utf-8")).hexdigest()


def collect_train_signals(data_glob=DEFAULT_DATA_GLOB):
    names, hashes = set(), set()
    for df in glob.glob(data_glob):
        if df.endswith(".bak"):
            continue
        with open(df, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for m in _NAME_IN_INSTR.findall(rec.get("instruction", "")):
                    names.add(m)
                for m in _COMP_IN_OUT.findall(rec.get("output", "")):
                    names.add(m)
                if rec.get("input"):
                    hashes.add(_sha(rec["input"]))
    return names, hashes


def assert_no_eval_leak(eval_srcs, data_glob=DEFAULT_DATA_GLOB, extra_names=()):
    """eval_srcs 중 하나라도 학습셋에 (파일명/식별자/내용해시) 걸리면 RuntimeError.

    extra_names: 파일명충돌 오탐 화이트리스트가 아니라, 추가로 금지할 basename(예: 'App' 은
                 합성 function App() 과 충돌 → eval 로 쓰지 말라는 의미로 넣을 수 있음).
    """
    names, hashes = collect_train_signals(data_glob)
    leaks = []
    for p in eval_srcs:
        p = Path(p)
        base = p.stem
        txt = p.read_text(encoding="utf-8")
        via = []
        if base in names:
            via.append("name/ident")
        if _sha(txt) in hashes:
            via.append("content-hash(renamed-safe)")
        if base in extra_names:
            via.append("blocklist")
        if via:
            leaks.append((base, str(p), "+".join(via)))
    if leaks:
        msg = ["EVAL LEAK GUARD FAILED — 아래 eval 태스크가 학습셋에 오염됨:"]
        for b, path, via in leaks:
            msg.append(f"  - {b}  ({via})  {path}")
        msg.append("→ 오염 파일을 eval 태스크셋에서 제거하거나 학습셋에서 빼세요. (영구 held-out 무결성)")
        raise RuntimeError("\n".join(msg))
    return True


def _eval_srcs_from_taskset(taskset_json, egov_root):
    spec = json.loads(Path(taskset_json).read_text(encoding="utf-8"))
    egov = Path(egov_root)
    srcs = []
    for tsid, ts in spec.get("tasksets", {}).items():
        if tsid == "heldout7":   # 앵커는 이미 검증됨(무결성 확인). 신규 셋만 재검증하려면 이 continue 유지.
            pass
        for rel in ts.get("tasks", {}).values():
            srcs.append(egov / rel)
    return srcs


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--taskset", default=str(ROOT / "scripts" / "tasksets_v2.json"))
    ap.add_argument("--egov", default=os.environ.get("EGOV_SRC", "d:/Documents/workspace/TwinSpace-platform/egovGeoportal/src"))
    ap.add_argument("--data-glob", default=DEFAULT_DATA_GLOB)
    args = ap.parse_args()
    srcs = _eval_srcs_from_taskset(args.taskset, args.egov)
    assert_no_eval_leak(srcs, data_glob=args.data_glob)
    print(f"OK — {len(srcs)} eval 태스크 전부 학습셋과 0오염 (data_glob={args.data_glob})")

# ── build_dataset_v2.main() 에 끼울 3줄 스니펫 (제안, 미적용) ──────────────────
#   from guard_eval_leak import assert_no_eval_leak, _eval_srcs_from_taskset
#   egov = os.environ.get("EGOV_SRC", "d:/.../egovGeoportal/src")
#   assert_no_eval_leak(_eval_srcs_from_taskset("scripts/tasksets_v2.json", egov))
#   # ↑ 데이터 기록(write) '전에' 호출 → 오염 시 학습셋 산출 자체를 막음.
