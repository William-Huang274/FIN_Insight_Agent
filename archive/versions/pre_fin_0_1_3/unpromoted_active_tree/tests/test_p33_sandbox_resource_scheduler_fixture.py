from __future__ import annotations

from pathlib import Path

from sec_agent.p33_sandbox_resource_scheduler_fixture import (
    CONTRACT_ID,
    build_p33_sandbox_resource_scheduler_fixture,
    default_p33_sandbox_resource_scheduler_fixture_paths,
)
from test_r53_r60_production_pilot_readiness import seed_p11_fixture


def test_p33_sandbox_resource_scheduler_fixture_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    manifest = build_p33_sandbox_resource_scheduler_fixture(tmp_path)

    assert manifest["status"] == "pass"
    assert manifest["release_decision"] == "P33_1_2_L4_scope_pass_sandbox_resource_scheduler_fixture"
    assert manifest["closeout_level"] == "L4_scope_pass"
    assert manifest["absorbed_contract_ids"] == [CONTRACT_ID]
    assert manifest["promotion_recommendation"] == "active_registry_ready_runtime_alignment_only"
    assert manifest["gate_fail_count"] == 0
    assert (tmp_path / manifest["source_fixture_refs"]["p33_manifest"]).exists()
    assert (tmp_path / manifest["source_fixture_refs"]["p33_report"]).exists()


def test_p33_sandbox_resource_scheduler_fixture_enforces_fail_closed_tool_policy(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    manifest = build_p33_sandbox_resource_scheduler_fixture(tmp_path)
    tool_audit = manifest["tool_audit"]

    assert tool_audit["blocked_count"] >= 6
    assert {
        "actor_tool_not_allowed",
        "domain_not_allowlisted",
        "path_outside_allowed_roots",
        "credential_argument_forbidden",
        "unknown_tool",
        "human_approval_required",
    }.issubset(set(tool_audit["blocked_reasons"]))
    assert tool_audit["secret_redacted"] is True
    assert tool_audit["approval_decision_count"] >= 1


def test_p33_sandbox_resource_scheduler_fixture_records_resource_queue_and_budget(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    manifest = build_p33_sandbox_resource_scheduler_fixture(tmp_path)
    resource = manifest["resource_router_audit"]
    scheduler = manifest["scheduler_audit"]
    budget = manifest["budget_preflight"]

    assert resource["readiness_status"]["resource_router_status"] == "resource_router_ledger_pass"
    assert resource["route_policy_count"] >= 4
    assert resource["queue_event_count"] >= 5
    assert resource["budget_record_count"] >= 1

    allowed_lanes = scheduler["cpu_spillover_allowed"]["lane_counts"]
    blocked_lanes = scheduler["cpu_spillover_blocked"]["lane_counts"]
    assert allowed_lanes["bge_cuda"] == 2
    assert allowed_lanes["bge_cpu_spillover"] >= 3
    assert blocked_lanes["queued_bge_cuda"] >= 3
    assert any(row["estimated_wait_ms"] > 0 for row in scheduler["cpu_spillover_blocked"]["scheduled_tasks"])

    assert budget["status"] == "fail"
    assert budget["issue_counts"]["preflight_case_token_budget_high"] == 1
    assert budget["issue_counts"]["preflight_paid_call_fanout_high"] == 1
    assert budget["issue_counts"]["preflight_specialist_fanout_broad"] == 1


def test_p33_sandbox_resource_scheduler_fixture_contract_projection_complete(tmp_path: Path) -> None:
    seed_p11_fixture(tmp_path)
    manifest = build_p33_sandbox_resource_scheduler_fixture(tmp_path)
    required = {
        "permission_decision",
        "queue_event_id",
        "resource_route",
        "budget_decision",
        "tool_or_model_call_ref",
        "failure_or_spillover_reason",
        "audit_artifact_ref",
    }

    assert manifest["contract_projection"]
    assert all(required.issubset(row.keys()) for row in manifest["contract_projection"])
    assert any(row["permission_decision"] == "blocked" for row in manifest["contract_projection"])
    assert any(row["audit_artifact_ref"] == "resource_queue_events_p12" for row in manifest["contract_projection"])
    assert any(row["audit_artifact_ref"] == "budget_preflight" for row in manifest["contract_projection"])

    paths = default_p33_sandbox_resource_scheduler_fixture_paths(tmp_path)
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()
