#!/usr/bin/env bash
# probe_141b_maxseq.sh — 최대 seq 프로브를 gpu_job.sh(웨지-세이프 systemd 유닛)로 발사.
#
# ⚠️ 이 런처는 피선생(메인세션)이 GPU가 빈 뒤 실행한다(서브에이전트 발사 게이트).
# ⚠️ base 로드가 ~69분 → probe는 한 번만 로드하고 in-process로 seq 스윕(재기동 없음).
#   timeout 3h(10800s)는 로드(≤80분)+스윕(≤40분) 여유. gpu_job가 RuntimeMaxSec로 하드상한.
# ⚠️ venv는 ai_model_mixtral(transformers 4.46.3) 필수. 5.13.1은 HQQ 로더 깨짐.
set -uo pipefail

REPO="/mnt/data/Documents/workspace/study/ai_model"
BASE="/run/media/user/새 볼륨/mixtral-8x22b-v0.1"
PY="/home/user/.venvs/ai_model_mixtral/bin/python"
LIMIT_GIB="${1:-54}"                      # GTT 한계(cap 56 - 2 마진)
SEQS="${2:-512,640,768,896,1024,1152,1280}"

export XDG_RUNTIME_DIR=/run/user/1000
cd "$REPO" || exit 1

# GPU 점유 사전 확인(72B 채점이 끝났는지) — gtt_used가 높으면 경고만 하고 진행은 사람 판단.
gtt=$(awk '{printf "%.1f", $1/1073741824}' /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null || echo "?")
echo "[probe] 현재 GTT 사용 ${gtt}GiB (다른 GPU 작업이 있으면 프로브 전에 비워야 정확)"
echo "[probe] base=$BASE"
echo "[probe] venv=$PY"
[ -x "$PY" ] || { echo "[probe] ✗ venv python 없음: $PY"; exit 1; }
[ -f "$BASE/model.safetensors.index.json" ] || { echo "[probe] ✗ base index 없음: $BASE"; exit 1; }

bash scripts/gpu_job.sh --name mixtralprobe --timeout 10800 --cwd "$REPO" -- \
  "$PY" scripts/probe_141b_maxseq.py \
    --base "$BASE" \
    --limit-gib "$LIMIT_GIB" \
    --seqs "$SEQS" \
    --hqq-nbits 2 --hqq-group-size 64 --lora-r 16

echo "[probe] 발사 완료. 로그: scripts/gpu_job.sh --logs mixtralprobe"
echo "[probe] 판정('✅ 채택 최대 seq') 확인 후 → bash /home/user/run_141b_highseq_master.sh <seq> <epochs>"
