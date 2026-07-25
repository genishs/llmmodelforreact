#!/usr/bin/env bash
# chain_pipeline_full.sh — 두목 지정 완전순차 파이프라인 (2026-07-17):
#   ① 123B 학습완료 대기 → ② 123B 채점 → ③ 72B Q4 학습(숏런→풀) → ④ 72B Q4 채점
# 단일 GPU·통합메모리라 전부 순차(겹치면 프리징). 각 단계는 앞 유닛 종료를 기다린 뒤 진행.
# 실패한 학습은 어댑터 부재로 채점 건너뜀. 채점=eval_hard_tsc(GPU 생성+tsc) → score_v2(GPU0 재채점).
set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain_pipeline.log"
UNIT123="gpujob-train123bfull-20260717-122446-555987.service"
BASE123="./models/base/mistral-large-2411"
ADPDIR123="./models/qwen-react-lora-123b-hqq"
BASE72="./models/base/qwen2.5-72b-instruct"
SHORT_FILE="./data/processed/react_train_123b_short.jsonl"
cd "$REPO" || exit 1; exec >>"$LOG" 2>&1
echo "===== [$(date '+%F %T')] 완전순차 파이프라인 시작 ====="

wait_unit_gone(){ local pat="$1" max="${2:-2400}"; for i in $(seq 1 "$max"); do systemctl --user list-units "$pat" --no-legend 2>/dev/null | grep -q running || return 0; sleep 15; done; return 1; }
gpu_free_ok(){ local b h; b=$(cat /sys/class/drm/card*/device/gpu_busy_percent 2>/dev/null|head -1); h=$(free -g|awk '/Mem:/{print $7}'); echo "[$(date '+%F %T')] GPU busy=${b}% host가용=${h}GB"; [ "${b:-100}" -le 50 ] 2>/dev/null && [ "${h:-0}" -ge 15 ] 2>/dev/null; }

# 채점 1건: eval_hard_tsc(생성+v1) → score_v2(재채점). $1=라벨 $2=어댑터디렉토리 $3=base $4=nbits
score_one(){
  local label="$1" adpdir="$2" base="$3" nbits="$4" adp="$2/adapter_model.safetensors"
  if [ ! -f "$adp" ] || [ "$(stat -c %s "$adp" 2>/dev/null||echo 0)" -lt 10000000 ]; then
    echo "[$(date '+%F %T')] ⏭ $label 채점 건너뜀 — 어댑터 없음/비정상($adp)"; return 1; fi
  echo "[$(date '+%F %T')] ▶ $label 채점 (eval_hard_tsc hqq${nbits}bit mn4096) — GPU 생성, ~14-16h"
  bash scripts/gpu_job.sh --name "score-$label" --timeout 72000 -- \
    "$PY" scripts/eval_hard_tsc.py --adapter "$adpdir" --base "$base" --label "$label" \
      --quant hqq --hqq-nbits "$nbits" --hqq-group-size 64 --heldout --max-new 4096
  sleep 20; wait_unit_gone "gpujob-score-$label-*" 1400
  echo "[$(date '+%F %T')] $label → score_v2 재채점(GPU0)"; "$PY" scripts/score_v2.py --label "$label" 2>&1 | tail -20
  echo "[$(date '+%F %T')] ✅ $label 채점완료"
}

# ── ① 123B 학습완료 대기 ──
echo "[$(date '+%F %T')] ①123B 학습완료 대기…"
for i in $(seq 1 2400); do systemctl --user is-active "$UNIT123" >/dev/null 2>&1 || break; sleep 15; done
echo "[$(date '+%F %T')] 123B 학습종료 (result=$(systemctl --user show "$UNIT123" -p Result --value 2>/dev/null))"; sleep 30

# ── ② 123B 채점 (Q2 2bit) ──
score_one "123b-hqq2-seq512" "$ADPDIR123" "$BASE123" 2

# ── ③ 72B Q4 학습: 숏런 → 검증 → 풀 ──
echo "[$(date '+%F %T')] ③72B Q4 학습 준비 — GPU/메모리 회복 확인"
sleep 20
if ! gpu_free_ok; then echo "✗ GPU/RAM 미회복 → 72B 중단(안전). 코디 확인."; exit 1; fi
[ -f "$BASE72/config.json" ] || { echo "✗ 72B 모델 없음 — 중단"; exit 1; }
echo "[$(date '+%F %T')] 72B Q4 숏런(80샘플, seq1024) 발사"
bash scripts/gpu_job.sh --name train72bq4short --timeout 21600 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE72" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 1024 --epochs 1 --train-file "$SHORT_FILE" \
    --out ./models/qwen-react-lora-72b-q4-short
sleep 20; wait_unit_gone 'gpujob-train72bq4short-*' 1440
ADPS="models/qwen-react-lora-72b-q4-short/adapter_model.safetensors"
slog=$(ls -t ~/gpu_jobs/logs/gpujob-train72bq4short-*.log 2>/dev/null|head -1)
wedge=$(grep -icE "hipError|unspecified launch|device wedged" "$slog" 2>/dev/null); wedge=${wedge:-0}
if [ -f "$ADPS" ] && [ "$(stat -c %s "$ADPS" 2>/dev/null||echo 0)" -gt 10000000 ] && [ "$wedge" -eq 0 ]; then
  echo "[$(date '+%F %T')] ✅ 72B Q4 숏런 성공(어댑터 $(( $(stat -c %s "$ADPS")/1024/1024 ))MB, 웨지0) → 풀에폭"
else
  echo "[$(date '+%F %T')] ✗ 72B Q4 숏런 실패(어댑터=$([ -f "$ADPS" ]&&echo Y||echo N) 웨지=$wedge) → 파이프라인 중단."; exit 1
fi
sleep 15
echo "[$(date '+%F %T')] 72B Q4 풀에폭(315샘플, seq1024) 발사"
bash scripts/gpu_job.sh --name train72bq4full --timeout 43200 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE72" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 1024 --epochs 1 \
    --out ./models/qwen-react-lora-72b-hqq-q4
sleep 20; wait_unit_gone 'gpujob-train72bq4full-*' 2880
echo "[$(date '+%F %T')] 72B Q4 풀에폭 종료 (result=$(systemctl --user list-units 'gpujob-train72bq4full-*' --all --no-legend 2>/dev/null|head -1))"; sleep 30

# ── ④ 72B Q4 채점 ──
score_one "72bq4-hqq4-seq1024" "./models/qwen-react-lora-72b-hqq-q4" "$BASE72" 4

echo "===== [$(date '+%F %T')] 완전순차 파이프라인 종료 ====="
