"""
torch-directml VRAM ceiling probe.

Allocates fixed-size tensors in a loop, KEEPING references so nothing is freed,
and prints cumulative allocated GB until the DML allocator OOMs
("Could not allocate tensor with N bytes" / "DML allocator out of memory").

Goal: empirically map the real usable ceiling on the DirectML device, and
compare it to what Task Manager reports as "Dedicated GPU memory" (DXGI LOCAL
budget). If the OOM point tracks the *dedicated* figure and NOT total unified
RAM, that proves DirectML is pinning tensors to the LOCAL/dedicated segment and
refusing to spill to the shared segment -- i.e. the ceiling is the DXGI budget,
raisable via AMD Variable Graphics Memory, not a torch flag.

Run:  python dml_ceiling_probe.py
While it runs, watch Task Manager > Performance > GPU:
  - "Dedicated GPU memory x / Y GB"  <- this Y is the DXGI LOCAL budget (the cap)
  - "Shared GPU memory"              <- DirectML only uses this for staging, not tensors
"""

import torch
import torch_directml

dev = torch_directml.device()
print("DirectML device:", dev, "| device_count:", torch_directml.device_count())

# Tunables
CHUNK_GB = 0.5                       # tensor size per step
DTYPE = torch.float16                # match your training dtype
elems = int(CHUNK_GB * (1024**3) / 2)  # 2 bytes per fp16 element

held = []          # keep refs so the allocator can't reclaim
total_gb = 0.0
try:
    while True:
        # allocate directly on device; touch it so the heap is really committed
        t = torch.ones(elems, dtype=DTYPE, device=dev)
        t += 1.0
        torch_directml.synchronize() if hasattr(torch_directml, "synchronize") else None
        held.append(t)
        total_gb += CHUNK_GB
        print(f"  allocated ~{total_gb:6.1f} GB on DML (tensors held: {len(held)})", flush=True)
except RuntimeError as e:
    print("\n=== OOM ===")
    print(f"Ceiling reached at ~{total_gb:.1f} GB (last successful cumulative).")
    print("Allocator error:", str(e)[:300])
    print("\nCompare ~{:.1f} GB against Task Manager 'Dedicated GPU memory' total.".format(total_gb))
    print("If they match (and both are << 64GB unified), the cap is the DXGI LOCAL")
    print("budget / dedicated carveout -- raise it with AMD Adrenalin VGM, not a torch flag.")
