from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF,
    BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
    BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF,
    BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME,
    CONSUMED_BOUNDED_AGENT_ADMISSION_IDS,
    BoundedAgentAdmission,
    build_bounded_agent_executor_for_admission,
    build_bounded_agent_input_pack,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.local_research_service import P36LocalResearchService
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now


TENANT_ID = "tenant-fin01-s2-t03-eval"
PROJECT_ID = "project-fin01-s2-t03-eval"
ACTOR_ID = "analyst-fin01-s2-t03-eval"
PERMISSIONS = frozenset(
    (
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    )
)
CONSUMED_WORK_UNIT_IDEMPOTENCY_KEYS = frozenset(
    {
        "fin01-s2-t03-bounded-agent-work-unit-v1",
        "fin01-s2-t03-bounded-agent-work-unit-v2-contract-r1",
        "fin01-s2-t03-bounded-agent-work-unit-v3-contract-r1",
        "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1",
        "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r2",
        "fin01-s2-t03-bounded-agent-work-unit-native-json-schema-gpt-5-6-sol-r1",
        "fin01-s2-t03-bounded-agent-work-unit-native-json-schema-gpt-5-6-sol-r2",
        "fin01-s2-t03-bounded-agent-work-unit-deepseek-segmented-v4-r1",
    }
)
R2_ADMISSION_ID = "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2"
R2_WORK_UNIT_IDEMPOTENCY_KEY = (
    "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r2"
)
R2_ORPHANED_TERMINAL_REASON = (
    "bounded_agent_profile_error:BoundedAgentExecutionInterrupted:"
    "canonical_terminalization_gap_after_specialist_provider_call"
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


def _accepted_case(client: TestClient) -> tuple[dict[str, Any], dict[str, Any]]:
    created = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "分析 NVDA 需求真实性与持续性",
            "as_of": "2026-07-20T00:00:00Z",
            "language": "zh-CN",
            "source_policy_ref": "local_official_only",
            "idempotency_key": "fin01-s2-t03-evaluation-case-v1",
        },
    )
    if created.status_code != 202:
        raise RuntimeError(f"case_prepare_failed:{created.status_code}:{created.text}")
    case = created.json()
    compiled = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/compile",
        headers=_headers(),
        json={
            "expected_case_version": case["case_version"],
            "expected_summary_version": case["summary_version"],
            "compiler_policy_ref": "fixture:p36-three-cell-v1",
            "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
            "actor_ref": ACTOR_ID,
            "idempotency_key": "fin01-s2-t03-evaluation-compile-v1",
        },
    )
    if compiled.status_code != 202:
        raise RuntimeError(f"planning_compile_failed:{compiled.status_code}:{compiled.text}")
    plan = compiled.json()
    accepted = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": plan["contract_version"],
            "expected_checkpoint_version": plan["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": "fin01-s2-t03-evaluation-accept-v1",
        },
    )
    if accepted.status_code != 202:
        raise RuntimeError(f"planning_accept_failed:{accepted.status_code}:{accepted.text}")
    return case, accepted.json()


def prepare(runtime_root: Path) -> dict[str, Any]:
    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    app = create_app(
        runtime_root / "workbench.sqlite", p02_case_service=case_service
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client)
    local = P36LocalResearchService.from_case_service(case_service, repo_root=ROOT)
    pack = build_bounded_agent_input_pack(local, case["case_id"], _principal())
    result = {
        "status": "prepared_no_model_call",
        "runtime_root": str(runtime_root.resolve()),
        "case_id": pack.case_id,
        "case_version": pack.case_version,
        "as_of": pack.as_of,
        "query": pack.query,
        "input_digest": pack.input_digest,
        "source_preview_digest": pack.source_preview_digest,
        "deterministic_analysis_digest": pack.deterministic_analysis_digest,
        "candidate_count": len(pack.candidates),
        "contract_version_id": plan["contract_version_id"],
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
        },
    }
    _write_json(runtime_root / "prepared_input.json", result)
    return result


