# -*- coding: utf-8 -*-
"""
GitHub 공개 레포에서 직접 React 코드를 수집하는 스크립트
(인증 불필요 - contents API 사용)

실행: python src/collect_github_data.py
      python src/collect_github_data.py --token YOUR_GITHUB_TOKEN  (rate limit 높이기)
"""

import os
import re
import sys
import time
import json
import base64
import argparse
import requests
from pathlib import Path

GITHUB_API = "https://api.github.com"

# 수집 대상 레포 및 경로 (인증 없이 접근 가능한 공개 레포)
REPOS = [
    # repo, 탐색 경로, 최대 파일 수
    ("alan2207/bulletproof-react", "apps/react-vite/src", 40),
    ("alan2207/bulletproof-react", "apps/nextjs-app/src", 30),
    ("pmndrs/zustand", "examples/demo/src", 15),
    ("vercel/next.js", "examples/with-react-hook-form", 10),
    ("vercel/next.js", "examples/with-context-api", 10),
    ("vercel/next.js", "examples/with-zustand", 10),
    ("vercel/next.js", "examples/with-redux", 10),
    ("shadcn-ui/ui", "apps/v4/components", 30),
    ("recharts/recharts", "src/component", 25),
    ("recharts/recharts", "src/cartesian", 20),
    ("TanStack/query", "examples/react/basic", 15),
    ("TanStack/query", "examples/react/infinite-scroll", 15),
    ("TanStack/query", "examples/react/pagination", 10),
    ("reduxjs/redux-toolkit", "examples/query/react/advanced", 15),
    ("reduxjs/redux-toolkit", "examples/query/react/kitchen-sink", 15),
    ("jotaijs/jotai", "examples", 20),
    ("pmndrs/react-spring", "demo/src/sandboxes", 20),
]

EXCLUDE_PATTERNS = [
    r"\.test\.",
    r"\.spec\.",
    r"\.stories\.",
    r"__tests__",
    r"node_modules",
    r"\.d\.ts$",
]


class GitHubDirectCollector:
    def __init__(self, token=None):
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ReactDataCollector/1.0",
        }
        if token:
            headers["Authorization"] = f"token {token}"
        self.session.headers.update(headers)

    def list_files(self, repo, path="", depth=0, max_depth=3):
        """레포 디렉토리에서 파일 목록 재귀 탐색"""
        if depth > max_depth:
            return []

        url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 404:
                return []
            if resp.status_code == 403:
                print(f"  [경고] Rate limit. 30초 대기...")
                time.sleep(30)
                resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []

            items = resp.json()
            if not isinstance(items, list):
                return []

            files = []
            for item in items:
                if item["type"] == "file":
                    if item["name"].endswith((".tsx", ".jsx", ".ts", ".js")):
                        files.append(item)
                elif item["type"] == "dir":
                    sub = self.list_files(repo, item["path"], depth + 1, max_depth)
                    files.extend(sub)
                    time.sleep(0.2)

            return files
        except Exception as e:
            print(f"  [오류] {e}")
            return []

    def get_file_content(self, download_url):
        """파일 raw 내용 다운로드"""
        try:
            resp = self.session.get(download_url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None


def is_valid_react_file(path, content):
    """유효한 React 파일인지 확인"""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, path):
            return False

    if not content or len(content) < 150 or len(content) > 10000:
        return False

    has_react = "from 'react'" in content or 'from "react"' in content
    has_jsx = bool(re.search(r"return\s*\(?\s*<", content))

    return has_react and has_jsx


def extract_segments(content):
    """파일에서 컴포넌트/훅 단위 분리"""
    segments = []

    patterns = [
        # export function Component
        r"(export\s+(?:default\s+)?function\s+[A-Z]\w*[\s\S]*?)(?=\nexport\s+(?:default\s+)?(?:function|const|class)|\Z)",
        # export const Component = ...
        r"(export\s+(?:default\s+)?const\s+[A-Z]\w*\s*(?::\s*\S+)?\s*=[\s\S]*?(?:\}\);|\}\)|\})\s*;?)\s*(?=\nexport|\Z)",
        # custom hook
        r"((?:export\s+)?(?:default\s+)?(?:function|const)\s+use[A-Z]\w*[\s\S]*?(?:\n\}|\}\);))\s*(?=\nexport|\Z)",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, content, re.MULTILINE):
            seg = m.group(1).strip()
            if 100 < len(seg) < 4000:
                segments.append(seg)

    if not segments:
        # 파일 전체 사용
        if 150 < len(content) < 4000:
            segments = [content]

    # 중복 제거
    seen, unique = set(), []
    for s in segments:
        key = s[:80]
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique


def code_to_qa(code):
    """코드에서 Q&A 쌍 생성"""
    templates = []

    if "useState" in code and "useEffect" in code:
        templates.append("useState와 useEffect를 함께 사용하는 React 컴포넌트를 작성해줘.")
    elif "useState" in code:
        states = re.findall(r"const\s+\[(\w+)", code)
        if states:
            templates.append(f"`{states[0]}` 상태를 관리하는 React 컴포넌트를 작성해줘.")
        else:
            templates.append("useState를 사용하는 React 컴포넌트를 작성해줘.")

    if re.search(r"const\s+use[A-Z]", code):
        names = re.findall(r"const\s+(use\w+)", code)
        if names:
            templates.append(f"`{names[0]}` 커스텀 훅을 구현해줘.")

    if "useContext" in code or "createContext" in code:
        templates.append("React Context API로 전역 상태를 관리하는 코드를 작성해줘.")

    if "useReducer" in code:
        templates.append("useReducer를 사용해서 복잡한 상태 로직을 관리하는 컴포넌트를 작성해줘.")

    if "useMemo" in code:
        templates.append("useMemo로 성능을 최적화하는 React 컴포넌트를 작성해줘.")

    if "useCallback" in code:
        templates.append("useCallback으로 함수 메모이제이션을 적용한 React 컴포넌트를 작성해줘.")

    if "async" in code and ("fetch" in code or "axios" in code):
        templates.append("async/await로 API를 호출하는 React 컴포넌트를 작성해줘.")

    if "onChange" in code and re.search(r"<input|<form|<select", code, re.IGNORECASE):
        templates.append("React에서 입력 폼을 관리하는 컴포넌트를 작성해줘.")

    # 컴포넌트 이름 기반 fallback
    if not templates:
        names = re.findall(r"(?:function|const)\s+([A-Z]\w*)", code)
        if names:
            templates.append(f"`{names[0]}` React 컴포넌트를 작성해줘.")

    return [{"instruction": t, "input": "", "output": code} for t in templates]


def collect(output_dir="./data/raw", token=None):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    collector = GitHubDirectCollector(token=token)

    all_qa = []
    seen_codes = set()

    print(f"GitHub 레포 직접 수집 ({len(REPOS)}개 레포)")
    print("=" * 50)

    for i, (repo, path, max_files) in enumerate(REPOS, 1):
        print(f"\n[{i}/{len(REPOS)}] {repo}/{path}")

        files = collector.list_files(repo, path)
        print(f"  파일 목록: {len(files)}개 발견")

        collected = 0
        for file_info in files[:max_files]:
            if any(re.search(p, file_info["path"]) for p in EXCLUDE_PATTERNS):
                continue

            content = collector.get_file_content(file_info["download_url"])
            if not content or not is_valid_react_file(file_info["path"], content):
                time.sleep(0.3)
                continue

            segments = extract_segments(content)
            for seg in segments:
                key = seg[:80].strip()
                if key in seen_codes:
                    continue
                seen_codes.add(key)

                qa_pairs = code_to_qa(seg)
                all_qa.extend(qa_pairs)

            collected += 1
            time.sleep(0.5)

        print(f"  수집: {collected}개 파일 | 누적 Q&A: {len(all_qa)}개")
        time.sleep(1)

    # 저장
    out_path = f"{output_dir}/github_react_qa.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for item in all_qa:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n{'=' * 50}")
    print(f"수집 완료: {len(all_qa)}개 Q&A")
    print(f"저장: {out_path}")
    return len(all_qa)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", type=str, default=None)
    args = parser.parse_args()

    if not args.token:
        print("[안내] 토큰 없이 실행 (시간당 60 req 제한, 속도 느림)")
        print("       GitHub 토큰으로 rate limit 올리기: --token ghp_xxx\n")

    collect(token=args.token)
