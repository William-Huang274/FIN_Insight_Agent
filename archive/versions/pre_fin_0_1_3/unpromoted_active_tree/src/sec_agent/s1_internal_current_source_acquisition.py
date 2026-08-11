from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from lxml import html

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import (
    CaptureFirstOfficialSourceClient,
    SourceTransport,
    parse_source_document,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


RUN_SCOPE = "S1_INTERNAL_CURRENT_OFFICIAL_SOURCE_ACQUISITION"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_current_source_acquisition_policy_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_internal_current_source_acquisition_admission_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_current_source_acquisition_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.internal_current_official_source_acquisition:v1"
PARSED_NAMESPACE = "fin-0.1.3/s1-internal-current-source-acquisition/parsed"


class S1InternalSourceAcquisitionError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_json_object_required"
        )
    return value


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_internal_source_acquisition_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_policy_identity_invalid"
        )
    for stem in ("qrels_review", "benchmark_evidence_pack"):
        ref = str(policy.get("immutable_inputs", {}).get(f"{stem}_ref") or "")
        supplied = str(
            policy.get("immutable_inputs", {}).get(f"{stem}_sha256") or ""
        )
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalSourceAcquisitionError(
                f"internal_source_acquisition_binding_invalid:{stem}"
            )
    qrels = _read_json(root / str(policy["immutable_inputs"]["qrels_review_ref"]))
    if (
        int(qrels.get("strict_current_target_in_pool_count") or 0) != 10
        or int(qrels.get("strict_current_target_absent_count") or 0) != 8
        or qrels.get("gate_decision", {}).get("BGE_fusion_rerank_admitted")
        is not False
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_qrels_state_invalid"
        )
    pack = _read_json(
        root / str(policy["immutable_inputs"]["benchmark_evidence_pack_ref"])
    )
    source_ids = {
        str(item.get("source_id") or "")
        for item in pack.get("source_registry") or []
    }
    targets = list(policy.get("acquisition_targets") or [])
    if len(targets) != 3:
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_target_count_invalid"
        )
    for target in targets:
        if any(
            str(item) not in source_ids
            for item in target.get("expected_source_refs") or []
        ):
            raise S1InternalSourceAcquisitionError(
                "internal_source_acquisition_expected_source_ref_invalid"
            )
        submission_url = str(target.get("submission_url") or "")
        parsed = urlparse(submission_url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() != "data.sec.gov"
            or not target.get("marker_groups")
        ):
            raise S1InternalSourceAcquisitionError(
                "internal_source_acquisition_target_shape_invalid"
            )
    budgets = dict(policy.get("budgets") or {})
    if (
        int(budgets.get("network_call_ceiling") or 0) != 8
        or int(budgets.get("retry_ceiling", -1)) != 0
        or int(budgets.get("model_calls", -1)) != 0
        or int(budgets.get("provider_calls", -1)) != 0
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_budget_invalid"
        )
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("benchmark_exact_url_may_seed_discovery") is not False
        or hard.get("candidate_may_be_promoted_to_evidence") is not False
        or hard.get("external_product_coverage_closed") is not False
        or any(
            int(hard.get(name, -1)) != 0
            for name in (
                "model",
                "provider",
                "embedding",
                "rerank",
                "evidence_promotion",
            )
        )
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_boundary_invalid"
        )
    return policy


def issue_internal_source_acquisition_admission(
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
        "implementation_commit": str(implementation_commit),
        "implementation_file_sha256": str(implementation_file_sha256),
        "policy_file_sha256": str(policy_file_sha256),
        "issued_at": str(issued_at),
        "expires_at": str(expires_at),
        "nonce": str(nonce),
        "maximum_executions": 1,
        "network_call_ceiling": int(policy["budgets"]["network_call_ceiling"]),
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
        "admission_id": f"fin013_s1_internal_source_admission_{digest[:20]}",
        "run_id": f"fin013_s1_internal_source_run_{digest[20:40]}",
        "attempt_id": f"fin013_s1_internal_source_attempt_{digest[40:60]}",
        "admission_digest": digest,
    }


