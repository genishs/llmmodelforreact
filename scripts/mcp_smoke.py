# -*- coding: utf-8 -*-
"""MCP 서버 스모크 테스트: initialize → list_tools → generate_react_code 호출."""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(ROOT, "src", "mcp_server.py")],
        cwd=ROOT,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            print("--- call generate_react_code (7B 로딩 ~18s) ---")
            res = await session.call_tool(
                "generate_react_code",
                {"instruction": "Create a useToggle custom hook in TypeScript.",
                 "max_tokens": 90},
            )
            for c in res.content:
                print("RESULT:\n" + c.text)


if __name__ == "__main__":
    asyncio.run(main())
