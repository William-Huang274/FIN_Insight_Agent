from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.financial_research_held_out_current_source_acquisition import (
    RUN_SCOPE,
    normalized_sha256,
)
from sec_agent.official_source_attempt_program import (
    CaptureFirstOfficialSourceClient,
    SourceTransport,
    parse_source_document,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_asml_current_exhibit_successor_policy_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_asml_current_exhibit_successor_admission_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_asml_current_exhibit_successor_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.asml_same_accession_current_exhibit_successor:v1"
RAW_NAMESPACE = "fin-0.1.3/s1-asml-current-exhibit-successor/raw"
PARSED_NAMESPACE = "fin-0.1.3/s1-asml-current-exhibit-successor/parsed"


class ASMLExhibitSuccessorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ASMLExhibitSuccessorError("asml_exhibit_json_object_required")
    return value


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_asml_exhibit_successor_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(path)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("source_case_key") != "ASML"
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_policy_identity_invalid")
    binding = dict(policy.get("immutable_source_result") or {})
    source_path = root / str(binding.get("path") or "")
    if (
        not source_path.is_file()
        or normalized_sha256(source_path) != str(binding.get("normalized_sha256") or "")
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_source_result_binding_invalid")
    source_result = _read_json(source_path)
    rows = [row for row in source_result.get("source_results") or [] if row.get("case_key") == "ASML"]
    if (
        len(rows) != 1
        or rows[0].get("status") != "captured_parsed_current_markers_pass"
        or rows[0].get("source", {}).get("form_type") != "6-K"
        or int(rows[0].get("source", {}).get("parsed_text_chars") or 0) >= int(policy["thin_primary_char_ceiling"])
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_thin_primary_precondition_invalid")
    budgets = dict(policy.get("budgets") or {})
    if (
        int(budgets.get("network_call_ceiling") or 0) != 3
        or int(budgets.get("candidate_document_ceiling") or 0) != 2
        or int(budgets.get("retry_ceiling", -1)) != 0
        or any(int(budgets.get(name, -1)) != 0 for name in ("model_calls", "provider_calls", "embedding_calls", "rerank_calls"))
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_budget_invalid")
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("accession_must_derive_from_bound_capture") is not True
        or hard.get("final_exhibit_url_seeded") is not False
        or hard.get("broad_web_search_used") is not False
        or hard.get("captured_document_is_evidence") is not False
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_boundary_invalid")
    return policy


def derive_asml_accession_index(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, str]:
    root = Path(repo_root).resolve()
    source_path = root / str(policy["immutable_source_result"]["path"])
    source_result = _read_json(source_path)
    row = next(row for row in source_result["source_results"] if row["case_key"] == "ASML")
    source = dict(row["source"])
    accession = str(source["accession_number"])
    accession_compact = re.sub(r"[^0-9]", "", accession)
    selected = urlparse(str(source["selected_url"]))
    selected_path = selected.path
    path_match = re.fullmatch(
        r"(?P<prefix>/Archives/edgar/data/(?P<cik>[0-9]+)/(?P<accession>[0-9]+)/)(?P<document>[^/]+)",
        selected_path,
    )
    if (
        selected.scheme != "https"
        or (selected.hostname or "").lower() != "www.sec.gov"
        or path_match is None
        or path_match.group("accession") != accession_compact
        or path_match.group("document") != str(source["primary_document"])
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_source_lineage_invalid")
    expected_prefix = path_match.group("prefix")
    return {
        "accession_number": accession,
        "accession_compact": accession_compact,
        "primary_document": str(source["primary_document"]),
        "index_url": f"https://www.sec.gov{expected_prefix}index.json",
        "accession_base_url": f"https://www.sec.gov{expected_prefix}",
        "source_result_digest": str(source_result["result_digest"]),
        "source_capture_digest": str(source["response_capture_digest"]),
    }


def select_exhibit_candidates(
    payload: Mapping[str, Any], *, accession_base_url: str, primary_document: str, ceiling: int
) -> list[dict[str, Any]]:
    directory = payload.get("directory")
    items = directory.get("item") if isinstance(directory, Mapping) else None
    if not isinstance(items, list):
        raise ASMLExhibitSuccessorError("asml_exhibit_index_shape_invalid")
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip()
        lowered = name.lower()
        if (
            not name
            or lowered == primary_document.lower()
            or not lowered.endswith((".htm", ".html", ".pdf"))
            or any(token in lowered for token in ("-index", "index.htm", ".xsd", "cal.xml", "def.xml", "lab.xml", "pre.xml"))
        ):
            continue
        exhibit_match = re.search(r"(?:ex(?:hibit)?[-_.]?)?99[-_.]?([1-4])", lowered)
        semantic = any(token in lowered for token in ("result", "release", "financial", "press", "quarter", "q2", "presentation"))
        if not exhibit_match and not semantic:
            continue
        exhibit_number = int(exhibit_match.group(1)) if exhibit_match else 9
        score = 100 - exhibit_number * 10 if exhibit_match else 20
        score += sum(
            weight
            for token, weight in (
                ("result", 12),
                ("release", 10),
                ("financial", 8),
                ("press", 6),
                ("q2", 5),
                ("presentation", 2),
            )
            if token in lowered
        )
        candidates.append(
            {
                "name": name,
                "url": urljoin(accession_base_url, name),
                "size": int(str(item.get("size") or "0") or 0),
                "type": str(item.get("type") or ""),
                "score": score,
                "exhibit_number": exhibit_number,
            }
        )
    candidates.sort(key=lambda row: (-int(row["score"]), int(row["exhibit_number"]), str(row["name"])))
    return candidates[:ceiling]


_DETAIL_FACETS: dict[str, tuple[str, ...]] = {
    "bookings_or_backlog": ("net bookings", "bookings", "backlog"),
    "euv_or_high_na": ("euv", "high-na", "high na"),
    "systems_or_units": ("systems sold", "systems recognized", "units sold"),
    "installed_base": ("installed base", "installed-base"),
    "gross_margin": ("gross margin",),
    "cash_or_working_capital": ("cash flow", "cash flows", "inventory", "customer advances"),
    "outlook": ("outlook", "expects 2026", "guidance"),
}


def evaluate_detailed_results(text: str, *, minimum_facet_hits: int) -> dict[str, Any]:
    lowered = text.lower()
    identity = "asml" in lowered
    period = any(token in lowered for token in ("q2 2026", "second quarter 2026", "quarter ended june"))
    facets = {
        facet: [token for token in tokens if token in lowered]
        for facet, tokens in _DETAIL_FACETS.items()
    }
    hit_facets = [facet for facet, tokens in facets.items() if tokens]
    passed = identity and period and len(hit_facets) >= minimum_facet_hits
    body = {
        "identity_pass": identity,
        "period_pass": period,
        "facet_hits": hit_facets,
        "facet_misses": [facet for facet in _DETAIL_FACETS if facet not in hit_facets],
        "facet_hit_count": len(hit_facets),
        "minimum_facet_hits": minimum_facet_hits,
        "detailed_results_pass": passed,
        "text_chars": len(text),
        "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return {**body, "assessment_digest": canonical_digest(body)}


def issue_asml_exhibit_admission(
    *,
    policy: Mapping[str, Any],
    implementation_commit: str,
    implementation_file_sha256: str,
    policy_file_sha256: str,
    issued_at: str,
    expires_at: str,
    nonce: str,
) -> dict[str, Any]:
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "policy_digest": canonical_digest(policy),
        "implementation_commit": implementation_commit,
        "implementation_file_sha256": implementation_file_sha256,
        "policy_file_sha256": policy_file_sha256,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "maximum_executions": 1,
        "network_call_ceiling": 3,
        "candidate_document_ceiling": 2,
        "retry_ceiling": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotion_calls": 0,
    }
    digest = canonical_digest(body)
    return {
        **body,
        "admission_id": f"fin013_s1_asml_exhibit_admission_{digest[:20]}",
        "run_id": f"fin013_s1_asml_exhibit_run_{digest[20:40]}",
        "attempt_id": f"fin013_s1_asml_exhibit_attempt_{digest[40:60]}",
        "admission_digest": digest,
    }


def validate_asml_exhibit_admission(
    admission: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    implementation_path: str | Path,
    policy_path: str | Path,
    observed_at: str,
) -> None:
    body = dict(admission)
    digest = str(body.pop("admission_digest", ""))
    admission_id = str(body.pop("admission_id", ""))
    run_id = str(body.pop("run_id", ""))
    attempt_id = str(body.pop("attempt_id", ""))
    expected = canonical_digest(body)
    if (
        digest != expected
        or admission_id != f"fin013_s1_asml_exhibit_admission_{expected[:20]}"
        or run_id != f"fin013_s1_asml_exhibit_run_{expected[20:40]}"
        or attempt_id != f"fin013_s1_asml_exhibit_attempt_{expected[40:60]}"
        or body.get("schema_version") != ADMISSION_SCHEMA
        or body.get("policy_digest") != canonical_digest(policy)
        or int(body.get("network_call_ceiling") or 0) != 3
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_admission_invalid")
    if (
        normalized_sha256(implementation_path) != str(body.get("implementation_file_sha256") or "")
        or normalized_sha256(policy_path) != str(body.get("policy_file_sha256") or "")
    ):
        raise ASMLExhibitSuccessorError("asml_exhibit_admission_binding_invalid")
    observed = _parse_time(observed_at)
    if not _parse_time(str(body["issued_at"])) <= observed <= _parse_time(str(body["expires_at"])):
        raise ASMLExhibitSuccessorError("asml_exhibit_admission_expired")


def _persist_parsed(
    *, store: FileCanonicalObjectStore, lineage: Mapping[str, str], candidate: Mapping[str, Any], response_url: str, parsed: Mapping[str, Any]
) -> dict[str, Any]:
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_asml_current_exhibit_parsed_capture_v1_0",
        "case_key": "ASML",
        "subject_entity_key": "ASML_HOLDING",
        "reporting_currency": "EUR",
        "accession_number": lineage["accession_number"],
        "source_url": response_url,
        "document_name": str(candidate["name"]),
        "parser_adapter": str(parsed["adapter"]),
        "parser_text_digest": str(parsed["text_sha256"]),
        "text": str(parsed["text"]),
    }
    ref = store.put_json(payload, namespace=PARSED_NAMESPACE, artifact_type="asml_current_exhibit_parsed_source")
    if canonical_digest(store.get_json(ref["object_key"], expected_digest=ref["digest"])) != ref["digest"]:
        raise ASMLExhibitSuccessorError("asml_exhibit_parsed_readback_failed")
    return ref


def execute_asml_exhibit_successor(
    *,
    policy: Mapping[str, Any],
    admission: Mapping[str, Any],
    repo_root: str | Path,
    runtime_root: str | Path,
    ledger: SharedAdmissionConsumptionLedger,
    transport: SourceTransport,
    observed_at: str,
) -> dict[str, Any]:
    runtime_path = Path(runtime_root).resolve()
    ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=CONTRACT_REF,
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(runtime_path),
        reserved_at=observed_at,
    )
    lineage = derive_asml_accession_index(policy=policy, repo_root=repo_root)
    store = FileCanonicalObjectStore(runtime_path / "objects")
    client = CaptureFirstOfficialSourceClient(store=store, transport=transport, namespace=RAW_NAMESPACE)
    allowed_hosts = {"www.sec.gov"}
    attempts: list[dict[str, Any]] = []
    response, attempt = client.fetch(
        case_key="ASML",
        route_id="ASML:same_accession_index",
        url=lineage["index_url"],
        allowed_hosts=allowed_hosts,
        timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
        byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
    )
    attempts.append(attempt)
    candidates: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    failure_code = ""
    if response is None or attempt["status"] != "captured":
        failure_code = str(attempt.get("failure_code") or "asml_exhibit_index_unavailable")
    else:
        try:
            candidates = select_exhibit_candidates(
                json.loads(response.body.decode("utf-8")),
                accession_base_url=lineage["accession_base_url"],
                primary_document=lineage["primary_document"],
                ceiling=int(policy["budgets"]["candidate_document_ceiling"]),
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            failure_code = f"asml_exhibit_index_json_invalid:{type(exc).__name__}"
        except ASMLExhibitSuccessorError as exc:
            failure_code = exc.code
    document_results: list[dict[str, Any]] = []
    for ordinal, candidate in enumerate(candidates, start=1):
        document_response, document_attempt = client.fetch(
            case_key="ASML",
            route_id=f"ASML:exhibit_candidate_{ordinal}",
            url=str(candidate["url"]),
            allowed_hosts=allowed_hosts,
            timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
            byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
        )
        attempts.append(document_attempt)
        document_result: dict[str, Any] = {"candidate": candidate, "attempt": document_attempt}
        if document_response is not None and document_attempt["status"] == "captured":
            parsed = parse_source_document(document_response)
            assessment = evaluate_detailed_results(
                str(parsed.get("text") or ""),
                minimum_facet_hits=int(policy["minimum_detailed_facet_hits"]),
            )
            parsed_ref = _persist_parsed(
                store=store,
                lineage=lineage,
                candidate=candidate,
                response_url=document_response.final_url,
                parsed=parsed,
            )
            document_result.update(
                {
                    "parser_adapter": parsed["adapter"],
                    "parsed_text_chars": len(str(parsed.get("text") or "")),
                    "parsed_text_digest": parsed["text_sha256"],
                    "parsed_capture_ref": parsed_ref["object_key"],
                    "parsed_capture_digest": parsed_ref["digest"],
                    "response_capture_ref": document_attempt["response_capture"]["object_key"],
                    "response_capture_digest": document_attempt["response_capture"]["digest"],
                    "assessment": assessment,
                }
            )
            if assessment["detailed_results_pass"]:
                selected = document_result
        document_results.append(document_result)
        if selected is not None:
            break
    if selected is None and not failure_code:
        failure_code = "asml_exhibit_detailed_results_not_found_within_budget"

    success = selected is not None
    counts = {
        "index_candidates": len(candidates),
        "documents_attempted": len(document_results),
        "detailed_documents_acquired": int(success),
        "network_calls": client.network_calls,
        "retry_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotion_calls": 0,
    }
    if counts["network_calls"] > 3:
        raise ASMLExhibitSuccessorError("asml_exhibit_network_budget_exceeded")
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "completed_detailed_exhibit_acquired" if success else "completed_with_attempt_backed_detail_gap",
        "policy_digest": canonical_digest(policy),
        "admission_digest": str(admission["admission_digest"]),
        "run_id": str(admission["run_id"]),
        "attempt_id": str(admission["attempt_id"]),
        "observed_at": observed_at,
        "bound_source_lineage": lineage,
        "index_attempt": attempt,
        "candidate_inventory": candidates,
        "document_results": document_results,
        "selected_detailed_source": selected,
        "failure_code": failure_code,
        "capture_refs": client.capture_refs,
        "observed_counts": counts,
        "stage_acceptance": {
            "asml_detailed_current_source_capture": success,
            "three_case_table_preserving_reparse": False,
            "held_out_product_generalization": False,
            "sparse_dense_rebuild_admitted": False,
            "external_residual_supplement_admitted": False,
            "model_research_admitted": False,
        },
        "known_boundary": "This same-accession source successor does not retry the three-case live, promote Evidence, build indexes, use broad web search or call a model.",
    }
    output = {**body, "result_digest": canonical_digest(body)}
    ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status="success" if success else "completed_with_gaps",
        terminal_phase="asml_same_accession_current_exhibit_terminal",
        terminal_code="detailed_exhibit_captured" if success else failure_code,
        terminal_result_digest=output["result_digest"],
        finalized_at=observed_at,
    )
    return output


def _retained_capture_inventory(runtime_path: Path) -> tuple[list[dict[str, Any]], int]:
    object_root = runtime_path / "objects"
    refs: list[dict[str, Any]] = []
    request_count = 0
    if not object_root.is_dir():
        return refs, request_count
    for path in sorted(object_root.rglob("*.json")):
        data = path.read_bytes()
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {}
        request_count += int(isinstance(payload, dict) and payload.get("capture_kind") == "source_request")
        refs.append({"object_key": path.relative_to(object_root).as_posix(), "digest": hashlib.sha256(data).hexdigest(), "byte_size": len(data)})
    return refs, request_count


def execute_asml_exhibit_successor_guarded(**kwargs: Any) -> dict[str, Any]:
    runtime_path = Path(kwargs["runtime_root"]).resolve()
    admission = kwargs["admission"]
    policy = kwargs["policy"]
    ledger = kwargs["ledger"]
    observed_at = str(kwargs["observed_at"])
    try:
        return execute_asml_exhibit_successor(**kwargs)
    except Exception as exc:
        try:
            receipt = ledger.read(str(admission["admission_digest"]))
        except Exception:
            raise exc
        if receipt.state != "reserved":
            raise exc
        refs, request_count = _retained_capture_inventory(runtime_path)
        code = str(getattr(exc, "code", "") or f"asml_exhibit_unhandled_{type(exc).__name__.lower()}")
        finalized_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        body = {
            "schema_version": RESULT_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "run_scope": RUN_SCOPE,
            "status": "terminal_failed",
            "policy_digest": canonical_digest(policy),
            "admission_digest": str(admission["admission_digest"]),
            "run_id": str(admission["run_id"]),
            "attempt_id": str(admission["attempt_id"]),
            "observed_at": observed_at,
            "finalized_at": finalized_at,
            "bound_source_lineage": {},
            "index_attempt": None,
            "candidate_inventory": [],
            "document_results": [],
            "selected_detailed_source": None,
            "failure_code": code,
            "capture_refs": refs,
            "observed_counts": {
                "index_candidates": 0,
                "documents_attempted": 0,
                "detailed_documents_acquired": 0,
                "network_calls": request_count,
                "retry_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "embedding_calls": 0,
                "rerank_calls": 0,
                "evidence_promotion_calls": 0,
            },
            "failure": {"phase": "asml_same_accession_current_exhibit_runtime", "code": code, "raw_captures_retained": bool(refs)},
            "stage_acceptance": {
                "asml_detailed_current_source_capture": False,
                "three_case_table_preserving_reparse": False,
                "held_out_product_generalization": False,
                "sparse_dense_rebuild_admitted": False,
                "external_residual_supplement_admitted": False,
                "model_research_admitted": False,
            },
            "known_boundary": "Consumed failure is terminal; retained captures are audit-only and no automatic retry is authorized.",
        }
        output = {**body, "result_digest": canonical_digest(body)}
        ledger.finalize(
            admission_digest=str(admission["admission_digest"]),
            run_id=str(admission["run_id"]),
            attempt_id=str(admission["attempt_id"]),
            terminal_status="failed",
            terminal_phase=str(output["failure"]["phase"]),
            terminal_code=code,
            terminal_result_digest=output["result_digest"],
            finalized_at=finalized_at,
        )
        return output


__all__ = [
    "ADMISSION_SCHEMA",
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "ASMLExhibitSuccessorError",
    "derive_asml_accession_index",
    "evaluate_detailed_results",
    "execute_asml_exhibit_successor",
    "execute_asml_exhibit_successor_guarded",
    "issue_asml_exhibit_admission",
    "load_asml_exhibit_successor_policy",
    "select_exhibit_candidates",
    "validate_asml_exhibit_admission",
]
