# -*- coding: utf-8 -*-
"""
eval_harness.py(4060/CUDA)의 DirectML/fp16 버전.

★ 채점 로직(TASKS·score_output·balanced·FIM)은 eval_harness.py에서 그대로 import해
   점수 기준을 100% 동일하게 유지한다. 차이는 모델 로딩뿐:
   - 4060: 4비트 nf4 베이스 (eval_harness.py)
   - 8060: fp16 스트리밍 베이스 (이 파일) — 실제 서빙과 같은 정밀도
   egov 실파일 경로도 이 장비(장비#1)에 맞게 오버라이드.

실행:
  python scripts/eval_harness_dml.py --adapter models/qwen-react-lora-7b-seq640 --label 8060-seq640-r16
결과: eval_results/<label>.json + 표 출력
"""
import argparse, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import torch
import torch_directml
from transformers import AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType, set_peft_model_state_dict
import safetensors.torch as st

from train_directml import stream_load_to_device, load_config
import eval_harness as EH   # 채점 로직·태스크 재사용(동일 기준)

# 이 장비(장비#1)의 egovGeoportal 경로로 오버라이드
EH.EGOV = Path("C:/Users/user/Documents/workspace/twinspace_platform/egovGeoportal/src")
BASE = str(ROOT / "models" / "base" / "qwen2.5-coder-7b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-new", type=int, default=400)
    args = ap.parse_args()

    config = load_config()
    device = torch_directml.device(); dtype = torch.float16
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print(f"[로드] fp16 스트리밍 + 어댑터 {args.adapter}", flush=True)
    model = stream_load_to_device(BASE, device, dtype)
    lc = config["lora"]
    acfg = json.loads((ROOT / args.adapter / "adapter_config.json").read_text())
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=acfg.get("r", lc["r"]),
        lora_alpha=acfg.get("lora_alpha", lc["lora_alpha"]),
        target_modules=acfg.get("target_modules", lc["target_modules"]),
        lora_dropout=lc["lora_dropout"], bias=lc["bias"]))
    sd = {k: v.to(dtype) for k, v in st.load_file(str(ROOT / args.adapter / "adapter_model.safetensors")).items()}
    set_peft_model_state_dict(model, sd)
    model = model.to(device); model.eval(); model.config.use_cache = True

    eos_id = tok.eos_token_id
    suppress = set(int(i) for i in (tok.all_special_ids or []))
    for t in EH.FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            suppress.add(int(tid))
    suppress.discard(int(eos_id))
    suppress_tokens = sorted(suppress)

    rows, grand = [], 0.0
    for name, instr, inp, expects in EH.TASKS:
        if inp:
            code = (EH.EGOV / inp).read_text(encoding="utf-8")
            prompt = f"### Instruction:\n{instr}\n\n### Input:\n{code}\n\n### Response:\n"
        else:
            prompt = f"### Instruction:\n{instr}\n\n### Response:\n"
        inputs = {k: v.to(device) for k, v in tok(prompt, return_tensors="pt").items()}
        in_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new, min_new_tokens=24,
                                 do_sample=False, pad_token_id=eos_id, eos_token_id=eos_id,
                                 suppress_tokens=suppress_tokens, repetition_penalty=1.1)
        gen = out[0][in_len:]
        raw = tok.decode(gen, skip_special_tokens=False)
        clean = tok.decode(gen, skip_special_tokens=True)
        for m in EH.FIM:
            j = clean.find(m)
            if j != -1:
                clean = clean[:j]
        sc = EH.score_output(raw, clean, expects)
        sc["task"] = name; sc["in_tok"] = in_len
        rows.append(sc); grand += sc["total"]
        print(f"[{name:16s}] total={sc['total']:.2f}  ne={sc['nonempty']} sp={sc['no_special']} "
              f"hash={sc['no_hash']} bal={sc['balanced']} exp={sc['expected']}  (in={in_len}tok)", flush=True)

    maxp = len(EH.TASKS) * 5
    pct = round(100 * grand / maxp, 1)
    print(f"\n[{args.label}] TOTAL {grand:.2f}/{maxp} = {pct}%", flush=True)
    outdir = ROOT / "eval_results"; outdir.mkdir(exist_ok=True)
    (outdir / f"{args.label}.json").write_text(
        json.dumps({"label": args.label, "adapter": args.adapter, "base": "fp16-directml",
                    "total": grand, "max": maxp, "pct": pct, "tasks": rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved → eval_results/{args.label}.json", flush=True)


if __name__ == "__main__":
    main()
