from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.calibration_case_audit import (
    build_calibration_case_selection,
    build_historical_case_audit,
    build_sector_report_archetype_audit,
    load_json,
    render_archetype_audit_markdown,
    render_calibration_selection_markdown,
    render_historical_audit_markdown,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build no-paid historical case and report archetype audits.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config_root = root / "configs" / "engineering_handoff"
    manifest_root = root / "data" / "manifests"
    doc_root = root / "docs" / "architecture" / "repository"

    historical = build_historical_case_audit(
        root, load_json(config_root / "historical_case_audit_sources_v0_1.json")
    )
    archetype = build_sector_report_archetype_audit(
        load_json(config_root / "sector_report_archetype_sources_v0_1.json")
    )
    selection = build_calibration_case_selection(historical, archetype)

    _write_json(manifest_root / "historical_case_performance_audit_v0_1.json", historical)
    _write_json(manifest_root / "sector_report_archetype_audit_v0_1.json", archetype)
    _write_json(manifest_root / "calibration_case_selection_v0_1.json", selection)
    (doc_root / "HISTORICAL_CASE_PERFORMANCE_AUDIT_20260711.zh-CN.md").write_text(
        render_historical_audit_markdown(historical), encoding="utf-8"
    )
    (doc_root / "SECTOR_REPORT_ARCHETYPE_AUDIT_20260711.zh-CN.md").write_text(
        render_archetype_audit_markdown(archetype), encoding="utf-8"
    )
    (doc_root / "CALIBRATION_CASE_SELECTION_20260711.zh-CN.md").write_text(
        render_calibration_selection_markdown(selection), encoding="utf-8"
    )
    print(json.dumps({"historical": historical["status"], "archetype": archetype["status"], "selection": selection["status"]}))
    return 0 if all(value["status"] == "pass" for value in (historical, archetype, selection)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
