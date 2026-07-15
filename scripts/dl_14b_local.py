# -*- coding: utf-8 -*-
"""
14B 견고한 다운로드 (local_dir판) — models/base/qwen2.5-coder-14b 에 직접 적재.

기존 dl_14b_robust.py는 HF 캐시로 받지만, 학습은 --base models/base/qwen2.5-coder-14b 를
기대(7B도 이 레이아웃). 그래서 local_dir로 그 경로에 직접 받고, stall/rate-limit에서
무한 재개(.incomplete 이어받기)한다. 완료 시 "ALL DONE" 출력 후 종료(0).

실행:  ~/.venvs/ai_model_rocm/bin/python scripts/dl_14b_local.py
"""
import time, sys, os
from huggingface_hub import snapshot_download

REPO = "Qwen/Qwen2.5-Coder-14B-Instruct"
LOCAL_DIR = "models/base/qwen2.5-coder-14b"
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
            max_workers=2,            # 비인증 rate-limit 완화
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
