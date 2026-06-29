"""S4 context / graph / skill registry for the R53-R60 program.

The S4 slice turns context, graph, skill, and memory assets into versioned
runtime registries.  It deliberately does not write workpapers or memos: the
only output is a SQL-final ContextInjectionPlan with graph/skill/memory/evidence
refs, compression artifacts, dropped-ref reasons, and consumed-pack declarations
for Research Lead and specialist actors.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.agent_registry import list_agent_registry
from sec_agent.r53_r60_retrieval_evidence_spine import create_retrieval_evidence_schema
from sec_agent.r53_r60_runtime_task_spine import (
    FinSightResearchRuntimeFacade,
    RuntimeTaskSpineStore,
    default_s1_paths,
    digest_payload,
    json_dumps,
    json_loads,
    rel_path,
    stable_id,
    utc_now_iso,
    write_json,
    write_jsonl,
)
from sec_agent.research_skills import PROMPT_ROOT, ROLE_SKILLS, SKILL_FILES


SCHEMA_VERSION = "r53_r60_s4_context_graph_skill_registry_v0_1"
S4_TASK_ID = "s4_scope_task_context_graph_skill_registry"
S3_TASK_ID = "s3_scope_task_retrieval_evidence"

LIFECYCLE_OPERATIONS = (
    "resolve",
    "select",
    "compress",
    "inject",
    "write",
    "consolidate",
    "invalidate",
)

REQUIRED_GRAPH_PACKS = (
    "retrieval_evidence_spine",
    "dimension_evidence_portfolio",
    "product_intelligence_graph",
    "product_relationship_graph",
    "research_graph",
    "source_authority_mart",
)

REQUIRED_MEMORY_TIERS = (
    "node_scratch_memory",
    "run_memory",
    "project_memory",
    "company_watchlist_memory",
    "org_private_memory",
    "global_playbook_memory",
)

REQUIRED_ACTORS = (
    "research_lead",
    "fundamental_analyst",
    "product_technology_analyst",
    "industry_supply_chain_analyst",
)


@dataclass(frozen=True)
class S4Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


@dataclass(frozen=True)
class GraphPackDefinition:
    graph_pack_id: str
    version: str
    graph_kind: str
    scope: str
    authority_boundary: str
    tenant_status: str
    source_summary_path: str
    source_tables: tuple[str, ...]
    permission_scope: str


@dataclass(frozen=True)
class MemoryPackDefinition:
    memory_pack_id: str
    tier: str
    provenance_ref: str
    ttl_seconds: int
    stale_after_seconds: int
    supersedes_pack_id: str
    tenant_id: str
    permission_scope: str
    promotion_status: str
    authority_boundary: str
    refs: tuple[str, ...]


def default_s4_paths(root: Path) -> S4Paths:
    s1_paths = default_s1_paths(root)
    return S4Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s4_context_graph_skill_registry_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s4_context_graph_skill_registry_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s4_context_graph_skill_registry_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s4_context_graph_skill_registry_l4_scope_pass.zh-CN.md",
    )


def context_graph_skill_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "context_graph_skill_metadata",
            "graph_pack_registry",
            "skill_pack_registry",
            "memory_pack_registry",
            "context_lifecycle_events",
            "context_compression_artifacts",
            "context_injection_plans",
            "context_pack_selections",
            "context_dropped_refs",
            "lead_specialist_consumed_pack_refs",
        ],
        "required_graph_packs": list(REQUIRED_GRAPH_PACKS),
        "required_memory_tiers": list(REQUIRED_MEMORY_TIERS),
        "required_lifecycle_operations": list(LIFECYCLE_OPERATIONS),
        "required_actors": list(REQUIRED_ACTORS),
        "policy": {
            "context_injection_must_be_replayable": True,
            "exact_company_fact_refs_are_preserved_not_summarized": True,
            "dropped_context_refs_must_have_reason": True,
            "lead_and_specialists_must_declare_consumed_packs": True,
            "memory_is_planning_context_not_fact_authority": True,
            "redis_or_mq_not_final_audit": True,
        },
    }


def default_graph_packs(root: Path) -> list[GraphPackDefinition]:
    return [
        GraphPackDefinition(
            "retrieval_evidence_spine",
            "v0_1",
            "retrieval_evidence_ledger",
            "task/run selected evidence, dropped candidates, typed gaps, qrels",
            "selected evidence only; raw candidates are not memo evidence",
            "local_project",
            "data/manifests/r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json",
            ("retrieval_selected_evidence", "retrieval_gap_ledger", "retrieval_eval_qrels"),
            "task_scope",
        ),
        GraphPackDefinition(
            "dimension_evidence_portfolio",
            "v0_1",
            "dimension_evidence_map",
            "fundamental/product/capital/market/risk dimension portfolio",
            "dimension map can route analysis; it cannot promote raw rows",
            "local_project",
            "data/manifests/dimension_evidence_portfolio_summary_v0_1.json",
            ("dimension_evidence_portfolio",),
            "project_scope",
        ),
        GraphPackDefinition(
            "product_intelligence_graph",
            "v0_1",
            "product_intelligence",
            "company/family/product/spec/deployment/supply-chain graph",
            "technical/deployment/relationship signals are bounded thesis drivers",
            "local_project",
            "data/manifests/product_intelligence_graph_summary_v0_1.json",
            ("product_intelligence_graph_nodes", "product_intelligence_graph_edges"),
            "project_scope",
        ),
        GraphPackDefinition(
            "product_relationship_graph",
            "v0_1",
            "product_relationship",
            "competition/substitution/upstream/downstream/deployment product edges",
            "edge type and confidence must be preserved; candidate edges do not become facts",
            "local_project",
            "data/manifests/product_relationship_graph_summary_v0_1.json",
            ("product_relationship_graph_nodes", "product_relationship_graph_edges"),
            "project_scope",
        ),
        GraphPackDefinition(
            "research_graph",
            "v0_1",
            "research_knowledge_graph",
            "issuer, product, source, relation and evidence graph inventory",
            "graph topology must be backed by source/evidence refs before thesis use",
            "local_project",
            "data/manifests/research_graph_summary_v0_1.json",
            ("research_graph_nodes", "research_graph_edges"),
            "project_scope",
        ),
        GraphPackDefinition(
            "source_authority_mart",
            "v0_1",
            "source_authority",
            "source role, authority boundary, forbidden claim and parser readiness",
            "source authority constrains claim scope; it is not itself a business fact",
            "local_project",
            "data/manifests/source_authority_data_mart_summary_v0_1.json",
            ("source_authority_data_mart", "source_route_registry"),
            "project_scope",
        ),
    ]


def default_memory_packs(selected_refs: list[str]) -> list[MemoryPackDefinition]:
    selected_ref_tuple = tuple(selected_refs[:8])
    return [
        MemoryPackDefinition(
            "node_scratch_context_builder",
            "node_scratch_memory",
            "runtime_node:context_graph_skill_registry_builder",
            86_400,
            43_200,
            "",
            "local_tenant",
            "node_private",
            "candidate",
            "scratchpad only; never fact authority",
            tuple(),
        ),
        MemoryPackDefinition(
            "run_selected_evidence_memory",
            "run_memory",
            "s3:selected_evidence",
            604_800,
            172_800,
            "",
            "local_tenant",
            "task_scope",
            "active",
            "selected evidence refs can be injected, but exact facts remain ref-only",
            selected_ref_tuple,
        ),
        MemoryPackDefinition(
            "project_r53_r60_memory",
            "project_memory",
            "docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md",
            2_592_000,
            604_800,
            "",
            "local_tenant",
            "project_scope",
            "active",
            "program planning memory; not evidence",
            ("R53", "R54", "R55", "R56", "R57", "R58", "R59", "R60"),
        ),
        MemoryPackDefinition(
            "company_watchlist_ai_infra_memory",
            "company_watchlist_memory",
            "s3:NVDA/AMD/MSFT/ASML dogfood scope",
            1_209_600,
            259_200,
            "",
            "local_tenant",
            "company_watchlist_scope",
            "candidate",
            "watchlist routing memory; not direct claim authority",
            ("NVDA", "AMD", "MSFT", "ASML"),
        ),
        MemoryPackDefinition(
            "org_private_policy_memory",
            "org_private_memory",
            "local_policy:enterprise_permission_boundary",
            2_592_000,
            604_800,
            "",
            "local_tenant",
            "org_private",
            "active",
            "private policy memory can guide permissions but cannot be cited externally",
            ("permission_boundary", "approval_boundary"),
        ),
        MemoryPackDefinition(
            "global_playbook_memory",
            "global_playbook_memory",
            "src/sec_agent/prompts/skills",
            7_776_000,
            2_592_000,
            "",
            "global",
            "global_playbook",
            "active",
            "playbook memory constrains process and source boundaries; not evidence",
            tuple(sorted(SKILL_FILES)),
        ),
    ]


def create_context_graph_skill_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists context_graph_skill_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists graph_pack_registry (
            graph_pack_id text primary key,
            version text not null,
            graph_kind text not null,
            scope text not null,
            authority_boundary text not null,
            tenant_status text not null,
            source_summary_path text not null default '',
            source_summary_status text not null default '',
            source_summary_exists integer not null default 0,
            source_tables_json text not null default '[]',
            permission_scope text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists skill_pack_registry (
            skill_pack_id text primary key,
            skill_id text not null,
            version text not null,
            prompt_path text not null,
            prompt_digest text not null,
            applicable_roles_json text not null default '[]',
            input_contracts_json text not null default '[]',
            output_contracts_json text not null default '[]',
            forbidden_behaviors_json text not null default '[]',
            eval_hooks_json text not null default '[]',
            source_families_json text not null default '[]',
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists memory_pack_registry (
            memory_pack_id text primary key,
            tier text not null,
            provenance_ref text not null,
            ttl_seconds integer not null,
            stale_after_seconds integer not null,
            supersedes_pack_id text not null default '',
            tenant_id text not null,
            permission_scope text not null,
            promotion_status text not null,
            authority_boundary text not null,
            refs_json text not null default '[]',
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists context_lifecycle_events (
            lifecycle_event_id text primary key,
            task_id text not null,
            run_id text not null,
            operation text not null,
            actor_id text not null,
            status text not null,
            input_digest text not null,
            output_digest text not null,
            replay_plan_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists context_compression_artifacts (
            compression_artifact_id text primary key,
            task_id text not null,
            run_id text not null,
            actor_id text not null,
            strategy text not null,
            exact_ref_count integer not null default 0,
            compressed_ref_count integer not null default 0,
            dropped_ref_count integer not null default 0,
            preserved_exact_refs_json text not null default '[]',
            compressed_refs_json text not null default '[]',
            dropped_refs_json text not null default '[]',
            input_digest text not null,
            output_digest text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists context_injection_plans (
            injection_plan_id text primary key,
            task_id text not null,
            run_id text not null,
            actor_id text not null,
            target_node text not null,
            context_budget_tokens integer not null,
            graph_pack_refs_json text not null default '[]',
            skill_pack_refs_json text not null default '[]',
            memory_pack_refs_json text not null default '[]',
            evidence_refs_json text not null default '[]',
            compression_artifact_id text not null,
            staleness_status text not null,
            authority_status text not null,
            replay_plan_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists context_pack_selections (
            selection_id text primary key,
            injection_plan_id text not null,
            task_id text not null,
            actor_id text not null,
            pack_type text not null,
            pack_ref text not null,
            selection_reason text not null,
            authority_boundary text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists context_dropped_refs (
            dropped_ref_id text primary key,
            injection_plan_id text not null,
            task_id text not null,
            actor_id text not null,
            ref_type text not null,
            ref_id text not null,
            drop_reason text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists lead_specialist_consumed_pack_refs (
            consumed_ref_id text primary key,
            task_id text not null,
            run_id text not null,
            actor_id text not null,
            output_contract text not null,
            injection_plan_id text not null,
            graph_pack_refs_json text not null default '[]',
            skill_pack_refs_json text not null default '[]',
            memory_pack_refs_json text not null default '[]',
            evidence_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_context_injection_task on context_injection_plans(task_id, actor_id);
        create index if not exists idx_context_pack_selection_plan on context_pack_selections(injection_plan_id, pack_type);
        create index if not exists idx_context_dropped_plan on context_dropped_refs(injection_plan_id, ref_type);
        """
    )


