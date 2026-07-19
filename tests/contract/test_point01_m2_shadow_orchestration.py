from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_9_shadow_orchestration_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_9_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_shadow_orchestrator_integrates_four_sector_attempts_and_replay(tmp_path) -> None:
    result = RUNNER.build_result(tmp_path / "work")
    assert result["status"] == "pass"
    assert result["checks"]["four_sector_shadow_compilations_pass"] is True
    assert result["checks"]["workunit_attempt_artifact_and_replay_integrated"] is True


def test_shadow_orchestrator_feature_flag_and_model_admission_boundaries_fail_closed(tmp_path) -> None:
    result = RUNNER.build_result(tmp_path / "work")
    assert result["checks"]["feature_flag_off_skips_all_writes"] is True
    assert result["checks"]["admitted_model_boundary_rejected_before_write"] is True


def test_m2_9_machine_fixture_cli_is_four_sector_and_model_free(tmp_path) -> None:
    output = tmp_path / "m2_9_shadow_orchestration.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output), "--work-root", str(tmp_path / "runner-work")], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["model_free"] is True
