import asyncio
from types import SimpleNamespace

import httpx
import pytest

from sec_agent.research_foundation.external_sources import ExternalSourceError, _engine_http
from sec_agent.research_foundation.regional_search import SearxNGProvider, SelectedSearchDiscovery


def request(backend='bing_china'):
    return SimpleNamespace(query='WorkBuddy 腾讯', search_backend=backend,
                           search_language='zh-CN', max_results=5)


def test_selected_engine_locale_and_ad_identity():
    def reply(r):
        assert r.url.params['engines'] == 'bing china'
        assert r.url.params['language'] == 'zh-CN'
        assert 'categories' not in r.url.params  # would add all engines in that category
        return httpx.Response(200, json={'results': [
            {'title': 'official', 'url': 'https://www.workbuddy.cn/', 'engines': ['bing china'], 'publishedDate': '2020-01-01'},
            {'title': 'wrong engine', 'url': 'https://example.com/', 'engines': ['baidu']},
            {'title': 'ad', 'url': 'https://ads.example.com/', 'engines': ['bing china'], 'is_ad': True},
        ]})
    hits = asyncio.run(SearxNGProvider('http://localhost:8080', transport=httpx.MockTransport(reply)).search(request()))
    assert len(hits) == 1 and hits[0].published_at is None


def test_captcha_is_fault_not_absence():
    observed = {}
    token = _engine_http.set(observed)
    try:
        provider = SearxNGProvider('http://localhost:8080', transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={'results': [], 'unresponsive_engines': [['baidu', 'CAPTCHA']]})))
        with pytest.raises(ExternalSourceError, match='searxng_engines_unavailable'):
            asyncio.run(provider.search(request('baidu')))
        assert observed == {'searxng:baidu': 'CAPTCHA'}
    finally:
        _engine_http.reset(token)


def test_site_ignored_by_upstream_is_feedback_not_successful_empty():
    r = request()
    r.query = 'site:imda.gov.sg generative AI'
    provider = SearxNGProvider('http://localhost:8080', transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={'results': [
            {'title': 'AI dictionary', 'url': 'https://dictionary.example/ai', 'engines': ['bing china']}]})))
    with pytest.raises(ExternalSourceError, match='searxng_site_constraint_ignored'):
        asyncio.run(provider.search(r))


@pytest.mark.parametrize('code', [403, 429, 502])
def test_http_errors_preserved(code):
    provider = SearxNGProvider('http://localhost:8080', transport=httpx.MockTransport(lambda r: httpx.Response(code)))
    with pytest.raises(ExternalSourceError, match=f'searxng_http_{code}'):
        asyncio.run(provider.search(request()))


def test_explicit_selection_does_not_call_paid_default():
    class Never:
        async def search(self, r):
            pytest.fail('selected engine must not call default')
    class Regional:
        async def search(self, r):
            return r.search_backend
    assert asyncio.run(SelectedSearchDiscovery(Never(), Regional()).search(request())) == 'bing_china'


def test_legacy_request_digests_do_not_gain_default_fields():
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    old = SourceDocumentRequest(source_space='web', operation='search', query='test')
    assert 'search_backend' not in old.model_dump()
    assert 'search_language' not in old.model_dump()
    with pytest.raises(ValueError, match='require_web_discovery'):
        SourceDocumentRequest(source_space='local', operation='search', query='test', search_backend='bing')


def test_dated_explicit_engine_never_falls_through_to_paid_search():
    from datetime import datetime, timezone
    from sec_agent.research_foundation.contracts import bind_research_method, load_research_graph_foundation
    from sec_agent.research_foundation.external_sources import ExternalSourceDiscovery, ExternalSearchRequest
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    scope = bind_research_method(load_research_graph_foundation(), ('Q1_ISSUER_TRUTH',),
        research_as_of=datetime(2026, 9, 2, tzinfo=timezone.utc),
        data_snapshot_id='test', execution_attempt_id='test').run_scope
    class Never:
        async def search(self, r): raise AssertionError('must not call another engine')
    class Empty:
        provider_id = 'searxng'
        async def search(self, r): return ()
    gate = DatedWebDiscovery(Never(), None, search_backup=Never(), fallback_discovery=Never(),
                            regional_discovery=ExternalSourceDiscovery(primary=Empty()))
    r = ExternalSearchRequest(query='test', branch_id='Q1_ISSUER_TRUTH', run_scope=scope,
                              purpose='test regional discovery', search_backend='bing')
    receipt = asyncio.run(gate.search(r))
    assert not receipt.candidates
    assert [a.provider_id for a in receipt.attempted_providers] == ['searxng']


def test_disabled_selected_engine_never_contacts_upstream(monkeypatch):
    monkeypatch.setenv('FIN_SEARCH_DISABLED_BACKENDS', 'bing,bing_china')
    provider = SearxNGProvider('http://localhost:8080', transport=httpx.MockTransport(
        lambda r: pytest.fail('unhealthy engine must not be retried')))
    for backend in ('auto', 'bing', 'bing_china'):
        with pytest.raises(ExternalSourceError, match='selected_engines_disabled'):
            asyncio.run(provider.search(request(backend)))


def test_partial_disable_retains_other_auto_engine(monkeypatch):
    monkeypatch.setenv('FIN_SEARCH_DISABLED_BACKENDS', 'bing')
    def reply(r):
        assert r.url.params['engines'] == 'bing china'
        return httpx.Response(200, json={'results': []})
    provider = SearxNGProvider('http://localhost:8080', transport=httpx.MockTransport(reply))
    assert asyncio.run(provider.search(request('auto'))) == ()


def test_search_health_disclosed_at_entrance_and_catalog(monkeypatch):
    from sec_agent.agent_runtime.source_toolkit import source_tool_guidance, source_catalog
    monkeypatch.setenv('FIN_SEARCH_DISABLED_BACKENDS', 'bing,bing_china')
    monkeypatch.setenv('FIN_SEARCH_DISABLED_REASON', 'query_constraints_ignored')
    assert 'query_constraints_ignored' in source_tool_guidance(['read_public_source'])
    result = asyncio.run(source_catalog([]).tool.ainvoke({'tool_name': 'read_public_source'}))
    assert 'bing_china' in result and 'query_constraints_ignored' in result


def test_disabled_feedback_exposes_actual_alternative(monkeypatch):
    from sec_agent.agent_runtime.conversation_web import web_read_feedback
    monkeypatch.setenv('FIN_SEARCH_DISABLED_BACKENDS', 'bing,bing_china')
    notes = web_read_feedback({'items': [], 'execution_receipt': {'attempts': [
        {'failure_code': 'searxng_selected_engines_disabled_use_auto_or_other_backend'}]}})
    note = next(n for n in notes if n['kind'] == 'disabled_search_backend')
    assert note['alternative']['arguments']['search_backend'] == 'auto'
    assert note['disabled_backends'] == ['bing', 'bing_china']
