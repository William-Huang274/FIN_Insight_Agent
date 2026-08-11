from __future__ import annotations

from collections import Counter
from copy import deepcopy
import ipaddress
import json
from pathlib import Path
import socket
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from sec_agent.canonical_runtime.models import canonical_digest


ASSESSMENT_SCHEMA = "fin_ia_0_1_3_s1_08_external_combined_live_assessment_v1_0"
SYNTHETIC_NETWORK = ipaddress.ip_network("198.18.0.0/15")
_OFFICIAL_DOMAIN_SUFFIXES = (
    "delltechnologies.com",
    "microsoft.com",
    "micron.com",
    "nvidia.com",
    "sec.gov",
    "tsmc.com",
)


class ExternalCombinedAssessmentError(RuntimeError):
    pass


Resolver = Callable[[str], Sequence[str]]


def assess_external_combined_live(
    *,
    result: Mapping[str, Any],
    runtime_root: str | Path,
    resolver: Resolver | None = None,
) -> dict[str, Any]:
    root = Path(runtime_root)
    if (
        result.get("schema_version")
        != "fin_ia_0_1_3_s1_08_external_combined_terminal_v1_0"
        or result.get("status") != "completed_with_typed_failures"
        or not root.is_dir()
    ):
        raise ExternalCombinedAssessmentError(
            "external_combined_r1_terminal_or_runtime_invalid"
        )

    official = _assess_official_lane(
        rows=result.get("official_case_results") or (),
        root=root / "official",
        resolver=resolver or _resolve,
    )
    shadow = _assess_shadow_lane(
        rows=result.get("firecrawl_shadow_results") or (),
        root=root / "firecrawl-shadow",
    )
    observed = deepcopy(dict(result.get("observed_counts") or {}))
    if (
        observed.get("official_cases_terminalized") != 3
        or observed.get("shadow_queries_terminalized") != 24
        or observed.get("model_calls") != 0
        or observed.get("embedding_calls") != 0
        or observed.get("rerank_calls") != 0
        or observed.get("evidence_promotions") != 0
        or observed.get("retry_calls") != 0
    ):
        raise ExternalCombinedAssessmentError(
            "external_combined_r1_observed_counts_invalid"
        )

    body = {
        "schema_version": ASSESSMENT_SCHEMA,
        "status": "terminal_valid_external_candidate_reachability_blocked",
        "result_digest": result["terminal_result_digest"],
        "public_record_digest": result["public_record_digest"],
        "run_id": result["run_id"],
        "attempt_id": result["attempt_id"],
        "query_variant": result["query_variant"],
        "observed_counts": observed,
        "capture_integrity": {
            "official_content_addressed_objects": official[
                "content_addressed_object_count"
            ],
            "official_content_addresses_valid": official[
                "all_content_addresses_valid"
            ],
            "firecrawl_capture_refs": shadow["capture_ref_count"],
            "firecrawl_capture_refs_sha_valid": shadow[
                "all_capture_ref_hashes_valid"
            ],
            "raw_request_or_response_content_lost": False,
        },
        "query_facet_binding": official["query_facet_binding"],
        "official_lane": official["summary"],
        "firecrawl_shadow_lane": shadow["summary"],
        "root_cause_disposition": {
            "deepseek_or_model_failure": False,
            "query_facet_quality_failure_established": False,
            "official_lane_project_defect": (
                "The combined runner omitted the already-established controlled "
                "synthetic-DNS handshake. Public allowlisted hosts resolved through "
                "the desktop network proxy into 198.18.0.0/15 and were rejected by "
                "the SSRF guard before any HTTP response could be captured."
            ),
            "firecrawl_external_constraint": (
                "The provider explicitly reported keyless free-tier credit exhaustion; "
                "this is not evidence that the remaining MU/NVDA queries were poor."
            ),
            "firecrawl_project_defects": [
                "HTTP 429 with reason=credits was not classified as a systemic stop.",
                "Case-major scheduling spent every successful observation on DELL before MU or NVDA.",
            ],
            "bound_query_telemetry_gap": (
                "The delegate received the facet-bound query and its digest appears in "
                "attempt budget state, but the public attempt query view still shows the "
                "pre-binding query and receipts omit the effective query text."
            ),
        },
        "stage_disposition": {
            "owner_stage": "S1_08_external_candidate_discovery",
            "r1_is_immutable_and_must_not_be_retried": True,
            "automatic_replacement_live_allowed": False,
            "bounded_zero_call_successor_required": [
                "controlled synthetic-DNS preflight and execution handshake",
                "case-slot-fair shadow scheduling",
                "systemic 429 credit-exhaustion stop with remaining identities terminalized",
                "effective facet-bound query preserved as audit truth",
                "capture replay and mutation proof",
            ],
            "historical_firecrawl_full_matrix_remains_quality_evidence": True,
            "fresh_external_recovery_authority_required_after_zero_call_proof": True,
            "internal_retrieval_started": False,
            "internal_retrieval_backlog_ref": (
                "configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_"
                "external_internal_progression_plan_v1_1.json"
            ),
        },
        "known_boundary": (
            "This assessment establishes an operational failure disposition, not "
            "external retrieval acceptance, internal candidate recall, BGE/reranker "
            "gain, Evidence promotion, report quality or release readiness."
        ),
    }
    return {**body, "assessment_digest": canonical_digest(body)}


