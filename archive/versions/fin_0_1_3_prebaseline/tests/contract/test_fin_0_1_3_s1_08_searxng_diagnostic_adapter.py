from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_searxng_diagnostic_adapter import (
    SearXNGDiagnosticAdapter,
    SearXNGDiagnosticError,
    SearXNGDiagnosticQuery,
    SearXNGDiagnosticResponse,
    UrllibSearXNGDiagnosticTransport,
    canonicalize_diagnostic_locator,
    load_searxng_diagnostic_policy,
    validate_searxng_diagnostic_result,
)


POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_searxng_diagnostic_provider_policy_v1_0.json"


class FixtureTransport:
    live_network = False

    def __init__(
        self,
        payload: object | None = None,
        *,
        status_code: int = 200,
        final_url: str = "",
        body_ceiling_exceeded: bool = False,
        error_code: str = "",
    ) -> None:
        self.payload = {"results": []} if payload is None else payload
        self.status_code = status_code
        self.final_url = final_url
        self.body_ceiling_exceeded = body_ceiling_exceeded
        self.error_code = error_code
        self.calls: list[dict[str, object]] = []

    def fetch(self, *, url, headers, timeout_seconds, byte_ceiling):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
                "byte_ceiling": byte_ceiling,
            }
        )
        if self.error_code:
            raise SearXNGDiagnosticError(self.error_code)
        body = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return SearXNGDiagnosticResponse(
            status_code=self.status_code,
            final_url=self.final_url or url,
            headers={"content-type": "application/json"},
            body=body,
            body_ceiling_exceeded=self.body_ceiling_exceeded,
        )


def _query(case_key: str = "DELL", *, query_id: str = "Q1") -> SearXNGDiagnosticQuery:
    return SearXNGDiagnosticQuery.create(
        query_id=query_id,
        case_key=case_key,
        evidence_slot_id=f"{case_key.lower()}_broad_web_locator",
        query_text=f"{case_key} AI infrastructure customer demand official source",
        categories=("general", "news"),
        time_range="year",
        result_ceiling=20,
    )


def _success_payload() -> dict[str, object]:
    return {
        "query": "DELL AI infrastructure",
        "results": [
            {
                "url": "https://Example.com/research/report?utm_source=test&b=2&a=1#section",
                "title": "Short title",
                "content": "A shorter locator snippet.",
                "publishedDate": "2026-07-20T00:00:00",
                "engines": ["brave"],
                "positions": [2],
                "score": 1.5,
            },
            {
                "url": "https://example.com/research/report?a=1&b=2",
                "title": "A more complete report title",
                "content": "A longer locator snippet that remains a candidate and is not financial evidence.",
                "published_date": "2026-07-20",
                "engine": "duckduckgo",
                "engines": ["duckduckgo"],
                "positions": [1],
                "score": 2.0,
            },
            {
                "url": "javascript:alert(1)",
                "title": "invalid",
            },
        ],
        "unresponsive_engines": [["google", "CAPTCHA"], ["bing", "timeout"]],
    }


def test_success_merges_engine_lineage_captures_raw_response_and_forbids_promotion(
    tmp_path: Path,
) -> None:
    policy = load_searxng_diagnostic_policy(POLICY)
    transport = FixtureTransport(_success_payload())
    adapter = SearXNGDiagnosticAdapter(
        policy=policy,
        runtime_root=tmp_path,
        transport=transport,
    )
    result = adapter.search(_query())
    validate_searxng_diagnostic_result(result)

    assert result["status"] == "completed"
    assert result["terminal_code"] == "diagnostic_locators_materialized"
    assert result["observed_counts"] == {
        "upstream_raw_results": 3,
        "normalized_locators": 1,
        "query_calls": 1,
        "network_calls": 0,
        "model_calls": 0,
        "provider_model_calls": 0,
        "evidence_promotions": 0,
    }
    locator = result["locators"][0]
    assert locator["canonical_locator"] == "https://example.com/research/report?a=1&b=2"
    assert locator["source_engines"] == ["brave", "duckduckgo"]
    assert locator["best_rank_candidate"] == 1
    assert locator["promotion_status"] == "diagnostic_locator_only"
    assert locator["evidence_promotion_allowed"] is False
    assert locator["writer_citable"] is False
    assert locator["numeric_authority"] == "none"
    assert result["rejection_codes"] == ["searxng_locator_url_invalid"]
    assert result["unresponsive_engines"] == [
        {"engine": "bing", "reason": "timeout"},
        {"engine": "google", "reason": "CAPTCHA"},
    ]
    assert len(adapter.capture_refs) == 3
    response_capture = adapter.store.get_json(
        result["response_capture"]["object_key"],
        expected_digest=result["response_capture"]["digest"],
    )
    assert json.loads(base64.b64decode(response_capture["body_base64"])) == _success_payload()
    assert response_capture["capture_before_parse"] is True
    assert response_capture["credential_cookie_authorization_present"] is False
    assert "Authorization" not in transport.calls[0]["headers"]
    assert "Cookie" not in transport.calls[0]["headers"]


