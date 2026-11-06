import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery, publisher_html_day, publisher_day
from sec_agent.research_foundation.external_sources import ExternalSourceError, FetchedPage, trafilatura_extract_text
from sec_agent.research_foundation.government_sources import GovernmentSourceFetcher, official_search_entries
from test_web_source_navigation import _reader, _call


def test_release_masthead_and_document_modified_metadata_not_body_dates():
    page = '<main><div><h1>Order</h1></div><section><p class="meta">September 21, 2026 | Austin, Texas | <a>Press Release</a></p><p>The deadline is October 19, 2026.</p></section></main>'
    assert publisher_html_day(page) == date(2026,9,21)
    assert publisher_html_day(page.replace('September 21, 2026 | Austin, Texas |', 'A speaker recalled September 21, 2026')) is None
    modified = '<div>Last Modified <span class="contentModifiedDate">2026-11-07</span></div>'
    assert publisher_html_day(page + modified) == date(2026,11,7)
    assert publisher_html_day(modified.replace('Last Modified','Copyright')) is None
    assert publisher_day('NOTICE DATE: September 3, 2026\nDAYS AFFECTED: September 10, 2026') == date(2026,9,3)


URL = 'https://www.ercot.com/services/comm/mkt_notices/M-A080326-04'
BODY = 'NOTICE DATE: September 3, 2026\nNOTICE TYPE: M-A080326-04 Legal\nLONG DESCRIPTION: ' + 'A notice body. '*50


class Denied:
    async def fetch(self, url, **_):
        raise ExternalSourceError('capture_http_status_403')


class Hosted:
    def __init__(self, text=BODY):
        self.text, self.calls = text, []
    async def fetch_markdown(self, url):
        self.calls.append(url)
        return self.text


def test_government_transcription_is_labelled_and_dated_without_claiming_origin_bytes():
    from sec_agent.research_foundation.dated_web_discovery import publisher_markdown_day
    url='https://publisher.gov/press/example'
    text='July 21st, 2026\n\n# Publisher announcement\n\nThe deadline is January 1, 2027. '+('Public announcement content. '*30)
    hosted=Hosted(text);fetcher=GovernmentSourceFetcher(Denied(),hosted)
    page=asyncio.run(fetcher.fetch(url,timeout_seconds=1))
    assert page.extraction_method=='deepseek_hosted_publication'
    assert page.origin_failure_code=='capture_http_status_403' and page.final_url==url
    assert publisher_markdown_day(text)==date(2026,7,21)
    assert publisher_markdown_day(text.replace('July 21st, 2026','In force July 21st, 2026')) is None
    assert publisher_markdown_day(text+'\nUpdated: August 3, 2026')==date(2026,8,3)
    reader,_,_=_reader(url=url,published=None)
    reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=fetcher)
    reader.capture.static_fetcher=fetcher
    doc=_call(reader,'search',query='release').items[0]['document_id']
    row=_call(reader,'read',document_id=doc).items[0]
    assert row['source_read_method']=='deepseek_hosted_publication'
    assert 'not independently verified original bytes' in row['authority_note']
    hosted.text=text.replace('July 21st','September 21st');reader.discovery.verified.clear()
    assert not _call(reader,'search',query='late release').items


def test_empty_origin_is_not_a_successful_undated_original():
    class Empty:
        async def fetch(self,url,**kwargs):return FetchedPage(final_url=url,html='')
    hosted=Hosted('July 21st, 2026\n\n# Release\n\nContent')
    page=asyncio.run(GovernmentSourceFetcher(Empty(),hosted).fetch('https://publisher.gov/news',timeout_seconds=1))
    assert page.origin_failure_code=='capture_empty_response'
    with pytest.raises(ExternalSourceError,match='capture_empty_response'):
        asyncio.run(GovernmentSourceFetcher(Empty(),hosted).fetch('https://other.example/news',timeout_seconds=1))


def test_government_406_can_use_exact_url_transcription_without_inventing_date():
    class NotAcceptable:
        async def fetch(self,url,**kwargs):raise ExternalSourceError('capture_http_status_406')
    hosted=Hosted('Undated catalog')
    page=asyncio.run(GovernmentSourceFetcher(NotAcceptable(),hosted).fetch('https://publisher.gov/catalog',timeout_seconds=1))
    assert page.origin_failure_code=='capture_http_status_406'
    assert hosted.calls==['https://publisher.gov/catalog']
    assert publisher_day(page.extracted_text) is None


def test_bill_catalog_discloses_only_dated_versions_within_cutoff():
    from sec_agent.research_foundation.government_sources import dated_bill_catalog
    text='SB26-999\n\n# Bill\nCurrent summary must not be shown.\n\n### Bill Text\n\nDate | Version | Documents\n---|---|---\n07/01/2026 | Signed Act |\n05/01/2026 | Introduced |\n\nOther material'
    result=dated_bill_catalog('https://leg.example.gov/bills/sb26-999',text,date(2026,6,30))
    assert [r['version_label'] for r in result['versions']]==['Introduced']
    assert not result['writer_citable'] and result['current_summary_withheld']
    assert 'Current summary' not in str(result)
    assert dated_bill_catalog('https://leg.example.gov/bills/sb26-998',text,date(2026,6,30)) is None


