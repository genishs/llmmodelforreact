#!/usr/bin/env bash
# mem_watch.sh — 학습 중 GTT/VRAM/스왑 피크 계측(읽기전용). gfx1151 card1.
#
# ⚠️ C2 불변식: 순수 관찰. 도는 학습에 절대 간섭하지 않는다(read-only /sys + free).
# 정상범위(PM): gtt_used 45~53GiB 상승, SwapFree 완만 감소, MemFree 0 붕괴 없음.
# 위험: SwapFree 급감 / OOM-kill → 별도 dmesg 감시로 판단.
#
# 사용: bash scripts/mem_watch.sh [interval_sec]   (기본 5s). Ctrl-C 또는 kill로 종료 시 피크 요약.
GTT=/sys/class/drm/card1/device/mem_info_gtt_used
VRAM=/sys/class/drm/card1/device/mem_info_vram_used
INT="${1:-5}"
peak_gtt=0; peak_vram=0
gib() { awk -v b="$1" 'BEGIN{printf "%.1f", b/1073741824}'; }
trap 'echo "=== PEAK: gtt=$(gib $peak_gtt)GiB vram=$(gib $peak_vram)GiB ==="; exit 0' INT TERM
while true; do
  g=$(cat "$GTT" 2>/dev/null || echo 0); v=$(cat "$VRAM" 2>/dev/null || echo 0)
  [ "$g" -gt "$peak_gtt" ] && peak_gtt=$g
  [ "$v" -gt "$peak_vram" ] && peak_vram=$v
  read -r memfree swapfree < <(free -g | awk '/Mem:/{m=$4} /Swap:/{s=$4} END{print m, s}')
  echo "$(date +%T) gtt=$(gib $g)GiB vram=$(gib $v)GiB peakgtt=$(gib $peak_gtt)GiB memfree=${memfree}G swapfree=${swapfree}G"
  sleep "$INT"
done