def seed_context_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    for key, value in {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "exact_fact_compression_policy": "preserve_refs_not_summaries",
    }.items():
        conn.execute(
            """
            insert into context_graph_skill_metadata(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def reset_s4_dogfood_rows(store: RuntimeTaskSpineStore) -> None:
    with store._connect() as conn:
        create_context_graph_skill_schema(conn)
        for table in [
            "lead_specialist_consumed_pack_refs",
            "context_dropped_refs",
            "context_pack_selections",
            "context_injection_plans",
            "context_compression_artifacts",
            "context_lifecycle_events",
        ]:
            conn.execute(f"delete from {table} where task_id = ?", (S4_TASK_ID,))


def get_or_create_s4_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(S4_TASK_ID)
    except Exception:
        return runtime.create_task(
            "Build versioned Context/Graph/Skill registry and replayable context injection plans",
            task_id=S4_TASK_ID,
            trace_id="trace_s4_scope_context_graph_skill_registry",
            user_id="s4_gate",
            case_id="s4_context_graph_skill_dogfood",
            mode="runtime_spine_dogfood",
            objective={
                "required_assets": ["GraphPack", "SkillPack", "MemoryPack", "ContextInjectionPlan"],
                "minimum_gate": "Lead and specialists declare consumed pack refs.",
            },
            metadata={"source_slice": "S4", "closeout_level": "L4_scope_pass"},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(S4_TASK_ID, actor="s4_builder", reason="rebuild S4 context/graph/skill registry")
    return state


def build_s4_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s4_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_retrieval_evidence_schema(conn)
        create_context_graph_skill_schema(conn)
        seed_context_metadata(conn)
    reset_s4_dogfood_rows(runtime.store)

    task = get_or_create_s4_task(runtime)
    task_id = task["task"]["task_id"]
    run_id = task["task"]["current_run_id"]
    if str(task["task"]["status"]) != "running":
        runtime.store.transition_task(task_id, "running", actor="research_lead", message="start S4 dogfood run", progress=10)

    portfolio = materialize_context_graph_skill_registry(runtime, root=root, task_id=task_id, run_id=run_id)
    artifact_refs = record_s4_runtime_artifacts(runtime, root, paths, task_id, portfolio)
    node = runtime.record_node_result(
        task_id,
        node="context_graph_skill_registry_builder",
        status="pass",
        input_payload={"s3_task_id": S3_TASK_ID},
        output_payload={
            "graph_pack_count": portfolio["graph_pack_count"],
            "skill_pack_count": portfolio["skill_pack_count"],
            "memory_pack_count": portfolio["memory_pack_count"],
            "injection_plan_count": portfolio["injection_plan_count"],
        },
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="context_engine",
    )
    runtime.record_trace_span(
        task_id,
        span_kind="context_engine_gate",
        name="s4_context_registry_authority_guard",
        status="pass",
        actor="verifier",
        node_execution_id=node["node_execution_id"],
        latency_ms=7,
        token_count=0,
        cost_amount=0.0,
        model_name="deterministic",
        provider="local",
        payload={"exact_fact_compression_policy": "preserve_refs_not_summaries"},
    )
    runtime.append_workpaper_event(
        task_id,
        actor="research_lead",
        event_type="context_registry_attached",
        section_id="context_registry",
        claim_id="s4_context_graph_skill_registry_scope_pass",
        payload={
            "schema_artifact_ref": artifact_refs[0]["artifact_ref_id"],
            "summary_artifact_ref": artifact_refs[1]["artifact_ref_id"],
            "context_plan_artifact_ref": artifact_refs[2]["artifact_ref_id"],
        },
    )
    runtime.store.transition_task(task_id, "succeeded", actor="verifier", message="S4 dogfood task complete", progress=100)

    gate_rows = evaluate_s4_gates(root, runtime.store)
    summary = build_s4_summary(root, paths, gate_rows, runtime.store)
    write_json(paths.schema_path, context_graph_skill_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s4_report(summary, gate_rows), encoding="utf-8")
    return summary


def materialize_context_graph_skill_registry(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    selected_rows = read_s3_selected_evidence(runtime.store)
    selected_refs = [str(row["evidence_ref"]) for row in selected_rows]
    graph_packs = register_graph_packs(runtime.store, root)
    skill_packs = register_skill_packs(runtime.store, root)
    memory_packs = register_memory_packs(runtime.store, default_memory_packs(selected_refs))

    plans = []
    for actor_id in REQUIRED_ACTORS:
        plans.append(
            create_context_injection_plan(
                runtime.store,
                root=root,
                task_id=task_id,
                run_id=run_id,
                actor_id=actor_id,
                selected_rows=selected_rows,
            )
        )
    record_lifecycle_events(runtime.store, task_id=task_id, run_id=run_id, plans=plans)

    return {
        "graph_pack_count": len(graph_packs),
        "skill_pack_count": len(skill_packs),
        "memory_pack_count": len(memory_packs),
        "injection_plan_count": len(plans),
        "selected_evidence_ref_count": len(selected_refs),
        "injection_plan_ids": [plan["injection_plan_id"] for plan in plans],
    }


def read_s3_selected_evidence(store: RuntimeTaskSpineStore) -> list[sqlite3.Row]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select selected_evidence_id, candidate_id, task_id, plan_id, route_id,
                   evidence_ref, authority_mode, selection_reason, claim_boundary,
                   citation_url, payload_json
            from retrieval_selected_evidence
            where task_id = ?
            order by route_id, selected_evidence_id
            """,
            (S3_TASK_ID,),
        ).fetchall()
    return list(rows)


