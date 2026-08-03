from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


FAMILIES = (
    "specialist_fact_atoms",
    "claim_candidate_atoms",
    "what_would_change_atoms",
)
LABELS = ("candidate_A", "candidate_B")
DIMENSIONS = (
    "evidence_selection_relevance",
    "epistemic_discipline",
    "decision_usefulness",
    "concise_information_density",
)
EXPECTED_PACKET_ID = (
    "FIN-0.1.2-S2-T04-IDENTITY-SEALED-BLIND-ASSESSMENT-PACKET-R1"
)


class BlindAssessmentFinalizationError(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_score_record(
    score: Mapping[str, Any], packet: Mapping[str, Any]
) -> dict[str, Any]:
    if score.get("schema_version") != (
        "fin_ia_0_1_2_s2_t04_independent_score_record_v1_0"
    ):
        raise BlindAssessmentFinalizationError("score_schema_invalid")
    if score.get("packet_id") != EXPECTED_PACKET_ID:
        raise BlindAssessmentFinalizationError("score_packet_id_invalid")
    if score.get("packet_id") != packet.get("packet_id"):
        raise BlindAssessmentFinalizationError("score_packet_binding_mismatch")
    if score.get("mapping_commitment") != packet.get("mapping_commitment"):
        raise BlindAssessmentFinalizationError("score_mapping_commitment_mismatch")
    expected_attestation = {
        "fresh_context_without_mapping_or_prior_observations": True,
        "read_only_this_packet": True,
        "did_not_guess_or_seek_identity": True,
    }
    if score.get("assessor_attestation") != expected_attestation:
        raise BlindAssessmentFinalizationError("assessor_attestation_invalid")

    family_scores = score.get("family_scores")
    if not isinstance(family_scores, list) or len(family_scores) != 3:
        raise BlindAssessmentFinalizationError("exact_three_family_scores_required")
    by_family: dict[str, dict[str, Any]] = {}
    computed_totals = {label: 0 for label in LABELS}
    for family in family_scores:
        family_id = family.get("family_id")
        if family_id not in FAMILIES or family_id in by_family:
            raise BlindAssessmentFinalizationError("family_score_identity_invalid")
        candidate_scores = family.get("candidate_scores")
        if not isinstance(candidate_scores, list) or len(candidate_scores) != 2:
            raise BlindAssessmentFinalizationError(
                f"exact_two_candidate_scores_required:{family_id}"
            )
        normalized_candidates: dict[str, dict[str, Any]] = {}
        for candidate in candidate_scores:
            label = candidate.get("label")
            if label not in LABELS or label in normalized_candidates:
                raise BlindAssessmentFinalizationError(
                    f"candidate_label_invalid:{family_id}"
                )
            dimensions = candidate.get("dimension_scores")
            if not isinstance(dimensions, dict) or set(dimensions) != set(
                DIMENSIONS
            ):
                raise BlindAssessmentFinalizationError(
                    f"dimension_set_invalid:{family_id}:{label}"
                )
            if any(
                type(dimensions[dimension]) is not int
                or not 0 <= dimensions[dimension] <= 2
                for dimension in DIMENSIONS
            ):
                raise BlindAssessmentFinalizationError(
                    f"dimension_score_invalid:{family_id}:{label}"
                )
            family_total = sum(dimensions[dimension] for dimension in DIMENSIONS)
            if candidate.get("family_total") != family_total:
                raise BlindAssessmentFinalizationError(
                    f"family_total_invalid:{family_id}:{label}"
                )
            evidence = candidate.get("evidence")
            if (
                not isinstance(evidence, list)
                or not evidence
                or any(not isinstance(row, str) or not row.strip() for row in evidence)
            ):
                raise BlindAssessmentFinalizationError(
                    f"score_evidence_invalid:{family_id}:{label}"
                )
            normalized_candidates[label] = dict(candidate)
            computed_totals[label] += family_total
        by_family[family_id] = normalized_candidates

    if set(by_family) != set(FAMILIES):
        raise BlindAssessmentFinalizationError("family_set_invalid")
    if score.get("candidate_totals") != computed_totals:
        raise BlindAssessmentFinalizationError("candidate_totals_invalid")
    if not isinstance(score.get("comparative_summary"), str) or not score[
        "comparative_summary"
    ].strip():
        raise BlindAssessmentFinalizationError("comparative_summary_invalid")
    return {
        "by_family": by_family,
        "candidate_totals": computed_totals,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BlindAssessmentFinalizationError(f"missing_file:{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def finalize(
    *,
    packet_path: Path,
    manifest_path: Path,
    score_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    packet_path = packet_path.resolve()
    manifest_path = manifest_path.resolve()
    score_path = score_path.resolve()
    output_root = output_root.resolve()
    final_result_path = output_root / "finalization-result.json"
    score_receipt_path = output_root / "score-freeze-receipt.json"
    if final_result_path.exists() or score_receipt_path.exists():
        raise BlindAssessmentFinalizationError(
            "blind_assessment_finalization_identity_already_claimed"
        )

    manifest = _load_json(manifest_path)
    packet_raw = packet_path.read_bytes()
    if _sha256(packet_raw) != manifest.get("packet_sha256"):
        raise BlindAssessmentFinalizationError("packet_digest_mismatch")
    packet = json.loads(packet_raw.decode("utf-8"))
    score = _load_json(score_path)
    normalized = validate_score_record(score, packet)

    # Freeze and read back the score before opening the identity mapping.
    score_raw = _canonical_bytes(score)
    score_sha = _sha256(score_raw)
    score_object_path = (
        output_root
        / "restricted-score-objects"
        / score_sha[:2]
        / score_sha[2:4]
        / f"{score_sha}.json"
    )
    _atomic_write(score_object_path, score_raw)
    score_receipt = {
        "schema_version": "fin_ia_0_1_2_s2_t04_score_freeze_receipt_v1_0",
        "packet_id": EXPECTED_PACKET_ID,
        "packet_sha256": manifest["packet_sha256"],
        "mapping_commitment": packet["mapping_commitment"],
        "score_sha256": score_sha,
        "score_object_ref": str(score_object_path),
        "score_schema_valid": True,
        "score_frozen_before_mapping_read": True,
    }
    _atomic_write(score_receipt_path, _canonical_bytes(score_receipt))
    if _sha256(score_object_path.read_bytes()) != score_sha:
        raise BlindAssessmentFinalizationError("score_readback_digest_mismatch")

    mapping_commitment = packet["mapping_commitment"]
    if not mapping_commitment.startswith("sha256:"):
        raise BlindAssessmentFinalizationError("mapping_commitment_invalid")
    mapping_sha = mapping_commitment.removeprefix("sha256:")
    mapping_path = Path(manifest["restricted_mapping_ref"])
    mapping_raw = mapping_path.read_bytes()
    if _sha256(mapping_raw) != mapping_sha:
        raise BlindAssessmentFinalizationError("mapping_digest_mismatch")
    mapping = json.loads(mapping_raw.decode("utf-8"))
    label_to_candidate = mapping.get("label_to_candidate")
    if set(label_to_candidate or {}) != set(LABELS) or set(
        label_to_candidate.values()
    ) != {"flash_stable", "pro_preview"}:
        raise BlindAssessmentFinalizationError("mapping_shape_invalid")

    score_by_candidate = {
        candidate: normalized["candidate_totals"][label]
        for label, candidate in label_to_candidate.items()
    }
    flash_score = score_by_candidate["flash_stable"]
    pro_score = score_by_candidate["pro_preview"]
    if pro_score - flash_score > 2:
        selected_candidate = "pro_preview"
        selection_reason = "Pro_blind_quality_lead_exceeds_two_points"
    else:
        selected_candidate = "flash_stable"
        selection_reason = "stable_preference_quality_gap_not_more_than_two_points"
    selected_label = {
        candidate: label for label, candidate in label_to_candidate.items()
    }[selected_candidate]

    retained_families: list[str] = []
    local_families: list[str] = []
    family_disposition: dict[str, Any] = {}
    for family_id in FAMILIES:
        selected_score = normalized["by_family"][family_id][selected_label]
        dimensions = selected_score["dimension_scores"]
        retained = (
            selected_score["family_total"] >= 4
            and dimensions["evidence_selection_relevance"] >= 1
            and dimensions["epistemic_discipline"] >= 1
            and dimensions["decision_usefulness"] >= 1
        )
        if retained:
            retained_families.append(family_id)
            owner = "selected_model_candidate"
        else:
            local_families.append(family_id)
            owner = "local_deterministic_or_honest_block"
        family_disposition[family_id] = {
            "selected_candidate_family_total": selected_score["family_total"],
            "selected_candidate_dimension_scores": dimensions,
            "retained_model_surface": retained,
            "owner": owner,
        }

    if not retained_families:
        selected_candidate = "no_model"
        selected_label = None
        selection_reason = "selected_candidate_retained_zero_families"
        s2_status = "honest_block_no_model_surface"
        s3_eligible = False
    else:
        s2_status = "pass_closed_bounded_model_surface_selected"
        s3_eligible = True

    model_refs = {
        "flash_stable": "deepseek:deepseek-v4-flash",
        "pro_preview": "deepseek:deepseek-v4-pro",
        "no_model": None,
    }
    lifecycle = {
        "flash_stable": "stable_API_only",
        "pro_preview": "preview_historical_control",
        "no_model": "not_applicable",
    }
    result = {
        "schema_version": "fin_ia_0_1_2_s2_t04_independent_blind_assessment_finalization_v1_0",
        "result_id": "FIN-0.1.2-S2-T04-INDEPENDENT-BLIND-ASSESSMENT-AND-S2-CLOSEOUT-R1",
        "status": "pass_independent_score_frozen_mapping_revealed_and_rules_applied",
        "packet_binding": {
            "packet_id": EXPECTED_PACKET_ID,
            "packet_sha256": manifest["packet_sha256"],
            "mapping_commitment": mapping_commitment,
        },
        "score_freeze": {
            "score_sha256": score_sha,
            "score_frozen_before_mapping_read": True,
            "assessor_attestation": score["assessor_attestation"],
            "independent_evaluator_contexts": 1,
        },
        "blind_scores_by_label": normalized["candidate_totals"],
        "revealed_scores_by_candidate": score_by_candidate,
        "selection": {
            "selected_candidate": selected_candidate,
            "selected_model_ref": model_refs[selected_candidate],
            "selected_lifecycle": lifecycle[selected_candidate],
            "reason": selection_reason,
            "Flash_score": flash_score,
            "Pro_score": pro_score,
            "Pro_minus_Flash": pro_score - flash_score,
            "automatic_runtime_fallback": False,
        },
        "family_surface_disposition": family_disposition,
        "retained_model_families": retained_families,
        "local_deterministic_or_honest_block_families": local_families,
        "operational_metrics_after_reveal": {
            "historical_executed_call_count": 8,
            "effective_scored_call_count": 6,
            "invalid_historical_WWC_call_count": 2,
            "effective_six_input_tokens": 9468,
            "effective_six_output_tokens": 1153,
            "effective_six_total_tokens": 10621,
            "effective_six_tokens_by_candidate": {
                "flash_stable": {"input": 4734, "output": 569, "total": 5303},
                "pro_preview": {"input": 4734, "output": 584, "total": 5318},
            },
            "effective_six_latency_ms_by_candidate": {
                "flash_stable": 5222,
                "pro_preview": 7446,
            },
            "historical_all_eight_executed_calls_estimated_cost_usd": 0.00713226,
            "effective_six_cost_allocation": "not_available_from_aggregated_run_evidence",
            "comparison_role": "post_score_context_only_not_selection_override",
        },
        "issue_disposition": {
            "issue_id": "RC-P36-104-fin-0-1-2-s2-t04-same-context-model-identity-contamination-and-unsealed-blind-assessment",
            "status": "closed_independent_context_score_freeze_before_reveal_pass",
        },
        "stage_acceptance": {
            "S2_T04": "pass",
            "S2": s2_status,
            "S3_eligible": s3_eligible,
            "S3_started": False,
            "release_qualified": False,
        },
        "observed_counts": {
            "product_model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
            "independent_evaluator_contexts": 1,
            "business_Run_or_Artifact_writes": 0,
        },
        "next_action": (
            "FIN-0.1.2-S3-STAGE-PLAN-AND-BOUNDED-MODEL-SURFACE-ENTRY-DECISION"
            if s3_eligible
            else "FIN-0.1.2-S2-HONEST-BLOCK-AND-NO-MODEL-SURFACE-DISPOSITION"
        ),
    }
    _atomic_write(final_result_path, _canonical_bytes(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(
        packet_path=args.packet,
        manifest_path=args.manifest,
        score_path=args.score,
        output_root=args.output_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
