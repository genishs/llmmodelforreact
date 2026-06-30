# -*- coding: utf-8 -*-
"""
DirectML 공유메모리(shared GPU memory) 사용 여부 소규모 테스트.

배경: 현재 전용 VRAM이 ~512MB(공유 모드)로 설정됨. 시스템 RAM 63GB.
질문: DirectML 텐서 할당이 전용 512MB를 넘어 **공유 풀**을 끌어오는가?
  - 전용만 쓰면 → ~0.5GB에서 실패
  - 공유 끌어오면 → 수 GB까지 성공(공유 풀 ~31GB 한도)

방법: 0.25GB fp16 텐서를 하나씩 DirectML 디바이스에 올리고 참조 유지.
  매 스텝 누적량 출력. 상한(--cap, 기본 8GB) 도달 또는 에러 시 중단.
  소규모·안전. (세그폴트 가능성 있으나 작은 스텝이라 영향 최소.)

실행: python scripts/dml_shared_probe.py [--step 0.25] [--cap 8]
"""
import os, sys, time, argparse
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import torch
import torch_directml
import psutil


def host_avail_gb():
    return psutil.virtual_memory().available / 1024**3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.25, help="스텝당 GB")
    ap.add_argument("--cap", type=float, default=8.0, help="상한 GB(여기 도달하면 안전 중단)")
    ap.add_argument("--floor", type=float, default=4.0, help="호스트 RAM 바닥 가드 GB(이 밑이면 정지=PC 프리징 방지)")
    args = ap.parse_args()

    dev = torch_directml.device()
    print(f"[env] device={dev} | name={torch_directml.device_name(0)}", flush=True)
    print(f"[env] 전용 VRAM ~512MB(공유모드) | 호스트 RAM 가용 {host_avail_gb():.1f}GB", flush=True)
    print(f"[plan] {args.step}GB씩 적재 → 상한 {args.cap}GB. 전용(0.5GB) 초과 성공=공유 사용 증거.\n", flush=True)

    # fp16 0.25GB = 0.25*1024^3 / 2 bytes = 134,217,728 elements
    elems = int(args.step * 1024**3 / 2)
    held = []
    total = 0.0
    t0 = time.time()
    try:
        while total < args.cap:
            if host_avail_gb() < args.floor:
                print(f"\n[가드] 호스트 RAM 가용 {host_avail_gb():.1f}GB < {args.floor}GB 바닥 → "
                      f"PC 프리징 방지 위해 {total:.2f}GB에서 안전 정지.", flush=True)
                print(f">>> 공유로 {total:.2f}GB 적재 확인(전용 0.5GB 초과). 더 가려면 호스트 RAM 확보 필요.", flush=True)
                return
            t = torch.empty(elems, dtype=torch.float16, device=dev)
            t.fill_(1.0)  # 실제 쓰기(지연할당 방지)
            held.append(t)
            total += args.step
            print(f"  적재 {total:.2f}GB OK | 호스트RAM가용 {host_avail_gb():.1f}GB", flush=True)
        print(f"\n[결과] ★상한 {args.cap}GB 도달 성공! 전용 0.5GB를 {args.cap/0.5:.0f}배 초과 → "
              f"**DirectML이 공유메모리를 끌어옴 확정.** ({time.time()-t0:.1f}s)", flush=True)
        print(">>> 함의: 공유모드(작은전용)서는 DirectML도 통합메모리를 쓴다 → 큰모델 가능성 재검토!", flush=True)
    except RuntimeError as e:
        print(f"\n[결과] {total:.2f}GB에서 실패: {str(e)[:200]}", flush=True)
        if total <= 1.0:
            print(">>> 전용(0.5GB) 근처서 실패 = **DirectML은 전용 바운드, 공유 미사용 확정.** "
                  "공유모드는 오히려 천장을 낮춤(이전 결론 재확인).", flush=True)
        else:
            print(f">>> 전용 0.5GB를 넘어 {total:.2f}GB까지 갔다 = **공유 일부 사용**. 천장={total:.2f}GB 부근.", flush=True)
    except Exception as e:
        print(f"\n[결과] {total:.2f}GB에서 비RuntimeError: {str(e)[:200]}", flush=True)


if __name__ == "__main__":
    main()
