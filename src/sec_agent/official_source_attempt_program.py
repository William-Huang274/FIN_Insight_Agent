from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import ipaddress
import socket
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_official_source_attempt_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_official_source_attempt_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.official_source_attempt_and_typed_gap:v1"
CAPTURE_SCHEMA = "fin_ia_0_1_3_official_source_capture_v1_0"
CAPTURE_NAMESPACE = "fin-0.1.3/s1-03/official-source-captures"
_SAFE_HEADERS = {"content-type", "content-length", "last-modified", "etag", "location"}
_CASES = {"DELL", "MU", "NVDA"}
_CONTACT_EMAIL_RE = re.compile(r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9._%+-])")


class OfficialSourceAttemptError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class OfficialSourceExecutionAuthority:
    admission_id: str
    admission_digest: str
    run_id: str
    attempt_id: str
    issued_at: str
    expires_at: str
    source_call_ceiling: int

    @classmethod
    def issue(
        cls,
        *,
        policy: Mapping[str, Any],
        run_nonce: str,
        issued_at: str,
        expires_at: str,
    ) -> "OfficialSourceExecutionAuthority":
        call_ceiling = sum(
            len(profile["source_routes"])
            for profile in policy["case_profiles"].values()
        )
        admission_body = {
            "contract_ref": CONTRACT_REF,
            "policy_digest": canonical_digest(policy),
            "run_nonce": run_nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "source_call_ceiling": call_ceiling,
            "retry_ceiling": 0,
            "model_calls": 0,
            "provider_calls": 0,
        }
        admission_digest = canonical_digest(admission_body)
        run_id = f"fin013_s1_03_run_{canonical_digest({'admission': admission_digest, 'nonce': run_nonce})[:20]}"
        attempt_id = f"fin013_s1_03_attempt_{canonical_digest({'run': run_id, 'nonce': run_nonce})[:20]}"
        return cls(
            admission_id=f"fin013_s1_03_admission_{admission_digest[:20]}",
            admission_digest=admission_digest,
            run_id=run_id,
            attempt_id=attempt_id,
            issued_at=issued_at,
            expires_at=expires_at,
            source_call_ceiling=call_ceiling,
        )

    def require_active(self, *, observed_at: str, policy: Mapping[str, Any]) -> None:
        expected = sum(
            len(profile["source_routes"])
            for profile in policy["case_profiles"].values()
        )
        if self.source_call_ceiling != expected:
            raise OfficialSourceAttemptError("official_source_authority_budget_invalid")
        observed = _parse_time(observed_at)
        if not _parse_time(self.issued_at) <= observed <= _parse_time(self.expires_at):
            raise OfficialSourceAttemptError("official_source_authority_not_active")

    def as_dict(self) -> dict[str, Any]:
        return {
            "admission_id": self.admission_id,
            "admission_digest": self.admission_digest,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "source_call_ceiling": self.source_call_ceiling,
        }


def _parse_time(value: str) -> datetime:
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
    redirect_chain: tuple[Mapping[str, Any], ...] = ()


class SourceTransport(Protocol):
    live_network: bool

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse: ...


