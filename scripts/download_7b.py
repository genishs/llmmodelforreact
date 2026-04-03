"""
Qwen2.5-Coder-7B-Instruct 다운로드 스크립트
저장 경로: ./models/base/qwen2.5-coder-7b
용량: ~28GB (FP32)

실행: python scripts/download_7b.py
"""

import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"
LOCAL_DIR = "./models/base/qwen2.5-coder-7b"


def main():
    save_path = Path(LOCAL_DIR)

    if save_path.exists() and any(save_path.iterdir()):
        print(f"[이미 존재] {LOCAL_DIR}")
        print("다시 다운로드하려면 해당 폴더를 삭제 후 실행하세요.")
        return

    save_path.mkdir(parents=True, exist_ok=True)
    print(f"[다운로드 시작] {MODEL_ID}")
    print(f"[저장 경로] {save_path.resolve()}")
    print(f"[예상 용량] ~28GB (FP32 weights)")
    print("=" * 50)

    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(save_path),
        ignore_patterns=["*.pt", "*.bin"],  # safetensors 우선 사용
    )

    print("\n[완료] 다운로드 성공!")
    print(f"경로: {save_path.resolve()}")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    main()
