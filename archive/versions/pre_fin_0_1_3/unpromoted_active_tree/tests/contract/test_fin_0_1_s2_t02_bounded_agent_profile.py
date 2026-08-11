from __future__ import annotations

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
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_PROFILE_REF,
    BoundedAgentAdmission,
    BoundedAgentArtifact,
    BoundedAgentExecutionError,
    BoundedAgentExecutionOutput,
    BoundedAgentInputPack,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
    ExecutionService,
    VT1_WORK_UNIT_TYPE,
)
from sec_agent.canonical_runtime.facade import ArtifactValidationError
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-s2-t02"
PROJECT_ID = "project-fin01-s2-t02"
ACTOR_ID = "analyst-fin01-s2-t02"
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


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": PERMISSIONS,
    }


def _accepted_case(client: TestClient, *, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    created = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "分析 NVDA 需求真实性与持续性",
            "as_of": "2026-07-20T00:00:00Z",
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
    work_unit_type: str,
):
    return client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": work_unit_type,
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((plan["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )


class _ZeroCallContractProbe:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.inputs: list[BoundedAgentInputPack] = []

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        self.inputs.append(input_pack)
        if self.fail:
            raise RuntimeError("t02_contract_probe_forced_failure")
        assert admission.execution_enabled is False
        observed_counts = {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "live_case_head_writes": 0,
        }
        hard_boundaries = {
            "candidate_is_evidence": 0,
            "graph_edge_is_evidence": 0,
            "writer_source_or_tool_calls": 0,
            "adapter_direct_canonical_writes": 0,
            "live_business_case_head_writes": 0,
            "release_admission": 0,
        }
        artifacts = []
        for artifact_type in BOUNDED_AGENT_ARTIFACT_TYPES:
            payload: dict[str, Any] = {
                "artifact_ref": f"logical:{artifact_type}",
                "profile_stage": "t02_zero_call_contract_probe",
                "input_digest": input_pack.input_digest,
                "quality_claim": "none_contract_path_only",
            }
            if artifact_type == BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE:
                payload.update(
                    {
                        "observed_counts": observed_counts,
                        "hard_boundaries": hard_boundaries,
                    }
                )
            if artifact_type == BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE:
                payload.update(
                    {
                        "paired_input_digest": input_pack.input_digest,
                        "deterministic_baseline": input_pack.deterministic_baseline,
                        "runs_must_be_distinct": True,
                        "material_gain_claim": "not_evaluated_in_t02",
                    }
                )
            artifacts.append(
                BoundedAgentArtifact(artifact_type=artifact_type, payload=payload)
            )
        return BoundedAgentExecutionOutput(
            terminal_reason="t02_zero_call_contract_probe_succeeded",
            artifacts=tuple(artifacts),
            trace_events=(
                {
                    "event_type": "BOUNDED_AGENT_T02_CONTRACT_PROBE_COMPLETED",
                    "event_payload": {
                        "input_digest": input_pack.input_digest,
                        "model_calls": 0,
                        "provider_calls": 0,
                        "network_calls": 0,
                    },
                },
            ),
        )


class _V4ShapeFailureProbe:
    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        raise BoundedAgentExecutionError(
            "bounded_specialist_and_lead:contract_validation_failed",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=("bounded_agent_specialist_result_keys_unexpected",),
            output_shape={
                "outer_key_count": 1,
                "expected_outer_keys_present": ["result"],
                "missing_outer_keys": [],
                "unexpected_outer_key_count": 0,
                "unexpected_outer_keys_digest": None,
                "recognized_wrapper_keys_present": ["result"],
                "expected_outer_value_types": {"result": "dict"},
                "result_key_count": 4,
                "expected_result_keys_present": [
                    "lead_adjudication",
                    "output_contract_ref",
                    "specialist_judgment",
                ],
                "missing_result_keys": [],
                "unexpected_result_key_count": 1,
                "unexpected_result_keys_digest": "a" * 64,
                "expected_result_value_types": {
                    "lead_adjudication": "dict",
                    "output_contract_ref": "str",
                    "specialist_judgment": "dict",
                },
            },
        )


class _StrictTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "bounded_specialist_and_lead:strict_tool_arguments_invalid_json",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=("bounded_agent_strict_tool_arguments_invalid_json",),
            strict_tool_parse_subtype="duplicate_key",
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "strict_tool_arguments"
            ]["raw_arguments"] = "secret-provider-arguments"
        raise error


class _SegmentedSpecialistShapeTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "domain_specialist:demand_authenticity_and_sustainability",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_segmented_specialist_shape_invalid:"
                "demand_authenticity_and_sustainability:"
                "facts_explanation_and_terminal",
            ),
            segmented_specialist_shape={
                "parser_contract": "closed_segment_top_level_shape:v1",
                "segment_id": "facts_explanation_and_terminal",
                "shape_subtype": "top_level_keys_unexpected",
                "missing_key_count": 0,
                "unexpected_key_count": 1,
                "raw_output_persisted": False,
                "arbitrary_key_names_persisted": False,
            },
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "segmented_specialist_shape"
            ]["observed_key_names"] = ["secret-provider-field"]
        raise error


class _SegmentedSpecialistTextTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "domain_specialist:demand_authenticity_and_sustainability",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_segmented_specialist_contract_invalid:"
                "demand_authenticity_and_sustainability:"
                "facts_explanation_and_terminal:"
                "s3_bounded_specialist_output_text_length_invalid:"
                "explanation_layer",
            ),
            segmented_specialist_text={
                "validator_contract": "closed_segment_narrative_text:v1",
                "segment_id": "facts_explanation_and_terminal",
                "field_id": "explanation_layer",
                "text_subtype": "item_over_max_unicode_characters",
                "failing_item_count": 1,
                "raw_text_persisted": False,
                "item_index_persisted": False,
                "arbitrary_key_names_persisted": False,
                "private_reasoning_persisted": False,
            },
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "segmented_specialist_text"
            ]["raw_text"] = "secret-provider-text"
        raise error


class _SegmentedSpecialistAuthorityTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "domain_specialist:demand_authenticity_and_sustainability",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_segmented_specialist_contract_invalid:"
                "demand_authenticity_and_sustainability:"
                "owner_grade_claim_cards:"
                "s3_owner_grade_claim_context_authority_invalid",
            ),
            segmented_specialist_authority={
                "validator_contract": "closed_segment_context_authority:v1",
                "segment_id": "owner_grade_claim_cards",
                "field_id": "judgment_layer.context_refs",
                "authority_subtype": "outside_current_cell_context_authority",
                "failing_item_count": 1,
                "raw_ref_persisted": False,
                "ref_digest_persisted": False,
                "item_index_persisted": False,
                "arbitrary_key_names_persisted": False,
                "private_reasoning_persisted": False,
            },
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "segmented_specialist_authority"
            ]["raw_ref"] = "secret-provider-ref"
        raise error


class _SegmentedSpecialistFactAuthorityTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "domain_specialist:value_and_profit_capture",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_segmented_specialist_contract_invalid:"
                "value_and_profit_capture:"
                "facts_explanation_and_terminal:"
                "s3_owner_grade_fact_support_authority_invalid",
            ),
            segmented_specialist_fact_authority={
                "validator_contract": "closed_fact_support_authority:v1",
                "segment_id": "facts_explanation_and_terminal",
                "field_id": "fact_layer.support_refs",
                "authority_subtype": (
                    "candidate_or_graph_ref_misclassified_as_fact"
                ),
                "failing_item_count": 1,
                "raw_ref_persisted": False,
                "ref_digest_persisted": False,
                "item_index_persisted": False,
                "arbitrary_key_names_persisted": False,
                "private_reasoning_persisted": False,
            },
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "segmented_specialist_fact_authority"
            ]["raw_ref"] = "secret-provider-fact-ref"
        raise error


class _SegmentedSpecialistEpistemicStatusTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "domain_specialist:demand_authenticity_and_sustainability",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_segmented_specialist_contract_invalid:"
                "demand_authenticity_and_sustainability:"
                "owner_grade_claim_cards:"
                "s3_owner_grade_epistemic_status_statement_conflict",
            ),
            segmented_specialist_epistemic_status={
                "validator_contract": "closed_claim_card_epistemic_status_state:v1",
                "segment_id": "owner_grade_claim_cards",
                "field_id": (
                    "judgment_layer.epistemic_status_support_fact_ids_"
                    "qualification_cannot_support"
                ),
                "status_subtype": "cannot_infer_has_support_fact_ids",
                "failing_item_count": 1,
                "raw_claim_persisted": False,
                "support_fact_ids_persisted": False,
                "cannot_support_text_persisted": False,
                "item_index_persisted": False,
                "arbitrary_key_names_persisted": False,
                "private_reasoning_persisted": False,
            },
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "segmented_specialist_epistemic_status"
            ]["raw_claim"] = "secret-provider-claim"
        raise error


class _ResearchLeadContractTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        error = BoundedAgentExecutionError(
            "research_lead",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_research_lead_v2_cardinality_above_maximum",
            ),
            research_lead_contract={
                "validator_contract": "closed_research_lead_output:v2",
                "failure_family": "cardinality",
                "failure_subtype": "above_maximum",
                "field_id": "remaining_gaps",
                "failing_item_count": 1,
                "raw_text_persisted": False,
                "ref_or_digest_persisted": False,
                "item_index_persisted": False,
                "arbitrary_key_names_persisted": False,
                "private_reasoning_persisted": False,
            },
        )
        if self.unsafe:
            error.failure_observation["failure_telemetry"][
                "research_lead_contract"
            ]["raw_text"] = "secret-provider-lead-text"
        raise error


class _ResearchLeadV3SemanticTelemetryFailureProbe:
    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: BoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        raise BoundedAgentExecutionError(
            "research_lead",
            usage_receipts=(),
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_research_lead_v3_semantic_"
                "fact_presence_summary_mismatch",
            ),
            research_lead_contract={
                "validator_contract": "closed_research_lead_output:v3",
                "failure_family": "semantic",
                "failure_subtype": "fact_presence_summary_mismatch",
                "field_id": (
                    "conflict_adjudications.fact_presence_summary"
                ),
                "failing_item_count": 1,
                "raw_text_persisted": False,
                "ref_or_digest_persisted": False,
                "item_index_persisted": False,
                "arbitrary_key_names_persisted": False,
                "private_reasoning_persisted": False,
            },
        )


def _t02_admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission(
        admission_id="fin01-s2-t02-zero-call-contract-probe-v1",
        execution_enabled=False,
        execution_mode="t02_zero_call_contract_probe",
    )


def test_t02_default_app_recognizes_but_does_not_admit_bounded_work_unit(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "default-runtime", repo_root=REPO_ROOT
    )
    app = create_app(tmp_path / "default.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="default-closed")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="default-closed-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "work_unit_type_not_admitted"
    assert not case_service._facade.store.list_latest(
        "canonical_work_units", case_id=case["case_id"]
    )


def test_t02_zero_call_profile_uses_same_runtime_and_exact_paired_baseline(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "probe-runtime", repo_root=REPO_ROOT
    )
    probe = _ZeroCallContractProbe()
    app = create_app(
        tmp_path / "probe.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=probe,
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="probe")
        deterministic = _create_work_unit(
            client,
            case,
            plan,
            key="probe-deterministic",
            work_unit_type=VT1_WORK_UNIT_TYPE,
        )
        bounded = _create_work_unit(
            client,
            case,
            plan,
            key="probe-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
        assert deterministic.status_code == bounded.status_code == 202

    assert len(probe.inputs) == 1
    facade = case_service._facade
    runs = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )
    assert len(runs) == 2
    assert len({row["research_run_id"] for row in runs}) == 2
    bounded_run = next(
        row
        for row in runs
        if row["execution_profile_version_ref"] == BOUNDED_AGENT_PROFILE_REF
    )
    assert bounded_run["state"] == "succeeded"
    artifacts = facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )
    bounded_artifacts = [
        row for row in artifacts if row["producer_attempt_id"] == bounded_run["attempt_id"]
    ]
    assert {row["artifact_type"] for row in bounded_artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    comparison_row = next(
        row
        for row in bounded_artifacts
        if row["artifact_type"] == BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE
    )
    comparison = facade.get_artifact_version(
        comparison_row["artifact_version_id"], include_payload=True
    )["payload"]
    assert comparison["paired_input_digest"] == probe.inputs[0].input_digest
    assert comparison["deterministic_baseline"]["observed_calls"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
    }
    attempts = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])
    assert len(attempts) == 2
    assert all(row["attempt_no"] == 1 for row in attempts)


