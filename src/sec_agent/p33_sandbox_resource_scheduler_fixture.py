"""P33 no-paid fixture for the sandbox / resource scheduler contract.

S2 proves the tool gateway and sandbox ledger. P12 proves durable runtime,
HIL, and resource router rows. R5 proves deterministic CUDA/CPU scheduling.
P33-1.2 ties those older slices to the P32 L3
``sandbox_resource_scheduler`` contract, so promotion is based on auditable
runtime rows instead of source-learning notes.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.agent_information_economy import build_preflight_information_economy
from sec_agent.project_os_preflight import compact_preflight_stdout, run_project_os_preflight
from sec_agent.r53_r60_durable_runtime_hil_resource_router import (
    P12_RUNTIME_DRILL_TASK_ID,
    build_p12_gate,
    default_p12_paths,
)
from sec_agent.r53_r60_research_to_quant_lab import row_to_dict, rows_to_dicts
from sec_agent.r53_r60_runtime_task_spine import json_loads, rel_path, utc_now_iso, write_json
from sec_agent.r53_r60_tool_sandbox_spine import build_s2_gate, default_s2_paths
from sec_agent.runtime_bridge.resource_scheduler import InferenceTask, schedule_inference_tasks_with_audit


SCHEMA_VERSION = "fin_insight_p33_sandbox_resource_scheduler_fixture_v0_1"
CONTRACT_ID = "l3_sandbox_resource_scheduler_contract_v0_1"
RELEASE_DECISION_PASS = "P33_1_2_L4_scope_pass_sandbox_resource_scheduler_fixture"
RELEASE_DECISION_BLOCKED = "P33_1_2_blocked_sandbox_resource_scheduler_fixture"


@dataclass(frozen=True)
class P33SandboxResourceSchedulerFixturePaths:
    manifest_path: Path
    report_path: Path


def default_p33_sandbox_resource_scheduler_fixture_paths(root: Path) -> P33SandboxResourceSchedulerFixturePaths:
    return P33SandboxResourceSchedulerFixturePaths(
        manifest_path=root / "data" / "manifests" / "p33_sandbox_resource_scheduler_fixture_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_sandbox_resource_scheduler_fixture_report.zh-CN.md",
    )


def build_p33_sandbox_resource_scheduler_fixture(
    root: Path,
    *,
    rebuild_dependencies: bool = True,
    write_outputs: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p33_sandbox_resource_scheduler_fixture_paths(root)
    if rebuild_dependencies:
        s2_summary = build_s2_gate(root)
        p12_summary = build_p12_gate(root)
    else:
        s2_summary = _read_json_if_exists(default_s2_paths(root).summary_path)
        p12_summary = _read_json_if_exists(default_p12_paths(root).summary_path)

    manifest = collect_sandbox_resource_scheduler_fixture_manifest(root, s2_summary=s2_summary, p12_summary=p12_summary)
    if write_outputs:
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_sandbox_resource_scheduler_fixture_report(manifest), encoding="utf-8")
    return manifest


def collect_sandbox_resource_scheduler_fixture_manifest(
    root: Path,
    *,
    s2_summary: Mapping[str, Any],
    p12_summary: Mapping[str, Any],
) -> dict[str, Any]:
    s2_paths = default_s2_paths(root)
    p12_paths = default_p12_paths(root)
    if not s2_paths.db_path.exists():
        raise FileNotFoundError(f"Runtime DB is missing: {s2_paths.db_path}")

    tool_audit = _collect_tool_audit(s2_paths.db_path)
    resource_router_audit = _collect_resource_router_audit(p12_paths.db_path)
    scheduler_audit = _build_scheduler_audit()
    budget_preflight = _build_budget_preflight_failure()
    project_os_preflight = run_project_os_preflight(root)
    contract_projection = _build_contract_projection(tool_audit, resource_router_audit, scheduler_audit, budget_preflight)
    acceptance_gates = evaluate_sandbox_resource_scheduler_fixture_gates(
        s2_summary=s2_summary,
        p12_summary=p12_summary,
        tool_audit=tool_audit,
        resource_router_audit=resource_router_audit,
        scheduler_audit=scheduler_audit,
        budget_preflight=budget_preflight,
        project_os_preflight=project_os_preflight,
        contract_projection=contract_projection,
    )
    fail_count = len([row for row in acceptance_gates if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    paths = default_p33_sandbox_resource_scheduler_fixture_paths(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "contract_id": CONTRACT_ID,
        "status": status,
        "release_decision": RELEASE_DECISION_PASS if status == "pass" else RELEASE_DECISION_BLOCKED,
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "promotion_recommendation": "active_registry_ready_runtime_alignment_only" if status == "pass" else "deferred_pending_repair",
        "promotion_scope": "sandbox_resource_initial",
        "absorbed_contract_ids": [CONTRACT_ID],
        "artifacts": [
            {
                "artifact_type": "p33_sandbox_resource_scheduler_fixture",
                "contract_aligned_plan": {
                    "absorbed_contract_ids": [CONTRACT_ID],
                    "used_case_contract_ids": [CONTRACT_ID],
                },
            }
        ],
        "source_fixture_refs": {
            "s2_summary": rel_path(default_s2_paths(root).summary_path, root),
            "s2_gate_rows": rel_path(default_s2_paths(root).gate_rows_path, root),
            "p12_summary": rel_path(default_p12_paths(root).summary_path, root),
            "p12_gate_rows": rel_path(default_p12_paths(root).gate_rows_path, root),
            "runtime_db": rel_path(default_p12_paths(root).db_path, root),
            "p33_manifest": rel_path(paths.manifest_path, root),
            "p33_report": rel_path(paths.report_path, root),
        },
        "input_contract_required_fields": [
            "agent_id",
            "tool_or_model_id",
            "requested_capability",
            "network_scope",
            "credential_scope",
            "resource_class",
            "budget_policy",
        ],
        "output_contract_required_fields": [
            "permission_decision",
            "queue_event_id",
            "resource_route",
            "budget_decision",
            "tool_or_model_call_ref",
            "failure_or_spillover_reason",
            "audit_artifact_ref",
        ],
        "tool_audit": tool_audit,
        "resource_router_audit": resource_router_audit,
        "scheduler_audit": scheduler_audit,
        "budget_preflight": budget_preflight,
        "project_os_preflight": compact_preflight_stdout(project_os_preflight),
        "contract_projection": contract_projection,
        "acceptance_gates": acceptance_gates,
        "gate_fail_count": fail_count,
        "runtime_entry_policy": (
            "Runtime alignment only: may align SandboxPolicy, ApprovalPolicy, "
            "ToolInvocationLedger, ResourceQueuePolicy, BudgetExceededGate, "
            "ModelProviderRouter, and AgentInformationEconomyLedger. It does not "
            "claim cloud/Kubernetes/vLLM production scheduling or all production tools."
        ),
        "do_not_promote": [
            "allow_all_network",
            "silent_cpu_fallback",
            "paid_full_chain_budget_bypass",
            "credential_argument_persisted",
            "unknown_tool_allowed",
        ],
        "rollback_gate": [
            "forbidden_tool_access_succeeds",
            "queue_or_spillover_not_audited",
            "budget_preflight_allows_expensive_fanout",
            "cpu_spillover_without_latency_or_quality_boundary",
        ],
    }


def _collect_tool_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        invocations = rows_to_dicts(
            conn.execute(
                """
                select tool_call_id, task_id, actor_id, node, tool_id, status,
                       policy_decision, sandbox_policy_id, approval_policy_id,
                       approval_decision_id, blocked_reason, payload_json
                from tool_invocations
                where task_id = 's2_scope_task_tool_sandbox'
                order by created_at, tool_call_id
                """
            ).fetchall()
        )
        approval_rows = rows_to_dicts(
            conn.execute(
                """
                select approval_decision_id, task_id, actor_id, tool_id, decision,
                       approver_actor_id, reason
                from approval_decisions
                where task_id = 's2_scope_task_tool_sandbox'
                order by created_at, approval_decision_id
                """
            ).fetchall()
        )
        policies = rows_to_dicts(
            conn.execute(
                """
                select tool_id, allowed_actors_json, sandbox_policy_id,
                       approval_policy_id, source_boundary, artifact_type, payload_json
                from tool_policy_bindings
                order by tool_id
                """
            ).fetchall()
        )

    blocked_reasons = sorted({str(row.get("blocked_reason") or "") for row in invocations if row.get("status") == "blocked"})
    payload_text = "\n".join(str(row.get("payload_json") or "") for row in invocations)
    return {
        "status": "pass",
        "tool_invocation_count": len(invocations),
        "executed_count": len([row for row in invocations if row.get("status") == "executed"]),
        "blocked_count": len([row for row in invocations if row.get("status") == "blocked"]),
        "blocked_reasons": blocked_reasons,
        "approval_decision_count": len(approval_rows),
        "policy_binding_count": len(policies),
        "secret_redacted": "redacted-test-value" not in payload_text and "[REDACTED]" in payload_text,
        "sample_invocations": [_compact_tool_invocation(row) for row in invocations],
        "approval_rows": approval_rows,
    }


def _collect_resource_router_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        route_policies = rows_to_dicts(
            conn.execute(
                """
                select route_policy_id, route_class, preferred_model, fallback_model,
                       resource_class, queue_class, max_tokens, cost_cap_usd,
                       spillover_policy, status
                from resource_model_route_policies_p12
                order by route_class
                """
            ).fetchall()
        )
        queue_events = rows_to_dicts(
            conn.execute(
                """
                select queue_event_id, task_id, route_policy_id, route_class, event_type,
                       assigned_model, assigned_resource, queue_wait_ms, token_count,
                       cost_amount, status
                from resource_queue_events_p12
                where task_id = ?
                order by route_class, queue_event_id
                """,
                (P12_RUNTIME_DRILL_TASK_ID,),
            ).fetchall()
        )
        budget_rows = rows_to_dicts(
            conn.execute(
                """
                select budget_id, task_id, budget_scope, token_budget, tokens_used,
                       cost_budget_usd, cost_used_usd, status
                from model_budget_ledger_p12
                where task_id = ?
                order by budget_id
                """,
                (P12_RUNTIME_DRILL_TASK_ID,),
            ).fetchall()
        )
        readiness = row_to_dict(conn.execute("select * from runtime_readiness_reports_p12 limit 1").fetchone())
    return {
        "status": "pass",
        "route_policy_count": len(route_policies),
        "queue_event_count": len(queue_events),
        "budget_record_count": len(budget_rows),
        "route_policies": route_policies,
        "queue_events": queue_events,
        "budget_rows": budget_rows,
        "readiness_status": {
            "resource_router_status": readiness.get("resource_router_status", ""),
            "release_decision": readiness.get("release_decision", ""),
            "full_runtime_migration_status": readiness.get("full_runtime_migration_status", ""),
        },
    }


def _build_scheduler_audit() -> dict[str, Any]:
    tasks = [
        InferenceTask(f"p33_bge_{idx}", route="retrieval", priority=idx, requires_cuda_bge=True, can_spill_to_cpu=True)
        for idx in range(1, 6)
    ]
    tasks.extend(
        [
            InferenceTask("p33_research_lead", route="research_lead", priority=6, model_tier="pro"),
            InferenceTask("p33_memo_writer", route="memo_writer", priority=7, model_tier="pro"),
        ]
    )
    spillover_allowed = schedule_inference_tasks_with_audit(
        tasks,
        cuda_bge_slots=2,
        cpu_spillover_allowed=True,
        token_budget_pressure=True,
        per_cuda_task_wait_ms=300,
    )
    spillover_blocked = schedule_inference_tasks_with_audit(
        tasks,
        cuda_bge_slots=2,
        cpu_spillover_allowed=False,
        token_budget_pressure=True,
        per_cuda_task_wait_ms=300,
    )
    return {
        "status": "pass",
        "cpu_spillover_allowed": spillover_allowed.__dict__,
        "cpu_spillover_blocked": spillover_blocked.__dict__,
    }


def _build_budget_preflight_failure() -> dict[str, Any]:
    plan = {
        "run_id": "p33_sandbox_resource_scheduler_budget_preflight_unit",
        "allowed": False,
        "status": "blocked_preflight_token_budget",
        "estimated_total_tokens": 272000,
        "estimated_paid_call_count": 18,
        "scheduler_advice": {"status": "case_budget_repair_required", "recommended_batch_count": 0},
        "cases": [
            {
                "case_id": "p33_ai_semis_budget_guard",
                "estimated_total_tokens": 150000,
                "estimated_paid_call_count": 9,
                "estimated_specialist_count": 5,
                "prunable_specialist_agents": ["market_valuation_analyst"],
                "estimated_total_tokens_after_specialist_pruning": 138000,
                "estimated_paid_call_count_after_specialist_pruning": 8,
                "nodes": [
                    {"node": "research_lead", "estimated_total_tokens": 11000},
                    {"node": "fundamental_analyst", "estimated_total_tokens": 20000},
                    {"node": "product_technology_analyst", "estimated_total_tokens": 18000},
                    {"node": "industry_supply_chain_analyst", "estimated_total_tokens": 17000},
                    {"node": "market_valuation_analyst", "estimated_total_tokens": 15000},
                    {"node": "risk_counterevidence_analyst", "estimated_total_tokens": 16000},
                    {"node": "memo_writer", "estimated_total_tokens": 25000},
                    {"node": "verifier", "estimated_total_tokens": 9000},
                    {"node": "universe_relationship", "estimated_total_tokens": 11000},
                ],
            }
        ],
    }
    return build_preflight_information_economy(plan)


def _build_contract_projection(
    tool_audit: Mapping[str, Any],
    resource_router_audit: Mapping[str, Any],
    scheduler_audit: Mapping[str, Any],
    budget_preflight: Mapping[str, Any],
) -> list[dict[str, Any]]:
    projection: list[dict[str, Any]] = []
    for row in tool_audit.get("sample_invocations") or []:
        if not isinstance(row, Mapping):
            continue
        projection.append(
            {
                "agent_id": row.get("actor_id", ""),
                "tool_or_model_id": row.get("tool_id", ""),
                "requested_capability": "tool_invocation",
                "network_scope": _network_scope_for_tool(str(row.get("tool_id") or "")),
                "credential_scope": "forbidden_by_default",
                "resource_class": "tool_gateway",
                "budget_policy": "tool_timeout_output_and_approval_policy",
                "permission_decision": row.get("policy_decision", ""),
                "queue_event_id": "",
                "resource_route": row.get("sandbox_policy_id", ""),
                "budget_decision": "no_paid_model_call",
                "tool_or_model_call_ref": row.get("tool_call_id", ""),
                "failure_or_spillover_reason": row.get("blocked_reason", ""),
                "audit_artifact_ref": "tool_invocations",
            }
        )
    for row in resource_router_audit.get("queue_events") or []:
        if not isinstance(row, Mapping):
            continue
        projection.append(
            {
                "agent_id": "runtime_facade",
                "tool_or_model_id": row.get("assigned_model", ""),
                "requested_capability": row.get("route_class", ""),
                "network_scope": "provider_or_local_resource",
                "credential_scope": "provider_key_not_exposed_to_agent",
                "resource_class": row.get("assigned_resource", ""),
                "budget_policy": "model_budget_ledger_p12",
                "permission_decision": "route_allowed",
                "queue_event_id": row.get("queue_event_id", ""),
                "resource_route": row.get("route_class", ""),
                "budget_decision": row.get("status", ""),
                "tool_or_model_call_ref": row.get("queue_event_id", ""),
                "failure_or_spillover_reason": row.get("event_type", ""),
                "audit_artifact_ref": "resource_queue_events_p12",
            }
        )
    projection.append(
        {
            "agent_id": "preflight_guard",
            "tool_or_model_id": "paid_full_chain",
            "requested_capability": "expensive_eval_preflight",
            "network_scope": "provider_call_blocked_before_execution",
            "credential_scope": "not_requested",
            "resource_class": "paid_llm",
            "budget_policy": budget_preflight.get("policy", ""),
            "permission_decision": "blocked" if budget_preflight.get("status") == "fail" else "allow",
            "queue_event_id": "",
            "resource_route": "not_scheduled",
            "budget_decision": budget_preflight.get("status", ""),
            "tool_or_model_call_ref": "agent_information_economy_preflight",
            "failure_or_spillover_reason": ",".join(sorted((budget_preflight.get("issue_counts") or {}).keys())),
            "audit_artifact_ref": "budget_preflight",
        }
    )
    return projection


def evaluate_sandbox_resource_scheduler_fixture_gates(
    *,
    s2_summary: Mapping[str, Any],
    p12_summary: Mapping[str, Any],
    tool_audit: Mapping[str, Any],
    resource_router_audit: Mapping[str, Any],
    scheduler_audit: Mapping[str, Any],
    budget_preflight: Mapping[str, Any],
    project_os_preflight: Mapping[str, Any],
    contract_projection: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    generated_at = utc_now_iso()

    def gate(gate_id: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "status": "pass" if status else "fail",
            "pass_level": "L4_scope_pass" if status else "blocked",
            "detail": dict(detail),
            "generated_at": generated_at,
        }

    blocked_reasons = set(tool_audit.get("blocked_reasons") or [])
    required_blocked = {
        "actor_tool_not_allowed",
        "domain_not_allowlisted",
        "path_outside_allowed_roots",
        "credential_argument_forbidden",
        "unknown_tool",
        "human_approval_required",
    }
    allowed = scheduler_audit.get("cpu_spillover_allowed") or {}
    blocked = scheduler_audit.get("cpu_spillover_blocked") or {}
    allowed_lanes = allowed.get("lane_counts") or {}
    blocked_lanes = blocked.get("lane_counts") or {}
    blocked_tasks = blocked.get("scheduled_tasks") or []
    queued_wait_ok = any(
        isinstance(row, Mapping) and row.get("lane") == "queued_bge_cuda" and int(row.get("estimated_wait_ms") or 0) > 0
        for row in blocked_tasks
    )
    issue_counts = budget_preflight.get("issue_counts") if isinstance(budget_preflight.get("issue_counts"), Mapping) else {}
    projection_fields = {
        "permission_decision",
        "queue_event_id",
        "resource_route",
        "budget_decision",
        "tool_or_model_call_ref",
        "failure_or_spillover_reason",
        "audit_artifact_ref",
    }
    return [
        gate(
            "p33_1_2_s2_tool_sandbox_l4_pass",
            s2_summary.get("release_decision") == "S2_L4_scope_pass" and int((s2_summary.get("counts") or {}).get("gate_fail_count") or 0) == 0,
            {"release_decision": s2_summary.get("release_decision"), "counts": s2_summary.get("counts")},
        ),
        gate(
            "p33_1_2_forbidden_tools_fail_closed",
            required_blocked.issubset(blocked_reasons),
            {"required_blocked": sorted(required_blocked), "observed": sorted(blocked_reasons)},
        ),
        gate(
            "p33_1_2_secret_redaction_and_hil_approval",
            bool(tool_audit.get("secret_redacted")) and int(tool_audit.get("approval_decision_count") or 0) >= 1,
            {"secret_redacted": tool_audit.get("secret_redacted"), "approval_decision_count": tool_audit.get("approval_decision_count")},
        ),
        gate(
            "p33_1_2_p12_resource_router_l4_pass",
            p12_summary.get("release_decision") == "P12_L4_scope_pass_runtime_drill_ready"
            and int((p12_summary.get("counts") or {}).get("gate_fail_count") or 0) == 0
            and resource_router_audit.get("readiness_status", {}).get("resource_router_status") == "resource_router_ledger_pass",
            {"release_decision": p12_summary.get("release_decision"), "readiness": resource_router_audit.get("readiness_status")},
        ),
        gate(
            "p33_1_2_route_queue_and_budget_rows_present",
            int(resource_router_audit.get("route_policy_count") or 0) >= 4
            and int(resource_router_audit.get("queue_event_count") or 0) >= 5
            and int(resource_router_audit.get("budget_record_count") or 0) >= 1,
            {
                "route_policy_count": resource_router_audit.get("route_policy_count"),
                "queue_event_count": resource_router_audit.get("queue_event_count"),
                "budget_record_count": resource_router_audit.get("budget_record_count"),
            },
        ),
        gate(
            "p33_1_2_gpu_queue_cpu_spillover_audited",
            int(allowed_lanes.get("bge_cuda") or 0) == 2
            and int(allowed_lanes.get("bge_cpu_spillover") or 0) >= 3
            and int(blocked_lanes.get("queued_bge_cuda") or 0) >= 3
            and queued_wait_ok,
            {"allowed_lanes": allowed_lanes, "blocked_lanes": blocked_lanes, "queued_wait_ok": queued_wait_ok},
        ),
        gate(
            "p33_1_2_budget_preflight_blocks_expensive_fanout",
            budget_preflight.get("status") == "fail"
            and {
                "preflight_case_token_budget_high",
                "preflight_paid_call_fanout_high",
                "preflight_specialist_fanout_broad",
            }.issubset(set(issue_counts.keys())),
            {"status": budget_preflight.get("status"), "issue_counts": dict(issue_counts)},
        ),
        gate(
            "p33_1_2_project_os_preflight_executable",
            project_os_preflight.get("status") in {"pass", "blocked", "diagnostic_override"}
            and str(project_os_preflight.get("policy") or "").startswith("fail_closed"),
            {"status": project_os_preflight.get("status"), "errors": project_os_preflight.get("errors")},
        ),
        gate(
            "p33_1_2_contract_projection_fields_complete",
            bool(contract_projection) and all(projection_fields.issubset(set(row.keys())) for row in contract_projection),
            {"projection_count": len(contract_projection), "required_fields": sorted(projection_fields)},
        ),
    ]


def render_sandbox_resource_scheduler_fixture_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# P33-1.2 Sandbox / Resource Scheduler Fixture Report",
        "",
        f"- Contract: `{manifest.get('contract_id')}`",
        f"- Status: `{manifest.get('status')}`",
        f"- Release decision: `{manifest.get('release_decision')}`",
        f"- Closeout level: `{manifest.get('closeout_level')}`",
        f"- Promotion recommendation: `{manifest.get('promotion_recommendation')}`",
        "",
        "## What This Proves",
        "",
        "- Tool/network/path/credential/unknown-tool access fails closed and is ledgered.",
        "- Human approval is required for bounded local execution and the decision is recorded.",
        "- Runtime resource routes, queue events, token/cost budget rows and SQL audit rows exist.",
        "- CUDA BGE slots, explicit CPU spillover, queued CUDA wait and token-budget blocking are auditable before paid/full-chain.",
        "",
        "## Acceptance Gates",
        "",
    ]
    for row in manifest.get("acceptance_gates") or []:
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('status')}` `{row.get('gate_id')}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            str(manifest.get("runtime_entry_policy") or ""),
            "",
            "## Source Fixture Refs",
            "",
        ]
    )
    for key, value in (manifest.get("source_fixture_refs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def _compact_tool_invocation(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "tool_call_id": row.get("tool_call_id", ""),
        "actor_id": row.get("actor_id", ""),
        "node": row.get("node", ""),
        "tool_id": row.get("tool_id", ""),
        "status": row.get("status", ""),
        "policy_decision": row.get("policy_decision", ""),
        "sandbox_policy_id": row.get("sandbox_policy_id", ""),
        "approval_policy_id": row.get("approval_policy_id", ""),
        "approval_decision_id": row.get("approval_decision_id", ""),
        "blocked_reason": row.get("blocked_reason", ""),
    }


def _network_scope_for_tool(tool_id: str) -> str:
    if tool_id == "live_web_snapshot":
        return "domain_allowlist_only"
    return "none_or_local"


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json_loads(path.read_text(encoding="utf-8"), {})
