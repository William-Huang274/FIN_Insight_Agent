from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_design_lint.py"
SPEC = importlib.util.spec_from_file_location("point01_m5_design_lint", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest() -> dict[str, object]:
    return json.loads((ROOT / "configs/engineering_handoff/point01_m5_design_freeze_manifest_v1_0.json").read_text(encoding="utf-8"))


def test_m5_design_freeze_lint_accepts_design_only_human_approval_without_runtime_admission() -> None:
    result = MODULE.build_result(_manifest())
    assert result["status"] == "pass"
    assert result["human_ops_security_review_status"] == "approved_m5_design_freeze_only"
    assert result["authority_boundary"]["model_execution"] == "not_admitted"
    assert "does not approve M5.1 execution" in result["boundary"]


def test_m5_design_freeze_rejects_incomplete_aggregate_dependencies() -> None:
    manifest = _manifest()
    closeout = next(row for row in manifest["children"] if row["point_id"] == "M5.9")
    closeout["dependencies"] = ["M5.1"]
    assert "m5_9_dependencies_must_cover_m5_1_to_m5_8" in MODULE.validate_manifest(manifest)


def test_m5_design_freeze_rejects_missing_security_acceptance() -> None:
    manifest = _manifest()
    capability_security = next(row for row in manifest["children"] if row["point_id"] == "M5.4")
    capability_security["acceptance"].remove("tenant cross-read denied")
    assert "M5.4:missing_acceptance:tenant cross-read denied" in MODULE.validate_manifest(manifest)
