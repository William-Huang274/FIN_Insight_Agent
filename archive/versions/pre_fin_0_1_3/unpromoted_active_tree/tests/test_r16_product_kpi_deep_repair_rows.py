from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r16_product_kpi_deep_repair_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_r16_product_kpi_deep_repair_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": "EL",
        "company": "The Estee Lauder Companies Inc.",
        "verifier_class": "business_segment_mixed_table_needs_column_group",
        "source_url": "https://www.sec.gov/example",
        "fact_id": "fact-1",
        "product_node_type": "segment",
        "product_or_segment": "Skin Care",
        "matched_product_alias": "Skin Care",
        "row_label": "Skin Care",
        "column_label": "2025",
        "metric_name": "product revenue",
        "metric_family": "product_revenue",
        "value": 6962000000,
        "unit": "USD",
        "unit_category": "currency",
        "period": "FY2025",
        "fiscal_year": 2025,
        "citation_span": "Skin Care net sales were 6,962 in the company filing table.",
    }
    row.update(overrides)
    return row


def test_r16_promotes_company_disclosed_product_category_metric() -> None:
    decision = MODULE.classify_verifier_row(_row(), group="column_group")

    assert decision["runtime_action"] == "promote_product_kpi_exact"
    assert decision["attempt_status"] == "product_line_metric_promoted"

    result = MODULE.build_r16_product_kpi_deep_repair(
        verifier_rows=[_row()],
        non_us_rejections=[],
        patentsview_attempts=[],
        generated_at="2026-06-21T00:00:00Z",
    )

    runtime_row = result["runtime_rows"][0]
    assert runtime_row["runtime_action"] == "promote_product_kpi_exact"
    assert runtime_row["product_node_type"] == "product_family"
    assert runtime_row["claim_types"][0] == "company_disclosed_product_kpi"


def test_r16_rejects_external_customer_rows_as_non_product() -> None:
    decision = MODULE.classify_verifier_row(
        _row(
            ticker="STLD",
            verifier_class="business_segment_mixed_table_needs_column_group",
            product_or_segment="External",
            matched_product_alias="External",
            row_label="External",
            citation_span="External sales table row.",
        ),
        group="column_group",
    )

    assert decision["runtime_action"] == "reject_boundary"
    assert decision["attempt_status"] == "non_product_or_total"


def test_r16_future_obligation_requires_future_period_column() -> None:
    current_period = MODULE.classify_verifier_row(
        _row(
            ticker="AEP",
            verifier_class="period_or_version_conflict",
            product_or_segment="Company",
            row_label="Company",
            column_label="Company",
            period="FY2024",
            fiscal_year=2024,
            citation_span="Remaining fixed performance obligations are shown by year.",
        ),
        group="period_version",
    )
    future_period = MODULE.classify_verifier_row(
        _row(
            ticker="AEP",
            verifier_class="period_or_version_conflict",
            product_or_segment="APCo",
            row_label="APCo",
            column_label="2025-2026",
            period="FY2025",
            fiscal_year=2024,
            citation_span="Remaining fixed performance obligations are shown by year.",
        ),
        group="period_version",
    )

    assert current_period["runtime_action"] == "reject_boundary"
    assert current_period["attempt_status"] == "period_version_boundary"
    assert future_period["runtime_action"] == "reroute_operating_metric"
    assert future_period["attempt_status"] == "future_obligation_or_backlog_metric"


def test_r16_patentsview_without_key_is_credential_boundary(monkeypatch) -> None:
    for name in ("PATENTSVIEW_API_KEY", "USPTO_PATENTSVIEW_API_KEY", "PATENT_SEARCH_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    attempts = MODULE.classify_patentsview_attempts(
        [{"ticker": "ADI", "status": "missing_patentsview_api_key", "source_url": "https://search.patentsview.org/api/v1/patent/"}],
        generated_at="2026-06-21T00:00:00Z",
    )

    adi = next(row for row in attempts if row["ticker"] == "ADI")
    assert adi["runtime_action"] == "boundary_only"
    assert adi["attempt_status"] == "credential_bound_gap"
    assert adi["boundary_reason"] == "patentsview_api_key_not_configured"
