from __future__ import annotations

import importlib.util
from pathlib import Path

from sec_agent.exact_slot_contracts import build_exact_slot_rows


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_targeted_official_technology_document_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_targeted_official_technology_document_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_official_technology_document_rows_enter_technology_proxy_exact_slot(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(url: str, *, timeout_s: float):
        assert "palantir.com" in url
        return (
            "ok",
            "<html><title>Palantir Foundry</title><body>Palantir Foundry uses an Ontology and AIP data platform.</body></html>",
            "",
        )

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    rows, attempts = MODULE.build_targeted_official_technology_document_rows(
        tickers=["PLTR"],
        generated_at="2026-06-24T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=1,
    )

    assert len(rows) == 1
    assert attempts[0]["status"] == "materialized"
    row = rows[0]
    assert row["ticker"] == "PLTR"
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["underlying_source_id"] == "official_technical_document"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "technology_topic_bound"
    assert row["technical_doc_id"]
    assert "product_sales" in row["forbidden_claims"]

    exact = build_exact_slot_rows(rows, generated_at="2026-06-24T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "technology_research_proxy"


def test_official_technology_document_requires_issuer_and_topic_binding(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(url: str, *, timeout_s: float):
        return "ok", "<html><body>Generic investor relations page without matching technology terms.</body></html>", ""

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    monkeypatch.setattr(MODULE, "_fetch_text_with_browser", fake_fetch)
    rows, attempts = MODULE.build_targeted_official_technology_document_rows(
        tickers=["PLTR"],
        generated_at="2026-06-24T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=1,
    )

    assert rows == []
    assert attempts[0]["status"] == "issuer_or_topic_binding_gap"
