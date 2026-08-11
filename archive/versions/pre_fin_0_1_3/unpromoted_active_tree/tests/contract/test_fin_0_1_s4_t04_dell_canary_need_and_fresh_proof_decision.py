from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
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
DECISION = RELEASES / (
    "fin_ia_0_1_s4_t04_dell_provider_canary_need_and_"
    "fresh_agent_proof_decision_v1_0.json"
)
SOURCE_GROUNDED_REPAIR = RELEASES / (
    "fin_ia_0_1_s4_t04_dell_source_grounded_input_materialization_"
    "and_fresh_proof_decision_v1_0.json"
)
PROGRAM = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
TASK_CLAIM_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
TASK_CLAIM_PROOF = RELEASES / (
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
TASK_CLAIM_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
TASK_CLAIM_AUTHORITY = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
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
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
R7_BINDING_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_case_runtime_"
    "binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
R7_EXACT_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "exact_live_execution_failure_result_v1_0.json"
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


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slice(program: dict, slice_id: str) -> dict:
    return next(
        row for row in program["slices"] if row["slice_id"] == slice_id
    )


def test_provider_only_canary_is_omitted_without_a_named_provider_delta() -> None:
    decision = _load(DECISION)
    canary = decision["provider_only_canary_decision"]

    assert canary["decision"] == "omit"
    assert canary["named_provider_only_risk"] is None
    assert canary["paid_canary_calls_authorized_or_performed"] == 0
    assert {
        "specialist_transport_v7",
        "output_contract_v4",
        "exact_run_supervision_v2",
        "retry_fallback_replay_relaunch_rerun_zero",
    }.issubset(canary["unchanged_provider_surfaces"])
    assert set(canary["changed_non_provider_surfaces"]) == {
        "issuer_identity_NVDA_to_DELL",
        "case_profile_and_research_profile",
        "case_local_method_context",
        "case_local_input_head",
    }


def test_source_grounded_input_gap_stops_fresh_proof_and_admission() -> None:
    decision = _load(DECISION)
    readiness = decision["upstream_exact_input_readiness"]
    proof = decision["fresh_agent_proof"]

    assert set(readiness["DELL_case_pack_fact_counts"].values()) == {0}
    assert readiness["canonical_CaseVersion_id"] is None
    assert readiness["DELL_source_route_count"] == 11
    assert readiness["DELL_routes_planned_not_executed"] == 11
    assert readiness["DELL_routes_promotable_without_execution"] == 0
    assert readiness["parser_backed_promotable_DELL_evidence_rows"] == 0
    assert readiness["source_grounded_exact_input_head_available"] is False
    assert proof["decision"] == "not_frozen_fail_closed"
    assert proof["work_unit_id"] is None
    assert proof["attempt_id"] is None
    assert proof["research_run_id"] is None
    assert proof["input_digest"] is None
    assert proof["prospective_admission"] is None
    assert proof["admission_issued"] is False
    assert proof["execution_started"] is False


def test_decision_is_zero_call_read_only_and_preserves_historical_bindings() -> None:
    decision = _load(DECISION)

    assert set(decision["observed_counts"].values()) == {0}
    assert decision["upstream_exact_input_readiness"][
        "canonical_runtime_audit"
    ]["read_only"] is True
    assert decision["upstream_exact_input_readiness"][
        "canonical_runtime_audit"
    ]["database_unchanged"] is True
    for relative, digest in decision["exact_code_bindings"].items():
        assert (ROOT / relative).is_file()
        assert len(digest) == 64
        assert set(digest).issubset(set("0123456789abcdef"))
    current_policy_sha = _sha256(
        ROOT
        / "apps/workbench/backend/application/"
        "bounded_agent_contract_policies.py"
    )
    historical_policy_sha = decision["exact_code_bindings"][
        "apps/workbench/backend/application/"
        "bounded_agent_contract_policies.py"
    ]
    if current_policy_sha != historical_policy_sha:
        implementation = _load(R7_BINDING_IMPLEMENTATION)
        supersession = implementation[
            "historical_exact_binding_supersession"
        ]
        policy_path = (
            "apps/workbench/backend/application/"
            "bounded_agent_contract_policies.py"
        )
        assert policy_path in supersession["allowed_changed_paths"]
        decision_ref = DECISION.relative_to(ROOT).as_posix()
        assert supersession["superseded_binding_contracts"][
            decision_ref
        ] == _sha256(DECISION)
        assert implementation["exact_code_bindings"][
            policy_path
        ] == current_policy_sha
    assert _sha256(ROOT / "src/sec_agent/s4_case_runtime.py") != decision[
        "exact_code_bindings"
    ]["src/sec_agent/s4_case_runtime.py"]
    assert _load(SOURCE_GROUNDED_REPAIR)["status"] == (
        "pass_source_grounded_exact_input_head_materialized_"
        "fresh_proof_frozen_admission_issuance_pending"
    )


def test_program_records_repair_pass_without_advancing_to_exact_live() -> None:
    program = _load(PROGRAM)
    s4 = _slice(program, "S4")
    statuses = {row["item_id"]: row["status"] for row in s4["items"]}
    current = program["next_action"]

    if R7_EXACT_FAILURE_RESULT.exists():
        failure = _load(R7_EXACT_FAILURE_RESULT)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_R7_terminal_failed_"
            "post_verifier_RC_P36_064_disposition_pending"
        )
        assert statuses["S4-T05"] == (
            "R7_terminal_failed_post_verifier_untyped_ValueError_"
            "RC_P36_064_disposition_pending"
        )
        assert current["item_id"] == failure["next_action"]
    elif R7_BINDING_IMPLEMENTATION.exists():
        implementation = _load(R7_BINDING_IMPLEMENTATION)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_063_"
            "profile_overlay_create_app_preflight_fixture_proven_"
            "fresh_agent_proof_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_063_profile_overlay_create_app_preflight_"
            "fixture_proven_fresh_agent_proof_pending"
        )
        assert current["item_id"] == implementation["next_action"]
    elif WWC_ATOM_ISSUANCE.exists():
        issuance = _load(WWC_ATOM_ISSUANCE)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_063_"
            "profile_overlay_create_app_preflight_implementation_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_063_profile_overlay_create_app_preflight_"
            "implementation_pending"
        )
        assert current["item_id"] == issuance["next_action"]
    elif WWC_TRUNCATION_DISPOSITION.exists():
        disposition = _load(WWC_TRUNCATION_DISPOSITION)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_062_"
            "WWC_judgment_atom_fresh_proof_contract_frozen_"
            "admission_issuance_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_062_WWC_judgment_atom_fresh_proof_contract_frozen_"
            "admission_issuance_pending"
        )
        assert current["item_id"] == disposition["next_action"]
    elif GAP_PROJECTION_R5_FAILURE_RESULT.exists():
        failure = _load(GAP_PROJECTION_R5_FAILURE_RESULT)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_062_"
            "specialist_v7_WWC_segment_truncation_disposition_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_062_specialist_v7_WWC_segment_truncation_"
            "disposition_pending"
        )
        assert current["item_id"] == failure["next_action"]
    elif GAP_PROJECTION_AUTHORITY.exists():
        authority = _load(GAP_PROJECTION_AUTHORITY)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
            "gap_atom_projection_R5_exact_live_authorized_execution_not_started"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_061_gap_atom_projection_R5_exact_live_authorized_"
            "execution_not_started"
        )
        assert current["item_id"] == authority["conditional_next_action"][
            "on_authority_decision_complete"
        ]
    elif GAP_PROJECTION_ISSUANCE.exists():
        issuance = _load(GAP_PROJECTION_ISSUANCE)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
            "gap_atom_projection_R5_admission_issued_unconsumed_"
            "execution_authority_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_061_gap_atom_projection_R5_admission_issued_unconsumed_"
            "execution_authority_pending"
        )
        assert current["item_id"] == issuance["next_action"]
    elif GAP_PROJECTION_FRESH_PROOF.exists():
        proof = _load(GAP_PROJECTION_FRESH_PROOF)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
            "gap_atom_projection_fresh_proof_pass_admission_issuance_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_061_gap_atom_projection_fresh_proof_pass_"
            "admission_issuance_pending"
        )
        assert current["item_id"] == proof["next_action"]
    elif NUMERIC_AUTHORITY_IMPLEMENTATION.exists():
        implementation = _load(NUMERIC_AUTHORITY_IMPLEMENTATION)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
            "gap_atom_projection_implementation_fixture_proven_"
            "fresh_proof_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_061_gap_atom_projection_implementation_fixture_proven_"
            "fresh_proof_pending"
        )
        assert current["item_id"] == implementation["next_action"]
    elif GAP_PROJECTION_DISPOSITION.exists():
        disposition = _load(GAP_PROJECTION_DISPOSITION)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
            "gap_atom_projection_selected_implementation_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_061_gap_atom_deterministic_projection_selected_"
            "implementation_pending"
        )
        assert current["item_id"] == disposition["next_action"]
    elif R4_FAILURE_RESULT.exists():
        failure = _load(R4_FAILURE_RESULT)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_061_"
            "research_lead_remaining_gaps_cardinality_disposition_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_061_research_lead_remaining_gaps_cardinality_"
            "disposition_pending"
        )
        assert current["item_id"] == failure["next_action"]
    elif NUMERIC_AUTHORITY_DECISION.exists():
        authority = _load(NUMERIC_AUTHORITY_DECISION)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
            "WWC_authority_R4_exact_live_authorized_execution_not_started"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_060_WWC_authority_R4_exact_live_authorized_"
            "execution_not_started"
        )
        assert current["item_id"] == authority["conditional_next_action"][
            "on_authority_decision_complete"
        ]
    elif NUMERIC_AUTHORITY_ISSUANCE.exists():
        issuance = _load(NUMERIC_AUTHORITY_ISSUANCE)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
            "WWC_authority_R4_admission_issued_unconsumed_"
            "execution_authority_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_060_WWC_authority_R4_admission_issued_unconsumed_"
            "execution_authority_pending"
        )
        assert current["item_id"] == issuance["next_action"]
    elif NUMERIC_AUTHORITY_PROOF.exists():
        proof = _load(NUMERIC_AUTHORITY_PROOF)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
            "WWC_authority_fresh_proof_frozen_admission_issuance_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_060_WWC_authority_fresh_proof_contract_frozen_"
            "admission_issuance_pending"
        )
        assert current["item_id"] == proof["next_action"]
    elif NUMERIC_AUTHORITY_IMPLEMENTATION.exists():
        implementation = _load(NUMERIC_AUTHORITY_IMPLEMENTATION)
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
            "shared_WWC_authority_runtime_injected_fixture_proven_"
            "fresh_agent_proof_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_060_shared_WWC_authority_runtime_injected_"
            "fixture_proven_fresh_agent_proof_pending"
        )
        assert current["item_id"] == implementation["next_action"]
    elif NUMERIC_AUTHORITY_DISPOSITION.exists():
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_060_"
            "disposed_minimum_shared_WWC_authority_policy_"
            "implementation_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_060_minimum_shared_WWC_authority_policy_"
            "implementation_pending"
        )
        assert current["item_id"] == _load(
            NUMERIC_AUTHORITY_DISPOSITION
        )["next_action"]
    elif R3_FAILURE_RESULT.exists():
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_R3_terminal_failed_"
            "RC_P36_059_closed_RC_P36_060_disposition_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_060_WWC_numeric_authority_surface_disposition_pending"
        )
        assert current["item_id"] == _load(R3_FAILURE_RESULT)["next_action"]
    elif TASK_CLAIM_AUTHORITY.exists():
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_059_"
            "task_claim_R3_exact_live_authorized_not_started"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_059_task_claim_R3_exact_live_authorized_not_started"
        )
    elif TASK_CLAIM_ISSUANCE.exists():
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_059_"
            "task_claim_R3_admission_issued_unconsumed_execution_"
            "authority_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_059_task_claim_R3_admission_issued_unconsumed_"
            "execution_authority_pending"
        )
    elif TASK_CLAIM_PROOF.exists():
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_059_"
            "task_claim_fresh_proof_frozen_admission_issuance_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_059_task_claim_fresh_proof_contract_frozen_"
            "admission_issuance_pending"
        )
    elif TASK_CLAIM_IMPLEMENTATION.exists():
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_RC_P36_059_"
            "minimum_closed_identity_runtime_injected_fixture_proven_"
            "fresh_agent_proof_pending"
        )
        assert statuses["S4-T05"] == (
            "RC_P36_059_minimum_closed_identity_runtime_injected_"
            "fixture_proven_fresh_agent_proof_pending"
        )
    else:
        assert program["status"] == (
            "S4_in_progress_T01_T02_T03_T04_pass_T05_exact_failed_"
            "RC_P36_058_disposed_zero_call_implementation_pending"
        )
        assert statuses["S4-T05"] == (
            "blocked_RC_P36_058_role_group_mapping_selected_zero_call_"
            "implementation_pending"
        )
    assert statuses["S4-T04"] == "pass_fresh_exact_admission_issued_unconsumed"
    assert current["S4_T04_provider_only_canary_decision"] == (
        "omit_no_named_provider_only_risk"
    )
    assert current["current_S4_T04_authorized"] is True
    assert current["current_S4_T04_decision_completed"] is True
    assert current["current_S4_T04_completed"] is True
    assert current["current_S4_T04_fresh_proof_frozen"] is True
    assert current["current_S4_T04_admission_issued"] is True
    assert current["current_S4_T04_admission_consumed"] is True
    assert current["current_S4_T04_execution_started"] is True
    assert current["current_S4_case_execution_started"] is True
    expected_current = (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(WWC_ATOM_ISSUANCE)["next_action"]
        if WWC_ATOM_ISSUANCE.exists()
        else _load(WWC_TRUNCATION_DISPOSITION)["next_action"]
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        _load(GAP_PROJECTION_R5_FAILURE_RESULT)["next_action"]
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else _load(GAP_PROJECTION_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if GAP_PROJECTION_AUTHORITY.exists()
        else _load(GAP_PROJECTION_ISSUANCE)["next_action"]
        if GAP_PROJECTION_ISSUANCE.exists()
        else _load(GAP_PROJECTION_FRESH_PROOF)["next_action"]
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE_RESULT)["next_action"]
        if R4_FAILURE_RESULT.exists()
        else _load(NUMERIC_AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if NUMERIC_AUTHORITY_DECISION.exists()
        else _load(NUMERIC_AUTHORITY_ISSUANCE)["next_action"]
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else _load(NUMERIC_AUTHORITY_PROOF)["next_action"]
        if NUMERIC_AUTHORITY_PROOF.exists()
        else _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        _load(NUMERIC_AUTHORITY_DISPOSITION)["next_action"]
        if NUMERIC_AUTHORITY_DISPOSITION.exists()
        else
        _load(R3_FAILURE_RESULT)["next_action"]
        if R3_FAILURE_RESULT.exists()
        else
        _load(TASK_CLAIM_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if TASK_CLAIM_AUTHORITY.exists()
        else
        "S4-T05-DELL-TASK-CLAIM-LINK-POLICY-R3-EXACT-LIVE-"
        "EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
        if TASK_CLAIM_ISSUANCE.exists()
        else
        "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
        if TASK_CLAIM_PROOF.exists()
        else "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "FRESH-AGENT-PROOF-DECISION"
        if TASK_CLAIM_IMPLEMENTATION.exists()
        else "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-"
        "DISPATCH-PREFLIGHT-ZERO-CALL-IMPLEMENTATION"
    )
    assert current["item_id"] == expected_current
    assert s4["T04_decision_sha256"] == _sha256(DECISION)
    assert current["S4_T04_source_grounded_repair_decision_sha256"] == (
        _sha256(SOURCE_GROUNDED_REPAIR)
    )


def test_RC_P36_056_history_closes_owned_upstream_gap_only() -> None:
    rows = [
        row
        for row in _jsonl(ROOT_CAUSES)
        if row["issue_id"]
        == (
            "RC-P36-056-s4-dell-source-grounded-exact-input-head-"
            "and-canonical-case-gap"
        )
    ]
    assert len(rows) == 2
    assert rows[0]["status"] == (
        "open_owned_pre_admission_source_grounded_input_gap"
    )
    issue = rows[-1]

    assert issue["status"] == (
        "closed_source_grounded_input_and_fresh_proof_repaired"
    )
    assert issue["owned_by_project"] is True
    assert issue["external_boundary"] is False
    assert issue["full_chain_blocker"] is False
    assert issue["blocking_run_scopes"] == []
    assert issue["verification_result"]["fresh_proof_frozen"] is True
    assert issue["verification_result"]["admission_issued"] is False
