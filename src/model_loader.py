# -*- coding: utf-8 -*-
"""
모델 싱글턴 로더 - API 서버와 MCP 서버가 공통으로 사용
"""

import torch
import torch_directml
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from pathlib import Path

BASE_MODEL_PATH = "./models/base/qwen2.5-coder-1.5b"
LORA_PATH = "./models/qwen-react-lora-v4"

_model = None
_tokenizer = None
_device = None


def get_model():
    global _model, _tokenizer, _device

    if _model is not None:
        return _model, _tokenizer, _device

    print("[모델 로드 중...]")
    _device = torch_directml.device()

    _tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_PATH, trust_remote_code=True
    )
    _tokenizer.pad_token = _tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        dtype=torch.float32,
        trust_remote_code=True,
    )

    lora_path = Path(LORA_PATH)
    if lora_path.exists():
        print(f"[LoRA 로드] {LORA_PATH}")
        model = PeftModel.from_pretrained(model, LORA_PATH)

    _model = model.to(_device)
    _model.eval()
    print("[모델 준비 완료]")
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
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
        )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )
    return response.strip()
