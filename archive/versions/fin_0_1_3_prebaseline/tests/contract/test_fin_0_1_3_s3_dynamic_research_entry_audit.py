from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


POLICY = ROOT / "configs/runtime" / (
    "fin_ia_0_1_3_s3_dynamic_research_planner_evidence_request_"
    "and_content_quality_entry_policy_v1_0.json"
)
RESULT = ROOT / "configs/releases" / (
    "fin_ia_0_1_3_s3_dynamic_research_entry_audit_and_scope_"
    "disposition_v1_0.json"
)
REGISTRY = ROOT / "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json"
ISSUES = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
ZERO_SCOPE = (
    "FIN_0_1_3_S3_DYNAMIC_RESEARCH_PLANNER_EVIDENCE_REQUEST_"
    "AND_CONTENT_QUALITY_ZERO_CALL"
)
FORMAL_SCOPE = "FIN_0_1_3_S3_Experiment_B_end_to_end_agentic_research"


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _assert_canonical(value: dict) -> None:
    body = {key: row for key, row in value.items() if key != "result_digest"}
    assert value["result_digest"] == canonical_digest(body)


def _latest_issue(prefix: str) -> dict:
    latest: dict | None = None
    for raw in ISSUES.read_text(encoding="utf-8").splitlines():
        row = json.loads(raw)
        if str(row.get("issue_id", "")).startswith(prefix):
            latest = row
    assert latest is not None
    return latest


def test_entry_policy_is_canonical_dynamic_and_zero_call() -> None:
    policy = _load(POLICY)
    _assert_canonical(policy)

    planner = policy["planner_contract"]
    assert "compile_10_to_20_decision_cells_from_the_open_question_not_from_a_fixed_call_count" in planner[
        "required_behavior"
    ]
    assert "fixed_three_cell_or_fixed_nine_call_report_plan" in planner[
        "forbidden_behavior"
    ]
    assert policy["evidence_request_loop"]["invariants"] == [
        "writer_has_no_source_tools",
        "retrieval_candidate_is_not_evidence",
        "new_evidence_cannot_change_a_judgment_without_cell_re_adjudication",
        "typed_gap_is_a_valid_terminal_state",
        "no_automatic_retry_or_provider_fallback",
        "source_tool_model_and_budget_failures_keep_their_own_stage_and_code",
    ]
    assert policy["zero_call_authority"]["fresh_authority_required_before_any_live"]
    assert "provider_or_model_call" in policy["zero_call_authority"]["forbidden_now"]


def test_entry_policy_keeps_numeric_wwc_and_content_quality_boundaries() -> None:
    policy = _load(POLICY)

    threshold = policy["mechanism_and_wwc_contract"]["threshold_policy"]
    assert threshold["numeric_threshold_allowed_only_when_bound_to_numeric_fact_formula_or_approved_scenario"]
    assert threshold["model_may_propose_unbound_numeric_threshold"] is False
    assert threshold["no_authoritative_threshold_result"] == (
        "cannot_operationalize_numeric_threshold_with_current_evidence"
    )

    economy = policy["information_economy_contract"]
    assert "unsupported_material_claim" in economy["hard_failures"]
    assert "cross_section_repetition" in economy["quality_findings"]

    quality = policy["quality_acceptance"]
    assert quality["absolute_thresholds"] == {
        "total_minimum": 24,
        "Q1_to_Q7_minimum": 2,
        "Q1_Q2_Q3_Q8_minimum": 3,
        "dimensions_at_or_above_three_minimum": 4,
    }
    assert quality["paired_thresholds"]["material_gain_dimensions_minimum"] == 3
    assert quality["final_authority"]["qualified_human_content_acceptance_required"]
    assert quality["final_authority"]["codex_or_automation_may_sign"] is False


def test_run_scopes_separate_zero_call_engineering_from_formal_research() -> None:
    registry = _load(REGISTRY)
    scopes = registry["scopes"]

    assert scopes["FIN_0_1_3_S3"] == {
        "owner_stage": "S3",
        "operation_class": "namespace",
        "parent_scope_id": "FIN_0_1_3",
        "executable": False,
        "allowed_projection_owner_stages": ["shared", "S1", "S2", "S3"],
    }
    assert scopes[ZERO_SCOPE]["operation_class"] == "shared_governance_implementation"
    assert scopes[ZERO_SCOPE]["parent_scope_id"] == "FIN_0_1_3_S3"
    assert scopes[ZERO_SCOPE]["executable"] is True
    assert scopes[FORMAL_SCOPE]["operation_class"] == "agentic_research"
    assert scopes[FORMAL_SCOPE]["parent_scope_id"] == "FIN_0_1_3_S3"


def test_stale_historical_projections_close_but_real_product_boundaries_stay_open() -> None:
    for prefix in ("RC-P36-151", "RC-P36-152", "RC-P36-154", "RC-P36-155"):
        row = _latest_issue(prefix)
        assert row["blocker_state"] == "closed"
        assert row["full_chain_blocker"] is False
        assert row["blocking_run_scopes"] == []
        assert row["original_failure_preserved"] is True
        for ref in row["evidence_refs"]:
            assert (ROOT / ref).exists(), ref

    assert _latest_issue("RC-P36-157")["blocker_state"] == "mitigated_open"
    assert _latest_issue("RC-P36-165")["blocker_state"] == "mitigated_open"
    assert _latest_issue("RC-P36-172")["blocker_state"] == "open"
    assert all(
        _latest_issue(prefix)["full_chain_blocker"] is True
        for prefix in ("RC-P36-157", "RC-P36-165", "RC-P36-172")
    )


def test_scoped_preflight_passes_while_formal_scope_remains_honestly_blocked() -> None:
    zero_call = run_project_os_preflight(ROOT, run_scope=ZERO_SCOPE)
    assert zero_call["status"] == "pass"
    assert zero_call["open_full_chain_blocker_count"] == 0
    assert zero_call["contract_errors"] == []

    formal = run_project_os_preflight(ROOT, run_scope=FORMAL_SCOPE)
    assert formal["status"] == "blocked"
    assert {
        row["issue_id"].split("-fin-")[0]
        for row in formal["open_full_chain_blockers"]
    } == {"RC-P36-157", "RC-P36-165", "RC-P36-172"}
    assert formal["contract_errors"] == []


def test_entry_decision_is_canonical_zero_call_and_not_formal_acceptance() -> None:
    result = _load(RESULT)
    _assert_canonical(result)

    assert result["preflight_before_correction"]["open_full_chain_blocker_count"] == 7
    assert result["preflight_after_correction"]["zero_call_scope"]["status"] == "pass"
    assert result["preflight_after_correction"]["formal_scope"] == {
        "status": "blocked",
        "open_full_chain_blocker_count": 3,
        "issue_prefixes": ["RC-P36-157", "RC-P36-165", "RC-P36-172"],
    }
    assert result["observed_calls"] == {
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    stage = result["stage_boundary"]
    assert stage["S3_engineering_started"] is True
    assert stage["S3_formal_agentic_research_passed"] is False
    assert stage["qualified_human_content_acceptance"] is False
    assert stage["release"] is False
