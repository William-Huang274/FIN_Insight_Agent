import asyncio
import json
from datetime import date

import pytest

from test_company_disclosures import request
from sec_agent.research_foundation.company_disclosures import CompanySources, FilingSearch, Issuer
from sec_agent.research_foundation.external_sources import ExternalSourceError


def issuer(rows):
    columns = {key: [r.get(key, '') for r in rows] for key in (
        'form', 'filingDate', 'reportDate', 'items', 'accessionNumber', 'primaryDocument')}
    return Issuer('EX', {'cik':1,'fiscalYearEnd':'0331','filings':{'recent':columns}}, [], '', None)


def row(form, filed='2026-11-04', report='', number=1, doc='primary.htm', items=''):
    return dict(form=form,filingDate=filed,reportDate=report,items=items,
                accessionNumber=f'0000000001-26-{number:06d}',primaryDocument=doc)


def test_foreign_current_reports_use_publication_window_not_period_end_or_8k_items():
    company=issuer([row('6-K',report='2026-11-04'), row('6-K',number=2),
                    row('6-K','2026-11-07',number=3),row('6-K','2026-07-29',number=4)])
    found=company.filings(request('EX fiscal Q2 2027 results','2026-11-06'))
    assert [r[3] for r in found]==['0000000001-26-000001','0000000001-26-000002']
    assert found[1][2] is None  # no invented report period


@pytest.mark.parametrize('form',['10-K','10-Q','10-KT','10-QT','20-F','40-F','6-K','8-K'])
def test_default_financial_forms_keep_original_and_amendment_identity(form):
    company=issuer([row(form,report='2026-03-31'),row(form+'/A',number=2,report='2026-03-31')])
    found=company.filings(request('EX disclosures 2026','2026-11-06'))
    assert {r[0] for r in found}=={form,form+'/A'}
    exact=company.filings(request('EX '+form+'/A 2026','2026-11-06'))
    assert [r[0] for r in exact]==[form+'/A']


@pytest.mark.parametrize('form',['F-1','F-3','S-1','DEF 14A','SC 13G','13F-HR','424B4','4'])
def test_explicit_form_from_actual_sec_inventory_is_not_filtered_as_financial_report(form):
    company=issuer([row(form),row('6-K',number=2)])
    found=company.filings(request('EX Form '+form+' 2026','2026-11-06'))
    assert [r[0] for r in found]==[form]


def test_numeric_form_is_not_selected_by_a_number_in_an_earnings_question():
    company=issuer([row('4'),row('6-K',number=2)])
    assert [r[0] for r in company.filings(request('EX earnings growth 4 percent 2026','2026-11-06'))]==['6-K']


def test_explicit_non_earnings_8k_is_not_discarded_for_missing_item_202():
    company=issuer([row('8-K',items='5.02'),row('8-K',number=2,items='2.02,9.01')])
    assert len(company.filings(request('EX 8-K','2026-11-06')))==2
    assert [r[3] for r in company.filings(request('EX earnings','2026-11-06'))]==['0000000001-26-000002']


def test_exhibits_belong_to_exact_accession_and_are_not_called_earnings_by_default():
    class SEC:
        async def get(self,url):
            return b'''<table class="tableFile">
            <tr><td>2</td><td>Shareholder letter</td><td><a href="letter.htm">letter</a></td><td>EX-99.2</td></tr>
            <tr><td>3</td><td>Presentation</td><td><a href="deck.pdf">deck</a></td><td>EX-99.3</td></tr>
            <tr><td>4</td><td>Bad</td><td><a href="../other.htm">other</a></td><td>EX-99.1</td></tr>
            <tr><td>5</td><td>Other issuer</td><td><a href="https://example.com/a.htm">other</a></td><td>EX-99.1</td></tr>
            </table>'''
    search=FilingSearch(issuer([row('6-K')]),SEC())
    hits=asyncio.run(search.search(request('EX Q2 2027 results','2026-11-06')))
    assert [h.url.split('/')[-1] for h in hits]==['letter.htm','deck.pdf','primary.htm']
    assert all('Item 2.02' not in h.title for h in hits)
    assert search.dates[hits[0].url]==date(2026,11,4)


def test_history_only_reads_overlapping_sec_declared_pages_and_caches_them():
    source=CompanySources(None,None);calls=[]
    page=issuer([row('20-F','2024-05-12','2024-03-31')]).data['filings']['recent']
    async def get(url):calls.append(url);return json.dumps(page).encode()
    source.get=get
    company=issuer([])
    company.data['filings']['files']=[
        dict(name='CIK0000000001-submissions-001.json',filingFrom='2024-01-01',filingTo='2024-12-31'),
        dict(name='CIK0000000001-submissions-002.json',filingFrom='2018-01-01',filingTo='2019-12-31'),
        dict(name='CIK0000009999-submissions-001.json',filingFrom='2024-01-01',filingTo='2024-12-31')]
    req=request('EX 20-F 2024','2026-11-06')
    asyncio.run(source.load_history(company,req));asyncio.run(source.load_history(company,req))
    assert len(calls)==1
    assert len(company.filings(req))==1
    assert company.history_failures[0]['reason']=='sec_history_identity_invalid'


