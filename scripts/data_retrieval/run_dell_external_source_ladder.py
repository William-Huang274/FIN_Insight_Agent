from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_source_capture import capture_plan  # noqa: E402
from retrieval.external_source_ladder import (  # noqa: E402
    EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION,
    build_external_fetch_shortlist,
    compile_external_source_ladder_successor_plan,
    compile_safe_provider_request,
    normalize_tencent_search_response,
    source_family_allowed_hosts,
    validate_external_source_ladder_plan,
    validate_external_source_ladder_successor_spec,
)
from retrieval.public_context_source import (  # noqa: E402
    PublicContextSourceError,
    adjudicate_publication_date_from_capture,
    compile_public_html_source_object,
    compile_public_pdf_source_object,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.text import tokenize  # noqa: E402


PLAN = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_external_source_ladder_plan_v1_0.json"
)
SUCCESSOR_SPEC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_external_source_ladder_successor_spec_v1_0.json"
)
DEFAULT_PRIVATE_ROOT = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1_dell_external_source_ladder"
)
DEFAULT_PUBLIC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_external_source_ladder_result_v1_0.json"
)
DEFAULT_PUBLIC_SUCCESSOR = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_external_source_ladder_result_v1_1.json"
)
DEFAULT_PUBLIC_CAPTURE_REPLAY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_external_capture_replay_result_v1_0.json"
)
_STOPWORDS = {
    "and",
    "for",
    "from",
    "official",
    "the",
    "with",
    "2025",
    "2026",
}


ProviderCall = Callable[[Mapping[str, Any], int], Mapping[str, Any]]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"external_ladder_json_not_mapping:{path.name}")
    return value


def _validate_content_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop(field, ""))
    if digest != canonical_digest(body):
        raise RuntimeError(code)


