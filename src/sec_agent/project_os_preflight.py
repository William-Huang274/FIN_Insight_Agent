from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
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
FULL_FRAGMENT_CLAIM_LOCAL_BOUNDARY_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_claim_local_boundary_"
    "live_scope_decision_v1_3"
)
FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_causal_polarity_"
    "live_scope_decision_v1_4"
)
FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_wwc_route_identifier_"
    "live_scope_decision_v1_5"
)
FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_failed_fragment_submission_successor_"
    "live_scope_decision_v1_6"
)
FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_STATUS = (
    "failed_fragment_zero_call_pass_one_non_thinking_submission_"
    "successor_authorized"
)
FRAGMENT_VALIDATION_REPAIR_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_fragment_validation_repair_"
    "live_scope_decision_v1_8"
)
FRAGMENT_VALIDATION_REPAIR_DECISION_STATUS = (
    "zero_call_pass_one_validation_repair_authorized"
)
FRAGMENT_VALIDATION_REPAIR_SCOPE = (
    "one_fresh_same_fragment_repair_after_clean_gate"
)
DYNAMIC_SINGLE_CELL_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_live_scope_decision_v1_0"
)
DYNAMIC_SINGLE_CELL_DECISION_STATUS = (
    "approved_one_honest_DELL_SEC_only_dynamic_single_cell"
)
DYNAMIC_SINGLE_CELL_SCOPE = (
    "one_honest_DELL_SEC_only_dynamic_single_cell"
)
DYNAMIC_FIVE_CELL_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_exact_once"
)
DYNAMIC_FIVE_CELL_SCOPE = "one_DELL_dynamic_five_cell_exact_once"
DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_successor_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_remaining_twelve_nodes_exact_once"
)
DYNAMIC_FIVE_CELL_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_successor_remaining_twelve_nodes"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_partial_successor_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_failed_three_plus_synthesis_exact_once"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_partial_successor_failed_three_plus_synthesis"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_node_successor_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_two_submissions_plus_synthesis_exact_once"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_node_successor_two_submissions_plus_synthesis"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_claim_surface_successor_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_claim_surface_successor_exact_once"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_claim_surface_successor_exact_once"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_scope_decision_v1_1"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_exact_once"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_exact_once"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
    "successor_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_value_submission_"
    "repair_plus_synthesis_exact_once"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_value_submission_repair_plus_synthesis"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_0 = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
    "live_scope_decision_v1_0"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_0 = (
    "dynamic_R1_preserved_one_counter_analysis_submission_"
    "successor_authorized"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_1 = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
    "live_scope_decision_v1_1"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_1 = (
    "dynamic_R1_historical_binding_pass_one_counter_analysis_submission_"
    "successor_authorized"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
    "live_scope_decision_v1_2"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS = (
    "dynamic_R1_authority_contract_pass_one_counter_analysis_submission_"
    "successor_authorized"
)
DYNAMIC_COUNTER_SUCCESSOR_SCOPE = (
    "one_dynamic_counter_WWC_failed_node_successor_after_clean_zero_call_gate"
)
DYNAMIC_TEMPORAL_REPAIR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_temporal_fragment_repair_"
    "live_scope_decision_v1_0"
)
DYNAMIC_TEMPORAL_REPAIR_DECISION_STATUS = (
    "dynamic_temporal_authority_zero_call_pass_one_counter_repair_authorized"
)
DYNAMIC_TEMPORAL_REPAIR_SCOPE = (
    "one_DELL_dynamic_counter_temporal_fragment_repair_after_clean_zero_call_gate"
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


def _git_blob_sha256(*, root: Path, commit: str, ref: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", str(commit or "").lower()):
        raise ValueError("project_os_historical_commit_invalid")
    _repo_path(root, ref)
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError("project_os_historical_blob_missing")
    return hashlib.sha256(completed.stdout).hexdigest()


def _git_latest_commit_for_ref(*, root: Path, ref: str) -> str:
    _repo_path(root, ref)
    completed = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", ref],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    commit = completed.stdout.strip().lower()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("project_os_historical_ref_commit_missing")
    return commit


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
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_value_repair_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") in {
        DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_SCHEMA,
        DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_SCHEMA,
    }:
        return _validate_dynamic_five_cell_claim_surface_successor_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_node_successor_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_partial_successor_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == DYNAMIC_FIVE_CELL_DECISION_SCHEMA:
        return _validate_dynamic_five_cell_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == DYNAMIC_TEMPORAL_REPAIR_DECISION_SCHEMA:
        return _validate_dynamic_temporal_repair_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        in {
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_0,
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_1,
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA,
        }
    ):
        return _validate_dynamic_counter_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == DYNAMIC_SINGLE_CELL_DECISION_SCHEMA:
        return _validate_dynamic_single_cell_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == FRAGMENT_VALIDATION_REPAIR_DECISION_SCHEMA:
        return _validate_fragment_validation_repair_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_failed_fragment_submission_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") in {
        FULL_FRAGMENT_FIXED_PACK_DECISION_SCHEMA,
        FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA,
        FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA,
    }:
        return _validate_full_fragment_fixed_pack_decision(
            root=root, decision=decision
        )
    if decision.get("schema_version") in {
        FULL_FRAGMENT_CLAIM_LOCAL_BOUNDARY_DECISION_SCHEMA,
        FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_SCHEMA,
        FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA,
    }:
        return _validate_claim_local_boundary_fixed_pack_decision(
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


def _validate_dynamic_single_cell_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": DYNAMIC_SINGLE_CELL_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": DYNAMIC_SINGLE_CELL_SCOPE,
        "evidence_mode": "current_reviewed_pack_request_scoped_reselection",
        "next_authorized_scope": (
            "one_DELL_value_capture_dynamic_single_cell_chat_live"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_dynamic_decision_field_invalid:{field}"
            )

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "natural_planner_required",
        "current_S1_S2_execution_required",
        "candidate_promotion_forbidden",
        "transcript_prefeed_forbidden",
        "same_current_product_pointer_required",
        "immutable_zero_call_predecessor_required",
        "S1_RC_S1_019_remains_open",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_dynamic_decision_true_required:{field}"
            )
    for field in (
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "five_cell_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_dynamic_decision_false_required:{field}"
            )

    expected_budget = {
        "maximum_model_calls": 7,
        "maximum_transport_attempts": 7,
        "maximum_planner_calls": 1,
        "maximum_fragment_analysis_calls": 3,
        "maximum_fragment_submission_calls": 3,
        "maximum_evidence_requests": 8,
        "maximum_tool_calls": 3,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_dynamic_decision_budget_invalid")

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_result_ref",
        sha_field="zero_call_result_sha256",
        digest_field="zero_call_result_digest",
    )
    zero_acceptance = zero.get("stage_acceptance") or {}
    if not (
        zero.get("schema_version")
        == "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_2"
        and zero.get("status")
        == "zero_call_dynamic_truth_spine_engineering_pass"
        and zero_acceptance.get(
            "dynamic_dell_terminal_deliverable_compiled"
        )
        is True
        and zero_acceptance.get("natural_model_planner_executed") is False
        and zero_acceptance.get("natural_model_judgment_executed") is False
    ):
        raise ValueError("project_os_dynamic_zero_call_predecessor_invalid")

    profile_specs = (
        (
            "planner_profile_ref",
            "planner_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
            {"type": "json_object"},
        ),
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "high",
            8000,
            None,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
            None,
        ),
    )
    profiles: dict[str, dict[str, Any]] = {}
    for ref_field, sha_field, thinking, reasoning, tokens, response_format in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        common_valid = (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and "temperature" not in defaults
            and "top_p" not in defaults
        )
        reasoning_valid = (
            defaults.get("reasoning_effort") == reasoning
            if reasoning is not None
            else "reasoning_effort" not in defaults
        )
        response_format_valid = (
            defaults.get("response_format") == response_format
            if response_format is not None
            else "response_format" not in defaults
        )
        if not (common_valid and reasoning_valid and response_format_valid):
            raise ValueError(
                f"project_os_dynamic_provider_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    repair_submission = health.get("repair_submission") or {}
    if not (
        health.get("status")
        == (
            "completed_failed_fragment_validation_repair_contract_valid_"
            "content_assessment_pending"
        )
        and (health.get("execution") or {}).get("retries") == 0
        and repair_submission.get("attempted") is True
        and repair_submission.get("finish_reason") == "tool_calls"
        and repair_submission.get("tool_call_count") == 1
    ):
        raise ValueError("project_os_dynamic_provider_health_invalid")

    return {
        "clean_proof_status": zero["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_single_cell_successor": True,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "ALL_FIVE_RESEARCH_CELLS",
        "run_scope_id": DYNAMIC_FIVE_CELL_SCOPE,
        "evidence_mode": (
            "current_reviewed_pack_request_scoped_reselection_with_typed_gaps"
        ),
        "next_authorized_scope": "one_DELL_dynamic_five_cell_chat_exact_once",
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_decision_field_invalid:{field}"
            )
    if tuple(decision.get("required_cell_ids") or ()) != required_cells:
        raise ValueError("project_os_five_cell_required_cells_invalid")

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "natural_planner_required",
        "current_S1_S2_execution_required",
        "candidate_promotion_forbidden",
        "transcript_prefeed_forbidden",
        "same_current_product_pointer_required",
        "continue_after_cell_failure",
        "synthesis_requires_all_cells",
        "immutable_zero_call_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_decision_true_required:{field}"
            )
    for field in (
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_decision_false_required:{field}"
            )

    expected_budget = {
        "maximum_model_calls": 13,
        "maximum_transport_attempts": 13,
        "maximum_planner_calls": 1,
        "maximum_cell_analysis_calls": 5,
        "maximum_cell_submission_calls": 5,
        "maximum_synthesis_analysis_calls": 1,
        "maximum_synthesis_submission_calls": 1,
        "maximum_evidence_requests": 8,
        "maximum_tool_calls": 6,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_five_cell_decision_budget_invalid")

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="runner_zero_call_result_ref",
        sha_field="runner_zero_call_result_sha256",
        digest_field="runner_zero_call_result_digest",
    )
    proof_acceptance = proof.get("acceptance") or {}
    replay = proof.get("current_S1_S2_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_runner_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_stable_five_cell_runner"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 59
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("case_key") == "DELL"
        and replay.get("requested_evidence_count") == 8
        and replay.get("candidate_promotions") == 0
        and tuple(replay.get("research_context_cells") or ()) == required_cells
        and proof_acceptance.get("stale_objective_binding_fails_closed") is True
        and proof_acceptance.get("success_path_exact_thirteen_calls") is True
        and proof_acceptance.get("cell_failure_does_not_hide_later_cells")
        is True
        and proof_acceptance.get("synthesis_requires_all_five_cells") is True
        and proof_acceptance.get("public_result_redacts_model_content") is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError("project_os_five_cell_runner_proof_invalid")
    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "dynamic_runtime",
        "five_cell_runtime",
        "current_consumer",
        "runner_tests",
        "runtime_tests",
        "consumer_tests",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError("project_os_five_cell_runner_proof_bindings_invalid")
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_runner_proof_bindings_invalid"
            )
        path = _repo_path(root, str(row.get("ref") or ""))
        if _sha256(path) != str(row.get("sha256") or ""):
            raise ValueError(
                f"project_os_five_cell_runner_source_drift:{name}"
            )

    _, context = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="five_cell_context_result_ref",
        sha_field="five_cell_context_result_sha256",
        digest_field="five_cell_context_result_digest",
    )
    if not (
        context.get("status")
        == "engineering_pass_zero_call_current_consumer_contract_successor"
        and (context.get("acceptance") or {}).get(
            "all_five_cells_have_role_method_pack"
        )
        is True
        and (context.get("acceptance") or {}).get(
            "all_graph_context_compiled_from_current_case"
        )
        is True
        and (context.get("acceptance") or {}).get("natural_model_quality_proven")
        is False
    ):
        raise ValueError("project_os_five_cell_context_predecessor_invalid")

    _, single = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="dynamic_single_cell_assessment_ref",
        sha_field="dynamic_single_cell_assessment_sha256",
    )
    if not (
        single.get("status")
        == (
            "dynamic_single_cell_L1_and_applicable_content_pass_"
            "S1_sync_then_five_cell"
        )
        and (single.get("acceptance") or {}).get("dynamic_single_cell_L1") is True
        and (single.get("acceptance") or {}).get(
            "DELL_value_capture_dynamic_single_cell_accepted"
        )
        is True
        and (single.get("acceptance") or {}).get("five_cell_live_authorized")
        is False
    ):
        raise ValueError("project_os_five_cell_single_cell_predecessor_invalid")

    profile_specs = (
        (
            "planner_profile_ref",
            "planner_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
            {"type": "json_object"},
        ),
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "high",
            8000,
            None,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
            None,
        ),
    )
    profiles: dict[str, dict[str, Any]] = {}
    for (
        ref_field,
        sha_field,
        thinking,
        reasoning,
        tokens,
        response_format,
    ) in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and (
                defaults.get("response_format") == response_format
                if response_format is not None
                else "response_format" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_provider_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }

    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_five_cell_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "ALL_FIVE_RESEARCH_CELLS",
        "run_scope_id": DYNAMIC_FIVE_CELL_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_dynamic_R1_planner_current_S1_S2_prefix_no_new_evidence"
        ),
        "next_authorized_scope": (
            "one_DELL_dynamic_five_cell_remaining_twelve_nodes_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_successor_decision_field_invalid:{field}"
            )
    if tuple(decision.get("required_cell_ids") or ()) != required_cells:
        raise ValueError(
            "project_os_five_cell_successor_required_cells_invalid"
        )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "same_current_product_pointer_required",
        "continue_after_cell_failure",
        "synthesis_requires_all_cells",
        "immutable_R1_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_successor_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_successor_false_required:{field}"
            )
    expected_budget = {
        "maximum_model_calls": 12,
        "maximum_transport_attempts": 12,
        "maximum_planner_calls": 0,
        "reused_predecessor_planner_calls": 1,
        "maximum_cell_analysis_calls": 5,
        "maximum_cell_submission_calls": 5,
        "maximum_synthesis_analysis_calls": 1,
        "maximum_synthesis_submission_calls": 1,
        "maximum_evidence_requests": 0,
        "reused_predecessor_evidence_requests": 8,
        "maximum_tool_calls": 6,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_five_cell_successor_decision_budget_invalid"
        )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="successor_runner_zero_call_result_ref",
        sha_field="successor_runner_zero_call_result_sha256",
        digest_field="successor_runner_zero_call_result_digest",
    )
    proof_acceptance = proof.get("acceptance") or {}
    replay = proof.get("successor_fake_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_successor_runner_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_stable_successor_remaining_twelve_nodes"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 65
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 12
        and replay.get("planner_calls_attempted") == 0
        and replay.get("current_S1_S2_executions") == 0
        and replay.get("reused_predecessor_planner_calls") == 1
        and replay.get("reused_predecessor_current_S1_S2") is True
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_contract_valid") is True
        and proof_acceptance.get("R1_preserved") is True
        and proof_acceptance.get("only_remaining_twelve_nodes_authorized")
        is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError(
            "project_os_five_cell_successor_runner_proof_invalid"
        )
    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "project_os_preflight",
        "current_consumer",
        "consumer_policy",
        "runner_tests",
        "project_os_tests",
        "consumer_tests",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError(
            "project_os_five_cell_successor_proof_bindings_invalid"
        )
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_successor_proof_bindings_invalid"
            )
        path = _repo_path(root, str(row.get("ref") or ""))
        if _sha256(path) != str(row.get("sha256") or ""):
            raise ValueError(
                f"project_os_five_cell_successor_source_drift:{name}"
            )

    _, capacity = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="capacity_successor_result_ref",
        sha_field="capacity_successor_result_sha256",
        digest_field="capacity_successor_result_digest",
    )
    if not (
        capacity.get("status")
        == "engineering_pass_zero_call_R1_capacity_contract_successor"
        and (capacity.get("acceptance") or {}).get("R1_preserved") is True
        and (capacity.get("acceptance") or {}).get(
            "value_capture_five_metrics_two_periods_equal_ten"
        )
        is True
        and (capacity.get("acceptance") or {}).get(
            "successor_live_authorized"
        )
        is False
    ):
        raise ValueError(
            "project_os_five_cell_successor_capacity_proof_invalid"
        )

    _, predecessor_public = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_public_result_ref",
        sha_field="predecessor_public_result_sha256",
        digest_field="predecessor_public_result_digest",
    )
    _, predecessor_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_private_result_ref",
        sha_field="predecessor_private_result_sha256",
    )
    if not (
        predecessor_public.get("status")
        == "terminal_failed_or_partial_no_retry"
        and predecessor_private.get("status")
        == "terminal_failed_or_partial_no_retry"
        and (predecessor_private.get("orchestration_failure") or {}).get(
            "failure_code"
        )
        == "research_consumer_cell_capacity_exceeded"
        and (predecessor_private.get("execution") or {}).get(
            "model_calls_attempted"
        )
        == 1
        and (predecessor_private.get("execution") or {}).get(
            "cell_analysis_calls_attempted"
        )
        == 0
    ):
        raise ValueError(
            "project_os_five_cell_successor_R1_predecessor_invalid"
        )

    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "high",
            8000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    profiles: dict[str, dict[str, Any]] = {}
    for ref_field, sha_field, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_successor_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_partial_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    reused_cells = required_cells[:2]
    remaining_cells = required_cells[2:]
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "FAILED_THREE_PLUS_SYNTHESIS",
        "run_scope_id": DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_dynamic_R2_prefix_two_valid_cells_no_new_evidence"
        ),
        "next_authorized_scope": (
            "one_DELL_dynamic_five_cell_failed_three_plus_synthesis_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_partial_successor_field_invalid:{field}"
            )
    if not (
        tuple(decision.get("required_cell_ids") or ()) == required_cells
        and tuple(decision.get("reused_cell_ids") or ()) == reused_cells
        and tuple(decision.get("remaining_cell_ids") or ())
        == remaining_cells
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_cells_invalid"
        )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "reuse_predecessor_valid_cells",
        "same_current_product_pointer_required",
        "synthesis_requires_all_cells",
        "immutable_R2_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_partial_successor_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "rerun_valid_cells",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_partial_successor_false_required:{field}"
            )
    expected_budget = {
        "maximum_model_calls": 8,
        "maximum_transport_attempts": 8,
        "maximum_planner_calls": 0,
        "reused_predecessor_planner_calls": 1,
        "maximum_cell_analysis_calls": 3,
        "maximum_cell_submission_calls": 3,
        "reused_predecessor_cell_judgments": 2,
        "maximum_synthesis_analysis_calls": 1,
        "maximum_synthesis_submission_calls": 1,
        "maximum_evidence_requests": 0,
        "reused_predecessor_evidence_requests": 8,
        "maximum_tool_calls": 4,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_five_cell_partial_successor_budget_invalid"
        )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="partial_successor_zero_call_result_ref",
        sha_field="partial_successor_zero_call_result_sha256",
        digest_field="partial_successor_zero_call_result_digest",
    )
    acceptance = proof.get("acceptance") or {}
    replay = proof.get("partial_successor_fake_replay") or {}
    compact = proof.get("compact_analysis_projection") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_compact_analysis_partial_resume"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 70
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 8
        and replay.get("planner_calls_attempted") == 0
        and replay.get("current_S1_S2_executions") == 0
        and replay.get("reused_predecessor_cell_judgments") == 2
        and replay.get("cell_analysis_calls_attempted") == 3
        and replay.get("cell_submission_calls_attempted") == 3
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_contract_valid") is True
        and compact.get("cell_count") == 5
        and compact.get("all_authority_ref_sets_preserved") is True
        and compact.get("submission_schema_removed") is True
        and compact.get("dynamic_transport_diagnostics_removed") is True
        and min(compact.get("character_reduction_percent") or [0]) >= 15
        and acceptance.get("R2_preserved") is True
        and acceptance.get("two_valid_cells_reused_not_rerun") is True
        and acceptance.get("only_three_failed_cells_executed") is True
        and acceptance.get("compact_analysis_projection_lossless") is True
        and acceptance.get("fresh_model_calls_equal_eight") is True
        and acceptance.get("natural_model_quality_proven") is False
        and acceptance.get("partial_successor_live_authorized") is False
        and acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_proof_invalid"
        )
    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "five_cell_runtime",
        "project_os_preflight",
        "runner_tests",
        "runtime_tests",
        "project_os_tests",
        "consumer_policy",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError(
            "project_os_five_cell_partial_successor_bindings_invalid"
        )
    implementation_commit = str(proof.get("implementation_commit") or "")
    proof_commit = _git_latest_commit_for_ref(
        root=root,
        ref=str(decision.get("partial_successor_zero_call_result_ref") or ""),
    )
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_partial_successor_bindings_invalid"
            )
        ref = str(row.get("ref") or "")
        _repo_path(root, ref)
        expected_sha = str(row.get("sha256") or "")
        if not any(
            _git_blob_sha256(root=root, commit=commit, ref=ref) == expected_sha
            for commit in {implementation_commit, proof_commit}
        ):
            raise ValueError(
                f"project_os_five_cell_partial_successor_source_drift:{name}"
            )

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_result_ref",
        sha_field="predecessor_result_sha256",
        digest_field="predecessor_result_digest",
    )
    cells = predecessor.get("cells") or []
    if not (
        predecessor.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_successor_live_result_v1_0"
        and predecessor.get("status") == "terminal_failed_or_partial_no_retry"
        and (predecessor.get("execution") or {}).get(
            "cell_judgments_accepted"
        )
        == 2
        and len(cells) == 5
        and [row.get("cell_id") for row in cells] == list(required_cells)
        and all(cells[index].get("validated_cell_digest") for index in (0, 1))
        and all(not cells[index].get("failure_code") for index in (0, 1))
        and [cells[index].get("failure_code") for index in (2, 3, 4)]
        == [
            "model_gateway_reasoning_budget_exhausted",
            "five_cell_live_cell_analysis_length_stop",
            "model_gateway_reasoning_budget_exhausted",
        ]
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_predecessor_invalid"
        )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_failure_assessment_ref",
        sha_field="predecessor_failure_assessment_sha256",
    )
    if not (
        predecessor_assessment.get("status")
        == "terminal_partial_two_of_five_contract_valid_three_analysis_budget_exhausted"
        and predecessor_assessment.get("result_digest")
        == predecessor.get("result_digest")
        and tuple(
            (predecessor_assessment.get("successor_disposition") or {}).get(
                "remaining_cell_ids"
            )
            or ()
        )
        == remaining_cells
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_assessment_invalid"
        )

    profiles: dict[str, Any] = {}
    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    for ref_field, sha_field, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_partial_successor_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 3,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_node_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    reused_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::cash_conversion",
    )
    resubmission_cells = (
        "CELL::value_capture",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "TWO_SUBMISSIONS_PLUS_SYNTHESIS",
        "run_scope_id": DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_dynamic_R3_three_valid_cells_two_analysis_drafts_no_new_evidence"
        ),
        "next_authorized_scope": (
            "one_DELL_dynamic_five_cell_two_submissions_plus_synthesis_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_node_successor_field_invalid:{field}"
            )
    if not (
        tuple(decision.get("required_cell_ids") or ()) == required_cells
        and tuple(decision.get("reused_cell_ids") or ()) == reused_cells
        and tuple(decision.get("resubmission_cell_ids") or ())
        == resubmission_cells
    ):
        raise ValueError("project_os_five_cell_node_successor_cells_invalid")
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "reuse_predecessor_valid_cells",
        "reuse_predecessor_analysis_drafts",
        "same_current_product_pointer_required",
        "synthesis_requires_all_cells",
        "immutable_R3_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_node_successor_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "rerun_valid_cells",
        "rerun_cell_analysis",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_node_successor_false_required:{field}"
            )
    expected_budget = {
        "maximum_model_calls": 4,
        "maximum_transport_attempts": 4,
        "maximum_planner_calls": 0,
        "reused_predecessor_planner_calls": 1,
        "maximum_cell_analysis_calls": 0,
        "reused_predecessor_cell_analysis_drafts": 2,
        "maximum_cell_submission_calls": 2,
        "reused_predecessor_cell_judgments": 3,
        "maximum_synthesis_analysis_calls": 1,
        "maximum_synthesis_submission_calls": 1,
        "maximum_evidence_requests": 0,
        "reused_predecessor_evidence_requests": 8,
        "maximum_tool_calls": 3,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_five_cell_node_successor_budget_invalid")

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="node_successor_zero_call_result_ref",
        sha_field="node_successor_zero_call_result_sha256",
        digest_field="node_successor_zero_call_result_digest",
    )
    acceptance = proof.get("acceptance") or {}
    replay = proof.get("node_successor_fake_replay") or {}
    capture = proof.get("R3_capture_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_node_successor_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_R3_node_successor_strict_resubmission"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 100
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 4
        and replay.get("planner_calls_attempted") == 0
        and replay.get("current_S1_S2_executions") == 0
        and replay.get("reused_predecessor_cell_judgments") == 3
        and replay.get("reused_predecessor_analysis_drafts") == 2
        and replay.get("cell_analysis_calls_attempted") == 0
        and replay.get("cell_submission_calls_attempted") == 2
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_analysis_calls_attempted") == 1
        and replay.get("synthesis_submission_calls_attempted") == 1
        and replay.get("strict_projected_submission_tools") == 3
        and replay.get("synthesis_contract_valid") is True
        and capture.get("analysis_capture_count") == 2
        and capture.get("all_request_response_digests_match") is True
        and capture.get("all_response_bodies_complete") is True
        and capture.get("all_saved_analysis_content_matches") is True
        and acceptance.get("R3_preserved") is True
        and acceptance.get("three_valid_judgments_reused_not_rerun") is True
        and acceptance.get(
            "two_analysis_drafts_capture_verified_and_reused"
        )
        is True
        and acceptance.get("only_two_cell_submissions_executed") is True
        and acceptance.get(
            "strict_projection_applied_to_all_three_submission_tools"
        )
        is True
        and acceptance.get("fresh_model_calls_equal_four") is True
        and acceptance.get("synthesis_requires_all_five_cells") is True
        and acceptance.get("natural_model_quality_proven") is False
        and acceptance.get("node_successor_live_authorized") is False
        and acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError("project_os_five_cell_node_successor_proof_invalid")

    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "five_cell_runtime",
        "strict_projection",
        "project_os_preflight",
        "runner_tests",
        "runtime_tests",
        "projection_tests",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError("project_os_five_cell_node_successor_bindings_invalid")
    implementation_commit = str(proof.get("implementation_commit") or "")
    proof_commit = _git_latest_commit_for_ref(
        root=root,
        ref=str(decision.get("node_successor_zero_call_result_ref") or ""),
    )
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_node_successor_bindings_invalid"
            )
        ref = str(row.get("ref") or "")
        _repo_path(root, ref)
        expected_sha = str(row.get("sha256") or "")
        if not any(
            _git_blob_sha256(root=root, commit=commit, ref=ref) == expected_sha
            for commit in {implementation_commit, proof_commit}
        ):
            raise ValueError(
                f"project_os_five_cell_node_successor_source_drift:{name}"
            )

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_result_ref",
        sha_field="predecessor_result_sha256",
        digest_field="predecessor_result_digest",
    )
    cells = predecessor.get("cells") or []
    expected_valid = {0, 1, 3}
    if not (
        predecessor.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_live_result_v1_0"
        and predecessor.get("status") == "terminal_failed_or_partial_no_retry"
        and (predecessor.get("execution") or {}).get(
            "cell_judgments_accepted"
        )
        == 3
        and len(cells) == 5
        and [row.get("cell_id") for row in cells] == list(required_cells)
        and all(cells[index].get("validated_cell_digest") for index in expected_valid)
        and all(not cells[index].get("failure_code") for index in expected_valid)
        and cells[2].get("failure_code")
        == "research_consumer_mechanism_atom_invalid"
        and cells[4].get("failure_code")
        == "research_consumer_thesis_atom_invalid"
    ):
        raise ValueError(
            "project_os_five_cell_node_successor_predecessor_invalid"
        )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_failure_assessment_ref",
        sha_field="predecessor_failure_assessment_sha256",
    )
    if not (
        predecessor_assessment.get("status")
        == "terminal_partial_three_of_five_contract_valid_two_strict_submission_surface_rejected"
        and predecessor_assessment.get("result_digest")
        == predecessor.get("result_digest")
    ):
        raise ValueError(
            "project_os_five_cell_node_successor_assessment_invalid"
        )
    _, strict_canary = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="strict_canary_result_ref",
        sha_field="strict_canary_result_sha256",
        digest_field="strict_canary_result_digest",
    )
    if not (
        strict_canary.get("status")
        == "completed_deepseek_beta_strict_pattern_qualified"
        and (strict_canary.get("acceptance") or {}).get(
            "deepseek_beta_endpoint_accepted_schema"
        )
        is True
        and (strict_canary.get("execution") or {}).get("retries") == 0
    ):
        raise ValueError("project_os_five_cell_node_successor_canary_invalid")

    profiles: dict[str, Any] = {}
    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            "https://api.deepseek.com",
            {"type": "enabled"},
            "max",
            16000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            "https://api.deepseek.com/beta",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    for ref_field, sha_field, base_url, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == base_url
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_node_successor_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "base_url": base_url,
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": False,
        "dynamic_five_cell_node_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_claim_surface_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    cell_scoped_successor = (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_SCHEMA
    )
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": (
            DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_STATUS
            if cell_scoped_successor
            else DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "ALL_FIVE_RESEARCH_CELLS",
        "run_scope_id": (
            DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE
            if cell_scoped_successor
            else DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_SCOPE
        ),
        "evidence_mode": (
            (
                "immutable_R4_planner_and_current_S1_S2_with_reviewed_exact_"
                "claim_anchor_period_bound_historical_relation_and_cell_"
                "scoped_submission_contract"
            )
            if cell_scoped_successor
            else (
                "immutable_R4_planner_and_current_S1_S2_with_reviewed_exact_"
                "claim_anchor_and_period_bound_historical_relation"
            )
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_claim_surface_successor_field_invalid:{field}"
            )
    if tuple(decision.get("required_cell_ids") or ()) != required_cells:
        raise ValueError(
            "project_os_five_cell_claim_surface_successor_cells_invalid"
        )
    for field in (
        "reuse_predecessor_planner_and_controlled_plan",
        "rerun_all_five_analysis_and_submission_nodes",
        "same_current_product_pointer_required",
        "reviewed_exact_source_anchor_required",
        "historical_relation_is_period_bound_and_issuer_attributed",
        "historical_relation_is_not_current_quarter_causality",
        "continue_after_cell_failure",
        "synthesis_requires_all_cells",
        "chat_live_authorized",
        "credential_presence_required",
        *(
            (
                "cell_scoped_claim_contract_required",
                "typed_unexpected_exception_terminal_required",
                "failed_attempt_authority_consumed",
                "failed_attempt_reuse_forbidden",
            )
            if cell_scoped_successor
            else ()
        ),
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_true_required:"
                + field
            )
    for field in (
        "reuse_predecessor_cell_analysis_or_judgments",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_false_required:"
                + field
            )
    expected_budget = {
        "maximum_model_calls": 12,
        "maximum_transport_attempts": 12,
        "maximum_planner_calls": 0,
        "reused_predecessor_planner_calls": 1,
        "maximum_cell_analysis_calls": 5,
        "maximum_cell_submission_calls": 5,
        "maximum_synthesis_analysis_calls": 1,
        "maximum_synthesis_submission_calls": 1,
        "maximum_evidence_requests": 0,
        "reused_predecessor_evidence_requests": 8,
        "maximum_tool_calls": 6,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_five_cell_claim_surface_successor_budget_invalid"
        )
    if cell_scoped_successor:
        if decision.get("failed_attempt_run_id") != (
            "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R5"
        ):
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_failed_attempt_invalid"
            )
        _zero_path, zero_result = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="cell_scoped_zero_call_result_ref",
            sha_field="cell_scoped_zero_call_result_sha256",
            digest_field="cell_scoped_zero_call_result_digest",
        )
        _failed_path, failed_result = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="failed_attempt_result_ref",
            sha_field="failed_attempt_result_sha256",
            digest_field="failed_attempt_result_digest",
        )
        assessment_ref = str(
            decision.get("failed_attempt_failure_assessment_ref") or ""
        )
        assessment_path = _repo_path(root, assessment_ref)
        assessment = _load_json(assessment_path)
        if not (
            _sha256(assessment_path)
            == decision.get("failed_attempt_failure_assessment_sha256")
            and assessment.get("assessment_digest")
            == decision.get("failed_attempt_failure_assessment_digest")
            and zero_result.get("status")
            == (
                "formal_zero_call_engineering_pass_"
                "fresh_live_scope_decision_pending"
            )
            and (zero_result.get("contract_proof") or {}).get(
                "nonqualified_messages_omit_claim_contracts_and_relation_aliases"
            )
            is True
            and (zero_result.get("contract_proof") or {}).get(
                "unexpected_project_exception_materializes_terminal_result"
            )
            is True
            and failed_result.get("run_id")
            == "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R5"
            and failed_result.get("status")
            == "terminal_unexpected_project_exception_preserved_no_retry"
            and (assessment.get("disposition") or {}).get(
                "R5_authority_consumed"
            )
            is True
            and (assessment.get("disposition") or {}).get(
                "R5_rerun_forbidden"
            )
            is True
        ):
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_repair_artifact_invalid"
            )
    return {
        "clean_proof_status": "engineering_pass_scope_bound_zero_call_regression",
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 0,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": False,
        "dynamic_five_cell_node_successor": False,
        "dynamic_five_cell_claim_surface_successor": True,
        "dynamic_five_cell_cell_scoped_claim_contract_successor": (
            cell_scoped_successor
        ),
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": {},
    }


