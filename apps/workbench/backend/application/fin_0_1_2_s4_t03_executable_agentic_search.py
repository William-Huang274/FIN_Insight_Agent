from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from apps.workbench.backend.application.fin_0_1_2_s4_retrieval_evidence_readiness import (
    RetrievalEvidenceRequest,
    load_current_fin_0_1_2_s4_t02_readiness,
)
from retrieval.bm25_retriever import BM25Retriever
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


CONTRACT_REF = "fin_0_1_2.S4.T03.executable_agentic_search:v1"
REQUEST_SCHEMA = "fin_ia_0_1_2_s4_t03_executable_search_request_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_2_s4_t03_agentic_search_admission_v1_0"
RUN_SCHEMA = "fin_ia_0_1_2_s4_t03_agentic_search_run_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_2_s4_t03_agentic_search_terminal_result_v1_0"
SOURCE_CAPTURE_SCHEMA = "fin_ia_0_1_2_s4_t03_source_interaction_capture_v1_0"
LOCAL_CAPTURE_SCHEMA = "fin_ia_0_1_2_s4_t03_local_retrieval_capture_v1_0"

NVDA_CIK = "0001045810"
NVDA_SEC_SUBMISSIONS_URL = (
    "https://data.sec.gov/submissions/CIK0001045810.json"
)
NVDA_IR_URL = "https://investor.nvidia.com/financial-info/financial-reports-and-filings/default.aspx"

TEXT_INDEX_RELATIVE_PATH = (
    "data/indexes/bm25/"
    "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027"
)
GOLD_MART_RELATIVE_PATH = (
    "data/workbench_private/research_data/gold_fact_signal_mart_v0_1.sqlite"
)
RESEARCH_GRAPH_RELATIVE_PATH = (
    "data/workbench_private/research_data/research_graph_store_v0_1.sqlite"
)

SOURCE_CAPTURE_NAMESPACE = "s4-t03/source-interaction-captures"
LOCAL_CAPTURE_NAMESPACE = "s4-t03/local-retrieval-captures"
TERMINAL_NAMESPACE = "s4-t03/terminal-results"

QUERY_PROFILES: Mapping[str, Mapping[str, Any]] = {
    "bottleneck_counterevidence_and_what_would_change": {
        "query_text": (
            "supply constraints export controls customer concentration data center "
            "revenue risks earnings release what could change the thesis"
        ),
        "accepted_candidate_roles": (
            "issuer_counterevidence_statement",
            "relationship_context",
        ),
        "empty_candidate_gap_code": "current_counterevidence_search_required",
    },
    "demand_authenticity_and_sustainability": {
        "query_text": (
            "data center revenue demand customer deployment orders backlog AI "
            "infrastructure demand sustainability"
        ),
        "accepted_candidate_roles": (
            "issuer_demand_statement",
            "relationship_context",
        ),
        "empty_candidate_gap_code": "current_demand_evidence_search_required",
    },
    "value_and_profit_capture": {
        "query_text": (
            "revenue gross profit operating income cash flow data center value "
            "and profit capture"
        ),
        "accepted_candidate_roles": (
            "issuer_financial_statement",
            "exact_numeric_context",
        ),
        "empty_candidate_gap_code": "current_value_evidence_search_required",
    },
}

ROUTE_REGISTRY: Mapping[str, tuple[str, ...]] = {
    "official_issuer_disclosure_metadata_route": (
        "sec_edgar_current_disclosure",
        "nvda_investor_relations_current_disclosure",
    ),
    "local_relationship_graph_metadata_route": (
        "relationship_graph_read_only",
    ),
    "public_source_index_metadata_route": (
        "route_catalog_only_not_direct_evidence",
    ),
    "local_exact_value_sql_metadata_route": (
        "exact_value_sql_read_only",
    ),
}

ALLOWED_SOURCE_HOSTS = {
    "data.sec.gov",
    "www.sec.gov",
    "investor.nvidia.com",
}

SAFE_RESPONSE_HEADERS = {
    "content-type",
    "content-length",
    "last-modified",
    "etag",
}


class Fin012S4T03SearchError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _date_only(value: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise Fin012S4T03SearchError("date_value_required")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError as exc:
            raise Fin012S4T03SearchError("date_value_invalid") from exc


def _clip(value: str, limit: int = 1200) -> str:
    normalized = " ".join(str(value or "").split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs").is_dir() and (parent / "src").is_dir():
            return parent
    raise Fin012S4T03SearchError("repository_root_not_found")


def _portable_stat_digest(path: Path) -> str:
    stat = path.stat()
    return canonical_digest({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns})


def _sec_accession(value: str) -> str:
    match = re.search(r"::(?P<accession>\d{18})::", str(value or ""))
    return match.group("accession") if match else ""


def _sec_archive_url(*, cik: str, accession: str, primary_document: str) -> str:
    cik_number = str(int(re.sub(r"\D", "", cik)))
    accession_compact = re.sub(r"\D", "", accession)
    if not accession_compact or not primary_document:
        return ""
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_number}/"
        f"{accession_compact}/{primary_document}"
    )


