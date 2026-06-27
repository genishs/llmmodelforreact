# -*- coding: utf-8 -*-
"""
14B fp16 LoRA seq 안정 상한 탐색 (DirectML / 8060S).

probe_14b_load.py가 seq128 학습가능을 실증함. 이 스크립트는 29GB를 **한 번만 적재**한 뒤
seq를 오름차순으로 올리며 forward+backward+AdamW 1스텝을 시도 → 첫 OOM 직전까지의 최대 성공 seq를 보고.
(단일 프로세스라 DirectML 캐싱할당자 단편화가 누적 → 결과는 보수적 하한 = 실학습 안전마진).

실행:  python scripts/probe_14b_seqsweep.py [--seqs 128,256,384,512,768,1024]
출력 마지막의 [SWEEP-RESULT] max_ok_seq=N 이 실학습에 쓸 안전 seq.
"""
import os, sys, time, gc, argparse
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch
import torch_directml
import psutil
from peft import LoraConfig, get_peft_model, TaskType
from dml_loader import stream_load_to_device


def ram():
    return psutil.virtual_memory().available / 1024**3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seqs", default="128,256,384,512,768,1024",
                    help="콤마구분 오름차순 seq 목록")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    seqs = [int(x) for x in args.seqs.split(",")]

    mp = args.model
    if mp is None:
        import glob
        cands = glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-14B-Instruct/snapshots/*"))
        if not cands:
            print("[FAIL] 14B 스냅샷 없음 — 다운로드 후 재실행.")
            sys.exit(2)
        mp = cands[0]
    print(f"[14B] model = {mp}")

    dev = torch_directml.device()
    print(f"[env] device={dev} | host RAM avail {ram():.1f}GB")

    print("\n=== 적재(1회) ===")
    t0 = time.time()
    model = stream_load_to_device(mp, dev, torch.float16)
    print(f"[OK-적재] {time.time()-t0:.1f}s | host RAM {ram():.1f}GB")

    # LoRA 부착(1회) — 실학습과 동일 설정
    lcfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05, bias="none",
    )
    model = get_peft_model(model, lcfg).to(dev)
    model.config.use_cache = False
    model.train()
    trainable = [p for p in model.parameters() if p.requires_grad]
    optim = torch.optim.AdamW(trainable, lr=1e-4)
    print("[OK-LoRA] 부착 완료\n")

    max_ok = 0
    for s in seqs:
        print(f"--- seq {s} 시도 ---", flush=True)
        try:
            ids = torch.randint(0, 1000, (1, s), device=dev)
            batch = {"input_ids": ids, "attention_mask": torch.ones_like(ids),
                     "labels": ids.clone()}
            t1 = time.time()
            out = model(**batch)
            loss = out.loss
            loss.backward()
            optim.step(); optim.zero_grad()
            dt = time.time() - t1
            print(f"  [OK] seq{s} | loss {loss.item():.3f} | step {dt:.1f}s | host RAM {ram():.1f}GB", flush=True)
            max_ok = s
            del ids, batch, out, loss
            gc.collect()
        except RuntimeError as e:
            print(f"  [OOM/ERR] seq{s} 실패: {str(e)[:200]}", flush=True)
            print(f"  → 단편화 누적 가능. max_ok={max_ok}에서 중단.", flush=True)
            break
        except Exception as e:
            print(f"  [ERR] seq{s} 비OOM 오류: {str(e)[:200]}", flush=True)
            break

    print(f"\n[SWEEP-RESULT] max_ok_seq={max_ok}")
    if max_ok:
        print(f">>> 실학습 권장 seq = {max_ok} (단일프로세스 보수치 → 실학습은 동등이상 안전).")
    else:
        print(">>> 최소 seq도 실패 — GPU 여유 부족. seq64 또는 Linux GTT 검토.")


if __name__ == "__main__":
    main()
