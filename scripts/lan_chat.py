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
import argparse, json, os, sys, time, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "comms", "lan_chat_log.jsonl")
_lock = threading.Lock()


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
        if urllib.parse.urlparse(self.path).path != "/send":
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
