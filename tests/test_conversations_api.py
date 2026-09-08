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