@dataclass(frozen=True)
class ExecutableSearchRequest:
    schema_version: str
    contract_ref: str
    request_id: str
    request_digest: str
    parent_request_id: str
    parent_request_digest: str
    case_key: str
    program_cell_id: str
    objective_digest: str
    target_entity_ref: str
    as_of: str
    query_text: str
    metadata_route_ids: tuple[str, ...]
    executable_adapter_ids: tuple[str, ...]
    accepted_candidate_roles: tuple[str, ...]
    candidate_ceiling: int
    source_allowlist: tuple[str, ...]
    source_locators: tuple[str, ...]
    parser_adapters: tuple[str, ...]
    source_policy_ref: str
    empty_candidate_gap_code: str
    writer_citable: bool = False
    domain_judgment_eligible: bool = False

    def require_valid(self) -> None:
        payload = {
            key: value
            for key, value in self.as_dict().items()
            if key not in {"request_id", "request_digest"}
        }
        if self.request_digest != canonical_digest(payload) or self.request_id != (
            f"executable_search_request_{self.request_digest[:20]}"
        ):
            raise Fin012S4T03SearchError("t03_executable_request_digest_mismatch")
        if self.case_key != "NVDA" or self.target_entity_ref != "NVDA":
            raise Fin012S4T03SearchError("t03_executable_request_case_mismatch")
        if self.writer_citable or self.domain_judgment_eligible:
            raise Fin012S4T03SearchError("t03_executable_request_nonpromotion_invalid")
        if not self.query_text or self.candidate_ceiling != 6:
            raise Fin012S4T03SearchError("t03_executable_request_query_or_ceiling_invalid")
        if set(self.source_allowlist) != ALLOWED_SOURCE_HOSTS:
            raise Fin012S4T03SearchError("t03_executable_request_allowlist_invalid")
        for route_id in self.metadata_route_ids:
            if route_id not in ROUTE_REGISTRY:
                raise Fin012S4T03SearchError("t03_executable_request_route_invalid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_ref": self.contract_ref,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "parent_request_id": self.parent_request_id,
            "parent_request_digest": self.parent_request_digest,
            "case_key": self.case_key,
            "program_cell_id": self.program_cell_id,
            "objective_digest": self.objective_digest,
            "target_entity_ref": self.target_entity_ref,
            "as_of": self.as_of,
            "query_text": self.query_text,
            "metadata_route_ids": list(self.metadata_route_ids),
            "executable_adapter_ids": list(self.executable_adapter_ids),
            "accepted_candidate_roles": list(self.accepted_candidate_roles),
            "candidate_ceiling": self.candidate_ceiling,
            "source_allowlist": list(self.source_allowlist),
            "source_locators": list(self.source_locators),
            "parser_adapters": list(self.parser_adapters),
            "source_policy_ref": self.source_policy_ref,
            "empty_candidate_gap_code": self.empty_candidate_gap_code,
            "writer_citable": self.writer_citable,
            "domain_judgment_eligible": self.domain_judgment_eligible,
        }


def compile_executable_search_request(
    request: RetrievalEvidenceRequest,
) -> ExecutableSearchRequest:
    if request.case_key != "NVDA" or request.target_entity_ref != "NVDA":
        raise Fin012S4T03SearchError("t03_only_nvda_canary_is_compilable")
    profile = QUERY_PROFILES.get(request.program_cell_id)
    if profile is None:
        raise Fin012S4T03SearchError("t03_program_cell_query_profile_missing")
    executable: list[str] = []
    for route_id in request.route_ids:
        adapters = ROUTE_REGISTRY.get(route_id)
        if adapters is None:
            raise Fin012S4T03SearchError("t03_metadata_route_binding_missing")
        executable.extend(adapters)
    payload = {
        "schema_version": REQUEST_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "parent_request_id": request.request_id,
        "parent_request_digest": request.request_digest,
        "case_key": request.case_key,
        "program_cell_id": request.program_cell_id,
        "objective_digest": request.objective_digest,
        "target_entity_ref": request.target_entity_ref,
        "as_of": request.as_of,
        "query_text": profile["query_text"],
        "metadata_route_ids": tuple(request.route_ids),
        "executable_adapter_ids": tuple(dict.fromkeys(executable)),
        "accepted_candidate_roles": tuple(profile["accepted_candidate_roles"]),
        "candidate_ceiling": request.candidate_ceiling,
        "source_allowlist": tuple(sorted(ALLOWED_SOURCE_HOSTS)),
        "source_locators": (NVDA_SEC_SUBMISSIONS_URL, NVDA_IR_URL),
        "parser_adapters": (
            "sec_submissions_recent_filings_v1",
            "nvda_ir_filing_link_parser_v1",
            "local_sec_chunk_projection_v1",
            "research_graph_projection_v1",
            "gold_fact_projection_v1",
        ),
        "source_policy_ref": "official_identity_then_read_only_local_content:v1",
        "empty_candidate_gap_code": profile["empty_candidate_gap_code"],
        "writer_citable": False,
        "domain_judgment_eligible": False,
    }
    digest = canonical_digest(payload)
    compiled = ExecutableSearchRequest(
        request_id=f"executable_search_request_{digest[:20]}",
        request_digest=digest,
        **payload,
    )
    compiled.require_valid()
    return compiled


