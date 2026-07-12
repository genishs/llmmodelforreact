# ROCm 학습환경 셋업 — 진행상황 & 재개 가이드 (halo-ubuntu-pm)

> 작성 2026-07-12 (halo 장비, **Ubuntu 26.04 Linux** 세션). 자리 이동으로 shutdown 예정.
> **목적**: 재부팅 후 이 지점부터 무손실 재개.
> **이 파일은 NTFS 레포(D:)에 있어 Windows에서도 읽힘** → Windows 쪽 halo-pm도 진행상황 확인 가능.
> 별칭 확정: 이 Linux 개발팀 = **halo-ubuntu-pm** (Windows측 `halo-pm`, 상대 장비 `shas-pm`과 구분).

## 상태 요약 (한 줄)
Ubuntu 26.04 + ROCm(gfx1151) 전환 → **torch 2.10.0+rocm7.13 설치·Gate A 통과 ✅**(bf16 OK·세그폴트 없음). 다음 = ML 의존성 → 모델 다운로드 → smoke.

## ✅✅ Gate A 통과 (2026-07-12, 핵심 관문 돌파)
- torch **2.10.0+rocm7.13.0a20260513** (cp312), `cuda_available=True`, device=AMD Radeon Graphics(gfx1151).
- fp32/**bf16 matmul 작동**(DirectML 불가였음), `empty_cache` OK, **세그폴트 없음**(ROCm #5853 회피 확인). → Linux+ROCm 경로 유효성 입증.
- ⚠️ **중요 발견**: `torch.cuda.mem_get_info` total=**32.7GB** — 물리 60GB 전체가 아님(**GTT 기본 한도 ≈ RAM의 50%**). **14B bf16(~32GB)는 경계선**(OOM 위험) → GTT 확대 필요(부팅 `amdgpu.gttsize`/`ttm.pages_limit` 커널파라미터 또는 BIOS VGM). **32B 4bit(~24GB)는 32GB 안에 안착.** ← 메모리 매트릭스 재조정 필요, 다음 세션 우선.
  - **원인 규명(2026-07-12)**: GPU 캡 = **TTM `pages_limit` = 7,987,871 pages ≈ 32.5GB = RAM 64GB의 50%**(커널 기본). `-rw-r--r--`(root 런타임 쓰기 가능), ttm은 모듈 → **재부팅 없이 sudo로 확대 가능**:
    ```bash
    echo 13107200 | sudo tee /sys/module/ttm/parameters/pages_limit          # ~50GB GTT 즉시
    echo 'options ttm pages_limit=13107200' | sudo tee /etc/modprobe.d/ttm-gtt.conf  # 재부팅 후에도 유지
    ```
    (13107200 pages = 50GB, 호스트에 ~14GB 남김. 7B/32B-4bit는 확대 불필요, **14B bf16만 필요**.)

## ✅ 완료 (재부팅해도 보존됨 — venv=ext4, 레포=NTFS, uv=~/.local)
- **OS**: Ubuntu 26.04 LTS, kernel 7.0, gfx1151(Radeon 8060S). **통합 RAM 60GB 전체 가시** (Windows 48/15.6 정적분할 탈출).
- **GPU 컴퓨트 접근**: `/dev/kfd`·`/dev/dri/renderD128`에 `user:user rw` **ACL 이미 설정** → **sudo/그룹변경/재로그인 불필요**. amdgpu 커널드라이버 로드됨.
- **uv**: `~/.local/bin/uv` (0.11.28). 사용 전 `export PATH="$HOME/.local/bin:$PATH"`.
- **Python 3.12.13** (uv 설치) + **venv = `~/.venvs/ai_model_rocm`** (ext4, 보존). 시스템 python은 3.14뿐이라 ML 스택 미지원 → 3.12 사용.
- **gh 인증**: 기본 config = **genishs** (repo scope). GH_CONFIG_DIR 프리픽스 불필요.
- **다운로드 대역폭 실측 ≈ 10 MB/s** (78 Mbps).

## 🔄 미완 / 다음 단계 (= 재개 지점)
1. **TheRock gfx1151 torch 설치** (미완). ⚠️ **핵심 함정**: `uv venv`는 venv 안에 `pip`을 넣지 않음 → `~/.venvs/.../bin/pip` 호출은 "No such file"로 조용히 실패(0바이트 로그의 정체였음). **반드시 `uv pip install` 사용**:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   uv pip install --python ~/.venvs/ai_model_rocm/bin/python torch \
     --index-url https://rocm.nightlies.amd.com/v2/gfx1151/
   ```
   (cp312 linux 휠 자동선택. **rocm 런타임 자체번들** → 시스템 ROCm(amdgpu-install) 설치 불필요 = Ubuntu 26.04↔24.04 저장소 불일치 회피.)
2. **Gate A — GPU sanity(세그폴트 게이트, 이 전환의 성패 관문)**: fp32/bf16 matmul + `empty_cache` + 세그폴트 없음. `scripts/rocm_resume.sh`가 자동 검증.
3. **ML 의존성**: `transformers peft accelerate datasets safetensors sentencepiece pyyaml psutil tqdm` (torch는 이미 설치되어 재설치 안 됨).
4. **베이스 모델 다운로드** (HF 캐시 비어있음): 7B(~15GB/25분) → 14B(~29GB/48분). 32B(62GB/103분)는 별도 세션.
5. **smoke 학습 (Gate B)**: `src/train_directml.py --backend cuda --dtype bf16 --seq 512 --smoke 5` — step2 이후 OOM 없음(DirectML 단편화 벽 해소) + bf16 안정 확인.

## 재개 방법 (택1)
- **간편**: `bash scripts/rocm_resume.sh` — 1~3단계 자동(설치→Gate A→deps), 4~5는 명령 안내.
- **또는** Claude Code 세션에서 *"ROCm 셋업 이어서"* 라고 하면 이 문서 기준으로 진행.

## 결정된 계획 (다음 세션 참고 — 이미 분석 완료)
- **메모리 매트릭스**(system-architect): 14B bf16는 gradient-checkpointing ON으로 **seq2048까지 여유**(~34GB). **32B는 bf16 적재 불가**(가중치 65GB > 물리 60GB) → **4bit(bnb-ROCm)로만**(~24GB). MLP-target LoRA는 사실상 공짜(+0.5~0.7GB).
- **진행 사다리**: ①7B bf16 seq512 smoke → ②**14B bf16 qkvo+MLP seq1024**(첫 실학습, 62.9% 베이스 대비 fp16→bf16·qkvo→+MLP·seq256→1024 3레버 동시개선) → ③14B seq2048 → ④**32B 4bit**(bnb-ROCm 빌드 스파이크 통과 후).
- **32B 결과까지 시간**: 훈련 런 순수 **3~7h** + 다운로드/빌드/채점 포함 end-to-end **~8~16h**(대부분 무인). **최대 관문 = bnb-ROCm(gfx1151) 빌드 성공.**
- **설정 노브**: gradient checkpointing **ON**, `PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`.

## 팀 운영 / 브릿지 상태
- **PM은 업무 배분에 집중**(사용자 지시). 실학습 실행 = `autonomous-operator`, 검증 = `qa-tester`, 코드수정 = `developer`/`dev-lead`, 문서화 = `product-planner`, SCM = `scm-manager`.
- **브릿지**: 코디네이션 레포 `genishs/claude-agent-team`, **이슈 #7** = ai_model 협업 스레드. 이 장비 별칭 **halo-ubuntu-pm**. shas-pm과 PM↔PM 방향성 마커 `🤖 **[halo-ubuntu-pm→shas-pm]**`로 통신. 워터마크 = `scratchpad/gh-watermark.txt`(코디네이션 레포 쪽).
- **이번 세션 진행상황을 이슈 #7에 `halo-ubuntu-pm→shas-pm` 코멘트로 게시함**.

## ✅ Gate B 통과 (2026-07-12 21:00, autonomous-operator 세션)
- 커맨드: `PYTORCH_HIP_ALLOC_CONF=expandable_segments:True ... train_directml.py --backend cuda --dtype bf16 --seq 512 --smoke 5 --train-file data/processed/react_train_r4.jsonl --out models/smoke-rocm` → `logs/smoke_7b_rocm.log`.
- 결과: cuda 백엔드 인식(AMD Radeon Graphics/gfx1151), 7B 339텐서 GPU 스트리밍 적재(18.5s), LoRA(qkvo, r16) trainable 10.09M/0.13%, **5 optim step 전부 OOM/세그폴트 없이 완주**, loss 0.86~0.96(유한값). **7.8s/step, GPU peak 14.6GB**(32.7GB 한도 내 여유 큼). ⚠️ 코디네이터 지시대로 `HSA_OVERRIDE_GFX_VERSION`은 설정하지 않음(빈 값 설정 시 `cuda_available=False`가 되는 회귀 확인됨 — 절대 재도입 금지).
- 판정: **Gate B PASS.** 재실행/디버깅 불필요했음(재launch 버전이 정상 동작).

## ✅ 7B bf16 qkvo+MLP seq512 본런 완료 (task 2, 2026-07-12 21:00~21:22, DONE)
- 커맨드: `train_directml.py --backend cuda --dtype bf16 --seq 512 --lora-mlp --train-file data/processed/react_train_r4.jsonl --out models/qwen-react-lora-7b-rocm` (config 기본 epochs=3, r=16→lora-mlp로 gate/up/down_proj 추가 → **trainable 40.37M/0.53%**). 로그: `logs/train_7b_rocm.log`.
- **최종 결과**: **112 optim step, 총 1340.1s(22.3분), 평균 11.8s/step, GPU peak 14.9GB 고정**(32.7GB 한도 대비 여유 충분, MLP타깃 추가로 smoke 대비 +0.3GB뿐). 단편화 없음(step시간 10.1→11.8s 완만 수렴 후 안정).
- **loss 곡선**: epoch1 val_loss **0.5703** → epoch2 **0.5026** → epoch3 **0.4961**(단조 감소, train loss step1 ~0.92 → 후반 ~0.4대). 3 epoch에서 완만 포화 조짐(4060 CUDA-QLoRA eval_loss 0.4709과 유사 대역 — 단 손실계산 방식 달라 직접비교 주의).
- **어댑터 저장 확인**: `models/qwen-react-lora-7b-rocm/` — `adapter_model.safetensors` **161MB(392 텐서, CPU/fp32)** + `adapter_config.json` + tokenizer 3종. **★ROCm 상에서 end-to-end LoRA 품질 파이프라인 첫 검증 완료** — 채점 가능한 7B 어댑터 확보.
- **다음**: 이 어댑터를 heldout7-mn4096 캐논으로 채점(qa-tester) → 기존 8060 seq512(81.8%)/r5mlp(80%)·4060 r4mlp(95%)와 비교. bf16+MLP+seq512 조합의 ROCm 실효 확인.

## ✅✅ 메모리 확장 완료 (2026-07-12 재부팅, 사용자 GRUB) — 60.1GB
- 재부팅 후 `torch.cuda.mem_get_info` total = **60.1GB**(구 32.7GB), amdgpu GTT total 60.1GB, 커널 cmdline `ttm.pages_limit=14680064`. **GRUB 부트파라미터 방식 성공.** `build-essential`도 설치됨(gcc/g++ 15.2). → 14B bf16 및 32B 4bit 모두 실행 가능.

## ✅✅ 14B bf16 qkvo+MLP seq1024 본런 (task, 2026-07-12 22:13~ 진행중) — ★>32GB 증명 확보
- 다운로드: `scripts/dl_14b_local.py`로 `models/base/qwen2.5-coder-14b` 직접 적재(6샤드 ~29GB, 20.9분, 1회 완주).
- **★>32GB 증명(핵심)**: 첫 실행(coordinator 지정 커맨드 그대로, `--grad-ckpt` 없음)이 loss(cross_entropy) 단계에서 OOM — **그 OOM 트레이스가 곧 증명**: "GPU 0 total capacity **56.00GiB**, **54.91GiB allocated by PyTorch**". 14B bf16 학습이 **54.9GB 할당** = 구 32.7GB 천장이면 절대 불가. **메모리 확장 실효 결정적 입증.**
- OOM 원인/수정: 계획서(이 문서 line 48/51)가 14B엔 gradient checkpointing ON을 명시하나 지정 커맨드에 `--grad-ckpt` 누락(스크립트가 이 플래그로 게이팅). **`--grad-ckpt` 추가해 재실행**(가역적 학습실행 수정, 위임범위 내).
- **재실행 정상 학습중**: `--seq 1024 --lora-mlp --grad-ckpt`, trainable 68.8M/0.46%. **~63~67s/step, GPU 28.7GB 안정**(=14.8B bf16 가중치 ~28GB + 소량 옵티마이저; grad-ckpt로 활성값 최소화, 손실계산 순간피크는 더 높아 run-1을 OOM시킴). loss ~0.81~0.91. 111 optim step → ETA ~2h + eval.
- 완료 시: 어댑터 `models/qwen-react-lora-14b-rocm` 저장 → 최종 loss/wall-clock/GPU peak 追記 → 타겟 커밋.

## ✅ 32B feasibility spike — bitsandbytes ROCm 4bit 빌드 (task 3) — **빌드+임포트 성공(GO), 수치검증 14B후 대기**
- **1차(재부팅 전) 블로커=시스템 C++ 툴체인 부재**(gcc/g++/libstdc++-dev 없음). 사용자 `build-essential` 설치로 해소.
- **2차 블로커=pip ROCm SDK(`_rocm_sdk_core`)가 런타임전용** — hipcc/libs/헤더는 있으나 **CMake 패키지(`hip-lang-config.cmake`) 없음** → bnb의 `enable_language(HIP)` 실패. **해소: `uv pip install rocm-sdk-devel==7.13.0a20260513`(TheRock gfx1151 인덱스, core와 정확히 동일버전) + `rocm-sdk init`**(9.3GB devel tar 확장 → `_rocm_sdk_devel/lib/cmake/hip*` 생성).
- **3차 블로커=gfx1151 wavefront 크기(실제 코드버그)**: `hipcub::WarpReduce<float,64>`가 gfx1151(wave32)에서 static_assert 실패. 원인=ROCm 7.13 clang에 legacy `__AMDGCN_WAVEFRONT_SIZE` 매크로 미정의 → WARP_SIZE가 잘못된 64로 폴백. **패치: `csrc/kernels.hip`의 WARP_SIZE 가드에 `#elif defined(__GFX11__)||defined(__GFX12__) → 32` 브랜치 추가**(RDNA3/3.5/4는 wave32). 패치 파일: `scripts/bnb-rocm-gfx1151-warpsize.patch`.
- **빌드 성공**: `cmake -DCOMPUTE_BACKEND=hip -DBNB_ROCM_ARCH=gfx1151 -DCMAKE_HIP_COMPILER=$DEVEL/lib/llvm/bin/amdclang++ -DCMAKE_PREFIX_PATH=$DEVEL` (DEVEL=`_rocm_sdk_devel`) → `libbitsandbytes_rocm713.so` 링크 완료 → `uv pip install -e . --no-build-isolation`.
- **검증(binding레벨)**: `import bitsandbytes` OK(0.43.3.dev), lib버전 **713**(우리가 빌드한 .so) CDLL 로드, `Linear4bit`/`Params4bit(nf4)` 존재·CPU 구성 OK. **남은 것=GPU nf4 matmul non-NaN 수치검증** — 단일 GPU라 14B 학습과 겹치면 OOM 위험 → **14B 완료 후 32B smoke 직전에 실행 예정**(coordinator의 GPU 비중첩 규칙 준수).
- **빌드 재현 레시피 요약**: ①`build-essential`(sudo, 완료) ②`rocm-sdk-devel==<core버전>` + `rocm-sdk init` ③kernels.hip warp-size 패치 ④위 cmake 인자 ⑤editable install. **다음 장비/재설치 시 이 5단계.**

## 32B 사전양자화 획득 (진행중)
- **fp16 64GB 대신 사전양자화 nf4본 채택**: `unsloth/Qwen2.5-Coder-32B-Instruct-bnb-4bit`(~19.2GB, `quant_method=bitsandbytes`, load_in_4bit) → 다운로드 3배 절감 + load-time fp16→4bit RAM 스파이크 회피. `scripts/dl_32b_bnb4.py`로 `models/base/qwen2.5-coder-32b-bnb-4bit`에 다운로드중(14B 학습과 병렬, 네트워크 vs GPU 무경합).
- **주의**: 이 체크포인트 로드/학습엔 **위 bnb-ROCm이 필수**(quant_method=bitsandbytes). 그래서 bnb 수치검증이 32B의 진짜 게이트.
- 다음(GPU 순차): 14B 완료 → bnb nf4 수치검증 → 32B 4bit 로드+2~5step smoke(host RAM peak·GPU GB·step time) → 클린이면 32B 4bit qkvo+MLP 본런.

## 주의 / 리스크
- torch 백그라운드 설치가 하니스 임시셸에서 반복 중단(0바이트 로그) → 다음엔 **사용자 실제(지속) 터미널**에서 실행. pip 캐시는 ext4(`~/.cache/pip`)에 남아 재실행 시 진행분 재활용.
- **Ubuntu 26.04**(계획서 원안은 24.04) — TheRock 휠 glibc/커널 호환 여부는 **Gate A가 트립와이어**. 실패 시 휠 변형(다른 날짜 빌드) 재시도.
- 레포가 **NTFS**라 git에 CRLF 대량 diff 노이즈 존재 → **신규 파일만 타겟 커밋**(전체 `git add` 금지).
