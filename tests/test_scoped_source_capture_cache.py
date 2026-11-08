import asyncio
from uuid import uuid4

import pytest


from sec_agent.research_foundation.source_capture_cache import ScopedSourceCaptureCache
from sec_agent.research_foundation.external_sources import (
    ExternalCaptureRequest, ExternalSearchRequest, ExternalSourceDiscovery,
    ExternalSourceCapture, ExternalSourceError, FetchedPage,
)
from test_external_sources import _run_scope, _FakeFetcher, _public_guard, _SingleURLProvider

BRANCH = "Q8_COMPETITION_VALUE_POOL"


def test_full_capture_does_not_reuse_old_prefix_and_reuses_full_text_on_resume(tmp_path):
    text = 'Original text. ' * 20000 + 'Late cash flow table.'
    fetcher = _FakeFetcher(FetchedPage(final_url='https://example.com/annual', extracted_text=text))
    tid = str(uuid4())
    cache = service(tmp_path, tid, fetcher)
    old = asyncio.run(cache.capture(request().model_copy(update={'max_characters':200000})))
    full = asyncio.run(cache.capture(request().model_copy(update={'max_characters':None})))
    resumed = asyncio.run(service(tmp_path, tid, fetcher).capture(request('A2').model_copy(update={'max_characters':None})))
    assert old.truncated and len(old.text) == 200000
    assert not full.truncated and full.text.endswith('Late cash flow table.')
    assert resumed.text == full.text and resumed.text_digest == old.text_digest == full.text_digest
    assert len(fetcher.calls) == 2 and full.text.startswith(old.text)


def request(attempt="A1"):
    from sec_agent.research_foundation.contracts import bind_research_method, load_research_graph_foundation
    base = _run_scope(BRANCH)
    scope = bind_research_method(load_research_graph_foundation(), (BRANCH,),
        research_as_of=base.research_as_of, data_snapshot_id=base.data_snapshot_id,
        execution_attempt_id=attempt).run_scope
    discovery = asyncio.run(ExternalSourceDiscovery(primary=_SingleURLProvider("https://example.com/annual")).search(
        ExternalSearchRequest(query="annual source", branch_id=BRANCH, run_scope=scope, purpose="test source reuse")))
    return ExternalCaptureRequest(discovery_receipt=discovery, candidate_id=discovery.candidates[0].candidate_id,
                                  branch_id=BRANCH, run_scope=scope, render_policy="static")


def service(tmp_path, thread_id, fetcher):
    guard = _public_guard()
    return ScopedSourceCaptureCache(root=tmp_path, thread_id=thread_id, guard=guard,
        capture=ExternalSourceCapture(guard=guard, static_fetcher=fetcher))


def test_reopen_cache_rebinds_attempt_without_changing_capture_provenance(tmp_path):
    fetcher = _FakeFetcher(FetchedPage(final_url="https://example.com/annual", extracted_text="source data " * 100))
    thread_id = str(uuid4())
    first = asyncio.run(service(tmp_path, thread_id, fetcher).capture(request()))
    second = asyncio.run(service(tmp_path, thread_id, fetcher).capture(request("A2")))
    assert len(fetcher.calls) == 1
    assert second.execution_attempt_id == "A2"
    assert second.receipt_digest != first.receipt_digest
    assert second.text == first.text and second.text_digest == first.text_digest
    assert second.captured_at == first.captured_at
    assert second.capture_method == "cached_public_source_replay"
    assert not second.archive_grade and second.admission_required_before_citation
    assert second.attempts[:-1] == first.attempts


def test_other_thread_and_explicit_refresh_cannot_reuse_previous_capture(tmp_path):
    fetcher = _FakeFetcher(FetchedPage(final_url="https://example.com/annual", extracted_text="source data " * 100))
    a = service(tmp_path, str(uuid4()), fetcher)
    asyncio.run(a.capture(request()))
    asyncio.run(service(tmp_path, str(uuid4()), fetcher).capture(request()))
    asyncio.run(a.capture(request(), force_refresh=True))
    assert len(fetcher.calls) == 3


def test_failure_is_not_cached_and_namespace_cannot_escape(tmp_path):
    fetcher = _FakeFetcher(ExternalSourceError("network_failed"))
    cache = service(tmp_path, str(uuid4()), fetcher)
    for _ in range(2):
        assert asyncio.run(cache.capture(request())).status == "tool_failure"
    assert len(fetcher.calls) == 2
    with pytest.raises(ValueError):
        service(tmp_path, "../../elsewhere", fetcher)


def test_cache_hit_still_checks_dns_policy(tmp_path):
    fetcher = _FakeFetcher(FetchedPage(final_url="https://example.com/annual", extracted_text="source data " * 100))
    cache = service(tmp_path, str(uuid4()), fetcher)
    asyncio.run(cache.capture(request()))
    from sec_agent.research_foundation.external_sources import PublicURLGuard
    cache.guard = PublicURLGuard(resolver=lambda host: ["127.0.0.1"])
    with pytest.raises(ExternalSourceError):
        asyncio.run(cache.capture(request()))
    assert len(fetcher.calls) == 1