def validate_internal_source_acquisition_admission(
    admission: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    implementation_path: str | Path,
    policy_path: str | Path,
    observed_at: str,
) -> dict[str, Any]:
    body = dict(admission)
    supplied = str(body.pop("admission_digest", ""))
    admission_id = str(body.pop("admission_id", ""))
    run_id = str(body.pop("run_id", ""))
    attempt_id = str(body.pop("attempt_id", ""))
    expected = canonical_digest(body)
    if (
        supplied != expected
        or admission_id != f"fin013_s1_internal_source_admission_{expected[:20]}"
        or run_id != f"fin013_s1_internal_source_run_{expected[20:40]}"
        or attempt_id
        != f"fin013_s1_internal_source_attempt_{expected[40:60]}"
        or body.get("schema_version") != ADMISSION_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or body.get("run_scope") != RUN_SCOPE
        or body.get("policy_digest") != canonical_digest(policy)
        or int(body.get("maximum_executions") or 0) != 1
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_admission_invalid"
        )
    if _normalized_sha256(Path(implementation_path)) != str(
        body.get("implementation_file_sha256") or ""
    ) or _normalized_sha256(Path(policy_path)) != str(
        body.get("policy_file_sha256") or ""
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_admission_file_binding_invalid"
        )
    observed = _parse_time(observed_at)
    if not _parse_time(str(body["issued_at"])) <= observed <= _parse_time(
        str(body["expires_at"])
    ):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_admission_expired"
        )
    return dict(admission)


def _submission_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    recent = dict((payload.get("filings") or {}).get("recent") or {})
    required = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
    if any(not isinstance(recent.get(name), list) for name in required):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_submissions_shape_invalid"
        )
    count = len(recent["accessionNumber"])
    if any(len(recent[name]) != count for name in required):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_submissions_length_invalid"
        )
    items = recent.get("items") if isinstance(recent.get("items"), list) else [""] * count
    if len(items) != count:
        items = [""] * count
    return [
        {
            "accession_number": str(recent["accessionNumber"][index]),
            "filing_date": str(recent["filingDate"][index]),
            "report_date": str(recent["reportDate"][index]),
            "form_type": str(recent["form"][index]).upper(),
            "primary_document": str(recent["primaryDocument"][index]),
            "items": str(items[index]),
        }
        for index in range(count)
    ]


def select_target_submission(
    payload: Mapping[str, Any], *, target: Mapping[str, Any]
) -> dict[str, Any]:
    form_type = str(target["form_type"]).upper()
    start = str(target.get("filing_date_not_before") or "")
    end = str(target.get("filing_date_not_after") or target["as_of_date"])
    report_date = str(target.get("report_date") or "")
    required_items = [str(item) for item in target.get("filing_items_any") or []]
    candidates = []
    for row in _submission_rows(payload):
        if row["form_type"] != form_type:
            continue
        if start and row["filing_date"] < start:
            continue
        if end and row["filing_date"] > end:
            continue
        if report_date and row["report_date"] != report_date:
            continue
        if required_items and not any(item in row["items"] for item in required_items):
            continue
        candidates.append(row)
    if not candidates:
        raise S1InternalSourceAcquisitionError(
            f"internal_source_acquisition_submission_not_found:{target['target_id']}"
        )
    candidates.sort(
        key=lambda row: (
            row["filing_date"],
            row["report_date"],
            row["accession_number"],
        ),
        reverse=True,
    )
    selected = dict(candidates[0])
    cik = str(int(str(target["cik"])))
    accession = selected["accession_number"].replace("-", "")
    selected["primary_url"] = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
        f"{selected['primary_document']}"
    )
    selected["candidate_count"] = len(candidates)
    return selected


def _markers_pass(text: str, groups: list[list[str]]) -> tuple[bool, list[list[str]]]:
    lowered = text.lower()
    missing = [
        [str(item) for item in group]
        for group in groups
        if not any(str(item).lower() in lowered for item in group)
    ]
    return not missing, missing


