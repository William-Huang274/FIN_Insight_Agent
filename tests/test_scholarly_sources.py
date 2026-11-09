import pytest

from sec_agent.research_foundation.external_sources import ExternalSourceCapture, ExternalSourceError, FetchedPage
from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
from sec_agent.research_foundation.scholarly_sources import ArxivSources, api_url, arxiv_locator, parse_record
from test_web_source_navigation import _reader, _call
from test_external_sources import _public_guard


def atom(version='2607.00001v1', updated='2026-07-01T19:00:00Z'):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom"><updated>2027-01-01T00:00:00Z</updated>
    <entry><id>http://arxiv.org/abs/{version}</id><title>Study</title>
    <published>2026-07-01T19:00:00Z</published><updated>{updated}</updated>
    <link href="https://arxiv.org/pdf/{version}" title="pdf" rel="related" type="application/pdf"/>
    <summary>Abstract, not complete methods. A source-bound research summary.</summary></entry></feed>'''


def test_atom_identity_version_and_update_not_feed_clock():
    assert parse_record(atom(), '2607.00001')['day'] == '2026-07-01'
    assert parse_record(atom('2607.00001v2', '2026-10-01T00:00:00Z'), '2607.00001')['day'] == '2026-10-01'
    for requested in ('2607.99999', '2607.00001v2'):
        with pytest.raises(ExternalSourceError, match='identity_or_version'):
            parse_record(atom(), requested)
    with pytest.raises(ExternalSourceError):
        parse_record(atom().replace('<updated>2026-07-01T19:00:00Z</updated>', ''), '2607.00001')
    assert arxiv_locator('https://arxiv.org/pdf/2607.00001v1.pdf') == ('pdf','2607.00001v1')
    assert arxiv_locator('https://arxiv.org.evil.example/abs/2607.00001') is None
    assert arxiv_locator('https://export.arxiv.org/api/query?id_list=2607.00001,2607.00002') is None


def test_search_read_record_then_full_text_and_replay_keep_separate_identities():
    reader, _, _ = _reader(url='https://arxiv.org/abs/2607.00001', published=None)
    class Origin:
        calls = []
        async def fetch(self, url, **_):
            self.calls.append(url)
            if '/api/' in url:
                return FetchedPage(final_url=url, html=atom(), status_code=200)
            return FetchedPage(final_url=url, extracted_text='Full paper results and methods.\n'*100, status_code=200, content_type='application/pdf')
    origin = Origin()
    scholarly = ArxivSources(origin, request_interval=0)
    reader.discovery = DatedWebDiscovery(reader.discovery, None, origin_fetcher=scholarly, scholarly=scholarly)
    reader.capture = ExternalSourceCapture(guard=_public_guard(), static_fetcher=scholarly)
    search = _call(reader, 'search', query='study')
    doc = search.items[0]['document_id']
    assert search.items[0]['source_url'] == api_url('2607.00001v1')
    first = _call(reader, 'read', document_id=doc).items[0]
    assert first['source_read_method'] == 'arxiv_api_metadata'
    assert first['access_scope'] == 'scholarly_metadata_and_abstract_only'
    assert 'NOT full paper' in first['passage']
    assert 'https://arxiv.org/pdf/2607.00001v1' in first['passage']
    assert first['discovered_links']
    count = len(origin.calls)
    assert _call(reader, 'read', document_id=doc).items[0]['passage_id'] == first['passage_id']
    assert len(origin.calls) == count
    pdf_reader, _, _ = _reader(url='https://arxiv.org/pdf/2607.00001v1', published=None)
    pdf_reader.discovery = DatedWebDiscovery(pdf_reader.discovery,None,origin_fetcher=scholarly,scholarly=scholarly)
    pdf_reader.capture = reader.capture
    found = _call(pdf_reader,'search',query='paper PDF')
    full = _call(pdf_reader,'read',document_id=found.items[0]['document_id']).items[0]
    assert full['source_url'] == 'https://arxiv.org/pdf/2607.00001v1'
    assert full['access_scope'] == 'requested_url_body_only'
    assert full['passage_id'] != first['passage_id'] and 'Full paper results' in full['passage']


def test_late_revision_not_replaced_by_first_submission():
    reader, _, _ = _reader(url='https://arxiv.org/abs/2607.00001',published=None)
    class Origin:
        async def fetch(self,url,**_):
            return FetchedPage(final_url=url,html=atom('2607.00001v2','2026-10-01T00:00:00Z'),status_code=200)
    scholarly=ArxivSources(Origin(),request_interval=0)
    reader.discovery=DatedWebDiscovery(reader.discovery,None,origin_fetcher=scholarly,scholarly=scholarly)
    result=_call(reader,'search',query='study')
    assert not result.items
    assert 'after_cutoff' in result.model_dump_json()
