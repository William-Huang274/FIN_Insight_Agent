from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m3_closeout_gate.py"
SPEC = importlib.util.spec_from_file_location("point01_m3_closeout_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_m3_closeout_gate_passes_after_current_thread_human_approval(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m3_closeout_gate_manifest_v1_0.json").read_text(encoding="utf-8"))
    result = MODULE.build_result(manifest, work_root=tmp_path)
    assert result["status"] == "pass"
    assert result["milestone"] == "M3_complete"
    assert result["unmet_conditions"] == []
    assert all(result["required_point_statuses"][f"M3.{number}"] == "pass" for number in range(1, 8))


def test_m3_human_approval_contract_requires_explicit_human_scope_and_boundary() -> None:
    approved = json.loads((ROOT / "configs/engineering_handoff/point01_m3_human_reviewer_approval_v1_0.json").read_text(encoding="utf-8"))
    pending = {**approved, "status": "pending_human_reviewer_approval", "approver_type": None, "approver_identity": None, "approved_at": None, "decision": None}
    assert MODULE._approval_errors(pending) == ["human_reviewer_approval_pending"]
    assert MODULE._approval_errors(approved) == []
