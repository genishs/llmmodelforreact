# -*- coding: utf-8 -*-
"""
probe_141b_maxseq.py — 141B(Mixtral-8x22B) HQQ2 어텐션-LoRA의 **최대 seq 판정** 프로브.

목적
  base를 **한 프로세스에서 딱 한 번** HQQ 스트리밍 양자화로 적재한 뒤(로드 ~69분, 반복 금지),
  같은 프로세스 안에서 seq를 512→640→768→...로 올려가며 각 seq에 대해
  **fwd+bwd 마이크로스텝**을 실제로 돌리고, 다음을 실측한다.
    - torch.cuda.max_memory_allocated / max_memory_reserved  (allocator 관점)
    - GTT 실사용 피크  (/sys/class/drm/card1/device/mem_info_gtt_used, 백그라운드 샘플러 스레드)
    - 마이크로스텝 벽시계 시간  (스텝시간 스케일링 실측 → 에폭시간 추정에 사용)
  OOM/에러는 try/except로 잡아 empty_cache 후 다음으로 넘어가고,
  **GTT 피크 ≤ 한계(기본 54GiB, cap 56 대비 2GiB 마진)인 최대 seq를 판정·출력**한다.

⚠️ 이 스크립트는 seq별로 프로세스를 재기동하지 않는다(로드 69분 반복은 치명적 낭비).
   모델은 최초 1회 로드, 이후 모든 seq를 in-process로 스윕한다.
⚠️ 어텐션-온리 LoRA(q/k/v/o_proj) 유지. --lora-mlp 금지(Mixtral MLP=전문가, 타깃 없음).
   → 이 프로브는 train_directml.build()를 그대로 재사용하므로 config의 target_modules를 따른다.
⚠️ 백그라운드 "감시"는 **같은 프로세스의 Python 데몬 스레드**다(sysfs 폴링).
   detached nohup/setsid 프로세스가 아니라 이 환경의 리핑 함정과 무관하다.

실행(피선생/메인세션이 발사; gpu_job.sh로 웨지-세이프하게):
  scripts/gpu_job.sh --name mixtralprobe --timeout 10800 --cwd <REPO> -- \
    /home/user/.venvs/ai_model_mixtral/bin/python scripts/probe_141b_maxseq.py \
      --base "/run/media/user/새 볼륨/mixtral-8x22b-v0.1" \
      --limit-gib 54 --seqs 512,640,768,896,1024,1152,1280
"""

import os
import sys
import time
import glob
import argparse
import threading
import datetime as dt

import torch

# train_directml의 로더/빌더/백엔드 추상화를 그대로 재사용(중복 구현 금지).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.train_directml import resolve_backend, build, load_config  # noqa: E402


