from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import (
    CaptureFirstOfficialSourceClient,
    SourceResponse,
    SourceTransport,
    parse_source_document,
)
from sec_agent.s1_08_official_content_tools import (
    OfficialLocatorCandidate,
    ParsedOfficialHtml,
    parse_official_html_capture,
)
from sec_agent.s1_residual_gap_external_supplement import (
    CASES,
    CONTRACT_REF,
    RUN_SCOPE,
    file_sha256,
    validate_residual_gap_external_priority_plan,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


AUTHORITY_SCHEMA = "fin_ia_0_1_3_s1_residual_gap_external_live_authority_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_residual_gap_external_live_result_v1_0"
PRIVATE_NAMESPACE = "fin-0.1.3/s1/residual-gap-external-live"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}", re.IGNORECASE)
_QUERY_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "official",
        "site",
        "quarter",
        "fiscal",
        "year",
        "earnings",
        "release",
        "prepared",
        "remarks",
        "report",
        "results",
        "2026",
        "2027",
    }
)
_NAVIGATION_NOISE = frozenset(
    {
        "privacy",
        "cookie",
        "careers",
        "contact",
        "governance",
        "committee",
        "accessibility",
        "sitemap",
        "subscribe",
    }
)


class ResidualGapExternalLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LocatorProviderResult:
    status: str
    locators: tuple[Mapping[str, Any], ...]
    capture_refs: tuple[Mapping[str, Any], ...] = ()
    failure_code: str = ""
    network_attempted: bool = False


class LocatorProvider(Protocol):
    live_network: bool

    @property
    def network_calls(self) -> int: ...

    def locate(self, *, intent: Mapping[str, Any]) -> LocatorProviderResult: ...


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResidualGapExternalLiveError(code)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_residual_gap_external_live_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    repo_root: str | Path,
    observed_at: str,
) -> None:
    root = Path(repo_root).resolve()
    body = deepcopy(dict(authority))
    supplied_digest = str(body.pop("authority_digest", ""))
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("contract_ref") == CONTRACT_REF
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("status") == "issued_unconsumed"
        and supplied_digest == canonical_digest(body),
        "residual_external_live_authority_identity_invalid",
    )
    _require(
        authority.get("priority_plan_digest") == plan.get("plan_digest")
        and authority.get("local_evidence_pack_result_digest")
        == plan.get("local_evidence_pack_result_digest")
        and authority.get("budget") == policy.get("budget") == plan.get("budget"),
        "residual_external_live_authority_plan_binding_invalid",
    )
    _require(
        _parse_time(str(authority.get("issued_at")))
        <= _parse_time(observed_at)
        <= _parse_time(str(authority.get("expires_at"))),
        "residual_external_live_authority_not_active",
    )
    _require(
        authority.get("maximum_executions") == 1
        and authority.get("automatic_retry") is False
        and authority.get("evidence_promotion_allowed") is False
        and authority.get("model_calls_allowed") == 0,
        "residual_external_live_authority_boundary_invalid",
    )
    bindings = authority.get("file_bindings") or {}
    _require(bindings, "residual_external_live_authority_bindings_missing")
    for ref, expected in bindings.items():
        path = (root / str(ref)).resolve()
        _require(
            path.is_file()
            and _HEX64.fullmatch(str(expected or "")) is not None
            and file_sha256(path) == expected,
            "residual_external_live_authority_file_binding_invalid",
        )


