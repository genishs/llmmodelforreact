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


SYNTH_PATH = "./data/handcrafted_synth.jsonl"


def full_tok_len(item):
    return len(TOK(format_alpaca(item)["text"])["input_ids"])


def out_tok_len(item):
    return len(TOK(item.get("output", ""))["input_ids"])


def load_synth(path=SYNTH_PATH):
    items = []
    if not Path(path).exists():
        return items
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def curate(cap, gh_out_cap):
    """혼합 전략: 핸드크래프트 + 합성 + '짧은' GitHub(출력 토큰 한도 이하)만.

    GitHub 스크랩은 '짧은 지시→거대 실소스'라 본질적으로 어려운 신호 →
    출력이 짧은(=집중된) 것만 채택하고 중복 지시문은 제거.
    """
    gh = load_github_data()
    by_instr = {}
    for x in gh:
        if not quality_filter(x):
            continue
        by_instr.setdefault(x.get("instruction", "").strip(), []).append(x)

    gh_clean, dropped_long, dropped_dup = [], 0, 0
    for instr, cands in by_instr.items():
        # 출력이 짧고(≤gh_out_cap) 전체도 한도 내인 것 중 가장 짧은(가장 집중된) 출력
        fit = [(out_tok_len(c), c) for c in cands
               if out_tok_len(c) <= gh_out_cap and full_tok_len(c) <= cap]
        if not fit:
            dropped_long += 1
            continue
        dropped_dup += len(cands) - 1
        gh_clean.append(min(fit, key=lambda t: t[0])[1])

    hc = [x for x in HANDCRAFTED_QA if quality_filter(x) and full_tok_len(x) <= cap]
    synth = [x for x in load_synth()
             if x.get("output") and full_tok_len(x) <= cap]

    stats = dict(gh_total=len(gh), gh_unique=len(by_instr),
                 dropped_long=dropped_long, dropped_dup=dropped_dup,
                 synth_loaded=len(load_synth()), synth_kept=len(synth))
    return hc, synth, gh_clean, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=384, help="전체 프롬프트 최대 토큰")
    ap.add_argument("--gh-out-cap", type=int, default=200,
                    help="GitHub 샘플 출력 최대 토큰(짧은 것만 채택)")
    ap.add_argument("--out", default="./data/processed")
    args = ap.parse_args()

    hc, synth, gh_clean, stats = curate(args.cap, args.gh_out_cap)
    all_data = hc + synth + gh_clean
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

    print("=" * 60)
    print(f"큐레이션 v2 혼합 (cap={args.cap}, gh_out_cap={args.gh_out_cap} 토큰)")
    print(f"  GitHub {stats['gh_total']}개 → 고유 {stats['gh_unique']}개 "
          f"(중복 {stats['dropped_dup']}, 출력김 {stats['dropped_long']} 제거) → 채택 {len(gh_clean)}개")
    print(f"  합성 {stats['synth_loaded']}개 로드 → 채택 {stats['synth_kept']}개")
    print(f"  핸드크래프트 {len(hc)}개")
    print(f"  합계 {len(all_data)}개 → 학습 {len(train)} / 검증 {len(val)}  →  {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