@dataclass(frozen=True)
class SearchAdmission:
    admission_id: str
    admission_digest: str
    issued_at: str
    expires_at: str
    case_key: str
    request_digests: tuple[str, ...]
    source_network_call_ceiling: int
    local_invocation_ceiling: int
    retry_ceiling: int
    fallback_ceiling: int
    wall_clock_seconds: int
    model_calls: int = 0
    provider_calls: int = 0
    paid_api_cost_usd: float = 0.0

    @classmethod
    def create(
        cls,
        *,
        issued_at: str,
        expires_at: str,
        request_digests: Sequence[str],
    ) -> "SearchAdmission":
        payload = {
            "schema_version": ADMISSION_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "case_key": "NVDA",
            "request_digests": tuple(request_digests),
            "source_network_call_ceiling": 2,
            "local_invocation_ceiling": 8,
            "retry_ceiling": 0,
            "fallback_ceiling": 1,
            "wall_clock_seconds": 300,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_api_cost_usd": 0.0,
        }
        digest = canonical_digest(payload)
        return cls(
            admission_id=f"s4_t03_search_admission_{digest[:20]}",
            admission_digest=digest,
            **{key: value for key, value in payload.items() if key not in {"schema_version", "contract_ref"}},
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SearchAdmission":
        expected = {
            "schema_version",
            "contract_ref",
            "admission_id",
            "admission_digest",
            "issued_at",
            "expires_at",
            "case_key",
            "request_digests",
            "source_network_call_ceiling",
            "local_invocation_ceiling",
            "retry_ceiling",
            "fallback_ceiling",
            "wall_clock_seconds",
            "model_calls",
            "provider_calls",
            "paid_api_cost_usd",
        }
        if set(value) != expected:
            raise Fin012S4T03SearchError("t03_admission_shape_invalid")
        if value.get("schema_version") != ADMISSION_SCHEMA or value.get("contract_ref") != CONTRACT_REF:
            raise Fin012S4T03SearchError("t03_admission_contract_identity_invalid")
        try:
            return cls(
                admission_id=str(value["admission_id"]),
                admission_digest=str(value["admission_digest"]),
                issued_at=str(value["issued_at"]),
                expires_at=str(value["expires_at"]),
                case_key=str(value["case_key"]),
                request_digests=tuple(str(row) for row in value["request_digests"]),
                source_network_call_ceiling=int(value["source_network_call_ceiling"]),
                local_invocation_ceiling=int(value["local_invocation_ceiling"]),
                retry_ceiling=int(value["retry_ceiling"]),
                fallback_ceiling=int(value["fallback_ceiling"]),
                wall_clock_seconds=int(value["wall_clock_seconds"]),
                model_calls=int(value["model_calls"]),
                provider_calls=int(value["provider_calls"]),
                paid_api_cost_usd=float(value["paid_api_cost_usd"]),
            )
        except (TypeError, ValueError) as exc:
            raise Fin012S4T03SearchError("t03_admission_shape_invalid") from exc

    def require_active(self, *, now: str, requests: Sequence[ExecutableSearchRequest]) -> None:
        expected_payload = {
            "schema_version": ADMISSION_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "case_key": self.case_key,
            "request_digests": self.request_digests,
            "source_network_call_ceiling": self.source_network_call_ceiling,
            "local_invocation_ceiling": self.local_invocation_ceiling,
            "retry_ceiling": self.retry_ceiling,
            "fallback_ceiling": self.fallback_ceiling,
            "wall_clock_seconds": self.wall_clock_seconds,
            "model_calls": self.model_calls,
            "provider_calls": self.provider_calls,
            "paid_api_cost_usd": self.paid_api_cost_usd,
        }
        if self.admission_digest != canonical_digest(expected_payload) or self.admission_id != (
            f"s4_t03_search_admission_{self.admission_digest[:20]}"
        ):
            raise Fin012S4T03SearchError("t03_admission_digest_mismatch")
        if self.case_key != "NVDA" or any(row.case_key != self.case_key for row in requests):
            raise Fin012S4T03SearchError("t03_admission_case_identity_mismatch")
        if tuple(row.request_digest for row in requests) != self.request_digests:
            raise Fin012S4T03SearchError("t03_admission_request_digest_mismatch")
        if not (_date_time(self.issued_at) <= _date_time(now) <= _date_time(self.expires_at)):
            raise Fin012S4T03SearchError("t03_admission_not_active")
        if (self.model_calls, self.provider_calls, self.paid_api_cost_usd) != (0, 0, 0.0):
            raise Fin012S4T03SearchError("t03_admission_not_zero_model")
        if (
            self.source_network_call_ceiling,
            self.local_invocation_ceiling,
            self.retry_ceiling,
            self.fallback_ceiling,
            self.wall_clock_seconds,
        ) != (2, 8, 0, 1, 300):
            raise Fin012S4T03SearchError("t03_admission_budget_contract_mismatch")
        if len(self.request_digests) != 3 or len(set(self.request_digests)) != 3:
            raise Fin012S4T03SearchError("t03_admission_request_topology_invalid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ADMISSION_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "admission_id": self.admission_id,
            "admission_digest": self.admission_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "case_key": self.case_key,
            "request_digests": list(self.request_digests),
            "source_network_call_ceiling": self.source_network_call_ceiling,
            "local_invocation_ceiling": self.local_invocation_ceiling,
            "retry_ceiling": self.retry_ceiling,
            "fallback_ceiling": self.fallback_ceiling,
            "wall_clock_seconds": self.wall_clock_seconds,
            "model_calls": self.model_calls,
            "provider_calls": self.provider_calls,
            "paid_api_cost_usd": self.paid_api_cost_usd,
        }


def _date_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SourceResponse:
    status_code: int
    final_url: str
    headers: Mapping[str, str]
    body: bytes


class SourceTransport(Protocol):
    live_network: bool

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse: ...


class _AllowlistRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Request | None:
        host = (urlparse(newurl).hostname or "").lower()
        if host not in self._allowed_hosts:
            raise Fin012S4T03SearchError("t03_non_allowlisted_redirect_blocked")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibSourceTransport:
    live_network = True

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse:
        host = (urlparse(url).hostname or "").lower()
        if urlparse(url).scheme != "https" or host not in allowed_hosts:
            raise Fin012S4T03SearchError("t03_source_url_not_allowlisted_https")
        opener = build_opener(_AllowlistRedirectHandler(allowed_hosts))
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = response.read()
                final_url = response.geturl()
                response_headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower() in SAFE_RESPONSE_HEADERS
                }
                return SourceResponse(
                    status_code=int(response.status),
                    final_url=final_url,
                    headers=response_headers,
                    body=body,
                )
        except (HTTPError, URLError, TimeoutError) as exc:
            raise Fin012S4T03SearchError("t03_source_fetch_failed") from exc


