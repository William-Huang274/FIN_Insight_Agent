"""Static-only contract tests for the M2-A1 receipt execution plan."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/engineering/run_point01_m2_a1_receipt_execution_plan_freeze.py"
SPEC = importlib.util.spec_from_file_location("m2_a1_receipt_execution_plan", RUNNER)
assert SPEC is not None and SPEC.loader is not None
plan_runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan_runner)


def test_historical_v2_3_plan_fails_closed_when_its_consumed_namespace_remains() -> None:
    """Phase B0 must preserve, not erase, the old authority namespace."""

    inputs = plan_runner.verify_inputs()
    assert inputs["status"] == "fail_closed"
    assert "runtime_namespace_must_be_absent_for_plan_freeze" in inputs["failures"]


def test_historical_plan_logic_still_rejects_many_receipts_or_reordered_baseline(monkeypatch) -> None:
    """An in-memory legacy-plan check never reactivates the historical plan."""

    monkeypatch.setattr(plan_runner, "NAMESPACE_PATH", ROOT / ".never-create-historical-v2-3-namespace")
    plan = plan_runner.build_plan()
    many_receipts = deepcopy(plan)
    many_receipts["ledger_constraint"]["chosen_strategy"] = "one_admission_plus_sixteen_receipts"
    many_receipts["plan_digest"] = plan_runner.canonical_digest({key: value for key, value in many_receipts.items() if key != "plan_digest"})
    assert plan_runner.build_gate(many_receipts)["status"] == "fail_closed"

    reordered = deepcopy(plan)
    reordered["scenario_execution_order"][0], reordered["scenario_execution_order"][1] = reordered["scenario_execution_order"][1], reordered["scenario_execution_order"][0]
    reordered["plan_digest"] = plan_runner.canonical_digest({key: value for key, value in reordered.items() if key != "plan_digest"})
    assert plan_runner.build_gate(reordered)["status"] == "fail_closed"
