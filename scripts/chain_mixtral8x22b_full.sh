#!/usr/bin/env bash
# chain_mixtral8x22b_full.sh — smoke 성공 시 141B "풀 학습"으로 자동 이어가는 무인 체인.
#
# 두목 범위확대: 가능성(smoke) 확인되면 실제 학습까지. 두목 05:00 복귀 수동중단 → 그때까지 죽지 말 것.
# 흐름: smoke 종료 대기 → 성공 판정 → (성공) 풀 학습 발사 + 계측 + watchdog / (실패) 발사 금지·큐잉.
# ⚠️ smoke와 동일 설정(hqq 2bit gs64, lora-r16 어텐션-온리, grad-ckpt seq512), --smoke만 제거.
#    --lora-mlp 절대 금지. venv=격리 ai_model_mixtral(transformers 4.46.3).

set -uo pipefail
REPO="/mnt/data/Documents/workspace/study/ai_model"
BASE="/run/media/user/새 볼륨/mixtral-8x22b-v0.1"
PY="/home/user/.venvs/ai_model_mixtral/bin/python"
LOG="/home/user/gpu_jobs/logs/chain_mixtral_full.log"
OUT="./models/mixtral-8x22b-hqq2-full"
cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] 풀학습 자동체인 시작"

# ---------- 0. 현재 smoke 로그 고정 ----------
SMOKE_LOG=$(ls -t /home/user/gpu_jobs/logs/gpujob-mixtralfeas-*.log 2>/dev/null | head -1)
echo "[$(date '+%F %T')] smoke 로그: $SMOKE_LOG"

# ---------- 1. smoke 종료 대기(최대 3h) ----------
for i in $(seq 1 1080); do
  pgrep -f "train_directml.py.*smoke" >/dev/null || break
  sleep 10
done
if pgrep -f "train_directml.py.*smoke" >/dev/null; then
  echo "[$(date '+%F %T')] ✗ smoke 3h 내 미종료 — 중단"; exit 1
fi
echo "[$(date '+%F %T')] smoke 종료 감지"
sleep 5

# ---------- 2. smoke 성공 판정 ----------
done8=$(grep -c "스모크 완료" "$SMOKE_LOG" 2>/dev/null); done8=${done8:-0}
step8=$(grep -cE "step 8 \|" "$SMOKE_LOG" 2>/dev/null); step8=${step8:-0}
err=$(grep -icE "Traceback|OutOfMemory|CUDA error|HIP error|hipError|device wedged|Killed|OOM-kill|RuntimeError" "$SMOKE_LOG" 2>/dev/null); err=${err:-0}
badloss=$(grep -oE "loss\(avg[0-9]+\) (nan|inf|-inf)" "$SMOKE_LOG" 2>/dev/null | wc -l); badloss=${badloss:-0}
lastloss=$(grep -oE "loss\(avg[0-9]+\) [0-9.]+" "$SMOKE_LOG" 2>/dev/null | tail -1)
echo "[$(date '+%F %T')] 판정: 스모크완료=$done8 step8=$step8 err=$err badloss=$badloss last='$lastloss'"
if [ "$done8" -lt 1 ] || [ "$step8" -lt 1 ] || [ "$err" -gt 0 ] || [ "$badloss" -gt 0 ]; then
  echo "[$(date '+%F %T')] ✗ smoke 실패 판정 → 풀학습 발사 금지."
  echo "[QUEUE] smoke 실패(완료=$done8 step8=$step8 err=$err badloss=$badloss). 로그: $SMOKE_LOG. 원인 진단 필요."
  exit 2
fi
echo "[$(date '+%F %T')] ✓ smoke 성공 판정"

# ---------- 3. 에폭 동적 계산(05:00까지 채우기; 최소3 최대20) ----------
avg=$(grep -oE "평균 [0-9.]+s/step" "$SMOKE_LOG" 2>/dev/null | tail -1 | grep -oE "[0-9.]+")
avg=${avg:-60}
target=$(date -d "05:00" +%s); now=$(date +%s)
[ "$target" -le "$now" ] && target=$(date -d "tomorrow 05:00" +%s)
remain=$(( target - now ))
# 에폭당 39 optim_step(315샘플/accum8). 안전마진 위해 remain의 90%만 사용.
steps_possible=$(awk -v r="$remain" -v a="$avg" 'BEGIN{printf "%d", (r*0.9)/a}')
EPOCHS=$(awk -v s="$steps_possible" 'BEGIN{e=int(s/39); if(e<3)e=3; if(e>20)e=20; print e}')
echo "[$(date '+%F %T')] avg=${avg}s/step remain=$((remain/60))min steps~=$steps_possible → EPOCHS=$EPOCHS"

# ---------- 4. host RAM 회복 대기 ----------
sleep 15
echo "[$(date '+%F %T')] host RAM 가용 $(free -g | awk '/Mem:/{print $7}')GB, SwapFree $(free -g | awk '/Swap:/{print $4}')GB"

# ---------- 5. 141B 풀학습 발사(detached --user 유닛, 타임아웃 넉넉=두목 수동중단) ----------
echo "[$(date '+%F %T')] 141B 풀학습 발사 EPOCHS=$EPOCHS OUT=$OUT"
bash scripts/gpu_job.sh --name mixtralfull --timeout 43200 --cwd "$REPO" -- \
  "$PY" src/train_directml.py \
    --backend cuda --dtype bf16 \
    --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 \
    --lora-r 16 \
    --grad-ckpt --seq 512 \
    --epochs "$EPOCHS" \
    --out "$OUT"

# ---------- 6. 계측 + watchdog 분리(GUI-off/세션사망 생존) ----------
setsid nohup bash "$REPO/scripts/mem_watch_until.sh" > /home/user/gpu_jobs/logs/mem_watch_mixtral_full.log 2>&1 &
echo "[$(date '+%F %T')] 계측 분리 시작 → mem_watch_mixtral_full.log"
setsid nohup bash "$REPO/scripts/mixtral_safety_watch.sh" "gpujob-mixtralfull-*" 4 >/dev/null 2>&1 &
echo "[$(date '+%F %T')] watchdog 분리 시작(SwapFree<4G 또는 OOM/wedge 시 하드중단)"
echo "[$(date '+%F %T')] 풀학습 체인 완료 — 학습은 mixtralfull 유닛에서 진행. 주기저장 25step, 05:00 수동중단 대비."