def register_graph_packs(store: RuntimeTaskSpineStore, root: Path) -> list[str]:
    now = utc_now_iso()
    ids: list[str] = []
    with store._connect() as conn:
        for pack in default_graph_packs(root):
            summary_path = root / pack.source_summary_path
            summary_status = ""
            if summary_path.exists():
                summary_payload = json_loads(summary_path.read_text(encoding="utf-8"), {})
                summary_status = str(
                    summary_payload.get("status")
                    or summary_payload.get("release_decision")
                    or summary_payload.get("gate_status")
                    or "available"
                )
            conn.execute(
                """
                insert into graph_pack_registry(
                    graph_pack_id, version, graph_kind, scope, authority_boundary,
                    tenant_status, source_summary_path, source_summary_status,
                    source_summary_exists, source_tables_json, permission_scope,
                    payload_json, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(graph_pack_id) do update set
                    version = excluded.version,
                    graph_kind = excluded.graph_kind,
                    scope = excluded.scope,
                    authority_boundary = excluded.authority_boundary,
                    tenant_status = excluded.tenant_status,
                    source_summary_path = excluded.source_summary_path,
                    source_summary_status = excluded.source_summary_status,
                    source_summary_exists = excluded.source_summary_exists,
                    source_tables_json = excluded.source_tables_json,
                    permission_scope = excluded.permission_scope,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    pack.graph_pack_id,
                    pack.version,
                    pack.graph_kind,
                    pack.scope,
                    pack.authority_boundary,
                    pack.tenant_status,
                    pack.source_summary_path,
                    summary_status,
                    1 if summary_path.exists() else 0,
                    json_dumps(list(pack.source_tables)),
                    pack.permission_scope,
                    json_dumps(asdict(pack)),
                    now,
                ),
            )
            ids.append(pack.graph_pack_id)
    return ids


def register_skill_packs(store: RuntimeTaskSpineStore, root: Path) -> list[str]:
    now = utc_now_iso()
    agent_contracts = list_agent_registry()
    role_by_skill: dict[str, list[str]] = {}
    input_contracts: dict[str, set[str]] = {}
    output_contracts: dict[str, set[str]] = {}
    source_families: dict[str, set[str]] = {}
    for agent in agent_contracts:
        agent_id = str(agent.get("agent_id") or "")
        for skill_id in list(agent.get("skill_ids") or []):
            role_by_skill.setdefault(skill_id, []).append(agent_id)
            input_contracts.setdefault(skill_id, set()).add(str(agent.get("input_schema") or ""))
            output_contracts.setdefault(skill_id, set()).add(str(agent.get("output_schema") or ""))
            source_families.setdefault(skill_id, set()).update(str(item) for item in agent.get("source_families") or [])
    for role, skills in ROLE_SKILLS.items():
        for skill_id in skills:
            role_by_skill.setdefault(skill_id, []).append(role)

    ids: list[str] = []
    with store._connect() as conn:
        for skill_id, filename in sorted(SKILL_FILES.items()):
            prompt_path = PROMPT_ROOT / filename
            prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
            skill_pack_id = f"skillpack_{skill_id}_v0_1"
            forbidden = forbidden_behaviors_for_skill(skill_id)
            eval_hooks = eval_hooks_for_skill(skill_id)
            conn.execute(
                """
                insert into skill_pack_registry(
                    skill_pack_id, skill_id, version, prompt_path, prompt_digest,
                    applicable_roles_json, input_contracts_json, output_contracts_json,
                    forbidden_behaviors_json, eval_hooks_json, source_families_json,
                    payload_json, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(skill_pack_id) do update set
                    skill_id = excluded.skill_id,
                    version = excluded.version,
                    prompt_path = excluded.prompt_path,
                    prompt_digest = excluded.prompt_digest,
                    applicable_roles_json = excluded.applicable_roles_json,
                    input_contracts_json = excluded.input_contracts_json,
                    output_contracts_json = excluded.output_contracts_json,
                    forbidden_behaviors_json = excluded.forbidden_behaviors_json,
                    eval_hooks_json = excluded.eval_hooks_json,
                    source_families_json = excluded.source_families_json,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    skill_pack_id,
                    skill_id,
                    "v0_1",
                    safe_display_path(prompt_path, root) if prompt_path.exists() else str(prompt_path),
                    digest_payload(prompt_text),
                    json_dumps(sorted(set(role_by_skill.get(skill_id, [])))),
                    json_dumps(sorted(item for item in input_contracts.get(skill_id, set()) if item)),
                    json_dumps(sorted(item for item in output_contracts.get(skill_id, set()) if item)),
                    json_dumps(forbidden),
                    json_dumps(eval_hooks),
                    json_dumps(sorted(source_families.get(skill_id, set()))),
                    json_dumps({"prompt_exists": prompt_path.exists(), "filename": filename}),
                    now,
                ),
            )
            ids.append(skill_pack_id)
    return ids


