#!/usr/bin/env bash
# chain_123b.sh — Mistral-123B 다운로드 완료를 기다렸다가 검증하고 HQQ 2bit seq512 학습을 발사한다.
#
# WHY: 123B는 seq512 단독이라야 통합메모리(54GB, 마진6)에 들어간다. 다운로드(캐시~15GB)와
#      동시 학습은 60GB 풀을 넘겨 프리징한다(2026-07-17 새벽 실측). → 다운로드 완료 후에만 학습.
# 두목 "123B seq512 고고싱" 승인(2026-07-17 아침).

set -uo pipefail
REPO="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
BASE="./models/base/mistral-large-2411"
PY="/home/user/.venvs/ai_model_rocm/bin/python"
LOG="/home/user/gpu_jobs/logs/chain123b.log"
DL_UNIT="dlmistral3.service"

cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] 123B 체인 시작"

# ---------- 1. Mistral 다운로드 완료 대기 (최대 2시간) ----------
echo "[$(date '+%F %T')] Mistral 다운로드 완료 대기…"
for i in $(seq 1 720); do   # 720*10s = 2h
  active=$(systemctl --user is-active "$DL_UNIT" 2>/dev/null)
  result=$(systemctl --user show "$DL_UNIT" -p Result --value 2>/dev/null)
  incomplete=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
  # 완료 = 유닛이 success로 종료 AND incomplete 0 (수동 stop/실패는 success 아님 → 오발사 방지)
  if [ "$active" != "active" ] && [ "$result" = "success" ] && [ "$incomplete" -eq 0 ]; then break; fi
  sleep 10
done
active=$(systemctl --user is-active "$DL_UNIT" 2>/dev/null)
incomplete=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
if [ "$active" = "active" ] || [ "$incomplete" -ne 0 ]; then
  echo "[$(date '+%F %T')] ✗ 중단: 2시간 내 다운로드 미완(active=$active, incomplete=$incomplete)"; exit 1
fi
echo "[$(date '+%F %T')] 다운로드 완료 (결과=$(systemctl --user show "$DL_UNIT" -p Result --value 2>/dev/null))"

# ---------- 2. 무결성 검증 ----------
echo "[$(date '+%F %T')] 검증…"
shards=$(ls "$BASE"/model-*.safetensors 2>/dev/null | wc -l)
idx="$BASE/model.safetensors.index.json"
expected=$("$PY" -c "import json;d=json.load(open('$idx'));print(len(set(d['weight_map'].values())))" 2>/dev/null || echo 0)
echo "  샤드 $shards개 (index 기대 $expected개) | incomplete 0 | config $([ -f "$BASE/config.json" ] && echo OK || echo MISSING)"
if [ "$expected" -gt 0 ]; then [ "$shards" = "$expected" ] || { echo "✗ 샤드 수 불일치($shards vs $expected) — 중단"; exit 1; }; else echo "  (index 기대치 파싱 실패 — incomplete 0 신뢰)"; [ "$shards" -gt 30 ] || { echo "✗ 샤드 너무 적음($shards) — 중단"; exit 1; }; fi
[ -f "$BASE/config.json" ] || { echo "✗ config 없음 — 중단"; exit 1; }
# safetensors 헤더 파싱 (조용한 손상 탐지)
"$PY" - <<PYEOF || { echo "✗ safetensors 무결성 실패 — 중단"; exit 1; }
import glob,json,struct,sys
ok=0
for f in sorted(glob.glob("$BASE/model-*.safetensors")):
    with open(f,"rb") as fh:
        n=struct.unpack("<Q",fh.read(8))[0]; json.loads(fh.read(n))
    ok+=1
print(f"  safetensors 헤더 OK: {ok}개"); sys.exit(0)
PYEOF
echo "[$(date '+%F %T')] ✓ 검증 통과"

# ---------- 3. host RAM 회복 대기 (다운로드 캐시 반환) ----------
sleep 15
echo "[$(date '+%F %T')] host RAM 가용: $(free -g | awk '/Mem:/{print $7}')GB"

# ---------- 4. 123B seq512 학습 발사 ----------
echo "[$(date '+%F %T')] 123B HQQ 2bit seq512 본런 발사"
bash scripts/gpu_job.sh --name train123b --timeout 43200 -- \
  "$PY" src/train_directml.py \
    --backend cuda --dtype bf16 \
    --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 \
    --lora-r 16 --lora-mlp \
    --grad-ckpt --seq 512 \
    --epochs 1 \
    --out ./models/qwen-react-lora-123b-hqq
echo "[$(date '+%F %T')] 체인 완료 — 123B 본런은 별도 유닛에서 진행 중"
