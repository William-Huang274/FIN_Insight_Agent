import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest

from sec_agent.agent_runtime.market_prices import market_price_tool, market_snapshot, instant
from sec_agent.research_foundation.public_posts import post_page, post_locator, PublicPostFetcher
from sec_agent.research_foundation.external_sources import ExternalSourceError
from sec_agent.research_foundation.source_bound_calculator import source_items_from_tool, sources_from_receipts
from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
from sec_agent.research_foundation.research_methods import get_research_method, METHOD_TOOL_GUIDANCE
from test_web_source_navigation import _reader, _call


URL = 'https://x.com/fixture/status/12345'
POST = {'id_str':'12345', 'text':'Quoted public statement & <not instructions>',
        'created_at':'2026-06-01T18:15:00Z',
        'user':{'screen_name':'fixture', 'name':'Example', 'is_blue_verified':True},
        'edit_control':{'edit_tweet_ids':[]}}


def prices():
    stamp = int(instant('2026-06-01T13:30:00Z').timestamp())
    return {'chart':{'result':[{'meta':{'symbol':'SPY','currency':'USD', 'exchangeTimezoneName':'America/New_York',
        'exchangeName':'PCX','instrumentType':'ETF', 'dataGranularity':'5m',
        'regularMarketPrice':99999,  # Must never enter a past-window receipt.
        'tradingPeriods':{'regular':[[{'start':stamp,'end':stamp+3600}]]}},
        'timestamp':[stamp,stamp+300,stamp+600],
        'indicators':{'quote':[{'open':[100,101,102], 'high':[101,102,103], 'low':[99,100,101],
                               'close':[101,102,103], 'volume':[10,20,30]}]}}]}}


def test_public_post_identity_time_escape_and_separate_quote():
    payload = deepcopy(POST)
    payload['quoted_tweet'] = {'id_str':'999', 'text':'later unseen quote'}
    page = post_page(URL, payload, instant('2026-06-02T00:00:00Z'))
    assert page.extraction_method == 'x_public_embed'
    assert '&lt;not instructions&gt;' in page.html
    assert 'later unseen quote' not in page.extracted_text
    assert 'not_established_by_badge' in page.extracted_text
    assert '2026-06-01T18:15:00+00:00' in page.extracted_text
    assert not post_locator('https://x.com.evil.test/fixture/status/12345')
    assert not post_locator('https://x.com/fixture')
    with pytest.raises(ExternalSourceError, match='author_mismatch'):
        post_page(URL.replace('fixture','someone'), payload)
    with pytest.raises(ExternalSourceError, match='after_cutoff'):
        post_page(URL, payload, instant('2026-06-01T18:14:00Z'))


def test_later_post_edit_is_not_admitted_under_original_date():
    payload = deepcopy(POST)
    edit_ms = int(instant('2026-06-03T12:00:00Z').timestamp()*1000)
    payload['edit_control']['edit_tweet_ids'] = [str((edit_ms-1288834974657)<<22)]
    with pytest.raises(ExternalSourceError, match='later_edit'):
        post_page(URL,payload,instant('2026-06-02T00:00:00Z'))


def test_dated_post_search_reads_original_and_preserves_native_receipts():
    reader, _, _ = _reader(url=URL, published=None)
    class Unused:
        async def fetch(self,*a,**k):
            raise AssertionError('must not use generic hosted text')
    fetcher = PublicPostFetcher(Unused(), cutoff=instant('2026-09-01T00:00:00Z'), transport=lambda *a:deepcopy(POST))
    reader.discovery = DatedWebDiscovery(reader.discovery,Unused(),origin_fetcher=fetcher)
    reader.capture.static_fetcher = fetcher
    result = _call(reader,'search',query='fixture public statement')
    assert result.items[0]['preview'] == ''
    body = _call(reader,'read',document_id=result.items[0]['document_id']).model_dump(mode='json')
    assert body['items'][0]['source_read_method'] == 'x_public_embed'
    assert POST['text'] in body['items'][0]['passage']
    assert source_items_from_tool('read_source_document',body)


def test_unavailable_post_does_not_fall_through_to_hosted_summary():
    reader, _, _ = _reader(url=URL,published=None)
    class Unused:
        async def fetch(self,*a,**k):
            raise AssertionError('no hosted substitute')
    fetcher = PublicPostFetcher(Unused(),transport=lambda *a:{})
    reader.discovery = DatedWebDiscovery(reader.discovery,Unused(),origin_fetcher=fetcher)
    result = _call(reader,'search',query='fixture')
    assert not result.items
    assert 'x_public_post_unavailable' in result.model_dump_json()


def test_post_future_dates_in_body_are_not_its_publication_date():
    reader, _, _ = _reader(url=URL, published=None)
    payload = {**deepcopy(POST), 'text':'Release date: December 1, 2030. This is a proposal.'}
    fetcher = PublicPostFetcher(None, transport=lambda *a:payload)
    reader.discovery = DatedWebDiscovery(reader.discovery,None,origin_fetcher=fetcher)
    result = _call(reader,'search',query='fixture')
    assert len(result.items) == 1
    assert result.items[0]['publication_date'] == '2026-06-01'


