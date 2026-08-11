from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


CONTRACT_REF = "fin_0_1_3.S3.evidence_selection_and_local_role_projection:v2"
CONTEXT_SCHEMA = "fin_ia_0_1_3_s3_evidence_selection_context_v2_0"
REQUIRED_FIELDS = (
    "epistemic_state",
    "answer_direction",
    "mechanism_alias",
    "selected_evidence_aliases",
    "selected_counterevidence_aliases",
    "gap_aliases",
    "confidence",
    "what_would_change_aliases",
)


class S3EvidenceRoleContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def compile_s3_evidence_selection_context(
    *, s2_context: Mapping[str, Any]
) -> dict[str, Any]:
    """Translate an immutable S2 context into the S3 v2 selection contract.

    S2 remains unchanged.  The provider selects observations; local code owns the
    semantic role assigned to each observation in the resulting claim.
    """

    old = s2_context.get("model_context") or {}
    old_contract = old.get("output_contract") or {}
    if not old or set(old_contract.get("required_fields") or []) != {
        "epistemic_state",
        "answer_direction",
        "mechanism_alias",
        "support_aliases",
        "counterevidence_aliases",
        "gap_aliases",
        "confidence",
        "what_would_change_aliases",
    }:
        raise S3EvidenceRoleContractError("s3_evidence_role_s2_context_invalid")
    model_context = {
        key: deepcopy(old[key])
        for key in (
            "case_key",
            "company_name",
            "program_cell_id",
            "decision_question",
            "method_steps",
            "evidence_options",
            "gap_options",
            "mechanism_options",
            "what_would_change_options",
        )
    }
    model_context["selection_instruction"] = (
        "Select observations and counterobservations relevant to the judgment. "
        "Do not decide whether an observation proves the thesis; local policy "
        "assigns observation_support, thesis_support, or boundary_only."
    )
    model_context["output_contract"] = {
        "required_fields": list(REQUIRED_FIELDS),
        "epistemic_states": deepcopy(old_contract["epistemic_states"]),
        "answer_directions": deepcopy(old_contract["answer_directions"]),
        "confidence_values": deepcopy(old_contract["confidence_values"]),
        "additional_properties": False,
    }
    sidecar = deepcopy(s2_context["local_authority_sidecar"])
    if not model_context["gap_options"]:
        sidecar["default_cannot_infer_gap"] = {
            "alias": "S3_LOCAL_GAP_" + canonical_digest(
                {
                    "request_id": s2_context["request_id"],
                    "decision_question": model_context["decision_question"],
                }
            )[:16].upper(),
            "gap_code": "s3_local_selected_evidence_does_not_resolve_decision_question",
            "cannot_infer": (
                "Selected evidence does not resolve the request-bound decision question: "
                + str(model_context["decision_question"])
            ),
            "source_exhaustion_proven": False,
            "local_default_for_zero_upstream_gap_options": True,
        }
    body = {
        "schema_version": CONTEXT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "request_id": s2_context["request_id"],
        "source_request_digest": s2_context["source_request_digest"],
        "source_s2_context_digest": s2_context["context_digest"],
        "model_context": model_context,
        "local_authority_sidecar": sidecar,
    }
    return {**body, "context_digest": canonical_digest(body)}


def validate_s3_evidence_selection_output(
    provider_output: Mapping[str, Any], *, compiled: Mapping[str, Any]
) -> None:
    context = compiled.get("model_context") or {}
    contract = context.get("output_contract") or {}
    if (
        compiled.get("schema_version") != CONTEXT_SCHEMA
        or compiled.get("contract_ref") != CONTRACT_REF
        or set(provider_output) != set(REQUIRED_FIELDS)
        or set(contract.get("required_fields") or []) != set(REQUIRED_FIELDS)
    ):
        raise S3EvidenceRoleContractError("s3_evidence_selection_shape_invalid")
    for field, allowed_key in (
        ("epistemic_state", "epistemic_states"),
        ("answer_direction", "answer_directions"),
        ("confidence", "confidence_values"),
    ):
        if provider_output.get(field) not in contract.get(allowed_key, []):
            raise S3EvidenceRoleContractError("s3_evidence_selection_enum_invalid")
    gap_authority = _aliases(context, "gap_options")
    local_default = (compiled.get("local_authority_sidecar") or {}).get(
        "default_cannot_infer_gap"
    )
    if local_default:
        gap_authority.add(str(local_default["alias"]))
    authorities = {
        "mechanism_alias": _aliases(context, "mechanism_options"),
        "selected_evidence_aliases": _aliases(context, "evidence_options"),
        "selected_counterevidence_aliases": _aliases(context, "evidence_options"),
        "gap_aliases": gap_authority,
        "what_would_change_aliases": _aliases(
            context, "what_would_change_options"
        ),
    }
    if provider_output.get("mechanism_alias") not in authorities["mechanism_alias"]:
        raise S3EvidenceRoleContractError("s3_evidence_selection_mechanism_invalid")
    for field in REQUIRED_FIELDS[3:6] + (REQUIRED_FIELDS[7],):
        values = provider_output.get(field)
        if (
            not isinstance(values, list)
            or len(values) != len(set(values))
            or not set(values).issubset(authorities[field])
        ):
            raise S3EvidenceRoleContractError("s3_evidence_selection_alias_invalid")
    if set(provider_output["selected_evidence_aliases"]) & set(
        provider_output["selected_counterevidence_aliases"]
    ):
        raise S3EvidenceRoleContractError("s3_evidence_selection_role_overlap")
    if not any(
        provider_output[field]
        for field in (
            "selected_evidence_aliases",
            "selected_counterevidence_aliases",
            "gap_aliases",
        )
    ):
        raise S3EvidenceRoleContractError("s3_evidence_selection_unbounded")
    cannot_infer = provider_output["epistemic_state"] == "cannot_infer"
    if cannot_infer != (provider_output["answer_direction"] == "cannot_infer"):
        raise S3EvidenceRoleContractError(
            "s3_evidence_selection_epistemic_direction_conflict"
        )
    if cannot_infer and not provider_output["gap_aliases"]:
        raise S3EvidenceRoleContractError("s3_evidence_selection_gap_required")