class _RecordingRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts
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
        if len(self.chain) >= 3:
            raise OfficialSourceAttemptError("official_source_redirect_ceiling_exceeded")
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self.allowed_hosts:
            raise OfficialSourceAttemptError("official_source_redirect_not_allowlisted")
        self.chain.append(
            {
                "status_code": int(code),
                "from_url": req.full_url,
                "to_url": newurl,
                "location": str(headers.get("Location") or newurl),
            }
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibOfficialSourceTransport:
    live_network = True

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed_hosts:
            raise OfficialSourceAttemptError("official_source_url_not_allowlisted")
        hostname = (parsed.hostname or "").lower()
        if (hostname == "sec.gov" or hostname.endswith(".sec.gov")) and not _sec_contact_declared(headers):
            raise OfficialSourceAttemptError("official_source_sec_contact_required")
        _require_public_network_host(parsed.hostname or "")
        redirect_handler = _RecordingRedirectHandler(allowed_hosts)
        opener = build_opener(redirect_handler)
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = response.read(byte_ceiling + 1)
                if len(body) > byte_ceiling:
                    raise OfficialSourceAttemptError("official_source_body_ceiling_exceeded")
                return SourceResponse(
                    status_code=int(response.status),
                    final_url=response.geturl(),
                    headers={
                        key.lower(): value
                        for key, value in response.headers.items()
                        if key.lower() in _SAFE_HEADERS
                    },
                    body=body,
                    redirect_chain=tuple(redirect_handler.chain),
                )
        except HTTPError as exc:
            body = exc.read(byte_ceiling + 1)
            return SourceResponse(
                status_code=int(exc.code),
                final_url=exc.geturl(),
                headers={
                    key.lower(): value
                    for key, value in exc.headers.items()
                    if key.lower() in _SAFE_HEADERS
                },
                body=body[:byte_ceiling],
                redirect_chain=tuple(redirect_handler.chain),
            )
        except (URLError, TimeoutError) as exc:
            raise OfficialSourceAttemptError("official_source_transport_failed") from exc


def load_official_source_policy(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != POLICY_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or set(payload.get("case_profiles") or {}) != _CASES
    ):
        raise OfficialSourceAttemptError("official_source_policy_invalid")
    for case_key, profile in payload["case_profiles"].items():
        if not profile.get("source_routes") or not profile.get("required_slots"):
            raise OfficialSourceAttemptError("official_source_policy_case_invalid")
        for route in profile["source_routes"]:
            parsed = urlparse(str(route.get("url") or ""))
            allowed = set(profile.get("allowed_hosts") or ())
            if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed:
                raise OfficialSourceAttemptError("official_source_policy_route_not_allowlisted")
    return payload


class CaptureFirstOfficialSourceClient:
    def __init__(
        self,
        *,
        store: FileCanonicalObjectStore,
        transport: SourceTransport,
        namespace: str = CAPTURE_NAMESPACE,
    ) -> None:
        self.store = store
        self.transport = transport
        self.namespace = namespace
        self.capture_refs: list[dict[str, Any]] = []
        self.network_calls = 0

    def fetch(
        self,
        *,
        case_key: str,
        route_id: str,
        url: str,
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> tuple[SourceResponse | None, dict[str, Any]]:
        headers = {
            "Accept": "application/json,text/html,application/pdf;q=0.9,*/*;q=0.1",
            "User-Agent": _official_source_user_agent(),
        }
        request_capture = {
            "schema_version": CAPTURE_SCHEMA,
            "capture_kind": "source_request",
            "case_key": case_key,
            "route_id": route_id,
            "method": "GET",
            "url": url,
            "headers": headers,
            "operator_contact_configured": _sec_contact_declared(headers),
            "credential_cookie_authorization_present": False,
        }
        request_ref = self._persist(request_capture, "official_source_request")
        self.network_calls += int(bool(self.transport.live_network))
        try:
            response = self.transport.fetch(
                url=url,
                headers=headers,
                allowed_hosts=allowed_hosts,
                timeout_seconds=timeout_seconds,
                byte_ceiling=byte_ceiling,
            )
        except OfficialSourceAttemptError as exc:
            failure = {
                "schema_version": CAPTURE_SCHEMA,
                "capture_kind": "source_transport_failure",
                "case_key": case_key,
                "route_id": route_id,
                "request_capture_ref": request_ref["object_key"],
                "request_capture_digest": request_ref["digest"],
                "failure_code": exc.code,
                "capture_before_parse": True,
                "credential_cookie_authorization_present": False,
            }
            failure_ref = self._persist(failure, "official_source_transport_failure")
            return None, {
                "route_id": route_id,
                "status": "transport_failure",
                "failure_code": exc.code,
                "request_capture": request_ref,
                "response_capture": failure_ref,
            }
        response_capture = {
            "schema_version": CAPTURE_SCHEMA,
            "capture_kind": "source_response",
            "case_key": case_key,
            "route_id": route_id,
            "request_capture_ref": request_ref["object_key"],
            "request_capture_digest": request_ref["digest"],
            "status_code": response.status_code,
            "final_url": response.final_url,
            "headers": {key: str(value) for key, value in response.headers.items() if key in _SAFE_HEADERS},
            "redirect_chain": list(response.redirect_chain),
            "body_base64": base64.b64encode(response.body).decode("ascii"),
            "body_sha256": hashlib.sha256(response.body).hexdigest(),
            "body_bytes": len(response.body),
            "capture_before_parse": True,
            "credential_cookie_authorization_present": False,
        }
        response_ref = self._persist(response_capture, "official_source_response")
        final = urlparse(response.final_url)
        if final.scheme != "https" or (final.hostname or "").lower() not in allowed_hosts:
            status = "rejected_final_url"
            failure_code = "official_source_final_url_not_allowlisted"
        elif not 200 <= response.status_code < 300:
            status = "http_failure"
            failure_code = f"official_source_http_{response.status_code}"
        else:
            status = "captured"
            failure_code = None
        return response, {
            "route_id": route_id,
            "status": status,
            "failure_code": failure_code,
            "request_capture": request_ref,
            "response_capture": response_ref,
        }

    def _persist(self, payload: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
        ref = self.store.put_json(payload, namespace=self.namespace, artifact_type=artifact_type)
        observed = self.store.get_json(ref["object_key"], expected_digest=ref["digest"])
        if canonical_digest(observed) != ref["digest"]:
            raise OfficialSourceAttemptError("official_source_capture_readback_failed")
        self.capture_refs.append(ref)
        return ref


def _official_source_user_agent() -> str:
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if contact and _CONTACT_EMAIL_RE.fullmatch(contact):
        return f"FIN-Insight-Agent/0.1.3 contact={contact}"
    return "FIN-Insight-Agent/0.1.3 research contact=local-operator"


def _sec_contact_declared(headers: Mapping[str, str]) -> bool:
    user_agent = next(
        (str(value) for key, value in headers.items() if str(key).lower() == "user-agent"),
        "",
    )
    return _CONTACT_EMAIL_RE.search(user_agent) is not None


def _require_public_network_host(hostname: str) -> None:
    """Reject literal or resolved private/local destinations before outbound fetch."""
    lowered = hostname.strip().lower().rstrip(".")
    if not lowered or lowered == "localhost" or lowered.endswith(".localhost"):
        raise OfficialSourceAttemptError("official_source_private_network_forbidden")
    try:
        candidates = {ipaddress.ip_address(lowered)}
    except ValueError:
        try:
            candidates = {
                ipaddress.ip_address(row[4][0])
                for row in socket.getaddrinfo(lowered, 443, type=socket.SOCK_STREAM)
            }
        except OSError as exc:
            raise OfficialSourceAttemptError("official_source_dns_resolution_failed") from exc
    synthetic_network = ipaddress.ip_network("198.18.0.0/15")
    allow_synthetic = str(os.environ.get("FINSIGHT_ALLOW_SYNTHETIC_DNS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    forbidden = [
        address
        for address in candidates
        if address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ]
    if forbidden and not (
        allow_synthetic
        and all(address.version == 4 and address in synthetic_network for address in forbidden)
    ):
        raise OfficialSourceAttemptError("official_source_private_network_forbidden")


def parse_source_document(response: SourceResponse) -> dict[str, Any]:
    content_type = str(response.headers.get("content-type") or "").lower()
    parser_attempts: list[dict[str, str]] = []
    candidates: list[str]
    if response.body.startswith(b"%PDF") or "application/pdf" in content_type:
        candidates = ["pdf", "html", "json"]
    elif "json" in content_type or response.body.lstrip().startswith((b"{", b"[")):
        candidates = ["json", "html", "pdf"]
    else:
        candidates = ["html", "json", "pdf"]
    for adapter in candidates:
        try:
            if adapter == "json":
                value = json.loads(response.body.decode("utf-8"))
                text = json.dumps(value, ensure_ascii=False, sort_keys=True)
            elif adapter == "html":
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.body, "html.parser")
                text = soup.get_text(" ", strip=True)
            else:
                from pypdf import PdfReader

                reader = PdfReader(BytesIO(response.body))
                text = " ".join((page.extract_text() or "") for page in reader.pages)
            text = re.sub(r"\s+", " ", text).strip()
            if not text or sum(character.isalpha() for character in text) < 3:
                raise ValueError("empty_text")
            parser_attempts.append({"adapter": adapter, "status": "success"})
            return {
                "status": "parsed",
                "adapter": f"official_source_{adapter}_text_v1",
                "parser_attempts": parser_attempts,
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        except Exception as exc:  # parser fallback must preserve each bounded failure
            parser_attempts.append(
                {"adapter": adapter, "status": "failed", "reason": type(exc).__name__}
            )
    return {
        "status": "parser_failure",
        "adapter": None,
        "parser_attempts": parser_attempts,
        "text": "",
        "text_sha256": None,
    }


def compile_official_source_attempt_program(
    *,
    policy: Mapping[str, Any],
    runtime_root: str | Path,
    transport: SourceTransport,
    authority: OfficialSourceExecutionAuthority | None = None,
    shared_admission_ledger: SharedAdmissionConsumptionLedger | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    runtime_path = Path(runtime_root).resolve()
    execution: dict[str, Any] | None = None
    if transport.live_network:
        if authority is None or shared_admission_ledger is None or not observed_at:
            raise OfficialSourceAttemptError("official_source_live_authority_required")
        authority.require_active(observed_at=observed_at, policy=policy)
        shared_admission_ledger.reserve(
            admission_digest=authority.admission_digest,
            admission_id=authority.admission_id,
            scope=CONTRACT_REF,
            run_id=authority.run_id,
            attempt_id=authority.attempt_id,
            runtime_identity=str(runtime_path),
            reserved_at=observed_at,
        )
        execution = authority.as_dict()
    store = FileCanonicalObjectStore(runtime_path / "objects")
    client = CaptureFirstOfficialSourceClient(store=store, transport=transport)
    case_results: list[dict[str, Any]] = []
    for case_key in sorted(policy["case_profiles"]):
        profile = policy["case_profiles"][case_key]
        route_results: list[dict[str, Any]] = []
        parsed_documents: list[dict[str, Any]] = []
        for route in profile["source_routes"]:
            response, attempt = client.fetch(
                case_key=case_key,
                route_id=str(route["route_id"]),
                url=str(route["url"]),
                allowed_hosts=set(profile["allowed_hosts"]),
                timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
                byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
            )
            if response is not None and attempt["status"] == "captured":
                parsed = parse_source_document(response)
                attempt["parser"] = {key: value for key, value in parsed.items() if key != "text"}
                if parsed["status"] == "parsed":
                    parsed_documents.append(
                        {
                            "route_id": route["route_id"],
                            "url": response.final_url,
                            "response_capture": attempt["response_capture"],
                            **parsed,
                        }
                    )
                else:
                    attempt["status"] = "parser_failure"
                    attempt["failure_code"] = "official_source_all_parsers_failed"
            route_results.append(attempt)
        slot_results = [
            _evaluate_slot(
                case_key=case_key,
                slot=slot,
                parsed_documents=parsed_documents,
                route_results=route_results,
                as_of_date=str(profile["as_of_date"]),
            )
            for slot in profile["required_slots"]
        ]
        case_results.append(
            {
                "case_key": case_key,
                "issuer_id": profile["issuer_id"],
                "as_of_date": profile["as_of_date"],
                "route_results": route_results,
                "slot_results": slot_results,
                "summary": {
                    "required_slots": len(slot_results),
                    "accepted_evidence": sum(row["status"] == "accepted_evidence" for row in slot_results),
                    "attempt_backed_typed_gaps": sum(row["status"] == "attempt_backed_typed_gap" for row in slot_results),
                    "source_exhaustion_proven": sum(bool(row.get("source_exhaustion_proven")) for row in slot_results),
                },
            }
        )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "execution": execution,
        "case_results": case_results,
        "capture_refs": client.capture_refs,
        "observed_counts": {
            "cases": len(case_results),
            "required_source_slots": sum(row["summary"]["required_slots"] for row in case_results),
            "accepted_evidence": sum(row["summary"]["accepted_evidence"] for row in case_results),
            "attempt_backed_typed_gaps": sum(row["summary"]["attempt_backed_typed_gaps"] for row in case_results),
            "network_calls": client.network_calls,
            "model_calls": 0,
            "provider_calls": 0,
            "business_runs": 0,
        },
        "stage_boundary": {
            "S1_03_official_source_attempt_contract_ready": True,
            "S1_04_graph_ready": False,
            "S1_05_retrieval_usefulness_ready": False,
            "S2_S3_research_content_ready": False,
            "model_or_full_chain_run": False,
        },
    }
    result = {**body, "program_digest": canonical_digest(body)}
    validate_official_source_attempt_program(result, policy=policy)
    if transport.live_network and authority is not None and shared_admission_ledger is not None:
        if client.network_calls != authority.source_call_ceiling:
            raise OfficialSourceAttemptError("official_source_authority_call_count_invalid")
        shared_admission_ledger.finalize(
            admission_digest=authority.admission_digest,
            run_id=authority.run_id,
            attempt_id=authority.attempt_id,
            terminal_status="success",
            terminal_phase="official_source_attempt_terminal",
            terminal_code="all_required_slots_terminal_evidence_or_attempt_backed_gap",
            terminal_result_digest=result["program_digest"],
            finalized_at=observed_at or authority.expires_at,
        )
    return result


def _evaluate_slot(
    *,
    case_key: str,
    slot: Mapping[str, Any],
    parsed_documents: Sequence[Mapping[str, Any]],
    route_results: Sequence[Mapping[str, Any]],
    as_of_date: str,
) -> dict[str, Any]:
    slot_id = str(slot["slot_id"])
    terminal_routes = all(
        row["status"] in {"captured", "http_failure", "transport_failure", "parser_failure", "rejected_final_url"}
        for row in route_results
    )
    if slot.get("promotion_mode") == "numeric_regex":
        extracted = _extract_numeric_slot(
            case_key=case_key,
            slot=slot,
            parsed_documents=parsed_documents,
            as_of_date=as_of_date,
        )
        if extracted is not None:
            return extracted
    elif slot.get("promotion_mode") != "attempt_only":
        for document in parsed_documents:
            lowered = str(document["text"]).lower()
            groups = slot.get("match_groups") or [
                [phrase] for phrase in (slot.get("match_any") or ())
            ]
            for group in groups:
                phrases = [str(phrase) for phrase in group]
                window = _smallest_phrase_window(
                    lowered,
                    phrases,
                    ceiling=int(slot.get("max_match_span_chars", 1200)),
                )
                if window is not None:
                    window_start, window_end = window
                    match = window_start
                    matched_label = " + ".join(phrases)
                    start = max(0, match - 180)
                    end = min(len(document["text"]), window_end + 320)
                    statement = str(document["text"])[start:end].strip()
                    body = {
                        "case_key": case_key,
                        "slot_id": slot_id,
                        "status": "accepted_evidence",
                        "evidence_role": slot["evidence_role"],
                        "matched_phrase": matched_label,
                        "statement": statement,
                        "source_url": document["url"],
                        "source_capture_ref": document["response_capture"]["object_key"],
                        "source_capture_digest": document["response_capture"]["digest"],
                        "parser_adapter": document["adapter"],
                        "parser_text_digest": document["text_sha256"],
                        "as_of_date": as_of_date,
                        "writer_citable": False,
                        "domain_judgment_eligible": False,
                        "claim_boundary": slot["claim_boundary"],
                        "source_exhaustion_proven": False,
                    }
                    return {**body, "result_digest": canonical_digest(body)}
    successful_parsed_routes = {
        str(row["route_id"]) for row in parsed_documents
    }
    source_exhaustion = terminal_routes and len(successful_parsed_routes) == len(route_results)
    body = {
        "case_key": case_key,
        "slot_id": slot_id,
        "status": "attempt_backed_typed_gap",
        "evidence_role": slot["evidence_role"],
        "gap_code": slot["gap_code"],
        "cannot_infer": slot["cannot_infer"],
        "attempt_refs": [
            {
                "route_id": row["route_id"],
                "status": row["status"],
                "request_capture_ref": row["request_capture"]["object_key"],
                "request_capture_digest": row["request_capture"]["digest"],
                "response_capture_ref": row["response_capture"]["object_key"],
                "response_capture_digest": row["response_capture"]["digest"],
                "failure_code": row.get("failure_code"),
            }
            for row in route_results
        ],
        "exhaustion_scope": "bounded_case_profile_official_routes_only",
        "source_exhaustion_proven": source_exhaustion,
        "source_unavailable_or_parser_failed": any(row["status"] != "captured" for row in route_results),
        "as_of_date": as_of_date,
        "writer_citable": False,
        "domain_judgment_eligible": False,
    }
    return {**body, "result_digest": canonical_digest(body)}


def _extract_numeric_slot(
    *,
    case_key: str,
    slot: Mapping[str, Any],
    parsed_documents: Sequence[Mapping[str, Any]],
    as_of_date: str,
) -> dict[str, Any] | None:
    extractor = slot.get("numeric_extractor") or {}
    pattern = str(extractor.get("pattern") or "")
    value_group = str(extractor.get("value_group") or "value")
    if not pattern:
        raise OfficialSourceAttemptError("official_source_numeric_extractor_invalid")
    for document in parsed_documents:
        match = re.search(pattern, str(document["text"]), flags=re.IGNORECASE)
        if match is None:
            continue
        raw_value = match.group(value_group)
        digits = re.sub(r"[^0-9.-]", "", raw_value)
        try:
            normalized_value = str(int(round(float(digits) * int(extractor["scale_multiplier"]))))
        except (KeyError, TypeError, ValueError) as exc:
            raise OfficialSourceAttemptError("official_source_numeric_value_invalid") from exc
        statement = str(document["text"])[max(0, match.start() - 100): min(len(document["text"]), match.end() + 160)].strip()
        body = {
            "case_key": case_key,
            "slot_id": str(slot["slot_id"]),
            "status": "accepted_evidence",
            "evidence_role": slot["evidence_role"],
            "matched_phrase": "deterministic_numeric_regex",
            "statement": statement,
            "source_url": document["url"],
            "source_capture_ref": document["response_capture"]["object_key"],
            "source_capture_digest": document["response_capture"]["digest"],
            "parser_adapter": document["adapter"],
            "parser_text_digest": document["text_sha256"],
            "as_of_date": as_of_date,
            "writer_citable": False,
            "domain_judgment_eligible": False,
            "claim_boundary": slot["claim_boundary"],
            "source_exhaustion_proven": False,
            "numeric_fact": {
                "raw_value": raw_value,
                "normalized_value": normalized_value,
                "unit": extractor["unit"],
                "scale_multiplier": str(extractor["scale_multiplier"]),
                "fiscal_year": int(extractor["fiscal_year"]),
                "fiscal_period": "FY",
                "period_role": "annual",
                "period_start": extractor["period_start"],
                "period_end": extractor["period_end"],
                "duration_days": 364,
                "source_filed_at": extractor["source_filed_at"],
                "published_at": extractor["source_filed_at"],
                "aggregation_scope": extractor["aggregation_scope"],
                "metric_family": extractor["metric_family"],
                "formula": None,
            },
        }
        return {**body, "result_digest": canonical_digest(body)}
    return None


def compose_material_numeric_source_successor(
    *,
    material_program_set: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
) -> dict[str, Any]:
    gap_rows = {
        (str(program["case_key"]), str(gap["slot_id"])): gap
        for program in material_program_set.get("case_programs") or ()
        for gap in program.get("typed_gaps") or ()
    }
    resolved: list[dict[str, Any]] = []
    unmatched_numeric: list[dict[str, str]] = []
    for case in official_source_program.get("case_results") or ():
        case_key = str(case["case_key"])
        for slot in case.get("slot_results") or ():
            numeric = slot.get("numeric_fact")
            if not isinstance(numeric, Mapping):
                continue
            key = (case_key, str(slot["slot_id"]))
            gap = gap_rows.get(key)
            if gap is None:
                unmatched_numeric.append({"case_key": case_key, "slot_id": key[1]})
                continue
            body = {
                "case_key": case_key,
                "slot_id": key[1],
                "resolved_typed_gap_ref": gap["typed_gap_ref"],
                "resolved_typed_gap_digest": gap["typed_gap_digest"],
                "numeric_fact": dict(numeric),
                "source_url": slot["source_url"],
                "source_capture_ref": slot["source_capture_ref"],
                "source_capture_digest": slot["source_capture_digest"],
                "parser_adapter": slot["parser_adapter"],
                "parser_text_digest": slot["parser_text_digest"],
                "claim_boundary": slot["claim_boundary"],
                "as_of_date": slot["as_of_date"],
                "free_numeric_narrative_authorized": False,
            }
            resolved.append({**body, "resolution_digest": canonical_digest(body)})
    resolved_keys = {(row["case_key"], row["slot_id"]) for row in resolved}
    remaining = [
        {
            "case_key": case_key,
            "slot_id": slot_id,
            "typed_gap_ref": gap["typed_gap_ref"],
            "typed_gap_digest": gap["typed_gap_digest"],
        }
        for (case_key, slot_id), gap in sorted(gap_rows.items())
        if (case_key, slot_id) not in resolved_keys
    ]
    body = {
        "schema_version": "fin_ia_0_1_3_material_numeric_official_source_successor_v1_0",
        "contract_ref": "fin_0_1_3.S1.material_numeric_official_source_successor:v1",
        "material_program_set_digest": material_program_set["program_set_digest"],
        "official_source_program_digest": official_source_program["program_digest"],
        "resolved_source_numeric_facts": sorted(resolved, key=lambda row: (row["case_key"], row["slot_id"])),
        "remaining_typed_gaps": remaining,
        "unmatched_official_numeric_slots": unmatched_numeric,
        "coverage": {
            "material_slots": sum(
                int(program["coverage"]["requested_material_slots"])
                for program in material_program_set.get("case_programs") or ()
            ),
            "material_typed_gaps_before_source": len(gap_rows),
            "resolved_by_official_source": len(resolved),
            "remaining_typed_gaps": len(remaining),
            "ungoverned_slots": 0,
        },
        "stage_boundary": {
            "graph_ready": False,
            "retrieval_usefulness_ready": False,
            "model_or_full_chain_run": False,
        },
    }
    return {**body, "successor_digest": canonical_digest(body)}


def _smallest_phrase_window(
    text: str, phrases: Sequence[str], *, ceiling: int
) -> tuple[int, int] | None:
    occurrences: list[list[int]] = []
    for phrase in phrases:
        positions = [match.start() for match in re.finditer(re.escape(phrase.lower()), text)]
        if not positions:
            return None
        occurrences.append(positions)
    best: tuple[int, int] | None = None
    for anchor in occurrences[0]:
        selected = [anchor]
        for positions in occurrences[1:]:
            selected.append(min(positions, key=lambda value: abs(value - anchor)))
        start = min(selected)
        end = max(
            position + len(phrases[index])
            for index, position in enumerate(selected)
        )
        if end - start <= ceiling and (best is None or end - start < best[1] - best[0]):
            best = (start, end)
    return best


def validate_official_source_attempt_program(
    result: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> dict[str, Any]:
    normalized = dict(result)
    digest = normalized.pop("program_digest", None)
    if (
        normalized.get("schema_version") != RESULT_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or normalized.get("policy_digest") != canonical_digest(policy)
        or digest != canonical_digest(normalized)
    ):
        raise OfficialSourceAttemptError("official_source_program_invalid")
    cases = normalized.get("case_results") or ()
    if {row.get("case_key") for row in cases} != _CASES:
        raise OfficialSourceAttemptError("official_source_program_case_set_invalid")
    for case in cases:
        expected = {
            str(row["slot_id"])
            for row in policy["case_profiles"][case["case_key"]]["required_slots"]
        }
        observed = {str(row.get("slot_id")) for row in case.get("slot_results") or ()}
        if expected != observed:
            raise OfficialSourceAttemptError("official_source_slot_coverage_invalid")
        for row in case["slot_results"]:
            row_body = dict(row)
            row_digest = row_body.pop("result_digest", None)
            if row_digest != canonical_digest(row_body):
                raise OfficialSourceAttemptError("official_source_slot_digest_invalid")
            if row["status"] not in {"accepted_evidence", "attempt_backed_typed_gap"}:
                raise OfficialSourceAttemptError("official_source_slot_terminal_state_invalid")
            if row["status"] == "accepted_evidence" and (
                row["writer_citable"] or row["domain_judgment_eligible"]
            ):
                raise OfficialSourceAttemptError("official_source_false_promotion")
            if row["status"] == "attempt_backed_typed_gap" and not row.get("attempt_refs"):
                raise OfficialSourceAttemptError("official_source_gap_without_attempt")
    counts = normalized["observed_counts"]
    if counts["required_source_slots"] != sum(len(row["slot_results"]) for row in cases):
        raise OfficialSourceAttemptError("official_source_summary_invalid")
    return dict(result)
