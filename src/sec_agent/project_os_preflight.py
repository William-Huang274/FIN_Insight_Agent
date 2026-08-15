from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


CURRENT_PREFLIGHT_SCHEMA = "fin_ia_current_decision_bound_project_os_preflight_v1_0"
FIXED_PACK_SCOPE = (
    "one_separately_authorized_natural_fixed_pack_replacement_with_zero_retry"
)
MICRO_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_micro_judgment_live_scope_decision_v1_0"
)
MICRO_FIXED_PACK_DECISION_STATUS = (
    "micro_judgment_formal_zero_call_pass_"
    "canonical_live_gate_required_one_chat_successor_authorized"
)
FULL_FRAGMENT_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_scope_decision_v1_0"
)
FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_surface_"
    "live_scope_decision_v1_1"
)
FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_relation_role_"
    "live_scope_decision_v1_2"
)
FULL_FRAGMENT_FIXED_PACK_DECISION_STATUS = (
    "full_fragment_zero_call_pass_one_fresh_chat_judgment_authorized"
)
REQUIRED_PROJECT_OS_REFS = (
    "docs/project_os/current_context_pack.zh-CN.md",
    "docs/project_os/senior_assistant_collaboration_policy.zh-CN.md",
    "docs/project_os/root_cause_issue_ledger.jsonl",
    "docs/project_os/capability_status_ledger.jsonl",
    "docs/project_os/full_chain_preflight_checklist.json",
    "docs/project_os/full_chain_run_policy.zh-CN.md",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_path(root: Path, ref: str) -> Path:
    if not ref or Path(ref).is_absolute():
        raise ValueError(f"project_os_ref_not_repo_relative:{ref}")
    path = (root / ref).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError(f"project_os_ref_missing:{ref}")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"project_os_json_object_required:{path.as_posix()}")
    return value


def _latest_jsonl_rows(path: Path, key: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"project_os_jsonl_invalid:{path.as_posix()}:{line_number}"
            ) from exc
        if not isinstance(row, dict) or not row.get(key):
            raise ValueError(
                f"project_os_jsonl_key_missing:{path.as_posix()}:{line_number}:{key}"
            )
        latest[str(row[key])] = row
    if not latest:
        raise ValueError(f"project_os_jsonl_empty:{path.as_posix()}")
    return latest


