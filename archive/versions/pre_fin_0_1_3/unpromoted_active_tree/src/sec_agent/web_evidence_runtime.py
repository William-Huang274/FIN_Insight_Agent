from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import (
    CaptureFirstOfficialSourceClient,
    SourceTransport,
    UrllibOfficialSourceTransport,
    parse_source_document,
)


SCHEMA_VERSION = "sec_agent_web_evidence_snapshot_v0.2"
CAPTURE_NAMESPACE = "fin-0.1.3/s1-07/current-web-evidence"
TRUSTED_PROMOTION_CLASSES = {
    "company_official_product_surface",
    "company_ir_material",
    "official_regulatory_page",
    "government_dataset_endpoint",
}
COMPANY_VERIFICATION_CLASSES = {
    "company_official_product_surface",
    "company_ir_material",
}
KNOWN_SOURCE_CLASSES = TRUSTED_PROMOTION_CLASSES | {
    "commerce_product_surface",
    "major_financial_news",
    "research_developer_signal",
    "social_official_account",
    "social_unverified_or_influencer",
}


def execute_web_evidence_snapshot(
    args: Mapping[str, Any],
    *,
    transport: SourceTransport | None = None,
) -> dict[str, Any]:
    request = dict(args)
    url = str(request.get("url") or request.get("snapshot_url") or "").strip()
    source_class = str(request.get("source_class") or "").strip()
    policy_ids = _strings(request.get("web_scope_policy_ids"))
    claim_types = [item.lower() for item in _strings(request.get("claim_types") or request.get("claim_type"))]
    company_domains = _hosts(request.get("company_domains"))
    allowed_hosts = _hosts(request.get("web_scope_allowed_domains")) | company_domains
    supplied_domain = _host(str(request.get("domain") or ""))
    parsed_url = urlparse(url)
    url_host = (parsed_url.hostname or "").lower().rstrip(".")
    missing = [name for name, value in (("url", url), ("source_class", source_class), ("web_scope_policy_ids", policy_ids)) if not value]
    if missing:
        return _gap("web_evidence_request_missing_fields", missing=missing)
    if source_class not in KNOWN_SOURCE_CLASSES:
        return _gap("web_evidence_source_class_invalid")
    if parsed_url.scheme != "https" or not url_host or parsed_url.username or parsed_url.password:
        return _gap("web_evidence_https_url_required")
    if not allowed_hosts or url_host not in allowed_hosts:
        return _gap("web_evidence_domain_not_allowlisted", domain=url_host)
    if supplied_domain and supplied_domain != url_host:
        return _gap("web_evidence_declared_domain_mismatch", domain=url_host)
    if source_class in COMPANY_VERIFICATION_CLASSES and (
        request.get("company_domain_verified") is not True or url_host not in company_domains
    ):
        return _gap("web_evidence_company_domain_not_verified", domain=url_host)

    seed = "|".join([url, source_class, ",".join(policy_ids), ",".join(claim_types)])
    snapshot_id = str(request.get("snapshot_id") or "websnap_" + hashlib.sha256(seed.encode()).hexdigest()[:16])
    capture_root = Path(str(request.get("web_capture_root") or ".codex_runtime/mcp_web_evidence")).resolve()
    timeout_seconds = max(1, min(int(float(request.get("fetch_timeout_s") or request.get("timeout_s") or 20)), 120))
    byte_ceiling = max(1024, min(int(request.get("byte_ceiling") or 8_388_608), 16_777_216))
    store = FileCanonicalObjectStore(capture_root / "objects")
    client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=transport or UrllibOfficialSourceTransport(),
        namespace=CAPTURE_NAMESPACE,
    )
    response, attempt = client.fetch(
        case_key=str(request.get("case_key") or request.get("ticker") or "__mcp_web__").upper(),
        route_id=snapshot_id,
        url=url,
        allowed_hosts=allowed_hosts,
        timeout_seconds=timeout_seconds,
        byte_ceiling=byte_ceiling,
    )
    common = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "snapshot_url": url,
        "as_of_datetime": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_class": source_class,
        "web_scope_policy_ids": policy_ids,
        "network_calls": client.network_calls,
        "capture_before_parse": True,
        "request_capture": attempt.get("request_capture"),
        "response_capture": attempt.get("response_capture"),
    }
    if response is None or attempt.get("status") != "captured":
        code = str(attempt.get("failure_code") or "web_evidence_fetch_failed")
        return {
            **common,
            "status": "error",
            "error": code,
            "context_rows": [],
            "evidence_rows": [],
            "promotion": {"decision": "reject", "reason_code": code},
            "source_gaps": [_gap_row(code, domain=url_host, attempt=attempt)],
            "artifact_refs": _artifact_refs(client.capture_refs),
        }

    parsed = parse_source_document(response)
    parser_payload = {
        "schema_version": "fin_ia_0_1_3_s1_07_parser_capture_v1_0",
        "snapshot_id": snapshot_id,
        "response_capture_ref": attempt["response_capture"]["object_key"],
        "response_capture_digest": attempt["response_capture"]["digest"],
        "parser": parsed,
    }
    parser_ref = store.put_json(parser_payload, namespace=CAPTURE_NAMESPACE, artifact_type="web_parser_result")
    capture_refs = [*client.capture_refs, parser_ref]
    parser_summary = {key: value for key, value in parsed.items() if key != "text"}
    if parsed.get("status") != "parsed":
        return {
            **common,
            "status": "error",
            "error": "web_evidence_all_parsers_failed",
            "parser": parser_summary,
            "parser_capture": parser_ref,
            "context_rows": [],
            "evidence_rows": [],
            "promotion": {"decision": "reject", "reason_code": "web_evidence_all_parsers_failed"},
            "source_gaps": [_gap_row("web_evidence_all_parsers_failed", domain=url_host, attempt=attempt)],
            "artifact_refs": _artifact_refs(capture_refs),
        }

    text = str(parsed["text"])
    title = str(request.get("source_title") or _title_from_text(text) or url_host)
    excerpt = text[: min(max(int(request.get("excerpt_chars") or 2400), 200), 4000)].strip()
    trusted = source_class in TRUSTED_PROMOTION_CLASSES
    row_body = {
        "evidence_ref": f"current_web_evidence:{snapshot_id}",
        "source_family": "live_public_web_context",
        "retrieval_route": "live_public_web_fetch_capture_parse",
        "source_class": source_class,
        "web_scope_policy_ids": policy_ids,
        "claim_types": claim_types,
        "url": response.final_url,
        "domain": (urlparse(response.final_url).hostname or url_host).lower(),
        "snapshot_id": snapshot_id,
        "as_of_datetime": common["as_of_datetime"],
        "citation": {"url": response.final_url, "title": title},
        "statement": excerpt,
        "source_capture_ref": attempt["response_capture"]["object_key"],
        "source_capture_digest": attempt["response_capture"]["digest"],
        "parser_capture_ref": parser_ref["object_key"],
        "parser_capture_digest": parser_ref["digest"],
        "parser_adapter": parsed["adapter"],
        "parser_text_digest": parsed["text_sha256"],
        "writer_citable": trusted,
        "domain_judgment_eligible": trusted,
        "context_only": not trusted,
        "lead_only": not trusted,
        "exact_value_authority": False,
        "authority_boundary": "parsed_source_text_only_no_numeric_or_causal_authority",
    }
    row = {**row_body, "evidence_row_digest": canonical_digest(row_body)}
    promotion = {
        "decision": "promote_parsed_evidence" if trusted else "retain_context_only",
        "trusted_source_class": trusted,
        "writer_citable": trusted,
        "exact_value_authority": False,
        "reason_code": "trusted_allowlisted_parsed_source" if trusted else "source_class_context_only",
    }
    promotion_ref = store.put_json(
        {
            "schema_version": "fin_ia_0_1_3_s1_07_evidence_promotion_receipt_v1_0",
            "snapshot_id": snapshot_id,
            "row_digest": row["evidence_row_digest"],
            "promotion": promotion,
        },
        namespace=CAPTURE_NAMESPACE,
        artifact_type="web_evidence_promotion_receipt",
    )
    capture_refs.append(promotion_ref)
    return {
        **common,
        "status": "ok" if trusted else "partial",
        "final_url": response.final_url,
        "redirect_chain": list(response.redirect_chain),
        "parser": parser_summary,
        "parser_capture": parser_ref,
        "promotion": promotion,
        "promotion_capture": promotion_ref,
        "context_rows": [row],
        "evidence_rows": [row] if trusted else [],
        "source_gaps": [] if trusted else [_gap_row("web_evidence_source_class_context_only", domain=url_host, attempt=attempt)],
        "artifact_refs": _artifact_refs(capture_refs),
    }