def test_notice_fallback_exact_identity_date_and_original_failure():
    hosted = Hosted()
    fetcher = GovernmentSourceFetcher(Denied(),hosted)
    page=asyncio.run(fetcher.fetch(URL,timeout_seconds=1))
    assert page.extracted_text==BODY and page.final_url==URL
    assert page.extraction_method=='deepseek_hosted_notice' and page.origin_failure_code=='capture_http_status_403'
    for text, error in [(BODY.replace('04 Legal','05 Legal'),'identity_mismatch'),
                        (BODY.replace('NOTICE DATE:','DAYS AFFECTED:'),'date_unverified')]:
        hosted.text=text
        with pytest.raises(ExternalSourceError,match=error):
            asyncio.run(fetcher.fetch(URL,timeout_seconds=1))
    hosted.calls.clear()
    with pytest.raises(ExternalSourceError,match='403'):
        asyncio.run(fetcher.fetch('https://www.ercot.com/login',timeout_seconds=1))
    assert not hosted.calls


def test_notice_capture_preserves_transport_identity_and_cutoff():
    reader, _, _ = _reader(url=URL,published=None)
    fetcher=GovernmentSourceFetcher(Denied(),Hosted())
    reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=fetcher)
    reader.capture.static_fetcher=fetcher
    # Fixture cutoff is Aug 1, so the September notice must not enter input.
    assert not _call(reader,'search',query='notice').items
    fetcher.hosted.text=BODY.replace('September 3','July 3')
    reader.discovery.verified.clear()
    doc=_call(reader,'search',query='notice').items[0]['document_id']
    result=_call(reader,'read',document_id=doc)
    assert result.items[0]['source_read_method']=='deepseek_hosted_notice'
    assert 'Hosted DS Fetch' in result.items[0]['authority_note']
    assert result.execution_receipt.attempts[0]['failure_code']=='capture_http_status_403'


def test_original_html_keeps_links_and_dated_read_offers_check_not_authorized_child():
    html='<html><body><article><h1>A policy publication</h1>'+''.join(
        '<p>Substantive original text with detail. '*3+'</p>' for _ in range(20))+'<p>Read the <a href="https://example.com/attachment.pdf">attached directive</a>.</p></article></body></html>'
    text=trafilatura_extract_text(html)
    assert 'https://example.com/attachment.pdf' in text
    reader, _, _ = _reader(text=text)
    from test_external_sources import _run_scope
    from sec_agent.research.reviewed_evidence_pack import canonical_digest
    original=_run_scope('Q8_COMPETITION_VALUE_POOL')
    body=original.model_dump(mode='json',exclude={'run_scope_digest'})
    body['data_snapshot_id']='dated-public-sources-v2'
    scope=type(original)(**body,run_scope_digest=canonical_digest(body))
    doc=_call(reader,'search',query='publication',scope=scope).items[0]['document_id']
    row=_call(reader,'read',document_id=doc,scope=scope).items[0]
    link=row['discovered_links'][0]
    assert link['read_entry']['arguments']=={'operation':'search','query':'https://example.com/attachment.pdf'}
    assert 'document_id' not in link and not link['writer_citable'] and not link['publication_date_inherited']


def test_fetch_failure_is_recorded_separately_from_successful_search():
    reader, _, _=_reader(url='https://example.com/undated',published=None)
    reader.discovery.primary.provider_id='deepseek_search'
    class Undated:
        async def fetch(self,url,**_):
            return FetchedPage(final_url=url,html='<h1>Undated</h1><p>Body</p>')
    class DS:
        async def fetch_markdown(self,url):
            raise ExternalSourceError('deepseek_fetch_http_404')
    reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=Undated(),search_backup=SimpleNamespace(primary=DS()))
    # No second provider is needed in this test; use direct provider receipt and
    # clear backup after it has supplied the failed Fetch operation.
    class Backup:
        primary=DS()
        async def search(self,request):
            return await reader.discovery.discovery.search(request)
    reader.discovery.search_backup=Backup()
    result=_call(reader,'search',query='undated publication')
    first=result.execution_receipt.attempts[0]
    assert first['status']=='ok'
    assert first['verification_failures']['deepseek_fetch:deepseek_fetch_http_404']==1
    from sec_agent.agent_runtime.conversation_web import web_read_feedback
    assert web_read_feedback(result.model_dump())[0]['kind']=='source_verification_failures'


def test_official_entries_are_optional_discovery_and_preserve_query():
    rows=official_search_entries('Abbott TCEQ ERCOT permits')
    assert {r['domain'] for r in rows}=={'gov.texas.gov','tceq.texas.gov','ercot.com'}
    assert rows[0]['arguments']['query'].startswith('Abbott TCEQ ERCOT permits site:')
    assert official_search_entries('permits site:tceq.texas.gov')==[]
    assert official_search_entries('ordinary company results')==[]


def test_canonical_page_is_refetched_dated_and_bound_not_a_guessed_parameter_strip():
    from sec_agent.research_foundation.dated_web_discovery import publisher_canonical_url
    original='https://example.com/notice?query-11-page=3'
    clean='https://example.com/notice'
    html='<head><link rel="canonical" href="'+clean+'"></head>'
    assert publisher_canonical_url(html,original)==clean
    assert publisher_canonical_url(html.replace('/notice','/different'),original) is None
    assert publisher_canonical_url(html.replace('example.com','another.com'),original) is None
    class Origin:
        calls=[]
        async def fetch(self,url,**_):
            self.calls.append(url)
            return FetchedPage(final_url=url,html=html if url==original else '<head><meta property="article:published_time" content="2026-07-01"></head><h1>Notice</h1>')
    reader,_,_=_reader(url=original,published=None)
    origin=Origin()
    reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=origin)
    item=_call(reader,'search',query='notice').items[0]
    assert origin.calls==[original,clean]
    assert item['source_url']==clean and item['publication_date']=='2026-07-01'
