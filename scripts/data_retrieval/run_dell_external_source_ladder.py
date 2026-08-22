from __future__ import annotations

import argparse
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
    compile_safe_provider_request,
    normalize_tencent_search_response,
    validate_external_source_ladder_plan,
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
_STOPWORDS = {
    "and",
    "dell",
    "for",
    "from",
    "official",
    "server",
    "servers",
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    locator_bundles: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    timeout = int(plan["execution_budget"]["provider_timeout_seconds"])
    secret_values = [
        os.environ.get("TENCENTCLOUD_SECRET_ID", ""),
        os.environ.get("TENCENTCLOUD_SECRET_KEY", ""),
    ]
    for unit in plan["query_units"]:
        unit_id = str(unit["query_unit_id"])
        unit_root = attempt_root / "provider" / _safe_name(unit_id)
        safe_request = compile_safe_provider_request(unit)
        request_path = unit_root / "safe_request.json"
        _write_new(request_path, safe_request)
        started = time.monotonic()
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
            raw_path = unit_root / "raw_response.json"
            _write_new(raw_path, raw_capture)
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
            raw_path = unit_root / "provider_failure.json"
            _write_new(raw_path, failure_capture)
            bundle = _empty_bundle(
                query_unit_id=unit_id,
                safe_request_digest=str(safe_request["request_digest"]),
                failure_code=failure_code,
            )
            bundle_path = unit_root / "locator_bundle.json"
            _write_new(bundle_path, bundle)
            status = "provider_locator_call_failed"
        locator_bundles.append(bundle)
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
                "locator_bundle_ref": _relative(bundle_path),
                "locator_bundle_sha256": _sha256(bundle_path),
                "locator_count": len(bundle.get("locators") or ()),
                "provider_call_count": 1,
                "retry_count": 0,
                "model_call_count": 0,
            }
        )
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
        sources.append(
            {
                "route_id": f"DELL_EXT_ORIGINAL_{index:03d}_{canonical_digest(url)[:10].upper()}",
                "case_key": "DELL",
                "url": url,
                "allowed_hosts": [host],
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


def _candidate_proposals(
    *,
    source_object: Mapping[str, Any],
    query_unit: Mapping[str, Any],
    limit: int = 2,
) -> list[dict[str, Any]]:
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
        )
        proposals.extend(source_proposals)
        receipt["source_object_status"] = "compiled_candidate_only"
        receipt["source_id"] = source_id
        receipt["source_object_digest"] = source_object["source_object_digest"]
        receipt["candidate_proposal_count"] = len(source_proposals)
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
                    row["status"] == "provider_locator_call_completed"
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
        "schema_version": "fin_ia_s1_dell_external_source_ladder_result_v1_0",
        "status": "dell_external_ladder_executed_candidate_decision_pending",
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
                row["status"] == "provider_locator_call_completed"
                for row in provider_receipts
            ),
            "failed_query_count": sum(
                row["status"] != "provider_locator_call_completed"
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


def run(
    *,
    attempt_id: str,
    private_root: Path,
    public_output: Path,
    provider_call: ProviderCall = _tencent_provider_call,
) -> dict[str, Any]:
    _require_clean()
    plan = validate_external_source_ladder_plan(_read_json(PLAN))
    attempt_root = private_root / attempt_id
    if attempt_root.exists() or public_output.exists():
        raise RuntimeError("dell_external_source_ladder_attempt_or_output_already_exists")
    prepared_from_commit = _head()
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    locator_bundles, provider_receipts = execute_locator_queries(
        plan=plan,
        attempt_root=attempt_root,
        provider_call=provider_call,
    )
    shortlist = build_external_fetch_shortlist(
        plan=plan,
        locator_bundles=locator_bundles,
    )
    shortlist_path = attempt_root / "fetch_shortlist.json"
    _write_new(shortlist_path, shortlist)
    original_result: dict[str, Any] | None = None
    capture_result: dict[str, Any] | None = None
    if shortlist.get("selected"):
        original_plan = _compile_original_capture_plan(plan=plan, shortlist=shortlist)
        original_plan_path = attempt_root / "original_capture_plan.json"
        _write_new(original_plan_path, original_plan)
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
        "schema_version": "fin_ia_s1_dell_external_source_ladder_private_result_v1_0",
        "status": "dell_external_source_ladder_exact_once_complete",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "plan_binding": {
            "ref": _relative(PLAN),
            "sha256": _sha256(PLAN),
            "plan_digest": plan["plan_digest"],
        },
        "provider_receipts": provider_receipts,
        "fetch_shortlist": shortlist,
        "original_capture_result": capture_result,
        "original_compilation_result": original_result,
        "observed_counts": {
            "provider_calls": sum(
                int(row["provider_call_count"]) for row in provider_receipts
            ),
            "provider_retries": 0,
            "model_calls": 0,
            "original_fetch_routes": len(shortlist.get("selected") or ()),
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
    parser.add_argument("--public-output", default=str(DEFAULT_PUBLIC))
    args = parser.parse_args(argv)
    result = run(
        attempt_id=args.attempt_id,
        private_root=_resolve(args.private_root),
        public_output=_resolve(args.public_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
