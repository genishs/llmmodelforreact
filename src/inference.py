"""
학습된 모델 추론 스크립트
실행: python src/inference.py
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


def get_device():
    try:
        import torch_directml
        return torch_directml.device(), "directml"
    except ImportError:
        pass
    if torch.cuda.is_available():
        return torch.device("cuda"), "cuda"
    return torch.device("cpu"), "cpu"


def load_model(base_model_name, lora_path=None):
    device, device_type = get_device()
    dtype = torch.float32 if device_type in ["directml", "cpu"] else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=dtype,
        trust_remote_code=True,
        device_map=None if device_type == "directml" else "auto",
    )

    if lora_path:
        print(f"LoRA 가중치 로드: {lora_path}")
        model = PeftModel.from_pretrained(model, lora_path)

    model = model.to(device)
    model.eval()
    return model, tokenizer, device


def generate(model, tokenizer, device, instruction, input_text="", max_new_tokens=512):
    if input_text:
        prompt = (
            f"### Instruction:\n{instruction}\n\n"
            f"### Input:\n{input_text}\n\n"
            f"### Response:\n"
        )
    else:
        prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

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
        skip_special_tokens=True
    )
    return response.strip()


def interactive_mode(model, tokenizer, device):
    print("\n=== React 코딩 어시스턴트 ===")
    print("종료: 'quit' 입력\n")

    while True:
        instruction = input("질문: ").strip()
        if instruction.lower() in ["quit", "exit", "q"]:
            break
        if not instruction:
            continue

        input_text = input("추가 컨텍스트 (없으면 Enter): ").strip()

        print("\n[생성 중...]\n")
        response = generate(model, tokenizer, device, instruction, input_text)
        print(f"[응답]\n{response}\n")
        print("-" * 50)


if __name__ == "__main__":
    BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    LORA_PATH = "./models/qwen-react-lora"  # 학습 후 사용

    import os
    lora_path = LORA_PATH if os.path.exists(LORA_PATH) else None

    if not lora_path:
        print("[정보] LoRA 가중치 없음 → 베이스 모델로 실행")

    model, tokenizer, device = load_model(BASE_MODEL, lora_path)
    interactive_mode(model, tokenizer, device)
