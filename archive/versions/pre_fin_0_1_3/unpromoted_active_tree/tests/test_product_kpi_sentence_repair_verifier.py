from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "verify_product_kpi_sentence_repair_candidates.py"
SPEC = importlib.util.spec_from_file_location("verify_product_kpi_sentence_repair_candidates", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _sentence_fact(**overrides: object) -> dict:
    row = {
        "ticker": "TEST",
        "company": "Test Co",
        "fact_id": "sentence-1",
        "source_id": "company_product_kpi_facts_structured_sentence_metric_parser",
        "metric_family": "product_revenue",
        "product_node_id": "PRODUCTNODE::TEST::segment::cloud",
        "product_or_segment": "Cloud",
        "period": "FY2025",
        "unit": "USD",
        "unit_category": "currency",
        "value": 1_200_000_000.0,
        "raw_value_text": "$1.2 billion",
        "citation_span": "row=Cloud revenue | value=$1.2 billion | unit=usd_billions | source_context=Cloud revenue was $1.2 billion in 2025.",
    }
    row.update(overrides)
    return row


def test_promotes_local_product_revenue_sentence() -> None:
    row = _sentence_fact()
    combined, promoted, rejected, summary = MODULE.verify_sentence_candidates(
        base_rows=[],
        repair_rows=[row],
        revenue_rejection_rows=[{"fact_id": "sentence-1", "rejection_reason": "not_structured_table_metric"}],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert len(combined) == 1
    assert len(promoted) == 1
    assert not rejected
    assert promoted[0]["repair_promotion_gate"] == "strict_local_product_revenue_sentence_verifier_v0_1"
    assert summary["promoted_fact_count"] == 1


def test_rejects_growth_or_financial_context_sentence() -> None:
    row = _sentence_fact(
        fact_id="sentence-2",
        citation_span=(
            "row=Data Center segment revenue growth | value=$68.1 million | unit=usd_millions | "
            "source_context=Data Center segment revenue growth of $68.1 million was attributable to foreign currency."
        ),
    )
    _, promoted, rejected, _ = MODULE.verify_sentence_candidates(
        base_rows=[],
        repair_rows=[row],
        revenue_rejection_rows=[{"fact_id": "sentence-2", "rejection_reason": "not_structured_table_metric"}],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert not promoted
    assert rejected[0]["rejection_reason"] == "local_product_value_relation_not_verified"


def test_rejects_sentence_claim_already_covered() -> None:
    row = _sentence_fact()
    _, promoted, rejected, _ = MODULE.verify_sentence_candidates(
        base_rows=[
            {
                "ticker": "TEST",
                "product_node_id": "PRODUCTNODE::TEST::segment::cloud",
                "metric_family": "product_revenue",
                "period": "FY2025",
                "unit": "USD",
            }
        ],
        repair_rows=[row],
        revenue_rejection_rows=[{"fact_id": "sentence-1", "rejection_reason": "not_structured_table_metric"}],
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert not promoted
    assert rejected[0]["rejection_reason"] == "claim_already_covered_by_accepted_fact_layer"
