# React Coding Assistant (로컬 LLM)

AMD Ryzen AI Max+ 392 (Strix Halo, Radeon 8060S) 위에서 **직접 학습하고 실행하는** React 특화 로컬 코딩 어시스턴트.

> 📊 **전체 학습·채점 이력 정본 → [`docs/training-history-master.md`](docs/training-history-master.md)**
> 로그에서 기계 추출한 원장(학습 17건 / 채점 전수). 해석·교훈은 [`docs/model-training-history.md`](docs/model-training-history.md).

---

## 성과 요약 (2026-08 기준)

**개인 노트북 한 대로 1.5B → 7B → 14B → 32B → 72B → 123B → 141B(MoE) LoRA 학습을 순차 실증**했다.

| 항목 | 결과 |
|---|---|
| 최대 학습 완주 | **141B** (Mixtral-8x22B MoE, HQQ 2bit, seq1280×2ep, 10.5h) |
| 최저 val_loss | **0.4642** (123B Mistral-Large, HQQ 2bit) |
| **실질 최대 배포 체급** | **72B** (Q4_K_M 44GB, heldout7 v2 **64.7%**) |
| 총 GPU 가동 | 약 72시간 / 본런 8회 + smoke·짧은런 9회 |
| 어댑터 산출물 | 31개 (외장 아카이브 보관, git 미포함) |

### 🔴 핵심 결론 3가지

1. **Q2_K(2bit) 추론은 코드 생성에 쓸 수 없다.** MoE(141B)는 반복 폭주(`// @ts-ignore` 569회), dense(123B)는 본문 포기(`// ... unchanged`). 증상은 달라도 결론은 같다.
2. **이 하드웨어에서 100B급 이상은 "학습은 되지만 배포는 불가".** GTT 56GiB가 Q2_K를 강제하는데(Q3_K 60~68GB·Q4_K_M 73~85GB는 적재 불가) 그 Q2_K가 모델을 파괴한다.
3. **val_loss는 배포 품질을 예측하지 못한다.** 123B는 val 0.4704로 캠페인 최고였으나 실제 추론에서는 12.2%.

---

## 시스템 스펙

| 항목 | 사양 |
|------|------|
| CPU | AMD Ryzen AI Max+ 392 (Zen 5, 12코어 / 24스레드) |
| Memory | **64GB 통합 메모리** (CPU·GPU 공유) — 물리 60GB 가용 |
| GPU | AMD Radeon 8060S (**gfx1151**) |
| **GTT 캡** | **56 GiB** (pinned, 스왑 불가) — 학습·추론 상한을 결정하는 값 |
| 스왑 | 64GB (NVMe) |
| NPU | XDNA 2 |
| **OS** | **Ubuntu 26.04 LTS** (kernel 7.0) — Windows 11 듀얼부팅 |

> **통합 메모리 = GPU와 CPU가 같은 물리 풀을 공유**한다. 일반 PC의 "VRAM + 시스템 RAM 합산"과 달라,
> CPU 오프로드만으로는 가용 메모리가 늘지 않는다. 실질적인 추가 계층은 mmap(디스크)과 스왑뿐이다.

### 백엔드

| 용도 | 스택 |
|---|---|
| **학습** | **ROCm 7.13** + PyTorch (TheRock gfx1151 휠) + **HQQ** 양자화 |
| **추론·채점** | **llama.cpp (Vulkan)** + GGUF |
| ~~DirectML~~ | 초기 1.5B~7B 시절에 사용 (연혁 참조) |
| ~~bitsandbytes~~ | gfx1151 wave32 버그로 사용 불가 → HQQ로 우회<br>※ 2026-07 ROCm 정식 wheel 배포로 상황 변경 가능성 — 재검토 대상 |

---

## 학습 결과 (본런 8건)

