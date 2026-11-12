import asyncio
from datetime import date

import pytest

from sec_agent.research_foundation.external_sources import FetchedPage, ExternalSourceError
from sec_agent.research_foundation.public_origin import PublicOriginFetcher, observed_navigation
from sec_agent.research_foundation.dated_web_discovery import publisher_html_day

URL = 'https://example.org/product'


class Fetch:
    def __init__(self, value):
        self.value, self.calls = value, 0

    async def fetch(self, *args, **kwargs):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def run(static, browser):
    return asyncio.run(PublicOriginFetcher(static, browser).fetch(URL, timeout_seconds=3))


def test_script_shell_uses_browser_and_preserves_original_failure():
    s = Fetch(FetchedPage(final_url=URL, html='<div id="app"></div><script src="app.js"></script>'))
    b = Fetch(FetchedPage(final_url=URL, html='<main>'+('actual product terms '*70)+'</main>', extraction_method='playwright_browser'))
    result = run(s, b)
    assert result.extraction_method == 'playwright_browser'
    assert result.origin_failure_code == 'capture_dynamic_shell'
    assert b.calls == 1


def test_short_static_document_not_forced_into_browser():
    s = Fetch(FetchedPage(final_url=URL, html='<h1>Short notice</h1><p>Published November 1, 2026.</p>'))
    b = Fetch(AssertionError('unnecessary browser'))
    assert run(s, b) == s.value
    assert b.calls == 0


@pytest.mark.parametrize('code', ['capture_http_status_429', 'capture_url_invalid_or_forbidden'])
def test_rate_limit_and_policy_failure_not_retried_in_browser(code):
    s, b = Fetch(ExternalSourceError(code)), Fetch(None)
    with pytest.raises(ExternalSourceError, match=code): run(s, b)
    assert b.calls == 0


def test_browser_failure_not_relabelled_as_missing_date():
    s = Fetch(ExternalSourceError('capture_http_status_403'))
    b = Fetch(ExternalSourceError('capture_access_challenge'))
    with pytest.raises(ExternalSourceError, match='capture_http_status_403;browser:capture_access_challenge'):
        run(s, b)
    assert b.calls == 1


def test_browser_still_empty_is_failure():
    p = FetchedPage(final_url=URL, html='<script src="app.js"></script><div>Loading</div>')
    with pytest.raises(ExternalSourceError, match='capture_browser_content_incomplete'):
        run(Fetch(p), Fetch(p))


def test_navigation_keeps_identity_without_undated_titles_or_inherited_dates():
    links = observed_navigation('<a href="/docs?version=2">2027 unreleased secret</a><a href="javascript:alert(1)">x</a><a href="https://u:p@example.org/">bad</a>', URL)
    assert len(links) == 1
    assert links[0]['url'] == 'https://example.org/docs?version=2'
    assert not links[0]['publication_date_inherited']
    assert 'secret' not in str(links)


def test_explicit_document_update_date_and_negative_body_date():
    html = '<html><head></head><body><h1>Billing</h1><p>Effective January 1, 2027</p><div class="updateTime-abc">更新时间: <time datetime="2026-10-24T10:12:37.273Z">2026-10-24 10:12</time></div></body></html>'
    assert publisher_html_day(html, url=URL) == date(2026,10,24)
    assert publisher_html_day(html.replace('updateTime-abc','event-date'), url=URL) is None
    assert publisher_html_day(html.replace('<div class=', '<blockquote><div class=').replace('</div>','</div></blockquote>'), url=URL) is None


def test_runtime_constructs_browser_route(monkeypatch, tmp_path):
    from uuid import uuid4
    from sec_agent.agent_runtime.conversation_web import public_web_tool
    import sec_agent.research_foundation.public_origin as origin
    seen = []
    class Wrapper:
        def __init__(self, static, browser): seen.append((static,browser))
    monkeypatch.setattr(origin,'PublicOriginFetcher',Wrapper)
    public_web_tool(thread_id=str(uuid4()),run_id=str(uuid4()),method_digest='0'*64,
                    cache_root=tmp_path,research_as_of='2026-11-12T00:00:00Z')
    assert len(seen) == 1
    assert type(seen[0][1]).__name__ == 'PlaywrightPageFetcher'


def test_undated_navigation_returned_even_when_hosted_date_lookup_fails():
    from test_web_source_navigation import _reader, _call
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    reader, _, _ = _reader(url=URL, published=None)
    origin = Fetch(FetchedPage(final_url=URL, html='<h1>Pricing</h1><a href="/docs/billing">Future price title</a>'))
    hosted = Fetch(ExternalSourceError('exa_skipped_after_task_limit'))
    reader.discovery = DatedWebDiscovery(reader.discovery, hosted, origin_fetcher=origin)
    result = _call(reader, 'search', query='product official pricing')
    assert not result.items
    body = result.model_dump_json()
    assert 'https://example.org/docs/billing' in body
    assert 'Future price title' not in body
    assert 'exa_skipped_after_task_limit' in body


def test_future_document_does_not_leak_navigation():
    from test_web_source_navigation import _reader, _call
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    reader, _, _ = _reader(url=URL, published=None)
    html = '<html><head><meta name="dateModified" content="2099-01-01"></head><body><h1>Future</h1><a href="/secret-future">Future pricing</a></body></html>'
    reader.discovery = DatedWebDiscovery(reader.discovery, None, origin_fetcher=Fetch(FetchedPage(final_url=URL,html=html)))
    result = _call(reader, 'search', query='product official pricing')
    assert not result.items
    assert 'secret-future' not in result.model_dump_json()


@pytest.mark.parametrize('locale,region', [('zh-CN','cn-zh'),('ja-JP','jp-jp'),('ko-KR','kr-kr'),(None,'wt-wt')])
def test_ddgs_receives_requested_locale_not_implicit_us(monkeypatch, locale, region):
    from ddgs.ddgs import DDGS
    from types import SimpleNamespace
    from sec_agent.research_foundation.external_sources import DDGSDiagnosticProvider
    calls = []
    def search(self, query, **kw):
        calls.append(kw)
        return []
    monkeypatch.setattr(DDGS, 'text', search)
    DDGSDiagnosticProvider()._search_sync(SimpleNamespace(query='产品定价',search_language=locale,max_results=5),{})
    assert calls[0]['region'] == region