def test_unavailable_history_does_not_erase_available_current_filings():
    source=CompanySources(None,None)
    async def fail(url):raise ExternalSourceError('sec_http_403')
    source.get=fail
    company=issuer([row('6-K')]);company.data['filings']['files']=[
        dict(name='CIK0000000001-submissions-001.json',filingFrom='2025-01-01',filingTo='2025-12-31')]
    req=request('EX 2026 results','2026-11-06');asyncio.run(source.load_history(company,req))
    assert len(company.filings(req))==1
    assert FilingSearch(company,source).failures[0]['reason']=='sec_http_403'


def test_sec_pdf_and_plaintext_are_decoded_as_their_actual_formats():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas
    stream=BytesIO();canvas=Canvas(stream);canvas.drawString(30,700,'Shareholder letter: revenue 123');canvas.save()
    source=CompanySources('fixture',None)
    async def get(url,timeout):return stream.getvalue() if url.endswith('.pdf') else b'Revenue < 100\nCosts 20'
    source.get=get
    pdf=asyncio.run(source.fetch('https://www.sec.gov/Archives/edgar/data/1/doc.pdf',timeout_seconds=5))
    assert pdf.content_type=='application/pdf' and 'revenue 123' in pdf.extracted_text
    text=asyncio.run(source.fetch('https://www.sec.gov/Archives/edgar/data/1/doc.txt',timeout_seconds=5))
    assert text.extracted_text=='Revenue < 100\nCosts 20'


def test_annual_website_discovery_accepts_20f_without_inventing_issuer_domains():
    source=CompanySources('fixture',None)
    company=issuer([row('20-F','2026-05-01','2026-03-31')]);calls=[]
    async def get(url,timeout=10):
        calls.append(url)
        if url.endswith('company_tickers.json'):return json.dumps({'0':{'ticker':'EX','title':'Example Holdings plc','cik_str':1}}).encode()
        if url.endswith('.json'):return json.dumps(company.data).encode()
        return b'<p>Our website is www.example.com</p>'
    source.get=get
    result=asyncio.run(source.lookup(request('EX 20-F 2026','2026-11-06')))
    assert result.domains==('example.com',)
    assert result.evidence['https://www.example.com/'].endswith('/primary.htm')


def test_broad_foreign_results_search_discloses_selection_bound():
    company=issuer([row('6-K',number=i) for i in range(1,11)])
    class SEC:
        async def get(self,url):return b'<html/>'
    search=FilingSearch(company,SEC())
    assert len(asyncio.run(search.search(request('EX results 2026','2026-11-06'))))==8
    assert search.failures[0]['available']==10


def test_annual_primary_precedes_certification_and_all_attachments_have_navigation():
    class SEC:
        async def get(self,url):
            return b'''<table class="tableFile">
            <tr><td>2</td><td>CEO certification</td><td><a href="cert.htm">cert</a></td><td>EX-13.1</td></tr>
            <tr><td>3</td><td>Material agreement</td><td><a href="contract.htm">contract</a></td><td>EX-10.2</td></tr>
            </table>'''
    search=FilingSearch(issuer([row('20-F',report='2026-03-31')]),SEC())
    hits=asyncio.run(search.search(request('EX 20-F 2026','2026-11-06')))
    assert hits[0].url.endswith('primary.htm')
    assert search.documents[1]['description']=='Material agreement'
    assert search.documents[1]['role']=='navigation_only'


def test_quoted_date_site_failure_returns_company_preserving_regulatory_query():
    from test_web_source_navigation import _reader, _call
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    from sec_agent.research_foundation.external_sources import ExternalSourceDiscovery, ProviderHit
    company=issuer([row('6-K')]);company.roots=['https://ir.example.com/'];company.domains=('example.com',)
    class Sources:
        async def lookup(self,req):return company
    class Engine:
        provider_id='fixture_ir'
        async def search(self,req):
            assert req.include_domains==('ir.example.com',)
            return [ProviderHit(url='https://ir.example.com/release',title='Results')]
    class Origin:
        async def fetch(self,*args,**kw):raise ExternalSourceError('capture_http_status_403')
    reader,_,_=_reader()
    reader.discovery=DatedWebDiscovery(ExternalSourceDiscovery(primary=Engine()),None,origin_fetcher=Origin(),companies=Sources())
    result=_call(reader,'search',query='site:ir.example.com "November 4, 2026" results')
    assert not result.items
    nav=result.execution_receipt.attempts[0]['issuer_navigation']['regulatory_readback']
    assert nav['arguments']=={'operation':'search','query':'EX "November 4, 2026" results'}


def test_pdf_filing_candidate_is_admitted_and_citable_via_normal_reader():
    from test_web_source_navigation import _reader, _call
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    from sec_agent.research_foundation.external_sources import ExternalSourceDiscovery, FetchedPage
    company=issuer([row('6-K','2026-04-23',number=1,doc='letter.pdf')])
    class Sources:
        async def lookup(self,req):return company
        async def get(self,url):return b'<html/>'
    class Empty:
        provider_id='fixture_empty'
        async def search(self,req):return []
    class Origin:
        async def fetch(self,url,**kw):return FetchedPage(final_url=url,extracted_text='Published results: revenue 123. '*50,content_type='application/pdf')
    reader,_,_=_reader()
    reader.discovery=DatedWebDiscovery(ExternalSourceDiscovery(primary=Empty()),None,origin_fetcher=Origin(),companies=Sources())
    reader.capture.static_fetcher=Origin()
    result=_call(reader,'search',query='EX 6-K 2026')
    doc=result.items[0]['document_id']
    read=_call(reader,'read',document_id=doc,max_characters=2000)
    assert read.items[0]['writer_citable']
    assert read.items[0]['passage'].startswith('Published results:')
