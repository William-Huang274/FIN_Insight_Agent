import asyncio
from datetime import date
import json
from types import SimpleNamespace

from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery, filing_index, publisher_day
from test_web_source_navigation import _reader, _call


def test_article_microdata_dates_require_exact_page_and_nearest_scope():
    from sec_agent.research_foundation.dated_web_discovery import publisher_html_day
    url='https://publisher.example/news/story'
    html=('<article itemscope itemtype="https://schema.org/Article">'
          '<link itemprop="mainEntityOfPage" href="'+url+'"><h1 itemprop="headline">Story</h1>'
          '<header><meta itemprop="datePublished" content="2026-11-05T16:04:08-06:00">'
          '<meta itemprop="dateModified" content="2026-11-06T08:00:00-06:00"></header>'
          '<aside itemscope itemtype="https://schema.org/NewsArticle">'
          '<link itemprop="mainEntityOfPage" href="https://publisher.example/other">'
          '<meta itemprop="dateModified" content="2027-01-01"></aside></article>')
    assert publisher_html_day(html,url=url)==date(2026,11,6)
    assert publisher_html_day(html,url=url+'/other') is None
    assert publisher_html_day(html.replace('itemprop="mainEntityOfPage"','itemprop="unrelated"'),url=url) is None
    assert publisher_html_day(html.replace('datePublished','observationDate').replace('dateModified','eventDate'),url=url) is None


def test_transcribed_release_can_have_image_placeholder_but_not_prose_before_dateline():
    from sec_agent.research_foundation.dated_web_discovery import publisher_markdown_day
    text='# Publisher release\n\nImage\n\nSeptember 23, 2026\n\nWASHINGTON — Announcement.'
    assert publisher_markdown_day(text)==date(2026,9,23)
    assert publisher_markdown_day(text.replace('Image','A forecast about the following date')) is None
    assert publisher_markdown_day(text.replace('September 23, 2026','September 23')) is None


def test_filtered_publisher_catalog_is_navigation_not_a_fetchable_dated_release():
    from sec_agent.research_foundation.dated_web_discovery import filtered_publication_catalog
    url='https://publisher.gov/news?f%5B0%5D=facet_dates%3A2026-04'
    assert filtered_publication_catalog(url)
    assert not filtered_publication_catalog('https://publisher.gov/release?f=normal')
    reader,_,_=_reader(url=url,published=None)
    class NeverFetch:
        async def fetch(self,*args,**kwargs):raise AssertionError('collection sent as publication')
    reader.discovery=DatedWebDiscovery(reader.discovery,NeverFetch(),origin_fetcher=NeverFetch())
    result=_call(reader,'search',query='publisher topic')
    assert not result.items
    assert 'publisher_directory_not_dated_document' in result.model_dump_json()
    assert url in result.model_dump_json() and 'Public source fixture' not in result.model_dump_json()


def test_pdf_issue_metadata_is_not_a_policy_effective_date_or_body_mention():
    memo='Office of an agency\nJanuary 9, 2026 \nMEMORANDUM FOR STAFF\nFROM: Director\nSUBJECT: Policy\nEffective January 1, 2027.'
    assert publisher_day(memo,pdf=True)==date(2026,1,9)
    assert publisher_day(memo.replace('January 9, 2026','Effective January 9, 2026'),pdf=True) is None
    assert publisher_day(memo,pdf=False) is None
    note='Public fiscal note\nVersion: First revised\nDate: May 6, 2026\nSummary Information\nProjected spending in 2027.'
    assert publisher_day(note,pdf=True)==date(2026,5,6)
    assert publisher_day(note.replace('Date:', 'Reporting date:'),pdf=True) is None
    assert publisher_day('Long body. '*150+note,pdf=True) is None
    letter='Agency letterhead\nSeptember 21, 2026\nMs. Example\nDirector\nP.O. Box 123\nCity, State 12345\nDear Director:\nWith this letter I direct an action.'
    assert publisher_day(letter,pdf=True)==date(2026,9,21)
    assert publisher_day(letter,pdf=False) is None
    assert publisher_day(letter.replace('September 21, 2026','Effective September 21, 2026'),pdf=True) is None
    assert publisher_day(letter.replace('12345','unknown'),pdf=True) is None
    assert publisher_day(letter.replace('Dear Director:', 'The report says:'),pdf=True) is None


def test_site_path_keeps_host_and_account_scope_when_provider_ignores_query():
    for url, accepted in [('https://example.com/account/status/1', True),
                          ('https://example.com/other/status/1', False),
                          ('https://unrelated.com/account/status/1', False)]:
        reader,_,_ = _reader(url=url,published=None)
        gate = DatedWebDiscovery(reader.discovery,None)
        gate.verified[url] = date(2026,6,1)
        reader.discovery=gate
        result=_call(reader,'search',query='site:example.com/account statements')
        assert bool(result.items) == accepted
        if not accepted:
            assert url not in result.model_dump_json()


