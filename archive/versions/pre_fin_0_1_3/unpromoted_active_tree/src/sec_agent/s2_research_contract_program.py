from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.prompt_metadata_contract import (
    PROMPT_METADATA_TYPE_POLICY_REF,
    compact_prompt_metadata,
    prompt_metadata_type_policy,
    validate_prompt_metadata_types,
)
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


POLICY_SCHEMA = "fin_ia_0_1_3_s2_research_question_method_contract_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s2_research_question_method_contract_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S2.research_question_method_and_judgment_choice:v1"
S1_CONTRACT_REF = "fin_0_1_3.S1.retrieval_evidence_usefulness_and_closeout:v1"
CASES = ("DELL", "MU", "NVDA")
CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)


class S2ResearchContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s2_research_contract_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("s1_contract_ref") != S1_CONTRACT_REF
        or policy.get("metadata_type_policy_ref")
        != PROMPT_METADATA_TYPE_POLICY_REF
        or tuple(policy.get("representative_cell_scope") or ()) != CELLS
        or tuple(sorted(policy.get("case_profiles") or {})) != CASES
    ):
        raise S2ResearchContractError("s2_research_contract_policy_invalid")
    provider = policy.get("provider_output_contract")
    if not isinstance(provider, Mapping):
        raise S2ResearchContractError("s2_provider_contract_missing")
    required_fields = tuple(provider.get("required_fields") or ())
    if len(required_fields) != 8 or len(set(required_fields)) != 8:
        raise S2ResearchContractError("s2_provider_required_fields_invalid")
    if not provider.get("forbidden_provider_fields") or not provider.get(
        "local_ownership"
    ):
        raise S2ResearchContractError("s2_provider_authority_boundary_missing")
    mechanism_atoms: set[str] = set()
    for case_key in CASES:
        profile = policy["case_profiles"][case_key]
        if not profile.get("company_name") or tuple(profile.get("cells") or ()) != CELLS:
            raise S2ResearchContractError("s2_case_profile_invalid")
        for cell_id in CELLS:
            cell = profile["cells"][cell_id]
            mechanisms = cell.get("mechanism_aliases")
            wwc = cell.get("what_would_change_aliases")
            if (
                not cell.get("decision_question")
                or len(cell.get("method_steps") or ()) < 2
                or not isinstance(mechanisms, Mapping)
                or len(mechanisms) < 2
                or not isinstance(wwc, Mapping)
                or len(wwc) < 2
            ):
                raise S2ResearchContractError("s2_case_cell_contract_invalid")
            for alias, atom in mechanisms.items():
                company_anchor = str(profile["company_name"]).split()[0].lower()
                atom_text = str(atom)
                if not str(alias).startswith(f"{case_key}_M_") or not atom_text.lower().startswith(
                    (case_key.lower(), company_anchor)
                ):
                    raise S2ResearchContractError(
                        "s2_company_specific_mechanism_invalid"
                    )
                if atom in mechanism_atoms:
                    raise S2ResearchContractError(
                        "s2_cross_case_generic_mechanism_duplicate"
                    )
                mechanism_atoms.add(str(atom))
            if any(not str(alias).startswith(f"{case_key}_W_") for alias in wwc):
                raise S2ResearchContractError("s2_wwc_alias_case_scope_invalid")
    return policy


