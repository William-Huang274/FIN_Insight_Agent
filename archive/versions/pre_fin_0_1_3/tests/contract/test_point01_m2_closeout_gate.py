from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_closeout_gate.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_closeout_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_m2_closeout_gate_passes_full_deterministic_shadow_scope(tmp_path) -> None:
    result = RUNNER.build_result(tmp_path / "work")
    assert result["gate_status"] == "pass"
    assert result["milestone_status"] == "M2_complete"
    assert all(result["checks"].values())


def test_m2_closeout_evaluator_detects_missing_child_point() -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m2_closeout_gate_manifest_v1_0.json").read_text(encoding="utf-8"))
    children = {point: {"returncode": 0, "payload": {"status": "pass", "checks": {}, "authority_boundary": {"model_call_count": 0, "external_call_count": 0}}} for point in RUNNER.RUNNERS}
    children["M2.2"]["returncode"] = 1
    checks = RUNNER.evaluate(children, manifest)
    assert checks["all_m2_0_to_m2_9_machine_artifacts_pass"] is False


def test_m2_closeout_gate_cli_is_replayable(tmp_path) -> None:
    output = tmp_path / "m2_closeout.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output), "--work-root", str(tmp_path / "runner-work")], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["gate_status"] == "pass"
