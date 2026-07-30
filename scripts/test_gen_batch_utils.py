# -*- coding: utf-8 -*-
"""
test_gen_batch_utils.py — gen_batch_utils.py 순수 함수 단위테스트. GPU 0, 모델 미적재, torch 불필요.

실행: python scripts/test_gen_batch_utils.py   (또는 시스템 python3 — torch 없이도 동작)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_batch_utils import bucket_by_length, build_prompt, trim_generated_at_eos  # noqa: E402


class TestBuildPrompt(unittest.TestCase):
    def test_with_content(self):
        p = build_prompt("do X", "code here")
        self.assertEqual(p, "### Instruction:\ndo X\n\n### Input:\ncode here\n\n### Response:\n")

    def test_without_content(self):
        p = build_prompt("do X", None)
        self.assertEqual(p, "### Instruction:\ndo X\n\n### Response:\n")

    def test_empty_string_content_treated_as_no_content(self):
        # eval_hard_tsc.py 원본: `if inp:` / `elif inline:` — 빈 문자열은 falsy라 Response-only 분기.
        p = build_prompt("do X", "")
        self.assertEqual(p, "### Instruction:\ndo X\n\n### Response:\n")


class TestBucketByLength(unittest.TestCase):
    def test_batch_size_1_is_all_singletons(self):
        """★ 회귀 안전장치: batch_size<=1 이면 기존 순차 경로와 동일하게 전부 단독 버킷."""
        items = [("a", 100), ("b", 5000), ("c", 20)]
        buckets = bucket_by_length(items, max_batch=1)
        self.assertEqual(buckets, [[("a", 100)], [("b", 5000)], [("c", 20)]])

    def test_batch_size_0_same_as_1(self):
        items = [("a", 100), ("b", 5000)]
        self.assertEqual(bucket_by_length(items, max_batch=0), [[it] for it in items])

    def test_groups_similar_lengths_respecting_max_batch(self):
        items = [("short1", 200), ("short2", 250), ("short3", 300), ("long", 7000)]
        buckets = bucket_by_length(items, max_batch=3, max_batch_tokens=None)
        # 길이순 정렬: short1,short2,short3,long. max_batch=3 -> 처음 3개가 한 버킷, long은 남는다.
        self.assertEqual(len(buckets), 2)
        names_in_bucket0 = sorted(x[0] for x in buckets[0])
        self.assertEqual(names_in_bucket0, ["short1", "short2", "short3"])
        self.assertEqual(buckets[1], [("long", 7000)])

    def test_token_budget_isolates_long_outlier(self):
        """실측 heldout7 유사 분포(212~7314) 재현: 예산이 있으면 medit급 아웃라이어가 자연히 단독 버킷."""
        items = [
            ("ho-select", 212), ("ho-gallery", 236), ("ho-about-org", 684),
            ("ho-attachfile", 1602), ("ho-admin-dae", 1685),
            ("ho-admin-mlist", 2743), ("ho-admin-medit", 7314),
        ]
        buckets = bucket_by_length(items, max_batch=4, max_batch_tokens=4000)
        # medit(7314) 혼자로는 이미 예산(4000)을 넘지만, 아이템 하나는 항상 자기 버킷을 받는다(건너뛸 수 없음).
        medit_bucket = [b for b in buckets if any(n == "ho-admin-medit" for n, _ in b)]
        self.assertEqual(len(medit_bucket), 1)
        self.assertEqual(len(medit_bucket[0]), 1)
        # 모든 버킷이 max_batch 이하, 그리고 (크기*최대길이)<=예산 이거나 단독 아이템.
        for b in buckets:
            self.assertLessEqual(len(b), 4)
            max_len = max(x[1] for x in b)
            if len(b) > 1:
                self.assertLessEqual(len(b) * max_len, 4000)
        # 모든 태스크가 정확히 한 번씩 등장(유실/중복 없음).
        all_names = sorted(n for b in buckets for n, _ in b)
        self.assertEqual(all_names, sorted(n for n, _ in items))

    def test_single_item_always_gets_its_own_bucket_even_over_budget(self):
        items = [("solo", 999999)]
        buckets = bucket_by_length(items, max_batch=4, max_batch_tokens=10)
        self.assertEqual(buckets, [[("solo", 999999)]])

    def test_deterministic_tie_break_preserves_original_order(self):
        items = [("a", 100), ("b", 100), ("c", 100)]
        buckets = bucket_by_length(items, max_batch=2, max_batch_tokens=None)
        # 동률(100)이면 원 인덱스 순서로 정렬 -> a,b 먼저 묶이고 c 단독.
        self.assertEqual(buckets, [[("a", 100), ("b", 100)], [("c", 100)]])

    def test_preserves_extra_tuple_fields(self):
        """실사용처럼 (name, prompt, in_len) 3-튜플도 마지막 원소만 길이로 취급."""
        items = [("t1", "prompt one", 50), ("t2", "prompt two", 60)]
        buckets = bucket_by_length(items, max_batch=2, max_batch_tokens=None)
        self.assertEqual(buckets, [[("t1", "prompt one", 50), ("t2", "prompt two", 60)]])


class TestTrimGeneratedAtEos(unittest.TestCase):
    def test_eos_found_trims_and_not_truncated(self):
        ids, truncated = trim_generated_at_eos([1, 2, 3, 99, 99, 99], eos_id=99)
        self.assertEqual(ids, [1, 2, 3])
        self.assertFalse(truncated)

    def test_eos_at_start(self):
        ids, truncated = trim_generated_at_eos([99, 1, 2], eos_id=99)
        self.assertEqual(ids, [])
        self.assertFalse(truncated)

    def test_no_eos_is_truncated(self):
        ids, truncated = trim_generated_at_eos([1, 2, 3], eos_id=99)
        self.assertEqual(ids, [1, 2, 3])
        self.assertTrue(truncated)

    def test_empty_input(self):
        ids, truncated = trim_generated_at_eos([], eos_id=99)
        self.assertEqual(ids, [])
        self.assertTrue(truncated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