def test_locator_bundle_is_stable_when_explicit_engine_positions_are_permuted(
    tmp_path: Path,
) -> None:
    policy = load_searxng_diagnostic_policy(POLICY)
    forward = _success_payload()
    reverse = deepcopy(forward)
    reverse["results"] = list(reversed(reverse["results"]))
    first = SearXNGDiagnosticAdapter(
        policy=policy,
        runtime_root=tmp_path / "a",
        transport=FixtureTransport(forward),
    ).search(_query())
    second = SearXNGDiagnosticAdapter(
        policy=policy,
        runtime_root=tmp_path / "b",
        transport=FixtureTransport(reverse),
    ).search(_query())
    assert first["locator_bundle_digest"] == second["locator_bundle_digest"]
    assert first["locators"] == second["locators"]


@pytest.mark.parametrize(
    ("transport", "terminal_code"),
    [
        (FixtureTransport(status_code=403), "searxng_json_format_disabled_or_forbidden"),
        (FixtureTransport(status_code=429), "searxng_rate_limited"),
        (FixtureTransport(status_code=502), "searxng_http_502"),
        (FixtureTransport(body_ceiling_exceeded=True), "searxng_body_ceiling_exceeded"),
        (FixtureTransport(b"not-json"), "searxng_response_invalid_json"),
        (FixtureTransport({"answers": []}), "searxng_response_schema_drift"),
    ],
)
def test_http_parse_and_body_failures_are_typed_and_capture_first(
    tmp_path: Path, transport: FixtureTransport, terminal_code: str
) -> None:
    adapter = SearXNGDiagnosticAdapter(
        policy=load_searxng_diagnostic_policy(POLICY),
        runtime_root=tmp_path,
        transport=transport,
    )
    result = adapter.search(_query())
    assert result["status"] == "failed"
    assert result["terminal_code"] == terminal_code
    assert len(adapter.capture_refs) == 3
    response = adapter.store.get_json(result["response_capture"]["object_key"])
    assert response["capture_before_parse"] is True
    assert response["capture_kind"] == "diagnostic_search_response"


def test_transport_failure_preserves_request_and_typed_failure_capture(tmp_path: Path) -> None:
    adapter = SearXNGDiagnosticAdapter(
        policy=load_searxng_diagnostic_policy(POLICY),
        runtime_root=tmp_path,
        transport=FixtureTransport(error_code="searxng_transport_unavailable"),
    )
    result = adapter.search(_query())
    assert result["status"] == "failed"
    assert result["terminal_code"] == "searxng_transport_unavailable"
    failure = adapter.store.get_json(result["response_capture"]["object_key"])
    assert failure["capture_kind"] == "diagnostic_search_transport_failure"
    assert failure["capture_before_parse"] is True
    assert len(adapter.capture_refs) == 3


def test_unknown_case_and_call_budget_fail_before_extra_transport(tmp_path: Path) -> None:
    transport = FixtureTransport()
    adapter = SearXNGDiagnosticAdapter(
        policy=load_searxng_diagnostic_policy(POLICY),
        runtime_root=tmp_path,
        transport=transport,
    )
    with pytest.raises(SearXNGDiagnosticError, match="searxng_cross_case_or_unknown_case"):
        adapter.search(_query("AMD"))
    assert transport.calls == []

    for index, case_key in enumerate(("DELL", "MU", "NVDA"), start=1):
        adapter.search(_query(case_key, query_id=f"Q{index}"))
    with pytest.raises(SearXNGDiagnosticError, match="searxng_query_call_ceiling_exceeded"):
        adapter.search(_query("DELL", query_id="Q4"))
    assert len(transport.calls) == 3
    assert adapter.network_calls == 0


def test_three_case_full_fake_route_never_promotes_locator_to_evidence(tmp_path: Path) -> None:
    transport = FixtureTransport(
        {
            "results": [
                {
                    "url": "https://example.org/current-research",
                    "title": "Current research locator",
                    "content": "Revenue 999 is untrusted locator text and remains non-citable.",
                    "engines": ["brave", "duckduckgo"],
                    "positions": [1, 2],
                }
            ]
        }
    )
    adapter = SearXNGDiagnosticAdapter(
        policy=load_searxng_diagnostic_policy(POLICY),
        runtime_root=tmp_path,
        transport=transport,
    )
    results = [
        adapter.search(_query(case_key, query_id=f"{case_key}-Q1"))
        for case_key in ("DELL", "MU", "NVDA")
    ]
    assert all(row["status"] == "completed" for row in results)
    assert all(row["observed_counts"]["evidence_promotions"] == 0 for row in results)
    assert all(row["locators"][0]["financial_fact_authority"] is False for row in results)
    assert adapter.query_calls == 3
    assert adapter.network_calls == 0


def test_result_and_policy_mutations_cannot_grant_evidence_authority(tmp_path: Path) -> None:
    policy = load_searxng_diagnostic_policy(POLICY)
    result = SearXNGDiagnosticAdapter(
        policy=policy,
        runtime_root=tmp_path,
        transport=FixtureTransport(_success_payload()),
    ).search(_query())
    mutated = deepcopy(result)
    mutated["locators"][0]["writer_citable"] = True
    locator_body = dict(mutated["locators"][0])
    locator_body.pop("locator_digest")
    mutated["locators"][0]["locator_digest"] = canonical_digest(locator_body)
    mutated["locator_bundle_digest"] = canonical_digest(mutated["locators"])
    result_body = dict(mutated)
    result_body.pop("result_digest")
    mutated["result_digest"] = canonical_digest(result_body)
    with pytest.raises(SearXNGDiagnosticError, match="searxng_locator_false_promotion"):
        validate_searxng_diagnostic_result(mutated)

    bad_policy = deepcopy(policy)
    bad_policy["capability_boundary"]["evidence_promotion_allowed"] = True
    with pytest.raises(SearXNGDiagnosticError, match="searxng_policy_false_promotion"):
        SearXNGDiagnosticAdapter(
            policy=bad_policy,
            runtime_root=tmp_path / "bad-policy",
            transport=FixtureTransport(),
        )


def test_final_origin_drift_is_typed_after_raw_capture(tmp_path: Path) -> None:
    adapter = SearXNGDiagnosticAdapter(
        policy=load_searxng_diagnostic_policy(POLICY),
        runtime_root=tmp_path,
        transport=FixtureTransport(final_url="https://public.example/search?format=json"),
    )
    result = adapter.search(_query())
    assert result["terminal_code"] == "searxng_final_origin_drift"
    assert result["locators"] == []
    assert len(adapter.capture_refs) == 3


def test_loopback_transport_and_locator_canonicalizer_fail_closed() -> None:
    UrllibSearXNGDiagnosticTransport(base_url="http://127.0.0.1:8888")
    with pytest.raises(SearXNGDiagnosticError, match="searxng_base_url_not_loopback"):
        UrllibSearXNGDiagnosticTransport(base_url="https://searx.example.com")
    with pytest.raises(SearXNGDiagnosticError, match="searxng_locator_credentials_forbidden"):
        canonicalize_diagnostic_locator("https://user:secret@example.com/a")
    assert (
        canonicalize_diagnostic_locator(
            "HTTPS://EXAMPLE.COM:443/a?utm_campaign=x&token=secret&z=2&a=1#frag"
        )
        == "https://example.com/a?a=1&z=2"
    )


def test_local_deployment_has_fixed_fanout_and_non_search_healthcheck() -> None:
    compose = (ROOT / "deploy/searxng-diagnostic/docker-compose.yml").read_text(encoding="utf-8")
    settings = (ROOT / "deploy/searxng-diagnostic/settings.yml").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts/dev/start_searxng_diagnostic.ps1").read_text(encoding="utf-8")
    policy = load_searxng_diagnostic_policy(POLICY)

    assert '"127.0.0.1:8888:8080"' in compose
    assert "http://127.0.0.1:8080/" in compose
    assert "/search" not in compose
    assert "keep_only:" in settings
    assert all(f"- {engine}" in settings for engine in ("bing", "brave", "duckduckgo", "google"))
    assert policy["metasearch_fanout_contract"] == {
        "configured_engines": ["bing", "brave", "duckduckgo", "google"],
        "fin_to_searxng_query_calls_exactly_enforced": True,
        "searxng_to_upstream_http_requests_exactly_enforced": False,
        "unresponsive_engine_lineage_required": True,
        "healthcheck_may_invoke_search": False,
    }
    assert "RandomNumberGenerator]::Fill" not in launcher
    assert "[Convert]::ToHexString" not in launcher
