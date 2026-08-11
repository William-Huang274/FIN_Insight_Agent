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
    parse_source_document,
)
from sec_agent.s1_internal_current_source_acquisition import (
    select_same_accession_exhibit,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_held_out_current_source_acquisition_policy_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_held_out_current_source_acquisition_admission_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_held_out_current_source_acquisition_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.held_out_current_official_source_acquisition:v1"
RUN_SCOPE = "S1_THREE_HELD_OUT_EXACT_OFFICIAL_CURRENT_SOURCE_DISCOVERY_CAPTURE_AND_BUNDLE_V2_REPROOF"
EXPECTED_CASES = ("ORCL", "ASML", "ANET")
PARSED_NAMESPACE = "fin-0.1.3/s1-held-out-current-source-acquisition/parsed"
RAW_NAMESPACE = "fin-0.1.3/s1-held-out-current-source-acquisition/raw"


class HeldOutCurrentSourceAcquisitionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def normalized_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_json_object_required")
    return value


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_held_out_current_source_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(path)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile") != "sha256_utf8_lf_normalized_v1"
    ):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_policy_identity_invalid")

    for binding in policy.get("immutable_inputs") or []:
        target = root / str(binding.get("path") or "")
        if (
            not target.is_file()
            or normalized_sha256(target) != str(binding.get("normalized_sha256") or "")
        ):
            raise HeldOutCurrentSourceAcquisitionError("held_out_source_input_binding_invalid")

    targets = list(policy.get("acquisition_targets") or [])
    if tuple(str(row.get("case_key") or "") for row in targets) != EXPECTED_CASES:
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_case_order_invalid")
    if "/Archives/" in json.dumps(targets) or any(
        any(character.isdigit() for character in str(row.get("known_accession") or ""))
        for row in targets
    ):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_answer_url_forbidden")
    for target in targets:
        cik = str(target.get("cik") or "")
        url = str(target.get("submission_url") or "")
        parsed = urlparse(url)
        forms = list(target.get("accepted_form_types") or [])
        if (
            not cik.isdigit()
            or len(cik) != 10
            or parsed.scheme != "https"
            or (parsed.hostname or "").lower() != "data.sec.gov"
            or parsed.path != f"/submissions/CIK{cik}.json"
            or not forms
            or len(forms) != len(set(forms))
            or not target.get("marker_groups")
        ):
            raise HeldOutCurrentSourceAcquisitionError("held_out_source_target_shape_invalid")

    budgets = dict(policy.get("budgets") or {})
    if (
        int(budgets.get("network_call_ceiling") or 0) != 9
        or int(budgets.get("retry_ceiling", -1)) != 0
        or any(
            int(budgets.get(name, -1)) != 0
            for name in ("model_calls", "provider_calls", "embedding_calls", "rerank_calls")
        )
    ):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_budget_invalid")
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("exact_accession_or_final_url_seeded") is not False
        or hard.get("captured_source_is_evidence") is not False
        or hard.get("broad_web_search_used") is not False
        or hard.get("index_rebuild_admitted") is not False
    ):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_boundary_invalid")
    return policy


def issue_held_out_current_source_admission(
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
        "admission_id": f"fin013_s1_heldout_source_admission_{digest[:20]}",
        "run_id": f"fin013_s1_heldout_source_run_{digest[20:40]}",
        "attempt_id": f"fin013_s1_heldout_source_attempt_{digest[40:60]}",
        "admission_digest": digest,
    }


