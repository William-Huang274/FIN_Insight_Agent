from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from typing import Any, Callable, Mapping

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.local_research_service import (
    P36LocalResearchService,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
    prepare_s4_source_grounded_exact_input,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    load_s4_source_grounded_input_pack,
)


TENANT_ID = "tenant-fin01-s3-t09-eval"
PROJECT_ID = "project-fin01-s3-t09-eval"
ACTOR_ID = "analyst-fin01-s3-t09-eval"
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    }
)
EXECUTION_IDENTITY = "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
EXPECTED_ADMISSION_ID = "fin01-s3-t09-three-cell-deepseek-segmented-exact-admission-r1"
EXPECTED_ADMISSION_DIGEST = (
    "ca7af62de613dcaa274cc8a0780658ef16e72082de54a8e1038eeeb6a4bfba3f"
)
EXPECTED_DECISION_SURFACE_REF = "p02_decision_surface_fd8fca1b6e3b98886fb71109:v1"
EXPECTED_PREPARATION_DIGEST = (
    "59d38459c8260bd8fc594c2d73917f028361b3c4f6039776f9d7382f235b1ad8"
)
EXPECTED_WORK_UNIT_ID = "wu_p02_5_b32274eec019e44d8982af58"
EXPECTED_ATTEMPT_ID = "attempt_fin01_8f40a1cf360e736835f65413"
EXPECTED_RESEARCH_RUN_ID = "research_run_fin01_a77b165e85be8757e5855a69"
EXPECTED_RUNTIME_ROOT_NAME = (
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
OUTPUT_PREFIX_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


@dataclass(frozen=True)
class S3T09ExecutionTarget:
    case_id: str
    admission_id: str
    admission_digest: str
    admission_ref: str
    runtime_root_ref: str
    execution_identity: str
    decision_surface_ref: str
    preparation_digest: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    maximum_output_tokens: int
    frozen_prepared_input_required: bool

    @property
    def runtime_root_name(self) -> str:
        return Path(self.runtime_root_ref).name


LEGACY_TARGET = S3T09ExecutionTarget(
    case_id="case_ac6fce120bf27977a1b45832",
    admission_id=EXPECTED_ADMISSION_ID,
    admission_digest=EXPECTED_ADMISSION_DIGEST,
    admission_ref=(
        "configs/releases/"
        "fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_exact_admission_v1_0.json"
    ),
    runtime_root_ref=f".codex_runtime/{EXPECTED_RUNTIME_ROOT_NAME}",
    execution_identity=EXECUTION_IDENTITY,
    decision_surface_ref=EXPECTED_DECISION_SURFACE_REF,
    preparation_digest=EXPECTED_PREPARATION_DIGEST,
    work_unit_id=EXPECTED_WORK_UNIT_ID,
    attempt_id=EXPECTED_ATTEMPT_ID,
    research_run_id=EXPECTED_RESEARCH_RUN_ID,
    maximum_output_tokens=7800,
    frozen_prepared_input_required=True,
)


def load_execution_target(issuance_path: Path) -> S3T09ExecutionTarget:
    issuance = json.loads(issuance_path.read_text(encoding="utf-8"))
    issued = issuance.get("issued_admission") or {}
    binding = issuance.get("exact_binding") or {}
    envelope = issuance.get("execution_envelope") or {}
    if issuance.get("status") != "issued_unconsumed_zero_call_preflight_pass":
        raise RuntimeError("s3_t09_issuance_not_unconsumed_and_preflight_passed")
    if issued.get("consumed") is not False or issued.get("execution_started") is not False:
        raise RuntimeError("s3_t09_issuance_already_consumed_or_started")
    required = (
        issued.get("admission_id"),
        issued.get("admission_digest"),
        issued.get("admission_ref"),
        issued.get("runtime_root"),
        issued.get("work_unit_idempotency_key"),
        binding.get("case_id"),
        binding.get("decision_surface_contract_ref"),
        binding.get("preparation_digest"),
        binding.get("predicted_work_unit_id"),
        binding.get("predicted_attempt_id"),
        binding.get("predicted_research_run_id"),
        envelope.get("maximum_output_tokens_total"),
    )
    if any(value in (None, "") for value in required):
        raise RuntimeError("s3_t09_issuance_exact_binding_incomplete")
    return S3T09ExecutionTarget(
        case_id=str(binding["case_id"]),
        admission_id=str(issued["admission_id"]),
        admission_digest=str(issued["admission_digest"]),
        admission_ref=str(issued["admission_ref"]),
        runtime_root_ref=str(issued["runtime_root"]),
        execution_identity=str(issued["work_unit_idempotency_key"]),
        decision_surface_ref=str(binding["decision_surface_contract_ref"]),
        preparation_digest=str(binding["preparation_digest"]),
        work_unit_id=str(binding["predicted_work_unit_id"]),
        attempt_id=str(binding["predicted_attempt_id"]),
        research_run_id=str(binding["predicted_research_run_id"]),
        maximum_output_tokens=int(envelope["maximum_output_tokens_total"]),
        frozen_prepared_input_required=False,
    )


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _services(
    runtime_root: Path,
) -> tuple[CaseService, P36LocalResearchService, EvidenceService]:
    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    local_service = P36LocalResearchService.from_case_service(
        case_service, repo_root=ROOT
    )
    evidence_service = EvidenceService.from_case_service(
        case_service, repo_root=ROOT
    )
    return case_service, local_service, evidence_service


def _load_admission(
    admission_path: Path, target: S3T09ExecutionTarget = LEGACY_TARGET
) -> S3ThreeCellBoundedAgentAdmission:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(admission_path.read_text(encoding="utf-8"))
    )
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    if admission.admission_id != target.admission_id:
        raise RuntimeError("s3_t09_exact_admission_id_mismatch")
    if digest != target.admission_digest:
        raise RuntimeError("s3_t09_exact_admission_digest_mismatch")
    return admission


