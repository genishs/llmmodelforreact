# -*- coding: utf-8 -*-
"""
모델 싱글턴 로더 - API 서버와 MCP 서버 공용.

7B LoRA(v3)를 DirectML에 fp16 스트리밍 적재. (1.5B를 호스트 RAM에 fp32로 올리던
구버전은 7B에 부적합 → dml_loader 스트리밍 사용.)
모든 진단 로그는 stderr로 보낸다(MCP는 stdout으로 프로토콜 통신).
"""
import os
import sys

import torch
import torch_directml
from peft import LoraConfig, get_peft_model, set_peft_model_state_dict, TaskType, PeftConfig
import safetensors.torch as st

from dml_loader import stream_load_to_device

# 프로젝트 루트(= src의 상위) 기준 절대 경로
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_MODEL_PATH = os.path.join(_ROOT, "models", "base", "qwen2.5-coder-7b")
ADAPTER_PATH = os.path.join(_ROOT, "models", "qwen-react-lora-7b-v3")
DTYPE = torch.float16

_model = None
_tokenizer = None
_device = None


def _err(msg):
    print(msg, file=sys.stderr, flush=True)


def get_model():
    global _model, _tokenizer, _device
    if _model is not None:
        return _model, _tokenizer, _device

    from transformers import AutoTokenizer
    _err("[model_loader] 7B v3 로드 시작...")
    _device = torch_directml.device()

    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    model = stream_load_to_device(BASE_MODEL_PATH, _device, DTYPE)

    # 어댑터 설정/가중치 적용 (fp16로 캐스팅해 베이스와 dtype 일치)
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
    model.eval()
    model.config.use_cache = True

    _model = model
    _err("[model_loader] 준비 완료 (7B fp16 + v3 어댑터)")
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
