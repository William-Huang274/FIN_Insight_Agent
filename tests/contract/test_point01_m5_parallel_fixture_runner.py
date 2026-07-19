from __future__ import annotations

import json
from pathlib import Path
from subprocess import run
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_7_parallel_context_fixtures.py"


def test_m5_parallel_context_fixture_runner(tmp_path) -> None:
    output = tmp_path / "parallel_result.json"
    completed = run([sys.executable, str(SCRIPT), "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["evidence"] == {"snapshot_isolated": True, "irrelevant_action": "continue", "rebase_requested_state": "rebase_required", "rebase_context_recompile_requested": True, "recompiled_snapshot_state": "active", "recompiled_context": {"eps": 2}, "cancel_state": "cancelled", "forged_ambiguous_receipt_rejected": True, "ambiguous_receipt_verified": True}
    assert result["worker_started"] is False
    assert result["model_call_count"] == 0
    assert result["external_call_count"] == 0