def _validate_artifact_binding(
    *,
    root: Path,
    decision: Mapping[str, Any],
    ref_field: str,
    sha_field: str,
    digest_field: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    ref = str(decision.get(ref_field) or "")
    path = _repo_path(root, ref)
    actual_sha = _sha256(path)
    expected_sha = str(decision.get(sha_field) or "")
    if actual_sha != expected_sha:
        raise ValueError(f"project_os_artifact_sha_drift:{ref_field}:{ref}")
    payload = _load_json(path)
    if digest_field is not None:
        expected_digest = str(decision.get(digest_field) or "")
        if str(payload.get("result_digest") or "") != expected_digest:
            raise ValueError(f"project_os_artifact_result_digest_drift:{ref_field}:{ref}")
    return path, payload


def _validate_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    if decision.get("schema_version") in {
        FULL_FRAGMENT_FIXED_PACK_DECISION_SCHEMA,
        FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA,
        FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA,
    }:
        return _validate_full_fragment_fixed_pack_decision(
            root=root, decision=decision
        )
    if decision.get("schema_version") == MICRO_FIXED_PACK_DECISION_SCHEMA:
        return _validate_micro_fixed_pack_decision(
            root=root, decision=decision
        )
    alias_status = (
        "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
        "one_chat_successor_authorized"
    )
    alias_mode = decision.get("status") == alias_status
    required_equal = {
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_DELL_value_capture_fixed_pack_claim_relation_alias_Chat_successor"
            if alias_mode
            else "one_DELL_value_capture_fixed_pack_claim_surface_Chat_replacement"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_decision_field_invalid:{field}")
    if "authorized" not in str(decision.get("status") or ""):
        raise ValueError("project_os_decision_not_authorized")

    required_true = (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
    )
    required_false = (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "product_publication_authorized",
    )
    for field in required_true:
        if decision.get(field) is not True:
            raise ValueError(f"project_os_decision_true_required:{field}")
    for field in required_false:
        if decision.get(field) is not False:
            raise ValueError(f"project_os_decision_false_required:{field}")
    if alias_mode:
        if decision.get("same_evidence_pack_and_provider_profile") is not True:
            raise ValueError(
                "project_os_decision_true_required:"
                "same_evidence_pack_and_provider_profile"
            )
        if decision.get("reasoning_or_token_limit_increase") is not False:
            raise ValueError(
                "project_os_decision_false_required:"
                "reasoning_or_token_limit_increase"
            )

    numeric_equal = {
        "maximum_model_calls": 3,
        "maximum_provider_transport_attempts": 3,
        "maximum_completion_tokens_per_call": 16000,
        "maximum_total_completion_tokens": 48000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_decision_budget_invalid:{field}")

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    acceptance = clean.get("acceptance") or {}
    legacy_clean_valid = (
        clean.get("status")
        == "engineering_pass_zero_call_claim_surface_authority"
        and acceptance.get("corrected_zero_call_judgment_passes") is True
        and acceptance.get("zero_request_fixed_pack_loop_passes") is True
        and acceptance.get("natural_replacement_live_proven") is False
    )
    alias_clean_valid = (
        clean.get("status")
        == "engineering_pass_zero_call_claim_relation_alias_capacity"
        and acceptance.get(
            "relation_alias_selection_and_local_expansion_pass"
        )
        is True
        and acceptance.get("capacity_reduction_pass") is True
        and acceptance.get("fake_loop_and_mutation_pass") is True
        and acceptance.get("natural_replacement_live_proven") is False
    )
    if (alias_mode and not alias_clean_valid) or (
        not alias_mode and not legacy_clean_valid
    ):
        raise ValueError("project_os_clean_proof_acceptance_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    if predecessor.get("status") != "terminal_failed_no_retry":
        raise ValueError("project_os_predecessor_status_invalid")
    expected_failure = (
        "model_gateway_reasoning_budget_exhausted"
        if alias_mode
        else "finance_loop_judgment_invalid:research_consumer_thesis_atom_invalid"
    )
    if predecessor.get("failure_code") != expected_failure:
        raise ValueError("project_os_predecessor_failure_code_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_profile_ref",
        sha_field="provider_profile_sha256",
    )
    if (
        profile.get("wire_api") != "openai_compatible_chat_completions"
        or profile.get("model") != "deepseek-v4-pro"
        or (profile.get("authority") or {}).get("retry_count") != 0
    ):
        raise ValueError("project_os_provider_profile_invalid")
    if (profile.get("request_defaults") or {}).get("max_tokens") != decision.get(
        "maximum_completion_tokens_per_call"
    ):
        raise ValueError("project_os_provider_profile_budget_drift")

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    if (
        health.get("status") != "completed_contract_valid_content_assessment_pending"
        or (health.get("execution") or {}).get("retries") != 0
        or not health.get("provider_steps")
    ):
        raise ValueError("project_os_provider_health_evidence_invalid")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": len(health["provider_steps"]),
        "claim_relation_alias_capacity_successor": alias_mode,
        "micro_judgment_successor": False,
    }


def _validate_full_fragment_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    surface_successor = (
        decision.get("schema_version")
        in {
            FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA,
            FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA,
        }
    )
    relation_role_successor = (
        decision.get("schema_version")
        == FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA
    )
    required_equal = {
        "status": FULL_FRAGMENT_FIXED_PACK_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            (
                "one_clean_synced_exact_once_DELL_value_capture_full_three_"
                "fragment_analysis_submission_Chat_R3"
            )
            if relation_role_successor
            else (
                "one_clean_synced_exact_once_DELL_value_capture_full_three_"
                "fragment_analysis_submission_Chat_live"
            )
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_full_fragment_decision_field_invalid:{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "terminal_contract_parity_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_full_fragment_decision_true_required:{field}"
            )
    if surface_successor:
        for field in (
            "fragment_surface_contract_parity_required",
            "saved_R1_replay_required",
            "final_QF_surface_rendering_required",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_full_fragment_decision_true_required:"
                    f"{field}"
                )
    if relation_role_successor:
        for field in (
            "relation_support_set_v1_2_required",
            "saved_R2_replay_required",
            "fragment_local_disposition_required",
            "clock_derived_authority_timestamp_required",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_full_fragment_decision_true_required:"
                    f"{field}"
                )
    for field in (
        "historical_failure_promoted",
        "immutable_thesis_predecessor_reused",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_full_fragment_decision_false_required:{field}"
            )
    numeric_equal = {
        "maximum_model_calls": 6,
        "maximum_provider_transport_attempts": 6,
        "maximum_tool_calls": 3,
        "maximum_analysis_completion_tokens_per_call": 8000,
        "maximum_submission_completion_tokens_per_call": 2000,
        "maximum_total_completion_tokens": 30000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_full_fragment_decision_budget_invalid:{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    expected_clean_status = (
        "zero_call_relation_support_and_fragment_local_disposition_pass"
        if relation_role_successor
        else "zero_call_full_fragment_sequence_and_terminal_judgment_pass_predecessor_not_reusable"
    )
    if not (
        clean.get("status") == expected_clean_status
        and (
            clean.get("fresh_process_results_byte_equivalent") is True
            if relation_role_successor
            else (clean.get("fresh_process") or {}).get("byte_equivalent")
            is True
        )
        and (clean.get("immutable_predecessor") or {}).get(
            "reuse_in_full_judgment_authorized"
        )
        is False
        and (
            (
                (clean.get("terminal_compilation") or {}).get(
                    "harness_generated_research_judgment"
                )
                is False
            )
            if relation_role_successor
            else (clean.get("full_fake_sequence") or {})
            .get("terminal_judgment", {})
            .get("harness_generated_research_judgment")
            is False
        )
        and (
            not surface_successor
            or (
                (
                    relation_role_successor
                    or (clean.get("surface_contract") or {}).get(
                        "saved_R1_replay_failure"
                    )
                    == "finance_loop_micro_narrative_invalid"
                )
                and (clean.get("surface_contract") or {}).get(
                    "final_deliverable_QF_surface_preserved"
                )
                is True
            )
        )
        and (
            not relation_role_successor
            or (
                (clean.get("relation_role_contract") or {}).get(
                    "saved_R2_thesis_replay_pass"
                )
                is True
                and (clean.get("relation_role_contract") or {}).get(
                    "saved_R2_mechanism_replay_pass"
                )
                is True
                and (clean.get("relation_role_contract") or {}).get(
                    "saved_R2_context_role_preserved"
                )
                is True
                and (clean.get("relation_role_contract") or {}).get(
                    "context_only_required_support_mutation_failure"
                )
                == "finance_loop_micro_required_authority_missing"
                and (clean.get("terminal_compilation") or {}).get(
                    "judgment_status"
                )
                == "bounded_support"
                and (clean.get("terminal_compilation") or {}).get(
                    "inference_authority"
                )
                == "bounded_inference"
            )
        )
    ):
        raise ValueError("project_os_full_fragment_clean_proof_invalid")

    _, disposition = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="scope_disposition_ref",
        sha_field="scope_disposition_sha256",
    )
    expected_disposition_status = (
        "approved_fresh_full_three_fragment_analysis_submission_Chat_R3"
        if relation_role_successor
        else "approved_fresh_full_three_fragment_analysis_submission_Chat_live"
    )
    if not (
        disposition.get("status") == expected_disposition_status
        and disposition.get("execution_budget", {}).get(
            "maximum_model_calls"
        )
        == 6
        and disposition.get("dynamic_agentic_research_authorized") is False
        and (
            not surface_successor
            or (
                (
                    relation_role_successor
                    or disposition.get("surface_contract_v1_1_required")
                    is True
                )
                and disposition.get("prior_failed_attempt_reused") is False
            )
        )
        and (
            not relation_role_successor
            or disposition.get("relation_support_set_v1_2_required") is True
        )
    ):
        raise ValueError("project_os_full_fragment_disposition_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_assessment_ref",
        sha_field="predecessor_assessment_sha256",
    )
    if not (
        predecessor.get("status")
        == "completed_fragment_contract_valid_content_assessment_pending"
        and (predecessor.get("execution") or {}).get("retries") == 0
        and predecessor_assessment.get("status")
        == "single_thesis_L1_pass_content_materially_improved_two_hypotheses_qualified_no_automatic_expansion"
        and decision.get("immutable_thesis_predecessor_reused") is False
    ):
        raise ValueError("project_os_full_fragment_predecessor_invalid")

    prior_failed_status = ""
    if surface_successor:
        _, prior_failed = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="immutable_failed_full_fragment_result_ref",
            sha_field="immutable_failed_full_fragment_result_sha256",
            digest_field="immutable_failed_full_fragment_result_digest",
        )
        _, prior_failed_assessment = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="failed_full_fragment_assessment_ref",
            sha_field="failed_full_fragment_assessment_sha256",
        )
        expected_failure_code = (
            "finance_loop_micro_required_authority_missing"
            if relation_role_successor
            else "finance_loop_micro_narrative_invalid"
        )
        expected_failure_fragment = (
            "submit_research_mechanism"
            if relation_role_successor
            else "submit_research_thesis"
        )
        expected_assessment_status = (
            "terminal_contract_failure_relation_evidence_role_and_"
            "fragment_disposition_compilation_defect_new_attempt_required"
            if relation_role_successor
            else "terminal_contract_failure_project_surface_projection_"
            "defect_new_attempt_required"
        )
        expected_preserved_field = (
            "immutable_R2_preserved"
            if relation_role_successor
            else "same_attempt_retry_forbidden"
        )
        if not (
            prior_failed.get("status") == "terminal_failed_no_retry"
            and prior_failed.get("failure_code") == expected_failure_code
            and prior_failed.get("failure_fragment_tool")
            == expected_failure_fragment
            and (prior_failed.get("execution") or {}).get("retries") == 0
            and prior_failed_assessment.get("status")
            == expected_assessment_status
            and (prior_failed_assessment.get("disposition") or {}).get(
                expected_preserved_field
            )
            is True
        ):
            raise ValueError(
                "project_os_full_fragment_failed_predecessor_invalid"
            )
        prior_failed_status = str(prior_failed["status"])

    _, analysis_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_profile_ref",
        sha_field="analysis_profile_sha256",
    )
    _, submission_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    for profile in (analysis_profile, submission_profile):
        if not (
            profile.get("wire_api") == "openai_compatible_chat_completions"
            and profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and (profile.get("authority") or {}).get("retry_count") == 0
        ):
            raise ValueError("project_os_full_fragment_provider_profile_invalid")
    analysis_defaults = analysis_profile.get("request_defaults") or {}
    submission_defaults = submission_profile.get("request_defaults") or {}
    if not (
        analysis_defaults.get("reasoning_effort") == "high"
        and analysis_defaults.get("max_tokens")
        == decision.get("maximum_analysis_completion_tokens_per_call")
        and submission_defaults.get("reasoning_effort") == "low"
        and submission_defaults.get("max_tokens")
        == decision.get("maximum_submission_completion_tokens_per_call")
    ):
        raise ValueError("project_os_full_fragment_provider_profile_budget_drift")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "prior_failed_full_fragment_status": prior_failed_status,
        "provider_id": analysis_profile["provider_id"],
        "provider_model": analysis_profile["model"],
        "api_key_env": analysis_profile["api_key_env"],
        "recent_provider_steps": 2,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": True,
        "relation_role_successor": relation_role_successor,
        "node_profiles": {
            "fragment_analysis": {
                "reasoning_effort": analysis_defaults["reasoning_effort"],
                "max_tokens": analysis_defaults["max_tokens"],
            },
            "contract_submission": {
                "reasoning_effort": submission_defaults["reasoning_effort"],
                "max_tokens": submission_defaults["max_tokens"],
            },
        },
    }


def _validate_micro_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": MICRO_FIXED_PACK_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_DELL_value_capture_fixed_pack_micro_judgment_Chat_successor"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_micro_decision_field_invalid:{field}")
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "canonical_live_gate_required",
        "same_evidence_pack",
    ):
        if decision.get(field) is not True:
            raise ValueError(f"project_os_micro_decision_true_required:{field}")
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(f"project_os_micro_decision_false_required:{field}")
    numeric_equal = {
        "maximum_model_calls": 4,
        "maximum_provider_transport_attempts": 4,
        "maximum_tool_calls": 5,
        "maximum_read_completion_tokens": 2000,
        "maximum_judgment_completion_tokens_per_call": 8000,
        "maximum_total_completion_tokens": 26000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_micro_decision_budget_invalid:{field}")

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    clean_acceptance = clean.get("acceptance") or {}
    if not (
        clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and clean_acceptance.get("natural_model_submission_proven") is False
        and clean_acceptance.get("fixed_pack_layer_one_accepted") is False
        and clean_acceptance.get("dynamic_agentic_research_authorized") is False
    ):
        raise ValueError("project_os_micro_clean_proof_acceptance_invalid")

    _, proof_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="micro_zero_call_authority_ref",
        sha_field="micro_zero_call_authority_sha256",
    )
    if (
        proof_authority.get("authority_id")
        != decision.get("formal_zero_call_authority_id")
        or proof_authority.get("status")
        != "fresh_zero_network_zero_model_bounded_finance_loop_proof_authorized"
    ):
        raise ValueError("project_os_micro_proof_authority_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    if not (
        predecessor.get("status") == "terminal_failed_no_retry"
        and predecessor.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and (predecessor.get("execution") or {}).get("retries") == 0
        and (predecessor.get("execution") or {}).get("fallbacks") == 0
    ):
        raise ValueError("project_os_micro_predecessor_invalid")

    _, capacity = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="prior_capacity_assessment_ref",
        sha_field="prior_capacity_assessment_sha256",
    )
    if not (
        capacity.get("status")
        == (
            "terminal_capacity_failure_preserved_"
            "monolithic_judgment_successor_required"
        )
        and capacity.get("result_digest") == predecessor.get("result_digest")
        and (capacity.get("acceptance") or {}).get(
            "fixed_pack_layer_one_accepted"
        )
        is False
    ):
        raise ValueError("project_os_micro_capacity_assessment_invalid")

    _, read_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="micro_read_profile_ref",
        sha_field="micro_read_profile_sha256",
    )
    _, judgment_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="micro_judgment_profile_ref",
        sha_field="micro_judgment_profile_sha256",
    )
    for profile in (read_profile, judgment_profile):
        if not (
            profile.get("wire_api") == "openai_compatible_chat_completions"
            and profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and (profile.get("authority") or {}).get("retry_count") == 0
        ):
            raise ValueError("project_os_micro_provider_profile_invalid")
    read_defaults = read_profile.get("request_defaults") or {}
    judgment_defaults = judgment_profile.get("request_defaults") or {}
    if not (
        read_defaults.get("reasoning_effort") == "low"
        and read_defaults.get("max_tokens")
        == decision.get("maximum_read_completion_tokens")
        and judgment_defaults.get("reasoning_effort") == "high"
        and judgment_defaults.get("max_tokens")
        == decision.get("maximum_judgment_completion_tokens_per_call")
    ):
        raise ValueError("project_os_micro_provider_profile_budget_drift")

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    if not (
        health.get("status")
        == "completed_contract_valid_content_assessment_pending"
        and (health.get("execution") or {}).get("retries") == 0
        and health.get("provider_steps")
    ):
        raise ValueError("project_os_provider_health_evidence_invalid")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "capacity_assessment_status": capacity["status"],
        "provider_id": read_profile["provider_id"],
        "provider_model": read_profile["model"],
        "api_key_env": read_profile["api_key_env"],
        "recent_provider_steps": len(health["provider_steps"]),
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": True,
        "node_profiles": {
            "tool_routing": {
                "reasoning_effort": read_defaults["reasoning_effort"],
                "max_tokens": read_defaults["max_tokens"],
            },
            "bounded_financial_judgment": {
                "reasoning_effort": judgment_defaults["reasoning_effort"],
                "max_tokens": judgment_defaults["max_tokens"],
            },
        },
    }