| 파라미터 | 베이스 모델 | 양자화 | seq | ep | 시간 | GPU | **val_loss** | 어댑터 |
|---|---|---|---|---|---|---|---|---|
| 32B | qwen2.5-coder-32b | HQQ 4bit | 1024 | 2 | 4.3h | 21.4GB | 0.4868 | 512MB |
| 72B | qwen2.5-72b-instruct | HQQ 2bit | 1024 | 1 | 4.6h | **28.0GB** | 0.7963 | 803MB |
| 72B | qwen2.5-72b-instruct | HQQ 4bit | 1024 | 1 | 5.5h | 44.4GB | 0.5753 | 803MB |
| 72B (v2) | qwen2.5-72b-instruct | HQQ 4bit | 1024 | 1 | 4.7h | 44.4GB | 0.5706 | 803MB |
| **123B** | mistral-large-2411 | HQQ 2bit | 512 | 1 | 5.4h | 40.3GB | **0.4704** | 1067MB |
| **123B (v2)** | mistral-large-2411 | HQQ 2bit | 512 | 1 | 4.7h | 40.3GB | **0.4642** ★ | 1067MB |
| **141B** | mixtral-8x22b-v0.1 (MoE) | HQQ 2bit | 512 | **3** | **11.4h** | 43.9GB | 0.6182 | 133MB |
| **141B** | mixtral-8x22b-v0.1 (MoE) | HQQ 2bit | **1280** | 2 | 10.5h | 44.0GB | 0.7132 | 133MB |

공통: `group_size 64` · `lora_r 16` · `alpha 32` · `grad-checkpoint`

**재현성 확인**: 같은 설정 재학습에서 123B 0.4704→0.4642, 72B 0.5753→0.5706 — 두 건 모두 재현 성공.

---

## 채점 결과 (heldout7 · `max_new 4096` · n=7 · llama.cpp 동일조건)

| 모델 | 추론 양자화 | **v2%** | 잘림 | 상태 |
|---|---|---|---|---|
| **7B** (4060-r4mlp) | **Q8_0** | **70.5** | 0/7 | 🟢 정상 |
| **72B** (Q4-v2) | **Q4_K_M** | **64.7** | 2/7 | 🟢 정상 |
| **123B** (챔피언) | Q2_K | **12.2** | 1/7 | 🔴 구문 파손 |
| **141B** (원본) | Q2_K | **10.7** (n=3) | 4/7 | 🔴 폭주 붕괴 |

**양자화 임계선: Q8 정상 > Q4 정상 >> Q2 붕괴**

> ⚠️ 채점 조건을 통일하지 않으면 비교가 무의미하다. 72B는 `max_new 2048`에서 58.6%,
> **4096에서 64.7%** (+6.1pp) — 절단 때문에 6pp가 왜곡됐다.

---

## 빠른 시작 (현행 · Linux/ROCm)

### 학습

```bash
# ROCm venv (dense 모델)
source ~/.venvs/ai_model_rocm/bin/activate

# Mixtral(MoE) 전용 — transformers 4.46.3 격리 venv
source ~/.venvs/ai_model_mixtral/bin/activate

python src/train_directml.py --backend cuda --dtype bf16 \
  --base <베이스경로> --quant hqq --hqq-nbits 2 --hqq-group-size 64 \
  --lora-r 16 --grad-ckpt --seq 512 --epochs 1 --out models/<이름>
```

**장시간 학습은 반드시 systemd 유닛으로 띄운다** (터미널·세션이 죽어도 살아남음):

```bash
bash scripts/gpu_job.sh --name <잡이름> --cwd "$PWD" -- python src/train_directml.py ...
bash scripts/gpu_job.sh --logs <잡이름>     # 로그 추적
```

> ⚠️ `gpu_job.sh`의 `REPO_DEFAULT`가 옛 경로로 하드코딩돼 있다. **`--cwd`를 항상 명시할 것.**

### 채점 (llama.cpp)

```bash
# 1) base → GGUF → 양자화
python <llamacpp>/convert_hf_to_gguf.py <base> --outtype q8_0 --outfile <out>.gguf
<llamacpp>/build-vulkan/bin/llama-quantize --allow-requantize <in> <out> Q4_K_M 24

# 2) 어댑터 → GGUF
python <llamacpp>/convert_lora_to_gguf.py models/<어댑터> --base <base> --outtype f16 --outfile <out>.gguf

# 3) 서버 + 채점
llama-server -m <모델>.gguf --lora <어댑터>.gguf --port 8811 -c 8192 -ngl 999
EGOV_SRC=<정답소스> python scripts/eval_hard_tsc_llamacpp.py \
   --server-url http://127.0.0.1:8811 --label <라벨> --heldout --max-new 4096
python scripts/score_v2.py --label <라벨>
```

> ⚠️ llama-server는 **로딩 중 `/health`에 503**을 준다. 준비 확인은 반드시 **`curl -sf`**로 —
> `-f` 없이 쓰면 로딩 중을 "준비됨"으로 오판해 전 태스크가 실패한다(실사고 있음).

---

## 서빙 (API / MCP / CLI)

