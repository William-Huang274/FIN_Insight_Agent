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
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_mu_10q_acquisition_policy_v1_0"
ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_internal_mu_10q_acquisition_admission_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_mu_10q_acquisition_result_v1_0"
CONTRACT_REF = (
    "fin_0_1_3.S1.internal_mu_q3_fy2026_10q_successor_acquisition:v1"
)
RUN_SCOPE = "S1_INTERNAL_MU_Q3_10Q_SUCCESSOR_ACQUISITION"
RAW_NAMESPACE = "fin-0.1.3/s1-internal-mu-10q-successor/raw"
PARSED_NAMESPACE = "fin-0.1.3/s1-internal-mu-10q-successor/parsed"


class S1InternalMu10QAcquisitionError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_object_required"
        )
    return value


def _digest_valid(value: Mapping[str, Any], field: str) -> bool:
    body = dict(value)
    supplied = str(body.pop(field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def load_internal_mu_10q_acquisition_policy(
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
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_policy_identity_invalid"
        )
    inputs = dict(policy.get("immutable_inputs") or {})
    for stem in ("qrels_review", "locator_observation"):
        ref = str(inputs.get(f"{stem}_ref") or "")
        supplied = str(inputs.get(f"{stem}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalMu10QAcquisitionError(
                f"internal_mu_10q_acquisition_binding_invalid:{stem}"
            )
    qrels = _read_json(root / str(inputs["qrels_review_ref"]))
    missing = [
        row
        for row in qrels.get("qrels") or []
        if not row.get("strict_current_target_in_pool")
    ]
    if (
        not _digest_valid(qrels, "review_digest")
        or int(qrels.get("strict_current_target_in_pool_count") or 0) != 17
        or len(missing) != 1
        or (
            missing[0].get("case_key"),
            missing[0].get("evidence_slot_id"),
            missing[0].get("evidence_owner_ticker"),
        )
        != ("MU", "regulatory_risk_and_financial_reconciliation", "MU")
    ):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_qrels_state_invalid"
        )
    locator = _read_json(root / str(inputs["locator_observation_ref"]))
    target = dict(policy.get("target") or {})
    locator_target = dict(locator.get("target") or {})
    comparable_target = {key: target.get(key) for key in locator_target}
    if (
        not _digest_valid(locator, "locator_digest")
        or locator.get("status") != "retained_capture_locator_proven"
        or locator.get("benchmark_exact_url_used_for_discovery") is not False
        or locator_target != comparable_target
    ):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_locator_invalid"
        )
    parsed_url = urlparse(str(target.get("source_url") or ""))
    if (
        parsed_url.scheme != "https"
        or (parsed_url.hostname or "").lower() != "www.sec.gov"
        or not target.get("marker_groups")
    ):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_target_invalid"
        )
    budgets = dict(policy.get("budgets") or {})
    if (
        int(budgets.get("network_call_ceiling") or 0) != 1
        or int(budgets.get("retry_ceiling", -1)) != 0
        or int(budgets.get("model_calls", -1)) != 0
        or int(budgets.get("provider_calls", -1)) != 0
    ):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_budget_invalid"
        )
    hard = dict(policy.get("hard_boundaries") or {})
    if (
        hard.get("source_url_must_equal_retained_locator") is not True
        or hard.get("benchmark_exact_url_used_for_discovery") is not False
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
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_boundary_invalid"
        )
    return policy


def issue_internal_mu_10q_acquisition_admission(
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
        "network_call_ceiling": 1,
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
        "admission_id": f"fin013_s1_mu10q_admission_{digest[:20]}",
        "run_id": f"fin013_s1_mu10q_run_{digest[20:40]}",
        "attempt_id": f"fin013_s1_mu10q_attempt_{digest[40:60]}",
        "admission_digest": digest,
    }


