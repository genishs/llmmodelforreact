#!/usr/bin/env bash
# run_141b_highseq_master.sh — 141B(Mixtral-8x22B) HQQ2 어텐션-LoRA **고-seq 재학습** 마스터.
#
# run_141b_master.sh(seq512 3에폭)를 파생. 차이:
#   - SEQ/EPOCHS를 인자로 받는다(프로브 채택값을 넣는다). 기본 768 / 1에폭.
#   - base는 이미 디스크에 있으므로 24h 다운로드 대기는 **빠른 무결성 검증**으로 축약.
#   - 출력은 seq별 새 디렉토리(models/mixtral-8x22b-hqq2-seqNNN) — 기존 어댑터 무접촉.
#   - 검증 → 스왑가드(≥60GiB) → smoke(--smoke 8, 고-seq fwd/bwd 실검증) → 풀학습(--smoke 제거).
#   - 주기저장 25스텝(train_directml SAVE_EVERY) + watchdog(SwapFree<4G/OOM/wedge 하드중단, 진척 보존).
#
# ⚠️ 어텐션-온리(q/k/v/o_proj). --lora-mlp 절대 금지(Mixtral MLP=전문가, 타깃 없음→크래시).
# ⚠️ bitsandbytes 금지(wave 커널 버그). HQQ만. venv=ai_model_mixtral(transformers 4.46.3) 필수.
# ⚠️ 기존 어댑터/base 무접촉. push 금지. base(exfat)는 read-only.
# ⚠️ 사용: bash /home/user/run_141b_highseq_master.sh <SEQ> <EPOCHS>
#          예) bash /home/user/run_141b_highseq_master.sh 768 1
#
# 재발방지: 이 스크립트는 gpu_job.sh(systemd 유닛)로 학습을 발사하고 즉시 반환한다.
#   완료 감시는 systemd/watchdog가 하며, detached nohup sleep 완료폴링은 쓰지 않는다.

set -uo pipefail

SEQ="${1:-768}"
EPOCHS="${2:-1}"
[[ "$SEQ" =~ ^[0-9]+$ ]]    || { echo "✗ SEQ 정수 아님: '$SEQ'"; exit 2; }
[[ "$EPOCHS" =~ ^[0-9]+$ ]] || { echo "✗ EPOCHS 정수 아님: '$EPOCHS'"; exit 2; }

REPO="/mnt/data/Documents/workspace/study/ai_model"
BASE="/run/media/user/새 볼륨/mixtral-8x22b-v0.1"
PY="/home/user/.venvs/ai_model_mixtral/bin/python"
LOG="/home/user/gpu_jobs/logs/run_141b_highseq_master.log"
SWAP_MIN_GIB=60
SHARDS_EXPECTED=59
OUT="./models/mixtral-8x22b-hqq2-seq${SEQ}"
FEAS_OUT="${OUT}-feas"
FULL_TIMEOUT=86400          # 24h 안전상한(의도적 컷 아님; 그 전 종료 예상)
export XDG_RUNTIME_DIR=/run/user/1000
export HF_HUB_ENABLE_HF_TRANSFER=1

mkdir -p /home/user/gpu_jobs/logs
cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] 고-seq 마스터 시작 SEQ=$SEQ EPOCHS=$EPOCHS OUT=$OUT"
[ -x "$PY" ] || { echo "✗ venv python 없음: $PY — 중단"; exit 1; }

shard_count(){ ls "$BASE"/model-*.safetensors 2>/dev/null | wc -l; }
incomplete_count(){ find "$BASE" -name '*.incomplete' 2>/dev/null | wc -l; }

