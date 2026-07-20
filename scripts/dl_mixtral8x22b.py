# -*- coding: utf-8 -*-
"""
Mixtral-8x22B-v0.1 (bf16 원본, ~281GB) 다운로더 — 외장하드 타깃, 무한 재개, 디스크 가드.

대상: mistral-community/Mixtral-8x22B-v0.1  (Apache 2.0, 미게이트, 토큰 불필요)
      MoE 141B총/39B활성, bf16 safetensors ~281GB

타깃: 외장하드 "새 볼륨"(452GB 여유) — 내장은 281GB 못 담음.
패턴: safetensors 샤드 + config + index + tokenizer 만.

디스크 가드: free space가 (남은필요치 + MARGIN) 미만이면 재개 대신 중단(오발사 방지).
무한 재개: 네트워크 오류는 30s 후 재시도. 미게이트라 max_workers 상향(속도).

실행: /home/user/.venvs/ai_model_rocm/bin/python scripts/dl_mixtral8x22b.py
로그: nohup 리다이렉트로 파일에.
"""
import time, sys, os, shutil
from huggingface_hub import snapshot_download

REPO = "mistral-community/Mixtral-8x22B-v0.1"
LOCAL_DIR = "/run/media/user/새 볼륨/mixtral-8x22b-v0.1"
EST_GB = 281
PAT = ["*.safetensors", "*.json", "*.txt", "tokenizer*", "merges*", "vocab*", "*.model"]
MARGIN_GB = 10
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")  # 안정성 우선(재개)


def free_gb(path):
    return shutil.disk_usage(os.path.abspath(path)).free / 1e9


def on_disk_gb(local_dir):
    if not os.path.isdir(local_dir):
        return 0.0
    total = 0
    for root, _, files in os.walk(local_dir):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1e9


def main():
    os.makedirs(LOCAL_DIR, exist_ok=True)
    print(f"[start {time.strftime('%F %T')}] repo={REPO}", flush=True)
    print(f"[target] {LOCAL_DIR}", flush=True)
    have = on_disk_gb(LOCAL_DIR)
    free = free_gb(LOCAL_DIR)
    print(f"[disk] free={free:.1f}GB  already_on_disk={have:.1f}GB  est_total~{EST_GB}GB", flush=True)
    need = max(0.0, EST_GB - have) + MARGIN_GB
    if free < need:
        print(f"[ABORT] free {free:.1f}GB < need {need:.1f}GB (est-have+{MARGIN_GB}) — 공간 부족, 중단", flush=True)
        sys.exit(2)

    attempt = 0
    t0 = time.time()
    while True:
        attempt += 1
        try:
            print(f"[dl] attempt {attempt} (elapsed {(time.time()-t0)/60:.1f}min, "
                  f"on_disk {on_disk_gb(LOCAL_DIR):.1f}GB, free {free_gb(LOCAL_DIR):.1f}GB)", flush=True)
            p = snapshot_download(
                repo_id=REPO,
                local_dir=LOCAL_DIR,
                allow_patterns=PAT,
                max_workers=6,
                etag_timeout=30,
            )
            print(f"ALL DONE {p} | {attempt} attempts | {(time.time()-t0)/60:.1f}min | "
                  f"on_disk {on_disk_gb(LOCAL_DIR):.1f}GB | free {free_gb(LOCAL_DIR):.1f}GB", flush=True)
            return
        except KeyboardInterrupt:
            print("interrupted", flush=True)
            sys.exit(130)
        except Exception as e:
            msg = str(e)[:250]
            if free_gb(LOCAL_DIR) < 2.0:
                print(f"[ABORT] free {free_gb(LOCAL_DIR):.1f}GB — 디스크 소진, 중단: {msg}", flush=True)
                sys.exit(3)
            print(f"[dl] attempt {attempt} 실패: {msg} → 30s 후 재개", flush=True)
            time.sleep(30)


if __name__ == "__main__":
    main()
