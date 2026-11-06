import asyncio
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from sec_agent.research_foundation.congress_api import (
    CongressAPI, bill_identity, congress_rendition_package, public_payload, api_json)
from sec_agent.research_foundation.external_sources import ExternalSourceError, FetchedPage
from sec_agent.agent_runtime.legislation import legislation_tool


URL = 'https://www.congress.gov/bill/119th-congress/house-bill/1'
PACKAGE = 'BILLS-119hr1ih'
DETAILS = 'https://www.govinfo.gov/app/details/'+PACKAGE
HTML = 'https://www.govinfo.gov/content/pkg/'+PACKAGE+'/html/'+PACKAGE+'.htm'
RECORD = {'congress':119,'type':'HR','number':'1','introducedDate':'2026-01-01',
          'updateDate':'2026-02-01T00:00:00Z','title':'Fixture bill'}
TEXT = {'date':'2026-01-01T00:00:00Z','type':'Introduced in House','formats':[
    {'type':'Formatted Text','url':'https://www.congress.gov/119/bills/hr1/BILLS-119hr1ih.htm'}]}


class API:
    def __init__(self):
        self.calls = []
        self.record = deepcopy(RECORD)
    async def read(self, identity, section, offset=0, limit=20):
        self.calls.append((identity,section,offset,limit))
        return {'source_url':'https://api.congress.gov/v3/bill/119/hr/1',
            'captured_at':'2026-06-01T00:00:00Z','next_offset':20 if section=='actions' else None,
            **({'bill':self.record} if section=='record' else {'textVersions':[TEXT]} if section=='texts'
               else {'actions':[{'actionDate':'2026-02-01','text':'Referred'},
                                {'actionDate':'2026-07-01','text':'Later action'}]})}


class Origin:
    def __init__(self): self.calls=[]
    async def fetch(self,url,**kw):
        self.calls.append(url)
        xml = f'''<mods xmlns="http://www.loc.gov/mods/v3"><identifier type="uri">{DETAILS}</identifier>
            <originInfo><dateIssued encoding="w3cdtf">2026-01-02</dateIssued></originInfo>
            <titleInfo><title>Fixture bill</title></titleInfo>
            <location><url displayLabel="HTML rendition">{HTML}</url></location></mods>'''
        return FetchedPage(final_url=url,html=xml,status_code=200)


@pytest.mark.parametrize('query',[URL,URL+'/text',URL+'/actions','119/hr/1',
    'https://api.congress.gov/v3/bill/119/hr/1'])
def test_locator_identity(query):
    assert bill_identity(query)==(119,'hr',1)


@pytest.mark.parametrize('query',['H.R.1','AI regulation','https://evil.test/'+URL,
    URL+'?api_key=secret','https://www.congress.gov.evil.test/bill/119th-congress/house-bill/1'])
def test_ambiguous_and_untrusted_locator_rejected(query):
    with pytest.raises(ValueError): bill_identity(query)


def test_rendition_identity_and_secret_redaction():
    assert congress_rendition_package(TEXT['formats'][0]['url'],(119,'hr',1))==PACKAGE
    assert congress_rendition_package(TEXT['formats'][0]['url'],(118,'hr',1)) is None
    assert public_payload({'request':{'api_key':'sensitive'},'next':'https://api.congress.gov/v3/bill?offset=2&api_key=sensitive'},'sensitive')=={
        'next':'https://api.congress.gov/v3/bill?offset=2'}


def test_existing_grant_navigation_and_recovery_cache(tmp_path):
    async def run():
        api, origin = API(), Origin()
        tid=str(uuid4())
        def tool(): return legislation_tool(thread_id=tid,cache_root=tmp_path,
            research_as_of='2026-06-30',api=api,origin=origin).tool
        first=tool()
        visible,_=await first.coroutine(query=URL)
        assert json.loads(visible)['record']['title']=='Fixture bill'
        visible, artifact=await first.coroutine(query=URL+'/text',operation='texts')
        row=json.loads(visible)['text_versions'][0]
        assert row['legislative_date'][:10]=='2026-01-01'
        option=row['read_options'][0]
        assert option['publication_date']=='2026-01-02'
        assert option['read_call']['arguments']['query']==HTML
        assert not row['full_text_read'] and not artifact['writer_citable']
        await tool().coroutine(query='119/hr/1',operation='record')
        assert [x[1] for x in api.calls]==['record','texts']
        visible,_=await first.coroutine(query=URL,operation='actions')
        result=json.loads(visible)
        assert len(result['actions'])==1 and result['omitted_date_count']==1
        assert result['next_offset']==20
    asyncio.run(run())


def test_updated_record_not_presented_as_historical_snapshot(tmp_path):
    api=API(); api.record['updateDate']='2026-07-01T00:00:00Z'
    tool=legislation_tool(thread_id=str(uuid4()),cache_root=tmp_path,api=api,research_as_of='2026-06-30').tool
    visible,_=asyncio.run(tool.coroutine(query=URL))
    assert 'Fixture bill' not in visible
    assert 'record_fields_withheld' in json.loads(visible)


def test_wrong_api_bill_and_rate_limit_stop():
    calls=[]
    def wrong(*a):return {'bill':{**RECORD,'number':'2'}}
    with pytest.raises(ExternalSourceError,match='identity_mismatch'):
        asyncio.run(CongressAPI(key='fixture',transport=wrong).read((119,'hr',1),'record'))
    def limited(*a):
        calls.append(a)
        raise ExternalSourceError('congress_api_rate_limited')
    api=CongressAPI(key='fixture',transport=limited)
    for _ in range(2):
        with pytest.raises(ExternalSourceError,match='rate_limited'):
            asyncio.run(api.read((119,'hr',1),'record'))
    assert len(calls)==1


def test_missing_key_fails_without_request(monkeypatch):
    import requests
    monkeypatch.setattr(requests,'get',lambda *a,**k:pytest.fail('must not dispatch'))
    with pytest.raises(ExternalSourceError,match='key_missing'):
        api_json('https://api.congress.gov/v3/bill',{},'')


@pytest.mark.parametrize('status,code',[(429,'rate_limited'),(403,'credential_rejected'),(404,'http_404')])
def test_transport_feedback_no_secret_in_errors(monkeypatch,status,code):
    import requests
    class Response:
        status_code=status
        def __enter__(self):return self
        def __exit__(self,*a):pass
    def get(*a,**kw):
        assert 'api_key' not in kw['params']
        assert kw['headers']['X-Api-Key']=='test-private-value'
        assert not kw['allow_redirects']
        return Response()
    monkeypatch.setattr(requests,'get',get)
    with pytest.raises(ExternalSourceError,match=code) as err:
        api_json('https://api.congress.gov/v3/bill',{},'test-private-value')
    assert 'test-private-value' not in str(err.value)
