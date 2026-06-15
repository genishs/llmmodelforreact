# -*- coding: utf-8 -*-
"""
모델 싱글턴 로더 - API 서버와 MCP 서버 공용.

환경에 따라 서빙 모델 선택 (환경변수 REACT_ASSISTANT_MODEL):
  - "1.5b" (기본): Qwen2.5-Coder-1.5B + qwen-react-lora-v4. 단순 로딩(tied-weight),
    VRAM ~6GB. 카브아웃이 작을 때(재부팅으로 VRAM 축소 등)도 동작.
  - "7b": Qwen2.5-Coder-7B + qwen-react-lora-7b-v4. dml_loader 스트리밍 fp16,
    VRAM ~31GB 필요(48GB VRAM 카브아웃 환경에서만).

모든 진단 로그는 stderr로 보낸다(MCP는 stdout으로 프로토콜 통신).
"""
import os
import sys
from pathlib import Path

import torch
import torch_directml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL = os.environ.get("REACT_ASSISTANT_MODEL", "1.5b").lower()

if _MODEL == "7b":
    BASE_MODEL_PATH = os.path.join(_ROOT, "models", "base", "qwen2.5-coder-7b")
    ADAPTER_PATH = os.path.join(_ROOT, "models", "qwen-react-lora-7b-v4")
    DTYPE = torch.float16
    STREAM = True
else:
    BASE_MODEL_PATH = os.path.join(_ROOT, "models", "base", "qwen2.5-coder-1.5b")
    ADAPTER_PATH = os.path.join(_ROOT, "models", "qwen-react-lora-v4")
    DTYPE = torch.float16  # VRAM 축소 환경(~8GB)에서 여유 확보(3GB)
    STREAM = False

_model = None
_tokenizer = None
_device = None


def _err(msg):
    print(msg, file=sys.stderr, flush=True)


def get_model():
    global _model, _tokenizer, _device
    if _model is not None:
        return _model, _tokenizer, _device

    from transformers import AutoModelForCausalLM, AutoTokenizer
    _err(f"[model_loader] 모델 로드 시작 ({_MODEL}, stream={STREAM})...")
    _device = torch_directml.device()

    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    if STREAM:
        # 7B: VRAM 직접 스트리밍 + 어댑터 fp16 적용
        from peft import LoraConfig, get_peft_model, set_peft_model_state_dict, TaskType, PeftConfig
        import safetensors.torch as st
        from dml_loader import stream_load_to_device

        model = stream_load_to_device(BASE_MODEL_PATH, _device, DTYPE)
        pc = PeftConfig.from_pretrained(ADAPTER_PATH)
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM, r=pc.r, lora_alpha=pc.lora_alpha,
            target_modules=pc.target_modules, lora_dropout=pc.lora_dropout, bias=pc.bias,
        )
        model = get_peft_model(model, lora_config)
        sd = {k: v.to(DTYPE) for k, v in
              st.load_file(os.path.join(ADAPTER_PATH, "adapter_model.safetensors")).items()}
        set_peft_model_state_dict(model, sd)
        model = model.to(_device)
    else:
        # 1.5B: 단순 로딩(호스트→디바이스). tied-weight 모델에 안전.
        from peft import PeftModel
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_PATH, dtype=DTYPE, trust_remote_code=True,
        )
        if Path(ADAPTER_PATH).exists():
            _err(f"[model_loader] LoRA 적용: {ADAPTER_PATH}")
            model = PeftModel.from_pretrained(model, ADAPTER_PATH)
        model = model.to(_device)

    model.eval()
    model.config.use_cache = True
    _model = model
    _err(f"[model_loader] 준비 완료 ({_MODEL})")
    return _model, _tokenizer, _device


def generate(instruction: str, input_text: str = "", max_new_tokens: int = 512) -> str:
    model, tokenizer, device = get_model()

    if input_text:
        prompt = (
            f"### Instruction:\n{instruction}\n\n"
            f"### Input:\n{input_text}\n\n"
            f"### Response:\n"
        )
    else:
        prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"

    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
        )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )
    return response.strip()
