#!/usr/bin/env bash
# mem_watch_until.sh — 학습(train_directml) 생존 동안 GTT/VRAM/스왑 피크 계측, 종료 시 PEAK 출력.
#
# ⚠️ C2 불변식: 순수 관찰(read-only /sys + free). 도는 학습에 절대 간섭 안 함.
# GUI-off(multi-user.target)에도 살아남게 체인이 setsid nohup 파일로그로 띄운다.
# 학습 프로세스(train_directml.py)가 사라지면 스스로 종료 → 피크를 로그 마지막 줄에 남긴다.
GTT=/sys/class/drm/card1/device/mem_info_gtt_used
VRAM=/sys/class/drm/card1/device/mem_info_vram_used
gib() { awk -v b="$1" 'BEGIN{printf "%.1f", b/1073741824}'; }
peak_gtt=0; peak_vram=0
# 학습 프로세스 등장 대기(최대 10분: 스트리밍 양자화 로드가 오래 걸릴 수 있음)
for i in $(seq 1 120); do pgrep -f "train_directml.py" >/dev/null && break; sleep 5; done
if ! pgrep -f "train_directml.py" >/dev/null; then echo "$(date +%T) train_directml 미등장 — 계측 종료"; exit 0; fi
echo "$(date +%T) 계측 시작(train_directml 감지)"
while pgrep -f "train_directml.py" >/dev/null; do
  g=$(cat "$GTT" 2>/dev/null || echo 0); v=$(cat "$VRAM" 2>/dev/null || echo 0)
  [ "$g" -gt "$peak_gtt" ] && peak_gtt=$g
  [ "$v" -gt "$peak_vram" ] && peak_vram=$v
  read -r mf sf < <(free -g | awk '/Mem:/{m=$4} /Swap:/{s=$4} END{print m, s}')
  echo "$(date +%T) gtt=$(gib $g)GiB vram=$(gib $v)GiB peakgtt=$(gib $peak_gtt)GiB memfree=${mf}G swapfree=${sf}G"
  sleep 5
done
echo "=== PEAK gtt=$(gib $peak_gtt)GiB vram=$(gib $peak_vram)GiB ($(date +%T)) train_directml 종료 ==="
