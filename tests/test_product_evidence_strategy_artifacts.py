from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_product_evidence_strategy_artifacts.py"
SPEC = importlib.util.spec_from_file_location("build_product_evidence_strategy_artifacts", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extract_product_taxonomy_and_metric_candidates_are_company_disclosed() -> None:
    rows = [
        {
            "ticker": "TEST",
            "company": "Test Co",
            "fiscal_year": 2025,
            "form_type": "10-K",
            "period_end": "2025-12-31",
            "section": "Item 1. Business",
            "block_heading": "Our key products and applications include the following technologies",
            "chunk_id": "TEST_2025_ITEM1_1",
            "source_url": "https://example.test/filing",
            "text": "Our key products and applications include the following technologies:\nCloud Platform\nThe company reported product revenue and backlog for its Cloud Platform.",
        }
    ]

    taxonomy_rows, metric_rows, scan_stats = MODULE.extract_product_evidence_candidates(
        rows,
        max_taxonomy_per_ticker_year=5,
        max_metric_per_ticker_family_year=2,
        max_snippet_chars=240,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert scan_stats["scanned_ticker_count"] == 1
    assert taxonomy_rows
    assert metric_rows
    assert taxonomy_rows[0]["signal_role"] == "company_disclosed"
    assert taxonomy_rows[0]["promotion_status"] == "taxonomy_candidate_needs_review"
    assert metric_rows[0]["signal_strength"] == "S5_primary_authority_candidate"
    assert metric_rows[0]["candidate_status"] == "needs_value_unit_period_product_parser"


def test_metric_extraction_is_balanced_by_ticker_family_year() -> None:
    rows = []
    for index in range(4):
        rows.append(
            {
                "ticker": "AAA",
                "company": "A Co",
                "fiscal_year": 2025,
                "section": "Item 1. Business",
                "chunk_id": f"AAA_{index}",
                "source_url": "https://example.test/a",
                "text": "Product revenue and backlog were discussed in the filing.",
            }
        )
    rows.append(
        {
            "ticker": "ZZZ",
            "company": "Z Co",
            "fiscal_year": 2025,
            "section": "Item 1. Business",
            "chunk_id": "ZZZ_1",
            "source_url": "https://example.test/z",
            "text": "Product revenue was discussed in the filing.",
        }
    )

    _, metric_rows, _ = MODULE.extract_product_evidence_candidates(
        rows,
        max_taxonomy_per_ticker_year=0,
        max_metric_per_ticker_family_year=1,
        max_snippet_chars=200,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    by_ticker_family = {(row["ticker"], row["metric_family"]) for row in metric_rows}
    assert ("AAA", "product_revenue") in by_ticker_family
    assert ("AAA", "backlog_or_orders") in by_ticker_family
    assert ("ZZZ", "product_revenue") in by_ticker_family
    assert sum(1 for row in metric_rows if row["ticker"] == "AAA" and row["metric_family"] == "product_revenue") == 1


def test_external_source_plan_keeps_commercial_blocked() -> None:
    strategy = {
        "industry_source_plan": {
            "software": {
                "company_disclosed_sources": ["SEC filings"],
                "public_proxy_sources": ["GitHub"],
                "commercial_market_tracker_sources": ["Sensor Tower"],
            }
        }
    }

    rows = MODULE.build_external_source_plan(strategy, generated_at="2026-06-11T00:00:00+00:00")
    by_source = {row["source_name"]: row for row in rows}

    assert by_source["SEC filings"]["signal_role"] == "company_disclosed"
    assert by_source["GitHub"]["signal_role"] == "public_proxy"
    assert by_source["Sensor Tower"]["signal_role"] == "commercial_market_tracker"
    assert by_source["Sensor Tower"]["current_policy_status"] == "blocked_no_commercial_policy"
    assert "Do not use weaker roles" in by_source["GitHub"]["non_degradation_guard"]


def test_boilerplate_taxonomy_labels_are_rejected() -> None:
    module = MODULE

    assert module._is_boilerplate_label("Item 1. Business") is True
    assert module._is_boilerplate_label("[TABLE_START id=8 rows=1]") is True
    assert module._is_boilerplate_label("Note 12") is True
    assert module._is_boilerplate_label("to our Consolidated Financial Statements") is True
    assert module._is_boilerplate_label("NVIDIA DGX Cloud") is False


def test_cli_writes_strategy_artifacts(tmp_path: Path) -> None:
    config = tmp_path / "strategy.yaml"
    chunks = tmp_path / "chunks.jsonl"
    taxonomy_output = tmp_path / "taxonomy.jsonl"
    metric_output = tmp_path / "metrics.jsonl"
    external_output = tmp_path / "external.jsonl"
    summary_output = tmp_path / "summary.json"
    report_output = tmp_path / "report.md"
    config.write_text(
        """
schema_version: test
direction_lock:
  research_target: public_evidence_research_analyst
  non_degradation_rule: strict
source_architecture:
  anchor: filings first
  increment: external validation
industry_source_plan:
  software:
    company_disclosed_sources: [SEC filings]
    public_proxy_sources: [GitHub]
    commercial_market_tracker_sources: [Sensor Tower]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    chunks.write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "company": "Test Co",
                "fiscal_year": 2025,
                "section": "Item 1. Business",
                "block_heading": "Products and Services",
                "chunk_id": "TEST_1",
                "source_url": "https://example.test",
                "text": "Products include cloud software and services. Product revenue grew.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = MODULE.main(
        [
            "--strategy-config",
            str(config),
            "--chunk-input",
            str(chunks),
            "--taxonomy-output",
            str(taxonomy_output),
            "--metric-output",
            str(metric_output),
            "--external-source-plan-output",
            str(external_output),
            "--summary-output",
            str(summary_output),
            "--report-output",
            str(report_output),
        ]
    )

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert result == 0
    assert summary["taxonomy_candidate_count"] >= 1
    assert summary["metric_candidate_count"] == 1
    assert summary["commercial_tracker_source_count"] == 1
