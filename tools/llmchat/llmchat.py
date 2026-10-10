#!/usr/bin/env python3
"""llmchat.py — halo-ubuntu llama-server 에 붙는 터미널 대화 클라이언트 (의존성 0, 파이썬 3.8+)

다른 PC(Windows·Mac·Linux 어디서든) 에 이 파일 하나만 복사해서 쓰면 된다.

    python3 llmchat.py                                   # 대화 모드
    python3 llmchat.py "한 줄 질문"                        # 한 번 묻고 끝
    cat app.tsx | python3 llmchat.py "이 코드 리뷰해줘"     # 파일 내용을 붙여서 질문

접속 정보 (인자 > 환경변수 > 기본값):
    --url   / LLM_URL   기본 http://192.168.234.209:8080
    --key   / LLM_KEY   API 키 (LAN 모드 서버는 필수)
    --think             생각 과정까지 보여주기 (기본: 생각은 하되 숨김)
    --no-think          생각 모드 끄기 — 간단한 질문에 훨씬 빠르다

대화 중 명령:  /reset 대화 초기화 · /think 생각 표시 토글 · /fast 생각 모드 끄기/켜기 · /quit 종료
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

try:                                  # Windows 콘솔 한글 깨짐 방지
    sys.stdout.reconfigure(encoding="utf-8"); sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass
if os.name == "nt":
    os.system("")                     # Windows 10+ 에서 ANSI 색 켜기

DIM, BOLD, RST, CYAN = "\033[2m", "\033[1m", "\033[0m", "\033[36m"


def stream_chat(url, key, messages, show_think, no_think):
    body = {"messages": messages, "stream": True, "temperature": 0.3}
    if no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {key}"} if key else {})})
    answer, thinking_shown, t0, n = [], False, time.time(), 0
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            delta = (json.loads(data).get("choices") or [{}])[0].get("delta", {})
            r_txt, c_txt = delta.get("reasoning_content"), delta.get("content")
            if r_txt:
                n += 1
                if show_think:
                    if not thinking_shown:
                        print(f"{DIM}[생각] ", end=""); thinking_shown = True
                    print(f"{DIM}{r_txt}{RST}", end="", flush=True)
                elif not thinking_shown:
                    print(f"{DIM}(생각 중…){RST}", end="", flush=True); thinking_shown = True
            if c_txt:
                n += 1
                if thinking_shown and not answer:
                    print("\r\033[K" if not show_think else f"{RST}\n", end="")
                answer.append(c_txt); print(c_txt, end="", flush=True)
    dt = time.time() - t0
    print(f"\n{DIM}— {n}토큰 · {dt:.1f}초 · {n/dt if dt else 0:.1f} t/s{RST}")
    return "".join(answer)


def main():
    ap = argparse.ArgumentParser(description="halo-ubuntu llama-server 터미널 클라이언트")
    ap.add_argument("prompt", nargs="?", help="한 번만 물을 질문 (없으면 대화 모드)")
    ap.add_argument("--url", default=os.environ.get("LLM_URL", "http://192.168.234.209:8080"))
    ap.add_argument("--key", default=os.environ.get("LLM_KEY", ""))
    ap.add_argument("--think", action="store_true", help="생각 과정 표시")
    ap.add_argument("--no-think", action="store_true", help="생각 모드 끄기(빠름)")
    a = ap.parse_args()

    piped = "" if sys.stdin.isatty() else sys.stdin.read()
    history, show, fast = [], a.think, a.no_think

    def ask(text):
        history.append({"role": "user", "content": text})
        try:
            reply = stream_chat(a.url, a.key, history, show, fast)
        except urllib.error.HTTPError as e:
            history.pop()
            msg = {401: "API 키가 없거나 틀렸습니다 (--key 또는 LLM_KEY)"}.get(e.code, e.reason)
            print(f"\n🔴 HTTP {e.code}: {msg}"); return
        except (urllib.error.URLError, OSError) as e:
            history.pop(); print(f"\n🔴 접속 실패: {a.url} — {e}\n   서버가 켜져 있나? 방화벽은? (~/llm.sh status)"); return
        history.append({"role": "assistant", "content": reply})

    if a.prompt or piped:
        ask((a.prompt or "") + (("\n\n```\n" + piped + "\n```") if piped else "")); return

    print(f"{BOLD}{a.url}{RST} 에 연결 · /reset /think /fast /quit")
    while True:
        try:
            text = input(f"\n{CYAN}두목>{RST} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/reset":
            history.clear(); print("대화 초기화"); continue
        if text == "/think":
            show = not show; print(f"생각 과정 표시: {'켬' if show else '끔'}"); continue
        if text == "/fast":
            fast = not fast; print(f"생각 모드: {'끔(빠름)' if fast else '켬'}"); continue
        ask(text)


if __name__ == "__main__":
    main()