def _scope_blocker_projection(
    *, root: Path, run_scope_id: str
) -> dict[str, Any]:
    ledger = _latest_jsonl_rows(
        _repo_path(root, "docs/project_os/root_cause_issue_ledger.jsonl"),
        "issue_id",
    )
    blocked: list[str] = []
    explicitly_allowed: list[str] = []
    out_of_scope: list[str] = []
    for issue_id, row in sorted(ledger.items()):
        if row.get("full_chain_blocker") is not True:
            continue
        blocking = {str(value) for value in row.get("blocking_run_scopes") or ()}
        allowed = {str(value) for value in row.get("allowed_run_scopes") or ()}
        if run_scope_id in allowed:
            explicitly_allowed.append(issue_id)
            continue
        if "*" in blocking or run_scope_id in blocking or (not blocking and not allowed):
            blocked.append(issue_id)
        else:
            out_of_scope.append(issue_id)
    if blocked:
        raise ValueError("project_os_scope_blocked:" + ",".join(blocked))
    if "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use" not in explicitly_allowed:
        raise ValueError("project_os_claim_surface_scope_allowance_missing")
    return {
        "blocking_issue_ids": blocked,
        "explicit_allow_issue_ids": explicitly_allowed,
        "out_of_scope_full_chain_blocker_count": len(out_of_scope),
    }


