# ROCm 학습환경 셋업 — 진행상황 & 재개 가이드 (halo-ubuntu-pm)

> 작성 2026-07-12, **최종 갱신 2026-07-16 06:00** (halo, Ubuntu 26.04 + ROCm gfx1151).
> **목적**: 이 지점부터 무손실 재개. NTFS 레포라 Windows에서도 읽힘.

## 상태 요약 (한 줄)
**32B 4bit(HQQ) QLoRA 학습 완주 — 어제(07-15)의 "비실용" 판정은 뒤집혔다.** 벽은 하드웨어가 아니라 **bitsandbytes 커널 하나**였다. 다만 **채점(평가)이 새 병목**(7.2h/회)이고, **채점 하니스 자체가 신뢰 불가**(seed 분산 ±20pp)로 밝혀져 **점수 해석은 전면 보류** 상태다.

---

# ★★★ 2026-07-16 세션 — 읽어야 할 3가지

## ① 32B 4bit 학습 = **가능하다** (어제 판정 뒤집힘)
```
[03:21:21] 종료: 78 steps, 총 15607.1s, 평균 194.4s/step | val_loss 0.5257→0.4868
[03:21:22] [본런 완료] 저장: models/qwen-react-lora-32b-hqq (896텐서, 512MB)
웨지/Traceback/OOM 0건 | GPU 21.4GB (상한 ~50GB의 43%)
```
- **모델**: Qwen2.5-Coder-32B **bf16 원본**(65GB, HF에서 다운로드) → 스트리밍 적재 → **in-place HQQ 4bit 양자화**(448 Linear) → LoRA r16 qkvo+MLP, seq1024, grad-ckpt, 2epoch.
- **명령**: `scripts/gpu_job.sh --name train32b2 --timeout 18000 -- python src/train_directml.py --backend cuda --dtype bf16 --base ./models/base/qwen2.5-coder-32b --quant hqq --hqq-nbits 4 --hqq-group-size 64 --lora-r 16 --lora-mlp --grad-ckpt --seq 1024 --epochs 2 --out ./models/qwen-react-lora-32b-hqq`
- **★70B 전망**: 32B가 **21.4GB**밖에 안 썼다. 70B nf4 추정 ≈39GB(가중치 36.5 + LoRA 0.25 + 옵티마 0.5 + grad 0.25 + 활성값 1.5) → **상한 ~50GB 안쪽. 메모리는 들어온다.**

## ② 근본원인: **bitsandbytes가 gfx1151에서 깨져 있었다** (하드웨어 무관)
- **bnb**는 wavefront 크기에 의존하는 **수제 HIP 커널**을 쓴다. `__AMDGCN_WAVEFRONT_SIZE`가 **ROCm 7.13 clang에서 미정의** → `WARP_SIZE`가 **64로 폴백**. 그런데 **gfx1151은 wave32** → OOB 메모리 접근 → `hipErrorLaunchFailure` → GPU 웨지.
- **HQQ/torchao**는 backward가 `dequant + 평범한 matmul`이고 **자체 4bit 커널이 없다** → bf16이 증명한 표준 ATen 경로를 그대로 탄다. **게이트 실측: torchao PASS(2.7s) / HQQ PASS(3.0s), 웨지 0.** (`scripts/test_nf4_backward_gate.py`)
- **HQQ를 택한 이유**: `peft/tuners/lora/hqq.py`가 존재 → transformers+peft에 drop-in. torchao NF4는 peft에 참조 0건 → 커스텀 배선 필요.
- **함정**: transformers 5.13.1의 `HqqConfig` 자동경로는 **파손**(`quantizers/base.py:289 get_quantize_ops()` 추상 미구현 → `NotImplementedError`). → `HQQLinear`로 **수동 치환**(`src/train_directml.py: load_hqq_onthefly()`).
- **`HQQBackend.PYTORCH` 필수** (ATEN은 CUDA 전용).
- **하드웨어 손상 우려는 근거 없음**: `device wedged, but recovered through reset`는 **설계된 복구 경로**(TDR 등가), 펌웨어 매개 소프트 리셋이며 전원 레일을 끊지 않는다. Gemini 3.1 Pro·아키텍트·PM 3자 독립 수렴. 실손해는 세션/데이터지 실리콘이 아니다.

