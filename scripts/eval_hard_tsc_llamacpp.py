# -*- coding: utf-8 -*-
"""
eval_hard_tsc_llamacpp.py — heldout7/hard11 "생성" 단계의 llama.cpp 백엔드판 (이슈 #9).

WHY:
  eval_hard_tsc.py(HF `model.generate()`, per-token decode)는 141B/123B급에서 ~0.1 tok/s라
  heldout7(7태스크) 채점에 태스크당 수시간·전체 ~30h 걸린다. GGUF+llama.cpp 배치추론으로
  같은 태스크를 생성하면 같은 그래픽카드에서도 수 시간 이내로 낮아진다는 것이 정석 해법.

  이 스크립트는 **생성만** 담당한다. torch/transformers/peft를 전혀 import하지 않는다
  (urllib.request로 이미 떠 있는 llama-server의 HTTP API만 사용) — 즉 이 파일 자체는
  GPU도, HF 스택도 필요 없다. 산출물 포맷은 eval_hard_tsc.py와 **바이트 호환**이라
  scripts/score_v2.py를 무수정으로 재사용해 채점한다:
    - eval_results/gen/<label>__<task>.tsx   (strip_fences 적용된 코드 텍스트)
    - eval_results/<label>.json              ({"label", "tasks": [{"task","truncated",...}]})

사전 준비 (이 스크립트가 하지 않는 것):
  1) llama.cpp 빌드(scripts_dev/build-llamacpp.sh 참고 — 이 레포에는 없음, 별도 툴체인 디렉터리).
  2) 베이스 GGUF (+ 있으면 LoRA GGUF 어댑터) 변환 — convert_hf_to_gguf.py / convert_lora_to_gguf.py.
  3) 서버 기동은 **호출자 책임**:
       llama-server -m base.gguf --lora adapter.gguf -c 8192 -ngl <N> --port 8811
     여러 태스크가 같은 서버 인스턴스를 재사용하는 편이(매 태스크 모델 재적재보다) 훨씬 빠르다.
     ⚠ GPU 사용 중인 다른 작업(예: 141B/123B HF 채점·학습)과 경합하므로, -ngl(GPU 오프로드 레이어수)
     값과 실행 시점은 GPU 여유를 확인한 뒤 정할 것(CLAUDE.md 하드 제약).

★ eval_hard_tsc.py의 TASKS/HELDOUT_TASKS/TS_CONV/BUGGY_TS/FIM 미러(scripts/score_v2.py가 이미
  HELDOUT_SRC로 같은 패턴을 쓴다 — torch를 끌어오지 않기 위한 의도적 중복). 하나를 바꾸면
  eval_hard_tsc.py · score_v2.py · 이 파일 3곳 동기화 필요.

실행 예:
  # 서버가 http://127.0.0.1:8811 에서 이미 떠 있다고 가정
  python scripts/eval_hard_tsc_llamacpp.py --label 123b-llamacpp-q4-heldout7 --heldout \
      --server-url http://127.0.0.1:8811 --max-new 2048
  python scripts/score_v2.py --labels 123b-llamacpp-q4-heldout7   # 채점(기존 스크립트 그대로)
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from gen_batch_utils import build_prompt  # noqa: E402  (순수 함수, torch 불필요)
from score_v2 import HELDOUT_SRC, resolve_egov  # noqa: E402  (score_v2도 torch 무의존 — 재사용)

EGOV = resolve_egov()

TS_CONV = "이 React 컴포넌트를 TypeScript(.tsx)로 변환해줘. props 타입을 interface로 정의하고 모든 함수/상태에 타입을 붙여줘. 코드만 출력해."

# 버그수정 태스크용 inline 입력 — eval_hard_tsc.BUGGY_TS 미러
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

FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>", "<|im_start|>"]

# (name, instruction, egov 상대경로 or "", inline 입력 or "") — eval_hard_tsc.TASKS 미러
TASKS = [
    ("counter-ts", "Write a typed React counter component in TypeScript with a Props interface (initial: number). Output code only.", "", ""),
    ("usedebounce-ts", "Create a generic custom hook useDebounce<T>(value: T, delay: number): T in TypeScript. Output code only.", "", ""),
    ("tanstack-ts", "TanStack Query의 useInfiniteQuery로 무한 스크롤 상품 목록 컴포넌트를 TypeScript로 만들어줘. Product interface와 페이지 응답 타입을 정의하고 로딩/에러를 처리해줘. 코드만 출력.", "", ""),
    ("form-ts", "Build a typed controlled login form component in TypeScript. Define a FormState interface and type all event handlers (React.ChangeEvent, React.FormEvent). Output code only.", "", ""),
    ("egov-paging-ts", TS_CONV, "components/EgovPaging.jsx", ""),
    ("egov-download-ts", TS_CONV, "pages/support/download/EgovDownloadDetail.jsx", ""),
    ("reducer-union-ts", "TypeScript로 todo 리스트의 useReducer를 작성해줘. Action을 판별유니온(discriminated union)으로 정의하고(ADD/REMOVE/TOGGLE, 각 payload 타입 다름), reducer의 switch가 모든 케이스를 타입안전하게 처리하도록. State와 Action 타입을 export. 코드만 출력.", "", ""),
    ("datatable-generic-ts", "Build a reusable generic <DataTable<T>> React component in TypeScript. Props: rows: T[] and columns: { key: keyof T; header: string; render?: (value: T[keyof T], row: T) => React.ReactNode }[]. Render a table with typed cells. Output code only.", "", ""),
    ("auth-context-ts", "TypeScript로 타입이 완전한 React AuthContext를 만들어줘. User 타입, AuthContextValue 인터페이스(user: User | null, login, logout), Provider 컴포넌트, 그리고 Provider 밖에서 쓰면 throw하는 useAuth() 훅. createContext의 기본값과 null 가드까지 타입안전하게. 코드만 출력.", "", ""),
    ("usefetch-union-ts", "Create a generic custom hook useFetch<T>(url: string) in TypeScript that returns a discriminated union state: { status: 'loading' } | { status: 'error'; error: Error } | { status: 'success'; data: T }. Use useState and useEffect. Output code only.", "", ""),
    ("bugfix-types-ts", "다음 TypeScript 컴포넌트는 strict 모드에서 타입에러가 여러 개 있어. 모든 타입에러를 고쳐서 컴파일되게 만들어줘(props에 interface 추가 포함). 수정된 전체 코드만 출력해.", "", BUGGY_TS),
]

# HELDOUT_SRC(score_v2.py)의 순서 기반 HELDOUT_TASKS — (name, instr, egov경로, inline) 튜플로 복원
HELDOUT_TASKS = [(name, TS_CONV, rel, "") for name, rel in HELDOUT_SRC.items()]


def strip_fences(text):
    """```tsx ... ``` 펜스 제거 + FIM 절단. eval_hard_tsc.strip_fences 미러(바이트 동일 로직)."""
    for m in FIM:
        j = text.find(m)
        if j != -1:
            text = text[:j]
    fence = re.search(r"```(?:tsx?|typescript|jsx?)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    m = re.search(r"^(import |interface |type |const |export |function )", text, re.MULTILINE)
    return text[m.start():].strip() if m else text.strip()


def llama_completion(server_url, prompt, max_new, repeat_penalty=1.1, timeout=600):
    """llama-server /completion 호출(그리디: temperature=0). 반환: (content, truncated, tokens_predicted).
    truncated = stop_type == 'limit'  (eval_hard_tsc.py의 truncated=max_new 도달&EOS없음과 동치)."""
    body = {
        "prompt": prompt,
        "n_predict": max_new,
        "temperature": 0,           # greedy (do_sample=False, num_beams=1 과 동치)
        "repeat_penalty": repeat_penalty,
        "cache_prompt": True,
        "return_tokens": False,
        # FIM/특수토큰 완전 금지 — eval_hard_tsc.gen_setup()의 suppress_tokens 미러.
        # 문자열 형태 logit_bias: 해당 문자열을 구성하는 전 토큰을 생성 불가로 만듦(서버 문서 511행).
        "logit_bias": [[tok, False] for tok in FIM],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        server_url.rstrip("/") + "/completion", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    content = out.get("content", "")
    stop_type = out.get("stop_type", "")
    truncated = (stop_type == "limit")
    tokens_predicted = out.get("tokens_predicted", 0)
    return content, truncated, tokens_predicted


def wait_for_server(server_url, timeout=120):
    """/health 폴링(서버가 이미 떠 있다는 전제이지만, 방금 기동됐다면 모델 로드 대기)."""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(server_url.rstrip("/") + "/health", timeout=5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError) as e:
            last_err = e
        time.sleep(2)
    raise RuntimeError(f"llama-server({server_url})가 {timeout}s 내 준비되지 않음: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--server-url", default="http://127.0.0.1:8811",
                     help="이미 기동된 llama-server 주소(이 스크립트는 서버를 실행하지 않음)")
    ap.add_argument("--max-new", type=int, default=2048)
    ap.add_argument("--only", default="", help="쉼표구분 task 이름만 생성")
    ap.add_argument("--heldout", action="store_true", help="확장 held-out eval셋(heldout7)으로 생성")
    ap.add_argument("--repeat-penalty", type=float, default=1.1)
    ap.add_argument("--skip-health-wait", action="store_true")
    args = ap.parse_args()

    base_tasks = HELDOUT_TASKS if args.heldout else TASKS
    only = set(s.strip() for s in args.only.split(",") if s.strip())
    tasks = [t for t in base_tasks if (not only or t[0] in only)]

    if not args.skip_health_wait:
        wait_for_server(args.server_url)

    archive_dir = ROOT / "eval_results" / "gen"
    archive_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, instr, inp, inline in tasks:
        if inp:
            code = (EGOV / inp).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
            prompt = build_prompt(instr, code)
        elif inline:
            prompt = build_prompt(instr, inline)
        else:
            prompt = build_prompt(instr, None)
        in_len_approx = len(prompt)  # 정확한 토큰 길이는 서버 토크나이저 몫 — 문자수만 로그용

        t0 = time.time()
        raw, truncated, new_tokens = llama_completion(
            args.server_url, prompt, args.max_new, repeat_penalty=args.repeat_penalty)
        dt = time.time() - t0

        src = strip_fences(raw)
        fname = f"{args.label}__{name}.tsx"
        (archive_dir / fname).write_text(src, encoding="utf-8")
        rows.append(dict(task=name, chars=len(src), truncated=truncated,
                          new_tokens=new_tokens, gen_seconds=round(dt, 1)))
        print(f"  generated [{name:18s}] {len(src):5d} chars "
              f"(new={new_tokens}tok {dt:.1f}s prompt_chars~{in_len_approx}"
              f"{' TRUNC!' if truncated else ''})", flush=True)

    outdir = ROOT / "eval_results"
    outdir.mkdir(exist_ok=True)
    (outdir / f"{args.label}.json").write_text(
        json.dumps({"label": args.label, "kind": "tsc_hard_llamacpp",
                     "server_url": args.server_url, "max_new": args.max_new,
                     "tasks": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"saved -> eval_results/{args.label}.json")
    print(f"채점: python scripts/score_v2.py --labels {args.label}")


if __name__ == "__main__":
    main()
