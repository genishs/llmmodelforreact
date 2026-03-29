# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 서버
Claude Code에서 로컬 React 어시스턴트를 툴로 사용할 수 있게 해줍니다.

실행: python src/mcp_server.py
Claude Code 설정: ~/.claude/settings.json 에 MCP 서버 등록 필요
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from model_loader import generate


app = Server("react-coding-assistant")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="improve_code_file",
            description=(
                "지정된 파일을 로컬 LLM으로 분석하여 코드 개선 제안을 반환합니다. "
                "버그, 성능 문제, 베스트 프랙티스 위반 등을 찾아 개선된 코드를 제시합니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "분석할 파일의 절대 경로 또는 상대 경로",
                    },
                    "focus": {
                        "type": "string",
                        "description": "집중할 개선 영역 (예: '성능', '타입 안전성', '버그 수정'). 선택사항.",
                    },
                },
                "required": ["file_path"],
            },
        ),
        types.Tool(
            name="improve_directory",
            description=(
                "디렉토리 내 모든 소스 파일을 순차적으로 분석하여 개선 제안을 반환합니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "분석할 디렉토리 경로",
                    },
                    "extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "분석할 확장자 목록 (기본: tsx, ts, jsx, js). 예: ['tsx', 'ts']",
                    },
                },
                "required": ["directory"],
            },
        ),
        types.Tool(
            name="generate_react_code",
            description=(
                "로컬 파인튜닝 모델로 React 코드를 생성합니다. "
                "React 컴포넌트, 커스텀 훅, TypeScript 타입 등을 생성할 수 있습니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "생성할 React 코드에 대한 설명 (예: 'useState로 카운터 컴포넌트 만들어줘')",
                    },
                    "context": {
                        "type": "string",
                        "description": "추가 컨텍스트 (현재 파일 내용, API 구조 등). 선택사항.",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "최대 생성 토큰 수 (기본값: 512)",
                        "default": 512,
                    },
                },
                "required": ["instruction"],
            },
        ),
        types.Tool(
            name="review_react_code",
            description=(
                "React 코드를 검토하고 개선 제안을 반환합니다. "
                "버그, 성능 문제, 베스트 프랙티스 위반 등을 찾아줍니다."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "검토할 React 코드",
                    },
                    "focus": {
                        "type": "string",
                        "description": "검토 중점 사항 (예: '성능', '타입 안전성', '접근성'). 선택사항.",
                    },
                },
                "required": ["code"],
            },
        ),
        types.Tool(
            name="convert_to_typescript",
            description="JavaScript React 코드를 TypeScript로 변환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "변환할 JavaScript React 코드",
                    },
                },
                "required": ["code"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    if name == "improve_code_file":
        from pathlib import Path
        from agent import tool_read_file, ask_model_to_improve

        file_path = arguments["file_path"]
        focus = arguments.get("focus", "")

        content = tool_read_file(file_path)
        if content.startswith("[읽기 오류]"):
            return [types.TextContent(type="text", text=content)]

        result = ask_model_to_improve(file_path, content)

        output = f"## 분석 결과\n{result['analysis']}\n\n"
        if result["has_changes"]:
            output += f"## 개선된 코드\n```\n{result['improved_code']}\n```"
        else:
            output += "## 결과\n개선 사항 없음 - 코드가 이미 양호합니다."

        return [types.TextContent(type="text", text=output)]

    elif name == "improve_directory":
        from agent import tool_list_files, tool_read_file, ask_model_to_improve
        import json

        directory = arguments["directory"]
        exts = {f".{e.lstrip('.')}" for e in arguments.get("extensions", ["tsx", "ts", "jsx", "js"])}

        files = tool_list_files(directory, exts)
        if not files:
            return [types.TextContent(type="text", text=f"'{directory}'에서 대상 파일을 찾지 못했습니다.")]

        results = []
        for fp in files[:5]:  # MCP에서는 최대 5개 (응답 크기 제한)
            content = tool_read_file(fp)
            r = ask_model_to_improve(fp, content)
            results.append({
                "file": fp,
                "analysis": r["analysis"],
                "has_changes": r["has_changes"],
            })

        output = f"## 디렉토리 분석: {directory}\n총 {len(files)}개 파일 발견, {len(results)}개 분석\n\n"
        for r in results:
            status = "개선 제안 있음" if r["has_changes"] else "양호"
            output += f"### {r['file']}\n**상태:** {status}\n{r['analysis']}\n\n"

        return [types.TextContent(type="text", text=output)]

    elif name == "generate_react_code":
        instruction = arguments["instruction"]
        context = arguments.get("context", "")
        max_tokens = arguments.get("max_tokens", 512)

        result = generate(
            instruction=instruction,
            input_text=context,
            max_new_tokens=max_tokens,
        )
        return [types.TextContent(type="text", text=result)]

    elif name == "review_react_code":
        code = arguments["code"]
        focus = arguments.get("focus", "")

        instruction = "다음 React 코드를 검토하고 개선 사항을 알려줘."
        if focus:
            instruction += f" 특히 {focus}에 집중해서 검토해줘."

        result = generate(
            instruction=instruction,
            input_text=code,
            max_new_tokens=512,
        )
        return [types.TextContent(type="text", text=result)]

    elif name == "convert_to_typescript":
        code = arguments["code"]

        result = generate(
            instruction="다음 JavaScript React 코드를 TypeScript로 변환해줘. 적절한 타입을 추가해줘.",
            input_text=code,
            max_new_tokens=600,
        )
        return [types.TextContent(type="text", text=result)]

    else:
        raise ValueError(f"알 수 없는 툴: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
