from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from ingestion.section_splitter import find_sec_filing_sections
from scripts.data_retrieval.build_current_retrieval_snapshot import _reviewed_targets
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


def test_successor_manifest_projects_reviewed_dell_transcript_without_hiding_other_gaps() -> None:
    manifest_path = (
        ROOT
        / "configs"
        / "retrieval"
        / "fin_ia_0_1_3_s1b_current_source_object_manifest_v1_1.json"
    )
    manifest = validate_source_object_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )

    transcripts = [
        row
        for row in manifest["sources"]
        if row.get("source_type") == "EARNINGS_CALL_TRANSCRIPT"
    ]
    assert {row["ticker"] for row in transcripts} == {"DELL", "TSM"}
    assert all(
        row["input_kind"] == "parsed_official_pdf_document"
        for row in transcripts
    )
    assert {
        row["ticker"]: row["publication_date"] for row in transcripts
    } == {"DELL": "2026-05-28", "TSM": "2026-07-16"}
    gap_ids = {row["gap_id"] for row in manifest["typed_gaps"]}
    assert "dell_q1_fy2027_transcript_product_transport_gap" not in gap_ids
    assert "tsm_advanced_packaging_current_source_not_captured" not in gap_ids
    assert {
        "mu_q3_fy2026_prepared_remarks_product_transport_gap",
        "three_case_market_valuation_fields_missing",
    }.issubset(gap_ids)


def test_successor_kernel_grants_transcript_route_only_to_relevant_slots() -> None:
    payload = json.loads(
        (
            ROOT
            / "configs"
            / "retrieval"
            / "fin_ia_0_1_3_s1_financial_research_kernel_v1_2.json"
        ).read_text(encoding="utf-8")
    )
    transcript_slots = {
        row["slot_id"]
        for row in payload["evidence_slots"]
        if "EARNINGS_CALL_TRANSCRIPT" in row["source_types"]
    }
    assert transcript_slots == {
        "demand_volume_quality",
        "operating_performance",
        "pricing_mix_value_capture",
        "capacity_inputs_execution",
    }


def test_current_snapshot_reaches_transcript_as_dell_evidence_candidate_only() -> None:
    snapshot = json.loads(
        (
            ROOT
            / "configs"
            / "runtime"
            / "fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert snapshot["status"].endswith("ready_with_typed_gaps")
    cases = {row["case_key"]: row for row in snapshot["cases"]}

    dell_transcript_candidates = []
    for lane in cases["DELL"]["retrieval"]["lane_results"]:
        for candidate in lane["candidates"]:
            if "EARNINGS_CALL_TRANSCRIPT" in str(
                candidate.get("source_record_id") or ""
            ):
                dell_transcript_candidates.append(candidate)
    assert dell_transcript_candidates
    assert any(
        candidate["reviewed_pack_match"] is True
        for candidate in dell_transcript_candidates
    )

    for case_key in ("MU", "NVDA"):
        related_transcript_candidates = []
        for lane in cases[case_key]["retrieval"]["lane_results"]:
            for candidate in lane["candidates"]:
                if "EARNINGS_CALL_TRANSCRIPT" in str(
                    candidate.get("source_record_id") or ""
                ):
                    related_transcript_candidates.append(candidate)
        assert related_transcript_candidates
        assert all(
            candidate["source_role"] == "related_entity_context"
            and candidate["reviewed_pack_match"] is False
            for candidate in related_transcript_candidates
        )


def test_composed_pack_private_root_override_fails_closed_on_escape_or_drift(
    tmp_path: Path,
) -> None:
    kernel = SimpleNamespace(slots=())
    base = tmp_path / "private"
    default_root = base / "default"
    default_root.mkdir(parents=True)

    escape = {
        "pack_artifacts": {
            "DELL": {
                "private_object_root_relative": "../escape",
                "object_key": "pack.json",
                "byte_size": 1,
                "digest": "0" * 64,
            }
        }
    }
    with pytest.raises(ValueError, match="private_object_root_invalid"):
        _reviewed_targets(
            kernel=kernel,
            pack_result=escape,
            pack_object_root=default_root,
            pack_private_root_base=base,
            case_key="DELL",
        )

    object_root = base / "case-root"
    object_root.mkdir()
    pack_path = object_root / "pack.json"
    pack_path.write_text('{"evidence_items": []}', encoding="utf-8")
    drift = {
        "pack_artifacts": {
            "DELL": {
                "private_object_root_relative": "case-root",
                "object_key": "pack.json",
                "byte_size": pack_path.stat().st_size,
                "digest": "0" * 64,
            }
        }
    }
    with pytest.raises(ValueError, match="pack_object_identity_drift"):
        _reviewed_targets(
            kernel=kernel,
            pack_result=drift,
            pack_object_root=default_root,
            pack_private_root_base=base,
            case_key="DELL",
        )
