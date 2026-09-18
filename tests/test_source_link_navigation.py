import asyncio
from copy import deepcopy

import pytest

from sec_agent.research_foundation.source_link_navigation import observed_document_links
from sec_agent.research_foundation.method_source_acquisition import MethodSourceAcquirer, SourceAcquisition
from sec_agent.research_foundation.external_sources import ExternalSourceCapture, ExternalSourceDiscovery, FetchedPage, ProviderHit
from sec_agent.research_foundation.web_source_navigation import WebSourceReader
from test_web_source_navigation import _call, BRANCH
from test_external_sources import _public_guard, _run_scope


INDEX = 'https://www.sec.gov/Archives/edgar/data/12345/000001234526000001/0000012345-26-000001-index.html'
TABLE = '| Seq | Description | Document | Type | Size |\n|---|---|---|---|---|\n|1|10-Q|company-20260630.htm iXBRL|10-Q|2000000|\n'


def test_observed_links_use_parser_and_sec_document_column_not_guessed_path():
    links = observed_document_links(TABLE, INDEX)
    assert len(links) == 1 and links[0]['url'] == INDEX.rsplit('/', 1)[0]+'/company-20260630.htm'
    assert links[0]['origin'] == 'runtime_compatibility:sec_filing_index_document_column'
    assert not observed_document_links(TABLE, 'https://example.com/index.html')
    assert not observed_document_links(TABLE.replace('Document', 'Comment'), INDEX)
    assert not observed_document_links(TABLE.replace('company-20260630.htm', '../../secret.htm'), INDEX)
    links = observed_document_links('[Quarter](quarter.htm) [local](https://127.0.0.1/a) [part](#note)\n`[code](bad.htm)`', 'https://example.com/filings/index')
    assert [r['url'] for r in links] == ['https://example.com/filings/quarter.htm']


def test_link_read_checkpoint_keeps_parent_provenance_and_does_not_inherit_date():
    fetched = []
    class Provider:
        provider_id = 'fixture'
        async def search(self, request):
            return [ProviderHit(title='Filing directory', url=INDEX, published_at='2025-01-01')]
    class Fetcher:
        async def fetch(self, url, **kwargs):
            fetched.append(url)
            return FetchedPage(final_url=url, extracted_text=(TABLE+'\nIndex information. '*30 if url == INDEX else 'Revenue note actual disclosure. '*30), status_code=200)
    def reader():
        return WebSourceReader(discovery=ExternalSourceDiscovery(primary=Provider()),
            capture=ExternalSourceCapture(guard=_public_guard(), hosted_fetcher=Fetcher()))
    first=reader()
    parent=_call(first,'search',query='quarterly filing').items[0]['document_id']
    window=_call(first,'read',document_id=parent).items[0]
    link=window['discovered_links'][0]
    assert link['parent_document_id']==parent and not link['writer_citable']
    assert link['publication_date'] is None
    receipt=first.export_navigation()
    assert len(fetched)==1  # discovery does not fetch every linked document
    second=reader()
    second.restore_navigation(receipt, branch_id=BRANCH, run_scope=_run_scope(BRANCH))
    child=_call(second,'read',document_id=link['document_id']).items[0]
    assert child['source_url']==link['source_url'] and child['publication_date'] is None
    assert child['source_locator']['capture_receipt_digest'] != window['source_locator']['capture_receipt_digest']
    tampered=deepcopy(receipt);tampered[0]['candidates'][0]['canonical_url']='https://example.com/forged'
    with pytest.raises(ValueError,match='digest_mismatch'):
        second.restore_navigation(tampered,branch_id=BRANCH,run_scope=_run_scope(BRANCH))
    acquire=MethodSourceAcquirer(reader=second,branch_id=BRANCH,run_scope=_run_scope(BRANCH),record=lambda *a:None)
    acquire.restore([{'navigation_state':receipt,'linked_candidates':[link]}])
    result=asyncio.run(acquire(SourceAcquisition(acquisition_id='follow',linked_document_ids=[link['document_id']],
        unresolved_question='Read actual body',why_existing_sources_insufficient='Directory only'),_run_scope(BRANCH).research_as_of.date().isoformat()))
    assert len(result['reads'])==1
    with pytest.raises(ValueError,match='not_in_observed'):
        asyncio.run(acquire(SourceAcquisition(acquisition_id='bad',linked_document_ids=['WEB::forged'],
            unresolved_question='body',why_existing_sources_insufficient='index'),_run_scope(BRANCH).research_as_of.date().isoformat()))


@pytest.mark.parametrize('capture_after_cutoff', [False, True])
def test_specialist_search_terms_reach_new_original_scope(capture_after_cutoff):
    from datetime import datetime, timezone, timedelta
    from test_web_source_navigation import _reader
    text='Opening unrelated. '*2000+'\nSpecificCashNote states payment received.\n'+'Other material. '*2000
    reader,fetcher,_=_reader(text=text)
    reader.capture._clock = lambda: _run_scope(BRANCH).research_as_of + timedelta(days=1 if capture_after_cutoff else -1)
    sid=_call(reader,'search',query='filing').items[0]['document_id']
    prefix=_call(reader,'read',document_id=sid,max_characters=2000).items[0]
    acquire=MethodSourceAcquirer(reader=reader,branch_id=BRANCH,run_scope=_run_scope(BRANCH),record=lambda *a:None)
    read={'status':'readable','source':{'id':sid},'items':[dict(id=prefix['passage_id'],body=prefix['passage'])],
        'coverage':{'complete_document':False}}
    updated,receipts=asyncio.run(acquire.read_for_task(read,['SpecificCashNote']))
    assert 'payment received' not in read['items'][0]['body']
    assert any('payment received' in p['body'] for p in updated['items']) is not capture_after_cutoff
    assert updated['coverage']['task_searches'][0]['query']=='SpecificCashNote'
    assert receipts[0].status==('scope_ineligible' if capture_after_cutoff else 'ok') and len(fetcher.calls)==1
