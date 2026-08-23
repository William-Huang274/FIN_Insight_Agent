from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from sec_agent.project_os_preflight import (
    CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_SCOPE,
    CURRENT_DYNAMIC_MULTI_AGENT_SCOPE,
    CURRENT_DYNAMIC_SINGLE_UNIT_SCOPE,
    CURRENT_DYNAMIC_SINGLE_UNIT_SEMANTIC_REPAIR_SCOPE,
    CURRENT_DYNAMIC_SINGLE_UNIT_FEEDBACK_SCOPE,
    CURRENT_DYNAMIC_SINGLE_UNIT_TRANSPORT_SCOPE,
    CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_SCOPE,
    FIXED_PACK_SCOPE,
    FRAGMENT_VALIDATION_REPAIR_SCOPE,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_SCOPE,
    REQUIRED_PROJECT_OS_REFS,
    _validate_current_dynamic_single_unit_decision,
    _validate_current_dynamic_multi_agent_content_repair_decision,
    _validate_current_dynamic_multi_agent_decision,
    _validate_current_dynamic_single_unit_semantic_repair_decision,
    _validate_dynamic_five_cell_claim_surface_successor_decision,
    _validate_dynamic_five_cell_node_successor_decision,
    _validate_dynamic_five_cell_partial_successor_decision,
    _validate_dynamic_five_cell_value_repair_successor_decision,
    _validate_fragment_validation_repair_decision,
    _validate_failed_fragment_submission_successor_decision,
    build_preflight,
    validate_multi_agent_preview_analysis_successor_scope_decision,
    validate_multi_agent_preview_submission_successor_scope_decision,
    validate_multi_agent_preview_lead_checkpoint_successor_scope_decision,
    validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision,
    validate_multi_agent_preview_specialist_analysis_successor_scope_decision,
    validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision,
    validate_multi_agent_preview_generic_successor_scope_decision,
    validate_multi_agent_preview_plan_successor_scope_decision,
    validate_multi_agent_preview_scope_decision,
)
from sec_agent.research.multi_agent_report_remap import (
    REPORT_REMAP_REFERENCE_PATCH_RUN_SCOPE,
    REPORT_REMAP_REPLACEMENT_RUN_SCOPE,
    REPORT_REMAP_RUN_SCOPE,
    ReportRemapAuthorityError,
    validate_report_remap_scope_decision,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_REMAP_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_scope_decision_v1_0.json"
)
REPORT_REMAP_REPLACEMENT_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_scope_decision_v1_1.json"
)
REPORT_REMAP_REFERENCE_PATCH_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_scope_decision_v1_2.json"
)
DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_live_decision_v1_0.json"
)
MICRO_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "micro_judgment_live_scope_decision_v1_0.json"
)
FULL_FRAGMENT_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "full_fragment_judgment_live_scope_decision_v1_0.json"
)
FULL_FRAGMENT_SURFACE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "full_fragment_judgment_surface_live_scope_decision_v1_1.json"
)
FULL_FRAGMENT_RELATION_ROLE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "full_fragment_judgment_relation_role_live_scope_decision_v1_2.json"
)
FULL_FRAGMENT_CLAIM_LOCAL_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_local_boundary_live_scope_decision_v1_3.json"
)
FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "causal_polarity_live_scope_decision_v1_4.json"
)
FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "wwc_route_identifier_live_scope_decision_v1_5.json"
)
NON_THINKING_SUCCESSOR_ZERO_RESULT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "non_thinking_submission_successor_zero_call_result_v1_7.json"
)
FULL_FRAGMENT_R6_RESULT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "full_fragment_judgment_chat_live_result_v1_5.json"
)
FULL_FRAGMENT_R6_ASSESSMENT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "full_fragment_judgment_chat_live_failure_assessment_v1_5.json"
)
FULL_FRAGMENT_R6_SUCCESSOR_FIXTURE_REF = (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_full_fragment_chat_r6_"
    "submission_successor_fixture_v1_0.json"
)
NON_THINKING_SUBMISSION_PROFILE_REF = (
    "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "contract_submission_non_thinking_profile_v1_0.json"
)
VALIDATION_REPAIR_ZERO_RESULT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "validation_repair_zero_call_result_v1_8.json"
)
FAILED_COUNTER_R7_RESULT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "failed_counter_submission_successor_chat_live_result_v1_0.json"
)
FAILED_COUNTER_R7_ASSESSMENT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "failed_counter_submission_successor_chat_live_failure_assessment_v1_0.json"
)
FAILED_COUNTER_R7_FIXTURE_REF = (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_failed_counter_submission_r7_"
    "rejected_fragment_v1_0.json"
)
ALIAS_CLEAN_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_relation_alias_capacity_zero_call_result_v1_0.json"
)
CAPACITY_PREDECESSOR_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_chat_live_result_v1_0.json"
)
DYNAMIC_SINGLE_CELL_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_value_capture_live_scope_decision_v1_0.json"
)
CURRENT_DYNAMIC_SINGLE_UNIT_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "live_scope_decision_v1_0.json"
)
CURRENT_DYNAMIC_MULTI_AGENT_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "live_scope_decision_v1_0.json"
)
CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "content_repair_successor_scope_decision_v1_0.json"
)
CURRENT_DYNAMIC_SINGLE_UNIT_TRANSPORT_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "live_scope_decision_v1_1.json"
)
CURRENT_DYNAMIC_SINGLE_UNIT_FEEDBACK_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "live_scope_decision_v1_2.json"
)
CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "workpaper_submission_scope_decision_v1_0.json"
)
CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_REPLACEMENT_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "workpaper_submission_scope_decision_v1_1.json"
)
CURRENT_DYNAMIC_SINGLE_UNIT_SEMANTIC_REPAIR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "semantic_repair_scope_decision_v1_0.json"
)
DYNAMIC_FIVE_CELL_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_live_scope_decision_v1_0.json"
)
DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_successor_"
    "live_scope_decision_v1_0.json"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_partial_successor_"
    "live_scope_decision_v1_0.json"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_node_successor_"
    "live_scope_decision_v1_0.json"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_"
    "claim_surface_successor_scope_decision_v1_0.json"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_"
    "cell_scoped_claim_contract_successor_scope_decision_v1_1.json"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_"
    "value_submission_repair_successor_scope_decision_v1_0.json"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_counter_successor_"
    "live_scope_decision_v1_0.json"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_V1_1_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_counter_successor_"
    "live_scope_decision_v1_1.json"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_V1_2_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_counter_successor_"
    "live_scope_decision_v1_2.json"
)
MULTI_AGENT_PREVIEW_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_0.json"
)
MULTI_AGENT_PREVIEW_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_1.json"
)
MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_2.json"
)
MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_3.json"
)
MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_4.json"
)
MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_5.json"
)
MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_6.json"
)
MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_7.json"
)
MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_8.json"
)
MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_"
    "scope_decision_v1_10.json"
)
MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_1.json"
)
MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_2.json"
)
MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_PROFILE_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_3.json"
)
MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_CHECKPOINT_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_4.json"
)
MULTI_AGENT_PREVIEW_ALL_ROLE_EVALUATIONS_CHECKPOINT_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_5.json"
)
MULTI_AGENT_PREVIEW_TERMINAL_WRITER_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_6.json"
)
MULTI_AGENT_PREVIEW_TERMINAL_WRITER_SUBMISSION_SCOPE_DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_compiled_"
    "successor_scope_decision_v1_7.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_ref(target_root: Path, ref: str) -> None:
    source = ROOT / ref
    target = target_root / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _fixture_root(tmp_path: Path) -> Path:
    for ref in REQUIRED_PROJECT_OS_REFS:
        _copy_ref(tmp_path, ref)
    _copy_ref(tmp_path, DECISION_REF)
    decision = json.loads((ROOT / DECISION_REF).read_text(encoding="utf-8"))
    for field in (
        "clean_zero_call_result_ref",
        "immutable_predecessor_result_ref",
        "provider_profile_ref",
        "provider_health_evidence_ref",
    ):
        _copy_ref(tmp_path, decision[field])
    return tmp_path


