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

기본 스캔대상 = <root>/data/*.jsonl + <root>/data/processed/*.jsonl 전체(UNION).
특정 라운드만 학습해도, 영구 held-out 은 '과거·미래 모든 학습 데이터의 합집합' 에 대해
클린이어야 하므로 union 검사가 정답. processed/*.jsonl(실제 학습입력)도 반드시 포함한다.

두 학습입력 스키마를 모두 지원:
  (A) 다중필드   {"instruction":..., "input":..., "output":...}   (handcrafted_*)
  (B) 단일 text  {"text": "### Instruction:\n...\n\n### Input:\n...\n\n### Response:\n..."}
                 (data/processed/react_train.jsonl 등, ### Input: 블록은 없을 수도 있음)

★설계 원칙 — "검사를 안 했는데 통과로 보고" 하는 공허참(empty-true)을 구조적으로 금지:
  - 프로젝트 루트를 파일 위치(parent.parent)에 의존하지 않고 마커(data/+scripts/)로 위로 탐색.
    파일을 옮겨도 조용히 깨지지 않는다.
  - 스캔 파일이 0개거나 추출 신호가 0개면 → 통과가 아니라 RuntimeError(가짜 안전망 방지).
  - egov 정본 트리를 못 찾으면 silent 폴백이 아니라 RuntimeError + 시도한 후보 전부 로그
    (halo 오탐: 잘못된 egov 트리로 감사 → 오탐. silent 폴백이 원인이었다).

사용:
  from guard_eval_leak import assert_no_eval_leak
  assert_no_eval_leak(eval_srcs=[...절대경로 .jsx...])          # build_dataset_v2.main() 진입부
  # 또는 CLI:  python guard_eval_leak.py --taskset .../tasksets_v2.json
"""
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# ── 정규식 ────────────────────────────────────────────────────────────────────
_NAME_IN_INSTR = re.compile(r"\(([A-Za-z][A-Za-z0-9]*)\.jsx\)")
_COMP_IN_OUT = re.compile(r"(?:function|const)\s+([A-Z][A-Za-z0-9]+)\s*[(:=]")
# text 단일필드 섹션 헤더. "### Instruction:" / "### Input:" / "### Response:"
_SECTION_RE = re.compile(r"^[ \t]*#{2,3}[ \t]*(Instruction|Input|Response)[ \t]*:[ \t]*\r?\n?",
                         re.IGNORECASE | re.MULTILINE)


def _lf(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _sha(s: str) -> str:
    return hashlib.sha256(_lf(s).encode("utf-8")).hexdigest()


# ── 프로젝트 루트 탐색 (결함1 수정: parent.parent 의존 제거) ──────────────────
def find_project_root(start=None):
    """ai_model 프로젝트 루트를 '마커'로 위로 올라가며 탐색.

    마커 = data/ 와 scripts/ 를 동시에 가진 디렉토리(= ai_model 루트).
    comms/ 나 comms/v2-proposal/ 은 이 마커가 없으므로 조용히 오인되지 않는다.
    우선순위: $AI_MODEL_ROOT > start 인자 > __file__ 위로 탐색.
    실패 시 RuntimeError(어디를 봤는지 로그) — 절대 '없는 data 를 글롭해서 0통과' 하지 않는다.
    """
    tried = []

    def _is_root(d: Path) -> bool:
        return (d / "data").is_dir() and (d / "scripts").is_dir()

    env = os.environ.get("AI_MODEL_ROOT")
    if env:
        d = Path(env).resolve()
        tried.append(f"$AI_MODEL_ROOT: {d}  ({'ok' if _is_root(d) else 'no data+scripts marker'})")
        if _is_root(d):
            return d

    starts = []
    if start:
        starts.append(Path(start).resolve())
    starts.append(Path(__file__).resolve())
    starts.append(Path.cwd())

    for s in starts:
        base = s if s.is_dir() else s.parent
        for d in [base, *base.parents]:
            if _is_root(d):
                return d
        tried.append(f"walk-up from {base}: no ancestor with data/+scripts/")

    raise RuntimeError(
        "프로젝트 루트(ai_model)를 찾지 못함 — data/ 와 scripts/ 를 동시에 가진 조상 디렉토리 부재.\n"
        "  시도:\n    " + "\n    ".join(tried) +
        "\n→ $AI_MODEL_ROOT 로 명시하거나 find_project_root(start=...) 로 지정하세요."
    )


def default_data_globs(project_root=None):
    """기본 스캔 글롭 = data/*.jsonl + data/processed/*.jsonl (UNION)."""
    root = Path(project_root) if project_root else find_project_root()
    return [str(root / "data" / "*.jsonl"),
            str(root / "data" / "processed" / "*.jsonl")]


# ── 레코드 → (instruction, input, output) 정규화 (결함2 수정) ─────────────────
def _split_text_sections(text: str):
    """단일 text 필드를 ### Instruction/Input/Response 섹션으로 분해.

    반환: {'instruction':..., 'input':..., 'output':...} (없는 섹션은 '')."""
    parts = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        key = m.group(1).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[key] = text[start:end].strip("\n")
    return {
        "instruction": parts.get("instruction", ""),
        "input": parts.get("input", ""),
        "output": parts.get("response", ""),
    }


def _record_fields(rec: dict):
    """다중필드 스키마와 단일 text 스키마를 모두 (instruction, input, output) 로 통일.

    - 'text' 키가 있으면 섹션 파싱(B 스키마).
    - 아니면 instruction/input/output 필드 직접 사용(A 스키마).
    - 혼재 레코드도 안전하게 처리(둘 다 있으면 명시 필드 우선, text 로 보강).
    """
    instr = rec.get("instruction", "") or ""
    inp = rec.get("input", "") or ""
    out = rec.get("output", "") or ""
    if isinstance(rec.get("text"), str) and rec["text"].strip():
        sec = _split_text_sections(rec["text"])
        instr = instr or sec["instruction"]
        inp = inp or sec["input"]
        out = out or sec["output"]
    return instr, inp, out


# ── 학습 신호 수집 ────────────────────────────────────────────────────────────
def collect_train_signals(data_globs=None, project_root=None):
    """학습셋 union 에서 (파일명/식별자 집합, content-hash 집합) 을 뽑는다.

    data_globs: str | list[str] | None. None 이면 default_data_globs() 사용.
    반환: (names:set, hashes:set, stats:dict)
    ★공허참 방지: 매칭 파일 0개이거나 신호 0개면 RuntimeError.
    """
    if data_globs is None:
        data_globs = default_data_globs(project_root)
    elif isinstance(data_globs, str):
        data_globs = [data_globs]

    names, hashes = set(), set()
    files_read = 0
    files_matched = []
    for g in data_globs:
        for df in glob.glob(g):
            if df.endswith(".bak"):
                continue
            files_matched.append(df)
            with open(df, encoding="utf-8") as fh:
                files_read += 1
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    instr, inp, out = _record_fields(rec)
                    for m in _NAME_IN_INSTR.findall(instr):
                        names.add(m)
                    for m in _COMP_IN_OUT.findall(out):
                        names.add(m)
                    if inp:
                        hashes.add(_sha(inp))

    stats = {"globs": data_globs, "files_read": files_read,
             "files": files_matched, "n_names": len(names), "n_hashes": len(hashes)}

    if files_read == 0:
        raise RuntimeError(
            "학습셋 스캔 파일 0개 — 가드가 '검사 없이 통과'할 뻔했다(공허참).\n"
            f"  글롭: {data_globs}\n"
            "→ 프로젝트 루트/글롭 경로를 확인하세요. (파일 위치 이동 시 조용히 깨지는 구조가 원인)"
        )
    if (len(names) + len(hashes)) == 0:
        raise RuntimeError(
            "학습셋을 읽었으나 추출 신호 0개 — 스키마 파싱 실패로 가짜 안전망일 수 있다(공허참).\n"
            f"  읽은 파일 {files_read}개, 글롭 {data_globs}\n"
            "→ 레코드 스키마(다중필드/단일 text)를 확인하세요."
        )
    return names, hashes, stats


def assert_no_eval_leak(eval_srcs, data_globs=None, extra_names=(), project_root=None, verbose=False):
    """eval_srcs 중 하나라도 학습셋에 (파일명/식별자/내용해시) 걸리면 RuntimeError.

    extra_names: 추가로 금지할 basename(예: 'App' 은 합성 function App() 과 충돌 → eval 로 쓰지
                 말라는 의미). 화이트리스트가 아님.
    """
    names, hashes, stats = collect_train_signals(data_globs, project_root)
    if verbose:
        print(f"[guard] 학습셋 신호: names={stats['n_names']} hashes={stats['n_hashes']} "
              f"(files={stats['files_read']})", flush=True)
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


# ── egov 정본 트리 해석 (결함3 + EGOV_SRC 하드닝) ────────────────────────────
def resolve_egov(project_root=None, override=None, verbose=True):
    """egov 실파일 정본 소스 루트. 장비마다 체크아웃 위치가 달라 후보 탐색 + 오버라이드.

    우선순위: --egov 인자 > $EGOV_SRC > 프로젝트루트 기반 sibling > 알려진 절대경로.
    ★halo 오탐 방지: 정본을 못 찾으면 조용히 cands[0] 폴백하지 않고 RuntimeError +
      시도한 모든 후보(존재여부 포함)를 로그. 어느 트리를 썼는지 항상 명시 출력한다.
    """
    root = Path(project_root) if project_root else find_project_root()
    cands = []  # (label, path)
    if override:
        cands.append(("--egov 인자", Path(override)))
    env = os.environ.get("EGOV_SRC")
    if env:
        cands.append(("$EGOV_SRC", Path(env)))
    cands += [
        ("sibling(root/../../twinspace_platform)",
         root.parent.parent / "twinspace_platform" / "egovGeoportal" / "src"),
        ("linux-ext-vol",
         Path("/run/media/user/새 볼륨/Documents/workspace/twinspace_platform/egovGeoportal/src")),
        ("win-original",
         Path("d:/Documents/workspace/TwinSpace-platform/egovGeoportal/src")),
    ]
    tried = []
    for label, c in cands:
        exists = c.exists()
        tried.append(f"{label}: {c}  ({'EXISTS' if exists else 'missing'})")
        if exists:
            if verbose:
                print(f"[guard] egov 정본 트리 채택 → {label}: {c}", flush=True)
                print("[guard] 시도한 후보:\n    " + "\n    ".join(tried), flush=True)
            return c
    raise RuntimeError(
        "egov 정본 트리를 찾지 못함 — silent 폴백 금지(halo 오탐 방지).\n"
        "  시도한 후보(순서대로):\n    " + "\n    ".join(tried) +
        "\n→ 정본 트리 경로를 $EGOV_SRC 또는 --egov 로 명시하세요."
    )


def _eval_srcs_from_taskset(taskset_json, egov_root):
    spec = json.loads(Path(taskset_json).read_text(encoding="utf-8"))
    egov = Path(egov_root)
    srcs = []
    for tsid, ts in spec.get("tasksets", {}).items():
        for rel in ts.get("tasks", {}).values():
            srcs.append(egov / rel)
    return srcs


if __name__ == "__main__":
    import argparse
    root = find_project_root()
    ap = argparse.ArgumentParser(description="학습셋↔eval 오염 차단 가드")
    ap.add_argument("--taskset", default=str(root / "scripts" / "tasksets_v2.json"))
    ap.add_argument("--egov", default=None,
                    help="egov 정본 트리 override(미지정 시 $EGOV_SRC > 후보탐색, 실패 시 크래시)")
    ap.add_argument("--data-glob", action="append", default=None,
                    help="반복 지정 가능. 미지정 시 data/*.jsonl + data/processed/*.jsonl")
    args = ap.parse_args()

    egov_root = resolve_egov(project_root=root, override=args.egov)
    srcs = _eval_srcs_from_taskset(args.taskset, egov_root)
    names, hashes, stats = collect_train_signals(args.data_glob, project_root=root)
    print(f"[guard] 학습셋 신호 수집: names={stats['n_names']} hashes={stats['n_hashes']} "
          f"(files_read={stats['files_read']})", flush=True)
    assert_no_eval_leak(srcs, data_globs=args.data_glob, project_root=root)
    print(f"OK — {len(srcs)} eval 태스크 전부 학습셋과 0오염 "
          f"(globs={stats['globs']}, egov={egov_root})")

# ── build_dataset_v2.main() 에 끼울 스니펫 (제안, 미적용) ────────────────────
#   from guard_eval_leak import assert_no_eval_leak, _eval_srcs_from_taskset, resolve_egov
#   egov = resolve_egov()                                   # 못 찾으면 크래시(silent 폴백 없음)
#   assert_no_eval_leak(_eval_srcs_from_taskset("scripts/tasksets_v2.json", egov))
#   # ↑ 데이터 기록(write) '전에' 호출 → 오염 시 학습셋 산출 자체를 막음.