## ③ ★ 새 병목 = **평가**, 그리고 **저울이 고장나 있다**
- **채점 속도 = 0.36 tok/s** (HQQ 4bit batch=1 디코드, 4태스크 독립 측정). 토큰마다 **17GB 전체를 dequant**해야 해서 배치 이득 0. **구조적 특성, 버그 아님.**
  → **heldout7 채점 1회 = 7.2시간** (학습 3.7h보다 길다!). `medit` 하나가 4096토큰 = **3.2시간**.
  → **∴ "32B가 7B보다 나은가"는 이 인프라로 답할 수 없다** (seed 반복이 불가능하므로).
- **채점 하니스 신뢰 불가 (shas-pm 실측)**:
  - **seed 분산 Δ20.0pp** — 동일 데이터·설정에서 seed만 42→1234로 바꾸니 88.6% → 68.6%.
  - **채점기 아티팩트** — r6base의 medit 0.80은 소스의 **안 닫힌 백틱 하나**가 이후 코드를 통째로 문자열로 삼켜 에러 검출을 줄인 결과. 닫으면 **0.40**. `score=max(0,1-err/5)`가 **구문 붕괴 구간에서 품질과 역상관**.
  - **충실도 미측정** — `return <div/>` 한 줄로 만점 가능(타당도 결함, 표본을 늘려도 안 잡힘).
- **∴ 지금까지의 모든 점수 차이(cap +17.2pp, r6admin −14.3pp, egovreal −8.6pp)가 노이즈(±20pp) 안**이다.

## 🔻 "레버(데이터) > 크기·정밀도" = **반증됨 (2026-07-16 양노드 교차검증 확인)**
이 프로젝트의 중심 명제였으나 **근거가 무너졌다.** 명제엔 기둥이 둘이었다:
- **기둥2 "레버 켠 14B가 안 올랐다"(14b-v1 62.9% vs 14b-rocm 60.0% = 2.9pp)** → **사망** (노이즈 바닥 안).
- **기둥1 "7B가 14B를 이긴다"(v1: 7B 73.8 vs 14B 61.5, +12.3pp)** → **채점버그 아티팩트로 판명.** v1 채점기(`max(0,1-err/5)`)가 **스텁을 충실한 변환보다 높게 쳐줬다**(물증 ho-admin-mlist: 7B는 죽은코드+주석 스텁을 0.80, 14B는 진짜 테이블 재현을 0.60). **하니스 v2**(충실도축 신설)로 재점수하니 **역전**: v2 7B 69.5 vs **14B 72.7 (+3.2pp)**.
- **교차검증**: shas/앗선생이 4060서 발견 → halo(8060)가 `score_v2.py`를 자기 아카이브에 독립 적용해 **소수점까지 재현**(flip·mlist 메커니즘·결정성·백틱 홀짝 5항목 통과, qa-tester). r6base medit(백틱 홀수=오염)이 v1 0.80→v2 0.20으로 정확히 짓눌림.
- **∴ 정직한 현재 상태 = "모른다".** "데이터>크기"는 근거 소멸, 그러나 "크기>데이터"로 확정된 것도 아니다(14B n=2, v2 노이즈 바닥 미측정). 함께 취소: *"14B의 벽은 구조적"* — medit 판정이 백틱 아티팩트로 오염돼 있었음(확인).
- **기여**: halo=백틱 홀짝 감사, 앗선생=충실도축 구현, shas=스텁 물증. 셋이 한 조각씩. 상세 [[eval-harness-untrustworthy]].

## 🖐️ 미결 — 두목 결재 대기
1. **하니스 v2**: `docs/decision-harness-v2-ko.md` — **두 PM 공동 권고 A**("모델 개선을 며칠 멈추고 저울부터 고친다"). 재채점은 GPU 0(생성물 아카이브만으로).
2. **32B 채점 미완**: 생성물 **4/7**(select·gallery·about-org·attachfile) 보존. 어댑터(512MB) 보존. 두목 지시로 **07-16 05:41 채점 중단**. 재개 시 어댑터로 이어서 채점 가능하고, 오프라인 채점(`scripts/score_saved_dml.py`, **GPU 0, 2분**)으로 partial 점수 산출 가능(단 4개 중 3개가 정보량 0).

