"""The configuration desk reads bounded public resources; it never starts runs."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.workbench.backend.api.v1.report_sessions import build_report_sessions_router


def test_studio_public_methods_and_native_topology_only():
    graph = AsyncMock(return_value={"nodes": [{"id": "writer", "data": {"internal": "not_public"}}],
        "edges": [{"source": "writer", "target": "end", "data": "not_public", "conditional": True}]})
    app = FastAPI()
    app.include_router(build_report_sessions_router(SimpleNamespace(sdk=SimpleNamespace(assistants=SimpleNamespace(get_graph=graph)))))
    with TestClient(app) as client:
        methods = client.get("/research-studio").json()
        assert {m["method_id"] for m in methods["methods"]} == {"lead", "finance", "industry_product", "counter", "writer", "verifier"}
        assert all(m["content"] and m["grants_authority"] is False for m in methods["methods"])
        assert methods["editable_runtime"] is False
        result = client.get("/research-studio/graph/research")
        assert result.status_code == 200
        assert result.json()["nodes"] == [{"id": "writer"}]
        assert "not_public" not in result.text
        graph.assert_awaited_once_with("research_session")
        assert client.get("/research-studio/graph/arbitrary").status_code == 422
        assert client.post("/research-studio", json={"method": "replace"}).status_code == 405
        assert client.get("/research-studio/graph/review").json()["graph_id"] == 'report_session'
