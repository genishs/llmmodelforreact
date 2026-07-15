#!/usr/bin/env bash
# chain_score_32b.sh — 32B 본런이 끝나기를 기다렸다가 heldout7 채점을 자동 발사한다.
#
# WHY: 두목이 자리를 비운 밤(마감 05:00 KST)에, 코디네이터 세션이 죽더라도
#      새벽에 "점수"가 나와 있어야 한다. 두목이 정한 증명 기준 = 스텝 완주가 아니라 채점 점수.
#
# 캐논: heldout7-mn4096-lf-PERFILE-noTS2347-rocm  (--heldout --max-new 4096)
# 비교축: 4060 r6base(7B, cap1024) = 88.6% — 동일 데이터·동일 캐논.
#
# 32B bf16 은 65GB 라 채점 시에도 메모리에 안 들어간다 → 채점도 반드시 --quant hqq (4bit).
# 이 경로는 14B 스모크로 검증됨(로드→양자화→생성→tsc→채점, exit 0).

set -uo pipefail

REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
ADAPTER="./models/qwen-react-lora-32b-hqq"
BASE="./models/base/qwen2.5-coder-32b"
LABEL="32b-rocm-hqq4bit-mlp-seq1024-cap1024"
LOG="/home/user/gpu_jobs/logs/chain_score32b.log"

cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] 채점 체인 시작"

# ---------- 1. 본런 종료 대기 (최대 8시간) ----------
echo "[$(date '+%F %T')] 32B 본런 종료 대기…"
for i in $(seq 1 2880); do   # 2880 * 10s = 8h
  if ! systemctl --user list-units 'gpujob-train32b-*' --no-legend 2>/dev/null | grep -q running; then
    break
  fi
  sleep 10
done
if systemctl --user list-units 'gpujob-train32b-*' --no-legend 2>/dev/null | grep -q running; then
  echo "[$(date '+%F %T')] ✗ 중단: 8시간 내 본런이 안 끝남"; exit 1
fi
echo "[$(date '+%F %T')] 본런 종료 감지"

# ---------- 2. 어댑터 검증 ----------
# 본런이 실패해 어댑터가 없거나 깨졌으면 6시간짜리 채점을 헛돌리지 않는다.
sleep 20   # 파일 flush 여유
if [ ! -f "$ADAPTER/adapter_model.safetensors" ]; then
  echo "[$(date '+%F %T')] ✗ 어댑터 없음($ADAPTER) — 본런이 실패한 것으로 보임. 채점 중단."
  ls -la "$ADAPTER" 2>&1 | head
  exit 1
fi
sz=$(stat -c %s "$ADAPTER/adapter_model.safetensors" 2>/dev/null || echo 0)
echo "[$(date '+%F %T')] ✓ 어댑터 발견: $(( sz / 1024 / 1024 ))MB"
[ "$sz" -gt 10000000 ] || { echo "✗ 어댑터가 비정상적으로 작음 — 중단"; exit 1; }

# ---------- 3. 채점 발사 ----------
echo "[$(date '+%F %T')] heldout7 채점 발사 (캐논 mn4096, --quant hqq)"
bash scripts/gpu_job.sh --name score32b --timeout 14400 -- \
  "$PY" scripts/eval_hard_tsc.py \
    --adapter "$ADAPTER" \
    --base "$BASE" \
    --label "$LABEL" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 \
    --heldout --max-new 4096
echo "[$(date '+%F %T')] 채점 체인 완료 — 채점은 별도 유닛에서 진행 중"
