@echo off
echo ===================================
echo AI Model 환경 설치 스크립트
echo ===================================

REM 가상환경 생성
python -m venv venv
call venv\Scripts\activate

REM pip 업그레이드
python -m pip install --upgrade pip

REM PyTorch 설치 (CPU 버전)
pip install torch torchvision torchaudio

REM DirectML 설치 (AMD GPU)
pip install torch-directml

REM 나머지 패키지
pip install transformers datasets peft accelerate
pip install tokenizers sentencepiece PyYAML tqdm psutil
pip install jupyter ipykernel pandas numpy

echo.
echo ===================================
echo 설치 완료! 환경 확인 실행:
echo python src/check_env.py
echo ===================================
pause
