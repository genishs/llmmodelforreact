#!/usr/bin/env python
"""
test_nf4_backward_gate.py -- decide which 4bit path can do BACKWARD on gfx1151.

BACKGROUND
    On this box (Radeon 8060S / gfx1151, iGPU shared with the display):
      - bf16 training           : rock solid
      - 4bit inference          : fine
      - 4bit QLoRA BACKWARD via bitsandbytes : wedges the GPU
        ("HIP error: unspecified launch failure" -> "amdgpu: device wedged")
        and, because the display shares the iGPU, kills the GNOME session.

THE HYPOTHESIS THIS TEST CHECKS
    bitsandbytes ships hand-written HIP kernels for the 4bit backward whose tiling
    is wavefront-size dependent. gfx1151 is RDNA3.5 / wave32, but the legacy
    __AMDGCN_WAVEFRONT_SIZE macro is undefined on ROCm 7.13 clang, so the build
    falls back to WARP_SIZE 64 -> out-of-bounds shared-memory access -> wedge.
    (See scripts/bnb-rocm-gfx1151-warpsize.patch in this repo.)

    torchao NF4 and HQQ (PYTORCH backend) have NO custom 4bit backward kernel at
    all: both dequantize to bf16/fp16 and then call a plain, well-tested matmul.
    If the hypothesis holds, those two must PASS while bnb FAILs.

    Verified in the installed sources:
      torchao 0.17.0
        site-packages/torchao/dtypes/nf4tensor.py:1061  class LinearNF4(torch.autograd.Function)
        site-packages/torchao/dtypes/nf4tensor.py:1069  backward = grad_output @ weight.to(grad_output.dtype)
        site-packages/torchao/dtypes/nf4tensor.py:1145  @implements_torch_function(F.linear) -> LinearNF4.apply
        site-packages/torchao/dtypes/nf4tensor.py:1085  def to_nf4(tensor, block_size=64, scaler_block_size=256)
      hqq 0.2.8.post1
        site-packages/hqq/core/quantize.py:289  class HQQMatmulNoCacheDeq(torch.autograd.Function)
        site-packages/hqq/core/quantize.py:304  backward = grad_output @ ctx.dequantize()
        site-packages/hqq/core/quantize.py:271  HQQBackend.PYTORCH = "forward_pytorch_backprop"

    NOTE: torchao's compiled cpp extensions do NOT load here ("Skipping import of
    cpp extensions due to incompatible torch version (needs >= 2.11)"). That is
    FINE and expected: NF4Tensor is pure-python + aten ops and needs no extension.
    This test asserts that explicitly rather than letting it be a silent unknown.

    We deliberately do NOT use quantize_(model, int4_weight_only()). That is an
    inference-oriented API; the training path is the torchtune QLoRA one above.

SAFETY / ISOLATION
    Each backend runs in its OWN subprocess with a hard timeout. A wedge or a
    hard crash in one backend therefore costs us that backend's verdict only --
    the others still report. bitsandbytes is the KNOWN-BAD control and is skipped
    unless you pass --include-bnb, because running it may kill the desktop.

USAGE
    # safe backends only (recommended first run)
    python scripts/test_nf4_backward_gate.py

    # include the known-bad control -- MAY WEDGE THE GPU AND KILL THE DESKTOP.
    # Only ever do this from a detached job:
    #   scripts/gpu_job.sh --name nf4gate --debug -- \
    #       python scripts/test_nf4_backward_gate.py --include-bnb
    python scripts/test_nf4_backward_gate.py --include-bnb

    # internal: run exactly one backend in-process (used by the orchestrator)
    python scripts/test_nf4_backward_gate.py --backend torchao
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

# Keep the test SMALL and FAST: one 4096x4096 Linear, batch 8. Big enough to be a
# real kernel launch on real tiles, small enough to finish in seconds and to never
# be an OOM story on the 8GiB VRAM carve-out.
DIM = 4096
BATCH = 8
BACKENDS = ("torchao", "hqq", "bnb")
PER_BACKEND_TIMEOUT = 180  # seconds; a wedge usually manifests in <30s


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _banner(msg: str) -> None:
    print(f"\n{'=' * 70}\n{msg}\n{'=' * 70}", flush=True)


def _device():
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "torch.cuda.is_available() is False. On this box that usually means "
            "HSA_OVERRIDE_GFX_VERSION got set (even to empty) -- it must stay UNSET."
        )
    return torch.device("cuda")


def _check(name: str, out, grad, dt: float) -> bool:
    """Shared assertions: output and grad must exist, be finite, and be non-trivial."""
    import torch

    ok = True
    if out is None or grad is None:
        print(f"  [{name}] FAIL: missing output or grad")
        return False
    if not torch.isfinite(out).all():
        print(f"  [{name}] FAIL: forward output has NaN/Inf")
        ok = False
    if not torch.isfinite(grad).all():
        print(f"  [{name}] FAIL: input grad has NaN/Inf")
        ok = False
    if grad.abs().sum().item() == 0.0:
        # An all-zero grad means backward silently did nothing -- that is a FAIL,
        # not a pass. This is the failure mode a naive "did it throw?" test misses.
        print(f"  [{name}] FAIL: input grad is all zeros (backward was a no-op)")
        ok = False
    print(
        f"  [{name}] out{tuple(out.shape)} {out.dtype} | "
        f"grad{tuple(grad.shape)} absmean={grad.abs().mean().item():.3e} | {dt * 1000:.1f} ms"
    )
    return ok


def _sync():
    import torch

    torch.cuda.synchronize()


# --------------------------------------------------------------------------
# backend: torchao NF4  (the torchtune QLoRA path)
# --------------------------------------------------------------------------
def run_torchao() -> bool:
    import torch
    import torch.nn.functional as F

    # NF4Tensor is pure python + aten ops; the cpp extension warning above is
    # expected and irrelevant. Assert that the import path we depend on works.
    from torchao.dtypes.nf4tensor import NF4Tensor, to_nf4, linear_nf4  # noqa: F401

    dev = _device()
    print(f"  to_nf4 / NF4Tensor / linear_nf4 imported OK (cpp extensions not required)")

    w = torch.randn(DIM, DIM, device=dev, dtype=torch.bfloat16)
    w_nf4 = to_nf4(w, block_size=64, scaler_block_size=256)
    assert isinstance(w_nf4, NF4Tensor), f"to_nf4 returned {type(w_nf4)}"
    print(f"  quantized {DIM}x{DIM} bf16 -> NF4Tensor")

    x = torch.randn(BATCH, DIM, device=dev, dtype=torch.bfloat16, requires_grad=True)
    _sync()

    t0 = time.perf_counter()
    # F.linear on an NF4Tensor weight dispatches via __torch_function__ into
    # LinearNF4.apply (nf4tensor.py:1145) -- the autograd path.
    out = F.linear(x, w_nf4)
    _sync()
    t_fwd = time.perf_counter() - t0

    t0 = time.perf_counter()
    out.sum().backward()
    _sync()
    t_bwd = time.perf_counter() - t0

    print(f"  forward {t_fwd * 1000:.1f} ms | backward {t_bwd * 1000:.1f} ms")

    # Also exercise the explicit functional entry point, which is what torchtune's
    # QLoRA linear actually calls.
    x2 = torch.randn(BATCH, DIM, device=dev, dtype=torch.bfloat16, requires_grad=True)
    linear_nf4(x2, w_nf4).sum().backward()
    _sync()
    assert x2.grad is not None and torch.isfinite(x2.grad).all(), "linear_nf4 grad bad"
    print("  linear_nf4() explicit entry point also produced finite grads")

    return _check("torchao-nf4", out, x.grad, t_fwd + t_bwd)


# --------------------------------------------------------------------------
# backend: HQQ
# --------------------------------------------------------------------------
def run_hqq() -> bool:
    import torch
    from hqq.core.quantize import BaseQuantizeConfig, HQQBackend, HQQLinear

    dev = _device()

    # HQQBackend.ATEN needs the hqq_aten CUDA extension, which does not exist on
    # ROCm. PYTORCH == "forward_pytorch_backprop" -> HQQMatmulNoCacheDeq
    # (quantize.py:289): dequantize() then a plain torch.matmul. That is the only
    # backend here with a defined, kernel-free backward.
    HQQLinear.set_backend(HQQBackend.PYTORCH)
    print("  HQQ backend forced to PYTORCH (ATEN is CUDA-only / unavailable on ROCm)")

    lin = torch.nn.Linear(DIM, DIM, bias=False, dtype=torch.bfloat16)
    qcfg = BaseQuantizeConfig(nbits=4, group_size=64, axis=1)
    qlin = HQQLinear(lin, quant_config=qcfg, compute_dtype=torch.bfloat16, device=str(dev))
    print(f"  quantized {DIM}x{DIM} -> HQQLinear nbits=4 group_size=64")

    x = torch.randn(BATCH, DIM, device=dev, dtype=torch.bfloat16, requires_grad=True)
    _sync()

    t0 = time.perf_counter()
    out = qlin(x)
    _sync()
    t_fwd = time.perf_counter() - t0

    t0 = time.perf_counter()
    out.sum().backward()
    _sync()
    t_bwd = time.perf_counter() - t0

    print(f"  forward {t_fwd * 1000:.1f} ms | backward {t_bwd * 1000:.1f} ms")
    return _check("hqq-4bit", out, x.grad, t_fwd + t_bwd)


# --------------------------------------------------------------------------
# backend: bitsandbytes -- KNOWN-BAD CONTROL, may wedge the GPU
# --------------------------------------------------------------------------
def run_bnb() -> bool:
    import bitsandbytes as bnb
    import torch
    from bitsandbytes.nn import Linear4bit

    dev = _device()
    print(f"  bitsandbytes {getattr(bnb, '__version__', '?')} from {bnb.__file__}")
    print("  *** KNOWN-BAD CONTROL: this is the call that wedges the GPU. ***")

    lin = Linear4bit(DIM, DIM, bias=False, compute_dtype=torch.bfloat16, quant_type="nf4")
    lin = lin.to(dev)  # quantization happens on .to(cuda)
    print(f"  quantized {DIM}x{DIM} -> Linear4bit nf4")

    x = torch.randn(BATCH, DIM, device=dev, dtype=torch.bfloat16, requires_grad=True)
    _sync()

    t0 = time.perf_counter()
    out = lin(x)
    _sync()  # forward is expected to be fine
    t_fwd = time.perf_counter() - t0
    print(f"  forward OK ({t_fwd * 1000:.1f} ms) -- now the backward, which is the suspect")

    t0 = time.perf_counter()
    out.sum().backward()
    _sync()  # the wedge, if it happens, surfaces here
    t_bwd = time.perf_counter() - t0

    print(f"  backward SURVIVED ({t_bwd * 1000:.1f} ms) -- unexpected, worth re-testing")
    return _check("bnb-nf4", out, x.grad, t_fwd + t_bwd)


RUNNERS = {"torchao": run_torchao, "hqq": run_hqq, "bnb": run_bnb}


# --------------------------------------------------------------------------
# single-backend (child) mode
# --------------------------------------------------------------------------
def run_one(name: str) -> int:
    _banner(f"BACKEND: {name}")
    print(f"  AMD_SERIALIZE_KERNEL={os.environ.get('AMD_SERIALIZE_KERNEL', '<unset>')}  "
          f"HIP_LAUNCH_BLOCKING={os.environ.get('HIP_LAUNCH_BLOCKING', '<unset>')}")
    if "HSA_OVERRIDE_GFX_VERSION" in os.environ:
        print("  WARNING: HSA_OVERRIDE_GFX_VERSION is SET -- it must be unset on this box!")
    try:
        import torch

        print(f"  torch {torch.__version__} | device {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"  FAIL: torch/device unavailable: {e}")
        return 1

    t0 = time.perf_counter()
    try:
        ok = RUNNERS[name]()
    except ImportError as e:
        print(f"  SKIP: backend not installed: {e}")
        return 77  # distinct code -> reported as SKIP, not FAIL
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 1
    dt = time.perf_counter() - t0
    print(f"\n  ==> {name}: {'PASS' if ok else 'FAIL'}  ({dt:.1f}s total)")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# orchestrator (parent) mode
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=BACKENDS, help="run ONE backend in-process (child mode)")
    ap.add_argument("--include-bnb", action="store_true",
                    help="also run the known-bad bitsandbytes control (MAY WEDGE THE GPU / KILL THE DESKTOP)")
    ap.add_argument("--timeout", type=int, default=PER_BACKEND_TIMEOUT, help="per-backend timeout (s)")
    args = ap.parse_args()

    if args.backend:
        return run_one(args.backend)

    # Safe backends first, so that if bnb wedges the box we already have the
    # verdicts that actually matter for choosing a training path.
    order = ["torchao", "hqq"] + (["bnb"] if args.include_bnb else [])

    _banner("nf4 BACKWARD GATE -- gfx1151 / Radeon 8060S")
    print(f"  shape       : Linear({DIM}x{DIM}), batch {BATCH}, bf16")
    print(f"  backends    : {', '.join(order)}")
    print(f"  timeout     : {args.timeout}s per backend")
    print(f"  isolation   : each backend runs in its own subprocess")
    if not args.include_bnb:
        print("  bnb         : SKIPPED (pass --include-bnb to run the known-bad control)")
    else:
        print("  bnb         : INCLUDED -- the desktop may die. Hope you ran this detached.")

    results: dict[str, str] = {}
    for name in order:
        t0 = time.perf_counter()
        try:
            p = subprocess.run(
                [sys.executable, os.path.abspath(__file__), "--backend", name],
                timeout=args.timeout,
            )
            rc = p.returncode
        except subprocess.TimeoutExpired:
            # A hang is a distinct, meaningful outcome: the GPU is very likely wedged.
            results[name] = f"TIMEOUT (>{args.timeout}s) -- GPU likely wedged"
            print(f"\n  ==> {name}: TIMEOUT after {args.timeout}s", flush=True)
            continue
        dt = time.perf_counter() - t0

        if rc == 0:
            results[name] = f"PASS ({dt:.1f}s)"
        elif rc == 77:
            results[name] = "SKIP (not installed)"
        elif rc < 0:
            # Killed by a signal -- SIGABRT/SIGSEGV is what a HIP wedge looks like
            # from the parent's point of view.
            results[name] = f"CRASH (signal {-rc}) -- GPU fault, check journalctl -k for 'wedged'"
        else:
            results[name] = f"FAIL (exit {rc})"

    _banner("SUMMARY")
    for name in order:
        verdict = results.get(name, "NOT RUN")
        mark = "PASS" if verdict.startswith("PASS") else ("SKIP" if verdict.startswith("SKIP") else "FAIL")
        print(f"  {mark:4}  {name:8}  {verdict}")

    if not args.include_bnb:
        print("\n  (bitsandbytes not run -- it is the known-bad control; --include-bnb to confirm.)")
    print("\n  Next: pick the fastest PASSing backend as the QLoRA path.")
    print("  If a backend CRASHed/TIMEOUTed, re-run it alone with:")
    print("    scripts/gpu_job.sh --name nf4-<backend> --debug -- \\")
    print("        python scripts/test_nf4_backward_gate.py --backend <backend>")
    print("  --debug sets AMD_SERIALIZE_KERNEL=3 + HIP_LAUNCH_BLOCKING=1 so the log")
    print("  names the exact faulting kernel instead of a vague async failure.")

    passed = [n for n in order if results.get(n, "").startswith("PASS")]
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