class CaptureFirstSourceClient:
    def __init__(
        self,
        *,
        store: FileCanonicalObjectStore,
        transport: SourceTransport,
    ) -> None:
        self._store = store
        self._transport = transport
        self.capture_objects: list[dict[str, Any]] = []
        self.logical_source_calls = 0
        self.live_network_calls = 0

    def fetch(self, *, url: str, allowed_hosts: set[str], timeout_seconds: int = 25) -> SourceResponse:
        request_headers = {
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.1",
            "User-Agent": "FIN-Insight-Agent research-canary contact=local-operator",
        }
        request_capture = {
            "schema_version": SOURCE_CAPTURE_SCHEMA,
            "capture_kind": "source_request",
            "sequence": len(self.capture_objects) + 1,
            "method": "GET",
            "url": url,
            "headers": request_headers,
            "credential_cookie_authorization_present": False,
            "captured_at": _utc_now(),
        }
        request_object = self._store.put_json(
            request_capture,
            namespace=SOURCE_CAPTURE_NAMESPACE,
            artifact_type="source_request_capture",
        )
        self._readback(request_object)
        self.capture_objects.append(request_object)
        self.logical_source_calls += 1
        if self._transport.live_network:
            self.live_network_calls += 1
        response = self._transport.fetch(
            url=url,
            headers=request_headers,
            allowed_hosts=allowed_hosts,
            timeout_seconds=timeout_seconds,
        )
        response_capture = {
            "schema_version": SOURCE_CAPTURE_SCHEMA,
            "capture_kind": "source_response",
            "sequence": len(self.capture_objects) + 1,
            "request_capture_digest": request_object["digest"],
            "status_code": response.status_code,
            "final_url": response.final_url,
            "headers": {
                key.lower(): str(value)
                for key, value in response.headers.items()
                if key.lower() in SAFE_RESPONSE_HEADERS
            },
            "body_base64": base64.b64encode(response.body).decode("ascii"),
            "body_sha256": _sha256_bytes(response.body),
            "body_bytes": len(response.body),
            "credential_cookie_authorization_present": False,
            "capture_before_parse": True,
            "captured_at": _utc_now(),
        }
        response_object = self._store.put_json(
            response_capture,
            namespace=SOURCE_CAPTURE_NAMESPACE,
            artifact_type="source_response_capture",
        )
        self._readback(response_object)
        self.capture_objects.append(response_object)
        final_host = (urlparse(response.final_url).hostname or "").lower()
        if urlparse(response.final_url).scheme != "https" or final_host not in allowed_hosts:
            raise Fin012S4T03SearchError("t03_source_final_url_not_allowlisted_https")
        if response.status_code < 200 or response.status_code >= 300:
            raise Fin012S4T03SearchError("t03_source_http_status_unusable")
        return response

    def _readback(self, obj: Mapping[str, Any]) -> None:
        payload = self._store.get_json(
            str(obj["object_key"]), expected_digest=str(obj["digest"])
        )
        if canonical_digest(payload) != obj["digest"]:
            raise Fin012S4T03SearchError("t03_source_capture_readback_mismatch")


@dataclass(frozen=True)
class OfficialFilingIdentity:
    accession: str
    filed_at: str
    form_type: str
    primary_document: str
    source_url: str
    source_capture_ref: str
    source_capture_digest: str
    parser_adapter: str


def parse_sec_submissions(
    response: SourceResponse,
    *,
    as_of: str,
    response_capture: Mapping[str, Any],
) -> tuple[OfficialFilingIdentity, ...]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
        recent = payload["filings"]["recent"]
        accessions = recent["accessionNumber"]
        forms = recent["form"]
        filed = recent["filingDate"]
        primary_documents = recent["primaryDocument"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise Fin012S4T03SearchError("t03_sec_submissions_parse_failed") from exc
    if not all(len(rows) == len(accessions) for rows in (forms, filed, primary_documents)):
        raise Fin012S4T03SearchError("t03_sec_submissions_parallel_arrays_invalid")
    cutoff = _date_only(as_of)
    out: list[OfficialFilingIdentity] = []
    for accession, form_type, filed_at, primary_document in zip(
        accessions, forms, filed, primary_documents
    ):
        if str(form_type) not in {"10-K", "10-Q", "8-K"}:
            continue
        if _date_only(str(filed_at)) > cutoff:
            continue
        compact_accession = re.sub(r"\D", "", str(accession))
        url = _sec_archive_url(
            cik=NVDA_CIK,
            accession=compact_accession,
            primary_document=str(primary_document),
        )
        out.append(
            OfficialFilingIdentity(
                accession=compact_accession,
                filed_at=str(filed_at),
                form_type=str(form_type),
                primary_document=str(primary_document),
                source_url=url,
                source_capture_ref=str(response_capture["object_key"]),
                source_capture_digest=str(response_capture["digest"]),
                parser_adapter="sec_submissions_recent_filings_v1",
            )
        )
    return tuple(out)


def parse_nvda_ir_links(
    response: SourceResponse,
    *,
    as_of: str,
    response_capture: Mapping[str, Any],
) -> tuple[OfficialFilingIdentity, ...]:
    try:
        text = response.body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise Fin012S4T03SearchError("t03_nvda_ir_parse_failed") from exc
    cutoff = _date_only(as_of)
    anchors = re.findall(
        r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<title>.*?)</a>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    out: list[OfficialFilingIdentity] = []
    for index, (href, raw_title) in enumerate(anchors):
        title = _clip(html.unescape(re.sub(r"<[^>]+>", " ", raw_title)), 240)
        absolute = urljoin(response.final_url, html.unescape(href))
        host = (urlparse(absolute).hostname or "").lower()
        if host not in ALLOWED_SOURCE_HOSTS or not re.search(
            r"(quarter|annual|financial|filing|results|earnings)", title, re.I
        ):
            continue
        date_match = re.search(r"20\d{2}[-/]\d{2}[-/]\d{2}", title + " " + absolute)
        filed_at = date_match.group(0).replace("/", "-") if date_match else cutoff.isoformat()
        if _date_only(filed_at) > cutoff:
            continue
        synthetic = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:18]
        out.append(
            OfficialFilingIdentity(
                accession=synthetic,
                filed_at=filed_at,
                form_type="issuer_IR",
                primary_document=title or f"NVDA IR link {index + 1}",
                source_url=absolute,
                source_capture_ref=str(response_capture["object_key"]),
                source_capture_digest=str(response_capture["digest"]),
                parser_adapter="nvda_ir_filing_link_parser_v1",
            )
        )
        if len(out) >= 12:
            break
    return tuple(out)


