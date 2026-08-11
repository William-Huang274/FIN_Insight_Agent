from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from sec_agent.repository_architecture_inventory import evaluate_repository_architecture_guard  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate repository architecture, complexity, archive, and Git hygiene gates.")
    parser.add_argument("--inventory", default="data/manifests/repository_architecture_inventory_v0_1.json")
    parser.add_argument("--policy", default="configs/repository/code_health_guard_policy_v0_1.json")
    parser.add_argument("--output", default="data/manifests/repository_code_health_guard_v0_1.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inventory = json.loads((REPO_ROOT / args.inventory).read_text(encoding="utf-8"))
    policy = json.loads((REPO_ROOT / args.policy).read_text(encoding="utf-8"))
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    result = evaluate_repository_architecture_guard(inventory, policy, tracked_paths=tracked)
    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
