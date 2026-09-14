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
from retrieval.financial_intent_v3 import (  # noqa: E402
    concept_aliases,
    evaluate_financial_intent,
)
from retrieval.evidence_role_v4 import (  # noqa: E402
    evaluate_evidence_role,
)
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    HYBRID_RESULT_GROUPED_RECALL_SCHEMA_VERSION,
    HYBRID_RUNTIME_POLICY_GROUPED_RECALL_SCHEMA_VERSION,
    _policy_feature_flags,
    retrieve_hybrid_candidates,
)
from retrieval.query_plan_v3 import (  # noqa: E402
    QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION,
    compile_query_facet_plan_for_request,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


def _read(ref: str) -> dict[str, object]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _object(identity: str, *, ticker: str, text: str) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_3",
        "compiled_object_id": identity,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {
            "source_record_id": f"SRC::{identity}",
            "ticker": ticker,
            "company": ticker,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-05-20",
            "period_end": "2026-04-26",
            "fiscal_year": 2027,
            "section": "Management's Discussion and Analysis",
            "subsection": "Supply and demand",
        },
        "lineage_source_record_ids": [f"SRC::{identity}"],
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def test_observed_public_supply_state_is_review_compatible_not_evidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "NVDA",
            "section": "Reviewed public source",
            "subsection": "NVIDIA Investor Relations",
            "source_type": "PUBLIC_WEB",
            "object_kind": "claim",
            "document_text": (
                "Blackwell production is ramping at full speed and cloud GPUs "
                "are sold out."
            ),
            "structured_projection": {},
        },
        slot_id="capacity_inputs_execution",
        facet_id="upstream_capacity_context",
        subject_ticker="DELL",
        evidence_owner_ticker="NVDA",
        relationship_direction="upstream_supplier_to_subject",
    )

    assert result.compatibility == "compatible"
    assert "direct_supply_capacity_signal" in result.labels
    assert "supply_risk_or_counterevidence" in result.labels
    assert result.evidence_promoted is False