def test_t02_bounded_failure_is_terminal_without_deterministic_fallback(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "failure-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "failure.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_ZeroCallContractProbe(fail=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="failure")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="failure-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
        assert response.status_code == 202

    facade = case_service._facade
    runs = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )
    attempts = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])
    artifacts = facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )
    assert len(runs) == len(attempts) == 1
    assert runs[0]["state"] == attempts[0]["state"] == "failed"
    assert runs[0]["execution_profile_version_ref"] == BOUNDED_AGENT_PROFILE_REF
    assert runs[0]["terminal_reason"].startswith(
        "bounded_agent_profile_error:RuntimeError"
    )
    assert artifacts == []


def test_t03_non_vt1_execution_identity_is_distinct_in_one_shared_store(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "identity-runtime", repo_root=REPO_ROOT
    )
    probe = _ZeroCallContractProbe()
    app = create_app(
        tmp_path / "identity.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=probe,
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="identity")
        first = _create_work_unit(
            client,
            case,
            plan,
            key="identity-bounded-admission-a",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
        second = _create_work_unit(
            client,
            case,
            plan,
            key="identity-bounded-admission-b",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
        replay_first = _create_work_unit(
            client,
            case,
            plan,
            key="identity-bounded-admission-a",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )

    assert first.status_code == second.status_code == replay_first.status_code == 202
    facade = case_service._facade
    work_units = facade.store.list_latest(
        "canonical_work_units", case_id=case["case_id"]
    )
    attempts = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])
    runs = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )
    assert len(probe.inputs) == 2
    assert len(work_units) == len(attempts) == len(runs) == 2
    assert len({row["work_unit_id"] for row in work_units}) == 2
    assert len({row["attempt_id"] for row in attempts}) == 2
    assert len({row["research_run_id"] for row in runs}) == 2
    expected_work_unit_ids = {
        "wu_p02_5_"
        + canonical_digest(
            {
                "tenant_id": TENANT_ID,
                "project_id": PROJECT_ID,
                "case_id": case["case_id"],
                "contract_version_id": plan["contract_version_id"],
                "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                "execution_identity": key,
            }
        )[:24]
        for key in (
            "identity-bounded-admission-a",
            "identity-bounded-admission-b",
        )
    }
    assert {row["work_unit_id"] for row in work_units} == expected_work_unit_ids


def test_t03_pending_non_vt1_dispatch_selects_exact_execution_identity(
    monkeypatch,
) -> None:
    service = ExecutionService.unavailable()
    principal = CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=frozenset(PERMISSIONS.split(",")),
    )
    rows = [
        {
            "work_unit_id": "wu-a",
            "state": "pending",
            "idempotency_key": "bounded-admission-a",
        },
        {
            "work_unit_id": "wu-b",
            "state": "pending",
            "idempotency_key": "bounded-admission-b",
        },
    ]
    monkeypatch.setattr(service, "_work_units_by_type", lambda *_: rows)

    assert service.pending_work_unit_id_for_type(
        "case-1",
        BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        principal,
    ) is None
    assert service.pending_work_unit_id_for_type(
        "case-1",
        BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        principal,
        idempotency_key="bounded-admission-a",
    ) == "wu-a"