def validate_internal_mu_10q_acquisition_admission(
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
        or admission_id != f"fin013_s1_mu10q_admission_{expected[:20]}"
        or run_id != f"fin013_s1_mu10q_run_{expected[20:40]}"
        or attempt_id != f"fin013_s1_mu10q_attempt_{expected[40:60]}"
        or body.get("schema_version") != ADMISSION_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or body.get("run_scope") != RUN_SCOPE
        or body.get("policy_digest") != canonical_digest(policy)
        or int(body.get("maximum_executions") or 0) != 1
        or int(body.get("network_call_ceiling") or 0) != 1
    ):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_admission_invalid"
        )
    if (
        str(body.get("implementation_file_sha256") or "")
        != _normalized_sha256(Path(implementation_path))
        or str(body.get("policy_file_sha256") or "")
        != _normalized_sha256(Path(policy_path))
    ):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_admission_file_binding_invalid"
        )
    now = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
    expiry = datetime.fromisoformat(str(body["expires_at"]).replace("Z", "+00:00"))
    if now.astimezone(timezone.utc) > expiry.astimezone(timezone.utc):
        raise S1InternalMu10QAcquisitionError(
            "internal_mu_10q_acquisition_admission_expired"
        )
    return dict(admission)


def _markers_pass(text: str, groups: list[list[str]]) -> tuple[bool, list[int]]:
    normalized = " ".join(str(text or "").lower().split())
    missing = [
        index
        for index, group in enumerate(groups)
        if not any(str(marker).lower() in normalized for marker in group)
    ]
    return not missing, missing


def _persist_parsed(
    *, store: FileCanonicalObjectStore, target: Mapping[str, Any], parsed: Mapping[str, Any]
) -> dict[str, Any]:
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_internal_mu_10q_parsed_capture_v1_0",
        "target_id": str(target["target_id"]),
        "ticker": "MU",
        "form_type": "10-Q",
        "reporting_fiscal_year": 2026,
        "filing_date": str(target["filing_date"]),
        "report_date": str(target["report_date"]),
        "accession_number": str(target["accession_number"]),
        "source_url": str(target["source_url"]),
        "parser_adapter": str(parsed["adapter"]),
        "parser_text_digest": str(parsed["text_sha256"]),
        "text": str(parsed["text"]),
    }
    ref = store.put_json(
        payload,
        namespace=PARSED_NAMESPACE,
        artifact_type="internal_mu_10q_parsed_source",
    )
    store.get_json(ref["object_key"], expected_digest=ref["digest"])
    return ref


def _runtime_capture_inventory(runtime_root: Path) -> list[dict[str, Any]]:
    object_root = runtime_root / "objects"
    if not object_root.is_dir():
        return []
    return [
        {
            "object_key": path.relative_to(object_root).as_posix(),
            "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size,
        }
        for path in sorted(object_root.rglob("*.json"))
    ]