def select_same_accession_exhibit(
    *, body: bytes, primary_url: str, allowed_hosts: set[str]
) -> str:
    try:
        tree = html.fromstring(body, base_url=primary_url)
    except Exception:
        return ""
    primary = urlparse(primary_url)
    base_dir = primary.path.rsplit("/", 1)[0] + "/"
    candidates: list[tuple[int, str]] = []
    for anchor in tree.xpath("//a[@href]"):
        url = urljoin(primary_url, str(anchor.get("href") or ""))
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() not in allowed_hosts
            or not parsed.path.startswith(base_dir)
            or url == primary_url
            or not parsed.path.lower().endswith((".htm", ".html", ".pdf"))
        ):
            continue
        label = " ".join(anchor.text_content().split()).lower()
        haystack = f"{parsed.path.lower()} {label}"
        score = sum(
            weight
            for token, weight in (
                ("ex99", 8),
                ("99.1", 8),
                ("earnings", 6),
                ("results", 5),
                ("release", 4),
                ("financial", 3),
                ("press", 2),
            )
            if token in haystack
        )
        if score:
            candidates.append((score, url))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def _persist_parsed_text(
    *,
    store: FileCanonicalObjectStore,
    target: Mapping[str, Any],
    selected: Mapping[str, Any],
    final_url: str,
    parsed: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_internal_parsed_source_capture_v1_0",
        "target_id": str(target["target_id"]),
        "ticker": str(target["ticker"]),
        "form_type": str(target["form_type"]),
        "reporting_fiscal_year": int(target["reporting_fiscal_year"]),
        "filing_date": str(selected["filing_date"]),
        "report_date": str(selected["report_date"]),
        "accession_number": str(selected["accession_number"]),
        "source_url": final_url,
        "parser_adapter": str(parsed["adapter"]),
        "parser_text_digest": str(parsed["text_sha256"]),
        "text": str(parsed["text"]),
    }
    ref = store.put_json(
        payload,
        namespace=PARSED_NAMESPACE,
        artifact_type="internal_current_official_parsed_source",
    )
    observed = store.get_json(ref["object_key"], expected_digest=ref["digest"])
    if canonical_digest(observed) != ref["digest"]:
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_parsed_capture_readback_failed"
        )
    return ref


