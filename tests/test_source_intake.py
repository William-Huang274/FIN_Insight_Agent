from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys

import pytest
from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.source_intake_service import (  # noqa: E402
    SourceIntakeService,
)
from ingestion.official_source_capture import _TransportResponse  # noqa: E402
from ingestion.source_intake import (  # noqa: E402
    SourceIntakeError,
    SourceIntakePolicy,
    SourceIntakeStore,
)


POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1d_source_intake_policy_v1_0.json"
)
DELL_ROUTE = "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT"


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("test-only-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _network_snapshot(_url: str) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_source_network_path_snapshot_v1_0",
        "hostname": "investors.delltechnologies.com",
        "resolution_status": "resolved",
        "resolved_address_count": 1,
        "resolved_address_classes": ["benchmark_fake_ip"],
        "environment_proxy_configured": False,
        "windows_user_proxy_enabled": False,
        "windows_pac_configured": False,
        "route_interface": "test-tun",
        "transparent_tun_likely": True,
        "diagnostic_boundary": (
            "fake_ip_and_tunnel_route_observed_application_clients_share_transparent_path"
        ),
    }


def test_repository_source_intake_policy_is_bounded_and_identity_complete() -> None:
    policy = SourceIntakePolicy.from_path(POLICY_PATH)
    assert set(policy.routes) == {
        "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT",
        "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
    }
    assert {route.case_key for route in policy.routes.values()} == {"DELL", "TSM"}
    assert all(
        route.source_url.startswith("https://")
        and route.publication_date.startswith("2026-")
        and route.expected_content_types == ("application/pdf",)
        and route.operator_upload_enabled
        for route in policy.routes.values()
    )


def test_upload_and_automatic_driver_share_pdf_intake_and_raw_cas(
    tmp_path: Path,
) -> None:
    policy = SourceIntakePolicy.from_path(POLICY_PATH)
    body = _pdf_bytes()

    def fake_fetcher(source):  # noqa: ANN001
        assert source["route_id"] == DELL_ROUTE
        return _TransportResponse(
            status_code=200,
            final_url=str(source["url"]),
            headers={"content-type": "application/pdf"},
            redirect_chain=(),
            body=body,
            transport_attempts=1,
        )

    service = SourceIntakeService(
        policy=policy,
        private_root=tmp_path / "source-intake",
        transport_fetchers={"requests": fake_fetcher},
        network_snapshotter=_network_snapshot,
    )
    uploaded = service.upload(
        route_id=DELL_ROUTE,
        attempt_id="upload-r1",
        body=body,
        declared_content_type="application/pdf",
    )
    automatic = service.acquire_automatic(
        route_id=DELL_ROUTE,
        attempt_id="automatic-r1",
    )

    assert uploaded["status"] == automatic["status"] == "captured_ready_for_parse"
    assert uploaded["raw_object_sha256"] == automatic["raw_object_sha256"]
    assert uploaded["pdf_page_count"] == automatic["pdf_page_count"] == 1
    assert uploaded["raw_object_reused"] is False
    assert automatic["raw_object_reused"] is True
    assert uploaded["promotion_status"] == automatic["promotion_status"] == (
        "source_only_not_evidence"
    )
    assert automatic["transport"] == {
        "adapter_id": "official_http_capture_v1",
        "transport": "requests",
        "attempts": 1,
        "http_status": 200,
        "failure_code": None,
        "failure_category": None,
    }
    raw_files = list((tmp_path / "source-intake" / "raw").rglob("*.bin"))
    assert len(raw_files) == 1


