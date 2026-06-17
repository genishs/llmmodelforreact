# 7B LoRA 학습 벤치마크 (DirectML / AMD Radeon 8060S)

날짜: 2026-06-13 · 작성: AI dev team (Opus 메인 + Sonnet 경량 운영)

> **이 문서는 AMD Radeon 8060S(DirectML) 버전이다.** 같은 7B를 NVIDIA RTX 4060(CUDA, 4비트
> QLoRA)에서 학습·검증하고 두 어댑터를 비교한 기록은
> [training-benchmark-7b-cuda.md](training-benchmark-7b-cuda.md)를 참고. 요약: DirectML은
> seq 256/384 한계로 데이터 51%가 잘려 TS 제네릭·복잡/긴 출력에서 무너지는 반면, CUDA seq768
> 학습본은 그 항목들과 실파일(egovGeoportal) 변환까지 처리한다.

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

## 추론 검증 (학습된 어댑터)

`src/inference_7b.py` — 학습 스크립트의 스트리밍 로더 재사용(기존 inference.py는 7B 불가).
7B fp16 베이스 + 학습 어댑터(224 텐서) 적용, React 프롬프트 3종 생성:

| 프롬프트 | 결과 | 속도 |
|----------|------|------|
| useState 카운터 (EN) | ✅ 정확 | 8.4 tok/s |
| 리사이즈 감지 커스텀 훅 (한글) | ✅ `useWindowSize` 정확 | 9.2 tok/s |
| useDebounce TS 제네릭 | ✅ 관용적 구현 | 9.3 tok/s |

- 로딩 17.9초, 생성 **~9 tok/s** (DirectML fp16).
- 학습 loss 변동이 컸어도 **출력 품질 양호** — 베이스 모델이 강하고 LoRA가 깨뜨리지 않음.
- 학습 데이터의 한글이 깨져 있었음에도(인코딩 mojibake) 한글 프롬프트에 정상 응답.
- 실행: `python src/inference_7b.py` | `--base`(대조군) | `"프롬프트..."`(직접 지정).

## 데이터 큐레이션·재학습 (v1 → v2 → v3)

초기 7B(v1)는 seq256·원본 84개로 loss가 크게 출렁였다. 원인 분석:
- **데이터는 손상 아님**(UTF-8 정상). 콘솔 mojibake는 표시 문제였음.
- **loss 출렁임의 주원인은 로깅 아티팩트** — step당 accum 8개 중 마지막 1개 손실만 찍었음.
  → `train_directml.py`를 accum 윈도우 평균 손실 + epoch별 val_loss로 개선.
- **GitHub 스크랩(74개)이 본질적으로 어려운 신호** — 짧고 거의 동일한 지시문
  (`X 컴포넌트 작성해줘`)에 거대한 임의 라이브러리 소스를 매핑(같은 지시문→모순 정답,
  출력 51%가 256토큰 초과로 잘림).

개선(seq 384 채택 — 7B에서 plateau 38.7GB로 fit 확인):

| 버전 | 데이터 구성 | 개수 | val_loss |
|------|-------------|------|----------|
| v2 | 짧은 GitHub 큐레이션만(dedup+길이필터) | 46 | 7.72 |
| v3 | 합성 59 + 짧은 GitHub 27 + 핸드크래프트 6 | 92 | 5.44 |
| **v4** | **합성 136(60+87) + 짧은 GitHub 27 + 핸드 6** | **169** | **4.06** |

- v4: 합성 데이터를 2차로 +87개(synth2: useThrottle/Drawer/Combobox/TreeView 등) 확대 →
  학습셋 92→169(학습152/검증17). **val_loss 5.44→4.06**(매 epoch 하강 5.01→4.15→4.06),
  57step/18분. 데이터 2배가 25% 추가 개선. **서빙 기본 모델 = v4.**
- v5: 합성 3차 +100개(synth3: CommandPalette/useWebSocket/Kanban 등) → 학습셋 169→254
  (학습228/검증26). val_loss 4.92→4.24→**4.14**. 85step/27분.
  **★ 데이터 확대 plateau 도달**: 92→169은 5.44→4.06(큰 개선)이나 169→254는 4.06→4.14로
  **개선 없음**(val셋 재분할 노이즈 범위 내 동률). 동일 스타일 합성 데이터 추가는 수익 소진.
  더 낮추려면 *다른 분포*(복잡/실무 컴포넌트, 멀티파일 컨텍스트) 또는 epoch/LR 튜닝 필요.

- `build_dataset_v2.py`: GitHub 중복지시문 제거 + 출력 토큰 한도(짧은 것만) + 합성 병합.
- 합성 데이터 `data/handcrafted_synth.jsonl`(60개): Sonnet 경량 워커가 생성. useToggle/
  usePrevious/ErrorBoundary/Tabs/usePagination/useAuth 등 60개 주제, 지시→집중 정답(≤~280토큰).
