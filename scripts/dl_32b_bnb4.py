# -*- coding: utf-8 -*-
"""
32B 사전양자화(bnb nf4) 다운로더 — unsloth/Qwen2.5-Coder-32B-Instruct-bnb-4bit (~19GB).

fp16 64GB 대신 사전양자화본(~19GB)을 받아 load-time fp16->4bit RAM 스파이크도 회피.
단, 로드/학습 시 bitsandbytes-ROCm가 필요(별도 빌드 게이트). local_dir 직접 적재 + 무한 재개.

실행:  ~/.venvs/ai_model_rocm/bin/python scripts/dl_32b_bnb4.py
"""
import time, sys, os
from huggingface_hub import snapshot_download

REPO = "unsloth/Qwen2.5-Coder-32B-Instruct-bnb-4bit"
LOCAL_DIR = "models/base/qwen2.5-coder-32b-bnb-4bit"
PAT = ["*.safetensors", "*.json", "*.txt", "tokenizer*", "merges*", "vocab*", "*.model"]
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.makedirs(LOCAL_DIR, exist_ok=True)

attempt = 0
t0 = time.time()
while True:
    attempt += 1
    try:
        print(f"[dl] attempt {attempt} (elapsed {(time.time()-t0)/60:.1f}min)", flush=True)
        p = snapshot_download(
            repo_id=REPO,
            local_dir=LOCAL_DIR,
            allow_patterns=PAT,
            max_workers=2,
            etag_timeout=30,
        )
        print(f"ALL DONE {p} | {attempt} attempts | {(time.time()-t0)/60:.1f}min", flush=True)
        sys.exit(0)
    except KeyboardInterrupt:
        print("interrupted", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"[dl] attempt {attempt} 실패: {str(e)[:200]} → 30s 후 재개", flush=True)
        time.sleep(30)