def _issue_explicitly_allows(
    *, root: Path, issue_id: str, allowed_scope: str
) -> bool:
    ledger = _latest_jsonl_rows(
        _repo_path(root, "docs/project_os/root_cause_issue_ledger.jsonl"),
        "issue_id",
    )
    issue = ledger.get(issue_id) or {}
    return allowed_scope in {
        str(value) for value in issue.get("allowed_run_scopes") or ()
    }


def _repository_projection(root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    head = git("rev-parse", "HEAD")
    upstream = git("rev-parse", "@{upstream}")
    porcelain = git("status", "--porcelain")
    if head != upstream:
        raise ValueError("project_os_repository_not_synced")
    if porcelain:
        raise ValueError("project_os_repository_not_clean")
    return {"head": head, "upstream": upstream, "clean": True, "synced": True}


def build_preflight(
    *,
    root: Path,
    decision_ref: str,
    environment: Mapping[str, str] | None = None,
    check_repository: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    project_os_digests: dict[str, str] = {}
    for ref in REQUIRED_PROJECT_OS_REFS:
        path = _repo_path(root, ref)
        if path.suffix == ".json":
            _load_json(path)
        elif path.suffix == ".jsonl":
            key = "issue_id" if "root_cause" in ref else "capability_id"
            _latest_jsonl_rows(path, key)
        elif not path.read_text(encoding="utf-8").strip():
            raise ValueError(f"project_os_document_empty:{ref}")
        project_os_digests[ref] = _sha256(path)

    decision_path = _repo_path(root, decision_ref)
    decision = _load_json(decision_path)
    decision_projection = _validate_fixed_pack_decision(root=root, decision=decision)
    scope_projection = _scope_blocker_projection(
        root=root, run_scope_id=str(decision["run_scope_id"])
    )
    if (
        decision.get("status")
        == (
            "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
            "one_chat_successor_authorized"
        )
        and "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget"
        not in scope_projection["explicit_allow_issue_ids"]
    ):
        raise ValueError("project_os_claim_relation_alias_scope_allowance_missing")
    if (
        decision_projection.get("micro_judgment_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence"
            ),
            allowed_scope=(
                "one_exact_once_natural_fixed_pack_micro_successor_after_all_gates"
            ),
        )
    ):
        raise ValueError("project_os_micro_judgment_scope_allowance_missing")
    if (
        decision_projection.get("full_fragment_judgment_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence"
            ),
            allowed_scope=(
                "one_full_fixed_pack_new_attempt_after_engineering_and_"
                "authority_gates"
            ),
        )
    ):
        raise ValueError("project_os_full_fragment_scope_allowance_missing")
    if (
        decision_projection.get("relation_role_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-018-relation-required-support-and-fragment-status-"
                "coupling"
            ),
            allowed_scope="one_new_R3_after_clean_synced_proof",
        )
    ):
        raise ValueError(
            "project_os_full_fragment_relation_role_scope_allowance_missing"
        )

    env = os.environ if environment is None else environment
    api_key_env = str(decision_projection["api_key_env"])
    credential_present = bool(str(env.get(api_key_env) or "").strip())
    if decision.get("credential_presence_required") is True and not credential_present:
        raise ValueError(f"project_os_provider_credential_missing:{api_key_env}")

    repository = _repository_projection(root) if check_repository else {
        "head": "not_checked",
        "upstream": "not_checked",
        "clean": "not_checked",
        "synced": "not_checked",
    }
    return {
        "schema_version": CURRENT_PREFLIGHT_SCHEMA,
        "status": "pass_current_decision_bound_preflight",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "decision_ref": decision_ref,
        "decision_sha256": _sha256(decision_path),
        "run_scope_id": decision["run_scope_id"],
        "case_key": decision["case_key"],
        "cell_id": decision["cell_id"],
        "checks": {
            "project_os_documents_available_and_parseable": True,
            "immutable_clean_proof_and_failure_bindings_valid": True,
            "root_cause_scope_allowed": True,
            "token_and_call_budget_bounded": True,
            "provider_profile_and_recent_complete_capture_valid": True,
            "provider_credential_present_value_unread": credential_present,
            "real_evidence_mode": decision["evidence_mode"],
            "repository_clean_and_synced": repository["clean"] is True,
        },
        "decision_projection": decision_projection,
        "scope_projection": scope_projection,
        "repository": repository,
        "project_os_document_digests": project_os_digests,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "credential_value_persisted": False,
        "known_boundary": (
            (
                "This current-baseline preflight permits only the decision-bound "
                "DELL value_capture full three-fragment fixed-Pack Chat successor. "
                "It is not exact-live authority, dynamic Agentic Research, "
                "five-cell acceptance, publication, or release."
            )
            if decision_projection.get("full_fragment_judgment_successor") is True
            else (
                "This current-baseline preflight permits only the decision-bound DELL "
                "value_capture fixed-Pack micro-judgment Chat successor. It is not "
                "exact-live authority, natural submission proof, dynamic Agentic "
                "Research, five-cell acceptance, publication, or release."
                if decision_projection.get("micro_judgment_successor") is True
                else (
                    "This current-baseline preflight permits only the decision-bound "
                    "DELL value_capture fixed-Pack Chat replacement. It is not "
                    "exact-live authority, dynamic Agentic Research, five-cell "
                    "acceptance, publication, or release."
                )
            )
        ),
    }
