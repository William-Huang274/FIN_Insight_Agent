from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.research_feedback import build_research_feedback_router
from apps.workbench.backend.authentication import service_owner
from sec_agent.agent_runtime.research_feedback import ResearchFeedbackStore, bind_issues
from test_research_feedback import action, observations


def test_feedback_api_permissions_run_binding_and_opinion_only(tmp_path):
    thread,run,other=map(str,(uuid4(),uuid4(),uuid4()))
    rows=bind_issues(action(),observations(),run_id=run,snapshot_id='s')
    store=ResearchFeedbackStore(tmp_path/'research-feedback.sqlite'); store.save(service_owner(),thread,rows)
    async def owned(t):
        if str(t)!=thread: raise HTTPException(404,'not found')
        return {'metadata':{}}
    async def state(t): return {'values':{'orientation_run_id':run,'research_orientation':{'overview':'test'}}}
    app=FastAPI();app.include_router(build_research_feedback_router(SimpleNamespace(
        audit_root=tmp_path,attachment_store=None,owned_thread=owned,state=state)))
    base=f'/research-sessions/{thread}/research-feedback'
    with TestClient(app) as client:
        assert client.get(base,params={'run_id':run}).json()['orientation']['overview']=='test'
        assert client.get(base,params={'run_id':other}).json()=={'items':[], 'orientation':None,
            'notice':'疑点与用户意见尚待核查；不会自动改写关系库或启动模型。'}
        assert client.get(base.replace(thread,other)).status_code==404
        payload={'submission_id':'attempt-123','content_digest':rows[0]['content_digest'],'choice':'request_check'}
        assert client.post(base+'/'+rows[0]['record_id'],json=payload).status_code==403
        assert client.post(base+'/'+rows[0]['record_id'],json=payload,headers={'x-workbench-request':'1','origin':'https://evil.invalid'}).status_code==403
        response=client.post(base+'/'+rows[0]['record_id'],json=payload,headers={'x-workbench-request':'1'})
        assert response.status_code==200
        assert response.json()['opinion']['execution_status']=='recorded_not_executed'
