from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from ingestion.official_source_capture import (  # noqa: E402
    OfficialSourceCaptureError,
    _TransportResponse,
    capture_plan,
    validate_capture_plan,
)


class _FakeResponse:
    status_code = 200
    url = "https://official.example.test/report.htm"
    headers = {"content-type": "text/html", "authorization": "forbidden"}
    history: list[object] = []

    def iter_content(self, chunk_size: int):  # noqa: ARG002
        yield b"<html><body>official source</body></html>"


class _FakeSession:
    def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ARG002
        return _FakeResponse()


def _plan() -> dict[str, object]:
    return {
        "schema_version": "fin_ia_s1b_official_source_capture_plan_v1_0",
        "status": "s1b_official_source_capture_plan",
        "policy": {
            "capture_before_parse": True,
            "https_only": True,
            "credentials_forbidden": True,
        },
        "sources": [
            {
                "case_key": "DELL",
                "route_id": "DELL_TEST_OFFICIAL",
                "url": "https://official.example.test/report.htm",
                "allowed_hosts": ["official.example.test"],
                "expected_content_types": ["text/html"],
                "transport": "requests",
                "max_transport_retries": 0,
                "timeout_seconds": 10,
                "byte_ceiling": 1000,
            }
        ],
    }


def test_capture_is_persisted_before_parse_without_sensitive_headers(
    tmp_path: Path,
) -> None:
    result = capture_plan(
        _plan(),
        output_root=tmp_path,
        attempt_id="r1",
        session=_FakeSession(),
    )

    assert result["status"] == "s1b_official_sources_captured"
    assert result["source_routes_executed"] == 1
    assert result["network_attempts_lower_bound"] == 1
    row = result["sources"][0]
    capture = json.loads(
        Path(row["response_capture"]["object_ref"]).read_text(encoding="utf-8")
    )
    assert capture["capture_before_parse"] is True
    assert capture["credential_cookie_authorization_present"] is False
    assert capture["headers"] == {"content-type": "text/html"}
    assert "forbidden" not in json.dumps(capture).lower()


def test_attempt_id_is_immutable(tmp_path: Path) -> None:
    capture_plan(
        _plan(),
        output_root=tmp_path,
        attempt_id="r1",
        session=_FakeSession(),
    )
    with pytest.raises(
        OfficialSourceCaptureError,
        match="attempt_already_exists",
    ):
        capture_plan(
            _plan(),
            output_root=tmp_path,
            attempt_id="r1",
            session=_FakeSession(),
        )


def test_non_https_or_unallowlisted_source_fails_closed() -> None:
    plan = _plan()
    source = plan["sources"][0]
    source["url"] = "http://untrusted.example.test/report.htm"
    with pytest.raises(OfficialSourceCaptureError, match="source_invalid"):
        validate_capture_plan(plan)


def test_repository_capture_plan_is_bounded_to_three_official_routes() -> None:
    plan = validate_capture_plan(
        json.loads(
            (
                ROOT
                / "configs"
                / "retrieval"
                / "fin_ia_0_1_3_s1b_official_source_capture_plan_v1_0.json"
            ).read_text(encoding="utf-8")
        )
    )
    assert len(plan["sources"]) == 3
    assert {row["case_key"] for row in plan["sources"]} == {
        "DELL",
        "MU",
        "NVDA",
    }
    assert plan["policy"]["bounded_addendum_not_general_crawler"] is True


def _successor_plan() -> dict[str, object]:
    plan = _plan()
    plan["schema_version"] = "fin_ia_s1d_official_source_capture_plan_v1_1"
    plan["status"] = "s1d_official_source_capture_plan"
    plan["sources"][0]["transport"] = "playwright_api_request"
    return plan


def test_playwright_successor_is_capture_first_with_injected_zero_network_fetcher(
    tmp_path: Path,
) -> None:
    body = b"%PDF-1.7 hermetic official source"

    def fake_fetcher(source):  # noqa: ANN001
        assert source["transport"] == "playwright_api_request"
        return _TransportResponse(
            status_code=200,
            final_url=str(source["url"]),
            headers={"content-type": "text/html", "authorization": "forbidden"},
            redirect_chain=(),
            body=body,
            transport_attempts=1,
        )

    result = capture_plan(
        _successor_plan(),
        output_root=tmp_path,
        attempt_id="successor-r1",
        transport_fetchers={"playwright_api_request": fake_fetcher},
    )

    assert result["status"] == "s1d_official_sources_captured"
    row = result["sources"][0]
    capture = json.loads(
        Path(row["response_capture"]["object_ref"]).read_text(encoding="utf-8")
    )
    assert capture["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert capture["headers"] == {"content-type": "text/html"}
    assert capture["capture_before_parse"] is True


def test_legacy_plan_cannot_silently_enable_playwright_transport() -> None:
    plan = _plan()
    plan["sources"][0]["transport"] = "playwright_api_request"
    with pytest.raises(OfficialSourceCaptureError, match="source_invalid"):
        validate_capture_plan(plan)


def test_repository_s1d_plan_is_bounded_to_dell_and_tsm_official_pdfs() -> None:
    plan = validate_capture_plan(
        json.loads(
            (
                ROOT
                / "configs"
                / "retrieval"
                / "fin_ia_0_1_3_s1d_official_source_capture_plan_v1_1.json"
            ).read_text(encoding="utf-8")
        )
    )
    assert {row["case_key"] for row in plan["sources"]} == {"DELL", "TSM"}
    assert all(row["transport"] == "playwright_api_request" for row in plan["sources"])
    assert plan["policy"]["broad_web_search_forbidden"] is True


def test_browser_download_plan_requires_allowlisted_discovery_and_bound_link() -> None:
    plan = _successor_plan()
    plan["schema_version"] = "fin_ia_s1d_official_source_browser_capture_plan_v1_2"
    plan["sources"][0].update(
        {
            "transport": "playwright_browser_download",
            "discovery_url": "https://official.example.test/results",
            "expected_download_url": "https://official.example.test/report.htm",
            "link_selector": "a[href='/report.htm']",
        }
    )
    assert validate_capture_plan(plan)["sources"][0]["discovery_url"].endswith(
        "/results"
    )

    plan["sources"][0]["discovery_url"] = "https://untrusted.example.test/results"
    with pytest.raises(OfficialSourceCaptureError, match="source_invalid"):
        validate_capture_plan(plan)


def test_repository_browser_download_successor_is_two_official_routes() -> None:
    plan = validate_capture_plan(
        json.loads(
            (
                ROOT
                / "configs"
                / "retrieval"
                / "fin_ia_0_1_3_s1d_official_source_browser_capture_plan_v1_2.json"
            ).read_text(encoding="utf-8")
        )
    )
    assert {row["case_key"] for row in plan["sources"]} == {"DELL", "TSM"}
    assert all(
        row["transport"] == "playwright_browser_download"
        and row["discovery_url"].startswith("https://")
        and row["expected_download_url"] == row["url"]
        for row in plan["sources"]
    )
