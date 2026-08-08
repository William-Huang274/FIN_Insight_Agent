from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from http.client import RemoteDisconnected
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


POLICY_SCHEMA = "fin_ia_0_1_3_s1_08_searxng_diagnostic_provider_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_08_searxng_diagnostic_query_result_v1_0"
CAPTURE_SCHEMA = "fin_ia_0_1_3_s1_08_searxng_diagnostic_capture_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.searxng_diagnostic_locator_provider:v1"
CAPTURE_NAMESPACE = "fin-0.1.3/s1-08/searxng-diagnostic-captures"
PROMOTION_STATUS = "diagnostic_locator_only"
_CASE_KEYS = frozenset({"DELL", "MU", "NVDA"})
_SAFE_RESPONSE_HEADERS = frozenset(
    {"content-type", "content-length", "date", "etag", "last-modified", "location"}
)
_TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "source",
    }
)
_SENSITIVE_QUERY_KEYS = frozenset(
    {
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
)


class SearXNGDiagnosticError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SearXNGDiagnosticQuery:
    query_id: str
    case_key: str
    evidence_slot_id: str
    query_text: str
    language: str = "en-US"
    time_range: str = ""
    categories: tuple[str, ...] = ("general",)
    result_ceiling: int = 20
    query_digest: str = ""

    @classmethod
    def create(
        cls,
        *,
        query_id: str,
        case_key: str,
        evidence_slot_id: str,
        query_text: str,
        language: str = "en-US",
        time_range: str = "",
        categories: Sequence[str] = ("general",),
        result_ceiling: int = 20,
    ) -> "SearXNGDiagnosticQuery":
        body = {
            "query_id": str(query_id),
            "case_key": str(case_key),
            "evidence_slot_id": str(evidence_slot_id),
            "query_text": str(query_text),
            "language": str(language),
            "time_range": str(time_range),
            "categories": sorted({str(value) for value in categories}),
            "result_ceiling": int(result_ceiling),
        }
        return cls(
            query_id=body["query_id"],
            case_key=body["case_key"],
            evidence_slot_id=body["evidence_slot_id"],
            query_text=body["query_text"],
            language=body["language"],
            time_range=body["time_range"],
            categories=tuple(body["categories"]),
            result_ceiling=body["result_ceiling"],
            query_digest=canonical_digest(body),
        )

    def digest_body(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "query_text": self.query_text,
            "language": self.language,
            "time_range": self.time_range,
            "categories": list(self.categories),
            "result_ceiling": self.result_ceiling,
        }


@dataclass(frozen=True)
class SearXNGDiagnosticResponse:
    status_code: int
    final_url: str
    headers: Mapping[str, str]
    body: bytes
    redirect_chain: tuple[Mapping[str, Any], ...] = ()
    body_ceiling_exceeded: bool = False


class SearXNGDiagnosticTransport(Protocol):
    live_network: bool

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SearXNGDiagnosticResponse: ...


class _SameOriginRedirectHandler(HTTPRedirectHandler):
    def __init__(self, *, expected_origin: str) -> None:
        super().__init__()
        self.expected_origin = expected_origin
        self.chain: list[dict[str, Any]] = []

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        if len(self.chain) >= 2:
            raise SearXNGDiagnosticError("searxng_redirect_ceiling_exceeded")
        if _url_origin(newurl) != self.expected_origin:
            raise SearXNGDiagnosticError("searxng_redirect_origin_drift")
        self.chain.append(
            {
                "status_code": int(code),
                "from_url": req.full_url,
                "to_url": newurl,
            }
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibSearXNGDiagnosticTransport:
    """Loopback-only transport for the self-hosted diagnostic instance."""

    live_network = True

    def __init__(self, *, base_url: str) -> None:
        self.base_url = _validated_loopback_base_url(base_url)
        self.origin = _url_origin(self.base_url)

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SearXNGDiagnosticResponse:
        if _url_origin(url) != self.origin or urlsplit(url).path != "/search":
            raise SearXNGDiagnosticError("searxng_request_origin_or_path_invalid")
        handler = _SameOriginRedirectHandler(expected_origin=self.origin)
        opener = build_opener(ProxyHandler({}), handler)
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = response.read(byte_ceiling + 1)
                exceeded = len(body) > byte_ceiling
                return SearXNGDiagnosticResponse(
                    status_code=int(response.status),
                    final_url=response.geturl(),
                    headers={
                        key.lower(): value
                        for key, value in response.headers.items()
                        if key.lower() in _SAFE_RESPONSE_HEADERS
                    },
                    body=body[:byte_ceiling],
                    redirect_chain=tuple(handler.chain),
                    body_ceiling_exceeded=exceeded,
                )
        except HTTPError as exc:
            body = exc.read(byte_ceiling + 1)
            return SearXNGDiagnosticResponse(
                status_code=int(exc.code),
                final_url=exc.geturl(),
                headers={
                    key.lower(): value
                    for key, value in exc.headers.items()
                    if key.lower() in _SAFE_RESPONSE_HEADERS
                },
                body=body[:byte_ceiling],
                redirect_chain=tuple(handler.chain),
                body_ceiling_exceeded=len(body) > byte_ceiling,
            )
        except SearXNGDiagnosticError:
            raise
        except TimeoutError as exc:
            raise SearXNGDiagnosticError("searxng_transport_timeout") from exc
        except (
            URLError,
            RemoteDisconnected,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            OSError,
        ) as exc:
            raise SearXNGDiagnosticError("searxng_transport_unavailable") from exc


def load_searxng_diagnostic_policy(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != POLICY_SCHEMA or payload.get("contract_ref") != CONTRACT_REF:
        raise SearXNGDiagnosticError("searxng_policy_identity_invalid")
    _validated_loopback_base_url(str(payload.get("base_url") or ""))
    if str(payload.get("endpoint") or "") != "/search":
        raise SearXNGDiagnosticError("searxng_policy_endpoint_invalid")
    if set(payload.get("allowed_case_keys") or ()) != _CASE_KEYS:
        raise SearXNGDiagnosticError("searxng_policy_case_set_invalid")
    budgets = payload.get("budgets") or {}
    for key in ("query_call_ceiling", "result_ceiling_per_query", "byte_ceiling_per_response", "timeout_seconds"):
        if not isinstance(budgets.get(key), int) or int(budgets[key]) <= 0:
            raise SearXNGDiagnosticError("searxng_policy_budget_invalid")
    boundary = payload.get("capability_boundary") or {}
    expected_false = (
        "evidence_promotion_allowed",
        "writer_citable",
        "domain_judgment_eligible",
        "financial_fact_authority",
        "production_capability_claim_allowed",
    )
    if str(boundary.get("promotion_status") or "") != PROMOTION_STATUS or any(
        boundary.get(key) is not False for key in expected_false
    ):
        raise SearXNGDiagnosticError("searxng_policy_false_promotion")
    if boundary.get("numeric_authority") != "none":
        raise SearXNGDiagnosticError("searxng_policy_numeric_authority_invalid")
    if payload.get("authentication") != "none":
        raise SearXNGDiagnosticError("searxng_policy_authentication_invalid")
    return payload


class SearXNGDiagnosticAdapter:
    def __init__(
        self,
        *,
        policy: Mapping[str, Any],
        runtime_root: str | Path,
        transport: SearXNGDiagnosticTransport,
    ) -> None:
        self.policy = dict(policy)
        self._validate_policy_mapping()
        self.transport = transport
        self.store = FileCanonicalObjectStore(Path(runtime_root).resolve() / "objects")
        self.capture_refs: list[dict[str, Any]] = []
        self.query_calls = 0
        self.network_calls = 0

    def search(self, query: SearXNGDiagnosticQuery) -> dict[str, Any]:
        self._validate_query(query)
        ceiling = int(self.policy["budgets"]["query_call_ceiling"])
        if self.query_calls >= ceiling:
            raise SearXNGDiagnosticError("searxng_query_call_ceiling_exceeded")
        url = self._request_url(query)
        headers = {"Accept": "application/json", "User-Agent": "FIN-Insight-Agent/0.1.3 diagnostic-locator"}
        request_capture = {
            "schema_version": CAPTURE_SCHEMA,
            "capture_kind": "diagnostic_search_request",
            "contract_ref": CONTRACT_REF,
            "query_digest": query.query_digest,
            "case_key": query.case_key,
            "evidence_slot_id": query.evidence_slot_id,
            "method": "GET",
            "url": url,
            "headers": headers,
            "credential_cookie_authorization_present": False,
            "capture_before_transport": True,
        }
        request_ref = self._persist(request_capture, "searxng_diagnostic_request")
        self.query_calls += 1
        self.network_calls += int(bool(self.transport.live_network))
        try:
            response = self.transport.fetch(
                url=url,
                headers=headers,
                timeout_seconds=int(self.policy["budgets"]["timeout_seconds"]),
                byte_ceiling=int(self.policy["budgets"]["byte_ceiling_per_response"]),
            )
        except SearXNGDiagnosticError as exc:
            failure_ref = self._persist(
                {
                    "schema_version": CAPTURE_SCHEMA,
                    "capture_kind": "diagnostic_search_transport_failure",
                    "contract_ref": CONTRACT_REF,
                    "query_digest": query.query_digest,
                    "request_capture_ref": request_ref["object_key"],
                    "request_capture_digest": request_ref["digest"],
                    "failure_code": exc.code,
                    "capture_before_parse": True,
                    "credential_cookie_authorization_present": False,
                },
                "searxng_diagnostic_transport_failure",
            )
            return self._terminal(
                query=query,
                request_ref=request_ref,
                response_ref=failure_ref,
                status="failed",
                terminal_code=exc.code,
            )
        response_ref = self._persist_response(query=query, request_ref=request_ref, response=response)
        response_failure = self._classify_response(response)
        if response_failure:
            return self._terminal(
                query=query,
                request_ref=request_ref,
                response_ref=response_ref,
                status="failed",
                terminal_code=response_failure,
            )
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._terminal(
                query=query,
                request_ref=request_ref,
                response_ref=response_ref,
                status="failed",
                terminal_code="searxng_response_invalid_json",
            )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("results"), list):
            return self._terminal(
                query=query,
                request_ref=request_ref,
                response_ref=response_ref,
                status="failed",
                terminal_code="searxng_response_schema_drift",
            )
        locators, rejection_codes = _normalize_results(
            payload["results"], result_ceiling=query.result_ceiling
        )
        unresponsive = _normalize_unresponsive_engines(payload.get("unresponsive_engines"))
        if locators:
            status = "completed"
            terminal_code = "diagnostic_locators_materialized"
        elif payload["results"]:
            status = "completed_empty"
            terminal_code = "no_valid_diagnostic_locator"
        else:
            status = "completed_empty"
            terminal_code = "upstream_returned_no_result"
        return self._terminal(
            query=query,
            request_ref=request_ref,
            response_ref=response_ref,
            status=status,
            terminal_code=terminal_code,
            locators=locators,
            rejection_codes=rejection_codes,
            upstream_raw_result_count=len(payload["results"]),
            unresponsive_engines=unresponsive,
        )

    def _request_url(self, query: SearXNGDiagnosticQuery) -> str:
        base_url = str(self.policy["base_url"]).rstrip("/")
        params: list[tuple[str, str]] = [
            ("q", query.query_text),
            ("format", "json"),
            ("language", query.language),
            ("categories", ",".join(query.categories)),
        ]
        if query.time_range:
            params.append(("time_range", query.time_range))
        return f"{base_url}/search?{urlencode(params)}"

    def _validate_policy_mapping(self) -> None:
        expected = {
            "schema_version": POLICY_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "authentication": "none",
        }
        if any(self.policy.get(key) != value for key, value in expected.items()):
            raise SearXNGDiagnosticError("searxng_policy_identity_invalid")
        _validated_loopback_base_url(str(self.policy.get("base_url") or ""))
        if self.policy.get("endpoint") != "/search":
            raise SearXNGDiagnosticError("searxng_policy_endpoint_invalid")
        if set(self.policy.get("allowed_case_keys") or ()) != _CASE_KEYS:
            raise SearXNGDiagnosticError("searxng_policy_case_set_invalid")
        boundary = self.policy.get("capability_boundary") or {}
        if (
            boundary.get("promotion_status") != PROMOTION_STATUS
            or boundary.get("evidence_promotion_allowed") is not False
            or boundary.get("writer_citable") is not False
            or boundary.get("domain_judgment_eligible") is not False
            or boundary.get("financial_fact_authority") is not False
            or boundary.get("production_capability_claim_allowed") is not False
            or boundary.get("numeric_authority") != "none"
        ):
            raise SearXNGDiagnosticError("searxng_policy_false_promotion")

    def _validate_query(self, query: SearXNGDiagnosticQuery) -> None:
        if query.query_digest != canonical_digest(query.digest_body()):
            raise SearXNGDiagnosticError("searxng_query_digest_invalid")
        if query.case_key not in set(self.policy["allowed_case_keys"]):
            raise SearXNGDiagnosticError("searxng_cross_case_or_unknown_case")
        if not query.query_id.strip() or not query.evidence_slot_id.strip() or not query.query_text.strip():
            raise SearXNGDiagnosticError("searxng_query_required_field_missing")
        if len(query.query_text) > int(self.policy["query_contract"]["max_query_chars"]):
            raise SearXNGDiagnosticError("searxng_query_text_ceiling_exceeded")
        if not query.categories or not set(query.categories).issubset(
            set(self.policy["query_contract"]["allowed_categories"])
        ):
            raise SearXNGDiagnosticError("searxng_query_category_invalid")
        if query.time_range not in set(self.policy["query_contract"]["allowed_time_ranges"]):
            raise SearXNGDiagnosticError("searxng_query_time_range_invalid")
        maximum = int(self.policy["budgets"]["result_ceiling_per_query"])
        if query.result_ceiling <= 0 or query.result_ceiling > maximum:
            raise SearXNGDiagnosticError("searxng_result_ceiling_invalid")

    def _persist_response(
        self,
        *,
        query: SearXNGDiagnosticQuery,
        request_ref: Mapping[str, Any],
        response: SearXNGDiagnosticResponse,
    ) -> dict[str, Any]:
        return self._persist(
            {
                "schema_version": CAPTURE_SCHEMA,
                "capture_kind": "diagnostic_search_response",
                "contract_ref": CONTRACT_REF,
                "query_digest": query.query_digest,
                "request_capture_ref": request_ref["object_key"],
                "request_capture_digest": request_ref["digest"],
                "status_code": response.status_code,
                "final_url": response.final_url,
                "headers": {
                    key.lower(): str(value)
                    for key, value in response.headers.items()
                    if key.lower() in _SAFE_RESPONSE_HEADERS
                },
                "redirect_chain": list(response.redirect_chain),
                "body_base64": base64.b64encode(response.body).decode("ascii"),
                "body_sha256": hashlib.sha256(response.body).hexdigest(),
                "body_bytes": len(response.body),
                "body_ceiling_exceeded": response.body_ceiling_exceeded,
                "capture_before_parse": True,
                "credential_cookie_authorization_present": False,
            },
            "searxng_diagnostic_response",
        )

    def _classify_response(self, response: SearXNGDiagnosticResponse) -> str:
        if _url_origin(response.final_url) != _url_origin(str(self.policy["base_url"])):
            return "searxng_final_origin_drift"
        if response.body_ceiling_exceeded:
            return "searxng_body_ceiling_exceeded"
        if response.status_code == 403:
            return "searxng_json_format_disabled_or_forbidden"
        if response.status_code == 429:
            return "searxng_rate_limited"
        if not 200 <= response.status_code < 300:
            return f"searxng_http_{response.status_code}"
        return ""

    def _terminal(
        self,
        *,
        query: SearXNGDiagnosticQuery,
        request_ref: Mapping[str, Any],
        response_ref: Mapping[str, Any],
        status: str,
        terminal_code: str,
        locators: Sequence[Mapping[str, Any]] = (),
        rejection_codes: Sequence[str] = (),
        upstream_raw_result_count: int = 0,
        unresponsive_engines: Sequence[Mapping[str, str]] = (),
    ) -> dict[str, Any]:
        locator_rows = [dict(row) for row in locators]
        locator_bundle_digest = canonical_digest(locator_rows)
        receipt_ref = self._persist(
            {
                "schema_version": CAPTURE_SCHEMA,
                "capture_kind": "diagnostic_search_normalization_receipt",
                "contract_ref": CONTRACT_REF,
                "query_digest": query.query_digest,
                "status": status,
                "terminal_code": terminal_code,
                "upstream_raw_result_count": int(upstream_raw_result_count),
                "normalized_locator_count": len(locator_rows),
                "locator_bundle_digest": locator_bundle_digest,
                "rejection_codes": sorted(str(value) for value in rejection_codes),
                "unresponsive_engines": [dict(row) for row in unresponsive_engines],
            },
            "searxng_diagnostic_normalization_receipt",
        )
        body = {
            "schema_version": RESULT_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "provider_kind": "self_hosted_searxng_diagnostic_locator",
            "provider_lifecycle_state": "diagnostic_adapter_proven",
            "query": {**query.digest_body(), "query_digest": query.query_digest},
            "status": status,
            "terminal_code": terminal_code,
            "request_capture": dict(request_ref),
            "response_capture": dict(response_ref),
            "normalization_receipt": dict(receipt_ref),
            "locators": locator_rows,
            "locator_bundle_digest": locator_bundle_digest,
            "unresponsive_engines": [dict(row) for row in unresponsive_engines],
            "rejection_codes": sorted(str(value) for value in rejection_codes),
            "observed_counts": {
                "upstream_raw_results": int(upstream_raw_result_count),
                "normalized_locators": len(locator_rows),
                "query_calls": 1,
                "network_calls": int(bool(self.transport.live_network)),
                "model_calls": 0,
                "provider_model_calls": 0,
                "evidence_promotions": 0,
            },
            "capability_boundary": {
                "promotion_status": PROMOTION_STATUS,
                "evidence_promotion_allowed": False,
                "writer_citable": False,
                "domain_judgment_eligible": False,
                "financial_fact_authority": False,
                "numeric_authority": "none",
                "production_capability_claim_allowed": False,
            },
        }
        result = {**body, "result_digest": canonical_digest(body)}
        validate_searxng_diagnostic_result(result)
        return result

    def _persist(self, payload: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
        ref = self.store.put_json(payload, namespace=CAPTURE_NAMESPACE, artifact_type=artifact_type)
        observed = self.store.get_json(ref["object_key"], expected_digest=ref["digest"])
        if canonical_digest(observed) != ref["digest"]:
            raise SearXNGDiagnosticError("searxng_capture_readback_failed")
        self.capture_refs.append(ref)
        return ref


def validate_searxng_diagnostic_result(result: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(result)
    digest = body.pop("result_digest", None)
    if (
        body.get("schema_version") != RESULT_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(body)
    ):
        raise SearXNGDiagnosticError("searxng_result_identity_invalid")
    boundary = body.get("capability_boundary") or {}
    forbidden_true = (
        "evidence_promotion_allowed",
        "writer_citable",
        "domain_judgment_eligible",
        "financial_fact_authority",
        "production_capability_claim_allowed",
    )
    if (
        boundary.get("promotion_status") != PROMOTION_STATUS
        or any(boundary.get(key) is not False for key in forbidden_true)
        or boundary.get("numeric_authority") != "none"
    ):
        raise SearXNGDiagnosticError("searxng_result_false_promotion")
    for locator in body.get("locators") or ():
        if (
            locator.get("promotion_status") != PROMOTION_STATUS
            or locator.get("evidence_promotion_allowed") is not False
            or locator.get("writer_citable") is not False
            or locator.get("domain_judgment_eligible") is not False
            or locator.get("financial_fact_authority") is not False
            or locator.get("numeric_authority") != "none"
        ):
            raise SearXNGDiagnosticError("searxng_locator_false_promotion")
        locator_body = dict(locator)
        locator_digest = locator_body.pop("locator_digest", None)
        if locator_digest != canonical_digest(locator_body):
            raise SearXNGDiagnosticError("searxng_locator_digest_invalid")
    if body.get("locator_bundle_digest") != canonical_digest(body.get("locators") or []):
        raise SearXNGDiagnosticError("searxng_locator_bundle_digest_invalid")
    if int((body.get("observed_counts") or {}).get("evidence_promotions", -1)) != 0:
        raise SearXNGDiagnosticError("searxng_result_false_promotion")
    return dict(result)


def _normalize_results(
    results: Sequence[Any], *, result_ceiling: int
) -> tuple[list[dict[str, Any]], list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    rejection_codes: list[str] = []
    for ordinal, raw in enumerate(results, start=1):
        if not isinstance(raw, Mapping):
            rejection_codes.append("searxng_result_row_not_object")
            continue
        try:
            canonical_locator = canonicalize_diagnostic_locator(str(raw.get("url") or ""))
        except SearXNGDiagnosticError as exc:
            rejection_codes.append(exc.code)
            continue
        engines = _engines(raw)
        positions = raw.get("positions") if isinstance(raw.get("positions"), list) else []
        observations = [
            {
                "engine": engine,
                "rank_candidate": int(positions[index])
                if index < len(positions) and isinstance(positions[index], int) and positions[index] > 0
                else ordinal,
            }
            for index, engine in enumerate(engines)
        ]
        if not observations:
            observations = [{"engine": "unattributed", "rank_candidate": ordinal}]
        grouped.setdefault(canonical_locator, []).append(
            {
                "original_url": str(raw.get("url") or ""),
                "title": _bounded_text(raw.get("title"), 500),
                "snippet_candidate": _bounded_text(raw.get("content"), 4000),
                "published_on_candidate": _bounded_text(
                    raw.get("publishedDate") or raw.get("published_date"), 128
                ),
                "score_candidate": _score_candidate(raw.get("score")),
                "engine_observations": observations,
            }
        )
    locators: list[dict[str, Any]] = []
    for canonical_locator, rows in grouped.items():
        observations = sorted(
            {
                (str(item["engine"]), int(item["rank_candidate"]))
                for row in rows
                for item in row["engine_observations"]
            }
        )
        title = _deterministic_best_text(row["title"] for row in rows)
        snippet = _deterministic_best_text(row["snippet_candidate"] for row in rows)
        published = _deterministic_best_text(
            row["published_on_candidate"] for row in rows
        )
        scores = sorted(
            {row["score_candidate"] for row in rows if row["score_candidate"] is not None}
        )
        row_body = {
            "canonical_locator": canonical_locator,
            "original_locator_candidates": sorted(
                {canonicalize_diagnostic_locator(row["original_url"]) for row in rows}
            ),
            "title": title,
            "snippet_candidate": snippet,
            "published_on_candidate": published,
            "source_engines": sorted({engine for engine, _ in observations}),
            "engine_rank_candidates": [
                {"engine": engine, "rank_candidate": rank}
                for engine, rank in observations
            ],
            "best_rank_candidate": min(rank for _, rank in observations),
            "score_candidates": scores,
            "promotion_status": PROMOTION_STATUS,
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
        }
        locators.append({**row_body, "locator_digest": canonical_digest(row_body)})
    locators.sort(key=lambda row: (row["best_rank_candidate"], row["canonical_locator"]))
    return locators[:result_ceiling], sorted(rejection_codes)


def canonicalize_diagnostic_locator(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as exc:
        raise SearXNGDiagnosticError("searxng_locator_url_invalid") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise SearXNGDiagnosticError("searxng_locator_url_invalid")
    if parsed.username or parsed.password:
        raise SearXNGDiagnosticError("searxng_locator_credentials_forbidden")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = (parsed.scheme.lower() == "http" and port == 80) or (
        parsed.scheme.lower() == "https" and port == 443
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    filtered_query = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in _TRACKING_QUERY_KEYS
        and key.lower() not in _SENSITIVE_QUERY_KEYS
    )
    path = parsed.path or "/"
    return urlunsplit(
        (parsed.scheme.lower(), netloc, path, urlencode(filtered_query, doseq=True), "")
    )


def _validated_loopback_base_url(base_url: str) -> str:
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise SearXNGDiagnosticError("searxng_base_url_invalid") from exc
    if (
        parsed.scheme.lower() != "http"
        or (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port is None
    ):
        raise SearXNGDiagnosticError("searxng_base_url_not_loopback")
    return base_url.rstrip("/")


def _url_origin(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    default_port = 80 if parsed.scheme.lower() == "http" else 443
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    return f"{parsed.scheme.lower()}://{host}:{port or default_port}"


def _engines(row: Mapping[str, Any]) -> list[str]:
    engines = row.get("engines") if isinstance(row.get("engines"), list) else []
    values = [str(value).strip() for value in engines if str(value).strip()]
    engine = str(row.get("engine") or "").strip()
    if engine:
        values.append(engine)
    return sorted(set(values))


def _bounded_text(value: Any, ceiling: int) -> str:
    return " ".join(str(value or "").split())[:ceiling]


def _deterministic_best_text(values: Sequence[str] | Any) -> str:
    candidates = sorted({str(value) for value in values if str(value)})
    return max(candidates, key=lambda value: (len(value), value)) if candidates else ""


def _score_candidate(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return format(value, ".12g")


def _normalize_unresponsive_engines(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, (list, tuple)) and item:
            rows.append(
                {
                    "engine": _bounded_text(item[0], 120),
                    "reason": _bounded_text(item[1] if len(item) > 1 else "", 240),
                }
            )
        elif isinstance(item, str):
            rows.append({"engine": _bounded_text(item, 120), "reason": ""})
    return sorted(rows, key=lambda row: (row["engine"], row["reason"]))
