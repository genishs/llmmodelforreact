# -*- coding: utf-8 -*-
"""
모델 싱글턴 로더 - API 서버와 MCP 서버 공용. 디바이스 자동 감지.

디바이스 우선순위: CUDA(NVIDIA) > DirectML(AMD/Win) > CPU.

서빙 모델 선택 (환경변수 REACT_ASSISTANT_MODEL):
  - "1.5b" (기본): Qwen2.5-Coder-1.5B + qwen-react-lora-v4.
  - "7b": Qwen2.5-Coder-7B + qwen-react-lora-7b-v4.
      · CUDA: 4비트 양자화(bitsandbytes)로 ~5GB → 8GB GPU(예: RTX 4060)에서 동작.
      · DirectML: fp16 스트리밍(~14GB, 48GB VRAM 카브아웃 환경 전용).

모든 진단 로그는 stderr로 보낸다(MCP는 stdout으로 프로토콜 통신).
"""
import os
import sys
from pathlib import Path

import torch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL = os.environ.get("REACT_ASSISTANT_MODEL", "1.5b").lower()

if _MODEL == "7b":
    BASE_MODEL_PATH = os.path.join(_ROOT, "models", "base", "qwen2.5-coder-7b")
    ADAPTER_PATH = os.path.join(_ROOT, "models", "qwen-react-lora-7b-v4")
else:
    BASE_MODEL_PATH = os.path.join(_ROOT, "models", "base", "qwen2.5-coder-1.5b")
    ADAPTER_PATH = os.path.join(_ROOT, "models", "qwen-react-lora-v4")

_model = None
_tokenizer = None
_device = None


def _err(msg):
    print(msg, file=sys.stderr, flush=True)


def _pick_device():
    """(device, kind) 반환. kind: 'cuda' | 'dml' | 'cpu'."""
    if torch.cuda.is_available():
        return torch.device("cuda"), "cuda"
    try:
        import torch_directml
        return torch_directml.device(), "dml"
    except ImportError:
        return torch.device("cpu"), "cpu"


def _load_cuda(model_cls, tok):
    """CUDA: 1.5b는 fp16, 7b는 4비트 양자화."""
    from peft import PeftModel
    if _MODEL == "7b":
        from transformers import BitsAndBytesConfig
        bnb = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
        )
        model = model_cls.from_pretrained(
            BASE_MODEL_PATH, quantization_config=bnb, device_map="auto",
            trust_remote_code=True,
        )
    else:
        model = model_cls.from_pretrained(
            BASE_MODEL_PATH, torch_dtype=torch.float16, device_map="cuda",
            trust_remote_code=True,
        )
    if Path(ADAPTER_PATH).exists():
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    return model


def _load_dml(model_cls, device):
    """DirectML: 7b는 스트리밍 fp16, 1.5b는 단순 fp16."""
    from peft import PeftModel
    if _MODEL == "7b":
        from peft import LoraConfig, get_peft_model, set_peft_model_state_dict, TaskType, PeftConfig
        import safetensors.torch as st
        from dml_loader import stream_load_to_device
        model = stream_load_to_device(BASE_MODEL_PATH, device, torch.float16)
        pc = PeftConfig.from_pretrained(ADAPTER_PATH)
        model = get_peft_model(model, LoraConfig(
            task_type=TaskType.CAUSAL_LM, r=pc.r, lora_alpha=pc.lora_alpha,
            target_modules=pc.target_modules, lora_dropout=pc.lora_dropout, bias=pc.bias,
        ))
        sd = {k: v.to(torch.float16) for k, v in
              st.load_file(os.path.join(ADAPTER_PATH, "adapter_model.safetensors")).items()}
        set_peft_model_state_dict(model, sd)
        return model.to(device)
    else:
        model = model_cls.from_pretrained(
            BASE_MODEL_PATH, dtype=torch.float16, trust_remote_code=True)
        if Path(ADAPTER_PATH).exists():
            model = PeftModel.from_pretrained(model, ADAPTER_PATH)
        return model.to(device)


def _load_cpu(model_cls, device):
    from peft import PeftModel
    model = model_cls.from_pretrained(
        BASE_MODEL_PATH, dtype=torch.float32, trust_remote_code=True)
    if Path(ADAPTER_PATH).exists():
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    return model.to(device)


def get_model():
    global _model, _tokenizer, _device
    if _model is not None:
        return _model, _tokenizer, _device

    from transformers import AutoModelForCausalLM, AutoTokenizer
    _device, kind = _pick_device()
    _err(f"[model_loader] 디바이스={kind}, 모델={_MODEL} 로드 시작...")

    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    if kind == "cuda":
        model = _load_cuda(AutoModelForCausalLM, _tokenizer)
    elif kind == "dml":
        model = _load_dml(AutoModelForCausalLM, _device)
    else:
        model = _load_cpu(AutoModelForCausalLM, _device)

    model.eval()
    model.config.use_cache = True
    _model = model
    _err(f"[model_loader] 준비 완료 (device={kind}, model={_MODEL})")
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
    # 4비트(device_map) 모델은 입력을 모델의 첫 디바이스로. 그 외는 _device로.
    target = getattr(model, "device", device)
    inputs = {k: v.to(target) for k, v in inputs.items()}

    # 특수 토큰 누수 방지.
    # ★ 긴 입력(840tok 등)에서 모델이 <|im_start|>(챗템플릿 토큰)를 도배 후 즉시 eos로
    #   빈 출력이 되는 붕괴를 실측(2026-06-17). eos로만 막던 기존 방식으론 못 잡혀서,
    #   <|im_start|> 포함 모든 특수/FIM 토큰을 suppress_tokens로 '생성 자체를 차단'하고
    #   min_new_tokens로 조기 정지를 막는다. (eos=<|im_end|>는 정지용으로 남김)
    eos_id = tokenizer.eos_token_id
    suppress_ids = set(int(i) for i in (tokenizer.all_special_ids or []))
    for tk in ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
               "<|repo_name|>", "<|file_sep|>", "<|endoftext|>", "<|im_start|>"]:
        tid = tokenizer.convert_tokens_to_ids(tk)
        if isinstance(tid, int) and tid >= 0 and tid != tokenizer.unk_token_id:
            suppress_ids.add(int(tid))
    suppress_ids.discard(int(eos_id))           # eos는 정지에 필요 → 억제 제외
    suppress_tokens = sorted(suppress_ids)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            min_new_tokens=24,                  # 즉시-eos 붕괴 방지
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=eos_id,
            suppress_tokens=suppress_tokens,
            repetition_penalty=1.1,
        )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )
    # FIM/특수 토큰은 'added but non-special'이라 디코드 텍스트에 문자열로 남을 수 있음 → 잘라냄
    for marker in ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
                   "<|repo_name|>", "<|file_sep|>", "<|endoftext|>"]:
        idx = response.find(marker)
        if idx != -1:
            response = response[:idx]
    return response.strip()