def execute_internal_source_acquisition(
    *,
    policy: Mapping[str, Any],
    admission: Mapping[str, Any],
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
    store = FileCanonicalObjectStore(runtime_path / "objects")
    client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=transport,
        namespace="fin-0.1.3/s1-internal-current-source-acquisition/raw",
    )
    results: list[dict[str, Any]] = []
    allowed_hosts = {"data.sec.gov", "www.sec.gov"}
    for target in policy["acquisition_targets"]:
        attempts: list[dict[str, Any]] = []
        submission_response, submission_attempt = client.fetch(
            case_key=str(target["ticker"]),
            route_id=f"{target['target_id']}:sec_submissions",
            url=str(target["submission_url"]),
            allowed_hosts=allowed_hosts,
            timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
            byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
        )
        attempts.append(submission_attempt)
        selected: dict[str, Any] | None = None
        accepted: dict[str, Any] | None = None
        failure_code = ""
        if submission_response is None or submission_attempt["status"] != "captured":
            failure_code = str(
                submission_attempt.get("failure_code")
                or "internal_source_acquisition_submissions_unavailable"
            )
        else:
            try:
                payload = json.loads(submission_response.body.decode("utf-8"))
                selected = select_target_submission(payload, target=target)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                failure_code = (
                    "internal_source_acquisition_submissions_json_invalid:"
                    + type(exc).__name__
                )
            except S1InternalSourceAcquisitionError as exc:
                failure_code = str(exc)
        primary_response = None
        if selected is not None:
            primary_response, primary_attempt = client.fetch(
                case_key=str(target["ticker"]),
                route_id=f"{target['target_id']}:primary_document",
                url=str(selected["primary_url"]),
                allowed_hosts=allowed_hosts,
                timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
                byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
            )
            attempts.append(primary_attempt)
            if primary_response is None or primary_attempt["status"] != "captured":
                failure_code = str(
                    primary_attempt.get("failure_code")
                    or "internal_source_acquisition_primary_unavailable"
                )
            else:
                parsed = parse_source_document(primary_response)
                markers_pass, missing = _markers_pass(
                    str(parsed.get("text") or ""),
                    [list(group) for group in target["marker_groups"]],
                )
                accepted = {
                    "response": primary_response,
                    "attempt": primary_attempt,
                    "parsed": parsed,
                    "markers_pass": markers_pass,
                    "missing_marker_groups": missing,
                    "selection": "primary_document",
                }
        if (
            selected is not None
            and primary_response is not None
            and accepted is not None
            and not accepted["markers_pass"]
            and bool(target.get("allow_one_same_accession_exhibit"))
        ):
            exhibit_url = select_same_accession_exhibit(
                body=primary_response.body,
                primary_url=primary_response.final_url,
                allowed_hosts=allowed_hosts,
            )
            if exhibit_url:
                exhibit_response, exhibit_attempt = client.fetch(
                    case_key=str(target["ticker"]),
                    route_id=f"{target['target_id']}:selected_exhibit",
                    url=exhibit_url,
                    allowed_hosts=allowed_hosts,
                    timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
                    byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
                )
                attempts.append(exhibit_attempt)
                if exhibit_response is not None and exhibit_attempt["status"] == "captured":
                    parsed = parse_source_document(exhibit_response)
                    markers_pass, missing = _markers_pass(
                        str(parsed.get("text") or ""),
                        [list(group) for group in target["marker_groups"]],
                    )
                    accepted = {
                        "response": exhibit_response,
                        "attempt": exhibit_attempt,
                        "parsed": parsed,
                        "markers_pass": markers_pass,
                        "missing_marker_groups": missing,
                        "selection": "same_accession_exhibit",
                    }
            else:
                failure_code = "internal_source_acquisition_exhibit_locator_absent"
        if accepted is not None and accepted["markers_pass"] and selected is not None:
            parsed_ref = _persist_parsed_text(
                store=store,
                target=target,
                selected=selected,
                final_url=str(accepted["response"].final_url),
                parsed=accepted["parsed"],
            )
            status = "captured_parsed_target_markers_pass"
            failure_code = ""
            source = {
                "accession_number": selected["accession_number"],
                "filing_date": selected["filing_date"],
                "report_date": selected["report_date"],
                "form_type": selected["form_type"],
                "primary_document": selected["primary_document"],
                "selected_url": str(accepted["response"].final_url),
                "selection": str(accepted["selection"]),
                "parser_adapter": str(accepted["parsed"]["adapter"]),
                "parser_text_digest": str(accepted["parsed"]["text_sha256"]),
                "parsed_text_chars": len(str(accepted["parsed"]["text"])),
                "parsed_capture_ref": parsed_ref["object_key"],
                "parsed_capture_digest": parsed_ref["digest"],
                "response_capture_ref": accepted["attempt"]["response_capture"][
                    "object_key"
                ],
                "response_capture_digest": accepted["attempt"]["response_capture"][
                    "digest"
                ],
            }
        else:
            status = "attempt_backed_typed_gap"
            source = None
            if not failure_code:
                failure_code = "internal_source_acquisition_target_markers_absent"
        result = {
            "target_id": str(target["target_id"]),
            "ticker": str(target["ticker"]),
            "expected_source_refs": list(target["expected_source_refs"]),
            "status": status,
            "source": source,
            "failure_code": failure_code,
            "attempts": attempts,
            "benchmark_exact_url_used_for_discovery": False,
            "candidate_state": "captured_source_not_evidence",
        }
        result["result_digest"] = canonical_digest(result)
        results.append(result)
    counts = {
        "targets": len(results),
        "acquired": sum(row["status"] == "captured_parsed_target_markers_pass" for row in results),
        "typed_gaps": sum(row["status"] == "attempt_backed_typed_gap" for row in results),
        "network_calls": client.network_calls,
        "retry_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotion_calls": 0,
    }
    if counts["network_calls"] > int(admission["network_call_ceiling"]):
        raise S1InternalSourceAcquisitionError(
            "internal_source_acquisition_network_budget_exceeded"
        )
    all_acquired = counts["acquired"] == counts["targets"]
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": (
            "completed_all_targets_acquired"
            if all_acquired
            else "completed_with_attempt_backed_source_gaps"
        ),
        "policy_digest": canonical_digest(policy),
        "admission_digest": str(admission["admission_digest"]),
        "run_id": str(admission["run_id"]),
        "attempt_id": str(admission["attempt_id"]),
        "observed_at": observed_at,
        "source_results": results,
        "capture_refs": client.capture_refs,
        "observed_counts": counts,
        "stage_boundary": {
            "generic_external_discovery_proven": False,
            "internal_corpus_source_acquisition_proven": all_acquired,
            "candidate_ceiling_proven": False,
            "BGE_fusion_rerank_admitted": False,
            "evidence_or_release": False,
        },
        "known_boundary": (
            "This exact-once run uses typed issuer/form/period criteria and SEC "
            "submissions, not benchmark URLs, to repair a bounded local corpus. It "
            "does not close the independent broad external-search blocker."
        ),
    }
    output = {**body, "result_digest": canonical_digest(body)}
    ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status="success" if all_acquired else "completed_with_gaps",
        terminal_phase="internal_current_official_source_acquisition_terminal",
        terminal_code=(
            "all_targets_captured_parsed_and_marker_bound"
            if all_acquired
            else "one_or_more_attempt_backed_source_gaps"
        ),
        terminal_result_digest=output["result_digest"],
        finalized_at=observed_at,
    )
    return output


