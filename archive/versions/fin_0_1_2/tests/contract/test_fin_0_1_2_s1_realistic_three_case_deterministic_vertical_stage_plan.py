from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_realistic_three_case_"
    "deterministic_vertical_stage_plan_v1_0.json"
)
CAPSULE_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_capsule_v1_0.json"
)
PRE_S2_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_to_s2_hermetic_fixture_"
    "resource_blocker_disposition_v1_0.json"
)
PRE_S2_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_pre_s2_hermetic_fixture_resource_"
    "rebaseline_minimum_zero_call_implementation_v1_0.json"
)
S0_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0_common_runtime_and_"
    "test_contract_rebaseline_v1_0.json"
)
SOURCE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_"
    "family_source_v1_0.json"
)

EXPECTED_CONSUMERS = {
    "prompt",
    "server_schema",
    "local_validator",
    "fake_provider",
    "selector",
    "renderer",
    "capacity",
    "budget",
    "typed_failure",
    "capture_index",
}
EXPECTED_CASES = ["DELL", "MU", "NVDA"]
EXPECTED_CELLS = [
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
]


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
    assert plan["status"] == (
        "S1_stage_plan_G0_pass_implementation_not_started"
    )
    assert plan["gates"]["G0_scope_and_owner"]["verdict"] == "pass"
    assert plan["gates"]["G1_contract_closure"]["verdict"].startswith(
        "pending_"
    )
    assert plan["gates"]["G2_deterministic_proof"]["verdict"].startswith(
        "pending_"
    )
    assert plan["gates"]["G3_natural_canary"]["owner"] == "FIN_0_1_2_S2"
    assert plan["gates"]["G5_formal_product_proof"]["owner"] == (
        "FIN_0_1_2_S2_through_S4"
    )
    assert [row["task_id"] for row in plan["fixed_task_budget"]] == [
        "S1-T01",
        "S1-T02",
        "S1-T03",
        "S1-T04",
    ]
    consumers = plan["consumer_migration"]
    assert len(consumers) == 10
    assert {row["consumer_id"] for row in consumers} == EXPECTED_CONSUMERS
    assert plan["consumer_migration_rule"]["required_consumer_count"] == 10
    assert plan["consumer_migration_rule"][
        "admission_optional_policy_activation_forbidden"
    ]
    fixture = plan["realistic_fixture_matrix"]
    assert fixture["cases"] == EXPECTED_CASES
    assert fixture["cells"] == EXPECTED_CELLS
    assert fixture["case_cell_pairs"] == 9
    assert plan["proof_matrix"]["candidate_counts"] == [
        0,
        1,
        3,
        6,
        7,
        22,
        76,
    ]
    mutations = set(plan["proof_matrix"]["negative_mutations"])
    assert {
        "cross_case_alias",
        "invalid_or_unbound_date_alias",
        "numeric_metric_value_period_unit_scale_sign_source_correspondence_mutation",
        "final_nine_artifact_identity_numeric_or_lineage_mutation",
        "Lead_Writer_or_Verifier_downstream_failure_after_prior_captures",
    }.issubset(mutations)
    assert not plan["proof_matrix"]["collect_all"][
        "invalid_output_promotable"
    ]
    budgets = plan["budgets"]
    assert budgets["stage_artifacts"] == {
        "StagePlan": 1,
        "StageCapsule": 1,
        "StageAssessment": 1,
        "StageCloseout": 1,
        "worklog": 1,
    }
    assert all(
        budgets[field] == 0
        for field in (
            "model_calls",
            "provider_calls",
            "business_network_or_source_calls",
            "new_admissions",
            "business_runs",
            "business_artifacts",
            "automatic_replacement_or_R_number_families",
        )
    )
    generalized_owner = plan["scope_boundary"]["FIN_0_2_owned"]
    assert "generalized_cross_family_contract_compiler" in generalized_owner
    assert not plan["method_and_pattern_truth"]["new_financial_method_claimed"]


