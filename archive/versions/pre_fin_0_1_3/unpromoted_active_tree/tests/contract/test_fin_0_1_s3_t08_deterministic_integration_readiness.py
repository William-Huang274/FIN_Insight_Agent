from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_PROFILE_REF,
    BoundedAgentAdmission,
    DeepSeekBoundedAgentExecutor,
    build_bounded_agent_input_pack,
)
from sec_agent.memo_llm import S3ThreeCellPresentationPackVersion
from tests.contract.test_fin_0_1_s3_t04_financial_numeric_fundamental_pack import (
    _run_payload,
)


RELEASES = ROOT / "configs" / "releases"
T08 = (
    RELEASES
    / "fin_ia_0_1_s3_t08_deterministic_integration_and_exact_live_readiness_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _contract() -> dict[str, Any]:
    return json.loads(T08.read_text(encoding="utf-8"))


def _pack(payload: dict[str, Any]) -> S3ThreeCellPresentationPackVersion:
    return S3ThreeCellPresentationPackVersion.model_validate(
        payload["s3_three_cell_presentation_pack"]
    )


def _latest_root_causes() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[str(row["issue_id"])] = row
    return latest


def test_t08_gate_remains_historical_while_current_backlog_advances_honestly() -> None:
    contract = _contract()
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert contract["status"] == (
        "pass_readiness_gate_exact_live_blocked_owned_three_cell_executor_gap"
    )
    assert contract["authority"]["S3_T09_execution_or_admission_issuance_authorized"] is False
    assert contract["exact_live_readiness_decision"]["S3_T09_may_execute"] is False
    assert contract["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "automatic_new_research_calls": 0,
        "live_business_writes": 0,
        "human_review_writes": 0,
        "new_admissions": 0,
        "paid_runs": 0,
    }
    s3 = next(row for row in backlog["slices"] if row["slice_id"] == "S3")
    t08 = next(row for row in s3["items"] if row["item_id"] == "S3-T08")
    t09 = next(row for row in s3["items"] if row["item_id"] == "S3-T09")
    assert t08["status"] == (
        "pass_readiness_gate_and_three_cell_adapter_repair_T09_ready_pending_separate_authority"
    )
    assert "S3-T08" in t09["depends_on"]
    assert backlog["next_action"]["item_id"] != "S3-T08"


def test_t08_deterministic_fixture_has_exact_three_terminal_cells_and_artifacts(
    tmp_path: Path,
) -> None:
    contract = _contract()
    payload = _run_payload(tmp_path)
    pack = _pack(payload)
    proof = contract["deterministic_integration_proof"]
    binding = pack.trace_review.review_binding
    assert pack.case_id == proof["case_id"]
    assert pack.work_unit_id == proof["work_unit_id"]
    assert pack.attempt_id == proof["attempt_id"]
    assert pack.research_run_id == proof["research_run_id"]
    assert binding.input_head_digest == proof["input_head_digest"]
    assert binding.verifier_input_digest == proof["verifier_input_digest"]
    assert payload["artifact_manifest"] == proof["artifact_manifest"]
    assert len(pack.surface_claims) == proof["exact_cell_count"] == 3
    observed = {
        row.program_cell_id: {
            "accepted_evidence_count": len(row.evidence_refs),
            "numeric_count": len(row.numeric_refs),
            "stop_semantic": row.stop_semantic,
        }
        for row in pack.surface_claims
    }
    for row in proof["cell_outcomes"]:
        assert observed[row["program_cell_id"]] == {
            "accepted_evidence_count": row["accepted_evidence_count"],
            "numeric_count": row["numeric_count"],
            "stop_semantic": row["stop_semantic"],
        }


def test_t08_method_runtime_lifecycle_is_deterministic_not_paid_claim(
    tmp_path: Path,
) -> None:
    contract = _contract()
    payload = _run_payload(tmp_path)
    graph_pack = payload["s3_bounded_graph_product_market_risk_pack"]
    observed_methods = {
        method_id
        for row in graph_pack["skill_contracts"]
        for method_id in row["method_ids"]
    }
    proof = contract["method_to_runtime_proof"]
    assert observed_methods == set(proof["method_ids"])
    assert [row["target_node"] for row in payload["s3_specialist_lead_consumption_receipts"]] == [
        "domain_specialist",
        "domain_specialist",
        "domain_specialist",
        "research_lead",
    ]
    assert {row["target_node"] for row in payload["s3_presentation_consumption_receipts"]} == {
        "memo_writer",
        "verifier",
        "workbench",
    }
    assert proof["lifecycle_state"] == (
        "runtime_injected_and_node_level_consumed_deterministic_only"
    )
    assert proof["paid_artifact_proven"] is False
    assert proof["human_accepted"] is False


def test_t08_reconciles_all_fifteen_latest_root_causes_without_false_close() -> None:
    reconciliation = _contract()["root_cause_reconciliation"]
    issues = reconciliation["issues"]
    latest = _latest_root_causes()
    assert len(issues) == reconciliation["required_issue_count"] == 15
    assert reconciliation["fully_closed_by_T08"] == 0
    assert sum(row["blocks_current_exact_live_readiness"] for row in issues) == 12
    assert all(row["issue_id"] in latest for row in issues)
    assert all(latest[row["issue_id"]]["full_chain_blocker"] is True for row in issues)


def test_t08_freezes_exact_paired_baseline_and_product_review_contracts() -> None:
    contract = _contract()
    baseline = contract["paired_deterministic_baseline_contract"]
    review = contract["product_review_contract"]
    assert baseline["baseline_profile_ref"] == (
        "fin01.execution_profile.p36_local_deterministic:v1"
    )
    assert baseline["agent_profile_ref_required"] == (
        "fin01.execution_profile.bounded_agent_internal_three_cell:v1"
    )
    assert "input_head_digest" in baseline["must_match"]
    assert set(baseline["must_be_distinct"]) == {
        "work_unit_id",
        "attempt_id",
        "research_run_id",
        "artifact_refs",
    }
    assert baseline["agent_failure_may_trigger_automatic_fallback"] is False
    assert baseline["comparison_requires_two_terminal_runs"] is True
    assert review["review_status"] == "not_performed"
    assert review["machine_verifier_may_sign_human_decision"] is False
    assert len(review["hard_failures"]) == 6
    assert len(review["material_gain_dimensions"]) == 9


def test_t08_D07B_policy_is_NVDA_hypothesis_not_universal_calibration() -> None:
    policy = _contract()["D07B_NVDA_initial_policy"]
    assert policy["status"] == "hypothesis_not_calibrated_policy"
    assert policy["scope"] == "NVDA_three_cell_only"
    assert policy["universal_or_cross_case_calibration_claimed"] is False
    assert policy["historical_runs_rewritten_by_policy_change"] is False
    assert len(policy["cell_hypotheses"]) == 3
    assert policy["remaining_three_case_calibration_task"] == "S4"


def test_t08_production_live_path_behaviorally_remains_single_cell() -> None:
    admission = BoundedAgentAdmission(
        admission_id="fin01-s3-t08-readiness-probe-not-an-admission",
        execution_mode="zero_call_readiness_probe",
        maximum_cell_count=3,
    )
    with pytest.raises(ValueError, match="bounded_admission_single_cell_required"):
        admission.assert_profile_admissible()
    assert admission.execution_profile_version_ref == BOUNDED_AGENT_PROFILE_REF
    input_source = inspect.getsource(build_bounded_agent_input_pack)
    assert 'row.get("evidence_role") == "demand_signal"' in input_source
    assert "bounded_input_single_cell_baseline_required" in input_source
    assert "single-cell executor" in str(DeepSeekBoundedAgentExecutor.__doc__)
    assert DeepSeekBoundedAgentExecutor._ROLE_AGENT_IDS == (
        "research_lead",
        "industry_supply_chain_analyst",
        "judgment_plan_aggregator",
        "memo_writer",
        "verifier",
    )
    decision = _contract()["exact_live_readiness_decision"]
    assert decision["earliest_faulty_owner"] == (
        "apps/workbench/backend/application/bounded_agent_executor.py"
    )
    assert decision["new_admission_issued"] is False
