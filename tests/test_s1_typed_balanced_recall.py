from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import (
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.hybrid_candidate_runtime import (
    HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION,
    _policy_feature_flags,
    retrieve_hybrid_candidates,
)
from retrieval.query_plan_v3 import compile_query_facet_plan_for_request
from retrieval.route_compiler import load_query_object_fact_route_policy


def _contracts():
    kernel = load_financial_research_kernel(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_2.json"
            ).read_text(encoding="utf-8")
        )
    )
    route = load_query_object_fact_route_policy(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_2.json"
            ).read_text(encoding="utf-8")
        ),
        kernel,
    )
    ontology = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_3.json"
        ).read_text(encoding="utf-8")
    )
    request = load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": "REQ::TYPED-BALANCED-COMMITMENT",
            "cell_id": "CELL::DEMAND",
            "requester_role": "demand_specialist",
            "evidence_domain": "demand",
            "case_key": "MU",
            "subject_ticker": "MU",
            "research_as_of": "2026-08-06",
            "target_entities": ["MU"],
            "requested_facet_ids": ["orders_and_backlog"],
            "metric_intents": ["orders", "operating_income"],
            "product_intents": [
                "HBM and data center business",
                "customer commitment and purchase structure"
            ],
            "period": {
                "start_date": "2025-01-01",
                "end_date": "2026-08-06",
                "fiscal_years": [2026]
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["10-K", "10-Q", "8-K"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["unbound industry demand"],
            "stop_condition": "return candidates, typed facts, or typed gaps",
            "clarification_policy": "return_typed_gap"
        },
        kernel,
    )
    return kernel, route, ontology, request


def _object(identity: str, text: str) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_3",
        "compiled_object_id": identity,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {
            "source_record_id": f"SRC::{identity}",
            "ticker": "MU",
            "company": "Micron Technology, Inc.",
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-06-25",
            "period_end": "2026-05-28",
            "fiscal_year": 2026,
            "section": "Management's Discussion and Analysis",
            "subsection": "Results",
        },
        "lineage_source_record_ids": [f"SRC::{identity}"],
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def test_query_plan_expands_canonical_metrics_and_disclosure_surfaces() -> None:
    kernel, _, ontology, request = _contracts()
    plan = compile_query_facet_plan_for_request(
        kernel,
        request,
        ontology=ontology,
    )
    lane = plan.lanes[0]
    surfaces = "\n".join(row.lexical_query for row in lane.lexical_subqueries)

    assert plan.schema_version == "fin_ia_typed_query_facet_plan_v1_2"
    assert "operating income" in surfaces
    assert "strategic customer agreements" in surfaces
    assert "take-or-pay agreements" in surfaces
    assert "binding commitments for specific volumes" in surfaces
    assert "bookings" not in lane.lexical_query
    assert "COBJ::" not in surfaces and "http" not in surfaces


def test_typed_balanced_policy_inherits_financial_ranking_and_owner_balance() -> None:
    assert _policy_feature_flags(
        HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION
    ) == (True, True, True)


def test_typed_balanced_recall_recovers_material_disclosure_crowded_out_by_broad_query() -> None:
    kernel, route, ontology, request = _contracts()
    generic = [
        _object(
            f"OBJ-GENERIC-{index:03d}",
            (
                "HBM data center orders backlog shipments customer demand "
                "operating results revenue pipeline qualification capacity "
                f"generic discussion {index}"
            ),
        )
        for index in range(80)
    ]
    target = _object(
        "OBJ-TARGET-AGREEMENT",
        (
            "Strategic customer agreements are structured as take-or-pay "
            "agreements, with binding commitments for specific volumes over "
            "multi-year contract terms and substantial customer deposits."
        ),
    )
    objects = tuple([*generic, target])
    embeddings = np.zeros((len(objects), 4), dtype=np.float32)
    query_embedding = np.zeros(4, dtype=np.float32)
    common = {
        "request": request,
        "kernel": kernel,
        "route_policy": route,
        "objects": objects,
        "qwen_document_embeddings": embeddings,
        "qwen_query_embedding": query_embedding,
        "first_stage_limit": 16,
        "candidate_union_limit": 24,
        "output_limit": 16,
        "max_candidates_per_source_record": 2,
        "intent_ontology": ontology,
    }

    predecessor = retrieve_hybrid_candidates(**common)
    successor = retrieve_hybrid_candidates(
        **common,
        typed_balanced_lexical_enabled=True,
    )
    predecessor_ids = {
        row["compiled_object_id"] for row in predecessor["candidates"]
    }
    successor_ids = {row["compiled_object_id"] for row in successor["candidates"]}

    assert "OBJ-TARGET-AGREEMENT" not in predecessor_ids
    assert "OBJ-TARGET-AGREEMENT" in successor_ids
    assert successor["schema_version"] == "fin_ia_s1c_hybrid_candidate_result_v1_5"
    assert successor["query"]["lexical_recall"]["subquery_count"] >= 3
    assert successor["authority"]["candidate_is_not_evidence"] is True
    assert successor["authority"]["numeric_authority"] is False
    assert len(successor["candidate_decision_seed"]) == successor["summary"][
        "union_count_before_source_quota"
    ]
    seed_ids = {
        row["compiled_object_id"] for row in successor["candidate_decision_seed"]
    }
    assert len(seed_ids) == len(successor["candidate_decision_seed"])
    assert "OBJ-TARGET-AGREEMENT" in seed_ids
    assert all(
        row["candidate_not_evidence"] is True
        and row["candidate_text_included"] is False
        and row["evidence_promoted"] is False
        and row["numeric_authority"] is False
        for row in successor["candidate_decision_seed"]
    )
