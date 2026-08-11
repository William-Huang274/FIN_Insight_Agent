from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from sec_agent.repository_architecture_inventory import (  # noqa: E402
    build_repository_architecture_inventory,
    load_inventory_policy,
    write_inventory_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the maintained FinSight repository architecture inventory.")
    parser.add_argument(
        "--policy",
        default="configs/repository/architecture_inventory_policy_v0_1.json",
    )
    parser.add_argument(
        "--json-output",
        default="data/manifests/repository_architecture_inventory_v0_1.json",
    )
    parser.add_argument(
        "--markdown-output",
        default="docs/architecture/repository/REPOSITORY_ARCHITECTURE_MAP.zh-CN.md",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    policy = load_inventory_policy(REPO_ROOT / args.policy)
    inventory = build_repository_architecture_inventory(REPO_ROOT, policy)
    write_inventory_outputs(
        inventory,
        json_path=REPO_ROOT / args.json_output,
        markdown_path=REPO_ROOT / args.markdown_output,
    )
    print(json.dumps(inventory["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
