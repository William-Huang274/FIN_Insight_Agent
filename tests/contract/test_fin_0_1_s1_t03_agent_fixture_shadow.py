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
    VT1_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
    FIN01_DETERMINISTIC_ARTIFACT_TYPE,
    FIN01_DETERMINISTIC_PROFILE_REF,
    FIN01_S3_REPORT_ARTIFACT_TYPE,
    FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
    FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
)
from sec_agent.agent_registry import agent_definition_version
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.research_skills import select_skill_pack_version


TENANT_ID = "tenant-fin01-t03"
PROJECT_ID = "project-fin01-t03"
ACTOR_ID = "analyst-fin01-t03"
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


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": PERMISSIONS,
    }


def _accepted_nvda_case(
    client: TestClient, *, key: str
) -> tuple[dict[str, Any], dict[str, Any]]:
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


def _create_work_unit(
    client: TestClient,
    case: dict[str, Any],
    plan: dict[str, Any],
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


def _business_snapshot(facade: Any) -> dict[str, list[dict[str, Any]]]:
    return {table: list(facade.store.list_versions(table)) for table in BUSINESS_TABLES}


def test_agent_fixture_shadow_selects_and_traces_versions_on_distinct_run(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=REPO_ROOT
    )
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_nvda_case(client, key="shadow-success")
        business_before = _business_snapshot(case_service._facade)
        deterministic = _create_work_unit(
            client,
            case,
            plan,
            key="shadow-success-deterministic",
            work_unit_type=VT1_WORK_UNIT_TYPE,
        )
        assert deterministic.status_code == 202, deterministic.text
        shadow = _create_work_unit(
            client,
            case,
            plan,
            key="shadow-success-agent",
            work_unit_type=AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
        )
        assert shadow.status_code == 202, shadow.text

    facade = case_service._facade
    work_units = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])
    attempts = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])
    runs = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )
    artifacts = facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )
    assert len(work_units) == len(attempts) == len(runs) == 2
    assert len(artifacts) == 11
    assert {row["execution_profile_version_ref"] for row in runs} == {
        FIN01_DETERMINISTIC_PROFILE_REF,
        FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
    }
    assert {row["artifact_type"] for row in artifacts} == {
        FIN01_DETERMINISTIC_ARTIFACT_TYPE,
        FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE,
        FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE,
        FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE,
        FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE,
        FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE,
        FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE,
            FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE,
            FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
            FIN01_S3_REPORT_ARTIFACT_TYPE,
            FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
        }
    shadow_run = next(
        row
        for row in runs
        if row["execution_profile_version_ref"]
        == FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF
    )
    shadow_attempt = next(
        row for row in attempts if row["attempt_id"] == shadow_run["attempt_id"]
    )
    shadow_work_unit = next(
        row for row in work_units if row["work_unit_id"] == shadow_run["work_unit_id"]
    )
    shadow_artifacts = [
        row for row in artifacts if row["producer_attempt_id"] == shadow_attempt["attempt_id"]
    ]
    shadow_artifact = next(
        row
        for row in shadow_artifacts
        if row["artifact_type"] == FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE
    )
    assert shadow_work_unit["work_unit_type"] == AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE
    assert shadow_work_unit["state"] == shadow_attempt["state"] == shadow_run["state"] == "succeeded"
    assert shadow_artifact["artifact_type"] == FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE
    assert shadow_artifact["producer_attempt_id"] == shadow_run["attempt_id"]
    assert set(shadow_attempt["output_refs"]) == {
        row["artifact_version_id"] for row in shadow_artifacts
    }
    assert shadow_run["research_run_version_id"].replace(":v2", ":v1") in shadow_artifact[
        "input_refs"
    ]

    payload = facade.object_store.get_json(
        shadow_artifact["object_key"], expected_digest=shadow_artifact["object_digest"]
    )
    graph_slice = payload["graph_slice"]
    assert payload["research_run_id"] == shadow_run["research_run_id"]
    assert payload["work_unit_id"] == shadow_run["work_unit_id"]
    assert payload["attempt_id"] == shadow_run["attempt_id"]
    assert len(payload["agent_definition_versions"]) == 8
    assert len(payload["skill_pack_versions"]) == 8
    assert graph_slice["primary_lead_agent_id"] == "research_lead"
    assert graph_slice["primary_specialist_agent_id"] == "industry_supply_chain_analyst"
    task = graph_slice["specialist_task"]
    assert task["research_run_id"] == shadow_run["research_run_id"]
    assert task["work_unit_id"] == shadow_run["work_unit_id"]
    assert task["attempt_id"] == shadow_run["attempt_id"]
    assert task["causation_event_id"]
    assert task["skill_pack_digest"]
    assert graph_slice["specialist_to_specialist_hidden_call_count"] == 0
    assert {"memo_writer", "verifier", "renderer", "persist_session_state"}.issubset(
        graph_slice["graph_nodes_executed"]
    )
    assert graph_slice["execution_counts"]["fixture_tool_observations"] == 1
    assert all(
        graph_slice["execution_counts"][key] == 0
        for key in ("model_calls", "provider_calls", "network_calls", "external_tool_calls", "business_writes")
    )
    assert set(payload["hard_boundaries"].values()) == {0}
    assert all(row["authority_grants"] == [] for row in payload["skill_pack_versions"])

    events = facade.store.list_events(shadow_run["research_run_id"])
    assert [row["sequence_no"] for row in events] == list(range(1, len(events) + 1))
    assert [row["event_type"] for row in events[:13]] == [
        "WORK_UNIT_STARTED",
        "ATTEMPT_STARTED",
        "SCHEDULER_LEASE_ACQUIRED",
        "RESEARCH_RUN_STARTED",
        "AGENT_DEFINITION_VERSIONS_SELECTED",
        "SKILL_PACK_CONSUMPTION_RECORDED",
        "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
        "RESEARCH_LEAD_FIXTURE_COMPLETED",
        "SPECIALIST_FIXTURE_COMPLETED",
        "TOOL_FIXTURE_OBSERVATION_RECORDED",
        "GRAPH_FIXTURE_OBSERVATION_RECORDED",
        "WRITER_FIXTURE_COMPLETED",
        "VERIFIER_FIXTURE_COMPLETED",
    ]
    assert [row["event_type"] for row in events[13:20]] == [
        "ARTIFACT_VERSION_CREATED"
    ] * 7
    assert [row["event_type"] for row in events[-3:]] == [
        "RESEARCH_RUN_COMPLETED",
        "ATTEMPT_COMPLETED",
        "WORK_UNIT_COMPLETED",
    ]
    assert all(row["task_run_id"] == shadow_run["research_run_id"] for row in events)
    assert all(row["work_unit_id"] == shadow_run["work_unit_id"] for row in events)
    assert all(row["attempt_id"] == shadow_run["attempt_id"] for row in events)
    assert events[4]["causation_event_id"] == events[3]["event_id"]
    assert events[5]["causation_event_id"] == events[4]["event_id"]
    assert all(
        events[index]["causation_event_id"] == events[index - 1]["event_id"]
        for index in range(4, 13)
    )
    assert facade.replay_projection(shadow_run["research_run_id"])["external_call_count"] == 0
    assert _business_snapshot(facade) == business_before


