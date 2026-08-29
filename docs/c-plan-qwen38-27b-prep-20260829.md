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

## 5) GPU 착수 — 8-step 스모크 결과 (2026-08-30, 오선생, PM 지시로 착수)

### 사전 코드 변경(GPU 착수 직전, 로컬 커밋)
- `e102b13`: 문서화만 해뒀던 prefix remap을 실제로 `train_directml.py`에 반영
  (`remap_checkpoint_key`/`build_checkpoint_key_maps`). CPU 합성 체크포인트(멀티샤드
  index.json, 8레이어 하이브리드, 가짜 vision/mtp 텐서 포함)로 실제 driver 함수를 import해
  실행 검증 — `stream_load_to_device`는 레퍼런스와 logits 완전일치(max diff 0.0),
  `load_hqq_onthefly`는 유한 출력. `build()` e2e(HQQ4bit+LoRA9종+forward+backward)도
  76/76 유한 gradient. 기존 qwen2.5-coder-1.5b/7b로 identity매핑(no-op) 하위호환 재확인.
- `build()`의 LoRA 부착검증을 `--lora-mlp` 전용에서 target_modules 전체로 확장(하나라도
  안 붙으면 RuntimeError).
- `795efce`/`31a6eef`: gradient checkpointing "요청"과 "실제 켜짐"을 분리해 로그로 확인
  가능하게 함 + 서프릭스별 LoRA 부착개수(Counter) 로깅 추가. (`31a6eef`는 그 직전 커밋이
  Edit 도구로 CRLF→LF를 깨뜨려 diff가 전체파일로 찍힌 것을 원복만 한 정정 커밋 — 내용변경 없음,
  `tr -d '\r'` 비교로 확인.)

### 1차 스모크 (`gpujob-c-smoke-20260830-023109`) — OOM으로 실패, 원인 규명됨
- HQQ 스트리밍 양자화 496 Linear 전부 성공(819.3s), LoRA 9종 타깃 전부 실제 부착 확인(304모듈:
  q/k/v/o_proj 16개씩, in_proj_a/b/qkv/z·out_proj 48개씩 — full_attention_interval=4 비율과
  정확히 일치). 여기까지는 완전히 정상.
- 첫 forward 도중(MLP down_proj) `torch.OutOfMemoryError: HIP out of memory. Tried to
  allocate 170.00 MiB ... 55.36 GiB is allocated by PyTorch`로 죽음. **wedge 아님** —
  `wedge_check`가 "no amdgpu wedge/reset messages ... GPU looks healthy" 확인, 클린한
  OOM 예외.
- **원인**: 스모크 커맨드에 `--grad-ckpt`를 안 넘김. `prepare_model_for_kbit_training(
  use_gradient_checkpointing=False)`로 호출돼 gradient checkpointing이 꺼진 채 돌았고,
  HQQ가 forward마다 4bit→bf16으로 되푸는 텐서를 grad-ckpt 없이는 backward를 위해 64레이어
  깊이 내내 전부 살려둬야 해서 27B가 사실상 bf16 통짜(~54GB)로 상주 → OOM. Mixtral/123B
  본런은 전부 `--grad-ckpt`를 명시했었는데(문서 확인) 이번 C안 최초 커맨드에서만 빠뜨림 —
  내 실수, PM이 재확인.

### 2차 스모크 (`gpujob-csmoke-20260830-025223`) — **PASS**
- `--grad-ckpt` + `--setenv PYTORCH_ALLOC_CONF=expandable_segments:True`(gpu_job.sh 유닛
  환경에 직접 주입, 호출측 export는 유닛에 전파 안 됨 확인) 적용.
- `gradient checkpointing: 요청=True | 실제 켜짐 확인(is_gradient_checkpointing)=True` —
  "설정했다"가 아니라 "켜졌다"를 로그로 직접 확인.
