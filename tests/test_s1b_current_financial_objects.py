from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from ingestion.section_splitter import find_sec_filing_sections
from retrieval.financial_objects import (
    FinancialObjectError,
    attach_legacy_aliases,
    compile_raw_sec_html_capture,
    project_market_snapshot,
    validate_source_object_manifest,
)


def _raw_capture(html: str) -> dict[str, object]:
    body = html.encode("utf-8")
    return {
        "capture_before_parse": True,
        "status_code": 200,
        "credential_cookie_authorization_present": False,
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_bytes": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "final_url": "https://www.sec.gov/example.htm",
    }


def _source_spec() -> dict[str, object]:
    return {
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "form_type": "10-K",
        "source_tier": "primary_sec_filing",
        "accession_number": "0000000000-26-000001",
        "publication_date": "2026-03-16",
        "period_end": "2026-01-30",
        "fiscal_year": 2026,
        "source_url": "https://www.sec.gov/example.htm",
        "target_words": 80,
        "overlap_words": 10,
        "min_words": 10,
    }


def test_inline_uppercase_fallback_uses_terminal_item_boundaries() -> None:
    text = (
        "X" * 4000
        + " ITEM 1 — BUSINESS "
        + "company business facts " * 300
        + " ITEM 1A — RISK FACTORS "
        + "risk facts " * 300
        + " ITEM 1B — UNRESOLVED STAFF COMMENTS None. "
        + " ITEM 7 — MANAGEMENT’S DISCUSSION AND ANALYSIS "
        + "management facts " * 300
        + " ITEM 7A — QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK "
        + "market risk facts " * 100
        + " ITEM 8 — FINANCIAL STATEMENTS "
        + "financial statement facts " * 300
        + " ITEM 9 — CHANGES IN AND DISAGREEMENTS None."
    )
    sections = find_sec_filing_sections(text, form_type="10-K")

    assert [row.item_code for row in sections] == ["1", "1A", "7", "7A", "8"]
    assert "ITEM 1B" not in sections[1].text
    assert "ITEM 9" not in sections[-1].text


def test_raw_capture_reparse_preserves_table_atom_and_parent_lineage() -> None:
    html = """
    <html><body>
      <h1>ITEM 1 — BUSINESS</h1><p>{business}</p>
      <h1>ITEM 1A — RISK FACTORS</h1><p>{risk}</p>
      <h1>ITEM 7 — MANAGEMENT’S DISCUSSION AND ANALYSIS</h1>
      <p>{management}</p>
      <table><tr><th>Metric</th><th>2026</th></tr><tr><td>Revenue</td><td>100</td></tr></table>
      <h1>ITEM 7A — QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK</h1>
      <p>{market}</p>
      <h1>ITEM 8 — FINANCIAL STATEMENTS</h1><p>{financial}</p>
    </body></html>
    """.format(
        business="business facts " * 450,
        risk="risk facts " * 450,
        management="management facts " * 450,
        market="market risk facts " * 200,
        financial="financial facts " * 450,
    )
    parent, children = compile_raw_sec_html_capture(
        _raw_capture(html),
        source_spec=_source_spec(),
        capture_ref="objects/raw/capture.json",
        capture_sha256="f" * 64,
    )

    assert parent["lineage_state"] == "immutable_capture_bound"
    assert parent["raw_body_bytes"] > 0
    assert parent["child_count"] == len(children)
    assert len(children) > 5
    table_children = [row for row in children if row["metadata"]["contains_table"]]
    assert table_children
    assert all(
        row["text"].count("[TABLE_START") == row["text"].count("[TABLE_END]")
        for row in table_children
    )
    assert all(
        row["metadata"]["parent_document_id"] == parent["document_id"]
        and row["metadata"]["source_capture_ref"] == "objects/raw/capture.json"
        for row in children
    )


def test_raw_capture_digest_mismatch_fails_closed() -> None:
    payload = _raw_capture("<html><body>ITEM 1 BUSINESS</body></html>")
    payload["body_sha256"] = "0" * 64
    with pytest.raises(FinancialObjectError, match="body_digest_mismatch"):
        compile_raw_sec_html_capture(
            payload,
            source_spec=_source_spec(),
            capture_ref="capture.json",
            capture_sha256="a" * 64,
        )


def test_market_snapshot_projection_is_role_not_valuation() -> None:
    parent, child = project_market_snapshot(
        {
            "ticker": "DELL",
            "as_of_date": "2026-06-24",
            "snapshot_id": "snapshot-r1",
            "evidence_id": "MARKET::DELL::2026-06-24",
            "text": "DELL market price and valuation snapshot as of 2026-06-24.",
            "provider": "test",
            "field_status": {
                "close_price": "provided",
                "market_cap": "missing_not_provided",
                "enterprise_value": "missing_not_provided",
                "pe_ttm": "missing_not_provided",
                "ev_sales_ttm": "missing_not_provided",
                "ev_ebitda_ttm": "missing_not_provided",
            },
            "missing_fields": ["market_cap", "enterprise_value"],
        },
        source_ref="market.jsonl",
        source_sha256="b" * 64,
    )

    assert parent["source_type"] == "MARKET_SNAPSHOT"
    assert child["publication_date"] == "2026-06-24"
    assert child["metadata"]["market_snapshot_is_not_valuation"] is True


def test_retired_segment_can_map_to_bounded_semantic_children() -> None:
    alias = {
        "evidence_id": "SUPP::DELL::OLD::CHUNK_0001",
        "ticker": "DELL",
        "source_url": "https://www.sec.gov/example.htm",
        "text": ("orders backlog customer readiness " * 40)
        + ("inventory cash flow payment terms " * 40),
    }
    children = [
        {
            "evidence_id": "CURRENT_DOC::DELL::10_K::1::BLOCK_1",
            "ticker": "DELL",
            "source_url": "https://www.sec.gov/example.htm",
            "text": "orders backlog customer readiness " * 45,
            "metadata": {},
        },
        {
            "evidence_id": "CURRENT_DOC::DELL::10_K::1::BLOCK_2",
            "ticker": "DELL",
            "source_url": "https://www.sec.gov/example.htm",
            "text": "inventory cash flow payment terms " * 45,
            "metadata": {},
        },
    ]

    result = attach_legacy_aliases([alias], children)

    assert result[0]["status"] == "alias_mapped"
    assert result[0]["coverage"] == 1.0
    assert len(result[0]["current_source_record_ids"]) == 2
    assert all(
        child["metadata"]["legacy_source_record_ids"]
        == ["SUPP::DELL::OLD::CHUNK_0001"]
        for child in children
    )


def test_repository_manifest_is_provider_neutral_and_contains_typed_gaps() -> None:
    manifest_path = (
        ROOT
        / "configs"
        / "retrieval"
        / "fin_ia_0_1_3_s1b_current_source_object_manifest_v1_0.json"
    )
    manifest = validate_source_object_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )

    assert {row["input_kind"] for row in manifest["sources"]} == {
        "legacy_candidate_jsonl",
        "legacy_qrel_alias_jsonl",
        "raw_sec_html_capture",
        "market_evidence_jsonl",
    }
    assert {
        row["gap_id"] for row in manifest["typed_gaps"]
    } >= {
        "dell_q1_fy2027_transcript_product_transport_gap",
        "mu_q3_fy2026_prepared_remarks_product_transport_gap",
        "three_case_market_valuation_fields_missing",
    }
