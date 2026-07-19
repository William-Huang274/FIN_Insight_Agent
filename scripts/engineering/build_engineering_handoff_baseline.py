from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.engineering_handoff import (
    build_handoff_summary,
    load_json,
    render_handoff_markdown,
    write_json,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the canonical/legacy/test-profile handoff baseline.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser.parse_args()


def main() -> int:
    root = parse_args().repo_root.resolve()
    config_root = root / "configs" / "engineering_handoff"
    summary = build_handoff_summary(
        root,
        load_json(config_root / "canonical_object_registry_v0_1.json"),
        load_json(config_root / "legacy_object_mapping_matrix_v0_1.json"),
        load_json(config_root / "test_profile_registry_v0_1.json"),
    )
    write_json(root / "data" / "manifests" / "engineering_handoff_summary_v0_1.json", summary)
    write_text(
        root / "docs" / "architecture" / "repository" / "ENGINEERING_HANDOFF_BASELINE_20260711.zh-CN.md",
        render_handoff_markdown(summary),
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "canonical_object_count": summary["canonical_object_count"],
                "legacy_mapping_count": summary["legacy_mapping_count"],
                "runtime_cutover_count": summary["runtime_cutover_count"],
                "test_file_count": summary["test_profile_audit"]["test_file_count"],
                "test_profile_file_counts": summary["test_profile_audit"]["profile_file_counts"],
                "errors": summary["errors"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
