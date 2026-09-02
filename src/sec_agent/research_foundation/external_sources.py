from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import re
import socket
import time
from typing import Any, AsyncContextManager, Literal, Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research_foundation.contracts import DellResearchRunScope


DISCOVERY_RECEIPT_SCHEMA_VERSION = "fin_ia_external_discovery_receipt_v1_0"
RETRIEVAL_CANDIDATE_SCHEMA_VERSION = "fin_ia_retrieval_candidate_v1_0"
CAPTURE_RECEIPT_SCHEMA_VERSION = "fin_ia_external_capture_receipt_v1_0"
EXA_HOSTED_MCP_ENDPOINT = "https://mcp.exa.ai/mcp"

_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_EXA_RESULT_SEPARATOR = re.compile(r"\n\s*---+\s*\n")
_EXA_FIELD = re.compile(r"^(Title|URL|Published|Author|Highlights):\s*(.*)$")
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
}
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
}


class ExternalSourceError(RuntimeError):
    """A bounded discovery or capture operation could not preserve its contract."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ExternalSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=3, max_length=600)
    branch_id: str = Field(min_length=1, max_length=96)
    run_scope: DellResearchRunScope
    purpose: str = Field(min_length=3, max_length=500)
    max_results: int = Field(default=5, ge=1, le=8)
    include_domains: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("query", "branch_id", "purpose")
    @classmethod
    def _strip_nonempty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value_empty")
        return normalized

    @field_validator("include_domains")
    @classmethod
    def _normalize_domains(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for raw in values:
            host = str(raw).strip().lower().rstrip(".")
            if "://" in host:
                host = str(urlsplit(host).hostname or "").lower().rstrip(".")
            if not _valid_hostname(host):
                raise ValueError("include_domain_invalid")
            if host not in normalized:
                normalized.append(host)
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_branch_scope(self) -> "ExternalSearchRequest":
        if self.branch_id not in self.run_scope.selected_branch_ids:
            raise ValueError("external_search_branch_outside_run_scope")
        return self

    @property
    def execution_attempt_id(self) -> str:
        return self.run_scope.execution_attempt_id

    @property
    def as_of(self) -> datetime:
        return self.run_scope.research_as_of

    @property
    def source_policy(self) -> Literal["public_web_locator_only"]:
        return "public_web_locator_only"

    @property
    def request_digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json"))


class ProviderHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    url: str
    snippet: str = ""
    published_at: str | None = None


class RetrievalCandidate(BaseModel):
    """A locator returned by discovery. It is deliberately not Evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["fin_ia_retrieval_candidate_v1_0"] = (
        RETRIEVAL_CANDIDATE_SCHEMA_VERSION
    )
    authority_state: Literal["retrieval_candidate"] = "retrieval_candidate"
    candidate_id: str
    provider_id: str
    branch_id: str
    case_id: str
    execution_attempt_id: str
    purpose: str
    research_as_of: str
    source_policy: Literal["public_web_locator_only"]
    data_snapshot_id: str
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_digest: str
    provider_rank: int = Field(ge=1)
    title: str
    canonical_url: str
    source_domain: str
    snippet: str
    published_at: str | None = None
    discovered_at: str
    candidate_is_not_evidence: Literal[True] = True
    search_snippet_is_not_source_text: Literal[True] = True


class ProviderAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    status: Literal["ok", "zero_results", "tool_failure"]
    returned_hits: int = Field(ge=0)
    accepted_hits: int = Field(ge=0)
    failure_code: str | None = None


class DiscoveryReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["fin_ia_external_discovery_receipt_v1_0"] = (
        DISCOVERY_RECEIPT_SCHEMA_VERSION
    )
    status: Literal["ok", "zero_results", "tool_failure"]
    branch_id: str
    case_id: str
    execution_attempt_id: str
    purpose: str
    research_as_of: str
    source_policy: Literal["public_web_locator_only"]
    data_snapshot_id: str
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_digest: str
    requested_max_results: int
    attempted_providers: tuple[ProviderAttempt, ...]
    candidates: tuple[RetrievalCandidate, ...]
    started_at: str
    completed_at: str
    elapsed_ms: int = Field(ge=0)
    failure_is_not_public_information_gap: Literal[True] = True
    empty_result_is_not_public_information_gap: Literal[True] = True
    result_is_not_evidence: Literal[True] = True
    receipt_digest: str

    @model_validator(mode="after")
    def validate_receipt_and_candidates(self) -> "DiscoveryReceipt":
        body = self.model_dump(mode="json", exclude={"receipt_digest"})
        if self.receipt_digest != canonical_digest(body):
            raise ValueError("external_discovery_receipt_digest_mismatch")
        candidate_ids: set[str] = set()
        for candidate in self.candidates:
            if candidate.candidate_id in candidate_ids:
                raise ValueError("external_discovery_candidate_id_duplicate")
            candidate_ids.add(candidate.candidate_id)
            if (
                candidate.branch_id != self.branch_id
                or candidate.case_id != self.case_id
                or candidate.execution_attempt_id != self.execution_attempt_id
                or candidate.purpose != self.purpose
                or candidate.research_as_of != self.research_as_of
                or candidate.source_policy != self.source_policy
                or candidate.data_snapshot_id != self.data_snapshot_id
                or candidate.method_sha256 != self.method_sha256
                or candidate.run_scope_digest != self.run_scope_digest
                or candidate.query_digest != self.query_digest
            ):
                raise ValueError("external_discovery_candidate_lineage_mismatch")
        return self