def preflight(
    runtime_root: Path,
    admission_path: Path,
    *,
    work_unit_idempotency_key: str,
) -> dict[str, Any]:
    """Validate the exact bounded admission without making a provider call."""

    admission = BoundedAgentAdmission.model_validate(
        json.loads(admission_path.read_text(encoding="utf-8"))
    )
    admission.assert_profile_admissible()
    if not admission.execution_enabled:
        raise RuntimeError("t03_exact_admission_not_enabled")
    if admission.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS:
        raise RuntimeError("t03_consumed_admission_reuse_forbidden")
    if work_unit_idempotency_key in CONSUMED_WORK_UNIT_IDEMPOTENCY_KEYS:
        raise RuntimeError("t03_consumed_work_unit_identity_reuse_forbidden")
    if (
        admission.specialist_output_contract_ref
        != BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    ):
        raise RuntimeError("t03_specialist_output_contract_v4_required")
    try:
        admission.assert_specialist_transport_binding()
    except ValueError as exc:
        if str(exc) == "bounded_specialist_strict_tool_provider_binding_required":
            raise RuntimeError("t03_strict_tool_provider_binding_required") from exc
        raise RuntimeError(f"t03_specialist_transport_binding_invalid:{exc}") from exc
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise RuntimeError("LLM_GATEWAY_TRANSPORT_RETRIES_must_be_0")
    credential_present = bool(
        admission.api_key_env and os.environ.get(admission.api_key_env)
    )
    if not credential_present:
        raise RuntimeError("t03_provider_credential_missing")

    prepared = json.loads(
        (runtime_root / "prepared_input.json").read_text(encoding="utf-8")
    )
    exact = {
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "as_of": admission.as_of,
        "input_digest": admission.input_digest,
    }
    if exact != {key: prepared[key] for key in exact}:
        raise RuntimeError("t03_admission_prepared_input_mismatch")

    max_output_tokens = sum(
        (
            admission.specialist_max_output_tokens,
            admission.lead_max_output_tokens,
            admission.writer_max_output_tokens,
            admission.verifier_max_output_tokens,
        )
    )
    output_only_cost_ceiling_usd = (
        max_output_tokens * admission.output_usd_per_million / 1_000_000
    )
    if output_only_cost_ceiling_usd >= admission.max_total_cost_usd:
        raise RuntimeError("t03_output_budget_exhausts_total_cost_cap")
    result = {
        "status": "pass_no_model_call",
        "admission_id": admission.admission_id,
        "admission_digest": canonical_digest(admission.digest_payload()),
        "work_unit_idempotency_key": work_unit_idempotency_key,
        "exact_input_match": True,
        "candidate_count": int(prepared["candidate_count"]),
        "credential_present": credential_present,
        "credential_value_persisted": False,
        "transport_retries": 0,
        "max_semantic_model_calls": admission.max_semantic_model_calls,
        "max_provider_calls": admission.max_provider_calls,
        "max_network_calls": admission.max_network_calls,
        "max_output_tokens": max_output_tokens,
        "output_only_cost_ceiling_usd": round(output_only_cost_ceiling_usd, 8),
        "max_total_cost_usd": admission.max_total_cost_usd,
        "source_network_calls_allowed": admission.source_network_calls_allowed,
        "external_tool_calls_allowed": admission.external_tool_calls_allowed,
        "live_business_case_head_writes_allowed": admission.live_business_case_head_writes_allowed,
        "provider_health_check": "first_admitted_semantic_call_fail_closed_no_extra_probe",
        "specialist_output_transport_ref": admission.resolved_specialist_transport_ref(),
        "specialist_output_tool_name": (
            BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
            if admission.resolved_specialist_transport_ref()
            not in {
                BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF,
                BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF,
            }
            else None
        ),
        "reasoning_effort": admission.reasoning_effort,
        "specialist_strict_schema_requested": (
            admission.resolved_specialist_transport_ref()
            != BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF
        ),
        "specialist_external_tool_execution_allowed": False,
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
        },
    }
    _write_json(runtime_root / "execution_preflight.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def execute(
    runtime_root: Path,
    admission_path: Path,
    *,
    work_unit_idempotency_key: str,
) -> dict[str, Any]:
    admission = BoundedAgentAdmission.model_validate(
        json.loads(admission_path.read_text(encoding="utf-8"))
    )
    admission.assert_profile_admissible()
    if not admission.execution_enabled:
        raise RuntimeError("t03_exact_admission_not_enabled")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise RuntimeError("LLM_GATEWAY_TRANSPORT_RETRIES_must_be_0")
    if not admission.api_key_env or not os.environ.get(admission.api_key_env):
        raise RuntimeError("t03_provider_credential_missing")
    os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = str(
        (runtime_root / "gateway_events.jsonl").resolve()
    )

    prepared_path = runtime_root / "prepared_input.json"
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    exact = {
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "as_of": admission.as_of,
        "input_digest": admission.input_digest,
    }
    if exact != {key: prepared[key] for key in exact}:
        raise RuntimeError("t03_admission_prepared_input_mismatch")

    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    local = P36LocalResearchService.from_case_service(case_service, repo_root=ROOT)
    current_pack = build_bounded_agent_input_pack(
        local, str(admission.case_id), _principal()
    )
    if current_pack.input_digest != admission.input_digest:
        raise RuntimeError("t03_current_input_digest_mismatch")
    planning = [
        row
        for row in case_service._facade.store.list_latest(
            "canonical_planning_checkpoint_versions", case_id=str(admission.case_id)
        )
        if row.get("review_status") == "accepted"
    ]
    if len(planning) != 1:
        raise RuntimeError("t03_exact_accepted_planning_checkpoint_required")
    contract_version_id = str(planning[0]["contract_version_id"])

    app = create_app(
        runtime_root / "workbench.sqlite",
        p02_case_service=case_service,
        p36_local_research_service=local,
        bounded_agent_admission=admission,
        bounded_agent_executor=build_bounded_agent_executor_for_admission(admission),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/cases/{admission.case_id}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                "expected_case_version": admission.case_version,
                "input_head_digest": canonical_digest((contract_version_id,)),
                "actor_ref": ACTOR_ID,
                "idempotency_key": work_unit_idempotency_key,
            },
        )
        if response.status_code != 202:
            raise RuntimeError(f"t03_work_unit_create_failed:{response.status_code}:{response.text}")
        run = _wait_for_bounded_terminal_run(
            client,
            case_id=str(admission.case_id),
            execution_profile_version_ref=admission.execution_profile_version_ref,
        )
    failure_event = next(
        (
            row
            for row in reversed(run.get("events") or ())
            if row.get("event_type") == "RESEARCH_RUN_FAILED"
        ),
        None,
    )
    failure_observation = (
        (failure_event.get("details") or {}).get("failure_observation")
        if isinstance(failure_event, dict)
        else None
    )
    manifest = next(
        (
            row.get("payload")
            for row in run.get("artifacts", ())
            if row.get("artifact_type") == "bounded_agent_manifest"
        ),
        None,
    )
    result = {
        "status": "completed" if run.get("state") == "succeeded" else "failed",
        "admission_path": str(admission_path.resolve()),
        "admission_digest": canonical_digest(admission.digest_payload()),
        "work_unit_idempotency_key": work_unit_idempotency_key,
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "input_digest": admission.input_digest,
        "research_run_id": run.get("research_run_id"),
        "attempt_id": run.get("attempt_id"),
        "run_state": run.get("state"),
        "terminal_reason": run.get("terminal_reason"),
        "artifact_version_ids": run.get("output_refs") or [],
        "artifact_types": [row.get("artifact_type") for row in run.get("artifacts", ())],
        "observed_counts": (manifest or {}).get("observed_counts"),
        "estimated_cost_usd": (manifest or {}).get("estimated_cost_usd"),
        "usage_receipts": (manifest or {}).get("usage_receipts"),
        "failure_observation": failure_observation,
        "private_chain_of_thought_included": False,
        "raw_provider_response_persisted": False,
    }
    _write_json(runtime_root / "first_run_result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if run.get("state") != "succeeded":
        raise RuntimeError(f"t03_run_failed:{run.get('terminal_reason')}")
    return result


def _wait_for_bounded_terminal_run(
    client: TestClient,
    *,
    case_id: str,
    execution_profile_version_ref: str,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 0.25,
) -> dict[str, Any]:
    """Wait for canonical terminal truth after the asynchronous HTTP 202 admission."""

    deadline = time.monotonic() + timeout_seconds
    last_state: str | None = None
    while time.monotonic() <= deadline:
        projection = client.get(
            f"/api/v1/cases/{case_id}/execution-projection",
            headers=_headers(),
        )
        if projection.status_code != 200:
            raise RuntimeError(
                f"t03_projection_failed:{projection.status_code}:{projection.text}"
            )
        bounded_runs = [
            row
            for row in projection.json()["runs"]
            if row.get("execution_profile_version_ref")
            == execution_profile_version_ref
        ]
        if len(bounded_runs) > 1:
            raise RuntimeError("t03_bounded_run_cardinality_violation")
        if bounded_runs:
            run = bounded_runs[0]
            last_state = str(run.get("state") or "")
            if last_state in {"succeeded", "failed", "cancelled"}:
                return run
        time.sleep(poll_interval_seconds)
    raise RuntimeError(f"t03_bounded_run_terminal_timeout:{last_state or 'not_started'}")


def _terminal_inspection_labels(
    run_state: str | None, persisted_counts: Any
) -> tuple[str, str | None]:
    if run_state == "succeeded":
        return "inspected_after_terminal_success", None
    if run_state in {"failed", "cancelled"}:
        return (
            "inspected_after_terminal_failure",
            None
            if persisted_counts is not None
            else "failure_preceded_safe_gateway_receipt_persistence",
        )
    return "inspected_before_terminal_state", None


def inspect(runtime_root: Path) -> dict[str, Any]:
    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    facade = case_service._facade
    work_units = [
        row
        for row in facade.store.list_latest("canonical_work_units")
        if row.get("work_unit_type") == BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE
    ]
    attempts = [
        row
        for row in facade.store.list_latest("canonical_attempts")
        if str(row.get("work_unit_id") or "")
        in {str(item.get("work_unit_id") or "") for item in work_units}
    ]
    runs = [
        row
        for row in facade.store.list_latest("canonical_research_run_versions")
        if row.get("execution_profile_version_ref")
        == "fin01.execution_profile.bounded_agent_internal:v1"
    ]
    artifacts = [
        row
        for row in facade.store.list_latest("canonical_artifact_versions")
        if str(row.get("producer_attempt_id") or "")
        in {str(item.get("attempt_id") or "") for item in attempts}
    ]
    run = runs[0] if len(runs) == 1 else {}
    failure_event = next(
        (
            row
            for row in reversed(facade.list_events(run.get("research_run_id")))
            if row.get("event_type") == "RESEARCH_RUN_FAILED"
        ),
        None,
    )
    failure_observation = (
        (failure_event.get("payload") or {}).get("failure_observation")
        if isinstance(failure_event, dict)
        else None
    )
    persisted_counts = (
        failure_observation.get("observed_counts")
        if isinstance(failure_observation, dict)
        else None
    )
    inspection_status, count_gap_reason = _terminal_inspection_labels(
        str(run.get("state") or "") or None, persisted_counts
    )
    result = {
        "status": inspection_status,
        "work_unit_count": len(work_units),
        "attempt_count": len(attempts),
        "research_run_count": len(runs),
        "artifact_count": len(artifacts),
        "work_unit_state": work_units[0].get("state") if len(work_units) == 1 else None,
        "attempt_state": attempts[0].get("state") if len(attempts) == 1 else None,
        "research_run_state": run.get("state"),
        "research_run_id": run.get("research_run_id"),
        "terminal_reason": run.get("terminal_reason"),
        "failure_codes": (
            failure_observation.get("failure_codes")
            if isinstance(failure_observation, dict)
            else None
        ),
        "persisted_model_provider_network_counts": persisted_counts,
        "estimated_cost_usd": (
            failure_observation.get("estimated_cost_usd")
            if isinstance(failure_observation, dict)
            else None
        ),
        "usage_receipts": (
            failure_observation.get("usage_receipts")
            if isinstance(failure_observation, dict)
            else None
        ),
        "output_shape": (
            failure_observation.get("output_shape")
            if isinstance(failure_observation, dict)
            else None
        ),
        "count_gap_reason": count_gap_reason,
        "rerun_performed": False,
        "fallback_performed": False,
    }
    _write_json(runtime_root / "first_run_terminal_inspection.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def close_orphaned_r2(
    runtime_root: Path,
    admission_path: Path,
    *,
    work_unit_idempotency_key: str,
) -> dict[str, Any]:
    """Close the exact r2 orphan without replaying or reconstructing provider output."""

    admission = BoundedAgentAdmission.model_validate(
        json.loads(admission_path.read_text(encoding="utf-8"))
    )
    if admission.admission_id != R2_ADMISSION_ID:
        raise RuntimeError("t03_orphan_closeout_exact_r2_admission_required")
    if admission.admission_id not in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS:
        raise RuntimeError("t03_orphan_closeout_consumed_admission_required")
    if work_unit_idempotency_key != R2_WORK_UNIT_IDEMPOTENCY_KEY:
        raise RuntimeError("t03_orphan_closeout_exact_r2_work_unit_key_required")
    if runtime_root.name != "fin01-s2-t03-v4-strict-tool-live-validation-r2":
        raise RuntimeError("t03_orphan_closeout_exact_r2_runtime_root_required")

    gateway_path = runtime_root / "gateway_events.jsonl"
    gateway_events = [
        json.loads(line)
        for line in gateway_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(gateway_events) != 2:
        raise RuntimeError("t03_orphan_closeout_gateway_event_cardinality_violation")
    started, finished = gateway_events
    expected_tags = {
        "admission_id": admission.admission_id,
        "input_digest": admission.input_digest,
        "research_run_id": "research_run_fin01_81e6277f9df729f23ab20140",
    }
    if (
        started.get("event_type") != "model_call_started"
        or finished.get("event_type") != "model_call_finished"
        or started.get("call_id") != finished.get("call_id")
        or started.get("trace_tags") != expected_tags
        or finished.get("trace_tags") != expected_tags
        or finished.get("status") != "ok"
        or finished.get("finish_reason") != "tool_calls"
        or int(finished.get("transport_attempt_count") or 0) != 1
    ):
        raise RuntimeError("t03_orphan_closeout_gateway_receipt_mismatch")

    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    facade = case_service._facade
    work_units = [
        row
        for row in facade.store.list_latest("canonical_work_units")
        if row.get("idempotency_key") == work_unit_idempotency_key
    ]
    if len(work_units) != 1:
        raise RuntimeError("t03_orphan_closeout_work_unit_cardinality_violation")
    work_unit = work_units[0]
    attempts = [
        row
        for row in facade.store.list_latest("canonical_attempts")
        if row.get("work_unit_id") == work_unit.get("work_unit_id")
    ]
    runs = [
        row
        for row in facade.store.list_latest("canonical_research_run_versions")
        if row.get("work_unit_id") == work_unit.get("work_unit_id")
    ]
    if len(attempts) != 1 or len(runs) != 1:
        raise RuntimeError("t03_orphan_closeout_execution_cardinality_violation")
    attempt, run = attempts[0], runs[0]
    exact_identity = {
        "work_unit_id": "wu_p02_5_a5a256b148228113b4583b3a",
        "attempt_id": "attempt_fin01_9537a9c63622cf56604af914",
        "research_run_id": "research_run_fin01_81e6277f9df729f23ab20140",
    }
    if {
        "work_unit_id": work_unit.get("work_unit_id"),
        "attempt_id": attempt.get("attempt_id"),
        "research_run_id": run.get("research_run_id"),
    } != exact_identity:
        raise RuntimeError("t03_orphan_closeout_execution_identity_mismatch")
    artifacts = [
        row
        for row in facade.store.list_latest("canonical_artifact_versions")
        if row.get("producer_attempt_id") == attempt.get("attempt_id")
    ]
    if artifacts:
        raise RuntimeError("t03_orphan_closeout_requires_zero_artifacts")

    states = (work_unit.get("state"), attempt.get("state"), run.get("state"))
    already_closed = states == ("failed", "failed", "failed")
    if already_closed:
        if run.get("terminal_reason") != R2_ORPHANED_TERMINAL_REASON:
            raise RuntimeError("t03_orphan_closeout_conflicting_terminal_truth")
    elif states != ("running", "running", "running"):
        raise RuntimeError("t03_orphan_closeout_requires_exact_running_orphan")
    else:
        run_events = facade.list_events(str(run["research_run_id"]))
        start_event = next(
            (row for row in run_events if row.get("event_type") == "RESEARCH_RUN_STARTED"),
            None,
        )
        if start_event is None:
            raise RuntimeError("t03_orphan_closeout_start_event_required")
        input_tokens = int(finished.get("input_tokens") or 0)
        output_tokens = int(finished.get("output_tokens") or 0)
        total_tokens = int(finished.get("total_tokens") or 0)
        if input_tokens + output_tokens != total_tokens:
            raise RuntimeError("t03_orphan_closeout_gateway_usage_mismatch")
        estimated_cost_usd = round(
            input_tokens * admission.input_cache_miss_usd_per_million / 1_000_000
            + output_tokens * admission.output_usd_per_million / 1_000_000,
            8,
        )
        command = CommandEnvelope(
            command_id="fin01_r2_orphan_closeout_"
            + canonical_digest(exact_identity)[:24],
            command_type="FAIL_RESEARCH_RUN",
            tenant_id=str(work_unit["tenant_id"]),
            project_id=str(work_unit["project_id"]),
            case_id=str(work_unit["case_id"]),
            actor_snapshot_ref=str(work_unit["actor_snapshot_ref"]),
            permission_snapshot_ref=str(work_unit["permission_snapshot_ref"]),
            policy_config_refs=tuple(attempt.get("policy_config_refs") or ()),
            idempotency_key=f"{work_unit_idempotency_key}:orphan-closeout:v1",
            expected_state_version=1,
            causation_event_id=str(start_event["event_id"]),
            correlation_id=str(work_unit["correlation_id"]),
            requested_at=utc_now(),
            payload={
                **exact_identity,
                "input_head_digest": str(attempt["input_head_digest"]),
                "lease_owner_ref": str(attempt["lease_owner_ref"]),
                "lease_fencing_token": int(attempt["lease_fencing_token"]),
                "failure_type": "bounded_agent_profile_execution_interrupted",
                "terminal_reason": R2_ORPHANED_TERMINAL_REASON,
                "failure_observation": {
                    "stage": "bounded_runtime_terminalization:orphaned_after_specialist_provider_call",
                    "failure_codes": [
                        "bounded_agent_canonical_terminalization_interrupted"
                    ],
                    "observed_counts": {
                        "model_calls": 1,
                        "provider_calls": 1,
                        "network_calls": 1,
                        "source_network_calls": 0,
                        "external_tool_calls": 0,
                    },
                    "estimated_cost_usd": estimated_cost_usd,
                    "usage_receipts": [
                        {
                            "stage": "bounded_specialist_and_lead",
                            "call_id": str(finished["call_id"]),
                            "provider": str(finished["provider"]),
                            "model": str(finished["model"]),
                            "status": str(finished["status"]),
                            "finish_reason": str(finished["finish_reason"]),
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens,
                            "estimated_cost_usd": estimated_cost_usd,
                            "latency_ms": int(finished["latency_ms"]),
                            "transport_attempt_count": int(
                                finished["transport_attempt_count"]
                            ),
                        }
                    ],
                    "private_reasoning_persisted": False,
                    "raw_provider_response_persisted": False,
                },
            },
        )
        facade.fail_research_run(command)

    closed_work_unit = facade.store.get_latest(
        "canonical_work_units", str(work_unit["work_unit_id"])
    )
    closed_attempt = facade.store.get_latest(
        "canonical_attempts", str(attempt["attempt_id"])
    )
    closed_run = facade.store.get_latest(
        "canonical_research_run_versions", str(run["research_run_id"])
    )
    post_gateway_events = [
        line
        for line in gateway_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    closed_failure_events = [
        row
        for row in facade.list_events(str(run["research_run_id"]))
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    ]
    closed_failure_observation = (
        (closed_failure_events[0].get("payload") or {}).get("failure_observation")
        if len(closed_failure_events) == 1
        else None
    )
    if (
        not closed_work_unit
        or not closed_attempt
        or not closed_run
        or (
            closed_work_unit.get("state"),
            closed_attempt.get("state"),
            closed_run.get("state"),
        )
        != ("failed", "failed", "failed")
        or closed_run.get("terminal_reason") != R2_ORPHANED_TERMINAL_REASON
        or not isinstance(closed_failure_observation, dict)
        or closed_failure_observation.get("failure_codes")
        != ["bounded_agent_canonical_terminalization_interrupted"]
        or len(post_gateway_events) != 2
    ):
        raise RuntimeError("t03_orphan_closeout_postcondition_failed")
    result = {
        "status": "already_closed" if already_closed else "closed_zero_call",
        "admission_id": admission.admission_id,
        "work_unit_id": closed_work_unit["work_unit_id"],
        "attempt_id": closed_attempt["attempt_id"],
        "research_run_id": closed_run["research_run_id"],
        "work_unit_state": closed_work_unit["state"],
        "attempt_state": closed_attempt["state"],
        "research_run_state": closed_run["state"],
        "terminal_reason": closed_run["terminal_reason"],
        "artifact_count": 0,
        "gateway_event_count_before": 2,
        "gateway_event_count_after": len(post_gateway_events),
        "additional_model_provider_network_calls": [0, 0, 0],
        "parse_subtype_reconstructed": False,
        "raw_provider_response_persisted": False,
        "rerun_performed": False,
        "fallback_performed": False,
    }
    _write_json(runtime_root / "orphan_closeout_result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("prepare", "preflight", "execute", "inspect", "close-orphaned")
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT / ".codex_runtime" / "fin01-s2-t03-bounded-first-run",
    )
    parser.add_argument("--admission", type=Path)
    parser.add_argument(
        "--work-unit-idempotency-key",
        default="fin01-s2-t03-bounded-agent-work-unit-v1",
        help="Exact execution identity key; a repair validation must not reuse the consumed v1 key.",
    )
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    if args.mode == "prepare":
        print(json.dumps(prepare(runtime_root), ensure_ascii=False, indent=2))
        return 0
    if args.mode == "inspect":
        inspect(runtime_root)
        return 0
    if args.mode == "close-orphaned":
        if args.admission is None:
            parser.error("--admission is required for close-orphaned")
        close_orphaned_r2(
            runtime_root,
            args.admission.resolve(),
            work_unit_idempotency_key=args.work_unit_idempotency_key,
        )
        return 0
    if args.admission is None:
        parser.error("--admission is required for preflight/execute")
    if args.mode == "preflight":
        preflight(
            runtime_root,
            args.admission.resolve(),
            work_unit_idempotency_key=args.work_unit_idempotency_key,
        )
        return 0
    execute(
        runtime_root,
        args.admission.resolve(),
        work_unit_idempotency_key=args.work_unit_idempotency_key,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
