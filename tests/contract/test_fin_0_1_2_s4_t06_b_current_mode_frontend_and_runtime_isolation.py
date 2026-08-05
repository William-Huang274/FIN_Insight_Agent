from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from scripts.releases.materialize_fin_ia_0_1_2_s4_t06_b_current_frontend_and_runtime_isolation import (
    OUTPUT as IMPLEMENTATION_RECORD,
    materialize,
)
from sec_agent.canonical_runtime.models import canonical_digest


READ_HEADERS = {
    "X-Fin-Product-Mode": "current",
    "X-Fin-Case-Permissions": "current_product:read",
}


def _case_service(tmp_path: Path, suffix: str) -> CaseService:
    return CaseService.for_fixture_root(
        tmp_path / f"canonical-{suffix}", repo_root=REPO_ROOT
    )


def test_runtime_modes_are_explicit_and_preserve_current_default(tmp_path: Path) -> None:
    current = create_app(
        tmp_path / "current.sqlite",
        p02_case_service=_case_service(tmp_path, "current"),
    )
    fixture = create_app(
        tmp_path / "fixture.sqlite",
        p02_case_service=_case_service(tmp_path, "fixture"),
        workbench_runtime_mode="fixture",
    )

    assert current.state.workbench_runtime_mode == "current"
    assert current.state.background_dispatch_enabled is True
    assert fixture.state.workbench_runtime_mode == "fixture"
    assert fixture.state.background_dispatch_enabled is False


def test_invalid_runtime_mode_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="workbench_runtime_mode_invalid"):
        create_app(
            tmp_path / "invalid.sqlite",
            p02_case_service=_case_service(tmp_path, "invalid"),
            workbench_runtime_mode="mixed",  # type: ignore[arg-type]
        )


def test_current_projection_remains_available_in_fixture_runtime_mode(
    tmp_path: Path,
) -> None:
    app = create_app(
        tmp_path / "fixture.sqlite",
        p02_case_service=_case_service(tmp_path, "projection"),
        workbench_runtime_mode="fixture",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/current-product/cases", headers=READ_HEADERS)
        denied = client.get(
            "/api/v1/current-product/cases",
            headers={"X-Fin-Product-Mode": "fixture"},
        )

    assert response.status_code == 200
    assert response.json()["projection_mode"] == "current"
    assert [row["case_key"] for row in response.json()["items"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == "current_product_mode_required"


def test_frontend_current_route_and_get_only_api_are_registered(tmp_path: Path) -> None:
    app = create_app(
        tmp_path / "fixture.sqlite",
        p02_case_service=_case_service(tmp_path, "routes"),
        workbench_runtime_mode="fixture",
    )
    route_methods = {
        route.path: frozenset(route.methods or ())
        for route in app.routes
        if route.path.startswith("/api/v1/current-product")
    }

    assert route_methods == {
        "/api/v1/current-product/cases": frozenset({"GET"}),
        "/api/v1/current-product/cases/{case_key}": frozenset({"GET"}),
        "/api/v1/current-product/cases/{case_key}/{surface}": frozenset({"GET"}),
    }
    frontend_routes = {route.path for route in app.routes}
    assert "/current" in frontend_routes
    assert "/current/{frontend_path:path}" in frontend_routes


def test_current_frontend_never_uses_fixture_principal_or_write_methods() -> None:
    api_source = (
        REPO_ROOT
        / "apps/workbench/frontend/vite/src/api/currentProduct.ts"
    ).read_text(encoding="utf-8")
    shell_source = (
        REPO_ROOT
        / "apps/workbench/frontend/vite/src/app/CurrentProductWorkbench.tsx"
    ).read_text(encoding="utf-8")

    assert '"X-Fin-Product-Mode": "current"' in api_source
    assert '"X-Fin-Case-Permissions": "current_product:read"' in api_source
    assert 'method: "GET"' in api_source
    assert "fixture_internal" not in api_source
    assert "fixture_internal" not in shell_source
    assert "fetch(" in api_source
    assert "POST" not in api_source
    assert "PATCH" not in api_source
    assert "DELETE" not in api_source


def test_T06_B_implementation_record_is_digest_bound_and_rebuilds_exactly() -> None:
    stored = json.loads(IMPLEMENTATION_RECORD.read_text(encoding="utf-8"))
    assert stored["record_digest"] == canonical_digest(
        {key: value for key, value in stored.items() if key != "record_digest"}
    )
    for binding in stored["code_and_test_bindings"]:
        path = REPO_ROOT / binding["ref"]
        assert path.stat().st_size == binding["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
    assert materialize() == stored
