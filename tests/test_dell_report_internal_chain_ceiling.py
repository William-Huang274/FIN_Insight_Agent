from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from retrieval.dell_report_internal_chain_ceiling import (
    DellReportInternalChainCeilingError,
    EXPECTED_UNOVERLAPPED_TARGET_IDS,
    build_dell_report_internal_chain_ceiling_public_projection,
    classify_internal_chain_object,
    compile_dell_report_internal_chain_ceiling_result,
    validate_dell_report_internal_chain_ceiling_policy,
    validate_dell_report_internal_chain_ceiling_successor_policy,
)
from retrieval.query_plan import canonical_digest


pytestmark = pytest.mark.requires_local_data

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json"
)
SUCCESSOR_POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_1.json"
)
FAILURE_RECEIPT_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_03b_internal_chain_r1_failure_receipt_v1_0.json"
)
RUNNER_PATH = (
    ROOT / "scripts" / "data_retrieval" / "run_dell_report_internal_chain_ceiling.py"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def bound_inputs() -> tuple[dict, dict, dict, dict, dict]:
    policy = _read(POLICY_PATH)
    bindings = policy["bound_inputs"]
    residual = _read(ROOT / bindings["residual_program_ref"])
    execution_program = _read(ROOT / bindings["execution_program_ref"])
    # The registry ref is the intentionally mutable current-runtime pointer.
    # R1/R2 are immutable R38 attempts, so exercise their validator with the
    # exact registry identity sealed in the policy instead of silently
    # substituting the now-current R39 bytes.
    registry = {
        "registry_id": bindings["runtime_registry_id"],
        "resource_canonical_digest": bindings["runtime_registry_digest"],
    }
    receipt = _read(ROOT / bindings["runtime_binding_receipt_ref"])
    return policy, residual, execution_program, registry, receipt


@pytest.fixture(scope="module")
def runner_module():
    spec = importlib.util.spec_from_file_location("dell_03B_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract(policy: dict, target_id: str) -> dict:
    return next(
        row for row in policy["target_contracts"] if row["target_id"] == target_id
    )


def _object(
    object_id: str,
    *,
    text: str,
    ticker: str = "DELL",
    publication_date: str = "2026-05-28",
) -> dict:
    source_id = f"SRC::{object_id}"
    return {
        "schema_version": "test",
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "object_kind": "claim",
        "base_object_view": {
            "source_record_id": source_id,
            "ticker": ticker,
            "source_type": "TEST",
            "source_tier": "primary_test",
            "publication_date": publication_date,
            "period_end": "2026-05-01",
            "section": "test",
            "subsection": "test",
        },
    }


def _seed(object_id: str, rank: int, *, final_rank: int | None) -> dict:
    return {
        "compiled_object_id": object_id,
        "rank_trace": {
            "raw_union_rank": rank,
            "financial_rank": rank,
            "review_priority_rank": rank,
            "final_output_rank": final_rank,
        },
        "route_membership": ["bm25_lexical"],
        "route_ranks": {
            "bm25_lexical": rank,
            "qwen3_embedding_0_6b_dense": None,
            "typed_relationship_graph": None,
        },
        "material_alignment_state": "eligible_not_reserved",
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
    }


def _synthetic_execution(
    policy: dict,
    *,
    seeds_by_request: dict[str, list[tuple[str, int | None]]],
) -> dict:
    request_ids = sorted(
        {
            request_id
            for contract in policy["target_contracts"]
            for request_id in contract["request_ids"]
        }
    )
    request_results = []
    for request_id in request_ids:
        entries = seeds_by_request[request_id]
        seeds = [
            _seed(object_id, index, final_rank=final_rank)
            for index, (object_id, final_rank) in enumerate(entries, start=1)
        ]
        final_ids = [
            object_id for object_id, final_rank in entries if final_rank is not None
        ]
        request_results.append(
            {
                "request": {"request_id": request_id},
                "projection_digest": f"DIGEST::{request_id}",
                "summary": {
                    "typed_fact_resolved_count": 0,
                    "typed_fact_gap_count": 1,
                    "typed_fact_conflict_count": 0,
                },
                "route_execution_truth": {
                    "narrative_route_requests": [
                        {"routes": [{"execution_state": "executed"}]}
                    ],
                    "typed_fact_route_requests": [],
                },
                "hybrid_object_retrieval": {
                    "candidate_decision_seed": seeds,
                    "candidates": [
                        {"compiled_object_id": object_id} for object_id in final_ids
                    ],
                },
            }
        )
    return {
        "status": "current_runtime_request_batch_zero_call_executed",
        "projection_digest": "EXECUTION::DIGEST",
        "summary": {
            "request_count": len(request_ids),
            "local_embedding_inference_batches": 1,
            "network_calls": 0,
            "model_calls": 0,
            "generation_model_calls": 0,
        },
        "request_results": request_results,
    }


def test_policy_validates_exact_six_target_scope(bound_inputs) -> None:
    policy, residual, execution_program, registry, receipt = bound_inputs
    result = validate_dell_report_internal_chain_ceiling_policy(
        policy,
        residual_program=residual,
        execution_program=execution_program,
        runtime_registry=registry,
        runtime_binding_receipt=receipt,
    )
    assert {row["target_id"] for row in result["target_contracts"]} == set(
        EXPECTED_UNOVERLAPPED_TARGET_IDS
    )
    assert result["execution_budget"]["request_count"] == 5
    assert result["authority"]["reranker_authorized"] is False


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value["authority"].update({"network_authorized": True}),
            "dell_03B_authority_surface_invalid",
        ),
        (
            lambda value: value["execution_budget"].update({"reranker_calls": 1}),
            "dell_03B_execution_budget_not_bounded",
        ),
        (
            lambda value: value["TokenBudgetBasis"].update({"input_scale": ""}),
            "dell_03B_token_budget_basis_missing:input_scale",
        ),
        (
            lambda value: value.update(
                {
                    "held_target_ids": [
                        "DELL-RSQ-03A-TARGET-DEMAND-DURABILITY"
                    ]
                }
            ),
            "dell_03B_exact_held_target_set_invalid",
        ),
    ],
)
def test_policy_mutations_fail_closed(bound_inputs, mutation, reason) -> None:
    policy, residual, execution_program, registry, receipt = bound_inputs
    changed = deepcopy(policy)
    mutation(changed)
    with pytest.raises(DellReportInternalChainCeilingError, match=reason):
        validate_dell_report_internal_chain_ceiling_policy(
            changed,
            residual_program=residual,
            execution_program=execution_program,
            runtime_registry=registry,
            runtime_binding_receipt=receipt,
        )


