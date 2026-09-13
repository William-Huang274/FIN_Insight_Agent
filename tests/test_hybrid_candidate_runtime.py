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
    LazyLocalQwenHybridCandidateRuntime,
    retrieve_hybrid_candidates,
)
from retrieval.route_compiler import load_query_object_fact_route_policy


def test_lazy_qwen_runtime_preserves_retrieve_many_interface_without_model_load() -> None:
    class RecordingDelegate:
        def __init__(self) -> None:
            self.call = None

        def retrieve_many(self, requests, **kwargs):
            self.call = (requests, kwargs)
            return ({"status": "delegated"},)

    delegate = RecordingDelegate()
    runtime = LazyLocalQwenHybridCandidateRuntime(ROOT, {})
    runtime._delegate = delegate
    requests = (object(),)
    kernel = object()
    route_policy = object()
    material_runtime_inputs = {"request": {"input": True}}
    material_runtime_policy = {"policy": True}
    intent_ontology = {"ontology": True}
    retrieval_need_policy = {"need": True}

    result = runtime.retrieve_many(
        requests,
        kernel=kernel,
        route_policy=route_policy,
        material_runtime_inputs=material_runtime_inputs,
        material_runtime_policy=material_runtime_policy,
        intent_ontology=intent_ontology,
        retrieval_need_policy=retrieval_need_policy,
    )

    assert result == ({"status": "delegated"},)
    assert delegate.call == (
        requests,
        {
            "kernel": kernel,
            "route_policy": route_policy,
            "material_runtime_inputs": material_runtime_inputs,
            "material_runtime_policy": material_runtime_policy,
            "intent_ontology": intent_ontology,
            "retrieval_need_policy": retrieval_need_policy,
        },
    )


def _object(
    identity: str,
    *,
    ticker: str,
    text: str,
    source: str,
    publication_date: str = "2026-05-30",
    fiscal_year: int = 2027,
) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_0",
        "compiled_object_id": identity,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {
            "source_record_id": source,
            "ticker": ticker,
            "company": ticker,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": publication_date,
            "period_end": "2026-05-01",
            "fiscal_year": fiscal_year,
            "section": "Results of Operations",
            "subsection": "Quarterly results",
        },
        "lineage_source_record_ids": [source],
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }
