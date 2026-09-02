from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import pytest
import requests

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research_foundation.contracts import (
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.external_sources import (
    DDGSDiagnosticProvider,
    ExaHostedMCPPageFetcher,
    ExaHostedMCPProvider,
    ExternalCaptureRequest,
    ExternalSearchRequest,
    ExternalSourceCapture,
    ExternalSourceDiscovery,
    ExternalSourceError,
    FetchedPage,
    PlaywrightPageFetcher,
    ProviderHit,
    PublicURLGuard,
    StaticHTTPPageFetcher,
)


_NOW = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc)


def _run_scope(*branches: str):
    return bind_dell_research_method(
        load_dell_reference_vertical_foundation(),
        branches,
        research_as_of=_NOW,
        data_snapshot_id="DELL-FOUNDATION-TEST-SNAPSHOT-01",
        execution_attempt_id="DELL-TEST-A01",
    ).run_scope


class _FakeExaClient:
    def __init__(self, text: str, *, structured: Any = None) -> None:
        self.text = text
        self.structured = structured
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        result = {
            "is_error": False,
            "content": [{"type": "text", "text": self.text}],
        }
        if self.structured is not None:
            result["structuredContent"] = self.structured
        return result


class _FakeClientContext(AbstractAsyncContextManager[_FakeExaClient]):
    def __init__(self, client: _FakeExaClient) -> None:
        self.client = client

    async def __aenter__(self) -> _FakeExaClient:
        return self.client

    async def __aexit__(self, *_: Any) -> None:
        return None


class _FailingProvider:
    provider_id = "primary"

    async def search(self, request: ExternalSearchRequest) -> tuple[ProviderHit, ...]:
        raise ExternalSourceError("primary_unavailable")


class _StaticProvider:
    provider_id = "primary"

    async def search(self, request: ExternalSearchRequest) -> tuple[ProviderHit, ...]:
        return (
            ProviderHit(
                title="Dell filing",
                url="https://investors.delltechnologies.com/a?utm_source=test",
                snippet="locator snippet",
                published_at="2026-08-01",
            ),
            ProviderHit(
                title="Off-domain",
                url="https://example.com/not-accepted",
                snippet="filtered",
            ),
        )


class _SingleURLProvider:
    provider_id = "single_url"

    def __init__(self, url: str) -> None:
        self.url = url

    async def search(self, request: ExternalSearchRequest) -> tuple[ProviderHit, ...]:
        return (ProviderHit(title="Bound candidate", url=self.url),)


class _FakeFetcher:
    def __init__(self, page: FetchedPage | ExternalSourceError) -> None:
        self.page = page
        self.calls: list[str] = []

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        self.calls.append(url)
        if isinstance(self.page, ExternalSourceError):
            raise self.page
        return self.page


class _FakeRoute:
    def __init__(self) -> None:
        self.aborted = False
        self.continued = False

    async def abort(self) -> None:
        self.aborted = True

    async def continue_(self) -> None:
        self.continued = True


class _FakeRequest:
    def __init__(self, url: str) -> None:
        self.url = url


class _OversizedResponse:
    is_redirect = False
    is_permanent_redirect = False
    headers = {"Content-Length": "101", "Content-Type": "text/html"}
    url = "https://example.com/"
    status_code = 200
    encoding = "utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, *, chunk_size: int):
        yield b"x" * 101


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get(self, *_: Any, **__: Any) -> _OversizedResponse:
        return _OversizedResponse()


class _ForbiddenResponse(_OversizedResponse):
    headers = {"Content-Length": "20", "Content-Type": "text/html"}
    status_code = 403


class _ForbiddenSession(_FakeSession):
    def get(self, *_: Any, **__: Any) -> _ForbiddenResponse:
        return _ForbiddenResponse()


class _NotModifiedResponse(_OversizedResponse):
    headers = {"Content-Length": "0", "Content-Type": "text/html"}
    status_code = 304


