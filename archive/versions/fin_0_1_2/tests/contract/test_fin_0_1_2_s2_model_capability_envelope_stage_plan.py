from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_deepseek_flash_stable_pro_preview_"
    "natural_capability_envelope_stage_plan_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_9.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_plan_has_four_bounded_tasks_and_no_automatic_T05() -> None:
    plan = _load(PLAN)
    tasks = plan["fixed_tasks"]

    assert plan["status"].startswith("S2_stage_plan_pass_")
    assert [task["task_id"] for task in tasks] == [
        "S2-T01",
        "S2-T02",
        "S2-T03",
        "S2-T04",
    ]
    assert tasks[0]["status"] == "pass"
    assert tasks[1]["status"] == "pending"
    assert tasks[2]["status"] == "pending_separate_authority_required"
    assert tasks[3]["status"] == "pending"
    assert not any(task["task_id"] == "S2-T05" for task in tasks)


def test_flash_and_pro_share_one_route_without_automatic_fallback() -> None:
    plan = _load(PLAN)
    candidates = plan["model_candidates"]
    route = plan["shared_provider_route"]

    assert [(row["model"], row["role"]) for row in candidates] == [
        ("deepseek-v4-flash", "preferred_stable_candidate"),
        ("deepseek-v4-pro", "historical_preview_control"),
    ]
    assert all(row["provider"] == "deepseek" for row in candidates)
    assert all(row["automatic_runtime_mainline"] is False for row in candidates)
    assert route["wire_api"] == "chat_completions_json_object"
    assert route["thinking"] == "disabled"
    assert route["temperature"] == 0.0
    assert route["provider_hopping"] is False
    assert route["automatic_model_fallback"] is False


def test_paired_canary_collects_all_isolated_semantic_results_under_hard_budget() -> None:
    plan = _load(PLAN)
    canary = plan["paired_canary_contract"]
    budget = plan["hard_budget"]

    assert canary["model_count"] == 2
    assert canary["family_count"] == 3
    assert canary["primary_call_count"] == 6
    assert canary["family_outputs_are_isolated"] is True
    assert canary["one_family_output_feeds_another"] is False
    assert canary["semantic_validation_failure_stops_other_independent_calls"] is False
    assert canary["transport_auth_security_or_capture_failure_stops_remaining_calls"] is True
    assert budget["primary_semantic_model_calls"] == 6
    assert budget["maximum_total_semantic_model_calls"] == 8
    assert budget["maximum_affected_family_replacement_pair_calls"] == 2
    assert budget["retry_budget"] == 0
    assert budget["fallback_budget"] == 0
    assert budget["provider_hopping_budget"] == 0
    assert budget["canonical_business_Run_or_Artifact_writes"] == 0


def test_model_surface_is_smaller_than_local_truth_ownership() -> None:
    plan = _load(PLAN)
    families = {row["family_id"]: row for row in plan["changed_contract_families"]}

    assert set(families) == {
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    }
    assert "maximum_six" in families["specialist_fact_atoms"]["current_local_owner"]
    assert "support_role_matrix" in families["claim_candidate_atoms"]["current_local_owner"]
    assert "select_maximum_three" in families["what_would_change_atoms"]["current_local_owner"]
    assert "material_number" in plan["assessment_contract"]["hard_integrity_dimensions"][5]


def test_post_canary_repair_is_bounded_and_not_available_for_model_failure() -> None:
    plan = _load(PLAN)
    rule = plan["post_canary_repair_rule"]

    assert rule["automatic_replacement"] is False
    assert rule["one_consolidated_zero_call_repair_bundle_maximum"] == 1
    assert rule["one_affected_family_two_model_replacement_pair_maximum"] == 1
    assert rule["replacement_for_model_noncompliance_or_weak_quality"] is False
    assert rule["second_new_project_owned_failure_after_replacement"].startswith(
        "S2_honest_block"
    )


def test_historical_evidence_is_bound_without_reclassifying_project_fault_as_model_fault() -> None:
    plan = _load(PLAN)
    historical = plan["historical_evidence_audit"]
    canary = historical["prior_pro_canary"]

    assert _sha256(ROOT / canary["authority_ref"]) == canary["authority_sha256"]
    assert _sha256(ROOT / canary["result_ref"]) == canary["result_sha256"]
    assert canary["result"] == "Fact_pass_Claim_failed_WWC_not_called"
    assert canary["model_or_provider_fault_established_for_Claim"] is False
    assert historical["strict_schema_transport"]["status"] == "parked_nonblocking"


def test_current_gap_blocks_calls_but_does_not_reopen_S1() -> None:
    plan = _load(PLAN)
    gap = plan["current_owned_gap"]

    assert gap["issue_id"].startswith("RC-P36-098-")
    assert gap["S1_reopened"] is False
    assert gap["earliest_owner"] == "S2-T02"
    assert plan["authority"]["model_canary_requires_separate_authority"] is True
    assert plan["authority"]["model_provider_network_or_business_execution_authorized"] is False
    assert set(plan["observed_counts"].values()) == {0}


def test_projection_binds_stage_plan_and_routes_only_to_zero_call_T02() -> None:
    plan = _load(PLAN)
    projection = _load(PROJECTION)

    assert projection["decision_binding"]["ref"] == PLAN.relative_to(ROOT).as_posix()
    assert projection["decision_binding"]["sha256"] == _sha256(PLAN)
    truth = projection["current_truth"]
    assert truth["stage"] == "S2"
    assert truth["S2_started"] is True
    assert truth["S2_stage_plan_passed"] is True
    assert truth["S2_model_canary_authorized"] is False
    assert truth["S2_model_calls"] == 0
    assert truth["current_next_action"] == plan["next_action"]
    assert projection["execution_authority"][
        "credential_model_provider_network_business_authorized"
    ] is False
