from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m3_design_lint.py"
SPEC = importlib.util.spec_from_file_location("point01_m3_design_lint", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_m3_design_freeze_lint_passes_and_preserves_shadow_boundary() -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m3_design_freeze_manifest_v1_0.json").read_text(encoding="utf-8"))
    result = MODULE.build_result(manifest)
    assert result["status"] == "pass"
    assert result["authority_boundary"]["legacy_task_run"] == "authoritative"
    assert result["authority_boundary"]["cutover"] == "forbidden"


def test_m3_design_freeze_lint_rejects_incomplete_closeout_dependencies() -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m3_design_freeze_manifest_v1_0.json").read_text(encoding="utf-8"))
    closeout = next(row for row in manifest["child_contracts"] if row["point_id"] == "M3.8")
    closeout["dependencies"] = ["M3.1"]
    assert "m3_8_dependencies_must_cover_m3_1_to_m3_7" in MODULE.validate_manifest(manifest)
