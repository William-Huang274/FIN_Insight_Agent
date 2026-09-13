from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.evidence_set_coverage import compile_requirement_plan  # noqa: E402
from sec_agent.research.material_scope import (  # noqa: E402
    ResearchMaterialScopeError,
    compile_research_material_scope,
    compile_research_material_scope_messages,
    parse_research_material_scope_output,
)


KERNEL = load_financial_research_kernel(
    json.loads(
        (
            ROOT
            / "configs/retrieval/financial_research_kernel.json"
        ).read_text(encoding="utf-8")
    )
)


def _request(
    *,
    request_id: str = "REQ::DELL-WORKING-CAPITAL-SCOPE",
    facet_id: str = "working_capital_risk",
    metric_intents: list[str] | None = None,
    product_intents: list[str] | None = None,
    fiscal_years: list[int] | None = None,
    case_key: str = "DELL",
    subject_ticker: str = "DELL",
):
    return load_evidence_request(
        {
            "schema_version": "fin_ia_evidence_request_v1_0",
            "request_id": request_id,
            "cell_id": f"CELL::{case_key}-MATERIAL-SCOPE",
            "requester_role": "cash_conversion_specialist",
            "evidence_domain": "operating_performance",
            "case_key": case_key,
            "subject_ticker": subject_ticker,
            "research_as_of": "2026-08-06",
            "target_entities": [subject_ticker],
            "requested_facet_ids": [facet_id],
            "metric_intents": metric_intents
            if metric_intents is not None
            else ["inventory", "accounts_receivable"],
            "product_intents": product_intents
            if product_intents is not None
            else ["AI infrastructure working-capital dynamics"],
            "period": {
                "start_date": "2025-02-01",
                "end_date": "2026-08-06",
                "fiscal_years": fiscal_years or [2026, 2027],
            },
            "granularity": "quarter_and_fiscal_year",
            "unit": "reported_source_unit",
            "acceptable_sources": ["10-K", "10-Q", "8-K"],
            "acceptable_proxy": False,
            "forbidden_proxy": ["unbound industry demand"],
            "stop_condition": "return candidates, typed facts, or typed gaps",
            "clarification_policy": "return_typed_gap",
        },
        KERNEL,
    )


def _working_capital_payload(request_id: str) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_research_material_scope_atoms_v1_0",
        "research_plan_digest": "PLAN::DEVELOPMENT",
        "request_scopes": [
            {
                "request_id": request_id,
                "product_intent_dispositions": [
                    {
                        "product_intent_index": 0,
                        "disposition": "contextual_retrieval_only",
                    }
                ],
                "requirement_atoms": [
                    {
                        "facet_id": "working_capital_risk",
                        "role": "bridge",
                        "metric_intent_indices": [0, 1],
                        "product_intent_indices": [],
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    },
                    {
                        "facet_id": "working_capital_risk",
                        "role": "counter",
                        "metric_intent_indices": [],
                        "product_intent_indices": [],
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    },
                ],
            }
        ],
    }


def test_material_scope_parser_requires_exact_json() -> None:
    payload = _working_capital_payload("REQ::DELL-WORKING-CAPITAL-SCOPE")
    parsed = parse_research_material_scope_output(
        json.dumps(payload, ensure_ascii=False)
    )
    assert parsed["schema_version"] == "fin_ia_research_material_scope_atoms_v1_0"

    with pytest.raises(ResearchMaterialScopeError, match="not_exact_json"):
        parse_research_material_scope_output(
            "```json\n" + json.dumps(payload) + "\n```"
        )
    with pytest.raises(ResearchMaterialScopeError, match="json_invalid"):
        parse_research_material_scope_output("{not-json}")
