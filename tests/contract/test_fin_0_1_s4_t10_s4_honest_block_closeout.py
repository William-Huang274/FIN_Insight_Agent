from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
CLOSEOUT = RELEASES / "fin_ia_0_1_s4_t10_s4_honest_block_closeout_decision_v1_0.json"
MANIFEST = RELEASES / (
    "fin_ia_0_1_s4_to_s5_honest_block_carry_forward_and_revalidation_manifest_v1_0.json"
)
PROGRAM = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG = RELEASES / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_source_bindings_are_current() -> None:
    manifest = _load(MANIFEST)
    assert len(manifest["source_bindings"]) == 10
    for binding in manifest["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_closeout_binds_manifest_and_forces_honest_block() -> None:
    closeout = _load(CLOSEOUT)
    assert closeout["status"] == (
        "terminal_S4_honestly_blocked_FIN_0_1_not_qualified_"
        "S5_decision_only_handoff_ready"
    )
    assert closeout["carry_forward"]["manifest_sha256"] == _sha256(MANIFEST)
    truth = closeout["pass_gate_truth"]
    assert truth["NVDA_historical_S3_R2_owner_accepted"] is True
    assert truth["owner_option_A_evidence_disposition_complete"] is True
    for field in (
        "DELL_R2",
        "MU_R2",
        "NVDA_post_transfer_exact_product_present",
        "NVDA_qualified_senior_R3",
        "T07_all_green",
        "three_case_R2_requirement_satisfied",
        "S4_pass",
        "FIN_0_1_release_qualified",
    ):
        assert truth[field] is False


def test_carry_forward_has_separate_s5_and_fin_0_1_2_owners() -> None:
    manifest = _load(MANIFEST)
    rows = {row["item_id"]: row for row in manifest["carry_forward_items"]}
    assert len(rows) == 8
    assert rows["CF-S5-04"]["owner"] == "FIN_0_1_1_S5_decision_only"
    assert rows["CF-012-S0-01"]["owner"] == "FIN_0_1_2_S0"
    assert rows["CF-012-S4-01"]["owner"] == "FIN_0_1_2_S4"
    assert manifest["release_gate_snapshot"]["release_candidate_execution_allowed"] is False
    assert manifest["non_inflation"]["FIN_0_2_definition_changed"] is False


def test_closeout_is_zero_call_and_does_not_enter_s5() -> None:
    closeout = _load(CLOSEOUT)
    assert set(closeout["observed_counts"].values()) == {0}
    assert closeout["authority"]["S5_entry_executed_by_this_record"] is False
    assert closeout["stage_decision"]["S4"] == "closed_honestly_blocked"
    assert closeout["stage_decision"]["S5"] == (
        "decision_only_honest_block_handoff_ready_not_entered"
    )
    assert closeout["stage_decision"]["release"] == "not_qualified_not_authorized"


def test_backlogs_record_terminal_t10_without_release_inflation() -> None:
    program = _load(PROGRAM)
    s4 = _load(S4_BACKLOG)
    program_s4 = next(row for row in program["slices"] if row["slice_id"] == "S4")
    program_s5 = next(row for row in program["slices"] if row["slice_id"] == "S5")
    program_t10 = next(row for row in program_s4["items"] if row["item_id"] == "S4-T10")
    s4_t10 = next(row for row in s4["tasks"] if row["item_id"] == "S4-T10")
    expected = "closed_terminal_honest_block_FIN_0_1_not_qualified"
    assert program_s4["status"] == expected
    assert program_t10["status"] == expected
    assert s4_t10["status"] == expected
    assert program_s5["status"] == "closed_honestly_blocked_decision_only_no_release_candidate"
    assert s4["non_inflation"]["S4_passed"] is False
    assert s4["non_inflation"]["S5_entry_ready"] is True
    assert s4["non_inflation"]["Alpha_release_or_production"] is False
    assert program["next_action"]["item_id"] == s4["current_next_action"]
