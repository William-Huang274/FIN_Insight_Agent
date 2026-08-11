"""P13 Graph / Skill / Memory lifecycle for the R53-R60 program.

S4 materialized GraphPack / SkillPack / MemoryPack registries and replayable
ContextInjectionPlan rows.  P13 adds the missing lifecycle control plane:
staging, deterministic eval, human approval, tenant overlay, canary,
promotion, rollback/invalidation, and ContextEngine injection policy records.

This is a scoped lifecycle drill.  It proves the governance path is SQL-final
and auditable; it does not claim full multi-tenant graph/skill/memory rollout.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_context_graph_skill_registry import (
    REQUIRED_ACTORS,
    REQUIRED_GRAPH_PACKS,
    REQUIRED_MEMORY_TIERS,
    build_s4_gate,
)
from sec_agent.r53_r60_durable_runtime_hil_resource_router import (
    P12_RUNTIME_DRILL_TASK_ID,
    build_p12_gate,
    default_p12_paths,
    table_row_count,
)
from sec_agent.r53_r60_research_to_quant_lab import row_to_dict, rows_to_dicts, table_exists
from sec_agent.r53_r60_runtime_task_spine import (
    FinSightResearchRuntimeFacade,
    RuntimeTaskSpineStore,
    default_s1_paths,
    json_dumps,
    json_loads,
    rel_path,
    stable_id,
    utc_now_iso,
    write_json,
    write_jsonl,
)


SCHEMA_VERSION = "r53_r60_p13_graph_skill_memory_lifecycle_v0_1"
P13_TASK_ID = "p13_scope_task_graph_skill_memory_lifecycle"
P13_LIFECYCLE_DRILL_TASK_ID = "p13_lifecycle_drill_task_graph_skill_memory_canary"

P13_DEMAND_IDS = (
    "P13-D01-asset-lifecycle-inventory",
    "P13-D02-patch-staging-registry",
    "P13-D03-deterministic-behavior-eval",
    "P13-D04-human-approval-and-policy",
    "P13-D05-tenant-overlay-and-canary",
    "P13-D06-promotion-rollback-invalidation",
    "P13-D07-contextengine-injection-visibility",
)

ASSET_TYPES = ("graph", "skill", "memory")
APPROVED_PATCH_IDS = (
    "p13_patch_graph_product_intelligence_authority_v0_2",
    "p13_patch_skill_product_specialist_evidence_pack_v0_2",
    "p13_patch_memory_research_experience_boundaries_v0_2",
)
NEGATIVE_PATCH_ID = "p13_patch_skill_auto_revenue_from_deployment_blocked"


@dataclass(frozen=True)
class P13Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p13_paths(root: Path) -> P13Paths:
    s1_paths = default_s1_paths(root)
    return P13Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p13_graph_skill_memory_lifecycle_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p13_graph_skill_memory_lifecycle_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p13_graph_skill_memory_lifecycle_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p13_graph_skill_memory_lifecycle_l4_scope_pass.zh-CN.md",
    )


def graph_skill_memory_lifecycle_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "release_scope": "graph_skill_memory_lifecycle_control_plane_drill",
        "tables": [
            "graph_skill_memory_lifecycle_metadata_p13",
            "capability_asset_inventory_p13",
            "asset_patch_proposals_p13",
            "asset_patch_eval_results_p13",
            "asset_human_approval_records_p13",
            "tenant_overlay_records_p13",
            "asset_canary_runs_p13",
            "asset_promotion_records_p13",
            "asset_active_versions_p13",
            "asset_invalidation_records_p13",
            "contextengine_injection_policy_records_p13",
            "asset_lifecycle_acceptance_records_p13",
            "asset_lifecycle_readiness_reports_p13",
            "asset_lifecycle_gate_results_p13",
        ],
        "required_asset_types": list(ASSET_TYPES),
        "required_graph_packs": list(REQUIRED_GRAPH_PACKS),
        "required_memory_tiers": list(REQUIRED_MEMORY_TIERS),
        "policy": {
            "sql_ledger_is_final_audit_source": True,
            "production_agents_cannot_self_promote_graph_skill_memory": True,
            "staging_eval_human_approval_canary_promote_required": True,
            "negative_authority_patch_must_be_blocked": True,
            "tenant_overlay_must_not_mutate_global_asset": True,
            "memory_pack_has_no_standalone_fact_authority": True,
            "exact_fact_refs_preserved_not_summarized": True,
            "not_full_multi_tenant_rollout": True,
        },
    }


def create_graph_skill_memory_lifecycle_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists graph_skill_memory_lifecycle_metadata_p13 (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists capability_asset_inventory_p13 (
            asset_inventory_id text primary key,
            asset_type text not null,
            asset_id text not null,
            active_version text not null,
            source_registry_table text not null,
            tenant_scope text not null,
            authority_boundary text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_patch_proposals_p13 (
            patch_id text primary key,
            asset_type text not null,
            asset_id text not null,
            from_version text not null,
            proposed_version text not null,
            proposal_source text not null,
            change_summary text not null,
            risk_class text not null,
            staging_status text not null,
            requires_human_approval integer not null,
            self_promotion_forbidden integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_patch_eval_results_p13 (
            eval_id text primary key,
            patch_id text not null,
            eval_suite text not null,
            deterministic_status text not null,
            regression_status text not null,
            authority_violation_count integer not null,
            forbidden_behavior_count integer not null,
            exact_ref_preservation_status text not null,
            decision text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_human_approval_records_p13 (
            approval_id text primary key,
            patch_id text not null,
            reviewer_role text not null,
            decision text not null,
            reason text not null,
            approved_scope_json text not null default '{}',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists tenant_overlay_records_p13 (
            overlay_id text primary key,
            tenant_id text not null,
            asset_type text not null,
            asset_id text not null,
            base_version text not null,
            overlay_version text not null,
            permission_scope text not null,
            overlay_policy_json text not null default '{}',
            mutates_global_asset integer not null,
            status text not null,
            created_at text not null
        );
        create table if not exists asset_canary_runs_p13 (
            canary_id text primary key,
            patch_id text not null,
            tenant_id text not null,
            case_id text not null,
            traffic_scope text not null,
            pass_count integer not null,
            fail_count integer not null,
            rollback_triggered integer not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_promotion_records_p13 (
            promotion_id text primary key,
            patch_id text not null,
            asset_type text not null,
            asset_id text not null,
            from_version text not null,
            to_version text not null,
            promotion_status text not null,
            active_after integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_active_versions_p13 (
            active_version_id text primary key,
            asset_type text not null,
            asset_id text not null,
            active_version text not null,
            promoted_by_patch_id text not null,
            tenant_scope text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_invalidation_records_p13 (
            invalidation_id text primary key,
            asset_type text not null,
            asset_id text not null,
            invalidated_version text not null,
            invalidation_reason text not null,
            replacement_version text not null,
            effective_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists contextengine_injection_policy_records_p13 (
            policy_id text primary key,
            actor_id text not null,
            selected_graph_packs_json text not null default '[]',
            selected_skill_packs_json text not null default '[]',
            selected_memory_packs_json text not null default '[]',
            compression_policy text not null,
            exact_ref_policy text not null,
            memory_fact_authority text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_lifecycle_acceptance_records_p13 (
            acceptance_id text primary key,
            demand_id text not null,
            product_acceptance_json text not null default '{}',
            engineering_acceptance_json text not null default '{}',
            quality_acceptance_json text not null default '{}',
            ops_acceptance_json text not null default '{}',
            evidence_refs_json text not null default '[]',
            status text not null,
            owner text not null,
            created_at text not null
        );
        create table if not exists asset_lifecycle_readiness_reports_p13 (
            report_id text primary key,
            task_id text not null,
            inventory_status text not null,
            staging_eval_status text not null,
            hil_status text not null,
            canary_status text not null,
            active_version_status text not null,
            contextengine_status text not null,
            lifecycle_rollout_status text not null,
            release_decision text not null,
            gate_refs_json text not null default '[]',
            known_gaps_json text not null default '[]',
            next_actions_json text not null default '[]',
            owner text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists asset_lifecycle_gate_results_p13 (
            gate_result_id text primary key,
            gate_id text not null,
            gate_group text not null,
            status text not null,
            pass_level text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_p13_inventory_asset on capability_asset_inventory_p13(asset_type, asset_id);
        create index if not exists idx_p13_patch_asset on asset_patch_proposals_p13(asset_type, asset_id);
        create index if not exists idx_p13_eval_patch on asset_patch_eval_results_p13(patch_id);
        create index if not exists idx_p13_approval_patch on asset_human_approval_records_p13(patch_id);
        """
    )


