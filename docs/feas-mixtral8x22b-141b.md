# 141B(Mixtral-8x22B) gfx1151 가능성 테스트

**목적(범위 엄수):** Mixtral-8x22B-v0.1(MoE 141B총/39B활성)이 이 AMD Strix Halo(gfx1151,
통합메모리 64GB) 장비에서 **(a) HQQ 2bit로 로드**되고 **(b) LoRA 학습 스텝이 실제로 도는지**
짧은 런(smoke 8스텝)으로 증명한다. **풀 학습 아님.** 두목 지시: "가능성까지만".

일시: 2026-07-20 야간 / 오선생(autonomous-operator) 단독 수행.

## 셋업

| 항목 | 값 |
|---|---|
| 모델 | `mistral-community/Mixtral-8x22B-v0.1` (Apache 2.0, 미게이트) |
| 원본 크기 | bf16 safetensors ~281GB, 66 files |
| 다운로드 타깃 | `/run/media/user/새 볼륨/mixtral-8x22b-v0.1` (외장 sdb2, 여유 452GB) |
| 양자화 | HQQ 2bit, group_size 64 (레이어 단위 스트리밍, RAM에 bf16 통짜 안 올림) |
| LoRA | r16, **어텐션-온리(q/k/v/o_proj)** — `--lora-mlp` 금지(MLP=전문가 w1/w2/w3+gate) |
| 학습 | seq 512, grad-ckpt, smoke 8스텝 |
| GPU | gfx1151(Radeon 8060S), GTT total 56GiB(card1) |
| venv | `/home/user/.venvs/ai_model_rocm` (torch 2.10 rocm, hqq 0.2.8, peft 0.19.1) |
| 스왑 | 발사 전제 ≥60GiB (초기 15GiB → 두목 `sudo swapon /swapfile` 필요) |

## 다운로드

- 발사: 2026-07-20 21:47, snapshot_download resume + 무한 재개 루프.
- 초기 속도(WiFi): ~15 MiB/s(128 Mbps), ETA ~5h. 유선랜 전환 후 재측정 예정.
- 무결성 검증: 샤드 수 == index 기대치 + safetensors 헤더 파싱(chain_123b 블록 재사용).

_(결과 추후 기입)_

## 가능성 런 계측 (TBD)

| 지표 | 값 |
|---|---|
| 로드 성공 | TBD |
| 스트리밍 HQQ 양자화 소요 | TBD |
| GTT 피크 (`mem_info_gtt_used`) | TBD |
| 스텝 실제 진행 | TBD |
| step당 시간 | TBD |
| loss (첫/끝) | TBD |
| 총 소요 | TBD |

## 결론 (TBD)

**141B가 이 장비에서 되는가?** — TBD

## 미결/큐잉

- 스왑 60GiB: `sudo swapon /swapfile` (sudo=두목 몫). 미완 시 학습 미발사·자동 큐잉.
- push 보류(프로젝트 규칙: 두목 지시 전 push 금지).
