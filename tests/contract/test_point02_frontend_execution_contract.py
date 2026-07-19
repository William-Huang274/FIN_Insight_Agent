from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "configs/releases/point02_api_v1_openapi_baseline_v1_1.json"
FRONTEND = ROOT / "apps/workbench/frontend/vite/src"
EXECUTION_CLIENT = FRONTEND / "api/execution.ts"
ACTIVITY_TRACE = FRONTEND / "features/activity-trace/ActivityTrace.tsx"
APP_SHELL = FRONTEND / "app/AppShell.tsx"
CASE_OVERVIEW = FRONTEND / "features/case-overview/CaseOverview.tsx"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execution_client_matches_p02_0_v1_1_routes_and_wire_schemas() -> None:
    contract = json.loads(OPENAPI.read_text(encoding="utf-8"))
    source = _source(EXECUTION_CLIENT)

    expected_operations = {
        "/cases/{case_id}/work-units": {"listWorkUnits", "createWorkUnit"},
        "/cases/{case_id}/work-units/{work_unit_id}/cancel": {"cancelWorkUnit"},
        "/cases/{case_id}/activity": {"getActivityTrace"},
    }
    for path, operation_ids in expected_operations.items():
        assert path in contract["paths"]
        assert operation_ids.issubset({operation["operationId"] for operation in contract["paths"][path].values()})
        for operation_id in operation_ids:
            assert re.search(rf"\b{operation_id}\b", source)

    assert '`${casePath(caseId)}/work-units`' in source
    assert '`${casePath(caseId)}/work-units/${encodeURIComponent(workUnitId)}/cancel`' in source
    assert '`${casePath(caseId)}/activity`' in source
    assert '"Idempotency-Key": command.idempotency_key' in source

    for schema_name in (
        "CreateWorkUnitCommand",
        "CancelWorkUnitCommand",
        "WorkUnitExecutionView",
        "WorkUnitExecutionItem",
        "ActivityTraceView",
        "ActivityEvent",
    ):
        for field in contract["components"]["schemas"][schema_name]["required"]:
            assert re.search(rf"\b{re.escape(field)}\b", source)

    assert 'JSON.stringify([contractVersionId])' in source
    assert 'crypto.subtle.digest("SHA-256", encoded)' in source


def test_activity_route_loads_live_projections_and_exposes_exact_vt1_controls() -> None:
    shell = _source(APP_SHELL)
    overview = _source(CASE_OVERVIEW)
    activity = _source(ACTIVITY_TRACE)

    assert 'kind: "activity"' in shell
    assert '/activity' in shell
    assert "<ActivityTrace" in shell
    assert "onOpenActivity" in overview
    assert 'copy("研究记录", "Research trace")' in overview

    for call in ("caseApi.getCase", "planningApi.getDecisionSurface", "executionApi.listWorkUnits", "executionApi.getActivityTrace"):
        assert call in activity

    assert 'projection?.surface.review_status === "accepted"' in activity
    assert 'workUnit.state === "pending"' in activity
    assert "projection.execution.work_units.length === 0" in activity
    assert "{canStart ? (" in activity
    assert 'work_unit_type: P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE' in activity
    assert 'P36_EVIDENCE_FIXTURE_WORK_UNIT_TYPE = "p36_evidence_fixture_entry"' in _source(EXECUTION_CLIENT)
    assert "expected_case_version: projection.workspace.case_version" in activity
    assert "decisionSurfaceInputHeadDigest(projection.surface.contract_version_id)" in activity

    assert 'if (workUnit.state !== "pending") return' in activity
    assert "expected_work_unit_version: workUnit.work_unit_version" in activity
    assert "expected_state_version: workUnit.state_version" in activity
    assert "fencing_token: FIXTURE_NO_LEASE_FENCING_TOKEN" in activity
    assert 'FIXTURE_NO_LEASE_FENCING_TOKEN = "fixture-no-lease"' in _source(EXECUTION_CLIENT)
    assert "actor_ref: executionApi.actorRef" in activity
    assert "idempotency_key:" in activity


def test_activity_renders_restored_states_stops_next_action_and_reopen() -> None:
    source = _source(ACTIVITY_TRACE)

    for state in ("loading", "empty", "offline", "permission", "conflict", "stale", "error"):
        assert re.search(rf'"{state}"', source)
    assert "useWorkbenchLocale" in source
    assert "labelToken(state)" in source
    assert "projection.activity.events" in source
    assert "left.sequence - right.sequence" in source
    assert "event.typed_stop" in source
    assert "Recorded stop" in source
    assert "Next action" in source
    assert "Return to case overview" in source
    assert "Return to research cases" in source
    assert "const hasWorkUnit = projection.execution.work_units.length > 0" in source
    assert "Reopen current" in source
    assert "load(true)" in source
    assert "load(false)" in source


def test_activity_surface_does_not_add_unadmitted_authority_or_transport() -> None:
    combined = "\n".join((_source(EXECUTION_CLIENT), _source(ACTIVITY_TRACE), _source(APP_SHELL), _source(CASE_OVERVIEW)))
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "openDatabase(",
        "FileSystemHandle",
        "EventSource(",
        "WebSocket(",
        "/runs",
        "/attempts",
        "/artifacts",
        "/models",
        "/tools",
        "/providers",
        "resumeWorkUnit",
        "retryWorkUnit",
    ):
        assert forbidden not in combined
