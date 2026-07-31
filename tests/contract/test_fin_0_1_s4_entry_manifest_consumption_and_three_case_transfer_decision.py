from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
R7_EXACT_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "exact_live_execution_failure_result_v1_0.json"
)
R7_BINDING_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_case_runtime_"
    "binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
WWC_TRUNCATION_DISPOSITION = RELEASES / (
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "assembly_fresh_agent_proof_decision_v1_0.json"
)
WWC_ATOM_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_case_runtime_binding_"
    "mismatch_zero_call_root_cause_disposition_v1_0.json"
)
GAP_PROJECTION_R5_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_AUTHORITY = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_"
    "exact_live_execution_and_paired_assessment_authority_decision_v1_0.json"
)
GAP_PROJECTION_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_"
    "fresh_exact_admission_issuance_v1_0.json"
)
GAP_PROJECTION_FRESH_PROOF = RELEASES / (
    "fin_ia_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_"
    "fresh_agent_proof_decision_v1_0.json"
)
MANIFEST = RELEASES / "fin_ia_0_1_s3_to_s4_early_delivery_carry_forward_manifest_v1_0.json"
ENTRY = RELEASES / (
    "fin_ia_0_1_s4_entry_manifest_consumption_and_three_case_transfer_"
    "decision_v1_0.json"
)
S4_BACKLOG = RELEASES / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
PROGRAM_BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
CROSS_SLICE = RELEASES / (
    "fin_ia_0_1_cross_slice_early_delivery_carry_forward_contract_v1_0.json"
)
S4_PLAN = (
    ROOT
    / "docs"
    / "architecture"
    / "repository"
    / "FIN_0_1_S4_THREE_CASE_TRANSFER_AND_HUMAN_CALIBRATION_EXECUTION_PLAN_20260726.zh-CN.md"
)
R3_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
NUMERIC_AUTHORITY_DISPOSITION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_surface_"
    "zero_call_root_cause_disposition_v1_0.json"
)
NUMERIC_AUTHORITY_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "assembly_fresh_agent_proof_decision_v1_0.json"
)
NUMERIC_AUTHORITY_PROOF = RELEASES / (
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_agent_"
    "proof_decision_v1_0.json"
)
NUMERIC_AUTHORITY_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_exact_"
    "admission_issuance_v1_0.json"
)
NUMERIC_AUTHORITY_DECISION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_exact_live_"
    "execution_and_paired_assessment_authority_decision_v1_0.json"
)
R4_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_DISPOSITION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_"
    "zero_call_root_cause_disposition_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slice(backlog: dict, slice_id: str) -> dict:
    return next(item for item in backlog["slices"] if item["slice_id"] == slice_id)


def test_entry_consumes_exact_frozen_manifest_and_binds_detailed_backlog() -> None:
    entry = _load(ENTRY)

    assert entry["status"] == (
        "pass_zero_call_manifest_consumed_S4_T01_complete_T02_next"
    )
    assert entry["authority"]["user_instruction"] == "认可"
    assert entry["consumed_manifest"]["expected_sha256"] == _sha256(MANIFEST)
    assert entry["consumed_manifest"]["observed_sha256"] == _sha256(MANIFEST)
    assert entry["consumed_manifest"]["digest_equal"] is True
    assert entry["consumed_manifest"]["item_count"] == 8
    assert entry["consumed_manifest"]["historical_manifest_rewritten"] is False
    if R3_FAILURE_RESULT.exists():
        assert entry["detailed_backlog"]["sha256"] != _sha256(S4_BACKLOG)
        assert entry["detailed_backlog"]["sha256"] == (
            "9d54045aa8091d4338d5b4e9460442b1bb5a9d6c2046a683f25ac6d18b38ede3"
        )
    else:
        assert entry["detailed_backlog"]["sha256"] == _sha256(S4_BACKLOG)


