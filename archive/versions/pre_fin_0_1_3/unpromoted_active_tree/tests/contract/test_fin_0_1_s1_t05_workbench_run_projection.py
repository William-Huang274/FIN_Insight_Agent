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
    ExecutionService,
    VT1_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.research_runtime import (
    FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
    FIN01_DETERMINISTIC_PROFILE_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-t05"
PROJECT_ID = "project-fin01-t05"
ACTOR_ID = "analyst-fin01-t05"
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
    )
)
TRACE_EVENT_TYPES = {
    "AGENT_DEFINITION_VERSIONS_SELECTED",
    "SKILL_PACK_CONSUMPTION_RECORDED",
    "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
    "RESEARCH_LEAD_FIXTURE_COMPLETED",
    "SPECIALIST_FIXTURE_COMPLETED",
    "TOOL_FIXTURE_OBSERVATION_RECORDED",
    "GRAPH_FIXTURE_OBSERVATION_RECORDED",
    "WRITER_FIXTURE_COMPLETED",
    "VERIFIER_FIXTURE_COMPLETED",
}


def _headers(*, permissions: str = PERMISSIONS) -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": permissions,
    }


def _accepted_case(client: TestClient, *, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case_response = client.post(
        "/api/v1/cases",
        headers=_headers(),
        json={
            "query": "分析 NVDA 需求真实性与持续性",
            "as_of": "2026-07-20T00:00:00Z",
            "language": "zh-CN",
            "source_policy_ref": "fixture:internal-only",
            "idempotency_key": f"{key}-case",
        },
    )
    assert case_response.status_code == 202, case_response.text
    case = case_response.json()
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


def _run(client: TestClient, case: dict[str, Any], plan: dict[str, Any], work_unit_type: str, *, key: str) -> None:
    response = client.post(
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
    assert response.status_code == 202, response.text


def _contains_private_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            token in str(key).lower().replace("-", "_")
            for key in value
            for token in (
                "chain_of_thought",
                "internal_monologue",
                "hidden_thought",
                "private_thought",
                "private_reasoning",
                "hidden_reasoning",
                "reasoning_trace",
                "scratchpad",
            )
        ) or any(_contains_private_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_private_key(item) for item in value)
    return False


def test_run_projection_distinguishes_profiles_and_exposes_exact_safe_truth(tmp_path: Path) -> None:
    service = CaseService.for_fixture_root(tmp_path / "canonical-runtime", repo_root=REPO_ROOT)
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="profile-truth")
        _run(client, case, plan, VT1_WORK_UNIT_TYPE, key="deterministic-run")
        _run(client, case, plan, AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE, key="agent-run")
        response = client.get(
            f"/api/v1/cases/{case['case_id']}/execution-projection",
            headers=_headers(),
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["private_chain_of_thought_included"] is False
    assert {run["execution_profile_version_ref"] for run in payload["runs"]} == {
        FIN01_DETERMINISTIC_PROFILE_REF,
        FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
    }
    agent_run = next(
        run
        for run in payload["runs"]
        if run["execution_profile_version_ref"] == FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF
    )
    assert agent_run["state"] == "succeeded"
    assert agent_run["terminal_reason"] == "agent_fixture_shadow_complete_cell_succeeded"
    assert TRACE_EVENT_TYPES.issubset({event["event_type"] for event in agent_run["events"]})
    assert all(event["private_chain_of_thought_included"] is False for event in agent_run["events"])
    assert not _contains_private_key([event["details"] for event in agent_run["events"]])
    assert len(agent_run["artifacts"]) == 7
    assert {artifact["artifact_version_id"] for artifact in agent_run["artifacts"]} == set(agent_run["output_refs"])
    assert all(artifact["payload_exact"] and not artifact["redacted_fields"] for artifact in agent_run["artifacts"])
    assert not _contains_private_key(agent_run["artifacts"])


def test_failed_agent_run_projects_typed_stop_without_artifact_or_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sec_agent.langgraph_orchestrator as orchestrator

    original = orchestrator.run_fin01_agent_fixture_shadow_cell

    def fail_writer(**kwargs: Any) -> dict[str, Any]:
        return original(**kwargs, fail_at_stage="writer")

    monkeypatch.setattr(orchestrator, "run_fin01_agent_fixture_shadow_cell", fail_writer)
    service = CaseService.for_fixture_root(tmp_path / "canonical-runtime", repo_root=REPO_ROOT)
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=service)
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="failure-truth")
        _run(client, case, plan, AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE, key="failed-agent-run")
        response = client.get(
            f"/api/v1/cases/{case['case_id']}/execution-projection",
            headers=_headers(),
        )
        forbidden = client.get(
            f"/api/v1/cases/{case['case_id']}/execution-projection",
            headers=_headers(permissions="case:read"),
        )

    run = response.json()["runs"][0]
    assert run["state"] == "failed"
    assert run["terminal_reason"] == "agent_fixture_shadow_profile_error:Fin01FixtureShadowStageError:writer"
    assert run["artifacts"] == []
    assert run["output_refs"] == []
    assert len(response.json()["runs"]) == 1
    assert forbidden.status_code == 403


def test_workbench_source_renders_profiles_structured_events_artifacts_and_stop_reason() -> None:
    root = REPO_ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"
    ui = (root / "app" / "WorkbenchNext.tsx").read_text(encoding="utf-8")
    client = (root / "api" / "execution.ts").read_text(encoding="utf-8")

    assert "executionApi.getResearchRunProjection(caseId)" in ui
    assert 'copy("本地确定性预览", "Local deterministic preview")' in ui
    assert 'copy("Agent 编排影子（Fixture）", "Agent orchestration shadow (fixture)")' in ui
    assert 'copy("真实停止原因", "Exact stop reason")' in ui
    assert 'copy("结构化字段（不含私有思维链）"' in ui
    assert "artifact.payload_exact" in ui
    assert "artifact.artifact_version_id" in ui
    assert "AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE" in ui
    assert '`${casePath(caseId)}/execution-projection`' in client


def test_projection_redacts_private_reasoning_fields_recursively() -> None:
    safe, redacted = ExecutionService._without_private_trace_fields(
        {
            "status": "structured",
            "scratchpad": "must never leave the runtime",
            "nested": {
                "private_reasoning": "hidden",
                "public_result": "bounded conclusion",
            },
        }
    )

    assert safe == {
        "status": "structured",
        "nested": {"public_result": "bounded conclusion"},
    }
    assert redacted == ["$.scratchpad", "$.nested.private_reasoning"]
