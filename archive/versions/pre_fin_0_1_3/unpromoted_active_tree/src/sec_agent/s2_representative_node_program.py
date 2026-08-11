from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_research_contract_program import (
    CASES,
    CELLS,
    CONTRACT_REF as S2_RESEARCH_CONTRACT_REF,
    S2ResearchContractError,
    validate_provider_judgment_choice,
)


PROGRAM_SCHEMA = "fin_ia_0_1_3_s2_representative_node_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S2.representative_evidence_claim_lead_node:v1"
S2_DECISION_SCHEMA = (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0"
)


class S2RepresentativeNodeError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def compile_representative_node_program(
    *,
    s2_decision: Mapping[str, Any],
    provider_outputs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    research_program = _assert_s2_decision_authority(s2_decision)
    fake_by_request = {
        str(row["request_id"]): deepcopy(row["provider_output"])
        for row in research_program.get("fake_provider_outputs") or []
    }
    output_by_request = {
        **fake_by_request,
        **{
            str(request_id): deepcopy(output)
            for request_id, output in (provider_outputs or {}).items()
        },
    }

    executions: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    for request in research_program.get("representative_requests") or []:
        request_id = str(request.get("request_id") or "")
        provider_output = output_by_request.get(request_id)
        if not isinstance(provider_output, Mapping):
            raise S2RepresentativeNodeError("representative_provider_output_missing")
        node_input = build_representative_node_input(request)
        claim = consume_representative_specialist_output(
            request=request,
            provider_output=provider_output,
        )
        executions.append(
            {
                "node_id": f"representative_specialist::{request_id}",
                "node_type": "representative_specialist_judgment_choice",
                "input_digest": node_input["node_input_digest"],
                "request_id": request_id,
                "request_digest": request["request_digest"],
                "provider_output_digest": canonical_digest(provider_output),
                "claim_id": claim["claim_id"],
                "claim_digest": claim["claim_digest"],
                "status": "consumed",
            }
        )
        claims.append(claim)

    leads = [
        synthesize_representative_lead(case_key, claims)
        for case_key in CASES
    ]
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "s2_research_contract_ref": S2_RESEARCH_CONTRACT_REF,
        "s2_decision_record_digest": s2_decision["record_digest"],
        "s2_research_program_digest": research_program["program_digest"],
        "context_injection_contract": {
            "authority": "explicit_current_governed_pack",
            "repository_environment_autoload": False,
            "implicit_working_directory_reads": False,
            "request_digest_required": True,
            "provider_may_expand_evidence_surface": False,
            "provider_may_author_final_narrative": False,
        },
        "node_executions": executions,
        "materialized_claims": claims,
        "lead_syntheses": leads,
        "observed_counts": {
            "representative_specialist_nodes": len(executions),
            "materialized_claims": len(claims),
            "representative_lead_nodes": len(leads),
            "case_count": len(CASES),
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
            "paid_artifact_proven": False,
            "dogfood_accepted": False,
        },
        "stage_boundary": {
            "S2_02_zero_call_node_consumption": "pass",
            "natural_output_canary": "not_run",
            "S2_03_context_economy": "not_started",
            "S3_dynamic_decision_surface": "not_started",
            "eight_dimension_final_content_quality": "not_proven",
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_representative_node_program(program, s2_decision=s2_decision)
    return program


def build_representative_node_input(request: Mapping[str, Any]) -> dict[str, Any]:
    _assert_request_shape(request)
    body = {
        "schema_version": "fin_ia_0_1_3_s2_representative_node_input_v1_0",
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "s1_query_digest": request["s1_query_digest"],
        "context_authority": "explicit_current_governed_pack",
        "repository_environment_autoload": False,
        "model_visible_request": deepcopy(request["model_visible_request"]),
    }
    return {**body, "node_input_digest": canonical_digest(body)}


def consume_representative_specialist_output(
    *,
    request: Mapping[str, Any],
    provider_output: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_request_shape(request)
    try:
        validate_provider_judgment_choice(provider_output, request=request)
    except S2ResearchContractError as exc:
        raise S2RepresentativeNodeError(exc.code) from exc

    visible = request["model_visible_request"]
    mechanism_map = _alias_map(visible, "mechanism_aliases")
    evidence_map = _alias_map(visible, "evidence_aliases")
    gap_map = _alias_map(visible, "gap_aliases")
    wwc_map = _alias_map(visible, "what_would_change_aliases")
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
        "support_evidence": _resolve_aliases(
            provider_output["support_aliases"], evidence_map
        ),
        "counterevidence": _resolve_aliases(
            provider_output["counterevidence_aliases"], evidence_map
        ),
        "typed_gaps": _resolve_aliases(provider_output["gap_aliases"], gap_map),
        "what_would_change": _resolve_aliases(
            provider_output["what_would_change_aliases"], wwc_map
        ),
        "provider_free_text_fields": [],
        "local_truth_ownership": deepcopy(request["local_render_authority"]),
        "lineage": {
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "s1_query_digest": request["s1_query_digest"],
            "provider_output_digest": canonical_digest(provider_output),
        },
    }
    claim_id = "fin013_s2_claim_" + canonical_digest(claim_body)[:24]
    claim_with_id = {"claim_id": claim_id, **claim_body}
    return {
        **claim_with_id,
        "claim_digest": canonical_digest(claim_with_id),
    }


def synthesize_representative_lead(
    case_key: str,
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    selected = sorted(
        [deepcopy(row) for row in claims if row.get("case_key") == case_key],
        key=lambda row: CELLS.index(str(row.get("program_cell_id"))),
    )
    if [row.get("program_cell_id") for row in selected] != list(CELLS):
        raise S2RepresentativeNodeError("representative_lead_claim_surface_incomplete")

    by_cell = {str(row["program_cell_id"]): row for row in selected}
    dependencies = []
    if by_cell[CELLS[0]]["support_evidence"] and by_cell[CELLS[1]]["support_evidence"]:
        dependencies.append(
            {
                "from_claim_id": by_cell[CELLS[0]]["claim_id"],
                "to_claim_id": by_cell[CELLS[1]]["claim_id"],
                "reason": "value_capture_judgment_depends_on_demand_evidence",
            }
        )
    conflicts = []
    directions = {str(row["answer_direction"]) for row in selected}
    if len(directions - {"cannot_infer"}) > 1:
        conflicts.append(
            {
                "claim_ids": [row["claim_id"] for row in selected],
                "reason": "cross_cell_direction_divergence_requires_S3_adjudication",
                "disposition": "defer_to_dynamic_decision_surface",
            }
        )
    gaps = [
        {"claim_id": row["claim_id"], **gap}
        for row in selected
        for gap in row["typed_gaps"]
    ]
    lead_body = {
        "case_key": case_key,
        "specialist_claim_refs": [row["claim_id"] for row in selected],
        "dependencies": dependencies,
        "conflicts": conflicts,
        "typed_gaps": gaps,
        "what_would_change": [
            {"claim_id": row["claim_id"], **condition}
            for row in selected
            for condition in row["what_would_change"]
        ],
        "lead_boundary": (
            "Representative S2 synthesis only; S3 owns dynamic cells, semantic "
            "adjudication, final narrative and eight-dimension content quality."
        ),
    }
    lead_id = "fin013_s2_lead_" + canonical_digest(lead_body)[:24]
    lead_with_id = {"lead_id": lead_id, **lead_body}
    return {**lead_with_id, "lead_digest": canonical_digest(lead_with_id)}


def validate_representative_node_program(
    program: Mapping[str, Any],
    *,
    s2_decision: Mapping[str, Any],
) -> None:
    research_program = _assert_s2_decision_authority(s2_decision)
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("s2_decision_record_digest") != s2_decision["record_digest"]
        or program.get("s2_research_program_digest") != research_program["program_digest"]
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S2RepresentativeNodeError("representative_program_authority_invalid")
    injection = program.get("context_injection_contract") or {}
    if (
        injection.get("authority") != "explicit_current_governed_pack"
        or injection.get("repository_environment_autoload") is not False
        or injection.get("implicit_working_directory_reads") is not False
    ):
        raise S2RepresentativeNodeError("representative_context_injection_invalid")
    executions = program.get("node_executions") or []
    claims = program.get("materialized_claims") or []
    leads = program.get("lead_syntheses") or []
    if len(executions) != 9 or len(claims) != 9 or len(leads) != 3:
        raise S2RepresentativeNodeError("representative_node_counts_invalid")
    if {row.get("case_key") for row in claims} != set(CASES):
        raise S2RepresentativeNodeError("representative_claim_cases_invalid")
    request_by_id = {
        str(row["request_id"]): row
        for row in research_program.get("representative_requests") or []
    }
    claim_by_id = {str(row["claim_id"]): row for row in claims}
    for claim in claims:
        claim_without_digest = {
            key: deepcopy(value)
            for key, value in claim.items()
            if key != "claim_digest"
        }
        if claim.get("claim_digest") != canonical_digest(claim_without_digest):
            raise S2RepresentativeNodeError("representative_claim_digest_invalid")
        if claim.get("provider_free_text_fields") != []:
            raise S2RepresentativeNodeError("representative_provider_free_text_forbidden")
        if not claim.get("support_evidence") and not claim.get("typed_gaps"):
            raise S2RepresentativeNodeError("representative_claim_unbounded")
    for execution in executions:
        request = request_by_id.get(str(execution.get("request_id") or ""))
        claim = claim_by_id.get(str(execution.get("claim_id") or ""))
        if request is None or claim is None:
            raise S2RepresentativeNodeError("representative_execution_binding_invalid")
        node_input = build_representative_node_input(request)
        if (
            execution.get("input_digest") != node_input["node_input_digest"]
            or execution.get("request_digest") != request["request_digest"]
            or execution.get("claim_digest") != claim["claim_digest"]
        ):
            raise S2RepresentativeNodeError("representative_execution_digest_invalid")
    for lead in leads:
        lead_without_digest = {
            key: deepcopy(value) for key, value in lead.items() if key != "lead_digest"
        }
        if lead.get("lead_digest") != canonical_digest(lead_without_digest):
            raise S2RepresentativeNodeError("representative_lead_digest_invalid")
        if len(lead.get("specialist_claim_refs") or []) != 3:
            raise S2RepresentativeNodeError("representative_lead_inputs_invalid")


def _assert_s2_decision_authority(
    s2_decision: Mapping[str, Any],
) -> Mapping[str, Any]:
    body = {
        key: deepcopy(value)
        for key, value in s2_decision.items()
        if key != "record_digest"
    }
    program = s2_decision.get("research_question_method_program")
    if (
        s2_decision.get("schema_version") != S2_DECISION_SCHEMA
        or s2_decision.get("status")
        != "S2_01_engineering_pass_S2_02_representative_node_eval_next"
        or not isinstance(program, Mapping)
        or program.get("contract_ref") != S2_RESEARCH_CONTRACT_REF
        or s2_decision.get("record_digest") != canonical_digest(body)
    ):
        raise S2RepresentativeNodeError("s2_decision_authority_invalid")
    return program


def _assert_request_shape(request: Mapping[str, Any]) -> None:
    visible = request.get("model_visible_request")
    if (
        not request.get("request_id")
        or not request.get("request_digest")
        or not request.get("s1_query_digest")
        or not isinstance(visible, Mapping)
        or visible.get("case_key") != request.get("case_key")
        or visible.get("program_cell_id") != request.get("program_cell_id")
    ):
        raise S2RepresentativeNodeError("representative_request_invalid")


def _alias_map(visible: Mapping[str, Any], field: str) -> dict[str, dict[str, Any]]:
    return {
        str(row["alias"]): deepcopy(dict(row))
        for row in visible.get(field) or []
    }


def _resolve_aliases(
    aliases: Sequence[str],
    authority: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [deepcopy(dict(authority[str(alias)])) for alias in aliases]


__all__ = [
    "CONTRACT_REF",
    "PROGRAM_SCHEMA",
    "S2RepresentativeNodeError",
    "build_representative_node_input",
    "compile_representative_node_program",
    "consume_representative_specialist_output",
    "synthesize_representative_lead",
    "validate_representative_node_program",
]
