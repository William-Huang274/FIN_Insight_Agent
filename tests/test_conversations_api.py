from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.conversations import build_conversations_router, public_messages, public_message_delta, SURFACE, GRAPH


def test_public_projection_excludes_tools_and_private_reasoning():
    result = public_messages({"values": {"messages": [
        {"type": "human", "content": "Hello"},
        {"type": "ai", "content": [{"type": "reasoning", "text": "PRIVATE"}, {"type": "text", "text": "Public answer"}], "additional_kwargs": {"reasoning_content": "PRIVATE"}},
        {"type": "tool", "content": "PRIVATE SOURCE ARGUMENTS"},
    ]}})
    assert [m["content"] for m in result] == ["Hello", "Public answer"]
    assert "PRIVATE" not in str(result)
    delta = public_message_delta([{"type": "AIMessageChunk", "id": "message", "content": [
        {"type": "reasoning", "text": "PRIVATE"}, {"type": "text", "text": "Public"}],
        "additional_kwargs": {"reasoning_content": "PRIVATE"}}, {}])
    assert delta == {"id": "message", "text": "Public"}
    assert public_message_delta([{"type": "tool", "id": "tool", "content": "PRIVATE"}, {}]) is None


def test_new_and_followup_use_native_runs_and_reject_cross_surface_or_busy():
    thread_id, run_id = str(uuid4()), str(uuid4())
    writes = []
    thread = {"thread_id": thread_id, "status": "idle", "metadata": {"surface": SURFACE, "graph": GRAPH}}
    async def get(_): return thread
    async def create_thread(**kwargs): writes.append(("thread", kwargs)); return thread
    async def create_run(*args, **kwargs): writes.append(("run", kwargs)); return {"run_id": run_id}
    async def get_state(_): return {"values": {"messages": []}, "tasks": []}
    async def graph(_): return {"nodes": []}
    sdk = SimpleNamespace(threads=SimpleNamespace(get=get, create=create_thread, get_state=get_state),
        runs=SimpleNamespace(create=create_run), assistants=SimpleNamespace(get_graph=graph))
    app = FastAPI(); app.include_router(build_conversations_router(SimpleNamespace(sdk=sdk, research_profile={} or {"enabled": True})), prefix="/api/v1")
    headers = {"X-Workbench-Request": "1"}
    with TestClient(app) as client:
        assert client.post("/api/v1/conversations", json={"message": "Hi"}).status_code == 403
        assert writes == []
        assert client.post("/api/v1/conversations", headers=headers, json={"message": "Hi", "model": "deepseek-v4-pro"}).status_code == 200
        assert writes[-1][1]["config"]["configurable"]["conversation_model"] == "deepseek-v4-pro"
        assert writes[-1][1]["input"] == {"messages": [{"role": "user", "content": "Hi"}]}
        assert client.post(f"/api/v1/conversations/{thread_id}/messages", headers=headers, json={"message": "Again"}).status_code == 200
        thread["status"] = "busy"
        assert client.post(f"/api/v1/conversations/{thread_id}/messages", headers=headers, json={"message": "Duplicate"}).status_code == 409
        thread["metadata"]["surface"] = "other_surface"
        assert client.get(f"/api/v1/conversations/{thread_id}").status_code == 404
        assert len([w for w in writes if w[0]=="run"]) == 2


def test_draft_upload_stores_task_copy_without_model_or_cross_thread_access(tmp_path):
    from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
    store = TaskAttachmentStore(tmp_path)
    thread_id = str(uuid4())
    thread = {"thread_id":thread_id, "status":"idle", "metadata":{"surface":SURFACE,"graph":GRAPH}}
    async def create(**kwargs): return thread
    async def get(_): return thread
    sdk = SimpleNamespace(threads=SimpleNamespace(create=create,get=get))  # no runs capability
    app = FastAPI();app.include_router(build_conversations_router(SimpleNamespace(sdk=sdk,attachment_store=store)))
    with TestClient(app) as client:
        headers={"X-Workbench-Request":"1", "X-Filename":"notes.md"}
        assert client.post("/conversations/drafts", headers=headers, json={"title":"Read notes"}).json()["model_calls"] == 0
        path=f"/conversations/{thread_id}/attachments"
        response=client.post(path, headers=headers,content=b"# Task\nA factual note.")
        assert response.status_code == 200 and len(store.list(thread_id)) == 1
        assert store.list(str(uuid4())) == []
        thread["status"]="busy"
        assert client.post(path,headers=headers,content=b"x").status_code == 409
        thread["metadata"]["surface"]="another"
        assert client.post(path,headers=headers,content=b"x").status_code == 404
        assert len(store.list(thread_id)) == 1