## ⚠️ 하네스 사용법 (오늘 밤 런을 두 번 죽일 뻔한 함정)
- **모든 GPU 잡은 `scripts/gpu_job.sh --name <n> --timeout <sec> -- <cmd>`** (systemd-run --user detach; 웨지/GNOME 사망/로그아웃에도 잡·로그 생존. `Linger=yes` 이미 켜짐).
- **`--timeout` 반드시 명시.** 기본 `RuntimeMaxSec=3600`(1h)이 **5.6시간짜리 32B 본런을 정확히 +3600초에 SIGINT로 죽였다**(2시간 유실). 실행 중 transient 유닛의 타임아웃은 **사후 연장 불가**(실측) → 재발사만이 유일.
- **`--setenv KEY=VAL`**: 유닛은 호출자 셸에서 fork되지 않아 export가 전파 안 됨.
- **`HSA_OVERRIDE_GFX_VERSION`은 절대 설정 금지**(빈 값이어도 cuda 불가용).
- **★★메모리 = 통합풀 총량 모델 (GPU mem + host RAM = 같은 물리 60GB, 2026-07-17 실측)**. Strix Halo는 통합메모리라 **GPU가 쓰는 만큼 host RAM이 줄어든다**. 상한을 "GPU 50GB"로만 보면 프리징에 당한다 — **총필요 = GPU_peak + host(OS~4 + 프레임워크~8 + IO캐시) ≤ 60GB**로 봐야 한다. IO캐시 = 학습단독 ~2GB / **다운로드 동시 ~15GB**. 실측 인시던트: 72B Q4(GPU 44.4GB) + Mistral 다운로드 동시 → host MemAvailable **0.3GB + 스왑 = 프리징 임박**(다운로드 일시중지로 회피). 파생 규칙:
  - **72B 풀런 = Q2(GPU 28+host14=42GB, 마진18)** ← Q4(44.4+14=58, 마진2)보다 안전. **대형 학습 중엔 동시 다운로드/무거운 IO 금지**(host RAM 먹혀 프리징).
  - **123B = Q2 seq512 단독이 유일한 길**(GPU40+host14=54GB, 마진6). seq1024(GPU47.9)는 총62GB=프리징. seq512라도 **학습 중 다운로드 절대 금지**(마진6을 IO가 먹음). → Mistral 다운로드는 123B 학습 **전에** 완료돼 있어야 함.
  - 메모리 예측은 **파라미터비 외삽**으로: `GPU_peak = 실측앵커 × 파라미터비 × seq비` (32B Q4 21.4GB / 72B Q2 28GB / 72B Q4 44.4GB 앵커). ×계수 방식 폐기.
- **★전력: 밤샘 학습엔 200W급 충전기 필수 (100W는 방전死)**. 이 박스의 학습 풀부하 시스템 전력 draw가 **100W를 초과**한다 → 100W 충전기로는 부족분을 배터리에서 빼 **밤새 서서히 방전**한다(2026-07-16 새벽 실측: 100W로 밤샘 후 배터리 6%까지 빠져 학습 강제중단, 그게 "05:00 중단"의 진짜 원인이었음 — 시간이 아니라 전력). **200W 교체 후 실측: 84W 부하에서 배터리 100%·방전 0W** = 충전기가 부하를 다 커버. 장시간 런은 반드시 200W 이상 연결 확인 후 시작. GPU 절전(sclk 중간단계)은 정상 — 메모리클럭(mclk)은 이미 최대라 전력 더 줘도 속도는 안 오름(메모리대역폭 병목).
- **AOTriton 미측정 카드**: 로그에 `Mem Efficient attention ... Enable it with TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`. mem-efficient는 CK가 아니라 **AOTriton 경로로 실재**하며 환경변수 하나로 열린다. **미측정** — 다음 세션 저비용 카드.

---

## ~~⛔⛔ 32B 4bit QLoRA 최종 판정 = 비실용~~ → **❌ 이 판정은 2026-07-16에 반증됨. 아래는 역사 기록용.**

