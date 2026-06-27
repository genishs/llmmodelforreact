# -*- coding: utf-8 -*-
"""
14B 견고한 다운로드 — stall/끊김/rate-limit에서 무한 재개(resume).

비인증 HF는 종종 throttle/stall → snapshot_download를 재시도 루프로 감싸 .incomplete에서
이어받아 모든 파일이 받아질 때까지 자동 완주. 사용자 부재 중 무인 완료용.

실행:  python scripts/dl_14b_robust.py
완료 시 "ALL DONE" 출력 후 종료(0). 그 전까지 예외마다 30s 쉬고 재개.
"""
import time, sys, os
from huggingface_hub import snapshot_download

REPO = "Qwen/Qwen2.5-Coder-14B-Instruct"
PAT = ["*.safetensors", "*.json", "*.txt", "tokenizer*", "merges*", "vocab*", "*.model"]
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

attempt = 0
t0 = time.time()
while True:
    attempt += 1
    try:
        print(f"[dl] attempt {attempt} (elapsed {(time.time()-t0)/60:.1f}min)", flush=True)
        p = snapshot_download(
            repo_id=REPO,
            allow_patterns=PAT,
            max_workers=2,            # 비인증 rate-limit 완화 위해 동시성 낮춤
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