def _validate_successor(
    successor: dict,
    *,
    bound_inputs: tuple[dict, dict, dict, dict, dict],
    failure: dict | None = None,
) -> dict:
    predecessor, residual, execution_program, registry, receipt = bound_inputs
    return validate_dell_report_internal_chain_ceiling_successor_policy(
        successor,
        predecessor_policy=predecessor,
        predecessor_failure_receipt=failure or _read(FAILURE_RECEIPT_PATH),
        residual_program=residual,
        execution_program=execution_program,
        runtime_registry=registry,
        runtime_binding_receipt=receipt,
    )


def _reseal(value: dict) -> None:
    value["result_digest"] = canonical_digest(
        {key: row for key, row in value.items() if key != "result_digest"}
    )


def test_R2_successor_inherits_exact_R1_contract(bound_inputs) -> None:
    successor = _read(SUCCESSOR_POLICY_PATH)
    inherited = _validate_successor(successor, bound_inputs=bound_inputs)
    assert inherited["program_id"] == "FIN-0.1.3-S1-DELL-RSQ-03B-R1"
    assert successor["attempt_id"] == "dell-rsq-03b-internal-chain-r2"
    assert successor["execution_budget"] == inherited["execution_budget"]
    assert successor["authority"] == inherited["authority"]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value.update(
                {"attempt_id": "dell-rsq-03b-internal-chain-r1"}
            ),
            "dell_03B_R2_identity_invalid",
        ),
        (
            lambda value: value["only_successor_changes"].update(
                {"source_store_source_record_id_alias_accepted": True}
            ),
            "dell_03B_R2_delta_invalid",
        ),
        (
            lambda value: value["execution_budget"].update(
                {"local_embedding_inference_batches_maximum": 2}
            ),
            "dell_03B_R2_execution_budget_drift",
        ),
        (
            lambda value: value["authority"].update(
                {"reranker_authorized": True}
            ),
            "dell_03B_R2_authority_drift",
        ),
    ],
)
def test_R2_successor_mutations_fail_closed(
    bound_inputs, mutation, reason
) -> None:
    successor = deepcopy(_read(SUCCESSOR_POLICY_PATH))
    mutation(successor)
    _reseal(successor)
    with pytest.raises(DellReportInternalChainCeilingError, match=reason):
        _validate_successor(successor, bound_inputs=bound_inputs)