class _NotModifiedSession(_FakeSession):
    def get(self, *_: Any, **__: Any) -> _NotModifiedResponse:
        return _NotModifiedResponse()


class _TimeoutSession(_FakeSession):
    def get(self, *_: Any, **__: Any) -> _ForbiddenResponse:
        raise requests.Timeout("fixture timeout")


def _public_guard() -> PublicURLGuard:
    return PublicURLGuard(resolver=lambda _host: ("93.184.216.34",))


def _capture_request(
    url: str,
    branch_id: str,
    **kwargs: Any,
) -> ExternalCaptureRequest:
    scope = _run_scope(branch_id)
    receipt = asyncio.run(
        ExternalSourceDiscovery(
            primary=_SingleURLProvider(url),
            clock=lambda: _NOW,
            monotonic=lambda: 1.0,
        ).search(
            ExternalSearchRequest(
                query="bounded official source locator",
                branch_id=branch_id,
                run_scope=scope,
                purpose="Bind one discovery candidate before capture.",
            )
        )
    )
    return ExternalCaptureRequest(
        discovery_receipt=receipt,
        candidate_id=receipt.candidates[0].candidate_id,
        branch_id=branch_id,
        run_scope=scope,
        **kwargs,
    )


def test_exa_hosted_mcp_adapter_parses_locator_only_output() -> None:
    client = _FakeExaClient(
        "Title: Dell Q1 materials\n"
        "URL: https://investors.delltechnologies.com/q1\n"
        "Published: 2026-05-28\n"
        "Author: N/A\n"
        "Highlights:\nRevenue and backlog were discussed.\n"
        "\n---\n\n"
        "Title: SEC filing\n"
        "URL: https://www.sec.gov/Archives/example\n"
        "Published: N/A\n"
        "Author: N/A\n"
        "Highlights:\nIssuer filing locator."
    )
    provider = ExaHostedMCPProvider(
        client_factory=lambda: _FakeClientContext(client)
    )

    hits = asyncio.run(
        provider.search(
            ExternalSearchRequest(
                query="official Dell filing and investor materials",
                branch_id="Q1_ISSUER_TRUTH",
                run_scope=_run_scope("Q1_ISSUER_TRUTH"),
                purpose="Locate issuer truth sources.",
                max_results=2,
            )
        )
    )

    assert [row.title for row in hits] == ["Dell Q1 materials", "SEC filing"]
    assert hits[0].snippet == "Revenue and backlog were discussed."
    assert hits[1].published_at is None
    assert client.calls == [
        (
            "web_search_exa",
            {
                "query": "official Dell filing and investor materials",
                "numResults": 2,
            },
        )
    ]


def test_exa_prefers_structured_content_over_text_fallback() -> None:
    client = _FakeExaClient(
        "Title: Wrong fallback\nURL: https://example.com/wrong",
        structured={
            "results": [
                {
                    "title": "Structured SEC result",
                    "url": "https://www.sec.gov/Archives/issuer",
                    "highlights": ["Structured locator snippet"],
                }
            ]
        },
    )
    provider = ExaHostedMCPProvider(
        client_factory=lambda: _FakeClientContext(client)
    )

    hits = asyncio.run(
        provider.search(
            ExternalSearchRequest(
                query="official issuer filing",
                branch_id="Q1_ISSUER_TRUTH",
                run_scope=_run_scope("Q1_ISSUER_TRUTH"),
                purpose="Verify structured MCP result preference.",
            )
        )
    )

    assert [row.title for row in hits] == ["Structured SEC result"]
    assert hits[0].snippet == "Structured locator snippet"


def test_exa_hosted_web_fetch_binds_exact_official_url_and_text() -> None:
    url = "https://investor.tsmc.com/english/q2.pdf"
    client = _FakeExaClient(
        "# TSMC Q2 transcript\n"
        f"URL: {url}\n\n"
        "Official transcript text with enough content for capture."
    )
    fetcher = ExaHostedMCPPageFetcher(
        guard=_public_guard(),
        client_factory=lambda: _FakeClientContext(client),
        max_characters=12_000,
    )

    page = asyncio.run(fetcher.fetch(url, timeout_seconds=20))

    assert page.final_url == url
    assert page.status_code == 200
    assert page.content_type == "text/markdown; transport=exa_web_fetch"
    assert page.extracted_text is not None
    assert "Official transcript text" in page.extracted_text
    assert client.calls == [
        (
            "web_fetch_exa",
            {"urls": [url], "maxCharacters": 12_000},
        )
    ]


