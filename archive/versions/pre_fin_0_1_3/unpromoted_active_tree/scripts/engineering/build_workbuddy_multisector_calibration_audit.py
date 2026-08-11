from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.workbuddy_calibration_audit import build_audit, load_json, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit WorkBuddy multi-sector HTML and trajectories.")
    parser.add_argument("--workbuddy-root", type=Path, default=Path.home() / "WorkBuddy")
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".workbuddy")
    args = parser.parse_args()
    config = load_json(ROOT / "configs" / "engineering_handoff" / "workbuddy_multisector_calibration_cases_v0_1.json")
    audit = build_audit(args.workbuddy_root, args.state_root, config)
    json_path = ROOT / "data" / "manifests" / "workbuddy_multisector_calibration_audit_v0_1.json"
    doc_path = ROOT / "docs" / "architecture" / "repository" / "WORKBUDDY_MULTISECTOR_CALIBRATION_AUDIT_20260711.zh-CN.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({key: audit[key] for key in ("status", "case_count", "trace_available_count", "agentic_loop_observed_count", "total_model_calls", "total_tool_calls", "total_web_searches")}))
    return 0 if audit["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
