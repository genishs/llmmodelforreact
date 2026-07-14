# -*- coding: utf-8 -*-
"""bnb-ROCm(gfx1151) nf4 4bit GPU 수치검증 — 32B/70B 4bit 트랙의 게이트.

빌드/임포트는 통과했으나(libbitsandbytes_rocm713.so) 실제 GPU에서 nf4 양자화/역양자화·
Linear4bit matmul이 non-NaN·정상값을 내는지는 미검증. 이 스크립트가 그 게이트다.

검사:
  1) import bitsandbytes + .so 버전 확인
  2) functional quantize_4bit/dequantize_4bit(nf4) GPU 왕복 → 유한값·상대오차 합리
  3) nn.Linear4bit forward(GPU) vs fp16 레퍼런스 → non-NaN·상대오차 합리

PASS 조건: 3개 모두 유한(non-NaN/Inf) + Linear4bit 상대오차 < 0.15(nf4 근사 허용).
실패(NaN/Inf/큰오차)면 4bit 트랙 전체 중단(coordinator에 blocker 보고).

실행: PYTORCH_HIP_ALLOC_CONF=expandable_segments:True python scripts/test_bnb_nf4_numeric.py
"""
import sys
import torch


def main():
    assert torch.cuda.is_available(), "cuda(ROCm) 미가용 — 게이트 무의미"
    dev = torch.device("cuda:0")
    print(f"device: {torch.cuda.get_device_name(0)}")

    import bitsandbytes as bnb
    print(f"bitsandbytes {bnb.__version__}")
    try:
        import bitsandbytes.cextension as ce
        print(f"  lib: {getattr(ce, 'BNB_BACKEND', '?')} / {getattr(ce.lib, '_name', ce.lib)}")
    except Exception as e:
        print(f"  (cextension 정보 조회 실패, 무해: {e})")

    torch.manual_seed(0)
    ok = True

    # --- 2) functional nf4 왕복 ---
    print("\n[2] functional quantize/dequantize_4bit (nf4) GPU 왕복")
    x = torch.randn(4096, 4096, dtype=torch.float16, device=dev)
    q, state = bnb.functional.quantize_4bit(x, quant_type="nf4")
    xdq = bnb.functional.dequantize_4bit(q, state, quant_type="nf4").to(torch.float16)
    finite = torch.isfinite(xdq).all().item()
    rel = (xdq.float() - x.float()).norm().item() / (x.float().norm().item() + 1e-9)
    print(f"    packed dtype={q.dtype} shape={tuple(q.shape)}  dequant finite={finite}  rel_err={rel:.4f}")
    if not finite or rel > 0.20:
        print("    ✗ FAIL (NaN/Inf 또는 rel_err 과대)"); ok = False
    else:
        print("    ✓ ok")

    # --- 3) Linear4bit forward vs fp16 레퍼런스 ---
    print("\n[3] nn.Linear4bit forward(GPU) vs fp16 레퍼런스")
    in_f, out_f = 2048, 2048
    ref = torch.nn.Linear(in_f, out_f, bias=False).to(torch.float16)
    W = ref.weight.data.clone()
    lin4 = bnb.nn.Linear4bit(in_f, out_f, bias=False, compute_dtype=torch.float16, quant_type="nf4")
    lin4.weight = bnb.nn.Params4bit(W, requires_grad=False, quant_type="nf4")
    lin4 = lin4.to(dev)
    ref = ref.to(dev)
    inp = torch.randn(8, in_f, dtype=torch.float16, device=dev)
    with torch.no_grad():
        y4 = lin4(inp)
        yref = ref(inp)
    finite = torch.isfinite(y4).all().item()
    rel = (y4.float() - yref.float()).norm().item() / (yref.float().norm().item() + 1e-9)
    print(f"    out shape={tuple(y4.shape)} finite={finite}  rel_err_vs_fp16={rel:.4f}")
    print(f"    sample y4[0,:4]={y4[0,:4].tolist()}")
    if not finite or rel > 0.15:
        print("    ✗ FAIL (NaN/Inf 또는 rel_err > 0.15)"); ok = False
    else:
        print("    ✓ ok")

    print("\n" + ("=== bnb nf4 GPU 수치검증 PASS ===" if ok else "=== bnb nf4 GPU 수치검증 FAIL (4bit 트랙 중단) ==="))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
