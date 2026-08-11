from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract
ROOT = Path(__file__).resolve().parents[2]


def test_m4_cutover_fixture_runner_materializes_case_scoped_m4_1_to_m4_7_results(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "scripts/engineering/run_point01_m4_cutover_fixtures.py", "--output-dir", str(tmp_path), "--work-root", str(tmp_path / "runtime")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads((tmp_path / "point01_m4_cutover_fixture_result_v1_0.json").read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["point_statuses"] == {f"M4.{number}": "pass" for number in range(1, 8)}
