#!/usr/bin/env bash
# llm.sh — 로컬 LLM 서버 켜기/끄기 (halo-ubuntu, Radeon 8060S / Vulkan)
#
#   ~/llm.sh start [모델별칭]      서버 켜기 (기본: cn, 이 PC 에서만)
#   ~/llm.sh start q38 lan          같은 망의 다른 PC 에서도 접속 (API 키 자동 생성·적용)
#   ~/llm.sh stop               서버 끄기
#   ~/llm.sh status             상태·속도
#   ~/llm.sh list               쓸 수 있는 모델
#
# 켜지면 브라우저로  http://127.0.0.1:8080  에 들어가 바로 대화하면 된다(llama.cpp 내장 웹 UI).
# OpenAI 호환 API 도 같은 주소: http://127.0.0.1:8080/v1/chat/completions
#
# --no-mmap 은 최신 llama.cpp 에서 --load-mode none 으로 바뀌었다.
# 서버는 systemd --user 유닛(llm-server)으로 띄운다. 터미널을 닫아도 살아 있고,
# 그냥 & 로 띄우면 세션이 정리될 때 같이 죽는다(이 장비에서 실제로 겪음).
set -uo pipefail

BIN=/home/user/llama.cpp-bin/b11539/llama-b11539          # 공식 사전빌드(ext4 에 둬야 .so 링크가 안 깨진다)
GG=/mnt/data/Documents/workspace/study/_llamacpp_toolchain/gguf-work
PORT=8080
UNIT=llm-server
LOG=/home/user/gpu_jobs/logs/llm-server.log

declare -A MODEL=(
  [q38]="$GG/Qwen3.8-27B-UD-Q6_K.gguf"                  # Qwen3.8-27B (2026-08) dense, 22GB
  [cn]="$GG/Qwen_Qwen3-Coder-Next-Q4_K_M.gguf"          # Qwen3-Coder-Next 80B-A3B (2026-01) MoE, 48.7GB — 코딩 에이전트용
  [c7]="$GG/qwen2.5-coder-7b-q8_0.gguf"                 # Qwen2.5-Coder-7B (2024-09), 7.5GB
)
# 컨텍스트: Qwen3.8 은 64레이어 중 48개가 linear_attention 이라 KV 가 작다 → 넉넉히 잡아도 된다
declare -A CTX=( [q38]=65536 [cn]=65536 [c7]=16384 )

cmd="${1:-status}"; key="${2:-cn}"; net="${3:-local}"
# LAN 모드: 같은 망의 다른 PC 에서 접속. llama-server 는 기본 인증이 없으므로 API 키를 반드시 건다.
KEYFILE=/home/user/.config/llm-api-key
HOST=127.0.0.1; KEYARG=()
if [ "$net" = "lan" ]; then
  HOST=0.0.0.0
  [ -s "$KEYFILE" ] || { mkdir -p "$(dirname "$KEYFILE")"; umask 077; head -c 18 /dev/urandom | base64 | tr -d '/+=' > "$KEYFILE"; }
  KEYARG=(--api-key "$(cat "$KEYFILE")")
fi

case "$cmd" in
  start)
    f="${MODEL[$key]:-}"; [ -n "$f" ] || { echo "모르는 별칭: $key  (list 로 확인)"; exit 1; }
    [ -f "$f" ] || { echo "모델 파일 없음: $f"; exit 1; }
    systemctl --user stop "$UNIT" 2>/dev/null; systemctl --user reset-failed "$UNIT" 2>/dev/null
    mkdir -p "$(dirname "$LOG")"; : > "$LOG"
    systemd-run --user --unit="$UNIT" --description="llama-server $key" \
      --property="StandardOutput=append:$LOG" --property="StandardError=append:$LOG" \
      "$BIN/llama-server" -m "$f" --alias "$key" \
        --host "$HOST" --port "$PORT" "${KEYARG[@]}" \
        -ngl 999 --load-mode none -fa on \
        -c "${CTX[$key]}" --jinja >/dev/null
    printf "모델 올리는 중"
    for i in $(seq 1 180); do
      # ⚠️ curl -f 필수 — 로딩 중엔 503 을 주는데 -f 없으면 그걸 '준비됨'으로 오판한다
      curl -sf -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { echo " ✅ ${i}초"; break; }
      systemctl --user is-active --quiet "$UNIT" || { echo; echo "🔴 서버가 죽었다:"; tail -15 "$LOG"; exit 1; }
      printf "."; sleep 1
    done
    if [ "$net" = "lan" ]; then
      IP=$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -1)
      echo "→ 이 PC:      http://127.0.0.1:$PORT"
      echo "→ 다른 PC:    http://$IP:$PORT"
      echo "→ API 키:     $(cat "$KEYFILE")   (웹 UI 설정 ⚙ 의 API Key 칸에 입력)"
    else echo "→ 브라우저:  http://127.0.0.1:$PORT   (LAN 접속은: $0 start $key lan)"; fi
    ;;
  stop)   systemctl --user stop "$UNIT" 2>/dev/null; echo "꺼짐" ;;
  status)
    if systemctl --user is-active --quiet "$UNIT"; then
      echo "켜짐: 모델 $(tr '\0' ' ' < /proc/$(pgrep -x llama-server | head -1)/cmdline 2>/dev/null | grep -oE -- '--alias [^ ]+' | cut -d' ' -f2) · 포트 $PORT"
      grep -aE 'eval time|tokens per second' "$LOG" | tail -2
    else echo "꺼짐"; fi
    echo "GTT $(awk '{printf "%.1f",$1/1073741824}' /sys/class/drm/card*/device/mem_info_gtt_used | head -1)G / 56G"
    ;;
  list)
    for k in "${!MODEL[@]}"; do f="${MODEL[$k]}"; printf "  %-5s %s  %s\n" "$k" "$([ -f "$f" ] && du -h "$f" | cut -f1 || echo '없음')" "$(basename "$f")"; done
    ;;
  *) echo "사용: $0 {start [별칭]|stop|status|list}" ;;
esac
