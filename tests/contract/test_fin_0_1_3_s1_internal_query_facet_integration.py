from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_query_facet_integration import (  # noqa: E402
    ROUTE_IDS,
    RUN_SCOPE,
    S1InternalQueryFacetError,
    build_internal_query_facet_zero_call_proof,
    compile_internal_query_facet_requests,
    load_internal_query_facet_policy,
    validate_internal_route_request,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_internal_query_facet_integration_policy_v1_0.json"
)
SOURCE_PROOF_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_unified_query_facet_zero_call_proof_v1_0.json"
)
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_internal_query_facet_integration_zero_call_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.fixture(scope="module")
def compiled() -> tuple[dict, tuple, tuple]:
    policy = load_internal_query_facet_policy(POLICY_PATH)
    bundles, requests = compile_internal_query_facet_requests(
        query_facet_proof=_load(SOURCE_PROOF_PATH), policy=policy
    )
    return policy, bundles, requests


def test_policy_binds_external_closeout_and_frozen_query_contract() -> None:
    policy = load_internal_query_facet_policy(POLICY_PATH)
    refs = policy["immutable_inputs"]
    for stem in (
        "query_facet_proof",
        "query_facet_policy",
        "progression_plan",
        "external_closeout",
        "retrieval_config",
        "milvus_runtime",
    ):
        assert _normalized_sha256(ROOT / refs[f"{stem}_ref"]) == refs[
            f"{stem}_sha256"
        ]
    closeout = _load(ROOT / refs["external_closeout_ref"])
    assert closeout["decision"]["external_release_blocker_preserved"] is True
    assert closeout["decision"]["internal_query_facet_integration_authorized"] is True
    assert closeout["decision"]["current_next_scope"] == RUN_SCOPE


