from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.app import create_app  # noqa: E402
from apps.workbench.backend.application.source_intake_service import (  # noqa: E402
    SourceIntakeService,
)
from ingestion.source_intake import SourceIntakePolicy  # noqa: E402


POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1d_source_intake_policy_v1_0.json"
)
DELL_ROUTE = "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT"


class _FixtureEvidencePacks:
    result_digest = "a" * 64

    def list_cases(self, principal):  # pragma: no cover - product route not called
        return {"items": []}

    def get_case(self, case_key, principal):  # pragma: no cover
        raise AssertionError("unexpected fixture Evidence Pack call")


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _client(tmp_path: Path) -> TestClient:
    service = SourceIntakeService(
        policy=SourceIntakePolicy.from_path(POLICY_PATH),
        private_root=tmp_path / "source-intake",
    )
    return TestClient(
        create_app(
            store_path=tmp_path / "operations.sqlite3",
            current_research_evidence_pack_service=_FixtureEvidencePacks(),
            source_intake_service=service,
            workbench_runtime_mode="fixture",
            frontend_dist_root=tmp_path / "frontend-not-built",
        )
    )


def test_operations_source_intake_routes_and_upload_are_real_consumers(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    routes = client.get("/api/operations/source-intake/routes")
    assert routes.status_code == 200
    assert routes.json()["boundary"] == "captured_source_is_not_evidence"
    assert {row["route_id"] for row in routes.json()["routes"]} == {
        "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT",
        "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
    }

    uploaded = client.post(
        f"/api/operations/source-intake/uploads/{DELL_ROUTE}",
        params={"attempt_id": "api-upload-r1"},
        content=_pdf_bytes(),
        headers={"Content-Type": "application/pdf"},
    )
    assert uploaded.status_code == 200
    attempt = uploaded.json()["attempt"]
    assert attempt["status"] == "captured_ready_for_parse"
    assert attempt["pdf_page_count"] == 1
    assert attempt["promotion_status"] == "source_only_not_evidence"
    assert "raw_object_ref" not in uploaded.text
    assert "body_base64" not in uploaded.text

    attempts = client.get("/api/operations/source-intake/attempts")
    assert attempts.status_code == 200
    assert attempts.json()["raw_bytes_exposed"] is False
    assert attempts.json()["attempts"][0]["attempt_id"] == "api-upload-r1"


def test_upload_route_identity_and_attempt_immutability_fail_closed(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    unknown = client.post(
        "/api/operations/source-intake/uploads/UNKNOWN",
        content=_pdf_bytes(),
        headers={"Content-Type": "application/pdf"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "source_intake_route_not_found"

    first = client.post(
        f"/api/operations/source-intake/uploads/{DELL_ROUTE}",
        params={"attempt_id": "api-immutable-r1"},
        content=_pdf_bytes(),
        headers={"Content-Type": "application/pdf"},
    )
    second = client.post(
        f"/api/operations/source-intake/uploads/{DELL_ROUTE}",
        params={"attempt_id": "api-immutable-r1"},
        content=_pdf_bytes(),
        headers={"Content-Type": "application/pdf"},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "source_intake_attempt_already_exists"
