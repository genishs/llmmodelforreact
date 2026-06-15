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

# 기본 1.5B로 추론
python src/inference_7b.py "useToggle 훅 만들어줘"   # (CLI; 내부는 model_loader 자동 디바이스)

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

- **DirectML(현 AMD PC) 경로**: 검증됨.
- **CUDA 경로**: 코드는 작성됐으나 **이 작업 환경엔 NVIDIA가 없어 미검증**.
  4060에서 첫 실행 시 확인 필요. 4비트는 `bitsandbytes`가 CUDA를 정상 인식해야 함
  (`python -c "import bitsandbytes"` 로 점검). 문제 시 1.5B fp16부터 시작 권장.

## 품질 기대치

- 1.5B: 작은 컴포넌트 TS 변환·표준 훅 생성에 적합. 긴 파일/복잡 로직·리뷰는 불안정.
- 7B(4비트): 1.5B보다 일관성↑. 4비트라 fp16 대비 미세한 품질 저하 가능하나 실사용 무난.