def compile_s2_research_question_method_program(
    *,
    policy: Mapping[str, Any],
    s1_decision: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_s1_authority(s1_decision)
    query_results = (
        s1_decision["retrieval_usefulness_program"].get("query_results") or []
    )
    query_map = {
        (str(row.get("case_key")), str(row.get("cell_id"))): row
        for row in query_results
    }
    if set(query_map) != {(case, cell) for case in CASES for cell in CELLS}:
        raise S2ResearchContractError("s2_s1_query_surface_incomplete")

    provider_contract = _compile_provider_contract(
        policy["provider_output_contract"]
    )
    requests: list[dict[str, Any]] = []
    fake_outputs: list[dict[str, Any]] = []
    for case_key in CASES:
        profile = policy["case_profiles"][case_key]
        for cell_id in CELLS:
            query = query_map[(case_key, cell_id)]
            request = _compile_request(
                case_key=case_key,
                company_name=str(profile["company_name"]),
                cell_id=cell_id,
                cell_policy=profile["cells"][cell_id],
                query=query,
                provider_contract=provider_contract,
            )
            fake = compile_fake_provider_output(request)
            validate_provider_judgment_choice(fake, request=request)
            requests.append(request)
            fake_outputs.append(
                {
                    "request_id": request["request_id"],
                    "provider_output": fake,
                    "validation_status": "pass",
                    "fake_digest": canonical_digest(fake),
                }
            )

    observed = {
        "case_count": len(CASES),
        "representative_request_count": len(requests),
        "selected_candidate_alias_count": sum(
            len(row["model_visible_request"]["evidence_aliases"])
            for row in requests
        ),
        "typed_gap_alias_count": sum(
            len(row["model_visible_request"]["gap_aliases"])
            for row in requests
        ),
        "company_specific_mechanism_choice_count": sum(
            len(row["model_visible_request"]["mechanism_aliases"])
            for row in requests
        ),
        "fake_provider_pass_count": len(fake_outputs),
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "s1_decision_record_digest": s1_decision["record_digest"],
        "s1_retrieval_program_digest": s1_decision[
            "retrieval_usefulness_program"
        ]["program_digest"],
        "metadata_type_policy": prompt_metadata_type_policy(),
        "provider_contract": provider_contract,
        "representative_requests": requests,
        "fake_provider_outputs": fake_outputs,
        "observed_counts": observed,
        "method_lifecycle": {
            "documented": True,
            "contract_translated": True,
            "fixture_proven": True,
            "runtime_injected_into_representative_node": False,
            "node_level_consumed": False,
            "paid_artifact_proven": False,
            "dogfood_accepted": False,
        },
        "stage_boundary": {
            "S2_01": "engineering_pass_contract_translated_fixture_proven",
            "S2_02": "representative_node_runtime_injection_and_eval_next",
            "S3_dynamic_decision_surface": "not_started",
            "fixed_three_cells_are_final_product_plan": False,
            "model_or_full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s2_research_question_method_program(
        program,
        policy=policy,
        s1_decision=s1_decision,
    )
    return program


def compile_fake_provider_output(request: Mapping[str, Any]) -> dict[str, Any]:
    visible = request.get("model_visible_request") or {}
    evidence = [str(row["alias"]) for row in visible.get("evidence_aliases") or []]
    gaps = [str(row["alias"]) for row in visible.get("gap_aliases") or []]
    mechanisms = [
        str(row["alias"]) for row in visible.get("mechanism_aliases") or []
    ]
    wwc = [
        str(row["alias"])
        for row in visible.get("what_would_change_aliases") or []
    ]
    cell_id = str(visible.get("program_cell_id") or "")
    if evidence and gaps:
        epistemic_state = "mixed_evidence"
        direction = "mixed"
    elif evidence:
        epistemic_state = "bounded_inference"
        direction = (
            "negative"
            if cell_id == "bottleneck_counterevidence_and_what_would_change"
            else "positive"
        )
    else:
        epistemic_state = "cannot_infer"
        direction = "cannot_infer"
    return {
        "epistemic_state": epistemic_state,
        "answer_direction": direction,
        "mechanism_alias": mechanisms[0],
        "support_aliases": evidence,
        "counterevidence_aliases": (
            evidence
            if cell_id == "bottleneck_counterevidence_and_what_would_change"
            else []
        ),
        "gap_aliases": gaps,
        "confidence": "medium" if evidence else "low",
        "what_would_change_aliases": wwc[:1],
    }


def validate_provider_judgment_choice(
    provider_output: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
) -> None:
    visible = request.get("model_visible_request")
    if not isinstance(visible, Mapping):
        raise S2ResearchContractError("s2_model_visible_request_missing")
    contract = visible.get("provider_output_contract")
    if not isinstance(contract, Mapping):
        raise S2ResearchContractError("s2_provider_output_contract_missing")
    required_fields = tuple(contract.get("required_fields") or ())
    if set(provider_output) != set(required_fields):
        raise S2ResearchContractError("s2_provider_output_shape_invalid")
    if provider_output.get("epistemic_state") not in contract.get(
        "epistemic_states", []
    ):
        raise S2ResearchContractError("s2_provider_epistemic_state_invalid")
    if provider_output.get("answer_direction") not in contract.get(
        "answer_directions", []
    ):
        raise S2ResearchContractError("s2_provider_answer_direction_invalid")
    if provider_output.get("confidence") not in contract.get(
        "confidence_values", []
    ):
        raise S2ResearchContractError("s2_provider_confidence_invalid")

    authorities = {
        "mechanism_alias": {
            str(row["alias"]) for row in visible.get("mechanism_aliases") or []
        },
        "support_aliases": {
            str(row["alias"]) for row in visible.get("evidence_aliases") or []
        },
        "counterevidence_aliases": {
            str(row["alias"]) for row in visible.get("evidence_aliases") or []
        },
        "gap_aliases": {
            str(row["alias"]) for row in visible.get("gap_aliases") or []
        },
        "what_would_change_aliases": {
            str(row["alias"])
            for row in visible.get("what_would_change_aliases") or []
        },
    }
    mechanism = provider_output.get("mechanism_alias")
    if not isinstance(mechanism, str) or mechanism not in authorities[
        "mechanism_alias"
    ]:
        raise S2ResearchContractError("s2_provider_mechanism_alias_invalid")
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
            or any(not isinstance(value, str) for value in values)
            or not set(values).issubset(authorities[field])
        ):
            raise S2ResearchContractError(f"s2_provider_{field}_invalid")
    if not provider_output["support_aliases"] and not provider_output["gap_aliases"]:
        raise S2ResearchContractError("s2_provider_unbounded_choice")
    if provider_output["epistemic_state"] == "cannot_infer" and provider_output[
        "support_aliases"
    ]:
        raise S2ResearchContractError("s2_cannot_infer_support_forbidden")


def validate_s2_research_question_method_program(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    s1_decision: Mapping[str, Any],
) -> None:
    _assert_s1_authority(s1_decision)
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("s1_decision_record_digest")
        != s1_decision["record_digest"]
        or program.get("s1_retrieval_program_digest")
        != s1_decision["retrieval_usefulness_program"]["program_digest"]
    ):
        raise S2ResearchContractError("s2_program_authority_binding_invalid")
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if program.get("program_digest") != canonical_digest(body):
        raise S2ResearchContractError("s2_program_digest_invalid")
    if program.get("metadata_type_policy") != prompt_metadata_type_policy():
        raise S2ResearchContractError("s2_metadata_policy_drift")
    if program.get("provider_contract") != _compile_provider_contract(
        policy["provider_output_contract"]
    ):
        raise S2ResearchContractError("s2_provider_contract_drift")

    requests = program.get("representative_requests") or []
    if len(requests) != 9:
        raise S2ResearchContractError("s2_representative_request_count_invalid")
    request_map = {
        (row["case_key"], row["program_cell_id"]): row for row in requests
    }
    if set(request_map) != {(case, cell) for case in CASES for cell in CELLS}:
        raise S2ResearchContractError("s2_representative_request_surface_invalid")
    mechanism_atoms: set[str] = set()
    for (case_key, cell_id), request in request_map.items():
        request_body = {
            key: deepcopy(value)
            for key, value in request.items()
            if key != "request_digest"
        }
        if request.get("request_digest") != canonical_digest(request_body):
            raise S2ResearchContractError("s2_request_digest_invalid")
        visible = request.get("model_visible_request") or {}
        if visible.get("case_key") != case_key or visible.get(
            "program_cell_id"
        ) != cell_id:
            raise S2ResearchContractError("s2_request_case_cell_binding_invalid")
        validate_prompt_metadata_types(visible.get("typed_metadata") or {})
        for row in visible.get("mechanism_aliases") or []:
            if not str(row.get("alias") or "").startswith(f"{case_key}_M_"):
                raise S2ResearchContractError("s2_cross_case_mechanism_alias")
            atom = str(row.get("atom") or "")
            if not atom or atom in mechanism_atoms:
                raise S2ResearchContractError("s2_generic_mechanism_collision")
            mechanism_atoms.add(atom)
        _assert_local_aliases(visible, case_key=case_key)

    fake_rows = program.get("fake_provider_outputs") or []
    if len(fake_rows) != 9:
        raise S2ResearchContractError("s2_fake_provider_count_invalid")
    for row in fake_rows:
        request = next(
            (
                request
                for request in requests
                if request["request_id"] == row.get("request_id")
            ),
            None,
        )
        if request is None or row.get("validation_status") != "pass":
            raise S2ResearchContractError("s2_fake_provider_binding_invalid")
        output = row.get("provider_output") or {}
        validate_provider_judgment_choice(output, request=request)
        if row.get("fake_digest") != canonical_digest(output):
            raise S2ResearchContractError("s2_fake_provider_digest_invalid")

    expected_counts = {
        "case_count": 3,
        "representative_request_count": 9,
        "selected_candidate_alias_count": 26,
        "typed_gap_alias_count": 2,
        "company_specific_mechanism_choice_count": 18,
        "fake_provider_pass_count": 9,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    if program.get("observed_counts") != expected_counts:
        raise S2ResearchContractError("s2_observed_counts_invalid")


def _compile_request(
    *,
    case_key: str,
    company_name: str,
    cell_id: str,
    cell_policy: Mapping[str, Any],
    query: Mapping[str, Any],
    provider_contract: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = sorted(
        query.get("selected_candidates") or [],
        key=lambda row: (
            int(row.get("route_priority") or 0),
            str(row.get("slot_id") or ""),
            str(row.get("candidate_id") or ""),
        ),
    )
    evidence_aliases = [
        {
            "alias": f"{case_key}_E{index:02d}",
            "candidate_id": row["candidate_id"],
            "candidate_digest": row["candidate_digest"],
            "candidate_role": row["candidate_role"],
            "slot_id": row["slot_id"],
            "claim_boundary": row["claim_boundary"],
            "metric_family": row.get("metric_family") or None,
            "edge_type": row.get("edge_type") or None,
            "target_entity_id": row.get("target_entity_id") or None,
            "financial_fact_authority": bool(row["financial_fact_authority"]),
            "relationship_fact_only": bool(row["relationship_fact_only"]),
        }
        for index, row in enumerate(candidates, start=1)
    ]
    gaps = sorted(
        query.get("typed_gaps") or [],
        key=lambda row: (str(row.get("slot_id") or ""), str(row.get("gap_code") or "")),
    )
    gap_aliases = [
        {
            "alias": f"{case_key}_G{index:02d}",
            "gap_code": row["gap_code"],
            "slot_id": row["slot_id"],
            "cannot_infer": row["cannot_infer"],
            "source_exhaustion_proven": False,
        }
        for index, row in enumerate(gaps, start=1)
    ]
    mechanism_aliases = [
        {"alias": str(alias), "atom": str(atom)}
        for alias, atom in cell_policy["mechanism_aliases"].items()
    ]
    wwc_aliases = [
        {"alias": str(alias), "condition": str(condition)}
        for alias, condition in cell_policy["what_would_change_aliases"].items()
    ]
    typed_metadata = compact_prompt_metadata(
        {
            "line_item_count": len(evidence_aliases) + len(gap_aliases),
            "row_count": len(evidence_aliases),
            "gap_count": len(gap_aliases),
            "relationship_context_available": any(
                row["relationship_fact_only"] for row in evidence_aliases
            ),
            "required_slot_recall": query.get("required_slot_recall"),
        },
        max_items=8,
        text_limit=80,
    )
    visible = {
        "case_key": case_key,
        "company_name": company_name,
        "program_cell_id": cell_id,
        "decision_question": cell_policy["decision_question"],
        "method_steps": list(cell_policy["method_steps"]),
        "evidence_aliases": evidence_aliases,
        "gap_aliases": gap_aliases,
        "mechanism_aliases": mechanism_aliases,
        "what_would_change_aliases": wwc_aliases,
        "typed_metadata": typed_metadata,
        "provider_output_contract": deepcopy(provider_contract),
        "instruction": (
            "Select only request-local aliases and closed enums. Do not return "
            "numbers, dates, identity fields, IDs, or free narrative."
        ),
    }
    request_id = f"FIN013-S2-{case_key}-{cell_id}"
    body = {
        "request_id": request_id,
        "case_key": case_key,
        "program_cell_id": cell_id,
        "s1_query_digest": query["query_digest"],
        "model_visible_request": visible,
        "local_render_authority": {
            "case_identity": case_key,
            "numeric_and_date_values_from_candidate_ids": [
                row["candidate_id"] for row in candidates
            ],
            "lineage_from_s1_query_digest": query["query_digest"],
            "provider_may_not_create_final_narrative": True,
        },
    }
    return {**body, "request_digest": canonical_digest(body)}


def _compile_provider_contract(source: Mapping[str, Any]) -> dict[str, Any]:
    required_fields = list(source["required_fields"])
    return {
        "contract_ref": CONTRACT_REF,
        "type": "object",
        "additional_properties": False,
        "required_fields": required_fields,
        "epistemic_states": list(source["epistemic_states"]),
        "answer_directions": list(source["answer_directions"]),
        "confidence_values": list(source["confidence_values"]),
        "alias_array_fields": [
            "support_aliases",
            "counterevidence_aliases",
            "gap_aliases",
            "what_would_change_aliases",
        ],
        "forbidden_provider_fields": list(source["forbidden_provider_fields"]),
        "local_ownership": list(source["local_ownership"]),
        "free_text_fields": [],
    }


def _assert_s1_authority(s1_decision: Mapping[str, Any]) -> None:
    body = {
        key: deepcopy(value)
        for key, value in s1_decision.items()
        if key != "record_digest"
    }
    retrieval = s1_decision.get("retrieval_usefulness_program")
    if (
        s1_decision.get("status") != "S1_pass_closed_S2_next_not_started"
        or not isinstance(retrieval, Mapping)
        or retrieval.get("contract_ref") != S1_CONTRACT_REF
        or s1_decision.get("record_digest") != canonical_digest(body)
        or retrieval.get("stage_boundary", {}).get("S1") != "pass_closed"
        or retrieval.get("stage_boundary", {}).get(
            "legacy_bm25_is_current_authority"
        )
        is not False
    ):
        raise S2ResearchContractError("s2_s1_authority_invalid")


def _assert_local_aliases(visible: Mapping[str, Any], *, case_key: str) -> None:
    alias_groups: Sequence[tuple[str, str]] = (
        ("evidence_aliases", f"{case_key}_E"),
        ("gap_aliases", f"{case_key}_G"),
        ("mechanism_aliases", f"{case_key}_M_"),
        ("what_would_change_aliases", f"{case_key}_W_"),
    )
    all_aliases: list[str] = []
    for field, prefix in alias_groups:
        aliases = [str(row.get("alias") or "") for row in visible.get(field) or []]
        if any(not alias.startswith(prefix) for alias in aliases):
            raise S2ResearchContractError("s2_cross_case_alias_leakage")
        all_aliases.extend(aliases)
    if len(all_aliases) != len(set(all_aliases)):
        raise S2ResearchContractError("s2_request_alias_collision")


__all__ = [
    "S2ResearchContractError",
    "compile_fake_provider_output",
    "compile_s2_research_question_method_program",
    "load_s2_research_contract_policy",
    "validate_provider_judgment_choice",
    "validate_s2_research_question_method_program",
]
