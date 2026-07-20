# 141B(Mixtral-8x22B) gfx1151 가능성 테스트 — dev-history

**날짜:** 2026-07-20 야간 (halo/8060 Linux 세션, 오선생 실행)
**목적(범위 엄수):** Mixtral-8x22B-v0.1(MoE 141B총/39B활성)이 이 AMD Strix Halo(gfx1151, 통합메모리
64GB) 장비에서 **(a) HQQ 2bit로 로드**되고 **(b) LoRA 학습 스텝이 실제로 도는지** 짧은 런(smoke
8스텝)으로 증명. **풀 학습 아님.**

**결론 한 줄:** 141B의 벽은 **하드웨어·메모리가 아니라 transformers 5.13.1의 Mixtral MoE
리팩터링**이 HQQ 스트리밍 로더(per-Linear 양자화)와 구조적으로 충돌한 것. **격리 venv +
transformers 4.46.3 다운그레이드**로 우회. 다운로드·메모리·스왑은 전부 정상.

---

## 1. 환경 스냅샷

| 항목 | 값 |
|---|---|
| 장비 | AMD Strix Halo — Radeon 8060S(**gfx1151**), 통합메모리 64GB(OS 가시 ~60.9 GiB) |
| GTT 상한 | 56.0 GiB (card1, 부팅 cmdline 핀 — 상향 금지) |
| 스왑 | 64 GiB (`/dev/nvme0n1p3` 15.3G + `/swapfile` 49G, 두목 `swapon` 복구) |
| ROCm / torch | torch **2.10.0+rocm7.13.0a20260513** (HIP; `--backend cuda`가 HIP 사용) |
| 양자화 | HQQ (PYTORCH 백엔드; ROCm는 ATEN 불가). **bitsandbytes 금지**(wave64→gfx1151 wave32 웨지) |
| 모델 | `mistral-community/Mixtral-8x22B-v0.1` (Apache2.0, 미게이트, 8전문가 top2) |
| 모델 위치 | `/run/media/user/새 볼륨/mixtral-8x22b-v0.1` (외장 sdb2), bf16 **281.2GB**, 59샤드 |
| 학습 스크립트 | `src/train_directml.py`, `load_hqq_onthefly`=레이어단위 스트리밍 HQQ 양자화 |
| 본 venv | `~/.venvs/ai_model_rocm` — **transformers 5.13.1**(123B/72B 검증환경, 불변 유지) |
| Mixtral venv | `~/.venvs/ai_model_mixtral` — 본 venv 복사 + **transformers 4.46.3**(이번 테스트 전용) |

**메모리 계획:** 123B HQQ2bit 실측 GTT 피크 ~45.4GiB → 141B ×1.15 ≈ 52 GiB < 캡 56 GiB. 메모리 통과 예상.

## 2. 다운로드 (정상)

- `scripts/dl_mixtral8x22b.py` — snapshot_download resume + 무한 재개 루프, 외장 타깃, 디스크 가드.
- WiFi 발사(21:47) → 유선 전환(NM `ipv4.method` link-local→auto 교정, 675Mbps) → resume 루프가 끊김 매끄럽게 이어받음.
- **281.2GB, 59 safetensors, incomplete 0, 무결성 검증(샤드수 59/59 + 헤더 파싱) 통과.** 총 77.6분.

## 3. 1차 발사 크래시 (transformers 5.13.1) — 발사 ~10초, GTT 1.3GiB(로드 전 사망)

```
File src/train_directml.py:228, in load_hqq_onthefly
    set_module_tensor_to_device(model, name, device, value=t)
AttributeError: 'MixtralDecoderLayer' object has no attribute 'block_sparse_moe'
```
로더 로그: `양자화대상 Linear 224개, 비양자화 1515개` 직후 사망. systemd unit status=1/FAILURE.
GPU 건강(웨지·리셋 없음) — 순수 코드/구조 문제.

### 근본 원인 — transformers 5.13.1 Mixtral MoE 리팩터링

