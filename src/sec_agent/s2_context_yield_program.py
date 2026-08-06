from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_representative_node_program import (
    compile_representative_node_program,
)
from sec_agent.s2_research_contract_program import (
    CASES,
    CELLS,
    validate_provider_judgment_choice,
)


POLICY_SCHEMA = "fin_ia_0_1_3_s2_03_context_yield_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s2_03_context_yield_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S2.context_yield_and_role_scoped_injection:v1"
S2_NATURAL_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s2_02_three_family_natural_canary_public_result_v1_0"
)
SYSTEM_INSTRUCTION = (
    "You are a bounded financial-research judgment selector. Return one JSON "
    "object only. Use only request-local aliases and enum values. Do not add "
    "fields, prose, markdown, numbers, dates, identities, or explanations."
)


class S2ContextYieldError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_context_yield_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("owning_stage") != "FIN_0_1_3_S2_03"
    ):
        raise S2ContextYieldError("s2_context_yield_policy_identity_invalid")
    gate = policy.get("capacity_gate") or {}
    if (
        gate.get("minimum_aggregate_character_reduction_ratio") != 0.25
        or gate.get("maximum_aggregate_compact_to_baseline_ratio") != 0.7
        or gate.get("maximum_per_request_compact_to_baseline_ratio") != 0.75
        or gate.get("maximum_candidate_options_per_request") != 8
    ):
        raise S2ContextYieldError("s2_context_yield_policy_capacity_invalid")
    natural = policy.get("natural_reproof") or {}
    if (
        natural.get("maximum_provider_calls") != 1
        or natural.get("retry_count") != 0
        or natural.get("fallback_count") != 0
        or natural.get("full_chain_calls") != 0
    ):
        raise S2ContextYieldError("s2_context_yield_policy_reproof_invalid")
    return policy


