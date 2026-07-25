# -*- coding: utf-8 -*-
"""
batch_decode_probe.py — 생성(추론) throughput을 batch=1 vs batch=N으로 실측한다.

WHY (샤스 요청, 2026-07-16):
  v2 채점은 heldout 20태스크 생성이 필요한데, 72B는 메모리대역폭 병목이라
  '가중치 1회 로드 → N시퀀스 동시 생성(batch)'이 batch=1 대비 throughput을 얼마나
  올리는지가 채점시간(7.2h)을 대폭 줄일 수 있는지 판가름한다. 핵심 숫자 = batch=N tok/s ÷ batch=1 tok/s 배수.

  이건 학습이 아니라 순수 추론 측정이므로 --smoke 학습 프로브와 별개다. 32B 채점처럼
  72B는 bf16로는 추론도 안 들어가므로(145GB) 반드시 HQQ(4bit)로 로드 — train_directml의
  검증된 load_hqq_onthefly()를 그대로 재사용(채점/학습과 동일 경로).

  ⚠️ 웨지 주의: gfx1151에서 generate가 웨지나면 프로세스가 죽는다. gpu_job.sh로 detached 실행 권장.

사용:
  scripts/gpu_job.sh --name bdprobe72b --timeout 3600 -- \
    python scripts/batch_decode_probe.py --base ./models/base/qwen2.5-72b-instruct \
      --hqq-nbits 4 --hqq-group-size 64 --max-new 128 --batches 1 4
"""
import argparse
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from train_directml import load_hqq_onthefly  # noqa: E402  (검증된 HQQ 스트리밍 로더 재사용)

# 채점 태스크와 유사한 짧은 코드 생성 프롬프트(길이 편차를 줄여 좌패딩 낭비 최소화).
PROMPTS = [
    "Write a React function component `Counter` that uses useState to increment a number on button click. Return only TypeScript code.\n",
    "Write a TypeScript interface `User` with id, name, and optional email, then a function that formats a User to a string. Return only code.\n",
    "Write a React hook `useToggle` that returns a boolean and a toggle function, fully typed in TypeScript. Return only code.\n",
    "Write a TypeScript generic function `firstOrNull<T>` that returns the first element of an array or null. Return only code.\n",
    "Write a React component `TodoList` that renders an array of strings as an unordered list, typed with TypeScript. Return only code.\n",
    "Write a TypeScript function `debounce` that delays a callback, fully typed. Return only code.\n",
    "Write a React `useState`-based form with a single text input and controlled value in TypeScript. Return only code.\n",
    "Write a TypeScript enum `Status` (Idle, Loading, Done) and a function mapping it to a label. Return only code.\n",
]


def _sync():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def measure(model, tok, prompts, max_new, device):
    """prompts를 하나의 배치로 좌패딩해 한 번의 generate로 생성. (총 새토큰 = len(prompts)*max_new).
    반환: (elapsed_s, total_new_tokens, tok_per_s)."""
    enc = tok(prompts, return_tensors="pt", padding=True).to(device)
    gen_kwargs = dict(
        max_new_tokens=max_new,
        min_new_tokens=max_new,   # 정확히 max_new개 생성 강제 → 공정 비교
        do_sample=False,
        num_beams=1,
        use_cache=True,
        pad_token_id=tok.pad_token_id,
    )
    _sync()
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**enc, **gen_kwargs)
    _sync()
    dt = time.time() - t0
    # 새로 생성된 토큰 수(입력 길이 제외). 각 시퀀스 max_new 강제이므로 = n*max_new.
    n_new = (out.shape[1] - enc["input_ids"].shape[1]) * out.shape[0]
    return dt, n_new, n_new / dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="bf16 원본 경로(HQQ로 즉석 양자화)")
    ap.add_argument("--hqq-nbits", type=int, default=4)
    ap.add_argument("--hqq-group-size", type=int, default=64)
    ap.add_argument("--max-new", type=int, default=128)
    ap.add_argument("--batches", type=int, nargs="+", default=[1, 4],
                    help="비교할 배치 크기들(예: 1 4). 각 배치는 PROMPTS 앞에서 그만큼 사용.")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[bdprobe] device={device} base={args.base} "
          f"hqq={args.hqq_nbits}bit/g{args.hqq_group_size} max_new={args.max_new} batches={args.batches}",
          flush=True)

    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    tok.padding_side = "left"  # decoder-only 생성은 좌패딩
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    t_load = time.time()
    model = load_hqq_onthefly(args.base, device, torch.bfloat16,
                              nbits=args.hqq_nbits, group_size=args.hqq_group_size)
    model.eval()
    print(f"[bdprobe] 모델 로드+HQQ 양자화 완료: {time.time()-t_load:.1f}s", flush=True)

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    # 워밍업(커널 컴파일/할당 제외) — 타이밍에서 버림
    try:
        print("[bdprobe] 워밍업 1회…", flush=True)
        _ = measure(model, tok, PROMPTS[:1], 16, device)
        print("[bdprobe] 워밍업 OK (웨지 없음)", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bdprobe] ✗ 워밍업 중 실패/웨지: {type(e).__name__}: {e}", flush=True)
        raise

    results = {}
    max_b = max(args.batches)
    if max_b > len(PROMPTS):
        raise SystemExit(f"batch {max_b} > 프롬프트 {len(PROMPTS)}개 — PROMPTS를 늘리세요")

    for b in args.batches:
        prompts = PROMPTS[:b]
        try:
            dt, n_new, tps = measure(model, tok, prompts, args.max_new, device)
            results[b] = tps
            print(f"[bdprobe] batch={b:2d} | {dt:6.2f}s | 새토큰 {n_new:5d} | "
                  f"**{tps:7.2f} tok/s** (전체 배치 합산)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[bdprobe] ✗ batch={b} 실패/웨지: {type(e).__name__}: {e}", flush=True)
            raise

    peak = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else 0.0
    print("\n===== 배치 디코드 프로브 결과 =====", flush=True)
    for b, tps in results.items():
        print(f"  batch={b:2d}: {tps:7.2f} tok/s", flush=True)
    if 1 in results and len(results) > 1:
        base_tps = results[1]
        for b, tps in results.items():
            if b == 1:
                continue
            print(f"  ▶ batch={b} 배수: {tps/base_tps:.2f}x  (batch=1 대비)", flush=True)
    print(f"  peak GPU mem: {peak:.2f} GB", flush=True)
    print("==================================", flush=True)


if __name__ == "__main__":
    main()