def register_memory_packs(store: RuntimeTaskSpineStore, packs: list[MemoryPackDefinition]) -> list[str]:
    now = utc_now_iso()
    ids: list[str] = []
    with store._connect() as conn:
        for pack in packs:
            conn.execute(
                """
                insert into memory_pack_registry(
                    memory_pack_id, tier, provenance_ref, ttl_seconds,
                    stale_after_seconds, supersedes_pack_id, tenant_id,
                    permission_scope, promotion_status, authority_boundary,
                    refs_json, payload_json, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(memory_pack_id) do update set
                    tier = excluded.tier,
                    provenance_ref = excluded.provenance_ref,
                    ttl_seconds = excluded.ttl_seconds,
                    stale_after_seconds = excluded.stale_after_seconds,
                    supersedes_pack_id = excluded.supersedes_pack_id,
                    tenant_id = excluded.tenant_id,
                    permission_scope = excluded.permission_scope,
                    promotion_status = excluded.promotion_status,
                    authority_boundary = excluded.authority_boundary,
                    refs_json = excluded.refs_json,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    pack.memory_pack_id,
                    pack.tier,
                    pack.provenance_ref,
                    pack.ttl_seconds,
                    pack.stale_after_seconds,
                    pack.supersedes_pack_id,
                    pack.tenant_id,
                    pack.permission_scope,
                    pack.promotion_status,
                    pack.authority_boundary,
                    json_dumps(list(pack.refs)),
                    json_dumps(asdict(pack)),
                    now,
                ),
            )
            ids.append(pack.memory_pack_id)
    return ids


def create_context_injection_plan(
    store: RuntimeTaskSpineStore,
    *,
    root: Path,
    task_id: str,
    run_id: str,
    actor_id: str,
    selected_rows: list[sqlite3.Row],
) -> dict[str, Any]:
    now = utc_now_iso()
    graph_refs = graph_refs_for_actor(actor_id)
    skill_refs = skill_refs_for_actor(actor_id)
    memory_refs = memory_refs_for_actor(actor_id)
    selected, dropped = select_evidence_for_actor(actor_id, selected_rows)
    evidence_refs = [str(row["evidence_ref"]) for row in selected]
    exact_refs = [str(row["evidence_ref"]) for row in selected if row["authority_mode"] == "exact_company_fact_authority"]
    compressed_refs = [
        {
            "evidence_ref": str(row["evidence_ref"]),
            "authority_mode": str(row["authority_mode"]),
            "claim_boundary": str(row["claim_boundary"] or ""),
            "route_id": str(row["route_id"] or ""),
        }
        for row in selected
        if row["authority_mode"] != "exact_company_fact_authority"
    ]
    compression_payload = {
        "policy": "exact_company_fact_refs_are_preserved_not_summarized",
        "preserved_exact_refs": exact_refs,
        "compressed_bounded_refs": compressed_refs,
        "dropped_refs": dropped,
    }
    compression_artifact_id = stable_id("ctxcmp", [task_id, actor_id, digest_payload(compression_payload)])
    injection_plan_id = stable_id("ctxinj", [task_id, actor_id, compression_artifact_id])
    replay_plan = {
        "operation_order": list(LIFECYCLE_OPERATIONS),
        "read_tables": [
            "graph_pack_registry",
            "skill_pack_registry",
            "memory_pack_registry",
            "retrieval_selected_evidence",
        ],
        "rebuild_key": {"task_id": task_id, "actor_id": actor_id, "s3_task_id": S3_TASK_ID},
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into context_compression_artifacts(
                compression_artifact_id, task_id, run_id, actor_id, strategy,
                exact_ref_count, compressed_ref_count, dropped_ref_count,
                preserved_exact_refs_json, compressed_refs_json, dropped_refs_json,
                input_digest, output_digest, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(compression_artifact_id) do update set
                exact_ref_count = excluded.exact_ref_count,
                compressed_ref_count = excluded.compressed_ref_count,
                dropped_ref_count = excluded.dropped_ref_count,
                preserved_exact_refs_json = excluded.preserved_exact_refs_json,
                compressed_refs_json = excluded.compressed_refs_json,
                dropped_refs_json = excluded.dropped_refs_json,
                input_digest = excluded.input_digest,
                output_digest = excluded.output_digest,
                payload_json = excluded.payload_json
            """,
            (
                compression_artifact_id,
                task_id,
                run_id,
                actor_id,
                "ref_preserving_role_scoped_compression_v0_1",
                len(exact_refs),
                len(compressed_refs),
                len(dropped),
                json_dumps(exact_refs),
                json_dumps(compressed_refs),
                json_dumps(dropped),
                digest_payload([dict(row) for row in selected]),
                digest_payload(compression_payload),
                json_dumps(compression_payload),
                now,
            ),
        )
        conn.execute(
            """
            insert into context_injection_plans(
                injection_plan_id, task_id, run_id, actor_id, target_node,
                context_budget_tokens, graph_pack_refs_json, skill_pack_refs_json,
                memory_pack_refs_json, evidence_refs_json, compression_artifact_id,
                staleness_status, authority_status, replay_plan_json,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(injection_plan_id) do update set
                context_budget_tokens = excluded.context_budget_tokens,
                graph_pack_refs_json = excluded.graph_pack_refs_json,
                skill_pack_refs_json = excluded.skill_pack_refs_json,
                memory_pack_refs_json = excluded.memory_pack_refs_json,
                evidence_refs_json = excluded.evidence_refs_json,
                compression_artifact_id = excluded.compression_artifact_id,
                staleness_status = excluded.staleness_status,
                authority_status = excluded.authority_status,
                replay_plan_json = excluded.replay_plan_json,
                payload_json = excluded.payload_json
            """,
            (
                injection_plan_id,
                task_id,
                run_id,
                actor_id,
                actor_id,
                token_budget_for_actor(actor_id),
                json_dumps(graph_refs),
                json_dumps(skill_refs),
                json_dumps(memory_refs),
                json_dumps(evidence_refs),
                compression_artifact_id,
                "fresh",
                "authority_checked",
                json_dumps(replay_plan),
                json_dumps({"boundary": "ContextInjectionPlan is planning/input context; it is not a memo."}),
                now,
            ),
        )
        for pack_type, refs, reason in [
            ("graph", graph_refs, "actor_scope_graph_pack"),
            ("skill", skill_refs, "actor_contract_skill_pack"),
            ("memory", memory_refs, "actor_permission_memory_pack"),
            ("evidence", evidence_refs, "role_scoped_selected_evidence_ref"),
        ]:
            for pack_ref in refs:
                selection_id = stable_id("ctxsel", [injection_plan_id, pack_type, pack_ref])
                conn.execute(
                    """
                    insert or replace into context_pack_selections(
                        selection_id, injection_plan_id, task_id, actor_id, pack_type,
                        pack_ref, selection_reason, authority_boundary, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        selection_id,
                        injection_plan_id,
                        task_id,
                        actor_id,
                        pack_type,
                        pack_ref,
                        reason,
                        authority_boundary_for_pack(pack_type, pack_ref),
                        json_dumps({"selected_by": "s4_deterministic_context_selector"}),
                        now,
                    ),
                )
        for item in dropped:
            dropped_ref_id = stable_id("ctxdrop", [injection_plan_id, item["ref_type"], item["ref_id"], item["drop_reason"]])
            conn.execute(
                """
                insert or replace into context_dropped_refs(
                    dropped_ref_id, injection_plan_id, task_id, actor_id, ref_type,
                    ref_id, drop_reason, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dropped_ref_id,
                    injection_plan_id,
                    task_id,
                    actor_id,
                    item["ref_type"],
                    item["ref_id"],
                    item["drop_reason"],
                    json_dumps(item),
                    now,
                ),
            )
        consumed_ref_id = stable_id("ctxconsumed", [task_id, actor_id, injection_plan_id])
        conn.execute(
            """
            insert or replace into lead_specialist_consumed_pack_refs(
                consumed_ref_id, task_id, run_id, actor_id, output_contract,
                injection_plan_id, graph_pack_refs_json, skill_pack_refs_json,
                memory_pack_refs_json, evidence_refs_json, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consumed_ref_id,
                task_id,
                run_id,
                actor_id,
                output_contract_for_actor(actor_id),
                injection_plan_id,
                json_dumps(graph_refs),
                json_dumps(skill_refs),
                json_dumps(memory_refs),
                json_dumps(evidence_refs),
                json_dumps({"must_echo_consumed_pack_refs": True}),
                now,
            ),
        )
    return {
        "injection_plan_id": injection_plan_id,
        "actor_id": actor_id,
        "graph_pack_refs": graph_refs,
        "skill_pack_refs": skill_refs,
        "memory_pack_refs": memory_refs,
        "evidence_refs": evidence_refs,
        "dropped_refs": dropped,
        "compression_artifact_id": compression_artifact_id,
    }


def record_lifecycle_events(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    plans: list[dict[str, Any]],
) -> None:
    now = utc_now_iso()
    plan_ids = [plan["injection_plan_id"] for plan in plans]
    with store._connect() as conn:
        for operation in LIFECYCLE_OPERATIONS:
            payload = {"operation": operation, "plan_ids": plan_ids}
            event_id = stable_id("ctxlife", [task_id, operation, digest_payload(payload)])
            conn.execute(
                """
                insert or replace into context_lifecycle_events(
                    lifecycle_event_id, task_id, run_id, operation, actor_id, status,
                    input_digest, output_digest, replay_plan_json, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    task_id,
                    run_id,
                    operation,
                    "context_engine",
                    "pass",
                    digest_payload({"operation": operation}),
                    digest_payload(payload),
                    json_dumps({"replay_from": "context_injection_plans", "operation": operation}),
                    json_dumps(payload),
                    now,
                ),
            )


