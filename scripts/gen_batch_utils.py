# -*- coding: utf-8 -*-
"""
gen_batch_utils.py — 배치 디코드 채점의 순수 로직 (버킷팅/프롬프트/트림). GPU 0.

WHY (이슈 #9, 2026-07-30):
  eval_hard_tsc.py --heldout 는 태스크 7개를 **순차** model.generate() 호출로 채점한다
  (배치=1). HQQ 2bit/4bit 디코드는 스텝당 가중치 역양자화 비용이 지배적(대역폭 바운드)이고
  이 비용은 배치 크기와 무관하게 "스텝 1회당 1번"만 든다 — 즉 배치=N이면 같은 역양자화
  비용으로 스텝당 N개 토큰을 만들어낸다. 그래서 batch_decode_probe.py(2026-07-16, 샤스 설계)가
  "배치=N 대비 batch=1의 몇 배" 를 재려 했으나 **실행 로그가 없다 — 작성만 되고 GPU에서
  실측된 적이 없다**(2026-07-30 확인, comms/eval_results/docs 전체 grep 0건). 배수 자체가
  미검증이므로 이 모듈은 "된다"고 주장하지 않고 **배치화 배관(bucketing/generate)만 정직하게
  준비**한다 — 실측은 141B 학습 종료 후 별도.

  실측 토큰 길이(2026-07-30, 123B 토크나이저, EGOV_SRC=twinspace_platform/sysadmin-front/src,
  GPU 미사용 순수 토크나이즈): heldout7 입력토큰 = 212~7314 (34배 편차, ho-admin-medit 최장).
  이 편차 때문에 "7개 전부 한 배치"는 짧은 태스크에 막대한 좌패딩 낭비 + medit의 긴 컨텍스트가
  KV캐시를 배치 전체에 강제해 OOM 위험(123B는 40GB 천장 근처에서 이미 여유가 얇음, CLAUDE.md).
  ∴ **길이순 그리디 버킷팅**으로 묶는다 — 비슷한 길이끼리, 버킷당 (배치크기 × 버킷내 최대길이)가
  예산(--batch-token-budget)을 넘지 않게. 아웃라이어(medit)는 자연히 단독 버킷이 된다.

설계 원칙:
  - **batch_size=1(기본값)은 기존 eval_hard_tsc.py 순차 경로와 바이트 단위로 동일한 산출을 낸다**
    (패딩이 발생하지 않아 tok(prompts, padding=True)가 tok(prompt) 단일호출과 동치 — 회귀 없음).
  - 순수 함수(bucket_by_length/build_prompt/trim_generated_at_eos)는 torch/모델 없이 단위테스트 가능.
  - generate_batch()만 torch/model을 다룬다(실행에는 필요하지만, 로드는 호출부 책임 — 이 파일은
    import 시 어떤 GPU 동작도 하지 않는다).

테스트: python scripts/test_gen_batch_utils.py  (GPU 0, 모델 미적재, ~1초)
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple


def build_prompt(instr: str, content: Optional[str] = None) -> str:
    """eval_hard_tsc.py 의 프롬프트 조립 로직 재현(순수 함수).
    content = egov 코드(inp) 또는 인라인 버그코드(inline) 중 있는 쪽. 둘 다 없으면 Response만."""
    if content:
        return f"### Instruction:\n{instr}\n\n### Input:\n{content}\n\n### Response:\n"
    return f"### Instruction:\n{instr}\n\n### Response:\n"


def bucket_by_length(
    items: Sequence[Tuple],
    max_batch: int = 1,
    max_batch_tokens: Optional[int] = None,
) -> List[List[Tuple]]:
    """items: (..., in_len) 튜플 시퀀스 — 마지막 원소가 입력 토큰 길이여야 한다
    (예: (name, prompt, in_len)). in_len 오름차순 그리디로 묶는다.

    조건: 버킷 크기 <= max_batch  AND  (버킷 크기) * (버킷 내 최대 in_len) <= max_batch_tokens
    (예산 초과분은 새 버킷으로 — 좌패딩 비용의 대략적 상한 근사).
    max_batch<=1 이면 전부 단독 버킷(batch=1 기존 경로와 동일 — 회귀 안전).
    단일 아이템은 예산을 혼자 넘더라도 항상 자기 버킷을 받는다(태스크를 건너뛸 수 없으므로).
    동률 시 원래 순서를 보존해 결정적(재현 가능)이다.

    반환: items 원소들의 리스트의 리스트(버킷들). 순서는 길이 오름차순(원 입력 순서 아님) —
    호출부는 반환된 순서대로 처리하고 이름으로 원 순서에 맞게 재정렬해야 한다."""
    if max_batch <= 1:
        return [[it] for it in items]

    order = sorted(range(len(items)), key=lambda i: (items[i][-1], i))
    buckets: List[List[Tuple]] = []
    cur: List[Tuple] = []
    for idx in order:
        item = items[idx]
        cand = cur + [item]
        cand_max_len = max(it[-1] for it in cand)
        cost = len(cand) * cand_max_len
        fits = (max_batch_tokens is None) or (cost <= max_batch_tokens)
        if cur and (len(cand) > max_batch or not fits):
            buckets.append(cur)
            cur = [item]
        else:
            cur = cand
    if cur:
        buckets.append(cur)
    return buckets


def trim_generated_at_eos(token_ids: Iterable[int], eos_id: int) -> Tuple[List[int], bool]:
    """생성된 새 토큰 id 리스트에서 첫 eos 이전까지 자른다.
    반환: (trimmed_ids, truncated). eos가 있으면 truncated=False(정상 종료),
    없으면 truncated=True(max_new 도달 — eval_hard_tsc.py 의 기존 truncated 판정과 동일 의미).

    배치 생성에서 먼저 끝난 행은 pad_token_id(=eos_id로 고정 호출)로 계속 채워지므로,
    eos_id 를 찾는 것만으로 pad_token_id 도 함께 올바르게 처리된다(같은 값이기 때문)."""
    ids = list(token_ids)
    try:
        cut = ids.index(int(eos_id))
        return ids[:cut], False
    except ValueError:
        return ids, True


def generate_batch(
    model,
    tok,
    prompts: Sequence[str],
    max_new: int,
    eos_id: int,
    suppress_tokens,
    min_new_tokens: int = 24,
    repetition_penalty: float = 1.1,
):
    """prompts(1개 이상)를 좌패딩 배치로 묶어 **단 한 번의 generate() 호출**로 생성한다.

    len(prompts)==1 일 때: tok([p], padding=True) 는 패딩을 추가하지 않으므로(배치 내 유일한
    시퀀스가 곧 최장) eval_hard_tsc.py 의 기존 단일-generate 호출과 동일한 입력 텐서 ·
    동일한 generate kwargs 를 만든다 — **회귀 없음**(코드 리뷰로 확인, GPU 실측은 별도).

    반환: prompts 와 같은 순서의 [(new_token_ids: List[int], truncated: bool, raw_new_tokens: int), ...].
    raw_new_tokens = eos 트림 전 길이(= 원래 eval_hard_tsc.py 의 `new_tokens` 출력과 동치, 배치=1일 때 동일 값)."""
    import torch  # 지연 임포트 — 순수 함수(bucket_by_length 등) 단위테스트는 torch 없이도 동작

    tok.padding_side = "left"
    enc = tok(list(prompts), return_tensors="pt", padding=True)
    enc = {k: v.to(model.device) for k, v in enc.items()}
    gen_kwargs = dict(
        max_new_tokens=max_new,
        min_new_tokens=min_new_tokens,
        do_sample=False,
        num_beams=1,
        use_cache=True,
        pad_token_id=eos_id,
        eos_token_id=eos_id,
        suppress_tokens=suppress_tokens,
        repetition_penalty=repetition_penalty,
    )
    with torch.no_grad():
        out = model.generate(**enc, **gen_kwargs)

    in_len = enc["input_ids"].shape[1]  # 좌패딩 후 배치 내 공통 길이 = 생성 시작 컬럼(전 행 동일)
    results = []
    for i in range(out.shape[0]):
        raw_ids = out[i][in_len:].tolist()
        trimmed, truncated = trim_generated_at_eos(raw_ids, eos_id)
        results.append((trimmed, truncated, len(raw_ids)))
    return results