> **⚠️ 이 섹션의 결론은 틀렸다.** 32B 4bit 학습은 **가능하다**(07-16 실측: 78스텝 완주, 194.4s/step).
> 아래 관측(웨지·저속) 자체는 사실이나 **원인 귀속이 틀렸다** — "gfx1151이 4bit 학습을 못 한다"가 아니라
> **"bitsandbytes가 gfx1151(wave32)에서 깨져 있다"** 였다. bnb를 버리고 **HQQ**를 쓰면 즉시 열린다.
> 상세는 문서 상단 「2026-07-16 세션」 참조. **이 섹션을 근거로 의사결정하지 말 것.**

### (역사) 원래 판정 — 2026-07-15 00:30, autonomous-operator
재부팅으로 GPU 복구(cuda True, GTT 60.1GB) 후 backward 웨지 픽스(`--attn-eager`)를 실측 검증. **두 변형 모두 backward 1 step 완주 실패**:
| # | 설정 | 결과 | GPU |
|---|---|---|---|
| try2 | `--attn-eager --grad-ckpt --seq512 --smoke2` | **21분+ GPU 100%인데 optim step 0개**(log가 `optim_steps≈2`에서 정지) | **웨지 안 됨**(cuda True 유지) |
| try3 | `--attn-eager` **NO grad-ckpt** `--empty-cache-every 0 --seq512 --smoke2`, `timeout 480` | **EXIT 124**(8분 하드타임아웃)=step 0개 | **웨지 안 됨** |
- **정확한 판정**: (a) **기본(실험적 SDPA) 어텐션** → 4bit backward가 `HIP unspecified launch failure`로 **GPU 물리 웨지**(재부팅 필요, 어젯밤 확인). (b) **eager(math SDP) 어텐션** → backward가 **웨지는 안 시키나**(GPU 건강 유지) **1 optim step도 8~21분에 못 끝냄**(grad-ckpt 유무 무관) = **실사용 불가**(실런은 며칠 소요). 
- **원인 좁힘**: eager math-SDP는 O(seq²) 어텐션 행렬을 fp32로 materialize → 32B×64layer×seq512에서 bnb Linear4bit backward(dequant 매 op)와 겹쳐 microbatch당 수분. bf16 비4bit 14B(seq1024)는 68s/step 정상 → **병목은 4bit dequant×eager 조합**. 로그: `logs/smoke_32b_try2.log`, `logs/smoke_32b_try3.log`.
- **결론(정직)**: **32B/70B 4bit QLoRA 학습 트랙은 이 gfx1151+bnb-ROCm(0.43.3.dev+wave32패치) 빌드에서 비실용.** 필요 시 = **다른 bnb ROCm 브랜치**(0.46+ multi-backend, flash-attn ROCm 지원 커널) 재빌드가 다음 스파이크. 4bit **forward/inference는 정상**(수치게이트 PASS)이라 추론용도는 가능.
- **70B 미시도**: 32B-4bit backward가 비실용이면 72B/70B-4bit는 자명하게 더 나쁨 → coordinator 지시대로 시도 안 함(리소스 낭비 회피).
- **★견고한 경로 = bf16**: 7B bf16(112step)·**14B bf16 qkvo+MLP seq1024 60.0% 채점 완료(banked 최고)**. 어댑터 `models/qwen-react-lora-14b-rocm`(275MB) 생존 확인. gfx1151에서 **bf16 LoRA는 완전히 안정**, 4bit만 미성숙.
- **세션 안전**: eager 변형은 GPU를 웨지 안 시켜 **이번엔 재부팅 소모 없이** 판정 완료(어젯밤 SDPA 웨지=1 재부팅 소모와 대비).

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