def _assess_official_lane(
    *,
    rows: Sequence[Mapping[str, Any]],
    root: Path,
    resolver: Resolver,
) -> dict[str, Any]:
    if len(rows) != 3 or not root.is_dir():
        raise ExternalCombinedAssessmentError("official_lane_shape_invalid")
    object_paths = sorted(root.rglob("*.json"))
    objects = [json.loads(path.read_text(encoding="utf-8")) for path in object_paths]
    address_valid = all(
        path.stem == canonical_digest(payload)
        for path, payload in zip(object_paths, objects, strict=True)
    )
    captures = [row for row in objects if row.get("capture_kind")]
    requests = [row for row in captures if row.get("capture_kind") == "source_request"]
    failures = [
        row for row in captures if row.get("capture_kind") == "source_transport_failure"
    ]
    responses = [row for row in captures if row.get("capture_kind") == "source_response"]
    failure_codes = Counter(str(row.get("failure_code") or "") for row in failures)

    hosts = sorted(
        {
            (urlparse(str(row.get("url") or "")).hostname or "").lower()
            for row in requests
            if row.get("url")
        }
    )
    resolution_rows: list[dict[str, Any]] = []
    for host in hosts:
        addresses = sorted(set(str(value) for value in resolver(host)))
        parsed = [ipaddress.ip_address(value) for value in addresses]
        resolution_rows.append(
            {
                "host": host,
                "addresses": addresses,
                "all_addresses_in_controlled_synthetic_range": bool(parsed)
                and all(
                    address.version == 4 and address in SYNTHETIC_NETWORK
                    for address in parsed
                ),
            }
        )

    receipts = [
        receipt
        for case in rows
        for receipt in (case.get("bound_query_receipts") or ())
    ]
    attempt_bound_digests = {
        str((attempt.get("attempt_budget_state") or {}).get("query_digest") or "")
        for case in rows
        for attempt in ((case.get("candidate_result") or {}).get("attempts") or ())
    }
    receipt_bound_digests = {
        str(receipt.get("bound_query_digest") or "") for receipt in receipts
    }
    query_view_mismatches = sum(
        str((attempt.get("query") or {}).get("query_digest") or "")
        != str((attempt.get("attempt_budget_state") or {}).get("query_digest") or "")
        for case in rows
        for attempt in ((case.get("candidate_result") or {}).get("attempts") or ())
    )
    case_rows = []
    for case in rows:
        candidate = case.get("candidate_result") or {}
        case_rows.append(
            {
                "case_key": case.get("case_key"),
                "status": case.get("status"),
                "network_calls": case.get("network_calls"),
                "document_fetches": case.get("document_fetches"),
                "accepted_candidates": len(candidate.get("accepted_candidates") or ()),
                "selected_candidates": len(candidate.get("selected_candidates") or ()),
                "typed_gaps": len(candidate.get("typed_gaps") or ()),
                "bound_query_receipts": len(case.get("bound_query_receipts") or ()),
            }
        )

    return {
        "content_addressed_object_count": len(object_paths),
        "all_content_addresses_valid": address_valid,
        "query_facet_binding": {
            "receipt_count": len(receipts),
            "attempt_budget_digests_equal_receipt_bound_digests": (
                attempt_bound_digests == receipt_bound_digests
            ),
            "attempt_query_view_mismatch_count": query_view_mismatches,
            "effective_query_text_preserved_in_receipts": all(
                bool(receipt.get("bound_query")) for receipt in receipts
            ),
        },
        "summary": {
            "case_results": case_rows,
            "request_captures": len(requests),
            "response_captures": len(responses),
            "transport_failure_captures": len(failures),
            "failure_codes": dict(sorted(failure_codes.items())),
            "post_run_dns_diagnostic": {
                "resolved_hosts": resolution_rows,
                "all_observed_hosts_use_controlled_synthetic_range": bool(
                    resolution_rows
                )
                and all(
                    row["all_addresses_in_controlled_synthetic_range"]
                    for row in resolution_rows
                ),
                "diagnostic_is_not_historical_dns_capture": True,
            },
        },
    }


