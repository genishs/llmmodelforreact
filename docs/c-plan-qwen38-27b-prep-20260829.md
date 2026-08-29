# C안 — Qwen3.8-27B 준비 결정로그 (2026-08-29, 오선생)

## 임무 범위
PM(피선생) 지시: GPU 점유 중(72B 채점 잡 + 예정된 A안 스모크) → **GPU 미사용 준비·검증만.**
학습/추론 착수 금지, 다운로드·스택 검증·계획 수립까지.

## 1) 모델 실존 확인

- **정확한 repo id: `Qwen/Qwen3.8-27B`** (HF API `id` 필드로 직접 확인, 추측 아님).
- 공개일 2026-08-14 15:00 UTC, **Apache-2.0**(LICENSE 파일 원문 직접 확인 — 표준 Apache 2.0, 추가 조항 없음).
- **총 55.586GB** (safetensors 18샤드 + 비전타워 + MTP 헤드 포함, `?blobs=true`로 파일별 크기 합산 실측).
- `model_type: "qwen3_5"`, `architectures: ["Qwen3_5ForConditionalGeneration"]` — **비전-언어(VL) 모델**
  (pipeline_tag=image-text-to-text). "27B"는 27.78B 텍스트 백본 기준 표기로 보이며 비전타워(ViT depth27,
  hidden1152)·MTP(1레이어)가 추가로 딸려 있어 체크포인트 총량은 그보다 큼.
- **코더 특화 변형 없음** — `Qwen/Qwen3.8-27B`, `Qwen3.8-27B-FP8` 두 개만 author=Qwen 검색에 나옴.
  Base/Instruct 별도 분리 없음(단일 레포가 이미 chat_template.jinja 보유 → instruct-tuned로 판단).
  huginnfork·unsloth의 FP8/GGUF/NVFP4는 서드파티 재양자화본, 공식 아님.

## 2) 🔴 스택 호환성 검증 — 실행 기반, 추측 아님

### 2-1. venv 실측 버전 (pip 부재 venv라 `python -m pip` 대신 import로 확인)
`/home/user/.venvs/ai_model_rocm`: transformers **5.13.1**, hqq **0.2.8.post1**,
bitsandbytes **0.43.3.dev**, torch **2.10.0+rocm7.13.0a20260513**, peft **0.19.1**, accelerate **1.14.0**.

### 2-2. bitsandbytes — 여전히 실질 불가 (신규 이유)
import는 되지만 **"Skipping import of cpp extensions due to incompatible torch version.
Please upgrade to torch >= 2.11.0 (found 2.10.0)"** — 실제 4bit/8bit 커널이 비활성 상태.
gfx1151 wave32/64 금지 이력과 별개로, 지금은 **torch 버전 자체가 안 맞아 quantized ops가 로드 안 됨.**
→ HQQ 경로 사용이 사실상 유일한 선택지(기존 32B 결정과 동일 결론, 재확인).

### 2-3. HQQ + transformers 5.13.1 — "자동경로는 깨져있다, 수동 치환은 된다"를 재확인
- `transformers.utils.is_hqq_available()` = True, `AUTO_QUANTIZER_MAPPING`에 `hqq` 등록됨.
- `HqqConfig` 생성, `AutoHfQuantizer.from_config(...).validate_environment()`까지는 **통과**.
- 단, `train_directml.py`의 기존 주석(2026-07-15 기록)이 이미 밝힌 대로 `from_pretrained(quantization_config=HqqConfig(...))`
  자동경로는 `transformers/quantizers/base.py get_quantize_ops()` 추상화 이후 `quantizer_hqq.py` 미구현으로
  `NotImplementedError`가 난다 — 이번 세션에서 재실행 확인은 안 했지만(코드 근거 확인으로 충분), 드라이버가
  이미 이 문제를 우회하는 `load_hqq_onthefly()`(수동 `HQQLinear` 치환)를 갖고 있어 **C안도 그대로 재사용 가능.**
- **핵심 신규 검증(HQQ 코어 자체)**: `HQQLinear(nn.Linear, ...)` CPU 실행 → forward 정상.
  `prepare_model_for_kbit_training` + `peft.get_peft_model`(LoRA) + forward + backward를 **합성
  Qwen3_5 소형 모델(hidden32, 4레이어, linear_attention 3 + full_attention 1)로 실제 실행** →
  38/38 trainable 파라미터에서 유한 gradient 확인. **결론: HQQ+PEFT LoRA 파이프라인은 하이브리드
  어텐션 구조에서도 동작한다(실행 검증 완료).**

