from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.mcp_tool_registry import invoke_mcp_tool, list_registered_tools  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Invoke a FinSight-Agent MCP registry tool without an MCP client.")
    parser.add_argument("--tool", required=True)
    parser.add_argument("--args-json", default="{}")
    parser.add_argument("--list-tools", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_tools:
        print(json.dumps({"status": "ok", "tools": list_registered_tools()}, ensure_ascii=False, indent=2))
        return 0
    try:
        arguments = json.loads(args.args_json)
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "error": f"invalid_args_json:{exc.msg}"}, ensure_ascii=False))
        return 2
    if not isinstance(arguments, dict):
        print(json.dumps({"status": "error", "error": "args_json_must_be_object"}, ensure_ascii=False))
        return 2
    result = invoke_mcp_tool(args.tool, arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") not in {"error"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

