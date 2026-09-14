from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from apps.workbench.backend.api.v1.research_retrieval import (
    build_research_retrieval_router,
)
from retrieval.candidate_retriever import CandidateCorpus, retrieve_query_plan
from retrieval.contracts import (
    RetrievalContractError,
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.query_plan import (
    compile_query_facet_plan,
    compile_query_facet_plan_for_request,
)
from sec_agent.runtime_resource_registry import resolve_registered_runtime_resource


def _evidence_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ-DELL-DEMAND-001",
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
    payload.update(overrides)
    return payload


def _record(
    evidence_id: str,
    ticker: str,
    publication_date: str,
    text: str,
    *,
    source_type: str = "10-Q",
    subsection: str = "Management discussion",
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "source_type": source_type,
        "source_tier": "primary_sec_filing",
        "ticker": ticker,
        "company": ticker,
        "fiscal_year": 2026,
        "period_end": "2026-06-30",
        "publication_date": publication_date,
        "section": "Item 2. Management's Discussion and Analysis",
        "subsection": subsection,
        "evidence_type": "management_discussion",
        "topics": [],
        "text": text,
        "source_url": f"https://example.test/{evidence_id}",
        "metadata": {"accession_number": evidence_id},
    }
