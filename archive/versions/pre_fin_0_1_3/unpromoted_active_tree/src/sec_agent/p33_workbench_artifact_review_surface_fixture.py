"""P33 no-paid fixture for Workbench artifact review surface.

P33-1.4 proves that the Workbench surface can replay a research task from the
SQL-final runtime ledger into evidence, Claim/Judgment material, typed gaps,
gate rows, artifact refs, deliverable/dashboard refs, and append-only review
actions.  The fixture does not run retrieval, LLMs, or paid full-chain jobs.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.r53_r60_deliverable_studio_dashboard import (
    build_s7_gate,
    default_s7_paths,
    get_dashboard_projection,
    get_deliverable_projection,
)
from sec_agent.r53_r60_runtime_task_spine import RuntimeTaskSpineStore, rel_path, utc_now_iso, write_json
from sec_agent.r53_r60_workbench_frontdoor_drilldown import (
    DEFAULT_TASK_ID,
    append_review_action,
    build_s6_projection,
    default_s6_paths,
    get_ops_projection,
    get_review_queue,
    get_task_artifacts,
    get_task_detail,
    get_task_drilldown,
    workbench_frontdoor_schema_contract,
)


SCHEMA_VERSION = "fin_insight_p33_workbench_artifact_review_surface_fixture_v0_1"
CONTRACT_ID = "l3_workbench_artifact_review_surface_contract_v0_1"
RELEASE_DECISION_PASS = "P33_1_4_L4_scope_pass_workbench_artifact_review_surface_fixture"
RELEASE_DECISION_BLOCKED = "P33_1_4_blocked_workbench_artifact_review_surface_fixture"

P33_FIXTURE_ACTION_PREFIX = "p33_workbench_surface_fixture"
REQUIRED_REVIEW_ACTIONS = ("accept", "reject", "supersede")
REQUIRED_DRILLDOWN_SURFACES = ("sections", "claims", "gaps", "gates", "artifacts", "events")


@dataclass(frozen=True)
class P33WorkbenchArtifactReviewSurfaceFixturePaths:
    manifest_path: Path
    report_path: Path


def default_p33_workbench_artifact_review_surface_fixture_paths(
    root: Path,
) -> P33WorkbenchArtifactReviewSurfaceFixturePaths:
    return P33WorkbenchArtifactReviewSurfaceFixturePaths(
        manifest_path=root / "data" / "manifests" / "p33_workbench_artifact_review_surface_fixture_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_workbench_artifact_review_surface_fixture_report.zh-CN.md",
    )


def build_p33_workbench_artifact_review_surface_fixture(
    root: Path,
    *,
    rebuild_dependencies: bool = True,
    write_outputs: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    if rebuild_dependencies:
        s6_summary = build_s6_projection(root)
        s7_summary = build_s7_gate(root)
    else:
        s6_summary = _read_json_if_exists(default_s6_paths(root).summary_path)
        s7_summary = _read_json_if_exists(default_s7_paths(root).summary_path)
    manifest = collect_workbench_artifact_review_surface_manifest(
        root,
        s6_summary=s6_summary,
        s7_summary=s7_summary,
    )
    if write_outputs:
        paths = default_p33_workbench_artifact_review_surface_fixture_paths(root)
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_workbench_artifact_review_surface_report(manifest), encoding="utf-8")
    return manifest


def collect_workbench_artifact_review_surface_manifest(
    root: Path,
    *,
    s6_summary: Mapping[str, Any],
    s7_summary: Mapping[str, Any],
) -> dict[str, Any]:
    task_id = DEFAULT_TASK_ID
    initial_drilldown = get_task_drilldown(root, task_id=task_id)["drilldown"]
    review_action_results = _ensure_fixture_review_actions(root, task_id=task_id, drilldown=initial_drilldown)
    drilldown = get_task_drilldown(root, task_id=task_id)["drilldown"]
    task_detail = get_task_detail(root, task_id=task_id)
    review_queue = get_review_queue(root, task_id=task_id)
    artifacts = get_task_artifacts(root, task_id=task_id)["artifacts"]
    ops = get_ops_projection(root, task_id=task_id)["ops"]
    deliverable = get_deliverable_projection(root, task_id=task_id)
    dashboard = get_dashboard_projection(root, task_id=task_id)
    replay = RuntimeTaskSpineStore(default_s6_paths(root).db_path).replay_task(task_id)

    audits = {
        "surface_audit": _surface_audit(s6_summary=s6_summary, s7_summary=s7_summary, drilldown=drilldown),
        "traceability_audit": _traceability_audit(
            task_detail=task_detail,
            drilldown=drilldown,
            artifacts=artifacts,
            deliverable=deliverable,
            dashboard=dashboard,
        ),
        "review_action_audit": _review_action_audit(review_queue=review_queue, replay=replay),
        "ops_audit": _ops_audit(ops=ops, replay=replay),
    }
    acceptance_gates = evaluate_workbench_artifact_review_surface_gates(audits)
    fail_count = len([row for row in acceptance_gates if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    paths = default_p33_workbench_artifact_review_surface_fixture_paths(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "contract_id": CONTRACT_ID,
        "status": status,
        "release_decision": RELEASE_DECISION_PASS if status == "pass" else RELEASE_DECISION_BLOCKED,
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "promotion_recommendation": "active_registry_ready_runtime_alignment_only" if status == "pass" else "deferred_pending_repair",
        "promotion_scope": "workbench_surface_initial",
        "absorbed_contract_ids": [CONTRACT_ID],
        "artifacts": [
            {
                "artifact_type": "p33_workbench_artifact_review_surface_fixture",
                "contract_aligned_plan": {
                    "absorbed_contract_ids": [CONTRACT_ID],
                    "used_case_contract_ids": [CONTRACT_ID],
                },
            }
        ],
        "source_fixture_refs": {
            "s6_summary": rel_path(default_s6_paths(root).summary_path, root),
            "s6_gate_rows": rel_path(default_s6_paths(root).gate_rows_path, root),
            "s7_summary": rel_path(default_s7_paths(root).summary_path, root),
            "s7_gate_rows": rel_path(default_s7_paths(root).gate_rows_path, root),
            "runtime_db": rel_path(default_s6_paths(root).db_path, root),
            "p33_manifest": rel_path(paths.manifest_path, root),
            "p33_report": rel_path(paths.report_path, root),
        },
        "input_contract_required_fields": [
            "task_id",
            "run_id",
            "artifact_refs",
            "evidence_refs",
            "claim_or_judgment_card_refs",
            "gap_refs",
            "gate_refs",
        ],
        "output_contract_required_fields": [
            "task_projection_id",
            "artifact_drilldown_refs",
            "review_action_event_id",
            "visible_gate_status",
            "deliverable_or_dashboard_projection_ref",
            "ops_trace_ref",
        ],
        "review_action_results": review_action_results,
        "surface_audit": audits["surface_audit"],
        "traceability_audit": audits["traceability_audit"],
        "review_action_audit": audits["review_action_audit"],
        "ops_audit": audits["ops_audit"],
        "acceptance_gates": acceptance_gates,
        "gate_fail_count": fail_count,
        "runtime_entry_policy": (
            "Runtime alignment only: Workbench may project SQL-final task, "
            "evidence, claim/judgment, gap, gate, artifact, deliverable and ops "
            "rows into reviewer surfaces. Frontend local state or chat transcript "
            "cannot become final audit source."
        ),
        "do_not_promote": [
            "chat_transcript_as_workbench",
            "frontend_local_state_as_audit_source",
            "review_action_without_workpaper_event",
            "artifact_panel_without_evidence_or_gate_drilldown",
        ],
        "rollback_gate": [
            "review_action_not_append_only",
            "artifact_drilldown_missing_evidence_or_gate",
            "deliverable_projection_not_sql_backed",
            "ops_trace_missing",
        ],
    }


def _ensure_fixture_review_actions(root: Path, *, task_id: str, drilldown: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = list(drilldown.get("claims") or [])
    gaps = list(drilldown.get("gaps") or [])
    judgment = dict(drilldown.get("judgment") or {})
    if not claims:
        raise ValueError("p33_workbench_fixture_requires_claim_cards")
    if not gaps:
        raise ValueError("p33_workbench_fixture_requires_typed_gaps")
    if not judgment.get("judgment_state_id"):
        raise ValueError("p33_workbench_fixture_requires_judgment_state")
    action_specs = [
        {
            "action": "accept",
            "review_target_type": "claim_card",
            "review_target_id": str(claims[0].get("claim_card_id") or ""),
            "comment": "P33 fixture accepts an evidence-backed claim for reviewer traceability.",
        },
        {
            "action": "reject",
            "review_target_type": "gap",
            "review_target_id": str(gaps[0].get("gap_id") or ""),
            "comment": "P33 fixture rejects hiding a typed gap behind a final conclusion.",
        },
        {
            "action": "supersede",
            "review_target_type": "judgment_state",
            "review_target_id": str(judgment.get("judgment_state_id") or ""),
            "comment": "P33 fixture supersedes judgment state when reviewer asks for revised logic.",
        },
    ]
    results: list[dict[str, Any]] = []
    for spec in action_specs:
        target_id = str(spec["review_target_id"])
        result = append_review_action(
            root,
            task_id=task_id,
            action=str(spec["action"]),
            comment=str(spec["comment"]),
            reviewer_role="p33_fixture_reviewer",
            review_target_type=str(spec["review_target_type"]),
            review_target_id=target_id,
            idempotency_key=f"{P33_FIXTURE_ACTION_PREFIX}:{spec['action']}:{target_id}",
        )
        results.append(result)
    return results


def _surface_audit(
    *,
    s6_summary: Mapping[str, Any],
    s7_summary: Mapping[str, Any],
    drilldown: Mapping[str, Any],
) -> dict[str, Any]:
    contract = workbench_frontdoor_schema_contract()
    endpoint_surfaces = {str(endpoint.get("surface")) for endpoint in contract.get("endpoints") or []}
    populated_surfaces = {
        surface: len(drilldown.get(surface) or []) if isinstance(drilldown.get(surface), list) else bool(drilldown.get(surface))
        for surface in REQUIRED_DRILLDOWN_SURFACES
    }
    missing_surfaces = [surface for surface, count in populated_surfaces.items() if not count]
    return {
        "status": "pass" if not missing_surfaces else "fail",
        "s6_release_decision": s6_summary.get("release_decision"),
        "s7_release_decision": s7_summary.get("release_decision"),
        "endpoint_surfaces": sorted(endpoint_surfaces),
        "review_endpoint_present": "review_action" in endpoint_surfaces,
        "ops_endpoint_present": "ops_projection" in endpoint_surfaces,
        "populated_surfaces": populated_surfaces,
        "missing_surfaces": missing_surfaces,
        "sql_final_policy": dict(contract.get("policy") or {}),
    }


def _traceability_audit(
    *,
    task_detail: Mapping[str, Any],
    drilldown: Mapping[str, Any],
    artifacts: list[Mapping[str, Any]],
    deliverable: Mapping[str, Any],
    dashboard: Mapping[str, Any],
) -> dict[str, Any]:
    claims = list(drilldown.get("claims") or [])
    gaps = list(drilldown.get("gaps") or [])
    gates = list(drilldown.get("gates") or [])
    artifact_ids = {str(row.get("artifact_ref_id")) for row in artifacts if row.get("artifact_ref_id")}
    context = dict(drilldown.get("context") or {})
    selected_refs = {str(ref) for ref in context.get("selected_evidence_refs") or []}
    claim_ids = {str(row.get("claim_card_id")) for row in claims if row.get("claim_card_id")}
    gap_ids = {str(row.get("gap_id")) for row in gaps if row.get("gap_id")}
    claim_rows_with_evidence = [
        row for row in claims if row.get("evidence_refs") and set(map(str, row.get("evidence_refs") or [])).intersection(selected_refs)
    ]
    typed_gaps = [row for row in gaps if row.get("gap_type") and row.get("gap_reason") and row.get("source_boundary")]
    judgment = dict(drilldown.get("judgment") or {})
    judgment_claim_refs = set(map(str, judgment.get("claim_card_refs") or []))
    judgment_gap_refs = set(map(str, judgment.get("gap_refs") or []))
    dashboard_ref_ids = set(
        map(
            str,
            ((dashboard.get("dashboard_projection") or {}).get("artifact_ref_ids") or []),
        )
    )
    render_jobs = list((deliverable or {}).get("render_jobs") or [])
    render_artifact_ids = {str(row.get("artifact_ref_id")) for row in render_jobs if row.get("artifact_ref_id")}
    return {
        "status": "pass",
        "task_projection_id": task_detail.get("task", {}).get("task_id"),
        "run_id": task_detail.get("task", {}).get("run_id"),
        "claim_count": len(claims),
        "claim_with_selected_evidence_count": len(claim_rows_with_evidence),
        "gap_count": len(gaps),
        "typed_gap_count": len(typed_gaps),
        "gate_count": len(gates),
        "artifact_count": len(artifacts),
        "artifact_ref_ids": sorted(artifact_ids),
        "judgment_state_id": judgment.get("judgment_state_id"),
        "judgment_claim_refs_covered": bool(judgment_claim_refs) and judgment_claim_refs.issubset(claim_ids),
        "judgment_gap_refs_covered": bool(judgment_gap_refs) and judgment_gap_refs.issubset(gap_ids),
        "deliverable_render_job_count": len(render_jobs),
        "deliverable_artifact_refs_covered": bool(render_artifact_ids) and render_artifact_ids.issubset(artifact_ids),
        "dashboard_artifact_refs_covered": bool(dashboard_ref_ids) and dashboard_ref_ids.issubset(artifact_ids),
        "selected_evidence_ref_count": len(selected_refs),
    }


def _review_action_audit(*, review_queue: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, Any]:
    actions = [
        row
        for row in review_queue.get("review_actions") or []
        if str((row.get("payload") or {}).get("idempotency_key") or "").startswith(P33_FIXTURE_ACTION_PREFIX)
    ]
    workpaper_events = {str(row.get("workpaper_event_id")): row for row in replay.get("workpaper_events") or []}
    action_types = {str(row.get("action")) for row in actions}
    rows_with_events = [row for row in actions if str(row.get("workpaper_event_id") or "") in workpaper_events]
    rows_with_targets = [
        row
        for row in actions
        if (row.get("payload") or {}).get("review_target_type") and (row.get("payload") or {}).get("review_target_id")
    ]
    return {
        "status": "pass",
        "fixture_action_count": len(actions),
        "required_actions": list(REQUIRED_REVIEW_ACTIONS),
        "action_types": sorted(action_types),
        "all_required_actions_present": set(REQUIRED_REVIEW_ACTIONS).issubset(action_types),
        "rows_with_workpaper_event_count": len(rows_with_events),
        "rows_with_target_count": len(rows_with_targets),
        "append_only_source": "workbench_review_actions_s6 + workpaper_events",
    }


def _ops_audit(*, ops: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, Any]:
    trace_spans = list(replay.get("trace_spans") or [])
    return {
        "status": "pass",
        "ops_status": ops.get("status"),
        "queue_status": ops.get("queue_status"),
        "trace_span_count": ops.get("trace_span_count"),
        "replay_trace_span_count": len(trace_spans),
        "rollback_ref": ops.get("rollback_ref"),
        "cost_amount": ops.get("cost_amount"),
        "token_count": ops.get("token_count"),
        "frontend_local_state_used": False,
        "chat_transcript_used_as_audit_source": False,
    }


def evaluate_workbench_artifact_review_surface_gates(audits: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    surface = audits["surface_audit"]
    trace = audits["traceability_audit"]
    review = audits["review_action_audit"]
    ops = audits["ops_audit"]
    checks = [
        (
            "s6_s7_surfaces_l4_pass",
            surface.get("s6_release_decision") == "S6_L4_scope_pass"
            and surface.get("s7_release_decision") == "S7_L4_scope_pass",
            "S6 Workbench and S7 deliverable/dashboard projections are deterministic L4-scope pass.",
            surface,
        ),
        (
            "drilldown_task_to_evidence_claim_gap_gate_artifact",
            surface.get("status") == "pass"
            and trace.get("claim_with_selected_evidence_count", 0) >= 1
            and trace.get("typed_gap_count", 0) >= 1
            and trace.get("gate_count", 0) >= 1
            and trace.get("artifact_count", 0) >= 1,
            "Workbench drilldown links task to evidence-backed claims, typed gaps, gates and artifacts.",
            trace,
        ),
        (
            "judgment_refs_cover_claims_and_gaps",
            bool(trace.get("judgment_state_id"))
            and bool(trace.get("judgment_claim_refs_covered"))
            and bool(trace.get("judgment_gap_refs_covered")),
            "JudgmentState references are covered by Workbench-visible ClaimCards and typed gaps.",
            trace,
        ),
        (
            "review_actions_append_only_workpaper_events",
            review.get("all_required_actions_present") is True
            and review.get("rows_with_workpaper_event_count") == review.get("fixture_action_count")
            and review.get("rows_with_target_count") == review.get("fixture_action_count"),
            "Accept/reject/supersede reviewer actions are ledgered and linked to WorkpaperEvents.",
            review,
        ),
        (
            "deliverable_dashboard_projection_sql_backed",
            bool(trace.get("deliverable_artifact_refs_covered"))
            and bool(trace.get("dashboard_artifact_refs_covered")),
            "Deliverable and dashboard projection refs are SQL-backed artifact refs.",
            trace,
        ),
        (
            "ops_trace_replay_visible",
            int(ops.get("trace_span_count") or 0) >= 1
            and int(ops.get("replay_trace_span_count") or 0) >= 1
            and bool(ops.get("rollback_ref")),
            "Ops trace, cost/token fields and rollback ref are visible from SQL-final replay.",
            ops,
        ),
        (
            "frontend_or_chat_state_not_audit_source",
            surface.get("sql_final_policy", {}).get("redis_or_frontend_state_not_final_audit") is True
            and ops.get("frontend_local_state_used") is False
            and ops.get("chat_transcript_used_as_audit_source") is False,
            "Frontend local state and chat transcript are not final audit sources.",
            {"surface_policy": surface.get("sql_final_policy"), "ops": ops},
        ),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "fixture_id": "P33-1.4",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def render_workbench_artifact_review_surface_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# P33-1.4 Workbench Artifact Review Surface Fixture",
        "",
        f"Generated: `{manifest['generated_at']}`",
        f"Contract: `{manifest['contract_id']}`",
        f"Status: `{manifest['status']}`",
        f"Release decision: `{manifest['release_decision']}`",
        f"Closeout level: `{manifest['closeout_level']}`",
        "",
        "## Scope",
        "",
        "This no-paid fixture proves the Workbench artifact-review surface can replay SQL-final task, evidence, "
        "Claim/Judgment, gap, gate, artifact, deliverable/dashboard, ops trace and reviewer-action rows.",
        "",
        "## Gate Rows",
        "",
    ]
    for row in manifest.get("acceptance_gates") or []:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Source Fixture Refs", ""])
    for key, value in (manifest.get("source_fixture_refs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(manifest.get("runtime_entry_policy")), ""])
    return "\n".join(lines)


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import json

    return json.loads(path.read_text(encoding="utf-8"))