@dataclass(frozen=True)
class SearchCandidate:
    candidate_id: str
    request_digest: str
    program_cell_id: str
    entity_ref: str
    candidate_role: str
    adapter_id: str
    route_id: str
    title: str
    excerpt: str
    published_at: str
    source_url: str
    locator: str
    source_snapshot_ref: str
    source_snapshot_digest: str
    parser_adapter: str
    parser_digest: str
    source_authority_rank: int
    score: float
    exact_value_authority: bool
    writer_citable: bool = False
    domain_judgment_eligible: bool = False

    @classmethod
    def create(cls, **payload: Any) -> "SearchCandidate":
        digest_payload = {
            **payload,
            "writer_citable": False,
            "domain_judgment_eligible": False,
        }
        digest = canonical_digest(digest_payload)
        return cls(
            candidate_id=f"s4_t03_candidate_{digest[:24]}",
            **digest_payload,
        )

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class LocalCaptureWriter:
    def __init__(self, store: FileCanonicalObjectStore) -> None:
        self._store = store
        self.capture_objects: list[dict[str, Any]] = []

    def capture(self, *, adapter_id: str, request: ExecutableSearchRequest, rows: Any) -> dict[str, Any]:
        payload = {
            "schema_version": LOCAL_CAPTURE_SCHEMA,
            "adapter_id": adapter_id,
            "request_id": request.request_id,
            "request_digest": request.request_digest,
            "captured_at": _utc_now(),
            "rows": rows,
            "read_only": True,
            "capture_before_projection": True,
        }
        obj = self._store.put_json(
            payload,
            namespace=LOCAL_CAPTURE_NAMESPACE,
            artifact_type="local_retrieval_capture",
        )
        readback = self._store.get_json(
            str(obj["object_key"]), expected_digest=str(obj["digest"])
        )
        if canonical_digest(readback) != obj["digest"]:
            raise Fin012S4T03SearchError("t03_local_capture_readback_mismatch")
        self.capture_objects.append(obj)
        return obj


class BM25SearchAdapter:
    adapter_id = "issuer_document_bm25_read_only"
    route_id = "official_issuer_disclosure_metadata_route"

    def __init__(self, *, index_dir: Path, capture: LocalCaptureWriter) -> None:
        self._index_dir = index_dir
        self._capture = capture
        self._retriever = BM25Retriever(self._index_dir)

    def search(
        self,
        request: ExecutableSearchRequest,
        *,
        official_filings: Mapping[str, OfficialFilingIdentity],
    ) -> tuple[SearchCandidate, ...]:
        rows = self._retriever.search(
            request.query_text,
            top_k=request.candidate_ceiling,
            filters={"ticker": request.case_key},
        )
        capture = self._capture.capture(
            adapter_id=self.adapter_id,
            request=request,
            rows=rows,
        )
        out: list[SearchCandidate] = []
        for row in rows:
            record = dict(row.get("record") or {})
            source_ref = str(row.get("evidence_id") or record.get("evidence_id") or "")
            metadata = dict(record.get("metadata") or {})
            accession = re.sub(
                r"\D",
                "",
                str(metadata.get("accession_number") or _sec_accession(source_ref)),
            )
            filing = official_filings.get(accession)
            if filing is None:
                continue
            excerpt = _clip(
                str(record.get("text") or row.get("text_preview") or "")
            )
            if not excerpt:
                continue
            role = (
                "issuer_demand_statement"
                if request.program_cell_id == "demand_authenticity_and_sustainability"
                else "issuer_financial_statement"
                if request.program_cell_id == "value_and_profit_capture"
                else "issuer_counterevidence_statement"
            )
            out.append(
                SearchCandidate.create(
                    request_digest=request.request_digest,
                    program_cell_id=request.program_cell_id,
                    entity_ref="NVDA",
                    candidate_role=role,
                    adapter_id=self.adapter_id,
                    route_id=self.route_id,
                    title=str(
                        record.get("subsection")
                        or record.get("section")
                        or source_ref
                    ),
                    excerpt=excerpt,
                    published_at=filing.filed_at,
                    source_url=filing.source_url,
                    locator=f"{record.get('section') or row.get('section') or ''}#{source_ref}",
                    source_snapshot_ref=str(capture["object_key"]),
                    source_snapshot_digest=str(capture["digest"]),
                    parser_adapter="local_sec_chunk_projection_v1",
                    parser_digest=canonical_digest(
                        {
                            "parser": "local_sec_chunk_projection_v1",
                            "official_identity_parser": filing.parser_adapter,
                            "official_source_capture_digest": filing.source_capture_digest,
                        }
                    ),
                    source_authority_rank=100,
                    score=float(row.get("score") or 0.0),
                    exact_value_authority=False,
                )
            )
        return tuple(out)


