from __future__ import annotations

import json
from pathlib import Path
from subprocess import run
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_6_hitl_governance_fixtures.py"


def test_m5_hitl_governance_fixture_runner(tmp_path) -> None:
    output = tmp_path / "hitl_result.json"
    completed = run([sys.executable, str(SCRIPT), "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["evidence"]["pause_survived_restart"] is True
    assert result["evidence"]["persisted_registry_authority_survives_restart"] is True
    assert result["evidence"]["resumed_fencing_token"] == 2
    assert result["evidence"]["revoked_resume_blocked"] is True
    assert result["evidence"]["pause_event_count"] == 2
    assert result["evidence"]["resume_event_count"] == 1
    assert result["evidence"]["invalidation_event_count"] == 1
    assert result["worker_started"] is False
    assert result["model_call_count"] == 0
    assert result["external_call_count"] == 0
