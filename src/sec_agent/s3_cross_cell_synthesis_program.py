from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


POLICY_SCHEMA = "fin_ia_0_1_3_s3_cross_cell_synthesis_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_cross_cell_synthesis_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.cross_cell_dependency_conflict_gap_synthesis:v1"
CASES = ("DELL", "MU", "NVDA")


class S3CrossCellSynthesisError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s3_cross_cell_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or tuple(sorted(policy.get("case_rules") or {})) != CASES
        or set(policy.get("allowed_dispositions") or ()) != {"resolve", "defer", "block"}
        or policy.get("authority_boundary", {}).get("model_contract_changed") is not False
    ):
        raise S3CrossCellSynthesisError("s3_cross_cell_policy_invalid")
    for case_key, rules in policy["case_rules"].items():
        if len(rules.get("dependencies") or []) != 1 or len(rules.get("conflicts") or []) != 1 or not rules.get("gaps"):
            raise S3CrossCellSynthesisError(f"s3_cross_cell_case_rule_invalid:{case_key}")
    return policy


def compile_s3_cross_cell_synthesis_program(*, policy: Mapping[str, Any], claim_decision: Mapping[str, Any]) -> dict[str, Any]:
    if claim_decision.get("acceptance", {}).get("S3_02") != "engineering_pass" or not _digest_ok(claim_decision):
        raise S3CrossCellSynthesisError("s3_cross_cell_upstream_invalid")
    cards = claim_decision["claim_quality_program"]["core_claim_cards"]
    card_map = {(str(row["case_key"]), str(row["program_cell_id"])): row for row in cards}
    syntheses = []
    for case_key in CASES:
        case_cards = [row for row in cards if row["case_key"] == case_key]
        rules = policy["case_rules"][case_key]
        dependencies = [_compile_dependency(case_key, row, card_map) for row in rules["dependencies"]]
        conflicts = [_compile_conflict(case_key, row, card_map) for row in rules["conflicts"]]
        gaps = [_compile_gap(case_key, row, card_map) for row in rules["gaps"]]
        natural = sum(row["choice_authority"] == "live_natural_exact_once" for row in case_cards)
        body = {
            "case_key": case_key,
            "claim_card_ids": [row["claim_card_id"] for row in case_cards],
            "natural_claim_count": natural,
            "fixture_claim_count": len(case_cards) - natural,
            "synthesis_authority": "fixture_mixed_engineering_only" if natural < len(case_cards) else "all_natural_candidate",
            "dependencies": dependencies,
            "conflicts": conflicts,
            "gaps": gaps,
            "planned_no_claim_cells_included": 0,
            "display_ready": False,
        }
        synthesis_id = "fin013_s3_lead_synthesis_" + canonical_digest(body)[:24]
        with_id = {"synthesis_id": synthesis_id, **body}
        syntheses.append({**with_id, "synthesis_digest": canonical_digest(with_id)})
    observed = {
        "case_syntheses": 3,
        "dependencies": sum(len(row["dependencies"]) for row in syntheses),
        "conflicts": sum(len(row["conflicts"]) for row in syntheses),
        "gaps": sum(len(row["gaps"]) for row in syntheses),
        "resolved_conflicts": sum(item["disposition"] == "resolve" for row in syntheses for item in row["conflicts"]),
        "deferred_conflicts": sum(item["disposition"] == "defer" for row in syntheses for item in row["conflicts"]),
        "blocked_conflicts": sum(item["disposition"] == "block" for row in syntheses for item in row["conflicts"]),
        "all_natural_case_syntheses": sum(row["synthesis_authority"] == "all_natural_candidate" for row in syntheses),
        "planned_no_claim_cells_included": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_runs": 0,
    }
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "claim_decision_digest": claim_decision["record_digest"],
        "case_syntheses": syntheses,
        "observed_counts": observed,
        "stage_boundary": {
            "S3_03": "engineering_pass_fixture_mixed_synthesis_proven",
            "business_synthesis_accepted": False,
            "all_natural_case_syntheses": False,
            "planned_no_claim_cells_synthesized": False,
            "model_contract_changed": False,
            "additional_canary_required": False,
            "S3_04_writer_depth": "not_started",
            "S3_05_quality_acceptance": "not_started",
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_cross_cell_synthesis_program(program, policy=policy)
    return program


def validate_s3_cross_cell_synthesis_program(program: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3CrossCellSynthesisError("s3_cross_cell_program_binding_invalid")
    syntheses = program.get("case_syntheses") or []
    if [row.get("case_key") for row in syntheses] != list(CASES):
        raise S3CrossCellSynthesisError("s3_cross_cell_case_surface_invalid")
    for synthesis in syntheses:
        validate_s3_case_synthesis(synthesis, policy=policy)
    if program.get("observed_counts") != {
        "case_syntheses": 3,
        "dependencies": 3,
        "conflicts": 3,
        "gaps": 5,
        "resolved_conflicts": 0,
        "deferred_conflicts": 3,
        "blocked_conflicts": 0,
        "all_natural_case_syntheses": 0,
        "planned_no_claim_cells_included": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_runs": 0,
    }:
        raise S3CrossCellSynthesisError("s3_cross_cell_observed_counts_invalid")


def validate_s3_case_synthesis(synthesis: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    case_key = str(synthesis.get("case_key") or "")
    if case_key not in CASES or len(synthesis.get("claim_card_ids") or []) != 3:
        raise S3CrossCellSynthesisError("s3_cross_cell_claim_surface_invalid")
    claim_ids = set(synthesis["claim_card_ids"])
    for dependency in synthesis.get("dependencies") or []:
        if dependency.get("from_claim_id") not in claim_ids or dependency.get("to_claim_id") not in claim_ids or dependency.get("from_claim_id") == dependency.get("to_claim_id"):
            raise S3CrossCellSynthesisError("s3_cross_cell_dependency_binding_invalid")
        if not dependency.get("mechanism") or not dependency.get("decision_effect") or not dependency.get("evidence_candidate_ids"):
            raise S3CrossCellSynthesisError("s3_cross_cell_dependency_semantics_missing")
    for conflict in synthesis.get("conflicts") or []:
        if set(conflict.get("claim_ids") or ()) - claim_ids or len(conflict.get("claim_ids") or ()) < 2:
            raise S3CrossCellSynthesisError("s3_cross_cell_conflict_binding_invalid")
        if conflict.get("disposition") not in policy["allowed_dispositions"] or not conflict.get("tension") or not conflict.get("reason"):
            raise S3CrossCellSynthesisError("s3_cross_cell_conflict_disposition_invalid")
        if conflict["disposition"] == "resolve" and synthesis.get("synthesis_authority") != "all_natural_candidate":
            raise S3CrossCellSynthesisError("s3_cross_cell_fixture_conflict_resolve_forbidden")
    gap_ids = set()
    for gap in synthesis.get("gaps") or []:
        if gap.get("gap_id") in gap_ids or gap.get("source_claim_id") not in claim_ids:
            raise S3CrossCellSynthesisError("s3_cross_cell_gap_binding_invalid")
        gap_ids.add(gap.get("gap_id"))
        if gap.get("priority") not in policy["allowed_priorities"] or not all(gap.get(field) for field in ("impact", "owner", "stop_condition", "next_evidence_route", "source_basis")):
            raise S3CrossCellSynthesisError("s3_cross_cell_gap_disposition_invalid")
    if synthesis.get("planned_no_claim_cells_included") != 0 or synthesis.get("display_ready") is not False:
        raise S3CrossCellSynthesisError("s3_cross_cell_authority_boundary_invalid")
    digest_body = {key: deepcopy(value) for key, value in synthesis.items() if key != "synthesis_digest"}
    if synthesis.get("synthesis_digest") != canonical_digest(digest_body):
        raise S3CrossCellSynthesisError("s3_cross_cell_synthesis_digest_invalid")


def _compile_dependency(case_key: str, rule: Mapping[str, Any], cards: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, Any]:
    source = cards[(case_key, str(rule["from_cell"]))]
    target = cards[(case_key, str(rule["to_cell"]))]
    evidence = sorted(set(source["support_candidate_ids"] + target["support_candidate_ids"]))
    if not evidence:
        raise S3CrossCellSynthesisError("s3_cross_cell_dependency_evidence_missing")
    return {
        "from_claim_id": source["claim_card_id"],
        "to_claim_id": target["claim_card_id"],
        "mechanism": rule["mechanism"],
        "decision_effect": rule["decision_effect"],
        "evidence_candidate_ids": evidence,
    }


def _compile_conflict(case_key: str, rule: Mapping[str, Any], cards: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, Any]:
    selected = [cards[(case_key, str(cell))] for cell in rule["claim_cells"]]
    return {
        "claim_ids": [row["claim_card_id"] for row in selected],
        "mechanism_aliases": [row["mechanism_alias"] for row in selected],
        "tension": rule["tension"],
        "disposition": rule["disposition"],
        "reason": rule["reason"],
    }


def _compile_gap(case_key: str, rule: Mapping[str, Any], cards: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, Any]:
    source = cards[(case_key, str(rule["source_cell"]))]
    if rule.get("source_gap_code"):
        codes = {row.get("gap_code") for row in source["typed_gaps"]}
        if rule["source_gap_code"] not in codes:
            raise S3CrossCellSynthesisError("s3_cross_cell_gap_source_code_missing")
        basis = {"type": "typed_gap", "gap_code": rule["source_gap_code"]}
    else:
        if rule.get("source_mechanism_alias") != source["mechanism_alias"]:
            raise S3CrossCellSynthesisError("s3_cross_cell_gap_source_mechanism_missing")
        basis = {"type": "claim_boundary", "mechanism_alias": source["mechanism_alias"], "evidence_boundary": source["evidence_boundary"]}
    return {
        "gap_id": rule["gap_id"],
        "source_claim_id": source["claim_card_id"],
        "source_basis": basis,
        "impact": rule["impact"],
        "priority": rule["priority"],
        "owner": rule["owner"],
        "stop_condition": rule["stop_condition"],
        "next_evidence_route": rule["next_evidence_route"],
    }


def _digest_ok(record: Mapping[str, Any]) -> bool:
    return record.get("record_digest") == canonical_digest({key: deepcopy(value) for key, value in record.items() if key != "record_digest"})
