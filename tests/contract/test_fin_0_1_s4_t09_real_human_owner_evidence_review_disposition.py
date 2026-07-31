from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DISPOSITION_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t09_real_human_owner_evidence_review_"
    "disposition_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
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


def test_disposition_binds_scope_and_pending_packet() -> None:
    disposition = _load(DISPOSITION_PATH)
    authority = disposition["authority"]
    assert _sha256(ROOT / authority["scope_decision_ref"]) == (
        authority["scope_decision_sha256"]
    )
    assert _sha256(ROOT / authority["review_packet_ref"]) == (
        authority["review_packet_sha256"]
    )
    assert authority["explicit_owner_response"] == "A"
    assert authority["selected_option_id"] == "A"
    assert authority["selected_disposition"] == (
        "accept_evidence_and_recommend_T10_honest_block"
    )


def test_all_six_findings_are_accepted_without_dispute() -> None:
    disposition = _load(DISPOSITION_PATH)
    findings = disposition["reviewed_findings"]
    assert findings["accepted_finding_count"] == 6
    assert findings["disputed_finding_count"] == 0
    assert len(findings["accepted_finding_ids"]) == 6
    assert findings["disputed_finding_ids"] == []


def test_owner_evidence_review_does_not_inflate_product_or_R3() -> None:
    disposition = _load(DISPOSITION_PATH)
    authority = disposition["authority"]
    assert authority["qualified_senior_R3_attestation_authorized_or_inferred"] is False
    assert authority["S4_pass_release_or_production_authorized_or_inferred"] is False
    track = disposition["qualified_senior_track"]
    assert track["qualified_senior_attestation_created"] is False
    assert track["historical_NVDA_R2_reused_as_R3"] is False
    assert track["owner_review_substituted_for_R3"] is False
    stage = disposition["T09_disposition"]
    assert stage["owner_product_acceptance_for_DELL_or_MU"] is False
    assert stage["qualified_senior_NVDA_R3"] is False
    assert stage["T09_full_pass"] is False


def test_honest_block_carry_forward_is_explicit() -> None:
    disposition = _load(DISPOSITION_PATH)
    stage = disposition["T09_disposition"]
    assert stage["T09_terminal_branch"] == (
        "honest_block_recommendation_complete"
    )
    assert stage["T10_entry"].startswith("ready_for_separate")
    assert stage["T10_recommended_outcome"] == (
        "S4_honestly_blocked_FIN_0_1_not_qualified"
    )
    carry = disposition["carry_forward_recommendation"]
    assert carry["S5_entry_mode"] == "decision_only_honest_block_after_T10"
    assert carry["release_requirements_weakened"] is False


def test_only_the_human_evidence_disposition_record_count_increased() -> None:
    disposition = _load(DISPOSITION_PATH)
    counts = disposition["observed_counts"]
    assert counts["owner_evidence_disposition_records"] == 1
    assert counts["owner_product_acceptance_records"] == 0
    assert counts["qualified_senior_attestations"] == 0
    zero_fields = {
        key: value
        for key, value in counts.items()
        if key
        not in {
            "owner_evidence_disposition_records",
            "owner_product_acceptance_records",
            "qualified_senior_attestations",
        }
    }
    assert set(zero_fields.values()) == {0}


def test_T09_progression_contract_advances_to_T10_scope_without_S4_pass() -> None:
    disposition = _load(DISPOSITION_PATH)
    program = _load(PROGRAM_BACKLOG)
    s4 = _load(S4_BACKLOG)
    program_s4 = next(
        item for item in program["slices"] if item["slice_id"] == "S4"
    )
    program_t09 = next(
        item for item in program_s4["items"] if item["item_id"] == "S4-T09"
    )
    s4_t09 = next(
        item for item in s4["tasks"] if item["item_id"] == "S4-T09"
    )
    assert program_t09["status"].startswith(
        "closed_owner_evidence_review_complete"
    )
    assert s4_t09["status"].startswith("closed_owner_evidence_review_complete")
    expected = "S4-T10-S4-PASS-OR-HONEST-BLOCK-CLOSEOUT-SCOPE-DECISION"
    assert disposition["next_action"] == expected
    assert program["next_action"]["item_id"].startswith("S4-T10-")
    assert s4["current_next_action"].startswith("S4-T10-")
    assert "not_qualified" in program["status"]
