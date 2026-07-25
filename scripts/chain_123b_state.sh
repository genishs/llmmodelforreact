#!/usr/bin/env bash
# chain_123b_state.sh — 다운로드 "상태"(유닛명 무관)로 완료 판정 → 검증 → 123B seq512 발사.
# 완료 판정 = incomplete 0 AND index.json 존재 AND 샤드수==index 기대 (셋 다여야 = 진짜 완료).
# 재시작으로 유닛명이 바뀌어도 안 꼬인다.
set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
BASE="./models/base/mistral-large-2411"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain123b.log"
cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "===== [$(date '+%F %T')] 123B 상태기반 체인 시작 ====="
idx="$BASE/model.safetensors.index.json"
for i in $(seq 1 1080); do   # 3h
  inc=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
  sh=$(ls "$BASE"/model-*.safetensors 2>/dev/null | wc -l)
  exp=$("$PY" -c "import json;print(len(set(json.load(open('$idx'))['weight_map'].values())))" 2>/dev/null || echo 0)
  if [ "$inc" -eq 0 ] && [ -f "$idx" ] && [ "$exp" -gt 0 ] && [ "$sh" -eq "$exp" ]; then
    echo "[$(date '+%F %T')] 완료 감지: 샤드 $sh/$exp, incomplete 0"; break
  fi
  sleep 15
done
inc=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
sh=$(ls "$BASE"/model-*.safetensors 2>/dev/null | wc -l)
exp=$("$PY" -c "import json;print(len(set(json.load(open('$idx'))['weight_map'].values())))" 2>/dev/null || echo 0)
[ "$inc" -eq 0 ] && [ "$exp" -gt 0 ] && [ "$sh" -eq "$exp" ] || { echo "[$(date '+%F %T')] ✗ 3h내 미완(inc=$inc sh=$sh exp=$exp) 중단"; exit 1; }
# safetensors 헤더 파싱
"$PY" - <<PY || { echo "✗ 헤더 무결성 실패"; exit 1; }
import glob,json,struct,sys
for f in sorted(glob.glob("$BASE/model-*.safetensors")):
    fh=open(f,"rb"); n=struct.unpack("<Q",fh.read(8))[0]; json.loads(fh.read(n)); fh.close()
print("헤더 OK")
PY
[ -f "$BASE/config.json" ] || { echo "✗ config 없음"; exit 1; }
echo "[$(date '+%F %T')] ✓ 검증 통과 → host RAM $(free -g|awk '/Mem:/{print $7}')GB"
sleep 15
echo "[$(date '+%F %T')] 123B ★짧은런(80샘플~10스텝) 발사 — 성공시 코디가 풀에폭 이어감"
bash scripts/gpu_job.sh --name train123bshort --timeout 21600 -- \
  "$PY" src/train_directml.py --backend cuda --dtype bf16 --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 512 --epochs 1 \
    --train-file ./data/processed/react_train_123b_short.jsonl \
    --out ./models/qwen-react-lora-123b-hqq-short
echo "[$(date '+%F %T')] 체인 완료"
