from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "configs/releases/point02_p02_4_vertical_contract_increment_v1_0.json"
FRONTEND_ROOT = ROOT / "apps/workbench/frontend/vite/src"
PLANNING_CLIENT = FRONTEND_ROOT / "api/planning.ts"
APP_SHELL = FRONTEND_ROOT / "app/AppShell.tsx"
TASK_CENTER = FRONTEND_ROOT / "features/task-center/TaskCenter.tsx"
CASE_OVERVIEW = FRONTEND_ROOT / "features/case-overview/CaseOverview.tsx"
DECISION_SURFACE = FRONTEND_ROOT / "features/decision-surface/DecisionSurface.tsx"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_frontend_planning_client_binds_the_approved_increment() -> None:
    contract = _load(CONTRACT_PATH)
    source = _source(PLANNING_CLIENT)

    assert _canonical_digest(contract) == "83319c49d2c91616503e83a2fce31ff2837792ecbbdb6015aaa08f4c85cfffb7"
    # The historical P02.4 contract remains immutable while the current VT4
    # browser entry binds the approved ten-cell candidate profile.
    assert 'P36_COMPILER_POLICY_REF = "fixture:p36-ten-cell-v1"' in source
    assert 'P36_PACK_SELECTION_REF = "fixture:p36-ai-infrastructure-v2"' in source

    operations = {row["operation_id"]: row for row in contract["api_delta"]["operations"]}
    expected_calls = {
        "compileDecisionSurface": ("/planning/compile", 'mutationInit("POST", command)'),
        "reviseDecisionSurface": ("/decision-surface", 'mutationInit("PATCH", command)'),
        "reviewPlanningCheckpoint": ("/planning/checkpoint", 'mutationInit("POST", command)'),
        "getDecisionSurface": ("/decision-surface", "this.request<DecisionSurfaceView>"),
    }
    assert set(operations) == set(expected_calls)
    for operation_id, (path_suffix, call_token) in expected_calls.items():
        assert re.search(rf"\b{operation_id}\b", source)
        assert path_suffix in source
        assert call_token in source

    for schema in contract["api_delta"]["wire_schemas"].values():
        for field in schema["required"]:
            assert re.search(rf"\b{re.escape(field)}\b", source)
    assert '"Idempotency-Key": command.idempotency_key' in source

    for permission in contract["api_delta"]["permissions"].values():
        assert f'"{permission}"' in source


def test_frontend_renders_complete_nested_decision_surface_projection() -> None:
    contract = _load(CONTRACT_PATH)
    client = _source(PLANNING_CLIENT)
    surface = _source(DECISION_SURFACE)

    for field in contract["api_delta"]["decision_surface_view_required"]:
        assert re.search(rf"\b{re.escape(field)}\b", client)
    for field in contract["api_delta"]["cell_view_required"]:
        assert re.search(rf"\b{re.escape(field)}\b", client)
        assert re.search(rf"\b{re.escape(field)}\b", surface)
    for field in contract["api_delta"]["evidence_slot_view_required"]:
        assert re.search(rf"\b{re.escape(field)}\b", client)
        assert re.search(rf"\b{re.escape(field)}\b", surface)

    assert "cell.evidence_slots.map" in surface
    assert "planningApi.reviseDecisionSurface" in surface
    assert 'review("accept")' in surface
    assert 'review("return")' in surface
    assert "expected_decision_surface_contract_version: projection.surface.contract_version" in surface
    assert "expected_checkpoint_version: projection.surface.checkpoint_version" in surface
    assert "expected_case_version: projection.workspace.case_version" in surface


def test_frontend_flow_keeps_api_projection_authoritative_across_routes_and_filters() -> None:
    shell = _source(APP_SHELL)
    task_center = _source(TASK_CENTER)
    overview = _source(CASE_OVERVIEW)
    surface = _source(DECISION_SURFACE)
    planning = _source(PLANNING_CLIENT)
    combined = "\n".join((shell, task_center, overview, surface, planning))

    for path in ("/tasks", "/cases/new", "/overview", "/decision-surface"):
        assert path in shell
    for token in ("listCases", "createCase", "getCase", "getDecisionSurface", "compileDecisionSurface"):
        assert token in combined

    assert "new Set(items.map((item) => item.status))" in task_center
    assert "items.filter((item) => item.status === statusFilter)" in task_center
    assert "setStatusFilter" in task_center
    assert "P36_COMPILER_POLICY_REF" in overview
    assert "P36_PACK_SELECTION_REF" in overview
    assert "expected_case_version: workspace.case_version" in overview
    assert "expected_summary_version: workspace.summary_version" in overview
    assert "Prepare research cells" in overview
    assert "localizeFixtureText(workspace.query)" in overview
    assert "useWorkbenchLocale" in overview
    assert "Compile new version" not in overview

    for state in ("loading", "empty", "offline", "permission", "conflict", "stale", "reconnecting"):
        assert state in combined

    for forbidden in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "openDatabase(",
        "FileSystemHandle",
        "WebSocket(",
        "EventSource(",
        "/model",
        "/runs",
        "/work-units",
    ):
        assert forbidden not in combined


def test_revision_and_review_use_api_responses_without_local_version_increments() -> None:
    surface = _source(DECISION_SURFACE)

    assert "const surface = await planningApi.reviseDecisionSurface" in surface
    assert "const surface = await planningApi.reviewPlanningCheckpoint" in surface
    assert 'setRemote({ kind: "ready", data: { workspace: projection.workspace, surface } })' in surface
    assert not re.search(r"contract_version\s*[:=].*\+\s*1", surface)
    assert not re.search(r"checkpoint_version\s*[:=].*\+\s*1", surface)
    assert "keyForAttempt(revisionAttemptRef" in surface
    assert "keyForAttempt(reviewAttemptRef" in surface
