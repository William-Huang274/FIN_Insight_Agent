from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t09_real_human_owner_review_and_qualified_senior_"
    "eligibility_scope_decision_v1_0.json"
)
PACKET_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t09_real_human_owner_evidence_review_packet_v1_0.json"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_binds_current_immutable_evidence() -> None:
    scope = _load(SCOPE_PATH)
    assert scope["status"] == (
        "pass_scope_frozen_owner_evidence_review_eligible_qualified_senior_"
        "R3_ineligible_pending_real_Human_disposition"
    )
    assert len(scope["source_bindings"]) == 7
    for binding in scope["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_scope_separates_owner_review_from_qualified_senior_R3() -> None:
    scope = _load(SCOPE_PATH)
    tracks = scope["review_tracks"]
    assert tracks["owner_product_and_program_evidence_review"]["eligibility"] == (
        "eligible"
    )
    assert tracks["qualified_senior_NVDA_R3_review"]["eligibility"] == (
        "ineligible"
    )
    assert (
        tracks["qualified_senior_NVDA_R3_review"][
            "historical_NVDA_R2_owner_acceptance_reusable_as_R3"
        ]
        is False
    )
    eligibility = scope["eligibility_result"]
    assert eligibility["T09_full_pass_possible_now"] is False
    assert eligibility["T09_honest_block_recommendation_possible_now"] is True
    assert eligibility["T10_may_start_before_explicit_owner_disposition"] is False


def test_continue_was_not_inflated_to_human_acceptance() -> None:
    scope = _load(SCOPE_PATH)
    authority = scope["authority"]
    assert authority["owner_acceptance_or_rejection_inferred"] is False
    assert authority["qualified_senior_identity_or_attestation_inferred"] is False
    assert set(scope["hard_budgets"].values()) == {0}


def test_packet_binds_scope_and_remains_pending() -> None:
    packet = _load(PACKET_PATH)
    authority = packet["authority"]
    assert _sha256(ROOT / authority["scope_decision_ref"]) == (
        authority["scope_decision_sha256"]
    )
    assert packet["status"] == (
        "pending_explicit_real_Human_owner_disposition_no_acceptance_inferred"
    )
    assert len(packet["owner_review_findings"]) == 6
    assert all(
        finding["owner_response"] is None
        for finding in packet["owner_review_findings"]
    )
    assert set(packet["observed_counts"].values()) == {0}


def test_packet_offers_bounded_human_dispositions() -> None:
    packet = _load(PACKET_PATH)
    options = {
        row["option_id"]: row["disposition"]
        for row in packet["owner_disposition_options"]
    }
    assert options == {
        "A": "accept_evidence_and_recommend_T10_honest_block",
        "B": "defer_pending_named_evidence_correction",
        "C": "reject_scope_and_return_to_program_rebaseline",
    }
    assert packet["record_creation_rule"]["plain_continue_is_not_a_disposition"]
    assert packet["record_creation_rule"]["machine_or_Codex_signature_forbidden"]
    assert packet["next_action"] == (
        "AWAIT-EXPLICIT-REAL-HUMAN-OWNER-OPTION-A-B-OR-C"
    )


def test_no_qualified_senior_attestation_is_created() -> None:
    packet = _load(PACKET_PATH)
    track = packet["qualified_senior_track"]
    assert track["status"] == "not_eligible_no_post_transfer_NVDA_candidate"
    assert track["attestation_created"] is False
    assert track["reviewer_identity_bound"] is False
    assert track["reviewer_experience_bound"] is False
    assert track["historical_NVDA_R2_reused"] is False


def test_packet_names_a_separate_future_human_record() -> None:
    packet = _load(PACKET_PATH)
    rule = packet["record_creation_rule"]
    assert rule["future_record_ref"] == (
        "configs/releases/"
        "fin_ia_0_1_s4_t09_real_human_owner_evidence_review_"
        "disposition_v1_0.json"
    )
    assert rule["create_only_after_explicit_Human_option_A_B_or_C"] is True
    assert packet["pending_real_Human_fields"]["explicit_disposition"] is None