def _validate_dynamic_five_cell_value_repair_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    reused_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    resubmission_cells = ("CELL::value_capture",)
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "VALUE_SUBMISSION_REPAIR_PLUS_SYNTHESIS",
        "run_scope_id": DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_R6_four_valid_cells_value_analysis_and_current_S1_S2"
        ),
        "next_authorized_scope": (
            "one_DELL_value_submission_repair_plus_synthesis_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_value_repair_field_invalid:{field}"
            )
    if not (
        tuple(decision.get("required_cell_ids") or ()) == required_cells
        and tuple(decision.get("reused_cell_ids") or ()) == reused_cells
        and tuple(decision.get("resubmission_cell_ids") or ())
        == resubmission_cells
    ):
        raise ValueError("project_os_five_cell_value_repair_cells_invalid")
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "reuse_predecessor_valid_cells",
        "reuse_predecessor_value_analysis",
        "reuse_rejected_value_call_only_as_typed_feedback",
        "same_current_product_pointer_required",
        "synthesis_requires_all_cells",
        "immutable_R6_predecessor_required",
        "relation_endpoints_bind_locally",
        "structured_financial_support_is_valid_support_channel",
        "narrative_date_number_ref_gate_unchanged",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_value_repair_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "rerun_valid_cells",
        "rerun_cell_analysis",
        "harness_rewrites_model_judgment",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_value_repair_false_required:{field}"
            )
    expected_budget = {
        "maximum_model_calls": 3,
        "maximum_transport_attempts": 3,
        "maximum_planner_calls": 0,
        "reused_predecessor_planner_calls": 1,
        "maximum_cell_analysis_calls": 0,
        "reused_predecessor_cell_analysis_drafts": 1,
        "maximum_cell_submission_calls": 1,
        "reused_predecessor_cell_judgments": 4,
        "maximum_synthesis_analysis_calls": 1,
        "maximum_synthesis_submission_calls": 1,
        "maximum_evidence_requests": 0,
        "reused_predecessor_evidence_requests": 8,
        "maximum_tool_calls": 2,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_five_cell_value_repair_budget_invalid")

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="value_repair_zero_call_result_ref",
        sha_field="value_repair_zero_call_result_sha256",
        digest_field="value_repair_zero_call_result_digest",
    )
    _, failed_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_attempt_result_ref",
        sha_field="failed_attempt_result_sha256",
        digest_field="failed_attempt_result_digest",
    )
    assessment_ref = str(decision.get("failed_attempt_failure_assessment_ref") or "")
    assessment_path = _repo_path(root, assessment_ref)
    assessment = _load_json(assessment_path)
    acceptance = proof.get("acceptance") or {}
    replay = proof.get("successor_fake_replay") or {}
    capture = proof.get("R6_capture_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == (
            "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
            "successor_zero_call_result_v1_0"
        )
        and proof.get("status")
        == "engineering_pass_zero_call_R6_value_repair_plus_synthesis_successor"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 100
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 3
        and replay.get("reused_predecessor_cell_judgments") == 4
        and replay.get("reused_predecessor_analysis_drafts") == 1
        and replay.get("cell_submission_calls_attempted") == 1
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_analysis_calls_attempted") == 1
        and replay.get("synthesis_submission_calls_attempted") == 1
        and replay.get("synthesis_contract_valid") is True
        and capture.get("analysis_capture_count") == 1
        and capture.get("all_request_response_digests_match") is True
        and capture.get("all_response_bodies_complete") is True
        and capture.get("saved_analysis_content_matches") is True
        and capture.get("rejected_submission_digest_matches") is True
        and capture.get("rejected_submission_replays_to_typed_failure")
        == "research_consumer_thesis_atom_invalid"
        and acceptance.get("R6_preserved") is True
        and acceptance.get("four_valid_judgments_reused_not_rerun") is True
        and acceptance.get("value_analysis_capture_verified_and_reused") is True
        and acceptance.get("rejected_value_submission_not_promoted") is True
        and acceptance.get("relation_endpoints_bind_locally") is True
        and acceptance.get("structured_financial_support_recognized") is True
        and acceptance.get("only_one_typed_value_repair_submission") is True
        and acceptance.get("synthesis_requires_all_five_cells") is True
        and acceptance.get("natural_model_quality_proven") is False
        and acceptance.get("successor_live_authorized") is False
        and failed_result.get("status")
        == "terminal_failed_or_partial_no_retry"
        and failed_result.get("result_digest")
        == decision.get("failed_attempt_result_digest")
        and _sha256(assessment_path)
        == decision.get("failed_attempt_failure_assessment_sha256")
        and assessment.get("assessment_digest")
        == decision.get("failed_attempt_failure_assessment_digest")
        and assessment.get("run_id") == "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R6"
        and (assessment.get("disposition") or {}).get("R6_authority_consumed")
        is True
        and (assessment.get("disposition") or {}).get("R6_rerun_forbidden")
        is True
    ):
        raise ValueError("project_os_five_cell_value_repair_proof_invalid")
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 10,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": False,
        "dynamic_five_cell_node_successor": False,
        "dynamic_five_cell_claim_surface_successor": False,
        "dynamic_five_cell_cell_scoped_claim_contract_successor": False,
        "dynamic_five_cell_value_repair_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": {},
    }


