# -*- coding: utf-8 -*-
"""
긴-입력 붕괴(EgovPaging 840tok 빈 출력) 진단 + 추론측 수정 시도 (DirectML/fp16).

가설: 모델이 0토큰을 내는 게 아니라, 긴 OOD 입력에서 첫머리에 특수토큰(FIM류)을 뱉어
후처리가 잘라 빈 문자열이 된다. → 특수토큰 억제 + min_new_tokens로 풀릴 수 있다.

3단계로 같은 입력을 비교:
  [A] RAW       : 억제 없음, skip_special_tokens=False → 실제 뱉는 토큰을 그대로 관찰(진단)
  [B] 기존방식   : FIM에서 잘라내기(현 verify 스크립트와 동일) → 빈 출력 재현
  [C] 수정       : suppress_tokens(특수토큰 전부) + min_new_tokens=64 + begin_suppress

실행:
  python scripts/diagnose_long_dml.py --adapter models/qwen-react-lora-7b-seq640
"""
import os, sys, io, time, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import torch
import torch_directml
from transformers import AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType, set_peft_model_state_dict
import safetensors.torch as st

from train_directml import stream_load_to_device, load_config

ROOT = Path(__file__).resolve().parent.parent
FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>"]
EGOV = Path("C:/Users/user/Documents/workspace/twinspace_platform/egovGeoportal/src/components/EgovPaging.jsx")
INSTR = "이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="models/qwen-react-lora-7b-seq640")
    ap.add_argument("--max-new", type=int, default=400)
    ap.add_argument("--min-new", type=int, default=64)
    args = ap.parse_args()

    config = load_config()
    base = config["model"]["base_model"]
    device = torch_directml.device()
    dtype = torch.float16

    code = EGOV.read_text(encoding="utf-8")
    prompt = f"### Instruction:\n{INSTR}\n\n### Input:\n{code}\n\n### Response:\n"

    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print(f"[로드] 베이스 7B fp16: {base}", flush=True)
    model = stream_load_to_device(base, device, dtype)
    lc = config["lora"]
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=lc["r"], lora_alpha=lc["lora_alpha"],
        target_modules=lc["target_modules"], lora_dropout=lc["lora_dropout"], bias=lc["bias"]))
    sd_path = str(ROOT / args.adapter / "adapter_model.safetensors")
    sd = {k: v.to(dtype) for k, v in st.load_file(sd_path).items()}
    set_peft_model_state_dict(model, sd)
    model = model.to(device)
    model.eval(); model.config.use_cache = True
    print(f"[로드] 어댑터: {args.adapter} ({len(sd)} 텐서)", flush=True)

    # 억제할 특수토큰 id 집합 (FIM류 + 모든 added/special). eos는 별도(min_new_tokens가 관리)
    special_ids = set()
    for t in FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            special_ids.add(tid)
    for tid in (tok.all_special_ids or []):
        special_ids.add(int(tid))
    # added vocab(특수 추가토큰)도 포함
    for t, tid in (tok.get_added_vocab() or {}).items():
        if t.startswith("<|") or t.startswith("###"):
            special_ids.add(int(tid))
    eos = tok.eos_token_id
    suppress = sorted(i for i in special_ids if i != eos)
    print(f"[설정] 억제 토큰 {len(suppress)}개, eos={eos}", flush=True)

    inputs = tok(prompt, return_tensors="pt")
    in_len = inputs["input_ids"].shape[1]
    inputs = {k: v.to(device) for k, v in inputs.items()}
    print(f"[입력] EgovPaging.jsx = {in_len} tokens\n", flush=True)

    def gen(**kw):
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**inputs, pad_token_id=tok.eos_token_id, **kw)
        g = out[0][in_len:]
        return g, time.time() - t0

    # [A] RAW 진단 — 무엇을 뱉는가
    g, dt = gen(max_new_tokens=40, do_sample=False, repetition_penalty=1.1)
    print("="*72 + "\n[A] RAW (억제無, skip_special=False) — 첫 40토큰 원시 관찰\n" + "-"*72)
    print("토큰ID:", g[:20].tolist())
    print("디코드(특수토큰 표시):", repr(tok.decode(g, skip_special_tokens=False)[:300]))

    # [B] 기존 방식 재현 — FIM 잘라내기
    g, dt = gen(max_new_tokens=args.max_new, do_sample=False, repetition_penalty=1.1,
                eos_token_id=sorted(special_ids | {eos}))
    txt = tok.decode(g, skip_special_tokens=True)
    for m in FIM:
        j = txt.find(m)
        if j != -1: txt = txt[:j]
    txt = txt.strip()
    print("\n" + "="*72 + f"\n[B] 기존방식(FIM정지) → {len(g)}tok\n" + "-"*72)
    print(txt if txt else "(빈 출력 0자)")

    # [C] 수정 — 특수토큰 억제 + min_new_tokens
    g, dt = gen(max_new_tokens=args.max_new, min_new_tokens=args.min_new, do_sample=False,
                repetition_penalty=1.1, suppress_tokens=suppress, eos_token_id=eos)
    txt = tok.decode(g, skip_special_tokens=True).strip()
    print("\n" + "="*72 + f"\n[C] 수정(특수토큰억제+min_new={args.min_new}) → {len(g)}tok / {dt:.1f}s\n" + "-"*72)
    print(txt if txt else "(빈 출력 0자)")


if __name__ == "__main__":
    main()
