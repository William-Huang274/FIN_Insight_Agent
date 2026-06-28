from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_company_reported_product_operating_metric_runtime_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_company_reported_product_operating_metric_runtime_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_company_reported_product_operating_metric_runtime_rows_pass_gate() -> None:
    runtime_rows, rejection_rows = MODULE.build_company_reported_product_operating_metric_runtime_rows(
        [_fact_row()],
        generated_at="2026-06-16T00:00:00Z",
    )
    assert not rejection_rows
    assert len(runtime_rows) == 1
    row = runtime_rows[0]
    assert row["source_id"] == "company_reported_product_operating_metrics"
    assert row["source_layer_id"] == "L1"
    assert row["promotion_status"] == "runtime_fact_allowed"
    assert row["exact_value_authority"] is True
    assert row["can_support_company_exact_fact"] is True
    assert row["product_binding_status"] == "product_mentioned_in_snapshot"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True),
                _source("company_reported_product_operating_metrics", "L1", "structured_not_promoted"),
            ]
        },
        observed_rows=runtime_rows,
        specialist_visible_rows={
            "fundamental_analyst": runtime_rows,
            "product_technology_analyst": runtime_rows,
            "capital_ownership_macro_analyst": runtime_rows,
        },
        required_dimensions=["fundamentals", "product_and_production"],
        generated_at="2026-06-16T00:00:00Z",
    )
    statuses = {row["requirement_id"]: row["status"] for row in coverage["requirements"]}
    assert coverage["status"] == "pass"
    assert statuses["primary_company_disclosure"] == "pass"
    assert statuses["official_product_surface"] == "pass"


def test_company_reported_product_operating_metric_runtime_rows_reject_incomplete_candidates() -> None:
    bad_fact = _fact_row()
    bad_fact["value"] = None
    rows, rejections = MODULE.build_company_reported_product_operating_metric_runtime_rows(
        [bad_fact],
        generated_at="2026-06-16T00:00:00Z",
    )
    assert rows == []
    assert rejections
    assert rejections[0]["rejection_reason"].startswith("missing_")


def test_company_reported_product_operating_metric_runtime_cli_like_summary(tmp_path: Path) -> None:
    fact_path = tmp_path / "facts.jsonl"
    fact_path.write_text(json.dumps(_fact_row()) + "\n", encoding="utf-8")
    source_layer_path = tmp_path / "source_layer.jsonl"
    source_layer_path.write_text(
        "\n".join(
            [
                json.dumps(_source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True)),
                json.dumps(_source("company_reported_product_operating_metrics", "L1", "structured_not_promoted")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = MODULE._load_jsonl(fact_path)
    runtime_rows, rejection_rows = MODULE.build_company_reported_product_operating_metric_runtime_rows(
        rows,
        generated_at="2026-06-16T00:00:00Z",
    )
    coverage = MODULE.build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability={"rows": MODULE._load_jsonl(source_layer_path)},
        observed_rows=runtime_rows,
        specialist_visible_rows={"fundamental_analyst": runtime_rows, "product_technology_analyst": runtime_rows},
        required_dimensions=["fundamentals", "product_and_production"],
        generated_at="2026-06-16T00:00:00Z",
    )
    summary = MODULE.build_summary(
        fact_rows=rows,
        runtime_rows=runtime_rows,
        rejection_rows=rejection_rows,
        coverage_gate=coverage,
        generated_at="2026-06-16T00:00:00Z",
        output_rows=tmp_path / "rows.jsonl",
        output_rejections=tmp_path / "reject.jsonl",
        output_coverage=tmp_path / "gate.json",
    )
    assert summary["status"] == "pass"
    assert summary["runtime_row_count"] == 1
    assert summary["coverage_gate_status"] == "pass"


def _fact_row() -> dict[str, object]:
    return {
        "fact_id": "PRODUCTKPI::TST::product_revenue::1",
        "fact_status": "parser_verified_fact",
        "ticker": "TST",
        "company": "TestCo Inc.",
        "industry_schema": "consumer_electronics_semiconductor_hardware",
        "product_or_segment": "Accelerator Segment",
        "product_node_id": "PRODUCTNODE::TST::accelerator",
        "product_node_type": "segment",
        "metric_family": "product_revenue",
        "metric_name": "net sales",
        "period": "FY2025",
        "period_end": "2025-12-31",
        "period_type": "annual",
        "unit": "USD",
        "unit_category": "currency",
        "value": 123000000.0,
        "raw_value_text": "$123 million",
        "scale": "million",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1/test.htm",
        "citation_span": "Accelerator Segment net sales were $123 million in fiscal 2025.",
        "source_document_id": "TST_2025_10K_ITEM1",
        "source_id": "company_product_kpi_facts_parser_verified",
        "runtime_use_boundary": "May support company-disclosed product KPI facts only.",
    }


def _source(source_id: str, layer_id: str, status: str, *, exact: bool = False) -> dict[str, object]:
    return {
        "source_id": source_id,
        "layer_id": layer_id,
        "evidence_graph_status": status,
        "runtime_ready_context": status in {"runtime_ready_context", "exact_authority_ready"},
        "exact_value_authority_ready": exact,
        "can_support_company_exact_fact": exact,
        "can_crawl_or_download": True,
        "can_structure": True,
    }
