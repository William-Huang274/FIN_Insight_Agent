from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.providers.chat_completions import load_chat_completion_profile

from .multi_agent_report_authority import (
    MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION,
)
from .reviewed_evidence_pack import canonical_digest


REPORT_REMAP_SCOPE_DECISION_SCHEMA_VERSION = (
    "fin_ia_s3_multi_agent_report_protected_remap_scope_decision_v1_0"
)
REPORT_REMAP_SCOPE_DECISION_STATUS = (
    "protected_report_zero_call_pass_one_writer_remap_node_authorized"
)
REPORT_REMAP_RUN_SCOPE = (
    "one_fresh_Writer_only_terminal_remapping_logical_node_with_separate_"
    "attempt_budget"
)
REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_SCHEMA_VERSION = (
    "fin_ia_s3_multi_agent_report_protected_remap_scope_decision_v1_1"
)
REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_STATUS = (
    "protected_report_length_failure_preserved_one_replacement_writer_remap_node_authorized"
)
REPORT_REMAP_REPLACEMENT_RUN_SCOPE = (
    "one_fresh_Writer_only_terminal_remapping_replacement_logical_node_after_"
    "preserved_length_failure"
)
REPORT_REMAP_LIVE_AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s3_multi_agent_report_protected_remap_live_authority_v1_0"
)
REPORT_REMAP_FULL_RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_multi_agent_report_protected_remap_full_result_v1_0"
)
REPORT_REMAP_PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_multi_agent_report_protected_remap_live_result_v1_0"
)

_EXPECTED_BOOLEAN_POLICY = {
    "replacement_is_new_logical_node_not_retry": True,
    "chat_live_authorized": True,
    "credential_presence_required": True,
    "immutable_source_report_required": True,
    "protected_surface_contract_required": True,
    "deterministic_renderer_required": True,
    "separate_logical_node_and_contract_attempt_counts_required": True,
    "upstream_agent_rerun_authorized": False,
    "writer_research_analysis_authorized": False,
    "new_evidence_or_numeric_fact_authorized": False,
    "external_source_network_authorized": False,
    "candidate_promotion_authorized": False,
    "responses_live_authorized": False,
    "anthropic_live_authorized": False,
    "S1_acceptance_authorized": False,
    "S3_acceptance_authorized": False,
    "generalization_claim_authorized": False,
    "qualified_human_acceptance_authorized": False,
    "product_publication_authorized": False,
    "release_authorized": False,
}

_EXPECTED_EXECUTION_LIMITS = {
    "reused_specialist_plan_count": 6,
    "reused_lead_plan_count": 1,
    "reused_workpaper_count": 6,
    "reused_lead_coordination_count": 1,
    "reused_completed_challenge_repair_count": 3,
    "reused_role_evaluation_count": 6,
    "reused_cross_role_evaluation_count": 1,
    "reused_legacy_report_count": 1,
    "maximum_new_logical_model_nodes": 1,
    "maximum_contract_attempts": 2,
    "maximum_new_analysis_calls": 0,
    "maximum_new_writer_continuations": 0,
    "external_source_network_calls": 0,
    "candidate_promotions": 0,
}

_EXPECTED_BOUND_INPUTS = {
    "predecessor_live_authority",
    "predecessor_public_result",
    "predecessor_content_assessment",
    "predecessor_private_full_result",
    "report_surface_zero_call_proof",
    "report_authority_catalog",
    "source_bound_numeric_review",
    "writer_submission_profile",
}
_EXPECTED_REPLACEMENT_BOUND_INPUTS = {
    *_EXPECTED_BOUND_INPUTS,
    "failed_remap_live_authority",
    "failed_remap_public_result",
    "failed_remap_private_terminal_result",
}


class ReportRemapAuthorityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReportRemapAuthorityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _repo_path(root: Path, ref: object) -> Path:
    text = str(ref or "").replace("\\", "/").strip()
    _require(bool(text) and not text.startswith("/"), "report_remap_ref_invalid")
    root = root.resolve()
    path = (root / text).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReportRemapAuthorityError("report_remap_ref_outside_root") from exc
    _require(path.is_file(), "report_remap_ref_missing:" + text)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportRemapAuthorityError(
            "report_remap_json_invalid:" + path.as_posix()
        ) from exc
    _require(isinstance(value, dict), "report_remap_json_not_object")
    return value


