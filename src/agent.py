# -*- coding: utf-8 -*-
"""
Code Improvement Agent
로컬 LLM을 실행 엔진으로 사용하는 코드 보완 에이전트

사용법:
  python src/agent.py --target ./path/to/project
  python src/agent.py --target ./path/to/project --auto   # 자동 적용
  python src/agent.py --file ./path/to/file.tsx           # 파일 1개
"""

import os
import sys
import argparse
import difflib
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from model_loader import generate

# ────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js", ".py", ".css"}
IGNORE_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", "venv"}
MAX_FILE_CHARS = 4000   # 모델에 보낼 최대 문자 수 (컨텍스트 한계)

# ────────────────────────────────────────────────
# 도구 정의
# ────────────────────────────────────────────────

def tool_list_files(directory: str, ext_filter: set = None) -> list[str]:
    """디렉토리 내 소스 파일 목록 반환"""
    root = Path(directory)
    if not root.exists():
        return []
    files = []
    for p in root.rglob("*"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file():
            if ext_filter is None or p.suffix in ext_filter:
                files.append(str(p))
    return sorted(files)


def tool_read_file(path: str) -> str:
    """파일 읽기"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"[읽기 오류] {e}"


def tool_write_file(path: str, content: str) -> str:
    """파일 쓰기"""
    try:
        Path(path).write_text(content, encoding="utf-8")
        return f"[저장 완료] {path}"
    except Exception as e:
        return f"[저장 오류] {e}"


def tool_run_shell(command: str, cwd: str = ".") -> str:
    """셸 명령 실행 (읽기 전용 — lint, typecheck 등)"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return output[:2000] if output else "(출력 없음)"
    except subprocess.TimeoutExpired:
        return "[타임아웃]"
    except Exception as e:
        return f"[실행 오류] {e}"


# ────────────────────────────────────────────────
# 모델 호출 (개선 제안 생성)
# ────────────────────────────────────────────────

REVIEW_INSTRUCTION = """다음 코드를 검토하고 개선된 전체 코드를 작성해줘.

개선 기준:
- 버그나 잠재적 오류 수정
- React/TypeScript 베스트 프랙티스 적용
- 불필요한 코드 제거, 가독성 향상
- 성능 개선 (불필요한 리렌더링 방지 등)

응답 형식:
ANALYSIS:
(무엇을 개선했는지 간략히)

IMPROVED_CODE:
```
(개선된 전체 코드)
```"""


def ask_model_to_improve(file_path: str, content: str) -> dict:
    """모델에게 코드 개선을 요청하고 결과 파싱"""
    # 파일이 너무 크면 앞부분만 사용
    truncated = content[:MAX_FILE_CHARS]
    if len(content) > MAX_FILE_CHARS:
        truncated += f"\n\n... (파일이 너무 커서 {MAX_FILE_CHARS}자까지만 분석)"

    context = f"파일: {file_path}\n\n{truncated}"

    raw = generate(
        instruction=REVIEW_INSTRUCTION,
        input_text=context,
        max_new_tokens=1024,
    )

    return _parse_model_response(raw, content)


def _parse_model_response(raw: str, original: str) -> dict:
    """모델 출력에서 분석과 개선 코드를 파싱"""
    analysis = ""
    improved_code = ""

    # ANALYSIS 섹션 파싱
    if "ANALYSIS:" in raw:
        parts = raw.split("ANALYSIS:", 1)[1]
        if "IMPROVED_CODE:" in parts:
            analysis = parts.split("IMPROVED_CODE:", 1)[0].strip()
        else:
            analysis = parts.strip()

    # IMPROVED_CODE 섹션 파싱
    if "IMPROVED_CODE:" in raw:
        code_part = raw.split("IMPROVED_CODE:", 1)[1].strip()
        # ```로 감싸진 코드 블록 추출
        if "```" in code_part:
            blocks = code_part.split("```")
            if len(blocks) >= 2:
                # 첫 번째 코드 블록 (언어 태그 제거)
                block = blocks[1]
                lines = block.split("\n")
                # 첫 줄이 언어 태그면 제거 (tsx, ts, js 등)
                if lines and lines[0].strip() in ("tsx", "ts", "js", "jsx", "py", "css", ""):
                    lines = lines[1:]
                improved_code = "\n".join(lines).strip()
        else:
            improved_code = code_part.strip()

    # 파싱 실패 시 raw 전체를 analysis로
    if not analysis and not improved_code:
        analysis = raw.strip()

    return {
        "analysis": analysis or "(분석 없음)",
        "improved_code": improved_code,
        "has_changes": bool(improved_code) and improved_code != original.strip(),
        "raw": raw,
    }


# ────────────────────────────────────────────────
# diff 표시
# ────────────────────────────────────────────────

def show_diff(original: str, improved: str, file_path: str):
    """unified diff 출력"""
    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        improved.splitlines(keepends=True),
        fromfile=f"원본: {file_path}",
        tofile=f"개선: {file_path}",
        n=3,
    ))
    if diff:
        print("\n" + "─" * 60)
        for line in diff[:100]:  # 너무 길면 100줄까지만
            if line.startswith("+") and not line.startswith("+++"):
                print(f"\033[32m{line}\033[0m", end="")   # 초록
            elif line.startswith("-") and not line.startswith("---"):
                print(f"\033[31m{line}\033[0m", end="")   # 빨강
            else:
                print(line, end="")
        print("─" * 60)
    else:
        print("  (변경 없음)")