**모델 구조 변화(5.13.1):**
```
MixtralDecoderLayer.mlp = MixtralSparseMoeBlock      # (구) block_sparse_moe → (신) mlp
  .gate    = MixtralTopKRouter
  .experts = MixtralExperts
    .gate_up_proj = nn.Parameter(num_experts, 2*intermediate, hidden)  # w1&w3 융합, 전 전문가 스택
    .down_proj    = nn.Parameter(num_experts, hidden, intermediate)    # w2, 전 전문가 스택
```
**체크포인트 이름(2024 mistral-community, 구조식):**
```
model.layers.N.block_sparse_moe.gate.weight
model.layers.N.block_sparse_moe.experts.{0..7}.w1/w2/w3.weight   # 전문가별 개별 nn.Linear
```
- 속성 rename(`block_sparse_moe`→`mlp`) + 전문가 표현 변경(**개별 Linear → 융합 nn.Parameter**) + 텐서 개수·shape 전부 다름.
- `MixtralForCausalLM._checkpoint_conversion_mapping = None` — 구→신 융합 변환은 `from_pretrained` 내부 로직이 처리. 우리 `load_hqq_onthefly`는 `from_pretrained`를 우회하고 체크포인트 이름을 모델 트리에 직접 set → 변환을 못 받아 사망.

### 왜 단순 rename으로 못 고치나 (핵심)

HQQ 스트리밍 로더의 전제 = **"각 nn.Linear를 HQQLinear로 치환해 저비트 양자화"**. 그런데 5.13.1
전문가는 nn.Linear가 아니라 **융합 nn.Parameter** → 전문가를 HQQLinear로 양자화 불가. 141B를 60GB에
넣으려면 전문가 2bit가 **필수**인데 융합 표현에선 불가 → 현재 transformers로는 이 접근이 원천 불가.
즉 HQQ-per-Linear는 **dense 또는 융합 안 된 구조식 MoE 체크포인트**에서만 성립(123B dense·72B가
통과한 이유이자, 141B가 막힌 이유).

## 4. 해소 — 격리 venv + transformers 다운그레이드 (실측 시행착오)

**전략:** transformers를 전문가 융합 이전(구조식 MoE, 개별 Linear) 버전으로 다운그레이드. 단
**본 `ai_model_rocm`은 절대 불변**(123B/72B 검증환경 보호) → 격리 venv에서만.

| 스텝 | 실측 결과 |
|---|---|
| venv 격리 | `cp -a ai_model_rocm ai_model_mixtral` (15G, 62186 파일 동일 복사). 본 env 불변 확인(설치 후 5.13.1 유지) |
| 설치 수단 | 본 venv엔 pip 없음(uv제 venv) → **uv 0.11.28** 사용: `uv pip install --python .../ai_model_mixtral/bin/python transformers==4.46.3` |
| 동반 다운그레이드 | huggingface-hub 1.23.0→**0.36.2**, tokenizers 0.22.2→**0.20.3** (4.46.3 요구, 복사본에서만) |
| torch 2.10 호환 | **PASS** — transformers 4.46.3이 torch 2.10.0+rocm7.13에서 정상 import (hqq cpp-ext는 스킵 경고뿐, PYTORCH 백엔드 무관) |
| 구조 판정 | `scripts/check_mixtral_struct.py`: layer0 moe attr = **block_sparse_moe (MixtralSparseMoeBlock) 복원**, 체크포인트 키 **1739개 전부 모델 트리에 존재(missing=0, match=1.0000)**, `block_sparse_moe.experts.0.w1.weight` 존재 확인 → **VERDICT: COMPATIBLE** |

**버전 선택 근거:** 4.46.3(2024-11)은 Mixtral을 구조식(개별 Linear)으로 유지하는 안정 버전이자
torch 2.10과 import 호환. 1차 시도에서 바로 COMPATIBLE → 추가 하향/상향 탐색 불필요.

## 5. 2차 발사 (transformers 4.46.3) — 로드 진행 실증

1차 대조 물증: 양자화대상 Linear가 **224개(5.13.1, 어텐션만) → 1624개(4.46.3, 전문가 개별 Linear
전부 포함)**. 즉 전문가가 per-Linear로 노출되어 HQQ 로더가 정상 인식.

```
[23:30:44] 모델 로드: .../mixtral-8x22b-v0.1 (dtype=bf16, hqq-2bit-onthefly)
[23:30:46]   HQQ 스트리밍 로드: 양자화대상 Linear 1624개, 비양자화 텐서 115개 (nbits=2 gs=64)
[23:30:53]   비양자화 텐서 115개 적재 완료 (7.2s, RAM 가용 53.1GB)
[23:31:23]   20/1624 Linear 양자화 완료 | RAM 가용 52.5GB   ← 크래시 없이 진행
```

## 6. 첫 학습 스텝 크래시 → device 버그 규명·수정 (해결됨)