def _execution_rows(
    case_service: CaseService, case_id: str
) -> dict[str, list[dict[str, Any]]]:
    store = case_service._facade.store
    return {
        table: store.list_latest(table, case_id=case_id)
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        )
    }


def _read_only_execution_rows(
    runtime_root: Path, case_id: str
) -> dict[str, list[dict[str, Any]]]:
    database_path = runtime_root / "canonical-runtime" / "canonical.sqlite"
    connection = sqlite3.connect(
        database_path.resolve().as_uri() + "?mode=ro", uri=True
    )
    connection.execute("pragma query_only = on")
    try:
        result: dict[str, list[dict[str, Any]]] = {}
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        ):
            latest: dict[str, dict[str, Any]] = {}
            for logical_id, payload_json in connection.execute(
                f"select logical_id, payload_json from {table} order by row_id"
            ):
                payload = json.loads(str(payload_json))
                if payload.get("case_id") == case_id:
                    payload["_logical_id"] = str(logical_id)
                    latest[str(logical_id)] = payload
            result[table] = list(latest.values())
        return result
    finally:
        connection.close()


def _target_execution_exists_in_rows(
    rows: Mapping[str, list[dict[str, Any]]], target: S3T09ExecutionTarget
) -> bool:
    return any(
        any(row.get("_logical_id") == logical_id for row in rows[table])
        for table, logical_id in (
            ("canonical_work_units", target.work_unit_id),
            ("canonical_attempts", target.attempt_id),
            ("canonical_research_run_versions", target.research_run_id),
        )
    )


def _target_execution_exists(
    case_service: CaseService, target: S3T09ExecutionTarget
) -> bool:
    store = case_service._facade.store
    return any(
        store.get_latest(table, logical_id) is not None
        for table, logical_id in (
            ("canonical_work_units", target.work_unit_id),
            ("canonical_attempts", target.attempt_id),
            ("canonical_research_run_versions", target.research_run_id),
        )
    )


