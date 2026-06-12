from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "download_public_source_extended_materialization.py"
SPEC = importlib.util.spec_from_file_location("download_public_source_extended_materialization", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_find_zip_link_prefers_label() -> None:
    html = """
    <a href="/files/structureddata/data/financial-statement-data-sets/2025q4.zip">2025 Q4</a>
    <a href="/files/structureddata/data/financial-statement-data-sets/2026q1.zip">2026 Q1</a>
    """

    link = MODULE.find_zip_link(html, "https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets", r"2026\s+Q1")

    assert link["url"].endswith("/files/structureddata/data/financial-statement-data-sets/2026q1.zip")
    assert link["label"] == "2026 Q1"


def test_extract_product_metric_candidates(tmp_path: Path) -> None:
    chunk_path = tmp_path / "chunks.jsonl"
    chunk_path.write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "company": "Test Co",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "section": "Item 1",
                "chunk_id": "TEST_1",
                "source_url": "https://example.com/filing",
                "text": "The company reported product revenue and backlog for its platform.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = MODULE.extract_product_metric_candidates([chunk_path], max_candidates=10, max_per_family=10, generated_at="2026-06-11T00:00:00+00:00")

    assert rows
    assert rows[0]["source_id"] == "company_reported_product_operating_metrics"
    assert rows[0]["ticker"] == "TEST"
    assert rows[0]["candidate_status"] == "needs_value_unit_period_product_parser"