def test_stage_plan_is_duplicate_key_free_and_contract_valid() -> None:
    _validate_plan(_load(PLAN_PATH))


def test_parent_hashes_and_bounded_runtime_files_are_exact() -> None:
    plan = _load(PLAN_PATH)
    bindings = {row["role"]: row for row in plan["parent_bindings"]}
    assert bindings["S0_closeout"]["sha256"] == _sha256(S0_PATH)
    assert bindings["common_runtime_contract_family_source"][
        "sha256"
    ] == _sha256(SOURCE_PATH)
    assert bindings["S0_closed_commit"]["ref"].endswith(
        "bbf32ee150db41c8a0ddd5e26bcd9b4f0e7d970c"
    )
    for row in plan["consumer_migration"]:
        path = ROOT / row["path"]
        assert path.is_file()
        assert row["runtime_owner"].split(".")[0] in path.read_text(
            encoding="utf-8"
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update(status="S1_passed"),
        lambda value: value["fixed_task_budget"].append(
            {"task_id": "S1-T05", "status": "pending"}
        ),
        lambda value: value["consumer_migration"].pop(),
        lambda value: value["realistic_fixture_matrix"].update(
            cases=["MU", "NVDA"]
        ),
        lambda value: value["proof_matrix"].update(candidate_counts=[1, 6]),
        lambda value: value["budgets"].update(model_calls=1),
        lambda value: value["scope_boundary"]["FIN_0_2_owned"].remove(
            "generalized_cross_family_contract_compiler"
        ),
    ],
)
def test_scope_inflation_and_proof_coverage_mutations_fail_closed(
    mutator: Any,
) -> None:
    plan = deepcopy(_load(PLAN_PATH))
    mutator(plan)
    with pytest.raises(AssertionError):
        _validate_plan(plan)


def test_root_causes_are_allocated_to_the_earliest_stage_without_product_inflation() -> None:
    plan = _load(PLAN_PATH)
    rows = {row["issue_prefix"]: row for row in plan["root_cause_allocation"]}
    assert set(rows) == {
        "RC-P36-067",
        "RC-P36-068",
        "RC-P36-080",
        "RC-P36-083",
        "RC-P36-084",
    }
    assert rows["RC-P36-067"]["product_reproof_owner"] == "FIN_0_1_2_S4"
    assert rows["RC-P36-068"]["product_reproof_owner"] == "FIN_0_1_2_S4"
    assert rows["RC-P36-083"]["generalized_fix_owner"] == "FIN_0_2"
    assert rows["RC-P36-084"]["semantic_rubric_owner"] == "FIN_0_1_2_S4"


def test_historical_records_close_S1_honestly_before_S2() -> None:
    capsule = _load(CAPSULE_PATH)
    disposition = _load(PRE_S2_DISPOSITION)
    implementation = _load(PRE_S2_IMPLEMENTATION)
    assert capsule["next_action"] == (
        "FIN-0.1.2-S1-TO-S2-HERMETIC-FIXTURE-RESOURCE-BLOCKER-DISPOSITION"
    )
    assert disposition["next_action"] == (
        "FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-"
        "MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert implementation["next_action"] == (
        "FIN-0.1.2-PRE-S2-RB-T03-INDEPENDENT-TWO-DISPOSABLE-"
        "REPLACEMENT-HERMETIC-PROOF"
    )
    assert capsule["product_truth"]["S2_entry_authorized"] is False
    assert disposition["product_truth"]["S2_entry"] is False
    assert implementation["product_truth"]["S2_entry"] is False


def test_stage_plan_does_not_reclassify_product_or_release_truth() -> None:
    plan = _load(PLAN_PATH)
    assert not plan["authority"]["DELL_MU_R2_or_NVDA_R3_product_reproof_authorized"]
    assert plan["budgets"]["business_runs"] == 0
    assert plan["budgets"]["business_artifacts"] == 0
    assert plan["scope_boundary"]["FIN_0_2_owned"]