class RelationshipGraphSearchAdapter:
    adapter_id = "relationship_graph_read_only"
    route_id = "local_relationship_graph_metadata_route"

    def __init__(self, *, database: Path, capture: LocalCaptureWriter) -> None:
        self._database = database
        self._capture = capture

    def search(self, request: ExecutableSearchRequest) -> tuple[SearchCandidate, ...]:
        query = """
            SELECT e.graph_edge_id, n.ticker, n.label, e.edge_type,
                   e.authority_mode, e.source_role, e.claim_boundary,
                   support.citation_url, support.citation_span, support.evidence_ref
            FROM research_graph_edges e
            JOIN research_graph_nodes n ON n.graph_node_id = e.from_node_id
            LEFT JOIN research_graph_evidence_support support
              ON support.support_id = (
                SELECT support_id FROM research_graph_evidence_support
                WHERE graph_edge_id = e.graph_edge_id
                ORDER BY CASE WHEN citation_url <> '' THEN 0 ELSE 1 END, support_id
                LIMIT 1
              )
            WHERE n.graph_node_id = 'company:NVDA'
              AND e.can_enter_evidence_bundle = 1
            ORDER BY CASE e.source_role
                WHEN 'supply_chain_official_relationship' THEN 1
                WHEN 'official_customer_order_or_deployment_event' THEN 2
                WHEN 'working_capital_liquidity' THEN 3
                ELSE 4
            END, e.graph_edge_id
            LIMIT 12
        """
        with _read_only_sqlite(self._database) as connection:
            rows = [dict(row) for row in connection.execute(query).fetchall()]
        capture = self._capture.capture(
            adapter_id=self.adapter_id,
            request=request,
            rows=rows,
        )
        out: list[SearchCandidate] = []
        allowed_roles = (
            {
                "supply_chain_official_relationship",
                "working_capital_liquidity",
            }
            if request.program_cell_id
            == "bottleneck_counterevidence_and_what_would_change"
            else {
                "official_customer_order_or_deployment_event",
                "supply_chain_official_relationship",
            }
        )
        for rank, row in enumerate(rows, start=1):
            if str(row.get("source_role") or "") not in allowed_roles:
                continue
            source_url = str(row.get("citation_url") or "")
            excerpt = _clip(str(row.get("citation_span") or row.get("claim_boundary") or ""))
            if not source_url.startswith("https://") or not excerpt:
                continue
            out.append(
                SearchCandidate.create(
                    request_digest=request.request_digest,
                    program_cell_id=request.program_cell_id,
                    entity_ref="NVDA",
                    candidate_role="relationship_context",
                    adapter_id=self.adapter_id,
                    route_id=self.route_id,
                    title=f"NVDA {str(row.get('edge_type') or 'relationship').replace('_', ' ')}",
                    excerpt=excerpt,
                    # The graph support table has build time but no source publication
                    # date. Leave the authority field empty so Evidence Gate rejects
                    # the row instead of laundering build time into evidence time.
                    published_at="",
                    source_url=source_url,
                    locator=str(row.get("evidence_ref") or row.get("graph_edge_id") or ""),
                    source_snapshot_ref=str(capture["object_key"]),
                    source_snapshot_digest=str(capture["digest"]),
                    parser_adapter="research_graph_projection_v1",
                    parser_digest=canonical_digest({"parser": "research_graph_projection_v1"}),
                    source_authority_rank=60,
                    score=float(20 - rank),
                    exact_value_authority=False,
                )
            )
        return tuple(out)


class ExactValueSqlSearchAdapter:
    adapter_id = "exact_value_sql_read_only"
    route_id = "local_exact_value_sql_metadata_route"

    def __init__(self, *, database: Path, capture: LocalCaptureWriter) -> None:
        self._database = database
        self._capture = capture

    def search(self, request: ExecutableSearchRequest) -> tuple[SearchCandidate, ...]:
        query = """
            WITH ranked AS (
                SELECT gold_row_id, ticker, metric_family, metric_name, value,
                       unit, period, as_of_date, fiscal_year, authority_mode,
                       claim_boundary, citation_url, citation_span, evidence_ref,
                       source_url,
                       ROW_NUMBER() OVER (
                         PARTITION BY metric_family
                         ORDER BY as_of_date DESC, fiscal_year DESC, period DESC, gold_row_id
                       ) AS metric_rank
                FROM gold_fact_signal_mart
                WHERE ticker = ?
                  AND metric_family IN ('revenue', 'gross_profit', 'operating_income')
                  AND can_enter_evidence_bundle = 1
                  AND exact_value_authority = 1
                  AND date(substr(as_of_date, 1, 10)) <= date(?)
            )
            SELECT * FROM ranked WHERE metric_rank = 1
            ORDER BY CASE metric_family
                WHEN 'revenue' THEN 1
                WHEN 'gross_profit' THEN 2
                ELSE 3
            END
        """
        with _read_only_sqlite(self._database) as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    query, (request.case_key, request.as_of[:10])
                ).fetchall()
            ]
        capture = self._capture.capture(
            adapter_id=self.adapter_id,
            request=request,
            rows=rows,
        )
        out: list[SearchCandidate] = []
        for rank, row in enumerate(rows, start=1):
            source_url = str(row.get("citation_url") or row.get("source_url") or "")
            if not source_url.startswith("https://"):
                continue
            excerpt = _clip(
                f"{row.get('metric_name') or row.get('metric_family')}: "
                f"{row.get('value')} {row.get('unit')}; {row.get('citation_span') or ''}"
            )
            out.append(
                SearchCandidate.create(
                    request_digest=request.request_digest,
                    program_cell_id=request.program_cell_id,
                    entity_ref="NVDA",
                    candidate_role="exact_numeric_context",
                    adapter_id=self.adapter_id,
                    route_id=self.route_id,
                    title=str(row.get("metric_name") or row.get("metric_family") or "Reported metric"),
                    excerpt=excerpt,
                    published_at=str(row.get("as_of_date") or row.get("period") or request.as_of[:10]),
                    source_url=source_url,
                    locator=str(row.get("evidence_ref") or row.get("gold_row_id") or ""),
                    source_snapshot_ref=str(capture["object_key"]),
                    source_snapshot_digest=str(capture["digest"]),
                    parser_adapter="gold_fact_projection_v1",
                    parser_digest=canonical_digest({"parser": "gold_fact_projection_v1"}),
                    source_authority_rank=110,
                    score=float(20 - rank),
                    exact_value_authority=True,
                )
            )
        return tuple(out)


