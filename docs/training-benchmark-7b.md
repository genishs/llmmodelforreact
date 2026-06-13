# 7B LoRA 학습 벤치마크 (DirectML / AMD Radeon 8060S)

날짜: 2026-06-13 · 작성: AI dev team (Opus 메인 + Sonnet 경량 운영)

## 결론 요약 — "어느 규모의 학습에 얼마나 걸리나"

| 항목 | 값 |
|------|----|
| **모델 규모** | Qwen2.5-Coder-**7B** (7,625,709,056 파라미터) |
| 학습 방식 | LoRA r=16 / α=32 (q,k,v,o_proj), **학습 파라미터 10,092,544 (0.13%)** |
| 정밀도 | **fp16** (DirectML는 bf16 미지원, fp32는 VRAM 초과) |
| 데이터 | train 75 + val 9 = 84개, **max_seq 256**(고정 패딩) |
| 스케줄 | 3 epoch × (75÷accum8) = **28 optim step** |
| **학습 시간** | **366.4초 (6분 6초), 평균 13.1초/step** |
| 모델 로딩 | 18초 (14.2GB safetensors → VRAM 스트리밍) |
| **전체 실행(로딩+학습+저장)** | **6분 39초** (14:45:02 → 14:51:41) |
| VRAM 사용 | **~31GB plateau** (48GB 카브아웃 중) |
| 시스템 RAM | 11.4 / 15.6GB 사용 (가용 ~4.4GB 유지) |
| 결과물 | `models/qwen-react-lora-7b-v1/adapter_model.safetensors` (40.4MB) |

> 비교: 기존 **1.5B를 CPU로** 학습한 v4는 84개·5epoch에 **26분**.
> 이번 **7B를 GPU(DirectML)로** 학습 = 5배 큰 모델인데도 **6분**. GPU 가속의 효과.

## 환경 제약 (이번에 실측으로 밝혀낸 것)

이 머신은 **AMD Ryzen AI Max+ 392 / 64GB 통합 메모리**. VRAM을 48GB로 카브아웃하면
시스템 RAM은 **15.6GB**만 남는다(가용 ~7GB). 그 위에서 발견한 DirectML 한계:

1. **bf16 미지원** — 디바이스에 bf16 텐서를 올리면 네이티브 크래시.
   → 디스크의 bf16 가중치를 **호스트에서 fp16/fp32로 변환 후** 디바이스로 이동해야 함.
2. **단일 텐서 할당 한도 ~3GB대** — 7B 임베딩(fp32 2.18GB)은 통과, 4GB 단일 할당은 실패.
3. **실사용 VRAM 천장 ~31GB** (48GB 설정이어도) — fp32 7B(28GB)는 활성값 올릴 자리가 없어 OOM.
   → **fp16(14GB)** 이라야 활성값 여유 확보.
4. **캐싱 할당자가 step마다 증가** + `empty_cache` API 없음 — 시퀀스가 길수록 plateau 지점이
   천장을 넘겨 OOM. **seq 256**에서 ~31GB로 plateau → 안정. seq 512/1024는 OOM.
5. **gradient checkpointing은 역효과** — DirectML에서 재계산이 버퍼를 더 쌓아 증가를 가속. 비활성.
6. **HF Trainer 사용 불가** — DirectML을 디바이스로 인식 못 함. **커스텀 학습 루프** 필요.
7. **PEFT save_pretrained 실패** — DirectML 텐서는 `OpaqueTensorImpl`이라 safetensors가 storage
   조회 불가. **어댑터를 CPU/fp32로 옮겨 직접 저장**해야 함.
8. AdamW `lerp` 연산은 CPU 폴백(경미한 성능 영향, 정상 동작).

## 재현 방법

```bash
cd C:\Users\user\Documents\workspace\study\ai_model
venv\Scripts\activate

# 스모크(2~6 step, 저장 없음) — 먼저 동작 확인 권장
python src/train_directml.py --dtype fp16 --seq 256 --smoke 6

# 본런 (config/training_config.yaml의 7B 설정 사용, seq만 256으로 오버라이드)
python src/train_directml.py --dtype fp16 --seq 256
```

플래그: `--dtype fp16|fp32` · `--seq N`(0=config) · `--scale`(fp16 손실 스케일, 기본 128) ·
`--grad-ckpt`(DirectML 비권장) · `--smoke N`(N step만, 저장 생략).

⚠️ **시작 전 시스템 RAM 6GB+ 확보**(브라우저 등 닫기). 로더에 RAM 가드(0.5GB) 내장 —
부족하면 스왑 프리징 대신 스스로 중단.

## 한계·다음 단계

- seq 256 고정 패딩이라 **긴 샘플은 잘림** → 품질 손해. fp16 + 소배치로 **loss 변동이 큼**
  (스텝별 0.6~12 진폭, 막판 ~1.0 수렴). 품질보다 "최대 규모 구동 + 시간 측정"이 목적이었음.
- 커스텀 루프는 **eval 미수행**(val 9개 미사용). 필요시 추가.
- 더 키우려면: ① VRAM 천장(~31GB)이 병목 → seq를 384로 올리는 여지 테스트(plateau<48 확인 필요)
  ② 데이터 확대 후 재학습 ③ 품질 위해 fp32 마스터 가중치 혼합정밀도 도입 검토.