def test_R2_rejects_mutated_R1_failure_receipt(bound_inputs) -> None:
    successor = _read(SUCCESSOR_POLICY_PATH)
    failure = deepcopy(_read(FAILURE_RECEIPT_PATH))
    failure["execution_receipt"]["4B_embedding_calls"] = 1
    failure["result_digest"] = canonical_digest(
        {key: row for key, row in failure.items() if key != "result_digest"}
    )
    with pytest.raises(
        DellReportInternalChainCeilingError,
        match="dell_03B_R2_failure_receipt_invalid",
    ):
        _validate_successor(
            successor,
            bound_inputs=bound_inputs,
            failure=failure,
        )


def test_asp_rule_rejects_traditional_server_asp_as_complete(bound_inputs) -> None:
    policy = bound_inputs[0]
    row = _object(
        "COBJ::ASP-TRADITIONAL",
        text=(
            "Traditional servers and networking revenue increased because average "
            "selling price rose and units sold declined."
        ),
    )
    result = classify_internal_chain_object(
        row, _contract(policy, "DELL-RSQ-03A-TARGET-ASP")
    )
    assert result["classification"] == "partial_context_only"
    assert "traditional servers and networking" in result[
        "forbidden_complete_terms_matched"
    ]


def test_units_rule_rejects_dollar_shipments_as_physical_units(bound_inputs) -> None:
    policy = bound_inputs[0]
    row = _object(
        "COBJ::DOLLAR-SHIPMENTS",
        text="Dell AI server shipments were $16.1 billion in the quarter.",
    )
    result = classify_internal_chain_object(
        row, _contract(policy, "DELL-RSQ-03A-TARGET-UNITS")
    )
    assert result["classification"] == "partial_context_only"
    assert result["forbidden_complete_regexes_matched"]


@pytest.mark.parametrize(
    ("target_id", "ticker", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "DELL",
            "Dell AI server configured price was US$400,000 per server for 20 servers.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "DELL",
            "Dell AI-optimized server shipments included 12,000 servers delivered.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "MU",
            "HBM capacity expansion beginning in calendar 2026 was allocated to Dell.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "TSM",
            "Advanced packaging capacity utilization rate was 95% in the quarter.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "MU",
            "HBM supply capacity in calendar 2026 supports Dell PowerEdge availability.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "NVDA",
            "NVIDIA partnership with Dell made the platform available from Dell PowerEdge.",
        ),
    ],
)
def test_each_target_has_a_positive_control(
    bound_inputs, target_id, ticker, text
) -> None:
    policy = bound_inputs[0]
    result = classify_internal_chain_object(
        _object(f"COBJ::{target_id}", text=text, ticker=ticker),
        _contract(policy, target_id),
    )
    assert result["classification"] == "complete_target_semantic_equivalent"