def preflight(
    runtime_root: Path,
    admission_path: Path,
    target: S3T09ExecutionTarget = LEGACY_TARGET,
    *,
    output_prefix: str | None = None,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    if runtime_root.name != target.runtime_root_name:
        raise RuntimeError("s3_t09_exact_runtime_root_required")
    admission = _load_admission(admission_path, target)
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise RuntimeError("LLM_GATEWAY_TRANSPORT_RETRIES_must_be_0")

    expected_frozen = {
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "as_of": admission.as_of,
        "decision_surface_contract_ref": target.decision_surface_ref,
        "execution_identity": target.execution_identity,
        "work_unit_id": target.work_unit_id,
        "attempt_id": target.attempt_id,
        "research_run_id": target.research_run_id,
        "input_digest": admission.input_digest,
        "preparation_digest": target.preparation_digest,
    }
    if target.frozen_prepared_input_required:
        prepared_path = runtime_root / "prepared_input.json"
        if not prepared_path.exists():
            raise RuntimeError("s3_t09_prepared_input_missing")
        frozen = json.loads(prepared_path.read_text(encoding="utf-8"))
        if {key: frozen.get(key) for key in expected_frozen} != expected_frozen:
            raise RuntimeError("s3_t09_frozen_prepared_input_mismatch")

    before = _read_only_execution_rows(runtime_root, str(admission.case_id))
    if _target_execution_exists_in_rows(before, target):
        raise RuntimeError("s3_t09_exact_execution_identity_already_consumed")
    with tempfile.TemporaryDirectory(prefix="s3-t09-exact-preflight-") as temp_dir:
        clone_runtime_root = Path(temp_dir) / runtime_root.name
        shutil.copytree(runtime_root, clone_runtime_root)
        (
            clone_case_service,
            clone_local_service,
            clone_evidence_service,
        ) = _services(clone_runtime_root)
        if admission.execution_mode.startswith("exact_live_s4_"):
            (
                effective_binding,
                research_profile_overlay,
            ) = resolve_s4_case_runtime_binding_for_admission(
                ROOT,
                admission,
            )
            current = prepare_s4_source_grounded_exact_input(
                clone_case_service,
                clone_evidence_service,
                effective_binding,
                load_s4_source_grounded_input_pack(
                    ROOT, admission.company
                ),
                str(admission.case_id),
                _principal(),
                decision_surface_contract_ref=target.decision_surface_ref,
                execution_identity=target.execution_identity,
                research_profile_overlay=research_profile_overlay,
            )
        else:
            current = prepare_s3_three_cell_bounded_agent_exact_input(
                clone_local_service,
                clone_evidence_service,
                str(admission.case_id),
                _principal(),
                decision_surface_contract_ref=target.decision_surface_ref,
                execution_identity=target.execution_identity,
            )
        preflight_provider_calls = 0

        def _preflight_chat_completion(**_: Any) -> Mapping[str, Any]:
            nonlocal preflight_provider_calls
            preflight_provider_calls += 1
            raise AssertionError("s3_t09_preflight_provider_call_forbidden")

        preflight_executor = (
            build_s3_three_cell_bounded_agent_executor_for_admission(
                admission,
                chat_completion_fn=_preflight_chat_completion,
            )
        )
        create_app(
            clone_runtime_root / "preflight-workbench.sqlite",
            p02_case_service=clone_case_service,
            p03_evidence_service=clone_evidence_service,
            p36_local_research_service=clone_local_service,
            s3_three_cell_bounded_agent_admission=admission,
            s3_three_cell_bounded_agent_executor=preflight_executor,
        )
        if preflight_provider_calls != 0:
            raise RuntimeError("s3_t09_preflight_provider_call_observed")
    current_binding = {
        "case_id": current.case_id,
        "case_version": current.case_version,
        "as_of": current.input_pack.as_of,
        "decision_surface_contract_ref": current.decision_surface_contract_ref,
        "execution_identity": current.execution_identity,
        "work_unit_id": current.work_unit_id,
        "attempt_id": current.attempt_id,
        "research_run_id": current.research_run_id,
        "input_digest": current.input_digest,
        "preparation_digest": current.preparation_digest,
    }
    if current_binding != expected_frozen:
        raise RuntimeError("s3_t09_current_exact_input_or_identity_drift")
    after = _read_only_execution_rows(runtime_root, str(admission.case_id))
    if before != after or _target_execution_exists_in_rows(after, target):
        raise RuntimeError("s3_t09_preflight_created_execution_state")
    if not admission.api_key_env or not os.environ.get(admission.api_key_env):
        raise RuntimeError("s3_t09_provider_credential_missing")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=lambda **_: {}
    )
    max_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    output_only_cost_ceiling_usd = (
        max_output_tokens * admission.output_usd_per_million / 1_000_000
    )
    if (
        max_output_tokens != target.maximum_output_tokens
        or output_only_cost_ceiling_usd >= admission.max_total_cost_usd
    ):
        raise RuntimeError("s3_t09_output_budget_invalid")
    result = {
        "status": "pass_exact_zero_call_execution_preflight",
        "runtime_root": str(runtime_root),
        "admission_id": admission.admission_id,
        "admission_digest": canonical_digest(admission.digest_payload()),
        **current_binding,
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
        "provider_health_probe_performed": False,
        "transport_retries": 0,
        "maximum_semantic_model_calls": admission.max_semantic_model_calls,
        "maximum_provider_calls": admission.max_provider_calls,
        "maximum_network_calls": admission.max_network_calls,
        "maximum_output_tokens": max_output_tokens,
        "output_only_cost_ceiling_usd": round(output_only_cost_ceiling_usd, 8),
        "maximum_total_cost_usd": admission.max_total_cost_usd,
        "source_network_calls_allowed": admission.source_network_calls_allowed,
        "external_tool_calls_allowed": admission.external_tool_calls_allowed,
        "live_business_case_head_writes_allowed": (
            admission.live_business_case_head_writes_allowed
        ),
        "execution_state_counts_before": {
            table: len(rows) for table, rows in before.items()
        },
        "execution_state_counts_after": {
            table: len(rows) for table, rows in after.items()
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
    }
    _write_json(
        runtime_root / _output_name("live_execution_preflight.json", output_prefix),
        result,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def execute(
    runtime_root: Path,
    admission_path: Path,
    *,
    chat_completion_fn: Callable[..., Mapping[str, Any]] | None = None,
    target: S3T09ExecutionTarget = LEGACY_TARGET,
    output_prefix: str | None = None,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    preflight_result = preflight(
        runtime_root, admission_path, target, output_prefix=output_prefix
    )
    admission = _load_admission(admission_path, target)
    os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = str(
        (runtime_root / "gateway_events.jsonl").resolve()
    )
    case_service, local_service, evidence_service = _services(runtime_root)
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=chat_completion_fn
    )
    app = create_app(
        runtime_root / "workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
        s3_three_cell_bounded_agent_admission=admission,
        s3_three_cell_bounded_agent_executor=executor,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/cases/{admission.case_id}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                "expected_case_version": admission.case_version,
                "input_head_digest": canonical_digest(
                    (target.decision_surface_ref,)
                ),
                "actor_ref": ACTOR_ID,
                "idempotency_key": target.execution_identity,
            },
        )
        if response.status_code != 202:
            raise RuntimeError(
                f"s3_t09_work_unit_create_failed:{response.status_code}:{response.text}"
            )

    store = case_service._facade.store
    work_unit = store.get_latest("canonical_work_units", target.work_unit_id)
    attempt = store.get_latest("canonical_attempts", target.attempt_id)
    run = store.get_latest(
        "canonical_research_run_versions", target.research_run_id
    )
    if not work_unit or not attempt or not run:
        raise RuntimeError("s3_t09_terminal_execution_identity_missing")
    states = {
        "work_unit_state": str(work_unit.get("state") or ""),
        "attempt_state": str(attempt.get("state") or ""),
        "research_run_state": str(run.get("state") or ""),
    }
    if states["research_run_state"] not in TERMINAL_STATES or len(set(states.values())) != 1:
        raise RuntimeError("s3_t09_execution_not_consistently_terminal")

    runtime_materialization_findings: list[dict[str, Any]] = []
    artifact_rows = [
        row
        for row in store.list_latest(
            "canonical_artifact_versions", case_id=str(admission.case_id)
        )
        if row.get("producer_attempt_id") == target.attempt_id
    ]
    artifact_payloads: dict[str, Any] = {}
    for row in artifact_rows:
        artifact_type = str(row["artifact_type"])
        try:
            artifact_payloads[artifact_type] = (
                case_service._facade.object_store.get_json(
                    str(row["object_key"]),
                    expected_digest=str(row["object_digest"]),
                )
            )
        except Exception as exc:
            runtime_materialization_findings.append(
                {
                    "phase": "artifact_readback",
                    "code": "artifact_payload_readback_failed",
                    "artifact_type": artifact_type,
                    "exception_type": type(exc).__name__,
                    "canonical_truth_unchanged": True,
                }
            )
    events = case_service._facade.list_events(target.research_run_id)
    terminal_event = next(
        (
            row
            for row in reversed(events)
            if row.get("event_type")
            in {"RESEARCH_RUN_COMPLETED", "RESEARCH_RUN_FAILED"}
        ),
        None,
    )
    capture_event = next(
        (
            row
            for row in reversed(events)
            if row.get("event_type")
            == "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED"
        ),
        None,
    )
    failure_event = next(
        (row for row in reversed(events) if row.get("event_type") == "RESEARCH_RUN_FAILED"),
        None,
    )
    failure_observation = (
        (failure_event.get("payload") or {}).get("failure_observation")
        if isinstance(failure_event, Mapping)
        else None
    )
    manifest = artifact_payloads.get("bounded_agent_manifest")
    source = manifest if isinstance(manifest, Mapping) else failure_observation
    source = source if isinstance(source, Mapping) else {}
    terminal_payload = (
        terminal_event.get("payload")
        if isinstance(terminal_event, Mapping)
        and isinstance(terminal_event.get("payload"), Mapping)
        else {}
    )
    capture_event_payload = (
        capture_event.get("payload")
        if isinstance(capture_event, Mapping)
        and isinstance(capture_event.get("payload"), Mapping)
        else {}
    )
    capture_payload = (
        capture_event_payload
        if capture_event_payload.get("provider_output_capture_refs")
        else terminal_payload
    )
    capture_refs = capture_payload.get("provider_output_capture_refs") or []
    if not isinstance(capture_refs, list):
        runtime_materialization_findings.append(
            {
                "phase": "provider_output_capture",
                "code": "provider_output_capture_refs_invalid",
                "canonical_truth_unchanged": True,
            }
        )
        capture_refs = []
    try:
        capture_audit = (
            case_service._facade.read_research_run_provider_output_captures(
                target.research_run_id
            )
            if capture_refs
            else ()
        )
    except Exception as exc:
        capture_audit = ()
        runtime_materialization_findings.append(
            {
                "phase": "provider_output_capture",
                "code": "provider_output_capture_readback_failed",
                "exception_type": type(exc).__name__,
                "canonical_truth_unchanged": True,
            }
        )
    if len(capture_audit) != len(capture_refs):
        runtime_materialization_findings.append(
            {
                "phase": "provider_output_capture",
                "code": "provider_output_capture_readback_mismatch",
                "declared_count": len(capture_refs),
                "restricted_readback_count": len(capture_audit),
                "canonical_truth_unchanged": True,
            }
        )
    capture_summary = {
        "policy_ref": capture_payload.get(
            "provider_output_capture_policy_ref"
        ),
        "capture_count": len(capture_refs),
        "restricted_readback_count": len(capture_audit),
        "assistant_output_present_count": sum(
            bool(row.get("assistant_output_present")) for row in capture_refs
        ),
        "capture_sequences": [
            int(row.get("capture_sequence") or 0) for row in capture_refs
        ],
        "stages": [str(row.get("stage") or "") for row in capture_refs],
        "call_ids": [str(row.get("call_id") or "") for row in capture_refs],
        "object_digests": [
            str(row.get("object_digest") or "") for row in capture_refs
        ],
        "assistant_output_text_in_runtime_result": False,
    }
    if (
        capture_refs
        and capture_summary["policy_ref"]
        != admission.provider_output_capture_policy_ref
    ):
        runtime_materialization_findings.append(
            {
                "phase": "provider_output_capture",
                "code": "provider_output_capture_policy_mismatch",
                "expected_policy_ref": (
                    admission.provider_output_capture_policy_ref
                ),
                "observed_policy_ref": capture_summary["policy_ref"],
                "canonical_truth_unchanged": True,
            }
        )
    receipts = [
        dict(row)
        for row in source.get("usage_receipts", ())
        if isinstance(row, Mapping)
    ]
    token_totals = {
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in receipts),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in receipts),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in receipts),
    }
    terminal_succeeded = states["research_run_state"] == "succeeded"
    artifact_types = sorted(artifact_payloads)
    if terminal_succeeded and set(artifact_types) != set(BOUNDED_AGENT_ARTIFACT_TYPES):
        runtime_materialization_findings.append(
            {
                "phase": "artifact_readback",
                "code": "terminal_success_artifact_set_incomplete",
                "canonical_truth_unchanged": True,
            }
        )
    if not terminal_succeeded and artifact_rows:
        runtime_materialization_findings.append(
            {
                "phase": "artifact_readback",
                "code": "terminal_failure_artifacts_present",
                "canonical_truth_unchanged": True,
            }
        )

    result = {
        "schema_version": "fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution_runtime_v1_0",
        "status": (
            (
                "terminal_succeeded_admission_consumed_no_retry"
                if not runtime_materialization_findings
                else (
                    "terminal_succeeded_admission_consumed_no_retry_"
                    "runtime_materialization_findings"
                )
            )
            if terminal_succeeded
            else (
                "terminal_failed_admission_consumed_no_retry"
                if not runtime_materialization_findings
                else (
                    "terminal_failed_admission_consumed_no_retry_"
                    "runtime_materialization_findings"
                )
            )
        ),
        "preflight": preflight_result,
        "identity": {
            "admission_id": admission.admission_id,
            "admission_digest": canonical_digest(admission.digest_payload()),
            "work_unit_idempotency_key": target.execution_identity,
            "case_id": admission.case_id,
            "case_version": admission.case_version,
            "input_digest": admission.input_digest,
            "work_unit_id": target.work_unit_id,
            "attempt_id": target.attempt_id,
            "research_run_id": target.research_run_id,
        },
        "canonical_terminal_truth": {
            **states,
            "terminal_reason": run.get("terminal_reason"),
            "artifact_count": len(artifact_rows),
            "artifact_types": artifact_types,
            "event_count": len(events),
            "orphaned_run": False,
        },
        "provider_execution": {
            "provider": admission.provider,
            "model": admission.model,
            "transport_ref": admission.transport_ref,
            "research_lead_transport_ref": admission.research_lead_transport_ref,
            "memo_writer_transport_ref": admission.memo_writer_transport_ref,
            "observed_counts": source.get("observed_counts"),
            "usage_receipts": receipts,
            **token_totals,
            "estimated_cost_usd": round(
                sum(float(row.get("estimated_cost_usd") or 0.0) for row in receipts),
                8,
            ),
            "retry_count": 0,
            "fallback_count": 0,
            "rerun_count": 0,
            "provider_output_capture": capture_summary,
        },
        "boundary_observation": {
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "live_business_case_head_writes": 0,
            "raw_provider_response_persisted": False,
            "assistant_final_output_text_persisted_restricted": bool(capture_refs),
            "assistant_final_output_text_persisted_count": len(capture_refs),
            "assistant_final_output_text_written_to_runtime_result": False,
            "private_chain_of_thought_persisted": False,
            "credential_value_persisted": False,
        },
        "failure_observation": failure_observation,
        "runtime_materialization_findings": runtime_materialization_findings,
        "artifact_payloads": artifact_payloads,
    }
    _write_json(
        runtime_root / _output_name("live_execution_result.json", output_prefix), result
    )
    print(json.dumps({**result, "artifact_payloads": {}}, ensure_ascii=False, indent=2))
    return result


