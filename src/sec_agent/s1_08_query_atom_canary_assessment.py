from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest


PUBLIC_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_public_result_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1_08.deepseek_query_atom_canary:v1"
EXPECTED_FAILURE = "s1_08_query_atom_canary_output_plan_binding_invalid"


class S108QueryAtomCanaryAssessmentError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def assess_failed_query_atom_canary(
    *,
    admission: Mapping[str, Any],
    terminal: Mapping[str, Any],
    capture: Mapping[str, Any],
    receipt: Mapping[str, Any],
    authority: Mapping[str, Any],
    zero_call_evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    _verify_digest(admission, "admission_digest", "assessment_admission_digest_invalid")
    _verify_digest(terminal, "terminal_result_digest", "assessment_terminal_digest_invalid")
    _verify_digest(authority, "decision_digest", "assessment_authority_digest_invalid")
    _verify_digest(receipt, "receipt_digest", "assessment_receipt_digest_invalid")
    _verify_digest(
        zero_call_evaluation,
        "evaluation_digest",
        "assessment_zero_call_evaluation_digest_invalid",
    )
    if canonical_digest(capture) != terminal.get("capture_digest"):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_capture_digest_invalid"
        )
    if (
        admission.get("contract_ref") != CONTRACT_REF
        or terminal.get("contract_ref") != CONTRACT_REF
        or terminal.get("admission_digest") != admission.get("admission_digest")
        or admission.get("authority_decision_digest")
        != authority.get("decision_digest")
        or terminal.get("request_digest") != admission.get("request_digest")
        or capture.get("request_digest") != admission.get("request_digest")
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_execution_binding_invalid"
        )
    if (
        terminal.get("status") != "terminal_failed_no_retry"
        or terminal.get("terminal_code") != EXPECTED_FAILURE
        or terminal.get("completed_calls") != 1
        or terminal.get("retry_count") != 0
        or terminal.get("fallback_count") != 0
        or terminal.get("accepted_atom_count") != 0
        or terminal.get("accepted_atoms") != []
        or terminal.get("runtime_activation") is not False
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_terminal_disposition_invalid"
        )
    if (
        receipt.get("state") != "terminal"
        or receipt.get("admission_digest") != admission.get("admission_digest")
        or receipt.get("terminal_status") != terminal.get("status")
        or receipt.get("terminal_code") != terminal.get("terminal_code")
        or receipt.get("terminal_result_digest")
        != terminal.get("terminal_result_digest")
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_exact_once_receipt_invalid"
        )
    if (
        capture.get("credential_or_authorization_value_saved") is not False
        or capture.get("provider_private_reasoning_saved") is not False
        or capture.get("business_evidence_or_fact_authority") is not False
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_capture_boundary_invalid"
        )
    provider_output = terminal.get("provider_output")
    if (
        not isinstance(provider_output, Mapping)
        or set(provider_output) != {"schema_version", "atoms"}
        or canonical_digest(provider_output)
        != terminal.get("provider_output_digest")
        or not isinstance(provider_output.get("atoms"), list)
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_provider_output_invalid"
        )
    request = capture.get("model_visible_request")
    if not isinstance(request, Mapping) or request.get("request_digest") != terminal.get(
        "request_digest"
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_model_visible_request_invalid"
        )
    allowed_keys = {
        tuple(str(value) for value in row.get("plan_key") or ())
        for row in request.get("plans") or []
    }
    expected_fields = {
        "case_key",
        "evidence_slot_id",
        "evidence_owner_entity_key",
        "language",
        "atom_kind",
        "value",
    }
    invalid_bindings: list[dict[str, Any]] = []
    duplicate_bindings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    shape_valid_count = 0
    for index, raw in enumerate(provider_output["atoms"]):
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            raise S108QueryAtomCanaryAssessmentError(
                "assessment_observed_atom_shape_invalid"
            )
        shape_valid_count += 1
        key = (
            str(raw["case_key"]),
            str(raw["evidence_slot_id"]),
            str(raw["evidence_owner_entity_key"]),
            str(raw["language"]),
        )
        row = {
            "atom_index": index,
            "case_key": key[0],
            "evidence_slot_id": key[1],
            "evidence_owner_entity_key": key[2],
            "language": key[3],
            "atom_kind": str(raw["atom_kind"]),
            "value": str(raw["value"]),
        }
        if key not in allowed_keys:
            invalid_bindings.append(row)
        elif key in seen:
            duplicate_bindings.append(row)
        seen.add(key)
    if not invalid_bindings and not duplicate_bindings:
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_plan_binding_failure_not_reproduced"
        )
    gates = zero_call_evaluation.get("quality_gates") or {}
    variants = zero_call_evaluation.get("variant_summary") or {}
    local = variants.get("deterministic_local_compiler") or {}
    raw = variants.get("user_raw_query") or {}
    if (
        gates.get("deterministic_local_structure_pass") is not True
        or zero_call_evaluation.get("status")
        != "zero_call_A_B_pass_model_atom_observation_pending"
    ):
        raise S108QueryAtomCanaryAssessmentError(
            "assessment_deterministic_baseline_invalid"
        )
    body = {
        "schema_version": PUBLIC_RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "recorded_at": terminal["observed_at"],
        "owning_stage": "FIN_0_1_3_S1_08",
        "status": "natural_query_atom_canary_terminal_failed_model_variant_rejected",
        "execution_git_commit": admission["execution_git_commit"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "authority_decision_digest": authority["decision_digest"],
        "admission_digest": admission["admission_digest"],
        "terminal_result_digest": terminal["terminal_result_digest"],
        "capture_digest": terminal["capture_digest"],
        "exact_once_receipt_digest": receipt["receipt_digest"],
        "request_digest": terminal["request_digest"],
        "provider_output_digest": terminal["provider_output_digest"],
        "provider": {
            "backend": admission["provider"]["backend"],
            "model": admission["provider"]["model"],
        },
        "natural_observation": {
            "terminal_status": terminal["status"],
            "terminal_code": terminal["terminal_code"],
            "gateway_status": terminal["gateway_status"],
            "finish_reason": terminal["finish_reason"],
            "usage": deepcopy(terminal["usage"]),
            "observed_atom_count": len(provider_output["atoms"]),
            "shape_valid_atom_count": shape_valid_count,
            "allowed_plan_binding_count": (
                shape_valid_count - len(invalid_bindings) - len(duplicate_bindings)
            ),
            "invalid_plan_binding_count": len(invalid_bindings),
            "duplicate_plan_binding_count": len(duplicate_bindings),
            "invalid_plan_bindings": invalid_bindings,
            "duplicate_plan_bindings": duplicate_bindings,
            "accepted_atom_count": 0,
            "partial_atom_salvage_performed": False,
            "retry_or_replacement_performed": False,
            "provider_output_is_financial_fact_or_evidence": False,
        },
        "three_way_disposition": {
            "user_raw_query": {
                "mean_facet_coverage": raw.get("mean_facet_coverage"),
                "duplicate_query_rate": raw.get("duplicate_query_rate"),
            },
            "deterministic_local_compiler": {
                "mean_facet_coverage": local.get("mean_facet_coverage"),
                "minimum_facet_coverage": local.get("minimum_facet_coverage"),
                "duplicate_query_rate": local.get("duplicate_query_rate"),
                "contamination_count": local.get("contamination_count"),
                "selected_as_external_and_internal_baseline": True,
            },
            "deepseek_query_atoms_plus_deterministic_local_compiler": {
                "status": "observed_but_contract_invalid_not_compared_or_activated",
                "accepted_atom_count": 0,
                "runtime_admitted": False,
            },
            "comparison_status": "contract_disposition_complete_no_model_assisted_query_metrics",
        },
        "observed_calls": {
            "provider": 1,
            "network": 1,
            "model": 1,
            "transport_attempts": terminal["usage"]["transport_attempt_count"],
            "retry": 0,
            "fallback": 0,
            "document_fetch": terminal["document_fetches"],
            "retrieval": terminal["retrieval_calls"],
            "embedding": terminal["embedding_calls"],
            "rerank": terminal["rerank_calls"],
            "evidence_promotion": terminal["evidence_promotions"],
        },
        "decision": {
            "deepseek_query_atom_variant": "reject_current_contract_no_retry_no_field_patch",
            "external_query_baseline": "deterministic_local_compiler_only",
            "next": "S1_08_OFFICIAL_ROUTES_PLUS_FIRECRAWL_SHADOW_COMBINED_LIVE_READINESS_DECISION",
            "additional_query_atom_model_call_authorized": False,
            "combined_external_live_authorized_by_this_result": False,
            "internal_retrieval_authorized_by_this_result": False,
            "internal_exact_BM25_dense_graph_then_qrels_then_BGE_rerank_backlog_preserved": True,
        },
        "stage_acceptance": {
            "natural_model_atom_observation": True,
            "model_assisted_query_plan": False,
            "three_way_contract_disposition": True,
            "fresh_combined_external_live": False,
            "internal_retrieval_query_facet": False,
            "candidate_ceiling_and_qrels": False,
            "BGE_fusion_rerank": False,
            "downstream_utilization": False,
            "S1_08": False,
            "release": False,
        },
        "public_private_separation": {
            "full_model_visible_request_and_raw_gateway_response_in_git": False,
            "private_capture_retained_outside_git": True,
            "credential_or_authorization_value_saved": False,
            "provider_private_reasoning_saved": False,
            "capture_ref": terminal["capture_ref"],
        },
        "known_boundary": (
            "This result rejects one model-assisted query variant because its typed "
            "plan binding was invalid. It does not establish fresh provider recall, "
            "document capture, Evidence quality, internal retrieval, BGE/rerank value, "
            "downstream research quality, S1-08 acceptance or release."
        ),
    }
    return {**body, "record_digest": canonical_digest(body)}


def _verify_digest(
    value: Mapping[str, Any], digest_key: str, error_code: str
) -> None:
    body = {key: deepcopy(item) for key, item in value.items() if key != digest_key}
    if value.get(digest_key) != canonical_digest(body):
        raise S108QueryAtomCanaryAssessmentError(error_code)
