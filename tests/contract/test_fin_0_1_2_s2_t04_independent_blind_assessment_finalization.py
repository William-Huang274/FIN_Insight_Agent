from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.releases.finalize_fin_ia_0_1_2_s2_t04_independent_blind_assessment import (
    BlindAssessmentFinalizationError,
    finalize,
    validate_score_record,
)
from scripts.releases.prepare_fin_ia_0_1_2_s2_t04_identity_sealed_blind_assessment_packet import (
    build_packet,
)


pytestmark = pytest.mark.fast_contract


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _score(packet: dict, *, a: tuple[int, int, int], b: tuple[int, int, int]):
    family_scores = []
    for index, family_id in enumerate(
        (
            "specialist_fact_atoms",
            "claim_candidate_atoms",
            "what_would_change_atoms",
        )
    ):
        candidate_scores = []
        for label, total in (("candidate_A", a[index]), ("candidate_B", b[index])):
            dimensions = {
                "evidence_selection_relevance": 1 if total >= 1 else 0,
                "epistemic_discipline": 1 if total >= 2 else 0,
                "decision_usefulness": 1 if total >= 3 else 0,
                "concise_information_density": max(0, total - 3),
            }
            candidate_scores.append(
                {
                    "label": label,
                    "dimension_scores": dimensions,
                    "family_total": sum(dimensions.values()),
                    "evidence": [f"{family_id} alias-grounded fixture reason"],
                }
            )
        family_scores.append(
            {"family_id": family_id, "candidate_scores": candidate_scores}
        )
    totals = {
        label: sum(
            candidate["family_total"]
            for family in family_scores
            for candidate in family["candidate_scores"]
            if candidate["label"] == label
        )
        for label in ("candidate_A", "candidate_B")
    }
    return {
        "schema_version": "fin_ia_0_1_2_s2_t04_independent_score_record_v1_0",
        "packet_id": packet["packet_id"],
        "mapping_commitment": packet["mapping_commitment"],
        "assessor_attestation": {
            "fresh_context_without_mapping_or_prior_observations": True,
            "read_only_this_packet": True,
            "did_not_guess_or_seek_identity": True,
        },
        "family_scores": family_scores,
        "candidate_totals": totals,
        "comparative_summary": "identity-free fixture summary",
    }


def _prepare(tmp_path: Path, *, mapping_bit: int, score_a, score_b):
    packet_root = tmp_path / "packet"
    build_packet(
        ROOT, packet_root, mapping_bit=mapping_bit, nonce_hex="aa" * 32
    )
    packet = _load(packet_root / "assessor-packet.json")
    score = _score(packet, a=score_a, b=score_b)
    score_path = tmp_path / "score.json"
    score_path.write_text(json.dumps(score), encoding="utf-8")
    return packet_root, packet, score_path


def test_score_validator_requires_exact_attestation_totals_and_dimensions(tmp_path: Path):
    packet_root, packet, score_path = _prepare(
        tmp_path, mapping_bit=0, score_a=(4, 4, 4), score_b=(4, 4, 4)
    )
    score = _load(score_path)
    validated = validate_score_record(score, packet)
    assert validated["candidate_totals"] == {"candidate_A": 12, "candidate_B": 12}
    score["assessor_attestation"]["read_only_this_packet"] = False
    with pytest.raises(BlindAssessmentFinalizationError, match="attestation"):
        validate_score_record(score, packet)


def test_flash_selected_when_quality_gap_is_not_more_than_two(tmp_path: Path):
    packet_root, _, score_path = _prepare(
        tmp_path, mapping_bit=0, score_a=(4, 4, 4), score_b=(4, 5, 5)
    )
    result = finalize(
        packet_path=packet_root / "assessor-packet.json",
        manifest_path=packet_root / "packet-manifest.json",
        score_path=score_path,
        output_root=tmp_path / "final",
    )
    assert result["selection"]["selected_candidate"] == "flash_stable"
    assert result["selection"]["Pro_minus_Flash"] == 2
    assert result["stage_acceptance"]["S2"] == "pass_closed_bounded_model_surface_selected"
    metrics = result["operational_metrics_after_reveal"]
    assert metrics["historical_executed_call_count"] == 8
    assert metrics["effective_scored_call_count"] == 6
    assert metrics["effective_six_total_tokens"] == 10621
    assert metrics["historical_all_eight_executed_calls_estimated_cost_usd"] == 0.00713226
    assert metrics["effective_six_cost_allocation"].startswith("not_available")


def test_pro_selected_only_when_blind_lead_exceeds_two(tmp_path: Path):
    packet_root, _, score_path = _prepare(
        tmp_path, mapping_bit=0, score_a=(4, 4, 4), score_b=(5, 5, 5)
    )
    result = finalize(
        packet_path=packet_root / "assessor-packet.json",
        manifest_path=packet_root / "packet-manifest.json",
        score_path=score_path,
        output_root=tmp_path / "final",
    )
    assert result["selection"]["selected_candidate"] == "pro_preview"
    assert result["selection"]["Pro_minus_Flash"] == 3


def test_selected_candidate_family_below_threshold_moves_local(tmp_path: Path):
    packet_root, _, score_path = _prepare(
        tmp_path, mapping_bit=0, score_a=(4, 3, 4), score_b=(2, 2, 2)
    )
    result = finalize(
        packet_path=packet_root / "assessor-packet.json",
        manifest_path=packet_root / "packet-manifest.json",
        score_path=score_path,
        output_root=tmp_path / "final",
    )
    assert result["selection"]["selected_candidate"] == "flash_stable"
    assert result["retained_model_families"] == [
        "specialist_fact_atoms",
        "what_would_change_atoms",
    ]
    assert result["local_deterministic_or_honest_block_families"] == [
        "claim_candidate_atoms"
    ]


def test_score_is_frozen_before_mapping_reveal_and_identity_is_one_shot(tmp_path: Path):
    packet_root, _, score_path = _prepare(
        tmp_path, mapping_bit=1, score_a=(4, 4, 4), score_b=(4, 4, 4)
    )
    output_root = tmp_path / "final"
    result = finalize(
        packet_path=packet_root / "assessor-packet.json",
        manifest_path=packet_root / "packet-manifest.json",
        score_path=score_path,
        output_root=output_root,
    )
    receipt = _load(output_root / "score-freeze-receipt.json")
    assert receipt["score_frozen_before_mapping_read"] is True
    assert result["score_freeze"]["score_frozen_before_mapping_read"] is True
    with pytest.raises(BlindAssessmentFinalizationError, match="already_claimed"):
        finalize(
            packet_path=packet_root / "assessor-packet.json",
            manifest_path=packet_root / "packet-manifest.json",
            score_path=score_path,
            output_root=output_root,
        )
