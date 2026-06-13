# -*- coding: utf-8 -*-
"""
데이터셋 큐레이션 v2 — loss 변동/품질 개선용.

기존 build_dataset.py의 문제:
  - GitHub 수집분이 짧고 거의 동일한 지시문(`X` 컴포넌트 작성해줘)에 거대한 임의 소스를 매핑
    → 같은 지시문이 모순된 정답으로 학습됨(loss 스파이크)
  - 출력의 절반이 seq 256 초과 → 잘린 불완전 코드가 정답

v2 개선:
  1) GitHub 지시문 중복 제거(instruction 1개당 1개 출력만, 토큰 한도 내 최대 길이 선호)
  2) 전체 프롬프트가 토큰 한도(--cap, 기본 384) 이내인 것만 채택 → 잘림 방지
  3) 핸드크래프트(고품질)는 전량 유지
  4) 원본 백업 후 react_train/val.jsonl 갱신

실행: python src/build_dataset_v2.py --cap 384
"""
import os
import sys
import io
import json
import random
import argparse
import shutil
from pathlib import Path

# build_dataset 임포트가 sys.stdout을 UTF-8로 래핑함(중복 래핑 금지)
from build_dataset import HANDCRAFTED_QA, format_alpaca, quality_filter, load_github_data
from transformers import AutoTokenizer

TOK = AutoTokenizer.from_pretrained("./models/base/qwen2.5-coder-7b", trust_remote_code=True)


def full_tok_len(item):
    return len(TOK(format_alpaca(item)["text"])["input_ids"])


def curate(cap):
    gh = load_github_data()
    # 1) 지시문별로 묶고, 토큰 한도 내에서 가장 긴(=가장 완결된) 출력 1개 선택
    by_instr = {}
    for x in gh:
        if not quality_filter(x):
            continue
        instr = x.get("instruction", "").strip()
        by_instr.setdefault(instr, []).append(x)

    gh_clean, dropped_oversize, dropped_dup = [], 0, 0
    for instr, cands in by_instr.items():
        fit = [(full_tok_len(c), c) for c in cands]
        fit = [(n, c) for n, c in fit if n <= cap]
        if not fit:
            dropped_oversize += 1
            continue
        dropped_dup += len(cands) - 1
        gh_clean.append(max(fit, key=lambda t: t[0])[1])  # 한도 내 최장 출력

    # 2) 핸드크래프트(고품질) — 한도 내인 것 유지
    hc = [x for x in HANDCRAFTED_QA if quality_filter(x) and full_tok_len(x) <= cap]

    return hc, gh_clean, dict(gh_total=len(gh), gh_unique=len(by_instr),
                              dropped_oversize=dropped_oversize, dropped_dup=dropped_dup)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=384, help="전체 프롬프트 최대 토큰")
    ap.add_argument("--out", default="./data/processed")
    args = ap.parse_args()

    hc, gh_clean, stats = curate(args.cap)
    all_data = hc + gh_clean
    random.seed(42)
    random.shuffle(all_data)
    split = max(1, int(len(all_data) * 0.9))
    train, val = all_data[:split], all_data[split:]
    if not val:
        val, train = all_data[-1:], all_data[:-1]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # 원본 백업(.orig, 최초 1회만)
    for name in ["react_train.jsonl", "react_val.jsonl"]:
        src = out / name
        bak = out / (name + ".orig")
        if src.exists() and not bak.exists():
            shutil.copy(src, bak)

    for name, data in [("react_train.jsonl", train), ("react_val.jsonl", val)]:
        with open(out / name, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(format_alpaca(item), ensure_ascii=False) + "\n")

    print("=" * 56)
    print(f"큐레이션 v2 (cap={args.cap} 토큰)")
    print(f"  GitHub 원본 {stats['gh_total']}개 → 고유지시문 {stats['gh_unique']}개")
    print(f"  중복출력 제거 {stats['dropped_dup']}개, 한도초과 지시문 제거 {stats['dropped_oversize']}개")
    print(f"  GitHub 채택 {len(gh_clean)}개 + 핸드크래프트 {len(hc)}개 = {len(all_data)}개")
    print(f"  학습 {len(train)} / 검증 {len(val)}  →  {out}")
    print("=" * 56)


if __name__ == "__main__":
    main()
