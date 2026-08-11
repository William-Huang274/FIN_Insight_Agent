from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.workbuddy_expert_variant_audit import build_audit, load_json, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit WorkBuddy expert and skill configuration variants.")
    parser.add_argument("--workbuddy-root", type=Path, default=Path.home() / "WorkBuddy")
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".workbuddy")
    args = parser.parse_args()
    config = load_json(ROOT / "configs" / "engineering_handoff" / "workbuddy_expert_variant_review_v0_1.json")
    audit = build_audit(args.workbuddy_root, args.state_root, config)
    manifest = ROOT / "data" / "manifests" / "workbuddy_expert_variant_audit_v0_1.json"
    report = ROOT / "docs" / "architecture" / "repository" / "WORKBUDDY_EXPERT_VARIANT_AB_AUDIT_20260712.zh-CN.md"
    manifest.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({
        "status": audit["status"],
        "variant_count": audit["variant_count"],
        **audit["promotion_summary"],
    }))
    return 0 if audit["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