def _bound_payload(
    *, root: Path, binding: Mapping[str, Any], name: str
) -> tuple[str, dict[str, Any]]:
    _require(
        set(binding).issubset({"ref", "sha256", "digest_field", "digest"})
        and set(binding).issuperset({"ref", "sha256"}),
        "report_remap_binding_shape_invalid:" + name,
    )
    path = _repo_path(root, binding["ref"])
    _require(
        _sha256(path) == str(binding["sha256"]),
        "report_remap_binding_sha_drift:" + name,
    )
    payload = _load_json(path)
    digest_field = str(binding.get("digest_field") or "")
    if digest_field:
        _require(
            payload.get(digest_field) == binding.get("digest"),
            "report_remap_binding_digest_drift:" + name,
        )
    return path.relative_to(root.resolve()).as_posix(), payload


def validate_report_remap_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one clean Writer-only protected-report remap decision."""

    root = root.resolve()
    value = deepcopy(dict(decision))
    replacement = (
        value.get("schema_version")
        == REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_SCHEMA_VERSION
    )
    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        *_EXPECTED_BOOLEAN_POLICY,
        "bound_inputs",
        "implementation_bindings",
        "execution_limits",
        "token_budget_basis",
        "authority_statement",
        "decision_digest",
    }
    _require(set(value) == expected_fields, "report_remap_decision_shape_invalid")
    expected_schema = (
        REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_SCHEMA_VERSION
        if replacement
        else REPORT_REMAP_SCOPE_DECISION_SCHEMA_VERSION
    )
    expected_status = (
        REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_STATUS
        if replacement
        else REPORT_REMAP_SCOPE_DECISION_STATUS
    )
    expected_run_scope = (
        REPORT_REMAP_REPLACEMENT_RUN_SCOPE
        if replacement
        else REPORT_REMAP_RUN_SCOPE
    )
    expected_next_scope = (
        "one_writer_terminal_protected_contract_remap_replacement"
        if replacement
        else "one_writer_terminal_protected_contract_remap"
    )
    _require(
        value["schema_version"] == expected_schema
        and value["status"] == expected_status
        and value["case_key"] == "DELL"
        and value["cell_id"] == "ALL"
        and value["run_scope_id"] == expected_run_scope
        and value["evidence_mode"]
        == "immutable_completed_report_plus_typed_authority_no_new_research"
        and value["next_authorized_scope"] == expected_next_scope,
        "report_remap_decision_identity_invalid",
    )
    _require(
        all(value.get(field) is expected for field, expected in _EXPECTED_BOOLEAN_POLICY.items()),
        "report_remap_decision_boolean_policy_invalid",
    )
    _require(
        value["execution_limits"] == _EXPECTED_EXECUTION_LIMITS,
        "report_remap_execution_limits_invalid",
    )
    unsigned = {key: item for key, item in value.items() if key != "decision_digest"}
    _require(
        value["decision_digest"] == canonical_digest(unsigned),
        "report_remap_decision_digest_invalid",
    )

    bound_inputs = _mapping(
        value["bound_inputs"], "report_remap_bound_inputs_invalid"
    )
    _require(
        set(bound_inputs)
        == (
            _EXPECTED_REPLACEMENT_BOUND_INPUTS
            if replacement
            else _EXPECTED_BOUND_INPUTS
        ),
        "report_remap_bound_inputs_invalid",
    )
    loaded: dict[str, dict[str, Any]] = {}
    refs: dict[str, str] = {}
    for name in sorted(bound_inputs):
        ref, payload = _bound_payload(
            root=root,
            binding=_mapping(
                bound_inputs[name], "report_remap_binding_invalid:" + name
            ),
            name=name,
        )
        refs[name] = ref
        loaded[name] = payload

    public = loaded["predecessor_public_result"]
    private = loaded["predecessor_private_full_result"]
    assessment = loaded["predecessor_content_assessment"]
    proof = loaded["report_surface_zero_call_proof"]
    catalog = loaded["report_authority_catalog"]
    _require(
        public.get("status")
        == "multi_agent_preview_report_compiled_content_assessment_pending"
        and public.get("result_digest")
        == bound_inputs["predecessor_public_result"].get("digest")
        and private.get("full_result_digest")
        == bound_inputs["predecessor_private_full_result"].get("digest")
        and private.get("report", {}).get("report_digest")
        == assessment.get("report_digest")
        and assessment.get("financial_truth_L1_pass") is False
        and assessment.get("material_research_quality_gain_observed") is True,
        "report_remap_predecessor_state_invalid",
    )
    _require(
        proof.get("status") == "zero_call_structure_pass_terminal_remap_eligible"
        and proof.get("result_digest")
        == bound_inputs["report_surface_zero_call_proof"].get("digest")
        and (proof.get("decision") or {}).get(
            "terminal_writer_remapping_live_ready"
        )
        is True
        and (proof.get("decision") or {}).get(
            "current_legacy_report_financial_truth_L1_pass"
        )
        is False,
        "report_remap_zero_call_proof_invalid",
    )
    _require(
        catalog.get("schema_version")
        == MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION
        and catalog.get("authority_catalog_digest")
        == bound_inputs["report_authority_catalog"].get("digest")
        == (proof.get("actual_dell_replay") or {}).get(
            "authority_catalog_digest"
        )
        and catalog.get("case_identity", {}).get("case_key") == "DELL",
        "report_remap_authority_catalog_invalid",
    )
    _require(
        refs["source_bound_numeric_review"]
        == (proof.get("bound_inputs") or {})
        .get("source_bound_numeric_review", {})
        .get("ref")
        and bound_inputs["source_bound_numeric_review"].get("sha256")
        == (proof.get("bound_inputs") or {})
        .get("source_bound_numeric_review", {})
        .get("sha256"),
        "report_remap_source_review_lineage_invalid",
    )
    if replacement:
        failed_authority = loaded["failed_remap_live_authority"]
        failed_public = loaded["failed_remap_public_result"]
        failed_private = loaded["failed_remap_private_terminal_result"]
        failed_attempts = failed_private.get("contract_attempts") or []
        _require(
            failed_authority.get("authority_digest")
            == failed_public.get("authority_digest")
            and failed_public.get("status")
            == "protected_report_terminal_remap_failure_preserved"
            and (failed_public.get("failure") or {}).get("failure_code")
            == "report_remap_live_unrepairable_tool_envelope"
            and (failed_public.get("execution") or {}).get(
                "logical_model_node_count"
            )
            == 1
            and (failed_public.get("execution") or {}).get(
                "contract_attempt_count"
            )
            == 1
            and (failed_public.get("execution") or {}).get("scope_compliant")
            is True
            and failed_public.get("full_result_ref")
            == refs["failed_remap_private_terminal_result"]
            and failed_public.get("full_result_sha256")
            == bound_inputs["failed_remap_private_terminal_result"].get("sha256")
            and failed_private.get("full_result_digest")
            == bound_inputs["failed_remap_private_terminal_result"].get("digest")
            and len(failed_attempts) == 1
            and failed_attempts[0].get("finish_reason") == "length"
            and failed_attempts[0].get("failure_code")
            == "report_remap_live_tool_arguments_json_invalid"
            and len(failed_attempts[0].get("tool_calls") or []) == 1
            and bool(
                ((failed_attempts[0].get("tool_calls") or [])[0]).get("id")
            )
            and failed_private.get("draft") is None
            and failed_private.get("rendered_report") is None,
            "report_remap_replacement_failure_lineage_invalid",
        )
    profile = load_chat_completion_profile(loaded["writer_submission_profile"])
    expected_max_tokens = 12000 if replacement else 7000
    _require(
        profile.provider_id == "deepseek"
        and profile.model == "deepseek-v4-pro"
        and profile.base_url == "https://api.deepseek.com"
        and profile.endpoint == "/chat/completions"
        and dict(profile.request_defaults)
        == {
            "max_tokens": expected_max_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        and profile.authority.get("retry_count") == 0,
        "report_remap_provider_profile_invalid",
    )
    implementation_bindings = value["implementation_bindings"]
    _require(
        isinstance(implementation_bindings, list)
        and len(implementation_bindings) >= 3,
        "report_remap_implementation_bindings_invalid",
    )
    implementation_refs: list[str] = []
    for binding in implementation_bindings:
        row = _mapping(binding, "report_remap_implementation_binding_invalid")
        _require(
            set(row) == {"ref", "sha256"},
            "report_remap_implementation_binding_invalid",
        )
        path = _repo_path(root, row["ref"])
        _require(
            _sha256(path) == str(row["sha256"]),
            "report_remap_implementation_sha_drift",
        )
        implementation_refs.append(path.relative_to(root).as_posix())
    _require(
        {
            "src/sec_agent/research/multi_agent_report_authority.py",
            "src/sec_agent/research/multi_agent_report_remap.py",
            "scripts/research/run_s3_multi_agent_report_remap_live.py",
        }.issubset(implementation_refs),
        "report_remap_required_implementation_missing",
    )
    token_basis = _mapping(
        value["token_budget_basis"], "report_remap_token_budget_basis_invalid"
    )
    expected_comparable = (
        "first_natural_remap_truncated_at_7000_after_six_sections_six_gaps_"
        "and_partial_second_wwc"
        if replacement
        else "prior_writer_report_required_two_bounded_contract_attempts"
    )
    _require(
        token_basis.get("node_id") == "AGENT::WRITER::PROTECTED_REPORT_REMAP"
        and token_basis.get("purpose")
        == "terminal_contract_remap_without_new_research"
        and int(token_basis.get("source_report_characters") or 0) > 0
        and int(token_basis.get("authority_catalog_characters") or 0) > 0
        and token_basis.get("required_section_count") == 6
        and token_basis.get("required_gap_count") == 6
        and token_basis.get("required_wwc_count") == 8
        and token_basis.get("schema_burden")
        == "nested_six_section_protected_tool_with_claim_scoped_refs"
        and token_basis.get("materiality_quality_risk") == "high"
        and token_basis.get("comparable_run_evidence") == expected_comparable
        and token_basis.get("reasoning_profile") == "thinking_disabled"
        and token_basis.get("maximum_output_tokens") == expected_max_tokens
        and token_basis.get("maximum_contract_attempts") == 2
        and token_basis.get("cost_and_latency_are_secondary_constraints") is True
        and token_basis.get("stop_behavior")
        == "stop_after_first_valid_contract_or_terminal_after_second_rejection",
        "report_remap_token_budget_basis_invalid",
    )
    return {
        "clean_proof_status": proof["status"],
        "provider_id": profile.provider_id,
        "provider_model": profile.model,
        "api_key_env": profile.api_key_env,
        "recent_provider_steps": 0,
        "multi_agent_preview": False,
        "multi_agent_report_protected_remap": True,
        "multi_agent_report_protected_remap_replacement": replacement,
        "run_scope_id": expected_run_scope,
        "execution_limits": deepcopy(_EXPECTED_EXECUTION_LIMITS),
        "token_budget_basis": deepcopy(dict(token_basis)),
        "authority_catalog_ref": refs["report_authority_catalog"],
        "source_report_ref": refs["predecessor_private_full_result"],
        "report_surface_zero_call_proof_ref": refs[
            "report_surface_zero_call_proof"
        ],
    }


__all__ = [
    "REPORT_REMAP_FULL_RESULT_SCHEMA_VERSION",
    "REPORT_REMAP_LIVE_AUTHORITY_SCHEMA_VERSION",
    "REPORT_REMAP_PUBLIC_RESULT_SCHEMA_VERSION",
    "REPORT_REMAP_REPLACEMENT_RUN_SCOPE",
    "REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_SCHEMA_VERSION",
    "REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_STATUS",
    "REPORT_REMAP_RUN_SCOPE",
    "REPORT_REMAP_SCOPE_DECISION_SCHEMA_VERSION",
    "REPORT_REMAP_SCOPE_DECISION_STATUS",
    "ReportRemapAuthorityError",
    "validate_report_remap_scope_decision",
]
