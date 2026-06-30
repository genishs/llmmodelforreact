# Linux + ROCm 듀얼부팅 설치 계획 (정보 수집본 — 실행은 사용자 재부팅 가능 시)

> 작성 2026-06-30 (8060). 목적: DirectML 39GB 캡·단편화·fp16강제 한계를 넘어 **gfx1151(Radeon 8060S)
> 네이티브 ROCm**으로 14B 고seq·20B+ 4bit·통합메모리 풀활용. **사용자 업무 중이라 지금은 정보만 수집, 설치 보류.**
> 코드는 이미 ROCm 대비 완료(`train_directml.py --backend cuda`, `docs/rocm-backend-setup.md`).

## ★ 핵심 발견 (웹 리서치, 2026-06-30)
- **Linux ROCm에서 PyTorch가 ~103GB 주소공간 인식**(96GB GPU 할당가능, 통합메모리). DirectML은 전용 39GB 하드캡 →
  **Linux는 통합 64GB(또는 그 이상)를 GPU가 동적 사용** = 사용자가 원한 "공유메모리 접근"이 여기서 실현. rocm-smi는
  APU에서 VRAM 0%로 표시(통합메모리라 정상, cosmetic).
- **gfx1151는 ROCm 7.2에서 Preview 지원**(공식 매트릭스엔 미등재지만 동작: 드라이버 로드·rocminfo 인식·텐서/커널 OK).
- **bitsandbytes ROCm 4bit = gfx1151 지원**(multi-backend refactor, alpha) → **20B 4bit~11GB·32B~18GB 개방**.
- ⚠️ **세그폴트 함정**: 제네릭 PyTorch nightly(`download.pytorch.org/whl/nightly/rocm7.1`)는 gfx1151서 **VRAM 접근 시
  세그폴트**(ROCm #5853, 미해결). **→ 반드시 TheRock gfx1151 전용 빌드 사용**(`rocm.nightlies.amd.com/v2/gfx1151/`).
  `HSA_OVERRIDE_GFX_VERSION`은 효과 없음.

## 설치 절차 (재부팅 가능 시점에)

### 0단계: 디스크 준비 (Windows에서, 사용자 확인 후)
- **대상 = Disk 1 (GIGABYTE 931.5GB, D: "새 볼륨", 여유 187GB)**. C:(Disk 0 Samsung, Windows)는 **절대 미접촉**.
- D:를 shrink해 리눅스용 미할당 ~150GB 확보(`Resize-Partition`) → Ubuntu 설치 시 그 공간에 ext4+swap 생성.
- ⚠️ **디스크 작업은 자동승인 훅이 안 막음** → 매 단계 사용자 명시 확인. shrink 전 D: 중요데이터 백업.

### 1단계: Ubuntu 24.04.3 LTS 설치 (사용자가 직접 — 부팅전 GUI라 Claude 불가)
- USB로 Ubuntu 24.04.3 부팅 → 미할당 공간에 설치(C: Windows 유지, 듀얼부팅 GRUB).
- BIOS: Secure Boot off 권장(ROCm 드라이버), 부팅순서 USB→설치 후 GRUB.
- 커널 6.14 HWE 핀: `sudo apt-mark hold linux-generic-hwe-24.04 linux-headers-generic-hwe-24.04 linux-image-generic-hwe-24.04`

### 2단계: ROCm 7.2 설치
```bash
cd /tmp
wget https://repo.radeon.com/amdgpu-install/7.2/ubuntu/noble/amdgpu-install_7.2.70200-1_all.deb
sudo apt install -y ./amdgpu-install_7.2.70200-1_all.deb && sudo apt update
sudo amdgpu-install -y --usecase=graphics,rocm
sudo usermod -aG render,video $USER
sudo reboot
rocminfo   # gfx1151 인식 확인
```

### 3단계: PyTorch (★TheRock gfx1151 빌드 — 세그폴트 회피)
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -U pip
# 방법A: TheRock gfx1151 nightly (권장 — 세그폴트 안전)
pip install torch --index-url https://rocm.nightlies.amd.com/v2/gfx1151/
# 방법B: ROCm 7.2 repo 휠(triton 먼저 — 의존성)
# pip install <repo.radeon.com .../triton-3.5.1+rocm7.2.0...whl>
# pip install <repo.radeon.com .../torch-2.9.1+rocm7.2.0...whl>
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
pip install transformers peft accelerate datasets safetensors psutil pyyaml
```

### 4단계: 우리 코드 — 백엔드 cuda로 즉시 사용
```bash
git clone <레포> && cd llmmodelforreact
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True   # ROCm서 작동(보조)
# 14B를 seq256→512로 (empty_cache 매step=단편화해소가 1차레버, 4060 확증)
python src/train_directml.py --backend cuda --dtype bf16 \
  --base <14B스냅샷> --seq 512 --lora-r 16 --epochs 1 \
  --train-file data/processed/react_train_r4.jsonl --out models/14b-rocm --smoke 5
```
- **검증 포인트**: ①cuda 인식 ②seq512 step2 이후 OOM 없는가(empty_cache로 DirectML 단편화벽 해소?) ③103GB 주소공간으로
  전용캡 초과 적재되는가 ④bf16 안정.

### 5단계 (선택): bitsandbytes-ROCm 4bit → 20B+
```bash
git clone https://github.com/ROCm/bitsandbytes && cd bitsandbytes
git checkout rocm_enabled_multi_backend
cmake -DCOMPUTE_BACKEND=hip -DBNB_ROCM_ARCH=gfx1151 -S . && make && pip install .
# 됨 → 20B 4bit(~11GB)·32B(~18GB) QLoRA 개방. 4bit blocksize=64 default(ROCm).
```
(multi-backend alpha라 빌드 이슈 가능. 안 되면 fp16 14B로도 충분히 진전.)

## 알려진 한계/주의
- gfx1151 ROCm은 **Preview/실험단계** — 안정성 변동. TheRock 빌드 필수(세그폴트 회피).
- 통합메모리 → **대형모델 로딩 지연**(device transfer 느림). decode가 hipMemcpy 바운드(perf 이슈, pytorch #171687).
- Windows DirectML 경로는 그대로 보존(`--backend directml` 기본) → 듀얼부팅이라 회귀 안전.

## 소스
- TinyComputers: ROCm 7.2 on gfx1151 (Ubuntu 24.04.3·설치명령·103GB)
- ROCm/ROCm #5853 (세그폴트→TheRock 빌드로 회피)
- ROCm/TheRock #655, #3032 (gfx1151 휠·GTT)
- bitsandbytes-foundation #1339, ROCm/bitsandbytes (multi-backend 4bit)