def validate_held_out_current_source_admission(
    admission: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    implementation_path: str | Path,
    policy_path: str | Path,
    observed_at: str,
) -> None:
    body = dict(admission)
    supplied = str(body.pop("admission_digest", ""))
    admission_id = str(body.pop("admission_id", ""))
    run_id = str(body.pop("run_id", ""))
    attempt_id = str(body.pop("attempt_id", ""))
    expected = canonical_digest(body)
    if (
        supplied != expected
        or admission_id != f"fin013_s1_heldout_source_admission_{expected[:20]}"
        or run_id != f"fin013_s1_heldout_source_run_{expected[20:40]}"
        or attempt_id != f"fin013_s1_heldout_source_attempt_{expected[40:60]}"
        or body.get("schema_version") != ADMISSION_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or body.get("run_scope") != RUN_SCOPE
        or body.get("policy_digest") != canonical_digest(policy)
        or int(body.get("maximum_executions") or 0) != 1
        or int(body.get("network_call_ceiling") or 0) != 9
    ):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_admission_invalid")
    if (
        normalized_sha256(implementation_path) != str(body.get("implementation_file_sha256") or "")
        or normalized_sha256(policy_path) != str(body.get("policy_file_sha256") or "")
    ):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_admission_binding_invalid")
    observed = _parse_time(observed_at)
    if not _parse_time(str(body["issued_at"])) <= observed <= _parse_time(str(body["expires_at"])):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_admission_expired")