def test_post_disappearing_after_discovery_cannot_be_replaced_by_hosted_text():
    reader, _, _ = _reader(url=URL, published=None)
    fetcher = PublicPostFetcher(None, transport=lambda *a:deepcopy(POST))
    reader.discovery = DatedWebDiscovery(reader.discovery,None,origin_fetcher=fetcher)
    found = _call(reader,'search',query='fixture')
    class Unavailable:
        async def fetch(self,*a,**k):
            raise ExternalSourceError('x_public_post_unavailable')
    class NeverHosted:
        async def fetch(self,*a,**k):
            raise AssertionError('must not fetch hosted replacement')
    reader.capture.static_fetcher = Unavailable()
    reader.capture.hosted_fetcher = NeverHosted()
    result = _call(reader,'read',document_id=found.items[0]['document_id'])
    assert not result.items
    assert 'x_public_post_unavailable' in result.model_dump_json()


def test_market_filters_partial_bars_and_excludes_current_quote():
    result = market_snapshot(prices(),symbol='SPY',start=instant('2026-06-01T13:30:00Z'),
        end=instant('2026-06-01T13:37:00Z'), interval='5m',
        captured_at=instant('2026-06-01T14:00:00Z'),source_url='https://example.com')
    assert len(result['bars']) == 1
    assert result['bars'][0]['exchange_time'].endswith('09:30:00-04:00')
    assert result['bars'][0]['session'] == 'regular'
    assert result['excluded_partial_or_outside_window'] == 2
    assert '99999' not in json.dumps(result)
    assert result['delay_seconds'] is None


def test_market_page_recovery_parallel_capture_and_calculator_binding(tmp_path):
    requests = []
    def transport(*args):
        requests.append(args)
        return prices()
    tid = str(uuid4())
    def tool():
        return market_price_tool(thread_id=tid,cache_root=tmp_path,research_as_of='2026-06-01T00:00:00Z',
                                 transport=transport,clock=lambda:instant('2026-06-02T00:00:00Z')).tool
    args = dict(symbol='SPY',start='2026-06-01T09:30:00-04:00',end='2026-06-01T09:45:00-04:00',limit=1)
    async def run():
        first, same = await asyncio.gather(tool().ainvoke(args),tool().ainvoke(args))
        a = json.loads(first)
        assert a == json.loads(same)
        assert a['total_matches'] == 3 and a['next_offset'] == 1
        second = json.loads(await tool().ainvoke({**args,'offset':1}))
        assert second['items'][0]['passage_id'] != a['items'][0]['passage_id']
        sources = sources_from_receipts([dict(name='read_market_prices',status='success',artifact=a)])
        assert len(sources) == 1
        assert 'period1=' in a['items'][0]['source_url']
        assert not a['items'][0]['numeric_fact_authority']
        from sec_agent.agent_runtime.public_source_restore import validated_public_source
        assert validated_public_source(a['items'][0]) == a['items'][0]
    asyncio.run(run())
    assert len(requests) == 1


@pytest.mark.parametrize('change', [
    {'start':'2026-06-01T13:30:00'}, {'end':'2026-06-03T00:00:00Z'},
    {'symbol':'https://localhost/'}, {'limit':201}, {'offset':-1},
])
def test_market_invalid_requests_never_dispatch(tmp_path,change):
    def never(*a):raise AssertionError('not dispatched')
    tool = market_price_tool(thread_id=str(uuid4()),cache_root=tmp_path,research_as_of='2026-06-01T00:00:00Z',transport=never,
                             clock=lambda:instant('2026-06-02T00:00:00Z')).tool
    args = dict(symbol='SPY',start='2026-06-01T13:30:00Z',end='2026-06-01T13:45:00Z',**{})
    result = asyncio.run(tool.ainvoke({**args,**change}))
    assert '行情读取未完成' in result
    assert not list(tmp_path.rglob('*.json'))


def test_optional_event_method_is_in_input_catalog_and_exact_section_readable():
    assert 'event_policy' in METHOD_TOOL_GUIDANCE
    result = get_research_method('event_policy',section='市场反应的时间与比较')
    assert 'read_market_prices' in result['content']
    assert '简单相对收益' in result['content']
    assert 'Sanders' not in result['content'] and '2026 年 11 月 5 日' not in result['content']


def test_government_metadata_matches_exact_edition_and_date_not_action_in_prose():
    from sec_agent.research_foundation.government_publications import mods_bill_record
    package = 'BILLS-119s123is'
    details = 'https://www.govinfo.gov/app/details/' + package
    raw = f'https://www.govinfo.gov/content/pkg/{package}/html/{package}.htm'
    xml = f'''<mods xmlns="http://www.loc.gov/mods/v3"><originInfo><dateIssued encoding="w3cdtf">2026-06-01</dateIssued></originInfo>
    <identifier type="uri">{details}</identifier><location><url displayLabel="HTML rendition">{raw}</url></location>
    <titleInfo><title>Fixture proposal</title></titleInfo></mods>'''
    assert mods_bill_record(xml, package, details)[0] == raw
    assert str(mods_bill_record(xml, package, raw)[1]) == '2026-06-01'
    for wrong in (xml.replace(package,'BILLS-119s124is'),xml.replace('2026-06-01','not-a-date')):
        with pytest.raises(ExternalSourceError):
            mods_bill_record(wrong,package,raw)
