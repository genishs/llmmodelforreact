# 환경 설정 가이드

## 1. Python 설치

### 방법 A: 공식 설치 (권장)
1. https://www.python.org/downloads/ 에서 Python 3.11 다운로드
2. 설치 시 "Add Python to PATH" 반드시 체크
3. 확인: `python --version`

### 방법 B: winget 사용
```powershell
winget install Python.Python.3.11
```

---

## 2. 가상환경 생성

```bash
cd C:\Users\user\Documents\workspace\study\ai_model
python -m venv venv

# 활성화 (Windows)
venv\Scripts\activate
```

---

## 3. PyTorch 설치 (AMD GPU - DirectML)

AMD GPU on Windows는 CUDA 대신 DirectML 사용

```bash
# PyTorch (CPU 버전 기본)
pip install torch torchvision torchaudio

# DirectML 백엔드 (AMD GPU 가속)
pip install torch-directml

# 핵심 패키지
pip install transformers datasets peft accelerate
pip install bitsandbytes-windows   # Windows용 양자화
pip install sentencepiece tokenizers
pip install jupyter ipykernel
```

---

## 4. GPU 확인 테스트

```python
import torch
import torch_directml

dml = torch_directml.device()
print(f"DirectML device: {dml}")

# 간단한 연산 테스트
x = torch.ones(3, 3).to(dml)
print(x)
```

---

## 5. 패키지 버전 (검증된 조합)

```
python==3.11
torch==2.3.0
torch-directml==0.2.4
transformers==4.44.0
datasets==2.20.0
peft==0.12.0
accelerate==0.33.0
```