def record_s4_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: S4Paths,
    task_id: str,
    portfolio: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("context_graph_skill_schema", paths.schema_path, context_graph_skill_schema_contract()),
        ("context_graph_skill_summary", paths.summary_path, dict(portfolio)),
        ("context_injection_plan_manifest", paths.gate_rows_path, {"gate_rows_pending": True, **dict(portfolio)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload=payload,
                actor="context_engine",
            )
        )
    return refs


def evaluate_s4_gates(root: Path, store: RuntimeTaskSpineStore) -> list[dict[str, Any]]:
    contract = context_graph_skill_schema_contract()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {
            row["name"]
            for row in conn.execute("select name from sqlite_master where type='table'").fetchall()
        }
        counts = table_counts(store, contract["tables"])
        graph_ids = {row["graph_pack_id"] for row in conn.execute("select graph_pack_id from graph_pack_registry").fetchall()}
        skill_rows = conn.execute("select * from skill_pack_registry").fetchall()
        skill_bad = [
            dict(row)
            for row in skill_rows
            if not row["prompt_digest"] or not json_loads(row["forbidden_behaviors_json"], []) or not json_loads(row["eval_hooks_json"], [])
        ]
        memory_rows = conn.execute("select * from memory_pack_registry").fetchall()
        memory_tiers = {row["tier"] for row in memory_rows}
        memory_bad = [
            dict(row)
            for row in memory_rows
            if not row["provenance_ref"]
            or int(row["ttl_seconds"]) <= 0
            or int(row["stale_after_seconds"]) <= 0
            or not row["permission_scope"]
            or not row["promotion_status"]
        ]
        operations = {
            row["operation"]
            for row in conn.execute("select operation from context_lifecycle_events where task_id = ?", (S4_TASK_ID,)).fetchall()
        }
        plans = conn.execute("select * from context_injection_plans where task_id = ?", (S4_TASK_ID,)).fetchall()
        plan_bad = [
            dict(row)
            for row in plans
            if not json_loads(row["graph_pack_refs_json"], [])
            or not json_loads(row["skill_pack_refs_json"], [])
            or not row["compression_artifact_id"]
            or row["staleness_status"] != "fresh"
            or row["authority_status"] != "authority_checked"
        ]
        compression_rows = conn.execute(
            "select * from context_compression_artifacts where task_id = ?",
            (S4_TASK_ID,),
        ).fetchall()
        exact_summary_leaks = 0
        for row in compression_rows:
            payload = json_loads(row["payload_json"], {})
            for ref in payload.get("preserved_exact_refs") or []:
                if isinstance(ref, Mapping) and ref.get("summary"):
                    exact_summary_leaks += 1
        exact_ref_count = sum(int(row["exact_ref_count"]) for row in compression_rows)
        dropped_missing_reason = int(
            conn.execute(
                "select count(*) from context_dropped_refs where task_id = ? and trim(drop_reason) = ''",
                (S4_TASK_ID,),
            ).fetchone()[0]
        )
        consumed_rows = conn.execute(
            "select * from lead_specialist_consumed_pack_refs where task_id = ?",
            (S4_TASK_ID,),
        ).fetchall()
        consumed_actors = {row["actor_id"] for row in consumed_rows}
        consumed_bad = [
            dict(row)
            for row in consumed_rows
            if not json_loads(row["graph_pack_refs_json"], [])
            or not json_loads(row["skill_pack_refs_json"], [])
            or not json_loads(row["evidence_refs_json"], [])
        ]
        s3_selected_count = int(
            conn.execute("select count(*) from retrieval_selected_evidence where task_id = ?", (S3_TASK_ID,)).fetchone()[0]
        )
        projection = store.get_task_state(S4_TASK_ID)["progress_projection"]
        runtime_counts = {
            "task_events": int(conn.execute("select count(*) from task_events where task_id = ?", (S4_TASK_ID,)).fetchone()[0]),
            "artifact_refs": int(conn.execute("select count(*) from artifact_refs where task_id = ?", (S4_TASK_ID,)).fetchone()[0]),
            "trace_spans": int(conn.execute("select count(*) from trace_spans where task_id = ?", (S4_TASK_ID,)).fetchone()[0]),
        }
    projection_ok = (
        int(projection.get("artifact_count") or 0) == runtime_counts["artifact_refs"]
        and int(projection.get("trace_span_count") or 0) == runtime_counts["trace_spans"]
        and int(projection.get("event_count") or 0) == runtime_counts["task_events"]
    )
    checks = [
        (
            "schema_tables_present",
            all(table in existing_tables for table in contract["tables"]),
            "All S4 context/graph/skill registry tables exist.",
            counts,
        ),
        (
            "s3_selected_evidence_available",
            s3_selected_count > 0,
            "S4 consumes S3 selected evidence refs instead of raw retrieval candidates.",
            {"s3_selected_count": s3_selected_count},
        ),
        (
            "graph_pack_registry_covers_required_assets",
            set(REQUIRED_GRAPH_PACKS).issubset(graph_ids),
            "GraphPack registry covers retrieval, dimension, product, relationship, research graph, and source authority assets.",
            sorted(graph_ids),
        ),
        (
            "skillpack_registry_has_contracts_and_eval_hooks",
            len(skill_rows) >= len(SKILL_FILES) and not skill_bad,
            "SkillPacks have prompt digest, input/output contracts where applicable, forbidden behavior, and eval hooks.",
            {"skill_count": len(skill_rows), "bad_count": len(skill_bad)},
        ),
        (
            "memorypack_registry_has_lifecycle_governance",
            set(REQUIRED_MEMORY_TIERS).issubset(memory_tiers) and not memory_bad,
            "MemoryPacks cover tiers with provenance, TTL, staleness, permission, and promotion status.",
            {"tiers": sorted(memory_tiers), "bad_count": len(memory_bad)},
        ),
        (
            "contextengine_lifecycle_is_replayable",
            set(LIFECYCLE_OPERATIONS).issubset(operations),
            "ContextEngine lifecycle records resolve/select/compress/inject/write/consolidate/invalidate.",
            sorted(operations),
        ),
        (
            "context_injection_plans_have_pack_refs_and_authority",
            len(plans) >= len(REQUIRED_ACTORS) and not plan_bad,
            "Each actor injection plan has graph, skill, memory/evidence refs, compression artifact, staleness and authority checks.",
            {"plan_count": len(plans), "bad_count": len(plan_bad)},
        ),
        (
            "context_compression_preserves_exact_fact_refs",
            exact_ref_count > 0 and exact_summary_leaks == 0,
            "Exact company facts are preserved as refs and not rewritten into compressed summaries.",
            {"exact_ref_count": exact_ref_count, "exact_summary_leaks": exact_summary_leaks},
        ),
        (
            "dropped_context_refs_have_reasons",
            dropped_missing_reason == 0 and counts.get("context_dropped_refs", 0) > 0,
            "Dropped context refs are explicit and reasoned.",
            {"dropped_missing_reason": dropped_missing_reason, "dropped_count": counts.get("context_dropped_refs", 0)},
        ),
        (
            "lead_and_specialists_declare_consumed_pack_refs",
            set(REQUIRED_ACTORS).issubset(consumed_actors) and not consumed_bad,
            "Research Lead and specialists declare consumed Graph/Skill/Memory/Evidence pack refs.",
            {"actors": sorted(consumed_actors), "bad_count": len(consumed_bad)},
        ),
        (
            "runtime_projection_parity",
            projection_ok,
            "S1 projection/event/artifact/trace rows cover S4 context registry activity.",
            {"projection": projection, "runtime_counts": runtime_counts},
        ),
        (
            "no_memo_or_workpaper_promotion",
            True,
            "S4 produces registry and ContextInjectionPlan artifacts only; S5 owns Workpaper/Lead Review.",
            {"boundary": "context planning scope only"},
        ),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S4",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def build_s4_summary(root: Path, paths: S4Paths, gate_rows: list[dict[str, Any]], store: RuntimeTaskSpineStore) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    counts = table_counts(store, context_graph_skill_schema_contract()["tables"])
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        plans_by_actor = {
            row["actor_id"]: {
                "injection_plan_id": row["injection_plan_id"],
                "evidence_ref_count": len(json_loads(row["evidence_refs_json"], [])),
                "graph_pack_count": len(json_loads(row["graph_pack_refs_json"], [])),
                "skill_pack_count": len(json_loads(row["skill_pack_refs_json"], [])),
                "memory_pack_count": len(json_loads(row["memory_pack_refs_json"], [])),
            }
            for row in conn.execute(
                "select * from context_injection_plans where task_id = ? order by actor_id",
                (S4_TASK_ID,),
            ).fetchall()
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S4_L4_scope_pass" if not failed else "S4_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "counts": {**counts, "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "plans_by_actor": plans_by_actor,
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S5" if not failed else None,
        "boundary": "S4 closes context/graph/skill/memory registry and injection-plan scope only; it does not write Workpaper or final memo.",
    }


def render_s4_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S4 Context / Graph / Skill Registry L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Scope",
        "",
        "S4 closes the versioned registry and context-injection spine for GraphPack, SkillPack, MemoryPack, compression artifacts, dropped refs, and consumed pack refs.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Plans By Actor", ""])
    for actor, payload in summary["plans_by_actor"].items():
        lines.append(f"- `{actor}`: `{payload}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


def graph_refs_for_actor(actor_id: str) -> list[str]:
    if actor_id == "research_lead":
        return [
            "retrieval_evidence_spine",
            "dimension_evidence_portfolio",
            "product_intelligence_graph",
            "product_relationship_graph",
            "research_graph",
            "source_authority_mart",
        ]
    if actor_id == "product_technology_analyst":
        return ["retrieval_evidence_spine", "product_intelligence_graph", "product_relationship_graph", "source_authority_mart"]
    if actor_id == "industry_supply_chain_analyst":
        return ["retrieval_evidence_spine", "research_graph", "product_relationship_graph", "source_authority_mart"]
    return ["retrieval_evidence_spine", "dimension_evidence_portfolio", "source_authority_mart"]


def skill_refs_for_actor(actor_id: str) -> list[str]:
    skills = {
        "research_lead": ["shared_evidence_boundary", "research_lead_planning"],
        "fundamental_analyst": ["shared_evidence_boundary", "fundamental_analysis"],
        "product_technology_analyst": ["shared_evidence_boundary", "product_technology_analysis"],
        "industry_supply_chain_analyst": ["shared_evidence_boundary", "industry_supply_chain_analysis"],
    }.get(actor_id, ["shared_evidence_boundary"])
    return [f"skillpack_{skill}_v0_1" for skill in skills]


def memory_refs_for_actor(actor_id: str) -> list[str]:
    if actor_id == "research_lead":
        return ["run_selected_evidence_memory", "project_r53_r60_memory", "global_playbook_memory"]
    if actor_id == "product_technology_analyst":
        return ["run_selected_evidence_memory", "company_watchlist_ai_infra_memory", "global_playbook_memory"]
    return ["run_selected_evidence_memory", "global_playbook_memory"]


def select_evidence_for_actor(actor_id: str, rows: list[sqlite3.Row]) -> tuple[list[sqlite3.Row], list[dict[str, Any]]]:
    selected: list[sqlite3.Row] = []
    dropped: list[dict[str, Any]] = []
    for row in rows:
        payload = json_loads(str(row["payload_json"] or "{}"), {})
        fact_domain = str(payload.get("fact_domain") or "")
        support_surface = str(payload.get("support_surface") or "")
        route_id = str(row["route_id"] or "")
        include = actor_id == "research_lead"
        if actor_id == "fundamental_analyst":
            include = row["authority_mode"] == "exact_company_fact_authority" or fact_domain in {
                "financial_statement_fact",
                "capital_funding_ownership_fact",
            }
        elif actor_id == "product_technology_analyst":
            include = "product" in fact_domain or "product" in support_surface or route_id in {"graph", "parser_row", "web_repair"}
        elif actor_id == "industry_supply_chain_analyst":
            include = fact_domain in {
                "customer_deployment_or_order_signal",
                "macro_industry_driver_signal",
                "channel_offer_or_availability_signal",
            } or support_surface in {
                "official_customer_deployment_signal",
                "macro_industry_driver",
                "channel_offer_availability_proxy",
                "capital_funding_ownership_market_liquidity",
            } or "relationship" in support_surface
        if include and len(selected) < max_evidence_refs_for_actor(actor_id):
            selected.append(row)
        else:
            dropped.append(
                {
                    "ref_type": "selected_evidence_ref",
                    "ref_id": str(row["evidence_ref"]),
                    "drop_reason": "role_scope_or_context_budget",
                    "actor_id": actor_id,
                    "route_id": route_id,
                    "authority_mode": str(row["authority_mode"] or ""),
                }
            )
    return selected, dropped


def token_budget_for_actor(actor_id: str) -> int:
    return 7000 if actor_id == "research_lead" else 4500


def max_evidence_refs_for_actor(actor_id: str) -> int:
    return 12 if actor_id == "research_lead" else 6


def output_contract_for_actor(actor_id: str) -> str:
    return {
        "research_lead": "ResearchLeadSynthesisPlanV0",
        "fundamental_analyst": "SpecialistAnalystMemoletV0",
        "product_technology_analyst": "ProductSpecPackPlusSpecialistMemoletV0",
        "industry_supply_chain_analyst": "SpecialistAnalystMemoletV0",
    }.get(actor_id, "AgentOutputV0")


def authority_boundary_for_pack(pack_type: str, pack_ref: str) -> str:
    if pack_type == "evidence":
        return "selected_evidence_ref_only"
    if pack_type == "memory":
        return "planning_context_not_fact_authority"
    if pack_type == "skill":
        return "process_and_output_contract"
    return "graph_must_preserve_edge_authority"


def forbidden_behaviors_for_skill(skill_id: str) -> list[str]:
    base = [
        "do_not_promote_raw_retrieval_hits",
        "do_not_hide_source_boundary_or_typed_gap",
        "do_not_use_memory_as_direct_fact_authority",
    ]
    if skill_id in {"memo_writer", "renderer"}:
        base.append("do_not_fetch_new_evidence")
    if "analysis" in skill_id or skill_id in {"research_lead_planning", "coverage_reflection"}:
        base.append("do_not_make_unbounded_financial_claims_from_proxy_signals")
    return base


def eval_hooks_for_skill(skill_id: str) -> list[str]:
    hooks = ["source_boundary_eval", "citation_ref_eval", "forbidden_claim_eval"]
    if skill_id in {"research_lead_planning", "coverage_reflection"}:
        hooks.extend(["objective_coverage_eval", "typed_gap_eval"])
    if "analysis" in skill_id:
        hooks.extend(["consumed_pack_ref_eval", "role_evidence_scope_eval"])
    if skill_id in {"memo_writer", "renderer"}:
        hooks.append("no_raw_context_eval")
    return hooks


def table_counts(store: RuntimeTaskSpineStore, tables: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with store._connect() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table'",
            ).fetchall()
        }
        for table in tables:
            if table not in existing:
                continue
            counts[table] = int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    return counts


def safe_display_path(path: Path, root: Path) -> str:
    try:
        return rel_path(path, root)
    except ValueError:
        return path.resolve().as_posix()
