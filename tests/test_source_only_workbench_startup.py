"""A public checkout can start without treating missing data as qualified."""
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackService, ResearchEvidencePackServiceError,
)


def test_source_only_startup_exposes_catalog_but_refuses_product_data(tmp_path, monkeypatch):
    monkeypatch.setenv("FINSIGHT_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("FINSIGHT_REPORT_SESSION_API_URL", raising=False)
    from apps.workbench.backend.app import create_app
    headers = {"X-Fin-Product-Mode": "current", "X-Fin-Case-Permissions": "current_product:read"}
    with TestClient(create_app(store_path=tmp_path / "workspace.sqlite")) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/readiness").status_code == 503
        catalog = client.get("/api/v1/research-cases", headers=headers)
        assert catalog.status_code == 200
        detail = client.get("/api/v1/current-research/evidence-packs/DELL", headers=headers)
        assert detail.status_code == 503
        assert "current_s1_product_readiness_private_result_missing" in detail.text
        assert str(tmp_path) not in detail.text


def test_wrong_digest_is_not_treated_as_a_missing_mount(tmp_path):
    target = tmp_path / "review.json"
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(ResearchEvidencePackServiceError) as error:
        ResearchEvidencePackService._load_product_readiness_private_result(
            private_base=Path(tmp_path), repo_relative_ref="data/workbench_private/review.json",
            expected_sha256="0" * 64, case_key="DELL",
        )
    assert error.value.error_code == "current_s1_product_readiness_private_result_unavailable"
