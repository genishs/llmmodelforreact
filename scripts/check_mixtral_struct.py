# -*- coding: utf-8 -*-
"""Mixtral 체크포인트 키 ↔ 모델 트리 구조 일치 판정.

load_hqq_onthefly는 from_pretrained를 우회하고 체크포인트 텐서 이름을 모델 모듈 트리에
set_module_tensor_to_device로 직접 꽂는다. 따라서 체크포인트 index의 모든 weight 키가
빈 모델(from_config)의 named_parameters/buffers에 존재해야 동작한다.
5.13.1은 전문가를 융합 nn.Parameter로 바꿔 block_sparse_moe.experts.N.w1 키가 사라짐 → 사망.

이 스크립트는 설치된 transformers 버전이 체크포인트와 100% 매칭하는지 판정한다(meta device, 즉시).
"""
import json, sys, torch, transformers
BASE = "/run/media/user/새 볼륨/mixtral-8x22b-v0.1"
print(f"transformers {transformers.__version__} | torch {torch.__version__}", flush=True)
from transformers import AutoConfig, AutoModelForCausalLM
try:
    from accelerate import init_empty_weights
except Exception:
    from transformers.modeling_utils import no_init_weights as _n  # fallback (unused)
    raise

cfg = AutoConfig.from_pretrained(BASE, trust_remote_code=True)
print(f"model_type={cfg.model_type} layers={cfg.num_hidden_layers} "
      f"experts={getattr(cfg,'num_local_experts','?')} top_k={getattr(cfg,'num_experts_per_tok','?')}", flush=True)

with init_empty_weights():
    m = AutoModelForCausalLM.from_config(cfg, torch_dtype=torch.bfloat16)

l0 = m.model.layers[0]
moe_attr = "block_sparse_moe" if hasattr(l0, "block_sparse_moe") else ("mlp" if hasattr(l0, "mlp") else "?")
print(f"layer0 moe attr: {moe_attr} ({type(getattr(l0, moe_attr, None)).__name__})", flush=True)

model_keys = set(n for n, _ in m.named_parameters())
model_keys |= set(n for n, _ in m.named_buffers())

idx = json.load(open(BASE + "/model.safetensors.index.json"))
ckpt_keys = set(idx["weight_map"].keys())
missing = sorted(k for k in ckpt_keys if k not in model_keys)
ratio = (len(ckpt_keys) - len(missing)) / len(ckpt_keys)

print(f"ckpt_keys={len(ckpt_keys)} model_keys={len(model_keys)} missing={len(missing)} match={ratio:.4f}", flush=True)
print("missing sample:", missing[:8], flush=True)
# 전문가 키 존재 여부(핵심)
expert_ckpt = [k for k in ckpt_keys if "experts.0.w1" in k][:2]
print("ckpt expert sample:", expert_ckpt, flush=True)
print("expert key in model?:", all(k in model_keys for k in expert_ckpt), flush=True)

verdict = "COMPATIBLE" if ratio == 1.0 else "INCOMPATIBLE"
print(f"VERDICT: {verdict}", flush=True)
sys.exit(0 if ratio == 1.0 else 1)