def compile_context_yield_program(
    *,
    policy: Mapping[str, Any],
    s2_decision: Mapping[str, Any],
    natural_result: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_policy(policy)
    representative = compile_representative_node_program(s2_decision=s2_decision)
    research = s2_decision["research_question_method_program"]
    _assert_natural_result(natural_result)
    natural_by_request = {
        str(row["request_id"]): deepcopy(row["provider_output"])
        for row in natural_result.get("family_results") or []
    }

    contexts: list[dict[str, Any]] = []
    baseline_characters = 0
    compact_characters = 0
    baseline_estimated_tokens = 0
    compact_estimated_tokens = 0
    for request in research.get("representative_requests") or []:
        compiled = compile_role_scoped_context(request)
        _validate_semantic_retention(request=request, compiled=compiled)
        fake = _fake_for_request(research, str(request["request_id"]))
        validate_compact_provider_output(fake, compiled=compiled)
        if request["request_id"] in natural_by_request:
            validate_provider_judgment_choice(
                natural_by_request[request["request_id"]], request=request
            )
            validate_compact_provider_output(
                natural_by_request[request["request_id"]], compiled=compiled
            )

        baseline_text = _prompt_text(request["model_visible_request"])
        compact_text = _prompt_text(compiled["model_context"])
        metrics = {
            "baseline_characters": len(baseline_text),
            "compact_characters": len(compact_text),
            "baseline_utf8_bytes": len(baseline_text.encode("utf-8")),
            "compact_utf8_bytes": len(compact_text.encode("utf-8")),
            "baseline_estimated_input_tokens": _estimate_tokens(baseline_text),
            "compact_estimated_input_tokens": _estimate_tokens(compact_text),
        }
        metrics["compact_to_baseline_character_ratio"] = round(
            metrics["compact_characters"] / metrics["baseline_characters"], 6
        )
        metrics["character_reduction_ratio"] = round(
            1 - metrics["compact_to_baseline_character_ratio"], 6
        )
        contexts.append({**compiled, "capacity": metrics})
        baseline_characters += metrics["baseline_characters"]
        compact_characters += metrics["compact_characters"]
        baseline_estimated_tokens += metrics["baseline_estimated_input_tokens"]
        compact_estimated_tokens += metrics["compact_estimated_input_tokens"]

    aggregate_ratio = round(compact_characters / baseline_characters, 6)
    capacity = {
        "request_count": len(contexts),
        "baseline_characters": baseline_characters,
        "compact_characters": compact_characters,
        "aggregate_compact_to_baseline_character_ratio": aggregate_ratio,
        "aggregate_character_reduction_ratio": round(1 - aggregate_ratio, 6),
        "baseline_estimated_input_tokens": baseline_estimated_tokens,
        "compact_estimated_input_tokens": compact_estimated_tokens,
        "estimated_input_token_reduction": (
            baseline_estimated_tokens - compact_estimated_tokens
        ),
        "maximum_compact_estimated_input_tokens": max(
            row["capacity"]["compact_estimated_input_tokens"] for row in contexts
        ),
    }
    _assert_capacity(policy=policy, contexts=contexts, capacity=capacity)

    counts = _semantic_counts(contexts)
    natural_selected = list(natural_by_request)
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "s2_decision_record_digest": s2_decision["record_digest"],
        "s2_representative_program_digest": representative["program_digest"],
        "s2_02_natural_result_digest": natural_result["record_digest"],
        "system_instruction": SYSTEM_INSTRUCTION,
        "role_scoped_contexts": contexts,
        "capacity": capacity,
        "semantic_retention": {
            **counts,
            "evidence_alias_retention_ratio": 1.0,
            "gap_alias_retention_ratio": 1.0,
            "mechanism_alias_retention_ratio": 1.0,
            "what_would_change_alias_retention_ratio": 1.0,
            "counterevidence_and_gap_hidden_for_capacity": False,
            "candidate_ids_digests_and_slot_ids_model_visible": False,
            "full_lineage_retained_in_local_sidecar": True,
        },
        "natural_output_compatibility": {
            "S2_02_actual_outputs_revalidated_against_compact_contract": len(
                natural_selected
            ),
            "request_ids": natural_selected,
            "compact_bytes_seen_by_model": False,
            "one_call_natural_reproof_required": True,
            "selected_request_id": policy["natural_reproof"][
                "selected_request_id"
            ],
        },
        "historical_baseline": deepcopy(
            policy["historical_fin_0_1_2_baseline"]
        ),
        "observed_counts": {
            "cases": len(CASES),
            "representative_requests": len(contexts),
            "natural_outputs_revalidated": len(natural_selected),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "business_runs": 0,
        },
        "method_lifecycle": {
            "documented": True,
            "contract_translated": True,
            "fixture_proven": True,
            "runtime_injected_into_representative_node": True,
            "node_level_consumed": True,
            "paid_artifact_proven_for_compact_bytes": False,
            "dogfood_accepted": False,
        },
        "stage_boundary": {
            "S2_03_zero_call": "engineering_pass",
            "S2_03_natural_reproof": "required_not_run",
            "S3_dynamic_decision_surface": "not_started",
            "eight_dimension_content_quality": "not_proven",
            "full_chain_authorized": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_context_yield_program(
        program,
        policy=policy,
        s2_decision=s2_decision,
        natural_result=natural_result,
    )
    return program


def compile_role_scoped_context(request: Mapping[str, Any]) -> dict[str, Any]:
    visible = request.get("model_visible_request")
    if not isinstance(visible, Mapping):
        raise S2ContextYieldError("s2_context_yield_request_invalid")
    contract = visible.get("provider_output_contract") or {}
    evidence = [_compact_evidence(row) for row in visible.get("evidence_aliases") or []]
    gaps = [
        {
            "alias": row["alias"],
            "cannot_infer": row["cannot_infer"],
            "source_exhaustion_proven": bool(row["source_exhaustion_proven"]),
        }
        for row in visible.get("gap_aliases") or []
    ]
    model_context = {
        "case_key": visible["case_key"],
        "company_name": visible["company_name"],
        "program_cell_id": visible["program_cell_id"],
        "decision_question": visible["decision_question"],
        "method_steps": deepcopy(visible["method_steps"]),
        "evidence_options": evidence,
        "gap_options": gaps,
        "mechanism_options": deepcopy(visible["mechanism_aliases"]),
        "what_would_change_options": deepcopy(
            visible["what_would_change_aliases"]
        ),
        "output_contract": {
            "required_fields": deepcopy(contract["required_fields"]),
            "epistemic_states": deepcopy(contract["epistemic_states"]),
            "answer_directions": deepcopy(contract["answer_directions"]),
            "confidence_values": deepcopy(contract["confidence_values"]),
            "additional_properties": False,
        },
    }
    sidecar = {
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "s1_query_digest": request["s1_query_digest"],
        "local_render_authority": deepcopy(request["local_render_authority"]),
        "evidence_alias_authority": {
            str(row["alias"]): deepcopy(dict(row))
            for row in visible.get("evidence_aliases") or []
        },
        "gap_alias_authority": {
            str(row["alias"]): deepcopy(dict(row))
            for row in visible.get("gap_aliases") or []
        },
    }
    body = {
        "schema_version": "fin_ia_0_1_3_s2_03_role_scoped_context_v1_0",
        "request_id": request["request_id"],
        "source_request_digest": request["request_digest"],
        "model_context": model_context,
        "local_authority_sidecar": sidecar,
    }
    return {**body, "context_digest": canonical_digest(body)}


def validate_compact_provider_output(
    provider_output: Mapping[str, Any], *, compiled: Mapping[str, Any]
) -> None:
    context = compiled.get("model_context") or {}
    contract = context.get("output_contract") or {}
    if set(provider_output) != set(contract.get("required_fields") or []):
        raise S2ContextYieldError("s2_compact_output_shape_invalid")
    for field, allowed_key in (
        ("epistemic_state", "epistemic_states"),
        ("answer_direction", "answer_directions"),
        ("confidence", "confidence_values"),
    ):
        if provider_output.get(field) not in contract.get(allowed_key, []):
            raise S2ContextYieldError("s2_compact_output_enum_invalid")
    authorities = {
        "mechanism_alias": _aliases(context, "mechanism_options"),
        "support_aliases": _aliases(context, "evidence_options"),
        "counterevidence_aliases": _aliases(context, "evidence_options"),
        "gap_aliases": _aliases(context, "gap_options"),
        "what_would_change_aliases": _aliases(
            context, "what_would_change_options"
        ),
    }
    if provider_output.get("mechanism_alias") not in authorities["mechanism_alias"]:
        raise S2ContextYieldError("s2_compact_output_mechanism_invalid")
    for field in (
        "support_aliases",
        "counterevidence_aliases",
        "gap_aliases",
        "what_would_change_aliases",
    ):
        values = provider_output.get(field)
        if (
            not isinstance(values, list)
            or len(values) != len(set(values))
            or not set(values).issubset(authorities[field])
        ):
            raise S2ContextYieldError("s2_compact_output_alias_invalid")
    if not provider_output["support_aliases"] and not provider_output["gap_aliases"]:
        raise S2ContextYieldError("s2_compact_output_unbounded")
    if (
        provider_output["epistemic_state"] == "cannot_infer"
        and provider_output["support_aliases"]
    ):
        raise S2ContextYieldError("s2_compact_output_cannot_infer_support")


def validate_context_yield_program(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    s2_decision: Mapping[str, Any],
    natural_result: Mapping[str, Any],
) -> None:
    _assert_policy(policy)
    _assert_natural_result(natural_result)
    body = {
        key: deepcopy(value)
        for key, value in program.items()
        if key != "program_digest"
    }
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("s2_decision_record_digest") != s2_decision.get("record_digest")
        or program.get("s2_02_natural_result_digest")
        != natural_result.get("record_digest")
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S2ContextYieldError("s2_context_yield_program_authority_invalid")
    contexts = program.get("role_scoped_contexts") or []
    if len(contexts) != 9:
        raise S2ContextYieldError("s2_context_yield_context_count_invalid")
    requests = s2_decision["research_question_method_program"][
        "representative_requests"
    ]
    request_map = {str(row["request_id"]): row for row in requests}
    for compiled in contexts:
        request = request_map.get(str(compiled.get("request_id") or ""))
        if request is None:
            raise S2ContextYieldError("s2_context_yield_request_binding_invalid")
        context_body = {
            key: deepcopy(value)
            for key, value in compiled.items()
            if key not in {"context_digest", "capacity"}
        }
        if compiled.get("context_digest") != canonical_digest(context_body):
            raise S2ContextYieldError("s2_context_yield_context_digest_invalid")
        _validate_semantic_retention(request=request, compiled=compiled)
    _assert_capacity(
        policy=policy,
        contexts=contexts,
        capacity=program.get("capacity") or {},
    )


def _compact_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    if row.get("financial_fact_authority"):
        authority = "financial_fact"
    elif row.get("relationship_fact_only"):
        authority = "relationship_fact_only"
    else:
        authority = "semantic_evidence"
    compact = {
        "alias": row["alias"],
        "role": row["candidate_role"],
        "claim_boundary": row["claim_boundary"],
        "authority": authority,
    }
    for source, target in (
        ("metric_family", "metric_family"),
        ("edge_type", "edge_type"),
        ("target_entity_id", "target_entity"),
    ):
        if row.get(source) is not None:
            compact[target] = row[source]
    return compact


def _validate_semantic_retention(
    *, request: Mapping[str, Any], compiled: Mapping[str, Any]
) -> None:
    visible = request["model_visible_request"]
    context = compiled.get("model_context") or {}
    sidecar = compiled.get("local_authority_sidecar") or {}
    if (
        context.get("case_key") != visible.get("case_key")
        or context.get("company_name") != visible.get("company_name")
        or context.get("program_cell_id") != visible.get("program_cell_id")
        or context.get("decision_question") != visible.get("decision_question")
        or context.get("method_steps") != visible.get("method_steps")
    ):
        raise S2ContextYieldError("s2_context_yield_question_or_method_loss")
    pairs: Sequence[tuple[str, str]] = (
        ("evidence_aliases", "evidence_options"),
        ("gap_aliases", "gap_options"),
        ("mechanism_aliases", "mechanism_options"),
        ("what_would_change_aliases", "what_would_change_options"),
    )
    for source, target in pairs:
        if _aliases(visible, source) != _aliases(context, target):
            raise S2ContextYieldError("s2_context_yield_alias_loss")
    evidence_source = {
        str(row["alias"]): row for row in visible.get("evidence_aliases") or []
    }
    evidence_context = {
        str(row["alias"]): row for row in context.get("evidence_options") or []
    }
    for alias, row in evidence_source.items():
        projected = evidence_context[alias]
        if projected != _compact_evidence(row):
            raise S2ContextYieldError("s2_context_yield_evidence_semantic_loss")
    gap_source = {
        str(row["alias"]): row for row in visible.get("gap_aliases") or []
    }
    gap_context = {
        str(row["alias"]): row for row in context.get("gap_options") or []
    }
    for alias, row in gap_source.items():
        if (
            gap_context[alias].get("cannot_infer") != row.get("cannot_infer")
            or gap_context[alias].get("source_exhaustion_proven")
            != row.get("source_exhaustion_proven")
        ):
            raise S2ContextYieldError("s2_context_yield_gap_semantic_loss")
    serialized = _canonical_json(context)
    if any(
        forbidden in serialized
        for forbidden in (
            "candidate_id",
            "candidate_digest",
            "slot_id",
            "gap_code",
            "request_digest",
            "s1_query_digest",
        )
    ):
        raise S2ContextYieldError("s2_context_yield_local_field_leak")
    if (
        sidecar.get("request_digest") != request.get("request_digest")
        or sidecar.get("s1_query_digest") != request.get("s1_query_digest")
        or set(sidecar.get("evidence_alias_authority") or {})
        != _aliases(visible, "evidence_aliases")
        or set(sidecar.get("gap_alias_authority") or {})
        != _aliases(visible, "gap_aliases")
    ):
        raise S2ContextYieldError("s2_context_yield_local_lineage_loss")


def _assert_capacity(
    *,
    policy: Mapping[str, Any],
    contexts: Sequence[Mapping[str, Any]],
    capacity: Mapping[str, Any],
) -> None:
    gate = policy["capacity_gate"]
    if (
        capacity.get("aggregate_compact_to_baseline_character_ratio", 1)
        > gate["maximum_aggregate_compact_to_baseline_ratio"]
        or capacity.get("aggregate_character_reduction_ratio", 0)
        < gate["minimum_aggregate_character_reduction_ratio"]
        or any(
            row.get("capacity", {}).get(
                "compact_to_baseline_character_ratio", 1
            )
            > gate["maximum_per_request_compact_to_baseline_ratio"]
            for row in contexts
        )
        or any(
            len(row.get("model_context", {}).get("evidence_options") or [])
            > gate["maximum_candidate_options_per_request"]
            for row in contexts
        )
    ):
        raise S2ContextYieldError("s2_context_yield_capacity_gate_failed")


def _semantic_counts(contexts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "evidence_aliases_retained": sum(
            len(row["model_context"]["evidence_options"]) for row in contexts
        ),
        "gap_aliases_retained": sum(
            len(row["model_context"]["gap_options"]) for row in contexts
        ),
        "mechanism_aliases_retained": sum(
            len(row["model_context"]["mechanism_options"]) for row in contexts
        ),
        "what_would_change_aliases_retained": sum(
            len(row["model_context"]["what_would_change_options"])
            for row in contexts
        ),
    }


def _assert_policy(policy: Mapping[str, Any]) -> None:
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
    ):
        raise S2ContextYieldError("s2_context_yield_policy_invalid")


def _assert_natural_result(result: Mapping[str, Any]) -> None:
    body = {
        key: deepcopy(value)
        for key, value in result.items()
        if key != "record_digest"
    }
    if (
        result.get("schema_version") != S2_NATURAL_RESULT_SCHEMA
        or result.get("record_digest") != canonical_digest(body)
        or result.get("disposition", {}).get("S2_02") != "pass_closed"
        or len(result.get("family_results") or []) != 3
    ):
        raise S2ContextYieldError("s2_context_yield_natural_result_invalid")


def _fake_for_request(
    research: Mapping[str, Any], request_id: str
) -> Mapping[str, Any]:
    row = next(
        (
            item
            for item in research.get("fake_provider_outputs") or []
            if item.get("request_id") == request_id
        ),
        None,
    )
    if row is None:
        raise S2ContextYieldError("s2_context_yield_fake_missing")
    return row["provider_output"]


def _aliases(value: Mapping[str, Any], field: str) -> set[str]:
    return {str(row["alias"]) for row in value.get(field) or []}


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _prompt_text(value: Mapping[str, Any]) -> str:
    return SYSTEM_INSTRUCTION + "\n" + _canonical_json(value)


def _estimate_tokens(value: str) -> int:
    return max(
        1,
        (len(value.encode("utf-8")) + 3) // 4,
        (len(value) + 1) // 2,
    )


__all__ = [
    "CONTRACT_REF",
    "PROGRAM_SCHEMA",
    "S2ContextYieldError",
    "compile_context_yield_program",
    "compile_role_scoped_context",
    "load_context_yield_policy",
    "validate_compact_provider_output",
    "validate_context_yield_program",
]