def test_exa_hosted_web_fetch_rejects_returned_url_substitution() -> None:
    client = _FakeExaClient(
        "# Nearby source\nURL: https://example.com/nearby\n\nWrong route."
    )
    fetcher = ExaHostedMCPPageFetcher(
        guard=_public_guard(),
        client_factory=lambda: _FakeClientContext(client),
    )

    with pytest.raises(ExternalSourceError) as error:
        asyncio.run(
            fetcher.fetch(
                "https://example.com/exact",
                timeout_seconds=20,
            )
        )

    assert error.value.code == "exa_mcp_web_fetch_url_mismatch"


def test_discovery_filters_domains_and_marks_candidate_not_evidence() -> None:
    discovery = ExternalSourceDiscovery(
        primary=_StaticProvider(),
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )
    request = ExternalSearchRequest(
        query="Dell issuer-reported AI server demand",
        branch_id="Q1_ISSUER_TRUTH",
        run_scope=_run_scope("Q1_ISSUER_TRUTH"),
        purpose="Locate issuer-reported demand evidence.",
        include_domains=("delltechnologies.com",),
    )

    receipt = asyncio.run(discovery.search(request))

    assert receipt.status == "ok"
    assert receipt.execution_attempt_id == "DELL-TEST-A01"
    assert receipt.run_scope_digest == request.run_scope.run_scope_digest
    assert receipt.empty_result_is_not_public_information_gap is True
    assert len(receipt.candidates) == 1
    candidate = receipt.candidates[0]
    assert candidate.authority_state == "retrieval_candidate"
    assert candidate.candidate_is_not_evidence is True
    assert candidate.search_snippet_is_not_source_text is True
    assert candidate.canonical_url == "https://investors.delltechnologies.com/a"
    body = receipt.model_dump(mode="json", exclude={"receipt_digest"})
    assert receipt.receipt_digest == canonical_digest(body)


def test_ddgs_is_used_only_as_diagnostic_fallback_after_primary_failure() -> None:
    calls: list[tuple[str, int]] = []

    def fake_ddgs(query: str, *, max_results: int) -> list[dict[str, str]]:
        calls.append((query, max_results))
        return [
            {
                "title": "NVIDIA platform update",
                "href": "https://www.nvidia.com/en-us/data-center/",
                "body": "diagnostic snippet",
            }
        ]

    discovery = ExternalSourceDiscovery(
        primary=_FailingProvider(),
        diagnostic_fallback=DDGSDiagnosticProvider(search_callable=fake_ddgs),
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )

    receipt = asyncio.run(
        discovery.search(
            ExternalSearchRequest(
                query="official NVIDIA platform production update",
                branch_id="Q4_ARCHITECTURE_RAMP",
                run_scope=_run_scope("Q4_ARCHITECTURE_RAMP"),
                purpose="Diagnose the primary discovery route failure.",
                max_results=3,
            )
        )
    )

    assert receipt.status == "ok"
    assert [row.status for row in receipt.attempted_providers] == [
        "tool_failure",
        "ok",
    ]
    assert receipt.candidates[0].provider_id == "ddgs_diagnostic_fallback"
    assert calls == [("official NVIDIA platform production update", 3)]


