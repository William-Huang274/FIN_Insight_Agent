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


def test_typed_balanced_policy_inherits_financial_ranking_and_owner_balance() -> None:
    assert _policy_feature_flags(
        HYBRID_RUNTIME_POLICY_TYPED_BALANCED_SCHEMA_VERSION
    ) == (True, True, True)