class _ReadOnlySqlite:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._connection = sqlite3.connect(
            f"file:{self._path.as_posix()}?mode=ro", uri=True
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA query_only = ON")
        return self._connection

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._connection is not None:
            self._connection.close()


def _read_only_sqlite(path: Path) -> _ReadOnlySqlite:
    return _ReadOnlySqlite(path)


def qualify_candidates(
    request: ExecutableSearchRequest,
    candidates: Sequence[SearchCandidate],
) -> tuple[tuple[SearchCandidate, ...], tuple[dict[str, Any], ...]]:
    accepted: list[SearchCandidate] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    cutoff = _date_only(request.as_of)
    def _published_sort_value(candidate: SearchCandidate) -> int:
        try:
            return _date_only(candidate.published_at).toordinal()
        except Fin012S4T03SearchError:
            return -1

    ordered = sorted(
        candidates,
        key=lambda row: (
            -row.source_authority_rank,
            -_published_sort_value(row),
            row.candidate_id,
        ),
    )
    for candidate in ordered:
        reasons: list[str] = []
        if candidate.candidate_id in seen:
            reasons.append("duplicate_candidate_id")
        seen.add(candidate.candidate_id)
        if candidate.request_digest != request.request_digest:
            reasons.append("request_digest_mismatch")
        if candidate.entity_ref != request.target_entity_ref:
            reasons.append("cross_case_entity")
        if candidate.program_cell_id != request.program_cell_id:
            reasons.append("program_cell_mismatch")
        if candidate.candidate_role not in request.accepted_candidate_roles:
            reasons.append("candidate_role_not_accepted")
        if not candidate.source_url.startswith("https://"):
            reasons.append("https_citation_required")
        if not candidate.locator:
            reasons.append("citation_locator_required")
        if not candidate.source_snapshot_ref or not re.fullmatch(
            r"[0-9a-f]{64}", candidate.source_snapshot_digest
        ):
            reasons.append("source_snapshot_lineage_invalid")
        if not candidate.parser_adapter or not re.fullmatch(
            r"[0-9a-f]{64}", candidate.parser_digest
        ):
            reasons.append("parser_lineage_invalid")
        try:
            if _date_only(candidate.published_at) > cutoff:
                reasons.append("candidate_after_as_of")
        except Fin012S4T03SearchError:
            reasons.append("candidate_date_invalid")
        if candidate.writer_citable or candidate.domain_judgment_eligible:
            reasons.append("t03_nonpromotion_boundary_violated")
        if reasons:
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "decision": "rejected",
                    "reason_codes": reasons,
                }
            )
            continue
        if len(accepted) < request.candidate_ceiling:
            accepted.append(candidate)
        else:
            rejected.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "decision": "rejected",
                    "reason_codes": ["request_candidate_ceiling_reached"],
                }
            )
    return tuple(accepted), tuple(rejected)


@dataclass
class _BudgetState:
    source_calls: int = 0
    local_invocations: int = 0
    fallbacks: int = 0