def test_capture_uses_browser_when_static_extraction_is_empty() -> None:
    guard = _public_guard()
    static = _FakeFetcher(
        FetchedPage(
            final_url="https://investors.delltechnologies.com/results",
            html="<html><script>load()</script></html>",
            status_code=200,
            content_type="text/html",
        )
    )
    browser = _FakeFetcher(
        FetchedPage(
            final_url="https://investors.delltechnologies.com/results",
            html="<html><main>Rendered issuer material</main></html>",
            status_code=200,
            content_type="text/html",
        )
    )
    capture = ExternalSourceCapture(
        guard=guard,
        static_fetcher=static,
        browser_fetcher=browser,
        extractor=lambda html: (
            "Rendered issuer material with enough bounded source text."
            if "Rendered" in html
            else ""
        ),
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )

    receipt = asyncio.run(
        capture.capture(
            _capture_request(
                "https://investors.delltechnologies.com/results",
                "Q1_ISSUER_TRUTH",
                minimum_useful_characters=20,
                max_characters=500,
            )
        )
    )

    assert receipt.status == "captured"
    assert receipt.authority_state == "captured_source_candidate"
    assert receipt.capture_method == "playwright_browser"
    assert [row.status for row in receipt.attempts] == ["empty", "ok"]
    assert receipt.admission_required_before_citation is True
    assert receipt.text == "Rendered issuer material with enough bounded source text."
    assert receipt.archive_grade is False
    assert receipt.robots_enforced is False
    assert receipt.source_capture_authority is False
    assert receipt.decoded_html_utf8_sha256 == sha256(
        browser.page.html.encode("utf-8")
    ).hexdigest()
    assert receipt.text_digest == sha256(receipt.text.encode("utf-8")).hexdigest()


def test_capture_uses_hosted_fetch_before_browser_after_static_failure() -> None:
    guard = _public_guard()
    static = _FakeFetcher(ExternalSourceError("capture_http_status_403"))
    hosted = _FakeFetcher(
        FetchedPage(
            final_url="https://openai.com/index/gpt-5-6/",
            extracted_text=(
                "# GPT-5.6\nURL: https://openai.com/index/gpt-5-6/\n\n"
                "Official provider text with enough bounded content."
            ),
            status_code=200,
            content_type="text/markdown; transport=exa_web_fetch",
        )
    )
    browser = _FakeFetcher(ExternalSourceError("should_not_run"))
    capture = ExternalSourceCapture(
        guard=guard,
        static_fetcher=static,
        hosted_fetcher=hosted,
        browser_fetcher=browser,
        extractor=lambda html: html,
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )

    receipt = asyncio.run(
        capture.capture(
            _capture_request(
                "https://openai.com/index/gpt-5-6/",
                "Q6_MODEL_COMPUTE_DEMAND",
                minimum_useful_characters=20,
                max_characters=500,
            )
        )
    )

    assert receipt.status == "captured"
    assert receipt.capture_method == "exa_hosted_web_fetch"
    assert [row.failure_code for row in receipt.attempts] == [
        "capture_http_status_403",
        None,
    ]
    assert receipt.decoded_html_utf8_sha256 is None
    assert browser.calls == []


def test_capture_rejects_browser_block_page_with_non_success_status() -> None:
    guard = _public_guard()
    static = _FakeFetcher(
        FetchedPage(
            final_url="https://www.sec.gov/Archives/",
            html="<html><body>Forbidden</body></html>",
            status_code=403,
            content_type="text/html",
        )
    )
    browser = _FakeFetcher(
        FetchedPage(
            final_url="https://www.sec.gov/Archives/",
            html=(
                "<html><body>Your Request Originates from an Undeclared "
                "Automated Tool</body></html>"
            ),
            status_code=403,
            content_type="text/html",
        )
    )
    capture = ExternalSourceCapture(
        guard=guard,
        static_fetcher=static,
        browser_fetcher=browser,
        extractor=lambda html: html,
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )

    receipt = asyncio.run(
        capture.capture(
            _capture_request(
                "https://www.sec.gov/Archives/",
                "Q1_ISSUER_TRUTH",
                minimum_useful_characters=20,
                max_characters=500,
            )
        )
    )

    assert receipt.status == "tool_failure"
    assert receipt.authority_state == "tool_failure"
    assert [row.failure_code for row in receipt.attempts] == [
        "capture_http_status_403",
        "capture_http_status_403",
    ]
    assert receipt.text == ""
    assert receipt.failure_is_not_public_information_gap is True


