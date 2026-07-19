from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "configs/releases/fin_ia_0_1_vertical_release_train_overlay_v1_0.json"
BASE_BACKLOG = ROOT / "configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_0.json"
FEATURE_SCOPE = ROOT / "configs/releases/fin_ia_0_1_feature_scope_matrix_v1_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_overlay_binds_exact_active_contract_files() -> None:
    overlay = _load(OVERLAY)
    for binding in overlay["contract_bindings"]:
        path = ROOT / binding["path"]
        assert path.is_file()
        assert binding["sha256"] == _sha256(path)


def test_every_base_execution_point_has_one_first_consuming_tranche() -> None:
    overlay = _load(OVERLAY)
    backlog = _load(BASE_BACKLOG)
    expected = {
        execution_point["id"]
        for point in backlog["points"]
        for execution_point in point["execution_points"]
    }
    mapped = [
        execution_point
        for execution_points in overlay["execution_point_first_consumption"].values()
        for execution_point in execution_points
    ]
    assert len(expected) == overlay["coverage_invariant"]["expected_execution_point_count"]
    assert len(mapped) == len(set(mapped))
    assert set(mapped) == expected


def test_first_consumption_never_precedes_a_backlog_dependency() -> None:
    overlay = _load(OVERLAY)
    backlog = _load(BASE_BACKLOG)
    first_tranche = {
        execution_point: tranche_index
        for tranche_index, execution_points in enumerate(
            overlay["execution_point_first_consumption"].values()
        )
        for execution_point in execution_points
    }
    targeted = {
        target["execution_point"]
        for tranche in overlay["release_train"]
        for target in tranche["execution_point_stage_targets"]
    }
    assert targeted == set(first_tranche)
    for point in backlog["points"]:
        for execution_point in point["execution_points"]:
            for dependency in execution_point["depends_on"]:
                if dependency in first_tranche:
                    assert first_tranche[dependency] <= first_tranche[execution_point["id"]]


def test_first_consumption_matches_each_execution_points_earliest_stage_target() -> None:
    overlay = _load(OVERLAY)
    tranche_ids = [tranche["tranche_id"] for tranche in overlay["release_train"]]
    declared_first = {
        execution_point: tranche_ids.index(tranche_id)
        for tranche_id, execution_points in overlay["execution_point_first_consumption"].items()
        for execution_point in execution_points
    }
    targeted_first: dict[str, int] = {}
    for tranche_index, tranche in enumerate(overlay["release_train"]):
        for target in tranche["execution_point_stage_targets"]:
            targeted_first.setdefault(target["execution_point"], tranche_index)
    assert declared_first == targeted_first


def test_train_targets_use_existing_maturity_and_gate_families() -> None:
    overlay = _load(OVERLAY)
    feature_scope = _load(FEATURE_SCOPE)
    assert overlay["status"] == "approved_execution_control"
    assert overlay["independent_review"]["disposition"] == "approve"
    assert overlay["independent_review"]["remaining_P0_P1"] == 0
    maturity = set(overlay["maturity_model"]["labels"])
    targets = [
        target
        for tranche in overlay["release_train"]
        for target in tranche["execution_point_stage_targets"]
    ]
    assert all(target["required_stage"] in maturity for target in targets)
    assert overlay["feature_scope_change"] == "none"
    assert overlay["gate_family_change"] == "none"
    assert overlay["maturity_model"]["integration_probe_is_not_stage_or_gate_family"] is True
    assert overlay["current_boundaries"]["production_readiness"] == "not_admitted"
    assert overlay["current_boundaries"]["legacy_global_authority"] == "retained"
    incremental_features = [
        feature_id
        for tranche in overlay["release_train"]
        for feature_id in tranche["incremental_feature_ids"]
    ]
    assert len(incremental_features) == len(set(incremental_features))
    assert set(incremental_features) == set(feature_scope["feature_ids"])


def test_release_train_starts_with_contract_closure_and_ends_at_p07_5() -> None:
    overlay = _load(OVERLAY)
    tranches = overlay["release_train"]
    assert [tranche["tranche_id"] for tranche in tranches] == [
        "VT0_PRE_W1_CONTRACT_CLOSURE",
        "VT1_W1_CASE_PLAN_EVIDENCE_WALKING_SKELETON",
        "VT2_W2_NUMERIC_JUDGMENT_REPAIR_LEAD",
        "VT3_W3_DELIVERABLE_REVIEW_TRACE",
        "VT4_W4_DOGFOOD_RELEASE_DECISION",
    ]
    assert tranches[0]["execution_point_stage_targets"] == [
        {
            "execution_point": "P02.0",
            "required_stage": "full",
            "scope": "route_action_command_read_model_openapi_owner_set_closure_only",
        }
    ]
    final_targets = {target["execution_point"] for target in tranches[-1]["execution_point_stage_targets"]}
    assert "P07.5" in final_targets
    assert overlay["immediate_next_action_after_overlay_approval"]["new_milestone"] is False
    assert overlay["immediate_next_action_after_overlay_approval"]["new_gate_family"] is False
    assert (
        overlay["immediate_next_action_after_overlay_approval"]["repair_budget_override"]
        == "exactly_one_bounded_repair_for_the_existing_set_closure_P1"
    )
    assert "do_not_start_P02.1_or_P02.2" in overlay["immediate_next_action_after_overlay_approval"][
        "failure_effect"
    ]


def test_w1_workbench_is_fixture_until_retrieval_is_full_and_followup_precedes_ui_closeout() -> None:
    overlay = _load(OVERLAY)
    tranches = {tranche["tranche_id"]: tranche for tranche in overlay["release_train"]}
    w1_targets = {
        target["execution_point"]: target["required_stage"]
        for target in tranches["VT1_W1_CASE_PLAN_EVIDENCE_WALKING_SKELETON"][
            "execution_point_stage_targets"
        ]
    }
    w2_target_order = [
        target["execution_point"]
        for target in tranches["VT2_W2_NUMERIC_JUDGMENT_REPAIR_LEAD"][
            "execution_point_stage_targets"
        ]
    ]
    assert w1_targets["P03.1"] == "fixture"
    assert w1_targets["P03.2"] == "fixture"
    assert w1_targets["P03.3"] == "fixture"
    w2_targets = {
        target["execution_point"]: target["required_stage"]
        for target in tranches["VT2_W2_NUMERIC_JUDGMENT_REPAIR_LEAD"][
            "execution_point_stage_targets"
        ]
    }
    assert w2_targets["P03.1"] == "full"
    assert w2_targets["P03.2"] == "full"
    assert w2_targets["P03.3"] == "full"
    assert w2_target_order.index("P05.5") < w2_target_order.index("P05.6")