- v3 val_loss가 매 epoch 하강(6.44→5.59→5.44), v2 대비 큰 개선. 학습 30step/9.6분.
- 재현: `python src/build_dataset_v2.py --cap 384 --gh-out-cap 200` →
  `python src/train_directml.py --dtype fp16 --seq 384 --out ./models/qwen-react-lora-7b-v3`

## seq 512 / 640 재학습 + 840토큰 붕괴의 진짜 원인 (2026-06-17)

"8060S가 VRAM만 충분하면 4060급 모델을 만든다"를 증명하기 위해, 48GB 카브아웃에서 **fp16 7B를
seq를 올려 재학습**했다(4060과 동일한 303개 데이터, 272/31).

| seq | smoke | 학습시간 | val_loss(ep1→2→3) | 비고 |
|-----|-------|----------|-------------------|------|
| 768 | **OOM** | — | — | 활성메모리가 48GB 천장 초과(step2 사망) |
| 512 | OK(~21s) | 43.9분 | 5.20→4.47→**4.38** | 데이터 95% 무잘림(p95=469) |
| 640 | OK(~27s) | 54.2분 | 6.15→5.26→**5.17** | 데이터 99% 무잘림(max 713) |

> seq별 val_loss는 **서로 비교 불가**(잘림 정도가 다른 검증셋 = 더 긴 seq일수록 더 어려운
> 타깃 → raw loss↑). 품질 판정은 출력으로 한다.

### ★ 840토큰 실파일 붕괴는 "seq 한계"가 아니라 **`<|im_start|>` 누수**였다 (핵심 발견)

seq512/640 모두 처음엔 EgovPaging.jsx(840tok) 변환에서 **빈 출력**이었다. 원시 토큰을 그대로
찍어보니(`scripts/diagnose_long_dml.py`) 모델이 0토큰을 낸 게 아니라:

```
생성 토큰: [151644, 151644, ... ×19, 151645]
        =  <|im_start|><|im_start|>...<|im_start|><|im_end|>
```

**긴 OOD 입력에서 Qwen 베이스의 챗템플릿 prior가 `### Response` 앵커를 이기고 `<|im_start|>`를
도배**하다가 eos로 끝나, 후처리가 잘라 빈 문자열이 됐던 것. 기존 FIM-정지 목록엔 `<|im_start|>`가
없어 못 걸렸다. 수정:

- **`suppress_tokens`로 `<|im_start|>` 포함 모든 특수/FIM 토큰의 *생성 자체*를 차단**(eos만 정지용 유지)
- **`min_new_tokens=24`**로 즉시-eos 붕괴 방지

→ 같은 seq640 어댑터가 **840토큰 EgovPaging.jsx를 완전한 TS로 변환**(interface PaginationProps,
JSX.Element[], null-safe 기본값). TS 제네릭·복잡 KR도 모두 클린(`###_AdjustorThunk` 누수도 사라짐).
**즉 8060S가 4060(seq768)만 처리하던 긴 실파일을 재학습 없이 추론 수정만으로 해냈다.** 수정은
`src/model_loader.py` generate()(서빙/MCP 공용)와 `scripts/verify_seq512_dml.py`에 반영.

> 교훈: "긴 파일엔 seq768 필수"는 **부분적으로만 참**이었다. 4060 seq768 어댑터는 긴 완전예제로
> `<|im_start|>` 억제를 학습해 수정 없이도 됐지만, **근본 원인은 추론측 특수토큰 처리**이며 8060S의
> 짧은 seq 어댑터도 그 처리만 더하면 동급 출력을 낸다.

### 남은 개선 레버
- 사소한 **literal `###` 텍스트 누수**(예: TanStack 출력 끝의 `###应用查看`) — 특수토큰이 아니라
  생성 텍스트라 suppress로 못 막음 → 학습데이터 EOS 위생 또는 `###` StoppingCriteria로.
- **LoRA capacity 확대**(MLP gate/up/down 타깃 추가 + r=32) 재학습으로 품질 자체 상승.
- 긴-입력 타깃 합성데이터(450~640tok) 주입으로 견고성 강화.

## 이전 한계 기록 (seq 256 시절)

- seq 256 고정 패딩이라 **긴 샘플은 잘림** → 품질 손해. fp16 + 소배치로 **loss 변동이 큼**
  (스텝별 0.6~12 진폭, 막판 ~1.0 수렴). 품질보다 "최대 규모 구동 + 시간 측정"이 목적이었음.
- 커스텀 루프는 **eval 미수행**(val 9개 미사용). → 이후 epoch별 val_loss 추가됨.
