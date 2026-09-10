from types import SimpleNamespace
from uuid import uuid4
import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.workbench.backend.api.v1.conversations import build_conversations_router, SURFACE, GRAPH
from apps.workbench.backend.api.v1.working_notes import working_notes_view
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.user_context import user_context_prompt


def test_direct_edits_are_scoped_versioned_and_do_not_start_model(tmp_path,monkeypatch):
    path=tmp_path/'notes.sqlite';monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(path))
    tid=str(uuid4());thread={'status':'idle','metadata':{'surface':SURFACE,'graph':GRAPH,'owner_id':'local-pilot'}}
    async def get(_):return thread
    app=FastAPI();app.include_router(build_conversations_router(SimpleNamespace(sdk=SimpleNamespace(threads=SimpleNamespace(get=get)))))
    memory=WorkingMemory(path,owner='local-pilot',workspace=tid,actor='cash-analyst')
    note=memory.save('现金观察','原始正文')
    with TestClient(app) as client:
        root=f'/conversations/{tid}';headers={'X-Workbench-Request':'1'}
        assert client.put(root+'/user-context',json={'body':'只做观察','version':0}).status_code==403
        assert client.put(root+'/user-context',json={'body':'只做观察','version':0},headers=headers).status_code==200
        assert '只做观察' in user_context_prompt('local-pilot',tid)
        assert client.put(root+'/user-context',json={'body':'等待附注，不继续检索','version':1},headers=headers).status_code==200
        prompt=user_context_prompt('local-pilot',tid)
        assert '等待附注' in prompt and '只做观察' not in prompt and '不授予' in prompt
        assert client.put(root+'/user-context',json={'body':'过期覆盖','version':1},headers=headers).status_code==409
        cleared=client.put(root+'/user-context',json={'body':'','version':2},headers=headers)
        assert cleared.status_code==200 and cleared.json()['version']==3
        assert user_context_prompt('local-pilot',tid)==''
        r=client.put(root+'/working-notes',json={'note_id':note['note_id'],'version':1,'body':'用户直接修改的正文'},headers=headers)
        assert r.status_code==200 and r.json()['version']==2
        assert memory.read(note['note_id'],version=1)['body']=='原始正文'
        assert memory.read(note['note_id'])['actor']=='cash-analyst'
        assert client.put(root+'/working-notes',json={'note_id':note['note_id'],'version':1,'body':'旧请求'},headers=headers).status_code==409
        thread['status']='busy'
        assert client.put(root+'/user-context',json={'body':'运行中修改','version':3},headers=headers).status_code==409
        thread['metadata']['owner_id']='someone-else'
        assert client.get(root+'/user-context').status_code==404
        assert client.put(root+'/working-notes',json={'note_id':note['note_id'],'version':2,'body':'他人修改'},headers=headers).status_code==404


def test_old_checkpoint_papers_are_readable_without_memory_migration(tmp_path,monkeypatch):
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.sqlite'))
    state={'values':{'case_papers':[{'agent_id':'analyst','task':{'branch_id':'Q1_ISSUER_TRUTH'},
        'notebook':{'messages':['PRIVATE_REASONING']},'final_submission':{'thesis':'收入兑现观察','narrative_markdown':'已形成的正文',
            'claims':[{'statement':'有待核查'}],'open_gaps':['需要附注']}}]}}
    async def run():
        catalog=await working_notes_view('task','alice',checkpoint=state)
        row=catalog['checkpoint_items'][0]
        assert row['actor']=='Q1_ISSUER_TRUTH' and row['editable'] is False
        note=await working_notes_view('task','alice',note_id=row['id'],checkpoint=state)
        assert '已形成的正文' in note['body'] and '需要附注' in note['body']
        assert 'PRIVATE_REASONING' not in str(catalog)+str(note)
        assert catalog['items']==[]
        assert (await working_notes_view('task','alice',query='无匹配',checkpoint=state))['checkpoint_items']==[]
    asyncio.run(run())


def test_human_correction_keeps_original_paper_visible():
    from apps.workbench.backend.application.checkpoint_papers import checkpoint_papers
    state={'values':{'case_papers':[{'agent_id':'analyst','final_submission':{'thesis':'现金观察','narrative_markdown':'原件'}}],
        'human_edits':[{'number':1,'papers':[{'paper_id':'P01','actor':'analyst','title':'现金观察','after':'第一次'}]},
            {'number':2,'papers':[{'paper_id':'P01','actor':'analyst','title':'现金观察','after':'最新人工正文'}]}]}}
    rows=checkpoint_papers(state)
    assert len(rows)==2 and rows[0]['body']=='最新人工正文' and rows[1]['body']=='原件'
    assert '人工修改 2 次' in rows[0]['origin'] and rows[0]['actor']=='analyst'
