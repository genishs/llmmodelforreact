#!/usr/bin/env python3
"""
lan_chat.py — 8060 ↔ 4060 직결 실시간 채팅 릴레이 (stdlib 전용, 외부 의존성 0).

같은 LAN에 있을 때 git push/pull 왕복(지연·교차발신 충돌) 대신 쓰는 저지연 채널.
한 노드가 `serve`로 릴레이를 띄우고, 양쪽이 `send`/`poll`로 같은 보드를 공유한다.
상대 노드는 파이썬 없이 그냥 curl만으로도 붙을 수 있다(프로토콜은 아래 참조).

메시지는 comms/lan_chat_log.jsonl 에 append (서버 재시작해도 히스토리 유지, 1줄=1메시지 JSON).
이건 LAN 임시 채널이고, **합의·점수 정본은 여전히 git의 from-40/80 + scores-*.jsonl** 이다.
중요한 결론은 직결로 빨리 합의한 뒤 git에 한 번 요약 커밋하는 식으로 운영한다.

--- HTTP 프로토콜 (curl로 충분) ---
  POST /send   body: {"from":"4060","text":"..."}     -> {"i": <할당된 인덱스>}
  GET  /poll?since=N                                   -> {"last": M, "messages":[{i,ts,from,text},...]}
  GET  /                                               -> 사람이 읽는 상태/도움말

예) 8060이 우리(192.168.0.247:8765)에 붙기:
  curl -s -X POST http://192.168.0.247:8765/send -d '{"from":"8060","text":"붙었다"}'
  curl -s "http://192.168.0.247:8765/poll?since=0"

--- CLI ---
  python scripts/lan_chat.py serve [--host 0.0.0.0] [--port 8765]
  python scripts/lan_chat.py send  --host H --port P --from 4060 --text "..."
  python scripts/lan_chat.py poll  --host H --port P [--since N]
  python scripts/lan_chat.py watch --host H --port P   # 새 메시지 실시간 tail
"""
import argparse, hashlib, json, os, sys, time, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "comms", "lan_chat_log.jsonl")
_lock = threading.Lock()


def _safe_path(rel):
    """REPO_ROOT 밖 접근 차단(path traversal 방지). 절대경로 반환 or None."""
    rel = (rel or "").lstrip("/").replace("\\", "/")
    full = os.path.abspath(os.path.join(REPO_ROOT, rel))
    if full == REPO_ROOT or full.startswith(REPO_ROOT + os.sep):
        return full
    return None


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def _load():
    msgs = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msgs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return msgs


