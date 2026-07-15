#!/usr/bin/env bash
# ROCm 학습환경 재개 스크립트 — halo-ubuntu-pm (Ubuntu 26.04 / gfx1151 / Radeon 8060S)
# 사용: bash scripts/rocm_resume.sh   (★ 사용자 실제/지속 터미널에서 실행 권장)
# 상세 상태·계획: docs/rocm-setup-resume.md
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
VENV="$HOME/.venvs/ai_model_rocm"
PY="$VENV/bin"
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

echo "===== [0] 환경 확인 ====="
if [ ! -x "$PY/python" ]; then
  echo "venv 없음 → 생성"; command -v uv >/dev/null || { echo "uv 없음. curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
  uv venv --python 3.12 "$VENV"
fi
"$PY/python" --version
if [ -e /dev/kfd ]; then echo "/dev/kfd OK ($(stat -c '%A' /dev/kfd))"; else echo "⚠️ /dev/kfd 없음 — amdgpu 미로드? (재부팅/드라이버 확인)"; fi

echo "===== [1] TheRock gfx1151 torch ====="
if "$PY/python" -c "import torch" 2>/dev/null; then
  echo "torch 이미 설치: $("$PY/python" -c 'import torch;print(torch.__version__)')"
else
  echo "torch 설치 중 (cp312 linux 휠, rocm 자체번들)..."
  # ★ uv venv는 pip을 포함하지 않음 → 반드시 'uv pip install' 사용 (venv의 pip 호출 금지)
  uv pip install --python "$PY/python" torch --index-url https://rocm.nightlies.amd.com/v2/gfx1151/ 2>&1 | tee logs/therock_torch_install.log
fi

echo "===== [2] Gate A — GPU sanity (세그폴트 게이트) ====="
"$PY/python" - <<'PY'
import traceback
try:
    import torch
    print("torch", torch.__version__, "| cuda_available", torch.cuda.is_available())
    assert torch.cuda.is_available(), "GPU 미인식"
    print("device", torch.cuda.get_device_name(0))
    x = torch.randn(1024, 1024, device="cuda"); print("fp32_matmul", float((x@x).sum()))
    xb = x.to(torch.bfloat16); print("bf16_matmul", float((xb@xb).sum()))
    torch.cuda.empty_cache(); print("empty_cache OK")
    f, t = torch.cuda.mem_get_info(); print(f"mem free={f/1e9:.1f}GB total={t/1e9:.1f}GB")
    print("GATE_A: PASS  ✅ (Linux+ROCm 경로 유효 — 세그폴트 없음)")
except Exception as e:
    traceback.print_exc(); print("GATE_A: FAIL", repr(e))
    print("→ 실패 시 TheRock 휠 다른 날짜 빌드로 재시도 (docs/rocm-linux-dualboot-plan.md 참조)")
PY

echo "===== [3] ML 의존성 (torch 재설치 방지) ====="
uv pip install --python "$PY/python" "transformers>=4.44" "peft>=0.12" "accelerate>=0.33" "datasets>=2.20" \
  safetensors sentencepiece pyyaml psutil tqdm 2>&1 | tail -6

echo "===== [4] 다음 단계 (수동, 대역폭 ~10MB/s) ====="
cat <<'NEXT'
  # 베이스 모델 다운로드 — 7B 먼저(~15GB, ~25분)
  $HOME/.venvs/ai_model_rocm/bin/python scripts/download_7b.py

  # smoke 학습 (Gate B): seq512 bf16 — step2 이후 OOM 없음 + bf16 안정 확인
  $HOME/.venvs/ai_model_rocm/bin/python src/train_directml.py --backend cuda --dtype bf16 \
    --seq 512 --lora-r 16 --epochs 1 --smoke 5 --out models/smoke-rocm \
    --train-file data/processed/react_train_r4.jsonl

  # 진행 사다리: 7B smoke → 14B bf16 qkvo+MLP seq1024(첫 실학습) → 14B seq2048 → 32B 4bit(bnb-ROCm 빌드 후)
NEXT
echo "===== 재개 스크립트 끝. 상세: docs/rocm-setup-resume.md ====="