def test_thirty_six_plans_pair_into_eighteen_bundles_and_ninety_requests(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    _, bundles, requests = compiled
    assert len(bundles) == 18
    assert len(requests) == 90
    assert len({bundle.bundle_id for bundle in bundles}) == 18
    assert len({request.request_id for request in requests}) == 90
    assert {
        route_id: sum(request.route_id == route_id for request in requests)
        for route_id in ROUTE_IDS
    } == {route_id: 18 for route_id in ROUTE_IDS}
    for bundle in bundles:
        assert set(bundle.source_plan_ids) == {"en", "zh"}
        local = [request for request in requests if request.bundle_id == bundle.bundle_id]
        assert {request.route_id for request in local} == set(ROUTE_IDS)


def test_content_routes_use_evidence_owner_not_current_case_ticker(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    _, bundles, requests = compiled
    dell_customer = next(
        bundle
        for bundle in bundles
        if (
            bundle.case_key,
            bundle.evidence_slot_id,
            bundle.evidence_owner_entity_key,
        )
        == ("DELL", "customer_demand_and_deployment_validation", "MSFT")
    )
    assert dell_customer.subject_ticker == "DELL"
    assert dell_customer.evidence_owner_ticker == "MSFT"
    for request in requests:
        if request.bundle_id != dell_customer.bundle_id:
            continue
        assert request.typed_filters["subject_ticker"] == "DELL"
        assert request.typed_filters["evidence_owner_ticker"] == "MSFT"
        if request.route_id != "internal_relationship_graph":
            if "ticker" in request.typed_filters:
                assert request.typed_filters["ticker"] == "MSFT"
            if "tickers" in request.typed_filters:
                assert request.typed_filters["tickers"] == ["MSFT"]


def test_tsmc_projects_to_local_tsm_and_preserves_relationship_direction(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    _, bundles, requests = compiled
    tsmc_bundles = [
        bundle for bundle in bundles if bundle.evidence_owner_entity_key == "TSMC"
    ]
    assert len(tsmc_bundles) == 3
    assert {bundle.evidence_owner_ticker for bundle in tsmc_bundles} == {"TSM"}
    for bundle in tsmc_bundles:
        assert bundle.relationship_direction == (
            "evidence_owner_own_supply_capacity_or_constraint"
        )
        local = [request for request in requests if request.bundle_id == bundle.bundle_id]
        assert len(local) == 5
        assert all(request.evidence_owner_ticker == "TSM" for request in local)
        assert all(
            request.typed_filters["relationship_direction"]
            == bundle.relationship_direction
            for request in local
        )


def test_each_route_consumes_its_own_query_family_and_filters(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    policy, bundles, requests = compiled
    bundle_map = {bundle.bundle_id: bundle for bundle in bundles}
    for request in requests:
        validate_internal_route_request(
            request, bundles=bundle_map, policy=policy
        )
        filters = request.typed_filters
        assert filters["fiscal_years"]
        assert filters["publication_date_on_or_before"] == "2026-08-06"
        assert filters["allow_relaxed_identity_period_or_relationship_fallback"] is False
        if request.route_id == "internal_sql_exact":
            assert request.query_texts == ()
            assert filters["metric_families"]
            assert filters["exact_value_authority"] is True
        elif request.route_id == "internal_object_bm25":
            assert request.query_texts
            assert filters["object_types"]
        elif request.route_id == "internal_bm25":
            assert request.query_texts
            assert filters["form_types"]
        elif request.route_id == "internal_milvus_dense":
            assert request.query_texts
            assert filters["typed_filter_required"] is True
            assert filters["vector_kinds"]
        else:
            assert request.query_texts == ()
            assert filters["query_kind"] == "typed_one_hop_evidence_relationship"
            assert filters["maximum_hops"] == 1
            assert filters["allowed_source_roles"]


def test_chinese_queries_are_retained_but_not_the_canonical_internal_query(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    _, _, requests = compiled
    query_routes = [
        request
        for request in requests
        if request.route_id
        in {"internal_object_bm25", "internal_bm25", "internal_milvus_dense"}
    ]
    assert query_routes
    assert all(request.query_texts for request in query_routes)
    assert all(request.alternate_language_query_texts for request in query_routes)
    assert all(
        request.query_texts != request.alternate_language_query_texts
        for request in query_routes
    )


def test_source_plan_request_identity_and_typed_scope_mutations_fail_closed(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    policy, bundles, requests = compiled
    source = _load(SOURCE_PROOF_PATH)
    source["plans"][0]["plan_digest"] = "0" * 64
    with pytest.raises(
        S1InternalQueryFacetError, match="internal_query_facet_source_proof_invalid"
    ):
        compile_internal_query_facet_requests(
            query_facet_proof=source, policy=policy
        )

    bundle_map = {bundle.bundle_id: bundle for bundle in bundles}
    mutated = replace(requests[0], evidence_owner_ticker="NVDA")
    with pytest.raises(
        S1InternalQueryFacetError, match="internal_route_request_owned_identity_invalid"
    ):
        validate_internal_route_request(
            mutated, bundles=bundle_map, policy=policy
        )

    body = requests[0].as_dict()
    body["typed_filters"]["fiscal_years"] = [2099]
    body.pop("request_id")
    body.pop("request_digest")
    digest = canonical_digest(body)
    rebound = replace(
        requests[0],
        request_id=f"internal_route_request_{digest[:20]}",
        request_digest=digest,
        typed_filters=body["typed_filters"],
    )
    with pytest.raises(
        S1InternalQueryFacetError, match="internal_route_request_typed_filter_drift"
    ):
        validate_internal_route_request(
            rebound, bundles=bundle_map, policy=policy
        )


def test_input_permutation_is_stable(compiled: tuple[dict, tuple, tuple]) -> None:
    policy, bundles, requests = compiled
    source = _load(SOURCE_PROOF_PATH)
    source["plans"] = list(reversed(source["plans"]))
    body = dict(source)
    body.pop("proof_digest")
    source["proof_digest"] = canonical_digest(body)
    other_bundles, other_requests = compile_internal_query_facet_requests(
        query_facet_proof=source, policy=policy
    )
    assert [bundle.bundle_digest for bundle in other_bundles] == [
        bundle.bundle_digest for bundle in bundles
    ]
    assert [request.request_digest for request in other_requests] == [
        request.request_digest for request in requests
    ]


def test_materialized_proof_is_zero_call_digest_bound_and_honest() -> None:
    proof = _load(OUTPUT_PATH)
    body = dict(proof)
    supplied = body.pop("proof_digest")
    assert supplied == canonical_digest(body)
    assert proof["status"] == "zero_call_engineering_pass"
    assert proof["bilingual_bundle_count"] == 18
    assert proof["physical_request_count"] == 90
    assert proof["route_request_counts"] == {
        route_id: 18 for route_id in ROUTE_IDS
    }
    assert not any(proof["observed_calls"].values())
    assert proof["quality_checks"]["candidate_ceiling_proven"] is False
    assert proof["quality_checks"]["BGE_fusion_rerank_admitted"] is False
    assert proof["stage_acceptance"]["internal_query_facet_projection"] is True
    assert proof["stage_acceptance"]["internal_route_execution"] is False
    assert proof["stage_acceptance"]["external_product_coverage"] is False


def test_project_os_preserves_completed_s1_scopes_after_physical_r2() -> None:
    completed = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert completed["status"] == "pass"
    candidate_ceiling = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_CANDIDATE_CEILING_AND_QRELS_GATE"
    )
    assert candidate_ceiling["status"] == "pass"
    refresh = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
    )
    assert refresh["status"] == "pass"
    assert refresh["open_full_chain_blockers"] == []
    dell_vertical = run_project_os_preflight(
        ROOT,
        run_scope="S1_DELL_FINANCIAL_SOURCE_OBJECT_AND_EVIDENCE_PACK_VERTICAL_SLICE",
    )
    assert dell_vertical["status"] == "pass"
    transfer = run_project_os_preflight(
        ROOT,
        run_scope="S1_MU_NVDA_CORE_UNCHANGED_TRANSFER",
    )
    assert transfer["status"] == "pass"
    current = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_CURRENT_OFFICIAL_SOURCE_ACQUISITION"
    )
    assert current["status"] == "pass"
    ranking = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
    )
    assert ranking["status"] == "pass"
    assert ranking["open_full_chain_blockers"] == []
    assert ranking["scope_resolution"]["operation_class"] == (
        "ranking_evaluation"
    )


def test_build_proof_does_not_smuggle_execution_or_ranking(
    compiled: tuple[dict, tuple, tuple],
) -> None:
    policy, bundles, requests = compiled
    proof = build_internal_query_facet_zero_call_proof(
        bundles=bundles, requests=requests, policy=policy
    )
    assert proof["stage_acceptance"] == {
        "internal_query_facet_projection": True,
        "internal_route_execution": False,
        "candidate_ceiling_and_qrels": False,
        "BGE_fusion_rerank": False,
        "downstream_utilization": False,
        "external_product_coverage": False,
        "release": False,
    }
    assert proof["observed_calls"] == {
        "network": 0,
        "provider": 0,
        "model": 0,
        "document_fetch": 0,
        "retrieval": 0,
        "embedding": 0,
        "rerank": 0,
        "evidence_promotion": 0,
    }
