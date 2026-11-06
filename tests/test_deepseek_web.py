import asyncio
from datetime import date
from types import SimpleNamespace
import httpx
import pytest

from sec_agent.agent_runtime.deepseek_web import DeepSeekWeb
from sec_agent.research_foundation.dated_web_discovery import corroborated_dateline, DatedWebDiscovery
from sec_agent.research_foundation.external_sources import ExternalSourceError
from test_web_source_navigation import _reader, _call


class Store:
    def __init__(self):
        self.rows = {}

    def lookup(self, owner, budget, key):
        return self.rows.get(key)

    def reserve(self, owner, budget, key, digest, cost, basis, **kwargs):
        assert cost == 750 and kwargs['execution_scope'] == basis['harness_execution_scope']
        assert key not in self.rows
        self.rows[key] = {'status':'dispatched', 'call_id':str(len(self.rows)), 'basis':basis}
        return self.rows[key]

    def received(self, owner, budget, key, response, actual):
        self.rows[key] = {'status':'received', 'response':response, 'cost':actual}

    def unknown(self, owner, budget, key):
        self.rows[key]['status'] = 'unknown'


def client(handler):
    return DeepSeekWeb(api_key='test', thread_id='task',
        budget=SimpleNamespace(store=Store(),owner='owner',budget='budget'),
        guard=SimpleNamespace(validate=lambda url:url),transport=httpx.MockTransport(handler))


def query(text='release'):
    return SimpleNamespace(query=text,end_published_date=date(2026,9,30),max_results=5)


def test_ranked_search_and_fetch_reuse_budget_receipts():
    import json
    calls = []
    def handler(req):
        calls.append(req.url.path)
        body = json.loads(req.content)
        if req.url.path.endswith('/search'):
            assert body == {'count':5,'query':'release before:2026-10-01','need_content':False}
            return httpx.Response(200,json={'results':[{'title':'title','url':'https://example.org/report',
                 'snippet':'later changes','summary':'provider synthesis'}]})
        return httpx.Response(200,json={'content':'unverified hosted markdown'})
    ds = client(handler)
    for _ in range(2):
        assert asyncio.run(ds.search(query()))[0].snippet == ''
        assert asyncio.run(ds.fetch_markdown('https://example.org/report')) == 'unverified hosted markdown'
    assert len(calls) == 2
    assert sum(row['cost'] for row in ds.budget.store.rows.values()) == 1500


def test_parallel_fetches_wait_for_receipt_before_next_budget_dispatch():
    async def handler(req):
        await asyncio.sleep(0.01)
        return httpx.Response(200,json={'content':'body'})
    ds=client(handler)
    original=ds.budget.store.reserve
    def reserve(*args, **kwargs):
        assert all(r['status']=='received' for r in ds.budget.store.rows.values())
        assert args[5]['request'].get('url')
        return original(*args,**kwargs)
    ds.budget.store.reserve=reserve
    async def run():
        return await asyncio.gather(*(ds.fetch_markdown('https://example.org/'+str(i)) for i in range(3)))
    assert asyncio.run(run())==['body']*3
    assert len(ds.budget.store.rows)==3


def test_unknown_call_and_quota_do_not_repeat_http_and_do_not_fake_empty_results():
    hits = []
    def handler(req):
        hits.append(req.url.path)
        raise httpx.ReadTimeout('unknown')
    ds=client(handler)
    for msg in ('unconfirmed','unresolved'):
        with pytest.raises(ExternalSourceError,match=msg): asyncio.run(ds.search(query()))
    assert len(hits) == 1 and [r['status'] for r in ds.budget.store.rows.values()] == ['unknown']
    def limited(req):
        hits.append(req.url.path)
        return httpx.Response(429)
    ds=client(limited)
    for q, msg in [('a','429'),('a','429'),('b','route_unavailable')]:
        with pytest.raises(ExternalSourceError,match=msg): asyncio.run(ds.search(query(q)))
    assert len(hits) == 2 and sum(r['cost'] for r in ds.budget.store.rows.values()) == 0