### 2-4. 🔴🔴 신규 발견 — Qwen3.8-27B는 하이브리드(선형+완전) 어텐션 구조, 기존 LoRA 설정이 안 맞는다
`config.json`의 `text_config` 실측:
- `num_hidden_layers: 64`, `full_attention_interval: 4` → **64개 중 16개(25%)만 `full_attention`
  (q_proj/k_proj/v_proj/o_proj), 나머지 48개(75%)는 `linear_attention`**(게이트 선형어텐션,
  Qwen3-Next 계열과 동일 패턴). linear_attention 레이어의 Linear 모듈명은 `in_proj_qkv`,
  `in_proj_z`, `in_proj_a`, `in_proj_b`, `out_proj`로 **q/k/v/o_proj와 이름이 다름.**
- 기존 `config/training_config*.yaml`(7B/14B/32B 전부)의 `target_modules: [q_proj,v_proj,k_proj,o_proj]`를
  그대로 쓰면 **레이어의 25%에만 LoRA가 붙고 75%(선형어텐션 대부분)는 완전히 학습에서 빠진다** —
  품질에 큰 영향을 줄 수 있는, 이번 조사 없이는 아무도 몰랐을 함정.
- **조치**: `config/training_config_qwen38_27b.yaml` 신규 작성, target_modules에 9종
  (q/k/v/o_proj + in_proj_qkv/in_proj_z/in_proj_a/in_proj_b/out_proj) 전부 포함.
  합성 모델로 실제 부착 확인(19개 LoRA 부착 지점 로그: linear_attention 3레이어×5개 + full_attention 1레이어×4개).

### 2-5. 🔴🔴 신규 발견 — 체크포인트 텐서명과 모델 파라미터명 불일치 (로더 수정 필요)
- 실제 체크포인트(`model.safetensors.index.json`) 텐서명: `model.language_model.layers.*`,
  `model.language_model.embed_tokens`, `model.language_model.norm`, `model.visual.*`, `mtp.*`, `lm_head.weight`.
- `AutoModelForCausalLM.from_config(cfg)`가 반환하는 실제 클래스는 `Qwen3_5ForCausalLM`(텍스트 전용,
  자동으로 VL config에서 잘 뽑아줌 — 이 부분은 정상 동작 확인됨)인데, 이 클래스의 파라미터명은
  `model.layers.*`, `model.embed_tokens`, `model.norm`, `lm_head.weight` — **`language_model.` 접두어가 없다.**
- `train_directml.py`의 `stream_load_to_device`/`load_hqq_onthefly`는 체크포인트 키를 그대로
  `set_module_tensor_to_device(model, name, ...)`에 넘기므로 **현재 코드로는 텍스트 백본 가중치가
  단 한 개도 안 실린다.** (다행히 로더 끝의 `remaining = [meta 텐서 목록]` 체크가 있어 **조용한 손상이
  아니라 즉시 RuntimeError로 fail-fast** — 그래도 GPU에서 실행하면 무의미한 로드 시간을 낭비하게 됨.)
- **실행 검증(합성 체크포인트)**: 소형 Qwen3_5ForCausalLM으로 실제 가중치를 만들고, 체크포인트처럼
  `model.` → `model.language_model.` 접두어를 붙이고 가짜 `model.visual.*`/`mtp.*` 텐서를 섞은 뒤,
  "`model.language_model.` 제거 + `model.visual.`/`mtp.` 스킵" 리매핑을 적용해 스트리밍 로드 →
  **전체 파라미터 100% 적재, reference forward logits와 완전 일치(`allclose`, max diff 0.0)**.
- **조치(코드는 아직 미반영)**: `train_directml.py`의 `stream_load_to_device`/`load_hqq_onthefly`에
  범용 prefix-remap 훅이 필요. **A/B안이 쓰는 공유 드라이버 파일이라 이번 턴엔 수정하지 않음**
  (GPU 작업 중인 상태에서 공유 코드를 건드리는 리스크 회피 — 가역성 원칙). 검증된 리매핑 로직은
  `docs/`에 기록해뒀으니 착수 시 반영. 대안으로 C안 전용 별도 로더 함수를 추가하는 것도 가능
  (기존 함수는 그대로 두고 `load_hqq_onthefly_vlm`류로 분리) — 착수 지시 시점에 PM과 협의.

### 스택 호환 판정: **조건부 가능(conditional go)**
- 되는 것(실행 검증 완료): HQQ 4bit 양자화, PEFT LoRA(하이브리드 타깃 포함), forward/backward, config 로드.
- 안 되는 것(실행 확인, bitsandbytes): torch 2.10 cpp ext 비활성 → bnb 사용 불가(예상대로, HQQ로 우회).
- 고쳐야 하는 것(코드 미반영, 방법은 검증됨): 체크포인트 prefix remap. **이거 없이 GPU에서 돌리면
  100% 즉시 실패**(fail-fast라 안전하지만 시간 낭비).
