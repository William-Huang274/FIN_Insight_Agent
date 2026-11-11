import asyncio
from io import BytesIO
import json
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from sec_agent.agent_runtime.market_expectations import market_expectations_tool
from sec_agent.research_foundation.public_provider_cache import PublicProviderCache
from sec_agent.research_foundation.expectation_sources import alpha_response
from sec_agent.research_foundation.source_bound_calculator import source_items_from_tool, SourceBoundCalculation, calculate_from_sources
from sec_agent.research_foundation.external_sources import StaticHTTPPageFetcher, ExternalSourceError, FetchedPage
from sec_agent.research_foundation.spreadsheet_sources import spreadsheet_text, spreadsheet_publication_day, XLSX_TYPE
from sec_agent.research_foundation.publication_metadata import extract_publication_metadata
from sec_agent.research_foundation.forecast_originals import read_forecast_original


class Client:
    calls = []
    payload = {'symbol': 'MSFT', 'estimates': [
        {'date': '2027-06-30', 'horizon': 'fiscal year', 'eps_estimate_average': '20.25',
         'eps_estimate_analyst_count': '32', 'eps_estimate_revision_down_trailing_7_days': None},
        {'date': '2026-12-31', 'horizon': 'fiscal quarter', 'eps_estimate_average': '5.1'}]}
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return SimpleNamespace(is_error=False, structured_content=None,
                               content=[SimpleNamespace(type='text', text=json.dumps(self.payload))])


def test_native_call_cache_source_binding_and_review_visibility(tmp_path, monkeypatch):
    monkeypatch.setenv('ALPHAVANTAGE_API_KEY', 'synthetic-test-key')
    Client.calls = []
    a = market_expectations_tool(cache_root=tmp_path, client_factory=Client).tool
    b = market_expectations_tool(cache_root=tmp_path, client_factory=Client).tool
    async def run():
        _, first = await a.coroutine(symbol='MSFT', limit=1)
        text, second = await b.coroutine(symbol='MSFT', offset=1, limit=1)
        assert len(Client.calls) == 1 and second['cache_hit']
        assert 'provider_snapshot' not in json.loads(text)
        assert len(second['provider_snapshot']['estimates']) == 2
        assert first['metadata']['currency'] is None
        assert first['metadata']['forecast_published_at'] is None
        assert 'null' in first['items'][0]['passage']
        sources = source_items_from_tool('read_market_expectations', first)
        sid = next(iter(sources))
        request = SourceBoundCalculation(expression='a*2', operands={'a': {
            'source_id': sid, 'quote': '"eps_estimate_average": "20.25"', 'literal': '20.25'}},
            result_unit='provider currency/share', rationale='Synthetic arithmetic, not a currency assumption.')
        result = calculate_from_sources(request, sources.__getitem__)
        assert result['arithmetic_verified']
        from sec_agent.agent_runtime.answer_review_provider import review_tool_names
        assert 'read_market_expectations' in review_tool_names(['read_market_expectations'])
        assert 'synthetic-test-key' not in json.dumps(first)
    asyncio.run(run())


def test_historical_task_never_requests_current_forecasts(tmp_path):
    def never(): raise AssertionError('no transport')
    t = market_expectations_tool(research_as_of='2000-01-01', cache_root=tmp_path, client_factory=never).tool
    _, result = asyncio.run(t.coroutine(symbol='MSFT'))
    assert result['status'] == 'historical_vintage_unverified' and not result['items']


def test_rate_limit_is_not_empty_consensus_and_stops_repeated_calls(tmp_path):
    calls=[]
    async def fetch():
        calls.append(1)
        return alpha_response(SimpleNamespace(is_error=False, structured_content={
            'Information': 'Please observe requests per second rate limit.'}))
    async def run():
        cache = PublicProviderCache(tmp_path, provider='test', spacing=0)
        first = await cache.get({'symbol':'A'}, fetch)
        second = await cache.get({'symbol':'B'}, fetch)
        assert first['status']=='provider_rate_limited'
        assert second['status']=='provider_cooldown' and len(calls)==1
    asyncio.run(run())


def test_daily_allowance_and_credential_partition(tmp_path):
    async def fetch(): return {'status':'ok','data':{'sample':1}}
    async def run():
        a=PublicProviderCache(tmp_path,provider='test',credential='a',daily_limit=1,spacing=0)
        assert (await a.get({'s':1},fetch))['status']=='ok'
        assert (await a.get({'s':1},fetch))['cache_hit']
        assert (await a.get({'s':2},fetch))['status']=='provider_daily_limit'
        b=PublicProviderCache(tmp_path,provider='test',credential='b',daily_limit=1,spacing=0)
        assert (await b.get({'s':2},fetch))['status']=='ok'
    asyncio.run(run())


