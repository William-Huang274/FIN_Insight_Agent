from __future__ import annotations

import asyncio
import json
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from scripts.qualification.run_dell_external_exact_url_qualification import (
    DEFAULT_CONFIG,
    QualificationRunFailed,
    load_config,
    run_qualification,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research_foundation.external_sources import (
    ExaHostedMCPPageFetcher,
    ExternalSourceError,
    ExternalSourceCapture,
    FetchedPage,
    PublicURLGuard,
)


_NOW = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)


class _UnusedFetcher:
    async def fetch(self, _url: str, *, timeout_seconds: float) -> FetchedPage:
        raise AssertionError(f"unused transport called with timeout={timeout_seconds}")


class _MappingHostedFetcher:
    def __init__(self, pages: dict[str, str], *, substitute_url: str | None = None):
        self.pages = pages
        self.substitute_url = substitute_url
        self.calls: list[str] = []

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        assert timeout_seconds == 60.0
        self.calls.append(url)
        return FetchedPage(
            final_url=self.substitute_url or url,
            extracted_text=self.pages[url],
            status_code=200,
            content_type="text/markdown; transport=exa_web_fetch",
        )


class _FakeMCPClient:
    def __init__(self, text: str):
        self.text = text
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        return {
            "isError": False,
            "content": [{"type": "text", "text": self.text}],
        }


class _FakeClientContext(AbstractAsyncContextManager[_FakeMCPClient]):
    def __init__(self, client: _FakeMCPClient):
        self.client = client

    async def __aenter__(self) -> _FakeMCPClient:
        return self.client

    async def __aexit__(self, *_: Any) -> None:
        return None


def _config(path: Path, routes: list[dict[str, Any]]) -> Path:
    body = {
        "schema_version": "fin_ia_dell_external_exact_url_qualification_config_v1_0",
        "status": "frozen_zero_model_exact_url_qualification",
        "case_id": "DELL_AI_INFRA_REFERENCE_VERTICAL",
        "research_as_of": "2026-09-02T00:00:00Z",
        "data_snapshot_id": "test_exact_routes_v1",
        "transport": "exa_hosted_web_fetch",
        "capture_authority": "qualification_only",
        "production_status": "HOLD",
        "candidate_is_not_evidence": True,
        "model_calls_authorized": False,
        "fail_fast": True,
        "routes": routes,
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _route(route_id: str, url: str, marker: str) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "branch_id": "Q5_SUPPLY_AND_PRICE",
        "official_url": url,
        "source_identity": {
            "publisher": "Official Publisher",
            "document_title": f"Official Document {route_id}",
            "source_period": "2026 Q2",
            "official_domain": "example.com",
        },
        "identity_marker_groups": [
            {"group_id": "publisher", "any_of": ["Official Publisher"]},
            {"group_id": "title", "any_of": [f"Official Document {route_id}"]},
        ],
        "content_marker_groups": [
            {"group_id": "content", "any_of": [marker]},
        ],
        "minimum_useful_characters": 200,
        "max_characters": 500,
    }


def _capture(hosted: Any) -> ExternalSourceCapture:
    guard = PublicURLGuard(resolver=lambda _host: ("93.184.216.34",))
    return ExternalSourceCapture(
        guard=guard,
        static_fetcher=_UnusedFetcher(),
        hosted_fetcher=hosted,
        browser_fetcher=None,
        extractor=lambda html: html,
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )


def _page_text(route_id: str, marker: str) -> str:
    return (
        f"# Official Document {route_id}\n"
        "Official Publisher\n\n"
        f"{marker}. "
        + "Bounded official source content. " * 18
    )


def test_frozen_default_config_is_exact_four_route_zero_model_contract() -> None:
    config, _file_sha256 = load_config(DEFAULT_CONFIG)

    assert [row.route_id for row in config.routes] == [
        "E01_OPENAI_GPT56_COMPUTE",
        "E02_TSMC_2Q26_TRANSCRIPT",
        "E03_MICRON_Q3_FY26_PREPARED_REMARKS",
        "E04_DELL_Q1_FY27_PERFORMANCE_REVIEW",
    ]
    assert config.model_calls_authorized is False
    assert config.candidate_is_not_evidence is True
    assert config.fail_fast is True
    assert all(row.official_url.startswith("https://") for row in config.routes)