def _validate_dynamic_counter_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    decision_schema = decision.get("schema_version")
    historical_binding = decision_schema in {
        DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_1,
        DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA,
    }
    authority_contract_v1_2 = (
        decision_schema == DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA
    )
    required_equal = {
        "status": (
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS
            if authority_contract_v1_2
            else (
                DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_1
                if historical_binding
                else DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_0
            )
        ),
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": DYNAMIC_COUNTER_SUCCESSOR_SCOPE,
        "evidence_mode": "immutable_dynamic_R1_prefix_no_new_evidence",
        "next_authorized_scope": (
            "one_DELL_dynamic_counter_WWC_analysis_submission_successor"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_dynamic_counter_decision_field_invalid:{field}"
            )

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "immutable_successful_prefix_reuse_required",
        "failed_node_only_required",
        "max_thinking_analysis_required",
        "non_thinking_submission_required",
        "predecessor_R1_remains_failed",
        "same_current_product_pointer_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_dynamic_counter_decision_true_required:{field}"
            )
    if historical_binding:
        for field in (
            "historical_git_blob_validation_required",
            "current_runtime_policies_directly_bound",
            "obsolete_v1_0_identity_reuse_forbidden",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_dynamic_counter_decision_true_required:"
                    f"{field}"
                )
    if authority_contract_v1_2:
        for field in (
            "real_authority_fixture_shape_required",
            "obsolete_v1_1_identity_reuse_forbidden",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_dynamic_counter_decision_true_required:"
                    f"{field}"
                )
    for field in (
        "planner_rerun_authorized",
        "current_S1_S2_rerun_authorized",
        "thesis_or_mechanism_rerun_authorized",
        "new_evidence_authorized",
        "candidate_promotion_authorized",
        "contract_relaxation_authorized",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "automatic_second_analysis_retry_authorized",
        "five_cell_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_dynamic_counter_decision_false_required:{field}"
            )

    expected_budget = {
        "successful_predecessor_model_nodes_reused": 5,
        "maximum_fresh_model_calls": 2,
        "maximum_transport_attempts": 2,
        "maximum_counter_analysis_calls": 1,
        "maximum_counter_submission_calls": 1,
        "maximum_analysis_completion_tokens": 16000,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_dynamic_counter_decision_budget_invalid")

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_result_ref",
        sha_field="zero_call_result_sha256",
        digest_field="zero_call_result_digest",
    )
    zero_acceptance = zero.get("acceptance") or {}
    replay = zero.get("replay_observation") or {}
    expected_zero_schema = (
        "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
        "zero_call_result_"
        + (
            "v1_2"
            if authority_contract_v1_2
            else ("v1_1" if historical_binding else "v1_0")
        )
    )
    expected_zero_status = (
        "zero_call_failed_counter_successor_authority_contract_engineering_pass"
        if authority_contract_v1_2
        else (
            "zero_call_failed_counter_successor_historical_binding_"
            "engineering_pass"
            if historical_binding
            else "zero_call_failed_counter_successor_engineering_pass"
        )
    )
    if not (
        zero.get("schema_version") == expected_zero_schema
        and zero.get("status") == expected_zero_status
        and zero_acceptance.get("immutable_successful_prefix_reused") is True
        and zero_acceptance.get("failed_counter_context_recompiled_exactly")
        is True
        and zero_acceptance.get("failed_counter_messages_recompiled_exactly")
        is True
        and zero_acceptance.get("new_evidence_or_candidate_promotion") is False
        and zero_acceptance.get("natural_successor_executed") is False
        and replay.get("successful_predecessor_model_nodes_reused") == 5
        and replay.get("failed_analysis_step_absent") is True
        and replay.get("failed_submission_step_absent") is True
        and replay.get("failed_validated_fragment_absent") is True
        and all(
            value == 0 for value in (zero.get("observed_calls") or {}).values()
        )
    ):
        raise ValueError("project_os_dynamic_counter_zero_call_invalid")
    if historical_binding and not (
        zero_acceptance.get(
            "historical_authority_validated_from_immutable_git_commit"
        )
        is True
        and zero_acceptance.get("current_runtime_policies_directly_bound")
        is True
        and (
            zero_acceptance.get("obsolete_v1_0_identity_reuse_forbidden")
            is True
            if not authority_contract_v1_2
            else zero_acceptance.get(
                "obsolete_v1_0_and_v1_1_identity_reuse_forbidden"
            )
            is True
        )
    ):
        raise ValueError(
            "project_os_dynamic_counter_historical_acceptance_invalid"
        )
    if authority_contract_v1_2 and zero_acceptance.get(
        "real_authority_fixture_shape_validated"
    ) is not True:
        raise ValueError(
            "project_os_dynamic_counter_authority_contract_acceptance_invalid"
        )

    _, predecessor_public = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_public_result_ref",
        sha_field="predecessor_public_result_sha256",
        digest_field="predecessor_public_result_digest",
    )
    predecessor_execution = predecessor_public.get("execution") or {}
    if not (
        predecessor_public.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_result_v1_0"
        and predecessor_public.get("status") == "terminal_failed_no_retry"
        and predecessor_public.get("failure_code")
        == "model_gateway_generation_budget_exhausted"
        and predecessor_public.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and predecessor_execution.get("model_calls_attempted") == 6
        and predecessor_execution.get("fragment_tool_calls_accepted") == 2
    ):
        raise ValueError("project_os_dynamic_counter_predecessor_public_invalid")

    _, predecessor_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_private_result_ref",
        sha_field="predecessor_private_result_sha256",
    )
    failed_rows = [
        row
        for row in predecessor_private.get("fragment_steps") or ()
        if row.get("fragment_tool")
        == "submit_research_counterargument_and_wwc"
    ]
    if not (
        predecessor_private.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_full_v1_0"
        and predecessor_private.get("status") == "terminal_failed_no_retry"
        and predecessor_private.get("full_result_digest")
        == decision.get("predecessor_private_result_digest")
        and set(predecessor_private.get("accepted_fragments") or {})
        == {"submit_research_thesis", "submit_research_mechanism"}
        and len(failed_rows) == 1
        and not failed_rows[0].get("analysis_step")
        and not failed_rows[0].get("submission_step")
        and not failed_rows[0].get("validated_fragment")
    ):
        raise ValueError("project_os_dynamic_counter_predecessor_private_invalid")

    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failure_assessment_ref",
        sha_field="failure_assessment_sha256",
    )
    disposition = assessment.get("successor_disposition") or {}
    if not (
        assessment.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_failure_assessment_v1_0"
        and assessment.get("status")
        == "terminal_failed_counter_WWC_analysis_generation_budget_exhausted"
        and disposition.get("preserve_R1") is True
        and disposition.get("maximum_fresh_model_calls") == 2
        and disposition.get("rerun_natural_planner") is False
        and disposition.get("rerun_current_S1_S2") is False
        and disposition.get("rerun_thesis_or_mechanism") is False
        and disposition.get("retry_count") == 0
        and disposition.get("new_evidence_or_authority") is False
        and disposition.get("contract_relaxation") is False
    ):
        raise ValueError("project_os_dynamic_counter_assessment_invalid")

    runner_path = _repo_path(root, str(decision.get("runner_ref") or ""))
    runner_digest = (
        _git_blob_sha256(
            root=root,
            commit=str(decision.get("implementation_commit") or ""),
            ref=str(decision.get("runner_ref") or ""),
        )
        if authority_contract_v1_2
        else _sha256(runner_path)
    )
    if runner_digest != str(decision.get("runner_sha256") or ""):
        raise ValueError("project_os_dynamic_counter_runner_drift")

    if historical_binding:
        _, obsolete_authority = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="obsolete_entry_authority_ref",
            sha_field="obsolete_entry_authority_sha256",
        )
        _, obsolete_failure = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="obsolete_entry_failure_ref",
            sha_field="obsolete_entry_failure_sha256",
        )
        _, predecessor_authority = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="predecessor_authority_ref",
            sha_field="predecessor_authority_sha256",
        )
        if not (
            obsolete_authority.get("schema_version")
            == (
                "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
                "authority_v1_0"
            )
            and obsolete_failure.get("status")
            == "entry_failed_zero_model_calls_historical_runner_current_path_drift"
            and sum((obsolete_failure.get("observed_calls") or {}).values()) == 0
            and predecessor_authority.get("schema_version")
            == "fin_ia_s3_dynamic_single_cell_live_authority_v1_0"
            and predecessor_authority.get("implementation_commit")
            == "ba02a24b3d01bdb70898e8ca09e442c50a09562f"
        ):
            raise ValueError(
                "project_os_dynamic_counter_historical_binding_invalid"
            )
        if authority_contract_v1_2:
            _, obsolete_authority_v1_1 = _validate_artifact_binding(
                root=root,
                decision=decision,
                ref_field="obsolete_entry_authority_v1_1_ref",
                sha_field="obsolete_entry_authority_v1_1_sha256",
            )
            _, obsolete_failure_v1_1 = _validate_artifact_binding(
                root=root,
                decision=decision,
                ref_field="obsolete_entry_failure_v1_1_ref",
                sha_field="obsolete_entry_failure_v1_1_sha256",
            )
            if not (
                obsolete_authority_v1_1.get("schema_version")
                == (
                    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
                    "authority_v1_1"
                )
                and obsolete_failure_v1_1.get("status")
                == "entry_failed_zero_model_calls_current_policy_required_set_omission"
                and sum(
                    (obsolete_failure_v1_1.get("observed_calls") or {}).values()
                )
                == 0
            ):
                raise ValueError(
                    "project_os_dynamic_counter_authority_contract_history_invalid"
                )
        for ref_field, sha_field in (
            ("loop_policy_ref", "loop_policy_sha256"),
            ("dynamic_micro_policy_ref", "dynamic_micro_policy_sha256"),
        ):
            _validate_artifact_binding(
                root=root,
                decision=decision,
                ref_field=ref_field,
                sha_field=sha_field,
            )

    profiles: dict[str, dict[str, Any]] = {}
    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    for ref_field, sha_field, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "response_format" not in defaults
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_dynamic_counter_provider_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    repair_submission = health.get("repair_submission") or {}
    if not (
        health.get("status")
        == (
            "completed_failed_fragment_validation_repair_contract_valid_"
            "content_assessment_pending"
        )
        and (health.get("execution") or {}).get("retries") == 0
        and repair_submission.get("attempted") is True
        and repair_submission.get("finish_reason") == "tool_calls"
        and repair_submission.get("tool_call_count") == 1
    ):
        raise ValueError("project_os_dynamic_counter_provider_health_invalid")

    return {
        "clean_proof_status": zero["status"],
        "predecessor_status": predecessor_public["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_counter_successor": True,
        "historical_binding_version": (
            "v1_2"
            if authority_contract_v1_2
            else ("v1_1_obsolete" if historical_binding else "v1_0_obsolete")
        ),
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_temporal_repair_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "schema_version": DYNAMIC_TEMPORAL_REPAIR_DECISION_SCHEMA,
        "status": DYNAMIC_TEMPORAL_REPAIR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": DYNAMIC_TEMPORAL_REPAIR_SCOPE,
        "evidence_mode": "immutable_dynamic_R3_same_evidence_no_new_evidence",
        "next_authorized_scope": (
            "one_non_thinking_counter_temporal_repair_submission"
        ),
        "terminal_failure_code": (
            "finance_loop_micro_temporal_relation_unbound"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_dynamic_temporal_repair_field_invalid:{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "temporal_authority_required",
        "immutable_successful_nodes_reuse_required",
        "rejected_fragment_preserved_as_failure_evidence",
        "same_current_product_pointer_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_dynamic_temporal_repair_true_required:"
                f"{field}"
            )
    for field in (
        "planner_rerun_authorized",
        "current_S1_S2_rerun_authorized",
        "thesis_or_mechanism_rerun_authorized",
        "counter_analysis_rerun_authorized",
        "new_evidence_authorized",
        "candidate_promotion_authorized",
        "contract_relaxation_authorized",
        "automatic_second_repair_authorized",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "five_cell_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_dynamic_temporal_repair_false_required:"
                f"{field}"
            )
    expected_budget = {
        "successful_predecessor_model_nodes_reused": 6,
        "rejected_predecessor_submission_reused_as_business_truth": False,
        "maximum_fresh_model_calls": 1,
        "maximum_transport_attempts": 1,
        "maximum_counter_repair_submission_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_dynamic_temporal_repair_budget_invalid"
        )

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_result_ref",
        sha_field="zero_call_result_sha256",
        digest_field="zero_call_result_digest",
    )
    if not (
        zero.get("schema_version")
        == "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_3"
        and zero.get("status")
        == "zero_call_dynamic_truth_spine_engineering_pass"
        and (zero.get("stage_acceptance") or {}).get(
            "unbound_cross_item_temporal_relation_fails_closed"
        )
        is True
        and (zero.get("observed_counts") or {}).get("model_calls") == 0
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_zero_call_invalid"
        )

    _, predecessor_public = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_public_result_ref",
        sha_field="predecessor_public_result_sha256",
        digest_field="predecessor_public_result_digest",
    )
    _, predecessor_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_private_result_ref",
        sha_field="predecessor_private_result_sha256",
    )
    _, base_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="base_predecessor_private_result_ref",
        sha_field="base_predecessor_private_result_sha256",
    )
    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="content_assessment_ref",
        sha_field="content_assessment_sha256",
    )
    if not (
        predecessor_public.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_failed_counter_successor_result_v1_1"
        and predecessor_public.get("status")
        == "completed_dynamic_counter_successor_contract_valid_content_assessment_pending"
        and predecessor_private.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_failed_counter_successor_full_v1_1"
        and predecessor_private.get("status")
        == "completed_dynamic_counter_successor_contract_valid_content_assessment_pending"
        and predecessor_private.get("full_result_digest")
        == decision.get("predecessor_private_result_digest")
        and base_private.get("full_result_digest")
        == decision.get("base_predecessor_private_result_digest")
        and predecessor_private.get("predecessor_private_result_digest")
        == base_private.get("full_result_digest")
        and assessment.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_failed_counter_successor_content_assessment_v1_0"
        and assessment.get("status")
        == "dynamic_single_cell_contract_pass_L1_fail_temporal_relation_overreach_repair_required"
        and (assessment.get("root_cause") or {}).get("issue_id")
        == "RC-S3-028-dynamic-narrative-temporal-relation-unbound"
        and (assessment.get("disposition") or {}).get(
            "maximum_future_model_calls_after_zero_call_proof"
        )
        == 1
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_predecessor_invalid"
        )

    for ref_field, sha_field in (
        ("runner_ref", "runner_sha256"),
        ("bounded_loop_ref", "bounded_loop_sha256"),
    ):
        if _sha256(_repo_path(root, str(decision.get(ref_field) or ""))) != str(
            decision.get(sha_field) or ""
        ):
            raise ValueError(
                f"project_os_dynamic_temporal_repair_runtime_drift:{ref_field}"
            )
    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    defaults = profile.get("request_defaults") or {}
    if not (
        profile.get("provider_id") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("base_url") == "https://api.deepseek.com"
        and profile.get("endpoint") == "/chat/completions"
        and defaults.get("stream") is False
        and defaults.get("thinking") == {"type": "disabled"}
        and defaults.get("max_tokens") == 2000
        and "reasoning_effort" not in defaults
        and (profile.get("authority") or {}).get("retry_count") == 0
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_profile_invalid"
        )
    predecessor_submission = predecessor_public.get("submission") or {}
    if not (
        predecessor_submission.get("finish_reason") == "tool_calls"
        and (predecessor_public.get("execution") or {}).get("retries") == 0
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_provider_health_invalid"
        )
    return {
        "clean_proof_status": zero["status"],
        "predecessor_status": predecessor_public["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_temporal_repair_successor": True,
        "dynamic_counter_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": {
            "submission_profile_ref": {
                "thinking": {"type": "disabled"},
                "reasoning_effort": None,
                "max_tokens": 2000,
            }
        },
    }


def _validate_failed_fragment_submission_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": "submit_research_counterargument_and_wwc",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_R6_failed_counter_submission_"
            "successor"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_submission_successor_decision_field_invalid:"
                f"{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "immutable_successful_prefix_reused",
        "immutable_counter_analysis_reused",
        "failed_node_only_execution_required",
        "non_thinking_submission_required",
        "reasoning_effort_omitted_required",
        "terminal_contract_parity_required",
        "clock_derived_authority_timestamp_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_submission_successor_decision_true_required:"
                f"{field}"
            )
    for field in (
        "historical_failure_promoted",
        "successful_predecessor_nodes_rerun",
        "analysis_node_rerun",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "heterogeneous_generalization_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_submission_successor_decision_false_required:"
                f"{field}"
            )
    numeric_equal = {
        "successful_predecessor_model_calls_reused": 5,
        "maximum_fresh_model_calls": 1,
        "maximum_provider_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_submission_successor_budget_invalid:"
                f"{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    replay = (clean.get("normalized_proof") or {}).get(
        "saved_r6_non_thinking_submission_successor_replay"
    ) or {}
    if not (
        clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and (clean.get("acceptance") or {}).get(
            "saved_r6_submission_successor_replay_pass"
        )
        is True
        and replay.get("predecessor_failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and replay.get("successful_predecessor_model_calls_reused") == 5
        and replay.get("fresh_model_calls_in_successor") == 1
        and replay.get("reasoning_effort_omitted") is True
        and replay.get("fake_only_not_business_promotion") is True
        and replay.get("harness_generated_research_judgment") is False
    ):
        raise ValueError("project_os_submission_successor_clean_proof_invalid")

    _, failed = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_failed_result_ref",
        sha_field="immutable_failed_result_sha256",
        digest_field="immutable_failed_result_digest",
    )
    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_result_assessment_ref",
        sha_field="failed_result_assessment_sha256",
    )
    if not (
        failed.get("status") == "terminal_failed_no_retry"
        and failed.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and failed.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (failed.get("execution") or {}).get("model_calls_attempted") == 6
        and (failed.get("execution") or {}).get("tool_calls_accepted") == 2
        and (failed.get("execution") or {}).get("retries") == 0
        and (assessment.get("root_cause") or {}).get("owner_layer")
        == "S3_replaceable_DeepSeek_contract_submission_profile"
    ):
        raise ValueError("project_os_submission_successor_failed_R6_invalid")

    _, fixture = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_successor_fixture_ref",
        sha_field="submission_successor_fixture_sha256",
    )
    if not (
        fixture.get("source_result_sha256")
        == decision.get("immutable_failed_result_sha256")
        and fixture.get("source_result_digest")
        == decision.get("immutable_failed_result_digest")
        and fixture.get("failed_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and set(fixture.get("accepted_fragments") or {})
        == {"submit_research_thesis", "submit_research_mechanism"}
        and bool(str(fixture.get("counter_analysis_content") or ""))
        and fixture.get("private_reasoning_persisted") is False
        and fixture.get("manual_fragment_or_tool_payload_constructed") is False
    ):
        raise ValueError("project_os_submission_successor_fixture_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    defaults = profile.get("request_defaults") or {}
    if not (
        profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("provider_id") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and (profile.get("authority") or {}).get("retry_count") == 0
        and defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        and "reasoning_effort" not in defaults
    ):
        raise ValueError("project_os_submission_successor_profile_invalid")
    return {
        "clean_proof_status": clean["status"],
        "prior_failed_full_fragment_status": failed["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": 6,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": False,
        "failed_fragment_submission_successor": True,
        "successful_predecessor_model_calls_reused": 5,
        "fresh_model_calls_authorized": 1,
        "node_profiles": {
            "contract_submission": {
                "thinking": "disabled",
                "reasoning_effort": "omitted",
                "max_tokens": defaults["max_tokens"],
            }
        },
    }


def _validate_fragment_validation_repair_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": FRAGMENT_VALIDATION_REPAIR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": "submit_research_counterargument_and_wwc",
        "terminal_failure_code": "claim_surface_narrative_relation_conflict",
        "run_scope_id": FRAGMENT_VALIDATION_REPAIR_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_R7_failed_counter_validation_repair"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_validation_repair_decision_field_invalid:"
                f"{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "immutable_successful_prefix_reused",
        "rejected_fragment_preserved",
        "failed_node_only_execution_required",
        "typed_validation_feedback_required",
        "non_thinking_submission_required",
        "terminal_contract_parity_required",
        "clock_derived_authority_timestamp_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_validation_repair_decision_true_required:"
                f"{field}"
            )
    for field in (
        "historical_failure_promoted",
        "successful_predecessor_nodes_rerun",
        "analysis_node_rerun",
        "causal_guard_relaxation",
        "manual_text_rewrite",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "heterogeneous_generalization_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_validation_repair_decision_false_required:"
                f"{field}"
            )
    numeric_equal = {
        "successful_predecessor_model_calls_reused": 6,
        "maximum_fresh_model_calls": 1,
        "maximum_provider_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_repair_turns": 1,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_validation_repair_budget_invalid:"
                f"{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    replay = (clean.get("normalized_proof") or {}).get(
        "saved_r7_validation_repair_successor_replay"
    ) or {}
    if not (
        clean.get("status") == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and (clean.get("acceptance") or {}).get(
            "saved_r7_validation_repair_successor_replay_pass"
        )
        is True
        and replay.get("predecessor_failure_code")
        == "claim_surface_narrative_relation_conflict"
        and replay.get("successful_predecessor_model_calls_reused") == 6
        and replay.get("fresh_model_calls_in_repair_successor") == 1
        and replay.get("maximum_repair_turns") == 1
        and replay.get("typed_tool_feedback_sequence") is True
        and replay.get("local_causal_guard_preserved") is True
        and replay.get("rejected_fragment_promoted_to_business_truth") is False
        and replay.get("harness_generated_research_judgment") is False
    ):
        raise ValueError("project_os_validation_repair_clean_proof_invalid")

    _, failed = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_failed_result_ref",
        sha_field="immutable_failed_result_sha256",
        digest_field="immutable_failed_result_digest",
    )
    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_result_assessment_ref",
        sha_field="failed_result_assessment_sha256",
    )
    if not (
        failed.get("status") == "terminal_failed_no_retry"
        and failed.get("failure_code")
        == "claim_surface_narrative_relation_conflict"
        and failed.get("failed_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (failed.get("execution") or {}).get("fresh_model_calls_attempted") == 1
        and (failed.get("execution") or {}).get(
            "successful_predecessor_model_calls_reused"
        )
        == 5
        and (failed.get("execution") or {}).get("retries") == 0
        and (assessment.get("root_cause") or {}).get("financial_L1_observed")
        is True
        and (assessment.get("root_cause") or {}).get(
            "local_validator_false_positive"
        )
        is False
    ):
        raise ValueError("project_os_validation_repair_failed_R7_invalid")

    _, fixture = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="rejected_fragment_fixture_ref",
        sha_field="rejected_fragment_fixture_sha256",
    )
    if not (
        fixture.get("source_result_sha256")
        == decision.get("immutable_failed_result_sha256")
        and fixture.get("source_result_digest")
        == decision.get("immutable_failed_result_digest")
        and fixture.get("fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and fixture.get("rejected_fragment_digest")
        == replay.get("rejected_fragment_digest")
    ):
        raise ValueError("project_os_validation_repair_fixture_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    defaults = profile.get("request_defaults") or {}
    if not (
        profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("provider_id") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and (profile.get("authority") or {}).get("retry_count") == 0
        and defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        and "reasoning_effort" not in defaults
    ):
        raise ValueError("project_os_validation_repair_profile_invalid")
    return {
        "clean_proof_status": clean["status"],
        "prior_failed_full_fragment_status": failed["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": 1,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": False,
        "failed_fragment_submission_successor": False,
        "fragment_validation_repair_successor": True,
        "successful_predecessor_model_calls_reused": 6,
        "fresh_model_calls_authorized": 1,
        "maximum_repair_turns": 1,
        "node_profiles": {
            "contract_submission_repair": {
                "thinking": "disabled",
                "reasoning_effort": "omitted",
                "max_tokens": defaults["max_tokens"],
            }
        },
    }


def _validate_claim_local_boundary_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    route_identifier_successor = (
        decision.get("schema_version")
        == FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA
    )
    causal_polarity_successor = decision.get("schema_version") in {
        FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_SCHEMA,
        FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA,
    }
    required_equal = {
        "status": FULL_FRAGMENT_FIXED_PACK_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_DELL_value_capture_full_three_"
            "fragment_analysis_submission_Chat_"
            + (
                "R6"
                if route_identifier_successor
                else ("R5" if causal_polarity_successor else "R4")
            )
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_claim_local_decision_field_invalid:"
                f"{field}"
            )
    true_fields = [
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "terminal_contract_parity_required",
        "fragment_surface_contract_parity_required",
        "claim_local_evidence_roles_required",
        "deterministic_report_evidence_summary_required",
        "global_support_laundering_forbidden",
        "typed_bridge_gap_boundary_required",
        "typed_same_scope_counter_boundary_required",
        "clock_derived_authority_timestamp_required",
    ]
    true_fields.extend(
        (
            "saved_R3_regression_replay_required",
            "saved_R4_causal_polarity_replay_required",
            "clause_scoped_causal_guard_required",
            "negated_or_unsupported_causal_surface_allowed",
            "ambiguous_single_character_cjk_term_forbidden",
            "positive_cross_scope_causal_surface_fail_closed",
        )
        if causal_polarity_successor
        else ("saved_R3_replay_required",)
    )
    if route_identifier_successor:
        true_fields.extend(
            (
                "saved_R5_route_identifier_replay_required",
                "registered_document_identifier_only_in_wwc_route_required",
                "unregistered_or_financial_numeric_surface_fail_closed",
                "document_identifier_in_narrative_fail_closed",
            )
        )
    for field in true_fields:
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_claim_local_decision_true_required:"
                f"{field}"
            )
    for field in (
        "historical_failure_promoted",
        "immutable_thesis_predecessor_reused",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "heterogeneous_generalization_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_claim_local_decision_false_required:"
                f"{field}"
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
                "project_os_claim_local_decision_budget_invalid:"
                f"{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    normalized_proof = clean.get("normalized_proof") or {}
    replay = normalized_proof.get(
        "saved_r3_claim_local_boundary_replay"
    ) or {}
    r4_replay = normalized_proof.get("saved_r4_causal_polarity_replay") or {}
    r5_replay = normalized_proof.get(
        "saved_r5_wwc_route_identifier_replay"
    ) or {}
    clean_acceptance = clean.get("acceptance") or {}
    common_clean_valid = (
        clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and clean_acceptance.get("saved_r3_terminal_replay_pass") is True
        and clean_acceptance.get("natural_model_submission_proven") is False
        and replay.get("claim_local_roles_preserved") is True
        and replay.get("report_level_summary_deterministic") is True
        and set(replay.get("boundary_authority_sources") or ())
        == {
            "typed_bridge_gap_relation",
            "typed_same_scope_counter_relation",
        }
        and (replay.get("mutation_failure_codes") or {}).get(
            "global_support_laundering"
        )
        == "claim_surface_required_authority_missing"
        and (replay.get("mutation_failure_codes") or {}).get(
            "typed_boundary_removed"
        )
        == "claim_authority_multi_driver_boundary_missing"
    )
    causal_clean_valid = (
        r4_replay.get("predecessor_failure_code")
        == "claim_surface_narrative_relation_conflict"
        and r4_replay.get("judgment_status") == "bounded_support"
        and r4_replay.get("inference_authority") == "bounded_inference"
        and r4_replay.get("claim_scope") == "multi_scope"
        and r4_replay.get("financial_scope") == "multi_scope_financial"
        and r4_replay.get("causal_bridge_authority")
        == "multi_driver_context_only"
        and r4_replay.get("clause_scoped_guard") is True
        and r4_replay.get("negated_or_unsupported_causal_surface_pass")
        is True
        and r4_replay.get(
            "single_character_cjk_substring_not_authoritative"
        )
        is True
        and r4_replay.get("positive_cross_scope_causal_surface_fail_closed")
        is True
        and set(r4_replay.get("boundary_authority_sources") or ())
        == {
            "typed_bridge_gap_relation",
            "typed_same_scope_counter_relation",
        }
        and r4_replay.get("model_narratives_preserved_exactly") is True
        and r4_replay.get("harness_generated_research_judgment") is False
        and (r4_replay.get("mutation_failure_codes") or {}).get(
            "positive_cross_scope_causal_zh"
        )
        == "claim_surface_narrative_relation_conflict"
        and (r4_replay.get("mutation_failure_codes") or {}).get(
            "positive_cross_scope_causal_en"
        )
        == "claim_surface_narrative_relation_conflict"
    )
    route_identifier_clean_valid = (
        not route_identifier_successor
        or (
            clean_acceptance.get("saved_r5_terminal_replay_pass") is True
            and r5_replay.get("predecessor_failure_code")
            == "research_consumer_wwc_evidence_route_invalid"
            and r5_replay.get("qualified_document_identifier") == "10-Q"
            and r5_replay.get("qualified_route_preserved_exactly") is True
            and r5_replay.get("field_scoped_numeric_surface_guard") is True
            and r5_replay.get("unregistered_numeric_surface_fail_closed")
            is True
            and r5_replay.get("model_narratives_preserved_exactly") is True
            and r5_replay.get("harness_generated_research_judgment") is False
            and set((r5_replay.get("mutation_failure_codes") or {}))
            == {
                "percentage_after_qualified_identifier",
                "year_after_qualified_identifier",
                "unknown_digit_identifier",
                "url_with_qualified_identifier",
                "document_identifier_in_narrative",
            }
        )
    )
    if not (
        common_clean_valid
        and (not causal_polarity_successor or causal_clean_valid)
        and route_identifier_clean_valid
    ):
        raise ValueError("project_os_claim_local_clean_proof_invalid")

    _, disposition = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="scope_disposition_ref",
        sha_field="scope_disposition_sha256",
    )
    if not (
        disposition.get("status")
        == (
            "approved_fresh_full_three_fragment_analysis_submission_Chat_"
            + (
                "R6"
                if route_identifier_successor
                else ("R5" if causal_polarity_successor else "R4")
            )
        )
        and disposition.get("decision_digest")
        == decision.get("scope_disposition_decision_digest")
        and (disposition.get("execution_budget") or {}).get(
            "maximum_model_calls"
        )
        == 6
        and disposition.get("claim_local_evidence_roles_required") is True
        and disposition.get("typed_bridge_gap_boundary_required") is True
        and disposition.get("typed_same_scope_counter_boundary_required")
        is True
        and disposition.get("prior_failed_attempt_reused") is False
        and disposition.get("dynamic_agentic_research_authorized") is False
        and (
            not causal_polarity_successor
            or (
                disposition.get("clause_scoped_causal_guard_required")
                is True
                and disposition.get(
                    "negated_or_unsupported_causal_surface_allowed"
                )
                is True
                and disposition.get(
                    "ambiguous_single_character_cjk_term_forbidden"
                )
                is True
                and disposition.get(
                    "positive_cross_scope_causal_surface_fail_closed"
                )
                is True
            )
        )
        and (
            not route_identifier_successor
            or (
                disposition.get(
                    "registered_document_identifier_only_in_wwc_route_required"
                )
                is True
                and disposition.get(
                    "unregistered_or_financial_numeric_surface_fail_closed"
                )
                is True
                and disposition.get(
                    "document_identifier_in_narrative_fail_closed"
                )
                is True
            )
        )
    ):
        raise ValueError("project_os_claim_local_disposition_invalid")

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
        and predecessor_assessment.get("status")
        == "single_thesis_L1_pass_content_materially_improved_two_hypotheses_qualified_no_automatic_expansion"
        and decision.get("immutable_thesis_predecessor_reused") is False
    ):
        raise ValueError("project_os_claim_local_predecessor_invalid")

    _, failed = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_failed_full_fragment_result_ref",
        sha_field="immutable_failed_full_fragment_result_sha256",
        digest_field="immutable_failed_full_fragment_result_digest",
    )
    _, failed_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_full_fragment_assessment_ref",
        sha_field="failed_full_fragment_assessment_sha256",
    )
    failed_valid = (
        failed.get("status") == "terminal_failed_no_retry"
        and failed.get("failure_code")
        == (
            "research_consumer_wwc_evidence_route_invalid"
            if route_identifier_successor
            else (
                "claim_surface_narrative_relation_conflict"
                if causal_polarity_successor
                else "finance_loop_micro_evidence_role_conflict"
            )
        )
        and failed.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (failed.get("execution") or {}).get("model_calls_attempted") == 6
        and (failed.get("execution") or {}).get("tool_calls_accepted") == 3
        and (failed.get("execution") or {}).get("retries") == 0
        and failed_assessment.get("status")
        == (
            "terminal_contract_failure_wwc_document_identifier_numeric_"
            "surface_false_positive_new_attempt_required"
            if route_identifier_successor
            else (
                "terminal_contract_failure_clause_and_negation_blind_lexical_"
                "guard_false_positive_new_attempt_required"
                if causal_polarity_successor
                else "terminal_contract_failure_claim_local_evidence_role_and_"
                "typed_boundary_aggregation_defect_new_attempt_required"
            )
        )
        and (failed_assessment.get("disposition") or {}).get(
            "immutable_R4_preserved"
            if causal_polarity_successor and not route_identifier_successor
            else (
                "immutable_R5_preserved"
                if route_identifier_successor
                else "immutable_R3_preserved"
            )
        )
        is True
    )
    if not failed_valid:
        raise ValueError("project_os_claim_local_failed_R3_invalid")

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
            profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and (profile.get("authority") or {}).get("retry_count") == 0
        ):
            raise ValueError("project_os_claim_local_profile_invalid")
    analysis_defaults = analysis_profile.get("request_defaults") or {}
    submission_defaults = submission_profile.get("request_defaults") or {}
    if not (
        analysis_defaults.get("reasoning_effort") == "high"
        and analysis_defaults.get("max_tokens") == 8000
        and submission_defaults.get("reasoning_effort") == "low"
        and submission_defaults.get("max_tokens") == 2000
    ):
        raise ValueError("project_os_claim_local_profile_budget_drift")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "prior_failed_full_fragment_status": failed["status"],
        "provider_id": analysis_profile["provider_id"],
        "provider_model": analysis_profile["model"],
        "api_key_env": analysis_profile["api_key_env"],
        "recent_provider_steps": 6,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": True,
        "relation_role_successor": False,
        "claim_local_boundary_successor": True,
        "causal_polarity_successor": causal_polarity_successor,
        "wwc_route_identifier_successor": route_identifier_successor,
        "node_profiles": {
            "fragment_analysis": {
                "reasoning_effort": analysis_defaults["reasoning_effort"],
                "max_tokens": analysis_defaults["max_tokens"],
            },
            "contract_submission": {
                "reasoning_effort": submission_defaults[
                    "reasoning_effort"
                ],
                "max_tokens": submission_defaults["max_tokens"],
            },
        },
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
    closed_preconditions: list[str] = []
    out_of_scope: list[str] = []
    for issue_id, row in sorted(ledger.items()):
        if row.get("full_chain_blocker") is not True:
            if (
                issue_id
                == "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use"
                and str(row.get("status") or "").startswith("closed_")
                and bool(row.get("current_evidence_refs"))
                and bool(str(row.get("verification_result") or ""))
            ):
                closed_preconditions.append(issue_id)
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
    required_claim_surface_issue = (
        "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use"
    )
    if (
        required_claim_surface_issue not in explicitly_allowed
        and required_claim_surface_issue not in closed_preconditions
    ):
        raise ValueError("project_os_claim_surface_scope_allowance_missing")
    return {
        "blocking_issue_ids": blocked,
        "explicit_allow_issue_ids": explicitly_allowed,
        "closed_precondition_issue_ids": closed_preconditions,
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
        decision_projection.get("failed_fragment_submission_successor")
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-022-contract-submission-thinking-profile-semantic-"
                "mismatch"
            ),
            allowed_scope=FIXED_PACK_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_failed_fragment_submission_scope_allowance_missing"
        )
    if (
        decision_projection.get("fragment_validation_repair_successor")
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-023-model-counterargument-positive-causal-overreach-"
                "and-missing-bounded-validation-repair"
            ),
            allowed_scope=FRAGMENT_VALIDATION_REPAIR_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_fragment_validation_repair_scope_allowance_missing"
        )
    if (
        decision_projection.get("dynamic_counter_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-025-dynamic-counter-WWC-analysis-high-thinking-"
                "nonconvergence"
            ),
            allowed_scope=DYNAMIC_COUNTER_SUCCESSOR_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_dynamic_counter_scope_allowance_missing"
        )
    if (
        decision_projection.get("dynamic_temporal_repair_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-028-dynamic-narrative-temporal-relation-unbound"
            ),
            allowed_scope=DYNAMIC_TEMPORAL_REPAIR_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_scope_allowance_missing"
        )
    if decision_projection.get("dynamic_five_cell_successor") is True:
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_scope_allowance_missing"
            )
    if (
        decision_projection.get("dynamic_five_cell_remaining_nodes_successor")
        is True
    ):
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-031-five-cell-route-metric-bundle-and-consumer-capacity-contract-mismatch",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_remaining_nodes_scope_allowance_missing"
            )
    if decision_projection.get("dynamic_five_cell_partial_successor") is True:
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-032-five-cell-analysis-view-duplication-and-shared-reasoning-output-budget",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_partial_scope_allowance_missing"
            )
    if decision_projection.get("dynamic_five_cell_node_successor") is True:
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_node_scope_allowance_missing"
            )
    if (
        decision_projection.get("dynamic_five_cell_value_repair_successor")
        is True
    ):
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
            "RC-S3-035-reviewed-claim-exact-source-hidden-by-prefix-projection",
            "RC-S3-036-global-claim-authority-contract-leaks-value-relations-into-nonqualified-cells",
            "RC-S3-037-value-numeric-relation-endpoint-redundancy-and-structured-support-not-recognized",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_value_repair_scope_allowance_missing"
            )
    if (
        decision_projection.get("dynamic_five_cell_claim_surface_successor")
        is True
    ):
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
            "RC-S3-035-reviewed-claim-exact-source-hidden-by-prefix-projection",
        }
        if decision_projection.get(
            "dynamic_five_cell_cell_scoped_claim_contract_successor"
        ) is True:
            required_allowances.add(
                "RC-S3-036-global-claim-authority-contract-leaks-value-"
                "relations-into-nonqualified-cells"
            )
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_claim_surface_scope_allowance_missing"
            )
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
    if (
        decision_projection.get("causal_polarity_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-020-clause-and-negation-blind-causal-lexical-guard-"
                "false-positive"
            ),
            allowed_scope="one_fresh_R5_after_clean_synced_proof_and_preflight",
        )
    ):
        raise ValueError(
            "project_os_full_fragment_causal_polarity_scope_allowance_missing"
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
    if decision_projection.get(
        "dynamic_five_cell_value_repair_successor"
    ) is True:
        known_boundary = (
            "This current-baseline preflight permits only one fresh "
            "decision-bound DELL Value submission repair plus synthesis. It "
            "preserves R6 as failed, reuses its four valid judgments and "
            "capture-verified Value analysis, permits one typed Value repair "
            "submission and synthesis only after all five cells validate, "
            "and forbids new Evidence, Harness-authored judgment, publication, "
            "S3 acceptance, heterogeneous generalization or release."
        )
    elif decision_projection.get(
        "dynamic_five_cell_cell_scoped_claim_contract_successor"
    ) is True:
        known_boundary = (
            "This current-baseline preflight permits only one fresh "
            "decision-bound DELL dynamic five-cell cell-scoped claim-contract "
            "successor. It preserves R5 as a consumed project failure, reuses "
            "only the immutable R4 planner and current S1/S2 result, reruns "
            "all five analyses and submissions plus synthesis, and forbids "
            "R5 reuse, new Evidence, cross-cell claim authority, publication, "
            "S3 acceptance, heterogeneous generalization or release."
        )
    elif (
        decision_projection.get("dynamic_five_cell_claim_surface_successor")
        is True
    ):
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell claim-surface successor. It reuses only "
            "the immutable R4 planner and current S1/S2 result, reruns all "
            "five analyses and submissions plus synthesis, exposes one "
            "reviewed period-bound issuer attribution, and forbids new "
            "Evidence, current-period causal promotion, publication, S3 "
            "acceptance, heterogeneous generalization or release."
        )
    elif decision_projection.get("dynamic_five_cell_node_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell node successor. It reuses the immutable "
            "R3 planner, current S1/S2, three valid judgments and two "
            "capture-verified analysis drafts; permits only two strict Beta "
            "submissions plus synthesis after all five judgments validate; "
            "and forbids analysis reruns, new Evidence, publication, S3 "
            "acceptance, heterogeneous generalization or release."
        )
    elif decision_projection.get("dynamic_five_cell_partial_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell partial successor. It reuses the immutable "
            "R2 planner, current S1/S2 and two valid cell judgments, permits "
            "only three failed cell analyses/submissions plus synthesis after "
            "all five judgments validate, and forbids valid-node reruns, new "
            "Evidence, publication, S3 acceptance, heterogeneous "
            "generalization or release."
        )
    elif (
        decision_projection.get("dynamic_five_cell_remaining_nodes_successor")
        is True
    ):
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell successor over the remaining twelve Chat "
            "nodes. It reuses the immutable successful R1 planner and current "
            "S1/S2 prefix, permits five cell analyses, five strict submissions "
            "and synthesis only after five valid judgments, and forbids prefix "
            "reruns, publication, S3 acceptance, heterogeneous generalization "
            "or release."
        )
    elif decision_projection.get("dynamic_five_cell_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell Chat run. It requires natural planning, "
            "current S1/S2 execution, all five cell attempts, and synthesis "
            "only after five valid judgments. Missing product-profit bridge "
            "authority must remain a typed gap. It does not authorize "
            "publication, S3 acceptance, heterogeneous generalization, or "
            "release."
        )
    elif decision_projection.get("dynamic_temporal_repair_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic counter temporal-validation repair submission. It "
            "reuses six successful model nodes, preserves the rejected R3 "
            "submission as failure evidence, and does not authorize new "
            "evidence, upstream reruns, a second repair, five-cell execution, "
            "publication, S3 acceptance, or release."
        )
    elif decision_projection.get("dynamic_counter_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "failed-node successor for DELL dynamic value_capture counter/WWC. "
            "It reuses five immutable successful model nodes and permits one "
            "max-thinking analysis plus one non-thinking strict submission. "
            "It does not authorize new evidence, another analysis retry, "
            "five-cell execution, publication, S3 acceptance, or release."
        )
    elif decision_projection.get("dynamic_single_cell_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL SEC-only dynamic value_capture single-cell Chat run. It "
            "requires natural planning and current S1/S2 execution, forbids "
            "candidate promotion and transcript prefeed, and does not authorize "
            "five-cell acceptance, publication, or release."
        )
    elif decision_projection.get("fragment_validation_repair_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "R7 failed counter/WWC validation-repair submission. It reuses "
            "six immutable successful model calls, preserves the rejected "
            "fragment and causal guard, and does not authorize another repair, "
            "dynamic Agentic Research, five-cell acceptance, publication, or "
            "release."
        )
    elif decision_projection.get("failed_fragment_submission_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "R6 failed counter/WWC contract-submission successor. It reuses "
            "five immutable successful model calls and does not authorize "
            "analysis reruns, dynamic Agentic Research, five-cell acceptance, "
            "publication, or release."
        )
    elif decision_projection.get("full_fragment_judgment_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only the decision-bound "
            "DELL value_capture full three-fragment fixed-Pack Chat successor. "
            "It is not exact-live authority, dynamic Agentic Research, "
            "five-cell acceptance, publication, or release."
        )
    elif decision_projection.get("micro_judgment_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only the decision-bound "
            "DELL value_capture fixed-Pack micro-judgment Chat successor. It "
            "is not exact-live authority, natural submission proof, dynamic "
            "Agentic Research, five-cell acceptance, publication, or release."
        )
    else:
        known_boundary = (
            "This current-baseline preflight permits only the decision-bound "
            "DELL value_capture fixed-Pack Chat replacement. It is not exact-"
            "live authority, dynamic Agentic Research, five-cell acceptance, "
            "publication, or release."
        )
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
        "known_boundary": known_boundary,
    }
