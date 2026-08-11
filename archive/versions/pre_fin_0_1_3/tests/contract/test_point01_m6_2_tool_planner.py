from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.tool_planner import BoundedToolPlanner, PlannerPermissionContext, ToolPlannerError, ToolRegistryEntry, ToolRegistrySnapshot


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_2_tool_planner_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_2_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_issuer_plan_is_authority_first_replayable_and_nonexecuting() -> None:
    snapshot, policy = RUNNER.registry_and_policy()
    planner = BoundedToolPlanner(registry=snapshot, policy=policy)
    request = RUNNER._request(sector="saas")
    first = planner.plan(request=request, permissions=RUNNER.permissions(snapshot))
    second = planner.plan(request=request, permissions=RUNNER.permissions(snapshot))
    assert first.plan.plan_digest == second.plan.plan_digest
    assert [step.selected_tool_id for step in first.plan.steps] == ["issuer_disclosure_metadata_tool", "official_company_commentary_metadata_tool"]
    assert first.plan.steps[0].execution_admission == "required_m5_4_capability_check"
    assert all(step.invocation_status == "not_executed" for step in first.plan.steps)
    assert first.tool_invocation_count == 0


def test_relationship_context_and_commercial_gap_follow_distinct_stop_rules() -> None:
    snapshot, policy = RUNNER.registry_and_policy()
    planner = BoundedToolPlanner(registry=snapshot, policy=policy)
    relationship = RUNNER._request(
        sector="relationship",
        evidence_role="relationship_signal",
        source_policy_ref="relationship_graph_only",
        acceptance_role="bounded_context_only",
        forbidden_substitutions=("issuer_metric_substitute",),
        metric_scope=(),
    )
    relationship_plan = planner.plan(request=relationship, permissions=RUNNER.permissions(snapshot)).plan
    assert [step.selected_tool_id for step in relationship_plan.steps] == ["relationship_graph_metadata_tool"]
    commercial = RUNNER._request(
        sector="commercial",
        evidence_role="commercial_tracker_metric",
        source_policy_ref="commercial_gap",
        acceptance_role="primary_or_bounded_context",
        forbidden_substitutions=("public_proxy_as_exact",),
        metric_scope=(),
    )
    commercial_plan = planner.plan(request=commercial, permissions=RUNNER.permissions(snapshot)).plan
    assert commercial_plan.status == "stopped"
    assert commercial_plan.stop_reason == "commercial_gap_stop_rule"
    assert commercial_plan.steps == ()


def test_planner_fails_closed_for_permission_context_and_duplicate_registry() -> None:
    snapshot, policy = RUNNER.registry_and_policy()
    request = RUNNER._request(sector="banks")
    denied = BoundedToolPlanner(registry=snapshot, policy=policy).plan(
        request=request,
        permissions=RUNNER.permissions(snapshot, allowed_tool_ids=()),
    ).plan
    assert denied.stop_reason == "permission_scope_stop_rule"
    with pytest.raises(ToolPlannerError, match="planner_permission_context_must_not_claim_execution_authority"):
        BoundedToolPlanner(registry=snapshot, policy=policy).plan(
            request=request,
            permissions=PlannerPermissionContext(
                permission_snapshot_ref="permission",
                allowed_tool_ids=tuple(entry.tool_id for entry in snapshot.entries),
                required_permission_scope="runtime_read_only",
                context_kind="execution_authority",
            ),
        )
    with pytest.raises(ToolPlannerError, match="duplicate_tool_registry_id"):
        ToolRegistrySnapshot.create(registry_id="duplicate", registry_version=1, entries=(snapshot.entries[0], snapshot.entries[0]))


def test_m6_2_review_is_user_scoped_and_does_not_claim_independent_human_signoff() -> None:
    review = json.loads((ROOT / "configs/engineering_handoff/point01_m6_2_cross_owner_design_review_v1_0.json").read_text(encoding="utf-8"))
    assert review["status"] == "user_confirmed_structured_cross_owner_review_accepted_for_m6_2"
    assert review["independent_human_or_multi_person_signoff"] is False
    assert review["user_confirmation"]["decision"] == "approve_m6_2_deterministic_tool_registry_and_selection_plan_only"


def test_m6_2_fixture_runner_covers_routes_stops_and_no_execution(tmp_path: Path) -> None:
    output = tmp_path / "m6_2_fixture.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["issuer_primary_and_bounded_fallback"] is True
    assert result["checks"]["commercial_gap_stops"] is True
    assert result["authority_boundary"]["tool_invocation_count"] == 0
