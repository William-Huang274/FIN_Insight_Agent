from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import (
    EvidenceService,
    S3ThreeCellEvidenceRoutePlanVersion,
    consume_s3_three_cell_evidence_route_plan,
)
from apps.workbench.backend.application.execution_service import (
    ExecutionService,
    VT1_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    FIN01_DETERMINISTIC_PROFILE_REF,
    compile_fin01_s3_three_cell_runtime_plan,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
T03 = RELEASES / "fin_ia_0_1_s3_t03_evidence_route_promotion_sourcehunter_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"

TENANT_ID = "tenant-fin01-s3-t03"
PROJECT_ID = "project-fin01-s3-t03"
ACTOR_ID = "analyst-fin01-s3-t03"
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


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _accepted_case(
    client: TestClient, *, key: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    created = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "Execute the FIN 0.1 NVDA three-cell evidence route fixture",
            "as_of": "2026-07-21T00:00:00Z",
            "language": "en",
            "source_policy_ref": "fixture:internal-only",
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
    accepted = client.post(
        f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
        headers=_headers(),
        json={
            "decision": "accept",
            "expected_case_version": case["case_version"],
            "expected_decision_surface_contract_version": compiled.json()[
                "contract_version"
            ],
            "expected_checkpoint_version": compiled.json()["checkpoint_version"],
            "actor_ref": ACTOR_ID,
            "idempotency_key": f"{key}-accept",
        },
    )
    assert accepted.status_code == 202, accepted.text
    return case, accepted.json()


def _create_work_unit(
    client: TestClient,
    case: dict[str, Any],
    plan: dict[str, Any],
    *,
    key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": VT1_WORK_UNIT_TYPE,
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((plan["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["work_units"][0]


def _run_payload(tmp_path: Path) -> dict[str, Any]:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=ROOT
    )
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="runtime")
        _create_work_unit(client, case, plan, key="runtime-execute")
    artifact = case_service._facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )[0]
    return case_service._facade.object_store.get_json(
        artifact["object_key"], expected_digest=artifact["object_digest"]
    )


def _latest_root_causes() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["issue_id"]] = row
    return latest


def test_t03_contract_remains_frozen_while_project_os_advances() -> None:
    contract = json.loads(T03.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    root_cause = _latest_root_causes()[
        "RC-P36-022-retrieval-rag-market-ownership-not-decision-cell-driven"
    ]
    assert contract["status"] == (
        "pass_after_independent_review_T04_ready_pending_separate_authorization"
    )
    assert contract["authority"]["S3_T03_zero_call_local_fixture_authorized"] is True
    assert contract["authority"]["S3_T04_execution_authorized"] is False
    assert contract["implementation"]["evidence_request_count"] == 3
    assert contract["implementation"]["runtime_evidence_promotion_count"] == 0
    assert backlog["next_action"]["item_id"] == (
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-"
        "PREFLIGHT-ZERO-CALL-IMPLEMENTATION"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is True
    assert root_cause["verification_result"]["three_cell_evidence_request_count"] == 3
    assert root_cause["verification_result"]["runtime_evidence_promotion_count"] == 0


def test_t03_runtime_persists_three_distinct_routes_and_zero_call_consumption(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    runtime_plan = payload["s3_runtime_plan"]
    plan = S3ThreeCellEvidenceRoutePlanVersion.model_validate(
        payload["s3_evidence_route_plan"]
    )
    receipts = consume_s3_three_cell_evidence_route_plan(
        plan,
        runtime_plan_version_ref=runtime_plan["runtime_plan_version_ref"],
        runtime_plan_digest=runtime_plan["runtime_plan_digest"],
    )
    assert payload["s3_evidence_route_consumption_receipts"] == list(receipts)
    assert len(plan.cell_routes) == len(receipts) == 3
    assert {row.research_run_id for row in plan.cell_routes} == {
        runtime_plan["research_run_id"]
    }
    routes = {
        row.program_cell_id: tuple(
            step.selected_route_id for step in row.tool_selection_plan.steps
        )
        for row in plan.cell_routes
    }
    assert routes["demand_authenticity_and_sustainability"] == (
        "local_object_bm25_official_disclosure",
        "local_materialized_customer_deployment_context",
    )
    assert routes["value_and_profit_capture"] == (
        "local_gold_sql_financial_table",
        "local_official_filing_table_address",
    )
    assert routes["bottleneck_counterevidence_and_what_would_change"] == (
        "local_relationship_graph_navigation",
        "local_official_counterevidence_source_followup",
    )
    assert all(
        preflight.invocation_status == "not_executed"
        and preflight.decision == "checks_pass_execution_not_admitted"
        for row in plan.cell_routes
        for preflight in row.tool_gateway_preflights
    )
    assert all(
        not row.promotion_assessment.accepted_evidence_refs
        and row.promotion_assessment.runtime_promotion_authorized is False
        and row.promotion_assessment.writer_citable is False
        for row in plan.cell_routes
    )
    assert {
        plan.model_calls,
        plan.provider_calls,
        plan.execution_network_calls,
        plan.source_network_calls,
        plan.external_tool_calls,
        plan.live_business_writes,
        plan.runtime_evidence_promotions,
    } == {0}


def test_t03_graph_observation_creates_followup_but_never_evidence_or_network(
    tmp_path: Path,
) -> None:
    plan = S3ThreeCellEvidenceRoutePlanVersion.model_validate(
        _run_payload(tmp_path)["s3_evidence_route_plan"]
    )
    counter = next(
        row
        for row in plan.cell_routes
        if row.program_cell_id
        == "bottleneck_counterevidence_and_what_would_change"
    )
    assert counter.graph_observation is not None
    assert counter.graph_observation.observation_class == "navigation_hypothesis_only"
    assert counter.graph_observation.direct_evidence_authorized is False
    assert counter.graph_observation.numeric_authority is False
    assert counter.source_followup_request is not None
    assert counter.source_followup_request.execution_admission == "not_admitted"
    assert counter.sourcehunter_boundary.status == (
        "proposal_only_blocked_missing_separate_network_admission"
    )
    assert counter.sourcehunter_boundary.request_executed is False
    assert counter.sourcehunter_boundary.network_calls == 0
    assert counter.promotion_assessment.decision == (
        "context_only_graph_observation_source_followup_required"
    )


def test_t03_missing_route_permission_returns_typed_stop_before_tool_execution(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=ROOT
    )
    execution_service = ExecutionService.from_case_service(case_service)
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        p02_execution_service=execution_service,
    )
    with TestClient(app) as client:
        case, accepted = _accepted_case(client, key="permission-stop")
        work_unit = _create_work_unit(
            client, case, accepted, key="permission-stop-execute"
        )
    runtime_plan = compile_fin01_s3_three_cell_runtime_plan(
        case_id=case["case_id"],
        work_unit_id=work_unit["work_unit_id"],
        attempt_id="attempt-fin01-s3-t03-permission-stop",
        research_run_id="run-fin01-s3-t03-permission-stop",
        execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
        decision_surface_contract_ref=accepted["contract_version_id"],
    )
    evidence_service = EvidenceService.from_case_service(
        case_service, repo_root=ROOT
    )
    plan = evidence_service.compile_s3_three_cell_runtime_evidence_plan(
        runtime_plan=runtime_plan.model_dump(mode="json"),
        principal=CasePrincipal(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            actor_id=ACTOR_ID,
            permissions=PERMISSIONS,
        ),
        allowed_tool_ids_by_program_cell={
            "bottleneck_counterevidence_and_what_would_change": (),
        },
    )
    counter = plan.cell_routes[2]
    assert counter.tool_selection_plan.status == "stopped"
    assert counter.tool_selection_plan.stop_reason == "permission_scope_stop_rule"
    assert counter.tool_gateway_preflights == ()
    assert counter.candidate_bundle.status == "not_attempted_typed_stop"
    assert counter.route_outcome == "typed_gap_sourcehunter_not_admitted"
    assert counter.sourcehunter_boundary.request_executed is False
    assert len(
        consume_s3_three_cell_evidence_route_plan(
            plan,
            runtime_plan_version_ref=runtime_plan.runtime_plan_version_ref,
            runtime_plan_digest=runtime_plan.runtime_plan_digest,
        )
    ) == 3


def test_t03_digest_and_zero_call_boundaries_fail_closed(tmp_path: Path) -> None:
    payload = _run_payload(tmp_path)
    runtime_plan = payload["s3_runtime_plan"]
    plan = S3ThreeCellEvidenceRoutePlanVersion.model_validate(
        payload["s3_evidence_route_plan"]
    )
    tampered = plan.model_copy(update={"source_network_calls": 1})
    with pytest.raises(ValueError, match="s3_evidence_route_zero_call_boundary_violated"):
        consume_s3_three_cell_evidence_route_plan(
            tampered,
            runtime_plan_version_ref=runtime_plan["runtime_plan_version_ref"],
            runtime_plan_digest=runtime_plan["runtime_plan_digest"],
        )
    tampered_route = plan.cell_routes[0].model_copy(
        update={"route_outcome": "typed_gap_sourcehunter_not_admitted"}
    )
    tampered_plan = plan.model_copy(
        update={"cell_routes": (tampered_route, *plan.cell_routes[1:])}
    )
    with pytest.raises(ValueError, match="s3_evidence_route_plan_digest_mismatch"):
        consume_s3_three_cell_evidence_route_plan(
            tampered_plan,
            runtime_plan_version_ref=runtime_plan["runtime_plan_version_ref"],
            runtime_plan_digest=runtime_plan["runtime_plan_digest"],
        )