def test_all_eight_domains_have_allowed_non_rebuild_dispositions() -> None:
    entry = _load(ENTRY)
    contract = _load(CROSS_SLICE)
    rows = entry["capability_dispositions"]
    allowed = set(
        contract["consumer_contract"]["allowed_later_slice_dispositions"]
    )

    assert len(rows) == 8
    assert {row["capability_domain"] for row in rows} == set(
        contract["required_capability_domains"]
    )
    assert all(row["S4_disposition"] in allowed for row in rows)
    assert all(row["rebuild_allowed_now"] is False for row in rows)
    assert sum(row["S4_disposition"] == "reuse_as_is" for row in rows) == 2
    assert sum(row["S4_disposition"] == "extend" for row in rows) == 2
    assert (
        sum(
            row["S4_disposition"] == "revalidate_for_new_case_or_candidate"
            for row in rows
        )
        == 4
    )


def test_detailed_backlog_freezes_ten_tasks_case_order_and_stop_rules() -> None:
    backlog = _load(S4_BACKLOG)
    tasks = backlog["tasks"]

    assert [task["item_id"] for task in tasks] == [
        f"S4-T{index:02d}" for index in range(1, 11)
    ]
    assert tasks[0]["status"] == (
        "pass_zero_call_manifest_consumed_and_detailed_backlog_frozen"
    )
    if R3_FAILURE_RESULT.exists():
        assert all("pending" in task["status"] for task in tasks[5:])
        assert (
            "RC_P36_064"
            if R7_EXACT_FAILURE_RESULT.exists()
            else "RC_P36_063"
            if WWC_ATOM_ISSUANCE.exists()
            else "RC_P36_062"
            if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
            else "RC_P36_061"
            if R4_FAILURE_RESULT.exists()
            else "RC_P36_060"
        ) in tasks[4]["status"]
    else:
        assert all("pending" in task["status"] for task in tasks[1:])
    assert backlog["shared_execution_policy"]["case_execution_order"] == [
        "DELL",
        "MU",
        "NVDA",
    ]
    assert backlog["shared_execution_policy"]["same_runtime_no_parallel_case_implementation"]
    assert backlog["shared_execution_policy"]["transport_retry_count"] == 0
    assert (
        backlog["shared_execution_policy"]["automatic_paid_retry_replay_relaunch_or_rerun"]
        is False
    )
    assert backlog["shared_execution_policy"]["first_credible_failure_stops_current_case"]


def test_method_to_runtime_gap_blocks_paid_full_chain_before_node_consumption() -> None:
    entry = _load(ENTRY)
    gap = entry["method_to_runtime_gap"]

    assert gap["status"] == "open_preexecution_owned_gap"
    assert gap["model_quality_issue"] is False
    for case_id in ("DELL", "MU"):
        assert gap[case_id]["required_before_full_chain"] == [
            "contract_translated",
            "fixture_proven",
            "runtime_injected",
            "node_level_consumed",
        ]
    assert "do_not_use_paid_full_chain" in gap["prohibited_shortcut"]


