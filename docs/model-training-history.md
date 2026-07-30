# 모델 생성 이력 & 결과 요약 (llmmodelforreact)

> **목적**: 어떤 모델을 / 어느 환경·OS에서 / 어떤 설정으로 학습했을 때 **성공·실패**했는지의 실측 기록.
> 추후 재현·의사결정의 근거. 2026-06 ~ 2026-07-19, 두 장비 협업(4060 shas / 8060 halo).
> 기술 정본=`CLAUDE.md`, 쉬운 설명=`docs/project-story-plain-ko.md`, 채점기 사건=`docs/decision-harness-v2-ko.md`.

---

## 0. 한 줄 요약

**개인 노트북 급 장비에서 7B → 14B → 32B → 72B → 123B(100B급) → 141B(Mixtral-8x22B MoE) LoRA 학습을
순차 실증**했다 — **141B까지 실증**.
**단, "학습 가능"과 "품질 우위"는 별개** — 채점기(v1)가 신뢰 불가로 판명돼 v2로 재건했고, v2에서도
**가장 쓸만한 건 대형이 아니라 잘 튜닝된 7B**로 보인다(단 대형은 채점 병목으로 완전판 미측정).

---

## 1. 두 실행 환경 (★성공/실패가 갈리는 근본 변수)

| | **4060 노드 (shas)** | **8060 노드 (halo)** |
|---|---|---|
| GPU | NVIDIA RTX 4060 Laptop **8GB 전용 VRAM** | AMD Radeon 8060S (**Strix Halo gfx1151**), 통합메모리 |
| 메모리 구조 | GPU 전용 8GB + 시스템 RAM **분리** | **통합 60GB** (GPU+host 같은 물리풀) ← 핵심 차이 |
| OS | Windows 11 | 초기 Windows→**Ubuntu 26.04 LTS**(kernel 7.0) 듀얼부팅 |
| 백엔드 | **CUDA** (bitsandbytes nf4) | 초기 DirectML → **ROCm 7.13**(TheRock gfx1151 휠) |
| 양자화 | 4bit QLoRA (bnb) | bf16 / **HQQ 4bit·2bit** (bnb는 gfx1151서 깨짐) |
| 상한 | 8GB → **7B가 사실상 천장** | 통합 60GB+스왑 → **141B(MoE)까지** |
| 학습 스크립트 | `src/train_qlora.py` (HF Trainer) | `src/train_directml.py` (커스텀 루프) |

**교훈**: 같은 "4bit 학습"이라도 **CUDA(4060)에선 bnb가 멀쩡, ROCm(8060)에선 bnb가 깨진다**(wave32 버그).
8060은 **HQQ/torchao**로 우회해야 했다. 환경이 곧 방법을 결정한다.

---

## 2. ★ 환경별 성공/실패 매트릭스 (실측)

### 8060 (Strix Halo / ROCm) — 대형모델 트랙

| 모델 | 정밀도 | 백엔드 | 결과 | 근거 |
|---|---|---|---|---|
| 32B | 4bit **bnb** | ROCm | ❌ **실패** | `hipErrorLaunchFailure` GPU 웨지. `__AMDGCN_WAVEFRONT_SIZE` 미정의→WARP_SIZE 64 폴백, gfx1151은 wave32 → OOB |
| 32B | 4bit **HQQ** | ROCm | ✅ **완주** | 78스텝, 194s/step, GPU 21.4GB, 웨지0. bnb 버리고 HQQ 쓰니 통과 |
| 14B | bf16 | ROCm | ✅ 완주 | val 0.48, seq1024, GPU 28.7GB |
| 72B | HQQ 2bit | ROCm | ✅ 완주 | val **0.796**, 39스텝, 411s/step, GPU 28GB |
| 72B | HQQ **4bit** | ROCm | ✅ **완주** | val **0.5753**, seq1024, Q2보다 무거운 44.4GB (통합풀 마진 얇음) |
| **123B** (Mistral-Large) | HQQ **2bit** | ROCm | ✅ **완주(100B급)** | val **0.4704**, ~6h, 어댑터 1.07GB, GPU **40.3GB**, 웨지0. **loss 5.27→0.42 교과서적** |
| **141B** (Mixtral-8x22B, MoE) | HQQ **2bit** | ROCm | ✅ **완주(최대)** | val **0.6182**, 3에폭 118스텝, 11.4h(344s/step), GTT피크 **47.3GiB**/56캡, 어댑터 139.5MB(어텐션-온리 r16, 34.8M/0.098%). ⚠️MoE라 transformers **4.46.3 격리venv**(5.13 전문가융합 비호환 회피) + **rotary 버퍼 device 수정**(0d3fb4a) 필요 |
| 32B/70B/123B | bf16 (무양자) | ROCm | ❌ 불가 | 메모리 초과 (32B bf16=65GB > 상한) |

