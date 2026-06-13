# -*- coding: utf-8 -*-
"""
DirectML 스트리밍 로더 (서빙용, stdout 오염 없음).

train_directml.py의 로더와 동일 로직이지만 로그를 stderr로 보낸다.
MCP 서버는 stdout으로 프로토콜을 주고받으므로 stdout에 절대 찍으면 안 됨.
DirectML 제약: bf16 미지원(호스트서 fp16 변환), 실사용 VRAM ~31GB, safetensors가
디바이스 직접 로드 불가 → 텐서 단위로 호스트 경유해 적재.
"""
import os
import sys
import glob
import json
import time
import gc

import torch
import psutil
from transformers import AutoConfig, AutoModelForCausalLM
from accelerate import init_empty_weights
from accelerate.utils import set_module_tensor_to_device
from safetensors import safe_open

RAM_GUARD_GB = 0.5


def ram_avail_gb():
    return psutil.virtual_memory().available / 1024**3


def _err(msg):
    print(msg, file=sys.stderr, flush=True)


def stream_load_to_device(model_path, device, dtype, log=_err):
    """safetensors 텐서를 지정 dtype으로 변환해 DirectML 디바이스에 직접 적재."""
    cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(cfg, torch_dtype=dtype)
    model.tie_weights()

    idx = os.path.join(model_path, "model.safetensors.index.json")
    if os.path.exists(idx):
        with open(idx, "r", encoding="utf-8") as f:
            wmap = json.load(f)["weight_map"]
        items = [(n, os.path.join(model_path, s)) for n, s in wmap.items()]
    else:
        shard = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))[0]
        with safe_open(shard, framework="pt", device="cpu") as f:
            items = [(n, shard) for n in f.keys()]

    log(f"[loader] {len(items)} tensors 적재 시작 (host RAM {ram_avail_gb():.1f}GB)")
    loaded, t0 = 0, time.time()
    for name, shard in items:
        if ram_avail_gb() < RAM_GUARD_GB:
            raise MemoryError(
                f"가용 RAM {ram_avail_gb():.2f}GB < {RAM_GUARD_GB}GB 가드. "
                f"다른 앱을 닫고 재시도하세요."
            )
        with safe_open(shard, framework="pt", device="cpu") as f:
            t = f.get_tensor(name).to(dtype)
        set_module_tensor_to_device(model, name, device, value=t)
        del t
        loaded += 1
        if loaded % 100 == 0:
            gc.collect()

    remaining = [n for n, p in model.named_parameters() if p.is_meta]
    if remaining:
        raise RuntimeError(f"적재 안 된 meta 텐서 {len(remaining)}개: {remaining[:5]}")
    log(f"[loader] 적재 완료: {loaded} tensors, {time.time()-t0:.1f}s, "
        f"host RAM {ram_avail_gb():.1f}GB")
    return model