def submission_rows(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    recent = dict((payload.get("filings") or {}).get("recent") or {})
    required = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
    if any(not isinstance(recent.get(name), list) for name in required):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_submissions_shape_invalid")
    count = len(recent["accessionNumber"])
    if any(len(recent[name]) != count for name in required):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_submissions_length_invalid")
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
    preferences = [str(value).upper() for value in target["accepted_form_types"]]
    start = str(target.get("filing_date_not_before") or "")
    end = str(target.get("filing_date_not_after") or target["as_of_date"])
    report_start = str(target.get("report_date_not_before") or "")
    candidates: list[dict[str, Any]] = []
    for row in submission_rows(payload):
        if row["form_type"] not in preferences:
            continue
        if start and row["filing_date"] < start:
            continue
        if end and row["filing_date"] > end:
            continue
        if report_start and row["report_date"] and row["report_date"] < report_start:
            continue
        candidates.append({**row, "form_preference": preferences.index(row["form_type"])})
    if not candidates:
        raise HeldOutCurrentSourceAcquisitionError(
            f"held_out_source_submission_not_found:{target['case_key']}"
        )
    candidates.sort(
        key=lambda row: (
            int(row["form_preference"]),
            -int(row["filing_date"].replace("-", "") or 0),
            row["accession_number"],
        )
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
    missing = [group for group in groups if not any(str(token).lower() in lowered for token in group)]
    return not missing, missing


def _persist_parsed(
    *,
    store: FileCanonicalObjectStore,
    target: Mapping[str, Any],
    selected: Mapping[str, Any],
    final_url: str,
    parsed: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_held_out_parsed_source_capture_v1_0",
        "case_key": str(target["case_key"]),
        "subject_entity_key": str(target["subject_entity_key"]),
        "cik": str(target["cik"]),
        "reporting_currency": str(target["reporting_currency"]),
        "form_type": str(selected["form_type"]),
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
        artifact_type="held_out_current_official_parsed_source",
    )
    observed = store.get_json(ref["object_key"], expected_digest=ref["digest"])
    if canonical_digest(observed) != ref["digest"]:
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_parsed_readback_failed")
    return ref


def execute_held_out_current_source_acquisition(
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
        namespace=RAW_NAMESPACE,
    )
    allowed_hosts = {"data.sec.gov", "www.sec.gov"}
    source_results: list[dict[str, Any]] = []
    for target in policy["acquisition_targets"]:
        attempts: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        accepted: dict[str, Any] | None = None
        failure_code = ""
        response, attempt = client.fetch(
            case_key=str(target["case_key"]),
            route_id=f"{target['case_key']}:sec_submissions",
            url=str(target["submission_url"]),
            allowed_hosts=allowed_hosts,
            timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
            byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
        )
        attempts.append(attempt)
        if response is None or attempt["status"] != "captured":
            failure_code = str(attempt.get("failure_code") or "held_out_source_submissions_unavailable")
        else:
            try:
                selected = select_target_submission(
                    json.loads(response.body.decode("utf-8")), target=target
                )
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                failure_code = f"held_out_source_submissions_json_invalid:{type(exc).__name__}"
            except HeldOutCurrentSourceAcquisitionError as exc:
                failure_code = exc.code

        primary_response = None
        if selected is not None:
            primary_response, primary_attempt = client.fetch(
                case_key=str(target["case_key"]),
                route_id=f"{target['case_key']}:primary_document",
                url=str(selected["primary_url"]),
                allowed_hosts=allowed_hosts,
                timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
                byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
            )
            attempts.append(primary_attempt)
            if primary_response is not None and primary_attempt["status"] == "captured":
                parsed = parse_source_document(primary_response)
                passed, missing = _markers_pass(
                    str(parsed.get("text") or ""),
                    [list(group) for group in target["marker_groups"]],
                )
                accepted = {
                    "response": primary_response,
                    "attempt": primary_attempt,
                    "parsed": parsed,
                    "markers_pass": passed,
                    "missing_marker_groups": missing,
                    "selection": "primary_document",
                }
            else:
                failure_code = str(
                    primary_attempt.get("failure_code") or "held_out_source_primary_unavailable"
                )

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
                    case_key=str(target["case_key"]),
                    route_id=f"{target['case_key']}:selected_exhibit",
                    url=exhibit_url,
                    allowed_hosts=allowed_hosts,
                    timeout_seconds=int(policy["budgets"]["timeout_seconds_per_route"]),
                    byte_ceiling=int(policy["budgets"]["byte_ceiling_per_response"]),
                )
                attempts.append(exhibit_attempt)
                if exhibit_response is not None and exhibit_attempt["status"] == "captured":
                    parsed = parse_source_document(exhibit_response)
                    passed, missing = _markers_pass(
                        str(parsed.get("text") or ""),
                        [list(group) for group in target["marker_groups"]],
                    )
                    accepted = {
                        "response": exhibit_response,
                        "attempt": exhibit_attempt,
                        "parsed": parsed,
                        "markers_pass": passed,
                        "missing_marker_groups": missing,
                        "selection": "same_accession_exhibit",
                    }
            else:
                failure_code = "held_out_source_exhibit_locator_absent"

        if accepted is not None and accepted["markers_pass"] and selected is not None:
            parsed_ref = _persist_parsed(
                store=store,
                target=target,
                selected=selected,
                final_url=str(accepted["response"].final_url),
                parsed=accepted["parsed"],
            )
            source = {
                "accession_number": selected["accession_number"],
                "filing_date": selected["filing_date"],
                "report_date": selected["report_date"],
                "form_type": selected["form_type"],
                "primary_document": selected["primary_document"],
                "candidate_count": selected["candidate_count"],
                "selected_url": str(accepted["response"].final_url),
                "selection": str(accepted["selection"]),
                "parser_adapter": str(accepted["parsed"]["adapter"]),
                "parser_text_digest": str(accepted["parsed"]["text_sha256"]),
                "parsed_text_chars": len(str(accepted["parsed"]["text"])),
                "parsed_capture_ref": parsed_ref["object_key"],
                "parsed_capture_digest": parsed_ref["digest"],
                "response_capture_ref": accepted["attempt"]["response_capture"]["object_key"],
                "response_capture_digest": accepted["attempt"]["response_capture"]["digest"],
            }
            status = "captured_parsed_current_markers_pass"
            failure_code = ""
        else:
            source = None
            status = "attempt_backed_typed_gap"
            if not failure_code:
                failure_code = "held_out_source_current_markers_absent"
        result = {
            "case_key": str(target["case_key"]),
            "status": status,
            "source": source,
            "failure_code": failure_code,
            "attempts": attempts,
            "exact_accession_or_final_url_seeded": False,
            "candidate_state": "captured_source_not_evidence",
        }
        result["result_digest"] = canonical_digest(result)
        source_results.append(result)

    counts = {
        "targets": len(source_results),
        "acquired": sum(row["status"] == "captured_parsed_current_markers_pass" for row in source_results),
        "typed_gaps": sum(row["status"] == "attempt_backed_typed_gap" for row in source_results),
        "network_calls": client.network_calls,
        "retry_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotion_calls": 0,
    }
    if counts["network_calls"] > int(admission["network_call_ceiling"]):
        raise HeldOutCurrentSourceAcquisitionError("held_out_source_network_budget_exceeded")
    all_acquired = counts["acquired"] == counts["targets"]
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "completed_all_targets_acquired" if all_acquired else "completed_with_attempt_backed_source_gaps",
        "policy_digest": canonical_digest(policy),
        "admission_digest": str(admission["admission_digest"]),
        "run_id": str(admission["run_id"]),
        "attempt_id": str(admission["attempt_id"]),
        "observed_at": observed_at,
        "source_results": source_results,
        "capture_refs": client.capture_refs,
        "observed_counts": counts,
        "stage_acceptance": {
            "held_out_current_source_capture": all_acquired,
            "current_source_reparse": False,
            "held_out_product_generalization": False,
            "sparse_dense_rebuild_admitted": False,
            "external_residual_supplement_admitted": False,
            "model_research_admitted": False,
        },
        "known_boundary": (
            "Official SEC sources were selected from issuer identity, form and date criteria. "
            "Captured source is not Evidence; parsing, bundle-v2 reproof and held-out acceptance remain separate."
        ),
    }
    output = {**body, "result_digest": canonical_digest(body)}
    ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status="success" if all_acquired else "completed_with_gaps",
        terminal_phase="held_out_current_official_source_acquisition_terminal",
        terminal_code="all_targets_captured" if all_acquired else "one_or_more_attempt_backed_gaps",
        terminal_result_digest=output["result_digest"],
        finalized_at=observed_at,
    )
    return output