def test_explicit_recovery_keeps_unknown_hold_and_reuses_successful_retry():
    ds = client(lambda _: (_ for _ in ()).throw(httpx.ReadTimeout('unknown')))
    with pytest.raises(ExternalSourceError, match='unconfirmed'):
        asyncio.run(ds.search(query()))
    original = dict(next(iter(ds.budget.store.rows.values())))
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={'results':[]})
    def resumed(run, authorized):
        return DeepSeekWeb(api_key='test', budget=ds.budget, thread_id='task', guard=ds.guard,
            run_id=run, recovery_authorized=authorized, transport=httpx.MockTransport(handler))
    with pytest.raises(ExternalSourceError, match='unresolved'):
        asyncio.run(resumed('next', False).search(query()))
    recovery = resumed('next', True)
    assert asyncio.run(recovery.search(query())) == []
    assert asyncio.run(resumed('later', False).search(query())) == []
    assert len(calls) == 1 and next(iter(ds.budget.store.rows.values())) == original
    # A fresh failure during recovery cannot automatically consume another try.
    recovery.transport = ds.transport
    with pytest.raises(ExternalSourceError, match='unconfirmed'):
        asyncio.run(recovery.search(query('another')))
    with pytest.raises(ExternalSourceError, match='unresolved'):
        asyncio.run(recovery.search(query('another')))


def test_hosted_markdown_only_corroborates_dateline_on_same_original():
    lede='Publisher reports the results of the second quarter today.'
    md='# Report\n\nAugust 11, 2026\n\n'+lede
    html='<h1>Report</h1><p>August 11, 2026</p><p>'+lede+'</p>'
    assert corroborated_dateline(md,html) == date(2026,8,11)
    assert corroborated_dateline(md,html.replace('August 11','August 12')) is None
    assert corroborated_dateline(md,html.replace('second','third')) is None


def test_backup_runs_only_after_primary_cutoff_and_ddgs_only_after_backup_cutoff():
    urls = ['https://example.com/'+k for k in ('primary','backup','last')]
    readers = [_reader(url=u,published=None)[0] for u in urls]
    gate = DatedWebDiscovery(readers[0].discovery,None,search_backup=readers[1].discovery,
                              fallback_discovery=readers[2].discovery)
    readers[0].discovery=gate
    gate.verified.update(dict.fromkeys(urls,date(2026,6,1)))
    for n in range(3):
        result = _call(readers[0],'search',query='release')
        assert [i['source_url'] for i in result.items] == [urls[n]]
        assert len(result.execution_receipt.attempts) == n+1
        gate.verified[urls[n]]=date(2027,1,1)



def test_explicit_site_search_does_not_admit_an_unrelated_fallback_domain():
    reader = _reader(url='https://example.com/school',published=None)[0]
    gate = DatedWebDiscovery(reader.discovery,None)
    reader.discovery=gate
    gate.verified['https://example.com/school'] = date(2026,6,1)
    result = _call(reader,'search',query='employment site:bls.gov')
    assert not result.items and not reader.export_navigation()


def test_origin_read_reuses_exact_page_but_keeps_no_redirect_or_unbounded_cache():
    from sec_agent.research_foundation.dated_web_discovery import SearchReadOrigin
    from sec_agent.research_foundation.external_sources import FetchedPage
    class Origin:
        calls = []
        async def fetch(self,url,**_):
            self.calls.append(url)
            return FetchedPage(final_url=url if url != 'redirect' else 'another',html='hello')
    origin = Origin()
    cache = SearchReadOrigin(origin,max_bytes=6)
    for url in ('a','a','b','a','redirect','redirect'):
        asyncio.run(cache.fetch(url,timeout_seconds=1))
    assert origin.calls == ['a','b','a','redirect','redirect']