# ---------- 1. base 무결성 빠른 검증(다운로드 완료 전제 — base 존재) ----------
echo "[$(date '+%F %T')] base 무결성 검증…"
sc=$(shard_count); ic=$(incomplete_count)
idx="$BASE/model.safetensors.index.json"
[ -f "$idx" ] || { echo "✗ index 없음: $idx — 중단"; exit 1; }
[ -f "$BASE/config.json" ] || { echo "✗ config 없음 — 중단"; exit 1; }
[ "$ic" -eq 0 ] || { echo "✗ incomplete=$ic — 중단"; exit 1; }
expected=$("$PY" -c "import json;d=json.load(open('$idx'));print(len(set(d['weight_map'].values())))" 2>/dev/null || echo 0)
echo "  샤드 $sc개 (index 기대 ${expected:-?}개) | incomplete 0 | config OK"
if [ "${expected:-0}" -gt 0 ]; then
  [ "$sc" = "$expected" ] || { echo "✗ 샤드 수 불일치($sc vs $expected) — 중단"; exit 1; }
else
  [ "$sc" -ge "$SHARDS_EXPECTED" ] || { echo "✗ 샤드 부족($sc/$SHARDS_EXPECTED) — 중단"; exit 1; }
fi
"$PY" - <<PYEOF || { echo "✗ safetensors 헤더 검증 실패 — 중단"; exit 1; }
import glob, json, struct, os, sys
base = "$BASE"
files = sorted(glob.glob(os.path.join(base, "model-*.safetensors")))
ok = 0; actual = 0
for f in files:
    with open(f, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        json.loads(fh.read(n))
    actual += os.path.getsize(f); ok += 1
idx = json.load(open(os.path.join(base, "model.safetensors.index.json")))
total = idx.get("metadata", {}).get("total_size", 0)
print(f"  safetensors 헤더 OK: {ok}개 | total_size={total/1e9:.1f}GB 실제={actual/1e9:.1f}GB")
if total > 0 and actual < total:
    print("  ✗ 실제 < total_size — 데이터 누락 의심"); sys.exit(1)
sys.exit(0)
PYEOF
echo "[$(date '+%F %T')] ✓ base 검증 통과"

# ---------- 2. 스왑 가드(읽기전용) ----------
swap_now(){ swapon --show=SIZE --bytes --noheadings 2>/dev/null | awk '{s+=$1} END{printf "%.0f", s/1073741824}'; }
swap_gib=$(swap_now); swap_gib=${swap_gib:-0}
echo "[$(date '+%F %T')] 스왑 총량 ${swap_gib}GiB (요구 ≥${SWAP_MIN_GIB}GiB)"
if [ "$swap_gib" -lt "$SWAP_MIN_GIB" ]; then
  echo "[$(date '+%F %T')] ✗ 스왑 부족 → 발사 보류."
  echo "[QUEUE] 두목 조치: sudo swapon /swapfile. 이후 재실행: bash /home/user/run_141b_highseq_master.sh $SEQ $EPOCHS"
  exit 2
fi
echo "[$(date '+%F %T')] ✓ 스왑 가드 통과"

# ---------- 3. host RAM 회복 대기 ----------
sleep 15
echo "[$(date '+%F %T')] host RAM 가용 $(free -g | awk '/Mem:/{print $7}')GB, SwapFree $(free -g | awk '/Swap:/{print $4}')GB"

# ---------- 4. smoke(고-seq 8스텝) 발사 + 종료 대기 ----------
echo "[$(date '+%F %T')] smoke(SEQ=$SEQ, 8스텝) 발사 — 고-seq fwd/bwd 실검증"
bash scripts/gpu_job.sh --name mixtralhsfeas --timeout 14400 --cwd "$REPO" -- \
  "$PY" src/train_directml.py \
    --backend cuda --dtype bf16 \
    --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 \
    --lora-r 16 \
    --grad-ckpt --seq "$SEQ" \
    --epochs 1 --smoke 8 \
    --out "$FEAS_OUT"
setsid nohup bash "$REPO/scripts/mem_watch_until.sh" > /home/user/gpu_jobs/logs/mem_watch_mixtral_hs_smoke.log 2>&1 &

sleep 20
SMOKE_LOG=$(ls -t /home/user/gpu_jobs/logs/gpujob-mixtralhsfeas-*.log 2>/dev/null | head -1)
echo "[$(date '+%F %T')] smoke 로그: $SMOKE_LOG"
for i in $(seq 1 120); do pgrep -f "train_directml.py.*smoke" >/dev/null && break; sleep 5; done   # 등장 대기(로드 ~80분)
for i in $(seq 1 1200); do pgrep -f "train_directml.py.*smoke" >/dev/null || break; sleep 10; done  # 종료 대기(~3.3h)
if pgrep -f "train_directml.py.*smoke" >/dev/null; then
  echo "[$(date '+%F %T')] ✗ smoke 미종료 — 중단"; echo "[QUEUE] smoke 미종료(SEQ=$SEQ)"; exit 1
fi
echo "[$(date '+%F %T')] smoke 종료 감지"; sleep 5

# ---------- 5. smoke 성공 판정 ----------
done8=$(grep -c "스모크 완료" "$SMOKE_LOG" 2>/dev/null); done8=${done8:-0}
step8=$(grep -cE "step 8 \|" "$SMOKE_LOG" 2>/dev/null); step8=${step8:-0}
err=$(grep -icE "Traceback|OutOfMemory|CUDA error|HIP error|hipError|device wedged|Killed|OOM-kill|RuntimeError" "$SMOKE_LOG" 2>/dev/null); err=${err:-0}
badloss=$(grep -oE "loss\(avg[0-9]+\) (nan|inf|-inf)" "$SMOKE_LOG" 2>/dev/null | wc -l); badloss=${badloss:-0}
lastloss=$(grep -oE "loss\(avg[0-9]+\) [0-9.]+" "$SMOKE_LOG" 2>/dev/null | tail -1)
echo "[$(date '+%F %T')] 판정: 완료=$done8 step8=$step8 err=$err badloss=$badloss last='$lastloss'"
if [ "$done8" -lt 1 ] || [ "$step8" -lt 1 ] || [ "$err" -gt 0 ] || [ "$badloss" -gt 0 ]; then
  echo "[$(date '+%F %T')] ✗ smoke 실패 → 풀학습 금지."
  echo "[QUEUE] smoke 실패(SEQ=$SEQ 완료=$done8 step8=$step8 err=$err badloss=$badloss). 로그: $SMOKE_LOG"
  exit 2
fi
echo "[$(date '+%F %T')] ✓ smoke 성공"

# ---------- 6. host RAM 회복 후 풀학습 발사 ----------
sleep 15
echo "[$(date '+%F %T')] host RAM 가용 $(free -g | awk '/Mem:/{print $7}')GB, SwapFree $(free -g | awk '/Swap:/{print $4}')GB"
echo "[$(date '+%F %T')] 풀학습 발사 SEQ=$SEQ EPOCHS=$EPOCHS OUT=$OUT (--smoke 제거, 주기저장 25step)"
bash scripts/gpu_job.sh --name mixtralhsfull --timeout "$FULL_TIMEOUT" --cwd "$REPO" -- \
  "$PY" src/train_directml.py \
    --backend cuda --dtype bf16 \
    --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 \
    --lora-r 16 \
    --grad-ckpt --seq "$SEQ" \
    --epochs "$EPOCHS" \
    --out "$OUT"

# ---------- 7. 계측 + watchdog 분리(GUI-off/세션사망 생존) ----------
setsid nohup bash "$REPO/scripts/mem_watch_until.sh" > /home/user/gpu_jobs/logs/mem_watch_mixtral_hs_full.log 2>&1 &
echo "[$(date '+%F %T')] 계측 분리 → mem_watch_mixtral_hs_full.log"
setsid nohup bash "$REPO/scripts/mixtral_safety_watch.sh" "gpujob-mixtralhsfull-*" 4 >/dev/null 2>&1 &
echo "[$(date '+%F %T')] watchdog 분리(SwapFree<4G 또는 OOM/wedge 시 하드중단, 진척=주기저장 보존)"
echo "[$(date '+%F %T')] ✓ 마스터 완료 — 풀학습은 mixtralhsfull 유닛 진행. 채점/push는 두목 지시 대기."