def test_capture_rejects_private_resolution_before_transport() -> None:
    guard = PublicURLGuard(resolver=lambda _host: ("127.0.0.1",))
    static = _FakeFetcher(
        FetchedPage(final_url="https://example.com/", html="should not run")
    )
    capture = ExternalSourceCapture(
        guard=guard,
        static_fetcher=static,
        browser_fetcher=None,
        extractor=lambda html: html,
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )

    receipt = asyncio.run(
        capture.capture(
            _capture_request(
                "https://example.com/",
                "Q9_COUNTEREVIDENCE_WWC",
            )
        )
    )

    assert receipt.status == "tool_failure"
    assert receipt.authority_state == "tool_failure"
    assert receipt.failure_is_not_public_information_gap is True
    assert receipt.attempts[0].failure_code == "capture_resolved_address_forbidden"
    assert static.calls == []


def test_static_transport_enforces_response_byte_ceiling_before_read() -> None:
    fetcher = StaticHTTPPageFetcher(
        guard=_public_guard(),
        maximum_response_bytes=100,
        session_factory=_FakeSession,
    )

    with pytest.raises(ExternalSourceError) as error:
        asyncio.run(
            fetcher.fetch("https://example.com/", timeout_seconds=5)
        )

    assert error.value.code == "capture_response_too_large"


def test_static_transport_preserves_http_status_as_typed_failure() -> None:
    fetcher = StaticHTTPPageFetcher(
        guard=_public_guard(),
        session_factory=_ForbiddenSession,
    )

    with pytest.raises(ExternalSourceError) as error:
        asyncio.run(fetcher.fetch("https://example.com/", timeout_seconds=5))

    assert error.value.code == "capture_http_status_403"


def test_static_transport_rejects_non_redirect_3xx_as_typed_failure() -> None:
    fetcher = StaticHTTPPageFetcher(
        guard=_public_guard(),
        session_factory=_NotModifiedSession,
    )

    with pytest.raises(ExternalSourceError) as error:
        asyncio.run(fetcher.fetch("https://example.com/", timeout_seconds=5))

    assert error.value.code == "capture_http_status_304"


def test_static_transport_preserves_timeout_as_typed_failure() -> None:
    fetcher = StaticHTTPPageFetcher(
        guard=_public_guard(),
        session_factory=_TimeoutSession,
    )

    with pytest.raises(ExternalSourceError) as error:
        asyncio.run(fetcher.fetch("https://example.com/", timeout_seconds=5))

    assert error.value.code == "capture_static_timeout"


def test_playwright_route_guard_aborts_private_subresource() -> None:
    guard = PublicURLGuard(
        resolver=lambda host: (
            ("127.0.0.1",) if host == "private.example.com" else ("93.184.216.34",)
        )
    )
    fetcher = PlaywrightPageFetcher(guard=guard)
    private_route = _FakeRoute()
    public_route = _FakeRoute()

    asyncio.run(
        fetcher._route_public_only(  # noqa: SLF001 - direct security-unit seam
            private_route,
            _FakeRequest("https://private.example.com/metadata"),
        )
    )
    asyncio.run(
        fetcher._route_public_only(  # noqa: SLF001 - direct security-unit seam
            public_route,
            _FakeRequest("https://cdn.example.com/app.js"),
        )
    )

    assert private_route.aborted is True
    assert private_route.continued is False
    assert public_route.aborted is False
    assert public_route.continued is True


def test_playwright_transport_enforces_rendered_html_byte_ceiling() -> None:
    fetcher = PlaywrightPageFetcher(
        guard=_public_guard(),
        maximum_response_bytes=100,
    )
    with pytest.raises(ExternalSourceError) as error:
        fetcher._require_bounded_html("界" * 34)  # noqa: SLF001 - resource seam
    assert error.value.code == "capture_response_too_large"