def _gap(code: str, *, missing: list[str] | None = None, domain: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": code,
        "context_rows": [],
        "evidence_rows": [],
        "source_gaps": [_gap_row(code, domain=domain, missing=missing)],
        "artifact_refs": [],
    }


def _gap_row(code: str, *, domain: str = "", missing: list[str] | None = None, attempt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source_family": "live_public_web_context",
        "reason_code": code,
        "domain": domain,
        "missing": list(missing or []),
        "attempt_backed": attempt is not None,
        "attempt_status": str((attempt or {}).get("status") or "not_started"),
        "source_available": False,
        "cannot_infer": "source content or financial claim from an unparsed, rejected, or context-only source",
    }


def _artifact_refs(refs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "artifact_id": str(ref.get("artifact_type") or "web_capture"),
            "path": str(ref.get("object_key") or ""),
            "digest": str(ref.get("digest") or ""),
            "row_count": 1,
        }
        for ref in refs
    ]


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item).strip() for item in value]
    else:
        values = [str(value).strip()]
    return [item for item in values if item]


def _host(value: str) -> str:
    raw = value.strip().lower().rstrip(".")
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower().rstrip(".")


def _hosts(value: Any) -> set[str]:
    return {host for item in _strings(value) if (host := _host(item))}


def _title_from_text(text: str) -> str:
    compact = " ".join(text.split())
    return compact[:160].strip()


__all__ = ["execute_web_evidence_snapshot"]
