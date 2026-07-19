from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("point01_m4_design_lint", ROOT / "scripts/engineering/run_point01_m4_design_lint.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_m4_design_freeze_lint_preserves_case_scoped_legacy_authority_boundary() -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m4_design_freeze_manifest_v1_0.json").read_text(encoding="utf-8"))
    result = MODULE.build_result(manifest)
    assert result["status"] == "pass"
    assert result["authority_boundary"]["legacy_task_run"] == "authoritative"


def test_m4_design_freeze_requires_all_child_dependencies_for_closeout() -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m4_design_freeze_manifest_v1_0.json").read_text(encoding="utf-8"))
    closeout = next(row for row in manifest["child_contracts"] if row["point_id"] == "M4.8")
    closeout["dependencies"] = ["M4.1"]
    assert "m4_8_dependencies_incomplete" in MODULE.validate_manifest(manifest)