def test_guarded_publisher_redirect_dates_target_and_stops_cycles():
    from sec_agent.research_foundation.external_sources import FetchedPage
    start,final='https://example.com/old','https://example.com/new'
    class Origin:
        cycle=False
        async def fetch(self,url,**_):
            target=final if url==start else start if self.cycle else final
            return FetchedPage(final_url=target,html='<html><head><meta property="article:published_time" content="2026-06-01"></head><body><h1>Release</h1></body></html>')
    reader,_,_=_reader(url=start,published=None)
    origin=Origin(); reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=origin)
    result=_call(reader,'search',query='publisher release')
    assert result.items[0]['source_url']==final
    origin.cycle=True;reader.discovery.verified.clear()
    result=_call(reader,'search',query='another query')
    assert not result.items
    assert 'publisher_navigation_cycle' in result.model_dump_json()


def test_undated_candidate_has_locator_feedback_but_no_text_or_late_candidate():
    from sec_agent.research_foundation.external_sources import FetchedPage
    url='https://example.com/notice'
    class Origin:
        stamp=''
        async def fetch(self,url,**_):
            return FetchedPage(final_url=url,html='<html><head>'+self.stamp+'</head><body><h1>Unverified future title</h1></body></html>')
    reader,_,_=_reader(url=url,published=None)
    origin=Origin();reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=origin)
    result=_call(reader,'search',query='notice')
    assert not result.items and url in result.model_dump_json()
    assert 'Unverified future title' not in result.model_dump_json()
    assert 'unresolved_originals' in result.model_dump_json()
    origin.stamp='<meta property="article:published_time" content="2027-06-01">'
    result=_call(reader,'search',query='another notice')
    assert not result.items and 'unresolved_originals' not in result.model_dump_json()


def test_bls_403_mirror_requires_matching_masthead_date_series_and_permitted_domain():
    from sec_agent.research_foundation.dated_web_discovery import dol_archive_copy
    from sec_agent.research_foundation.external_sources import FetchedPage

    original = 'https://www.bls.gov/news.release/archives/realer_06102026.htm'
    mirror = 'https://www.dol.gov/newsroom/economicdata/realer_06102026.pdf'
    reader, _, _ = _reader(url=original, published=None)
    _call(reader, 'search', query='real earnings')
    candidate = next(iter(reader._candidates.values()))[1]
    header = ('Transmission of material in this release is embargoed until USDL- 26-0825\n'
              '8:30 a.m. (ET) Wednesday, June 10, 2026\nwww.bls.gov/ces\nREAL EARNINGS – MAY 2026')

    class Origin:
        text = header

        async def fetch(self, locator, **_):
            assert locator == mirror
            return FetchedPage(final_url=locator, content_type='application/pdf', extracted_text=self.text)

    origin = Origin()
    result, day = asyncio.run(dol_archive_copy(candidate, origin, ()))
    assert day == date(2026, 6, 10) and result.canonical_url == mirror
    assert result.candidate_id != candidate.candidate_id
    assert asyncio.run(dol_archive_copy(candidate, origin, ('bls.gov',))) is None
    for invalid in (header.replace('June 10', 'June 12'), header.replace('REAL EARNINGS', 'OTHER RELEASE')):
        origin.text = invalid
        assert asyncio.run(dol_archive_copy(candidate, origin, ())) is None


def test_employment_release_uses_its_embargo_dateline_over_the_reference_month():
    masthead = ("Transmission of material in this news release is embargoed until USDL-26-1435\n"
                "8:30 a.m. (ET) Friday, September 4, 2026\n"
                "THE EMPLOYMENT SITUATION — AUGUST 2026")
    assert publisher_day(masthead) == date(2026, 9, 4)
    assert publisher_day(masthead.split("Friday, ")[-1].replace("September 4, 2026", "August 2026")) is None


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


def test_admitted_primary_suppresses_fallback_but_late_primary_does_not():
    primary, _, _ = _reader(url='https://example.com/first', published=None)
    secondary, _, _ = _reader(url='https://example.com/second', published=None)
    class Unexpected:
        async def fetch(self, *args, **kwargs):
            raise AssertionError('cached date expected')
    gate = DatedWebDiscovery(primary.discovery, Unexpected(), fallback_discovery=secondary.discovery)
    primary.discovery = gate
    first, second = 'https://example.com/first', 'https://example.com/second'
    gate.verified.update({first:date(2026,6,1),second:date(2026,6,2)})
    result = _call(primary,'search',query='fixture')
    assert [x['source_url'] for x in result.items] == [first]
    gate.verified[first] = date(2027,1,1)
    result = _call(primary,'search',query='second query')
    assert [x['source_url'] for x in result.items] == [second]
    assert result.items[0]['preview'] == ''