def _append(msg):
    with _lock:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 콘솔 스팸 억제
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/poll":
            qs = urllib.parse.parse_qs(parsed.query)
            since = int(qs.get("since", ["0"])[0])
            msgs = _load()
            new = [m for m in msgs if m.get("i", 0) > since]
            self._json(200, {"last": (msgs[-1]["i"] if msgs else 0), "messages": new})
        elif parsed.path == "/files":
            qs = urllib.parse.parse_qs(parsed.query)
            rel = qs.get("dir", [""])[0]
            d = _safe_path(rel)
            if not d or not os.path.isdir(d):
                return self._json(404, {"error": "no such dir"})
            items = []
            for nm in sorted(os.listdir(d)):
                p = os.path.join(d, nm)
                items.append({"name": nm, "is_dir": os.path.isdir(p),
                              "size": (os.path.getsize(p) if os.path.isfile(p) else 0)})
            self._json(200, {"dir": rel, "items": items})
        elif parsed.path == "/sha":
            qs = urllib.parse.parse_qs(parsed.query)
            p = _safe_path(qs.get("name", [""])[0])
            if not p or not os.path.isfile(p):
                return self._json(404, {"error": "no such file"})
            self._json(200, {"name": qs.get("name", [""])[0], "size": os.path.getsize(p),
                             "sha256": _sha256_file(p)})
        elif parsed.path == "/file":
            qs = urllib.parse.parse_qs(parsed.query)
            p = _safe_path(qs.get("name", [""])[0])
            if not p or not os.path.isfile(p):
                return self._json(404, {"error": "no such file"})
            sz = os.path.getsize(p)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(sz))
            self.send_header("X-Sha256", _sha256_file(p))
            self.end_headers()
            with open(p, "rb") as f:
                for blk in iter(lambda: f.read(1 << 20), b""):
                    self.wfile.write(blk)
            print(f"  -> served {qs.get('name',[''])[0]} ({sz} bytes)", flush=True)
        elif parsed.path == "/":
            msgs = _load()
            lines = [f"[{m['i']}] {time.strftime('%H:%M:%S', time.localtime(m['ts']))} "
                     f"{m['from']}: {m['text']}" for m in msgs[-30:]]
            txt = ("lan_chat relay OK. %d msgs.\nPOST /send {from,text} | GET /poll?since=N\n\n"
                   % len(msgs)) + "\n".join(lines)
            body = txt.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/file":
            return self._recv_file()
        if path != "/send":
            return self._json(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8", errors="replace") if n else "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        with _lock:
            msgs = _load()
            i = (msgs[-1]["i"] + 1) if msgs else 1
        msg = {"i": i, "ts": time.time(),
               "from": str(data.get("from", "?"))[:32],
               "text": str(data.get("text", ""))[:8000]}
        _append(msg)
        print(f"  <- [{i}] {msg['from']}: {msg['text'][:80]}", flush=True)
        self._json(200, {"i": i})

    def _recv_file(self):
        """POST /file: 헤더 X-Filename(REPO_ROOT 상대경로) + X-Sha256 → 스트리밍 저장·검증.
        업로드 대상은 comms/lan_xfer/incoming/ 아래로 강제(덮어쓰기 사고 방지)."""
        fn = self.headers.get("X-Filename", "").lstrip("/").replace("\\", "/")
        sha_exp = self.headers.get("X-Sha256", "")
        n = int(self.headers.get("Content-Length", 0))
        if not fn:
            return self._json(400, {"error": "missing X-Filename"})
        dest = _safe_path(os.path.join("comms/lan_xfer/incoming", fn))
        if not dest:
            return self._json(400, {"error": "bad path"})
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        h = hashlib.sha256()
        got = 0
        with open(dest, "wb") as f:
            while got < n:
                blk = self.rfile.read(min(1 << 20, n - got))
                if not blk:
                    break
                f.write(blk); h.update(blk); got += len(blk)
        sha_got = h.hexdigest()
        ok = (not sha_exp) or (sha_exp == sha_got)
        rel = os.path.relpath(dest, REPO_ROOT).replace("\\", "/")
        print(f"  <= recv {rel} ({got} bytes) sha_ok={ok}", flush=True)
        self._json(200 if ok else 422,
                   {"saved": rel, "bytes": got, "sha256": sha_got, "sha_ok": ok})


def cmd_serve(args):
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"lan_chat relay listening on {args.host}:{args.port}  log={LOG_PATH}", flush=True)
    print("  (Ctrl-C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


def _post(host, port, obj):
    url = f"http://{host}:{port}/send"
    req = urllib.request.Request(url, data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_poll(host, port, since):
    url = f"http://{host}:{port}/poll?since={since}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def cmd_send(args):
    print(_post(args.host, args.port, {"from": getattr(args, "from"), "text": args.text}))


def cmd_poll(args):
    res = _get_poll(args.host, args.port, args.since)
    for m in res["messages"]:
        print(f"[{m['i']}] {time.strftime('%H:%M:%S', time.localtime(m['ts']))} {m['from']}: {m['text']}")
    print(f"-- last={res['last']}")


def cmd_watch(args):
    since = args.since
    print(f"watching {args.host}:{args.port} from #{since} ...", flush=True)
    while True:
        try:
            res = _get_poll(args.host, args.port, since)
            for m in res["messages"]:
                print(f"[{m['i']}] {time.strftime('%H:%M:%S', time.localtime(m['ts']))} {m['from']}: {m['text']}", flush=True)
                since = m["i"]
        except Exception as e:
            print(f"(poll err: {e})", flush=True)
        time.sleep(2)


def cmd_files(args):
    url = f"http://{args.host}:{args.port}/files?dir={urllib.parse.quote(args.dir)}"
    with urllib.request.urlopen(url, timeout=15) as r:
        res = json.loads(r.read().decode("utf-8"))
    print(f"dir={res['dir'] or '.'}")
    for it in res["items"]:
        kind = "DIR " if it["is_dir"] else f"{it['size']:>12,}"
        print(f"  {kind}  {it['name']}")


def cmd_getfile(args):
    """LAN 피어에서 파일 다운로드 + sha256 검증."""
    url = f"http://{args.host}:{args.port}/file?name={urllib.parse.quote(args.name)}"
    out = args.out or os.path.join("comms/lan_xfer/incoming", os.path.basename(args.name))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    h = hashlib.sha256(); got = 0
    with urllib.request.urlopen(url, timeout=120) as r:
        sha_exp = r.headers.get("X-Sha256", "")
        with open(out, "wb") as f:
            for blk in iter(lambda: r.read(1 << 20), b""):
                f.write(blk); h.update(blk); got += len(blk)
    ok = (not sha_exp) or (sha_exp == h.hexdigest())
    print(f"saved {out} ({got:,} bytes) sha_ok={ok}" + ("" if ok else f"\n  EXPECTED {sha_exp}\n  GOT      {h.hexdigest()}"))
    if not ok:
        sys.exit(3)


def cmd_putfile(args):
    """로컬 파일을 LAN 피어로 업로드(피어 comms/lan_xfer/incoming/<as>에 저장) + sha256 검증."""
    src = args.name
    if not os.path.isfile(src):
        print(f"no such file: {src}"); sys.exit(1)
    sha = _sha256_file(src); sz = os.path.getsize(src)
    remote = args.as_name or os.path.basename(src)
    url = f"http://{args.host}:{args.port}/file"
    with open(src, "rb") as f:
        req = urllib.request.Request(url, data=f, method="POST",
                                     headers={"X-Filename": remote, "X-Sha256": sha,
                                              "Content-Length": str(sz),
                                              "Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=300) as r:
            print(json.loads(r.read().decode("utf-8")))


def cmd_dump(args):
    """릴레이 로그(jsonl)를 사람이 읽기 좋은 markdown transcript로 렌더.
    사용자가 git에서 LAN 대화를 확인할 수 있도록 체크포인트마다 호출 → 커밋/푸시."""
    msgs = _load()
    out = args.out or os.path.join(os.path.dirname(LOG_PATH), "lan_chat_transcript.md")
    lines = ["# LAN 직결 채팅 transcript (8060 ↔ 4060)",
             "",
             "> `scripts/lan_chat.py` LAN 릴레이로 주고받은 메시지 기록. 정본은 jsonl, 이건 가독용 렌더.",
             f"> 총 {len(msgs)}개 메시지. 체크포인트마다 `dump` 후 커밋됨.",
             ""]
    last_day = None
    for m in msgs:
        day = time.strftime("%Y-%m-%d", time.localtime(m["ts"]))
        if day != last_day:
            lines.append(f"\n## {day}\n"); last_day = day
        t = time.strftime("%H:%M:%S", time.localtime(m["ts"]))
        lines.append(f"- **[{m['i']}] {t} {m['from']}** — {m['text']}")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out} ({len(msgs)} msgs)")


def cmd_wake(args):
    """피어(자기 아닌 발신자) 메시지가 오면 그것만 출력하고 즉시 종료(exit 0).
    백그라운드로 띄워두면 종료=에이전트 재호출 트리거 → 'origin/LAN push→즉시 깨우기'.
    타임아웃(기본 0=무한) 도달 시 exit 2(메시지 없음)."""
    since, me, t0 = args.since, args.me, time.time()
    while True:
        try:
            res = _get_poll(args.host, args.port, since)
            for m in res["messages"]:
                since = m["i"]
                if m.get("from") != me:
                    print(json.dumps(m, ensure_ascii=False), flush=True)
                    return  # exit 0 → 하니스가 깨움
        except Exception as e:
            print(f"(wake poll err: {e})", flush=True)
        if args.timeout and (time.time() - t0) > args.timeout:
            sys.exit(2)
        time.sleep(args.interval)


def main():
    p = argparse.ArgumentParser(description="LAN chat relay for 8060<->4060")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--host", default="0.0.0.0"); s.add_argument("--port", type=int, default=8765); s.set_defaults(func=cmd_serve)
    s = sub.add_parser("send"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--from", required=True); s.add_argument("--text", required=True); s.set_defaults(func=cmd_send)
    s = sub.add_parser("poll"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--since", type=int, default=0); s.set_defaults(func=cmd_poll)
    s = sub.add_parser("watch"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--since", type=int, default=0); s.set_defaults(func=cmd_watch)
    s = sub.add_parser("files"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--dir", default=""); s.set_defaults(func=cmd_files)
    s = sub.add_parser("getfile"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--name", required=True); s.add_argument("--out", default=None); s.set_defaults(func=cmd_getfile)
    s = sub.add_parser("putfile"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--name", required=True); s.add_argument("--as", dest="as_name", default=None); s.set_defaults(func=cmd_putfile)
    s = sub.add_parser("dump"); s.add_argument("--out", default=None); s.set_defaults(func=cmd_dump)
    s = sub.add_parser("wake"); s.add_argument("--host", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--since", type=int, default=0); s.add_argument("--me", default="4060"); s.add_argument("--interval", type=float, default=2.0); s.add_argument("--timeout", type=float, default=0); s.set_defaults(func=cmd_wake)
    # Windows 콘솔 기본 cp949 → 한글/이모지 print 시 크래시. UTF-8로 고정(서버 로깅·클라 출력 공통).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
