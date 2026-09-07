"""Historical report reads use native checkpoints and remain task scoped."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import httpx

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.report_sessions import ReportSessionService, build_report_sessions_router


def version_app():
    thread, foreign, old_id, new_id, pending_id = [str(uuid4()) for _ in range(5)]
    source = {"source_id": "NUMFACT::fixture", "value_decimal": "12", "unit": "USD", "numeric_fact_authority": True}
    old = {"checkpoint": {"checkpoint_id": old_id}, "next": ["human_review"], "created_at": "2026-09-01T00:00:00Z",
        "values": {"report_version": 1, "phase": "needs_revision", "report_revision_reason": "初始研究",
            "report": {"title": "旧报告", "narrative_markdown": "旧结论。[NUMFACT::fixture]",
                "citations": {"NUMFACT::fixture": {"claim": {}, "sources": [source]}}, "charts": []},
            "private_messages": "PRIVATE_SENTINEL_MUST_NOT_LEAVE_SERVER"}}
    new = deepcopy(old)
    new.update(checkpoint={"checkpoint_id": new_id})
    new["values"].update(report_version=2, report_revision_reason="根据现金流来源修订")
    new["values"]["report"].update(title="新报告", narrative_markdown="修订结论。[NUMFACT::fixture]")
    pending = deepcopy(new)
    pending.update(checkpoint={"checkpoint_id": pending_id}, next=["verifier"])
    pending["values"]["report"]["narrative_markdown"] = "尚未复核的中间结果"
    calls = []
    async def get(tid):
        return {"metadata": {"surface": "dell_report_workbench" if tid == thread else "another_surface"}}
    async def history(tid, **kwargs):
        calls.append((tid, kwargs))
        return [pending, new, deepcopy(new), old]
    async def state(tid, checkpoint_id=None):
        return deepcopy({old_id: old, new_id: new, pending_id: pending}.get(checkpoint_id, new))
    service = ReportSessionService("http://127.0.0.1:8123", None,
        sdk=SimpleNamespace(threads=SimpleNamespace(get=get, get_history=history, get_state=state)))
    def native_history(request):
        assert request.method == "GET" and request.url.path == f"/threads/{thread}/history"
        assert request.url.params == httpx.QueryParams({"limit": 10, "before": new_id})
        calls.append((thread, dict(request.url.params)))
        return httpx.Response(200, json=[old])
    service.http = httpx.AsyncClient(base_url="http://127.0.0.1:8123", transport=httpx.MockTransport(native_history))
    app = FastAPI()
    app.include_router(build_report_sessions_router(service), prefix="/api/v1")
    return app, thread, foreign, old_id, new_id, pending_id, calls


def test_versions_exclude_intermediate_outputs_deduplicate_and_hide_private_state():
    app, tid, foreign, old, new, pending, calls = version_app()
    with TestClient(app) as client:
        result = client.get(f"/api/v1/research-sessions/{tid}/report-versions")
        assert result.status_code == 200
        assert [v["version"] for v in result.json()["versions"]] == [2, 1]
        assert "PRIVATE_SENTINEL" not in result.text
        assert client.get(f"/api/v1/research-sessions/{tid}/report-versions/{pending}").status_code == 404
        count = len(calls)
        assert client.get(f"/api/v1/research-sessions/{foreign}/report-versions").status_code == 404
        assert len(calls) == count


def test_older_versions_use_native_get_cursor_and_check_thread_ownership_first():
    app, tid, foreign, old, new, _, calls = version_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/research-sessions/{tid}/report-versions", params={"before": new})
        assert response.status_code == 200
        assert response.json() == {"versions": [{"version": 1, "checkpoint_id": old,
            "created_at": "2026-09-01T00:00:00Z", "title": "旧报告", "reason": "初始研究"}], "next_cursor": None}
        count = len(calls)
        assert client.get(f"/api/v1/research-sessions/{foreign}/report-versions", params={"before": new}).status_code == 404
        assert len(calls) == count


def test_version_diff_export_and_source_use_the_selected_snapshot():
    app, tid, _, old, new, _, _ = version_app()
    base = f"/api/v1/research-sessions/{tid}"
    with TestClient(app) as client:
        result = client.get(f"{base}/report-diff", params={"before": old})
        assert result.status_code == 200
        assert "-旧结论" in result.json()["diff"] and "+修订结论" in result.json()["diff"]
        assert result.json()["reason"] == "根据现金流来源修订"
        historical = client.get(f"{base}/report-versions/{old}")
        assert historical.json()["report_version"] == 1 and "PRIVATE_SENTINEL" not in historical.text
        exported = client.get(f"{base}/report/export/md", params={"checkpoint_id": old})
        assert "旧结论" in exported.text and "修订结论" not in exported.text
        source = client.get(f"{base}/source", params={"source_id": "NUMFACT::fixture", "checkpoint_id": old})
        assert source.status_code == 200 and source.json()["value_decimal"] == "12"
        assert client.get(f"{base}/source", params={"source_id": "NUMFACT::other", "checkpoint_id": old}).status_code == 404
        assert client.get(f"{base}/report-versions/{new}").json()["report"]["title"] == "新报告"