# ────────────────────────────────────────────────
# Agent 루프
# ────────────────────────────────────────────────

class CodeImprovementAgent:
    def __init__(self, auto_apply: bool = False):
        self.auto_apply = auto_apply
        self.stats = {"analyzed": 0, "improved": 0, "skipped": 0, "errors": 0}

    def run_on_file(self, file_path: str):
        print(f"\n{'='*60}")
        print(f"[분석 중] {file_path}")
        print("="*60)

        content = tool_read_file(file_path)
        if content.startswith("[읽기 오류]"):
            print(f"  {content}")
            self.stats["errors"] += 1
            return

        self.stats["analyzed"] += 1
        print(f"  크기: {len(content):,}자 / {content.count(chr(10))+1}줄")

        # 모델 호출
        print("  모델 분석 중...")
        result = ask_model_to_improve(file_path, content)

        # 분석 결과 출력
        print(f"\n[분석 결과]\n{result['analysis']}")

        if not result["has_changes"]:
            print("\n  → 개선 사항 없음")
            self.stats["skipped"] += 1
            return

        # diff 표시
        improved = result["improved_code"]
        show_diff(content, improved, file_path)

        # 적용 여부 결정
        if self.auto_apply:
            tool_write_file(file_path, improved)
            print(f"  [자동 적용] {file_path}")
            self.stats["improved"] += 1
        else:
            answer = input("\n  적용하시겠습니까? [y/n/v(전체보기)] ").strip().lower()
            if answer == "v":
                print("\n[개선된 코드 전체]\n")
                print(improved)
                answer = input("\n  적용하시겠습니까? [y/n] ").strip().lower()
            if answer == "y":
                tool_write_file(file_path, improved)
                print(f"  [적용 완료]")
                self.stats["improved"] += 1
            else:
                print("  [건너뜀]")
                self.stats["skipped"] += 1

    def run_on_directory(self, directory: str):
        print(f"\n[대상 디렉토리] {Path(directory).resolve()}")
        files = tool_list_files(directory, SUPPORTED_EXTENSIONS)

        if not files:
            print("  대상 파일 없음")
            return

        print(f"  발견된 파일: {len(files)}개\n")
        for i, f in enumerate(files, 1):
            print(f"  [{i}/{len(files)}] {Path(f).name}")

        if not self.auto_apply:
            start = input(f"\n{len(files)}개 파일을 순서대로 분석합니다. 시작할까요? [y/n] ").strip().lower()
            if start != "y":
                print("취소")
                return

        for file_path in files:
            self.run_on_file(file_path)

        self._print_summary()

    def _print_summary(self):
        s = self.stats
        print(f"\n{'='*60}")
        print(f"[완료] 분석: {s['analyzed']} | 개선: {s['improved']} | 건너뜀: {s['skipped']} | 오류: {s['errors']}")
        print("="*60)


# ────────────────────────────────────────────────
# 진입점
# ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Code Improvement Agent")
    parser.add_argument("--target", "-t", help="분석할 디렉토리 경로")
    parser.add_argument("--file", "-f", help="분석할 파일 경로 (단일 파일)")
    parser.add_argument("--auto", "-a", action="store_true", help="자동 적용 (승인 없이)")
    parser.add_argument("--ext", nargs="*", help="대상 확장자 (기본: tsx ts jsx js py css)")
    args = parser.parse_args()

    if not args.target and not args.file:
        parser.print_help()
        print("\n예시:")
        print("  python src/agent.py --target ../twinspace_platform/src")
        print("  python src/agent.py --file ./src/components/Button.tsx")
        print("  python src/agent.py --target ./src --auto")
        sys.exit(0)

    if args.ext:
        global SUPPORTED_EXTENSIONS
        SUPPORTED_EXTENSIONS = {f".{e.lstrip('.')}" for e in args.ext}

    print("=" * 60)
    print(" Code Improvement Agent")
    print(f" 모드: {'자동 적용' if args.auto else '대화형 (수동 승인)'}")
    print("=" * 60)

    # 모델 미리 로드
    print("\n[모델 로딩 중...]")
    from model_loader import get_model
    get_model()
    print("[모델 준비 완료]\n")

    agent = CodeImprovementAgent(auto_apply=args.auto)

    if args.file:
        agent.run_on_file(args.file)
    else:
        agent.run_on_directory(args.target)


if __name__ == "__main__":
    main()
