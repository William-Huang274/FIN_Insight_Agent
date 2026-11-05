import asyncio
from datetime import date, datetime, time
from types import SimpleNamespace

import pytest

from sec_agent.research_foundation.dated_web_discovery import publisher_day
from sec_agent.research_foundation.external_sources import ExternalSourceError, FetchedPage
from sec_agent.research_foundation.publisher_catalogs import CatalogSearch, PublisherCatalog


def request(query, cutoff=date(2026, 9, 30), domains=()):
    return SimpleNamespace(query=query, run_scope=SimpleNamespace(research_as_of=datetime.combine(cutoff,time.min)), include_domains=domains)


class Origin:
    def __init__(self, pages):
        self.pages = pages

    async def fetch(self, url, **kwargs):
        html = self.pages.get(url)
        if html is None:
            raise ExternalSourceError('capture_http_status_403')
        return FetchedPage(final_url=url, html=html)


def test_month_and_stage_select_a_catalog_link_not_a_pinned_document_id():
    url = 'https://data.sca.isr.umich.edu/reports.php?year=2024'
    html = """<h1>2024 Reports</h1><a href="fetchdoc.php?docid=11">April Preliminary Results</a>
      <a href="fetchdoc.php?docid=12">April Final Results</a><a href="fetchdoc.php?docid=13">May Final Results</a>
      <a href="https://unrelated.org/fetchdoc.php?docid=14">April Final Results</a>"""
    def ids(q):
        req = request(q)
        search = CatalogSearch(PublisherCatalog.match(req), Origin({url:html}))
        return [hit.url.split('=')[-1] for hit in asyncio.run(search.search(req))]
    assert ids('Michigan consumer sentiment April 2024 final') == ['12']
    assert ids('密歇根消费者信心 2024年4月 初值') == ['11']
    assert ids('Michigan consumer sentiment April 2024') == ['12', '11']
    assert PublisherCatalog.match(request('Michigan consumer sentiment April 2024',domains=('bls.gov',))) is None


def test_survey_masthead_not_a_data_table_or_a_reporting_period():
    assert publisher_day('May 2024 survey results    June 3, 2024',pdf=True) == date(2024, 6, 3)
    for text in ('May 2024 survey results','May 2024   48.1','June 3, 2024',
                 'Earlier edition: May 2024 survey results    June 3, 2024'):
        assert publisher_day(text,pdf=True) is None


def test_fed_catalog_admits_schedule_and_only_released_results():
    base = 'https://www.federalreserve.gov/newsevents/pressreleases/'
    def row(day, title):
        return f'<div class="row"><time>{day}</time><div class="eventlist__event"><a href="x.htm">{title}</a></div></div>'
    pages = {base+'2022-press.htm':row('02/20/2022','Board begins 2022 Survey of Consumer Finances'),
             base+'2023-press.htm':row('10/18/2023','Board releases results of the 2022 Survey of Consumer Finances')}
    def search(cut):
        req = request('Federal Reserve Survey of Consumer Finances 2022 results released 2023',cut)
        return asyncio.run(CatalogSearch(PublisherCatalog.match(req), Origin(pages)).search(req))
    assert [x.published_at for x in search(date(2023,9,30))] == ['2022-02-20']
    assert [x.published_at for x in search(date(2023,10,18))] == ['2023-10-18','2022-02-20']
    del pages[base+'2023-press.htm']
    with pytest.raises(ExternalSourceError,match='incomplete'):
        search(date(2023,10,18))
