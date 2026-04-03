"""
LoRA fine-tuning 스크립트
모델: Qwen2.5-Coder-7B (48GB GPU 기준)

실행: python src/train.py
"""

import os
import yaml
import torch
from pathlib import Path
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, TaskType


def load_config(config_path="./config/training_config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_device():
    """학습 디바이스 선택.

    7B FP32 모델은 CPU 로딩(28GB) + DirectML 복사(28GB) = 56GB 순간 필요.
    통합 메모리 환경에서 DirectML OOM 발생하므로 학습은 CPU로 수행.
    추론/서빙은 model_loader.py 에서 DirectML 사용.
    """
    # CUDA가 있으면 CUDA 사용 (일반 GPU 서버 환경)
    if torch.cuda.is_available():
        print(f"[디바이스] CUDA 사용: {torch.cuda.get_device_name(0)}")
        return torch.device("cuda"), "cuda"

    # AMD 통합 메모리 환경: 학습은 CPU (64GB 풀 전체 활용)
    try:
        import torch_directml
        dml_name = torch_directml.device_name(0)
        print(f"[디바이스] CPU 학습 모드 (AMD 통합 메모리 환경)")
        print(f"  GPU({dml_name})는 추론 서빙에 사용됩니다.")
        print(f"  이유: 7B FP32 학습 시 CPU+GPU 동시 56GB 필요 → DirectML OOM")
    except ImportError:
        print("[디바이스] CPU 사용")

    return torch.device("cpu"), "cpu"


def load_model_and_tokenizer(model_name, device_type):
    print(f"\n[모델 로드] {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # DirectML은 float32 사용 (bf16/fp16 미지원)
    dtype = torch.float32 if device_type in ["directml", "cpu"] else torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=dtype,
        trust_remote_code=True,
        device_map=None if device_type in ["directml", "cpu"] else "auto",
        # meta device 비활성화: PEFT backward pass와 충돌 방지
        # CPU 64GB 환경에서는 메모리 여유가 있으므로 safe
        low_cpu_mem_usage=False,
    )

    print(f"  파라미터 수: {sum(p.numel() for p in model.parameters()):,}")
    return model, tokenizer


def apply_lora(model, config):
    lora_cfg = config["lora"]
    train_cfg = config["training"]

    if train_cfg.get("gradient_checkpointing", False):
        model.gradient_checkpointing_enable()
        # PEFT + gradient checkpointing 호환성을 위해 필요
        model.enable_input_require_grads()

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        target_modules=lora_cfg["target_modules"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias=lora_cfg["bias"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


def tokenize_dataset(dataset, tokenizer, max_length):
    def tokenize(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
    return dataset.map(tokenize, batched=True, remove_columns=["text"])


def main():
    # 설정 로드
    config = load_config()
    print("[설정 로드 완료]")

    # 디바이스 확인
    device, device_type = get_device()

    # 모델 로드
    model_name = config["model"]["base_model"]
    model, tokenizer = load_model_and_tokenizer(model_name, device_type)

    # LoRA 적용
    model = apply_lora(model, config)

    # DirectML의 경우 모델을 device로 이동
    if device_type == "directml":
        model = model.to(device)

    # 데이터 로드
    data_cfg = config["data"]
    print(f"\n[데이터 로드]")
    train_dataset = load_dataset(
        "json", data_files=data_cfg["train_file"], split="train"
    )
    val_dataset = load_dataset(
        "json", data_files=data_cfg["val_file"], split="train"
    )
    print(f"  학습: {len(train_dataset)}개, 검증: {len(val_dataset)}개")

    # 토크나이징
    max_length = data_cfg["max_seq_length"]
    train_dataset = tokenize_dataset(train_dataset, tokenizer, max_length)
    val_dataset = tokenize_dataset(val_dataset, tokenizer, max_length)

    # 학습 설정
    train_cfg = config["training"]
    Path(train_cfg["output_dir"]).mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=train_cfg["output_dir"],
        num_train_epochs=train_cfg["num_train_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        warmup_ratio=train_cfg["warmup_ratio"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        logging_steps=train_cfg["logging_steps"],
        save_steps=train_cfg["save_steps"],
        save_total_limit=train_cfg["save_total_limit"],
        fp16=train_cfg["fp16"],
        bf16=train_cfg["bf16"],
        gradient_checkpointing=train_cfg.get("gradient_checkpointing", False),
        dataloader_num_workers=train_cfg["dataloader_num_workers"],
        remove_unused_columns=train_cfg["remove_unused_columns"],
        eval_strategy="steps",
        eval_steps=train_cfg["save_steps"],
        load_best_model_at_end=True,
        report_to="none",  # wandb 비활성화
    )

    # 데이터 콜레이터
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    # 학습
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
    )

    print("\n[학습 시작]")
    trainer.train()

    # 저장
    output_path = train_cfg["output_dir"]
    trainer.save_model(output_path)
    tokenizer.save_pretrained(output_path)
    print(f"\n[완료] 모델 저장: {output_path}")


if __name__ == "__main__":
    main()