def test_zero_model_exact_url_runner_writes_replayable_pass_bundle(
    tmp_path: Path,
) -> None:
    routes = [
        _route("E01_ROUTE_ONE", "https://example.com/e01", "Marker one"),
        _route("E02_ROUTE_TWO", "https://example.com/e02", "Marker two"),
        _route("E03_ROUTE_THREE", "https://example.com/e03", "Marker three"),
        _route("E04_ROUTE_FOUR", "https://example.com/e04", "Marker four"),
    ]
    config = _config(tmp_path / "config.json", routes)
    pages = {
        route["official_url"]: _page_text(route["route_id"], f"Marker {word}")
        for route, word in zip(routes, ("one", "two", "three", "four"), strict=True)
    }
    hosted = _MappingHostedFetcher(pages)

    manifest_path = asyncio.run(
        run_qualification(
            config_path=config,
            output_root=tmp_path / "out",
            attempt_id="dell_external_exact_url_test_r1",
            capture=_capture(hosted),
            clock=lambda: _NOW,
        )
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "PASS"
    assert manifest["declared_route_count"] == 4
    assert manifest["passed_route_count"] == 4
    assert manifest["model_calls"] == 0
    assert manifest["deepseek_calls"] == 0
    assert manifest["paid_calls"] == 0
    assert manifest["hosted_transport_internal_model_usage_observable"] is False
    assert len(manifest["implementation"]["runner_sha256"]) == 64
    assert len(manifest["implementation"]["external_sources_sha256"]) == 64
    assert manifest["candidate_is_not_evidence"] is True
    assert manifest["evidence_admission_authorized"] is False
    assert manifest["mcp_promotion_authorized"] is False
    assert manifest["manifest_digest"] == canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifest_digest"}
    )
    assert hosted.calls == [route["official_url"] for route in routes]
    for route in routes:
        route_dir = manifest_path.parent / "routes" / route["route_id"]
        result = json.loads((route_dir / "route_result.json").read_text("utf-8"))
        text = (route_dir / "captured_text.txt").read_bytes()
        assert result["status"] == "PASS"
        assert result["candidate_is_not_evidence"] is True
        assert result["bounded_text_sha256"] == sha256(text).hexdigest()
        assert result["bounded_text_bytes"] == len(text)


def test_runner_fails_fast_and_preserves_missing_marker_artifact(
    tmp_path: Path,
) -> None:
    first = _route("E01_ROUTE_ONE", "https://example.com/e01", "Required marker")
    second = _route("E02_ROUTE_TWO", "https://example.com/e02", "Second marker")
    config = _config(tmp_path / "config.json", [first, second])
    hosted = _MappingHostedFetcher(
        {
            first["official_url"]: _page_text(first["route_id"], "Wrong content"),
            second["official_url"]: _page_text(second["route_id"], "Second marker"),
        }
    )

    with pytest.raises(QualificationRunFailed) as error:
        asyncio.run(
            run_qualification(
                config_path=config,
                output_root=tmp_path / "out",
                attempt_id="dell_external_exact_url_test_fail_r1",
                capture=_capture(hosted),
                clock=lambda: _NOW,
            )
        )

    manifest = json.loads(error.value.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "FAIL"
    assert manifest["attempted_route_count"] == 1
    assert manifest["passed_route_count"] == 0
    assert manifest["terminal_failure_code"] == "content_marker_missing:content"
    assert manifest["candidate_is_not_evidence"] is True
    assert manifest["route_results"][0]["exact_url_bound"] is True
    assert manifest["route_results"][0]["identity_marker_groups_passed"] is True
    assert manifest["route_results"][0]["content_marker_groups_passed"] is False
    assert manifest["route_results"][0]["matched_identity_markers"]
    assert hosted.calls == [first["official_url"]]
    assert (
        error.value.manifest_path.parent
        / "routes"
        / first["route_id"]
        / "captured_text.txt"
    ).is_file()


def test_runner_rejects_final_url_substitution_even_with_matching_text(
    tmp_path: Path,
) -> None:
    route = _route("E01_ROUTE_ONE", "https://example.com/e01", "Required marker")
    config = _config(tmp_path / "config.json", [route])
    hosted = _MappingHostedFetcher(
        {route["official_url"]: _page_text(route["route_id"], "Required marker")},
        substitute_url="https://example.com/nearby",
    )

    with pytest.raises(QualificationRunFailed) as error:
        asyncio.run(
            run_qualification(
                config_path=config,
                output_root=tmp_path / "out",
                attempt_id="dell_external_exact_url_test_substitution_r1",
                capture=_capture(hosted),
                clock=lambda: _NOW,
            )
        )

    manifest = json.loads(error.value.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "FAIL"
    assert manifest["terminal_failure_code"] == "captured_exact_url_binding_mismatch"
    assert manifest["evidence_admission_authorized"] is False


def test_existing_exa_fetcher_rejects_exact_url_substitution_before_runner() -> None:
    requested = "https://example.com/exact"
    client = _FakeMCPClient(
        "# Nearby document\nURL: https://example.com/nearby\n\nOfficial text."
    )
    fetcher = ExaHostedMCPPageFetcher(
        guard=PublicURLGuard(resolver=lambda _host: ("93.184.216.34",)),
        client_factory=lambda: _FakeClientContext(client),
    )

    with pytest.raises(ExternalSourceError) as error:
        asyncio.run(fetcher.fetch(requested, timeout_seconds=20))

    assert getattr(error.value, "code", None) == "exa_mcp_web_fetch_url_mismatch"