def _assess_shadow_lane(
    *, rows: Sequence[Mapping[str, Any]], root: Path
) -> dict[str, Any]:
    if len(rows) != 24 or not root.is_dir():
        raise ExternalCombinedAssessmentError("firecrawl_shadow_shape_invalid")
    capture_ref_count = 0
    all_hashes_valid = True
    credit_failures = 0
    retry_after_seconds: list[int] = []
    successful_cases: Counter[str] = Counter()
    successful_locators = 0
    official_locator_occurrences = 0
    unique_domains: set[str] = set()
    published_date_count = 0
    statuses: Counter[int] = Counter()
    for row in rows:
        refs = row.get("capture_refs") or {}
        for name in ("safe_request", "raw_response", "typed_failure", "call_terminal"):
            ref = refs.get(name)
            digest = refs.get(f"{name}_sha256")
            if not ref:
                continue
            capture_ref_count += 1
            path = root / str(ref)
            all_hashes_valid = all_hashes_valid and path.is_file() and _sha256(path) == digest
        status = int(row.get("http_status") or 0)
        statuses[status] += 1
        if row.get("status") == "completed":
            successful_cases[str(row.get("case_key") or "")] += 1
            locators = (row.get("provider_projection") or {}).get("locators") or []
            successful_locators += len(locators)
            published_date_count += sum(
                bool(locator.get("published_at_raw")) for locator in locators
            )
            for locator in locators:
                domain = str(locator.get("source_domain") or "").lower()
                if domain:
                    unique_domains.add(domain)
                if any(
                    domain == suffix or domain.endswith("." + suffix)
                    for suffix in _OFFICIAL_DOMAIN_SUFFIXES
                ):
                    official_locator_occurrences += 1
            continue
        raw_ref = refs.get("raw_response")
        if status != 429 or not raw_ref:
            continue
        try:
            payload = json.loads((root / str(raw_ref)).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if str(payload.get("reason") or "").lower() == "credits":
            credit_failures += 1
            if payload.get("retry_after_seconds") is not None:
                retry_after_seconds.append(int(payload["retry_after_seconds"]))

    return {
        "capture_ref_count": capture_ref_count,
        "all_capture_ref_hashes_valid": all_hashes_valid,
        "summary": {
            "http_status_counts": {str(key): value for key, value in sorted(statuses.items())},
            "successful_queries": sum(successful_cases.values()),
            "failed_queries": len(rows) - sum(successful_cases.values()),
            "successful_queries_by_case": dict(sorted(successful_cases.items())),
            "successful_locator_occurrences": successful_locators,
            "unique_source_domains_in_successful_queries": len(unique_domains),
            "official_domain_locator_occurrences": official_locator_occurrences,
            "provider_published_date_occurrences": published_date_count,
            "credit_exhaustion_failures": credit_failures,
            "credit_exhaustion_retry_after_seconds_range": (
                [min(retry_after_seconds), max(retry_after_seconds)]
                if retry_after_seconds
                else []
            ),
            "remaining_queries_stopped_after_first_credit_exhaustion": False,
            "successful_case_coverage": [len(successful_cases), 3],
        },
    }


def _resolve(host: str) -> Sequence[str]:
    return tuple(
        sorted(
            {
                str(row[4][0])
                for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        )
    )


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