def execute_residual_gap_external_live(
    *,
    policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    authority: Mapping[str, Any],
    repo_root: str | Path,
    runtime_root: str | Path,
    observed_at: str,
    execution_commit: str,
    official_transport: SourceTransport,
    locator_provider: LocatorProvider,
    shared_admission_ledger: SharedAdmissionConsumptionLedger,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime_path = Path(runtime_root).resolve()
    _require(not runtime_path.exists(), "residual_external_live_runtime_already_exists")
    validate_residual_gap_external_priority_plan(plan, policy=policy)
    validate_residual_gap_external_live_authority(
        authority,
        policy=policy,
        plan=plan,
        repo_root=root,
        observed_at=observed_at,
    )
    shared_admission_ledger.reserve(
        admission_digest=str(authority["authority_digest"]),
        admission_id=str(authority["admission_id"]),
        scope=CONTRACT_REF,
        run_id=str(authority["run_id"]),
        attempt_id=str(authority["attempt_id"]),
        runtime_identity=str(runtime_path),
        reserved_at=observed_at,
    )
    runtime_path.mkdir(parents=True, exist_ok=False)
    store = FileCanonicalObjectStore(runtime_path / "objects")
    client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=official_transport,
        namespace=PRIVATE_NAMESPACE,
    )
    intents_by_case = {
        case_key: [
            row
            for row in plan["selected_intents"]
            if row["case_key"] == case_key
        ]
        for case_key in CASES
    }
    discovery: dict[str, dict[str, Any]] = {}
    for case_key in CASES:
        profile = policy["case_profiles"][case_key]
        root_url = str(profile["official_discovery_roots"][0])
        response, attempt = client.fetch(
            case_key=case_key,
            route_id=f"residual_discovery::{case_key}",
            url=root_url,
            allowed_hosts=set(profile["allowed_subject_hosts"]),
            timeout_seconds=30,
            byte_ceiling=16_777_216,
        )
        discovery[case_key] = _materialize_discovery(
            store=store,
            case_key=case_key,
            as_of=str(plan["as_of_date"]),
            response=response,
            attempt=attempt,
        )
    official_network_after_discovery = client.network_calls

    intent_results: list[dict[str, Any]] = []
    document_cache: dict[tuple[str, str], dict[str, Any]] = {}
    provider_call_ceiling = int(policy["budget"]["locator_provider_call_ceiling"])
    document_fetch_ceiling = int(policy["budget"]["official_document_fetch_ceiling"])
    document_fetches_started = 0
    for case_key in CASES:
        for intent in intents_by_case[case_key]:
            root_locators = tuple(discovery[case_key].get("locators") or ())
            ranked = _rank_locators(intent=intent, locators=root_locators)
            provider_result: LocatorProviderResult | None = None
            route = "official_discovery_root"
            if not ranked:
                route = "official_domain_locator_provider_fallback"
                if locator_provider.network_calls >= provider_call_ceiling:
                    provider_result = LocatorProviderResult(
                        status="typed_gap",
                        locators=(),
                        failure_code="locator_provider_call_ceiling_reached",
                    )
                else:
                    provider_result = locator_provider.locate(intent=intent)
                ranked = _rank_locators(
                    intent=intent,
                    locators=tuple(provider_result.locators),
                )
            selected = ranked[0] if ranked else None
            if selected is None:
                intent_results.append(
                    _typed_gap_result(
                        intent=intent,
                        route=route,
                        code=(
                            provider_result.failure_code
                            if provider_result is not None and provider_result.failure_code
                            else "no_qualified_official_locator"
                        ),
                        provider_result=provider_result,
                    )
                )
                continue
            locator_url = str(selected["url"])
            cache_key = (case_key, locator_url)
            if cache_key not in document_cache:
                if document_fetches_started >= document_fetch_ceiling:
                    document_cache[cache_key] = {
                        "status": "typed_gap",
                        "code": "official_document_fetch_ceiling_reached",
                    }
                else:
                    document_fetches_started += 1
                    response, attempt = client.fetch(
                        case_key=case_key,
                        route_id=(
                            "residual_document::"
                            f"{case_key}::{canonical_digest(locator_url)[:16]}"
                        ),
                        url=locator_url,
                        allowed_hosts=set(intent["allowed_document_hosts"]),
                        timeout_seconds=30,
                        byte_ceiling=16_777_216,
                    )
                    document_cache[cache_key] = _materialize_document(
                        store=store,
                        case_key=case_key,
                        as_of=str(plan["as_of_date"]),
                        response=response,
                        attempt=attempt,
                        locator=selected,
                    )
            document = deepcopy(document_cache[cache_key])
            content_hits = _content_hits(intent, document)
            terminal_status, code = _document_disposition(
                document=document,
                content_hits=content_hits,
            )
            intent_results.append(
                {
                    "intent_id": intent["intent_id"],
                    "intent_digest": intent["intent_digest"],
                    "case_key": case_key,
                    "intent_key": intent["intent_key"],
                    "decision_surface": intent["decision_surface"],
                    "selected_gap_ids": list(intent["selected_gap_ids"]),
                    "route": route,
                    "status": terminal_status,
                    "terminal_code": code,
                    "selected_locator": {
                        "url": locator_url,
                        "title": str(selected.get("title") or ""),
                        "source_domain": (urlsplit(locator_url).hostname or "").lower(),
                        "local_locator_score": int(selected["local_locator_score"]),
                        "provider_rank": selected.get("provider_rank"),
                        "provider_snippet_used_as_evidence": False,
                        "provider_date_used_as_authority": False,
                    },
                    "document": document,
                    "matched_business_terms": content_hits,
                    "provider_capture_refs": (
                        [dict(value) for value in provider_result.capture_refs]
                        if provider_result is not None
                        else []
                    ),
                    "evidence_promotion_allowed": False,
                    "writer_citable": False,
                }
            )

    counts = Counter(str(row["status"]) for row in intent_results)
    total_network = client.network_calls + locator_provider.network_calls
    _require(
        client.network_calls <= (
            int(policy["budget"]["official_discovery_fetch_ceiling"])
            + document_fetch_ceiling
        )
        and locator_provider.network_calls <= provider_call_ceiling
        and total_network <= int(policy["budget"]["total_network_call_ceiling"]),
        "residual_external_live_network_budget_exceeded",
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "terminal_completed_with_candidates_and_typed_gaps",
        "source_commit": str(execution_commit),
        "admission_id": str(authority["admission_id"]),
        "admission_digest": str(authority["authority_digest"]),
        "admission_consumed": True,
        "run_id": str(authority["run_id"]),
        "attempt_id": str(authority["attempt_id"]),
        "as_of_date": str(plan["as_of_date"]),
        "priority_plan_digest": str(plan["plan_digest"]),
        "discovery_results": [
            _public_discovery(discovery[case_key]) for case_key in CASES
        ],
        "intent_results": intent_results,
        "observed_counts": {
            "intents": len(intent_results),
            "candidate_ready_for_local_readjudication": counts[
                "candidate_ready_for_local_readjudication"
            ],
            "captured_candidate_with_typed_date_or_content_gap": counts[
                "captured_candidate_with_typed_date_or_content_gap"
            ],
            "typed_gap": counts["typed_gap"],
            "official_discovery_network_calls": official_network_after_discovery,
            "official_document_network_calls": (
                client.network_calls - official_network_after_discovery
            ),
            "locator_provider_network_calls": locator_provider.network_calls,
            "total_network_calls": total_network,
            "retry_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "rerank_calls": 0,
            "evidence_promotions": 0,
        },
        "capture_refs": [dict(ref) for ref in client.capture_refs],
        "stage_acceptance": {
            "all_twelve_intents_terminal": len(intent_results) == 12,
            "capture_first": True,
            "provider_locator_only": True,
            "external_live_complete": True,
            "external_evidence_readjudicated": False,
            "deepseek_research": False,
            "release": False,
        },
        "known_boundary": (
            "Captured official documents are candidate material for local readjudication. "
            "This terminal does not promote Evidence, close every residual gap, prove "
            "DeepSeek research quality, or accept a report."
        ),
    }
    public_body = strip_private_runtime_fields(body)
    return {**public_body, "result_digest": canonical_digest(public_body)}


