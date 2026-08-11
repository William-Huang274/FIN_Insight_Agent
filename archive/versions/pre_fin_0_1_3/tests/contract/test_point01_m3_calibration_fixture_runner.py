from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]


def test_m3_calibration_fixture_runner_materializes_all_child_results(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/engineering/run_point01_m3_calibration_fixtures.py", "--output-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads((tmp_path / "point01_m3_calibration_fixture_result_v1_0.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["status"] == "pass"
    assert result["point_statuses"] == {f"M3.{number}": "pass" for number in range(1, 8)}
    assert all((tmp_path / f"point01_m3_{number}_fixture_result_v1_0.json").is_file() for number in range(1, 8))