**8060 결정적 실측 3가지**:
- **통합메모리 = GPU+host 같은 풀**: GPU가 40GB 쥐면 host RAM 바닥 → **스왑 15→64GB 라이브 증설**로 버팀.
- **메모리 예측 공식**(32B/72B/123B 3점 검증): `GPU_peak = 실측앵커 × 파라미터비 × seq비`. ×계수 폐기.
- **속도**: **2bit이 4bit보다 빠름**(72B Q2 400s < Q4 500s). 메모리대역폭 병목이라 가중치 절반이 이득.
- **전력**: 밤샘 학습엔 **200W 충전기 필수**(100W는 방전死).
- **MoE 대형은 라이브러리 버전 정합이 관문**: transformers 신버전(5.13)이 Mixtral 전문가를 융합
  nn.Parameter로 리팩터해 HQQ per-Linear 로더와 충돌 — 141B는 학습에 쓴 버전(4.46.3)과 다른
  transformers로 로드하면 dense 모델과 달리 곧바로 AttributeError로 죽는다(실측: `bdprobe141b`
  시도, `MixtralDecoderLayer`에 `block_sparse_moe` 없음). **dense와 달리 venv/버전을 못 섞는다.**

> **🔄 2026-07-31 재실행 진행 중**: 123B 재학습(베이스 재다운로드 중) · 72B 4bit 재학습 ·
> 141B/123B batch-decode 채점(이슈 #9, 진행 중 — 결과 후속). 141B는 학습 완주했으나
> **채점은 아직 진행 중이라 §3 최종결과표엔 점수 미기재**(아래 참고).

### 4060 (RTX 4060 8GB / CUDA) — 7B 튜닝 트랙

| 어댑터 | 데이터/설정 | 결과 | 비고 |
|---|---|---|---|
| r4mlp | cap384 283개, qkvo_mlp r16, seq768 | ✅ | 옛 챔피언(v1 71.4%) |
| r6base | cap1024 351개, 동일설정 | ✅ | 옛 "챔피언"(v1 88.6%) — **실은 seed 뽑기+백틱 아티팩트** |
| r6admin | +admin 짧은패턴 10 | ✅ 학습 / ❌ 효과 | v1 74.3%, **−14.3pp 회귀** |
| r7abl | r6base − egovreal 8건 | ✅ | ablation, v2 최고 |
| cap512 | cap512 339개 | ✅ | cap 사다리 실험 |
| seed1234 | r6base와 동일, **seed만 42→1234** | ✅ | **노이즈 바닥 측정 = Δ20pp 폭로** |
| 14B 4bit | — | ❌ | 8GB에 fp16 7B(14GB)도 OOM. **14B는 4060 불가** |

**4060 교훈**: 8GB는 7B가 천장. `ho-admin-medit`(22KB 입력) 채점은 8GB 벼랑에서 스래싱(1태스크 14h+).

---

## 3. ★★ 최종 결과표 — v1 vs v2 재점수 (heldout7)

**채점기가 두 개다.** v1=`max(0,1-에러/5)`(신뢰불가 판명), v2=구문/타입분리+충실도축(양노드 교차검증 5/5).
**v2가 정본.** 과거 원장은 불변으로 두고 병기.

| 어댑터 | 체급 | 환경 | n | **v1%** | **v2%** |
|---|---|---|---|---|---|
| **r6base** (옛 챔피언) | 7B | 4060 4bit | 7 | **88.6** | **71.1** ⚠️ |
| r7abl (r6base−egovreal) | 7B | 4060 4bit | 7 | 80.0 | **75.0** |
| seed1234 (r6base 리시드) | 7B | 4060 4bit | 7 | 68.6 | 72.4 |
| r6admin | 7B | 4060 4bit | 7 | 74.3 | 67.7 |
| r4mlp | 7B | 4060 4bit | 7 | 71.4 | 64.9 |
| cap512 | 7B | 4060 4bit | 7 | 60.0 | 65.9 |
| 8060-14b-v1 | 14B | 8060 fp16 DirectML | 7 | 62.9 | 73.9 |
| 14b-rocm | 14B | 8060 bf16 ROCm | 7 | 60.0 | 71.5 |
| 32b-rocm-hqq4bit | 32B | 8060 HQQ4 ROCm | **4** | 60.0 | 72.0 |
| 123b-hqq2 (Mistral-Large) | 123B | 8060 HQQ2 ROCm | **5** | 56.0 | 67.0 |

> ⚠️ **표를 읽는 법 (반드시)**:
> - **v1은 신뢰 불가**. `r6base 88.6%`는 seed만 바꿔도 68.6%로 흔들렸고(±20pp), 백틱 하나로 부풀려졌다.
> - **v2에서 `r6base 88.6→71.1`로 급락** = 그 88.6이 아티팩트였다는 증거. v2가 진실에 가깝다.
> - **32B(n=4)·123B(n=5)는 부분측정** — 가장 변별력 큰 medit·mlist가 채점 타임아웃으로 빠짐.
>   **대형모델 순위는 이 표로 판정 불가.** 완전판은 채점 배치디코드 도입 후.
> - **동일 n=7 비교만 유효**: 7B(r7abl 75.0, r6base 71.1) ↔ 14B(v1 73.9, rocm 71.5) → **현 표본에선 구분 불가(노이즈 이내). "7B>14B"도 "14B>7B"도 아닌 "모른다".**
> - **141B(Mixtral-8x22B)는 학습 완주(val 0.6182)했으나 채점(batch-decode, 이슈 #9)은
>   2026-07-31 기준 진행 중** — 점수 미확정. 확정되기 전까지 이 표에 행을 추가하지 않는다
>   (점수 날조 금지). 완료 시 이 표에 후속 갱신.

---

## 4. 핵심 발견 (성공·실패에서 배운 것)

1. **"학습 가능"과 "품질 우위"는 별개**. 123B 완주(A)는 파이프라인이 끝까지 돈 사실로 증명 — **채점기가 망가져도 참**. 하지만 "123B가 낫다"(B)는 분산 통제·완전 채점 없이 주장 불가.
2. **채점기(측정 도구)가 최대 리스크였다**. seed 분산 ±20pp + 백틱 아티팩트 + 스텁 과잉보상. **몇 주간 이 위에서 인과를 세웠다.** → v2 재건. `docs/decision-harness-v2-ko.md`.
3. **데이터는 양이 아니라 품질·구성**. 짧은 합성 추가=회귀(r6admin −14.3pp), 데이터量↑=희석. 핵심 스킬 적정량이 sweet spot.
4. **val_loss를 품질지표로 쓰지 말 것**. loss 낮은 쪽이 일반화는 나빴다(r4mlp 0.385→71.4% vs r6base 0.410→88.6%). seed 실험서도 loss 거의 같은데 점수 20pp 차.
5. **평가가 병목**. 4bit batch=1 디코드 0.36 tok/s → 123B 채점 20h 타임아웃 5/7. 배치디코드/llama.cpp가 다음 관문.
6. **환경이 방법을 결정**. bnb는 CUDA OK / gfx1151 깨짐 → HQQ. 통합메모리는 스왑 백스톱. Windows 정적분할 vs Linux GTT 동적.

---

## 5. 재현 커맨드 (요약)

```bash
# 4060 (CUDA 4bit) — 7B
python src/build_dataset_v2.py --cap 1024 --gh-out-cap 512    # 351개
python src/train_qlora.py --seq 768 --rank 16 --target qkvo_mlp --out models/<name>
# ⚠️ train_directml.py 아님(그건 fp16 전용, 8GB서 OOM)

# 8060 (ROCm HQQ) — 대형
python src/train_directml.py --backend cuda --dtype bf16 --seq N   # bf16
# HQQ 2bit/4bit는 HQQLinear 수동치환(transformers 5.13 HqqConfig 파손) + HQQBackend.PYTORCH

# 채점 (양노드 공통, GPU0 재점수)
python scripts/score_v2.py --labels <라벨>     # v2(정본). v1은 eval_hard_tsc.py
```

**함정**: ①4060은 train_qlora(4bit), 8060은 train_directml — 헷갈리면 OOM. ②`--cap`은 출력상한 아닌 전체 프롬프트 토큰상한(최대 레버). ③config의 fp16/grad_ckpt는 런타임에 덮어써짐. ④학습 오염 방지 3중가드(`comms/v2-proposal/guard_eval_leak.py`).

---

## 6. 미해결 / 다음 (2026-07-19 기준)

- **대형모델 완전 채점** — 배치디코드/llama.cpp 도입 후 32B/72B/123B를 n=7로. "체급이 v2에서 사나"의 진짜 답.
- **v2 노이즈 바닥** — seed 스윕 ≥3 (미측정).
- **태스크 7→20** — Core-16 선정·오염가드 완료, 실제 생성은 GPU 대기.
- **★원래 목적 = React 어시스턴트 배포** — 배포모델은 아마 대형 아닌 잘 튜닝된 7B/14B. 이슈 #9.

---

*이력 정리: shas-pm(4060) + 팀(앗·큐·데·오·개동·비선생) + halo-ubuntu-pm(8060). 협업 원본 = `genishs/claude-agent-team` 이슈 #7(학습)·#9(채점·추론).*
