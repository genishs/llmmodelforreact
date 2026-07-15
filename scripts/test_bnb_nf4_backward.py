# -*- coding: utf-8 -*-
"""bnb-ROCm(gfx1151) nf4 4bit BACKWARD(autograd) 수치검증 — 4bit QLoRA 학습의 진짜 게이트.

배경(2026-07-14 크래시복구 세션에서 발견):
  기존 `test_bnb_nf4_numeric.py`는 FORWARD만 검사했다(quantize/dequantize 왕복 + Linear4bit forward).
  그 게이트는 PASS했으나, 실제 32B 4bit QLoRA 학습에서 **backward()가 gfx1151 GPU를
  `HIP error: unspecified launch failure`로 웨지**시켰다(GPU 컨텍스트 손상 → 재부팅 필요).
  즉 forward-only 게이트는 4bit 학습 가능성을 보증하지 못한다. 이 스크립트가 그 공백을 메운다.

  또한 실제 체크포인트(32B/72B unsloth nf4)는 **bnb_4bit_use_double_quant=True**(중첩양자화)인데,
  기존 게이트는 double-quant를 켜지 않아(compress_statistics=False) 중첩 dequant 경로를 검사한 적이 없다.

이 스크립트는 4단계를 순차 실행하며 각 단계 후 flush → **로그의 마지막 성공단계가 웨지 지점**이다.
  [1] Linear4bit forward (no double-quant)          — 기존 게이트가 커버(기대 PASS)
  [2] Linear4bit backward (no double-quant)         — grad_input autograd
  [3] Linear4bit forward (double-quant, 체크포인트와 동일)
  [4] Linear4bit backward (double-quant)            — ★32B 실패가 재현될 유력 지점

주의: 이 스크립트는 GPU를 웨지시킬 수 있다(그게 검사대상). **재부팅 직후 다른 GPU작업 전에 단독 실행**.
      단계별로 별도 프로세스로 돌리려면 --stage N 으로 하나씩(웨지 시 컨텍스트 격리) 실행 권장.

실행: PYTORCH_HIP_ALLOC_CONF=expandable_segments:True python scripts/test_bnb_nf4_backward.py [--stage N]
"""
import sys
import argparse
import torch


def log(msg):
    print(msg, flush=True)


def make_lin(in_f, out_f, double_quant, dev):
    import bitsandbytes as bnb
    ref = torch.nn.Linear(in_f, out_f, bias=False).to(torch.bfloat16)
    W = ref.weight.data.clone()
    lin4 = bnb.nn.Linear4bit(
        in_f, out_f, bias=False, compute_dtype=torch.bfloat16,
        quant_type="nf4", compress_statistics=double_quant,
    )
    lin4.weight = bnb.nn.Params4bit(
        W, requires_grad=False, quant_type="nf4",
        compress_statistics=double_quant,
    )
    return lin4.to(dev)


def stage_forward(double_quant, dev):
    tag = "double-quant" if double_quant else "no-double-quant"
    log(f"\n[forward {tag}] Linear4bit forward")
    lin4 = make_lin(2048, 2048, double_quant, dev)
    inp = torch.randn(8, 2048, dtype=torch.bfloat16, device=dev)
    with torch.no_grad():
        y = lin4(inp)
    torch.cuda.synchronize()
    finite = torch.isfinite(y).all().item()
    log(f"    out={tuple(y.shape)} finite={finite}")
    assert finite, "forward NaN/Inf"
    log(f"    ✓ forward {tag} ok")


def stage_backward(double_quant, dev):
    tag = "double-quant" if double_quant else "no-double-quant"
    log(f"\n[backward {tag}] Linear4bit backward (grad→input)")
    lin4 = make_lin(2048, 2048, double_quant, dev)
    # QLoRA처럼: 4bit 가중치는 frozen, grad는 input(이전 레이어로) 경로로 흐른다.
    inp = torch.randn(8, 2048, dtype=torch.bfloat16, device=dev, requires_grad=True)
    y = lin4(inp)
    loss = y.float().pow(2).mean()
    loss.backward()                      # ← 여기가 32B에서 웨지된 연산
    torch.cuda.synchronize()             # 비동기 launch failure를 여기서 동기포착
    finite = torch.isfinite(inp.grad).all().item()
    log(f"    grad_input finite={finite} norm={inp.grad.float().norm().item():.4f}")
    assert finite, "backward NaN/Inf"
    log(f"    ✓ backward {tag} ok")


STAGES = [
    ("forward-nodq", lambda dev: stage_forward(False, dev)),
    ("backward-nodq", lambda dev: stage_backward(False, dev)),
    ("forward-dq", lambda dev: stage_forward(True, dev)),
    ("backward-dq", lambda dev: stage_backward(True, dev)),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=0,
                    help="1..4만 단독 실행(웨지 격리용). 0=전체 순차.")
    args = ap.parse_args()

    assert torch.cuda.is_available(), "cuda(ROCm) 미가용 — GPU 웨지상태면 재부팅 필요"
    dev = torch.device("cuda:0")
    import bitsandbytes as bnb
    log(f"device: {torch.cuda.get_device_name(0)} | bnb {bnb.__version__}")

    torch.manual_seed(0)
    run = STAGES if args.stage == 0 else [STAGES[args.stage - 1]]
    for name, fn in run:
        fn(dev)

    log("\n=== bnb nf4 4bit BACKWARD 수치검증 PASS (4bit QLoRA 학습 가능) ===")


if __name__ == "__main__":
    main()
