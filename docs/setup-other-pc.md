# 다른 PC에서 구동하기 (백업·이전 가이드)

대상 예시: **Intel 14700HX / 32GB RAM / RTX 4060 8GB** (NVIDIA = CUDA).
CUDA는 현재 AMD DirectML 환경보다 빠르고 안정적이며 4비트 양자화를 지원합니다.

## 무엇이 백업되어 있나

| 항목 | 위치 | 비고 |
|------|------|------|
| 코드 전체 | GitHub `genishs/llmmodelforreact` | `git clone`으로 이전 |
| **학습된 LoRA 어댑터** | 레포 안 `models/qwen-react-lora-*` | 1.5B(v2~v4)·**7B(v4)** 포함(작음) |
| 합성 학습 데이터 | 레포 `data/handcrafted_synth*.jsonl` | 재현/재학습용 |
| 베이스 모델 | **레포에 없음** | 새 PC에서 HuggingFace로 재다운로드 |

> 베이스 모델(1.5B ~3GB, 7B ~15GB)은 용량이 커서 레포에 없습니다. 아래 1-c에서 받습니다.

## 새 PC 설치 (CUDA)

```bash
# 1-a. 클론
git clone https://github.com/genishs/llmmodelforreact.git ai_model
cd ai_model

# 1-b. 가상환경 + CUDA PyTorch
python -m venv venv
venv\Scripts\activate                       # (Linux: source venv/bin/activate)
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements-cuda.txt

# 1-c. 베이스 모델 다운로드 (HuggingFace)
pip install -U "huggingface_hub[cli]"
huggingface-cli download Qwen/Qwen2.5-Coder-1.5B-Instruct --local-dir models/base/qwen2.5-coder-1.5b
# 7B도 쓰려면:
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct  --local-dir models/base/qwen2.5-coder-7b
```

## 실행

```bash
# 환경 확인(CUDA 인식되는지)
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# 기본 1.5B로 추론 (CUDA에서는 inference.py / model_loader 경로를 쓸 것)
python src/inference.py            # 대화형 CLI (자동 디바이스 감지)
# ⚠️ inference_7b.py는 DirectML 전용(torch_directml를 모듈 레벨 import)이라 CUDA에선 실행 불가.

# REST API
python src/serve_api.py            # http://localhost:8000/docs

# MCP (프로젝트 폴더에 .mcp.json 두고 Claude Code 실행)
```

## 모델 선택 (1.5B ↔ 7B)

`model_loader.py`가 **디바이스 자동 감지**(CUDA>DirectML>CPU)하고, 환경변수로 모델 선택:

```bash
# 기본: 1.5B (가볍고 빠름, ~3GB VRAM)
# 7B 쓰려면(권장: 4060이면 4비트로 ~5GB):
set REACT_ASSISTANT_MODEL=7b        # (Linux: export REACT_ASSISTANT_MODEL=7b)
```

- **CUDA + 7b** → 자동으로 **4비트 양자화(nf4)** 로 로드 → 8GB VRAM(4060)에 적재.
- **CUDA + 1.5b** → fp16.
- MCP에서 7B 쓰려면 `.mcp.json`의 서버에 `"env": {"REACT_ASSISTANT_MODEL": "7b"}` 추가.

## 검증 상태 (정직)

- **DirectML(AMD PC) 경로**: 검증됨.
- **CUDA 경로(RTX 4060 8GB)**: **2026-06-16 실측 검증 완료.** 1.5B fp16 추론, 7B 4비트
  추론(~14 tok/s, VRAM 5.89GB), 7B QLoRA 학습(seq768, 19.7분) 모두 동작 확인.
  단, **8GB에서 7B QLoRA는 메모리 처치 없이는 사실상 못 돌린다**(공유메모리 스필로 step이
  10초→170초). 처치는 `src/train_qlora.py`에 반영됨 — 상세·비교·egovGeoportal 실파일 테스트는
  [training-benchmark-7b-cuda.md](training-benchmark-7b-cuda.md) 참고.
  점검: `python -c "import bitsandbytes"`, `set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.

## 7B QLoRA 재학습 (잘림 없이) — 4060의 핵심 이점

DirectML(AMD)에선 VRAM 한계로 seq 256/384에 묶여 데이터의 51%가 잘렸다. CUDA에선
4비트 양자화로 가중치가 ~5GB라 **seq 768(잘림 0건)** 학습이 가능하다. (학습셋 실측 토큰
길이 최대 713/평균 263이라 768로 충분 — seq 1024는 과대 설정으로 메모리만 낭비.)

```bash
# 1) 데이터 빌드 (cap 1024로 빌드해도 모든 샘플이 768 이하라 동일)
python src/build_dataset_v2.py --cap 1024 --gh-out-cap 512   # → 303개(272/31)

# 2) QLoRA 학습 (메모리 처치 포함)
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python src/train_qlora.py --seq 768 --out ./models/qwen-react-lora-7b-qlora
```

- ⚠️ **8GB GPU 필수 처치(이미 `train_qlora.py`에 반영):** `prepare_model_for_kbit_training`이
  embed/lm_head를 fp32로 올려 +2.2GB → 스필되므로 fp16으로 되돌림; step마다 `empty_cache`로
  단편화 누적 차단; `adamw_8bit`(paged 아님); `per_device_eval_batch_size=1`. 처치 전엔 step이
  10초→170초로 급락해 사실상 못 끝낸다. 근거·수치는 [training-benchmark-7b-cuda.md](training-benchmark-7b-cuda.md).
- 실측: 3 epoch/102 step, **19.7분**, train_loss 0.55 / eval_loss 0.47.
- 학습 후 서빙: `model_loader.py`의 7b ADAPTER_PATH를 `qwen-react-lora-7b-qlora`로 바꾸거나,
  그 경로를 가리키게 하고 `REACT_ASSISTANT_MODEL=7b`로 실행.
- bf16을 쓰려면 train_qlora.py 안의 `compute_dtype`/`fp16`/`bf16` 주석 참고(4060은 bf16 지원).

## 품질 기대치

- 1.5B: 작은 컴포넌트 TS 변환·표준 훅 생성에 적합. 긴 파일/복잡 로직·리뷰는 불안정.
- 7B(4비트): 1.5B보다 일관성↑. 4비트라 fp16 대비 미세한 품질 저하 가능하나 실사용 무난.