- LoRA 부착 재확인: 총 304모듈, 서프릭스별 `{'in_proj_a': 48, 'in_proj_b': 48,
  'in_proj_qkv': 48, 'in_proj_z': 48, 'k_proj': 16, 'o_proj': 16, 'out_proj': 48,
  'q_proj': 16, 'v_proj': 16}` — 사전계산치(16×4 + 48×5=304)와 완전 일치.
  trainable 47,521,792 / all(비양자화분) 14,768,242,176 = 0.3218%.
- **8-step 전부 완주**, loss(avg8) 궤적 1.6301→1.5364→1.1745→0.8311→0.6094→0.7117→
  0.6407→0.6225 (유한·전반적 하강, 6→7 소폭 반등은 8건짜리 accum 윈도우 노이즈로 정상 범위).
  `[스모크 완료] 저장 생략. backward 정상 동작 확인됨.`
- **s/step 실측**: step1 175.2s(MIOpen/컴포저블커널 최초 컴파일 오버헤드 포함, 로그에
  `e_grid_desc_...` 컴파일 스팸 확인), step2-8 정상상태 평균 **168.17s/step**
  (167.4~169.8 범위, 매우 안정적).
- **GTT 실측**: step 실행 중 GPU 18.7GB(고정, 8스텝 내내 변화 없음 — A안처럼 스텝마다
  점증하지 않음, MoE 옵티마이저 상태 누적 문제와 무관한 구조라 예상대로), 종료 후 47MB로
  완전 반환. 56GB 캡 대비 **여유 37GB+** — 본런(78스텝) 내내 안전할 것으로 판단.
- 커널 로그: wedge/reset 메시지 없음, GPU 정상.

### 예상 소요 재산정(범위 아님 — 실측 기반)
- 78스텝(첫스텝 컴파일 175.2s + 나머지 77스텝×168.17s) ≈ **3.65h**
- 모델로드+HQQ양자화+세팅 ≈ **13.3분**
- **본런 총 예상 ≈ 3.87시간** (당초 범위 3.25~7.6h 중 낙관치에 가까움 — fla 미설치
  torch fallback의 실제 영향은 우려보다 작았음).

### 본런 승인 대기
PM 지시대로 본런은 착수하지 않고 대기. 8-step 스모크 PASS + s/step/GTT 실측치를 위
결과와 함께 보고.

## 6) 채점 경로 전환 — GGUF 불가, HF/PyTorch(`eval_hard_tsc.py`)로 (PM 지시, 2026-08-30)

PM이 학습 중 미리 확인: 우리 llama.cpp(5f55650, 2026-07-30)의 `convert_hf_to_gguf.py`에
`qwen3_5` 언급 0건 — 변환기가 이 아키텍처를 모른다. llama.cpp 업데이트는 캠페인 중 리스크
대비 이득이 없어 보류(B안 채점을 몇 시간 전 정상 수행한 툴체인), 배포용 GGUF는 캠페인
종료 후 별건. 대신 `scripts/eval_hard_tsc.py`(HF/PyTorch, `--quant hqq` 지원, 7B/14B/32B
계열 전례 있음)로 어댑터 유/무를 **같은 파이프라인 안에서** 비교.

### 🔴 사전 점검(GPU 미사용, 학습 중 코드 리뷰)에서 발견한 것
- `eval_hard_tsc.py`가 `train_directml.load_hqq_onthefly`를 그대로 import해서 쓴다 —
  즉 오늘 반영한 prefix remap(VLM 체크포인트 텐서명 매핑) 수정이 **채점 경로에도 자동
  적용된다**(별도 수정 불필요, 코드 확인으로 검증).
- `gen_batch_utils.build_prompt`는 모델의 chat_template을 안 쓰고 고정
  `### Instruction/### Input/### Response` 포맷만 쓴다 — Qwen3.8-27B의 복잡한 멀티모달
  Jinja 템플릿과 무관, 학습 데이터 포맷과 동일 계열이라 호환 문제 없음.
