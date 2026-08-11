from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

from fastapi.testclient import TestClient
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentAdmission,
    BoundedAgentExecutionError,
    BoundedAgentExecutionOutput,
    BoundedAgentInputPack,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
)
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from sec_agent.canonical_runtime.facade import (
    ArtifactValidationError,
    MissingDependency,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-s3-t09-capture"
PROJECT_ID = "project-fin01-s3-t09-capture"
ACTOR_ID = "analyst-fin01-s3-t09-capture"
PERMISSIONS = ",".join(
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
ORIGINAL_ASSISTANT_TEXT = (
    '{"judgment_layer":[{"epistemic_status":"cannot_infer",'
    '"support_fact_ids":["fact:conflict"],"cannot_support":[]}]} '
)


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": PERMISSIONS,
    }


def _accepted_case(
    client: TestClient, *, key: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    created = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "分析 NVDA 需求真实性与持续性",
            "as_of": "2026-07-22T00:00:00Z",
            "language": "zh-CN",
            "source_policy_ref": "local_official_only",
            "idempotency_key": f"{key}-case",
        },
    )
    assert created.status_code == 202, created.text
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
            "idempotency_key": f"{key}-compile",
        },
    )
    assert compiled.status_code == 202, compiled.text
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
            "idempotency_key": f"{key}-accept",
        },
    )
    assert accepted.status_code == 202, accepted.text
    return case, accepted.json()


def _create_work_unit(
    client: TestClient,
    case: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    key: str,
):
    return client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((plan["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )


def _capture(*, unsafe: bool = False) -> dict[str, Any]:
    return {
        "capture_policy_ref": S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        "capture_sequence": 1,
        "stage": "domain_specialist:value_and_profit_capture:owner_grade_claim_cards",
        "call_id": "call-capture-1",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "provider_status": "ok",
        "finish_reason": "stop",
        "assistant_output_text": ORIGINAL_ASSISTANT_TEXT,
        "assistant_output_present": True,
        "raw_provider_response_included": unsafe,
        "private_reasoning_included": False,
    }


class _CapturedFailureProbe:
    def __init__(
        self,
        *,
        unsafe: bool = False,
        unsafe_failure_code: bool = False,
        writer_telemetry: bool = False,
        verifier_telemetry: bool = False,
    ) -> None:
        self.unsafe = unsafe
        self.unsafe_failure_code = unsafe_failure_code
        self.writer_telemetry = writer_telemetry
        self.verifier_telemetry = verifier_telemetry

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        raise BoundedAgentExecutionError(
            "domain_specialist:value_and_profit_capture",
            usage_receipts=[],
            estimated_cost_usd=0.00941302,
            failure_codes=(
                (
                    "s3_owner_grade_epistemic_status_statement_conflict"
                    if self.unsafe_failure_code
                    else "s3_bounded_epistemic_status_statement_conflict"
                ),
            ),
            memo_writer_contract=(
                {
                    "validator_contract": "closed_memo_writer_output:v2",
                    "failure_family": "authority",
                    "failure_subtype": "claim_ref_invalid",
                    "field_id": "claim_renderings.claim_id",
                    "failing_item_count": 1,
                    "raw_text_persisted": False,
                    "ref_or_digest_persisted": False,
                    "item_index_persisted": False,
                    "arbitrary_key_names_persisted": False,
                    "private_reasoning_persisted": False,
                }
                if self.writer_telemetry
                else None
            ),
            verifier_state_machine=(
                {
                    "validator_contract": (
                        "fin01.s3.owner_grade_verifier_"
                        "output_state_machine:v1"
                    ),
                    "failure_subtype": "pass_with_nonempty_issue_codes",
                    "failing_layer_count": 4,
                    "nonempty_issue_layer_count": 4,
                    "nonempty_ref_layer_count": 4,
                    "raw_issue_codes_persisted": False,
                    "raw_refs_persisted": False,
                    "repair_owner_persisted": False,
                    "raw_output_persisted": False,
                    "private_reasoning_persisted": False,
                }
                if self.verifier_telemetry
                else None
            ),
            provider_output_captures=[_capture(unsafe=self.unsafe)],
        )


def _admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission(
        admission_id="fin01-s3-t09-provider-output-capture-probe-v1",
        execution_enabled=False,
        execution_mode="provider_output_capture_contract_probe",
    )


def test_failed_run_persists_exact_assistant_text_by_digest_and_event_ref(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "capture-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "capture.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CapturedFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="capture")
        response = _create_work_unit(
            client, case, plan, key="capture-bounded"
        )
    assert response.status_code == 202, response.text

    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    serialized_event = json.dumps(failed_event, ensure_ascii=False)
    assert ORIGINAL_ASSISTANT_TEXT not in serialized_event
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED"
        for row in case_service._facade.store.list_events()
    )
    assert failed_event["payload"]["provider_output_capture_policy_ref"] == (
        S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
    )
    refs = failed_event["payload"]["provider_output_capture_refs"]
    assert len(refs) == 1
    ref = refs[0]
    assert ref["stage"].endswith("owner_grade_claim_cards")
    assert ref["access_class"] == "internal_restricted_run_audit"
    assert ref["raw_provider_response_persisted"] is False
    assert ref["private_reasoning_persisted"] is False
    assert ref["object_key"].startswith("fin01/provider-output-captures/")

    replayed = case_service._facade.read_research_run_provider_output_captures(
        failed_event["task_run_id"]
    )
    assert len(replayed) == 1
    payload = replayed[0]
    assert payload["assistant_output_text"] == ORIGINAL_ASSISTANT_TEXT
    assert payload["research_run_id"] == failed_event["task_run_id"]
    assert payload["case_id"] == case["case_id"]
    assert payload["access_class"] == "internal_restricted_run_audit"
    assert "api_key" not in serialized_event.lower()


def test_invalid_failure_observation_rejects_before_atomic_capture(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "capture-before-terminal-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "capture-before-terminal.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CapturedFailureProbe(unsafe_failure_code=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="capture-before-terminal")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client, case, plan, key="capture-before-terminal-bounded"
            )

    events = case_service._facade.store.list_events()
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED"
        for row in events
    )
    assert not any(row.get("event_type") == "RESEARCH_RUN_FAILED" for row in events)
    run_id = str(
        case_service._facade.store.list_latest(
            "canonical_research_run_versions", case_id=case["case_id"]
        )[0]["research_run_id"]
    )
    with pytest.raises(
        MissingDependency, match="provider_output_capture_audit_event_required"
    ):
        case_service._facade.read_research_run_provider_output_captures(run_id)
    run = case_service._facade.store.get_latest(
        "canonical_research_run_versions", run_id
    )
    assert run is not None and run["state"] == "running"


def test_failure_transaction_rolls_back_capture_event_and_terminal_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "capture-rollback-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "capture-rollback.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CapturedFailureProbe(),
    )
    original_event = case_service._facade._event

    def fail_inside_transaction(*args: Any, **kwargs: Any):
        event_type = args[2] if len(args) > 2 else kwargs.get("event_type")
        if event_type == "RESEARCH_RUN_FAILED":
            raise RuntimeError("injected_failure_inside_atomic_terminalization")
        return original_event(*args, **kwargs)

    monkeypatch.setattr(case_service._facade, "_event", fail_inside_transaction)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="capture-rollback")
        with pytest.raises(
            RuntimeError, match="injected_failure_inside_atomic_terminalization"
        ):
            _create_work_unit(
                client, case, plan, key="capture-rollback-bounded"
            )

    events = case_service._facade.store.list_events()
    assert not any(
        row.get("event_type")
        in {"RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED", "RESEARCH_RUN_FAILED"}
        for row in events
    )
    work_unit = case_service._facade.store.list_latest(
        "canonical_work_units", case_id=case["case_id"]
    )[0]
    attempt = case_service._facade.store.list_latest(
        "canonical_attempts", case_id=case["case_id"]
    )[0]
    run = case_service._facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    assert [work_unit["state"], attempt["state"], run["state"]] == [
        "running",
        "running",
        "running",
    ]


