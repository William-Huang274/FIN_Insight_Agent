import asyncio
from datetime import date
import json
from types import SimpleNamespace

from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery, filing_index, publisher_day
from test_web_source_navigation import _reader, _call


def test_filing_day_not_period_end_filters_receipts_before_model_search_and_can_restore():
    url = 'https://www.sec.gov/Archives/edgar/data/100517/000010051726000139/ual-20260630.htm'
    assert filing_index(url).endswith('/0000100517-26-000139-index.htm')

    class Index:
        async def fetch(self, locator, **_):
            assert locator == filing_index(url)
            return SimpleNamespace(final_url=locator, extracted_text='Filing Date 2026-09-03 Accepted 2026-09-03 Period of Report 2026-06-30')

    reader, _, _ = _reader(url=url, published=None)
    reader.discovery = DatedWebDiscovery(reader.discovery, Index())
    search = _call(reader,'search',query='financial results')
    assert search.items == () and not reader.export_navigation()
    assert 'Public source fixture' not in search.model_dump_json()
    reader.discovery.verified[filing_index(url)] = date(2026,7,16)
    result = _call(reader,'search',query='financial results')
    assert result.items[0]['publication_date'] == '2026-07-16'
    assert result.items[0]['preview'] == ''
    assert 'Locator only' not in json.dumps(reader.export_navigation())
    assert _call(reader,'read',document_id=result.items[0]['document_id']).items[0]['writer_citable']


def test_publication_day_does_not_take_provider_header_or_financial_period():
    header = '# Release\nURL: https://example.com/release\nPublished: 2026-05-01\n\n'
    assert publisher_day(header+'Quarter ended March 31, 2026') is None
    assert publisher_day(header+'Period of report\nMarch 31, 2026\nResults') is None
    assert publisher_day(header+'Thursday, June 11, 2026\n') == date(2026,6,11)
    assert publisher_day(header+'Published: June 11, 2026\nUpdated: July 4, 2026\n') == date(2026,7,4)