> 아래는 **1.5B~7B 시절에 구축한 서빙 경로**다. Windows/DirectML 전제로 작성돼 있으며
> Linux/ROCm 환경에서의 현행 동작은 **미검증**이다.

```bash
python src/inference.py     # CLI 대화형
python src/serve_api.py     # REST API (Swagger: http://localhost:8000/docs)
```

MCP 서버는 `.mcp.json`으로 Claude Code에 등록된다.

```typescript
const res = await fetch('http://localhost:8000/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ instruction: '...', max_new_tokens: 512 })
});
```

---

## 프로젝트 구조

```
ai_model/
├── docs/
│   ├── training-history-master.md   ★ 학습·채점 원장 (정본)
│   ├── model-training-history.md    해석·교훈 정리본
│   └── ...
├── src/
│   ├── train_directml.py            학습 (ROCm, HQQ 스트리밍 양자화)
│   ├── model_loader.py / serve_api.py / mcp_server.py   서빙
│   └── ...
├── scripts/
│   ├── gpu_job.sh                   ★ systemd 유닛 러너 (장시간 작업 필수)
│   ├── probe_141b_maxseq.py         seq 상한 프로브
│   ├── eval_hard_tsc_llamacpp.py    llama.cpp 채점 하니스
│   ├── score_v2.py                  채점기 v2 (정본)
│   └── ...
├── eval_results/                    채점 결과 JSON + 생성물 .tsx
├── comms/scores-*.jsonl             점수 원장
└── models/                          어댑터 (대용량은 gitignore, 외장 보관)
```

⚠️ **대용량 바이너리는 git에 넣지 않는다** (`.gitignore`: `models/**/*.safetensors`, `tokenizer.json`, `*.gguf`).
어댑터·GGUF·base 모델은 외장 아카이브에만 보관한다.

---

## 다음 과제

- [ ] 🔴 **어댑터 기여도 검증** — 원본 단독(`--lora` 제거) 점수를 한 번도 잰 적이 없다. GPU 72시간 투자의 값어치가 미확인. **~50분이면 검증 가능 → 최우선**
- [ ] 🚨 **141B LoRA 타깃 재확인** — "MoE라 MLP에 LoRA 못 붙임"은 오진 가능성. transformers 4.46.3의 Mixtral expert는 fused가 아닌 `nn.Linear w1/w2/w3`라 타깃 가능했다(학습가능 0.098%의 원인일 수 있음)
- [ ] 🔓 **스택 재검토** — Unsloth가 gfx1151 공식 지원(2026-07), bitsandbytes ROCm 정식 wheel(2026-07) → HQQ 핀(transformers 4.46.3) 해제 검토
- [ ] **신세대 모델로 전환** — 크기가 아니라 "배포 가능한 양자화에 들어가는 체급". 후보: Qwen3.6-27B(dense), 50GB 이하 MoE
- [ ] 태스크 7→20 확대 (Core-16 선정·오염가드 완료, 생성 대기)

---

## 연혁

| 시기 | 내용 |
|---|---|
| 2026-06 | Qwen2.5-Coder **1.5B** LoRA v1~v4 (데이터 4→84개), Windows + **DirectML** |
| 2026-06 | **7B** 업그레이드, RTX 4060(CUDA) 4bit QLoRA 교차검증 |
| 2026-07 | **Linux/ROCm 전환** → 14B·32B·72B, HQQ 양자화 도입 |
| 2026-07 | **123B**(Mistral-Large) 100B급 돌파 |
| 2026-07~08 | **141B**(Mixtral MoE) 완주, seq1280 실증 |
| 2026-08 | llama.cpp 채점 체계 구축, **전 모델 동일조건 재측정** → Q2_K 임계선 발견 |

초기 1.5B 버전 이력(v1 4개 → v4 84개, train_loss 0.634→0.734)은 git 히스토리 참조.

---

## 주요 기술 스택

| 용도 | 라이브러리 |
|------|----------|
| 학습 백엔드 | **ROCm 7.13** (TheRock gfx1151 휠) |
| 양자화(학습) | **HQQ** 0.2.8 (2bit/4bit, `SUPPORTED_BITS=[8,6,5,4,3,2,1.58,1]`) |
| 추론·채점 | **llama.cpp** (Vulkan) + GGUF |
| LoRA | peft |
| 모델/토크나이저 | transformers (dense 5.x / **Mixtral은 4.46.3 격리 venv**) |
| REST API | FastAPI + uvicorn |
| MCP 서버 | mcp |