def _retained_capture_inventory(runtime_path: Path) -> tuple[list[dict[str, Any]], int]:
    object_root = runtime_path / "objects"
    if not object_root.is_dir():
        return [], 0
    refs: list[dict[str, Any]] = []
    request_count = 0
    for path in sorted(object_root.rglob("*.json")):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict) and payload.get("capture_kind") == "source_request":
            request_count += 1
        refs.append(
            {
                "object_key": path.relative_to(object_root).as_posix(),
                "digest": digest,
                "byte_size": len(data),
            }
        )
    return refs, request_count


def _typed_failure_code(exc: Exception) -> str:
    supplied = str(getattr(exc, "code", "") or "").strip()
    if supplied:
        return supplied
    if isinstance(exc, S1InternalSourceAcquisitionError):
        value = str(exc).strip()
        if value:
            return value
    return "internal_source_acquisition_unhandled_" + type(exc).__name__.lower()


def execute_internal_source_acquisition_guarded(
    *,
    policy: Mapping[str, Any],
    admission: Mapping[str, Any],
    runtime_root: str | Path,
    ledger: SharedAdmissionConsumptionLedger,
    transport: SourceTransport,
    observed_at: str,
) -> dict[str, Any]:
    """Execute once and materialize a typed terminal after any consumed failure.

    A durable reservation is already consumption. If a parser, budget or unexpected
    runtime error occurs after reservation, this wrapper keeps the raw captures,
    finalizes the shared ledger, and returns a failure result instead of leaving the
    admission in an ambiguous reserved state.
    """

    runtime_path = Path(runtime_root).resolve()
    try:
        return execute_internal_source_acquisition(
            policy=policy,
            admission=admission,
            runtime_root=runtime_path,
            ledger=ledger,
            transport=transport,
            observed_at=observed_at,
        )
    except Exception as exc:
        try:
            receipt = ledger.read(str(admission["admission_digest"]))
        except Exception:
            raise exc
        if (
            receipt.state != "reserved"
            or receipt.run_id != str(admission["run_id"])
            or receipt.attempt_id != str(admission["attempt_id"])
        ):
            raise exc
        capture_refs, request_count = _retained_capture_inventory(runtime_path)
        failure_code = _typed_failure_code(exc)
        finalized_at = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
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
            "source_results": [],
            "capture_refs": capture_refs,
            "observed_counts": {
                "targets": len(list(policy.get("acquisition_targets") or [])),
                "acquired": 0,
                "typed_gaps": 0,
                "network_calls": request_count,
                "retry_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "embedding_calls": 0,
                "rerank_calls": 0,
                "evidence_promotion_calls": 0,
            },
            "failure": {
                "phase": "internal_current_official_source_acquisition_runtime",
                "code": failure_code,
                "raw_captures_retained": bool(capture_refs),
            },
            "stage_boundary": {
                "generic_external_discovery_proven": False,
                "internal_corpus_source_acquisition_proven": False,
                "candidate_ceiling_proven": False,
                "BGE_fusion_rerank_admitted": False,
                "evidence_or_release": False,
            },
            "known_boundary": (
                "The admission was consumed and the failure terminalized. Retained "
                "captures are audit material only and are not Evidence. No retry or "
                "automatic replacement is authorized."
            ),
        }
        output = {**body, "result_digest": canonical_digest(body)}
        ledger.finalize(
            admission_digest=str(admission["admission_digest"]),
            run_id=str(admission["run_id"]),
            attempt_id=str(admission["attempt_id"]),
            terminal_status="failed",
            terminal_phase=str(output["failure"]["phase"]),
            terminal_code=failure_code,
            terminal_result_digest=output["result_digest"],
            finalized_at=finalized_at,
        )
        return output


__all__ = [
    "ADMISSION_SCHEMA",
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S1InternalSourceAcquisitionError",
    "execute_internal_source_acquisition",
    "execute_internal_source_acquisition_guarded",
    "issue_internal_source_acquisition_admission",
    "load_internal_source_acquisition_policy",
    "select_same_accession_exhibit",
    "select_target_submission",
    "validate_internal_source_acquisition_admission",
]
