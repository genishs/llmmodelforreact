# -*- coding: utf-8 -*-
"""
실제 프로젝트 파일에 어댑터를 적용해보는 테스트 (CUDA, 4비트 베이스).

egovGeoportal 같은 실코드(JSX)를 입력으로 주고 변환/리뷰를 시킨다.
model_loader와 같은 Instruction/Input/Response 포맷.

실행:
  python scripts/test_on_file.py --adapter models/qwen-react-lora-7b-qlora \
      --file <abs.jsx> --instruction "이 컴포넌트를 TypeScript로 변환해줘. props 타입을 정의해줘."
"""
import argparse
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
BASE = str(ROOT / "models" / "base" / "qwen2.5-coder-7b")
FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--instruction", required=True)
    ap.add_argument("--max-new", type=int, default=512)
    args = ap.parse_args()

    code = Path(args.file).read_text(encoding="utf-8")
    prompt = (f"### Instruction:\n{args.instruction}\n\n"
              f"### Input:\n{code}\n\n### Response:\n")

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, device_map="auto", trust_remote_code=True)
    model = PeftModel.from_pretrained(model, str(ROOT / args.adapter))
    model.eval()

    stop_ids = [tok.eos_token_id]
    for t in FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            stop_ids.append(tid)

    inputs = {k: v.to(model.device) for k, v in tok(prompt, return_tensors="pt").items()}
    in_len = inputs["input_ids"].shape[1]
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=args.max_new, do_sample=False,
                             pad_token_id=tok.eos_token_id, eos_token_id=list(dict.fromkeys(stop_ids)),
                             repetition_penalty=1.1)
    text = tok.decode(out[0][in_len:], skip_special_tokens=True)
    for m in FIM:
        i = text.find(m)
        if i != -1:
            text = text[:i]
    print(f"\n{'='*70}\n[{args.adapter}]  input_tokens={in_len}\nINSTRUCTION: {args.instruction}\nFILE: {Path(args.file).name}\n{'='*70}")
    print(text.strip())


if __name__ == "__main__":
    main()