- **🔴 PM 계획의 전제 하나가 실제 코드와 달랐다**: "`--adapter` 인자만 제거하면 base단독
  채점"이라 하셨으나, 실제로는 `--adapter required=True` + `PeftModel.from_pretrained`
  무조건 호출이라 인자를 빼면 argparse 에러로 즉시 죽는다. **수정 완료**(커밋
  `3d4502e`): `--adapter` 기본값 `""`로 선택화, 비어있으면 PEFT 래핑 스킵하고 base
  단독 반환. 기존 어댑터 지정 경로는 완전 동일(회귀 없음).
- ⚠️ **아직 검증 안 된 것**: `model.generate()`가 이 하이브리드(게이트 선형어텐션+완전어텐션)
  아키텍처에서 실제로 동작하는지는 이번 세션에서 forward/backward만 검증했지 자기회귀
  생성(캐시 처리)은 아직 한 번도 실행해본 적이 없다. **1태스크 스모크가 속도 측정만이
  아니라 이 경로의 최초 정합성 검증이기도 하다** — PASS 못 하면 그 자체가 중요한 신호.

### 준비된 실행 커맨드 (GPU 착수는 학습 완료 후, PM 지시대로 지금은 실행 안 함)
```
# 1) 스모크: 1태스크(held-out 중 최단, ho-select)로 s/step·생성정상여부 실측
python scripts/eval_hard_tsc.py \
  --base "/run/media/user/새 볼륨/ai_model/models/base/qwen3.8-27b" \
  --adapter models/qwen38-27b-react-lora-v1 \
  --quant hqq --hqq-nbits 4 --hqq-group-size 64 \
  --heldout --only ho-select --max-new 4096 \
  --label qwen38-27b-smoke-ho-select

# 2) 본채점 — 어댑터 있음
python scripts/eval_hard_tsc.py \
  --base "/run/media/user/새 볼륨/ai_model/models/base/qwen3.8-27b" \
  --adapter models/qwen38-27b-react-lora-v1 \
  --quant hqq --hqq-nbits 4 --hqq-group-size 64 \
  --heldout --max-new 4096 \
  --label qwen38-27b-react-v1-hqq4-mn4096

# 3) 본채점 — 어댑터 없음(base 단독, No-LoRA)
python scripts/eval_hard_tsc.py \
  --base "/run/media/user/새 볼륨/ai_model/models/base/qwen3.8-27b" \
  --quant hqq --hqq-nbits 4 --hqq-group-size 64 \
  --heldout --max-new 4096 \
  --label qwen38-27b-BASE-noLoRA-hqq4-mn4096
```
🔴 **주의(PM 지시)**: 이 점수는 llama.cpp 경로 기존 점수(72B 64.7%·123B 12.2%·141B 10.7%·
7B 70.5%)와 **직접 비교 불가**(파이프라인 다름). 표기 시 경로 명기, 비교는 이 3건
안에서(어댑터 유 vs 무)만.

## 7) 본런 완주 (2026-08-30 07:32, PM 확인)

```
78 steps, 총 13,686.8s(3.80h), 평균 171.3s/step (8-step 스모크 추정 3.87h와 거의 일치)
step78 loss(avg8) 0.3849
[epoch 1/2] val_loss 0.4744 → [epoch 2/2] val_loss 0.4324 (개선, 발산/붕괴 신호 없음)
최종 어댑터: models/qwen38-27b-react-lora-v1/adapter_model.safetensors
  190,172,032 bytes, 608 텐서(LoRA A/B × 304모듈)
클린 종료(exit 0), wedge/reset 없음, GPU 정상.
```
PM 확인: val_loss 0.4324 = 캠페인 전체 1위(기존 1위 123B-v2 0.4642), 파라미터 1/4.5·
어댑터크기 1/6·GPU시간 1/2.8로 달성. 단, **val_loss는 배포 성적 예측 못 함**(123B가 val
2위 0.4704인데 실채점 12.2%였던 선례) — 채점이 진짜 판정, 축배는 채점 후.

## 8) 채점 착수 — HF/PyTorch 경로(`eval_hard_tsc.py`), GPU 완전 회수 확인 후
아래 절 계속 기록 예정(스모크 → 본채점 2건). 실행 커맨드는 6절 참조(--adapter 커밋
3d4502e로 optional화 완료해 두 조건 비교 가능).