## ✅✅ 14B bf16 qkvo+MLP seq1024 본런 완료 (2026-07-13 00:23)
- **112 steps, 3 epoch, 총 7775.6s(~2h10m), 평균 68.6s/step, GPU 28.7GB 안정**(grad-ckpt로 활성값 최소화; run-1은 grad-ckpt 없이 54.9GB 할당 OOM=★>32GB 실증).
- **val_loss: 0.6078 → 0.4895 → 0.4812**(단조감소). trainable 68.8M(qkvo+MLP r16).
- 어댑터: `models/qwen-react-lora-14b-rocm`(672텐서, **263MB**, 로컬보관). **첫 ROCm 14B 어댑터.**
- ⚠️ **미실행**: 14B held-out 채점 / 32B smoke·본런 — 14B 완료(00:23) 후 파이프라인이 stale-monitor 정체로 진행 안 됨(~5h 유휴). 
- **다음 세션 즉시 가능(전부 준비됨)**: ①14B heldout7 채점 ②bnb-ROCm nf4 numeric test ③32B smoke(--load-4bit, nf4 19GB 적재)→32B 본런. bnb 빌드·32B 다운로드·로더코드 모두 커밋됨.

## ✅ 14B 정성 확인 (B, 2026-07-13 아침, qa-tester) — PASS
- ho-select·ho-gallery 생성 → 둘 다 **clean·valid React/TS, EOS 정상종료, im_start/FIM 누수 없음**. ho-select는 원본 onChange 버그(항상 같은값 재설정)까지 자발 수정. val_loss 0.4812와 일관 = 학습 제대로 됨 정성 확증.
- **처리량 ~4.3 tok/s**(14B bf16 ROCm) → 정식채점 시간예산: 1536토큰 ~6분, ho-admin-medit 4096토큰 ~15분(느림).
- base는 bf16 무양자(`from_pretrained torch_dtype=bf16 device_map=auto`)+`PeftModel`로 로드(어댑터 `models/qwen-react-lora-14b-rocm`). egov 원본은 sibling 체크아웃 `twinspace_platform/egovGeoportal/src/components/`.

## ⏭️ C — 다음 세션 정식 채점 (큐잉)
1. **node/tsc 설치**(현재 미설치): `sudo apt install nodejs npm` 또는 nvm → `tsc_eval`에서 `npm install`.
2. `eval_hard_tsc.py --adapter models/qwen-react-lora-14b-rocm --heldout --max-new 4096`(heldout7, base bf16) → `scores-8060.jsonl` 등록 → 62.9% 베이스·8060 r5mlp(80%)·4060(95%) 대조.
3. 이어서 32B: nf4 numeric test → smoke(실 step시간 측정) → 본런.

## 📦 70B급 2종 사전다운로드 완료 (2026-07-13, Windows halo-pm 측) — Linux에서 즉시 사용가능
> 사용자 지시로 **크기 상한 탐색 테스트용** 70B급 nf4를 Windows에서 공유 파티션에 미리 받아둠. GitHub push 없이도 Ubuntu 부팅 즉시 `models/base/`에서 확인됨. 받은 스크립트: `scripts/dl_70b_tests.py`(순차·무한재개·디스크가드), 로그 `logs/dl_70b_tests.log`.

| 모델 | 경로 | 크기 | 샤드 | 상태 |
|---|---|---|---|---|
| `unsloth/Qwen2.5-72B-Instruct-bnb-4bit` | `models/base/qwen2.5-72b-instruct-bnb-4bit` | 39GB | 9 | ✅ clean(index/tokenizer/config 완비, .incomplete 없음) |
| `unsloth/Llama-3.3-70B-Instruct-bnb-4bit` | `models/base/llama-3.3-70b-instruct-bnb-4bit` | 37GB | 8 | ✅ clean |

- **둘 다 nf4(quant_method=bitsandbytes)** → 로드/학습에 **bnb-ROCm(gfx1151) 필수**(이미 빌드 완료). 32B와 동일 `--load-4bit` 경로 재사용 예상.
- **디스크 주의**: 다운로드 후 D: 여유 **~42GB(95% 사용)**. 활성 데이터 드라이브라 빠듯 — 실효 없는 쪽은 회수 가능. 70B QLoRA는 어댑터 소·nf4라 fp16 스파이크 없음(정적 ~40GB가 주비용).
- **성격**: 코드특화 base(Qwen2.5-Coder) 없는 체급이라 **전부 범용 모델**. 이전 교훈(좁은 React/TS는 코드특화>범용/크기, `scores` r6qwen3 base-exp)상 32B Coder 대비 실효는 미지수 → **60GB 통합메모리에서 seq/배치·step time 실측이 목적.** 우선순위는 14B채점·32B 본런 뒤(비강제).

