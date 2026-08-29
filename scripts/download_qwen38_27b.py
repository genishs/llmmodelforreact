"""
Qwen3.8-27B (C안 후보) 다운로드 스크립트
저장 경로: /run/media/user/sgshs_data/ai_model_fast/qwen3.8-27b (NVMe, USB하드 아님)
용량: ~55.6GB (bf16 safetensors, vision tower 포함 전체 체크포인트)
라이선스: Apache-2.0

실행 (systemd-run으로 반드시 감쌀 것 — & / nohup은 수확당함):
  systemd-run --user --unit=dl-qwen38-27b \
    --setenv=HF_HUB_ENABLE_HF_TRANSFER=1 \
    /home/user/.venvs/ai_model_rocm/bin/python \
    /mnt/data/Documents/workspace/study/ai_model/scripts/download_qwen38_27b.py
"""

import os
from pathlib import Path
from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen3.8-27B"
LOCAL_DIR = "/run/media/user/sgshs_data/ai_model_fast/qwen3.8-27b"


def main():
    save_path = Path(LOCAL_DIR)
    save_path.mkdir(parents=True, exist_ok=True)
    print(f"[다운로드 시작] {MODEL_ID}")
    print(f"[저장 경로] {save_path.resolve()}")
    print(f"[예상 용량] ~55.6GB (bf16, vision tower 포함)")
    print("=" * 50)

    # snapshot_download는 기본적으로 resume 지원 → systemd 재기동/중단에도 이어받기 가능.
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(save_path),
        ignore_patterns=["*.pt", "*.bin", "*.gguf"],
    )

    print("\n[완료] 다운로드 성공!")
    print(f"경로: {save_path.resolve()}")


if __name__ == "__main__":
    main()
