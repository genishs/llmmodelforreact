#!/usr/bin/env bash
# chain_123b_2stage.sh — 다운로드완료 → 검증 → ①짧은런(80샘플~10스텝) → 성공확인 → ②풀에폭 자동.
# 두목 "성공하면 바로 다음으로" 사전승인(2026-07-17). 무인 자동 진행.
set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
BASE="./models/base/mistral-large-2411"; PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain123b.log"
cd "$REPO" || exit 1; exec >>"$LOG" 2>&1
echo "===== [$(date '+%F %T')] 123B 2단계 자동체인 시작 ====="
idx="$BASE/model.safetensors.index.json"

# --- 1. 다운로드 완료 대기 (상태기반, 3h) ---
for i in $(seq 1 1080); do
  inc=$(find "$BASE" -name "*.incomplete" 2>/dev/null|wc -l); sh=$(ls "$BASE"/model-*.safetensors 2>/dev/null|wc -l)
  exp=$("$PY" -c "import json;print(len(set(json.load(open('$idx'))['weight_map'].values())))" 2>/dev/null||echo 0)
  [ "$inc" -eq 0 ] && [ -f "$idx" ] && [ "$exp" -gt 0 ] && [ "$sh" -eq "$exp" ] && { echo "[$(date '+%F %T')] 다운로드 완료: 샤드 $sh/$exp"; break; }
  sleep 15
done
inc=$(find "$BASE" -name "*.incomplete" 2>/dev/null|wc -l); sh=$(ls "$BASE"/model-*.safetensors 2>/dev/null|wc -l)
exp=$("$PY" -c "import json;print(len(set(json.load(open('$idx'))['weight_map'].values())))" 2>/dev/null||echo 0)
[ "$inc" -eq 0 ] && [ "$exp" -gt 0 ] && [ "$sh" -eq "$exp" ] || { echo "✗ 다운로드 미완(inc=$inc sh=$sh exp=$exp)"; exit 1; }
"$PY" - <<PY || { echo "✗ 헤더 무결성 실패"; exit 1; }
import glob,json,struct
for f in sorted(glob.glob("$BASE/model-*.safetensors")):
    fh=open(f,"rb");n=struct.unpack("<Q",fh.read(8))[0];json.loads(fh.read(n));fh.close()
print("헤더 OK")
PY
[ -f "$BASE/config.json" ] || { echo "✗ config 없음"; exit 1; }
echo "[$(date '+%F %T')] ✓ 검증 통과 (host RAM $(free -g|awk '/Mem:/{print $7}')GB)"; sleep 15

# --- 2. 짧은런 발사 + 완료 대기 ---
echo "[$(date '+%F %T')] ★단계1: 짧은런(80샘플~10스텝, seq512) 발사"
bash scripts/gpu_job.sh --name train123bshort --timeout 21600 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 512 --epochs 1 \
    --train-file ./data/processed/react_train_123b_short.jsonl \
    --out ./models/qwen-react-lora-123b-hqq-short
sleep 20
su=$(systemctl --user list-units 'gpujob-train123bshort-*' --no-legend 2>/dev/null|awk '{print $1}'|head -1)
echo "[$(date '+%F %T')] 짧은런 유닛=$su, 완료 대기…"
for i in $(seq 1 720); do systemctl --user is-active "$su" >/dev/null 2>&1 || break; sleep 15; done

# --- 3. 짧은런 성공 확인 ---
ADP="models/qwen-react-lora-123b-hqq-short/adapter_model.safetensors"
slog=$(ls -t ~/gpu_jobs/logs/gpujob-train123bshort-*.log 2>/dev/null|head -1)
wedge=$(grep -icE "hipError|unspecified launch|device wedged" "$slog" 2>/dev/null); wedge=${wedge:-0}
# WHY: grep -c는 0건일 때 "0"을 찍으며 exit 1 → 기존 `||echo 0`이 "0"을 덧붙여 "0\n0" → 정수비교 붕괴(2026-07-17 숏런 후 오판). ||echo 제거로 수정.
if [ -f "$ADP" ] && [ "$(stat -c %s "$ADP" 2>/dev/null||echo 0)" -gt 10000000 ] && [ "$wedge" -eq 0 ]; then
  echo "[$(date '+%F %T')] ✅ 짧은런 성공: 어댑터 $(( $(stat -c %s "$ADP")/1024/1024 ))MB, 웨지 0 → ★단계2 풀에폭 발사"
else
  echo "[$(date '+%F %T')] ✗ 짧은런 실패(어댑터=$([ -f "$ADP" ]&&echo Y||echo N) 웨지=$wedge) → 풀에폭 안 감. 코디 확인 필요."; exit 1
fi
sleep 10

# --- 4. 풀에폭 자동 발사 (전체 데이터) ---
echo "[$(date '+%F %T')] ★단계2: 풀 1에폭(315샘플~39스텝, seq512) 발사"
bash scripts/gpu_job.sh --name train123bfull --timeout 43200 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 512 --epochs 1 \
    --out ./models/qwen-react-lora-123b-hqq
echo "[$(date '+%F %T')] 2단계 체인 완료 — 풀에폭 별도 유닛 진행 중"