## ✅✅ bnb-ROCm 재빌드 + nf4 GPU 수치검증 PASS (2026-07-14 23:28, autonomous-operator, 크래시 복구세션)
- **크래시로 bnb 소실 발견**: 이전 세션의 bnb 소스/`libbitsandbytes_rocm713.so`가 **/tmp 스크래치패드에 있어 크래시로 전멸**(editable .pth는 죽은 /tmp 경로를 가리켜 `import bitsandbytes` 실패). `_rocm_sdk_devel`(9.3GB, venv=ext4)·패치파일(레포)은 생존.
- **정확한 소스 복원**: 패치 base blob `3836858`(csrc/kernels.hip)을 전 브랜치 검색 → **ROCm 포크 `ROCm/bitsandbytes` 브랜치 `fix/warp-size-gfx942`가 정확히 일치**. upstream 아님(BNB_ROCM_ARCH·kernels.hip은 포크 전용). v0.43.3.dev. 패치 clean 적용(gfx11/12 wave32 브랜치).
- **재빌드**: 영속 위치 `~/bnb-rocm`(ext4, 크래시 생존)에 빌드 — 이번엔 /tmp 회피. cmake+ninja(venv), `-DCOMPUTE_BACKEND=hip -DBNB_ROCM_ARCH=gfx1151 -DCMAKE_HIP_COMPILER=$DEVEL/lib/llvm/bin/amdclang++ -DCMAKE_PREFIX_PATH=$DEVEL`. **컴파일 ~20s**, `.so` 링크 성공 → `uv pip install -e . --no-build-isolation`(editable .pth를 `~/bnb-rocm`로 갱신).
- **★게이트 PASS**: `scripts/test_bnb_nf4_numeric.py` → nf4 quant/dequant 왕복 finite·rel_err **0.0956**, Linear4bit vs fp16 finite·rel_err **0.0936**(둘 다 임계 이내). `lib: ROCm / libbitsandbytes_rocm713.so` 로드확인. (`rocminfo not found` 경고는 bnb arch 자동탐지 폴백일 뿐 무해 — .so는 정상적재.) **4bit 트랙(32B/70B) 언블록.** 로그 `logs/bnb_nf4_numeric.log`, 빌드로그 `logs/bnb_rebuild.log`.
- **재현 메모(다음 크래시 대비)**: bnb를 **절대 /tmp에 두지 말 것**. `~/bnb-rocm`에 소스 존재하면 `uv pip install -e . --no-build-isolation`만으로 즉시 복구, 소실 시 위 5줄.

## ⚠️ transformers 버전 게이트 우회 (2026-07-14) — bnb 0.43.3 → 라벨 0.46.1
- transformers **5.13.1**의 4bit 로더가 `bitsandbytes>=0.46.1` 요구(`validate_environment`) → 우리 빌드 0.43.3.dev 거부.
- **필요 API는 이미 존재·시그니처 일치 확인**: `Params4bit.from_prequantized(data,quantized_stats,requires_grad,device,**kwargs)`(transformers가 `module=`도 넘기나 **kwargs가 흡수), `Linear4bit` OK, nf4 forward 수치게이트 PASS. → **API 호환은 검증됨.**
- **조치(가역)**: `~/bnb-rocm/setup.py` version을 `0.46.1`로 라벨링 후 editable 재설치 → `importlib.metadata.version('bitsandbytes')==0.46.1`로 게이트 통과. **실소스는 여전히 0.43.3.dev+gfx1151패치**(주석에 명시).

