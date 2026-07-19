from __future__ import annotations

import json
import re
from pathlib import Path

from sec_agent.canonical_runtime.candidate_bundle import CandidateBundlePolicy
from sec_agent.canonical_runtime.evidence_request import EvidenceRequestPolicy
from sec_agent.canonical_runtime.tool_planner import PlannerPolicy, ToolRegistryEntry, ToolRegistrySnapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "configs" / "releases" / "point03_vt1_evidence_workbench_contract_v1_0.json"
FRONTEND_ROOT = REPO_ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"
EVIDENCE_CLIENT_PATH = FRONTEND_ROOT / "api" / "evidence.ts"
EVIDENCE_WORKBENCH_PATH = FRONTEND_ROOT / "features" / "evidence-workbench" / "EvidenceWorkbench.tsx"
APP_SHELL_PATH = FRONTEND_ROOT / "app" / "AppShell.tsx"
CASE_OVERVIEW_PATH = FRONTEND_ROOT / "features" / "case-overview" / "CaseOverview.tsx"
ACTIVITY_TRACE_PATH = FRONTEND_ROOT / "features" / "activity-trace" / "ActivityTrace.tsx"
SHELL_CSS_PATH = FRONTEND_ROOT / "app" / "p02-shell.css"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_contract_closes_three_cell_fixture_scope_and_browser_routes() -> None:
    contract = _contract()

    assert contract["status"] == "active_fixture_shadow_internal_development"
    assert contract["active_slot_roles"] == ["demand_signal", "revenue_capture", "thesis_counterevidence"]
    assert {(route["method"], route["operation"]) for route in contract["routes"]} == {
        ("GET", "getEvidenceWorkbench"),
        ("POST", "compileEvidenceFixture"),
        ("POST", "rejectEvidenceCandidate"),
        ("POST", "requestEvidenceRepair"),
    }
    assert contract["review_actions"]["force_accept"] == "forbidden_until_Point04_promotion"


def test_contract_reuses_strict_point01_compiler_planner_and_bundle_models() -> None:
    contract = _contract()

    request_policy = EvidenceRequestPolicy.model_validate(contract["evidence_request_policy"])
    tools = tuple(ToolRegistryEntry.model_validate(tool) for tool in contract["tool_registry"]["tools"])
    registry = ToolRegistrySnapshot.create(
        registry_id=contract["tool_registry"]["registry_id"],
        registry_version=contract["tool_registry"]["registry_version"],
        entries=tools,
    )
    planner_policy = PlannerPolicy.model_validate(contract["planner_policy"])
    candidate_policy = CandidateBundlePolicy.model_validate(contract["candidate_policy"])

    assert set(request_policy.role_rules) == set(contract["active_slot_roles"])
    assert len(registry.entries) == 3
    assert planner_policy.required_execution_admission == "not_admitted_fixture_plan_only"
    assert set(candidate_policy.required_candidate_kinds_by_evidence_role) == {
        "demand_candidate",
        "revenue_candidate",
        "counterevidence_candidate",
    }


def test_fixture_candidates_are_metadata_only_and_counterevidence_is_an_explicit_gap() -> None:
    contract = _contract()
    fixture_sets = contract["fixture_candidate_sets"]

    assert len(fixture_sets["demand_signal"]) == 2
    assert len(fixture_sets["revenue_capture"]) == 2
    assert fixture_sets["thesis_counterevidence"] == []
    for entries in fixture_sets.values():
        for entry in entries:
            assert entry["metadata"]["content_ref"].startswith("fixture://")
            assert entry["metadata"]["document_version"] == "fixture:v1"
            assert "excerpt" in entry["display"]
            assert "applicability_boundary" in entry["display"]


def test_contract_keeps_every_external_and_promotion_boundary_closed() -> None:
    boundaries = _contract()["hard_boundaries"]

    for key in (
        "retrieval_execution",
        "tool_invocation",
        "network_calls",
        "model_calls",
        "provider_calls",
        "paid_full_chain",
        "attempts",
        "artifacts",
    ):
        assert boundaries[key] == 0
    assert boundaries["evidence_promotion"] == "not_in_Point03_VT1"
    assert boundaries["numeric_parsing"] == "not_in_Point03_VT1"


def test_frontend_evidence_client_binds_routes_permissions_and_exact_versions() -> None:
    contract = _contract()
    source = _source(EVIDENCE_CLIENT_PATH)

    for route in contract["routes"]:
        assert re.search(rf"\b{re.escape(route['operation'])}\b", source)
        assert f'"{route["permission"]}"' in source

    for suffix in (
        "/evidence",
        "/compile",
        "/candidates/${encodeURIComponent(candidateId)}/reject",
        "/slots/${encodeURIComponent(evidenceSlotId)}/request-repair",
    ):
        assert suffix in source

    for field in (
        "expected_workspace_version",
        "reason",
        "actor_ref",
        "idempotency_key",
    ):
        assert re.search(rf"\b{field}\b", source)
    assert '"Idempotency-Key": command.idempotency_key' in source


def test_frontend_evidence_workbench_renders_three_cell_review_surface_and_boundaries() -> None:
    source = _source(EVIDENCE_WORKBENCH_PATH)

    for token in (
        "All ${evidence.cells.length} research cells",
        "SummaryStrip",
        "CandidateInspector",
        "candidate",
        "context_only",
        "rejected",
        "typed_gap",
        "repair_requested",
        "Source",
        "Authority",
        "Citation",
        "Published",
        "Applicability boundary",
        "Not promoted",
        "Prepare evidence fixture",
        "Reject candidate",
        "Request source repair",
        "required",
        "useWorkbenchLocale",
    ):
        assert token in source

    for state in ("loading", "empty", "offline", "permission", "conflict", "stale", "error"):
        assert re.search(rf'"{state}"', source)

    assert "evidenceApi.getEvidenceWorkbench" in source
    assert "evidenceApi.compileEvidenceFixture" in source
    assert "evidenceApi.rejectEvidenceCandidate" in source
    assert "evidenceApi.requestEvidenceRepair" in source
    assert "expected_workspace_version: projection.evidence.workspace_version" in source
    assert "if (!projection || !reviewDraft || !reason.trim()) return" in source
    assert "setRemote({ kind: \"ready\", data: { ...projection, evidence: updated } })" in source


def test_frontend_route_and_entry_points_open_evidence_without_unadmitted_controls() -> None:
    shell = _source(APP_SHELL_PATH)
    overview = _source(CASE_OVERVIEW_PATH)
    activity = _source(ACTIVITY_TRACE_PATH)
    workbench = _source(EVIDENCE_WORKBENCH_PATH)
    client = _source(EVIDENCE_CLIENT_PATH)
    css = _source(SHELL_CSS_PATH)
    combined = "\n".join((shell, overview, activity, workbench, client))

    assert 'kind: "evidence"' in shell
    assert "/evidence" in shell
    assert "<EvidenceWorkbench" in shell
    assert "onOpenEvidence" in overview
    assert "onOpenEvidence" in activity
    assert ".p03-workbench-grid" in css
    assert "@media (max-width: 720px)" in css
    assert "minmax(0, 1fr)" in css

    for forbidden in (
        "forceAccept",
        "force_accept",
        "acceptEvidenceCandidate",
        "promoteEvidence",
        "/promote",
        "localStorage",
        "sessionStorage",
        "EventSource(",
        "WebSocket(",
        "/attempts",
        "/artifacts",
        "/models",
        "/providers",
    ):
        assert forbidden not in combined
