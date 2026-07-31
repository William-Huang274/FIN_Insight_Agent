from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
INVENTORY = RELEASES / "fin_ia_0_1_s5_blocked_release_evidence_inventory_v1_0.json"
DECISION = RELEASES / (
    "fin_ia_0_1_s5_decision_only_honest_block_handoff_and_release_decision_v1_0.json"
)
PROGRAM = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG = RELEASES / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_inventory_and_decision_source_bindings_are_current() -> None:
    for document in (_load(INVENTORY), _load(DECISION)):
        for binding in document["source_bindings"]:
            path = ROOT / binding["ref"]
            assert path.is_file()
            assert _sha256(path) == binding["sha256"]
    decision = _load(DECISION)
    inventory_binding = next(
        row for row in decision["source_bindings"] if row["role"] == "S5_blocked_release_evidence_inventory"
    )
    assert inventory_binding["sha256"] == _sha256(INVENTORY)


def test_inventory_separates_accepted_diagnostic_and_recovery_evidence() -> None:
    inventory = _load(INVENTORY)
    product = inventory["product_evidence"]
    assert product["NVDA"]["accepted_artifacts"] == 9
    assert product["DELL"]["coherent_agent_artifacts_observed"] == 9
    assert product["MU"]["coherent_agent_artifacts_observed"] == 9
    assert product["DELL"]["L1_pass"] is False
    assert product["MU"]["L1_pass"] is False
    assert product["agent_artifacts_observed_total"] == 27
    assert product["agent_artifacts_accepted_total"] == 9
    assert inventory["repository_and_recovery"]["potential_plaintext_secret_paths"] == 0
    assert inventory["capture_and_failure_inventory"][
        "complete_content_addressed_stdout_stderr_for_every_historical_proof"
    ] is False


def test_release_gates_force_terminal_honest_block() -> None:
    decision = _load(DECISION)
    gates = decision["release_gates"]
    for gate in ("RG1_vertical_path", "RG2_evidence_numeric_integrity", "RG3_research_outcome", "RG4_review_product_value"):
        assert gates[gate]["verdict"] == "blocked"
        assert gates[gate]["release_candidate_execution_allowed"] is False
    assert gates["RG5_release_rollback"]["verdict"] == "pass_internal_recoverability_only"
    assert gates["RG5_release_rollback"]["may_override_RG1_to_RG4"] is False
    release = decision["release_decision"]
    assert release["S5"] == "closed_honestly_blocked_decision_only"
    assert release["FIN_0_1_release_qualified"] is False
    assert release["release_candidate_created"] is False
    assert release["decision_is_terminal_for_FIN_0_1_1_S5"] is True


def test_s5_is_zero_call_and_hands_off_to_internal_freeze() -> None:
    decision = _load(DECISION)
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["next_action"] == "FIN-0.1.1-INTERNAL-HONEST-BLOCK-BASELINE-FREEZE"
    assert "FIN_0_1_2_S0" in decision["remaining_ownership"]
    assert decision["non_inflation"]["FIN_0_2_definition_changed"] is False


def test_program_and_s4_backlog_record_s5_terminal_decision() -> None:
    program = _load(PROGRAM)
    s4 = _load(S4_BACKLOG)
    s5 = next(row for row in program["slices"] if row["slice_id"] == "S5")
    assert s5["status"] == "closed_honestly_blocked_decision_only_no_release_candidate"
    assert len(s5["items"]) == 5
    assert s5["items"][-1]["status"] == "terminal_honest_block_no_release_candidate"
    assert program["next_action"]["item_id"] == "FIN-0.1.1-INTERNAL-HONEST-BLOCK-BASELINE-FREEZE"
    assert program["next_action"]["S5_entered"] is True
    assert s4["current_next_action"] == "FIN-0.1.1-INTERNAL-HONEST-BLOCK-BASELINE-FREEZE"
    assert s4["T10_honest_block_closeout_scope"]["S5_entered"] is True
    assert s4["non_inflation"]["Alpha_release_or_production"] is False
