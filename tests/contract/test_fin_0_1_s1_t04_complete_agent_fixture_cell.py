from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import (
    AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
    FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-t04"
PROJECT_ID = "project-fin01-t04"
ACTOR_ID = "analyst-fin01-t04"
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
BUSINESS_TABLES = (
    "canonical_research_cases",
    "canonical_case_control_versions",
    "canonical_decision_surface_contract_versions",
    "canonical_decision_surface_cell_versions",
    "canonical_evidence_slot_versions",
    "canonical_compile_gap_versions",
    "canonical_planning_checkpoint_versions",
)
CELL_ARTIFACT_TYPES = {
    FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE,
}
TRACE_EVENT_TYPES = (
    "AGENT_DEFINITION_VERSIONS_SELECTED",
    "SKILL_PACK_CONSUMPTION_RECORDED",
    "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
    "RESEARCH_LEAD_FIXTURE_COMPLETED",
    "SPECIALIST_FIXTURE_COMPLETED",
    "TOOL_FIXTURE_OBSERVATION_RECORDED",
    "GRAPH_FIXTURE_OBSERVATION_RECORDED",
    "WRITER_FIXTURE_COMPLETED",
    "VERIFIER_FIXTURE_COMPLETED",
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
            "as_of": "2026-07-19T00:00:00Z",
            "language": "zh-CN",
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


def _run_shadow(
    client: TestClient,
    case: dict[str, Any],
    plan: dict[str, Any],
    *,
    key: str,
):
    return client.post(
        f"/api/v1/cases/{case['case_id']}/work-units",
        headers=_headers(),
        json={
            "work_unit_type": AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
            "expected_case_version": case["case_version"],
            "input_head_digest": canonical_digest((plan["contract_version_id"],)),
            "actor_ref": ACTOR_ID,
            "idempotency_key": key,
        },
    )


def _business_snapshot(facade: Any) -> dict[str, list[dict[str, Any]]]:
    return {table: list(facade.store.list_versions(table)) for table in BUSINESS_TABLES}


def _payloads_by_type(facade: Any, artifacts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        row["artifact_type"]: facade.object_store.get_json(
            row["object_key"], expected_digest=row["object_digest"]
        )
        for row in artifacts
    }


def test_complete_nvda_fixture_cell_shares_one_run_and_never_invokes_external_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sec_agent.langgraph_orchestrator as orchestrator

    def external_tool_forbidden(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("T04 fixture shadow attempted an external tool")

    monkeypatch.setattr(orchestrator, "invoke_mcp_tool", external_tool_forbidden)
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=REPO_ROOT
    )
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="complete-cell")
        business_before = _business_snapshot(case_service._facade)
        response = _run_shadow(client, case, plan, key="complete-cell-run")
        assert response.status_code == 202, response.text

    facade = case_service._facade
    run = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    attempt = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])[0]
    work_unit = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])[0]
    artifacts = facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )
    assert run["execution_profile_version_ref"] == FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF
    assert run["state"] == attempt["state"] == work_unit["state"] == "succeeded"
    assert run["terminal_reason"] == "agent_fixture_shadow_complete_cell_succeeded"
    assert len(artifacts) == 7
    assert {row["artifact_type"] for row in artifacts} == CELL_ARTIFACT_TYPES
    assert {row["producer_attempt_id"] for row in artifacts} == {run["attempt_id"]}
    assert set(attempt["output_refs"]) == {row["artifact_version_id"] for row in artifacts}
    run_v1 = run["research_run_version_id"].replace(":v2", ":v1")
    assert all(run_v1 in row["input_refs"] for row in artifacts)

    payloads = _payloads_by_type(facade, artifacts)
    assert all(
        payloads[row["artifact_type"]]["artifact_version_id"]
        == row["artifact_version_id"]
        for row in artifacts
    )
    assert {payload["research_run_id"] for payload in payloads.values()} == {
        run["research_run_id"]
    }
    assert all(
        payload["research_run_version_id"] == run_v1
        and set(payload["artifact_manifest"].values()) == set(attempt["output_refs"])
        for payload in payloads.values()
    )
    manifest = payloads[FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE]
    graph = manifest["graph_slice"]
    assert {"memo_writer", "verifier", "renderer", "persist_session_state"}.issubset(
        graph["graph_nodes_executed"]
    )
    assert graph["execution_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
        "fixture_tool_observations": 1,
        "business_writes": 0,
    }
    assert set(manifest["hard_boundaries"].values()) == {0}

    evidence = payloads[FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE]
    numeric = payloads[FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE]
    judgment = payloads[FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE]
    workpaper = payloads[FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE]
    report = payloads[FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE]
    trace = payloads[FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE]
    assert numeric["evidence_refs"] == [evidence["artifact_ref"]]
    assert judgment["evidence_refs"] == [evidence["artifact_ref"]]
    assert judgment["numeric_refs"] == [numeric["artifact_ref"]]
    assert workpaper["judgment_refs"] == [judgment["artifact_ref"]]
    assert report["workpaper_refs"] == [workpaper["artifact_ref"]]
    assert trace["event_scope"] == {"task_run_id": run["research_run_id"]}
    assert report["human_review_status"] == "not_performed"

    events = facade.store.list_events(run["research_run_id"])
    trace_events = [row for row in events if row["event_type"] in TRACE_EVENT_TYPES]
    assert tuple(row["event_type"] for row in trace_events) == TRACE_EVENT_TYPES
    assert all(row["task_run_id"] == run["research_run_id"] for row in events)
    assert all(row["work_unit_id"] == run["work_unit_id"] for row in events)
    assert all(row["attempt_id"] == run["attempt_id"] for row in events)
    assert all(
        trace_events[index]["causation_event_id"]
        == (events[3]["event_id"] if index == 0 else trace_events[index - 1]["event_id"])
        for index in range(len(trace_events))
    )
    replay = facade.replay_projection(run["research_run_id"])
    assert len(replay["research_run_traces"][run["research_run_id"]]) == len(
        TRACE_EVENT_TYPES
    )
    assert set(replay["artifacts"]) == set(attempt["output_refs"])
    assert replay["external_call_count"] == 0
    assert _business_snapshot(facade) == business_before


def test_writer_failure_is_terminal_and_cannot_reuse_deterministic_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sec_agent.langgraph_orchestrator as orchestrator

    original = orchestrator.run_fin01_agent_fixture_shadow_cell

    def fail_writer(**kwargs: Any) -> dict[str, Any]:
        return original(**kwargs, fail_at_stage="writer")

    monkeypatch.setattr(orchestrator, "run_fin01_agent_fixture_shadow_cell", fail_writer)
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=REPO_ROOT
    )
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="writer-failure")
        response = _run_shadow(client, case, plan, key="writer-failure-run")
        assert response.status_code == 202, response.text

    facade = case_service._facade
    run = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    attempt = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])[0]
    work_unit = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])[0]
    assert run["state"] == attempt["state"] == work_unit["state"] == "failed"
    assert run["terminal_reason"] == (
        "agent_fixture_shadow_profile_error:Fin01FixtureShadowStageError:writer"
    )
    assert facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    ) == []
    assert attempt["output_refs"] == []
    assert work_unit.get("forked_from_work_unit_id") is None
    assert [row["event_type"] for row in facade.store.list_events(run["research_run_id"])[-3:]] == [
        "RESEARCH_RUN_FAILED",
        "ATTEMPT_FAILED",
        "WORK_UNIT_FAILED",
    ]
