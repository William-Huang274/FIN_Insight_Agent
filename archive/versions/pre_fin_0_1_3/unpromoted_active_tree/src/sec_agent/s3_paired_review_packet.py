from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_paired_review_packet_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.same_input_claim_only_baseline_paired_review:v1"
CASES = ("DELL", "MU", "NVDA")


class S3PairedReviewPacketError(ValueError):
    pass


def compile_s3_paired_review_packet(
    *,
    binding_decision: Mapping[str, Any],
    claim_decision: Mapping[str, Any],
    writer_decision: Mapping[str, Any],
    quality_policy: Mapping[str, Any],
) -> dict[str, Any]:
    for name, value in (
        ("binding", binding_decision),
        ("claim", claim_decision),
        ("writer", writer_decision),
    ):
        if not _record_digest_ok(value):
            raise S3PairedReviewPacketError(f"s3_paired_review_{name}_digest_invalid")
    bindings = {
        row["case_key"]: row
        for row in binding_decision["final_delivery_binding_program"]["case_bindings"]
    }
    cards = claim_decision["claim_quality_program"]["core_claim_cards"]
    workpapers = {
        row["case_key"]: row
        for row in writer_decision["workpaper_writer_content_program"]["case_workpapers"]
    }
    packets = []
    for case_key in CASES:
        agent = bindings[case_key]
        case_cards = [row for row in cards if row["case_key"] == case_key]
        baseline_body = {
            "case_key": case_key,
            "baseline_type": "deterministic_claim_only_same_input",
            "claim_cards": [
                {
                    "claim_card_id": row["claim_card_id"],
                    "program_cell_id": row["program_cell_id"],
                    "epistemic_state": row["epistemic_state"],
                    "answer_direction": row["answer_direction"],
                    "mechanism_atom": row["mechanism_atom"],
                    "evidence_boundary": deepcopy(row["evidence_boundary"]),
                    "numeric_facts": deepcopy(row["numeric_facts"]),
                    "typed_gaps": deepcopy(row["typed_gaps"]),
                    "what_would_change": deepcopy(row["what_would_change"]),
                }
                for row in case_cards
            ],
            "explicit_non_capabilities": [
                "no_cross_cell_dependency_or_conflict_adjudication",
                "no_executive_thesis_synthesis",
                "no_eight_lens_decision_ready_workpaper",
            ],
        }
        baseline_digest = canonical_digest(baseline_body)
        baseline_verifier_body = {
            "case_key": case_key,
            "final_delivery_digest": baseline_digest,
            "L1_status": "pass",
            "L2_status": "pass",
            "derivation": "claim_only_projection_from_the_same_L1_L2_verified_all_natural_claims",
        }
        baseline_verifier_digest = canonical_digest(baseline_verifier_body)
        agent_context = agent["sealed_candidate_context"]
        baseline_context = deepcopy(agent_context)
        baseline_context.update(
            {
                "workpaper_id": f"fin013_s3_claim_only_baseline_{case_key.lower()}",
                "workpaper_digest": baseline_digest,
                "final_delivery_digest": baseline_digest,
                "verifier_binding_digest": baseline_verifier_digest,
                "run_id": "fin013_s3_claim_only_baseline_" + baseline_digest[:20],
                "artifact_digest": baseline_digest,
            }
        )
        baseline_context["candidate_context_digest"] = canonical_digest(
            {key: value for key, value in baseline_context.items() if key != "candidate_context_digest"}
        )
        dimensions = [
            {
                "dimension_id": row["dimension_id"],
                "name": row["name"],
                "required_reason_ref_types": deepcopy(row["required_reason_ref_types"]),
                "baseline_score": None,
                "agent_score": None,
                "reviewer_reason": None,
                "reason_refs": [],
                "reviewer_confirmed_material_gain": None,
            }
            for row in quality_policy["dimensions"]
        ]
        packet_body = {
            "case_key": case_key,
            "input_head_digest": agent_context["input_head_digest"],
            "baseline": {
                "delivery": {**baseline_body, "final_delivery_digest": baseline_digest},
                "verifier": {**baseline_verifier_body, "verifier_binding_digest": baseline_verifier_digest},
                "sealed_candidate_context": baseline_context,
            },
            "agent": {
                "delivery": deepcopy(agent["delivery"]),
                "verifier": deepcopy(agent["verifier"]),
                "sealed_candidate_context": deepcopy(agent_context),
                "workpaper": deepcopy(workpapers[case_key]),
            },
            "known_quality_findings": [
                "agent_thesis_support_aliases_are_zero",
                "agent_selected_counterevidence_aliases_are_zero",
                "some_agent_sections_repeat_numeric_facts",
                "twenty_nine_dynamic_cells_remain_unresearched",
            ],
            "dimension_review_rows": dimensions,
            "review_state": "prepared_unscored",
            "paired_pass": None,
            "qualified_human_content_acceptance": None,
        }
        packets.append({**packet_body, "packet_digest": canonical_digest(packet_body)})
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "baseline_policy": {
            "same_input_claim_cards_required": True,
            "distinct_run_and_artifact_required": True,
            "baseline_may_use_agent_synthesis": False,
            "old_version_or_fixture_preview_allowed": False,
            "model_calls": 0,
        },
        "case_packets": packets,
        "observed_counts": {
            "case_packets": 3,
            "baseline_deliveries": 3,
            "agent_deliveries": 3,
            "unscored_dimension_rows": 24,
            "formal_score_packets": 0,
            "paired_assessments": 0,
            "qualified_human_acceptances": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "business_runs": 0,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_paired_review_packet(program)
    return program


def validate_s3_paired_review_packet(program: Mapping[str, Any]) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3PairedReviewPacketError("s3_paired_review_program_digest_invalid")
    packets = program.get("case_packets") or []
    if [row.get("case_key") for row in packets] != list(CASES):
        raise S3PairedReviewPacketError("s3_paired_review_case_surface_invalid")
    for packet in packets:
        packet_body = {key: deepcopy(value) for key, value in packet.items() if key != "packet_digest"}
        if packet.get("packet_digest") != canonical_digest(packet_body):
            raise S3PairedReviewPacketError("s3_paired_review_packet_digest_invalid")
        baseline = packet["baseline"]
        agent = packet["agent"]
        baseline_context = baseline["sealed_candidate_context"]
        agent_context = agent["sealed_candidate_context"]
        baseline_delivery = baseline["delivery"]
        baseline_delivery_digest = canonical_digest(
            {
                key: deepcopy(value)
                for key, value in baseline_delivery.items()
                if key != "final_delivery_digest"
            }
        )
        baseline_verifier = baseline["verifier"]
        baseline_verifier_digest = canonical_digest(
            {
                key: deepcopy(value)
                for key, value in baseline_verifier.items()
                if key != "verifier_binding_digest"
            }
        )
        baseline_context_digest = canonical_digest(
            {
                key: deepcopy(value)
                for key, value in baseline_context.items()
                if key != "candidate_context_digest"
            }
        )
        agent_delivery = agent["delivery"]
        agent_claim_ids = sorted(
            {
                claim_id
                for section in agent_delivery.get("sections") or []
                for claim_id in section.get("claim_card_ids") or []
            }
        )
        baseline_claim_ids = sorted(
            row.get("claim_card_id") for row in baseline_delivery.get("claim_cards") or []
        )
        if (
            packet.get("input_head_digest") != agent_context["input_head_digest"]
            or baseline_context["input_head_digest"] != agent_context["input_head_digest"]
            or baseline_context["run_id"] == agent_context["run_id"]
            or baseline_context["artifact_digest"] == agent_context["artifact_digest"]
            or baseline_delivery["baseline_type"] != "deterministic_claim_only_same_input"
            or len(baseline_delivery["claim_cards"]) != 3
            or baseline_claim_ids != agent_claim_ids
        ):
            raise S3PairedReviewPacketError("s3_paired_review_identity_or_baseline_invalid")
        if (
            baseline_delivery.get("final_delivery_digest") != baseline_delivery_digest
            or baseline_verifier.get("final_delivery_digest") != baseline_delivery_digest
            or baseline_verifier.get("verifier_binding_digest") != baseline_verifier_digest
            or baseline_context.get("final_delivery_digest") != baseline_delivery_digest
            or baseline_context.get("artifact_digest") != baseline_delivery_digest
            or baseline_context.get("workpaper_digest") != baseline_delivery_digest
            or baseline_context.get("verifier_binding_digest") != baseline_verifier_digest
            or baseline_context.get("candidate_context_digest") != baseline_context_digest
        ):
            raise S3PairedReviewPacketError("s3_paired_review_baseline_internal_binding_invalid")
        if (
            agent_context.get("final_delivery_digest") != agent_delivery.get("final_delivery_digest")
            or agent_context.get("workpaper_digest") != agent_delivery.get("workpaper_digest")
            or agent_context.get("workpaper_id") != agent_delivery.get("workpaper_id")
            or agent_context.get("verifier_binding_digest")
            != agent["verifier"].get("verifier_binding_digest")
        ):
            raise S3PairedReviewPacketError("s3_paired_review_agent_internal_binding_invalid")
        if len(packet.get("dimension_review_rows") or []) != 8:
            raise S3PairedReviewPacketError("s3_paired_review_dimension_surface_invalid")
        if any(
            row.get(field) is not None
            for row in packet["dimension_review_rows"]
            for field in ("baseline_score", "agent_score", "reviewer_reason", "reviewer_confirmed_material_gain")
        ):
            raise S3PairedReviewPacketError("s3_paired_review_premature_score_or_gain")
        if packet.get("paired_pass") is not None or packet.get("qualified_human_content_acceptance") is not None:
            raise S3PairedReviewPacketError("s3_paired_review_premature_acceptance")


def _record_digest_ok(value: Mapping[str, Any]) -> bool:
    digest = value.get("record_digest")
    return isinstance(digest, str) and digest == canonical_digest(
        {key: deepcopy(item) for key, item in value.items() if key != "record_digest"}
    )


__all__ = [
    "CONTRACT_REF",
    "PROGRAM_SCHEMA",
    "S3PairedReviewPacketError",
    "compile_s3_paired_review_packet",
    "validate_s3_paired_review_packet",
]
