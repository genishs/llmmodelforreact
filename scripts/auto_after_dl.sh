#!/usr/bin/env bash
# 오토모드: 14B 다운로드 완료 감지 → 즉시 probe_14b_load.py 자동 실행.
# 완료 판정: dl_14b.log의 "ALL DONE" 마커(권위) 우선, 보조로 .incomplete 0개.
# probe 결과 → logs/probe_14b.log. 사용자 지시(2026-06-27): 자동/오토모드 바로 시작.
set -u
cd /c/Users/user/Documents/workspace/study/ai_model || exit 1
PY=./venv/Scripts/python.exe
DLOG=logs/dl_14b.log
PLOG=logs/probe_14b.log
BLOBS="$HOME/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-14B-Instruct/blobs"

echo "[auto] $(date) 다운로드 완료 감시 시작" | tee -a "$PLOG"
while true; do
  if grep -q "ALL DONE" "$DLOG" 2>/dev/null; then
    echo "[auto] $(date) ALL DONE 마커 감지 → probe 시작" | tee -a "$PLOG"; break
  fi
  inc=$(ls "$BLOBS"/*.incomplete 2>/dev/null | wc -l)
  shards=$(ls "$BLOBS" 2>/dev/null | wc -l)
  # 보조 판정: incomplete 0 + blob이 충분히(>=10) 존재 = 사실상 완료
  if [ "$inc" = "0" ] && [ "$shards" -ge 10 ]; then
    echo "[auto] $(date) incomplete=0, blobs=$shards → 완료로 판단, probe 시작" | tee -a "$PLOG"; break
  fi
  sleep 30
done

echo "[auto] $(date) probe_14b_load.py 실행" | tee -a "$PLOG"
"$PY" scripts/probe_14b_load.py 2>&1 | tee -a "$PLOG"
rc=${PIPESTATUS[0]}
echo "[auto] $(date) probe 종료 (exit=$rc)" | tee -a "$PLOG"