def test_concurrent_requests_coalesce_and_failed_payload_is_not_cached(tmp_path):
    calls=[]
    async def fetch():
        calls.append(1)
        await asyncio.sleep(.05)
        return {'status':'ok','data':{'sample':1}}
    async def run():
        a=PublicProviderCache(tmp_path,provider='test',spacing=0)
        b=PublicProviderCache(tmp_path,provider='test',spacing=0)
        values=await asyncio.gather(a.get({'s':1},fetch),b.get({'s':1},fetch))
        assert len(calls)==1 and sum(v['cache_hit'] for v in values)==1
    asyncio.run(run())


@pytest.mark.parametrize('payload', [{'Information':'Premium entitlement required'}, {'Error Message':'Invalid symbol'}])
def test_provider_error_is_not_data(payload):
    assert alpha_response(SimpleNamespace(is_error=False,structured_content=payload))['status']=='provider_error'


def workbook_bytes():
    workbook=Workbook()
    sheet=workbook.active
    sheet.title='Consensus'
    sheet['B3']='Example analyst consensus - 3 November 2026'
    sheet['B5']='GBP million'
    sheet['C5']=2027
    sheet['B6']='Revenue'
    sheet['C6']=100.25
    sheet['C6'].number_format='#,##0.00'
    sheet['D6']='=C6*2'
    stream=BytesIO(); workbook.save(stream)
    return stream.getvalue()


def test_xlsx_native_decode_keeps_coordinates_units_formulas_and_edition():
    page=StaticHTTPPageFetcher._decode(workbook_bytes(),'https://example.com/report.xlsx',200,XLSX_TYPE,2_000_000)
    text=page.extracted_text
    assert page.content_type==XLSX_TYPE
    assert 'C6: 100.25' in text and 'GBP million' in text
    assert '"formula": "=C6*2"' in text and '"cached_result": null' in text
    assert str(spreadsheet_publication_day(text))=='2026-11-03'
    assert spreadsheet_publication_day(text.replace('analyst consensus -','event scheduled for')) is None


def test_xlsx_invalid_binary_is_typed_error():
    with pytest.raises(ExternalSourceError,match='capture_spreadsheet_unreadable'):
        spreadsheet_text(b'not a workbook')


def test_consensus_heading_date_is_not_a_forecast_period_or_related_article():
    html='<html><head><title>Consensus</title></head><body><h1>Consensus</h1><h2>Example analyst consensus - 3 November 2026</h2><table><tr><td>2027 forecasts</td></tr></table></body></html>'
    assert str(extract_publication_metadata(html,url='https://example.com/consensus').version_day)=='2026-11-03'
    assert not extract_publication_metadata(html.replace('<h1>Consensus</h1>','<h1>Events</h1>'),url='https://example.com/consensus').evidence
    assert not extract_publication_metadata(html.replace('<h2>','<article><h2>').replace('</h2>','</h2></article>'),url='https://example.com/consensus').evidence


def test_forecast_original_preserves_source_unit_not_renamed_akshare_field():
    class Fetcher:
        async def fetch(self,url,timeout_seconds):
            return FetchedPage(final_url=url, html='<html><body><article><h1>预测原件</h1><p>本表为各机构当前预测，需按原始财政年度及币种理解，不代表已实现盈利。</p><table><tr><th>财政年度</th><th>每股盈利（分）</th><th>纯利（百万元人民币）</th></tr><tr><td>2027</td><td>2467.45</td><td>223652</td></tr></table><p>公司投资者应核对预测的统计口径与机构样本，原件中的单位保持不变。</p></article></body></html>')
    result=asyncio.run(read_forecast_original('stock_hk_profit_forecast_et',{'symbol':'00700'},fetcher=Fetcher()))
    assert result['status']=='ok'
    assert '每股盈利（分）' in str(result['raw_table_headers'])
    assert '百万元人民币' in result['item']['passage']
    body={'status':'ok','items':[result['item']]}
    assert source_items_from_tool('query_public_data',body)
    assert not source_items_from_tool('query_public_data',{'status':'ok','result':{'rows':[{'EPS':2467.45}]}})


def test_forecast_page_shell_is_not_a_readable_forecast_original():
    class Fetcher:
        async def fetch(self,url,timeout_seconds):
            return FetchedPage(final_url=url, html='<html><body><article><h1>盈利预测</h1><p>'+('免责声明，不构成投资建议。'*30)+'</p></article></body></html>')
    result=asyncio.run(read_forecast_original('stock_profit_forecast_em',{},fetcher=Fetcher()))
    assert result['status']=='original_table_unavailable' and 'item' not in result
