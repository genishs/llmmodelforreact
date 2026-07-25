#!/usr/bin/env bash
# chain_72b_q4.sh — 123B 풀런 완주를 기다렸다가 GPU가 비면 72B Q4(4bit) seq1024를 2단계(숏런→풀에폭)로 자동 학습.
#
# WHY 이어받기: 단일 GPU·통합메모리(60GB)라 123B(GTT48+스왑)와 72B Q4(44GB)를 동시에 못 올린다(프리징).
#              그래서 123B 유닛이 inactive 될 때까지 대기 후에만 발사.
# WHY Q4 seq1024: 기존 72B는 Q2 seq1024 풀에폭(val_loss 0.796). 같은 seq로 4bit를 돌려 2bit와 품질 비교.
# WHY 숏런 먼저: Q4(44.4GB)는 Q2(28GB)보다 무거워 seq1024 메모리 여유가 얇다 → 80샘플로 먼저 확인 후 풀에폭.
# 두목 "빈 시간에 72b 4비트 도전" 승인(2026-07-17 낮, 자리비움 ~22시).
set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
BASE="./models/base/qwen2.5-72b-instruct"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain72bq4.log"
WAIT_UNIT="gpujob-train123bfull-20260717-122446-555987.service"  # 이 유닛이 끝나면 GPU가 빈다
SHORT_FILE="./data/processed/react_train_123b_short.jsonl"        # 80샘플(모델무관, 재사용)
cd "$REPO" || exit 1; exec >>"$LOG" 2>&1
echo "===== [$(date '+%F %T')] 72B Q4 체인 시작 (123B 완주 대기) ====="

# ---------- 1. 123B 풀런 완주 대기 (최대 10h) ----------
for i in $(seq 1 2400); do   # 2400*15s = 10h
  systemctl --user is-active "$WAIT_UNIT" >/dev/null 2>&1 || break
  sleep 15
done
res123=$(systemctl --user show "$WAIT_UNIT" -p Result --value 2>/dev/null)
echo "[$(date '+%F %T')] 123B 유닛 종료 감지 (result=$res123)"
sleep 30   # GPU/메모리 반환 대기

# ---------- 2. GPU 건강 + 메모리 회복 확인 ----------
busy=$(cat /sys/class/drm/card*/device/gpu_busy_percent 2>/dev/null | head -1)
freeg=$(free -g | awk '/Mem:/{print $7}')
echo "[$(date '+%F %T')] GPU busy=${busy}% | host 가용 ${freeg}GB (양자화 시작에 ~28GB 필요)"
if [ "${busy:-100}" -gt 50 ] 2>/dev/null; then echo "✗ GPU 아직 바쁨(${busy}%) — 이전 런 잔류? 중단"; exit 1; fi
if [ "${freeg:-0}" -lt 20 ] 2>/dev/null; then echo "✗ host RAM 회복 부족(${freeg}GB) — 프리징 위험, 중단"; exit 1; fi
[ -f "$BASE/config.json" ] || { echo "✗ 72B 모델 없음($BASE) — 중단"; exit 1; }

# ---------- 3. 72B Q4 숏런 (80샘플~10스텝, seq1024) ----------
echo "[$(date '+%F %T')] ★단계1: 72B Q4 숏런(80샘플, seq1024) 발사"
bash scripts/gpu_job.sh --name train72bq4short --timeout 21600 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 1024 --epochs 1 \
    --train-file "$SHORT_FILE" \
    --out ./models/qwen-react-lora-72b-q4-short
sleep 20
su=$(systemctl --user list-units 'gpujob-train72bq4short-*' --no-legend 2>/dev/null|awk '{print $1}'|head -1)
echo "[$(date '+%F %T')] 숏런 유닛=$su, 완료 대기…"
for i in $(seq 1 1440); do systemctl --user is-active "$su" >/dev/null 2>&1 || break; sleep 15; done

# ---------- 4. 숏런 성공 확인 (버그수정: grep -c 는 0건에 exit1+"0"출력 → ||echo 금지) ----------
ADP="models/qwen-react-lora-72b-q4-short/adapter_model.safetensors"
slog=$(ls -t ~/gpu_jobs/logs/gpujob-train72bq4short-*.log 2>/dev/null|head -1)
wedge=$(grep -icE "hipError|unspecified launch|device wedged" "$slog" 2>/dev/null); wedge=${wedge:-0}
if [ -f "$ADP" ] && [ "$(stat -c %s "$ADP" 2>/dev/null||echo 0)" -gt 10000000 ] && [ "$wedge" -eq 0 ]; then
  echo "[$(date '+%F %T')] ✅ 72B Q4 숏런 성공: 어댑터 $(( $(stat -c %s "$ADP")/1024/1024 ))MB, 웨지 0 → ★단계2 풀에폭"
else
  echo "[$(date '+%F %T')] ✗ 72B Q4 숏런 실패(어댑터=$([ -f "$ADP" ]&&echo Y||echo N) 웨지=$wedge) → 풀에폭 안 감. 코디 확인."; exit 1
fi
sleep 15
echo "[$(date '+%F %T')] host 가용 $(free -g|awk '/Mem:/{print $7}')GB"

# ---------- 5. 72B Q4 풀에폭 (315샘플, seq1024) — 기존 Q2 어댑터 보존(별도 -q4 디렉토리) ----------
echo "[$(date '+%F %T')] ★단계2: 72B Q4 풀 1에폭(315샘플~39스텝, seq1024) 발사"
bash scripts/gpu_job.sh --name train72bq4full --timeout 43200 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE" \
    --quant hqq --hqq-nbits 4 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 1024 --epochs 1 \
    --out ./models/qwen-react-lora-72b-hqq-q4
echo "[$(date '+%F %T')] 72B Q4 체인 완료 — 풀에폭 별도 유닛 진행 중"
