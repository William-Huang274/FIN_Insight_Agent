from __future__ import annotations

import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from sec_agent.research_foundation.external_sources import (
    ExternalSourceCapture, ExternalSourceDiscovery, ExternalSourceError,
    FetchedPage, ProviderHit, PublicURLGuard,
)
from sec_agent.research_foundation.source_document_navigation import (
    SourceDocumentRequest, navigate_source_nodes,
)
from sec_agent.research_foundation.web_source_navigation import WebSourceReader
from test_dell_external_sources import _run_scope, _FakeFetcher, _public_guard


BRANCH = "Q8_COMPETITION_VALUE_POOL"


def _reader(*, url="https://example.com/news", published="2026-08-01", text=None, failure=False):
    class Provider:
        provider_id = "fixture_not_live"

        async def search(self, request):
            return (ProviderHit(title="Public source fixture", url=url,
                                snippet="Locator only", published_at=published),)

    text = text or "Source fixture, not a real financial assertion.\n" * 130
    fetcher = _FakeFetcher(ExternalSourceError("fixture_network_failure") if failure
                           else FetchedPage(final_url=url, extracted_text=text, status_code=200))
    reader = WebSourceReader(discovery=ExternalSourceDiscovery(primary=Provider()),
        capture=ExternalSourceCapture(guard=_public_guard(), static_fetcher=fetcher, hosted_fetcher=fetcher))
    return reader, fetcher, text


def _call(reader, operation, *, scope=None, branch=BRANCH, **selection):
    return asyncio.run(reader(request=SourceDocumentRequest(source_space="web", operation=operation, **selection),
                              branch_id=branch, run_scope=scope or _run_scope(branch)))


def test_web_search_read_paginate_preserve_exact_source_without_numeric_promotion():
    reader, fetcher, text = _reader()
    search = _call(reader, "search", query="peer company results")
    candidate = search.items[0]
    assert not candidate["writer_citable"] and not fetcher.calls
    doc_id = candidate["document_id"]
    read = _call(reader, "read", document_id=doc_id, max_characters=2000)
    row = read.items[0]
    assert row["passage"] == text[:2000] and read.next_offset == 2000
    assert row["content_sha256"] == sha256(row["passage"].encode()).hexdigest()
    assert row["source_locator"]["character_end"] == 2000
    assert row["writer_citable"] and not row["numeric_fact_authority"]
    assert not read.evidence_admission_performed and not row["source_document_completeness_verified"]
    next_page = _call(reader, "read", document_id=doc_id, offset=2000, max_characters=2000)
    assert next_page.items[0]["passage"] == text[2000:4000]
    assert len(fetcher.calls) == 1
    assert next_page.source_snapshot_sha256 == read.source_snapshot_sha256
    with pytest.raises(ValueError, match="offset_out_of_range"):
        _call(reader, "read", document_id=doc_id, offset=len(text))


def test_commercial_landing_page_is_explicitly_not_the_paid_report():
    reader, _, _ = _reader(url="https://www.trendforce.com/research/download/RP260728RU")
    doc_id = _call(reader, "search", query="SSD prices").items[0]["document_id"]
    row = _call(reader, "read", document_id=doc_id).items[0]
    assert row["access_scope"] == "commercial_report_landing_page_only"
    assert "NOT the paid report" in row["authority_note"]


def test_known_future_source_is_rejected_before_capture_and_unknown_date_is_disclosed():
    reader, fetcher, _ = _reader(published="2026-09-03")
    doc_id = _call(reader, "search", query="as of results").items[0]["document_id"]
    with pytest.raises(ValueError, match="publication_after_research_as_of"):
        _call(reader, "read", document_id=doc_id)
    assert not fetcher.calls
    reader, _, _ = _reader(published=None)
    doc_id = _call(reader, "search", query="as of results").items[0]["document_id"]
    assert _call(reader, "read", document_id=doc_id).items[0]["publication_date_status"].startswith("unknown")


def test_failed_fetch_is_not_promoted_to_public_information_gap():
    reader, _, _ = _reader(failure=True)
    doc_id = _call(reader, "search", query="source unavailable").items[0]["document_id"]
    result = _call(reader, "read", document_id=doc_id)
    assert not result.items and "not public non-disclosure" in result.notice
    assert "fixture_network_failure" in result.notice


def test_web_requires_discovery_within_current_run_and_branch():
    reader, fetcher, _ = _reader()
    with pytest.raises(ValueError, match="not_discovered"):
        _call(reader, "read", document_id="WEB::unknown")
    doc_id = _call(reader, "search", query="peer results").items[0]["document_id"]
    with pytest.raises(ValueError, match="not_discovered"):
        _call(reader, "read", document_id=doc_id, branch="Q5_SUPPLY_AND_PRICE")
    with pytest.raises(ValueError, match="scope_invalid"):
        _call(reader, "read", document_id=doc_id, branch="Q5_SUPPLY_AND_PRICE", scope=_run_scope(BRANCH))
    assert not fetcher.calls


@pytest.mark.parametrize("selection", [
    {"operation": "read", "document_id": "https://example.com/raw"},
    {"operation": "read", "document_id": "WEB::a", "page_start": 1},
    {"operation": "read", "document_id": "WEB::a", "node_id": "BLOCK::a"},
    {"operation": "catalog"},
])
def test_web_schema_does_not_accept_paths_raw_urls_or_fabricated_pdf_pages(selection):
    with pytest.raises(ValidationError):
        SourceDocumentRequest(source_space="web", **selection)


