import asyncio
from datetime import date

from sec_agent.research_foundation.legislation_discovery import LegislationDiscovery
from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
from sec_agent.research_foundation.external_sources import ExternalSourceError
from test_web_source_navigation import _reader, _call


URL = 'https://www.congress.gov/bill/119th-congress/house-bill/1/text'


class API:
    day = '2026-05-01'
    calls = 0

    async def read(self, identity, *args):
        self.calls += 1
        return {'source_url':'https://api.congress.gov/v3/bill/119/hr/1',
                'bill':{'introducedDate':self.day, 'title':'LATER TITLE MUST NOT LEAK'}}


class NoHTML:
    async def fetch(self, *args, **kwargs):
        raise AssertionError('Congress discovery must not request challenged HTML')


def test_search_returns_usable_api_navigation_without_snippet_or_citable_document():
    reader, _, _ = _reader(url=URL, published=None)
    api = API()
    reader.discovery = DatedWebDiscovery(reader.discovery, NoHTML(), origin_fetcher=NoHTML(),
                                        legislation=LegislationDiscovery(api))
    result = _call(reader, 'search', query='site:congress.gov policy')
    assert not result.items
    attempt = result.execution_receipt.attempts[0]
    nav = attempt['legislation_navigation'][0]
    assert nav['next_calls'][1] == {'tool':'read_legislation','arguments':{'query':URL,'operation':'texts'}}
    assert nav['writer_citable'] is False and nav['full_text_read'] is False
    assert 'LATER TITLE' not in result.model_dump_json()
    _call(reader, 'search', query='site:congress.gov policy again')
    assert api.calls == 1


def test_future_identity_and_api_failure_do_not_admit_source_or_hide_failure():
    api = API()
    api.day = '2027-01-01'
    assert asyncio.run(LegislationDiscovery(api).resolve(URL, date(2026,6,30))) == 'after_cutoff'
    class Failed:
        async def read(self, *args):
            raise ExternalSourceError('congress_api_credential_rejected')
    assert asyncio.run(LegislationDiscovery(Failed()).resolve(URL, date(2026,6,30))) == 'congress_api_credential_rejected'


def test_provider_ignored_site_filter_is_not_successful_retrieval():
    reader, _, _ = _reader(url='https://travel.example.com/summer', published='2026-06-01')
    result = _call(reader, 'search', query='site:congress.gov policy')
    assert not result.items
    attempt = result.execution_receipt.attempts[0]
    assert attempt['returned_hits'] == 1 and attempt['accepted_hits'] == 0
    assert attempt['candidate_filter_counts'] == {'outside_requested_domains':1}
