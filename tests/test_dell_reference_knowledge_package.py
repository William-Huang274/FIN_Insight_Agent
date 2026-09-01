from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from ingestion.official_source_capture import _TransportResponse
from scripts.data_retrieval.build_dell_reference_knowledge_package import (
    _parse,
    build_package,
    load_plan,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_PLAN = ROOT / "configs/research/fin_ia_0_1_3_dell_reference_knowledge_package_v1_0.json"
E0_PLAN = (
    ROOT
    / "configs/research/fin_ia_0_1_3_dell_reference_knowledge_package_e0_v1_0.json"
)
FOUNDATION = (
    ROOT
    / "configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)


def test_real_plan_is_bounded_official_narrative_only() -> None:
    plan = load_plan(REAL_PLAN)
    sources = plan["capture_plan"]["sources"]
    assert len(sources) == 19
    assert len(sources) <= 20
    assert sum(source["byte_ceiling"] for source in sources) <= 52_000_000
    assert all(source["numeric_authority"] is False for source in sources)
    assert all(source["stable_url"] == source["url"] for source in sources)
    assert not any(source.get("event_id") for source in sources)


def test_e0_plan_is_exactly_five_official_candidate_documents() -> None:
    plan = load_plan(E0_PLAN)
    sources = plan["capture_plan"]["sources"]
    assert len(sources) == plan["limits"]["max_sources"] == 5
    assert sum(source["byte_ceiling"] for source in sources) <= 8_000_000
    assert all(source["numeric_authority"] is False for source in sources)
    assert all(source["stable_url"] == source["url"] for source in sources)
    assert {
        source["route_id"] for source in sources
    } == {
        "dell_fy2027_q2_sec_exhibit_99_1",
        "hpe_fy2026_q2_earnings_transcript",
        "meta_2026_q2_sec_exhibit_99_1",
        "meta_2026_q2_earnings_call_transcript",
        "hpe_fy2026_q2_earnings_press_release",
    }
    event_sources = [source for source in sources if source.get("event_id")]
    assert [source["event_id"] for source in event_sources] == ["DELL_FY2027_Q2"]
    assert plan["foundation_lifecycle_gate"]["expected_foundation_sha256"] == (
        hashlib.sha256(FOUNDATION.read_bytes()).hexdigest()
    )


def test_event_source_requires_foundation_lifecycle_gate(tmp_path: Path) -> None:
    payload = json.loads(E0_PLAN.read_text(encoding="utf-8"))
    payload.pop("foundation_lifecycle_gate")
    path = tmp_path / "event-plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="knowledge_event_lifecycle_gate_missing"):
        load_plan(path)


def test_event_source_rejects_disallowed_foundation_state(tmp_path: Path) -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    foundation["case_identity"]["current_snapshot_state"] = (
        "FY2027_Q2_PRE_EVENT_NOT_CAPTURED"
    )
    foundation_path = tmp_path / "foundation.json"
    foundation_path.write_text(json.dumps(foundation), encoding="utf-8")

    payload = json.loads(E0_PLAN.read_text(encoding="utf-8"))
    payload["foundation_lifecycle_gate"]["foundation_contract_path"] = str(
        foundation_path
    )
    payload["foundation_lifecycle_gate"]["expected_foundation_sha256"] = (
        hashlib.sha256(foundation_path.read_bytes()).hexdigest()
    )
    plan_path = tmp_path / "event-plan.json"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="knowledge_event_lifecycle_state_invalid"):
        load_plan(plan_path)


def _fake_plan(path: Path) -> None:
    def source(route: str, kind: str) -> dict:
        content_type = "text/html" if kind == "html" else "application/pdf"
        return {
            "route_id": route, "case_key": "CASE", "title": route,
            "publisher": "Official Publisher", "publication_date": "2026-01-01",
            "source_role": "issuer_management_disclosure", "document_kind": kind,
            "branches": ["Q1_ISSUER_TRUTH"], "numeric_authority": False,
            "url": f"https://official.example/{route}",
            "stable_url": f"https://official.example/{route}",
            "allowed_hosts": ["official.example"],
            "expected_content_types": [content_type], "byte_ceiling": 100_000,
            "timeout_seconds": 5, "transport": "requests", "max_transport_retries": 0,
        }

    payload = {
        "schema_version": "fin_ia_dell_reference_knowledge_package_plan_v1_0",
        "status": "qualification_input_not_evidence", "case_id": "CASE",
        "as_of": "2026-09-02T00:00:00+08:00",
        "limits": {"max_sources": 20, "max_total_declared_bytes": 200_000,
                   "min_document_chars": 100, "chunk_size_chars": 180,
                   "chunk_overlap_chars": 20},
        "processing_policy": {
            "html_parser": "trafilatura_2_2_0",
            "pdf_parser": "pypdf_born_digital_text_only",
            "splitter": "langchain_recursive_character_text_splitter_1_1_2",
            "numeric_authority": False, "search_snippets_admitted": False,
            "model_calls": 0,
        },
        "capture_plan": {
            "schema_version": "fin_ia_official_source_capture_plan_v1_0",
            "status": "official_source_capture_plan",
            "policy": {"capture_before_parse": True, "https_only": True,
                       "credentials_forbidden": True},
            "sources": [source("html_ok", "html"), source("pdf_empty", "pdf")],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_package_uses_capture_cas_and_preserves_parser_failure(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    _fake_plan(plan_path)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf = io.BytesIO()
    writer.write(pdf)
    html = ("<html><body><article><h1>Official release</h1><p>" +
            "Primary-source narrative context. " * 20 + "</p></article></body></html>").encode()

    def fetch(source: dict) -> _TransportResponse:
        is_pdf = source["document_kind"] == "pdf"
        return _TransportResponse(
            status_code=200, final_url=source["url"],
            headers={"content-type": "application/pdf" if is_pdf else "text/html"},
            redirect_chain=(), body=pdf.getvalue() if is_pdf else html,
            transport_attempts=1,
        )

    result = build_package(
        plan_path, tmp_path / "out", "attempt-1",
        transport_fetchers={"requests": fetch},
    )
    root = tmp_path / "out" / "attempt-1"
    assert result["status"] == "partial"
    assert result["parsed_source_count"] == 1
    assert result["failed_source_count"] == 1
    assert result["chunk_count"] >= 2
    assert (root / "objects" / "raw").is_dir()
    assert (root / "raw_bodies" / "sha256").is_dir()
    rows = {row["route_id"]: row for row in result["sources"]}
    assert rows["html_ok"]["status"] == "parsed"
    assert rows["pdf_empty"]["status"] == "typed_failure"
    assert rows["pdf_empty"]["failure_code"].startswith("body_parse_failure:")
    chunks = [json.loads(line) for line in (root / "chunks.jsonl").read_text().splitlines()]
    assert all(row["numeric_authority"] is False for row in chunks)
    assert all(row["stable_url"].startswith("https://official.example/") for row in chunks)
    assert result["model_calls"] == 0


def test_plan_rejects_numeric_authority(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    _fake_plan(path)
    payload = json.loads(path.read_text())
    payload["capture_plan"]["sources"][0]["numeric_authority"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        load_plan(path)
    except ValueError as exc:
        assert str(exc) == "knowledge_source_contract_invalid"
    else:
        raise AssertionError("numeric authority must be rejected")


def test_html_parser_uses_generic_beautifulsoup_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "scripts.data_retrieval.build_dell_reference_knowledge_package."
        "trafilatura.extract",
        lambda *_args, **_kwargs: None,
    )
    body = (
        b"<DOCUMENT><TYPE>EX-99.1<TEXT><html><body>"
        b"<div><font>Second-Quarter Summary</font></div>"
        + (b"<div><font>Official issuer disclosure.</font></div>" * 12)
        + b"</body></html></TEXT></DOCUMENT>"
    )

    units = _parse(body, "html")

    assert len(units) == 1
    assert "Second-Quarter Summary" in units[0][1]
    assert "Official issuer disclosure." in units[0][1]
