# -*- coding: utf-8 -*-
"""
70B급 테스트용 사전양자화(bnb nf4) 다운로더 — 순차, 무한 재개, 디스크 가드.

대상(둘 다 nf4 4bit 사전양자화 ~40GB, load_in_4bit, quant_method=bitsandbytes):
  1) unsloth/Qwen2.5-72B-Instruct-bnb-4bit   -> models/base/qwen2.5-72b-instruct-bnb-4bit
  2) unsloth/Llama-3.3-70B-Instruct-bnb-4bit -> models/base/llama-3.3-70b-instruct-bnb-4bit

공유 NTFS 파티션(models/base/)이라 Linux(ROCm) 학습이 그대로 읽음.
로드/학습엔 bnb-ROCm(gfx1151) 필수(quant_method=bitsandbytes) — 이미 빌드 완료.

디스크 가드: 각 모델 시작 전 free space 확인. (예상크기 + 6GB 여유마진) 미만이면
그 모델은 SKIP 하고 다음으로(첫 모델 온전 보존). 순차라 중간 중단해도 안전.

실행:  venv/Scripts/python.exe scripts/dl_70b_tests.py    (프로젝트 루트에서)
로그:  logs/dl_70b_tests.log 로 리다이렉트 권장.
"""
import time, sys, os, shutil
from huggingface_hub import snapshot_download

MODELS = [
    ("unsloth/Qwen2.5-72B-Instruct-bnb-4bit",   "models/base/qwen2.5-72b-instruct-bnb-4bit",   42),
    ("unsloth/Llama-3.3-70B-Instruct-bnb-4bit", "models/base/llama-3.3-70b-instruct-bnb-4bit", 41),
]
PAT = ["*.safetensors", "*.json", "*.txt", "tokenizer*", "merges*", "vocab*", "*.model"]
MARGIN_GB = 6
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def free_gb(path="."):
    return shutil.disk_usage(os.path.abspath(path)).free / 1e9


def already_done(local_dir, est_gb):
    """이미 대부분 받아졌으면(추정치의 90%↑) 완료로 간주 → 재개 스킵 판단용 참고."""
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


def download_one(repo, local_dir, est_gb):
    os.makedirs(local_dir, exist_ok=True)
    have = already_done(local_dir, est_gb)
    free = free_gb()
    print(f"\n===== {repo}", flush=True)
    print(f"[disk] free={free:.1f}GB  already_on_disk={have:.1f}GB  est_total~{est_gb}GB", flush=True)
    # 남은 필요치 = est - have (이미 받은 만큼 차감), + 마진
    need = max(0.0, est_gb - have) + MARGIN_GB
    if free < need:
        print(f"[SKIP] free {free:.1f}GB < need {need:.1f}GB (est-have+{MARGIN_GB}) → 이 모델 건너뜀(공간부족)", flush=True)
        return "skip-space"
    attempt = 0
    t0 = time.time()
    while True:
        attempt += 1
        try:
            print(f"[dl] attempt {attempt} (elapsed {(time.time()-t0)/60:.1f}min, free {free_gb():.1f}GB)", flush=True)
            p = snapshot_download(
                repo_id=repo,
                local_dir=local_dir,
                allow_patterns=PAT,
                max_workers=2,      # 비인증 rate-limit 완화
                etag_timeout=30,
            )
            print(f"ALL DONE {p} | {attempt} attempts | {(time.time()-t0)/60:.1f}min | free {free_gb():.1f}GB", flush=True)
            return "done"
        except KeyboardInterrupt:
            print("interrupted", flush=True)
            sys.exit(130)
        except Exception as e:
            # 디스크 꽉참 등 회복불가 신호면 중단
            msg = str(e)[:200]
            if free_gb() < 1.5:
                print(f"[ABORT] free {free_gb():.1f}GB — 디스크 소진, 이 모델 중단: {msg}", flush=True)
                return "abort-space"
            print(f"[dl] attempt {attempt} 실패: {msg} → 30s 후 재개", flush=True)
            time.sleep(30)


def main():
    print(f"[start] free={free_gb():.1f}GB  models={len(MODELS)}", flush=True)
    results = {}
    for repo, local_dir, est in MODELS:
        results[repo] = download_one(repo, local_dir, est)
    print("\n===== SUMMARY =====", flush=True)
    for repo, st in results.items():
        print(f"  {st:12s}  {repo}", flush=True)
    print(f"[end] free={free_gb():.1f}GB", flush=True)


if __name__ == "__main__":
    main()
