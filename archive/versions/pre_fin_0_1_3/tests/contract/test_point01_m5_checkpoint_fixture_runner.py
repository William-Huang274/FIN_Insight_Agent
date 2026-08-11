from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_3_checkpoint_artifact_fixtures.py"
SPEC = importlib.util.spec_from_file_location("point01_m5_checkpoint_fixture_runner", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_m5_checkpoint_fixture_runner_proves_versioning_and_restart_recovery() -> None:
    policy_path = ROOT / "configs/engineering_handoff/point01_m5_3_checkpoint_artifact_policy_v1_0.json"
    result = MODULE.build_result(json.loads(policy_path.read_text(encoding="utf-8")), policy_path=policy_path)
    assert result["status"] == "pass"
    assert result["evidence"]["checkpoint_event_count"] == result["evidence"]["checkpoint_artifact_count"] == 2
    assert result["evidence"]["stale_write_blocked"] is True
    assert result["evidence"]["restart_snapshot_matches_v2"] is True
    assert result["worker_started"] is False
    assert result["model_call_count"] == result["external_call_count"] == 0
