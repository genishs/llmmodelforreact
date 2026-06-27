# -*- coding: utf-8 -*-
"""
14B fp16 LoRA 실현가능성 단계 테스트 (DirectML / 8060S).

배경: probe로 GPU 텐서 천장이 ~39GB임이 측정됨(이전 믿음 28GB는 학습 단편화 벽).
14B fp16 가중치 ≈ 29GB < 39GB → 재도전 가치. 호스트 RAM은 매우 적어(가용 ~5GB)
반드시 stream_load_to_device(meta+텐서단위)로 디스크→GPU 직접 적재.

단계:
  Stage2  14B fp16를 DML 디바이스에 스트리밍 적재 (호스트 OOM 없이 되나?)
  Stage3  LoRA(어텐션 r16) 부착 → seq N batch1 forward+backward+step 1회 (GPU 여유로 도나?)

실행:  python scripts/probe_14b_load.py [--seq 128] [--model <path>]
어느 단계서 막히든 즉시 사유 출력하고 중단 → Windows/DirectML 14B 가부 확정.
"""
import os, sys, time, gc, argparse
# Windows 콘솔 cp949가 ≈ 등 비-cp949 문자를 못 찍어 죽는 문제 방지 → stdout/stderr UTF-8 고정
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch
import torch_directml
import psutil
from transformers import AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType
from dml_loader import stream_load_to_device


def ram():
    return psutil.virtual_memory().available / 1024**3

def gpu_used_gb(dev):
    # torch_directml.gpu_memory(idx)는 30개 카운터 리스트(단위 불명, 참고용) → 합산.
    # 진짜 go/no-go 신호는 예외(OOM)이지 이 값이 아님.
    try:
        v = torch_directml.gpu_memory(0)
        if isinstance(v, (list, tuple)):
            s = sum(float(x) for x in v)
            return s / 1024**3 if s > 1e6 else s  # 바이트면 GB로, 아니면 원값
        return float(v) / 1024**3
    except Exception:
        return float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", type=int, default=128)
    ap.add_argument("--model", default=None,
                    help="14B 경로(생략 시 HF 캐시 자동탐색)")
    args = ap.parse_args()

    # 모델 경로 자동탐색 (HF 캐시 snapshot)
    mp = args.model
    if mp is None:
        import glob
        cands = glob.glob(os.path.expanduser(
            "~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-14B-Instruct/snapshots/*"))
        if not cands:
            print("[FAIL] 14B 스냅샷을 찾지 못함 — 다운로드 완료 후 재실행.")
            sys.exit(2)
        mp = cands[0]
    print(f"[14B] model = {mp}")

    dev = torch_directml.device()
    dtype = torch.float16
    print(f"[env] device={dev} | host RAM avail {ram():.1f}GB | start GPU {gpu_used_gb(dev):.1f}GB")

    # ---------- Stage 2: 스트리밍 적재 ----------
    print("\n=== Stage 2: 14B fp16 스트리밍 적재 ===")
    t0 = time.time()
    try:
        model = stream_load_to_device(mp, dev, dtype)
    except MemoryError as e:
        print(f"[FAIL-Stage2] 호스트 RAM 고갈: {e}")
        print(">>> 결론: 5GB대 호스트로 29GB 적재 불가 → 더 닫거나 Linux GTT 필요.")
        sys.exit(3)
    except RuntimeError as e:
        print(f"[FAIL-Stage2] GPU/런타임 오류(적재중 OOM 가능): {str(e)[:300]}")
        print(">>> 결론: GPU 전용풀(~39GB)에 29GB 적재가 단편화로 실패. Linux GTT 필요.")
        sys.exit(3)
    load_s = time.time() - t0
    print(f"[OK-Stage2] 적재 완료 {load_s:.1f}s | host RAM {ram():.1f}GB | GPU 사용 {gpu_used_gb(dev):.1f}GB")
    headroom = 39.0 - gpu_used_gb(dev)
    print(f"  → GPU 잔여(천장39 기준) ≈ {headroom:.1f}GB (활성값+LoRA+옵티마이저+단편화가 여기 들어가야 함)")

    # ---------- Stage 3: LoRA + 학습 1스텝 ----------
    print(f"\n=== Stage 3: LoRA(어텐션 r16) + seq{args.seq} 학습 1스텝 ===")
    tok = AutoTokenizer.from_pretrained(mp, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    lcfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05, bias="none",
    )
    try:
        model = get_peft_model(model, lcfg).to(dev)
        model.config.use_cache = False
        model.train()
        print(f"  LoRA 부착 후 GPU {gpu_used_gb(dev):.1f}GB")

        # 더미 배치(고정 seq) — 실제 학습과 동일한 메모리 패턴
        ids = torch.randint(0, 1000, (1, args.seq), device=dev)
        batch = {"input_ids": ids, "attention_mask": torch.ones_like(ids), "labels": ids.clone()}
        trainable = [p for p in model.parameters() if p.requires_grad]
        optim = torch.optim.AdamW(trainable, lr=1e-4)

        out = model(**batch)
        print(f"  forward OK | loss {out.loss.item():.3f} | GPU {gpu_used_gb(dev):.1f}GB")
        out.loss.backward()
        print(f"  backward OK | GPU {gpu_used_gb(dev):.1f}GB")
        optim.step(); optim.zero_grad()
        print(f"[OK-Stage3] seq{args.seq} 학습 1스텝 성공 | 최종 GPU {gpu_used_gb(dev):.1f}GB")
        print(f">>> 결론: 14B fp16 LoRA가 DirectML/Windows에서 seq{args.seq}로 학습 가능!")
        print(f"    다음: seq를 단계적으로 올려 안정 상한 탐색 → 데이터로 실학습.")
    except RuntimeError as e:
        print(f"[FAIL-Stage3] seq{args.seq} 학습 OOM/오류: {str(e)[:300]}")
        print(f">>> 결론: 14B 적재는 됐으나 seq{args.seq} 학습 스텝이 GPU 여유 부족으로 실패.")
        print("    레버: seq 더 낮춤(64), 또는 GPU 천장이 부족 → Linux GTT 필요.")
        sys.exit(4)


if __name__ == "__main__":
    main()