def execute_internal_mu_10q_acquisition_guarded(
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
        store=store, transport=transport, namespace=RAW_NAMESPACE
    )
    target = dict(policy["target"])
    terminal_status = "failed"
    terminal_code = "internal_mu_10q_acquisition_unhandled"
    try:
        response, attempt = client.fetch(
            case_key="MU",
            route_id="MU_Q3_FY2026_CURRENT_10Q:primary_document",
            url=str(target["source_url"]),
            allowed_hosts={"www.sec.gov"},
            timeout_seconds=int(policy["budgets"]["timeout_seconds"]),
            byte_ceiling=int(policy["budgets"]["byte_ceiling"]),
        )
        source = None
        failure_code = ""
        status = "attempt_backed_typed_gap"
        if response is None or attempt.get("status") != "captured":
            failure_code = str(
                attempt.get("failure_code")
                or "internal_mu_10q_acquisition_source_unavailable"
            )
        else:
            parsed = parse_source_document(response)
            markers_ok, missing = _markers_pass(
                str(parsed.get("text") or ""),
                [list(group) for group in target["marker_groups"]],
            )
            if markers_ok:
                parsed_ref = _persist_parsed(
                    store=store, target=target, parsed=parsed
                )
                status = "captured_parsed_target_markers_pass"
                source = {
                    key: target[key]
                    for key in (
                        "accession_number",
                        "filing_date",
                        "report_date",
                        "form_type",
                        "primary_document",
                        "source_url",
                    )
                }
                source.update(
                    {
                        "parser_adapter": str(parsed["adapter"]),
                        "parser_text_digest": str(parsed["text_sha256"]),
                        "parsed_text_chars": len(str(parsed["text"])),
                        "parsed_capture_ref": str(parsed_ref["object_key"]),
                        "parsed_capture_digest": str(parsed_ref["digest"]),
                        "response_capture_ref": str(
                            attempt["response_capture"]["object_key"]
                        ),
                        "response_capture_digest": str(
                            attempt["response_capture"]["digest"]
                        ),
                    }
                )
            else:
                failure_code = (
                    "internal_mu_10q_acquisition_markers_absent:"
                    + ",".join(str(item) for item in missing)
                )
        success = status == "captured_parsed_target_markers_pass"
        body = {
            "schema_version": RESULT_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "run_scope": RUN_SCOPE,
            "status": "completed_target_acquired" if success else "completed_with_attempt_backed_gap",
            "policy_digest": canonical_digest(policy),
            "admission_digest": str(admission["admission_digest"]),
            "run_id": str(admission["run_id"]),
            "attempt_id": str(admission["attempt_id"]),
            "observed_at": observed_at,
            "source_result": {
                "target_id": str(target["target_id"]),
                "ticker": "MU",
                "status": status,
                "source": source,
                "failure_code": failure_code,
                "attempt": attempt,
                "benchmark_exact_url_used_for_discovery": False,
                "candidate_state": "captured_source_not_evidence",
            },
            "capture_refs": client.capture_refs,
            "observed_counts": {
                "targets": 1,
                "acquired": int(success),
                "typed_gaps": int(not success),
                "network_calls": client.network_calls,
                "retry_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "embedding_calls": 0,
                "rerank_calls": 0,
                "evidence_promotion_calls": 0,
            },
            "stage_boundary": {
                "mu_10q_source_acquisition_proven": success,
                "candidate_ceiling_proven": False,
                "BGE_fusion_rerank_admitted": False,
                "external_product_coverage_closed": False,
                "evidence_or_release": False,
            },
            "known_boundary": (
                "The direct SEC URL was derived from a retained submissions capture. "
                "This result is a captured candidate source, not Evidence or broad "
                "external-search acceptance."
            ),
        }
        # ``network_calls`` intentionally counts only real network I/O. Fake
        # transports still exercise the complete capture/parse/terminal path,
        # so a zero-call proof observes zero while live consumes one call.
        expected_network_calls = int(bool(transport.live_network))
        if client.network_calls != expected_network_calls:
            raise S1InternalMu10QAcquisitionError(
                "internal_mu_10q_acquisition_network_count_invalid"
            )
        output = {**body, "result_digest": canonical_digest(body)}
        terminal_status = "success" if success else "completed_with_gaps"
        terminal_code = (
            "mu_10q_captured_parsed_and_marker_bound"
            if success
            else "mu_10q_attempt_backed_gap"
        )
    except Exception as exc:
        failure_code = str(exc) or type(exc).__name__
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
            "failure_code": failure_code,
            "capture_refs": _runtime_capture_inventory(runtime_path),
            "observed_counts": {
                "targets": 1,
                "acquired": 0,
                "typed_gaps": 1,
                "network_calls": client.network_calls,
                "retry_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "embedding_calls": 0,
                "rerank_calls": 0,
                "evidence_promotion_calls": 0,
            },
            "stage_boundary": {
                "mu_10q_source_acquisition_proven": False,
                "candidate_ceiling_proven": False,
                "BGE_fusion_rerank_admitted": False,
                "external_product_coverage_closed": False,
                "evidence_or_release": False,
            },
        }
        output = {**body, "result_digest": canonical_digest(body)}
        terminal_code = "mu_10q_consumed_failure_terminalized"
    ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=terminal_status,
        terminal_phase="internal_mu_10q_successor_acquisition_terminal",
        terminal_code=terminal_code,
        terminal_result_digest=str(output["result_digest"]),
        finalized_at=observed_at,
    )
    return output


__all__ = [
    "ADMISSION_SCHEMA",
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S1InternalMu10QAcquisitionError",
    "execute_internal_mu_10q_acquisition_guarded",
    "issue_internal_mu_10q_acquisition_admission",
    "load_internal_mu_10q_acquisition_policy",
    "validate_internal_mu_10q_acquisition_admission",
]