def retained_capture_inventory(runtime_path: Path) -> tuple[list[dict[str, Any]], int]:
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
        refs.append(
            {
                "object_key": path.relative_to(object_root).as_posix(),
                "digest": hashlib.sha256(data).hexdigest(),
                "byte_size": len(data),
            }
        )
    return refs, request_count


def execute_held_out_current_source_acquisition_guarded(**kwargs: Any) -> dict[str, Any]:
    runtime_path = Path(kwargs["runtime_root"]).resolve()
    admission = kwargs["admission"]
    policy = kwargs["policy"]
    ledger = kwargs["ledger"]
    observed_at = str(kwargs["observed_at"])
    try:
        return execute_held_out_current_source_acquisition(**kwargs)
    except Exception as exc:
        try:
            receipt = ledger.read(str(admission["admission_digest"]))
        except Exception:
            raise exc
        if receipt.state != "reserved":
            raise exc
        refs, request_count = retained_capture_inventory(runtime_path)
        code = str(getattr(exc, "code", "") or f"held_out_source_unhandled_{type(exc).__name__.lower()}")
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
            "source_results": [],
            "capture_refs": refs,
            "observed_counts": {
                "targets": len(policy.get("acquisition_targets") or []),
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
                "phase": "held_out_current_official_source_acquisition_runtime",
                "code": code,
                "raw_captures_retained": bool(refs),
            },
            "stage_acceptance": {
                "held_out_current_source_capture": False,
                "current_source_reparse": False,
                "held_out_product_generalization": False,
                "sparse_dense_rebuild_admitted": False,
                "external_residual_supplement_admitted": False,
                "model_research_admitted": False,
            },
            "known_boundary": "Consumed failure is terminal and retained captures are audit material only; no automatic retry is authorized.",
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
    "RUN_SCOPE",
    "HeldOutCurrentSourceAcquisitionError",
    "execute_held_out_current_source_acquisition",
    "execute_held_out_current_source_acquisition_guarded",
    "issue_held_out_current_source_admission",
    "load_held_out_current_source_policy",
    "normalized_sha256",
    "select_target_submission",
    "submission_rows",
    "validate_held_out_current_source_admission",
]