def _materialize_discovery(
    *,
    store: FileCanonicalObjectStore,
    case_key: str,
    as_of: str,
    response: SourceResponse | None,
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    if response is None or attempt.get("status") != "captured":
        return {
            "case_key": case_key,
            "status": "typed_gap",
            "code": str(attempt.get("failure_code") or "official_discovery_failed"),
            "attempt": deepcopy(dict(attempt)),
            "locators": [],
        }
    response_capture = attempt["response_capture"]
    parsed = parse_source_document(response)
    parsed_html = _parse_html(
        response=response,
        as_of=as_of,
        response_capture=response_capture,
    )
    text = parsed_html.main_text if parsed_html is not None else str(parsed.get("text") or "")
    parser_ref = store.put_json(
        {
            "schema_version": "fin_ia_0_1_3_s1_residual_discovery_parser_v1_0",
            "case_key": case_key,
            "response_capture_ref": response_capture["object_key"],
            "response_capture_digest": response_capture["digest"],
            "parser": {key: value for key, value in parsed.items() if key != "text"},
            "parsed_text": text,
            "parsed_text_digest": canonical_digest(text),
        },
        namespace=PRIVATE_NAMESPACE,
        artifact_type="residual_external_discovery_parser",
    )
    locators = [
        _locator_row(value)
        for value in (parsed_html.document_locators if parsed_html is not None else ())
    ]
    return {
        "case_key": case_key,
        "status": "captured_and_parsed",
        "code": "official_discovery_materialized",
        "response_capture": deepcopy(dict(response_capture)),
        "parser_capture": parser_ref,
        "locator_count": len(locators),
        "locators": locators,
    }


def _materialize_document(
    *,
    store: FileCanonicalObjectStore,
    case_key: str,
    as_of: str,
    response: SourceResponse | None,
    attempt: Mapping[str, Any],
    locator: Mapping[str, Any],
) -> dict[str, Any]:
    if response is None or attempt.get("status") != "captured":
        return {
            "status": "typed_gap",
            "code": str(attempt.get("failure_code") or "official_document_fetch_failed"),
            "url": str(locator.get("url") or ""),
        }
    response_capture = attempt["response_capture"]
    parsed = parse_source_document(response)
    parsed_html = _parse_html(
        response=response,
        as_of=as_of,
        response_capture=response_capture,
    )
    text = parsed_html.main_text if parsed_html is not None else str(parsed.get("text") or "")
    publication = (
        parsed_html.publication_date.as_dict()
        if parsed_html is not None
        else {
            "date_value": "",
            "date_kind": "",
            "date_source": "",
            "date_confidence": "",
            "conflict_status": "publication_date_unproven",
            "candidates": [],
            "capture_ref": response_capture["object_key"],
            "capture_digest": response_capture["digest"],
        }
    )
    parser_ref = store.put_json(
        {
            "schema_version": "fin_ia_0_1_3_s1_residual_document_parser_v1_0",
            "case_key": case_key,
            "response_capture_ref": response_capture["object_key"],
            "response_capture_digest": response_capture["digest"],
            "parser": {key: value for key, value in parsed.items() if key != "text"},
            "publication_date": publication,
            "parsed_text": text,
            "parsed_text_digest": canonical_digest(text),
        },
        namespace=PRIVATE_NAMESPACE,
        artifact_type="residual_external_document_parser",
    )
    return {
        "status": "captured_and_parsed" if text else "typed_gap",
        "code": "official_document_materialized" if text else "official_document_parser_empty",
        "url": response.final_url,
        "title": (
            parsed_html.title if parsed_html is not None else str(locator.get("title") or "")
        ),
        "response_capture": deepcopy(dict(response_capture)),
        "parser_capture": parser_ref,
        "publication_date": publication,
        "text_digest": canonical_digest(text),
        "text_chars": len(text),
        "_private_text": text,
    }


def _parse_html(
    *,
    response: SourceResponse,
    as_of: str,
    response_capture: Mapping[str, Any],
) -> ParsedOfficialHtml | None:
    content_type = str(response.headers.get("content-type") or "").lower()
    if "html" not in content_type and not response.body.lstrip().lower().startswith(
        (b"<html", b"<!doctype", b"<?xml")
    ):
        return None
    return parse_official_html_capture(
        body=response.body,
        final_url=response.final_url,
        headers=response.headers,
        as_of=as_of,
        capture_ref=str(response_capture["object_key"]),
        capture_digest=str(response_capture["digest"]),
    )


def _locator_row(locator: OfficialLocatorCandidate) -> dict[str, Any]:
    return {
        "url": locator.url,
        "title": locator.title,
        "published_on": locator.published_on,
        "date_kind": locator.date_kind,
        "date_source": locator.date_source,
        "source_family": locator.source_family,
        "provider_rank": None,
    }


def _rank_locators(
    *,
    intent: Mapping[str, Any],
    locators: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    allowed_hosts = {str(value).lower() for value in intent["allowed_document_hosts"]}
    rows: dict[str, dict[str, Any]] = {}
    for raw in locators:
        url = str(raw.get("canonical_url") or raw.get("url") or "").strip()
        split = urlsplit(url)
        host = (split.hostname or "").lower()
        if split.scheme.lower() != "https" or host not in allowed_hosts or split.username:
            continue
        title = " ".join(str(raw.get("title") or "").split())
        score = _locator_score(intent=intent, title=title, url=url)
        if score < 2:
            continue
        row = {
            "url": url,
            "title": title,
            "provider_rank": raw.get("provider_rank"),
            "local_locator_score": score,
        }
        existing = rows.get(url)
        if existing is None or score > int(existing["local_locator_score"]):
            rows[url] = row
    return sorted(
        rows.values(),
        key=lambda row: (
            -int(row["local_locator_score"]),
            int(row["provider_rank"] or 10_000),
            row["url"],
        ),
    )


def _locator_score(*, intent: Mapping[str, Any], title: str, url: str) -> int:
    haystack = f"{title} {urlsplit(url).path}".lower()
    terms = _business_terms(intent)
    score = sum(term in haystack for term in terms)
    if any(token in haystack for token in ("earnings", "results", "financial", "quarter", "10-q", "10-k", "20-f", "6-k")):
        score += 2
    if any(token in haystack for token in _NAVIGATION_NOISE):
        score -= 4
    return score


def _business_terms(intent: Mapping[str, Any]) -> tuple[str, ...]:
    text = " ".join(
        [
            str(intent.get("decision_surface") or ""),
            str((intent.get("semantic_locator_query") or {}).get("en") or ""),
        ]
    ).lower()
    terms = {
        token
        for token in _TOKEN_RE.findall(text)
        if token not in _QUERY_STOP and not token.startswith("site")
    }
    return tuple(sorted(terms))


def _content_hits(intent: Mapping[str, Any], document: Mapping[str, Any]) -> list[str]:
    text = str(document.get("_private_text") or "").lower()
    return [term for term in _business_terms(intent) if term in text][:24]


def _document_disposition(
    *, document: Mapping[str, Any], content_hits: Sequence[str]
) -> tuple[str, str]:
    if document.get("status") != "captured_and_parsed":
        return "typed_gap", str(document.get("code") or "document_unavailable")
    publication = document.get("publication_date") or {}
    if publication.get("conflict_status") != "none":
        return (
            "captured_candidate_with_typed_date_or_content_gap",
            str(publication.get("conflict_status") or "publication_date_unproven"),
        )
    if len(content_hits) < 2:
        return (
            "captured_candidate_with_typed_date_or_content_gap",
            "captured_document_business_term_coverage_insufficient",
        )
    return "candidate_ready_for_local_readjudication", "captured_official_candidate_ready"


def _typed_gap_result(
    *,
    intent: Mapping[str, Any],
    route: str,
    code: str,
    provider_result: LocatorProviderResult | None,
) -> dict[str, Any]:
    return {
        "intent_id": intent["intent_id"],
        "intent_digest": intent["intent_digest"],
        "case_key": intent["case_key"],
        "intent_key": intent["intent_key"],
        "decision_surface": intent["decision_surface"],
        "selected_gap_ids": list(intent["selected_gap_ids"]),
        "route": route,
        "status": "typed_gap",
        "terminal_code": code,
        "selected_locator": None,
        "document": None,
        "matched_business_terms": [],
        "provider_capture_refs": (
            [dict(value) for value in provider_result.capture_refs]
            if provider_result is not None
            else []
        ),
        "evidence_promotion_allowed": False,
        "writer_citable": False,
    }


def _public_discovery(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(item)
        for key, item in value.items()
        if key != "locators"
    }


def strip_private_runtime_fields(result: Mapping[str, Any]) -> dict[str, Any]:
    public = deepcopy(dict(result))
    for row in public.get("intent_results") or []:
        document = row.get("document")
        if isinstance(document, dict):
            document.pop("_private_text", None)
    return public


__all__ = [
    "AUTHORITY_SCHEMA",
    "LocatorProvider",
    "LocatorProviderResult",
    "PRIVATE_NAMESPACE",
    "RESULT_SCHEMA",
    "ResidualGapExternalLiveError",
    "execute_residual_gap_external_live",
    "strip_private_runtime_fields",
    "validate_residual_gap_external_live_authority",
]