def test_program_backlog_preserves_entry_and_tracks_current_S4_T05_gate() -> None:
    program = _load(PROGRAM_BACKLOG)
    s4 = _slice(program, "S4")
    task_status = {task["item_id"]: task["status"] for task in s4["items"]}

    expected_program_status = (
        "S4_in_progress_T01_T02_T03_T04_pass_T05_R7_terminal_failed_"
        "post_verifier_RC_P36_064_disposition_pending"
        if R7_EXACT_FAILURE_RESULT.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_063_"
        "profile_overlay_create_app_preflight_fixture_proven_"
        "fresh_agent_proof_pending"
        if R7_BINDING_IMPLEMENTATION.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_063_"
            "profile_overlay_create_app_preflight_implementation_pending"
        if WWC_ATOM_ISSUANCE.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_062_"
        "WWC_judgment_atom_fresh_proof_contract_frozen_"
        "admission_issuance_pending"
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_062_"
        "specialist_v7_WWC_segment_truncation_disposition_pending"
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
        "gap_atom_projection_R5_exact_live_authorized_execution_not_started"
        if GAP_PROJECTION_AUTHORITY.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
        "gap_atom_projection_R5_admission_issued_unconsumed_"
        "execution_authority_pending"
        if GAP_PROJECTION_ISSUANCE.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
        "gap_atom_projection_fresh_proof_pass_admission_issuance_pending"
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
        "gap_atom_projection_implementation_fixture_proven_"
        "fresh_proof_pending"
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
        "gap_atom_projection_selected_implementation_pending"
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
        "research_lead_remaining_gaps_cardinality_disposition_pending"
        if R4_FAILURE_RESULT.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
        "WWC_authority_R4_exact_live_authorized_execution_not_started"
        if NUMERIC_AUTHORITY_DECISION.exists()
        else
        "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
        "WWC_authority_R4_admission_issued_unconsumed_"
        "execution_authority_pending"
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
        "WWC_authority_fresh_proof_frozen_admission_issuance_pending"
        if NUMERIC_AUTHORITY_PROOF.exists()
        else "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
        "shared_WWC_authority_runtime_injected_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert program["status"] == expected_program_status
    assert s4["case_execution_order"] == ["DELL", "MU", "NVDA"]
    assert task_status["S4-T01"] == "pass_zero_call"
    assert task_status["S4-T02"] == (
        "pass_zero_call_case_packs_and_method_contract_translated"
    )
    assert task_status["S4-T03"] == (
        "pass_zero_paid_case_runtime_injected_node_consumed_and_leakage_preflight"
    )
    assert task_status["S4-T04"] == "pass_fresh_exact_admission_issued_unconsumed"
    expected_t05_status = (
        "R7_terminal_failed_post_verifier_untyped_ValueError_"
        "RC_P36_064_disposition_pending"
        if R7_EXACT_FAILURE_RESULT.exists()
        else
        "RC_P36_063_profile_overlay_create_app_preflight_"
        "fixture_proven_fresh_agent_proof_pending"
        if R7_BINDING_IMPLEMENTATION.exists()
        else
        "RC_P36_063_profile_overlay_create_app_preflight_"
            "implementation_pending"
        if WWC_ATOM_ISSUANCE.exists()
        else
        "RC_P36_062_WWC_judgment_atom_fresh_proof_contract_frozen_"
        "admission_issuance_pending"
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        "RC_P36_062_specialist_v7_WWC_segment_truncation_"
        "disposition_pending"
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else
        "RC_P36_061_gap_atom_projection_R5_exact_live_authorized_"
        "execution_not_started"
        if GAP_PROJECTION_AUTHORITY.exists()
        else
        "RC_P36_061_gap_atom_projection_R5_admission_issued_unconsumed_"
        "execution_authority_pending"
        if GAP_PROJECTION_ISSUANCE.exists()
        else
        "RC_P36_061_gap_atom_projection_fresh_proof_pass_"
        "admission_issuance_pending"
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        "RC_P36_061_gap_atom_projection_implementation_fixture_proven_"
        "fresh_proof_pending"
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        "RC_P36_061_gap_atom_deterministic_projection_selected_"
        "implementation_pending"
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        "RC_P36_061_research_lead_remaining_gaps_cardinality_"
        "disposition_pending"
        if R4_FAILURE_RESULT.exists()
        else
        "RC_P36_060_WWC_authority_R4_exact_live_authorized_"
        "execution_not_started"
        if NUMERIC_AUTHORITY_DECISION.exists()
        else
        "RC_P36_060_WWC_authority_R4_admission_issued_unconsumed_"
        "execution_authority_pending"
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else "RC_P36_060_WWC_authority_fresh_proof_contract_frozen_"
        "admission_issuance_pending"
        if NUMERIC_AUTHORITY_PROOF.exists()
        else "RC_P36_060_shared_WWC_authority_runtime_injected_"
        "fixture_proven_fresh_agent_proof_pending"
    )
    assert task_status["S4-T05"] == expected_t05_status
    latest_state = (
        R7_EXACT_FAILURE_RESULT
        if R7_EXACT_FAILURE_RESULT.exists()
        else R7_BINDING_IMPLEMENTATION
        if R7_BINDING_IMPLEMENTATION.exists()
        else WWC_ATOM_ISSUANCE
        if WWC_ATOM_ISSUANCE.exists()
        else WWC_TRUNCATION_DISPOSITION
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        GAP_PROJECTION_R5_FAILURE_RESULT
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else GAP_PROJECTION_AUTHORITY
        if GAP_PROJECTION_AUTHORITY.exists()
        else GAP_PROJECTION_ISSUANCE
        if GAP_PROJECTION_ISSUANCE.exists()
        else GAP_PROJECTION_FRESH_PROOF
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        NUMERIC_AUTHORITY_IMPLEMENTATION
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else GAP_PROJECTION_DISPOSITION
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        R4_FAILURE_RESULT
        if R4_FAILURE_RESULT.exists()
        else NUMERIC_AUTHORITY_DECISION
        if NUMERIC_AUTHORITY_DECISION.exists()
        else NUMERIC_AUTHORITY_ISSUANCE
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else NUMERIC_AUTHORITY_PROOF
        if NUMERIC_AUTHORITY_PROOF.exists()
        else NUMERIC_AUTHORITY_IMPLEMENTATION
    )
    latest = _load(latest_state)
    expected_next = (
        latest["next_action"]
        if latest_state
        in {
            WWC_ATOM_ISSUANCE,
            WWC_TRUNCATION_DISPOSITION,
            GAP_PROJECTION_R5_FAILURE_RESULT,
            GAP_PROJECTION_ISSUANCE,
            GAP_PROJECTION_FRESH_PROOF,
            NUMERIC_AUTHORITY_IMPLEMENTATION,
            GAP_PROJECTION_DISPOSITION,
            R4_FAILURE_RESULT,
        }
        else latest["conditional_next_action"]["on_authority_decision_complete"]
        if latest_state
        in {GAP_PROJECTION_AUTHORITY, NUMERIC_AUTHORITY_DECISION}
        else latest["next_action"]
    )
    assert program["next_action"]["item_id"] == expected_next
    assert program["next_action"]["current_S4_T03_completed"] is True
    assert program["next_action"]["current_S4_T04_authorized"] is True
    assert program["next_action"]["current_S4_T04_completed"] is True
    assert (
        program["next_action"]["current_S4_T04_fresh_proof_frozen"] is True
    )
    assert program["next_action"]["current_S4_T04_admission_issued"] is True
    assert program["next_action"]["current_S4_T04_admission_consumed"] is True
    assert program["next_action"]["current_S4_T04_execution_started"] is True
    assert program["next_action"]["current_S4_case_execution_authorized"] is True
    assert program["next_action"]["current_S4_case_execution_started"] is True
    assert program["next_action"]["current_S4_T05_exact_execution_completed"] is True
    assert program["next_action"]["current_S4_T05_completed"] is False
    assert program["next_action"]["current_S4_T05_artifact_count"] == 0


def test_budget_is_planning_only_and_no_execution_or_maturity_is_inflated() -> None:
    entry = _load(ENTRY)
    backlog = _load(S4_BACKLOG)
    counts = entry["observed_counts"]

    assert backlog["planning_budget_not_execution_authority"][
        "S4_initial_ceiling_including_any_separately_authorized_canary"
    ] == {
        "model_calls": 40,
        "total_tokens": 225000,
        "estimated_cost_usd": 0.15,
    }
    assert all(value == 0 for value in counts.values())
    assert entry["stage_decision"]["S4"] == "started_entry_only"
    assert entry["stage_decision"]["S4_pass"] is False
    assert entry["stage_decision"]["DELL_R2"] == "not_started"
    assert entry["stage_decision"]["MU_R2"] == "not_started"
    assert entry["stage_decision"]["NVDA_R3"] == "not_started"
    assert backlog["non_inflation"]["Alpha_release_or_production"] is False
    assert "机器 Verifier、owner self-review、shadow review 均不能替代 R3" in (
        S4_PLAN.read_text(encoding="utf-8")
    )