def test_handoff_pins_native_checkpoint_rejects_stale_and_does_not_run_model():
    tid, cid, child = str(uuid4()), str(uuid4()), str(uuid4()); created=[]
    thread={"thread_id":tid,"status":"idle","metadata":{"surface":SURFACE,"graph":GRAPH,"title":"Original"}}
    state={"checkpoint":{"checkpoint_id":cid},"tasks":[],"values":{"messages":[{"type":"human","content":"Keep annual units"}]}}
    async def get(_):return thread
    async def get_state(_):return state
    async def create(**kwargs):created.append(kwargs);return {"thread_id":child}
    sdk=SimpleNamespace(threads=SimpleNamespace(get=get,get_state=get_state,create=create))
    app=FastAPI();app.include_router(build_conversations_router(SimpleNamespace(sdk=sdk)))
    with TestClient(app) as client:
        route=f"/conversations/{tid}/handoff"; headers={"X-Workbench-Request":"1"}
        preview=client.get(route+"-preview").json()
        assert preview["checkpoint_id"]==cid and preview["message_count"]==1
        body={"checkpoint_id":cid,"note":"Continue and retain annual units"}
        assert client.post(route,json=body).status_code==403
        assert client.post(route,headers=headers,json={**body,"checkpoint_id":str(uuid4())}).status_code==409
        state["tasks"]=[{"interrupts":[{"id":"pending"}]}]
        assert client.post(route,headers=headers,json=body).status_code==409
        state["tasks"]=[]
        assert client.post(route,headers=headers,json=body).json()=={"thread_id":child,"model_calls":0}
        assert created[0]["metadata"]["handoff"]=={"source_thread":tid,**body}
        assert "messages" not in created[0]  # no second transcript or summary


def test_approval_is_native_resume_and_rejects_stale_or_altered_permission():
    tid,cid=str(uuid4()),str(uuid4());writes=[]
    thread={"status":"interrupted","metadata":{"surface":SURFACE,"graph":GRAPH}}
    state={"checkpoint":{"checkpoint_id":cid},"tasks":[{"interrupts":[{"id":"approval-1","value":{"action_requests":[{"name":"run_isolated_python","args":{"code":"print(2)"}}]}}]}]}
    async def get(_):return thread
    async def get_state(_):return state
    async def runs(*args,**kwargs):return [{"status":"interrupted","metadata":{"model":"deepseek-v4-flash","permission_mode":"request_standard"}}]
    async def create(*args,**kwargs):writes.append(kwargs);return {"run_id":str(uuid4())}
    sdk=SimpleNamespace(threads=SimpleNamespace(get=get,get_state=get_state),runs=SimpleNamespace(list=runs,create=create))
    app=FastAPI();app.include_router(build_conversations_router(SimpleNamespace(sdk=sdk)))
    with TestClient(app) as client:
        path=f"/conversations/{tid}/approvals";headers={"X-Workbench-Request":"1"}
        body={"checkpoint_id":cid,"interrupt_id":"approval-1","decisions":["approve"]}
        assert client.post(path,json=body).status_code==403
        assert client.post(path,headers=headers,json={**body,"permission_mode":"full_access"}).status_code==422
        assert client.post(path,headers=headers,json={**body,"checkpoint_id":str(uuid4())}).status_code==409
        assert not writes
        assert client.post(path,headers=headers,json=body).status_code==200
        assert writes[0]["command"]=={"resume":{"approval-1":{"decisions":[{"type":"approve"}]}}}
        assert writes[0]["config"]["configurable"]["permission_mode"]=="request_standard"
        state["tasks"]=[]
        assert client.post(path,headers=headers,json=body).status_code==409
