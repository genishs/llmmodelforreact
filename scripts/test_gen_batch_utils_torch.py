# -*- coding: utf-8 -*-
"""
test_gen_batch_utils_torch.py — generate_batch() 통합 스모크(CPU 전용, 가짜 model.generate()).

GPU 0 / 실제 가중치 미적재. 진짜 로컬 토크나이저(123b 어댑터 사본, CPU 파싱만) + 가짜 model 객체
(model.device=cpu, model.generate()가 결정론적 텐서를 즉석 조립)로 generate_batch()의 텐서
경로(좌패딩, 배치 분할, eos 트림)를 실제로 실행해 검증한다. 141B 학습과 GPU를 절대 다투지 않음
(torch.device('cpu') 고정, cuda 호출 없음).

실행: /home/user/.venvs/ai_model_rocm/bin/python scripts/test_gen_batch_utils_torch.py
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import torch  # noqa: E402  (CPU 전용 — device 항상 cpu로 고정, cuda 미호출)
from transformers import AutoTokenizer  # noqa: E402

from gen_batch_utils import generate_batch  # noqa: E402

TOK_DIR = ROOT / "models" / "qwen-react-lora-123b-hqq"  # 토크나이저 파일만 사용(가중치 무관)


class _FakeModel:
    """model.generate() 를 흉내낸다: 배치별로 미리 정한 tail(뒤에 붙일 새 토큰들)을 반환.
    실제 HF batched generate 처럼 '전 행 동일 길이'로 텐서를 만들되, 먼저 끝난 행은
    eos_id로 패딩(짧은 tail을 eos로 채움) — pad_token_id=eos_id 호출과 동일한 실제 동작 재현."""

    def __init__(self, eos_id, tails):
        self.device = torch.device("cpu")
        self.eos_id = eos_id
        self.tails = tails  # 배치 순서와 동일한 list[list[int]] (eos 포함 가능, max_new보다 짧을 수 있음)

    def generate(self, input_ids, attention_mask, **kwargs):
        max_new = kwargs["max_new_tokens"]
        batch = input_ids.shape[0]
        in_len = input_ids.shape[1]
        rows = []
        for i in range(batch):
            tail = list(self.tails[i])
            padded_tail = (tail + [self.eos_id] * max_new)[:max_new]  # eos_id로 우측 패딩(실제 동작 재현)
            row = input_ids[i].tolist() + padded_tail
            rows.append(row)
        return torch.tensor(rows, dtype=input_ids.dtype)


class TestGenerateBatchIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not TOK_DIR.exists():
            raise unittest.SkipTest(f"토크나이저 없음: {TOK_DIR} (다른 장비/최초 clone일 수 있음)")
        cls.tok = AutoTokenizer.from_pretrained(str(TOK_DIR), trust_remote_code=True)
        if cls.tok.pad_token is None:
            cls.tok.pad_token = cls.tok.eos_token

    def test_batch_of_3_mixed_lengths_and_eos_trim(self):
        tok = self.tok
        eos_id = tok.eos_token_id
        prompts = [
            "short prompt",
            "a somewhat longer prompt with more tokens in it",
            "medium length prompt here",
        ]
        # ★ 더미 id는 실제 eos_id(=2)와 절대 겹치지 않도록 100+로 시작(테스트 자작 버그 방지 —
        #   처음엔 [1,2,3,4,5,6]을 썼다가 '2'가 진짜 eos_id와 우연히 겹쳐 조기 트림되는 걸 실측으로 발견).
        # row0: eos 바로(2토큰 후) -> truncated=False, 짧게 트림.
        # row1: eos 없이 max_new 꽉 채움 -> truncated=True.
        # row2: eos가 중간에 -> truncated=False.
        max_new = 6
        tails = [
            [111, 222, eos_id],
            [101, 102, 103, 104, 105, 106],
            [107, 108, eos_id],
        ]
        model = _FakeModel(eos_id, tails)
        results = generate_batch(model, tok, prompts, max_new, eos_id, suppress_tokens=[])

        self.assertEqual(len(results), 3)
        ids0, trunc0, raw0 = results[0]
        ids1, trunc1, raw1 = results[1]
        ids2, trunc2, raw2 = results[2]

        self.assertEqual(ids0, [111, 222])
        self.assertFalse(trunc0)
        self.assertEqual(raw0, max_new)  # eos 이전 트림과 무관하게 raw 길이는 배치 전체 max_new

        self.assertEqual(ids1, [101, 102, 103, 104, 105, 106])
        self.assertTrue(trunc1)
        self.assertEqual(raw1, max_new)

        self.assertEqual(ids2, [107, 108])
        self.assertFalse(trunc2)

    def test_single_item_batch_no_padding_added(self):
        """★ 회귀 확인: len(prompts)==1 이면 tok([p], padding=True)가 패딩을 추가하지 않아
        eval_hard_tsc.py의 기존 단일-generate 호출과 동일한 input_ids를 만든다."""
        tok = self.tok
        eos_id = tok.eos_token_id
        prompt = "solo prompt for regression check"

        # generate_batch 가 실제로 만드는 input_ids 캡처
        captured = {}
        real_generate = _FakeModel.generate

        def spy_generate(self_, input_ids, attention_mask, **kwargs):
            captured["input_ids"] = input_ids.clone()
            captured["attention_mask"] = attention_mask.clone()
            return real_generate(self_, input_ids, attention_mask, **kwargs)

        model = _FakeModel(eos_id, [[1, 2, eos_id]])
        model.generate = spy_generate.__get__(model, _FakeModel)

        generate_batch(model, tok, [prompt], max_new=4, eos_id=eos_id, suppress_tokens=[])

        # 기존 경로(tok(prompt, return_tensors="pt"))와 동일해야 함(패딩 없음, 유일한 시퀀스=최장이므로).
        expected = tok(prompt, return_tensors="pt")
        self.assertTrue(torch.equal(captured["input_ids"], expected["input_ids"]))
        self.assertTrue(torch.equal(captured["attention_mask"], expected["attention_mask"]))
        self.assertTrue(torch.all(captured["attention_mask"] == 1))  # 패딩 0 없음


if __name__ == "__main__":
    unittest.main(verbosity=2)