def test_compile_routes_embedding_reranker_and_external_separately(
    bound_inputs,
) -> None:
    policy, residual, execution_program, registry, receipt = bound_inputs
    objects = [
        _object("COBJ::NEUTRAL", text="Dell general disclosure."),
        _object(
            "COBJ::UNITS-FINAL",
            text="Dell AI server shipments included 12,000 servers delivered.",
        ),
        _object(
            "COBJ::CAPACITY-UNION",
            ticker="MU",
            text=(
                "HBM capacity expansion beginning in calendar 2026 was allocated "
                "to Dell."
            ),
        ),
        _object(
            "COBJ::REL-CORPUS",
            ticker="NVDA",
            text=(
                "NVIDIA partnership with Dell made the platform available from "
                "Dell PowerEdge."
            ),
        ),
    ]
    request_ids = sorted(
        {
            request_id
            for contract in policy["target_contracts"]
            for request_id in contract["request_ids"]
        }
    )
    seeds = {request_id: [("COBJ::NEUTRAL", 1)] for request_id in request_ids}
    seeds["REQ::DELL::UNIT_VOLUME::V1"] = [("COBJ::UNITS-FINAL", 1)]
    seeds["REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1"] = [
        ("COBJ::CAPACITY-UNION", None)
    ]
    execution = _synthetic_execution(policy, seeds_by_request=seeds)
    synthetic_receipt = deepcopy(receipt)
    synthetic_receipt["source_object_index_lineage"]["compiled_object_count"] = len(
        objects
    )
    synthetic_receipt["source_object_index_lineage"]["source_record_count"] = len(
        objects
    )
    synthetic_receipt["source_object_index_lineage"].update(
        {
            "all_source_records_lineage_bound": True,
            "compiled_lineage_ids_outside_bound_source_store": [],
            "compiled_lineage_source_record_count": len(objects),
            "source_records_missing_from_compiled_lineage": [],
        }
    )
    synthetic_receipt["embedding_index"]["object_count"] = len(objects)
    result = compile_dell_report_internal_chain_ceiling_result(
        policy=policy,
        residual_program=residual,
        execution_program=execution_program,
        runtime_registry=registry,
        runtime_binding_receipt=synthetic_receipt,
        execution=execution,
        object_rows=objects,
        source_record_ids={row["base_object_view"]["source_record_id"] for row in objects},
        recorded_at="2026-08-25T00:00:00+00:00",
        prepared_from_commit="a" * 40,
        attempt_id="test-r1",
        input_bindings={},
    )
    by_id = {row["target_id"]: row for row in result["target_results"]}
    assert by_id["DELL-RSQ-03A-TARGET-UNITS"]["candidate_ceiling"][
        "complete_target_in_final_review"
    ] is True
    assert by_id["DELL-RSQ-03A-TARGET-CAPACITY-RELEASE"][
        "downstream_disposition"
    ]["03D_same_pool_reranker_challenger_eligible"] is True
    assert by_id["DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH"][
        "downstream_disposition"
    ]["03D_4B_embedding_recall_challenger_eligible"] is True
    assert by_id["DELL-RSQ-03A-TARGET-ASP"]["downstream_disposition"][
        "03C_external_route_required_for_complete_target"
    ] is True
    assert result["summary"]["held_target_execution_count"] == 0
    assert result["authority"]["03D_4B_embedding_authorized"] is False
    exact_source_ids = [
        row["base_object_view"]["source_record_id"] for row in objects
    ]
    with pytest.raises(
        DellReportInternalChainCeilingError,
        match="dell_03B_source_identity_population_duplicate",
    ):
        compile_dell_report_internal_chain_ceiling_result(
            policy=policy,
            residual_program=residual,
            execution_program=execution_program,
            runtime_registry=registry,
            runtime_binding_receipt=synthetic_receipt,
            execution=execution,
            object_rows=objects,
            source_record_ids=[*exact_source_ids, exact_source_ids[0]],
            recorded_at="2026-08-25T00:00:00+00:00",
            prepared_from_commit="a" * 40,
            attempt_id="test-source-duplicate",
            input_bindings={},
        )
    source_ids = {
        row["base_object_view"]["source_record_id"] for row in objects
    }
    source_ids.remove("SRC::COBJ::NEUTRAL")
    source_ids.add("SRC::NOT-IN-COMPILED-LINEAGE")
    with pytest.raises(
        DellReportInternalChainCeilingError,
        match="dell_03B_source_compiled_lineage_population_mismatch",
    ):
        compile_dell_report_internal_chain_ceiling_result(
            policy=policy,
            residual_program=residual,
            execution_program=execution_program,
            runtime_registry=registry,
            runtime_binding_receipt=synthetic_receipt,
            execution=execution,
            object_rows=objects,
            source_record_ids=source_ids,
            recorded_at="2026-08-25T00:00:00+00:00",
            prepared_from_commit="a" * 40,
            attempt_id="test-lineage-mismatch",
            input_bindings={},
        )


def test_reranker_remains_eligible_when_complete_target_is_rank_11(
    bound_inputs,
) -> None:
    policy, residual, execution_program, registry, receipt = bound_inputs
    complete = _object(
        "COBJ::UNITS-RANK-11",
        text="Dell AI server shipments included 12,000 servers delivered.",
    )
    neutral_objects = [
        _object(f"COBJ::NEUTRAL-{index}", text="Dell general disclosure.")
        for index in range(1, 12)
    ]
    objects = [*neutral_objects, complete]
    request_ids = sorted(
        {
            request_id
            for contract in policy["target_contracts"]
            for request_id in contract["request_ids"]
        }
    )
    seeds = {
        request_id: [(neutral_objects[0]["compiled_object_id"], 1)]
        for request_id in request_ids
    }
    seeds["REQ::DELL::UNIT_VOLUME::V1"] = [
        *[
            (row["compiled_object_id"], index)
            for index, row in enumerate(neutral_objects[:10], start=1)
        ],
        (complete["compiled_object_id"], 11),
    ]
    execution = _synthetic_execution(policy, seeds_by_request=seeds)
    synthetic_receipt = deepcopy(receipt)
    synthetic_receipt["source_object_index_lineage"]["compiled_object_count"] = len(
        objects
    )
    synthetic_receipt["source_object_index_lineage"]["source_record_count"] = len(
        objects
    )
    synthetic_receipt["source_object_index_lineage"].update(
        {
            "all_source_records_lineage_bound": True,
            "compiled_lineage_ids_outside_bound_source_store": [],
            "compiled_lineage_source_record_count": len(objects),
            "source_records_missing_from_compiled_lineage": [],
        }
    )
    synthetic_receipt["embedding_index"]["object_count"] = len(objects)
    result = compile_dell_report_internal_chain_ceiling_result(
        policy=policy,
        residual_program=residual,
        execution_program=execution_program,
        runtime_registry=registry,
        runtime_binding_receipt=synthetic_receipt,
        execution=execution,
        object_rows=objects,
        source_record_ids={row["base_object_view"]["source_record_id"] for row in objects},
        recorded_at="2026-08-25T00:00:00+00:00",
        prepared_from_commit="a" * 40,
        attempt_id="test-rank-11",
        input_bindings={},
    )
    target = next(
        row
        for row in result["target_results"]
        if row["target_id"] == "DELL-RSQ-03A-TARGET-UNITS"
    )
    assert target["candidate_ceiling"]["best_complete_target_final_rank"] == 11
    assert target["candidate_ceiling"]["complete_target_useful_at_k"] is False
    assert target["downstream_disposition"][
        "03D_same_pool_reranker_challenger_eligible"
    ] is True


