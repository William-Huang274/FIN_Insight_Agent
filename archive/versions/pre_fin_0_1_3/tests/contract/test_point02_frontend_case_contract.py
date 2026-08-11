from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "configs" / "releases" / "point02_api_v1_openapi_baseline_v1_1.json"
CLIENT_PATH = REPO_ROOT / "apps" / "workbench" / "frontend" / "vite" / "src" / "api" / "cases.ts"
APP_SHELL_PATH = REPO_ROOT / "apps" / "workbench" / "frontend" / "vite" / "src" / "app" / "AppShell.tsx"


def test_typed_frontend_case_client_matches_v1_1_case_routes_and_dtos() -> None:
    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    source = CLIENT_PATH.read_text(encoding="utf-8")

    assert set(openapi["paths"]).issuperset({"/cases", "/cases/{case_id}"})
    assert re.search(r'CASES_PATH\s*=\s*"/api/v1/cases"', source)
    assert 'this.request<CaseWorkspaceProjection>(CASES_PATH' in source
    assert 'method: "POST"' in source
    assert 'this.request<TaskCenterProjection>(CASES_PATH)' in source
    assert '`${CASES_PATH}/${encodeURIComponent(caseId)}`' in source
    assert 'X-Fin-Case-Expected-Version' in source

    command_fields = openapi["components"]["schemas"]["CreateCaseDraftCommand"]["required"]
    workspace_fields = openapi["components"]["schemas"]["CaseWorkspaceProjection"]["required"]
    for field in command_fields + workspace_fields:
        assert re.search(rf"\b{field}\b", source)


def test_case_shell_consumes_typed_client_and_renders_base_remote_states() -> None:
    source = APP_SHELL_PATH.read_text(encoding="utf-8")

    for token in (
        "CaseApiClient",
        "listCases",
        "createCase",
        "getCase",
        "loading",
        "empty",
        "permission",
        "stale",
        "conflict",
        "reconnect",
        "/cases/new",
        "/cases/",
    ):
        assert token in source
