#!/usr/bin/env bash
# mixtral_safety_watch.sh — 무인 141B 풀학습 안전 watchdog.
#
# ⚠️ C2: 정상 학습엔 간섭 안 함(읽기 감시). 프리즈 임박 신호에서만 학습 유닛을 하드 중단.
#   두목 부재 무인 상황이라, GPU 웨지→GNOME 프리즈로 세션 통째 사망하는 것을 예방한다.
# 개입 조건: (a) SwapFree < 임계(프리즈 임박), (b) 커널 OOM-kill/amdgpu 웨지·리셋/hipError.
# 개입 = 학습 유닛 정지(진척은 train의 주기 체크포인트가 이미 저장) + 큐잉 로그.
UNIT_GLOB="${1:-gpujob-mixtralfull-*}"
SWAP_MIN_GIB="${2:-4}"
LOG=/home/user/gpu_jobs/logs/mixtral_safety_watch.log
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] watchdog 시작 (unit=$UNIT_GLOB, swap_min=${SWAP_MIN_GIB}G)"
# 학습 등장 대기(최대 15분: 스트리밍 양자화 로드 시간 감안)
for i in $(seq 1 180); do pgrep -f "train_directml.py" >/dev/null && break; sleep 5; done
if ! pgrep -f "train_directml.py" >/dev/null; then echo "[$(date '+%F %T')] train 미등장 — watchdog 종료"; exit 0; fi
echo "[$(date '+%F %T')] train 감지 — 감시 개시"
while pgrep -f "train_directml.py" >/dev/null; do
  sf=$(free -g | awk '/Swap:/{print $4}'); sf=${sf:-99}
  mf=$(free -g | awk '/Mem:/{print $4}'); mf=${mf:-99}
  oom=$(journalctl -k --no-pager --since "-2min" 2>/dev/null | grep -icE "Out of memory|oom-kill|oom_reaper|amdgpu.*(reset|wedged)|ring .*timeout|hip[eE]rror|GPU reset" || echo 0)
  if [ "$sf" -lt "$SWAP_MIN_GIB" ] || [ "$oom" -gt 0 ]; then
    echo "[$(date '+%F %T')] !!! 위험감지 SwapFree=${sf}G MemFree=${mf}G oom/wedge=$oom → 학습 유닛 중단"
    systemctl --user stop $UNIT_GLOB 2>/dev/null
    sleep 3
    pkill -TERM -f "train_directml.py" 2>/dev/null   # 유닛 stop 미흡 시 보조(주기저장 핸들러 발동)
    echo "[$(date '+%F %T')] [QUEUE] 무인 프리즈 방지로 141B 풀학습 강제중단(SwapFree=${sf}G oom=$oom)."
    echo "        마지막 주기 체크포인트는 ./models/mixtral-8x22b-hqq2-full 에 보존됨. 원인 점검 필요."
    exit 1
  fi
  sleep 15
done
echo "[$(date '+%F %T')] train 정상 종료 — watchdog 종료"