def test_release_label_and_later_explicit_update():
    assert publisher_day('EMBARGOED UNTIL RELEASE AT 8:30 a.m. EDT, Thursday, June 25, 2026') == date(2026,6,25)
    assert publisher_day('Published: June 1, 2026\nLast Update:\nJuly 2, 2026') == date(2026,7,2)


def test_only_release_masthead_date_or_article_metadata_qualifies():
    from sec_agent.research_foundation.dated_web_discovery import publisher_html_day
    release = '<main><span>Press Release</span><h1>Example</h1><div></div><div>May 12, 2026</div><p>Report content</p></main>'
    assert publisher_html_day(release) == date(2026,5,12)
    assert publisher_html_day(release.replace('Press Release','Data series')) is None
    meta = '<head><meta property="article:modified_time" content="2026-07-15T12:00:00Z"></head>'
    assert publisher_html_day(meta + release) == date(2026,7,15)


def test_labelled_publication_time_requires_agreeing_visible_masthead():
    from sec_agent.research_foundation.dated_web_discovery import publisher_html_day
    html = ('<main><article><h1>Regulations finalized</h1><section><article><div class="info">'
            '<div class="published">News: <time datetime="2025-09-23">September 23, 2025</time></div>'
            '<div class="description"><p>Article text</p></div></div></article></section></article></main>')
    assert publisher_html_day(html) == date(2025,9,23)
    assert publisher_html_day(html.replace('published', 'event-date')) is None
    assert publisher_html_day(html.replace('2025-09-23', '2025-09-24')) is None
    assert publisher_html_day(html.replace('<h1>', '<p>Earlier prose</p><h1>')) == date(2025,9,23)
    assert publisher_html_day(html.replace('<div class="published">', '<p>Article starts</p><div class="published">')) is None
    assert publisher_html_day(html.replace('</main>', '<time datetime="2026-01-01">January 1, 2026</time></main>')) is None
    assert publisher_html_day('<head><meta property="article:modified_time" content="2026-10-01"></head>'+html) == date(2026,10,1)

def test_known_url_skips_ranked_search_and_keeps_cutoff_and_guard(monkeypatch):
    from sec_agent.research_foundation.external_sources import PublicURLGuard, FetchedPage
    monkeypatch.setattr('sec_agent.research_foundation.external_sources._resolve_host', lambda _: ['8.8.8.8'])
    day = 'June 1, 2026'
    class Origin:
        async def fetch(self, url, **_):
            assert url == 'https://example.com/original'
            return FetchedPage(final_url=url, extracted_text='Published: '+day)
    class NeverSearch:
        async def search(self, _):
            raise AssertionError('Known URL incorrectly went to ranked search')
    reader, _, _ = _reader(url='https://example.com/original')
    reader.discovery = DatedWebDiscovery(NeverSearch(), None, origin_fetcher=Origin())
    assert _call(reader,'search',query='http://127.0.0.1/admin').items == ()
    url = 'https://example.com/original'
    item = _call(reader,'search',query=url).items[0]
    assert item['publication_date']=='2026-06-01' and not item['writer_citable']
    assert _call(reader,'read',document_id=item['document_id']).items[0]['writer_citable']
    reader.discovery.verified.clear()
    day = 'June 1, 2099'
    assert not _call(reader,'search',query=url).items


def test_publication_page_has_own_identity_and_must_link_exact_pdf():
    from sec_agent.research_foundation.dated_web_discovery import census_publication_page
    from sec_agent.research_foundation.external_sources import FetchedPage
    pdf = 'https://www2.census.gov/library/publications/2026/demo/p60-289.pdf'
    url = 'https://www.census.gov/library/publications/2026/demo/p60-289.html'
    reader, _, _ = _reader(url=pdf, published=None)
    _call(reader, 'search', query='household incomes')
    candidate = next(iter(reader._candidates.values()))[1]
    class Publisher:
        link = pdf
        async def fetch(self, locator, **_):
            assert locator == url
            return FetchedPage(final_url=url,html='<head><meta property="article:published_time" content="2026-09-15"></head>'
                               +'<h1>Income Report</h1><a href="'+self.link+'">Download</a>')
    publisher = Publisher()
    row, day = asyncio.run(census_publication_page(candidate,publisher,()))
    assert day.isoformat() == '2026-09-15' and row.canonical_url == url and row.candidate_id != candidate.candidate_id
    publisher.link=pdf.replace('289','290')
    assert asyncio.run(census_publication_page(candidate,publisher,())) is None
