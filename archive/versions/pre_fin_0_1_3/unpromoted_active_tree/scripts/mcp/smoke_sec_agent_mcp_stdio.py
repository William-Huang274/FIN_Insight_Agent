from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the FinSight-Agent MCP stdio server.")
    parser.add_argument(
        "--server-script",
        default="scripts/mcp/run_sec_agent_mcp_server.py",
        help="MCP stdio server script to launch.",
    )
    parser.add_argument("--call-contract-tool", action="store_true", help="Also call list_sec_agent_tools.")
    return parser.parse_args()


async def _run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
    except ImportError as exc:
        return {"status": "error", "error": f"mcp_not_installed:{exc}"}

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(args.server_script)],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            payload: dict[str, Any] = {
                "status": "ok",
                "tool_count": len(tool_names),
                "tool_names": tool_names,
                "has_sec_search_filings": "sec_search_filings" in tool_names,
            }
            if args.call_contract_tool:
                result = await session.call_tool("list_sec_agent_tools", {})
                payload["list_sec_agent_tools_content_count"] = len(result.content)
            return payload


def main() -> int:
    try:
        import anyio
    except ImportError as exc:
        print(json.dumps({"status": "error", "error": f"anyio_not_installed:{exc}"}, ensure_ascii=False))
        return 2

    result = anyio.run(_run_smoke, parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
