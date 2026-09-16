"""Version identity, atomic revision writes and exact saved-source comparisons."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
import httpx

from apps.workbench.backend.api.v1.projects import build_projects_router
from apps.workbench.backend.authentication import install_conversation_auth, service_owner
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.project_asset_versions import RevisionConflict
from test_project_library import app_at, index, PROJECT, THREAD, WRITE, Identity


@pytest.fixture
def project(tmp_path, monkeypatch):
    # Exercise rollback at an explicit deployment quota, not the product default.
    monkeypatch.setenv('FINSIGHT_PROJECT_MAX_VERSIONS','12')
    client=TestClient(app_at(tmp_path,monkeypatch))
    client.put('/api/v1/projects',headers=WRITE,json=index())
    base=f'/api/v1/projects/{PROJECT}'
    old=client.post(base+'/documents',headers={**WRITE,'X-File-Name':'Q1.md'},content=b'# Q1\nRevenue 100 USD\n').json()
    return client,base,old,ProjectLibrary(tmp_path)


def route(base, asset, action, kind='document'):
    return f'{base}/assets/{kind}/{asset}/{action}'


def revision(client, base, parent, content=b'# Q2\nRevenue 120 USD\n', **params):
    return client.post(base+'/documents',params={'parent':parent,**params},
                       headers={**WRITE,'X-File-Name':'Q2.md'},content=content)


def test_revision_survives_reopen_and_exact_old_task_input_is_unchanged(project,tmp_path,monkeypatch):
    client,base,old,library=project
    scope=library.scope('alice',PROJECT); old_id=old['document_id']
    store=TaskAttachmentStore(tmp_path/'tasks')
    snapshot=store.copy_project_materials(THREAD,PROJECT,[library.documents.get(scope,old_id)])[0]
    new=revision(client,base,old_id,change_kind='new_period',note='Q2 additional disclosure')
    assert new.status_code==200
    new_id=new.json()['document_id']
    reopened=TestClient(app_at(tmp_path,monkeypatch))
    history=reopened.get(route(base,old_id,'history'),headers=WRITE).json()['items']
    assert [v['version_info']['sequence'] for v in history]==[1,2]
    assert history[1]['version_info']=={'family':old_id,'sequence':2,'parent':old_id,'change_kind':'new_period','note':'Q2 additional disclosure'}
    diff=reopened.get(route(base,old_id,'compare'),params={'other':new_id},headers=WRITE).json()
    assert not diff['raw_equal'] and '+Revenue 120 USD' in diff['lines'] and '-Revenue 100 USD' in diff['lines']
    assert store.get(THREAD,snapshot['document_id'])['body']==b'# Q1\nRevenue 100 USD\n'
    assert reopened.get(base+f'/documents/{old_id}/download',headers=WRITE).content==b'# Q1\nRevenue 100 USD\n'
    second_thread=str(uuid4())
    newer=store.copy_project_materials(second_thread,PROJECT,[library.documents.get(scope,new_id)])[0]
    assert newer['project_origin']['document_id']==new_id
    assert store.get(second_thread,newer['document_id'])['body']==b'# Q2\nRevenue 120 USD\n'


def test_revision_stale_concurrent_and_parse_failure_leave_no_orphans(project):
    client,base,old,library=project; old_id=old['document_id']; scope=library.scope('alice',PROJECT)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:revision(client,base,old_id),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    assert len(library.documents.list(scope))==2
    assert client.post(base+'/documents',params={'parent':old_id},headers={**WRITE,'X-File-Name':'bad.pdf'},content=b'invalid').status_code==422
    with library.documents.connect() as db:
        assert db.execute('SELECT count(*) FROM attachment_revisions').fetchone()[0]==1
    # Count failure happens after relation registration: both inserts must roll back.
    newest=next(r.json()['document_id'] for r in results if r.status_code==200)
    for i in range(10):library.documents.add(scope,f'{i}.txt',b'content')
    assert revision(client,base,newest).status_code==422
    with library.documents.connect() as db:
        assert db.execute('SELECT count(*) FROM attachment_revisions').fetchone()[0]==1


def test_other_owner_unrelated_documents_and_revocation_are_enforced(project):
    client,base,old,library=project; old_id=old['document_id']
    new_id=revision(client,base,old_id).json()['document_id']
    other=client.post(base+'/documents',headers={**WRITE,'X-File-Name':'Q1.md'},content=b'same name distinct source').json()['document_id']
    assert client.get(route(base,old_id,'compare'),params={'other':other},headers=WRITE).status_code==409
    bob={**WRITE,'Authorization':'Bearer bob'}
    client.put('/api/v1/projects',headers=bob,json=index())
    for action in ['history','dependencies','compare']:
        assert client.get(route(base,old_id,action),params={'other':new_id},headers=bob).status_code==404
    assert client.post(base+'/documents',params={'parent':old_id},headers={**bob,'X-File-Name':'x.txt'},content=b'x').status_code==404
    client.put(base+f'/assets/document/{old_id}/access',headers=WRITE,json={'revoked':True})
    assert client.get(route(base,old_id,'compare'),params={'other':new_id},headers=WRITE).status_code==409
    assert client.get(route(base,old_id,'history'),headers=WRITE).json()['items'][0]['access_status']=='revoked'
    assert revision(client,base,old_id).status_code==409


def test_large_text_and_unread_pages_never_report_a_complete_comparison(project):
    client,base,old,library=project; scope=library.scope('alice',PROJECT)
    large=revision(client,base,old['document_id'],content=b'x'*300001).json()['document_id']
    diff=client.get(route(base,old['document_id'],'compare'),params={'other':large},headers=WRITE).json()
    assert diff['truncated'] and not diff['raw_equal']
    with library.documents.connect() as db:
        db.execute('UPDATE attachments SET pages=? WHERE id=?',(json.dumps([{'text':'','needs_vision':True,'page':1,'heading':'scan'}]),large))
    diff=client.get(route(base,old['document_id'],'compare'),params={'other':large},headers=WRITE).json()
    assert diff['unread_pages']


def save_sec(library, observations, *, cik='0000000001', status='complete', version=None):
    scope=library.scope('alice',PROJECT); version=version or str(uuid4())
    raw=json.dumps({'facts':{'us-gaap':{'Revenue':{'units':{'USD':observations}}}}}).encode()
    source={'kind':'sec_companyfacts','sha256':sha256(raw).hexdigest(),'url':'https://data.sec.gov/synthetic','bytes':len(raw)}
    root=library.documents.root/'sec-snapshots'/scope/version/'raw'/'SYN'
    root.mkdir(parents=True); (root/'sec_companyfacts.json').write_bytes(raw)
    with library.documents.connect() as db:
        db.execute('INSERT INTO project_sec_versions VALUES(?,?,?)',(scope,version,json.dumps({
            'version':version,'cik':cik,'ticker':'SYN','status':status,'requested_at':'2026-09-16T00:00:00Z','sources':[source]})))
    return version


def test_sec_diff_preserves_large_values_duplicates_periods_and_filing_identity(project):
    client,base,_,library=project
    row={'val':9007199254740993,'start':'2025-01-01','end':'2025-03-31','filed':'2025-05-01','accn':'original','form':'10-Q'}
    old=save_sec(library,[row,row])
    newrow={**row,'val':9007199254740994,'accn':'amended','filed':'2025-06-01'}
    new=save_sec(library,[row,newrow])
    diff=client.get(route(base,old,'compare','sec'),params={'other':new},headers=WRITE).json()
    assert diff['added']==diff['removed']==1
    assert [r['observation']['val'] for r in diff['items']]==['9007199254740993','9007199254740994']
    assert diff['items'][0]['observation']['accn']=='original' and diff['items'][1]['observation']['accn']=='amended'
    assert all(r['unit']=='USD' and r['observation']['start']=='2025-01-01' for r in diff['items'])
    unrelated=save_sec(library,[row],cik='0000000002')
    failed=save_sec(library,[],status='failed')
    for target in [unrelated,failed]:
        assert client.get(route(base,old,'compare','sec'),params={'other':target},headers=WRITE).status_code==409
    client.put(base+f'/assets/sec/{new}/access',headers=WRITE,json={'revoked':True})
    assert client.get(route(base,old,'compare','sec'),params={'other':new},headers=WRITE).status_code==409


def test_sec_difference_pagination_is_complete_and_order_independent(project):
    client,base,_,library=project
    rows=[{'val':i,'end':'2025-12-31','filed':'2026-02-01','accn':str(i)} for i in range(70)]
    old=save_sec(library,[]); new=save_sec(library,rows); reordered=save_sec(library,list(reversed(rows)))
    diff=client.get(route(base,old,'compare','sec'),params={'other':new},headers=WRITE).json()
    assert diff['total']==70 and len(diff['items'])==50 and diff['next_offset']==50
    second=client.get(route(base,old,'compare','sec'),params={'other':new,'offset':50},headers=WRITE).json()
    assert len(second['items'])==20 and second['next_offset'] is None
    same=client.get(route(base,new,'compare','sec'),params={'other':reordered},headers=WRITE).json()
    assert same['total']==0 and not same['raw_equal']


def test_direct_dependencies_survive_revocation_and_unknown_history_is_not_safe(project,tmp_path):
    client,base,old,library=project;scope=library.scope('alice',PROJECT); old_id=old['document_id']
    store=TaskAttachmentStore(tmp_path/'tasks')
    snapshot=store.copy_project_materials(THREAD,PROJECT,[library.documents.get(scope,old_id)])[0]
    foreign=str(uuid4())
    library.save('alice',1,{'projects':index()['projects'],'assignments':{THREAD:PROJECT,foreign:PROJECT},'pinned':[]})
    origin={'thread_id':THREAD,'report_version':1,'report_digest':'a'*64,'phase':'human_completed','human_edit_count':1,
            'source_dependencies':[snapshot['project_origin']]}
    saved=library.documents.add(scope,'report.md',b'report',research_origin=origin)
    library.documents.add(scope,'legacy.md',b'old metadata',research_origin={k:v for k,v in {**origin,'report_version':2}.items() if k!='source_dependencies'})
    async def owned(thread):
        if thread!=THREAD or service_owner()!='alice':raise HTTPException(404,'missing')
    app=FastAPI();install_conversation_auth(app,backend=Identity())
    app.include_router(build_projects_router(library.documents.root,SimpleNamespace(owned_thread=owned,attachment_store=store)),prefix='/api/v1')
    live=TestClient(app)
    data=live.get(route(base,old_id,'dependencies'),headers=WRITE).json()
    assert data['tasks']==[{'thread_id':THREAD}] and data['reports'][0]['document_id']==saved['document_id']
    assert data['unknown_tasks']==data['unknown_reports']==1 and foreign not in str(data)
    library.set_access('alice',PROJECT,'document',old_id,True)
    data=live.get(route(base,old_id,'dependencies'),headers=WRITE).json()
    assert data['reports'][0]['access_status']=='dependency_unavailable' and len(data['tasks'])==1
    assert revision(live,base,saved['document_id']).status_code==409
    family=live.get(route(base,saved['document_id'],'history'),headers=WRITE).json()['items']
    assert [r['version_info']['sequence'] for r in family]==[1,2]


@pytest.mark.parametrize('failure',['missing','transport','timeout'])
def test_dependency_service_unavailable_is_unknown_not_empty_safe_result(project,failure):
    _,base,old,library=project
    library.save('alice',1,{'projects':index()['projects'],'assignments':{THREAD:PROJECT,str(uuid4()):PROJECT},'pinned':[]})
    calls=[]
    async def owned(thread):
        calls.append(thread)
        if failure=='transport':raise httpx.ConnectError('private upstream details')
        if failure=='timeout':raise TimeoutError('private upstream details')
        response=httpx.Response(404,request=httpx.Request('GET','https://internal.invalid/threads/private'))
        raise httpx.HTTPStatusError('private details',request=response.request,response=response)
    app=FastAPI();install_conversation_auth(app,backend=Identity())
    app.include_router(build_projects_router(library.documents.root,SimpleNamespace(owned_thread=owned)),prefix='/api/v1')
    result=TestClient(app).get(route(base,old['document_id'],'dependencies'),headers=WRITE)
    assert result.status_code==200 and result.json()['unknown_tasks']==2
    assert result.json()['tasks']==[] and 'private' not in result.text
    assert len(calls)==(2 if failure=='missing' else 1)