def test_closed_writer_subtype_telemetry_reaches_canonical_terminal_failure(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "writer-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "writer-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CapturedFailureProbe(writer_telemetry=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="writer-telemetry")
        response = _create_work_unit(
            client, case, plan, key="writer-telemetry-bounded"
        )
    assert response.status_code == 202, response.text
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["memo_writer_contract"]
    assert telemetry["failure_subtype"] == "claim_ref_invalid"
    assert failed_event["payload"]["failure_observation"]["failure_codes"] == [
        "s3_bounded_epistemic_status_statement_conflict"
    ]


def test_closed_verifier_state_machine_telemetry_reaches_atomic_failure(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "verifier-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "verifier-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CapturedFailureProbe(verifier_telemetry=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="verifier-telemetry")
        response = _create_work_unit(
            client, case, plan, key="verifier-telemetry-bounded"
        )
    assert response.status_code == 202, response.text
    events = case_service._facade.store.list_events()
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED"
        for row in events
    )
    failed_event = next(
        row for row in events if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["verifier_state_machine"]
    assert telemetry["failure_subtype"] == "pass_with_nonempty_issue_codes"
    assert telemetry["failing_layer_count"] == 4
    assert "typed_issue" not in json.dumps(telemetry)
    assert "artifact:fixture" not in json.dumps(telemetry)
    assert len(failed_event["payload"]["provider_output_capture_refs"]) == 1


def test_capture_contract_rejects_raw_provider_envelope_before_failure_event(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-capture-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-capture.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=_CapturedFailureProbe(unsafe=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-capture")
        with pytest.raises(
            ArtifactValidationError,
            match="provider_output_capture_contract_invalid",
        ):
            _create_work_unit(
                client, case, plan, key="unsafe-capture-bounded"
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )
