from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from sec_agent.project_os_preflight import (
    FIXED_PACK_SCOPE,
    FRAGMENT_VALIDATION_REPAIR_SCOPE,
    REQUIRED_PROJECT_OS_REFS,
    _validate_fragment_validation_repair_decision,
    _validate_failed_fragment_submission_successor_decision,
    build_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
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
        in result["scope_projection"]["explicit_allow_issue_ids"]
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
