from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_concurrency_security_drills.py"
POLICY = ROOT / "configs/engineering_handoff/point01_m5_concurrency_security_policy_v1_0.json"
SPEC = importlib.util.spec_from_file_location("point01_m5_concurrency_security", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_concurrent_budget_and_security_synthetic_drill_is_atomic_and_fail_closed() -> None:
    result = MODULE.build_result(json.loads(POLICY.read_text(encoding="utf-8")), policy_path=POLICY)
    assert result["status"] == "pass"
    assert result["evidence"]["budget_outcomes"] == ["reserved", "terminal_stop"]
    assert result["evidence"]["security_outcomes"] == ["allowed", "denied"]
    assert result["evidence"]["revoked_grant_denial_code"] == "capability_grant_revoked"
    assert result["worker_started"] is False
    assert result["external_call_count"] == 0
