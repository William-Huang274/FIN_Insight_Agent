from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_8_model_admission_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_8_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_model_admission_denies_missing_preflights_without_adapter_call() -> None:
    result = RUNNER.build_result()
    assert result["status"] == "pass"
    assert result["checks"]["denied_path_records_all_missing_admission_inputs"] is True
    assert result["adapter_call_count"] == 0


def test_model_admission_policy_remains_hard_denied_even_with_other_gates_ready() -> None:
    result = RUNNER.build_result()
    proposal = result["otherwise_ready_but_policy_denied_proposal"]
    assert proposal["admission_decision"]["denial_reasons"] == ["policy_model_execution_disabled"]
    assert proposal["structured_output_repair_trace"]["status"] == "not_attempted"


def test_m2_8_machine_fixture_cli_is_replayable_and_model_free(tmp_path) -> None:
    output = tmp_path / "m2_8_model_admission.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["model_free"] is True
