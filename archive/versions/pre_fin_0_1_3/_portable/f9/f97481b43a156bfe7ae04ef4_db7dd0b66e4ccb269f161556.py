from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t07_entry_current_worktree_three_case_regression_"
    "and_nvda_post_transfer_exact_revalidation_scope_decision_v1_0.json"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load() -> dict[str, Any]:
    return json.loads(
        DECISION_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_decision_binds_current_code_and_exact_test_package() -> None:
    decision = _load()
    assert decision["status"] == (
        "pass_scope_frozen_one_zero_call_regression_package_authorized_"
        "not_executed_NVDA_exact_live_not_authorized"
    )
    assert decision["authorized_regression_package"]["maximum_packages"] == 1
    assert decision["authorized_regression_package"]["packages_executed"] == 0
    assert decision["authorized_regression_package"]["collected_test_count"] == 97

    bindings = list(decision["current_worktree_bindings"].values())
    bindings.extend(decision["authorized_regression_package"]["test_files"])
    for binding in bindings:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_three_case_and_mutation_acceptance_are_explicit() -> None:
    decision = _load()
    package = decision["authorized_regression_package"]
    assert package["expected_three_case_full_fake"] == {
        "DELL": [6, 12, 12, 9],
        "MU": [6, 12, 12, 9],
        "NVDA": [6, 12, 12, 9],
    }
    negative = set(package["required_negative_and_mutation_matrix"])
    assert {
        "cross_case_and_structural_fixture_fact_leakage_fail_closed",
        "material_numeric_projection_and_rendered_value_mutations_fail_closed",
        "current_case_delivery_identity_mutation_fails_closed",
        "manifest_and_trace_lineage_mutations_fail_closed",
        "terminal_failure_result_is_materialized",
    } <= negative


def test_scope_cannot_reopen_t05_t06_or_auto_run_nvda() -> None:
    decision = _load()
    authority = decision["authority"]
    assert authority["T05_or_T06_reopen_authorized"] is False
    assert authority["credential_presence_or_value_read_authorized"] is False
    assert (
        authority["model_provider_network_source_or_external_tool_call_authorized"]
        is False
    )
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority["NVDA_exact_live_authorized"] is False
    assert (
        authority["paired_assessment_owner_acceptance_or_R3_authorized"]
        is False
    )
    assert set(decision["hard_budgets"].values()) == {0}


def test_regression_pass_only_allows_a_separate_authority_decision() -> None:
    decision = _load()
    progression = decision["stop_and_progression_rule"]
    assert progression["regression_pass_is_product_pass"] is False
    assert progression["regression_pass_is_R3"] is False
    assert progression["all_97_tests_pass"] == (
        "record_current_worktree_engineering_regression_pass_and_make_a_"
        "separate_zero_call_NVDA_exact_live_authority_decision"
    )
    assert decision["next_action"] == (
        "S4-T07-CURRENT-WORKTREE-DELL-MU-NVDA-97-TEST-ZERO-CALL-REGRESSION"
    )
