import torch
from collections import Counter
from transformers import AutoConfig, AutoModelForCausalLM
from accelerate import init_empty_weights
BASE="/run/media/user/새 볼륨/mixtral-8x22b-v0.1"
cfg=AutoConfig.from_pretrained(BASE, trust_remote_code=True)
with init_empty_weights():
    m=AutoModelForCausalLM.from_config(cfg, torch_dtype=torch.bfloat16)
bufs=[(n,b) for n,b in m.named_buffers()]
print("총 buffer:", len(bufs))
print("device 분포:", dict(Counter(('meta' if b.is_meta else str(b.device)) for _,b in bufs)))
nonmeta_noncuda=[(n,str(b.device)) for n,b in bufs if not b.is_meta and b.device.type!='cuda']
print("CPU(비meta) buffer 수:", len(nonmeta_noncuda))
print("  샘플:", nonmeta_noncuda[:8])
inv=[(n,('meta' if b.is_meta else str(b.device))) for n,b in bufs if 'inv_freq' in n or 'rotary' in n]
print("rotary/inv_freq buffer:", len(inv), "| 샘플:", inv[:4])
