from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_final_delivery_verifier_l1_l2_binding_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.final_delivery_verifier_L1_L2_binding:v1"
CASES = ("DELL", "MU", "NVDA")


class S3FinalDeliveryBindingError(ValueError):
    pass


def compile_s3_final_delivery_binding(
    *,
    claim_decision: Mapping[str, Any],
    writer_decision: Mapping[str, Any],
    quality_decision: Mapping[str, Any],
    s1_decision: Mapping[str, Any],
    formal_result: Mapping[str, Any],
) -> dict[str, Any]:
    for name, value in (
        ("claim", claim_decision),
        ("writer", writer_decision),
        ("quality", quality_decision),
    ):
        if not _record_digest_ok(value):
            raise S3FinalDeliveryBindingError(f"s3_final_binding_{name}_digest_invalid")
    if (
        formal_result.get("status") != "terminal_succeeded_exact_once"
        or formal_result.get("completed_calls") != 9
        or not _record_digest_ok(formal_result)
    ):
        raise S3FinalDeliveryBindingError("s3_final_binding_formal_result_invalid")

    cards = claim_decision["claim_quality_program"]["core_claim_cards"]
    workpapers = writer_decision["workpaper_writer_content_program"]["case_workpapers"]
    base_contexts = {
        row["case_key"]: row
        for row in quality_decision["research_quality_gate_program"]["candidate_contexts"]
    }
    candidate_map = {
        candidate["candidate_id"]: candidate
        for query in s1_decision["retrieval_usefulness_program"]["query_results"]
        for candidate in query.get("selected_candidates") or []
    }
    outputs = []
    for case_key in CASES:
        case_cards = [row for row in cards if row["case_key"] == case_key]
        workpaper = next(row for row in workpapers if row["case_key"] == case_key)
        l1_findings = _l1_findings(case_key, case_cards, candidate_map)
        l2_findings = _l2_findings(case_key, case_cards, workpaper, candidate_map)
        delivery_body = {
            "case_key": case_key,
            "authority": workpaper["workpaper_authority"],
            "workpaper_id": workpaper["workpaper_id"],
            "workpaper_digest": workpaper["workpaper_digest"],
            "sections": deepcopy(workpaper["sections"]),
            "source_run_id": formal_result["run_id"],
            "source_attempt_id": formal_result["attempt_id"],
            "source_terminal_result_digest": formal_result["terminal_result_digest"],
        }
        final_delivery_digest = canonical_digest(delivery_body)
        verifier_body = {
            "case_key": case_key,
            "final_delivery_digest": final_delivery_digest,
            "L1_status": "pass" if not l1_findings else "fail",
            "L1_findings": l1_findings,
            "L2_status": "pass" if not l2_findings else "fail",
            "L2_findings": l2_findings,
            "verifier_policy": "fail_closed_identity_numeric_lineage_and_bounded_epistemic_fidelity_v1",
        }
        verifier = {**verifier_body, "verifier_binding_digest": canonical_digest(verifier_body)}
        input_head_digest = canonical_digest(
            {
                "case_key": case_key,
                "claim_card_digests": [row["claim_card_digest"] for row in case_cards],
                "source_terminal_result_digest": formal_result["terminal_result_digest"],
            }
        )
        context = deepcopy(base_contexts[case_key])
        context.update(
            {
                "generic_precheck_status": "pass",
                "L1_status": verifier["L1_status"],
                "L2_status": verifier["L2_status"],
                "final_delivery_digest": final_delivery_digest,
                "verifier_binding_digest": verifier["verifier_binding_digest"],
                "identity_sealed": True,
                "input_head_digest": input_head_digest,
                "run_id": formal_result["run_id"],
                "artifact_digest": final_delivery_digest,
            }
        )
        context["candidate_context_digest"] = canonical_digest(
            {key: value for key, value in context.items() if key != "candidate_context_digest"}
        )
        outputs.append(
            {
                "case_key": case_key,
                "delivery": {**delivery_body, "final_delivery_digest": final_delivery_digest},
                "verifier": verifier,
                "sealed_candidate_context": context,
                "scoreability": (
                    "eligible_pending_formal_score"
                    if verifier["L1_status"] == verifier["L2_status"] == "pass"
                    else "blocked_by_L1_or_L2"
                ),
            }
        )
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "formal_result_digest": formal_result["record_digest"],
        "case_bindings": outputs,
        "observed_counts": {
            "final_deliveries": 3,
            "verifier_bindings": 3,
            "L1_passes": sum(row["verifier"]["L1_status"] == "pass" for row in outputs),
            "L2_passes": sum(row["verifier"]["L2_status"] == "pass" for row in outputs),
            "sealed_scoreable_candidates": sum(row["scoreability"] == "eligible_pending_formal_score" for row in outputs),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "business_runs": 0,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_final_delivery_binding(program)
    return program


def validate_s3_final_delivery_binding(program: Mapping[str, Any]) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3FinalDeliveryBindingError("s3_final_binding_program_digest_invalid")
    rows = program.get("case_bindings") or []
    if [row.get("case_key") for row in rows] != list(CASES):
        raise S3FinalDeliveryBindingError("s3_final_binding_case_surface_invalid")
    for row in rows:
        delivery = row["delivery"]
        verifier = row["verifier"]
        context = row["sealed_candidate_context"]
        if delivery["final_delivery_digest"] != canonical_digest(
            {key: value for key, value in delivery.items() if key != "final_delivery_digest"}
        ):
            raise S3FinalDeliveryBindingError("s3_final_binding_delivery_digest_invalid")
        if verifier["verifier_binding_digest"] != canonical_digest(
            {key: value for key, value in verifier.items() if key != "verifier_binding_digest"}
        ):
            raise S3FinalDeliveryBindingError("s3_final_binding_verifier_digest_invalid")
        if context["candidate_context_digest"] != canonical_digest(
            {key: value for key, value in context.items() if key != "candidate_context_digest"}
        ):
            raise S3FinalDeliveryBindingError("s3_final_binding_context_digest_invalid")
        expected = (
            "eligible_pending_formal_score"
            if verifier["L1_status"] == verifier["L2_status"] == "pass"
            else "blocked_by_L1_or_L2"
        )
        if row.get("scoreability") != expected:
            raise S3FinalDeliveryBindingError("s3_final_binding_scoreability_invalid")


def _l1_findings(case_key: str, cards: list[Mapping[str, Any]], candidates: Mapping[str, Any]) -> list[dict[str, str]]:
    findings = []
    for card in cards:
        if card.get("case_key") != case_key:
            findings.append({"code": "cross_case_claim", "ref": str(card.get("claim_card_id"))})
        for fact in card.get("numeric_facts") or []:
            source = candidates.get(fact.get("candidate_id"))
            if source is None or fact.get("case_key") != case_key:
                findings.append({"code": "numeric_authority_missing_or_cross_case", "ref": str(fact.get("candidate_id"))})
                continue
            expected = source
            for field in ("metric_family", "normalized_value", "unit", "published_at"):
                if str(fact.get(field)) != str(expected.get(field)):
                    findings.append({"code": f"numeric_{field}_drift", "ref": str(fact.get("candidate_id"))})
    return findings


def _l2_findings(
    case_key: str,
    cards: list[Mapping[str, Any]],
    workpaper: Mapping[str, Any],
    candidates: Mapping[str, Any],
) -> list[dict[str, str]]:
    findings = []
    claim_ids = {str(row["claim_card_id"]) for row in cards}
    for card in cards:
        roles = card.get("evidence_role_projection") or {}
        if card.get("epistemic_state") == "cannot_infer" and (
            roles.get("thesis_support") or roles.get("observation_support") or not card.get("typed_gaps")
        ):
            findings.append({"code": "cannot_infer_boundary_violation", "ref": str(card["claim_card_id"])})
        for candidate_id in (card.get("support_candidate_ids") or []) + (card.get("counterevidence_candidate_ids") or []):
            source = candidates.get(candidate_id)
            if source is None or source.get("case_key") != case_key:
                findings.append({"code": "evidence_authority_missing_or_cross_case", "ref": str(candidate_id)})
        if not card.get("evidence_boundary") and not card.get("typed_gaps"):
            findings.append({"code": "claim_without_boundary_or_gap", "ref": str(card["claim_card_id"])})
    if workpaper.get("workpaper_authority") != "all_natural_candidate":
        findings.append({"code": "workpaper_not_all_natural", "ref": str(workpaper.get("workpaper_id"))})
    for section in workpaper.get("sections") or []:
        for claim_id in section.get("claim_card_ids") or []:
            if claim_id not in claim_ids:
                findings.append({"code": "section_unknown_claim", "ref": str(claim_id)})
    return findings


def _record_digest_ok(value: Mapping[str, Any]) -> bool:
    digest = value.get("record_digest")
    if not isinstance(digest, str):
        return False
    return digest == canonical_digest(
        {key: deepcopy(item) for key, item in value.items() if key != "record_digest"}
    )


__all__ = [
    "CONTRACT_REF",
    "PROGRAM_SCHEMA",
    "S3FinalDeliveryBindingError",
    "compile_s3_final_delivery_binding",
    "validate_s3_final_delivery_binding",
]