def test_agent_fixture_shadow_failure_stays_failed_without_artifact_or_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sec_agent.langgraph_orchestrator as orchestrator

    def fail_shadow(**_: Any) -> dict[str, Any]:
        raise RuntimeError("bounded agent fixture failure")

    monkeypatch.setattr(orchestrator, "run_fin01_agent_fixture_shadow_cell", fail_shadow)
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=REPO_ROOT
    )
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_nvda_case(client, key="shadow-failure")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="shadow-failure-agent",
            work_unit_type=AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
        )
        assert response.status_code == 202, response.text

    facade = case_service._facade
    work_units = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])
    attempt = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])[0]
    run = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    assert len(work_units) == 1
    assert work_units[0]["work_unit_type"] == AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE
    assert work_units[0]["state"] == attempt["state"] == run["state"] == "failed"
    assert run["terminal_reason"] == "agent_fixture_shadow_profile_error:RuntimeError"
    assert facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    ) == []
    assert work_units[0].get("forked_from_work_unit_id") is None
    assert [row["event_type"] for row in facade.store.list_events(run["research_run_id"])[-3:]] == [
        "RESEARCH_RUN_FAILED",
        "ATTEMPT_FAILED",
        "WORK_UNIT_FAILED",
    ]


def test_agent_fixture_shadow_commit_failure_is_terminal_not_left_running(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=REPO_ROOT
    )

    def fail_commit(_: Any):
        raise RuntimeError("bounded canonical commit failure")

    case_service._facade.complete_research_run = fail_commit
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        case, plan = _accepted_nvda_case(client, key="shadow-commit-failure")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="shadow-commit-failure-agent",
            work_unit_type=AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
        )
        assert response.status_code == 202, response.text

    facade = case_service._facade
    run = facade.store.list_latest(
        "canonical_research_run_versions", case_id=case["case_id"]
    )[0]
    attempt = facade.store.list_latest("canonical_attempts", case_id=case["case_id"])[0]
    work_unit = facade.store.list_latest("canonical_work_units", case_id=case["case_id"])[0]
    assert run["state"] == attempt["state"] == work_unit["state"] == "failed"
    assert run["terminal_reason"] == "profile_commit_error:RuntimeError"
    assert facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    ) == []
    assert [row["event_type"] for row in facade.store.list_events(run["research_run_id"])[-3:]] == [
        "RESEARCH_RUN_FAILED",
        "ATTEMPT_FAILED",
        "WORK_UNIT_FAILED",
    ]


def test_agent_and_skill_versions_are_stable_and_profile_selection_fails_closed() -> None:
    first = agent_definition_version("industry_supply_chain_analyst")
    second = agent_definition_version("industry_supply_chain_analyst")
    assert first["agent_definition_version_ref"] == second["agent_definition_version_ref"]
    assert first["canonical_digest"] == second["canonical_digest"]

    registered = ("shared_evidence_boundary", "relationship_universe")
    skipped = select_skill_pack_version(
        agent_id="industry_supply_chain_analyst",
        registered_skill_ids=registered,
        execution_profile_version_ref=FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
        allowed_execution_profile_refs=(FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,),
        optional_skill_observation_keys={
            "relationship_universe": "relationship_graph_required"
        },
        observations={"relationship_graph_required": False},
    )
    selected = select_skill_pack_version(
        agent_id="industry_supply_chain_analyst",
        registered_skill_ids=registered,
        execution_profile_version_ref=FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
        allowed_execution_profile_refs=(FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,),
        optional_skill_observation_keys={
            "relationship_universe": "relationship_graph_required"
        },
        observations={"relationship_graph_required": True},
    )
    assert len(skipped["skill_definitions"]) == 1
    assert len(selected["skill_definitions"]) == 2
    assert skipped["canonical_digest"] != selected["canonical_digest"]
    with pytest.raises(PermissionError, match="execution_profile_not_allowed_for_skill_pack"):
        select_skill_pack_version(
            agent_id="industry_supply_chain_analyst",
            registered_skill_ids=registered,
            execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
            allowed_execution_profile_refs=(FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,),
        )