def test_default_local_reader_cannot_silently_enable_web():
    request = SourceDocumentRequest(source_space="web", operation="search", query="peer results")
    with pytest.raises(ValueError, match="live_web_source_read_not_enabled"):
        navigate_source_nodes([], request, snapshot="test")
    old = SourceDocumentRequest(operation="read", document_id="DOC::1")
    assert "source_space" not in old.model_dump()
    assert "source_space" not in json.loads(old.model_dump_json())


@pytest.mark.parametrize("url", ["http://127.0.0.1:6696/", "https://10.0.0.1/", "file:///etc/passwd"])
def test_public_network_guard_remains_in_effect(url):
    with pytest.raises(ExternalSourceError):
        PublicURLGuard().validate(url)


@pytest.mark.local_data_integration
def test_real_a5_seed_remains_valid_after_additive_web_request_schema():
    from sec_agent.agent_runtime.dell_workpaper_review_graph import validate_workpaper_state
    path = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260906-dell-q1-agentic-review-repair-a5/specialist-final-state.private.json")
    if not path.is_file():
        pytest.skip("immutable local A5 seed unavailable")
    seed = json.loads(path.read_text(encoding="utf-8"))["values"]["target_state"]
    validate_workpaper_state(seed)


@pytest.mark.local_data_integration
def test_web_reader_uses_existing_real_mcp_source_tool(monkeypatch):
    from test_dell_agent_server_data_composition import DEFAULT_ARTIFACT_ENV, _all_artifacts_available, _execute_evidence
    from sec_agent.agent_runtime.dell_agent_server_data_composition import open_dell_approved_data_composition
    if not _all_artifacts_available():
        pytest.skip("local approved data unavailable")
    reader, fetcher, _ = _reader()
    # Real transport/tool/lane composition, fake only external provider network.
    monkeypatch.setattr("sec_agent.research_foundation.web_source_navigation.WebSourceReader", lambda **kwargs: reader)
    with open_dell_approved_data_composition(run_invocation_id="web-mcp-fixture", environment=DEFAULT_ARTIFACT_ENV,
                                            source_read_enabled=True, live_web_read_enabled=True) as composition:
        assert composition.network_calls_authorized and not composition.paid_calls_authorized
        search = _execute_evidence(composition, label="web-search", request={"source_document": {
            "source_space": "web", "operation": "search", "query": "peer results"}})
        doc_id = next(row["document_id"] for row in search.items if row.get("document_id"))
        read = _execute_evidence(composition, label="web-read", request={"source_document": {
            "source_space": "web", "operation": "read", "document_id": doc_id}})
        assert read.status == "success" and "source_bound_passage" in read.result_states
        assert len(fetcher.calls) == 1


def test_paid_web_permission_is_explicit_and_requires_source_tool(tmp_path):
    from test_dell_specialist_paid_shadow import _authority
    from sec_agent.agent_runtime.dell_specialist_paid_shadow import DellQ1SpecialistPaidShadowAuthority
    from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256
    old = _authority(tmp_path)
    assert not old.live_external_calls_authorized
    body = old.model_dump(mode="json", exclude={"decision_digest"})
    body["live_external_calls_authorized"] = True
    with pytest.raises(ValidationError, match="live_web_requires_source_read"):
        DellQ1SpecialistPaidShadowAuthority.model_validate_json(json.dumps({**body, "decision_digest": canonical_sha256(body)}))
    body["source_read_enabled"] = True
    parsed = DellQ1SpecialistPaidShadowAuthority.model_validate_json(json.dumps({**body, "decision_digest": canonical_sha256(body)}))
    assert parsed.live_external_calls_authorized


@pytest.mark.skipif(not os.environ.get("FINSIGHT_LIVE_WEB_PROBE_OUTPUT"), reason="explicit host-only network probe")
def test_live_exa_mcp_search_and_source_read():
    from test_dell_agent_server_data_composition import DEFAULT_ARTIFACT_ENV, _execute_evidence
    from sec_agent.agent_runtime.dell_agent_server_data_composition import open_dell_approved_data_composition
    output = Path(os.environ["FINSIGHT_LIVE_WEB_PROBE_OUTPUT"])
    output.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        with (output / name).open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)

    request = {"source_document": {"source_space": "web", "operation": "search",
        "query": "HPE fiscal 2026 second quarter June 1 2026 official earnings AI servers", "limit": 4}}
    save("request.json", {"request": request, "model_calls": 0, "purpose": "Host tool qualification, not agent research"})
    with open_dell_approved_data_composition(run_invocation_id=output.name, environment=DEFAULT_ARTIFACT_ENV,
                                            source_read_enabled=True, live_web_read_enabled=True) as composition:
        search = _execute_evidence(composition, label="live-web-search", request=request)
        save("search.json", search.model_dump(mode="json"))
        candidate = next(row for row in search.items if "hpe.com/us/en/newsroom/press-release/2026/06/" in row.get("source_url", ""))
        read = _execute_evidence(composition, label="live-web-read", request={"source_document": {
            "source_space": "web", "operation": "read", "document_id": candidate["document_id"], "max_characters": 24000}})
        save("read.json", read.model_dump(mode="json"))
        assert read.status == "success"
        row = next(row for row in read.items if row.get("result_state") == "source_bound_passage")
        assert len(row["passage"]) > 500 and not row["numeric_fact_authority"]
        assert row["mcp_receipt_chain"] and row["source_url"].startswith("https://www.hpe.com/")
        print(json.dumps({"status": "pass", "url": row["source_url"], "characters": len(row["passage"]),
                          "model_calls": 0, "mcp_source_receipts": len(row["mcp_receipt_chain"])}))