def _micro_fixture_root(tmp_path: Path) -> Path:
    for ref in REQUIRED_PROJECT_OS_REFS:
        _copy_ref(tmp_path, ref)
    _copy_ref(tmp_path, MICRO_DECISION_REF)
    decision = json.loads(
        (ROOT / MICRO_DECISION_REF).read_text(encoding="utf-8")
    )
    for field in (
        "clean_zero_call_result_ref",
        "micro_zero_call_authority_ref",
        "immutable_predecessor_result_ref",
        "prior_capacity_assessment_ref",
        "micro_read_profile_ref",
        "micro_judgment_profile_ref",
        "provider_health_evidence_ref",
    ):
        _copy_ref(tmp_path, decision[field])
    return tmp_path


def _dynamic_five_cell_fixture_root(tmp_path: Path) -> Path:
    for ref in REQUIRED_PROJECT_OS_REFS:
        _copy_ref(tmp_path, ref)
    _copy_ref(tmp_path, DYNAMIC_FIVE_CELL_DECISION_REF)
    decision = json.loads(
        (ROOT / DYNAMIC_FIVE_CELL_DECISION_REF).read_text(encoding="utf-8")
    )
    for field in (
        "runner_zero_call_result_ref",
        "five_cell_context_result_ref",
        "dynamic_single_cell_assessment_ref",
        "planner_profile_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
    ):
        _copy_ref(tmp_path, decision[field])
    proof = json.loads(
        (ROOT / decision["runner_zero_call_result_ref"]).read_text(
            encoding="utf-8"
        )
    )
    for row in proof["source_bindings"].values():
        _copy_ref(tmp_path, row["ref"])
    return tmp_path


def _multi_agent_plan_successor_fixture_root(tmp_path: Path) -> Path:
    for ref in REQUIRED_PROJECT_OS_REFS:
        _copy_ref(tmp_path, ref)
    _copy_ref(tmp_path, MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF)
    decision = json.loads(
        (
            ROOT / MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    for field, value in decision.items():
        if field.endswith("_ref") and isinstance(value, str):
            _copy_ref(tmp_path, value)
    return tmp_path


def test_current_fixed_pack_decision_passes_without_network_or_secret_read() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == FIXED_PACK_SCOPE
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["credential_value_persisted"] is False
    assert result["checks"]["provider_credential_present_value_unread"] is True
    assert (
        "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use"
        in result["scope_projection"]["closed_precondition_issue_ids"]
    )


def test_historical_multi_agent_preview_scope_remains_auditable_but_not_current() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = validate_multi_agent_preview_scope_decision(
        root=ROOT, decision=decision
    )
    assert projection["run_scope_id"] == MULTI_AGENT_PREVIEW_SCOPE
    assert projection["multi_agent_preview"] is True
    assert projection["specialist_agent_count"] == 6
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_preview_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=MULTI_AGENT_PREVIEW_SCOPE_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_multi_agent_preview_scope_decision_fails_if_execution_budget_expands() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["execution_limits"]["maximum_model_nodes"] = 23
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_execution_limits_invalid",
    ):
        validate_multi_agent_preview_scope_decision(
            root=ROOT, decision=decision
        )


def test_historical_transport_successor_binds_R2_but_cannot_be_reauthorized() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_SUCCESSOR_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = validate_multi_agent_preview_scope_decision(
        root=ROOT, decision=decision
    )
    assert projection["multi_agent_preview"] is True
    assert projection["multi_agent_preview_transport_successor"] is True
    assert projection["execution_limits"]["maximum_model_nodes"] == 22
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_preview_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=MULTI_AGENT_PREVIEW_SUCCESSOR_SCOPE_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_multi_agent_preview_plan_checkpoint_successor_preserves_plans_and_separates_phases() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["run_scope_id"] == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE
    assert projection["multi_agent_preview_plan_checkpoint_successor"] is True
    assert projection["reused_specialist_plan_count"] == 6
    assert (
        projection["successor_zero_call_proof_status"]
        == "R3_plan_checkpoint_successor_zero_call_pass"
    )
    assert projection["maximum_proposed_atoms"] == 20
    assert projection["maximum_evidence_requests"] == 12
    assert projection["proved_proposed_atom_count"] == 13
    assert projection["proved_selected_atom_count"] == 12
    assert projection["proved_deferred_atom_count"] == 1
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 16
    assert "starting at Research Lead" in result["known_boundary"]
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert {
        "RC-AR-002-old-five-cell-workflow-lacked-independent-role-"
        "coordination-and-feedback-loop",
        "RC-AR-003-multi-agent-node-couples-max-thinking-analysis-and-"
        "strict-contract-submission",
    }.issubset(set(result["scope_projection"]["explicit_allow_issue_ids"]))


def test_multi_agent_preview_plan_checkpoint_successor_rejects_specialist_rerun() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["successor_constraints"]["rerun_successful_specialist_plans"] = True
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_plan_successor_constraints_invalid",
    ):
        validate_multi_agent_preview_plan_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_plan_checkpoint_successor_rejects_execution_budget_drift() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["successor_constraints"]["maximum_evidence_requests"] = 13
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_plan_successor_constraints_invalid",
    ):
        validate_multi_agent_preview_plan_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_plan_checkpoint_successor_rejects_promoting_overlay(
    tmp_path: Path,
) -> None:
    root = _multi_agent_plan_successor_fixture_root(tmp_path)
    decision_path = root / MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE_DECISION_REF
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    overlay_path = root / decision["planning_overlay_ref"]
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    overlay["authority"]["product_pointer_promotion"] = True
    overlay_path.write_text(json.dumps(overlay), encoding="utf-8")
    decision["planning_overlay_sha256"] = _sha(overlay_path)

    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_plan_successor_planning_overlay_invalid",
    ):
        validate_multi_agent_preview_plan_successor_scope_decision(
            root=root, decision=decision
        )


def test_multi_agent_preview_analysis_checkpoint_successor_binds_one_continuation() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["run_scope_id"] == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE
    assert projection["multi_agent_preview_analysis_checkpoint_successor"] is True
    assert projection["maximum_analysis_continuations"] == 1
    assert projection["reused_specialist_plan_count"] == 6
    assert (
        projection["successor_zero_call_proof_status"]
        == "R4_visible_analysis_checkpoint_successor_zero_call_pass"
    )
    assert "exactly one low-reasoning continuation" in result["known_boundary"]
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert {
        "RC-AR-002-old-five-cell-workflow-lacked-independent-role-"
        "coordination-and-feedback-loop",
        "RC-AR-003-multi-agent-node-couples-max-thinking-analysis-and-"
        "strict-contract-submission",
        "RC-AR-005-agent-analysis-one-shot-has-no-fragment-checkpoint-"
        "feedback-or-continuation",
    }.issubset(set(result["scope_projection"]["explicit_allow_issue_ids"]))


def test_multi_agent_preview_analysis_checkpoint_successor_rejects_second_continuation() -> None:
    decision = json.loads(
        (
            ROOT / MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["successor_constraints"]["maximum_analysis_continuations"] = 2
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_analysis_successor_constraints_invalid",
    ):
        validate_multi_agent_preview_analysis_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_submission_successor_reuses_completed_analysis() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["run_scope_id"] == MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE
    assert projection["multi_agent_preview_submission_checkpoint_successor"] is True
    assert projection["maximum_new_lead_analysis_calls"] == 0
    assert projection["reused_specialist_plan_count"] == 6
    assert (
        projection["successor_zero_call_proof_status"]
        == "R5_completed_analysis_submission_successor_zero_call_pass"
    )
    assert "permits no new Research Lead analysis" in result["known_boundary"]
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert {
        "RC-AR-002-old-five-cell-workflow-lacked-independent-role-"
        "coordination-and-feedback-loop",
        "RC-AR-003-multi-agent-node-couples-max-thinking-analysis-and-"
        "strict-contract-submission",
        "RC-AR-005-agent-analysis-one-shot-has-no-fragment-checkpoint-"
        "feedback-or-continuation",
        "RC-AR-006-analysis-continuation-validator-conflates-partial-and-"
        "missing-fields",
    }.issubset(set(result["scope_projection"]["explicit_allow_issue_ids"]))


def test_multi_agent_preview_submission_successor_rejects_lead_analysis_rerun() -> None:
    decision = json.loads(
        (
            ROOT / MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["successor_constraints"]["rerun_lead_analysis_or_continuation"] = True
    with pytest.raises(
        ValueError,
        match="project_os_multi_agent_submission_successor_constraints_invalid",
    ):
        validate_multi_agent_preview_submission_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_lead_checkpoint_successor_starts_downstream() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["run_scope_id"] == (
        MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE
    )
    assert (
        projection["multi_agent_preview_lead_checkpoint_downstream_successor"]
        is True
    )
    assert projection["maximum_new_lead_plan_model_calls"] == 0
    assert projection["reused_specialist_plan_count"] == 6
    assert projection["reused_lead_plan_count"] == 1
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 15
    assert "fresh attempt begins at six role workpapers" in result[
        "known_boundary"
    ]
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0


def test_multi_agent_preview_lead_checkpoint_successor_rejects_lead_rerun() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["successor_constraints"][
        "rerun_lead_analysis_continuation_or_submission"
    ] = True
    with pytest.raises(
        ValueError,
        match=(
            "project_os_multi_agent_lead_checkpoint_successor_"
            "constraints_invalid"
        ),
    ):
        validate_multi_agent_preview_lead_checkpoint_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_workpaper_checkpoint_successor_starts_at_counter() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["run_scope_id"] == (
        MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE
    )
    assert (
        projection[
            "multi_agent_preview_workpaper_checkpoint_downstream_successor"
        ]
        is True
    )
    assert projection["reused_workpaper_count"] == 5
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 10
    assert (
        projection["execution_limits"]["maximum_new_initial_workpaper_nodes"]
        == 1
    )
    assert "only the pending Counterevidence workpaper" in result[
        "known_boundary"
    ]


def test_multi_agent_preview_workpaper_checkpoint_rejects_completed_rerun() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["successor_constraints"]["rerun_completed_workpapers"] = True
    with pytest.raises(
        ValueError,
        match=(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "constraints_invalid"
        ),
    ):
        validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_specialist_analysis_successor_resumes_once() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["run_scope_id"] == (
        MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE
    )
    assert projection[
        "multi_agent_preview_specialist_analysis_checkpoint_successor"
    ] is True
    assert projection["reused_workpaper_count"] == 5
    assert projection["execution_limits"][
        "maximum_resumed_specialist_analysis_continuations"
    ] == 1
    assert projection["execution_limits"][
        "maximum_new_initial_workpaper_nodes"
    ] == 0
    assert "exact original Counter conversation" in result["known_boundary"]


def test_multi_agent_preview_specialist_analysis_successor_rejects_initial_rerun() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["successor_constraints"][
        "rerun_initial_counterevidence_analysis"
    ] = True
    with pytest.raises(
        ValueError,
        match=(
            "project_os_multi_agent_specialist_analysis_successor_"
            "constraints_invalid"
        ),
    ):
        validate_multi_agent_preview_specialist_analysis_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_coordination_checkpoint_starts_at_repairs() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    projection = result["decision_projection"]
    assert result["run_scope_id"] == (
        MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE
    )
    assert projection[
        "multi_agent_preview_coordination_checkpoint_successor"
    ] is True
    assert projection["reused_workpaper_count"] == 6
    assert projection["reused_lead_coordination_count"] == 1
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 8
    assert projection["execution_limits"][
        "maximum_new_lead_coordination_model_calls"
    ] == 0
    assert "only the three accepted role-local repairs" in result[
        "known_boundary"
    ]


def test_multi_agent_preview_coordination_checkpoint_rejects_coordination_rerun() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["successor_constraints"]["rerun_lead_coordination"] = True
    with pytest.raises(
        ValueError,
        match=(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "constraints_invalid"
        ),
    ):
        validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_repair_context_successor_enters_full_preflight() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    projection = result["decision_projection"]
    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == (
        MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE
    )
    assert projection["multi_agent_preview_repair_context_successor"] is True
    assert projection["reused_completed_challenge_repair_count"] == 2
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 6
    assert projection["execution_limits"][
        "maximum_resumed_downstream_analysis_continuations"
    ] == 0
    assert "only one fresh role-scoped Supply repair" in result[
        "known_boundary"
    ]


def test_multi_agent_preview_generic_successor_binds_compiled_frontier() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT, decision=decision
    )

    assert projection["multi_agent_preview_generic_successor"] is True
    assert projection["run_scope_id"] == MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE
    assert projection["reused_completed_challenge_repair_count"] == 3
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 5
    assert projection["execution_limits"][
        "maximum_resumed_downstream_analysis_continuations"
    ] == 0

    preflight = build_preflight(
        root=ROOT,
        decision_ref=MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert "3 capture-bound completed repairs" in preflight["known_boundary"]
    assert "0 frontier-authorized fresh repair nodes" in preflight["known_boundary"]
    assert "Supply remains pending fresh" not in preflight["known_boundary"]


def test_multi_agent_preview_generic_successor_rejects_frontier_digest_drift() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["successor_execution_frontier_result_digest"] = "0" * 64

    with pytest.raises(
        ValueError, match="project_os_artifact_result_digest_drift"
    ):
        validate_multi_agent_preview_generic_successor_scope_decision(
            root=ROOT, decision=decision
        )


def test_multi_agent_preview_hierarchical_evaluator_binds_zero_call_proof() -> None:
    decision = json.loads(
        (
            ROOT / MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["multi_agent_preview_generic_successor"] is True
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 13
    assert projection["hierarchical_evaluator_zero_call_proof_status"] == (
        "hierarchical_evaluator_capture_replay_fake_mutation_zero_call_pass"
    )
    assert projection[
        "hierarchical_evaluator_zero_call_proof_result_digest"
    ] == decision["hierarchical_evaluator_zero_call_proof_result_digest"]


def test_multi_agent_preview_hierarchical_evaluator_rejects_proof_digest_drift() -> None:
    decision = json.loads(
        (
            ROOT / MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["hierarchical_evaluator_zero_call_proof_result_digest"] = "0" * 64

    with pytest.raises(
        ValueError,
        match="project_os_artifact_result_digest_drift",
    ):
        validate_multi_agent_preview_generic_successor_scope_decision(
            root=ROOT,
            decision=decision,
        )


def test_multi_agent_preview_hierarchical_evaluator_separates_audit_profile() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_PROFILE_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["recent_provider_steps"] == 1
    assert projection["evaluator_analysis_profile_ref"] == decision[
        "evaluator_analysis_profile_ref"
    ]
    assert projection["evaluator_analysis_reasoning_effort"] == "low"
    assert projection["evaluator_analysis_maximum_token_ceiling"] == 10000
    assert decision["evaluator_analysis_profile_ref"] != decision[
        "repair_analysis_profile_ref"
    ]
    assert projection["token_budget_basis_policy"][
        "evaluator_analysis_basis_is_separate_from_repair_basis"
    ] is True

    preflight = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_PROFILE_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert preflight["status"] == "pass_current_decision_bound_preflight"
    assert (
        "RC-AR-023-hierarchical-role-audit-reused-high-reasoning-repair-profile"
        in preflight["scope_projection"]["explicit_allow_issue_ids"]
    )


def test_multi_agent_preview_role_evaluation_checkpoint_resumes_at_operating() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_CHECKPOINT_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["evaluator_analysis_reasoning_effort"] is None
    assert projection["evaluator_analysis_thinking_mode"] == "disabled"
    assert projection["reused_role_evaluation_count"] == 1
    assert projection["execution_limits"][
        "maximum_initial_role_evaluation_nodes"
    ] == 5
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 12
    assert projection["token_budget_basis_policy"][
        "reused_role_evaluations_have_no_new_token_budget"
    ] is True

    preflight = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_HIERARCHICAL_EVALUATOR_CHECKPOINT_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert preflight["status"] == "pass_current_decision_bound_preflight"
    assert (
        "RC-AR-023-hierarchical-role-audit-reused-high-reasoning-repair-profile"
        in preflight["scope_projection"]["explicit_allow_issue_ids"]
    )
    assert (
        "RC-AR-024-low-reasoning-evaluator-has-no-visible-output-reserve-or-node-checkpoint"
        not in preflight["scope_projection"]["explicit_allow_issue_ids"]
    )


def test_multi_agent_preview_all_role_evaluations_resume_at_cross_role() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_ALL_ROLE_EVALUATIONS_CHECKPOINT_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["evaluator_analysis_reasoning_effort"] is None
    assert projection["evaluator_analysis_thinking_mode"] == "disabled"
    assert projection["reused_role_evaluation_count"] == 6
    assert projection["execution_limits"][
        "maximum_initial_role_evaluation_nodes"
    ] == 0
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 7

    preflight = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_ALL_ROLE_EVALUATIONS_CHECKPOINT_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert preflight["status"] == "pass_current_decision_bound_preflight"
    assert (
        "RC-AR-025-evaluator-gap-ref-authority-and-checkpoint-chain-asymmetry"
        in preflight["scope_projection"]["explicit_allow_issue_ids"]
    )


def test_multi_agent_preview_terminal_writer_reuses_all_upstream_nodes() -> None:
    decision = json.loads(
        (ROOT / MULTI_AGENT_PREVIEW_TERMINAL_WRITER_SCOPE_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["multi_agent_preview_terminal_writer_successor"] is True
    assert projection["reused_role_evaluation_count"] == 6
    assert projection["reused_cross_role_evaluation_count"] == 1
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 1
    assert projection["execution_limits"][
        "maximum_resumed_writer_analysis_continuations"
    ] == 1
    assert projection["writer_terminal_successor_zero_call_proof_status"] == (
        "writer_checkpoint_continuation_submission_fake_mutation_zero_call_pass"
    )

    preflight = build_preflight(
        root=ROOT,
        decision_ref=MULTI_AGENT_PREVIEW_TERMINAL_WRITER_SCOPE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    boundary = preflight["known_boundary"]
    assert "exactly 1 non-thinking Writer continuation" in boundary
    assert "6 completed role evaluations" in boundary
    assert "1 completed cross-role evaluation" in boundary
    assert "forbids every upstream Agent, repair or Evaluator rerun" in boundary
    assert "partial-draft business promotion" in boundary
    assert "permits only those pending frontier nodes" not in boundary
    assert "forbids analysis continuation" not in boundary


def test_multi_agent_preview_terminal_writer_submission_reuses_completed_analysis() -> None:
    decision = json.loads(
        (
            ROOT
            / MULTI_AGENT_PREVIEW_TERMINAL_WRITER_SUBMISSION_SCOPE_DECISION_REF
        ).read_text(encoding="utf-8")
    )

    projection = validate_multi_agent_preview_generic_successor_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection[
        "multi_agent_preview_terminal_writer_submission_successor"
    ] is True
    assert projection["multi_agent_preview_terminal_writer_successor"] is False
    assert projection["reused_role_evaluation_count"] == 6
    assert projection["reused_cross_role_evaluation_count"] == 1
    assert projection["execution_limits"]["maximum_new_model_nodes"] == 1
    assert projection["execution_limits"][
        "maximum_resumed_writer_analysis_continuations"
    ] == 0
    assert projection[
        "writer_terminal_submission_successor_zero_call_proof_status"
    ] == "writer_completed_analysis_strict_submission_fake_mutation_zero_call_pass"

    preflight = build_preflight(
        root=ROOT,
        decision_ref=(
            MULTI_AGENT_PREVIEW_TERMINAL_WRITER_SUBMISSION_SCOPE_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert preflight["status"] == "pass_current_decision_bound_preflight"
    assert preflight["decision_projection"][
        "multi_agent_preview_terminal_writer_submission_successor"
    ] is True
    boundary = preflight["known_boundary"]
    assert "one content-complete Writer analysis checkpoint" in boundary
    assert "exactly 1 non-thinking Writer strict submission" in boundary
    assert "0 new analysis calls" in boundary
    assert "0 analysis continuation calls" in boundary
    assert "6 completed role evaluations" in boundary
    assert "1 completed cross-role evaluation" in boundary
    assert "forbids every upstream Agent, repair or Evaluator rerun" in boundary
    assert "permits only those pending frontier nodes" not in boundary
    assert "at most two evaluator-directed local repairs" not in boundary
    assert "a conditional Writer" not in boundary


def test_dynamic_single_cell_decision_binds_current_proof_profiles_and_health() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=DYNAMIC_SINGLE_CELL_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == (
        "one_honest_DELL_SEC_only_dynamic_single_cell"
    )
    assert result["decision_projection"]["dynamic_single_cell_successor"] is True
    assert result["decision_projection"]["node_profiles"] == {
        "planner_profile_ref": {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
            "max_tokens": 16000,
        },
        "analysis_profile_ref": {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "max_tokens": 8000,
        },
        "submission_profile_ref": {
            "thinking": {"type": "disabled"},
            "reasoning_effort": None,
            "max_tokens": 2000,
        },
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["credential_value_persisted"] is False


def test_current_dynamic_single_unit_decision_binds_current_loop_and_budget() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_SINGLE_UNIT_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_current_dynamic_single_unit_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_SCOPE
    assert projection["current_dynamic_single_unit"] is True
    assert projection["current_dynamic_transport_successor"] is False
    assert projection["dynamic_single_cell_successor"] is False
    assert projection["execution_limits"] == {
        "maximum_model_calls": 4,
        "maximum_transport_attempts": 4,
        "maximum_retrieval_rounds": 2,
        "maximum_s1_s2_requests": 12,
        "maximum_external_source_network_calls": 0,
        "retries_per_model_node": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }

    # RC-S3-058 was closed by the immutable R2 transport proof.  The historical
    # v1.0 decision must remain parseable, while execution remains protected by
    # its exact-once authority/result rather than by keeping a closed issue open.
    result = build_preflight(
        root=ROOT,
        decision_ref=CURRENT_DYNAMIC_SINGLE_UNIT_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert result["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_SCOPE
    assert result["decision_projection"]["current_dynamic_single_unit"] is True


def test_current_dynamic_multi_agent_decision_binds_six_role_live_scope() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_MULTI_AGENT_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_current_dynamic_multi_agent_decision(
        root=ROOT,
        decision=decision,
    )
    assert projection["run_scope_id"] == CURRENT_DYNAMIC_MULTI_AGENT_SCOPE
    assert projection["current_dynamic_multi_agent"] is True
    assert projection["execution_limits"]["maximum_model_calls"] == 29
    assert projection["execution_limits"]["maximum_s1_s2_requests"] == 13
    assert set(projection["node_profiles"]) == {
        "specialist_request_planning",
        "specialist_reflection_and_plan_delta",
        "specialist_workpaper_submission",
        "research_lead_coordination",
        "role_local_repair_submission",
    }
    result = build_preflight(
        root=ROOT,
        decision_ref=CURRENT_DYNAMIC_MULTI_AGENT_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert result["run_scope_id"] == CURRENT_DYNAMIC_MULTI_AGENT_SCOPE
    assert result["decision_projection"]["current_dynamic_multi_agent"] is True
    assert "six independent specialist sessions" in result["known_boundary"]


def test_current_dynamic_multi_agent_content_repair_binds_exact_scope() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_current_dynamic_multi_agent_content_repair_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["run_scope_id"] == CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_SCOPE
    assert projection["current_dynamic_multi_agent_content_repair"] is True
    assert projection[
        "current_dynamic_multi_agent_content_repair_successor"
    ] is True
    assert projection["failed_R6_provider_calls"] == 0
    assert projection["successor_zero_call_status"] == (
        "content_repair_successor_zero_call_proven"
    )
    assert projection["execution_limits"]["maximum_new_model_calls"] == 12
    assert projection["execution_limits"]["maximum_new_s1_s2_requests"] == 0
    assert projection["execution_limits"]["maximum_external_source_network_calls"] == 0
    assert set(projection["node_profiles"]) == {
        "role_repair_analysis",
        "role_repair_submission",
        "lead_recheck_analysis",
        "lead_recheck_submission",
    }

    result = build_preflight(
        root=ROOT,
        decision_ref=CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert result["run_scope_id"] == CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_SCOPE
    assert result["decision_projection"][
        "current_dynamic_multi_agent_content_repair"
    ] is True
    assert "exactly five role-local financial-truth repairs" in result["known_boundary"]
    assert "at most 12 Provider calls" in result["known_boundary"]
    assert "consumed R6 terminal failure" in result["known_boundary"]
    assert "fresh R7" in result["known_boundary"]
    assert "does not authorize Writer" in result["known_boundary"]


def test_current_dynamic_multi_agent_content_repair_rejects_budget_drift() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["execution_budget"]["maximum_new_model_calls"] = 13

    with pytest.raises(
        ValueError,
        match="project_os_current_dynamic_multi_agent_content_repair_budget_invalid",
    ):
        _validate_current_dynamic_multi_agent_content_repair_decision(
            root=ROOT,
            decision=decision,
        )


def test_current_dynamic_multi_agent_content_repair_rejects_target_drift() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_MULTI_AGENT_CONTENT_REPAIR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["repair_agent_ids"][-1] = "AGENT::SUPPLY_CONSTRAINTS"

    with pytest.raises(
        ValueError,
        match="project_os_current_dynamic_multi_agent_content_repair_target_invalid",
    ):
        _validate_current_dynamic_multi_agent_content_repair_decision(
            root=ROOT,
            decision=decision,
        )


def test_current_dynamic_single_unit_decision_rejects_budget_drift() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_SINGLE_UNIT_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["execution_budget"]["maximum_model_calls"] = 5

    with pytest.raises(
        ValueError,
        match="project_os_current_dynamic_decision_budget_invalid",
    ):
        _validate_current_dynamic_single_unit_decision(
            root=ROOT,
            decision=decision,
        )


def test_current_dynamic_transport_successor_preserves_R1_and_uses_capability_profile() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=CURRENT_DYNAMIC_SINGLE_UNIT_TRANSPORT_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_TRANSPORT_SCOPE
    projection = result["decision_projection"]
    assert projection["current_dynamic_single_unit"] is True
    assert projection["current_dynamic_transport_successor"] is True
    assert projection["failed_predecessor_status"] == "terminal_failed_no_retry"
    assert "preserves the R1 HTTP 400" in result["known_boundary"]
    assert "omits unsupported thinking-mode tool_choice" in result["known_boundary"]


def test_current_dynamic_transport_successor_rejects_legacy_profile() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_SINGLE_UNIT_TRANSPORT_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    legacy_ref = (
        "configs/providers/"
        "fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_1.json"
    )
    decision["provider_profile_ref"] = legacy_ref
    decision["provider_profile_sha256"] = hashlib.sha256(
        (ROOT / legacy_ref).read_bytes()
    ).hexdigest()

    with pytest.raises(
        ValueError,
        match="project_os_current_dynamic_provider_profile_invalid",
    ):
        _validate_current_dynamic_single_unit_decision(
            root=ROOT,
            decision=decision,
        )


def test_current_dynamic_feedback_successor_binds_R2_and_round_contract() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=CURRENT_DYNAMIC_SINGLE_UNIT_FEEDBACK_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    projection = result["decision_projection"]

    assert projection["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_FEEDBACK_SCOPE
    assert projection["current_dynamic_single_unit"] is True
    assert projection["current_dynamic_transport_successor"] is False
    assert projection["current_dynamic_feedback_successor"] is True
    assert projection["failed_predecessor_status"] == "terminal_failed_no_retry"
    # R3 consumed this exact-once authority and proved both feedback rounds.
    # The historical v1.2 decision remains parseable, while the now-closed
    # RC-S3-059 must not remain a permanent live-scope blocker.
    assert (
        "RC-S3-059-current-dynamic-reflection-schema-disconnected-from-round-feedback"
        not in result["scope_projection"]["explicit_allow_issue_ids"]
    )


def test_current_dynamic_workpaper_successor_reuses_R3_without_retrieval() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_current_dynamic_single_unit_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_SCOPE
    assert projection["current_dynamic_workpaper_successor"] is True
    assert projection["current_dynamic_feedback_successor"] is False
    assert projection["failed_predecessor_status"] == "terminal_failed_no_retry"
    assert projection["execution_limits"]["maximum_model_calls"] == 1
    assert projection["execution_limits"]["maximum_retrieval_rounds"] == 0
    assert projection["execution_limits"]["maximum_s1_s2_requests"] == 0
    assert projection["node_profiles"]["workpaper_submission"][
        "maximum_completion_tokens"
    ] == 8000


def test_current_dynamic_workpaper_replacement_preserves_zero_call_R4() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_REPLACEMENT_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    projection = result["decision_projection"]

    assert projection["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_WORKPAPER_SCOPE
    assert projection["current_dynamic_workpaper_successor"] is True
    assert projection["current_dynamic_workpaper_replacement"] is True
    assert projection["execution_limits"]["maximum_model_calls"] == 1
    assert projection["execution_limits"]["maximum_retrieval_rounds"] == 0
    assert result["scope_projection"]["blocking_issue_ids"] == []
    latest_issue_rows: dict[str, dict[str, object]] = {}
    for line in (ROOT / "docs/project_os/root_cause_issue_ledger.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            row = json.loads(line)
            latest_issue_rows[str(row["issue_id"])] = row
    assert latest_issue_rows[
        "RC-S3-060-current-dynamic-workpaper-thinking-budget-starved-visible-submission"
    ]["status"] == "closed_by_R5_compact_non_thinking_contract_valid_submission"
    assert latest_issue_rows[
        "RC-S3-061-current-dynamic-workpaper-successor-used-unregistered-runtime-events"
    ]["status"] == (
        "closed_by_R5_canonical_provider_attempt_events_and_terminal_materialization"
    )


def test_historical_current_dynamic_semantic_repair_binds_contract_but_cannot_rerun() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_SINGLE_UNIT_SEMANTIC_REPAIR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_current_dynamic_single_unit_semantic_repair_decision(
        root=ROOT,
        decision=decision,
    )

    assert projection["run_scope_id"] == CURRENT_DYNAMIC_SINGLE_UNIT_SEMANTIC_REPAIR_SCOPE
    assert projection["current_dynamic_semantic_repair"] is True
    assert projection["execution_limits"]["maximum_model_calls"] == 2
    assert projection["execution_limits"]["maximum_retrieval_rounds"] == 0
    assert projection["node_profiles"]["feedback_plan_delta"][
        "maximum_completion_tokens"
    ] == 16000
    assert projection["node_profiles"]["semantic_patch_submission"][
        "maximum_completion_tokens"
    ] == 8000

    # The immutable historical decision still proves the intended R5 feedback
    # and two-node budget.  Its paid scope has since been consumed by R6/R7,
    # so Project OS must fail closed instead of silently authorizing a rerun.
    with pytest.raises(
        ValueError,
        match="project_os_current_dynamic_semantic_repair_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=CURRENT_DYNAMIC_SINGLE_UNIT_SEMANTIC_REPAIR_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_current_dynamic_semantic_repair_rejects_budget_drift() -> None:
    decision = json.loads(
        (ROOT / CURRENT_DYNAMIC_SINGLE_UNIT_SEMANTIC_REPAIR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["execution_budget"]["maximum_model_calls"] = 3

    with pytest.raises(
        ValueError,
        match="project_os_current_dynamic_semantic_repair_budget_invalid",
    ):
        _validate_current_dynamic_single_unit_semantic_repair_decision(
            root=ROOT,
            decision=decision,
        )


def test_historical_dynamic_five_cell_decision_fails_closed_after_consumer_successor(
) -> None:
    with pytest.raises(
        ValueError,
        match="project_os_five_cell_runner_source_drift:",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_FIVE_CELL_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_historical_dynamic_five_cell_remaining_nodes_successor_fails_after_partial_runtime() -> None:
    with pytest.raises(
        ValueError,
        match="project_os_five_cell_successor_source_drift:",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_historical_dynamic_five_cell_partial_successor_remains_bound_but_closed_after_r3() -> None:
    decision = json.loads(
        (ROOT / DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_dynamic_five_cell_partial_successor_decision(
        root=ROOT,
        decision=decision,
    )
    assert projection["dynamic_five_cell_partial_successor"] is True
    assert projection["dynamic_five_cell_remaining_nodes_successor"] is False
    assert projection["node_profiles"] == {
        "analysis_profile_ref": {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "max",
            "max_tokens": 16000,
        },
        "submission_profile_ref": {
            "thinking": {"type": "disabled"},
            "reasoning_effort": None,
            "max_tokens": 2000,
        },
    }

    with pytest.raises(
        ValueError,
        match="project_os_dynamic_five_cell_partial_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )

    assert decision["run_scope_id"] == (
        "one_DELL_dynamic_five_cell_partial_successor_"
        "failed_three_plus_synthesis"
    )


def test_dynamic_five_cell_node_successor_binds_R3_captures_and_strict_profiles() -> None:
    decision = json.loads(
        (ROOT / DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_dynamic_five_cell_node_successor_decision(
        root=ROOT,
        decision=decision,
    )
    assert projection["dynamic_five_cell_node_successor"] is True
    assert projection["dynamic_five_cell_partial_successor"] is False
    assert projection["node_profiles"]["submission_profile_ref"] == {
        "base_url": "https://api.deepseek.com/beta",
        "thinking": {"type": "disabled"},
        "reasoning_effort": None,
        "max_tokens": 2000,
    }

    with pytest.raises(
        ValueError,
        match="project_os_dynamic_five_cell_node_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_dynamic_five_cell_claim_surface_successor_is_current_scope() -> None:
    decision = json.loads(
        (ROOT / DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    projection = _validate_dynamic_five_cell_claim_surface_successor_decision(
        root=ROOT,
        decision=decision,
    )
    assert projection["dynamic_five_cell_claim_surface_successor"] is True
    assert projection["dynamic_five_cell_node_successor"] is False

    result = build_preflight(
        root=ROOT,
        decision_ref=DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == (
        "one_DELL_dynamic_five_cell_claim_surface_successor_exact_once"
    )
    assert set(result["scope_projection"]["explicit_allow_issue_ids"]) >= {
        "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
        "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
        "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
        "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
        "RC-S3-035-reviewed-claim-exact-source-hidden-by-prefix-projection",
    }
    assert result["model_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0


def test_dynamic_five_cell_cell_scoped_claim_successor_is_current_scope() -> None:
    decision = json.loads(
        (
            ROOT
            / DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    projection = _validate_dynamic_five_cell_claim_surface_successor_decision(
        root=ROOT,
        decision=decision,
    )
    assert projection["dynamic_five_cell_claim_surface_successor"] is True
    assert projection[
        "dynamic_five_cell_cell_scoped_claim_contract_successor"
    ] is True

    result = build_preflight(
        root=ROOT,
        decision_ref=(
            DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_REF
        ),
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == (
        "one_DELL_dynamic_five_cell_cell_scoped_claim_contract_"
        "successor_exact_once"
    )
    assert (
        "RC-S3-036-global-claim-authority-contract-leaks-value-"
        "relations-into-nonqualified-cells"
    ) in set(result["scope_projection"]["explicit_allow_issue_ids"])
    assert result["model_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0


def test_dynamic_five_cell_cell_scoped_claim_successor_binds_R5_failure() -> None:
    decision = json.loads(
        (
            ROOT
            / DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["failed_attempt_reuse_forbidden"] = False

    with pytest.raises(
        ValueError,
        match=(
            "project_os_five_cell_claim_surface_successor_true_required:"
            "failed_attempt_reuse_forbidden"
        ),
    ):
        _validate_dynamic_five_cell_claim_surface_successor_decision(
            root=ROOT,
            decision=decision,
        )


def test_dynamic_five_cell_value_repair_successor_binds_R6_and_proof() -> None:
    decision = json.loads(
        (
            ROOT / DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    projection = _validate_dynamic_five_cell_value_repair_successor_decision(
        root=ROOT,
        decision=decision,
    )
    assert projection["dynamic_five_cell_value_repair_successor"] is True
    assert projection["recent_provider_steps"] == 10
    assert projection["provider_model"] == "deepseek-v4-pro"

    preflight = build_preflight(
        root=ROOT,
        decision_ref=DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )
    assert preflight["status"] == "pass_current_decision_bound_preflight"
    assert preflight["run_scope_id"] == (
        "one_DELL_dynamic_five_cell_value_submission_repair_plus_synthesis"
    )
    assert set(preflight["scope_projection"]["explicit_allow_issue_ids"]) >= {
        "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
        "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
        "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
        "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
        "RC-S3-035-reviewed-claim-exact-source-hidden-by-prefix-projection",
        "RC-S3-036-global-claim-authority-contract-leaks-value-relations-into-nonqualified-cells",
        "RC-S3-037-value-numeric-relation-endpoint-redundancy-and-structured-support-not-recognized",
    }
    assert preflight["model_calls"] == 0
    assert preflight["provider_calls"] == 0
    assert preflight["network_calls"] == 0


def test_dynamic_five_cell_value_repair_successor_rejects_budget_drift() -> None:
    decision = json.loads(
        (
            ROOT / DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["execution_budget"]["maximum_model_calls"] = 4
    with pytest.raises(
        ValueError,
        match="project_os_five_cell_value_repair_budget_invalid",
    ):
        _validate_dynamic_five_cell_value_repair_successor_decision(
            root=ROOT,
            decision=decision,
        )


def test_dynamic_five_cell_value_repair_successor_rejects_analysis_rerun() -> None:
    decision = json.loads(
        (
            ROOT / DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_REF
        ).read_text(encoding="utf-8")
    )
    decision["rerun_cell_analysis"] = True
    with pytest.raises(
        ValueError,
        match=(
            "project_os_five_cell_value_repair_false_required:"
            "rerun_cell_analysis"
        ),
    ):
        _validate_dynamic_five_cell_value_repair_successor_decision(
            root=ROOT,
            decision=decision,
        )


def test_dynamic_five_cell_node_successor_rejects_analysis_rerun() -> None:
    decision = json.loads(
        (ROOT / DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    decision["rerun_cell_analysis"] = True

    with pytest.raises(
        ValueError,
        match="project_os_five_cell_node_successor_false_required:rerun_cell_analysis",
    ):
        _validate_dynamic_five_cell_node_successor_decision(
            root=ROOT,
            decision=decision,
        )


def test_dynamic_five_cell_decision_rejects_weakened_runner_proof(
    tmp_path: Path,
) -> None:
    root = _dynamic_five_cell_fixture_root(tmp_path)
    decision_path = root / DYNAMIC_FIVE_CELL_DECISION_REF
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    proof_path = root / decision["runner_zero_call_result_ref"]
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["acceptance"]["cell_failure_does_not_hide_later_cells"] = False
    proof_path.write_text(json.dumps(proof), encoding="utf-8")
    decision["runner_zero_call_result_sha256"] = _sha(proof_path)
    decision_path.write_text(json.dumps(decision), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="project_os_five_cell_runner_proof_invalid",
    ):
        build_preflight(
            root=root,
            decision_ref=DYNAMIC_FIVE_CELL_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def test_obsolete_dynamic_counter_successor_v1_0_fails_after_entry_drift() -> None:
    with pytest.raises(
        ValueError, match="project_os_dynamic_counter_runner_drift"
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_COUNTER_SUCCESSOR_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_obsolete_dynamic_counter_successor_v1_1_fails_after_set_repair() -> None:
    with pytest.raises(
        ValueError, match="project_os_dynamic_counter_runner_drift"
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_COUNTER_SUCCESSOR_DECISION_V1_1_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_dynamic_counter_successor_v1_2_history_survives_runner_evolution_but_scope_is_closed(
) -> None:
    with pytest.raises(
        ValueError, match="project_os_dynamic_counter_scope_allowance_missing"
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DYNAMIC_COUNTER_SUCCESSOR_DECISION_V1_2_REF,
            environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
            check_repository=False,
        )


def test_missing_provider_credential_fails_closed() -> None:
    with pytest.raises(
        ValueError, match="project_os_provider_credential_missing:DEEPSEEK_API_KEY"
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DECISION_REF,
            environment={},
            check_repository=False,
        )


def test_micro_judgment_decision_passes_with_two_bound_node_profiles() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=MICRO_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == FIXED_PACK_SCOPE
    assert result["decision_projection"]["micro_judgment_successor"] is True
    assert result["decision_projection"]["node_profiles"] == {
        "tool_routing": {"reasoning_effort": "low", "max_tokens": 2000},
        "bounded_financial_judgment": {
            "reasoning_effort": "high",
            "max_tokens": 8000,
        },
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["credential_value_persisted"] is False


def test_full_fragment_decision_passes_with_analysis_and_submission_profiles() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=FULL_FRAGMENT_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == FIXED_PACK_SCOPE
    assert result["decision_projection"][
        "full_fragment_judgment_successor"
    ] is True
    assert result["decision_projection"]["node_profiles"] == {
        "fragment_analysis": {"reasoning_effort": "high", "max_tokens": 8000},
        "contract_submission": {"reasoning_effort": "low", "max_tokens": 2000},
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["credential_value_persisted"] is False


def test_full_fragment_surface_successor_binds_failed_R1_and_QF_rendering() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=FULL_FRAGMENT_SURFACE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["decision_projection"][
        "full_fragment_judgment_successor"
    ] is True
    assert result["decision_projection"][
        "prior_failed_full_fragment_status"
    ] == "terminal_failed_no_retry"
    assert result["decision_projection"]["node_profiles"] == {
        "fragment_analysis": {"reasoning_effort": "high", "max_tokens": 8000},
        "contract_submission": {"reasoning_effort": "low", "max_tokens": 2000},
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0


def test_full_fragment_relation_role_successor_binds_failed_R2_and_context_role() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=FULL_FRAGMENT_RELATION_ROLE_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["decision_projection"]["relation_role_successor"] is True
    assert result["decision_projection"][
        "prior_failed_full_fragment_status"
    ] == "terminal_failed_no_retry"
    assert result["decision_projection"]["node_profiles"] == {
        "fragment_analysis": {"reasoning_effort": "high", "max_tokens": 8000},
        "contract_submission": {"reasoning_effort": "low", "max_tokens": 2000},
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0


def test_claim_local_boundary_successor_binds_failed_R3_and_typed_boundaries() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=FULL_FRAGMENT_CLAIM_LOCAL_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["decision_projection"][
        "claim_local_boundary_successor"
    ] is True
    assert result["decision_projection"][
        "prior_failed_full_fragment_status"
    ] == "terminal_failed_no_retry"
    assert result["decision_projection"]["node_profiles"] == {
        "fragment_analysis": {
            "reasoning_effort": "high",
            "max_tokens": 8000,
        },
        "contract_submission": {
            "reasoning_effort": "low",
            "max_tokens": 2000,
        },
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0


def test_causal_polarity_successor_binds_failed_R4_and_positive_guard() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["decision_projection"]["causal_polarity_successor"] is True
    assert result["decision_projection"][
        "prior_failed_full_fragment_status"
    ] == "terminal_failed_no_retry"
    assert result["decision_projection"]["node_profiles"] == {
        "fragment_analysis": {
            "reasoning_effort": "high",
            "max_tokens": 8000,
        },
        "contract_submission": {
            "reasoning_effort": "low",
            "max_tokens": 2000,
        },
    }
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0


def test_wwc_route_identifier_successor_binds_failed_R5_field_guard() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["decision_projection"]["causal_polarity_successor"] is True
    assert result["decision_projection"][
        "wwc_route_identifier_successor"
    ] is True
    assert result["decision_projection"][
        "prior_failed_full_fragment_status"
    ] == "terminal_failed_no_retry"
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0


def test_failed_fragment_submission_successor_binds_R6_and_non_thinking() -> None:
    clean = json.loads(
        (ROOT / NON_THINKING_SUCCESSOR_ZERO_RESULT_REF).read_text(
            encoding="utf-8"
        )
    )
    failed = json.loads(
        (ROOT / FULL_FRAGMENT_R6_RESULT_REF).read_text(encoding="utf-8")
    )
    decision = {
        "schema_version": (
            "fin_ia_s3_fixed_pack_failed_fragment_submission_successor_"
            "live_scope_decision_v1_6"
        ),
        "status": (
            "failed_fragment_zero_call_pass_one_non_thinking_submission_"
            "successor_authorized"
        ),
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": "submit_research_counterargument_and_wwc",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_R6_failed_counter_submission_"
            "successor"
        ),
        "replacement_is_new_attempt_not_retry": True,
        "chat_live_authorized": True,
        "credential_presence_required": True,
        "same_evidence_pack": True,
        "immutable_successful_prefix_reused": True,
        "immutable_counter_analysis_reused": True,
        "failed_node_only_execution_required": True,
        "non_thinking_submission_required": True,
        "reasoning_effort_omitted_required": True,
        "terminal_contract_parity_required": True,
        "clock_derived_authority_timestamp_required": True,
        "historical_failure_promoted": False,
        "successful_predecessor_nodes_rerun": False,
        "analysis_node_rerun": False,
        "responses_live_authorized": False,
        "anthropic_live_authorized": False,
        "dynamic_layer_two_authorized": False,
        "five_cell_live_authorized": False,
        "heterogeneous_generalization_authorized": False,
        "product_publication_authorized": False,
        "reasoning_or_token_limit_increase": False,
        "successful_predecessor_model_calls_reused": 5,
        "maximum_fresh_model_calls": 1,
        "maximum_provider_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "clean_zero_call_result_ref": NON_THINKING_SUCCESSOR_ZERO_RESULT_REF,
        "clean_zero_call_result_sha256": _sha(
            ROOT / NON_THINKING_SUCCESSOR_ZERO_RESULT_REF
        ),
        "clean_zero_call_result_digest": clean["result_digest"],
        "immutable_failed_result_ref": FULL_FRAGMENT_R6_RESULT_REF,
        "immutable_failed_result_sha256": _sha(
            ROOT / FULL_FRAGMENT_R6_RESULT_REF
        ),
        "immutable_failed_result_digest": failed["result_digest"],
        "failed_result_assessment_ref": FULL_FRAGMENT_R6_ASSESSMENT_REF,
        "failed_result_assessment_sha256": _sha(
            ROOT / FULL_FRAGMENT_R6_ASSESSMENT_REF
        ),
        "submission_successor_fixture_ref": (
            FULL_FRAGMENT_R6_SUCCESSOR_FIXTURE_REF
        ),
        "submission_successor_fixture_sha256": _sha(
            ROOT / FULL_FRAGMENT_R6_SUCCESSOR_FIXTURE_REF
        ),
        "submission_profile_ref": NON_THINKING_SUBMISSION_PROFILE_REF,
        "submission_profile_sha256": _sha(
            ROOT / NON_THINKING_SUBMISSION_PROFILE_REF
        ),
    }
    result = _validate_failed_fragment_submission_successor_decision(
        root=ROOT,
        decision=decision,
    )
    assert result["failed_fragment_submission_successor"] is True
    assert result["successful_predecessor_model_calls_reused"] == 5
    assert result["fresh_model_calls_authorized"] == 1
    assert result["node_profiles"] == {
        "contract_submission": {
            "thinking": "disabled",
            "reasoning_effort": "omitted",
            "max_tokens": 2000,
        }
    }


def test_fragment_validation_repair_binds_R7_and_preserves_guard() -> None:
    clean = json.loads(
        (ROOT / VALIDATION_REPAIR_ZERO_RESULT_REF).read_text(encoding="utf-8")
    )
    failed = json.loads(
        (ROOT / FAILED_COUNTER_R7_RESULT_REF).read_text(encoding="utf-8")
    )
    decision = {
        "schema_version": (
            "fin_ia_s3_fixed_pack_fragment_validation_repair_"
            "live_scope_decision_v1_8"
        ),
        "status": "zero_call_pass_one_validation_repair_authorized",
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": "submit_research_counterargument_and_wwc",
        "terminal_failure_code": "claim_surface_narrative_relation_conflict",
        "run_scope_id": FRAGMENT_VALIDATION_REPAIR_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_R7_failed_counter_validation_repair"
        ),
        "replacement_is_new_attempt_not_retry": True,
        "chat_live_authorized": True,
        "credential_presence_required": True,
        "same_evidence_pack": True,
        "immutable_successful_prefix_reused": True,
        "rejected_fragment_preserved": True,
        "failed_node_only_execution_required": True,
        "typed_validation_feedback_required": True,
        "non_thinking_submission_required": True,
        "terminal_contract_parity_required": True,
        "clock_derived_authority_timestamp_required": True,
        "historical_failure_promoted": False,
        "successful_predecessor_nodes_rerun": False,
        "analysis_node_rerun": False,
        "causal_guard_relaxation": False,
        "manual_text_rewrite": False,
        "responses_live_authorized": False,
        "anthropic_live_authorized": False,
        "dynamic_layer_two_authorized": False,
        "five_cell_live_authorized": False,
        "heterogeneous_generalization_authorized": False,
        "product_publication_authorized": False,
        "reasoning_or_token_limit_increase": False,
        "successful_predecessor_model_calls_reused": 6,
        "maximum_fresh_model_calls": 1,
        "maximum_provider_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_repair_turns": 1,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "clean_zero_call_result_ref": VALIDATION_REPAIR_ZERO_RESULT_REF,
        "clean_zero_call_result_sha256": _sha(
            ROOT / VALIDATION_REPAIR_ZERO_RESULT_REF
        ),
        "clean_zero_call_result_digest": clean["result_digest"],
        "immutable_failed_result_ref": FAILED_COUNTER_R7_RESULT_REF,
        "immutable_failed_result_sha256": _sha(
            ROOT / FAILED_COUNTER_R7_RESULT_REF
        ),
        "immutable_failed_result_digest": failed["result_digest"],
        "failed_result_assessment_ref": FAILED_COUNTER_R7_ASSESSMENT_REF,
        "failed_result_assessment_sha256": _sha(
            ROOT / FAILED_COUNTER_R7_ASSESSMENT_REF
        ),
        "rejected_fragment_fixture_ref": FAILED_COUNTER_R7_FIXTURE_REF,
        "rejected_fragment_fixture_sha256": _sha(
            ROOT / FAILED_COUNTER_R7_FIXTURE_REF
        ),
        "submission_profile_ref": NON_THINKING_SUBMISSION_PROFILE_REF,
        "submission_profile_sha256": _sha(
            ROOT / NON_THINKING_SUBMISSION_PROFILE_REF
        ),
    }
    result = _validate_fragment_validation_repair_decision(
        root=ROOT,
        decision=decision,
    )
    assert result["fragment_validation_repair_successor"] is True
    assert result["successful_predecessor_model_calls_reused"] == 6
    assert result["fresh_model_calls_authorized"] == 1
    assert result["maximum_repair_turns"] == 1
    assert result["node_profiles"] == {
        "contract_submission_repair": {
            "thinking": "disabled",
            "reasoning_effort": "omitted",
            "max_tokens": 2000,
        }
    }


def test_micro_judgment_profile_digest_drift_fails_closed(
    tmp_path: Path,
) -> None:
    root = _micro_fixture_root(tmp_path)
    decision_path = root / MICRO_DECISION_REF
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["micro_judgment_profile_sha256"] = "0" * 64
    decision_path.write_text(json.dumps(decision), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="project_os_artifact_sha_drift:micro_judgment_profile_ref",
    ):
        build_preflight(
            root=root,
            decision_ref=MICRO_DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def test_claim_relation_alias_capacity_decision_passes_same_strict_preflight(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    _copy_ref(root, ALIAS_CLEAN_REF)
    _copy_ref(root, CAPACITY_PREDECESSOR_REF)
    decision_path = root / DECISION_REF
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    clean = json.loads((root / ALIAS_CLEAN_REF).read_text(encoding="utf-8"))
    predecessor = json.loads(
        (root / CAPACITY_PREDECESSOR_REF).read_text(encoding="utf-8")
    )
    decision.update(
        {
            "status": (
                "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
                "one_chat_successor_authorized"
            ),
            "next_authorized_scope": (
                "one_DELL_value_capture_fixed_pack_claim_relation_alias_"
                "Chat_successor"
            ),
            "clean_zero_call_result_ref": ALIAS_CLEAN_REF,
            "clean_zero_call_result_sha256": _sha(root / ALIAS_CLEAN_REF),
            "clean_zero_call_result_digest": clean["result_digest"],
            "immutable_predecessor_result_ref": CAPACITY_PREDECESSOR_REF,
            "immutable_predecessor_result_sha256": _sha(
                root / CAPACITY_PREDECESSOR_REF
            ),
            "immutable_predecessor_result_digest": predecessor[
                "result_digest"
            ],
            "same_evidence_pack_and_provider_profile": True,
            "reasoning_or_token_limit_increase": False,
        }
    )
    decision_path.write_text(json.dumps(decision), encoding="utf-8")

    result = build_preflight(
        root=root,
        decision_ref=DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["decision_projection"][
        "claim_relation_alias_capacity_successor"
    ] is True
    assert (
        "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget"
        in result["scope_projection"]["explicit_allow_issue_ids"]
    )


def test_bound_artifact_sha_drift_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    decision = json.loads((root / DECISION_REF).read_text(encoding="utf-8"))
    clean_path = root / decision["clean_zero_call_result_ref"]
    clean_path.write_text(clean_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="project_os_artifact_sha_drift"):
        build_preflight(
            root=root,
            decision_ref=DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def test_new_scope_specific_blocker_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    ledger = root / "docs/project_os/root_cause_issue_ledger.jsonl"
    blocker = {
        "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
        "issue_id": "RC-TEST-CURRENT-SCOPE-BLOCKER",
        "status": "open",
        "full_chain_blocker": True,
        "blocking_run_scopes": [FIXED_PACK_SCOPE],
        "allowed_run_scopes": [],
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(blocker, ensure_ascii=False) + "\n")

    with pytest.raises(
        ValueError,
        match="project_os_scope_blocked:RC-TEST-CURRENT-SCOPE-BLOCKER",
    ):
        build_preflight(
            root=root,
            decision_ref=DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def test_consumed_report_remap_scope_preserves_one_node_two_attempt_semantics() -> None:
    decision = json.loads(
        (ROOT / REPORT_REMAP_DECISION_REF).read_text(encoding="utf-8")
    )
    assert decision["run_scope_id"] == REPORT_REMAP_RUN_SCOPE
    assert decision["execution_limits"]["maximum_new_logical_model_nodes"] == 1
    assert decision["execution_limits"]["maximum_contract_attempts"] == 2
    assert decision["execution_limits"]["maximum_new_analysis_calls"] == 0
    assert decision["execution_limits"]["maximum_new_writer_continuations"] == 0


def test_report_remap_replacement_binds_length_failure_and_budget_basis() -> None:
    decision = json.loads(
        (ROOT / REPORT_REMAP_REPLACEMENT_DECISION_REF).read_text(encoding="utf-8")
    )
    assert decision["run_scope_id"] == REPORT_REMAP_REPLACEMENT_RUN_SCOPE
    assert decision["execution_limits"]["maximum_new_logical_model_nodes"] == 1
    assert decision["token_budget_basis"]["maximum_output_tokens"] == 12000
    assert decision["bound_inputs"]["failed_remap_public_result"][
        "digest"
    ] == "72d5fe7f3d1c16e9f6014bece396ef00a45f5212d971ce7480038d86a36af648"


def test_historical_report_reference_patch_rejects_current_runtime_drift() -> None:
    decision = json.loads(
        (ROOT / REPORT_REMAP_REFERENCE_PATCH_DECISION_REF).read_text(
            encoding="utf-8"
        )
    )
    assert decision["run_scope_id"] == REPORT_REMAP_REFERENCE_PATCH_RUN_SCOPE
    assert decision["execution_limits"]["maximum_reference_patch_targets"] == 5
    assert decision["token_budget_basis"]["maximum_output_tokens"] == 4000

    # The immutable proof and its legacy quality policy remain readable, but
    # the authority must not be reusable after the report runtime changes.
    with pytest.raises(
        ReportRemapAuthorityError,
        match="report_remap_implementation_sha_drift",
    ):
        validate_report_remap_scope_decision(root=ROOT, decision=decision)
