from pathlib import Path

from fastapi.testclient import TestClient

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_workspace_service import (
    ResearchWorkspaceService,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {
    "X-Fin-Product-Mode": "current",
    "X-Fin-Case-Permissions": "current_product:read",
}


def _client_without_private_objects(tmp_path: Path) -> TestClient:
    projection = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    evidence = ResearchEvidencePackService(
        config=projection,
        result=read_registered_runtime_json(
            ROOT, str(projection["source_result_resource_id"])
        ),
        private_object_root=tmp_path / "empty-object-root",
        private_root_base=tmp_path / "empty-private-root",
        reviewed_anchor_catalog=read_registered_runtime_json(
            ROOT,
            str(projection["reviewed_anchor_catalog_resource_id"]),
        ),
    )
    workspace = ResearchWorkspaceService(
        config=read_registered_runtime_json(
            ROOT, "application.config.current_research_workspace_catalog"
        ),
        evidence_packs=evidence,
    )
    return TestClient(
        create_app(
            store_path=tmp_path / "workbench.sqlite3",
            current_research_evidence_pack_service=evidence,
            research_workspace_service=workspace,
            workbench_runtime_mode="fixture",
        )
    )


def test_missing_product_data_is_visible_before_case_navigation(tmp_path: Path) -> None:
    client = _client_without_private_objects(tmp_path)

    readiness = client.get("/api/readiness")
    assert readiness.status_code == 503
    assert readiness.json()["status"] == "data_mount_required"
    assert readiness.json()["unavailable_case_keys"] == ["DELL", "MU", "NVDA"]

    listed = client.get("/api/v1/research-cases", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()["evidence_objects_ready"] is False
    assert all(
        row["evidence_object_ready"] is False
        and row["available_surfaces"] == []
        for row in listed.json()["items"]
    )

    detail = client.get(
        "/api/v1/research-cases/case_dell_current", headers=HEADERS
    )
    assert detail.status_code == 503
    assert detail.json()["detail"]["reason"] == (
        "current_research_evidence_pack_object_unavailable"
    )
