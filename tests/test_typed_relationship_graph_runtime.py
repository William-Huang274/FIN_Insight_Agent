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
