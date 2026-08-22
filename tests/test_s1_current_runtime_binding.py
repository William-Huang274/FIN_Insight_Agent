from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.current_runtime_binding import (
    CurrentS1RuntimeBindingError,
    build_current_s1_runtime_binding_receipt,
    project_request_route_execution_truth,
    validate_current_s1_runtime_binding_receipt,
)


POLICY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_6.json"
)
RECEIPT = (
    ROOT
    / "configs"
    / "runtime"
    / "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_7.json"
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
    assert lineage["compiled_object_count"] == 34117
    assert lineage["deduplicated_source_records_carried_only_by_lineage"] == 30
    assert lineage["all_source_records_lineage_bound"] is True
    assert lineage["source_records_missing_from_compiled_lineage"] == []
    assert receipt["embedding_index"]["dtype"] == "float16"
    assert receipt["embedding_index"][
        "cuda_only_learned_execution_policy_preserved"
    ] is True
    assert receipt["acceptance"]["product_pack_readiness_producer_registered"] is True
    assert receipt["acceptance"][
        "product_pack_readiness_workbench_consumer_registered"
    ] is True
    assert receipt["product_readiness"]["cases"]["DELL"][
        "readiness_state"
    ] == "blocked_by_evidence_admission"
    assert receipt["product_readiness"]["cases"]["MU"][
        "readiness_state"
    ] == "blocked_by_candidate_coverage"
    assert receipt["product_readiness"]["cases"]["NVDA"][
        "readiness_state"
    ] == "blocked_by_candidate_coverage"
    assert receipt["product_readiness"]["cases"]["DELL"][
        "candidate_review_item_count"
    ] == 18
    assert receipt["product_readiness"]["cases"]["MU"][
        "candidate_review_item_count"
    ] == 23
    assert receipt["product_readiness"]["cases"]["NVDA"][
        "candidate_review_item_count"
    ] == 18
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
    assert [row["required_for_current_runtime"] for row in routes] == [
        True,
        True,
        False,
    ]
    assert scheduled["required_candidate_routes_all_executed"] is False
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
    assert executed["required_candidate_routes_all_executed"] is True


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


def test_current_runtime_receipt_fails_closed_if_product_readiness_is_removed() -> None:
    receipt = deepcopy(_read(RECEIPT))
    receipt["product_readiness"]["cases"].pop("MU")

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


def test_current_runtime_receipt_can_build_against_prospective_registry() -> None:
    registry = _read(
        ROOT
        / "configs"
        / "runtime"
        / "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
    )
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-PROSPECTIVE"
    )

    policy = _read(POLICY)
    policy["binding_receipt_projection"] = {
        "workbench_per_object_lineage_drilldown_complete": True,
    }
    receipt = build_current_s1_runtime_binding_receipt(
        ROOT,
        policy,
        payload_overrides={"runtime_registry": registry},
    )

    assert receipt["registry_binding"]["registry_id"].endswith(
        "PROSPECTIVE"
    )
    assert receipt["acceptance"][
        "workbench_per_object_lineage_drilldown_complete"
    ] is True
    assert receipt["acceptance"]["s1_qualified_stable"] is False


def test_current_product_direct_request_exposes_non_gap_candidate_ceiling() -> None:
    service = ResearchRetrievalService.from_runtime_paths(
        ROOT,
        hybrid_candidate_runtime=object(),
    )
    request = {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ-DELL-CURRENT-BINDING-001",
        "cell_id": "DELL-DEMAND-CELL-001",
        "requester_role": "demand_specialist",
        "evidence_domain": "demand",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["DELL"],
        "requested_facet_ids": ["orders_and_backlog"],
        "metric_intents": ["orders", "backlog"],
        "product_intents": ["AI-optimized servers"],
        "period": {
            "start_date": None,
            "end_date": "2026-08-06",
            "fiscal_years": [],
        },
        "granularity": "quarter_and_fiscal_year",
        "unit": "reported_source_unit",
        "acceptable_sources": ["10-K", "10-Q", "8-K"],
        "acceptable_proxy": False,
        "forbidden_proxy": ["unbound industry demand"],
        "stop_condition": "return candidates or a typed gap",
        "clarification_policy": "return_typed_gap",
    }
    projection = service.execute_request(
        "DELL",
        request,
        ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        ),
    )

    provenance = projection["candidate_ceiling_provenance"]
    assert provenance["runtime_binding_digest"] == projection[
        "runtime_binding"
    ]["result_digest"]
    assert provenance["earliest_observed_limitation"] == (
        "hybrid_candidate_runtime_not_executed"
    )
    assert provenance["gap_eligibility"][
        "public_information_gap_eligible"
    ] is False
    source_truth = projection["source_route_execution_truth"]
    assert source_truth["candidate_coverage_state"] == "not_evaluated"
    assert source_truth["supplement_route_required"] is False
    assert source_truth["requirements"][0]["local_candidate_count"] > 0
    assert {
        row["route_id"]: row["execution_state"]
        for row in source_truth["requirements"][0]["source_routes"]
    }["sec_edgar_official_primary"] == (
        "not_scheduled_candidate_coverage_not_evaluated"
    )
