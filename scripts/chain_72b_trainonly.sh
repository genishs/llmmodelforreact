#!/usr/bin/env bash
# chain_72b_trainonly.sh — 두목 지시(2026-07-18): 72B Q4 **채점 연기**. 마감(내일 07/19) 안에 못 끝나서 학습까지만.
#   ① 이미 도는 123B 채점 유닛 완료 대기(새로 발사 안 함) → ② 123B score_v2 재채점 → ③ 72B Q4 학습(숏런→풀) → 종료(72B 채점 없음).
# 기존 chain_pipeline_full.sh(stage4=72B채점 포함)를 대체. 123B 채점 유닛은 독립 유닛이라 이 스크립트 교체와 무관하게 계속 돈다.
set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain_72b_trainonly.log"
BASE72="./models/base/qwen2.5-72b-instruct"
SHORT_FILE="./data/processed/react_train_123b_short.jsonl"
cd "$REPO" || exit 1; exec >>"$LOG" 2>&1
echo "===== [$(date '+%F %T')] 72B 학습전용 체인 시작 (72B 채점은 두목 지시로 연기) ====="

wait_unit_gone(){ local pat="$1" max="${2:-2400}"; for i in $(seq 1 "$max"); do systemctl --user list-units "$pat" --no-legend 2>/dev/null | grep -q running || return 0; sleep 30; done; return 1; }
gpu_free_ok(){ local b h; b=$(cat /sys/class/drm/card*/device/gpu_busy_percent 2>/dev/null|head -1); h=$(free -g|awk '/Mem:/{print $7}'); echo "[$(date '+%F %T')] GPU busy=${b}% host가용=${h}GB"; [ "${b:-100}" -le 50 ] 2>/dev/null && [ "${h:-0}" -ge 15 ] 2>/dev/null; }

# ── ① 기존 123B 채점 유닛 완료 대기 (새 유닛 발사 안 함) ──
echo "[$(date '+%F %T')] ①123B 채점(gpujob-score-123b-*) 완료 대기 — 전 태스크(medit 포함) 완주까지"
if ! wait_unit_gone 'gpujob-score-123b-*' 5760; then echo "✗ 48h 내 123B 채점 미완 — 중단(코디 확인)"; exit 1; fi
echo "[$(date '+%F %T')] 123B 채점 유닛 종료 감지"; sleep 20

# ── ② 123B score_v2 재채점 (GPU0, 빠름) ──
echo "[$(date '+%F %T')] ②123B score_v2 재채점"
"$PY" scripts/score_v2.py --label 123b-hqq2-seq512 2>&1 | tail -25 || echo "[경고] score_v2 실패(생성물은 보존됨 — 나중 재채점 가능)"
echo "[$(date '+%F %T')] 123B 채점 완료 (v1: eval_results/123b-hqq2-seq512*.json / v2: comms/scores-4060-v2.jsonl)"

# ── ③ 72B Q4 학습: 숏런 → 검증 → 풀 ──
echo "[$(date '+%F %T')] ③72B Q4 학습 준비 — GPU/메모리 회복 확인"; sleep 20
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
  echo "[$(date '+%F %T')] ✗ 72B Q4 숏런 실패(어댑터=$([ -f "$ADPS" ]&&echo Y||echo N) 웨지=$wedge) → 중단."; exit 1
fi
sleep 15
echo "[$(date '+%F %T')] 72B Q4 풀에폭(315샘플, seq1024) 발사"
bash scripts/gpu_job.sh --name train72bq4full --timeout 43200 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE72" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 1024 --epochs 1 \
    --out ./models/qwen-react-lora-72b-hqq-q4
sleep 20; wait_unit_gone 'gpujob-train72bq4full-*' 2880
echo "[$(date '+%F %T')] 72B Q4 풀에폭 종료"

# ── ④ 종료 (72B 채점 없음 — 연기) ──
echo "===== [$(date '+%F %T')] 72B 학습전용 체인 종료. 72B Q4 채점은 다음 사이클(배치디코드)로 연기. ====="
echo "  생성물/어댑터 보존: models/qwen-react-lora-72b-hqq-q4/ · 나중 heldout 채점 or 4060 v2 재점수 가능."