# -*- coding: utf-8 -*-
"""
1.5B lm_head DirectML 에러 분리 진단: tied-weight 문제 vs 공유메모리 compute 문제.

배경: 1.5B(tied lm_head=embed)가 적재OK·트랜스포머 forward OK인데 lm_head F.linear서 실패.
  7B/14B(untied)는 lm_head 통과 → tied가 의심.

테스트:
  A) tied 그대로 lm_head forward → 에러 재현?
  B) lm_head를 embed에서 분리(clone, 별도 파라미터)한 뒤 forward → 되나?
  → B가 되면 'tied+DirectML' 문제 확정(공유compute는 정상). A·B 둘 다 실패면 공유compute 문제.

실행: python scripts/diag_1p5b_lmhead.py
"""
import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import torch, torch_directml, torch.nn as nn

# train_directml의 로더 재사용(tie 수정 포함)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "td", os.path.join(os.path.dirname(__file__), "..", "src", "train_directml.py"))
td = importlib.util.module_from_spec(spec)
spec.loader.exec_module(td)

dev = torch_directml.device()
MP = os.path.join(os.path.dirname(__file__), "..", "models", "base", "qwen2.5-coder-1.5b")
print(f"[load] 1.5B 적재 시작 (dev={dev})", flush=True)
model = td.stream_load_to_device(MP, dev, torch.float16)
model.config.use_cache = False
model.eval()
print("[load] OK", flush=True)

ids = torch.randint(0, 1000, (1, 64), device=dev)

# --- Test A: tied 그대로 ---
print("\n=== Test A: tied lm_head forward ===", flush=True)
try:
    with torch.no_grad():
        out = model(input_ids=ids)
    print(f"  [A-OK] tied forward 성공! logits {tuple(out.logits.shape)}", flush=True)
    a_ok = True
except Exception as e:
    print(f"  [A-FAIL] {type(e).__name__}: {str(e)[:120]}", flush=True)
    a_ok = False

# --- Test B: lm_head 분리(untie) 후 forward ---
print("\n=== Test B: lm_head untie(clone) 후 forward ===", flush=True)
try:
    # 현재 lm_head.weight가 embed와 같은 텐서 → 별도 복제로 교체
    w = model.lm_head.weight.detach().clone()
    model.lm_head.weight = nn.Parameter(w, requires_grad=False)
    model.config.tie_word_embeddings = False
    print(f"  untie 완료 (lm_head 별도 텐서 {tuple(w.shape)})", flush=True)
    with torch.no_grad():
        out = model(input_ids=ids)
    print(f"  [B-OK] untied forward 성공! logits {tuple(out.logits.shape)}", flush=True)
    b_ok = True
except Exception as e:
    print(f"  [B-FAIL] {type(e).__name__}: {str(e)[:120]}", flush=True)
    b_ok = False

# --- 결론 ---
print("\n=== 결론 ===", flush=True)
if not a_ok and b_ok:
    print(">>> ★tied-weight + DirectML 문제 확정. untie하면 1.5B 공유모드 학습 가능 → 공유 compute는 정상.", flush=True)
    print("    조치: 로더/빌드에서 DirectML일 때 lm_head를 clone으로 untie하면 됨.", flush=True)
elif a_ok:
    print(">>> tied도 성공?! 이전 실패는 다른 원인(학습경로 LoRA/loss). forward 자체는 OK.", flush=True)
else:
    print(">>> A·B 둘 다 실패 = 공유메모리 compute 문제(tied 무관). 공유모드 학습 불가 확정.", flush=True)