def inspect(
    runtime_root: Path,
    target: S3T09ExecutionTarget = LEGACY_TARGET,
    *,
    output_prefix: str | None = None,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    rows = _read_only_execution_rows(runtime_root, target.case_id)

    def exact(table: str, logical_id: str) -> dict[str, Any] | None:
        return next(
            (row for row in rows[table] if row.get("_logical_id") == logical_id),
            None,
        )

    work_unit = exact("canonical_work_units", target.work_unit_id)
    attempt = exact("canonical_attempts", target.attempt_id)
    run = exact("canonical_research_run_versions", target.research_run_id)
    artifacts = [
        row
        for row in rows["canonical_artifact_versions"]
        if row.get("producer_attempt_id") == target.attempt_id
    ]
    result = {
        "status": "inspected_no_provider_call",
        "identity": {
            "work_unit_id": target.work_unit_id,
            "attempt_id": target.attempt_id,
            "research_run_id": target.research_run_id,
        },
        "counts": {
            "canonical_work_units": int(work_unit is not None),
            "canonical_attempts": int(attempt is not None),
            "canonical_research_run_versions": int(run is not None),
            "canonical_artifact_versions": len(artifacts),
        },
        "work_unit_state": work_unit.get("state") if work_unit else None,
        "attempt_state": attempt.get("state") if attempt else None,
        "research_run_state": run.get("state") if run else None,
        "additional_model_provider_network_calls": [0, 0, 0],
    }
    _write_json(
        runtime_root
        / _output_name("live_execution_terminal_inspection.json", output_prefix),
        result,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _output_name(default_name: str, output_prefix: str | None) -> str:
    if output_prefix is None:
        return default_name
    if not OUTPUT_PREFIX_PATTERN.fullmatch(output_prefix):
        raise RuntimeError("s3_t09_output_prefix_invalid")
    return f"{output_prefix}_{default_name}"


def _assert_supervised_cli_execution() -> None:
    supervision_root_value = str(
        os.environ.get("FIN_IA_S3_T09_SUPERVISION_ROOT") or ""
    ).strip()
    contract_ref = str(
        os.environ.get("FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF") or ""
    ).strip()
    if (
        not supervision_root_value
        or contract_ref != "fin01.s3.exact_run_supervision:v2"
    ):
        raise RuntimeError("s3_t09_exact_execute_requires_supervised_lifecycle")
    launch_path = Path(supervision_root_value).resolve() / "launch_receipt.json"
    launch_deadline = time.monotonic() + 5
    while not launch_path.exists() and time.monotonic() < launch_deadline:
        time.sleep(0.02)
    if not launch_path.exists():
        raise RuntimeError("s3_t09_supervision_launch_receipt_missing")
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
        current_process_identity,
        process_identity_matches,
    )

    host_binding = launch.get("host_capability_binding") or {}
    host_receipt_ref = str(host_binding.get("receipt_ref") or "").strip()
    host_receipt_path = (
        Path(host_receipt_ref).resolve() if host_receipt_ref else None
    )
    if (
        launch.get("contract_ref") != contract_ref
        or launch.get("process_topology")
        != "direct_actual_runner_no_intermediate_wrapper"
        or int(launch.get("runner_pid") or 0) != os.getpid()
        or not process_identity_matches(
            launch.get("runner_process_identity") or {},
            current_process_identity(),
        )
        or launch.get("parent_enforced_timeout_seconds") is not None
        or launch.get("parent_may_terminate_child") is not False
        or launch.get("monitoring_contract")
        != "read_only_no_signal_no_retry_no_relaunch"
        or launch.get("automatic_retry_count") != 0
        or launch.get("fallback_count") != 0
        or launch.get("replay_count") != 0
        or launch.get("relaunch_count") != 0
        or host_receipt_path is None
        or not host_receipt_path.exists()
        or hashlib.sha256(host_receipt_path.read_bytes()).hexdigest()
        != host_binding.get("receipt_sha256")
    ):
        raise RuntimeError("s3_t09_supervision_launch_contract_invalid")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the exact-once FIN 0.1 S3-T09 DeepSeek three-cell admission."
    )
    parser.add_argument("mode", choices=("preflight", "execute", "inspect"))
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--admission",
        type=Path,
        default=None,
    )
    parser.add_argument("--issuance", type=Path, default=None)
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Optional safe filename prefix that preserves prior runtime evidence.",
    )
    args = parser.parse_args()
    target = (
        load_execution_target(args.issuance.resolve())
        if args.issuance is not None
        else LEGACY_TARGET
    )
    runtime_root = args.runtime_root or ROOT / target.runtime_root_ref
    admission_path = args.admission or ROOT / target.admission_ref
    if args.mode == "preflight":
        preflight(
            runtime_root,
            admission_path.resolve(),
            target,
            output_prefix=args.output_prefix,
        )
    elif args.mode == "execute":
        _assert_supervised_cli_execution()
        execute(
            runtime_root,
            admission_path.resolve(),
            target=target,
            output_prefix=args.output_prefix,
        )
    else:
        inspect(runtime_root, target, output_prefix=args.output_prefix)
    return 0


def _entrypoint() -> int:
    exit_code = 1
    failure_code: str | None = None
    try:
        exit_code = int(main())
        return exit_code
    except BaseException as exc:
        failure_code = f"unhandled_{type(exc).__name__}"
        traceback.print_exc()
        exit_code = 1
        return exit_code
    finally:
        if str(
            os.environ.get("FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF") or ""
        ).strip() == "fin01.s3.exact_run_supervision:v2":
            from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
                finalize_supervised_process,
            )

            finalize_supervised_process(
                exit_code,
                failure_code=failure_code or (
                    "process_exit_nonzero" if exit_code else None
                ),
            )


if __name__ == "__main__":
    raise SystemExit(_entrypoint())
