from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RUNTIME = ROOT / "configs" / "runtime"
CONTRACT_TESTS = ROOT / "tests" / "contract"
DECISION = RELEASES / (
    "fin_ia_0_1_2_s5_decision_only_honest_block_candidate_freeze_"
    "and_fin_0_1_3_handoff_v1_0.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    return []


def test_source_bindings_are_content_addressed_and_current() -> None:
    decision = _load(DECISION)
    for binding in decision["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_freeze_preserves_progress_without_inflating_release_truth() -> None:
    decision = _load(DECISION)
    truth = decision["frozen_product_truth"]
    assert truth["current_projection"] == {
        "cases": 3,
        "case_keys": ["DELL", "MU", "NVDA"],
        "evidence_rows": 45,
        "numeric_rows": 9,
        "typed_gaps": 9,
        "approved_graph_edges": 0,
        "business_artifacts": 27,
        "bounded_owner_R2_acceptances": 3,
    }
    assert set(truth["preserved_progress"].values()) == {True}
    assert truth["release_blockers"]["DELL_financial_period_duration_L1"].endswith(
        "RC_P36_130"
    )
    assert truth["release_qualified"] is False
    assert truth["production_ready"] is False


def test_known_gate_inputs_force_decision_only_honest_block() -> None:
    decision = _load(DECISION)
    gates = decision["decision_only_release_gate_reconciliation"]
    assert gates["formal_candidate_gate_execution_performed"] is False
    for gate in (
        "RG1_vertical_current_workflow",
        "RG2_financial_truth_and_evidence_authority",
        "RG3_research_content_outcome",
        "RG4_qualified_product_use",
    ):
        assert gates[gate]["verdict"] == "blocked_known_input"
    assert gates["RG5_release_recovery_security_and_cost"]["verdict"] == (
        "pass_internal_recoverability_only"
    )
    assert gates["RG5_release_recovery_security_and_cost"]["may_override_RG1_to_RG4"] is False
    release = decision["release_decision"]
    assert release["FIN_0_1_2_S5"] == "closed_honestly_blocked_decision_only"
    assert release["FIN_0_1_2_release_qualified"] is False
    assert release["decision_is_terminal_for_FIN_0_1_2"] is True


def test_old_FIN_0_1_3_namespace_is_visible_but_not_promoted() -> None:
    decision = _load(DECISION)
    namespace = decision["historical_FIN_0_1_3_namespace_collision"]
    observed = {
        "release_configs": len(list(RELEASES.glob("fin_ia_0_1_3*.json"))),
        "runtime_configs": len(list(RUNTIME.glob("fin_ia_0_1_3*.json"))),
        "contract_tests": len(list(CONTRACT_TESTS.glob("test_fin_0_1_3*.py"))),
    }
    assert observed == {
        "release_configs": 18,
        "runtime_configs": 16,
        "contract_tests": 13,
    }
    assert sum(observed.values()) == namespace["historical_files_present"]["total"]
    old_active_manifest = _load(
        RELEASES / "fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_3.json"
    )
    old_refs = [value for value in _strings(old_active_manifest) if "0_1_3" in value]
    assert len(old_refs) == namespace["pre_handoff_active_manifest_old_FIN_0_1_3_references"]
    assert namespace["status"] == "open_owned_by_013_S0_01"
    assert namespace["S5_disposition"].startswith("record_and_handoff")


def test_closeout_is_zero_call_and_enters_only_FIN_0_1_3_S0_01() -> None:
    decision = _load(DECISION)
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["FIN_0_1_3_handoff"]["FIN_0_2_definition_changed"] is False
    assert decision["FIN_0_1_3_handoff"]["old_R2_or_R3_may_auto_promote_after_changed_input_data_or_contract"] is False
    assert decision["next_action"] == (
        "FIN-0.1.3-S0-01-DELTA-INHERITANCE-NAMESPACE-AND-SECRET-SAFE-"
        "CURRENT-TRUTH-BASELINE"
    )