def test_invalid_pdf_is_captured_privately_but_never_admitted_for_parse(
    tmp_path: Path,
) -> None:
    store = SourceIntakeStore(
        tmp_path / "source-intake",
        SourceIntakePolicy.from_path(POLICY_PATH),
    )
    result = store.ingest_pdf_bytes(
        route_id=DELL_ROUTE,
        attempt_id="fake-pdf-r1",
        body=b"<html>not a pdf</html>",
        acquisition_method="operator_upload",
        adapter_id="operator_upload_v1",
        declared_content_type="application/pdf",
    )

    assert result["status"] == "captured_rejected"
    assert result["failure_code"] == "source_intake_pdf_signature_invalid"
    assert result["pdf_page_count"] == 0
    assert result["raw_object_sha256"]
    manifest = json.loads(
        (tmp_path / "source-intake" / result["manifest_ref"]).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["source_body_is_evidence"] is False
    assert manifest["raw_object_ref"].startswith("raw/sha256/")


def test_attempt_identity_content_type_size_and_route_fail_closed(
    tmp_path: Path,
) -> None:
    policy = SourceIntakePolicy.from_path(POLICY_PATH)
    store = SourceIntakeStore(tmp_path / "source-intake", policy)
    body = _pdf_bytes()
    store.ingest_pdf_bytes(
        route_id=DELL_ROUTE,
        attempt_id="immutable-r1",
        body=body,
        acquisition_method="operator_upload",
        adapter_id="operator_upload_v1",
        declared_content_type="application/pdf",
    )
    with pytest.raises(SourceIntakeError, match="attempt_already_exists"):
        store.ingest_pdf_bytes(
            route_id=DELL_ROUTE,
            attempt_id="immutable-r1",
            body=body,
            acquisition_method="operator_upload",
            adapter_id="operator_upload_v1",
            declared_content_type="application/pdf",
        )
    rejected = store.ingest_pdf_bytes(
        route_id=DELL_ROUTE,
        attempt_id="mime-r1",
        body=body,
        acquisition_method="operator_upload",
        adapter_id="operator_upload_v1",
        declared_content_type="text/plain",
    )
    assert rejected["failure_code"] == "source_intake_declared_content_type_invalid"
    with pytest.raises(SourceIntakeError, match="route_not_found"):
        store.ingest_pdf_bytes(
            route_id="UNKNOWN",
            attempt_id="unknown-r1",
            body=body,
            acquisition_method="operator_upload",
            adapter_id="operator_upload_v1",
            declared_content_type="application/pdf",
        )


def test_truncated_and_encrypted_pdfs_are_captured_but_rejected(
    tmp_path: Path,
) -> None:
    store = SourceIntakeStore(
        tmp_path / "source-intake",
        SourceIntakePolicy.from_path(POLICY_PATH),
    )
    body = _pdf_bytes()
    eof_offset = body.rfind(b"%%EOF")
    assert eof_offset > 0
    truncated = store.ingest_pdf_bytes(
        route_id=DELL_ROUTE,
        attempt_id="truncated-r1",
        body=body[:eof_offset],
        acquisition_method="operator_upload",
        adapter_id="operator_upload_v1",
        declared_content_type="application/pdf",
    )
    encrypted = store.ingest_pdf_bytes(
        route_id=DELL_ROUTE,
        attempt_id="encrypted-r1",
        body=_encrypted_pdf_bytes(),
        acquisition_method="operator_upload",
        adapter_id="operator_upload_v1",
        declared_content_type="application/pdf",
    )

    assert truncated["status"] == "captured_rejected"
    assert truncated["failure_code"] == "source_intake_pdf_truncated"
    assert encrypted["status"] == "captured_rejected"
    assert encrypted["failure_code"] == "source_intake_pdf_encrypted"
    assert encrypted["raw_object_sha256"]


def test_policy_host_binding_and_byte_ceiling_fail_closed(tmp_path: Path) -> None:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["routes"][0]["source_url"] = "https://example.com/not-official.pdf"
    with pytest.raises(SourceIntakeError, match="policy_source_url_invalid"):
        SourceIntakePolicy.from_mapping(payload)

    bounded_payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    bounded_payload["routes"][0]["byte_ceiling"] = 1
    bounded_store = SourceIntakeStore(
        tmp_path / "source-intake",
        SourceIntakePolicy.from_mapping(bounded_payload),
    )
    with pytest.raises(SourceIntakeError, match="body_too_large"):
        bounded_store.ingest_pdf_bytes(
            route_id=DELL_ROUTE,
            attempt_id="too-large-r1",
            body=_pdf_bytes(),
            acquisition_method="operator_upload",
            adapter_id="operator_upload_v1",
            declared_content_type="application/pdf",
        )


def test_automatic_403_preserves_typed_transport_and_tun_diagnostics(
    tmp_path: Path,
) -> None:
    def fake_fetcher(source):  # noqa: ANN001
        return _TransportResponse(
            status_code=403,
            final_url=str(source["url"]),
            headers={"content-type": "text/html"},
            redirect_chain=(),
            body=b"<html>access denied</html>",
            transport_attempts=1,
        )

    service = SourceIntakeService(
        policy=SourceIntakePolicy.from_path(POLICY_PATH),
        private_root=tmp_path / "source-intake",
        transport_fetchers={"requests": fake_fetcher},
        network_snapshotter=_network_snapshot,
    )
    result = service.acquire_automatic(
        route_id=DELL_ROUTE,
        attempt_id="automatic-403-r1",
    )

    assert result["status"] == "acquisition_failed"
    assert result["failure_code"] == "official_source_http_403"
    assert result["transport"]["failure_category"] == (
        "access_control_or_origin_policy"
    )
    assert result["network_path"]["transparent_tun_likely"] is True
    assert result["raw_object_sha256"] is None
    assert result["promotion_status"] == "source_only_not_evidence"


def test_attempt_listing_never_exposes_raw_object_path(tmp_path: Path) -> None:
    service = SourceIntakeService(
        policy=SourceIntakePolicy.from_path(POLICY_PATH),
        private_root=tmp_path / "source-intake",
    )
    service.upload(
        route_id=DELL_ROUTE,
        attempt_id="list-r1",
        body=_pdf_bytes(),
        declared_content_type="application/pdf",
    )
    rows = service.attempts()
    assert len(rows) == 1
    serialized = json.dumps(rows)
    assert "raw_object_ref" not in serialized
    assert "body_base64" not in serialized
