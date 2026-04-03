# -*- coding: utf-8 -*-
"""
환경 확인 스크립트
실행: python src/check_env.py
"""

import sys
import io

# Windows 콘솔 UTF-8 출력
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def check_python():
    print(f"Python: {sys.version}")
    assert sys.version_info >= (3, 10), "Python 3.10 이상 필요"
    print("  [OK] Python 버전")

def check_torch():
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"  CUDA 사용 가능: {torch.cuda.is_available()}")
        print("  [OK] PyTorch")
        return torch
    except ImportError:
        print("  [FAIL] PyTorch 미설치 -> pip install torch")
        return None

def check_directml(torch):
    try:
        import torch_directml
        dml = torch_directml.device()
        x = torch.ones(2, 2).to(dml)
        _ = x + x
        device_name = torch_directml.device_name(0)
        device_count = torch_directml.device_count()
        print(f"DirectML: 설치됨 (GPU {device_count}개)")
        print(f"  device: {dml}")
        print(f"  GPU 이름: {device_name}")
        print("  [OK] DirectML (AMD GPU)")
        return dml
    except ImportError:
        print("  [FAIL] torch-directml 미설치 -> pip install torch-directml")
        return None
    except Exception as e:
        print(f"  [FAIL] DirectML 오류: {e}")
        return None

def check_transformers():
    try:
        import transformers
        print(f"Transformers: {transformers.__version__}")
        print("  [OK] Transformers")
    except ImportError:
        print("  [FAIL] transformers 미설치 -> pip install transformers")

def check_peft():
    try:
        import peft
        print(f"PEFT: {peft.__version__}")
        print("  [OK] PEFT (LoRA)")
    except ImportError:
        print("  [FAIL] peft 미설치 -> pip install peft")

def check_datasets():
    try:
        import datasets
        print(f"Datasets: {datasets.__version__}")
        print("  [OK] Datasets")
    except ImportError:
        print("  [FAIL] datasets 미설치 -> pip install datasets")

def check_memory():
    try:
        import psutil
        ram = psutil.virtual_memory()
        print(f"RAM: 전체 {ram.total // (1024**3)}GB / 사용 가능 {ram.available // (1024**3)}GB")
        print("  [OK] 메모리 확인")
    except ImportError:
        print("  메모리 확인: pip install psutil")

if __name__ == "__main__":
    print("=" * 50)
    print("AI Model 환경 확인")
    print("=" * 50)

    check_python()
    print()
    torch = check_torch()
    print()
    if torch:
        check_directml(torch)
    print()
    check_transformers()
    check_peft()
    check_datasets()
    print()
    check_memory()
    print()
    print("=" * 50)
    print("환경 확인 완료")
    print("=" * 50)