def test_t03_v4_safe_result_shape_is_persisted_by_canonical_failure_path(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "v4-failure-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "v4-failure.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_V4ShapeFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="v4-failure")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="v4-failure-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    observation = failed_event["payload"]["failure_observation"]
    assert observation["failure_codes"] == [
        "bounded_agent_specialist_result_keys_unexpected"
    ]
    assert observation["output_shape"]["unexpected_result_key_count"] == 1
    assert observation["output_shape"]["unexpected_result_keys_digest"] == "a" * 64
    assert observation["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
    }


def test_t03_strict_failure_telemetry_is_persisted_by_canonical_failure_path(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "strict-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "strict-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_StrictTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="strict-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="strict-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    observation = failed_event["payload"]["failure_observation"]
    assert observation["failure_telemetry"] == {
        "strict_tool_arguments": {
            "parser_contract": "native_json_object_no_fence_no_duplicate_keys",
            "parse_subtype": "duplicate_key",
            "raw_arguments_persisted": False,
            "argument_digest_persisted": False,
            "argument_length_persisted": False,
        }
    }
    assert "secret-provider-arguments" not in str(observation)
    run = case_service._facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    assert run["state"] == "failed"


def test_t03_unsafe_failure_telemetry_is_rejected_and_dispatch_error_surfaces(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_StrictTelemetryFailureProbe(unsafe=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-telemetry")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-telemetry-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )


def test_s3_segmented_shape_telemetry_is_persisted_without_key_names_or_body(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "segmented-shape-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "segmented-shape-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_SegmentedSpecialistShapeTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="segmented-shape-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="segmented-shape-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["segmented_specialist_shape"]
    assert telemetry == {
        "parser_contract": "closed_segment_top_level_shape:v1",
        "segment_id": "facts_explanation_and_terminal",
        "shape_subtype": "top_level_keys_unexpected",
        "missing_key_count": 0,
        "unexpected_key_count": 1,
        "raw_output_persisted": False,
        "arbitrary_key_names_persisted": False,
    }
    assert "secret-provider-field" not in str(telemetry)


def test_s3_segmented_shape_telemetry_rejects_arbitrary_key_names(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-segmented-shape-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-segmented-shape.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_SegmentedSpecialistShapeTelemetryFailureProbe(
            unsafe=True
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-segmented-shape")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-segmented-shape-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )


def test_s3_segmented_text_telemetry_is_persisted_without_text_or_item_index(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "segmented-text-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "segmented-text-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_SegmentedSpecialistTextTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="segmented-text-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="segmented-text-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["segmented_specialist_text"]
    assert telemetry == {
        "validator_contract": "closed_segment_narrative_text:v1",
        "segment_id": "facts_explanation_and_terminal",
        "field_id": "explanation_layer",
        "text_subtype": "item_over_max_unicode_characters",
        "failing_item_count": 1,
        "raw_text_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }


def test_s3_segmented_text_telemetry_rejects_raw_text(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-segmented-text-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-segmented-text.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_SegmentedSpecialistTextTelemetryFailureProbe(
            unsafe=True
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-segmented-text")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-segmented-text-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )


def test_s3_segmented_authority_telemetry_is_persisted_without_ref_or_digest(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "segmented-authority-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "segmented-authority-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_SegmentedSpecialistAuthorityTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="segmented-authority-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="segmented-authority-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["segmented_specialist_authority"]
    assert telemetry == {
        "validator_contract": "closed_segment_context_authority:v1",
        "segment_id": "owner_grade_claim_cards",
        "field_id": "judgment_layer.context_refs",
        "authority_subtype": "outside_current_cell_context_authority",
        "failing_item_count": 1,
        "raw_ref_persisted": False,
        "ref_digest_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }
    assert "secret-provider-ref" not in str(telemetry)


def test_s3_segmented_authority_telemetry_rejects_raw_ref(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-segmented-authority-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-segmented-authority.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_SegmentedSpecialistAuthorityTelemetryFailureProbe(
            unsafe=True
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-segmented-authority")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-segmented-authority-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )


def test_s3_segmented_fact_authority_telemetry_is_persisted_content_free(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "segmented-fact-authority-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "segmented-fact-authority.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=(
            _SegmentedSpecialistFactAuthorityTelemetryFailureProbe()
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="segmented-fact-authority")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="segmented-fact-authority-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["segmented_specialist_fact_authority"]
    assert telemetry == {
        "validator_contract": "closed_fact_support_authority:v1",
        "segment_id": "facts_explanation_and_terminal",
        "field_id": "fact_layer.support_refs",
        "authority_subtype": (
            "candidate_or_graph_ref_misclassified_as_fact"
        ),
        "failing_item_count": 1,
        "raw_ref_persisted": False,
        "ref_digest_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }
    assert "secret-provider-fact-ref" not in str(telemetry)


def test_s3_segmented_fact_authority_telemetry_rejects_raw_ref(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-segmented-fact-authority-runtime",
        repo_root=REPO_ROOT,
    )
    app = create_app(
        tmp_path / "unsafe-segmented-fact-authority.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=(
            _SegmentedSpecialistFactAuthorityTelemetryFailureProbe(
                unsafe=True
            )
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(
            client, key="unsafe-segmented-fact-authority"
        )
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-segmented-fact-authority-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )


def test_s3_segmented_epistemic_status_telemetry_is_persisted_content_free(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "segmented-epistemic-status-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "segmented-epistemic-status.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=(
            _SegmentedSpecialistEpistemicStatusTelemetryFailureProbe()
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="segmented-epistemic-status")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="segmented-epistemic-status-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["segmented_specialist_epistemic_status"]
    assert telemetry == {
        "validator_contract": "closed_claim_card_epistemic_status_state:v1",
        "segment_id": "owner_grade_claim_cards",
        "field_id": (
            "judgment_layer.epistemic_status_support_fact_ids_"
            "qualification_cannot_support"
        ),
        "status_subtype": "cannot_infer_has_support_fact_ids",
        "failing_item_count": 1,
        "raw_claim_persisted": False,
        "support_fact_ids_persisted": False,
        "cannot_support_text_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }
    assert "secret-provider-claim" not in str(telemetry)


def test_s3_segmented_epistemic_status_telemetry_rejects_raw_claim(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-segmented-epistemic-status-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-segmented-epistemic-status.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=(
            _SegmentedSpecialistEpistemicStatusTelemetryFailureProbe(
                unsafe=True
            )
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-segmented-epistemic-status")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-segmented-epistemic-status-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )


def test_s3_research_lead_contract_telemetry_is_persisted_content_free(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "research-lead-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "research-lead-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_ResearchLeadContractTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="research-lead-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="research-lead-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["research_lead_contract"]
    assert telemetry["validator_contract"] == "closed_research_lead_output:v2"
    assert telemetry["failure_family"] == "cardinality"
    assert telemetry["failure_subtype"] == "above_maximum"
    assert "secret-provider-lead-text" not in str(telemetry)


def test_s3_research_lead_v3_semantic_telemetry_is_persisted_content_free(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "research-lead-v3-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "research-lead-v3-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_ResearchLeadV3SemanticTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="research-lead-v3-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="research-lead-v3-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    telemetry = failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ]["research_lead_contract"]
    assert telemetry == {
        "validator_contract": "closed_research_lead_output:v3",
        "failure_family": "semantic",
        "failure_subtype": "fact_presence_summary_mismatch",
        "field_id": "conflict_adjudications.fact_presence_summary",
        "failing_item_count": 1,
        "raw_text_persisted": False,
        "ref_or_digest_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }


def test_s3_research_lead_contract_telemetry_rejects_raw_text(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-research-lead-telemetry-runtime", repo_root=REPO_ROOT
    )
    app = create_app(
        tmp_path / "unsafe-research-lead-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_ResearchLeadContractTelemetryFailureProbe(
            unsafe=True
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-research-lead-telemetry")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-research-lead-telemetry-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )
