from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts/engineering/run_point01_m2_design_lint.py"
MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m2_design_freeze_manifest_v1_0.json"
REVIEW_PATH = ROOT / "configs/engineering_handoff/point01_m2_cross_owner_design_review_v1_0.json"
SPEC = importlib.util.spec_from_file_location("point01_m2_design_lint", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_m2_design_freeze_manifest_has_complete_acyclic_child_contracts() -> None:
    result = MODULE.build_result(_manifest(), manifest_path=MANIFEST_PATH)
    assert result["status"] == "pass"
    assert result["child_contract_count"] == 10
    assert result["owner_count"] == 10
    assert result["cross_owner_design_review_status"] == "user_confirmed_calibration_accepted"
    assert result["model_execution_permitted"] is False
    assert result["external_call_count"] == 0
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    assert review["independent_human_or_multi_person_signoff"] is False
    assert review["user_confirmation"]["status"] == "accepted"
    assert len(review["reviewer_lenses"]) == 5
    assert len(review["findings"]) == 5


def test_m2_design_lint_fails_closed_for_ownership_cycle_and_model_admission_regression() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["child_contracts"][1]["owned_objects"].append("CompilerInputContract")
    manifest["child_contracts"][0]["dependencies"] = ["M2.2"]
    manifest["child_contracts"][7]["model_run_admission"]["model_execution_permitted"] = True
    errors = MODULE.validate_manifest(manifest)
    assert "object_has_multiple_owners:CompilerInputContract" in errors
    assert "dependency_cycle_detected" in errors
    assert "m2_8_model_admission_must_fail_closed" in errors


def test_m2_design_lint_requires_reachable_contract_producers() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["child_contracts"][3]["input_contracts"].append("UnownedContract")
    manifest["child_contracts"][1]["dependencies"] = ["M2.1"]
    errors = MODULE.validate_manifest(manifest)
    assert "input_contract_without_producer_or_external_declaration:M2.4:UnownedContract" in errors
    assert "input_contract_dependency_missing:M2.2:PackResolution:M2.3" in errors


def test_m2_design_lint_cli_writes_machine_readable_result(tmp_path) -> None:
    output = tmp_path / "m2_design_lint_result.json"
    completed = subprocess.run([sys.executable, str(SCRIPT_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["authority_boundary"]["legacy_task_run"] == "authoritative"