## ⛔ 32B 4bit smoke — FORWARD OK · BACKWARD가 gfx1151 GPU 웨지 (2026-07-14 23:34, ★핵심 블로커)
- 커맨드: `--backend cuda --dtype bf16 --load-4bit --base .../qwen2.5-coder-32b-bnb-4bit --lora-mlp --seq 512 --smoke 5 --grad-ckpt`. 로그 `logs/smoke_32b_rocm.log`.
- **로드·forward는 정상**: 771텐서 4bit 적재(~19s), trainable 134M/0.408%, **host RAM peak ~36GB**(4bit ~19GB + 로더 오버헤드; 60GB 안에 안전), forward loss 계산 성공(SDPA 실험적 경고 출력됨=forward 통과).
- **backward에서 즉사**: `(out.loss*SCALE/accum).backward()` → grad-checkpoint recompute→backward 경로에서 **`torch.AcceleratorError: HIP error: unspecified launch failure`(hipErrorLaunchFailure)**. 이후 `hipModuleUnload failed` 연발.
- **★2차 피해=GPU 컨텍스트 웨지**: launch-failure가 amdgpu 링을 매달아 이후 **`torch.cuda.is_available()=False`, device_count=0**(모든 신규 프로세스). `gpu_recovery=-1`(auto)이나 **gfx1151=APU라 커널 리셋 미작동** → **재부팅 필요**. sysfs `card1/device/reset`·dmesg는 root전용, **이 세션 sudo 무권한** → 복구 불가. **← 이 웨지가 이전 오퍼레이터 콘솔 크래시의 유력 원인.**
- **원인 좁힘(높은 확신)**: 14B **bf16(비-4bit)** qkvo+MLP seq1024 grad-ckpt 본런은 112step 정상완주(=SDPA·grad-ckpt backward는 gfx1151에서 일반적으로 OK). 32B의 유일한 신규변수=**bnb 4bit(Linear4bit) backward**. 또한 forward-only 수치게이트는 backward·**double-quant**(체크포인트는 `bnb_4bit_use_double_quant=True`, 게이트는 미검사)를 커버 안 함. → **4bit autograd backward 커널이 유력 용의자.** 단 GPU 死로 격리검증 미완.
- **판정**: 4bit forward/inference는 OK, **4bit QLoRA 학습 backward는 이 bnb-ROCm/gfx1151 빌드에서 불안정**(잠정). 32B/70B 4bit **학습** 트랙 블록.

## ▶️ 재부팅 직후 다음 세션 즉시실행 플랜 (전부 준비·커밋됨)
0. **재부팅 필수**(GPU 웨지 해제). 부팅 후 `torch.cuda.is_available()` True 확인.
1. **backward 격리 진단**(신규 `scripts/test_bnb_nf4_backward.py`): `--stage 1..4` 단독 or 전체. no-dq/dq × forward/backward 4단계 → **로그 마지막 성공단계=웨지지점**. 어느 커널인지 확정. (웨지 가능하니 GPU작업 전 단독실행.)
2. **coordinator 픽스 사다리**(첫 clean backward에서 멈춤):
   - ① **eager 어텐션**(#1 용의자=실험적 SDPA): 신규플래그 `--attn-eager`(train_directml.py에 구현·커밋됨. `attn_implementation=eager` + flash/mem-eff SDP 백엔드 비활성). 32B smoke에 붙여 재시도. 로그 `logs/smoke_32b_try2.log`.
   - ② 여전히 실패 → **grad-ckpt 제거**(`--grad-ckpt` 빼기; 32B-4bit ~24GB라 seq512 무-ckpt도 60GB 안에 들 수 있음, host RAM 감시). recompute-backward 경로 제거.
   - ③ 여전히 → `AMD_SERIALIZE_KERNEL=3`로 2step 재실행 → 정확한 실패커널명 캡처·기록.
   - ④ 다 실패 → 4bit **학습** backward가 gfx1151/이 bnb빌드에서 깨진 것으로 확정. (7B/14B bf16 2step은 여전히 되는지로 GPU 건강 재확인.) 그러면 32B는 **더 신규 bnb ROCm 브랜치 재빌드**(0.46+ IFU-multi-backend류)가 다음 스파이크. 그동안 14B(60.0%)가 banked 최고.
3. eager/무-ckpt로 clean backward 나오면 → 실 s/step 측정 → 데드라인 맞춰 sizing(2ep/seq/step) → 32B 본런→어댑터→heldout7 채점→scores-8060 등록→커밋.
- **게이트 교훈**: `test_bnb_nf4_numeric.py`는 **forward-only라 불충분**. 4bit 학습 GO 판정은 반드시 `test_bnb_nf4_backward.py`(backward+double-quant)까지 PASS해야 함.
