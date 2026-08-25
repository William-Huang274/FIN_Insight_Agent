from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from retrieval.dell_report_residual_source_program import (
    DellReportResidualSourceProgramError,
    compile_dell_report_residual_source_program,
    validate_dell_report_residual_source_policy,
)
from retrieval.query_plan import canonical_digest


pytestmark = pytest.mark.requires_local_data

ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_SCRIPT = (
    ROOT
    / "scripts/data_retrieval/materialize_dell_report_residual_source_program.py"
)
RESIDUAL_SPEC = importlib.util.spec_from_file_location(
    "dell_report_residual_runner", RESIDUAL_SCRIPT
)
assert RESIDUAL_SPEC is not None and RESIDUAL_SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(RESIDUAL_SPEC)
RESIDUAL_SPEC.loader.exec_module(RUNNER)

ADMISSION_SCRIPT = (
    ROOT
    / "scripts/data_retrieval/materialize_dell_report_evidence_admission_packet.py"
)
ADMISSION_SPEC = importlib.util.spec_from_file_location(
    "dell_report_admission_runner_for_residual", ADMISSION_SCRIPT
)
assert ADMISSION_SPEC is not None and ADMISSION_SPEC.loader is not None
ADMISSION_RUNNER = importlib.util.module_from_spec(ADMISSION_SPEC)
ADMISSION_SPEC.loader.exec_module(ADMISSION_RUNNER)

POLICY_PATH = ROOT / RUNNER.DEFAULT_POLICY


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _redigest(value: dict, field: str) -> None:
    value[field] = canonical_digest(
        {key: item for key, item in value.items() if key != field}
    )


@pytest.fixture(scope="module")
def local_inputs() -> dict:
    policy = _json(POLICY_PATH)
    payloads: dict[str, dict] = {}
    sha256_by_ref: dict[str, str] = {}
    missing: list[str] = []
    for name, binding in policy["input_bindings"].items():
        path = ROOT / binding["ref"]
        if not path.is_file():
            missing.append(binding["ref"])
            continue
        raw = path.read_bytes()
        sha256_by_ref[binding["ref"]] = hashlib.sha256(raw).hexdigest()
        if binding.get("digest_field") is not None:
            payloads[name] = json.loads(raw.decode("utf-8"))
    if missing:
        pytest.skip(f"private residual-program inputs absent: {missing}")
    admission = ADMISSION_RUNNER.compile_materialization(
        program_path=ROOT / ADMISSION_RUNNER.DEFAULT_PROGRAM,
        private_output_path=ROOT / ADMISSION_RUNNER.DEFAULT_PRIVATE_OUTPUT,
        recorded_at="2026-08-25T16:00:00+08:00",
        prepared_from_commit="TEST_ADMISSION_COMMIT",
    )["public"]
    return {
        "policy": policy,
        "payloads": payloads,
        "sha256_by_ref": sha256_by_ref,
        "admission": admission,
    }


def _compile(local_inputs: dict, **overrides: object) -> dict:
    values = {
        "policy": local_inputs["policy"],
        "input_payloads": local_inputs["payloads"],
        "input_sha256_by_ref": local_inputs["sha256_by_ref"],
        "admission_manifest": local_inputs["admission"],
        "admission_manifest_ref": ADMISSION_RUNNER.DEFAULT_PUBLIC_OUTPUT,
        "admission_manifest_sha256": "a" * 64,
        "recorded_at": "2026-08-25T16:30:00+08:00",
        "prepared_from_commit": "TEST_RESIDUAL_COMMIT",
    }
    values.update(overrides)
    return compile_dell_report_residual_source_program(**values)


def test_real_policy_compiles_complete_gap_and_route_partition(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)

    assert result["counts"] == {
        "crosswalk_pack_gap_count": 14,
        "pack_gap_acquisition_target_count": 8,
        "independent_S2_acquisition_target_count": 1,
        "total_acquisition_target_count": 9,
        "currently_unoverlapped_target_count": 6,
        "admission_held_target_count": 3,
        "non_acquisition_pack_gap_count": 6,
        "route_family_count": 7,
        "compiled_route_contract_count": 63,
    }
    assert len(result["gap_disposition_register"]) == 15
    assert len({row["gap_id"] for row in result["gap_disposition_register"]}) == 15
    assert result["program_digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "program_digest"}
    )


