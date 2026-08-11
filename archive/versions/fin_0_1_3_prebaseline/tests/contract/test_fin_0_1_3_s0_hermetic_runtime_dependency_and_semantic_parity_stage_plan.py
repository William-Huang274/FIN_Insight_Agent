from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s0_hermetic_runtime_dependency_"
    "and_semantic_parity_stage_plan_v1_0.json"
)
DISPOSITION_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0c_terminal_honest_block_"
    "repair_owner_version_disposition_v1_0.json"
)
CLOSEOUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0c_t03_corrective_hermetic_proof_"
    "and_terminal_honest_block_closeout_v1_0.json"
)
EXPECTED_PLAN_SHA256 = (
    "034c7714e5773fe48b0d69ed6ab373ba02074e497d803bcd73349932f2177000"
)
EXPECTED_ISSUES = {
    "RC-P36-090-fin-0-1-2-pre-s2-t03-disposable-self-introspection-git-inventory-dependency",
    "RC-P36-091-fin-0-1-2-hermetic-package-recursive-json-ref-admits-ignored-runtime-state",
    "RC-P36-092-fin-0-1-2-code-declared-static-runtime-resource-missing-from-hermetic-inventory",
    "RC-P36-093-fin-0-1-2-hermetic-semantic-parity-untyped-host-python-traceback-path",
}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_plan(plan: dict[str, Any]) -> None:
    assert plan["status"] == "G0_pass_T01_complete_T02_ready_zero_call"
    assert plan["G0_scope_and_owner"]["verdict"] == "pass"
    assert [row["task_id"] for row in plan["fixed_tasks"]] == [
        "FIN-0.1.3-S0-T01",
        "FIN-0.1.3-S0-T02",
        "FIN-0.1.3-S0-T03",
        "FIN-0.1.3-S0-T04",
    ]
    assert [row["status"] for row in plan["fixed_tasks"]] == [
        "pass_current_artifact",
        "ready_not_started",
        "locked_until_T02_all_green",
        "locked_until_T03_all_green",
    ]
    issue_rows = plan["G0_scope_and_owner"]["issue_ownership"]
    assert {row["issue_id"] for row in issue_rows} == EXPECTED_ISSUES
    assert len({row["owner"] for row in issue_rows}) == 4

    registry = plan["resource_dependency_contract"]
    assert registry["authority"].startswith("RuntimeResourceRegistry_")
    assert set(registry["required_row_fields"]) == {
        "resource_id",
        "repo_relative_path",
        "sha256",
        "bytes",
        "classification",
        "consumer_ids",
        "load_phase",
        "required",
        "source_owner",
    }
    assert any("direct_unregistered" in row for row in registry["rules"])
    assert any("ignored_untracked" in row for row in registry["rules"])

    environment = plan["typed_environment_semantic_parity_contract"]
    assert {
        "sys_prefix",
        "sys_base_prefix",
        "purelib_root",
        "platlib_root",
        "installed_distribution_roots",
    }.issubset(environment["typed_roots"])
    assert "unknown_absolute_paths_fail_closed" in environment[
        "normalization_boundary"
    ]
    assert "business_value_that_looks_like_a_path" in environment[
        "mutation_matrix"
    ]

    proof = plan["T03_zero_call_engineering_proof"]
    assert any("DELL_MU_NVDA_each_6_nodes" in row for row in proof["required_matrix"])
    assert any("final_nine_numeric_identity" in row for row in proof["required_matrix"])
    assert any("downstream_failure_capture" in row for row in proof["required_matrix"])
    formal = plan["T04_formal_proof_and_closeout"]
    assert any("two_fresh_disposable_roots" in row for row in formal["required_conditions"])
    assert any("all_current_tests_collect_import_and_execute" in row for row in formal["required_conditions"])

    budgets = plan["budgets"]
    assert budgets["maximum_implementation_bundles"] == 1
    assert budgets["maximum_formal_two_disposable_proof_packages"] == 1
    assert all(
        budgets[field] == 0
        for field in (
            "model_calls",
            "provider_calls",
            "credential_reads_or_probes",
            "business_network_or_source_calls",
            "new_admissions",
            "business_runs",
            "business_artifacts",
            "automatic_T05_R_H_replacement_or_FIN_0_1_4",
        )
    )
    assert plan["observed_counts"]["runtime_implementation_files_changed"] == 0
    assert plan["observed_counts"][
        "formal_two_disposable_proof_packages_created_or_executed"
    ] == 0
    assert plan["product_truth"]["FIN_0_1_release_qualified"] is False
    assert plan["product_truth"]["FIN_0_2_definition_changed"] is False
    assert plan["next_action"] == (
        "FIN-0.1.3-S0-RUNTIME-RESOURCE-REGISTRY-AND-TYPED-ENVIRONMENT-"
        "PROJECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_stage_plan_is_immutable_duplicate_key_free_and_contract_valid() -> None:
    assert _sha256(PLAN_PATH) == EXPECTED_PLAN_SHA256
    _validate_plan(_load(PLAN_PATH))


def test_stage_plan_binds_the_two_immutable_parent_decisions() -> None:
    plan = _load(PLAN_PATH)
    bindings = {row["role"]: row for row in plan["source_bindings"]}
    assert bindings[
        "FIN_0_1_2_terminal_repair_owner_and_version_disposition"
    ]["sha256"] == _sha256(DISPOSITION_PATH)
    assert bindings[
        "FIN_0_1_2_S0C_terminal_failed_proof_closeout"
    ]["sha256"] == _sha256(CLOSEOUT_PATH)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update(status="S0_pass"),
        lambda value: value["fixed_tasks"].append(
            {"task_id": "FIN-0.1.3-S0-T05", "status": "ready"}
        ),
        lambda value: value["G0_scope_and_owner"]["issue_ownership"].pop(),
        lambda value: value["resource_dependency_contract"]["rules"].pop(),
        lambda value: value["typed_environment_semantic_parity_contract"].update(
            typed_roots=["disposable_repository_root"]
        ),
        lambda value: value["budgets"].update(model_calls=1),
        lambda value: value["budgets"].update(
            maximum_formal_two_disposable_proof_packages=2
        ),
        lambda value: value["product_truth"].update(
            FIN_0_1_release_qualified=True
        ),
    ],
)
def test_scope_budget_and_product_truth_mutations_fail_closed(mutator: Any) -> None:
    plan = deepcopy(_load(PLAN_PATH))
    mutator(plan)
    with pytest.raises(AssertionError):
        _validate_plan(plan)


def test_T01_immutably_records_that_prospective_contracts_were_not_created() -> None:
    plan = _load(PLAN_PATH)
    assert len(plan["prospective_contract_refs"]) == 6
    assert plan["observed_counts"]["runtime_implementation_files_changed"] == 0
    assert plan["observed_counts"]["implementation_bundles_executed"] == 0
    assert plan["authority"]["runtime_implementation_executed_by_this_plan"] is False


def test_T01_did_not_authorize_execution_or_product_reproof() -> None:
    plan = _load(PLAN_PATH)
    authority = plan["authority"]
    assert authority["runtime_implementation_executed_by_this_plan"] is False
    assert authority["proof_package_created_or_executed_by_this_plan"] is False
    assert authority["model_provider_credential_network_execution_authorized"] is False
    assert authority["S1_S2_transfer_product_or_release_execution_authorized"] is False
