# ROCm/CUDA 백엔드 전환 — 설치·테스트 가이드 (DirectML 공유메모리 한계 돌파 시도)

> 작성 2026-06-27 (8060). **동기**: DirectML이 14B fp16을 **seq256**에 묶은 근본 원인은
> `torch_directml`에 **`empty_cache`가 없어 단편화가 누적**되는 것 + **전용 메모리에 하드 바운드**
> (공유메모리 미사용). 코드는 수정 완료(테스트는 VRAM 재할당 후). 이 문서 = 백엔드 전환 절차/근거.

## 왜 ROCm인가 (웹 기술검토 결론, 2026-06-27)
- **DirectML 측(막힘 확정)**: MS DirectML #361·#379 — OOM이 **전용 GPU 메모리 크기에만 연동**,
  총 시스템 RAM과 무관 = 공유 풀 미사용. MS "not planned" 종결. `PYTORCH_CUDA_ALLOC_CONF` 등
  CUDA env var **무시**. → 할당자 커스터마이즈로도 그 아래 클로즈드 DirectML.dll이 전용-바운드라 막힘.
- **ROCm 측(가능성)**: ROCm/TheRock #3032 — gfx1151(우리 칩)에서 PyTorch가 전용 VRAM 후
  **shared GPU memory(GTT)로 넘어감 = Windows에서도 공유 통합메모리 접근 발생**. 그리고
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, `PYTORCH_NO_CUDA_MEMORY_CACHING=1`이
  **ROCm에선 작동**(HIP가 CUDA API로 위장). 단 아직 bleeding-edge(고할당 시 spill-OOM 버그).
- **핵심 이득 3가지**: ①`torch.cuda.empty_cache()` 작동 → **단편화 해소 → seq256 천장 상향 기대**
  ②**bf16 지원**(DirectML 불가) ③메모리 env var 유효 + GTT 공유접근.

## 코드 변경(완료, 커밋됨)
`src/train_directml.py`가 **이중 백엔드**가 됨:
- `--backend {directml,cuda,auto}` (기본 directml). cuda = ROCm/HIP 또는 NVIDIA.
- `--dtype bf16` 허용(cuda 전용. directml이면 fp16으로 자동 강제).
- `--empty-cache-every N` (기본 -1=auto: cuda는 매 optim step, directml은 0). 단편화 억제 레버.
- top-level `import torch_directml` 제거 → **ROCm 전용 환경(torch_directml 미설치)에서도 import 가능**.
- step 로그에 cuda일 때 `GPU xx.xGB`(torch.cuda.memory_allocated) 표시.

## 설치 (택1) — VRAM 재할당 후 진행
### A. Windows 네이티브 ROCm — TheRock gfx1151 휠 (재부팅·OS전환 없이 시도 가능)
```
# 새 venv 권장(현 DirectML venv와 분리)
python -m venv venv-rocm && venv-rocm\Scripts\activate
# TheRock(ROCm on Windows) gfx1151 nightly 휠 — 프로젝트 README/ROCm TheRock 릴리스에서 정확 index 확인
pip install --index-url <therock-gfx1151-wheel-index> torch torchvision
pip install transformers peft accelerate datasets safetensors psutil pyyaml
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
### B. 베어메탈 Linux + ROCm (정공법, 안정성↑, 4bit/20B+까지)
- Ubuntu + ROCm 설치 → `pip install torch --index-url https://download.pytorch.org/whl/rocm6.x`
- GTT 동적 통합메모리로 카브 제약·단편화 해소. bitsandbytes-ROCm로 4bit → 20B/32B 개방.

## 테스트 레시피 (재할당 후)
```bash
# env var(ROCm서 작동): 공유/단편화 제어
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
# 14B를 seq256→512로 올려가며 empty_cache 효과 측정
python src/train_directml.py --backend cuda --dtype bf16 \
  --base <14B스냅샷> --seq 512 --lora-r 16 --epochs 1 \
  --train-file data/processed/react_train_r4.jsonl --out models/qwen-react-lora-14b-rocm --smoke 5
```
**확인 포인트**:
1. `torch.cuda.is_available()=True` (백엔드 인식)
2. seq512(또는 그 이상) smoke가 **step 2 이후도 OOM 없이** 진행되는가 → empty_cache가 DirectML의
   step-2 OOM(단편화)을 해소하는지. (DirectML은 320 step2서 죽었음.)
3. 전용 카브를 **작게** 두고도 GTT 공유로 14B(29GB)가 적재되는가 → "공유메모리 접근" 실증.
4. bf16 손실 곡선 정상성.

## 폴백/주의
- TheRock(Windows ROCm)은 실험단계 → 불안정하면 **Linux ROCm(B)** 로.
- DirectML 경로는 그대로 보존(`--backend directml` 기본) → 회귀 안전.
- 측정 캐논·held-out은 백엔드 무관(어댑터+점수). 백엔드는 "더 큰 모델·고seq를 여는" 인프라일 뿐.

## 근거 소스
- microsoft/DirectML #379, #361 (DirectML 전용-바운드, not planned)
- ROCm/TheRock #3032 (gfx1151 GTT 공유접근·env var 작동)
- PyTorch Forums: Windows GPU shared memory fallback (개념 실재, 스택 의존)
