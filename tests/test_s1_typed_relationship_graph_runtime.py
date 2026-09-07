from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    HYBRID_RESULT_RELATIONSHIP_GRAPH_SCHEMA_VERSION,
    _direct_relationship_material_route_qualified,
    retrieve_hybrid_candidates,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


def _contracts():
    kernel = load_financial_research_kernel(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
            ).read_text(encoding="utf-8")
        )
    )
    route = load_query_object_fact_route_policy(
        json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
            ).read_text(encoding="utf-8")
        ),
        kernel,
    )
    request = load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": "REQ::DELL::RELATIONSHIP-GRAPH-TEST",
            "cell_id": "CELL::DELL::SUPPLY-CHAIN",
            "requester_role": "supply_specialist",
            "evidence_domain": "relationship",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
            "target_entities": ["DELL", "NVDA"],
            "requested_facet_ids": ["counterparty_direct_mention"],
            "metric_intents": ["shipments"],
            "product_intents": ["supplier names Dell"],
            "period": {
                "start_date": "2025-02-01",
                "end_date": "2026-08-06",
                "fiscal_years": [2026, 2027],
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["PUBLIC_WEB"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["wrong relationship direction"],
            "stop_condition": "return candidates or a typed gap",
            "clarification_policy": "return_typed_gap",
        },
        kernel,
    )
    return kernel, route, request


def _object(
    identity: str,
    *,
    ticker: str,
    text: str,
    publication_date: str = "2026-02-13",
    fiscal_year: int | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_3",
        "compiled_object_id": identity,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {
            "source_record_id": f"SRC::{identity}",
            "ticker": ticker,
            "company": ticker,
            "source_type": "PUBLIC_WEB",
            "source_tier": "named_counterparty_or_standards_primary",
            "publication_date": publication_date,
            "period_end": "",
            "fiscal_year": fiscal_year,
            "section": "Official announcement",
            "subsection": "Relationship",
        },
        "lineage_source_record_ids": [f"SRC::{identity}"],
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def test_graph_route_recalls_current_explicit_mention_and_rejects_mutations() -> None:
    kernel, route, request = _contracts()
    objects = (
        _object(
            "CURRENT-DIRECT-DELL",
            ticker="NVDA",
            text=(
                "NVIDIA-powered Dell Technologies servers will be available "
                "for enterprise AI deployments this quarter."
            ),
        ),
        _object(
            "OLD-DIRECT-DELL",
            ticker="NVDA",
            text="NVIDIA-powered Dell Technologies servers were announced.",
            publication_date="2023-08-22",
        ),
        _object(
            "NO-DIRECT-DELL",
            ticker="NVDA",
            text="Customers and suppliers support the NVIDIA platform.",
        ),
        _object(
            "WRONG-COMPANY",
            ticker="MU",
            text="Micron and Dell Technologies announced a server collaboration.",
        ),
    )
    result = retrieve_hybrid_candidates(
        request=request,
        kernel=kernel,
        route_policy=route,
        objects=objects,
        qwen_document_embeddings=np.zeros((len(objects), 4), dtype=np.float32),
        qwen_query_embedding=np.zeros(4, dtype=np.float32),
        first_stage_limit=4,
        candidate_union_limit=8,
        output_limit=4,
        max_candidates_per_source_record=2,
        typed_relationship_graph_enabled=True,
    )
    by_id = {row["compiled_object_id"]: row for row in result["candidates"]}

    assert result["schema_version"] == HYBRID_RESULT_RELATIONSHIP_GRAPH_SCHEMA_VERSION
    assert "typed_relationship_graph" in by_id["CURRENT-DIRECT-DELL"][
        "route_membership"
    ]
    assert result["summary"]["typed_relationship_graph_first_stage_count"] == 1
    assert result["summary"]["typed_relationship_graph_executed"] is True
    assert result["summary"]["hard_filter_exclusions"] == {
        "outside_evidence_owner_scope": 1,
        "reporting_period_outside_request": 1,
    }
    assert result["route_execution"]["executed_candidate_routes"] == [
        "bm25_lexical",
        "dense_embedding",
        "typed_relationship_graph",
    ]
    assert result["query"]["typed_relationship_graph"]["result_or_label_access"] is False
    assert result["authority"]["candidate_is_not_evidence"] is True
    assert result["authority"]["numeric_authority"] is False


def test_direct_relationship_material_gate_requires_graph_qualification() -> None:
    assert _direct_relationship_material_route_qualified(
        facet_id="counterparty_direct_mention",
        object_id="DIRECT",
        graph_ranks={"DIRECT": 1},
    ) is True
    assert _direct_relationship_material_route_qualified(
        facet_id="counterparty_direct_mention",
        object_id="GENERIC-CUSTOMER-TEXT",
        graph_ranks={},
    ) is False
    assert _direct_relationship_material_route_qualified(
        facet_id="upstream_capacity_context",
        object_id="CAPACITY-CONTEXT",
        graph_ranks={},
    ) is True
def test_nonperiodic_current_source_uses_publication_window_not_missing_fiscal_year() -> None:
    kernel, route, request = _contracts()
    current = _object(
        "CURRENT-NONPERIODIC",
        ticker="NVDA",
        text="Dell Technologies server systems are powered by NVIDIA platforms.",
        fiscal_year=None,
    )
    result = retrieve_hybrid_candidates(
        request=request,
        kernel=kernel,
        route_policy=route,
        objects=(current,),
        qwen_document_embeddings=np.zeros((1, 4), dtype=np.float32),
        qwen_query_embedding=np.zeros(4, dtype=np.float32),
        first_stage_limit=1,
        candidate_union_limit=1,
        output_limit=1,
        max_candidates_per_source_record=1,
        typed_relationship_graph_enabled=True,
    )

    assert result["summary"]["eligible_object_count"] == 1
    assert result["candidates"][0]["compiled_object_id"] == "CURRENT-NONPERIODIC"