def test_admission_overlap_holds_demand_working_capital_and_product_profit(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    held = {
        target["target_id"]
        for target in result["route_targets"]
        if target["current_route_state"]
        == "held_by_qualified_human_admission"
    }

    assert held == {
        "DELL-RSQ-03A-TARGET-DEMAND-DURABILITY",
        "DELL-RSQ-03A-TARGET-WORKING-CAPITAL",
        "DELL-RSQ-03A-TARGET-PRODUCT-PROFIT",
    }
    assert all(target["current_network_authority"] is False for target in result["route_targets"])
    assert result["authority"]["03C_external_capture_execution_authorized"] is False


def test_every_target_has_all_routes_and_quality_complete_query_contract(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)

    for target in result["route_targets"]:
        assert len(target["route_contracts"]) == 7
        assert len({route["route_family_id"] for route in target["route_contracts"]}) == 7
        for route in target["route_contracts"]:
            query = route["query_contract"]
            assert query["target_proposition"]
            assert query["subject"]
            assert query["owner_scope"]
            assert query["time_scope"]
            assert query["source_role"]
            assert query["forbidden_inference"]
            assert query["answer_URL_or_qrel_seeded"] is False
            lowered = query["locator_query_template"].casefold()
            assert "http://" not in lowered
            assert "https://" not in lowered
            assert "qrel" not in lowered
            assert route["capture_policy"]
            assert route["fallback"]
            assert route["stop_condition"]
            assert route["network_execution_authorized"] is False


def test_prior_22_query_ladder_is_reconciled_not_repeated(local_inputs: dict) -> None:
    result = _compile(local_inputs)

    assert result["prior_ladder_reconciliation"][
        "fresh_provider_query_count_already_spent"
    ] == 22
    assert result["prior_ladder_reconciliation"][
        "repeat_old_query_units_as_fresh_calls"
    ] is False
    for target in result["route_targets"]:
        predecessor = target["predecessor_ladder"]
        assert predecessor["prior_query_count"] > 0
        assert predecessor["reconcile_before_any_new_locator_call"] is True
        assert predecessor["repeat_predecessor_query_forbidden"] is True


def test_4b_embedding_and_reranker_are_retained_but_not_authorized(
    local_inputs: dict,
) -> None:
    ranking = _compile(local_inputs)["mixed_retrieval_and_ranking_dependency"]
    nodes = {node["node_id"]: node for node in ranking["nodes"]}

    assert set(nodes) == {
        "bm25_plus_qwen3_embedding_0_6b_baseline",
        "qwen_4b_embedding_shadow_challenger_4bit",
        "qwen_4b_reranker_4bit",
    }
    assert ranking["candidate_ceiling_before_reranker"] is True
    assert ranking["current_authority"] is False
    assert "8GB GPU" in nodes["qwen_4b_embedding_shadow_challenger_4bit"][
        "runtime_profile"
    ]
    for node in nodes.values():
        basis = node["TokenBudgetBasis"]
        assert basis["node_purpose"]
        assert basis["input_scale"]
        assert basis["required_outputs"]
        assert basis["schema_burden"]
        assert basis["materiality_and_quality_risk"]
        assert basis["comparable_run_evidence"]
        assert basis["reasoning_profile"]
        assert basis["stop_and_truncation_behavior"]
        assert basis["authority_granted"] is False


def test_crosswalk_disposition_mutation_fails_target_contract(
    local_inputs: dict,
) -> None:
    payloads = deepcopy(local_inputs["payloads"])
    rows = payloads["G1_crosswalk_private"]["audit_projection"][
        "pack_gap_entries"
    ]
    target = next(
        row for row in rows if row["gap_id"] == "dell-gap-capacity-release-timing"
    )
    target["research_disposition"] = "closed"

    with pytest.raises(
        DellReportResidualSourceProgramError,
        match="dell_report_residual_target_crosswalk_mismatch",
    ):
        _compile(local_inputs, input_payloads=payloads)


def test_admission_partition_mutation_fails_closed(local_inputs: dict) -> None:
    policy = deepcopy(local_inputs["policy"])
    demand = next(
        target
        for target in policy["target_policies"]
        if target["target_id"] == "DELL-RSQ-03A-TARGET-DEMAND-DURABILITY"
    )
    demand["admission_overlap_request_ids"] = []
    _redigest(policy, "policy_digest")

    with pytest.raises(
        DellReportResidualSourceProgramError,
        match="dell_report_residual_admission_partition_invalid",
    ):
        _compile(local_inputs, policy=policy)


def test_decided_or_drifted_admission_manifest_requires_new_program_state(
    local_inputs: dict,
) -> None:
    admission = deepcopy(local_inputs["admission"])
    admission["counts"]["qualified_human_decision_count"] = 1
    _redigest(admission, "result_digest")

    with pytest.raises(
        DellReportResidualSourceProgramError,
        match="dell_report_residual_admission_state_invalid",
    ):
        _compile(local_inputs, admission_manifest=admission)


def test_route_attempt_budget_and_input_sha_fail_closed(local_inputs: dict) -> None:
    policy = deepcopy(local_inputs["policy"])
    policy["route_family_policies"][0]["max_attempts"] = 99
    _redigest(policy, "policy_digest")
    with pytest.raises(
        DellReportResidualSourceProgramError,
        match="dell_report_residual_route_attempt_budget_invalid",
    ):
        validate_dell_report_residual_source_policy(policy)

    sha256_by_ref = deepcopy(local_inputs["sha256_by_ref"])
    ref = local_inputs["policy"]["input_bindings"]["prior_ladder_result"]["ref"]
    sha256_by_ref[ref] = "0" * 64
    with pytest.raises(
        DellReportResidualSourceProgramError,
        match="dell_report_residual_input_sha256_mismatch:prior_ladder_result",
    ):
        _compile(local_inputs, input_sha256_by_ref=sha256_by_ref)


def test_program_has_zero_calls_and_no_false_closure(local_inputs: dict) -> None:
    result = _compile(local_inputs)

    assert result["execution"] == {
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "embedding_calls": 0,
        "reranker_calls": 0,
        "captures": 0,
        "candidate_promotions": 0,
        "evidence_promotions": 0,
        "gap_closures": 0,
    }
    assert result["authority"]["proved_information_boundary_authorized"] is False
    assert result["authority"]["G3_pass"] is False
    assert all(row["execution_eligible_now"] is False for row in result["gap_disposition_register"])


def test_materializer_rejects_dirty_worktree_and_output_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(
        RUNNER.DellReportResidualSourceMaterializationError,
        match="dell_report_residual_clean_worktree_required",
    ):
        RUNNER._require_clean_worktree("?? unexpected.txt")

    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    existing = tmp_path / "already.json"
    existing.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        FileExistsError,
        match="dell_report_residual_output_exists:already.json",
    ):
        RUNNER._write_new(existing, {"value": 1})
