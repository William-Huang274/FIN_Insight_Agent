from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s0c_terminal_honest_block_"
    "repair_owner_version_disposition_v1_0.json"
)
EXPECTED_DECISION_SHA256 = (
    "c79b8918628612f995f0a76e7819998ec873f5f191fd345680084ef3bb59d0d3"
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


def test_disposition_freezes_FIN_0_1_2_without_renamed_gate_bypass() -> None:
    decision = _load(DECISION)
    assert _sha256(DECISION) == EXPECTED_DECISION_SHA256
    assert decision["decision_options"][0]["selected"] is False
    assert decision["decision_options"][1]["selected"] is True
    lineage = decision["selected_version_lineage"]
    assert lineage["FIN_0_1_2"]["status"] == (
        "frozen_internal_honest_block_S0C_terminal_failed_S2_not_entered"
    )
    assert lineage["FIN_0_1_2"]["release_qualified"] is False
    assert lineage["FIN_0_1_2"]["historical_bytes_or_failed_packages_rewritten"] is False
    assert lineage["FIN_0_2"]["original_definition_preserved"] is True
    assert lineage["FIN_0_2"]["common_Runtime_debt_fallback_owner"] is False


def test_disposition_source_bindings_match_current_durable_sources() -> None:
    decision = _load(DECISION)
    for binding in decision["source_bindings"]:
        assert _sha256(ROOT / binding["ref"]) == binding["sha256"]


def test_all_four_open_blockers_transfer_to_new_FIN_0_1_3_S0_owners() -> None:
    decision = _load(DECISION)
    transfers = decision["issue_owner_transfer"]
    assert len(transfers) == 4
    assert {row["issue_id"].split("-")[2] for row in transfers} == {
        "090",
        "091",
        "092",
        "093",
    }
    assert all(row["observed_in"] == "FIN_0_1_2" for row in transfers)
    assert all(row["new_owner"].startswith("FIN_0_1_3_S0_") for row in transfers)


def test_new_S0_has_fixed_non_expanding_budget_and_upstream_closure() -> None:
    decision = _load(DECISION)
    stage = decision["FIN_0_1_3_S0_stage_boundary"]
    assert stage["fixed_task_ids"] == [
        "FIN-0.1.3-S0-T01",
        "FIN-0.1.3-S0-T02",
        "FIN-0.1.3-S0-T03",
        "FIN-0.1.3-S0-T04",
    ]
    budgets = decision["fixed_budgets_and_stop_rules"]
    assert budgets["maximum_implementation_bundles"] == 1
    assert budgets["maximum_formal_two_disposable_proof_packages"] == 1
    assert budgets["automatic_FIN_0_1_3_S0_T05_R_H_or_replacement_family"] is False
    assert budgets["automatic_FIN_0_1_4_on_failure"] is False
    assert budgets["S0C_T03_or_historical_package_rerun"] is False
    scope = decision["T01_stage_plan_required_scope"]
    assert any("active-suite collect-only" in item for item in scope["resource_dependency_contract"])
    assert any("unknown absolute paths fail-closed" in item for item in scope["semantic_environment_contract"])


def test_decision_is_zero_call_and_does_not_enter_S1_S2_or_model_canary() -> None:
    decision = _load(DECISION)
    counts = decision["observed_counts"]
    assert counts["runtime_implementation_files_changed"] == 0
    assert counts["proof_packages_created_or_executed"] == 0
    assert counts["credential_reads_or_probes"] == 0
    assert counts["model_calls"] == 0
    assert counts["provider_calls"] == 0
    assert counts["business_artifacts"] == 0
    truth = decision["product_truth"]
    assert truth["FIN_0_1_3_S0"] == "not_started"
    assert truth["FIN_0_1_3_S1"] == "not_started"
    assert truth["FIN_0_1_3_S2_entry"] is False
    assert truth["FIN_0_1_release_qualified"] is False
    assert decision["next_action"] == (
        "FIN-0.1.3-S0-HERMETIC-RUNTIME-DEPENDENCY-AND-"
        "SEMANTIC-PARITY-STAGE-PLAN"
    )
