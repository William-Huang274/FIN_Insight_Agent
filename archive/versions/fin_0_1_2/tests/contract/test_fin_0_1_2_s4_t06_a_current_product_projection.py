from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "src")]

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_product_projection import (
    CURRENT_PRODUCT_CASE_KEYS,
    CURRENT_PRODUCT_SURFACES,
    CurrentProductPrincipal,
    CurrentProductProjectionError,
    CurrentProductProjectionService,
    validate_current_product_projection_manifest,
)
DEFAULT_MANIFEST_OUTPUT = REPO_ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_a_current_product_projection_"
    "manifest_v1_0.json"
)
from sec_agent.canonical_runtime.models import canonical_digest


READ_HEADERS = {
    "X-Fin-Product-Mode": "current",
    "X-Fin-Case-Permissions": "current_product:read",
}


@pytest.fixture()
def manifest() -> dict[str, Any]:
    return json.loads(DEFAULT_MANIFEST_OUTPUT.read_text(encoding="utf-8"))


@pytest.fixture()
def service() -> CurrentProductProjectionService:
    return CurrentProductProjectionService.from_repository(REPO_ROOT)


@pytest.fixture()
def api(tmp_path: Path) -> SimpleNamespace:
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=CaseService.unavailable("fixture_not_in_T06_A"),
    )
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, root=tmp_path)


def _recompute_view_case_manifest(
    value: dict[str, Any], case_index: int, surface: str
) -> None:
    view = value["cases"][case_index]["views"][surface]
    view["view_digest"] = canonical_digest(
        {key: item for key, item in view.items() if key != "view_digest"}
    )
    case = value["cases"][case_index]
    case["case_projection_digest"] = canonical_digest(
        {
            key: item
            for key, item in case.items()
            if key != "case_projection_digest"
        }
    )
    value["manifest_digest"] = canonical_digest(
        {
            key: item
            for key, item in value.items()
            if key != "manifest_digest"
        }
    )


def _forbidden_product_paths(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in {
                "authorization",
                "capture_objects",
                "credential",
                "cookie",
                "object_key",
                "provider_output",
                "raw_provider_response",
                "request_headers",
                "response_headers",
            } or "private_reasoning" in normalized:
                found.append("/".join((*path, str(key))))
            found.extend(_forbidden_product_paths(item, (*path, str(key))))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden_product_paths(item, (*path, str(index))))
    elif isinstance(value, str):
        normalized = value.replace("\\", "/").lower()
        if ".codex_runtime" in normalized or "restricted-provider-captures" in normalized:
            found.append("/".join(path))
    return found


def test_manifest_is_self_consistent_and_registry_loaded_without_attempt_runtime(
    manifest: dict[str, Any], service: CurrentProductProjectionService
) -> None:
    assert validate_current_product_projection_manifest(manifest) == manifest
    assert service.manifest_digest == manifest["manifest_digest"]
    assert [row["case_key"] for row in manifest["cases"]] == list(
        CURRENT_PRODUCT_CASE_KEYS
    )
    assert ".codex_runtime" not in json.dumps(manifest, ensure_ascii=False)


def test_manifest_projects_all_required_surfaces_without_raw_runtime_content(
    manifest: dict[str, Any]
) -> None:
    assert _forbidden_product_paths(manifest) == []
    for case in manifest["cases"]:
        assert tuple(case["views"]) == CURRENT_PRODUCT_SURFACES
        assert case["source_anchors"]["exact_result"].get("ref") is None
        assert len(case["views"]["evidence"]["data"]["rows"]) == 15
        assert len(case["views"]["numeric"]["data"]["rows"]) == 3
        assert len(case["views"]["gaps"]["data"]["rows"]) == 3
        assert case["views"]["run"]["data"]["raw_content_exposed"] is False
        assert case["views"]["trace"]["data"]["raw_content_exposed"] is False


def test_three_case_business_identity_and_graph_typed_empty(
    manifest: dict[str, Any]
) -> None:
    for case in manifest["cases"]:
        case_key = case["case_key"]
        evidence = case["views"]["evidence"]["data"]["rows"]
        numeric = case["views"]["numeric"]["data"]["rows"]
        assert {row["entity_ref"] for row in evidence} == {case_key}
        assert {row["entity_ref"] for row in numeric} == {case_key}
        assert case["views"]["graph"]["data"] == {
            "status": "typed_empty_no_approved_current_graph_evidence",
            "nodes": [],
            "edges": [],
            "reason": "approved_current_evidence_pack_contains_no_graph_evidence",
        }


def test_manifest_digest_mutation_fails_closed(manifest: dict[str, Any]) -> None:
    mutated = deepcopy(manifest)
    mutated["cases"][0]["views"]["case"]["data"]["ticker"] = "MU"
    with pytest.raises(
        CurrentProductProjectionError,
        match="current_product_projection_manifest_identity_or_digest_invalid",
    ):
        validate_current_product_projection_manifest(mutated)