def normalize_s3_evidence_selection_output(
    provider_output: Mapping[str, Any], *, compiled: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = deepcopy(dict(provider_output))
    default_gap = (compiled.get("local_authority_sidecar") or {}).get(
        "default_cannot_infer_gap"
    )
    action = "none"
    if (
        normalized.get("epistemic_state") == "cannot_infer"
        and normalized.get("answer_direction") == "cannot_infer"
        and normalized.get("gap_aliases") == []
        and not (compiled.get("model_context") or {}).get("gap_options")
        and default_gap
    ):
        normalized["gap_aliases"] = [str(default_gap["alias"])]
        action = "attach_local_default_for_zero_upstream_gap_options"
    receipt_body = {
        "contract_ref": CONTRACT_REF,
        "action": action,
        "raw_provider_output_digest": canonical_digest(provider_output),
        "normalized_provider_output_digest": canonical_digest(normalized),
        "default_gap_alias": str(default_gap["alias"]) if action != "none" else None,
        "provider_authored_default_gap": False,
    }
    return normalized, {
        **receipt_body,
        "receipt_digest": canonical_digest(receipt_body),
    }


def consume_s3_evidence_selection_output(
    *, request: Mapping[str, Any], compiled: Mapping[str, Any], provider_output: Mapping[str, Any]
) -> dict[str, Any]:
    validate_s3_evidence_selection_output(provider_output, compiled=compiled)
    visible = request["model_visible_request"]
    evidence_map = _alias_map(visible, "evidence_aliases")
    gap_map = _alias_map(visible, "gap_aliases")
    default_gap = (compiled.get("local_authority_sidecar") or {}).get(
        "default_cannot_infer_gap"
    )
    if default_gap:
        gap_map[str(default_gap["alias"])] = deepcopy(dict(default_gap))
    mechanism_map = _alias_map(visible, "mechanism_aliases")
    wwc_map = _alias_map(visible, "what_would_change_aliases")
    selected_aliases = list(provider_output["selected_evidence_aliases"])
    roles = _project_roles(
        epistemic_state=str(provider_output["epistemic_state"]),
        aliases=selected_aliases,
    )
    selected = _resolve(selected_aliases, evidence_map)
    counter = _resolve(
        provider_output["selected_counterevidence_aliases"], evidence_map
    )
    mechanism_alias = str(provider_output["mechanism_alias"])
    claim_body = {
        "case_key": request["case_key"],
        "company_name": visible["company_name"],
        "program_cell_id": request["program_cell_id"],
        "decision_question": visible["decision_question"],
        "epistemic_state": provider_output["epistemic_state"],
        "answer_direction": provider_output["answer_direction"],
        "confidence": provider_output["confidence"],
        "mechanism_alias": mechanism_alias,
        "mechanism_atom": mechanism_map[mechanism_alias]["atom"],
        # Compatibility projection for existing S3 card compilation.  The
        # authoritative meaning is evidence_role_projection below.
        "support_evidence": selected,
        "counterevidence": counter,
        "typed_gaps": _resolve(provider_output["gap_aliases"], gap_map),
        "what_would_change": _resolve(
            provider_output["what_would_change_aliases"], wwc_map
        ),
        "evidence_role_projection": roles,
        "provider_free_text_fields": [],
        "local_truth_ownership": deepcopy(request["local_render_authority"]),
        "lineage": {
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "s1_query_digest": request["s1_query_digest"],
            "s3_context_digest": compiled["context_digest"],
            "provider_output_digest": canonical_digest(provider_output),
            "evidence_role_contract_ref": CONTRACT_REF,
        },
    }
    claim_id = "fin013_s3_claim_v2_" + canonical_digest(claim_body)[:24]
    with_id = {"claim_id": claim_id, **claim_body}
    return {**with_id, "claim_digest": canonical_digest(with_id)}


def _project_roles(*, epistemic_state: str, aliases: Sequence[str]) -> dict[str, list[str]]:
    roles = {
        "observation_support": [],
        "thesis_support": [],
        "boundary_only": [],
    }
    if epistemic_state == "cannot_infer":
        roles["boundary_only"] = list(aliases)
    elif epistemic_state == "fact_supported":
        roles["thesis_support"] = list(aliases)
    else:
        roles["observation_support"] = list(aliases)
    return roles


def _aliases(value: Mapping[str, Any], field: str) -> set[str]:
    return {str(row["alias"]) for row in value.get(field) or []}


def _alias_map(value: Mapping[str, Any], field: str) -> dict[str, dict[str, Any]]:
    return {
        str(row["alias"]): deepcopy(dict(row)) for row in value.get(field) or []
    }


def _resolve(
    aliases: Sequence[str], authority: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    return [deepcopy(dict(authority[str(alias)])) for alias in aliases]


__all__ = [
    "CONTRACT_REF",
    "CONTEXT_SCHEMA",
    "REQUIRED_FIELDS",
    "S3EvidenceRoleContractError",
    "compile_s3_evidence_selection_context",
    "consume_s3_evidence_selection_output",
    "normalize_s3_evidence_selection_output",
    "validate_s3_evidence_selection_output",
]