class Fin012S4T03SearchRunner:
    def __init__(
        self,
        *,
        repository_root: str | Path,
        runtime_root: str | Path,
        transport: SourceTransport,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.runtime_root = Path(runtime_root).resolve()
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.store = FileCanonicalObjectStore(self.runtime_root / "objects")
        self.source_client = CaptureFirstSourceClient(
            store=self.store,
            transport=transport,
        )
        self.local_capture = LocalCaptureWriter(self.store)

    def execute(
        self,
        *,
        admission: SearchAdmission,
        now: str | None = None,
        run_nonce: str,
    ) -> dict[str, Any]:
        started = time.monotonic()
        observed_at = now or _utc_now()
        readiness = load_current_fin_0_1_2_s4_t02_readiness("NVDA")
        requests = tuple(
            compile_executable_search_request(row)
            for row in readiness.evidence_requests
        )
        for request in requests:
            request.require_valid()
        admission.require_active(now=observed_at, requests=requests)
        run_base = {
            "schema_version": RUN_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "case_key": "NVDA",
            "request_digests": [row.request_digest for row in requests],
            "run_nonce": run_nonce,
            "started_at": observed_at,
        }
        run_digest = canonical_digest(run_base)
        run_id = f"s4_t03_search_run_{run_digest[:20]}"
        attempt_id = f"s4_t03_search_attempt_{canonical_digest({'run': run_id, 'nonce': run_nonce})[:20]}"
        budget = _BudgetState()
        status = "failed"
        phase = "initialize"
        code = "unclassified_failure"
        request_results: list[dict[str, Any]] = []
        try:
            self._require_sources()
            phase = "official_source_identity"
            filings = self._load_official_filing_identities(
                as_of=requests[0].as_of,
                admission=admission,
                budget=budget,
            )
            official_by_accession = {row.accession: row for row in filings}
            phase = "local_retrieval"
            object_adapter = BM25SearchAdapter(
                index_dir=self.repository_root / TEXT_INDEX_RELATIVE_PATH,
                capture=self.local_capture,
            )
            graph_adapter = RelationshipGraphSearchAdapter(
                database=self.repository_root / RESEARCH_GRAPH_RELATIVE_PATH,
                capture=self.local_capture,
            )
            exact_adapter = ExactValueSqlSearchAdapter(
                database=self.repository_root / GOLD_MART_RELATIVE_PATH,
                capture=self.local_capture,
            )
            for request in requests:
                raw_candidates: list[SearchCandidate] = []
                if request.program_cell_id == "value_and_profit_capture":
                    self._consume_local_budget(admission, budget)
                    raw_candidates.extend(exact_adapter.search(request))
                    self._consume_local_budget(admission, budget)
                    raw_candidates.extend(
                        object_adapter.search(
                            request, official_filings=official_by_accession
                        )
                    )
                else:
                    self._consume_local_budget(admission, budget)
                    raw_candidates.extend(
                        object_adapter.search(
                            request, official_filings=official_by_accession
                        )
                    )
                    self._consume_local_budget(admission, budget)
                    raw_candidates.extend(graph_adapter.search(request))
                phase = "evidence_gate"
                accepted, rejected = qualify_candidates(request, raw_candidates)
                request_results.append(
                    {
                        "request": request.as_dict(),
                        "status": "current_evidence_candidates_ready" if accepted else "typed_gap",
                        "typed_gap_codes": [] if accepted else [request.empty_candidate_gap_code],
                        "accepted_candidates": [row.as_dict() for row in accepted],
                        "rejected_candidates": list(rejected),
                        "accepted_count": len(accepted),
                        "rejected_count": len(rejected),
                        "writer_citable": False,
                        "domain_judgment_eligible": False,
                        "business_artifact_created": False,
                    }
                )
            phase = "terminalize"
            if not all(row["accepted_count"] > 0 for row in request_results):
                status = "bounded_gap"
                code = "one_or_more_current_evidence_requests_empty"
            else:
                status = "success"
                code = "three_request_current_evidence_candidate_pack_ready"
        except Fin012S4T03SearchError as exc:
            code = exc.code
        except Exception as exc:  # typed envelope preserves unexpected project defects
            code = f"unexpected_project_failure:{type(exc).__name__}"
        elapsed = time.monotonic() - started
        if elapsed > admission.wall_clock_seconds and status == "success":
            status = "failed"
            phase = "budget"
            code = "wall_clock_budget_exceeded"
        terminal = {
            "schema_version": TERMINAL_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "run_id": run_id,
            "run_digest": run_digest,
            "attempt_id": attempt_id,
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "case_key": "NVDA",
            "status": status,
            "phase": phase,
            "code": code,
            "request_results": request_results,
            "capture_objects": [
                *self.source_client.capture_objects,
                *self.local_capture.capture_objects,
            ],
            "observed_counts": {
                "source_calls": budget.source_calls,
                "live_source_network_calls": self.source_client.live_network_calls,
                "local_retrieval_or_tool_invocations": budget.local_invocations,
                "fallbacks": budget.fallbacks,
                "same_target_retries": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "paid_api_cost_usd": 0.0,
                "accepted_candidates": sum(row["accepted_count"] for row in request_results),
                "rejected_candidates": sum(row["rejected_count"] for row in request_results),
                "business_artifacts": 0,
            },
            "elapsed_seconds": round(elapsed, 6),
            "completed_at": _utc_now(),
            "T04_consumption_authorized": status == "success",
            "writer_citable_in_T03": False,
            "domain_judgment_eligible_in_T03": False,
        }
        terminal_object = self.store.put_json(
            terminal,
            namespace=TERMINAL_NAMESPACE,
            artifact_type="typed_terminal_result",
        )
        readback = self.store.get_json(
            terminal_object["object_key"], expected_digest=terminal_object["digest"]
        )
        if canonical_digest(readback) != terminal_object["digest"]:
            raise Fin012S4T03SearchError("t03_terminal_result_readback_mismatch")
        return {**terminal, "terminal_object": terminal_object}

    def _load_official_filing_identities(
        self,
        *,
        as_of: str,
        admission: SearchAdmission,
        budget: _BudgetState,
    ) -> tuple[OfficialFilingIdentity, ...]:
        self._consume_source_budget(admission, budget)
        try:
            response = self.source_client.fetch(
                url=NVDA_SEC_SUBMISSIONS_URL,
                allowed_hosts=ALLOWED_SOURCE_HOSTS,
            )
            capture = self.source_client.capture_objects[-1]
            filings = parse_sec_submissions(
                response,
                as_of=as_of,
                response_capture=capture,
            )
            if filings:
                return filings
        except Fin012S4T03SearchError:
            filings = ()
        if budget.fallbacks >= admission.fallback_ceiling:
            raise Fin012S4T03SearchError("t03_official_source_identity_unavailable")
        budget.fallbacks += 1
        self._consume_source_budget(admission, budget)
        response = self.source_client.fetch(
            url=NVDA_IR_URL,
            allowed_hosts=ALLOWED_SOURCE_HOSTS,
        )
        capture = self.source_client.capture_objects[-1]
        filings = parse_nvda_ir_links(
            response,
            as_of=as_of,
            response_capture=capture,
        )
        if not filings:
            raise Fin012S4T03SearchError("t03_official_source_identity_unavailable")
        return filings

    @staticmethod
    def _consume_source_budget(admission: SearchAdmission, budget: _BudgetState) -> None:
        if budget.source_calls >= admission.source_network_call_ceiling:
            raise Fin012S4T03SearchError("t03_source_network_budget_exceeded")
        budget.source_calls += 1

    @staticmethod
    def _consume_local_budget(admission: SearchAdmission, budget: _BudgetState) -> None:
        if budget.local_invocations >= admission.local_invocation_ceiling:
            raise Fin012S4T03SearchError("t03_local_invocation_budget_exceeded")
        budget.local_invocations += 1

    def _require_sources(self) -> None:
        required = (
            self.repository_root / TEXT_INDEX_RELATIVE_PATH / "metadata.json",
            self.repository_root / TEXT_INDEX_RELATIVE_PATH / "bm25.pkl",
            self.repository_root / GOLD_MART_RELATIVE_PATH,
            self.repository_root / RESEARCH_GRAPH_RELATIVE_PATH,
        )
        if any(not path.is_file() for path in required):
            raise Fin012S4T03SearchError("t03_required_local_source_missing")


def compile_current_nvda_executable_requests() -> tuple[ExecutableSearchRequest, ...]:
    readiness = load_current_fin_0_1_2_s4_t02_readiness("NVDA")
    return tuple(
        compile_executable_search_request(row)
        for row in readiness.evidence_requests
    )


__all__ = [
    "ALLOWED_SOURCE_HOSTS",
    "CONTRACT_REF",
    "CaptureFirstSourceClient",
    "ExecutableSearchRequest",
    "Fin012S4T03SearchError",
    "Fin012S4T03SearchRunner",
    "OfficialFilingIdentity",
    "ROUTE_REGISTRY",
    "SearchAdmission",
    "SearchCandidate",
    "SourceResponse",
    "SourceTransport",
    "UrllibSourceTransport",
    "compile_current_nvda_executable_requests",
    "compile_executable_search_request",
    "parse_nvda_ir_links",
    "parse_sec_submissions",
    "qualify_candidates",
]