class SearchProvider(Protocol):
    provider_id: str

    async def search(self, request: ExternalSearchRequest) -> Sequence[ProviderHit]: ...


class _MCPClient(Protocol):
    async def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Any: ...


class ExaHostedMCPProvider:
    """Thin Exa hosted-MCP discovery adapter; Exa output remains locator-only."""

    provider_id = "exa_hosted_mcp_web_search"

    def __init__(
        self,
        *,
        endpoint: str = EXA_HOSTED_MCP_ENDPOINT,
        client_factory: Callable[[], AsyncContextManager[_MCPClient]] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self._client_factory = client_factory

    def _client(self) -> AsyncContextManager[_MCPClient]:
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from mcp import Client
        except ImportError as exc:  # pragma: no cover - dependency profile guard
            raise ExternalSourceError("exa_mcp_dependency_missing") from exc
        return Client(self.endpoint, read_timeout_seconds=self.timeout_seconds)

    async def search(self, request: ExternalSearchRequest) -> Sequence[ProviderHit]:
        try:
            async with self._client() as client:
                result = await client.call_tool(
                    "web_search_exa",
                    {
                        "query": request.query,
                        "numResults": request.max_results,
                    },
                )
        except ExternalSourceError:
            raise
        except Exception as exc:
            raise ExternalSourceError("exa_mcp_search_failed") from exc

        if bool(_read_attr(result, "is_error", "isError", default=False)):
            raise ExternalSourceError("exa_mcp_tool_error")
        structured = _read_attr(
            result,
            "structured_content",
            "structuredContent",
            default=None,
        )
        structured_hits = _parse_structured_search_hits(structured)
        if structured_hits:
            return tuple(structured_hits[: request.max_results])
        text = "\n".join(_tool_result_text(result)).strip()
        if not text:
            return ()
        return tuple(_parse_exa_search_text(text)[: request.max_results])


class DDGSDiagnosticProvider:
    """Local diagnostic fallback; it is not an admission or citation authority."""

    provider_id = "ddgs_diagnostic_fallback"

    def __init__(
        self,
        *,
        search_callable: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._search_callable = search_callable

    def _search_sync(self, request: ExternalSearchRequest) -> Sequence[Mapping[str, Any]]:
        if self._search_callable is not None:
            return self._search_callable(
                request.query,
                max_results=request.max_results,
            )
        try:
            from ddgs import DDGS
        except ImportError as exc:  # pragma: no cover - dependency profile guard
            raise ExternalSourceError("ddgs_dependency_missing") from exc
        return list(DDGS().text(request.query, max_results=request.max_results))

    async def search(self, request: ExternalSearchRequest) -> Sequence[ProviderHit]:
        try:
            rows = await asyncio.to_thread(self._search_sync, request)
        except ExternalSourceError:
            raise
        except Exception as exc:
            raise ExternalSourceError("ddgs_search_failed") from exc
        hits: list[ProviderHit] = []
        for row in rows[: request.max_results]:
            url = str(row.get("href") or row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            if not url or not title:
                continue
            hits.append(
                ProviderHit(
                    title=title,
                    url=url,
                    snippet=str(row.get("body") or row.get("snippet") or "").strip(),
                    published_at=(
                        str(row.get("date") or "").strip() or None
                    ),
                )
            )
        return tuple(hits)


class ExternalSourceDiscovery:
    def __init__(
        self,
        *,
        primary: SearchProvider,
        diagnostic_fallback: SearchProvider | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.primary = primary
        self.diagnostic_fallback = diagnostic_fallback
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic

    async def search(self, request: ExternalSearchRequest) -> DiscoveryReceipt:
        started = self._clock()
        started_tick = self._monotonic()
        query_digest = request.request_digest
        attempts: list[ProviderAttempt] = []
        candidates: list[RetrievalCandidate] = []
        seen_urls: set[str] = set()

        providers = [self.primary]
        if self.diagnostic_fallback is not None:
            providers.append(self.diagnostic_fallback)

        for provider_index, provider in enumerate(providers):
            if provider_index and candidates:
                break
            try:
                hits = tuple(await provider.search(request))
            except ExternalSourceError as exc:
                attempts.append(
                    ProviderAttempt(
                        provider_id=provider.provider_id,
                        status="tool_failure",
                        returned_hits=0,
                        accepted_hits=0,
                        failure_code=exc.code,
                    )
                )
                continue
            except Exception:
                attempts.append(
                    ProviderAttempt(
                        provider_id=provider.provider_id,
                        status="tool_failure",
                        returned_hits=0,
                        accepted_hits=0,
                        failure_code="provider_unclassified_failure",
                    )
                )
                continue

            accepted_before = len(candidates)
            for provider_rank, hit in enumerate(hits, start=1):
                if len(candidates) >= request.max_results:
                    break
                try:
                    canonical_url = _canonicalize_candidate_url(hit.url)
                except ExternalSourceError:
                    continue
                host = str(urlsplit(canonical_url).hostname or "").lower()
                if request.include_domains and not _host_in_domains(
                    host, request.include_domains
                ):
                    continue
                if canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)
                body = {
                    "provider_id": provider.provider_id,
                    "branch_id": request.branch_id,
                    "case_id": request.run_scope.case_id,
                    "execution_attempt_id": request.execution_attempt_id,
                    "data_snapshot_id": request.run_scope.data_snapshot_id,
                    "method_sha256": request.run_scope.method_sha256,
                    "run_scope_digest": request.run_scope.run_scope_digest,
                    "query_digest": query_digest,
                    "provider_rank": provider_rank,
                    "title": hit.title.strip()[:512],
                    "canonical_url": canonical_url,
                    "source_domain": host,
                }
                candidates.append(
                    RetrievalCandidate(
                        candidate_id=canonical_digest(body),
                        provider_id=provider.provider_id,
                        branch_id=request.branch_id,
                        case_id=request.run_scope.case_id,
                        execution_attempt_id=request.execution_attempt_id,
                        purpose=request.purpose,
                        research_as_of=_iso(request.as_of),
                        source_policy=request.source_policy,
                        data_snapshot_id=request.run_scope.data_snapshot_id,
                        method_sha256=request.run_scope.method_sha256,
                        run_scope_digest=request.run_scope.run_scope_digest,
                        query_digest=query_digest,
                        provider_rank=provider_rank,
                        title=hit.title.strip()[:512],
                        canonical_url=canonical_url,
                        source_domain=host,
                        snippet=hit.snippet.strip()[:3000],
                        published_at=hit.published_at,
                        discovered_at=_iso(started),
                    )
                )
            accepted = len(candidates) - accepted_before
            attempts.append(
                ProviderAttempt(
                    provider_id=provider.provider_id,
                    status="ok" if accepted else "zero_results",
                    returned_hits=len(hits),
                    accepted_hits=accepted,
                )
            )

        completed = self._clock()
        if candidates:
            status: Literal["ok", "zero_results", "tool_failure"] = "ok"
        elif attempts and all(row.status == "tool_failure" for row in attempts):
            status = "tool_failure"
        else:
            status = "zero_results"
        body = {
            "schema_version": DISCOVERY_RECEIPT_SCHEMA_VERSION,
            "status": status,
            "branch_id": request.branch_id,
            "case_id": request.run_scope.case_id,
            "execution_attempt_id": request.execution_attempt_id,
            "purpose": request.purpose,
            "research_as_of": _iso(request.as_of),
            "source_policy": request.source_policy,
            "data_snapshot_id": request.run_scope.data_snapshot_id,
            "method_sha256": request.run_scope.method_sha256,
            "run_scope_digest": request.run_scope.run_scope_digest,
            "query_digest": query_digest,
            "requested_max_results": request.max_results,
            "attempted_providers": [row.model_dump(mode="json") for row in attempts],
            "candidates": [row.model_dump(mode="json") for row in candidates],
            "started_at": _iso(started),
            "completed_at": _iso(completed),
            "elapsed_ms": max(0, round((self._monotonic() - started_tick) * 1000)),
            "failure_is_not_public_information_gap": True,
            "empty_result_is_not_public_information_gap": True,
            "result_is_not_evidence": True,
        }
        return DiscoveryReceipt(**body, receipt_digest=canonical_digest(body))


class ExternalCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    discovery_receipt: DiscoveryReceipt
    candidate_id: str = Field(min_length=1, max_length=128)
    branch_id: str = Field(min_length=1, max_length=96)
    run_scope: DellResearchRunScope
    max_characters: int = Field(default=12_000, ge=500, le=50_000)
    render_policy: Literal["auto", "static", "hosted", "browser"] = "auto"
    minimum_useful_characters: int = Field(default=200, ge=1, le=2_000)
    timeout_seconds: float = Field(default=20.0, ge=1.0, le=60.0)
    transport_authority: Literal["qualification_only"] = "qualification_only"
    production_status: Literal["HOLD"] = "HOLD"

    @model_validator(mode="after")
    def validate_discovery_binding(self) -> "ExternalCaptureRequest":
        receipt = self.discovery_receipt
        if self.branch_id not in self.run_scope.selected_branch_ids:
            raise ValueError("external_capture_branch_outside_run_scope")
        if (
            receipt.status != "ok"
            or receipt.branch_id != self.branch_id
            or receipt.case_id != self.run_scope.case_id
            or receipt.execution_attempt_id
            != self.run_scope.execution_attempt_id
            or receipt.research_as_of != _iso(self.run_scope.research_as_of)
            or receipt.data_snapshot_id != self.run_scope.data_snapshot_id
            or receipt.method_sha256 != self.run_scope.method_sha256
            or receipt.run_scope_digest != self.run_scope.run_scope_digest
        ):
            raise ValueError("external_capture_discovery_scope_mismatch")
        matches = [
            row for row in receipt.candidates if row.candidate_id == self.candidate_id
        ]
        if len(matches) != 1:
            raise ValueError("external_capture_candidate_binding_invalid")
        return self

    @property
    def candidate(self) -> RetrievalCandidate:
        return next(
            row
            for row in self.discovery_receipt.candidates
            if row.candidate_id == self.candidate_id
        )

    @property
    def url(self) -> str:
        return self.candidate.canonical_url


class FetchedPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    final_url: str
    html: str = ""
    extracted_text: str | None = None
    status_code: int | None = None
    content_type: str | None = None


class PageFetcher(Protocol):
    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage: ...


class CaptureAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal[
        "trafilatura_static",
        "exa_hosted_web_fetch",
        "playwright_browser",
    ]
    status: Literal["ok", "empty", "tool_failure"]
    extracted_characters: int = Field(ge=0)
    failure_code: str | None = None


class CaptureReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["fin_ia_external_capture_receipt_v1_0"] = (
        CAPTURE_RECEIPT_SCHEMA_VERSION
    )
    status: Literal["captured", "tool_failure"]
    authority_state: Literal["captured_source_candidate", "tool_failure"]
    branch_id: str
    case_id: str
    execution_attempt_id: str
    purpose: str
    research_as_of: str
    source_policy: Literal["public_web_locator_only"]
    data_snapshot_id: str
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str
    provider_id: str
    query_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_url: str
    final_url: str | None
    source_domain: str | None
    capture_method: Literal[
        "trafilatura_static",
        "exa_hosted_web_fetch",
        "playwright_browser",
    ] | None
    attempts: tuple[CaptureAttempt, ...]
    text: str
    extracted_characters: int = Field(ge=0)
    truncated: bool
    decoded_html_utf8_sha256: str | None
    text_digest: str | None
    captured_at: str
    elapsed_ms: int = Field(ge=0)
    captured_candidate_is_not_evidence: Literal[True] = True
    admission_required_before_citation: Literal[True] = True
    failure_is_not_public_information_gap: Literal[True] = True
    archive_grade: Literal[False] = False
    robots_enforced: Literal[False] = False
    source_capture_authority: Literal[False] = False
    transport_authority: Literal["qualification_only"] = "qualification_only"
    production_status: Literal["HOLD"] = "HOLD"
    receipt_digest: str

    @model_validator(mode="after")
    def validate_receipt_digest(self) -> "CaptureReceipt":
        body = self.model_dump(mode="json", exclude={"receipt_digest"})
        if self.receipt_digest != canonical_digest(body):
            raise ValueError("external_capture_receipt_digest_mismatch")
        return self


class PublicURLGuard:
    """Reject local/private destinations before each capture transport hop."""

    def __init__(
        self,
        *,
        resolver: Callable[[str], Sequence[str]] | None = None,
    ) -> None:
        self._resolver = resolver or _resolve_host

    def validate(self, raw_url: str, *, resolve: bool = True) -> str:
        try:
            canonical = _canonicalize_https_url(raw_url)
        except (ExternalSourceError, ValueError) as exc:
            raise ExternalSourceError("capture_url_invalid_or_forbidden") from exc
        host = str(urlsplit(canonical).hostname or "").lower()
        if not _valid_hostname(host) and not _is_ip_literal(host):
            raise ExternalSourceError("capture_host_invalid")
        if _is_ip_literal(host):
            _require_public_address(host)
        elif resolve:
            try:
                addresses = tuple(self._resolver(host))
            except Exception as exc:
                raise ExternalSourceError("capture_dns_resolution_failed") from exc
            if not addresses:
                raise ExternalSourceError("capture_dns_resolution_empty")
            for address in addresses:
                _require_public_address(address)
        return canonical


class StaticHTTPPageFetcher:
    """Bounded HTTP transport; extraction is performed separately by trafilatura."""

    transport_authority = "qualification_only"
    production_status = "HOLD"

    def __init__(
        self,
        *,
        guard: PublicURLGuard,
        user_agent: str = "FIN-Insight-Agent/0.1 research-source-capture",
        maximum_redirects: int = 5,
        maximum_response_bytes: int = 5_000_000,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.guard = guard
        self.user_agent = user_agent
        self.maximum_redirects = maximum_redirects
        self.maximum_response_bytes = maximum_response_bytes
        self._session_factory = session_factory

    def _fetch_sync(self, raw_url: str, timeout_seconds: float) -> FetchedPage:
        import requests

        url = self.guard.validate(raw_url)
        session_factory = self._session_factory or requests.Session
        with session_factory() as session:
            for redirect_index in range(self.maximum_redirects + 1):
                with session.get(
                    url,
                    allow_redirects=False,
                    timeout=timeout_seconds,
                    headers={"User-Agent": self.user_agent},
                    stream=True,
                ) as response:
                    if response.is_redirect or response.is_permanent_redirect:
                        if redirect_index >= self.maximum_redirects:
                            raise ExternalSourceError("capture_redirect_limit_exceeded")
                        location = str(response.headers.get("Location") or "").strip()
                        if not location:
                            raise ExternalSourceError("capture_redirect_location_missing")
                        url = self.guard.validate(urljoin(url, location))
                        continue
                    status_code = int(response.status_code)
                    if status_code < 200 or status_code >= 300:
                        raise ExternalSourceError(
                            f"capture_http_status_{status_code}"
                        )
                    declared_length = str(
                        response.headers.get("Content-Length") or ""
                    ).strip()
                    if (
                        declared_length.isdigit()
                        and int(declared_length) > self.maximum_response_bytes
                    ):
                        raise ExternalSourceError("capture_response_too_large")
                    body = bytearray()
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        body.extend(chunk)
                        if len(body) > self.maximum_response_bytes:
                            raise ExternalSourceError("capture_response_too_large")
                    final_url = self.guard.validate(str(response.url))
                    encoding = str(response.encoding or "utf-8")
                    return FetchedPage(
                        final_url=final_url,
                        html=bytes(body).decode(encoding, errors="replace"),
                        status_code=status_code,
                        content_type=response.headers.get("Content-Type"),
                    )
        raise ExternalSourceError("capture_static_unreachable")

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        import requests

        try:
            return await asyncio.to_thread(self._fetch_sync, url, timeout_seconds)
        except ExternalSourceError:
            raise
        except requests.Timeout as exc:
            raise ExternalSourceError("capture_static_timeout") from exc
        except requests.ConnectionError as exc:
            raise ExternalSourceError("capture_static_connection_failed") from exc
        except requests.RequestException as exc:
            raise ExternalSourceError("capture_static_request_failed") from exc
        except Exception as exc:
            raise ExternalSourceError("capture_static_fetch_failed") from exc


class ExaHostedMCPPageFetcher:
    """Thin hosted full-text fallback over Exa's maintained ``web_fetch_exa``.

    Exa performs the cross-site retrieval and document-to-markdown conversion.
    FIN still validates the requested public URL before transmission and requires
    the returned document header to bind back to that exact canonical URL.  The
    returned text remains a capture candidate; it is not archive-grade source
    bytes and receives no Evidence authority here.
    """

    transport_authority = "qualification_only"
    production_status = "HOLD"

    def __init__(
        self,
        *,
        guard: PublicURLGuard,
        endpoint: str = EXA_HOSTED_MCP_ENDPOINT,
        client_factory: Callable[[], AsyncContextManager[_MCPClient]] | None = None,
        max_characters: int = 50_000,
        maximum_response_bytes: int = 2_000_000,
    ) -> None:
        if max_characters < 1 or maximum_response_bytes < 1:
            raise ValueError("exa_hosted_fetch_limit_invalid")
        self.guard = guard
        self.endpoint = endpoint
        self._client_factory = client_factory
        self.max_characters = max_characters
        self.maximum_response_bytes = maximum_response_bytes

    def _client(
        self,
        *,
        timeout_seconds: float,
    ) -> AsyncContextManager[_MCPClient]:
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from mcp import Client
        except ImportError as exc:  # pragma: no cover - dependency profile guard
            raise ExternalSourceError("exa_mcp_dependency_missing") from exc
        return Client(self.endpoint, read_timeout_seconds=timeout_seconds)

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        requested_url = await asyncio.to_thread(self.guard.validate, url)
        try:
            async with self._client(timeout_seconds=timeout_seconds) as client:
                result = await client.call_tool(
                    "web_fetch_exa",
                    {
                        "urls": [requested_url],
                        "maxCharacters": self.max_characters,
                    },
                )
        except ExternalSourceError:
            raise
        except Exception as exc:
            raise ExternalSourceError("exa_mcp_web_fetch_failed") from exc

        if bool(_read_attr(result, "is_error", "isError", default=False)):
            raise ExternalSourceError("exa_mcp_web_fetch_tool_error")
        text = "\n".join(_tool_result_text(result)).strip()
        if not text:
            raise ExternalSourceError("exa_mcp_web_fetch_empty")
        if len(text.encode("utf-8")) > self.maximum_response_bytes:
            raise ExternalSourceError("capture_response_too_large")

        returned_url = _first_exa_document_url(text)
        if returned_url is None:
            raise ExternalSourceError("exa_mcp_web_fetch_url_missing")
        try:
            returned_url = await asyncio.to_thread(
                self.guard.validate,
                returned_url,
            )
        except ExternalSourceError as exc:
            raise ExternalSourceError("exa_mcp_web_fetch_url_invalid") from exc
        if returned_url != requested_url:
            raise ExternalSourceError("exa_mcp_web_fetch_url_mismatch")
        return FetchedPage(
            final_url=returned_url,
            extracted_text=text,
            status_code=200,
            content_type="text/markdown; transport=exa_web_fetch",
        )


class PlaywrightPageFetcher:
    """Browser fallback for public, JavaScript-rendered pages."""

    transport_authority = "qualification_only"
    production_status = "HOLD"

    def __init__(
        self,
        *,
        guard: PublicURLGuard,
        maximum_response_bytes: int = 5_000_000,
    ) -> None:
        self.guard = guard
        if maximum_response_bytes < 1:
            raise ValueError("maximum_response_bytes_invalid")
        self.maximum_response_bytes = maximum_response_bytes

    def _require_bounded_html(self, html: str) -> str:
        if len(html.encode("utf-8")) > self.maximum_response_bytes:
            raise ExternalSourceError("capture_response_too_large")
        return html

    async def _route_public_only(self, route: Any, request: Any) -> None:
        request_url = str(request.url)
        if not request_url.startswith(("http://", "https://")):
            await route.abort()
            return
        try:
            await asyncio.to_thread(self.guard.validate, request_url)
        except ExternalSourceError:
            await route.abort()
            return
        await route.continue_()

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - dependency profile guard
            raise ExternalSourceError("playwright_dependency_missing") from exc

        canonical = await asyncio.to_thread(self.guard.validate, url)
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(service_workers="block")

                    await context.route("**/*", self._route_public_only)
                    page = await context.new_page()
                    response = await page.goto(
                        canonical,
                        wait_until="domcontentloaded",
                        timeout=round(timeout_seconds * 1000),
                    )
                    if response is None:
                        raise ExternalSourceError(
                            "capture_browser_response_missing"
                        )
                    status_code = int(response.status)
                    if status_code < 200 or status_code >= 300:
                        raise ExternalSourceError(
                            f"capture_http_status_{status_code}"
                        )
                    await page.wait_for_timeout(750)
                    final_url = await asyncio.to_thread(self.guard.validate, page.url)
                    html = self._require_bounded_html(await page.content())
                    return FetchedPage(
                        final_url=final_url,
                        html=html,
                        status_code=status_code,
                        content_type=await response.header_value("content-type"),
                    )
                finally:
                    await browser.close()
        except ExternalSourceError:
            raise
        except Exception as exc:
            raise ExternalSourceError("capture_browser_fetch_failed") from exc


def trafilatura_extract_text(html: str) -> str:
    try:
        import trafilatura
    except ImportError as exc:  # pragma: no cover - dependency profile guard
        raise ExternalSourceError("trafilatura_dependency_missing") from exc
    try:
        return str(
            trafilatura.extract(
                html,
                output_format="txt",
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            or ""
        ).strip()
    except Exception as exc:
        raise ExternalSourceError("trafilatura_extract_failed") from exc


class ExternalSourceCapture:
    def __init__(
        self,
        *,
        guard: PublicURLGuard,
        static_fetcher: PageFetcher,
        hosted_fetcher: PageFetcher | None = None,
        browser_fetcher: PageFetcher | None = None,
        extractor: Callable[[str], str] = trafilatura_extract_text,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.guard = guard
        self.static_fetcher = static_fetcher
        self.hosted_fetcher = hosted_fetcher
        self.browser_fetcher = browser_fetcher
        self.extractor = extractor
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic

    @classmethod
    def with_default_transports(cls) -> "ExternalSourceCapture":
        guard = PublicURLGuard()
        return cls(
            guard=guard,
            static_fetcher=StaticHTTPPageFetcher(guard=guard),
            hosted_fetcher=ExaHostedMCPPageFetcher(guard=guard),
            browser_fetcher=PlaywrightPageFetcher(guard=guard),
        )

    async def capture(self, request: ExternalCaptureRequest) -> CaptureReceipt:
        captured_at = self._clock()
        started_tick = self._monotonic()
        attempts: list[CaptureAttempt] = []
        requested_url: str
        try:
            requested_url = await asyncio.to_thread(self.guard.validate, request.url)
        except ExternalSourceError as exc:
            return self._failure_receipt(
                request=request,
                requested_url=request.url,
                attempts=(
                    CaptureAttempt(
                        method="trafilatura_static",
                        status="tool_failure",
                        extracted_characters=0,
                        failure_code=exc.code,
                    ),
                ),
                captured_at=captured_at,
                started_tick=started_tick,
            )

        methods: list[
            tuple[
                Literal[
                    "trafilatura_static",
                    "exa_hosted_web_fetch",
                    "playwright_browser",
                ],
                PageFetcher,
            ]
        ] = []
        if request.render_policy in {"auto", "static"}:
            methods.append(("trafilatura_static", self.static_fetcher))
        if (
            request.render_policy in {"auto", "hosted"}
            and self.hosted_fetcher is not None
        ):
            methods.append(("exa_hosted_web_fetch", self.hosted_fetcher))
        if request.render_policy in {"auto", "browser"} and self.browser_fetcher:
            methods.append(("playwright_browser", self.browser_fetcher))
        if request.render_policy in {"browser", "hosted"} and not methods:
            missing_method = (
                "playwright_browser"
                if request.render_policy == "browser"
                else "exa_hosted_web_fetch"
            )
            return self._failure_receipt(
                request=request,
                requested_url=requested_url,
                attempts=(
                    CaptureAttempt(
                        method=missing_method,
                        status="tool_failure",
                        extracted_characters=0,
                        failure_code=(
                            "capture_browser_fetcher_unavailable"
                            if request.render_policy == "browser"
                            else "capture_hosted_fetcher_unavailable"
                        ),
                    ),
                ),
                captured_at=captured_at,
                started_tick=started_tick,
            )

        last_page: FetchedPage | None = None
        last_text = ""
        selected_method: Literal[
            "trafilatura_static",
            "exa_hosted_web_fetch",
            "playwright_browser",
        ] | None = None
        for method, fetcher in methods:
            try:
                page = await fetcher.fetch(
                    requested_url,
                    timeout_seconds=request.timeout_seconds,
                )
                if page.status_code is not None and not (
                    200 <= page.status_code < 300
                ):
                    raise ExternalSourceError(
                        f"capture_http_status_{page.status_code}"
                    )
                final_url = await asyncio.to_thread(self.guard.validate, page.final_url)
                page = page.model_copy(update={"final_url": final_url})
                text = (
                    page.extracted_text.strip()
                    if page.extracted_text is not None
                    else self.extractor(page.html).strip()
                )
            except ExternalSourceError as exc:
                attempts.append(
                    CaptureAttempt(
                        method=method,
                        status="tool_failure",
                        extracted_characters=0,
                        failure_code=exc.code,
                    )
                )
                text = ""
                page = None
            except Exception:
                attempts.append(
                    CaptureAttempt(
                        method=method,
                        status="tool_failure",
                        extracted_characters=0,
                        failure_code="capture_unclassified_failure",
                    )
                )
                text = ""
                page = None

            if page is not None:
                last_page = page
                last_text = text
                attempts.append(
                    CaptureAttempt(
                        method=method,
                        status=(
                            "ok"
                            if len(text) >= request.minimum_useful_characters
                            else "empty"
                        ),
                        extracted_characters=len(text),
                        failure_code=(
                            None
                            if len(text) >= request.minimum_useful_characters
                            else "capture_extracted_text_below_minimum"
                        ),
                    )
                )
                if len(text) >= request.minimum_useful_characters:
                    selected_method = method
                    break

        if selected_method is None or last_page is None:
            return self._failure_receipt(
                request=request,
                requested_url=requested_url,
                attempts=tuple(attempts),
                captured_at=captured_at,
                started_tick=started_tick,
            )

        bounded_text = last_text[: request.max_characters]
        body = {
            "schema_version": CAPTURE_RECEIPT_SCHEMA_VERSION,
            "status": "captured",
            "authority_state": "captured_source_candidate",
            "branch_id": request.branch_id,
            "case_id": request.run_scope.case_id,
            "execution_attempt_id": request.run_scope.execution_attempt_id,
            "purpose": request.discovery_receipt.purpose,
            "research_as_of": _iso(request.run_scope.research_as_of),
            "source_policy": request.discovery_receipt.source_policy,
            "data_snapshot_id": request.run_scope.data_snapshot_id,
            "method_sha256": request.run_scope.method_sha256,
            "run_scope_digest": request.run_scope.run_scope_digest,
            "discovery_receipt_digest": request.discovery_receipt.receipt_digest,
            "candidate_id": request.candidate_id,
            "provider_id": request.candidate.provider_id,
            "query_digest": request.candidate.query_digest,
            "requested_url": requested_url,
            "final_url": last_page.final_url,
            "source_domain": str(urlsplit(last_page.final_url).hostname or "").lower(),
            "capture_method": selected_method,
            "attempts": [row.model_dump(mode="json") for row in attempts],
            "text": bounded_text,
            "extracted_characters": len(last_text),
            "truncated": len(last_text) > len(bounded_text),
            "decoded_html_utf8_sha256": (
                _utf8_sha256(last_page.html)
                if last_page.extracted_text is None
                else None
            ),
            "text_digest": _utf8_sha256(last_text),
            "captured_at": _iso(captured_at),
            "elapsed_ms": max(0, round((self._monotonic() - started_tick) * 1000)),
            "captured_candidate_is_not_evidence": True,
            "admission_required_before_citation": True,
            "failure_is_not_public_information_gap": True,
            "archive_grade": False,
            "robots_enforced": False,
            "source_capture_authority": False,
            "transport_authority": request.transport_authority,
            "production_status": request.production_status,
        }
        return CaptureReceipt(**body, receipt_digest=canonical_digest(body))

    def _failure_receipt(
        self,
        *,
        request: ExternalCaptureRequest,
        requested_url: str,
        attempts: tuple[CaptureAttempt, ...],
        captured_at: datetime,
        started_tick: float,
    ) -> CaptureReceipt:
        body = {
            "schema_version": CAPTURE_RECEIPT_SCHEMA_VERSION,
            "status": "tool_failure",
            "authority_state": "tool_failure",
            "branch_id": request.branch_id,
            "case_id": request.run_scope.case_id,
            "execution_attempt_id": request.run_scope.execution_attempt_id,
            "purpose": request.discovery_receipt.purpose,
            "research_as_of": _iso(request.run_scope.research_as_of),
            "source_policy": request.discovery_receipt.source_policy,
            "data_snapshot_id": request.run_scope.data_snapshot_id,
            "method_sha256": request.run_scope.method_sha256,
            "run_scope_digest": request.run_scope.run_scope_digest,
            "discovery_receipt_digest": request.discovery_receipt.receipt_digest,
            "candidate_id": request.candidate_id,
            "provider_id": request.candidate.provider_id,
            "query_digest": request.candidate.query_digest,
            "requested_url": requested_url,
            "final_url": None,
            "source_domain": None,
            "capture_method": None,
            "attempts": [row.model_dump(mode="json") for row in attempts],
            "text": "",
            "extracted_characters": 0,
            "truncated": False,
            "decoded_html_utf8_sha256": None,
            "text_digest": None,
            "captured_at": _iso(captured_at),
            "elapsed_ms": max(0, round((self._monotonic() - started_tick) * 1000)),
            "captured_candidate_is_not_evidence": True,
            "admission_required_before_citation": True,
            "failure_is_not_public_information_gap": True,
            "archive_grade": False,
            "robots_enforced": False,
            "source_capture_authority": False,
            "transport_authority": request.transport_authority,
            "production_status": request.production_status,
        }
        return CaptureReceipt(**body, receipt_digest=canonical_digest(body))


def _parse_exa_search_text(text: str) -> list[ProviderHit]:
    hits: list[ProviderHit] = []
    for block in _EXA_RESULT_SEPARATOR.split(text):
        fields: dict[str, str] = {}
        highlights: list[str] = []
        collecting_highlights = False
        for raw_line in block.splitlines():
            line = raw_line.strip()
            match = _EXA_FIELD.match(line)
            if match:
                key, value = match.groups()
                fields[key] = value.strip()
                collecting_highlights = key == "Highlights"
                if collecting_highlights and value.strip():
                    highlights.append(value.strip())
                continue
            if collecting_highlights and line:
                highlights.append(line)
        title = fields.get("Title", "").strip()
        url = fields.get("URL", "").strip()
        if title and url:
            published = fields.get("Published", "").strip()
            hits.append(
                ProviderHit(
                    title=title,
                    url=url,
                    snippet="\n".join(highlights).strip(),
                    published_at=(published if published and published != "N/A" else None),
                )
            )
    return hits


def _parse_structured_search_hits(value: Any) -> list[ProviderHit]:
    """Prefer hosted-provider structured results without depending on one schema."""

    queue: list[Any] = [value]
    hits: list[ProviderHit] = []
    seen_urls: set[str] = set()
    visited = 0
    while queue and visited < 100:
        current = queue.pop(0)
        visited += 1
        if isinstance(current, Mapping):
            url = str(current.get("url") or current.get("href") or "").strip()
            title = str(current.get("title") or current.get("name") or "").strip()
            if url and title and url not in seen_urls:
                seen_urls.add(url)
                snippet_value = (
                    current.get("snippet")
                    or current.get("text")
                    or current.get("highlights")
                    or current.get("content")
                    or ""
                )
                if isinstance(snippet_value, Sequence) and not isinstance(
                    snippet_value, (str, bytes)
                ):
                    snippet_value = "\n".join(str(row) for row in snippet_value)
                hits.append(
                    ProviderHit(
                        title=title,
                        url=url,
                        snippet=str(snippet_value).strip(),
                        published_at=(
                            str(
                                current.get("published_at")
                                or current.get("publishedDate")
                                or current.get("date")
                                or ""
                            ).strip()
                            or None
                        ),
                    )
                )
            queue.extend(current.values())
        elif isinstance(current, Sequence) and not isinstance(
            current, (str, bytes)
        ):
            queue.extend(current)
    return hits


def _tool_result_text(result: Any) -> list[str]:
    content = _read_attr(result, "content", default=())
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
        return []
    output: list[str] = []
    for item in content:
        item_type = _read_attr(item, "type", default=None)
        if item_type != "text":
            continue
        value = _read_attr(item, "text", default="")
        if value:
            output.append(str(value))
    return output


def _first_exa_document_url(text: str) -> str | None:
    """Read the bound URL header emitted for the first fetched Exa document."""

    for line in text.splitlines()[:12]:
        if line.startswith("URL:"):
            value = line.partition(":")[2].strip()
            return value or None
    return None


def _read_attr(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _canonicalize_candidate_url(raw_url: str) -> str:
    try:
        canonical = _canonicalize_https_url(raw_url)
    except (ExternalSourceError, ValueError) as exc:
        raise ExternalSourceError("discovery_candidate_url_invalid") from exc
    host = str(urlsplit(canonical).hostname or "").lower()
    if _is_ip_literal(host):
        _require_public_address(host)
    elif not _valid_hostname(host):
        raise ExternalSourceError("discovery_candidate_host_invalid")
    return canonical


def _canonicalize_https_url(raw_url: str) -> str:
    parts = urlsplit(str(raw_url).strip())
    if (
        parts.scheme.lower() != "https"
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ExternalSourceError("public_https_url_invalid")
    try:
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port
    except (UnicodeError, ValueError) as exc:
        raise ExternalSourceError("public_https_host_invalid") from exc
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ExternalSourceError("public_https_host_forbidden")
    if port not in {None, 443}:
        raise ExternalSourceError("public_https_port_forbidden")
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.casefold()
        if (
            lowered.startswith("utm_")
            or lowered in _TRACKING_QUERY_KEYS
            or lowered in _SENSITIVE_QUERY_KEYS
        ):
            continue
        query.append((key, value))
    if _is_ip_literal(host) and ":" in host:
        netloc = f"[{host}]"
    else:
        netloc = host
    return urlunsplit(
        (
            "https",
            netloc,
            parts.path or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def _valid_hostname(host: str) -> bool:
    if not host or len(host) > 253 or host.endswith(".local"):
        return False
    labels = host.split(".")
    return len(labels) >= 2 and all(_HOST_LABEL.fullmatch(label) for label in labels)


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _require_public_address(raw_address: str) -> None:
    try:
        address = ipaddress.ip_address(raw_address)
    except ValueError as exc:
        raise ExternalSourceError("capture_resolved_address_invalid") from exc
    if not address.is_global:
        raise ExternalSourceError("capture_resolved_address_forbidden")


def _resolve_host(host: str) -> tuple[str, ...]:
    rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return tuple(sorted({str(row[4][0]) for row in rows}))


def _host_in_domains(host: str, domains: Sequence[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _utf8_sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "CAPTURE_RECEIPT_SCHEMA_VERSION",
    "DISCOVERY_RECEIPT_SCHEMA_VERSION",
    "EXA_HOSTED_MCP_ENDPOINT",
    "RETRIEVAL_CANDIDATE_SCHEMA_VERSION",
    "CaptureReceipt",
    "DDGSDiagnosticProvider",
    "DiscoveryReceipt",
    "ExaHostedMCPProvider",
    "ExaHostedMCPPageFetcher",
    "ExternalCaptureRequest",
    "ExternalSearchRequest",
    "ExternalSourceCapture",
    "ExternalSourceDiscovery",
    "ExternalSourceError",
    "FetchedPage",
    "PlaywrightPageFetcher",
    "ProviderHit",
    "PublicURLGuard",
    "RetrievalCandidate",
    "StaticHTTPPageFetcher",
    "trafilatura_extract_text",
]
