from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_representative_node_program import consume_representative_specialist_output


POLICY_SCHEMA = "fin_ia_0_1_3_s3_claim_and_observable_wwc_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_claim_and_observable_wwc_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.company_specific_claim_and_observable_wwc:v1"
CASES = ("DELL", "MU", "NVDA")
CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)


class S3ClaimQualityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s3_claim_quality_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or len(policy.get("required_claim_fields") or ()) != 10
        or len(policy.get("required_wwc_fields") or ()) != 5
        or len(policy.get("wwc_profiles") or {}) != 18
        or policy.get("authority_boundary", {}).get("new_model_contract") is not False
    ):
        raise S3ClaimQualityError("s3_claim_quality_policy_invalid")
    required_wwc = set(policy["required_wwc_fields"])
    for alias, profile in policy["wwc_profiles"].items():
        if not alias.startswith(("DELL_W_", "MU_W_", "NVDA_W_")) or set(profile) != required_wwc:
            raise S3ClaimQualityError("s3_claim_quality_wwc_profile_invalid")
        if any(not str(value).strip() for value in profile.values()):
            raise S3ClaimQualityError("s3_claim_quality_wwc_dimension_blank")
    return policy


def compile_s3_claim_quality_program(
    *,
    policy: Mapping[str, Any],
    s1_decision: Mapping[str, Any],
    s2_decision: Mapping[str, Any],
    representative_decision: Mapping[str, Any],
    s3_surface_decision: Mapping[str, Any],
    natural_s2_result: Mapping[str, Any],
    natural_s2_03_result: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_inputs(
        policy=policy,
        s1_decision=s1_decision,
        s2_decision=s2_decision,
        representative_decision=representative_decision,
        s3_surface_decision=s3_surface_decision,
        natural_s2_result=natural_s2_result,
        natural_s2_03_result=natural_s2_03_result,
    )
    requests = {
        (str(row["case_key"]), str(row["program_cell_id"])): row
        for row in s2_decision["research_question_method_program"]["representative_requests"]
    }
    fixture_claims = {
        (str(row["case_key"]), str(row["program_cell_id"])): row
        for row in representative_decision["representative_node_program"]["materialized_claims"]
    }
    natural_outputs, natural_refs = _natural_output_map(natural_s2_result, natural_s2_03_result)
    candidate_map = {
        str(candidate["candidate_id"]): candidate
        for query in s1_decision["retrieval_usefulness_program"]["query_results"]
        for candidate in query.get("selected_candidates") or []
    }
    cards = []
    for case_key in CASES:
        for cell_id in CELLS:
            key = (case_key, cell_id)
            if key in natural_outputs:
                claim = consume_representative_specialist_output(
                    request=requests[key], provider_output=natural_outputs[key]
                )
                authority = "live_natural_exact_once"
                natural_ref = natural_refs[key]
            else:
                claim = deepcopy(fixture_claims[key])
                authority = "fixture_choice_engineering_only"
                natural_ref = None
            cards.append(
                _compile_card(
                    claim=claim,
                    candidate_map=candidate_map,
                    policy=policy,
                    choice_authority=authority,
                    natural_ref=natural_ref,
                )
            )
    planned = _planned_dynamic_cells(s3_surface_decision)
    observed = {
        "core_claim_cards": len(cards),
        "live_natural_claim_cards": sum(row["choice_authority"] == "live_natural_exact_once" for row in cards),
        "fixture_only_claim_cards": sum(row["choice_authority"] == "fixture_choice_engineering_only" for row in cards),
        "structured_wwc": sum(len(row["what_would_change"]) for row in cards),
        "numeric_fact_bindings": sum(len(row["numeric_facts"]) for row in cards),
        "typed_gap_bindings": sum(len(row["typed_gaps"]) for row in cards),
        "planned_dynamic_cells_without_claim_choice": len(planned),
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
        "upstream_digests": {
            "S1": s1_decision["record_digest"],
            "S2_01": s2_decision["record_digest"],
            "S2_02_representative": representative_decision["record_digest"],
            "S2_02_natural": natural_s2_result["record_digest"],
            "S2_03_natural": natural_s2_03_result["record_digest"],
            "S3_01": s3_surface_decision["record_digest"],
        },
        "core_claim_cards": cards,
        "planned_dynamic_cells_without_claim_choice": planned,
        "observed_counts": observed,
        "stage_boundary": {
            "S3_02": "engineering_pass_contract_and_fixture_proven",
            "live_natural_core_claim_coverage": "4/9",
            "fixture_claims_are_business_truth": False,
            "planned_cells_are_claims": False,
            "changed_model_contract": False,
            "additional_natural_canary_required": False,
            "remaining_natural_choices": "defer_to_single_formal_full_chain_after_S3_deterministic_gates",
            "S3_03_cross_cell_synthesis": "not_started",
            "S3_04_writer_depth": "not_started",
            "S3_05_quality_acceptance": "not_started",
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_claim_quality_program(program, policy=policy)
    return program


def validate_s3_claim_quality_program(program: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3ClaimQualityError("s3_claim_quality_program_binding_invalid")
    cards = program.get("core_claim_cards") or []
    if [(row.get("case_key"), row.get("program_cell_id")) for row in cards] != [
        (case_key, cell_id) for case_key in CASES for cell_id in CELLS
    ]:
        raise S3ClaimQualityError("s3_claim_quality_card_surface_invalid")
    for card in cards:
        validate_s3_claim_card(card, policy=policy)
    observed = program.get("observed_counts") or {}
    if (
        observed.get("core_claim_cards") != 9
        or observed.get("live_natural_claim_cards") != 4
        or observed.get("fixture_only_claim_cards") != 5
        or observed.get("typed_gap_bindings") != 2
        or observed.get("planned_dynamic_cells_without_claim_choice") != 29
        or any(observed.get(field) != 0 for field in ("model_calls", "provider_calls", "network_calls", "source_calls", "business_runs"))
    ):
        raise S3ClaimQualityError("s3_claim_quality_observed_counts_invalid")
    planned = program.get("planned_dynamic_cells_without_claim_choice") or []
    if len(planned) != 29 or any(row.get("status") != "planned_no_claim_choice" for row in planned):
        raise S3ClaimQualityError("s3_claim_quality_planned_boundary_invalid")


def validate_s3_claim_card(card: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    if set(policy["required_claim_fields"]) - set(card):
        raise S3ClaimQualityError("s3_claim_quality_required_field_missing")
    case_key = str(card.get("case_key") or "")
    company = str(card.get("company_name") or "")
    statement = str(card.get("mechanism_atom") or "")
    if case_key not in CASES or not company or company.split()[0].lower() not in statement.lower():
        raise S3ClaimQualityError("s3_claim_quality_company_mechanism_invalid")
    if any(fragment.lower() in statement.lower() for fragment in policy["forbidden_generic_fragments"]):
        raise S3ClaimQualityError("s3_claim_quality_generic_statement_forbidden")
    if not card.get("evidence_boundary") and not card.get("typed_gaps"):
        raise S3ClaimQualityError("s3_claim_quality_evidence_or_gap_missing")
    for fact in card.get("numeric_facts") or []:
        if fact.get("case_key") != case_key or not all(fact.get(field) for field in ("candidate_id", "metric_family", "normalized_value", "unit", "published_at")):
            raise S3ClaimQualityError("s3_claim_quality_numeric_binding_invalid")
    required_wwc = set(policy["required_wwc_fields"])
    for condition in card.get("what_would_change") or []:
        if set(condition) - {"alias", "condition", *required_wwc} or not required_wwc.issubset(condition):
            raise S3ClaimQualityError("s3_claim_quality_wwc_shape_invalid")
        if condition.get("alias") not in policy["wwc_profiles"]:
            raise S3ClaimQualityError("s3_claim_quality_wwc_alias_invalid")
        if any(not str(condition[field]).strip() for field in required_wwc):
            raise S3ClaimQualityError("s3_claim_quality_wwc_dimension_blank")
    if card.get("choice_authority") == "live_natural_exact_once":
        if not card.get("natural_result_ref"):
            raise S3ClaimQualityError("s3_claim_quality_natural_ref_missing")
    elif card.get("choice_authority") == "fixture_choice_engineering_only":
        if card.get("natural_result_ref") is not None:
            raise S3ClaimQualityError("s3_claim_quality_fixture_promoted_as_natural")
    else:
        raise S3ClaimQualityError("s3_claim_quality_choice_authority_invalid")
    digest_body = {key: deepcopy(value) for key, value in card.items() if key != "claim_card_digest"}
    if card.get("claim_card_digest") != canonical_digest(digest_body):
        raise S3ClaimQualityError("s3_claim_quality_card_digest_invalid")


def _compile_card(
    *, claim: Mapping[str, Any], candidate_map: Mapping[str, Any], policy: Mapping[str, Any], choice_authority: str, natural_ref: Mapping[str, Any] | None
) -> dict[str, Any]:
    evidence = list(claim.get("support_evidence") or [])
    candidate_ids = [str(row["candidate_id"]) for row in evidence]
    numeric = []
    boundaries = []
    for candidate_id in candidate_ids:
        source = candidate_map[candidate_id]
        boundary = str(source.get("claim_boundary") or "")
        if boundary and boundary not in boundaries:
            boundaries.append(boundary)
        if source.get("financial_fact_authority") is True:
            numeric.append({
                "case_key": source["case_key"],
                "candidate_id": candidate_id,
                "metric_family": source["metric_family"],
                "normalized_value": source["normalized_value"],
                "unit": source["unit"],
                "published_at": source["published_at"],
                "claim_boundary": source["claim_boundary"],
            })
    structured_wwc = []
    for row in claim.get("what_would_change") or []:
        alias = str(row["alias"])
        structured_wwc.append({"alias": alias, "condition": row["condition"], **deepcopy(policy["wwc_profiles"][alias])})
    body = {
        "case_key": claim["case_key"],
        "company_name": claim["company_name"],
        "program_cell_id": claim["program_cell_id"],
        "decision_question": claim["decision_question"],
        "epistemic_state": claim["epistemic_state"],
        "answer_direction": claim["answer_direction"],
        "confidence": claim["confidence"],
        "mechanism_alias": claim["mechanism_alias"],
        "mechanism_atom": claim["mechanism_atom"],
        "evidence_boundary": boundaries,
        "support_candidate_ids": candidate_ids,
        "counterevidence_candidate_ids": [str(row["candidate_id"]) for row in claim.get("counterevidence") or []],
        "numeric_facts": numeric,
        "typed_gaps": deepcopy(claim.get("typed_gaps") or []),
        "what_would_change": structured_wwc,
        "choice_authority": choice_authority,
        "natural_result_ref": deepcopy(natural_ref),
        "display_ready": False,
        "lineage": {
            **deepcopy(claim["lineage"]),
            "source_claim_digest": claim["claim_digest"],
        },
    }
    card_id = "fin013_s3_claim_card_" + canonical_digest(body)[:24]
    with_id = {"claim_card_id": card_id, **body}
    return {**with_id, "claim_card_digest": canonical_digest(with_id)}


def _natural_output_map(first: Mapping[str, Any], second: Mapping[str, Any]) -> tuple[dict[tuple[str, str], Mapping[str, Any]], dict[tuple[str, str], Mapping[str, Any]]]:
    outputs: dict[tuple[str, str], Mapping[str, Any]] = {}
    refs: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in first["family_results"]:
        key = (str(row["case_key"]), str(row["program_cell_id"]))
        outputs[key] = row["provider_output"]
        refs[key] = {"result": "S2_02", "record_digest": first["record_digest"], "request_id": row["request_id"], "provider_output_digest": row["provider_output_digest"]}
    row = second["natural_reproof"]
    key = (str(row["local_claim_case"]), str(row["local_claim_cell"]))
    if key in outputs:
        raise S3ClaimQualityError("s3_claim_quality_duplicate_natural_choice")
    outputs[key] = row["provider_output"]
    refs[key] = {"result": "S2_03", "record_digest": second["record_digest"], "request_id": second["request_id"], "provider_output_digest": row["provider_output_digest"]}
    return outputs, refs


def _planned_dynamic_cells(s3_surface_decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for surface in s3_surface_decision["dynamic_decision_surface_program"]["surfaces"]:
        for cell in surface["cells"]:
            if cell["cell_key"] in CELLS:
                continue
            rows.append({
                "case_key": surface["case_key"],
                "cell_key": cell["cell_key"],
                "decision_question": cell["decision_question"],
                "owner_role": cell["owner_role"],
                "evidence_roles": [slot["evidence_role"] for slot in cell["evidence_slots"]],
                "stop_rule": cell["stop_rule"],
                "status": "planned_no_claim_choice",
                "reason": "No current provider choice exists for this newly planned dynamic Cell; do not fabricate a Claim.",
            })
    return rows


def _assert_digest(record: Mapping[str, Any]) -> bool:
    body = {key: deepcopy(value) for key, value in record.items() if key != "record_digest"}
    return record.get("record_digest") == canonical_digest(body)


def _assert_inputs(**inputs: Mapping[str, Any]) -> None:
    policy = inputs["policy"]
    if policy.get("contract_ref") != CONTRACT_REF:
        raise S3ClaimQualityError("s3_claim_quality_policy_binding_invalid")
    for key in ("s1_decision", "s2_decision", "representative_decision", "s3_surface_decision", "natural_s2_result", "natural_s2_03_result"):
        if not _assert_digest(inputs[key]):
            raise S3ClaimQualityError(f"s3_claim_quality_upstream_digest_invalid:{key}")
    if inputs["s1_decision"].get("acceptance", {}).get("S1") != "pass_closed" or inputs["s3_surface_decision"].get("acceptance", {}).get("S3_01") != "engineering_pass":
        raise S3ClaimQualityError("s3_claim_quality_upstream_status_invalid")
    if inputs["natural_s2_result"].get("execution", {}).get("status") != "terminal_succeeded_exact_once" or inputs["natural_s2_03_result"].get("natural_reproof", {}).get("status") != "terminal_succeeded_exact_once":
        raise S3ClaimQualityError("s3_claim_quality_natural_result_invalid")