def test_cross_case_mutation_fails_after_all_digests_are_recomputed(
    manifest: dict[str, Any]
) -> None:
    mutated = deepcopy(manifest)
    mutated["cases"][0]["views"]["evidence"]["data"]["rows"][0][
        "entity_ref"
    ] = "MU"
    _recompute_view_case_manifest(mutated, 0, "evidence")
    with pytest.raises(
        CurrentProductProjectionError,
        match="current_product_projection_business_row_shape_invalid",
    ):
        validate_current_product_projection_manifest(mutated)


def test_graph_fabrication_fails_after_all_digests_are_recomputed(
    manifest: dict[str, Any]
) -> None:
    mutated = deepcopy(manifest)
    mutated["cases"][2]["views"]["graph"]["data"]["edges"] = [
        {"from": "NVDA", "to": "MU"}
    ]
    _recompute_view_case_manifest(mutated, 2, "graph")
    with pytest.raises(
        CurrentProductProjectionError,
        match="current_product_projection_graph_must_remain_typed_empty",
    ):
        validate_current_product_projection_manifest(mutated)


def test_raw_capture_reference_fails_after_all_digests_are_recomputed(
    manifest: dict[str, Any]
) -> None:
    mutated = deepcopy(manifest)
    mutated["cases"][1]["views"]["trace"]["data"]["capture_objects"] = []
    _recompute_view_case_manifest(mutated, 1, "trace")
    with pytest.raises(
        CurrentProductProjectionError,
        match="current_product_projection_forbidden_raw_surface",
    ):
        validate_current_product_projection_manifest(mutated)


def test_service_requires_explicit_current_mode_and_permission(
    service: CurrentProductProjectionService,
) -> None:
    with pytest.raises(CurrentProductProjectionError, match="current_product_mode_required"):
        service.list_cases(CurrentProductPrincipal("fixture", frozenset({"current_product:read"})))
    with pytest.raises(
        CurrentProductProjectionError,
        match="current_product_read_permission_required",
    ):
        service.list_cases(CurrentProductPrincipal("current", frozenset()))


def test_service_returns_defensive_read_only_copies(
    service: CurrentProductProjectionService,
) -> None:
    principal = CurrentProductPrincipal(
        "current", frozenset({"current_product:read"})
    )
    first = service.get_surface("DELL", "evidence", principal)
    first["data"]["rows"][0]["entity_ref"] = "MU"
    second = service.get_surface("DELL", "evidence", principal)
    assert second["data"]["rows"][0]["entity_ref"] == "DELL"
    assert first["view_digest"] == second["view_digest"]


def test_api_operates_with_fixture_case_service_unavailable_and_is_read_only(
    api: SimpleNamespace,
) -> None:
    before = DEFAULT_MANIFEST_OUTPUT.read_bytes()
    listed = api.client.get("/api/v1/current-product/cases", headers=READ_HEADERS)
    assert listed.status_code == 200, listed.text
    assert [row["case_key"] for row in listed.json()["items"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]
    for surface in CURRENT_PRODUCT_SURFACES:
        response = api.client.get(
            f"/api/v1/current-product/cases/MU/{surface}",
            headers=READ_HEADERS,
        )
        assert response.status_code == 200, response.text
        assert response.json()["surface"] == surface
    assert DEFAULT_MANIFEST_OUTPUT.read_bytes() == before


def test_api_fails_closed_on_fixture_mode_permission_and_unknown_case(
    api: SimpleNamespace,
) -> None:
    fixture = api.client.get(
        "/api/v1/current-product/cases",
        headers={**READ_HEADERS, "X-Fin-Product-Mode": "fixture"},
    )
    denied = api.client.get(
        "/api/v1/current-product/cases",
        headers={"X-Fin-Product-Mode": "current"},
    )
    unknown = api.client.get(
        "/api/v1/current-product/cases/AMD",
        headers=READ_HEADERS,
    )
    assert fixture.status_code == 403
    assert fixture.json()["detail"]["reason"] == "current_product_mode_required"
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == (
        "current_product_read_permission_required"
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["reason"] == "current_product_case_not_found"


def test_openapi_keeps_business_projection_get_only_and_namespaces_control_writes(
    api: SimpleNamespace,
) -> None:
    paths = api.client.get("/openapi.json").json()["paths"]
    current_paths = {
        path: operations
        for path, operations in paths.items()
        if path.startswith("/api/v1/current-product")
    }
    assert {
        "/api/v1/current-product/cases",
        "/api/v1/current-product/cases/{case_key}",
        "/api/v1/current-product/cases/{case_key}/review-control",
        "/api/v1/current-product/cases/{case_key}/return-requests",
        "/api/v1/current-product/cases/{case_key}/{surface}",
    }.issubset(current_paths)
    assert set(current_paths["/api/v1/current-product/cases"]) == {"get"}
    assert set(current_paths["/api/v1/current-product/cases/{case_key}"]) == {
        "get"
    }
    assert set(
        current_paths["/api/v1/current-product/cases/{case_key}/{surface}"]
    ) == {"get"}
    assert set(
        current_paths[
            "/api/v1/current-product/cases/{case_key}/review-control"
        ]
    ) == {"get"}
    assert set(
        current_paths[
            "/api/v1/current-product/cases/{case_key}/return-requests"
        ]
    ) == {"post"}
