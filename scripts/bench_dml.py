# -*- coding: utf-8 -*-
"""
공유 벤치마크 B1~B6 채점 하니스 (DirectML/fp16, im_start 억제 수정 포함).

경쟁 라운드마다 어댑터를 이걸로 돌려 6개 프롬프트 출력을 docs/bench-outputs/<name>.md에
저장한다. 같은 그리디/억제 설정이라 어댑터 간 비교가 공정하다.

실행:
  python scripts/bench_dml.py --adapter models/qwen-react-lora-7b-seq640
  python scripts/bench_dml.py --adapter models/qwen-react-lora-7b-seq640-r32 --tag seq640-r32
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
COMP = Path("C:/Users/user/Documents/workspace/twinspace_platform/egovGeoportal/src/components")
FIM = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|fim_pad|>",
       "<|repo_name|>", "<|file_sep|>", "<|endoftext|>", "<|im_start|>"]

BUGGY = """function Timer() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setCount(count + 1), 1000);
  }, []);
  return <div>{count}</div>;
}"""


def load_file(name):
    p = COMP / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--max-new", type=int, default=420)
    args = ap.parse_args()
    tag = args.tag or Path(args.adapter).name

    egov840 = load_file("EgovPaging.jsx")
    egovMed = load_file("EgovInfoPopup.jsx")
    tests = [
        ("B1 카운터(EN) 정지품질", "Write a React counter component using useState. Include increment and reset buttons.", ""),
        ("B2 useDebounce(힌트無,TS) 제네릭", "Create a custom hook useDebounce(value, delay) in TypeScript.", ""),
        ("B3 TanStack 무한스크롤(KR)", "TanStack Query의 useInfiniteQuery로 무한 스크롤 상품 목록을 구현해줘. Product 타입과 로딩/에러 처리를 포함해줘.", ""),
        ("B4 EgovPaging 840tok→TS", "이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘.", egov840),
        ("B5 EgovInfoPopup 중간→TS", "이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘.", egovMed),
        ("B6 버그 useEffect 리뷰·수정", "이 코드의 버그를 찾아 수정하고 이유를 설명해줘.", BUGGY),
    ]

    config = load_config()
    base = config["model"]["base_model"]
    device = torch_directml.device(); dtype = torch.float16
    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print(f"[로드] 베이스 7B fp16 + 어댑터 {args.adapter}", flush=True)
    model = stream_load_to_device(base, device, dtype)
    lc = config["lora"]
    # 어댑터 config에서 r/target 읽어 LoRA 구조 일치시킴
    import json
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
    for t in FIM:
        tid = tok.convert_tokens_to_ids(t)
        if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
            suppress.add(int(tid))
    suppress.discard(int(eos_id))
    suppress = sorted(suppress)

    out_md = [f"# 벤치 출력 — `{tag}`  (adapter: {args.adapter})\n",
              f"베이스 7B fp16 · greedy · im_start억제+min_new=24 · {time.strftime('%Y-%m-%d %H:%M')}\n"]
    for name, instr, code in tests:
        prompt = (f"### Instruction:\n{instr}\n\n### Input:\n{code}\n\n### Response:\n"
                  if code else f"### Instruction:\n{instr}\n\n### Response:\n")
        inp = tok(prompt, return_tensors="pt"); in_len = inp["input_ids"].shape[1]
        inp = {k: v.to(device) for k, v in inp.items()}
        t0 = time.time()
        with torch.no_grad():
            o = model.generate(**inp, max_new_tokens=args.max_new, min_new_tokens=24, do_sample=False,
                               pad_token_id=eos_id, eos_token_id=eos_id, suppress_tokens=suppress,
                               repetition_penalty=1.1)
        g = o[0][in_len:]; txt = tok.decode(g, skip_special_tokens=True).strip()
        dt = time.time() - t0
        block = (f"\n## {name}  (in={in_len}tok, out={len(g)}tok, {len(g)/max(dt,1e-9):.1f}tok/s)\n"
                 f"```\n{txt if txt else '(빈 출력 0자)'}\n```\n")
        out_md.append(block)
        print(block, flush=True)

    od = ROOT / "docs" / "bench-outputs"; od.mkdir(parents=True, exist_ok=True)
    (od / f"{tag}.md").write_text("\n".join(out_md), encoding="utf-8")
    print(f"\n[저장] docs/bench-outputs/{tag}.md", flush=True)


if __name__ == "__main__":
    main()
