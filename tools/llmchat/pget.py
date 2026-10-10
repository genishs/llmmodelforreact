#!/usr/bin/env python3
"""pget.py — 큰 파일을 HTTP Range 로 여러 연결 동시에 받는다 (의존성 0).

    python3 pget.py <URL> <저장경로> <전체바이트> [연결수=8]

- 256MB 조각 단위로 나눠 받고, 끝난 조각은 <저장경로>.done 에 기록 → 중단돼도 이어받는다.
- 조각마다 받은 바이트 수를 확인하고, 모자라면 재시도한다.
- 무결성(sha256) 확인은 끝난 뒤 따로 한다.
"""
import os, sys, threading, time, urllib.request

url, out, total = sys.argv[1], sys.argv[2], int(sys.argv[3])
nconn = int(sys.argv[4]) if len(sys.argv) > 4 else 8
CH = 256 * 1024 * 1024
done_path = out + ".done"
chunks = [(i, s, min(s + CH, total) - 1) for i, s in enumerate(range(0, total, CH))]
done = set(int(x) for x in open(done_path).read().split()) if os.path.exists(done_path) else set()

if not os.path.exists(out) or os.path.getsize(out) != total:
    with open(out, "ab") as f:
        f.truncate(total)                     # 미리 전체 크기로 잡아두고 오프셋에 쓴다

fd = os.open(out, os.O_RDWR)
lock = threading.Lock()
todo = [c for c in chunks if c[0] not in done]
got = [0]
t0 = time.time()


def worker():
    while True:
        with lock:
            if not todo:
                return
            idx, s, e = todo.pop(0)
        for attempt in range(1, 21):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={s}-{e}"})
                pos, n = s, 0
                with urllib.request.urlopen(req, timeout=120) as r:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        os.pwrite(fd, b, pos); pos += len(b); n += len(b)
                        with lock:
                            got[0] += len(b)
                if n != e - s + 1:
                    raise IOError(f"조각 {idx}: {n}/{e-s+1} bytes")
                with lock:
                    done.add(idx)
                    with open(done_path, "a") as f:
                        f.write(f"{idx}\n")
                break
            except Exception as ex:
                print(f"조각 {idx} 재시도 {attempt}: {ex}", flush=True)
                time.sleep(min(30, 2 * attempt))
        else:
            print(f"🔴 조각 {idx} 20회 실패", flush=True)


def report():
    while any(t.is_alive() for t in ths):
        time.sleep(30)
        el = time.time() - t0
        with lock:
            d = len(done)
        rate = got[0] / el / 1048576 if el else 0
        left = (len(chunks) - d) * CH / 1048576 / rate / 60 if rate else 0
        print(f"[{time.strftime('%H:%M:%S')}] {d}/{len(chunks)} 조각 · {rate:.1f} MB/s · 남은 약 {left:.0f}분", flush=True)


ths = [threading.Thread(target=worker, daemon=True) for _ in range(nconn)]
for t in ths:
    t.start()
threading.Thread(target=report, daemon=True).start()
for t in ths:
    t.join()
os.close(fd)
ok = len(done) == len(chunks)
print("✅ 모든 조각 완료" if ok else f"🔴 미완료 {len(chunks)-len(done)}조각", flush=True)
sys.exit(0 if ok else 1)