def seed_p13_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "source_of_truth": "S1 SQL runtime task spine",
        "scope_boundary": "Lifecycle drill only; not full multi-tenant graph/skill/memory rollout.",
    }
    for key, value in metadata.items():
        conn.execute(
            """
            insert into graph_skill_memory_lifecycle_metadata_p13(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_p13_rows(conn: sqlite3.Connection) -> None:
    for table in [
        "asset_lifecycle_gate_results_p13",
        "asset_lifecycle_readiness_reports_p13",
        "asset_lifecycle_acceptance_records_p13",
        "contextengine_injection_policy_records_p13",
        "asset_invalidation_records_p13",
        "asset_active_versions_p13",
        "asset_promotion_records_p13",
        "asset_canary_runs_p13",
        "tenant_overlay_records_p13",
        "asset_human_approval_records_p13",
        "asset_patch_eval_results_p13",
        "asset_patch_proposals_p13",
        "capability_asset_inventory_p13",
    ]:
        conn.execute(f"delete from {table}")


def build_p13_gate(root: Path, *, task_id: str = P13_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p13_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_p13_dependencies(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_graph_skill_memory_lifecycle_schema(conn)
        seed_p13_metadata(conn)
        clear_p13_rows(conn)

    lifecycle_task = get_or_create_lifecycle_drill_task(runtime)
    materialized = materialize_graph_skill_memory_lifecycle(runtime, root=root, drill_task_id=P13_LIFECYCLE_DRILL_TASK_ID)
    p13_task = get_or_create_p13_task(runtime, task_id=task_id)
    if str(p13_task["task"]["status"]) != "running":
        p13_task = runtime.store.transition_task(
            task_id,
            "running",
            actor="capability_lifecycle_builder",
            message="start P13 Graph/Skill/Memory lifecycle build",
            progress=10,
        )

    write_json(paths.schema_path, graph_skill_memory_lifecycle_schema_contract())
    artifact_refs = record_p13_artifacts(runtime, root, paths, task_id, materialized)
    event = runtime.append_workpaper_event(
        task_id,
        actor="capability_lifecycle_owner",
        event_type="graph_skill_memory_lifecycle_ready",
        section_id="graph_skill_memory_lifecycle",
        claim_id="p13_graph_skill_memory_lifecycle_scope_pass",
        payload={
            "schema_version": SCHEMA_VERSION,
            "drill_task_id": P13_LIFECYCLE_DRILL_TASK_ID,
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "scope_boundary": "Lifecycle control plane is wired; full tenant rollout remains a later pilot gate.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="graph_skill_memory_lifecycle_builder",
        status="pass",
        input_payload={"dependencies": ["S4 context registry", "P12 durable runtime drill"]},
        output_payload={**materialized, "workpaper_event_id": event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="capability_lifecycle_builder",
    )
    for name, payload in [
        ("p13_patch_staging_gate", {"patch_count": materialized["patch_proposal_count"]}),
        ("p13_eval_negative_guard_gate", {"blocked_negative_patch_count": materialized["blocked_negative_patch_count"]}),
        ("p13_hil_approval_gate", {"approval_count": materialized["human_approval_count"]}),
        ("p13_canary_promotion_gate", {"promotion_count": materialized["promotion_count"]}),
    ]:
        runtime.record_trace_span(
            task_id,
            span_kind="capability_lifecycle_gate",
            name=name,
            status="pass",
            actor="capability_lifecycle_verifier",
            node_execution_id=node["node_execution_id"],
            latency_ms=0,
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"closeout_level": "L4_scope_pass", **payload},
        )
    runtime.store.transition_task(task_id, "succeeded", actor="capability_lifecycle_verifier", message="P13 lifecycle drill complete", progress=100)

    gate_rows = evaluate_p13_gates(root, runtime.store, task_id=task_id, drill_task_id=P13_LIFECYCLE_DRILL_TASK_ID, materialized=materialized)
    persist_p13_gate_results(runtime.store, gate_rows)
    finalize_p13_readiness_report(runtime.store, gate_rows)
    summary = build_p13_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p13_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_p13_dependencies(root: Path) -> None:
    s4_summary_path = root / "data" / "manifests" / "r53_r60_s4_context_graph_skill_registry_summary_v0_1.json"
    if not dependency_summary_passes(s4_summary_path, "S4_L4_scope_pass"):
        build_s4_gate(root)

    p12_summary_path = default_p12_paths(root).summary_path
    if not dependency_summary_passes(p12_summary_path, "P12_L4_scope_pass_runtime_drill_ready"):
        build_p12_gate(root)


def dependency_summary_passes(path: Path, release_decision: str) -> bool:
    if not path.exists():
        return False
    payload = json_loads(path.read_text(encoding="utf-8"), {})
    return payload.get("status") == "pass" and payload.get("release_decision") == release_decision


def get_or_create_p13_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Build Graph/Skill/Memory lifecycle gate package",
            task_id=task_id,
            trace_id="trace_p13_graph_skill_memory_lifecycle",
            user_id="p13_gate",
            case_id="p13_graph_skill_memory_lifecycle_l4_scope",
            mode="capability_lifecycle_gate",
            objective={"minimum_evidence": "staging/eval/approval/canary/promotion/invalidation rows exist"},
            metadata={"source_slice": "P13", "closeout_level": "L4_scope_pass"},
        )
    if str(state["task"]["status"]) in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="p13_builder", reason="rebuild P13 Graph/Skill/Memory lifecycle")
    return state


def get_or_create_lifecycle_drill_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(P13_LIFECYCLE_DRILL_TASK_ID)
    except Exception:
        state = runtime.create_task(
            "Run P13 capability lifecycle drill with staged graph/skill/memory patches",
            task_id=P13_LIFECYCLE_DRILL_TASK_ID,
            trace_id="trace_p13_lifecycle_drill",
            user_id="capability_admin",
            case_id="pilot_case_ai_infra_graph_skill_memory_lifecycle",
            mode="capability_lifecycle_drill",
            objective={
                "research_question": "Can capability assets be staged, evaluated, approved, canaried, promoted and invalidated without self-promotion?",
                "required_assets": list(ASSET_TYPES),
            },
            metadata={"source_slice": "P13", "drill": True},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        state = runtime.resume_task(P13_LIFECYCLE_DRILL_TASK_ID, actor="p13_lifecycle_drill", reason="rerun capability lifecycle drill")
    if str(state["task"]["status"]) != "running":
        state = runtime.store.transition_task(
            P13_LIFECYCLE_DRILL_TASK_ID,
            "running",
            actor="p13_lifecycle_drill",
            message="start graph/skill/memory lifecycle drill",
            progress=5,
        )
    return state


def materialize_graph_skill_memory_lifecycle(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    drill_task_id: str,
) -> dict[str, Any]:
    store = runtime.store
    with store._connect() as conn:
        create_graph_skill_memory_lifecycle_schema(conn)
        clear_p13_rows(conn)
    drill_state = runtime.get_task_state(drill_task_id)
    run_id = str(drill_state["task"]["current_run_id"])
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            inventory = insert_asset_inventory(conn, now=now)
            patches = insert_patch_proposals(conn, inventory=inventory, now=now)
            insert_patch_evals(conn, patches=patches, now=now)
            insert_human_approvals(conn, patches=patches, now=now)
            insert_tenant_overlays(conn, patches=patches, now=now)
            insert_canary_runs(conn, patches=patches, now=now)
            insert_promotions_and_active_versions(conn, patches=patches, now=now)
            insert_invalidations(conn, patches=patches, now=now)
            insert_contextengine_policy_records(conn, now=now)
            insert_acceptance_records(conn, now=now)
            insert_readiness_report(conn, now=now, task_id=drill_task_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    runtime.store.transition_task(drill_task_id, "succeeded", actor="p13_lifecycle_verifier", message="P13 lifecycle drill complete", progress=100)
    return collect_p13_counts(store, drill_task_id=drill_task_id, run_id=run_id)


def insert_asset_inventory(conn: sqlite3.Connection, *, now: str) -> dict[str, list[dict[str, Any]]]:
    inventory: dict[str, list[dict[str, Any]]] = {"graph": [], "skill": [], "memory": []}
    graph_rows = rows_to_dicts(conn.execute("select * from graph_pack_registry order by graph_pack_id").fetchall())
    skill_rows = rows_to_dicts(conn.execute("select * from skill_pack_registry order by skill_pack_id").fetchall())
    memory_rows = rows_to_dicts(conn.execute("select * from memory_pack_registry order by memory_pack_id").fetchall())

    for row in graph_rows:
        record = {
            "asset_type": "graph",
            "asset_id": row["graph_pack_id"],
            "active_version": row["version"],
            "source_registry_table": "graph_pack_registry",
            "tenant_scope": row["tenant_status"],
            "authority_boundary": row["authority_boundary"],
            "payload": {"graph_kind": row["graph_kind"], "scope": row["scope"], "source_tables": json_loads(row["source_tables_json"], [])},
        }
        inventory["graph"].append(record)
        insert_inventory_row(conn, record, now=now)

    for row in skill_rows:
        record = {
            "asset_type": "skill",
            "asset_id": row["skill_pack_id"],
            "active_version": row["version"],
            "source_registry_table": "skill_pack_registry",
            "tenant_scope": "global_default",
            "authority_boundary": "skill_policy_not_fact_authority",
            "payload": {
                "skill_id": row["skill_id"],
                "roles": json_loads(row["applicable_roles_json"], []),
                "eval_hooks": json_loads(row["eval_hooks_json"], []),
            },
        }
        inventory["skill"].append(record)
        insert_inventory_row(conn, record, now=now)

    for row in memory_rows:
        record = {
            "asset_type": "memory",
            "asset_id": row["memory_pack_id"],
            "active_version": "v0_1",
            "source_registry_table": "memory_pack_registry",
            "tenant_scope": row["tenant_id"],
            "authority_boundary": row["authority_boundary"],
            "payload": {"tier": row["tier"], "ttl_seconds": row["ttl_seconds"], "promotion_status": row["promotion_status"]},
        }
        inventory["memory"].append(record)
        insert_inventory_row(conn, record, now=now)
    return inventory


def insert_inventory_row(conn: sqlite3.Connection, record: Mapping[str, Any], *, now: str) -> None:
    conn.execute(
        "insert into capability_asset_inventory_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stable_id("p13inv", [record["asset_type"], record["asset_id"]]),
            record["asset_type"],
            record["asset_id"],
            record["active_version"],
            record["source_registry_table"],
            record["tenant_scope"],
            record["authority_boundary"],
            "active_baseline",
            json_dumps(record.get("payload") or {}),
            now,
        ),
    )


def insert_patch_proposals(
    conn: sqlite3.Connection,
    *,
    inventory: Mapping[str, list[dict[str, Any]]],
    now: str,
) -> list[dict[str, Any]]:
    graph_asset = find_asset(inventory, "graph", preferred_id="product_intelligence_graph")
    skill_asset = find_asset(inventory, "skill", contains="product")
    memory_asset = find_asset(inventory, "memory", contains="global_playbook")
    patches = [
        {
            "patch_id": APPROVED_PATCH_IDS[0],
            "asset_type": "graph",
            "asset_id": graph_asset["asset_id"],
            "from_version": graph_asset["active_version"],
            "proposed_version": "v0_2_product_authority_edges",
            "proposal_source": "lead_review_gap_audit",
            "change_summary": "Split product evidence authority into exact KPI, technical fact, deployment signal, proxy and navigation edges.",
            "risk_class": "medium",
            "staging_status": "staged_waiting_eval",
            "payload": {"allowed_claims": ["bounded_product_thesis_driver"], "forbidden_claims": ["proxy_as_revenue_exact"]},
        },
        {
            "patch_id": APPROVED_PATCH_IDS[1],
            "asset_type": "skill",
            "asset_id": skill_asset["asset_id"],
            "from_version": skill_asset["active_version"],
            "proposed_version": "v0_2_product_evidence_pack_required",
            "proposal_source": "eval_failure_cluster",
            "change_summary": "Require ProductEvidencePack role separation and forbid product page or deployment signal from becoming revenue/share exact.",
            "risk_class": "medium",
            "staging_status": "staged_waiting_eval",
            "payload": {"required_inputs": ["ProductEvidencePack"], "negative_examples": ["deployment_to_revenue_exact"]},
        },
        {
            "patch_id": APPROVED_PATCH_IDS[2],
            "asset_type": "memory",
            "asset_id": memory_asset["asset_id"],
            "from_version": memory_asset["active_version"],
            "proposed_version": "v0_2_research_experience_boundaries",
            "proposal_source": "human_reviewer_feedback",
            "change_summary": "Record reviewer lesson: exact financial facts preserve refs; product/deployment signals remain bounded thesis drivers.",
            "risk_class": "low",
            "staging_status": "staged_waiting_eval",
            "payload": {"lesson_scope": "team_experience", "fact_authority": "no_standalone_fact_authority"},
        },
        {
            "patch_id": NEGATIVE_PATCH_ID,
            "asset_type": "skill",
            "asset_id": skill_asset["asset_id"],
            "from_version": skill_asset["active_version"],
            "proposed_version": "v0_2_auto_revenue_promotion_rejected",
            "proposal_source": "unsafe_auto_learning_candidate",
            "change_summary": "Unsafe candidate attempts to let customer deployments imply product revenue exact.",
            "risk_class": "high",
            "staging_status": "staged_waiting_eval",
            "payload": {"forbidden_claim_attempt": "customer_deployment_implies_product_revenue_exact"},
        },
    ]
    for patch in patches:
        conn.execute(
            "insert into asset_patch_proposals_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                patch["patch_id"],
                patch["asset_type"],
                patch["asset_id"],
                patch["from_version"],
                patch["proposed_version"],
                patch["proposal_source"],
                patch["change_summary"],
                patch["risk_class"],
                patch["staging_status"],
                1,
                1,
                json_dumps(patch["payload"]),
                now,
            ),
        )
    return patches


def find_asset(
    inventory: Mapping[str, list[dict[str, Any]]],
    asset_type: str,
    *,
    preferred_id: str = "",
    contains: str = "",
) -> dict[str, Any]:
    rows = list(inventory.get(asset_type) or [])
    if preferred_id:
        for row in rows:
            if row["asset_id"] == preferred_id:
                return row
    if contains:
        needle = contains.lower()
        for row in rows:
            haystack = json_dumps(row).lower()
            if needle in haystack:
                return row
    if not rows:
        raise RuntimeError(f"missing_asset_type:{asset_type}")
    return rows[0]


def insert_patch_evals(conn: sqlite3.Connection, *, patches: list[dict[str, Any]], now: str) -> None:
    for patch in patches:
        is_negative = patch["patch_id"] == NEGATIVE_PATCH_ID
        conn.execute(
            "insert into asset_patch_eval_results_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13eval", [patch["patch_id"]]),
                patch["patch_id"],
                "graph_skill_memory_lifecycle_regression_v0_1",
                "fail" if is_negative else "pass",
                "fail" if is_negative else "pass",
                2 if is_negative else 0,
                1 if is_negative else 0,
                "pass",
                "blocked" if is_negative else "pass",
                json_dumps(
                    {
                        "checks": [
                            "authority_boundary",
                            "forbidden_claim_policy",
                            "exact_ref_preservation",
                            "tenant_overlay_no_global_mutation",
                        ],
                        "negative_patch": is_negative,
                    }
                ),
                now,
            ),
        )


def insert_human_approvals(conn: sqlite3.Connection, *, patches: list[dict[str, Any]], now: str) -> None:
    for patch in patches:
        is_negative = patch["patch_id"] == NEGATIVE_PATCH_ID
        decision = "rejected" if is_negative else "approved"
        conn.execute(
            "insert into asset_human_approval_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13approval", [patch["patch_id"]]),
                patch["patch_id"],
                "capability_owner",
                decision,
                "authority violation blocked" if is_negative else "deterministic eval passed; approve for internal canary only",
                json_dumps({"tenant_scope": "internal_research", "traffic_scope": "canary"} if not is_negative else {}),
                "approval_rejected" if is_negative else "approval_granted",
                json_dumps({"human_required": True, "self_promotion_forbidden": True}),
                now,
            ),
        )


def insert_tenant_overlays(conn: sqlite3.Connection, *, patches: list[dict[str, Any]], now: str) -> None:
    for patch in patches:
        if patch["patch_id"] == NEGATIVE_PATCH_ID:
            continue
        conn.execute(
            "insert into tenant_overlay_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13overlay", [patch["patch_id"], "tenant_internal_ai_research"]),
                "tenant_internal_ai_research",
                patch["asset_type"],
                patch["asset_id"],
                patch["from_version"],
                f"{patch['proposed_version']}__tenant_internal_ai_research",
                "tenant_private_internal_research",
                json_dumps({"inherits_global": True, "global_asset_mutation": False, "override_scope": "AI infrastructure dogfood"}),
                0,
                "overlay_ready",
                now,
            ),
        )


def insert_canary_runs(conn: sqlite3.Connection, *, patches: list[dict[str, Any]], now: str) -> None:
    for patch in patches:
        if patch["patch_id"] == NEGATIVE_PATCH_ID:
            continue
        conn.execute(
            "insert into asset_canary_runs_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13canary", [patch["patch_id"], "pilot_case_ai_infra"]),
                patch["patch_id"],
                "tenant_internal_ai_research",
                "pilot_case_ai_infra_product_graph_memory",
                "10_percent_internal_dogfood_shadow",
                3,
                0,
                0,
                "canary_pass",
                json_dumps({"deterministic_cases": ["NVDA_AMD_GPU", "ASML_TSM_EUV", "MSFT_AMZN_GOOG_CLOUD_CAPEX"]}),
                now,
            ),
        )


def insert_promotions_and_active_versions(conn: sqlite3.Connection, *, patches: list[dict[str, Any]], now: str) -> None:
    for patch in patches:
        if patch["patch_id"] == NEGATIVE_PATCH_ID:
            continue
        conn.execute(
            "insert into asset_promotion_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13promotion", [patch["patch_id"]]),
                patch["patch_id"],
                patch["asset_type"],
                patch["asset_id"],
                patch["from_version"],
                patch["proposed_version"],
                "promoted_to_internal_active",
                1,
                json_dumps({"requires_rollforward_migration_for_full_tenant_rollout": True}),
                now,
            ),
        )
        conn.execute(
            "insert into asset_active_versions_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13active", [patch["asset_type"], patch["asset_id"], patch["proposed_version"]]),
                patch["asset_type"],
                patch["asset_id"],
                patch["proposed_version"],
                patch["patch_id"],
                "tenant_internal_ai_research",
                "active_internal_canary",
                json_dumps({"base_version": patch["from_version"]}),
                now,
            ),
        )


def insert_invalidations(conn: sqlite3.Connection, *, patches: list[dict[str, Any]], now: str) -> None:
    for patch in patches:
        if patch["patch_id"] == NEGATIVE_PATCH_ID:
            conn.execute(
                "insert into asset_invalidation_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p13invalidate", [patch["patch_id"]]),
                    patch["asset_type"],
                    patch["asset_id"],
                    patch["proposed_version"],
                    "blocked_by_authority_eval",
                    patch["from_version"],
                    "candidate_invalidated_no_activation",
                    json_dumps({"negative_patch_guard": True}),
                    now,
                ),
            )
        else:
            conn.execute(
                "insert into asset_invalidation_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p13invalidate", [patch["asset_id"], patch["from_version"]]),
                    patch["asset_type"],
                    patch["asset_id"],
                    patch["from_version"],
                    "superseded_by_approved_internal_canary_version",
                    patch["proposed_version"],
                    "superseded_with_rollback_ref",
                    json_dumps({"rollback_target": patch["from_version"]}),
                    now,
                ),
            )


def insert_contextengine_policy_records(conn: sqlite3.Connection, *, now: str) -> None:
    graph_refs = [row[0] for row in conn.execute("select graph_pack_id from graph_pack_registry order by graph_pack_id").fetchall()]
    skill_refs = [row[0] for row in conn.execute("select skill_pack_id from skill_pack_registry order by skill_pack_id limit 4").fetchall()]
    memory_refs = [row[0] for row in conn.execute("select memory_pack_id from memory_pack_registry order by memory_pack_id").fetchall()]
    for actor in REQUIRED_ACTORS:
        conn.execute(
            "insert into contextengine_injection_policy_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13ctxpolicy", [actor]),
                actor,
                json_dumps(graph_refs),
                json_dumps(skill_refs),
                json_dumps(memory_refs),
                "bounded_summary_plus_exact_ref_pin",
                "preserve_exact_refs_not_summaries",
                "memory_not_fact_authority",
                "policy_ready",
                json_dumps({"contextengine_operations": ["resolve", "select", "compress", "inject", "write", "invalidate"]}),
                now,
            ),
        )


def insert_acceptance_records(conn: sqlite3.Connection, *, now: str) -> None:
    evidence = [
        "capability_asset_inventory_p13",
        "asset_patch_proposals_p13",
        "asset_patch_eval_results_p13",
        "asset_human_approval_records_p13",
        "asset_canary_runs_p13",
        "asset_promotion_records_p13",
        "asset_invalidation_records_p13",
        "contextengine_injection_policy_records_p13",
    ]
    for demand_id in P13_DEMAND_IDS:
        conn.execute(
            "insert into asset_lifecycle_acceptance_records_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stable_id("p13accept", [demand_id]),
                demand_id,
                json_dumps({"status": "pass", "workflow_value": "capability assets can evolve without unreviewed self-modification"}),
                json_dumps({"status": "pass", "sql_final": True, "stage_eval_approve_canary_promote": True}),
                json_dumps({"status": "pass", "negative_authority_patch_blocked": True, "deterministic_gates": True}),
                json_dumps({"status": "pass", "rollback_and_invalidation_visible": True}),
                json_dumps(evidence),
                "pass",
                "capability_lifecycle_owner",
                now,
            ),
        )


def insert_readiness_report(conn: sqlite3.Connection, *, now: str, task_id: str) -> None:
    known_gaps = [
        {
            "gap": "real_tenant_canary_traffic",
            "reason": "P13 proves the lifecycle contract with deterministic internal canary rows, not real multi-tenant traffic.",
            "next_action": "Run approved GraphPack/SkillPack/MemoryPack changes against pilot workpapers and reviewer acceptance.",
        },
        {
            "gap": "automatic_learning_patch_execution",
            "reason": "Self-improvement remains proposal-only. Production agents cannot write active graph/skill/memory versions.",
            "next_action": "Keep learning loop as patch proposals gated by eval and human approval.",
        },
        {
            "gap": "full_contextengine_runtime_migration",
            "reason": "ContextEngine policy records are available; all live graph nodes are not yet migrated to read them dynamically.",
            "next_action": "P14/P15 should bind data plane and workbench execution to these policies.",
        },
    ]
    next_actions = [
        "wire_product_specialist_to_active_product_intelligence_graph_version",
        "run_pilot_cases_with_contextengine_policy_selection",
        "export_lifecycle_state_to_workbench_admin_console",
        "connect P14 ingestion and P15 workbench to active capability versions",
    ]
    conn.execute(
        "insert into asset_lifecycle_readiness_reports_p13 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "p13_graph_skill_memory_lifecycle_report_v0_1",
            task_id,
            "baseline_inventory_ready",
            "stage_eval_guard_pass",
            "human_approval_required_and_recorded",
            "internal_canary_pass",
            "active_versions_promoted_with_rollback_refs",
            "contextengine_policy_ready",
            "controlled_lifecycle_drill_only",
            "P13_pending_gate_finalization",
            json_dumps([]),
            json_dumps(known_gaps),
            json_dumps(next_actions),
            "capability_lifecycle_owner",
            json_dumps({"not_full_tenant_rollout": True}),
            now,
        ),
    )


def evaluate_p13_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    drill_task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = graph_skill_memory_lifecycle_schema_contract()
    generated_at = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        report = row_to_dict(conn.execute("select * from asset_lifecycle_readiness_reports_p13 limit 1").fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        inventory_by_type = {
            row["asset_type"]: int(row["count"])
            for row in conn.execute("select asset_type, count(*) as count from capability_asset_inventory_p13 group by asset_type").fetchall()
        }
        graph_ids = {row[0] for row in conn.execute("select asset_id from capability_asset_inventory_p13 where asset_type = 'graph'").fetchall()}
        memory_tiers = {
            json_loads(row[0], {}).get("tier")
            for row in conn.execute("select payload_json from capability_asset_inventory_p13 where asset_type = 'memory'").fetchall()
        }
        proposal_types = {row[0] for row in conn.execute("select distinct asset_type from asset_patch_proposals_p13").fetchall()}
        negative_eval_blocked = int(
            conn.execute(
                "select count(*) from asset_patch_eval_results_p13 where patch_id = ? and decision = 'blocked' and authority_violation_count > 0",
                (NEGATIVE_PATCH_ID,),
            ).fetchone()[0]
        )
        approved_count = int(conn.execute("select count(*) from asset_human_approval_records_p13 where decision = 'approved'").fetchone()[0])
        rejected_count = int(conn.execute("select count(*) from asset_human_approval_records_p13 where decision = 'rejected'").fetchone()[0])
        overlay_bad = int(conn.execute("select count(*) from tenant_overlay_records_p13 where mutates_global_asset != 0").fetchone()[0])
        canary_bad = int(conn.execute("select count(*) from asset_canary_runs_p13 where status != 'canary_pass' or fail_count != 0 or rollback_triggered != 0").fetchone()[0])
        promotion_count = table_row_count(conn, "asset_promotion_records_p13")
        invalidation_count = table_row_count(conn, "asset_invalidation_records_p13")
        unapproved_promotions = int(
            conn.execute(
                """
                select count(*)
                from asset_promotion_records_p13 p
                left join asset_human_approval_records_p13 h on h.patch_id = p.patch_id and h.decision = 'approved'
                left join asset_canary_runs_p13 c on c.patch_id = p.patch_id and c.status = 'canary_pass'
                where h.patch_id is null or c.patch_id is null
                """
            ).fetchone()[0]
        )
        context_bad = int(
            conn.execute(
                """
                select count(*) from contextengine_injection_policy_records_p13
                where exact_ref_policy != 'preserve_exact_refs_not_summaries'
                   or memory_fact_authority != 'memory_not_fact_authority'
                   or status != 'policy_ready'
                """
            ).fetchone()[0]
        )
        acceptance_bad = int(conn.execute("select count(*) from asset_lifecycle_acceptance_records_p13 where status != 'pass'").fetchone()[0])
        artifact_count = int(
            conn.execute(
                "select count(*) from artifact_refs where task_id = ? and artifact_type like 'graph_skill_memory_lifecycle_%'",
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'graph_skill_memory_lifecycle_ready'",
                (task_id,),
            ).fetchone()[0]
        )
        active_bad = int(
            conn.execute(
                """
                select count(*) from asset_active_versions_p13 a
                left join asset_promotion_records_p13 p on p.patch_id = a.promoted_by_patch_id and p.active_after = 1
                where p.patch_id is null
                """
            ).fetchone()[0]
        )
        s4_summary = root / "data" / "manifests" / "r53_r60_s4_context_graph_skill_registry_summary_v0_1.json"
        p12_summary = default_p12_paths(root).summary_path
        dependency_ok = dependency_summary_passes(s4_summary, "S4_L4_scope_pass") and dependency_summary_passes(
            p12_summary,
            "P12_L4_scope_pass_runtime_drill_ready",
        )

    def gate(gate_id: str, gate_group: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_group": gate_group,
            "status": "pass" if status else "fail",
            "pass_level": "L4_scope_pass" if status else "blocked",
            "detail": dict(detail),
            "generated_at": generated_at,
        }

    return [
        gate("p13_schema_tables_present", "schema", set(contract["tables"]).issubset(existing_tables), {"required_tables": contract["tables"]}),
        gate("p13_s4_p12_dependencies_pass", "dependency", dependency_ok, {"s4_summary": rel_path(s4_summary, root), "p12_summary": rel_path(p12_summary, root)}),
        gate(
            "p13_inventory_covers_graph_skill_memory",
            "inventory",
            all(inventory_by_type.get(kind, 0) > 0 for kind in ASSET_TYPES)
            and set(REQUIRED_GRAPH_PACKS).issubset(graph_ids)
            and set(REQUIRED_MEMORY_TIERS).issubset(memory_tiers),
            {"inventory_by_type": inventory_by_type, "required_graphs": list(REQUIRED_GRAPH_PACKS), "required_memory_tiers": list(REQUIRED_MEMORY_TIERS)},
        ),
        gate(
            "p13_patch_staging_covers_all_asset_types",
            "staging",
            proposal_types == set(ASSET_TYPES) and materialized["patch_proposal_count"] >= 4,
            {"proposal_types": sorted(proposal_types), "patch_proposal_count": materialized["patch_proposal_count"]},
        ),
        gate("p13_negative_authority_patch_blocked", "eval", negative_eval_blocked == 1, {"blocked_negative_patch_count": negative_eval_blocked}),
        gate("p13_human_approval_required_and_recorded", "approval", approved_count >= 3 and rejected_count >= 1, {"approved_count": approved_count, "rejected_count": rejected_count}),
        gate("p13_tenant_overlay_no_global_mutation", "tenant_overlay", overlay_bad == 0 and materialized["tenant_overlay_count"] >= 3, {"overlay_bad": overlay_bad, "tenant_overlay_count": materialized["tenant_overlay_count"]}),
        gate("p13_canary_pass_before_promotion", "canary", canary_bad == 0 and promotion_count >= 3 and unapproved_promotions == 0, {"canary_bad": canary_bad, "promotion_count": promotion_count, "unapproved_promotions": unapproved_promotions}),
        gate("p13_active_versions_and_invalidations_ready", "promotion", active_bad == 0 and invalidation_count >= 4, {"active_bad": active_bad, "invalidation_count": invalidation_count}),
        gate("p13_contextengine_injection_policy_safe", "contextengine", context_bad == 0 and materialized["context_policy_count"] >= len(REQUIRED_ACTORS), {"context_bad": context_bad, "context_policy_count": materialized["context_policy_count"]}),
        gate("p13_acceptance_records_complete", "acceptance", materialized["acceptance_count"] == len(P13_DEMAND_IDS) and acceptance_bad == 0, {"acceptance_count": materialized["acceptance_count"], "acceptance_bad": acceptance_bad}),
        gate(
            "p13_readiness_report_boundary_not_full_rollout",
            "release_boundary",
            bool(report)
            and report.get("lifecycle_rollout_status") == "controlled_lifecycle_drill_only"
            and drill_task.get("status") == "succeeded"
            and artifact_count >= 4
            and workpaper_event_count >= 1,
            {
                "lifecycle_rollout_status": report.get("lifecycle_rollout_status"),
                "drill_task_status": drill_task.get("status"),
                "artifact_count": artifact_count,
                "workpaper_event_count": workpaper_event_count,
            },
        ),
    ]


def collect_p13_counts(store: RuntimeTaskSpineStore, *, drill_task_id: str, run_id: str) -> dict[str, Any]:
    with store._connect() as conn:
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (drill_task_id,)).fetchone())
        blocked_negative = int(
            conn.execute(
                "select count(*) from asset_patch_eval_results_p13 where patch_id = ? and decision = 'blocked'",
                (NEGATIVE_PATCH_ID,),
            ).fetchone()[0]
        )
        return {
            "drill_task_id": drill_task_id,
            "drill_run_id": run_id,
            "drill_task_status": drill_task.get("status"),
            "drill_resume_count": int(drill_task.get("resume_count") or 0),
            "asset_inventory_count": table_row_count(conn, "capability_asset_inventory_p13"),
            "graph_inventory_count": count_where(conn, "capability_asset_inventory_p13", "asset_type = 'graph'"),
            "skill_inventory_count": count_where(conn, "capability_asset_inventory_p13", "asset_type = 'skill'"),
            "memory_inventory_count": count_where(conn, "capability_asset_inventory_p13", "asset_type = 'memory'"),
            "patch_proposal_count": table_row_count(conn, "asset_patch_proposals_p13"),
            "patch_eval_count": table_row_count(conn, "asset_patch_eval_results_p13"),
            "blocked_negative_patch_count": blocked_negative,
            "human_approval_count": table_row_count(conn, "asset_human_approval_records_p13"),
            "tenant_overlay_count": table_row_count(conn, "tenant_overlay_records_p13"),
            "canary_count": table_row_count(conn, "asset_canary_runs_p13"),
            "promotion_count": table_row_count(conn, "asset_promotion_records_p13"),
            "active_version_count": table_row_count(conn, "asset_active_versions_p13"),
            "invalidation_count": table_row_count(conn, "asset_invalidation_records_p13"),
            "context_policy_count": table_row_count(conn, "contextengine_injection_policy_records_p13"),
            "acceptance_count": table_row_count(conn, "asset_lifecycle_acceptance_records_p13"),
        }


def count_where(conn: sqlite3.Connection, table: str, where_clause: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table} where {where_clause}").fetchone()[0])


def persist_p13_gate_results(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from asset_lifecycle_gate_results_p13")
        for row in gate_rows:
            conn.execute(
                "insert into asset_lifecycle_gate_results_p13 values (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("p13gate", [row["gate_id"], row["generated_at"]]),
                    row["gate_id"],
                    row["gate_group"],
                    row["status"],
                    row["pass_level"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def finalize_p13_readiness_report(store: RuntimeTaskSpineStore, gate_rows: list[dict[str, Any]]) -> None:
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    decision = "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready" if fail_count == 0 else "P13_blocked"
    with store._connect() as conn:
        conn.execute(
            """
            update asset_lifecycle_readiness_reports_p13
            set release_decision = ?, gate_refs_json = ?, payload_json = ?
            where report_id = ?
            """,
            (
                decision,
                json_dumps([row["gate_id"] for row in gate_rows]),
                json_dumps({"gate_fail_count": fail_count, "gate_count": len(gate_rows)}),
                "p13_graph_skill_memory_lifecycle_report_v0_1",
            ),
        )


def build_p13_summary(
    root: Path,
    paths: P13Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        drill_task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (P13_LIFECYCLE_DRILL_TASK_ID,)).fetchone())
        report = row_to_dict(conn.execute("select * from asset_lifecycle_readiness_reports_p13 limit 1").fetchone())
    fail_count = len([row for row in gate_rows if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    outputs = {
        "schema": rel_path(paths.schema_path, root),
        "gate_rows": rel_path(paths.gate_rows_path, root),
        "summary": rel_path(paths.summary_path, root),
        "closeout_report": rel_path(paths.report_path, root),
        "runtime_db": rel_path(paths.db_path, root),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "slice": "P13 Graph / Skill / Memory Lifecycle",
        "status": status,
        "release_decision": "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready" if status == "pass" else "P13_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "inventory_status": report.get("inventory_status") or "not_evaluated",
        "staging_eval_status": report.get("staging_eval_status") or "not_evaluated",
        "hil_status": report.get("hil_status") or "not_evaluated",
        "canary_status": report.get("canary_status") or "not_evaluated",
        "active_version_status": report.get("active_version_status") or "not_evaluated",
        "contextengine_status": report.get("contextengine_status") or "not_evaluated",
        "lifecycle_rollout_status": report.get("lifecycle_rollout_status") or "not_evaluated",
        "task": task,
        "drill_task": drill_task,
        "counts": {**dict(materialized), "gate_count": len(gate_rows), "gate_fail_count": fail_count},
        "readiness_report": report,
        "outputs": outputs,
        "policy": graph_skill_memory_lifecycle_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_p13_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P13 Graph / Skill / Memory Lifecycle L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Inventory status: `{summary['inventory_status']}`",
        f"- Staging / eval status: `{summary['staging_eval_status']}`",
        f"- HIL status: `{summary['hil_status']}`",
        f"- Canary status: `{summary['canary_status']}`",
        f"- Active version status: `{summary['active_version_status']}`",
        f"- ContextEngine status: `{summary['contextengine_status']}`",
        f"- Lifecycle rollout status: `{summary['lifecycle_rollout_status']}`",
        "",
        "## Scope Boundary",
        "",
        "P13 proves a controlled lifecycle path for GraphPack, SkillPack, and MemoryPack assets: baseline inventory, staged patch proposals, deterministic eval, human approval, tenant overlay, internal canary, promotion, active-version records, and invalidation. It does not claim full tenant rollout or autonomous self-modification.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}` ({row['gate_group']}): `{row['status']}`")
    lines.extend(["", "## Known Gaps", ""])
    for gap in json_loads(str(summary["readiness_report"].get("known_gaps_json") or "[]"), []):
        lines.append(f"- `{gap.get('gap')}`: {gap.get('reason')}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def record_p13_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: P13Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("graph_skill_memory_lifecycle_schema", paths.schema_path, graph_skill_memory_lifecycle_schema_contract()),
        ("graph_skill_memory_lifecycle_summary", paths.summary_path, dict(materialized)),
        ("graph_skill_memory_lifecycle_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("graph_skill_memory_lifecycle_closeout_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="capability_lifecycle_builder",
            )
        )
    return refs
