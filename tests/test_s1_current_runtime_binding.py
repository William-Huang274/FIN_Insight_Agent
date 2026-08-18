from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.current_runtime_binding import (
    CurrentS1RuntimeBindingError,
    project_request_route_execution_truth,
    validate_current_s1_runtime_binding_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_0.json"
)
RECEIPT = (
    ROOT
    / "configs"
    / "runtime"
    / "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_0.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_runtime_receipt_preserves_lineage_and_open_gates() -> None:
    receipt = validate_current_s1_runtime_binding_receipt(
        _read(RECEIPT),
        _read(POLICY),
    )

    lineage = receipt["source_object_index_lineage"]
    assert lineage["source_record_count"] == 1841
    assert lineage["compiled_object_count"] == 20761
    assert lineage["deduplicated_source_records_carried_only_by_lineage"] == 29
    assert lineage["all_source_records_lineage_bound"] is True
    assert lineage["source_records_missing_from_compiled_lineage"] == []
    assert receipt["embedding_index"]["dtype"] == "float16"
    assert receipt["embedding_index"][
        "cuda_only_learned_execution_policy_preserved"
    ] is True
    assert receipt["acceptance"]["product_pack_readiness_producer_registered"] is False
    assert receipt["acceptance"]["s1_qualified_stable"] is False


def test_request_route_truth_distinguishes_unavailable_route_from_source_gap() -> None:
    receipt = validate_current_s1_runtime_binding_receipt(
        _read(RECEIPT),
        _read(POLICY),
    )
    execution_plan = {
        "narrative_requests": [
            {
                "route_request_id": "NRR::one",
                "query_family_id": "customer_demand_read_through",
                "candidate_routes": [
                    "bm25_lexical",
                    "dense_embedding",
                    "typed_relationship_graph",
                ],
            }
        ],
        "typed_fact_requests": [],
    }

    scheduled = project_request_route_execution_truth(
        execution_plan=execution_plan,
        binding_receipt=receipt,
    )
    routes = scheduled["narrative_route_requests"][0]["routes"]
    assert [row["execution_state"] for row in routes] == [
        "scheduled_in_current_hybrid_runtime",
        "scheduled_in_current_hybrid_runtime",
        "not_executed_route_unavailable",
    ]
    assert all(row["public_information_gap_eligible"] is False for row in routes)

    executed = project_request_route_execution_truth(
        execution_plan=execution_plan,
        binding_receipt=receipt,
        hybrid_result={"result_digest": "a" * 64},
    )
    assert executed["hybrid_candidate_runtime_executed"] is True
    assert executed["narrative_route_requests"][0]["routes"][0][
        "execution_state"
    ] == "executed"
    assert executed["narrative_route_requests"][0]["routes"][2][
        "execution_state"
    ] == "not_executed_route_unavailable"


def test_current_runtime_receipt_fails_closed_on_digest_mutation() -> None:
    receipt = _read(RECEIPT)
    receipt["source_object_index_lineage"]["source_record_count"] += 1

    with pytest.raises(CurrentS1RuntimeBindingError):
        validate_current_s1_runtime_binding_receipt(receipt, _read(POLICY))


def test_current_runtime_receipt_fails_closed_if_s1_is_relabelled_passed() -> None:
    receipt = deepcopy(_read(RECEIPT))
    receipt["acceptance"]["s1_qualified_stable"] = True

    with pytest.raises(CurrentS1RuntimeBindingError):
        validate_current_s1_runtime_binding_receipt(receipt, _read(POLICY))


def test_current_runtime_receipt_fails_closed_on_policy_semantic_drift() -> None:
    policy = deepcopy(_read(POLICY))
    policy["runtime_route_capabilities"][-1]["capability_state"] = "available"

    with pytest.raises(
        CurrentS1RuntimeBindingError,
        match="current_s1_runtime_receipt_policy_drift",
    ):
        validate_current_s1_runtime_binding_receipt(_read(RECEIPT), policy)


def test_current_runtime_receipt_rebuilds_against_bound_assets() -> None:
    receipt = validate_current_s1_runtime_binding_receipt(
        _read(RECEIPT),
        _read(POLICY),
        repository_root=ROOT,
    )

    assert receipt["source_object_index_lineage"][
        "all_source_records_lineage_bound"
    ] is True
