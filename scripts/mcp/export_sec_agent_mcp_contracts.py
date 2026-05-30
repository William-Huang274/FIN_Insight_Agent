from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.mcp_contracts import export_mcp_tool_contracts, validate_mcp_tool_contracts  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export FinSight-Agent MCP tool contracts.")
    parser.add_argument(
        "--output",
        default="configs/mcp/sec_agent_mcp_tool_contracts_v0_1.json",
        help="Destination JSON contract path.",
    )
    parser.add_argument("--check", action="store_true", help="Validate contracts without writing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        payload = export_mcp_tool_contracts()
        validate_mcp_tool_contracts(payload["tools"])
        print(json.dumps({"status": "ok", "tool_count": len(payload["tools"])}, ensure_ascii=False))
        return 0
    payload = export_mcp_tool_contracts(REPO_ROOT / args.output)
    print(json.dumps({"status": "ok", "tool_count": len(payload["tools"]), "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