로드는 성공했으나 첫 forward에서 크래시:
```
RuntimeError: indices should be either on cpu or on the same device as the indexed tensor (cpu)
  apply_rotary_pos_emb: cos = cos[position_ids]   (modeling_mixtral.py:245)
```
**원인 확정(scripts/buf_check 실측, 재로드 없이):** `init_empty_weights` 빈 모델의 버퍼 **168개**
(56레이어 × `rotary_emb.inv_freq`/`cos_cached`/`sin_cached`)가 **전부 CPU**. 이들은 non-persistent
버퍼라 state_dict에 없어 `load_hqq_onthefly`의 스트리밍 루프(state_dict 텐서만 device 이동)가 건드리지
않음 → CPU 잔류 → forward에서 GPU 활성값과 device 불일치. 로더의 meta 검사는 `named_parameters()`만
보고 버퍼를 놓쳤음. dense(123B)에선 rotary 인덱싱이 이 조합으로 안 걸렸음(Mixtral 첫 노출).

**수정(커밋 `0d3fb4a`):** `load_hqq_onthefly` 끝에 모든 non-meta 버퍼를 device로 이동 + meta 버퍼 경고.
+ 자동체인 판정 grep 버그(`|| echo 0`가 `0\n0` 생성) 교정.

## 7. 계측 (정지 전까지 실측)

| 지표 | 값 |
|---|---|
| 로드 성공 | ✅ 1624 Linear HQQ2bit 양자화 완료(어텐션 224 + 전문가 1344 + 라우터 56) |
| 스트리밍 양자화 소요 | ~46분 |
| **GTT 피크 (card1)** | **44.2 GiB < 56 캡 (여유 12GiB)** — 141B 메모리 통과 실증 |
| 스왑 | 62G 여유 유지, SwapFree 붕괴 없음 |
| LoRA | 34.8M (0.098%, 어텐션-온리 q/k/v/o_proj) 부착 |
| 학습 스텝 | ⏸️ 첫 스텝 device 크래시 → 수정(`0d3fb4a`) 후 재검증은 **다음 세션**(두목 중단) |
| loss | 미측정 |

## 8. 결론

- **141B가 이 gfx1151/64GB 장비 메모리에 들어감은 실증됨** (GTT 44.2GiB < 56캡). 벽은 하드웨어가 아님.
- transformers 구조 비호환 → **격리 venv 4.46.3**로 해결(체크포인트 키 100% 매칭).
- 첫 스텝 device 버그 → **원인 규명·수정 완료**(`0d3fb4a`). 검증 smoke는 두목 중단으로 미완.
- 종합: **"141B 로드 실증 + device 수정 준비 완료", 스텝 검증·풀학습은 다음 세션.**

## 9. 다음 세션 To-Do

1. `0d3fb4a` 수정본으로 smoke 재검증(`--smoke 8`): 버퍼 이동으로 rotary device 통과 확인.
2. smoke 성공 시 → 풀학습 발사(`scripts/chain_mixtral8x22b_full.sh`, 에폭 지정) → 141B 어댑터 산출.
3. 격리 venv `~/.venvs/ai_model_mixtral`(4.46.3), 어텐션-온리, seq512, 스왑 64G 선행조건.

## 10. 교훈 / 후속 함의

- **천장 싸움이 메모리 → 소프트웨어 스택 호환성으로 이동.** 하드웨어(gfx1151 통합메모리)는 141B급도 담을 여력 실증.
- HQQ 스트리밍 로더는 **dense/구조식-MoE 전용**. MoE 대응 시 (a) 버전 핀 (b) 융합-전문가 지원 **(c) non-persistent 버퍼 device 이동**(이번 발견)이 필요.
- **재현성:** transformers 5.x는 MoE 표현을 적극 리팩터링 중 → 대형 MoE 로드 시 "체크포인트 포맷 ↔ 라이브러리 구조" 정합을 매번 확인. **Mixtral 전용 핀 = transformers 4.46.3 @ `~/.venvs/ai_model_mixtral`.**

---
## 부록: 재현 절차
```bash
# 1) 격리 venv (본 env 불변)
cp -a ~/.venvs/ai_model_rocm ~/.venvs/ai_model_mixtral
uv pip install --python ~/.venvs/ai_model_mixtral/bin/python transformers==4.46.3
# 2) 구조 판정(COMPATIBLE 확인)
~/.venvs/ai_model_mixtral/bin/python scripts/check_mixtral_struct.py
# 3) 체인 발사(다운로드 대기→검증→스왑가드→smoke 8스텝, detached --user 유닛)
setsid nohup bash scripts/chain_mixtral8x22b_feas.sh &
```
*기록: halo-linux 세션(오선생 실행·halo-pm 조율). 관련 GitHub 이슈 #7.*