# ----------------------------------------------------------------- GTT 샘플러
def _find_gtt_path():
    """mem_info_gtt_used sysfs 경로 자동탐지(iGPU=gtt_total 최대인 card 선호)."""
    cands = sorted(glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"))
    if not cands:
        return None, None
    best = None
    best_total = -1
    for p in cands:
        tot_p = p.replace("mem_info_gtt_used", "mem_info_gtt_total")
        try:
            with open(tot_p) as f:
                tot = int(f.read().strip())
        except Exception:
            tot = 0
        if tot > best_total:
            best_total, best = tot, p
    vram = best.replace("mem_info_gtt_used", "mem_info_vram_used") if best else None
    return best, vram


def _read_gib(path):
    try:
        with open(path) as f:
            return int(f.read().strip()) / 1073741824.0
    except Exception:
        return float("nan")


class GttSampler(threading.Thread):
    """같은 프로세스의 데몬 스레드. sysfs gtt_used/vram_used를 고빈도 폴링해 피크 기록.
    (detached OS 프로세스가 아님 → 이 환경의 백그라운드 리핑 함정과 무관.)"""

    def __init__(self, gtt_path, vram_path, interval=0.05):
        super().__init__(daemon=True)
        self.gtt_path = gtt_path
        self.vram_path = vram_path
        self.interval = interval
        self._stop = threading.Event()
        self.max_gtt = 0.0
        self.max_vram = 0.0

    def reset(self):
        self.max_gtt = 0.0
        self.max_vram = 0.0

    def run(self):
        while not self._stop.is_set():
            if self.gtt_path:
                g = _read_gib(self.gtt_path)
                if g == g and g > self.max_gtt:  # NaN-safe
                    self.max_gtt = g
            if self.vram_path:
                v = _read_gib(self.vram_path)
                if v == v and v > self.max_vram:
                    self.max_vram = v
            time.sleep(self.interval)

    def stop(self):
        self._stop.set()


def log(msg):
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _is_oom(exc):
    s = f"{type(exc).__name__}: {exc}".lower()
    return any(k in s for k in (
        "out of memory", "hip out of memory", "hiperror", "miopen",
        "hip error", "alloc", "cuda error"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/run/media/user/새 볼륨/mixtral-8x22b-v0.1",
                    help="HQQ 스트리밍 로드할 bf16 원본 체크포인트 디렉토리")
    ap.add_argument("--config", default="./config/training_config.yaml")
    ap.add_argument("--seqs", default="512,640,768,896,1024,1152,1280",
                    help="오름차순 시험할 seq 목록(콤마구분). 512는 sanity(기지값 47.3GiB 대조)")
    ap.add_argument("--limit-gib", type=float, default=54.0,
                    help="GTT 피크 한계. 이 이하인 최대 seq를 채택(기본 54=cap56-2 마진)")
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--hqq-nbits", type=int, default=2)
    ap.add_argument("--hqq-group-size", type=int, default=64)
    ap.add_argument("--micro-per-seq", type=int, default=2,
                    help="seq별 마이크로스텝 반복수(1회차는 커널 워밍업 흡수, 시간=min·GTT=max)")
    ap.add_argument("--accum", type=int, default=8, help="에폭시간 추정용 accum(=실제 학습값)")
    ap.add_argument("--steps-per-epoch", type=int, default=39,
                    help="에폭시간 추정용 optim step/epoch(train 315줄/accum8≈39)")
    args = ap.parse_args()

    seqs = [int(x) for x in args.seqs.split(",") if x.strip()]
    LIMIT = args.limit_gib

    gtt_path, vram_path = _find_gtt_path()
    log(f"GTT sysfs: {gtt_path or '(미탐지 — allocator reserved로만 판정)'}")
    log(f"seq 스윕: {seqs} | GTT 한계 {LIMIT}GiB | HQQ {args.hqq_nbits}bit gs{args.hqq_group_size} | lora_r{args.lora_r}")

    backend, device, dev_name, empty_cache, mem_used_gb = resolve_backend("cuda")
    log(f"백엔드={backend} device={dev_name}")

    config = load_config(args.config)
    config["lora"]["r"] = args.lora_r
    config["lora"]["lora_alpha"] = args.lora_r * 2
    # target_modules는 config(q/v/k/o_proj) 그대로 — 어텐션-온리 보장(MLP 미포함 재확인).
    tm = config["lora"]["target_modules"]
    assert not any(m in tm for m in ("gate_proj", "up_proj", "down_proj")), \
        f"MLP LoRA 타깃 금지인데 config에 존재: {tm}"

    # ── base 1회 로드(HQQ 스트리밍 양자화, ~69분). 이후 재로드 없음. ──
    t_load = time.time()
    log("base HQQ 스트리밍 적재 시작(1회, 재기동 없음)…")
    model, tok = build(args.base, device, config, torch.bfloat16, grad_ckpt=True,
                       quant="hqq", hqq_nbits=args.hqq_nbits,
                       hqq_group_size=args.hqq_group_size)
    model.train()
    vocab = int(model.config.vocab_size)
    log(f"적재 완료: {time.time()-t_load:.1f}s, vocab={vocab}")

    trainable = [p for p in model.parameters() if p.requires_grad]
    optim = torch.optim.AdamW(trainable, lr=1e-4, eps=1e-4)  # 실제 런과 동일(상태 극소=LoRA)

    sampler = GttSampler(gtt_path, vram_path)
    sampler.start()

    results = []  # (seq, ok, gtt_peak, reserved, allocated, micro_s)
    best = None
    for seq in seqs:
        # 이전 seq 잔여 해제 후 측정 초기화
        optim.zero_grad(set_to_none=True)
        empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        sampler.reset()
        micro_times = []
        ok = True
        err = ""
        try:
            for _ in range(max(1, args.micro_per_seq)):
                ids = torch.randint(100, vocab - 100, (1, seq), device=device)
                mask = torch.ones((1, seq), dtype=torch.long, device=device)
                labels = ids.clone()
                torch.cuda.synchronize(device)
                t0 = time.time()
                out = model(input_ids=ids, attention_mask=mask, labels=labels)
                loss = out.loss
                loss.backward()
                optim.step()
                optim.zero_grad(set_to_none=True)
                torch.cuda.synchronize(device)
                micro_times.append(time.time() - t0)
                del out, loss, ids, mask, labels
        except Exception as e:  # noqa: BLE001 — OOM/HIP/wedge 전부 포착
            ok = False
            err = f"{type(e).__name__}: {e}"[:180]
            empty_cache()

        reserved = torch.cuda.max_memory_reserved(device) / 1073741824.0
        allocated = torch.cuda.max_memory_allocated(device) / 1073741824.0
        gtt_peak = sampler.max_gtt
        micro_s = min(micro_times) if micro_times else float("nan")
        results.append((seq, ok, gtt_peak, reserved, allocated, micro_s))

        # GTT 미탐지 환경 폴백: reserved+오버헤드로 근사(오버헤드 3.4GiB=실측 GTT-allocator 관측치)
        gate_val = gtt_peak if (gtt_path and gtt_peak > 0) else (reserved + 3.4)
        status = "OK" if ok else "FAIL"
        log(f"seq {seq:>5} | {status} | GTT피크 {gtt_peak:6.2f}GiB | "
            f"reserved {reserved:6.2f} | alloc {allocated:6.2f} | "
            f"micro {micro_s:6.1f}s | gate {gate_val:.2f}/{LIMIT}"
            + ("" if ok else f" | {err}"))

        if not ok:
            log(f"  ↑ seq {seq}에서 실패(OOM/에러) — 오름차순 종료. 채택 상한 = 직전 성공 seq.")
            break
        if gate_val > LIMIT:
            log(f"  ↑ seq {seq} GTT {gate_val:.2f} > 한계 {LIMIT} — 오름차순 종료.")
            break
        best = (seq, micro_s)

    sampler.stop()

    # ---------------- 요약 + 에폭시간 추정 ----------------
    print("\n" + "=" * 78, flush=True)
    print("PROBE 요약 (141B HQQ2 어텐션-LoRA, grad-ckpt)", flush=True)
    print("=" * 78, flush=True)
    print(f"{'seq':>6} {'판정':>5} {'GTT피크':>9} {'reserved':>9} {'alloc':>8} {'micro_s':>8} "
          f"{'step_s≈':>8} {'1ep_h≈':>7} {'2ep_h≈':>7}", flush=True)
    for seq, ok, gtt_peak, reserved, allocated, micro_s in results:
        step_s = micro_s * args.accum if micro_s == micro_s else float("nan")
        ep_h = step_s * args.steps_per_epoch / 3600.0
        print(f"{seq:>6} {'OK' if ok else 'FAIL':>5} {gtt_peak:8.2f}G {reserved:8.2f}G "
              f"{allocated:7.2f}G {micro_s:7.1f}s {step_s:7.0f}s {ep_h:6.2f}h {ep_h*2:6.2f}h",
              flush=True)
    print("=" * 78, flush=True)
    if best:
        bseq, bmicro = best
        bstep = bmicro * args.accum
        b1 = bstep * args.steps_per_epoch / 3600.0
        print(f"✅ 채택 최대 seq = {bseq}  (GTT ≤ {LIMIT}GiB 통과)", flush=True)
        print(f"   실측 step시간 ≈ {bstep:.0f}s/step, 1에폭({args.steps_per_epoch}스텝) ≈ {b1:.2f}h, "
              f"2에폭 ≈ {b1*2:.2f}h", flush=True)
        print(f"   → 풀학습 발사: bash /home/user/run_141b_highseq_master.sh {bseq} 1", flush=True)
    else:
        print("❌ 통과 seq 없음(512 sanity조차 실패). 로드/환경 점검 필요.", flush=True)
    print("=" * 78, flush=True)


if __name__ == "__main__":
    main()
