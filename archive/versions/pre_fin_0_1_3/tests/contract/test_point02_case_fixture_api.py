from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.app import create_app


def _headers(*, tenant: str = "tenant_fixture", permissions: str = "case:read,case:create") -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": tenant,
        "X-Fin-Case-Project": "project_fixture",
        "X-Fin-Case-Actor": "analyst_fixture",
        "X-Fin-Case-Permissions": permissions,
        "X-Trace-Id": "trace_point02_fixture",
    }


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    fixture_root = tmp_path / "p02-fixture"
    service = CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT)
    return TestClient(create_app(store_path=tmp_path / "workbench.sqlite", p02_case_service=service)), fixture_root


def _create_payload(*, query: str = "Compare accelerator demand") -> dict[str, str]:
    return {
        "query": query,
        "as_of": "2026-07-18T00:00:00Z",
        "language": "en",
        "source_policy_ref": "fixture:internal",
        "idempotency_key": "case-create-001",
    }


def test_fixture_case_api_create_list_get_and_reopen_keep_identity_and_version(tmp_path: Path) -> None:
    client, fixture_root = _client(tmp_path)

    created = client.post("/api/v1/cases", headers=_headers(), json=_create_payload())

    assert created.status_code == 202
    workspace = created.json()
    assert set(workspace) == {
        "case_id",
        "case_version",
        "summary_version",
        "query",
        "as_of",
        "language",
        "planning_checkpoint_state",
    }
    assert workspace["case_version"] == 1
    assert workspace["summary_version"] == 1
    assert workspace["query"] == "Compare accelerator demand"
    assert workspace["language"] == "en"
    assert workspace["planning_checkpoint_state"] == "legacy_authority_retained"
    assert created.headers["etag"] == '"case-version=1"'

    repeated = client.post("/api/v1/cases", headers=_headers(), json=_create_payload())
    assert repeated.status_code == 202
    assert repeated.json() == workspace

    listed = client.get("/api/v1/cases", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["next_cursor"] is None
    assert len(listed.json()["items"]) == 1
    task_center_row = listed.json()["items"][0]
    assert task_center_row["case_id"] == workspace["case_id"]
    assert task_center_row["case_version"] == 1
    assert task_center_row["query"] == workspace["query"]
    assert task_center_row["status"] == "shadow_created"
    assert task_center_row["updated_at"]

    fetched = client.get(f"/api/v1/cases/{workspace['case_id']}", headers=_headers())
    assert fetched.status_code == 200
    assert fetched.json() == workspace

    refresh_entrypoint = client.get(f"/cases/{workspace['case_id']}/overview")
    assert refresh_entrypoint.status_code == 200
    assert 'id="root"' in refresh_entrypoint.text

    reopened = TestClient(
        create_app(
            store_path=tmp_path / "reopened-workbench.sqlite",
            p02_case_service=CaseService.for_fixture_root(fixture_root, repo_root=REPO_ROOT),
        )
    )
    reread = reopened.get(f"/api/v1/cases/{workspace['case_id']}", headers=_headers())
    assert reread.status_code == 200
    assert reread.json() == workspace
    assert (fixture_root / "canonical.sqlite").is_file()
    object_snapshots = list((fixture_root / "objects").rglob("*.json"))
    assert len(object_snapshots) == 1
    assert json.loads(object_snapshots[0].read_text(encoding="utf-8")) == workspace


def test_fixture_case_api_is_fail_closed_for_permissions_tenants_and_stale_reads(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    created = client.post("/api/v1/cases", headers=_headers(), json=_create_payload())
    assert created.status_code == 202
    case_id = created.json()["case_id"]

    missing_permission = client.get(f"/api/v1/cases/{case_id}", headers=_headers(permissions="case:create"))
    assert missing_permission.status_code == 403
    assert missing_permission.json()["error"]["error_code"] == "permission_denied"

    cross_tenant_list = client.get("/api/v1/cases", headers=_headers(tenant="tenant_other"))
    assert cross_tenant_list.status_code == 200
    assert cross_tenant_list.json() == {"items": [], "next_cursor": None}

    cross_tenant_get = client.get(f"/api/v1/cases/{case_id}", headers=_headers(tenant="tenant_other"))
    assert cross_tenant_get.status_code == 404
    assert cross_tenant_get.json()["error"]["error_code"] == "case_not_found"

    stale = client.get(
        f"/api/v1/cases/{case_id}",
        headers={**_headers(), "X-Fin-Case-Expected-Version": "0"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["error_code"] == "version_conflict"
    assert stale.json()["detail"]["current_version"] == 1

    idempotency_conflict = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json=_create_payload(query="Different request with reused key"),
    )
    assert idempotency_conflict.status_code == 409
    assert idempotency_conflict.json()["error"]["error_code"] == "idempotency_conflict"


def test_case_api_is_not_admitted_without_an_explicit_fixture_service(tmp_path: Path) -> None:
    client = TestClient(create_app(store_path=tmp_path / "workbench.sqlite"))

    response = client.post("/api/v1/cases", headers=_headers(), json=_create_payload())

    assert response.status_code == 403
    assert response.json()["error"]["error_code"] == "operation_not_admitted"


def test_runtime_openapi_binds_case_operations_to_the_v1_1_dto_names(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    document = client.get("/openapi.json").json()

    create_operation = document["paths"]["/api/v1/cases"]["post"]
    list_operation = document["paths"]["/api/v1/cases"]["get"]
    get_operation = document["paths"]["/api/v1/cases/{case_id}"]["get"]
    assert create_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/CreateCaseDraftCommand"
    assert create_operation["responses"]["202"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/CaseWorkspaceProjection"
    assert list_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/TaskCenterProjection"
    assert get_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/CaseWorkspaceProjection"