def _bound_path(ref: str) -> Path:
    path = Path(str(ref))
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load_successor_context(
    spec_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = validate_external_source_ladder_successor_spec(_read_json(spec_path))
    binding = spec["predecessor_binding"]
    base_plan_path = _bound_path(str(binding["plan_ref"]))
    public_path = _bound_path(str(binding["public_result_ref"]))
    private_path = _bound_path(str(binding["private_result_ref"]))
    for path, expected in (
        (base_plan_path, binding["plan_sha256"]),
        (public_path, binding["public_result_sha256"]),
        (private_path, binding["private_result_sha256"]),
    ):
        if _sha256(path) != str(expected):
            raise RuntimeError("external_ladder_successor_predecessor_sha_mismatch")
    base_plan = validate_external_source_ladder_plan(_read_json(base_plan_path))
    public = _read_json(public_path)
    private = _read_json(private_path)
    _validate_content_digest(
        public,
        "result_digest",
        "external_ladder_successor_public_result_digest_invalid",
    )
    _validate_content_digest(
        private,
        "result_digest",
        "external_ladder_successor_private_result_digest_invalid",
    )
    if (
        public.get("result_digest") != binding.get("public_result_digest")
        or public.get("private_execution_sha256") != binding.get("private_result_sha256")
        or base_plan.get("plan_digest") != binding.get("plan_digest")
        or private.get("plan_binding", {}).get("plan_digest") != binding.get("plan_digest")
    ):
        raise RuntimeError("external_ladder_successor_predecessor_binding_invalid")
    plan = compile_external_source_ladder_successor_plan(
        base_plan=base_plan,
        successor_spec=spec,
    )
    return plan, private, spec


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def _require_clean() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("dell_external_source_ladder_clean_worktree_required")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _redact(value: object, secrets: Sequence[str]) -> object:
    if isinstance(value, Mapping):
        return {str(key): _redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value


def _tencent_provider_call(request_body: Mapping[str, Any], timeout: int) -> Mapping[str, Any]:
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.wsa.v20250508 import models
        from tencentcloud.wsa.v20250508.wsa_client import WsaClient
    except ImportError as exc:
        raise RuntimeError("tencent_wsa_sdk_unavailable") from exc
    secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID", "").strip()
    secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY", "").strip()
    if not secret_id or not secret_key:
        raise RuntimeError("tencent_wsa_credentials_missing")
    http_profile = HttpProfile()
    http_profile.endpoint = "wsa.tencentcloudapi.com"
    http_profile.reqTimeout = timeout
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = WsaClient(credential.Credential(secret_id, secret_key), "", client_profile)
    request = models.SearchProRequest()
    request.from_json_string(json.dumps(dict(request_body), ensure_ascii=False))
    response = client.SearchPro(request)
    return json.loads(response.to_json_string())


def _empty_bundle(
    *,
    query_unit_id: str,
    safe_request_digest: str,
    failure_code: str,
) -> dict[str, Any]:
    body = {
        "schema_version": EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION,
        "query_unit_id": query_unit_id,
        "safe_request_digest": safe_request_digest,
        "provider_request_id": None,
        "provider_version": None,
        "provider_message": None,
        "locators": [],
        "rejections": [{"provider_rank": None, "code": failure_code}],
        "raw_page_count": 0,
        "provider_date_is_authority": False,
        "evidence_promotion_allowed": False,
    }
    return {**body, "bundle_digest": canonical_digest(body)}


def execute_locator_queries(
    *,
    plan: Mapping[str, Any],
    attempt_root: Path,
    provider_call: ProviderCall,
    predecessor_private_result: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    locator_bundles: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    timeout = int(plan["execution_budget"]["provider_timeout_seconds"])
    secret_values = [
        os.environ.get("TENCENTCLOUD_SECRET_ID", ""),
        os.environ.get("TENCENTCLOUD_SECRET_KEY", ""),
    ]
    predecessor_receipts = {
        str(row.get("query_unit_id") or ""): row
        for row in (predecessor_private_result or {}).get("provider_receipts") or ()
    }
    provider_calls = 0
    for unit in plan["query_units"]:
        unit_id = str(unit["query_unit_id"])
        execution_mode = str(unit.get("execution_mode") or "provider")
        if execution_mode == "replay":
            predecessor = predecessor_receipts.get(unit_id)
            if predecessor is None:
                raise RuntimeError("external_ladder_predecessor_locator_receipt_missing")
            bundle_path = _bound_path(str(predecessor.get("locator_bundle_ref") or ""))
            if _sha256(bundle_path) != str(predecessor.get("locator_bundle_sha256") or ""):
                raise RuntimeError("external_ladder_predecessor_locator_sha_mismatch")
            bundle = _read_json(bundle_path)
            _validate_content_digest(
                bundle,
                "bundle_digest",
                "external_ladder_predecessor_locator_digest_invalid",
            )
            if (
                bundle.get("query_unit_id") != unit_id
                or predecessor.get("status") != "provider_locator_call_completed"
            ):
                raise RuntimeError("external_ladder_predecessor_locator_binding_invalid")
            locator_bundles.append(bundle)
            receipts.append(
                {
                    "query_unit_id": unit_id,
                    "proposition_id": unit["proposition_id"],
                    "tier_id": unit["tier_id"],
                    "status": "predecessor_locator_bundle_replayed",
                    "failure_code": None,
                    "elapsed_ms": 0,
                    "safe_request_ref": predecessor.get("safe_request_ref"),
                    "safe_request_sha256": predecessor.get("safe_request_sha256"),
                    "raw_capture_ref": predecessor.get("raw_capture_ref"),
                    "raw_capture_sha256": predecessor.get("raw_capture_sha256"),
                    "locator_bundle_ref": predecessor.get("locator_bundle_ref"),
                    "locator_bundle_sha256": predecessor.get("locator_bundle_sha256"),
                    "locator_count": len(bundle.get("locators") or ()),
                    "provider_call_count": 0,
                    "historical_provider_call_count": 1,
                    "retry_count": 0,
                    "model_call_count": 0,
                }
            )
            continue
        unit_root = attempt_root / "provider" / _safe_name(unit_id)
        safe_request = compile_safe_provider_request(unit)
        request_path = unit_root / "safe_request.json"
        _write_new(request_path, safe_request)
        started = time.monotonic()
        response_capture_path: Path | None = None
        failure_capture_path: Path | None = None
        try:
            payload = provider_call(safe_request["request_body"], timeout)
            raw_body = {
                "schema_version": "fin_ia_s1_external_provider_raw_response_capture_v1_0",
                "query_unit_id": unit_id,
                "safe_request_digest": safe_request["request_digest"],
                "capture_before_parse": True,
                "credential_fields_present": False,
                "raw_response": _redact(payload, secret_values),
            }
            raw_capture = {**raw_body, "capture_digest": canonical_digest(raw_body)}
            response_capture_path = unit_root / "raw_response.json"
            _write_new(response_capture_path, raw_capture)
            bundle = normalize_tencent_search_response(
                raw_payload=payload,
                query_unit=unit,
                safe_request=safe_request,
                result_ceiling=int(plan["execution_budget"]["result_ceiling_per_call"]),
            )
            bundle_path = unit_root / "locator_bundle.json"
            _write_new(bundle_path, bundle)
            status = "provider_locator_call_completed"
            failure_code = None
        except Exception as exc:  # terminal receipt must survive provider failures
            failure_code = f"{type(exc).__name__}:{str(_redact(str(exc), secret_values))[:300]}"
            failure_body = {
                "schema_version": "fin_ia_s1_external_provider_failure_capture_v1_0",
                "query_unit_id": unit_id,
                "safe_request_digest": safe_request["request_digest"],
                "failure_code": failure_code,
                "credential_fields_present": False,
                "retry_executed": False,
            }
            failure_capture = {
                **failure_body,
                "capture_digest": canonical_digest(failure_body),
            }
            failure_capture_path = unit_root / "provider_failure.json"
            _write_new(failure_capture_path, failure_capture)
            bundle = _empty_bundle(
                query_unit_id=unit_id,
                safe_request_digest=str(safe_request["request_digest"]),
                failure_code=failure_code,
            )
            bundle_path = unit_root / "locator_bundle.json"
            _write_new(bundle_path, bundle)
            status = "provider_locator_call_failed"
        raw_path = response_capture_path or failure_capture_path
        if raw_path is None:
            raise RuntimeError("external_ladder_provider_capture_missing")
        locator_bundles.append(bundle)
        provider_calls += 1
        receipts.append(
            {
                "query_unit_id": unit_id,
                "proposition_id": unit["proposition_id"],
                "tier_id": unit["tier_id"],
                "status": status,
                "failure_code": failure_code,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "safe_request_ref": _relative(request_path),
                "safe_request_sha256": _sha256(request_path),
                "raw_capture_ref": _relative(raw_path),
                "raw_capture_sha256": _sha256(raw_path),
                "raw_capture_kind": (
                    "provider_response"
                    if response_capture_path is not None
                    else "provider_failure"
                ),
                "provider_response_capture_ref": (
                    _relative(response_capture_path)
                    if response_capture_path is not None
                    else None
                ),
                "provider_response_capture_sha256": (
                    _sha256(response_capture_path)
                    if response_capture_path is not None
                    else None
                ),
                "provider_failure_capture_ref": (
                    _relative(failure_capture_path)
                    if failure_capture_path is not None
                    else None
                ),
                "provider_failure_capture_sha256": (
                    _sha256(failure_capture_path)
                    if failure_capture_path is not None
                    else None
                ),
                "locator_bundle_ref": _relative(bundle_path),
                "locator_bundle_sha256": _sha256(bundle_path),
                "locator_count": len(bundle.get("locators") or ()),
                "provider_call_count": 1,
                "retry_count": 0,
                "model_call_count": 0,
            }
        )
    if provider_calls > int(plan["execution_budget"]["provider_call_ceiling"]):
        raise RuntimeError("external_ladder_provider_call_ceiling_exceeded")
    return locator_bundles, receipts


def _compile_original_capture_plan(
    *,
    plan: Mapping[str, Any],
    shortlist: Mapping[str, Any],
) -> dict[str, Any]:
    sources = []
    for index, row in enumerate(shortlist.get("selected") or (), start=1):
        url = str(row["canonical_url"])
        host = str(urlsplit(url).hostname or "").lower()
        registry = dict(row["source_registry"])
        sources.append(
            {
                "route_id": f"DELL_EXT_ORIGINAL_{index:03d}_{canonical_digest(url)[:10].upper()}",
                "case_key": "DELL",
                "url": url,
                "allowed_hosts": source_family_allowed_hosts(
                    registry,
                    observed_host=host,
                ),
                "expected_content_types": [
                    "text/html",
                    "application/xhtml+xml",
                    "application/pdf",
                    "application/octet-stream",
                    "text/plain",
                ],
                "byte_ceiling": int(plan["execution_budget"]["original_fetch_byte_ceiling"]),
                "timeout_seconds": int(plan["execution_budget"]["original_fetch_timeout_seconds"]),
                "transport": "requests",
                "max_transport_retries": 0,
                "locator_digest": row["locator_digest"],
            }
        )
    return {
        "schema_version": "fin_ia_official_source_capture_plan_v1_0",
        "status": "official_source_capture_plan",
        "plan_id": str(plan["plan_id"]) + "::ORIGINAL-CAPTURES",
        "policy": {
            "capture_before_parse": True,
            "https_only": True,
            "credentials_forbidden": True,
        },
        "sources": sources,
    }


def _load_capture_object(ref: str) -> dict[str, Any]:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return _read_json(path.resolve())


def _proposal_terms(unit: Mapping[str, Any]) -> set[str]:
    raw = " ".join(
        [
            str(unit.get("query") or ""),
            " ".join(str(value).replace("_", " ") for value in unit.get("expected_output_ids") or ()),
        ]
    )
    return {token for token in tokenize(raw) if len(token) > 2 and token not in _STOPWORDS}


def _block_candidate_proposals(
    *,
    source_object: Mapping[str, Any],
    query_unit: Mapping[str, Any],
    policy: Mapping[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    scope_terms = {str(value).casefold() for value in policy["scope_anchor_terms"]}
    material_terms = {
        str(value).casefold() for value in policy["material_signal_terms"]
    }
    minimum_scope = int(policy["minimum_scope_anchor_hits"])
    minimum_material = int(policy["minimum_material_signal_hits"])
    before = int(policy["context_blocks_before"])
    after = int(policy["context_blocks_after"])
    expected_terms = _proposal_terms(query_unit)
    scored: list[tuple[float, int, int, str, str, list[str], list[str], list[str]]] = []
    for segment in source_object.get("segments") or ():
        segment_text = str(segment.get("text") or "")
        blocks = [value.strip() for value in segment_text.split("\n\n") if value.strip()]
        for index, central in enumerate(blocks):
            central_tokens = set(tokenize(central))
            scope_hits = sorted(scope_terms.intersection(central_tokens))
            material_hits = sorted(material_terms.intersection(central_tokens))
            if len(scope_hits) < minimum_scope or len(material_hits) < minimum_material:
                continue
            start = max(0, index - before)
            end = min(len(blocks), index + after + 1)
            excerpt = "\n\n".join(blocks[start:end])
            if excerpt not in segment_text:
                raise RuntimeError("external_ladder_candidate_window_not_capture_bound")
            query_hits = sorted(expected_terms.intersection(set(tokenize(excerpt))))
            score = (
                3.0 * len(scope_hits)
                + 2.0 * len(material_hits)
                + 0.25 * len(query_hits)
            )
            scored.append(
                (
                    score,
                    len(material_hits),
                    len(scope_hits),
                    str(segment["segment_id"]),
                    excerpt,
                    scope_hits,
                    material_hits,
                    query_hits,
                )
            )
    proposals: list[dict[str, Any]] = []
    seen_excerpts: set[str] = set()
    for (
        score,
        _material_count,
        _scope_count,
        segment_id,
        excerpt,
        scope_hits,
        material_hits,
        query_hits,
    ) in sorted(scored, key=lambda row: (-row[0], -row[1], -row[2], row[3], row[4])):
        if excerpt in seen_excerpts:
            continue
        body = {
            "source_id": source_object["source_id"],
            "source_object_digest": source_object["source_object_digest"],
            "segment_id": segment_id,
            "proposition_id": query_unit["proposition_id"],
            "query_unit_id": query_unit["query_unit_id"],
            "query_tier_id": query_unit["tier_id"],
            "expected_output_ids": list(query_unit["expected_output_ids"]),
            "excerpt": excerpt,
            "scope_anchor_hits": scope_hits,
            "material_signal_hits": material_hits,
            "query_term_overlap": query_hits,
            "deterministic_locator_relevance": round(score, 6),
            "selection_method": str(
                policy.get("selection_method")
                or "capture_bound_central_block_identity_and_material_signal_v1"
            ),
            "candidate_not_evidence": True,
            "candidate_decision_required": True,
        }
        proposals.append({**body, "candidate_proposal_digest": canonical_digest(body)})
        seen_excerpts.add(excerpt)
        if len(proposals) >= limit:
            break
    return proposals


def _candidate_proposals(
    *,
    source_object: Mapping[str, Any],
    query_unit: Mapping[str, Any],
    candidate_selection_policy: Mapping[str, Any] | None = None,
    limit: int = 2,
) -> list[dict[str, Any]]:
    if candidate_selection_policy is not None:
        raw_policy = candidate_selection_policy.get(str(query_unit["proposition_id"]))
        if not isinstance(raw_policy, Mapping):
            raise RuntimeError("external_ladder_candidate_policy_missing")
        effective_policy = deepcopy(dict(raw_policy))
        expected_output_text = " ".join(
            str(value).casefold()
            for value in query_unit.get("expected_output_ids") or ()
        )
        relationship_request = any(
            cue in expected_output_text
            for cue in (
                "relationship",
                "supplier_names",
                "dell_names",
                "platform_delivery",
            )
        )
        if relationship_request:
            effective_policy["material_signal_terms"] = sorted(
                {
                    *(
                        str(value).casefold()
                        for value in effective_policy["material_signal_terms"]
                    ),
                    "available",
                    "availability",
                    "building",
                    "builders",
                    "collaboration",
                    "collaborating",
                    "combines",
                    "deliver",
                    "delivered",
                    "delivers",
                    "delivery",
                    "partner",
                    "partners",
                    "partnership",
                    "support",
                    "supported",
                    "supports",
                }
            )
            effective_policy["minimum_material_signal_hits"] = 1
            effective_policy["selection_method"] = (
                "capture_bound_relationship_facets_and_material_signal_v1"
            )
        return _block_candidate_proposals(
            source_object=source_object,
            query_unit=query_unit,
            policy=effective_policy,
            limit=limit,
        )
    terms = _proposal_terms(query_unit)
    scored = []
    for segment in source_object.get("segments") or ():
        text = str(segment.get("text") or "")
        tokens = set(tokenize(text))
        overlap = sorted(terms.intersection(tokens))
        score = len(overlap) / max(1, len(terms))
        if overlap:
            scored.append((score, len(overlap), str(segment["segment_id"]), text, overlap))
    proposals = []
    for score, overlap_count, segment_id, text, overlap in sorted(
        scored, key=lambda row: (-row[0], -row[1], row[2])
    )[:limit]:
        body = {
            "source_id": source_object["source_id"],
            "source_object_digest": source_object["source_object_digest"],
            "segment_id": segment_id,
            "proposition_id": query_unit["proposition_id"],
            "query_unit_id": query_unit["query_unit_id"],
            "expected_output_ids": list(query_unit["expected_output_ids"]),
            "excerpt": text,
            "query_term_overlap": overlap,
            "deterministic_locator_relevance": round(score, 6),
            "candidate_not_evidence": True,
            "candidate_decision_required": True,
        }
        proposals.append(
            {**body, "candidate_proposal_digest": canonical_digest(body)}
        )
    return proposals


def compile_captured_originals(
    *,
    plan: Mapping[str, Any],
    shortlist: Mapping[str, Any],
    capture_result: Mapping[str, Any],
) -> dict[str, Any]:
    units = {str(row["query_unit_id"]): row for row in plan["query_units"]}
    selected_by_locator = {
        str(row["locator_digest"]): row for row in shortlist.get("selected") or ()
    }
    capture_source_specs = _compile_original_capture_plan(plan=plan, shortlist=shortlist)["sources"]
    locator_by_route = {
        str(row["route_id"]): selected_by_locator[str(row["locator_digest"])]
        for row in capture_source_specs
    }
    source_objects: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for capture_row in capture_result.get("sources") or ():
        route_id = str(capture_row.get("route_id") or "")
        locator = locator_by_route[route_id]
        unit = units[str(locator["query_unit_id"])]
        receipt: dict[str, Any] = {
            "route_id": route_id,
            "query_unit_id": unit["query_unit_id"],
            "proposition_id": unit["proposition_id"],
            "tier_id": unit["tier_id"],
            "locator_digest": locator["locator_digest"],
            "canonical_url": locator["canonical_url"],
            "capture_status": capture_row.get("status"),
            "capture_failure_code": capture_row.get("failure_code"),
            "source_object_status": "not_compiled",
            "candidate_proposal_count": 0,
        }
        if capture_row.get("status") != "captured":
            receipts.append(receipt)
            continue
        response_ref = str(capture_row["response_capture"]["object_ref"])
        response = _load_capture_object(response_ref)
        date_receipt = adjudicate_publication_date_from_capture(
            response_capture=response,
            research_as_of=str(plan["research_as_of"]),
            provider_date_telemetry=locator.get("provider_date_telemetry"),
        )
        receipt["publication_date_receipt"] = date_receipt
        publication_date = date_receipt.get("selected_publication_date")
        if not publication_date:
            receipt["source_object_status"] = "publication_date_unresolved"
            receipts.append(receipt)
            continue
        registry = dict(locator["source_registry"])
        body_sha256 = str(response.get("body_sha256") or "")
        source_id = "PUBLIC::DELL-EXT::" + canonical_digest(
            {
                "url": response.get("final_url"),
                "body_sha256": body_sha256,
                "publication_date": publication_date,
            }
        )[:20].upper()
        source_spec = {
            "source_id": source_id,
            "case_key": "DELL",
            "speaker_entity": registry["speaker_entity"],
            "speaker_ticker": registry.get("speaker_ticker"),
            "source_class": registry["source_class"],
            "source_role": registry["source_role"],
            "source_type": (
                "PUBLIC_PDF"
                if str(capture_row.get("content_type") or "") == "application/pdf"
                or str(response.get("body_base64") or "").startswith("JVBER")
                else "PUBLIC_WEB"
            ),
            "relationship_directions": sorted(
                set(registry.get("relationship_directions") or ())
                | set(unit.get("relationship_directions") or ())
            ),
            "publication_date": publication_date,
            "research_as_of": plan["research_as_of"],
            "source_url": response["final_url"],
            "title": locator.get("title"),
            "parser_profile": "article_main_html",
            "segment_character_target": 2400,
        }
        try:
            if source_spec["source_type"] == "PUBLIC_PDF":
                source_object = compile_public_pdf_source_object(
                    response_capture=response,
                    source_spec=source_spec,
                    capture_ref=_relative(Path(response_ref)),
                    capture_sha256=str(capture_row["response_capture"]["sha256"]),
                )
            else:
                source_object = compile_public_html_source_object(
                    response_capture=response,
                    source_spec=source_spec,
                    capture_ref=_relative(Path(response_ref)),
                    capture_sha256=str(capture_row["response_capture"]["sha256"]),
                )
        except PublicContextSourceError as exc:
            receipt["source_object_status"] = f"parse_rejected:{exc}"
            receipts.append(receipt)
            continue
        source_objects.append(source_object)
        source_proposals = _candidate_proposals(
            source_object=source_object,
            query_unit=unit,
            candidate_selection_policy=(
                plan.get("candidate_selection_policy")
                if isinstance(plan.get("candidate_selection_policy"), Mapping)
                else None
            ),
        )
        proposals.extend(source_proposals)
        receipt["source_object_status"] = "compiled_candidate_only"
        receipt["source_id"] = source_id
        receipt["source_object_digest"] = source_object["source_object_digest"]
        receipt["candidate_proposal_count"] = len(source_proposals)
        receipt["capture_reused_from_predecessor"] = (
            capture_row.get("capture_reused_from_predecessor") is True
        )
        receipt["predecessor_capture_status"] = capture_row.get(
            "predecessor_capture_status"
        )
        receipts.append(receipt)
    body = {
        "schema_version": "fin_ia_s1_external_original_compilation_result_v1_0",
        "case_key": "DELL",
        "research_as_of": plan["research_as_of"],
        "source_objects": source_objects,
        "candidate_proposals": proposals,
        "route_receipts": receipts,
        "summary": {
            "original_route_count": len(receipts),
            "captured_count": sum(row["capture_status"] == "captured" for row in receipts),
            "source_object_count": len(source_objects),
            "candidate_proposal_count": len(proposals),
            "publication_date_unresolved_count": sum(
                row["source_object_status"] == "publication_date_unresolved"
                for row in receipts
            ),
            "parse_rejected_count": sum(
                str(row["source_object_status"]).startswith("parse_rejected:")
                for row in receipts
            ),
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "candidate_decision_required": True,
            "evidence_promotion_allowed": False,
            "public_information_gap_authorized": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def _predecessor_original_capture_index(
    *,
    predecessor_plan: Mapping[str, Any],
    predecessor_private_result: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    shortlist = predecessor_private_result.get("fetch_shortlist")
    capture_result = predecessor_private_result.get("original_capture_result")
    if not isinstance(shortlist, Mapping) or not isinstance(capture_result, Mapping):
        raise RuntimeError("external_ladder_predecessor_original_capture_missing")
    specs = _compile_original_capture_plan(
        plan=predecessor_plan,
        shortlist=shortlist,
    )["sources"]
    locator_by_route = {
        str(spec["route_id"]): locator
        for spec, locator in zip(specs, shortlist.get("selected") or (), strict=True)
    }
    result: dict[str, dict[str, Any]] = {}
    for row in capture_result.get("sources") or ():
        route_id = str(row.get("route_id") or "")
        locator = locator_by_route.get(route_id)
        if locator is None:
            raise RuntimeError("external_ladder_predecessor_capture_route_unbound")
        result[str(locator["canonical_url"])] = {
            "capture_row": row,
            "locator": locator,
        }
    return result


def execute_original_capture_successor(
    *,
    plan: Mapping[str, Any],
    shortlist: Mapping[str, Any],
    attempt_root: Path,
    predecessor_plan: Mapping[str, Any] | None,
    predecessor_private_result: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    full_plan = _compile_original_capture_plan(plan=plan, shortlist=shortlist)
    selected = list(shortlist.get("selected") or ())
    predecessor_index = (
        _predecessor_original_capture_index(
            predecessor_plan=predecessor_plan,
            predecessor_private_result=predecessor_private_result,
        )
        if predecessor_plan is not None and predecessor_private_result is not None
        else {}
    )
    replay_rows: dict[str, dict[str, Any]] = {}
    live_sources: list[dict[str, Any]] = []
    reuse_receipts: list[dict[str, Any]] = []
    for source_spec, locator in zip(full_plan["sources"], selected, strict=True):
        route_id = str(source_spec["route_id"])
        predecessor = predecessor_index.get(str(locator["canonical_url"]))
        if predecessor is None:
            live_sources.append(source_spec)
            reuse_receipts.append(
                {
                    "route_id": route_id,
                    "canonical_url": locator["canonical_url"],
                    "disposition": "fresh_original_capture_required",
                    "reason": "no_predecessor_capture_for_locator",
                }
            )
            continue
        old_row = dict(predecessor["capture_row"])
        old_status = str(old_row.get("status") or "")
        response_ref = str((old_row.get("response_capture") or {}).get("object_ref") or "")
        response_sha = str((old_row.get("response_capture") or {}).get("sha256") or "")
        reusable = old_status in {"captured", "rejected_final_url"} and bool(response_ref)
        response: dict[str, Any] | None = None
        if reusable:
            response_path = _bound_path(response_ref)
            reusable = _sha256(response_path) == response_sha
            if reusable:
                response = _read_json(response_path)
                final_host = str(urlsplit(str(response.get("final_url") or "")).hostname or "").lower()
                reusable = final_host in source_family_allowed_hosts(
                    locator["source_registry"],
                    observed_host=str(locator["source_domain"]),
                )
                reusable = reusable and 200 <= int(response.get("status_code") or 0) < 300
        if not reusable:
            live_sources.append(source_spec)
            reuse_receipts.append(
                {
                    "route_id": route_id,
                    "canonical_url": locator["canonical_url"],
                    "disposition": "fresh_original_capture_required",
                    "reason": (
                        "predecessor_transport_or_capture_not_reusable"
                        if old_status != "rejected_final_url"
                        else "predecessor_same_source_family_validation_failed"
                    ),
                    "predecessor_status": old_status,
                }
            )
            continue
        replay_row = deepcopy(old_row)
        replay_row.update(
            {
                "route_id": route_id,
                "status": "captured",
                "failure_code": None,
                "capture_reused_from_predecessor": True,
                "predecessor_route_id": old_row.get("route_id"),
                "predecessor_capture_status": old_status,
                "transport_attempts": 0,
            }
        )
        replay_rows[route_id] = replay_row
        reuse_receipts.append(
            {
                "route_id": route_id,
                "canonical_url": locator["canonical_url"],
                "disposition": "immutable_original_capture_reused",
                "predecessor_route_id": old_row.get("route_id"),
                "predecessor_status": old_status,
                "response_capture_ref": response_ref,
                "response_capture_sha256": response_sha,
                "final_url": response.get("final_url") if response else None,
            }
        )

    live_rows: dict[str, dict[str, Any]] = {}
    live_result: dict[str, Any] | None = None
    if live_sources:
        live_plan = {**full_plan, "sources": live_sources}
        live_plan_path = attempt_root / "original_capture_live_plan.json"
        _write_new(live_plan_path, live_plan)
        live_result = capture_plan(
            live_plan,
            output_root=attempt_root / "original_capture",
            attempt_id="original-r2",
        )
        live_rows = {
            str(row["route_id"]): {
                **dict(row),
                "capture_reused_from_predecessor": False,
                "predecessor_capture_status": None,
            }
            for row in live_result.get("sources") or ()
        }
    combined_rows = []
    for spec in full_plan["sources"]:
        route_id = str(spec["route_id"])
        row = replay_rows.get(route_id) or live_rows.get(route_id)
        if row is None:
            raise RuntimeError("external_ladder_successor_capture_route_missing")
        combined_rows.append(row)
    capture_result = {
        "schema_version": "fin_ia_s1_external_original_capture_successor_result_v1_0",
        "status": (
            "external_original_capture_successor_complete"
            if all(row.get("status") == "captured" for row in combined_rows)
            else "external_original_capture_successor_partial"
        ),
        "source_routes_executed": len(combined_rows),
        "predecessor_captures_reused": len(replay_rows),
        "fresh_network_routes": len(live_sources),
        "fresh_network_attempts_lower_bound": int(
            (live_result or {}).get("network_attempts_lower_bound") or 0
        ),
        "fresh_network_attempts_upper_bound": int(
            (live_result or {}).get("network_attempts_upper_bound") or 0
        ),
        "model_calls": 0,
        "sources": combined_rows,
    }
    reuse_body = {
        "schema_version": "fin_ia_s1_external_original_capture_reuse_receipt_v1_0",
        "case_key": "DELL",
        "plan_digest": plan["plan_digest"],
        "receipts": reuse_receipts,
        "summary": {
            "selected_original_count": len(selected),
            "predecessor_capture_reused_count": len(replay_rows),
            "fresh_original_capture_count": len(live_sources),
        },
    }
    reuse_result = {**reuse_body, "receipt_digest": canonical_digest(reuse_body)}
    return capture_result, reuse_result


def build_public_projection(
    *,
    plan: Mapping[str, Any],
    provider_receipts: Sequence[Mapping[str, Any]],
    shortlist: Mapping[str, Any],
    original_result: Mapping[str, Any] | None,
    private_result_ref: str,
    private_result_sha256: str,
    prepared_from_commit: str,
    recorded_at: str,
) -> dict[str, Any]:
    proposition_rows = []
    for proposition_id in sorted(
        {str(row["proposition_id"]) for row in plan["query_units"]}
    ):
        query_receipts = [
            row for row in provider_receipts if row["proposition_id"] == proposition_id
        ]
        selected = [
            row
            for row in shortlist.get("selected") or ()
            if row["proposition_id"] == proposition_id
        ]
        originals = [
            row
            for row in (original_result or {}).get("route_receipts") or ()
            if row["proposition_id"] == proposition_id
        ]
        proposition_rows.append(
            {
                "proposition_id": proposition_id,
                "query_count": len(query_receipts),
                "query_success_count": sum(
                    row["status"]
                    in {
                        "provider_locator_call_completed",
                        "predecessor_locator_bundle_replayed",
                    }
                    for row in query_receipts
                ),
                "replayed_query_count": sum(
                    row["status"] == "predecessor_locator_bundle_replayed"
                    for row in query_receipts
                ),
                "locator_count": sum(int(row["locator_count"]) for row in query_receipts),
                "selected_original_count": len(selected),
                "captured_original_count": sum(
                    row["capture_status"] == "captured" for row in originals
                ),
                "compiled_source_object_count": sum(
                    row["source_object_status"] == "compiled_candidate_only"
                    for row in originals
                ),
                "candidate_proposal_count": sum(
                    int(row["candidate_proposal_count"]) for row in originals
                ),
                "tier_ids_with_selected_original": sorted(
                    {str(row["tier_id"]) for row in selected}
                ),
                "external_route_exhausted": False,
                "public_information_gap_eligible": False,
            }
        )
    body = {
        "schema_version": (
            "fin_ia_s1_dell_external_source_ladder_result_v1_1"
            if plan.get("predecessor_binding")
            else "fin_ia_s1_dell_external_source_ladder_result_v1_0"
        ),
        "status": (
            "dell_external_ladder_successor_executed_candidate_decision_pending"
            if plan.get("predecessor_binding")
            else "dell_external_ladder_executed_candidate_decision_pending"
        ),
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": plan["research_as_of"],
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "provider": {
            "provider_id": "tencent_wsa_searchpro_standard_locator_v1",
            "query_count": len(provider_receipts),
            "successful_query_count": sum(
                row["status"]
                in {
                    "provider_locator_call_completed",
                    "predecessor_locator_bundle_replayed",
                }
                for row in provider_receipts
            ),
            "failed_query_count": sum(
                row["status"]
                not in {
                    "provider_locator_call_completed",
                    "predecessor_locator_bundle_replayed",
                }
                for row in provider_receipts
            ),
            "replayed_query_count": sum(
                row["status"] == "predecessor_locator_bundle_replayed"
                for row in provider_receipts
            ),
            "fresh_provider_query_count": sum(
                row["status"]
                in {"provider_locator_call_completed", "provider_locator_call_failed"}
                for row in provider_receipts
            ),
            "locator_count": sum(int(row["locator_count"]) for row in provider_receipts),
            "provider_call_count": sum(
                int(row["provider_call_count"]) for row in provider_receipts
            ),
            "retry_count": 0,
            "model_call_count": 0,
            "provider_result_is_locator_only": True,
        },
        "shortlist_summary": dict(shortlist.get("summary") or {}),
        "original_summary": dict((original_result or {}).get("summary") or {}),
        "propositions": proposition_rows,
        "private_execution_ref": private_result_ref,
        "private_execution_sha256": private_result_sha256,
        "authority": {
            "candidate_decision_complete": False,
            "evidence_promotion_authorized": False,
            "public_information_gap_authorized": False,
            "evidence_pack_readiness_authorized": False,
            "dynamic_single_unit_authorized": False,
        },
        "known_boundary": (
            "The paid provider supplied locators only. Original captures and compiled "
            "source objects remain candidate material. CandidateDecision, Evidence Gate, "
            "current Pack promotion, S2 recompilation and dynamic research are not yet authorized."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def build_capture_replay_public_projection(
    *,
    predecessor_ref: str,
    predecessor_sha256: str,
    predecessor_result_digest: str,
    original_result: Mapping[str, Any],
    status_changes: Sequence[Mapping[str, Any]],
    private_result_ref: str,
    private_result_sha256: str,
    prepared_from_commit: str,
    recorded_at: str,
) -> dict[str, Any]:
    proposal_counts: dict[str, int] = {}
    for row in original_result.get("candidate_proposals") or ():
        proposition_id = str(row.get("proposition_id") or "")
        proposal_counts[proposition_id] = proposal_counts.get(proposition_id, 0) + 1
    body = {
        "schema_version": "fin_ia_s1_dell_external_capture_replay_result_v1_0",
        "status": "dell_external_capture_replay_complete_candidate_decision_pending",
        "case_key": "DELL",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "predecessor_binding": {
            "private_result_ref": predecessor_ref,
            "private_result_sha256": predecessor_sha256,
            "private_result_digest": predecessor_result_digest,
        },
        "original_summary": deepcopy(dict(original_result.get("summary") or {})),
        "candidate_proposal_count_by_proposition": dict(
            sorted(proposal_counts.items())
        ),
        "changed_route_count": len(status_changes),
        "private_execution_ref": private_result_ref,
        "private_execution_sha256": private_result_sha256,
        "observed_counts": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retry_count": 0,
            "candidate_evidence_promotions": 0,
        },
        "authority": {
            "capture_replay_only": True,
            "candidate_decision_complete": False,
            "evidence_promotion_authorized": False,
            "public_information_gap_authorized": False,
            "evidence_pack_readiness_authorized": False,
            "dynamic_single_unit_authorized": False,
        },
        "known_boundary": (
            "The replay recompiled immutable captured originals under the current "
            "date, article-body and query-facet implementation. Recovered source "
            "objects and proposals remain candidates until CandidateDecision and "
            "Evidence Gate; unresolved routes are not public-information gaps."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def run_capture_replay(
    *,
    attempt_id: str,
    private_root: Path,
    public_output: Path,
    predecessor_private_result_path: Path,
) -> dict[str, Any]:
    _require_clean()
    attempt_root = private_root / attempt_id
    if attempt_root.exists() or public_output.exists():
        raise RuntimeError("dell_external_capture_replay_attempt_or_output_exists")

    predecessor_sha256 = _sha256(predecessor_private_result_path)
    predecessor = _read_json(predecessor_private_result_path)
    _validate_content_digest(
        predecessor,
        "result_digest",
        "dell_external_capture_replay_predecessor_digest_invalid",
    )
    plan_binding = predecessor.get("plan_binding")
    shortlist = predecessor.get("fetch_shortlist")
    capture_result = predecessor.get("original_capture_result")
    prior_compilation = predecessor.get("original_compilation_result")
    if not all(
        isinstance(value, Mapping)
        for value in (plan_binding, shortlist, capture_result, prior_compilation)
    ):
        raise RuntimeError("dell_external_capture_replay_predecessor_shape_invalid")
    plan_path = _bound_path(str(plan_binding.get("ref") or ""))
    if _sha256(plan_path) != str(plan_binding.get("sha256") or ""):
        raise RuntimeError("dell_external_capture_replay_plan_sha_mismatch")
    plan = validate_external_source_ladder_plan(_read_json(plan_path))
    if plan.get("plan_digest") != plan_binding.get("plan_digest"):
        raise RuntimeError("dell_external_capture_replay_plan_digest_mismatch")

    for row in capture_result.get("sources") or ():
        response = row.get("response_capture")
        if not isinstance(response, Mapping):
            continue
        response_path = _bound_path(str(response.get("object_ref") or ""))
        if _sha256(response_path) != str(response.get("sha256") or ""):
            raise RuntimeError("dell_external_capture_replay_capture_sha_mismatch")

    prepared_from_commit = _head()
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    original_result = compile_captured_originals(
        plan=plan,
        shortlist=shortlist,
        capture_result=capture_result,
    )
    old_receipts = {
        str(row.get("route_id") or ""): row
        for row in prior_compilation.get("route_receipts") or ()
    }
    status_changes: list[dict[str, Any]] = []
    for row in original_result.get("route_receipts") or ():
        route_id = str(row.get("route_id") or "")
        old = old_receipts.get(route_id, {})
        old_status = str(old.get("source_object_status") or "")
        new_status = str(row.get("source_object_status") or "")
        old_count = int(old.get("candidate_proposal_count") or 0)
        new_count = int(row.get("candidate_proposal_count") or 0)
        if old_status == new_status and old_count == new_count:
            continue
        status_changes.append(
            {
                "route_id": route_id,
                "proposition_id": row.get("proposition_id"),
                "canonical_url": row.get("canonical_url"),
                "prior_source_object_status": old_status,
                "replay_source_object_status": new_status,
                "prior_candidate_proposal_count": old_count,
                "replay_candidate_proposal_count": new_count,
            }
        )

    attempt_root.mkdir(parents=True, exist_ok=False)
    original_path = attempt_root / "original_compilation_result.json"
    _write_new(original_path, original_result)
    change_path = attempt_root / "route_change_receipts.json"
    _write_new(
        change_path,
        {
            "schema_version": "fin_ia_s1_external_capture_replay_change_receipts_v1_0",
            "status": "capture_replay_route_changes_recorded",
            "changes": status_changes,
        },
    )
    private_body = {
        "schema_version": "fin_ia_s1_dell_external_capture_replay_private_result_v1_0",
        "status": "dell_external_capture_replay_complete",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "predecessor_binding": {
            "private_result_ref": _relative(predecessor_private_result_path),
            "private_result_sha256": predecessor_sha256,
            "private_result_digest": predecessor["result_digest"],
        },
        "plan_binding": deepcopy(dict(plan_binding)),
        "original_compilation_result": original_result,
        "route_change_receipts": status_changes,
        "observed_counts": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retry_count": 0,
            "immutable_capture_rows_replayed": sum(
                isinstance(row.get("response_capture"), Mapping)
                for row in capture_result.get("sources") or ()
            ),
            "candidate_evidence_promotions": 0,
        },
    }
    private_result = {**private_body, "result_digest": canonical_digest(private_body)}
    private_path = attempt_root / "terminal_result.json"
    _write_new(private_path, private_result)
    public_result = build_capture_replay_public_projection(
        predecessor_ref=_relative(predecessor_private_result_path),
        predecessor_sha256=predecessor_sha256,
        predecessor_result_digest=str(predecessor["result_digest"]),
        original_result=original_result,
        status_changes=status_changes,
        private_result_ref=_relative(private_path),
        private_result_sha256=_sha256(private_path),
        prepared_from_commit=prepared_from_commit,
        recorded_at=recorded_at,
    )
    _write_new(public_output, public_result)
    return public_result


def run(
    *,
    attempt_id: str,
    private_root: Path,
    public_output: Path,
    provider_call: ProviderCall = _tencent_provider_call,
    plan_path: Path = PLAN,
    successor_spec_path: Path | None = None,
) -> dict[str, Any]:
    _require_clean()
    predecessor_private_result: dict[str, Any] | None = None
    predecessor_plan: dict[str, Any] | None = None
    successor_spec: dict[str, Any] | None = None
    if successor_spec_path is not None:
        plan, predecessor_private_result, successor_spec = _load_successor_context(
            successor_spec_path
        )
        predecessor_plan = validate_external_source_ladder_plan(
            _read_json(_bound_path(successor_spec["predecessor_binding"]["plan_ref"]))
        )
    else:
        plan = validate_external_source_ladder_plan(_read_json(plan_path))
    attempt_root = private_root / attempt_id
    if attempt_root.exists() or public_output.exists():
        raise RuntimeError("dell_external_source_ladder_attempt_or_output_already_exists")
    prepared_from_commit = _head()
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    effective_plan_path = attempt_root / "effective_plan.json"
    _write_new(effective_plan_path, plan)
    locator_bundles, provider_receipts = execute_locator_queries(
        plan=plan,
        attempt_root=attempt_root,
        provider_call=provider_call,
        predecessor_private_result=predecessor_private_result,
    )
    shortlist = build_external_fetch_shortlist(
        plan=plan,
        locator_bundles=locator_bundles,
    )
    shortlist_path = attempt_root / "fetch_shortlist.json"
    _write_new(shortlist_path, shortlist)
    original_result: dict[str, Any] | None = None
    capture_result: dict[str, Any] | None = None
    capture_reuse_result: dict[str, Any] | None = None
    if shortlist.get("selected"):
        original_plan = _compile_original_capture_plan(plan=plan, shortlist=shortlist)
        original_plan_path = attempt_root / "original_capture_plan.json"
        _write_new(original_plan_path, original_plan)
        if predecessor_private_result is not None:
            capture_result, capture_reuse_result = execute_original_capture_successor(
                plan=plan,
                shortlist=shortlist,
                attempt_root=attempt_root,
                predecessor_plan=predecessor_plan,
                predecessor_private_result=predecessor_private_result,
            )
            _write_new(
                attempt_root / "original_capture_reuse_receipt.json",
                capture_reuse_result,
            )
        else:
            capture_result = capture_plan(
                original_plan,
                output_root=attempt_root / "original_capture",
                attempt_id="original-r1",
            )
        original_result = compile_captured_originals(
            plan=plan,
            shortlist=shortlist,
            capture_result=capture_result,
        )
        original_result_path = attempt_root / "original_compilation_result.json"
        _write_new(original_result_path, original_result)
    private_body = {
        "schema_version": (
            "fin_ia_s1_dell_external_source_ladder_private_result_v1_1"
            if successor_spec is not None
            else "fin_ia_s1_dell_external_source_ladder_private_result_v1_0"
        ),
        "status": "dell_external_source_ladder_exact_once_complete",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "plan_binding": {
            "ref": _relative(effective_plan_path),
            "sha256": _sha256(effective_plan_path),
            "plan_digest": plan["plan_digest"],
        },
        "successor_spec_binding": (
            {
                "ref": _relative(successor_spec_path),
                "sha256": _sha256(successor_spec_path),
                "spec_digest": successor_spec["spec_digest"],
            }
            if successor_spec is not None and successor_spec_path is not None
            else None
        ),
        "predecessor_binding": (
            deepcopy(dict(successor_spec["predecessor_binding"]))
            if successor_spec is not None
            else None
        ),
        "provider_receipts": provider_receipts,
        "fetch_shortlist": shortlist,
        "original_capture_result": capture_result,
        "original_capture_reuse_result": capture_reuse_result,
        "original_compilation_result": original_result,
        "observed_counts": {
            "provider_calls": sum(
                int(row["provider_call_count"]) for row in provider_receipts
            ),
            "replayed_provider_query_results": sum(
                row["status"] == "predecessor_locator_bundle_replayed"
                for row in provider_receipts
            ),
            "provider_retries": 0,
            "model_calls": 0,
            "original_fetch_routes": len(shortlist.get("selected") or ()),
            "predecessor_original_captures_reused": int(
                (capture_reuse_result or {}).get("summary", {}).get(
                    "predecessor_capture_reused_count"
                )
                or 0
            ),
            "fresh_original_capture_routes": int(
                (capture_reuse_result or {}).get("summary", {}).get(
                    "fresh_original_capture_count"
                )
                or len(shortlist.get("selected") or ())
            ),
            "candidate_evidence_promotions": 0,
        },
        "sdk": {
            "package": "tencentcloud-sdk-python",
            "version": importlib.metadata.version("tencentcloud-sdk-python"),
        },
    }
    private_result = {**private_body, "result_digest": canonical_digest(private_body)}
    private_result_path = attempt_root / "terminal_result.json"
    _write_new(private_result_path, private_result)
    public_result = build_public_projection(
        plan=plan,
        provider_receipts=provider_receipts,
        shortlist=shortlist,
        original_result=original_result,
        private_result_ref=_relative(private_result_path),
        private_result_sha256=_sha256(private_result_path),
        prepared_from_commit=prepared_from_commit,
        recorded_at=recorded_at,
    )
    _write_new(public_output, public_result)
    return public_result


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the exact-once DELL external locator and original-source ladder."
    )
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--private-root", default=str(DEFAULT_PRIVATE_ROOT))
    parser.add_argument("--plan", default=str(PLAN))
    parser.add_argument("--successor-spec")
    parser.add_argument("--capture-replay-predecessor")
    parser.add_argument("--public-output")
    args = parser.parse_args(argv)
    if args.successor_spec and args.capture_replay_predecessor:
        raise RuntimeError("external_ladder_live_and_capture_replay_are_mutually_exclusive")
    successor_spec_path = _resolve(args.successor_spec) if args.successor_spec else None
    public_output = (
        _resolve(args.public_output)
        if args.public_output
        else DEFAULT_PUBLIC_CAPTURE_REPLAY.resolve()
        if args.capture_replay_predecessor
        else DEFAULT_PUBLIC_SUCCESSOR.resolve()
        if successor_spec_path is not None
        else DEFAULT_PUBLIC.resolve()
    )
    if args.capture_replay_predecessor:
        result = run_capture_replay(
            attempt_id=args.attempt_id,
            private_root=_resolve(args.private_root),
            public_output=public_output,
            predecessor_private_result_path=_resolve(
                args.capture_replay_predecessor
            ),
        )
    else:
        result = run(
            attempt_id=args.attempt_id,
            private_root=_resolve(args.private_root),
            public_output=public_output,
            plan_path=_resolve(args.plan),
            successor_spec_path=successor_spec_path,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
