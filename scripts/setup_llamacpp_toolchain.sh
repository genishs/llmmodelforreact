#!/usr/bin/env bash
# setup_llamacpp_toolchain.sh — llama.cpp(Vulkan) 무sudo 빌드 툴체인 부트스트랩 (이슈 #9).
#
# WHY: 이 장비(gfx1151/Strix Halo)엔 sudo가 없다. Ubuntu 저장소엔 glslc/libvulkan-dev/
# SPIRV-Headers 등 llama.cpp Vulkan 백엔드 빌드에 필요한 패키지가 있지만 설치(apt install)엔
# root가 필요하다. `apt-get download`(패키지 파일만 받기)와 `dpkg -x`(설치 없이 파일만 추출)는
# root가 필요 없다는 점을 이용해 사용자 홈 아래에 로컬 툴체인을 구성한다. cmake/ninja는
# PyPI 휠(prebuilt 바이너리 포함)로 조달 — 이 역시 sudo 불필요.
#
# 산출물: $WORK_DIR/local-toolchain (glslc 등) + $WORK_DIR/llamacpp-venv (cmake/ninja) +
#         $WORK_DIR/llamacpp-src (git clone) + build-cpu/ + build-vulkan/ (각각 bin/llama-cli 등)
#
# ⚠ 실행 위치 주의: $WORK_DIR을 tmpfs(/tmp 등)에 두지 말 것 — 이 장비 /tmp는 tmpfs(RAM 백엔드,
# `mount | grep tmpfs.*\ /tmp\ ` 로 확인)라 빌드 산출물이 그대로 host RAM을 먹는다. 기본값은
# 리포 바깥의 실디스크 경로(/mnt/data, ntfs-3g 실디스크)다.
#
# 실행: bash scripts/setup_llamacpp_toolchain.sh [WORK_DIR]
#   기본 WORK_DIR = /mnt/data/Documents/workspace/study/_llamacpp_toolchain
#
# 검증 커맨드(빌드 후):
#   LD_LIBRARY_PATH="$WORK_DIR/local-toolchain/usr/lib/x86_64-linux-gnu" \
#     "$WORK_DIR/llamacpp-src/build-vulkan/bin/llama-cli" --list-devices
#   → "Vulkan0: AMD Radeon 8060S (RADV STRIX_HALO) ..." 가 보이면 성공(추론 실행 아님, 순수 열거).
set -euo pipefail

WORK_DIR="${1:-/mnt/data/Documents/workspace/study/_llamacpp_toolchain}"
JOBS="${LLAMACPP_BUILD_JOBS:-6}"   # 병렬도 낮게: 이 장비는 통합메모리(APU)라 컴파일도 RAM 공유

case "$WORK_DIR" in
  /tmp/*) echo "REFUSING: WORK_DIR=$WORK_DIR 가 /tmp 아래 — tmpfs면 RAM을 직접 먹는다. 실디스크 경로를 쓸 것." >&2; exit 1 ;;
esac

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo "== 1) 필요 .deb 만 download(설치 아님) 후 로컬 추출 =="
mkdir -p apt-extract local-toolchain
cd apt-extract
# 최소 필요셋(실측 확정, 2026-07-31): glslc 실행에 libshaderc1, cmake Vulkan 검색에
# libvulkan-dev(vulkan.h + libvulkan.so 심링크), Vulkan 백엔드의 SPIRV-Headers/-Tools cmake config에
# spirv-headers/spirv-tools-dev(+spirv-tools-headers 의존).
apt-get download glslc libshaderc1 libvulkan-dev spirv-headers spirv-tools-dev spirv-tools-headers
for f in *.deb; do dpkg -x "$f" "$WORK_DIR/local-toolchain"; done
cd "$WORK_DIR"

# libvulkan-dev의 libvulkan.so는 libvulkan.so.1(런타임, libvulkan1 패키지)로의 심링크인데
# libvulkan1은 여기서 받지 않았다(이미 시스템에 설치돼 있다는 전제 — mesa-vulkan-drivers와 함께
# 보통 기본 설치됨, `dpkg -l libvulkan1`로 확인). 없다면 위 apt-get download 목록에 libvulkan1 추가.
if [ ! -e /usr/lib/x86_64-linux-gnu/libvulkan.so.1 ]; then
  echo "WARN: 시스템에 libvulkan.so.1 이 없다 — libvulkan1 을 추가로 download+추출 필요" >&2
else
  ln -sf /usr/lib/x86_64-linux-gnu/libvulkan.so.1 local-toolchain/usr/lib/x86_64-linux-gnu/libvulkan.so
fi

echo "== 2) glslc 동작 확인 =="
LD_LIBRARY_PATH="$WORK_DIR/local-toolchain/usr/lib/x86_64-linux-gnu" \
  "$WORK_DIR/local-toolchain/usr/bin/glslc" --version

echo "== 3) cmake/ninja(PyPI prebuilt, sudo 불필요) =="
if [ ! -d llamacpp-venv ]; then
  uv venv --python 3.12 llamacpp-venv
fi
# shellcheck disable=SC1091
source llamacpp-venv/bin/activate
uv pip install cmake ninja

echo "== 4) llama.cpp clone(얕은 클론) =="
if [ ! -d llamacpp-src ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git llamacpp-src
fi
cd llamacpp-src

TOOLCHAIN="$WORK_DIR/local-toolchain"
export LD_LIBRARY_PATH="$TOOLCHAIN/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

echo "== 5) CPU 백엔드 빌드(항상 되는 폴백, 회귀 기준선) =="
cmake -S . -B build-cpu -G Ninja -DGGML_NATIVE=OFF -DGGML_VULKAN=OFF -DGGML_HIP=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu -j"$JOBS"

echo "== 6) Vulkan 백엔드 빌드 =="
cmake -S . -B build-vulkan -G Ninja \
  -DGGML_NATIVE=OFF -DGGML_VULKAN=ON -DGGML_HIP=OFF -DCMAKE_BUILD_TYPE=Release \
  -DVulkan_INCLUDE_DIR="$TOOLCHAIN/usr/include" \
  -DVulkan_LIBRARY="$TOOLCHAIN/usr/lib/x86_64-linux-gnu/libvulkan.so" \
  -DVulkan_GLSLC_EXECUTABLE="$TOOLCHAIN/usr/bin/glslc" \
  -DCMAKE_PREFIX_PATH="$TOOLCHAIN/usr"
cmake --build build-vulkan -j"$JOBS"

echo "== 7) 열거 확인(추론 실행 아님 — GPU 경합 없음) =="
"$WORK_DIR/llamacpp-src/build-vulkan/bin/llama-cli" --list-devices

echo
echo "완료. 실행 시 항상 LD_LIBRARY_PATH=\"$TOOLCHAIN/usr/lib/x86_64-linux-gnu\" 를 잡아줄 것"
echo "(glslc는 빌드 시점에만 필요하지만, libvulkan 로더 관련 잔여 참조가 있을 수 있어 습관화 권장)."