def test_public_projection_excludes_candidate_text(bound_inputs) -> None:
    private = {
        "status": "dell_03B_internal_chain_candidate_ceiling_executed",
        "attempt_id": "test",
        "recorded_at": "2026-08-25T00:00:00+00:00",
        "prepared_from_commit": "a" * 40,
        "case_key": "DELL",
        "input_bindings": {},
        "runtime_registry": {},
        "execution_projection_digest": "x",
        "execution_summary": {},
        "target_results": [
            {
                "target_id": "DELL-RSQ-03A-TARGET-ASP",
                "private_semantic_matches": [{"model_text": "secret"}],
                "private_union_assessments": [{"model_text": "secret"}],
                "public_top_semantic_matches": [],
            }
        ],
        "summary": {},
        "authority": {},
        "known_boundary": "bounded",
        "result_digest": "private-digest",
    }
    public = build_dell_report_internal_chain_ceiling_public_projection(
        private_result=private,
        private_ref="data/workbench_private/test/full_result.json",
        private_sha256="b" * 64,
    )
    serialized = json.dumps(public)
    assert "model_text" not in serialized
    assert "secret" not in serialized


def test_runner_material_blueprints_are_exact_subset(
    bound_inputs, runner_module
) -> None:
    policy, _, execution_program, _, _ = bound_inputs
    request_ids = {
        request_id
        for contract in policy["target_contracts"]
        for request_id in contract["request_ids"]
    }
    result = runner_module._material_blueprints(
        execution_program, request_ids=request_ids
    )
    assert set(result) == request_ids
    assert len(result) == policy["execution_budget"]["request_count"]
    assert all(row["material_requirements"] for row in result.values())


def test_runner_reads_real_source_store_canonical_evidence_ids(
    bound_inputs, runner_module
) -> None:
    receipt = bound_inputs[-1]
    source_ref = receipt["bindings"]["source_records"]["ref"]
    source_rows = runner_module._read_jsonl(ROOT / source_ref)
    assert len(source_rows) == 1888
    assert all("evidence_id" in row for row in source_rows)
    assert all("source_record_id" not in row for row in source_rows)
    source_ids = runner_module._source_record_ids(source_rows)
    assert len(source_ids) == 1888
    assert len(source_ids) == receipt["source_object_index_lineage"][
        "source_record_count"
    ]
    object_ref = receipt["bindings"]["compiled_objects"]["ref"]
    object_rows = runner_module._read_jsonl(ROOT / object_ref)
    objects_by_id, compiled_source_ids = (
        runner_module.validate_dell_report_source_compiled_identity_population(
            object_rows=object_rows,
            source_record_ids=source_ids,
            runtime_binding_receipt=receipt,
        )
    )
    assert len(objects_by_id) == 34198
    assert compiled_source_ids == source_ids


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        (
            [{"source_record_id": "SRC::OBJECT-ALIAS"}],
            "dell_03B_source_record_id_alias_forbidden:1",
        ),
        ([{}], "dell_03B_source_evidence_id_missing:1"),
        ([{"evidence_id": " padded "}], "dell_03B_source_evidence_id_missing:1"),
        (
            [{"evidence_id": "SRC::1"}, {"evidence_id": "SRC::1"}],
            "dell_03B_source_evidence_id_duplicate:SRC::1",
        ),
    ],
)
def test_runner_source_identity_contract_fails_closed(
    runner_module, rows, reason
) -> None:
    with pytest.raises(ValueError, match=reason):
        runner_module._source_record_ids(rows)


def test_runner_R2_implementation_bindings_are_exact(runner_module) -> None:
    runner_module._validate_implementation_bindings(_read(SUCCESSOR_POLICY_PATH))
