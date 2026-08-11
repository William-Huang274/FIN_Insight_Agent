from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "scripts/releases/run_fin_ia_0_1_3_s2_05_experiment_a.py"


def test_production_preflight_binds_layered_successor_without_provider_call() -> None:
    completed = subprocess.run(
        [sys.executable, str(ENTRYPOINT), "--preflight-only"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "zero_call_layered_preflight_ready_admission_not_issued"
    assert result["execution_mode"] == "capture_first_full_chain_then_layered_evaluation"
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0
    assert result["admission_issued"] is False


def test_production_source_calls_layered_executor_not_legacy_executor() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert "execute_case_layered(" in source
    assert "result = execute_case(" not in source
