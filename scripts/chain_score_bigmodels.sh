#!/usr/bin/env bash
# chain_score_bigmodels.sh — 모든 학습(123B 풀 → 72B Q4 숏런/풀) 완료 후, 123B·72B Q4 어댑터를 순차 채점.
#
# WHY 순차: 단일 GPU. 학습이 GPU를 놓을 때까지(=72B Q4 풀 어댑터 생성 or 학습파이프라인 종료) 대기 후 채점.
# WHY 채점=학습보다 느림: 메모리대역폭 병목·batch=1 디코드. 123B(Q2)~14h, 72B(Q4)~16h 예상. 두목 "양쪽 다 풀채점" 승인(2026-07-17).
# 각 모델: ①eval_hard_tsc(GPU 생성+tsc v1채점, 캐논 --heldout --max-new 4096 --quant hqq) → ②score_v2(GPU0 재채점, 진짜 점수).
# 학습과 절대 안 겹침(겹치면 프리징). 실패한 학습은 어댑터 부재로 건너뜀(헛채점 방지).
set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain_score_big.log"
A123="./models/qwen-react-lora-123b-hqq/adapter_model.safetensors"
A72Q4="./models/qwen-react-lora-72b-hqq-q4/adapter_model.safetensors"
cd "$REPO" || exit 1; exec >>"$LOG" 2>&1
echo "===== [$(date '+%F %T')] 대형모델 채점 체인 시작 (학습 완료 대기) ====="

# ---------- 1. 모든 학습 종료 대기 (최대 16h) ----------
# 종료신호 = 72B Q4 풀 어댑터 생성(정상완주) OR 학습유닛이 3회연속 부재(파이프라인 종료; 숏런→풀 사이 <60s 갭 오탐 방지)
idle=0
for i in $(seq 1 960); do   # 960*60s = 16h
  [ -f "$A72Q4" ] && { echo "[$(date '+%F %T')] 72B Q4 풀 어댑터 감지 → 전체 학습 완료로 판단"; break; }
  if systemctl --user list-units 'gpujob-train*-*' --no-legend 2>/dev/null | grep -q running; then idle=0; else idle=$((idle+1)); fi
  # 10회(10분) 연속 부재라야 종료 판정 — 단계전환 공백(123B끝→72B시작 ~45s, 숏런→풀 ~35s)에 오판해 72B와 GPU 충돌하는 것 방지.
  [ "$idle" -ge 10 ] && { echo "[$(date '+%F %T')] 학습유닛 10분연속 부재 → 파이프라인 종료(72B 미완일 수 있음). 있는 어댑터만 채점."; break; }
  sleep 60
done
sleep 30   # GPU/메모리 반환 여유
busy=$(cat /sys/class/drm/card*/device/gpu_busy_percent 2>/dev/null | head -1)
echo "[$(date '+%F %T')] 학습 종료 확인. GPU busy=${busy}% | host 가용 $(free -g|awk '/Mem:/{print $7}')GB"

# ---------- 채점 함수 ----------
score_one() {  # $1=라벨 $2=어댑터경로(.safetensors) $3=어댑터디렉토리 $4=base $5=nbits
  local label="$1" adp="$2" adpdir="$3" base="$4" nbits="$5"
  if [ ! -f "$adp" ] || [ "$(stat -c %s "$adp" 2>/dev/null||echo 0)" -lt 10000000 ]; then
    echo "[$(date '+%F %T')] ⏭ $label: 어댑터 없음/비정상($adp) → 학습 실패로 보고 채점 건너뜀"; return 1
  fi
  echo "[$(date '+%F %T')] ▶ $label 채점 발사 (eval_hard_tsc, hqq ${nbits}bit, mn4096) — GPU 생성, 오래 걸림"
  bash scripts/gpu_job.sh --name "score-$label" --timeout 64800 -- \
    "$PY" scripts/eval_hard_tsc.py \
      --adapter "$adpdir" --base "$base" --label "$label" \
      --quant hqq --hqq-nbits "$nbits" --hqq-group-size 64 \
      --heldout --max-new 4096
  sleep 20
  local su
  su=$(systemctl --user list-units "gpujob-score-$label-*" --no-legend 2>/dev/null|awk '{print $1}'|head -1)
  echo "[$(date '+%F %T')] $label 채점 유닛=$su, 완료 대기…"
  for j in $(seq 1 1200); do systemctl --user is-active "$su" >/dev/null 2>&1 || break; sleep 60; done  # 최대 20h
  # v2 재채점 (GPU 0, 빠름)
  echo "[$(date '+%F %T')] $label → score_v2 재채점 (GPU0)"
  "$PY" scripts/score_v2.py --label "$label" 2>&1 | tail -20
  echo "[$(date '+%F %T')] ✅ $label 채점 완료 (v1: eval_results/${label}*.json / v2: comms/scores-4060-v2.jsonl)"
}

# ---------- 2. 123B 먼저 (Q2 2bit) ----------
score_one "123b-hqq2-seq512" "$A123" "./models/qwen-react-lora-123b-hqq" "./models/base/mistral-large-2411" 2

# ---------- 3. 72B Q4 다음 (4bit) ----------
score_one "72bq4-hqq4-seq1024" "$A72Q4" "./models/qwen-react-lora-72b-hqq-q4" "./models/base/qwen2.5-72b-instruct" 4

echo "===== [$(date '+%F %T')] 대형모델 채점 체인 종료 ====="