- 미검증(다음 턴 GPU 필요): 실제 27B 가중치로 로드 성공 여부, HQQ 스트리밍 로드 소요시간,
  s/step 실측, linear_attention torch-fallback의 실제 속도(아래 4절).

## 3) 다운로드

- 저장 위치: `/run/media/user/sgshs_data/ai_model_fast/qwen3.8-27b` (NVMe, 지시대로 USB하드 아님).
- 실행: `systemd-run --user --unit=dl-qwen38-27b` 로 기동(수확 방지). 스크립트:
  `scripts/download_qwen38_27b.py` (신규, `huggingface_hub.snapshot_download` 기반, resume 지원).
- huggingface_hub **1.23.0**(ai_model_rocm venv) 사용 — `HF_HUB_ENABLE_HF_TRANSFER`는 deprecated
  경고(신규 Xet 백엔드로 대체됨, 별도 설정 불필요) 확인.
- **실측 다운로드 속도**: 시작 20:23:12, 168초 경과 시점 7.92GB 수신 → **평균 ~47MB/s**(버스트 구간 최대
  ~130MB/s대, `nvmecopy.service`(262GB 로컬 rsync, 동시 진행 중) 디스크쓰기 경합 감안한 실측치).
- **완료 예상**: 잔여 ~47.7GB ÷ ~47MB/s ≈ 17분 → **약 20:40~20:45 KST 완료 예상**(버스트 있으면 더 빠를 수 있음).
- 무결성 검증(완료 후 별도 확인 필요, 이번 턴엔 미실행): 샤드 수(18) vs index weight_map, index total_size
  vs 실제 합, config/tokenizer 존재 — Mixtral 다운로드 때 쓴 절차(`docs/mixtral-download-20260730.md`) 재사용 예정.

## 4) 학습 계획 (실행 안 함 — 제안만)

신규 파일: `config/training_config_qwen38_27b.yaml`

- HQQ 4bit, group_size=64 (32B 레퍼런스와 동일 — bnb 불가로 유일한 실사용 가능 경로).
- LoRA r=16/alpha=32, target_modules 9종(위 2-4절), attention-only(--lora-mlp 없음, 32B 레퍼런스와 동일선상).
- seq=1024, epochs=2, bs=1×accum=8 → `315//8=39 step/epoch × 2ep = 78 step`
  (**PM이 언급한 "78스텝" 레퍼런스와 정확히 일치 — 같은 코퍼스·config 계열임을 재확인**).
- 데이터: 기존 351건(315train/36val) 그대로, 증량 안 함(앜선생 조사 결과 반영).

**예상 소요 — 불확실성 명시**:
- 32B 레퍼런스: 194s/step (HQQ4bit, seq1024). 27B는 파라미터가 32B의 ~87%이므로 표준어텐션이었다면
  단순 비례로 ~168s/step 예상.
- 그러나 Qwen3.8-27B는 75% 레이어가 gated linear-attention이고, **fla(flash-linear-attention) 미설치로
  torch 순수구현(fallback) 사용**(`[transformers] The fast path is not available...` 경고 실측 확인).
  선형어텐션 자체는 완전어텐션보다 FLOPs가 적지만, 최적화 커널 없이 torch로 도니 상쇄되거나 역전될 수 있음
  — **방향을 예단할 근거가 없다.**
- 그래서 **범위로만 제시**: 낙관 ~150s/step(총 78step≈3.25h) ~ 비관 ~350s/step(총 78step≈7.6h).
  로드 시간은 텍스트 백본만 읽으므로(비전타워·MTP 스킵) 32B보다 가볍게 잡아 10~30분 추가 예상.
  **→ 실측 없이 이 숫자를 믿지 말 것. 첫 GPU 착수는 반드시 8-step 스모크로 s/step부터 확인**
  (Mixtral 캠페인 때와 동일 패턴: smoke PASS 확인 후에만 본런 자동/수동 진행).
- 참고: `fla-org/flash-linear-attention`은 `pip install flash-linear-attention[rocm]`으로 ROCm 지원 명시
  (웹 확인, gfx1151 개별 검증은 안 됨) — 설치 시도는 GPU 착수 턴으로 이월(패키지 설치 자체는 GPU 불필요라
  이번 턴에 할 수도 있었으나, torch 2.10 재빌드/버전 충돌 리스크가 있어 스택을 더 흔들지 않기 위해 보류).

## 사용자 확인 대기 큐
없음 — 이번 턴 범위(준비·검증) 안에서 전부 위임 권한 내 처리. GPU 착수 자체가 다음 지시 대상.

## 커밋
로컬 커밋만(push 안 함, 개인 학습 레포).
