from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULT = ROOT / ".codex_runtime/fin012-s4-t05c-mu-agent-exact-live-r1/execution-result.json"


def render_for_host_stdout(value: object) -> str:
    """Remain printable even when Windows stdout uses a legacy GBK codec."""

    return json.dumps(value, ensure_ascii=True, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    payload = json.loads(args.result.resolve().read_text(encoding="utf-8"))
    print(render_for_host_stdout(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
