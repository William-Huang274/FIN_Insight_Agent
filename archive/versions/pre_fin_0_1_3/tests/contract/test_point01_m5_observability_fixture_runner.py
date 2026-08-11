from __future__ import annotations

import json
from pathlib import Path
from subprocess import run
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_8_observability_ops_fixtures.py"


def test_m5_observability_fixture_runner(tmp_path) -> None:
    output = tmp_path / "ops_result.json"
    completed = run([sys.executable, str(SCRIPT), "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["evidence"]["reconnect_has_no_duplicate"] is True
    assert result["evidence"]["open_alert_count"] == 1
    assert result["evidence"]["raw_reasoning_rejected"] is True
    assert result["worker_started"] is False
    assert result["model_call_count"] == 0
    assert result["external_call_count"] == 0
