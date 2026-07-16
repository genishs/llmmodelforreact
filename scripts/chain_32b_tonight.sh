#!/usr/bin/env bash
# chain_32b_tonight.sh — 32B bf16 다운로드 완료를 기다렸다가 검증하고 HQQ 4bit 본런을 발사한다.
#
# WHY: 두목이 자리를 비운 밤(마감 05:00 KST)에 사람 개입 없이 다운로드→검증→학습이 이어지게 한다.
#      systemd-run --user 로 띄우므로 GNOME 사망/로그아웃/터미널 종료에도 살아남는다.
#
# 검증을 넣는 이유: 다운로드가 조용히 깨진 채로 6시간짜리 본런을 태우면 밤을 통째로 날린다.

set -uo pipefail

REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
BASE="./models/base/qwen2.5-coder-32b"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain32b.log"
DL_UNIT="dl32b.service"

cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] chain 시작"

# ---------- 1. 다운로드 완료 대기 (최대 3시간) ----------
echo "[$(date '+%F %T')] 다운로드 대기…"
for i in $(seq 1 1080); do   # 1080 * 10s = 3h
  systemctl --user is-active --quiet "$DL_UNIT" || break
  sleep 10
done
if systemctl --user is-active --quiet "$DL_UNIT"; then
  echo "[$(date '+%F %T')] ✗ 중단: 3시간 내 다운로드가 안 끝남"; exit 1
fi
echo "[$(date '+%F %T')] 다운로드 유닛 종료. 결과=$(systemctl --user show "$DL_UNIT" -p Result --value 2>/dev/null)"

# ---------- 2. 검증 ----------
echo "[$(date '+%F %T')] 검증…"
shards=$(ls "$BASE"/model-*.safetensors 2>/dev/null | wc -l)
incomplete=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
size=$(du -sb "$BASE" 2>/dev/null | cut -f1)
echo "  샤드: $shards/14 | incomplete: $incomplete | 크기: $(( size / 1024 / 1024 / 1024 ))GB"

[ "$shards" -eq 14 ]      || { echo "✗ 샤드 수 불일치 — 중단"; exit 1; }
[ "$incomplete" -eq 0 ]   || { echo "✗ 미완료 파일 존재 — 중단"; exit 1; }
[ -f "$BASE/config.json" ] || { echo "✗ config.json 없음 — 중단"; exit 1; }
[ "$size" -gt 60000000000 ] || { echo "✗ 크기 미달($size) — 중단"; exit 1; }

# safetensors 헤더가 실제로 읽히는지 (조용한 손상 탐지)
"$PY" - <<'PYEOF' || { echo "✗ safetensors 무결성 실패 — 중단"; exit 1; }
import glob, json, sys, struct
ok = 0
for f in sorted(glob.glob("./models/base/qwen2.5-coder-32b/model-*.safetensors")):
    with open(f, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        json.loads(fh.read(n))          # 헤더 파싱 실패 시 예외
    ok += 1
print(f"  safetensors 헤더 OK: {ok}개")
sys.exit(0 if ok == 14 else 1)
PYEOF
echo "[$(date '+%F %T')] ✓ 검증 통과"

# ---------- 3. 본런 발사 ----------
echo "[$(date '+%F %T')] 32B HQQ 본런 발사"
bash scripts/gpu_job.sh --name train32b --timeout 21600 -- \
  "$PY" src/train_directml.py \
    --backend cuda --dtype bf16 \
    --base "$BASE" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 \
    --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 1024 \
    --epochs 3 \
    --out ./models/qwen-react-lora-32b-hqq
echo "[$(date '+%F %T')] chain 완료 — 본런은 별도 유닛에서 진행 중"
