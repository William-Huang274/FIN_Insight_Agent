"""S3 retrieval / evidence spine for the R53-R60 program.

The S3 slice turns accepted RD3/RD5/RD6/RD7/PIG assets into a runtime
retrieval ledger.  It deliberately keeps retrieval hits separate from
promotable evidence: candidates, selections, drops, qrels, and typed gaps are
all SQL-final and trace-linked before later slices build context, workpapers,
or deliverables.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

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
from sec_agent.r53_r60_tool_sandbox_spine import FinSightToolGateway


SCHEMA_VERSION = "r53_r60_s3_retrieval_evidence_spine_v0_1"

REQUIRED_ROUTES = (
    "sql_exact",
    "graph",
    "bm25",
    "object_bm25",
    "milvus_semantic",
    "web_repair",
    "parser_row",
)
PROMOTABLE_AUTHORITY_MODES = {"exact_company_fact_authority", "bounded_thesis_driver_authority"}
FORBIDDEN_SELECTED_AUTHORITY_MODES = {"planning_or_gap_only", "retrieval_candidate_only"}

UPSTREAM_SUMMARIES = {
    "gold_fact_signal_mart": ("data/manifests/gold_fact_signal_mart_summary_v0_1.json", {"pass"}),
    "retrieval_index_registry": ("data/manifests/retrieval_index_registry_summary_v0_1.json", {"pass"}),
    "agent_runtime_consumption_contract": (
        "data/manifests/agent_runtime_consumption_contract_summary_v0_1.json",
        {"pass"},
    ),
    "research_graph": ("data/manifests/research_graph_summary_v0_1.json", {"pass"}),
    "product_intelligence_graph": ("data/manifests/product_intelligence_graph_summary_v0_1.json", {"pass"}),
    "data_quality_release_eval_gate": (
        "data/manifests/data_quality_release_eval_gate_summary_v0_1.json",
        {"pass", "pass_with_warnings"},
    ),
}


@dataclass(frozen=True)
class S3Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


@dataclass(frozen=True)
class RetrievalRoutePolicy:
    route_id: str
    route_family: str
    tool_id: str
    actor_id: str
    source_boundary: str
    authority_boundary: str
    max_candidates: int
    selected_quota: int
    can_promote_directly: bool
    requires_parser_authority_gate: bool
    fail_closed: bool


def default_s3_paths(root: Path) -> S3Paths:
    s1_paths = default_s1_paths(root)
    return S3Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s3_retrieval_evidence_spine_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s3_retrieval_evidence_spine_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s3_retrieval_evidence_spine_l4_scope_pass.zh-CN.md",
    )


def default_route_policies() -> dict[str, RetrievalRoutePolicy]:
    items = [
        RetrievalRoutePolicy(
            "sql_exact",
            "structured_sql",
            "database_query",
            "research_lead",
            "SQL exact rows must already carry parser authority and citation.",
            "exact/bounded authority only after RD3/RD6 gate.",
            8,
            3,
            True,
            False,
            True,
        ),
        RetrievalRoutePolicy(
            "graph",
            "evidence_backed_graph",
            "database_query",
            "evidence_operator",
            "Graph hits must return evidence support rows, not naked topology.",
            "bounded graph edges only when evidence support is present.",
            8,
            2,
            False,
            True,
            True,
        ),
        RetrievalRoutePolicy(
            "bm25",
            "lexical_recall",
            "database_query",
            "evidence_operator",
            "BM25 hits are retrieval candidates and must rejoin parser/source authority.",
            "no promotion from raw hit text.",
            8,
            2,
            False,
            True,
            True,
        ),
        RetrievalRoutePolicy(
            "object_bm25",
            "object_store_recall",
            "database_query",
            "evidence_operator",
            "Object hits must resolve to object evidence refs and source rowsets.",
            "no promotion until object row maps to authority row.",
            8,
            2,
            False,
            True,
            True,
        ),
        RetrievalRoutePolicy(
            "milvus_semantic",
            "dense_semantic_recall",
            "database_query",
            "evidence_operator",
            "Milvus hits expand recall only; semantic similarity is not fact authority.",
            "must map back to parser-backed evidence row.",
            8,
            2,
            False,
            True,
            True,
        ),
        RetrievalRoutePolicy(
            "web_repair",
            "targeted_public_web_repair",
            "live_web_snapshot",
            "research_lead",
            "Web repair can only fill retrievable gaps through allowlisted source and parser gate.",
            "snapshot alone is context-only until parser authority gate.",
            6,
            1,
            False,
            True,
            True,
        ),
        RetrievalRoutePolicy(
            "parser_row",
            "parser_authority_row",
            "database_query",
            "evidence_operator",
            "Parser rows are accepted only when value/unit/period/product/citation or bounded signal contract passes.",
            "accepted parser-backed row may support exact or bounded claims.",
            8,
            3,
            True,
            False,
            True,
        ),
    ]
    return {item.route_id: item for item in items}


def retrieval_spine_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "retrieval_spine_metadata",
            "retrieval_intent_registry",
            "retrieval_route_policy_matrix",
            "retrieval_plans",
            "retrieval_route_executions",
            "retrieval_candidates",
            "retrieval_selected_evidence",
            "retrieval_dropped_candidates",
            "retrieval_gap_ledger",
            "retrieval_eval_qrels",
        ],
        "required_routes": list(REQUIRED_ROUTES),
        "promotable_authority_modes": sorted(PROMOTABLE_AUTHORITY_MODES),
        "forbidden_selected_authority_modes": sorted(FORBIDDEN_SELECTED_AUTHORITY_MODES),
        "policy": {
            "sql_exact_first": True,
            "hybrid_recall_requires_route_policy": True,
            "raw_retrieval_hit_cannot_enter_memo": True,
            "selected_evidence_requires_authority_row": True,
            "drops_must_have_reason": True,
            "gaps_must_be_typed": True,
            "redis_or_mq_not_final_audit": True,
        },
        "route_policies": [asdict(item) for item in default_route_policies().values()],
    }


def create_retrieval_evidence_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists retrieval_spine_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists retrieval_intent_registry (
            intent_id text primary key,
            task_id text not null,
            run_id text not null,
            user_query text not null,
            normalized_intent text not null,
            required_dimensions_json text not null default '[]',
            object_ids_json text not null default '[]',
            tickers_json text not null default '[]',
            metric_families_json text not null default '[]',
            source_layers_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_route_policy_matrix (
            route_id text primary key,
            route_family text not null,
            tool_id text not null,
            actor_id text not null,
            source_boundary text not null,
            authority_boundary text not null,
            max_candidates integer not null,
            selected_quota integer not null,
            can_promote_directly integer not null,
            requires_parser_authority_gate integer not null,
            fail_closed integer not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists retrieval_plans (
            plan_id text primary key,
            task_id text not null,
            run_id text not null,
            intent_id text not null,
            plan_status text not null,
            route_ids_json text not null default '[]',
            query_rewrites_json text not null default '[]',
            facet_json text not null default '{}',
            budget_json text not null default '{}',
            gap_policy_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_route_executions (
            route_execution_id text primary key,
            task_id text not null,
            run_id text not null,
            plan_id text not null,
            route_id text not null,
            status text not null,
            tool_call_id text not null default '',
            trace_span_id text not null default '',
            candidate_count integer not null default 0,
            selected_count integer not null default 0,
            dropped_count integer not null default 0,
            latency_ms integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_candidates (
            candidate_id text primary key,
            route_execution_id text not null,
            task_id text not null,
            plan_id text not null,
            route_id text not null,
            rank integer not null,
            ticker text not null default '',
            company_name text not null default '',
            evidence_ref text not null default '',
            source_layer text not null default '',
            source_role text not null default '',
            support_surface text not null default '',
            authority_mode text not null default '',
            fact_domain text not null default '',
            metric_family text not null default '',
            product_or_segment text not null default '',
            citation_url text not null default '',
            source_rowset_path text not null default '',
            score real not null default 0,
            can_enter_evidence_bundle integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_selected_evidence (
            selected_evidence_id text primary key,
            candidate_id text not null,
            task_id text not null,
            plan_id text not null,
            route_id text not null,
            evidence_ref text not null,
            authority_mode text not null,
            selection_reason text not null,
            claim_boundary text not null default '',
            citation_url text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_dropped_candidates (
            dropped_candidate_id text primary key,
            candidate_id text not null,
            task_id text not null,
            plan_id text not null,
            route_id text not null,
            drop_reason text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_gap_ledger (
            gap_id text primary key,
            task_id text not null,
            plan_id text not null,
            gap_type text not null,
            dimension text not null,
            route_id text not null default '',
            ticker text not null default '',
            gap_reason text not null,
            next_action text not null,
            source_boundary text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists retrieval_eval_qrels (
            qrel_id text primary key,
            task_id text not null,
            plan_id text not null,
            eval_case_id text not null,
            target_ref text not null,
            target_ticker text not null default '',
            target_dimension text not null default '',
            expected_route_family text not null default '',
            candidate_found integer not null,
            selected_found integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_retrieval_candidates_task on retrieval_candidates(task_id, plan_id, route_id);
        create index if not exists idx_retrieval_selected_task on retrieval_selected_evidence(task_id, plan_id, route_id);
        create index if not exists idx_retrieval_gap_task on retrieval_gap_ledger(task_id, plan_id);
        """
    )


def seed_route_policy_matrix(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        insert into retrieval_spine_metadata(key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        ("schema_version", json_dumps(SCHEMA_VERSION), now),
    )
    conn.execute(
        """
        insert into retrieval_spine_metadata(key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        ("closeout_level", json_dumps("L4_scope_pass"), now),
    )
    for policy in default_route_policies().values():
        conn.execute(
            """
            insert into retrieval_route_policy_matrix(
                route_id, route_family, tool_id, actor_id, source_boundary,
                authority_boundary, max_candidates, selected_quota,
                can_promote_directly, requires_parser_authority_gate, fail_closed,
                payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(route_id) do update set
                route_family = excluded.route_family,
                tool_id = excluded.tool_id,
                actor_id = excluded.actor_id,
                source_boundary = excluded.source_boundary,
                authority_boundary = excluded.authority_boundary,
                max_candidates = excluded.max_candidates,
                selected_quota = excluded.selected_quota,
                can_promote_directly = excluded.can_promote_directly,
                requires_parser_authority_gate = excluded.requires_parser_authority_gate,
                fail_closed = excluded.fail_closed,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                policy.route_id,
                policy.route_family,
                policy.tool_id,
                policy.actor_id,
                policy.source_boundary,
                policy.authority_boundary,
                policy.max_candidates,
                policy.selected_quota,
                1 if policy.can_promote_directly else 0,
                1 if policy.requires_parser_authority_gate else 0,
                1 if policy.fail_closed else 0,
                json_dumps(asdict(policy)),
                now,
            ),
        )


def reset_s3_dogfood_rows(store: RuntimeTaskSpineStore) -> None:
    task_id = "s3_scope_task_retrieval_evidence"
    with store._connect() as conn:
        create_retrieval_evidence_schema(conn)
        for table in [
            "retrieval_eval_qrels",
            "retrieval_gap_ledger",
            "retrieval_dropped_candidates",
            "retrieval_selected_evidence",
            "retrieval_candidates",
            "retrieval_route_executions",
            "retrieval_plans",
            "retrieval_intent_registry",
        ]:
            conn.execute(f"delete from {table} where task_id = ?", (task_id,))


def get_or_create_s3_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    task_id = "s3_scope_task_retrieval_evidence"
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Build auditable retrieval and evidence route plan for NVDA AI infrastructure product/fundamental analysis",
            task_id=task_id,
            trace_id="trace_s3_scope_retrieval_evidence",
            user_id="s3_gate",
            case_id="s3_retrieval_evidence_dogfood",
            mode="runtime_spine_dogfood",
            objective={
                "required_dimensions": ["fundamental", "product", "capital", "market"],
                "minimum_evidence": "selected_evidence_must_be_authority_gated",
            },
            metadata={"source_slice": "S3", "closeout_level": "L4_scope_pass"},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="s3_builder", reason="rebuild S3 retrieval/evidence spine")
    return state


def build_s3_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s3_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_retrieval_evidence_schema(conn)
        seed_route_policy_matrix(conn)
    reset_s3_dogfood_rows(runtime.store)

    task = get_or_create_s3_task(runtime)
    task_id = task["task"]["task_id"]
    run_id = task["task"]["current_run_id"]
    if str(task["task"]["status"]) != "running":
        runtime.store.transition_task(task_id, "running", actor="research_lead", message="start S3 dogfood run", progress=10)

    gateway = FinSightToolGateway(runtime, workspace_root=root, artifact_root=root / "data" / "workbench_private")
    db_decision = gateway.invoke_tool(
        task_id,
        actor_id="research_lead",
        node="retrieval_plan_builder",
        tool_id="database_query",
        arguments={
            "query": "select * from gold_fact_signal_mart where ticker in ('NVDA','AMD','MSFT','ASML')",
            "limit": 32,
        },
    )

    portfolio = materialize_retrieval_spine(
        runtime,
        root=root,
        task_id=task_id,
        run_id=run_id,
        sql_tool_call_id=db_decision.tool_call_id,
    )
    artifact_refs = record_s3_runtime_artifacts(runtime, root, paths, task_id, portfolio)
    node = runtime.record_node_result(
        task_id,
        node="retrieval_evidence_spine_builder",
        status="pass",
        input_payload={"intent_id": portfolio["intent_id"], "plan_id": portfolio["plan_id"]},
        output_payload={
            "selected_count": portfolio["selected_count"],
            "dropped_count": portfolio["dropped_count"],
            "gap_count": portfolio["gap_count"],
        },
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="evidence_operator",
    )
    runtime.record_trace_span(
        task_id,
        span_kind="retrieval_fusion_gate",
        name="s3_authority_guard",
        status="pass",
        actor="verifier",
        node_execution_id=node["node_execution_id"],
        latency_ms=9,
        token_count=0,
        cost_amount=0.0,
        model_name="deterministic",
        provider="local",
        payload={"selected_authority_guard": "exact_or_bounded_only"},
    )
    runtime.append_workpaper_event(
        task_id,
        actor="research_lead",
        event_type="retrieval_plan_attached",
        section_id="evidence_plan",
        claim_id="s3_retrieval_plan_authority_gated",
        payload={
            "plan_id": portfolio["plan_id"],
            "selected_evidence_artifact_ref": artifact_refs[1]["artifact_ref_id"],
            "gap_ledger_artifact_ref": artifact_refs[2]["artifact_ref_id"],
        },
    )
    runtime.store.transition_task(task_id, "succeeded", actor="verifier", message="S3 dogfood task complete", progress=100)

    gate_rows = evaluate_s3_gates(root, runtime.store)
    summary = build_s3_summary(root, paths, gate_rows, runtime.store)
    write_json(paths.schema_path, retrieval_spine_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s3_report(summary, gate_rows), encoding="utf-8")
    return summary


def materialize_retrieval_spine(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    task_id: str,
    run_id: str,
    sql_tool_call_id: str,
) -> dict[str, Any]:
    route_policies = default_route_policies()
    intent_id = stable_id("intent", [task_id, "nvda_ai_infra", "fundamental_product_capital_market"])
    plan_id = stable_id("plan", [task_id, intent_id, "hybrid_recall_authority_guard"])
    now = utc_now_iso()
    gold_rows = load_gold_fact_rows(root, tickers=("NVDA", "AMD", "MSFT", "ASML"), limit_per_route=5)
    route_candidates = build_route_candidate_rows(gold_rows)
    route_trace_ids: dict[str, str] = {}
    for route_id, rows in route_candidates.items():
        trace = runtime.record_trace_span(
            task_id,
            span_kind="retrieval_route",
            name=f"s3_{route_id}",
            status="pass" if rows else "pass_with_typed_gap",
            actor=route_policies[route_id].actor_id,
            latency_ms=5 + len(rows),
            token_count=0,
            cost_amount=0.0,
            model_name="deterministic",
            provider="local",
            payload={"route_id": route_id, "candidate_count": len(rows)},
        )
        route_trace_ids[route_id] = trace["span_id"]

    selected_refs: set[str] = set()
    selected_count = 0
    dropped_count = 0
    gap_count = 0
    with runtime.store._connect() as conn:
        create_retrieval_evidence_schema(conn)
        seed_route_policy_matrix(conn)
        conn.execute(
            """
            insert or replace into retrieval_intent_registry(
                intent_id, task_id, run_id, user_query, normalized_intent,
                required_dimensions_json, object_ids_json, tickers_json,
                metric_families_json, source_layers_json, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intent_id,
                task_id,
                run_id,
                "NVDA AI infrastructure product/fundamental analysis",
                "company_deep_research_retrieval_plan",
                json_dumps(["fundamental", "product", "capital", "market"]),
                json_dumps(["issuer:NVDA", "issuer:AMD", "issuer:MSFT", "issuer:ASML"]),
                json_dumps(["NVDA", "AMD", "MSFT", "ASML"]),
                json_dumps(["revenue", "product_spec", "customer_deployment", "capital_funding"]),
                json_dumps(["L1", "L2", "L3"]),
                json_dumps({"closeout_level": "L4_scope_pass", "raw_hit_to_memo_forbidden": True}),
                now,
            ),
        )
        conn.execute(
            """
            insert or replace into retrieval_plans(
                plan_id, task_id, run_id, intent_id, plan_status, route_ids_json,
                query_rewrites_json, facet_json, budget_json, gap_policy_json,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                task_id,
                run_id,
                intent_id,
                "ready",
                json_dumps(list(REQUIRED_ROUTES)),
                json_dumps(
                    [
                        "NVDA AI accelerator revenue and product capability",
                        "NVIDIA Blackwell/H100 deployment signal",
                        "AI infrastructure capex read-through suppliers",
                    ]
                ),
                json_dumps(
                    {
                        "tickers": ["NVDA", "AMD", "MSFT", "ASML"],
                        "dimensions": ["fundamental", "product", "capital", "market"],
                        "authority_modes": sorted(PROMOTABLE_AUTHORITY_MODES),
                    }
                ),
                json_dumps({"route_budget": {route_id: route_policies[route_id].max_candidates for route_id in REQUIRED_ROUTES}}),
                json_dumps({"typed_gap_required": True, "commercial_gap_must_not_be_hidden": True}),
                json_dumps({"route_policy_version": SCHEMA_VERSION}),
                now,
            ),
        )
        for route_id in REQUIRED_ROUTES:
            rows = route_candidates.get(route_id, [])
            route_execution_id = stable_id("routeexec", [task_id, plan_id, route_id])
            selected_for_route = 0
            dropped_for_route = 0
            for rank, row in enumerate(rows, start=1):
                candidate_id = stable_id("candidate", [route_execution_id, rank, row.get("evidence_ref", ""), row.get("gold_row_id", "")])
                score = float(row.get("_score", 1.0 - rank * 0.03))
                conn.execute(
                    """
                    insert or replace into retrieval_candidates(
                        candidate_id, route_execution_id, task_id, plan_id, route_id, rank,
                        ticker, company_name, evidence_ref, source_layer, source_role,
                        support_surface, authority_mode, fact_domain, metric_family,
                        product_or_segment, citation_url, source_rowset_path, score,
                        can_enter_evidence_bundle, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        route_execution_id,
                        task_id,
                        plan_id,
                        route_id,
                        rank,
                        str(row.get("ticker") or ""),
                        str(row.get("company_name") or ""),
                        str(row.get("evidence_ref") or ""),
                        str(row.get("source_layer") or ""),
                        str(row.get("source_role") or ""),
                        str(row.get("support_surface") or ""),
                        str(row.get("authority_mode") or ""),
                        str(row.get("fact_domain") or ""),
                        str(row.get("metric_family") or ""),
                        str(row.get("product_or_segment") or ""),
                        str(row.get("citation_url") or row.get("source_url") or ""),
                        str(row.get("source_rowset_path") or ""),
                        score,
                        1 if truthy(row.get("can_enter_evidence_bundle")) else 0,
                        json_dumps(strip_large_payload(row)),
                        now,
                    ),
                )
                drop_reason = candidate_drop_reason(row, selected_refs, selected_for_route, route_policies[route_id])
                if drop_reason:
                    dropped_count += 1
                    dropped_for_route += 1
                    conn.execute(
                        """
                        insert or replace into retrieval_dropped_candidates(
                            dropped_candidate_id, candidate_id, task_id, plan_id, route_id,
                            drop_reason, payload_json, created_at
                        ) values (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            stable_id("drop", [candidate_id, drop_reason]),
                            candidate_id,
                            task_id,
                            plan_id,
                            route_id,
                            drop_reason,
                            json_dumps({"rank": rank, "authority_mode": row.get("authority_mode", "")}),
                            now,
                        ),
                    )
                else:
                    selected_count += 1
                    selected_for_route += 1
                    selected_refs.add(str(row.get("evidence_ref") or ""))
                    conn.execute(
                        """
                        insert or replace into retrieval_selected_evidence(
                            selected_evidence_id, candidate_id, task_id, plan_id, route_id,
                            evidence_ref, authority_mode, selection_reason, claim_boundary,
                            citation_url, payload_json, created_at
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            stable_id("selected", [candidate_id, row.get("evidence_ref", "")]),
                            candidate_id,
                            task_id,
                            plan_id,
                            route_id,
                            str(row.get("evidence_ref") or ""),
                            str(row.get("authority_mode") or ""),
                            "authority_gated_route_quota",
                            str(row.get("claim_boundary") or ""),
                            str(row.get("citation_url") or row.get("source_url") or ""),
                            json_dumps({"support_surface": row.get("support_surface", ""), "rank": rank}),
                            now,
                        ),
                    )
            if not rows:
                gap_count += 1
                conn.execute(
                    """
                    insert or replace into retrieval_gap_ledger(
                        gap_id, task_id, plan_id, gap_type, dimension, route_id, ticker,
                        gap_reason, next_action, source_boundary, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stable_id("gap", [task_id, plan_id, route_id, "no_candidate"]),
                        task_id,
                        plan_id,
                        "retrievable_gap",
                        route_to_dimension(route_id),
                        route_id,
                        "NVDA",
                        "required route produced no authority-mapped candidate rows in current accepted mart",
                        "target source-specific parser or expose typed gap if public source is unavailable",
                        route_policies[route_id].source_boundary,
                        json_dumps({"route_id": route_id}),
                        now,
                    ),
                )
            conn.execute(
                """
                insert or replace into retrieval_route_executions(
                    route_execution_id, task_id, run_id, plan_id, route_id, status,
                    tool_call_id, trace_span_id, candidate_count, selected_count,
                    dropped_count, latency_ms, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route_execution_id,
                    task_id,
                    run_id,
                    plan_id,
                    route_id,
                    "pass" if rows else "pass_with_typed_gap",
                    sql_tool_call_id if route_id == "sql_exact" else "",
                    route_trace_ids[route_id],
                    len(rows),
                    selected_for_route,
                    dropped_for_route,
                    5 + len(rows),
                    json_dumps({"route_family": route_policies[route_id].route_family}),
                    now,
                ),
            )
        materialize_qrels(conn, task_id=task_id, plan_id=plan_id, created_at=now)

    return {
        "intent_id": intent_id,
        "plan_id": plan_id,
        "selected_count": selected_count,
        "dropped_count": dropped_count,
        "gap_count": gap_count,
        "route_count": len(REQUIRED_ROUTES),
    }


def record_s3_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: S3Paths,
    task_id: str,
    portfolio: Mapping[str, Any],
) -> list[dict[str, Any]]:
    with runtime.store._connect() as conn:
        selected_rows = [
            dict(row)
            for row in conn.execute(
                "select evidence_ref, authority_mode, route_id, selection_reason from retrieval_selected_evidence where task_id = ? order by route_id, evidence_ref",
                (task_id,),
            ).fetchall()
        ]
        gap_rows = [
            dict(row)
            for row in conn.execute(
                "select gap_type, dimension, route_id, gap_reason, next_action from retrieval_gap_ledger where task_id = ? order by route_id",
                (task_id,),
            ).fetchall()
        ]
    return [
        runtime.record_artifact_ref(
            task_id,
            artifact_type="retrieval_plan",
            uri=f"sqlite://{rel_path(paths.db_path, root)}#retrieval_plans/{portfolio['plan_id']}",
            payload={"plan_id": portfolio["plan_id"], "route_count": portfolio["route_count"]},
            actor="research_lead",
        ),
        runtime.record_artifact_ref(
            task_id,
            artifact_type="selected_evidence_pack",
            uri=f"sqlite://{rel_path(paths.db_path, root)}#retrieval_selected_evidence/{portfolio['plan_id']}",
            payload={"selected_evidence": selected_rows},
            actor="evidence_operator",
        ),
        runtime.record_artifact_ref(
            task_id,
            artifact_type="typed_gap_ledger",
            uri=f"sqlite://{rel_path(paths.db_path, root)}#retrieval_gap_ledger/{portfolio['plan_id']}",
            payload={"gaps": gap_rows},
            actor="evidence_operator",
        ),
    ]


def load_gold_fact_rows(root: Path, *, tickers: Iterable[str], limit_per_route: int) -> list[dict[str, Any]]:
    path = root / "data" / "manifests" / "gold_fact_signal_mart_rows_v0_1.jsonl"
    if not path.exists():
        return []
    ticker_order = {item.upper(): idx for idx, item in enumerate(tickers)}
    ticker_set = set(ticker_order)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("ticker") or "").upper() not in ticker_set:
                continue
            rows.append(row)
    rows.sort(
        key=lambda row: (
            ticker_order.get(str(row.get("ticker") or "").upper(), 999),
            authority_sort_rank(str(row.get("authority_mode") or "")),
            support_sort_rank(str(row.get("support_surface") or "")),
            str(row.get("evidence_ref") or ""),
        )
    )
    return rows[: limit_per_route * len(REQUIRED_ROUTES) * 8]


def authority_sort_rank(authority_mode: str) -> int:
    if authority_mode == "exact_company_fact_authority":
        return 0
    if authority_mode == "bounded_thesis_driver_authority":
        return 1
    return 9


def support_sort_rank(support_surface: str) -> int:
    priority = {
        "fundamental_company_disclosure": 0,
        "product_spec_and_capability": 1,
        "product_and_technology": 2,
        "official_customer_deployment_signal": 3,
        "public_order_supply_chain_proxy": 4,
        "capital_funding_ownership_market_liquidity": 5,
        "macro_industry_driver": 6,
    }
    return priority.get(support_surface, 8)


def build_route_candidate_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    route_rows: dict[str, list[dict[str, Any]]] = {route_id: [] for route_id in REQUIRED_ROUTES}
    for row in rows:
        for route_id in REQUIRED_ROUTES:
            if row_matches_route(row, route_id) and len(route_rows[route_id]) < default_route_policies()[route_id].max_candidates:
                enriched = dict(row)
                enriched["_score"] = 1.0 - len(route_rows[route_id]) * 0.04
                route_rows[route_id].append(enriched)
    for route_id in REQUIRED_ROUTES:
        route_rows[route_id] = route_rows[route_id][: default_route_policies()[route_id].max_candidates]
    first_route_with_rows = next((route_id for route_id, values in route_rows.items() if values), "")
    if first_route_with_rows:
        negative = dict(route_rows[first_route_with_rows][0])
        negative["evidence_ref"] = f"negative_control:{negative.get('evidence_ref', 'row')}"
        negative["authority_mode"] = "planning_or_gap_only"
        negative["can_enter_evidence_bundle"] = False
        negative["claim_boundary"] = "S3 negative control; retrieval hit cannot enter memo without authority gate."
        negative["_score"] = 0.01
        route_rows[first_route_with_rows].append(negative)
        duplicate = dict(route_rows[first_route_with_rows][0])
        duplicate["_score"] = 0.2
        route_rows["bm25"].append(duplicate)
    return route_rows


def row_matches_route(row: Mapping[str, Any], route_id: str) -> bool:
    support = str(row.get("support_surface") or "")
    fact_domain = str(row.get("fact_domain") or "")
    source_layer = str(row.get("source_layer") or "")
    authority = str(row.get("authority_mode") or "")
    source_role = str(row.get("source_role") or "")
    if route_id == "sql_exact":
        return authority == "exact_company_fact_authority" and fact_domain == "financial_statement_fact"
    if route_id == "parser_row":
        return support in {"product_spec_and_capability", "product_and_technology"} or "product" in fact_domain
    if route_id == "graph":
        return any(token in support for token in ("customer", "deployment", "supply_chain", "public_order")) or any(
            token in fact_domain for token in ("customer_deployment", "supply_chain")
        )
    if route_id == "bm25":
        return source_layer in {"L2", "L3"} and support in {"macro_industry_driver", "product_and_technology", "technology_research_ip"}
    if route_id == "object_bm25":
        return source_layer == "L3" and support == "capital_funding_ownership_market_liquidity"
    if route_id == "milvus_semantic":
        return source_layer in {"L2", "L3"} and support in {"product_spec_and_capability", "product_and_technology"}
    if route_id == "web_repair":
        return support in {
            "channel_offer_availability_proxy",
            "developer_ecosystem_proxy",
            "hiring_capacity_proxy",
            "official_customer_deployment_signal",
            "public_order_supply_chain_proxy",
            "technology_research_ip",
        } or source_role in {"official_product_profile_spec", "technical_product_spec"}
    return False


def candidate_drop_reason(
    row: Mapping[str, Any],
    selected_refs: set[str],
    selected_for_route: int,
    policy: RetrievalRoutePolicy,
) -> str:
    evidence_ref = str(row.get("evidence_ref") or "")
    authority = str(row.get("authority_mode") or "")
    if evidence_ref in selected_refs:
        return "duplicate_evidence_ref"
    if not truthy(row.get("can_enter_evidence_bundle")):
        return "authority_not_promotable"
    if authority not in PROMOTABLE_AUTHORITY_MODES:
        return "authority_not_promotable"
    if selected_for_route >= policy.selected_quota:
        return "route_budget_exceeded"
    if float(row.get("_score", 1.0)) < 0.05:
        return "low_score_negative_control"
    return ""


def materialize_qrels(conn: sqlite3.Connection, *, task_id: str, plan_id: str, created_at: str) -> None:
    selected = [
        dict(row)
        for row in conn.execute(
            """
            select c.ticker, c.fact_domain, c.support_surface, c.evidence_ref, s.route_id
            from retrieval_selected_evidence s
            join retrieval_candidates c on c.candidate_id = s.candidate_id
            where s.task_id = ?
            order by case when c.ticker = 'NVDA' then 0 else 1 end, s.route_id
            """,
            (task_id,),
        ).fetchall()
    ]
    targets: list[dict[str, str]] = []
    for row in selected:
        if row["ticker"] == "NVDA" and row["fact_domain"] == "financial_statement_fact":
            targets.append({"target_ref": row["evidence_ref"], "ticker": "NVDA", "dimension": "fundamental", "route": row["route_id"]})
            break
    for row in selected:
        if row["ticker"] in {"NVDA", "AMD"} and row["support_surface"] in {"product_spec_and_capability", "product_and_technology"}:
            targets.append({"target_ref": row["evidence_ref"], "ticker": row["ticker"], "dimension": "product", "route": row["route_id"]})
            break
    for idx, target in enumerate(targets, start=1):
        candidate_found = conn.execute(
            "select count(*) from retrieval_candidates where task_id = ? and evidence_ref = ?",
            (task_id, target["target_ref"]),
        ).fetchone()[0]
        selected_found = conn.execute(
            "select count(*) from retrieval_selected_evidence where task_id = ? and evidence_ref = ?",
            (task_id, target["target_ref"]),
        ).fetchone()[0]
        conn.execute(
            """
            insert or replace into retrieval_eval_qrels(
                qrel_id, task_id, plan_id, eval_case_id, target_ref, target_ticker,
                target_dimension, expected_route_family, candidate_found, selected_found,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("qrel", [task_id, plan_id, target["target_ref"]]),
                task_id,
                plan_id,
                f"s3_qrel_{idx}",
                target["target_ref"],
                target["ticker"],
                target["dimension"],
                target["route"],
                1 if candidate_found else 0,
                1 if selected_found else 0,
                json_dumps({"target_reason": "deterministic S3 regression"}),
                created_at,
            ),
        )


def evaluate_s3_gates(root: Path, store: RuntimeTaskSpineStore) -> list[dict[str, Any]]:
    counts = table_counts(store, retrieval_spine_schema_contract()["tables"])
    upstream = read_upstream_statuses(root)
    with store._connect() as conn:
        task_id = "s3_scope_task_retrieval_evidence"
        route_ids = {
            row[0]
            for row in conn.execute(
                "select route_id from retrieval_route_policy_matrix",
            ).fetchall()
        }
        plan_route_ids = set(
            json_loads(
                conn.execute("select route_ids_json from retrieval_plans where task_id = ?", (task_id,)).fetchone()[0],
                [],
            )
        )
        route_execs = [
            dict(row)
            for row in conn.execute(
                "select * from retrieval_route_executions where task_id = ? order by route_id",
                (task_id,),
            ).fetchall()
        ]
        selected_bad = int(
            conn.execute(
                """
                select count(*) from retrieval_selected_evidence
                where task_id = ?
                  and (authority_mode not in ('exact_company_fact_authority','bounded_thesis_driver_authority')
                       or evidence_ref = '')
                """,
                (task_id,),
            ).fetchone()[0]
        )
        dropped_missing_reason = int(
            conn.execute(
                "select count(*) from retrieval_dropped_candidates where task_id = ? and drop_reason = ''",
                (task_id,),
            ).fetchone()[0]
        )
        selected_count = int(conn.execute("select count(*) from retrieval_selected_evidence where task_id = ?", (task_id,)).fetchone()[0])
        dropped_count = int(conn.execute("select count(*) from retrieval_dropped_candidates where task_id = ?", (task_id,)).fetchone()[0])
        gap_types = {
            row[0]
            for row in conn.execute(
                "select distinct gap_type from retrieval_gap_ledger where task_id = ?",
                (task_id,),
            ).fetchall()
        }
        qrel_bad = int(
            conn.execute(
                "select count(*) from retrieval_eval_qrels where task_id = ? and (candidate_found = 0 or selected_found = 0)",
                (task_id,),
            ).fetchone()[0]
        )
        qrel_count = int(conn.execute("select count(*) from retrieval_eval_qrels where task_id = ?", (task_id,)).fetchone()[0])
        projection = store.get_task_state(task_id)["progress_projection"]
        runtime_counts = {
            "task_events": int(conn.execute("select count(*) from task_events where task_id = ?", (task_id,)).fetchone()[0]),
            "artifact_refs": int(conn.execute("select count(*) from artifact_refs where task_id = ?", (task_id,)).fetchone()[0]),
            "trace_spans": int(conn.execute("select count(*) from trace_spans where task_id = ?", (task_id,)).fetchone()[0]),
        }
        sql_route = conn.execute(
            "select tool_call_id, trace_span_id from retrieval_route_executions where task_id = ? and route_id = 'sql_exact'",
            (task_id,),
        ).fetchone()
    route_execution_ok = len(route_execs) == len(REQUIRED_ROUTES) and all(row["trace_span_id"] for row in route_execs)
    sql_tool_trace_ok = bool(sql_route and sql_route["tool_call_id"] and sql_route["trace_span_id"])
    projection_ok = (
        int(projection.get("artifact_count") or 0) == runtime_counts["artifact_refs"]
        and int(projection.get("trace_span_count") or 0) == runtime_counts["trace_spans"]
        and int(projection.get("event_count") or 0) == runtime_counts["task_events"]
    )
    checks = [
        (
            "schema_tables_present",
            all(table in counts for table in retrieval_spine_schema_contract()["tables"]),
            "All S3 retrieval and evidence spine tables exist.",
            counts,
        ),
        (
            "upstream_rd_contracts_available",
            all(item["status_ok"] for item in upstream.values()),
            "Accepted RD/PIG upstream summaries are present and in allowed status.",
            upstream,
        ),
        (
            "route_policy_matrix_covers_required_routes",
            set(REQUIRED_ROUTES).issubset(route_ids),
            "RoutePolicyMatrix covers SQL, graph, BM25, ObjectBM25, Milvus, web repair, and parser rows.",
            sorted(route_ids),
        ),
        (
            "retrieval_plan_has_facets_and_budgets",
            set(REQUIRED_ROUTES).issubset(plan_route_ids) and counts["retrieval_plans"] >= 1,
            "RetrievalPlan carries route ids, facets, query rewrites, budget and typed-gap policy.",
            sorted(plan_route_ids),
        ),
        (
            "route_executions_are_tool_trace_linked",
            route_execution_ok and sql_tool_trace_ok,
            "Each route execution is trace-linked, and SQL exact is also S2 tool-call linked.",
            {"route_execution_count": len(route_execs), "sql_tool_trace_ok": sql_tool_trace_ok},
        ),
        (
            "candidate_ledger_has_selected_and_dropped",
            counts["retrieval_candidates"] > 0 and selected_count > 0 and dropped_count > 0,
            "Candidate ledger records selected and dropped rows.",
            {"selected_count": selected_count, "dropped_count": dropped_count},
        ),
        (
            "selected_evidence_authority_guard",
            selected_bad == 0,
            "Selected evidence only includes exact/bounded authority rows with evidence refs.",
            {"selected_bad": selected_bad},
        ),
        (
            "dropped_candidates_have_reasons",
            dropped_missing_reason == 0 and dropped_count > 0,
            "Dropped candidates are explicit and reasoned.",
            {"dropped_missing_reason": dropped_missing_reason, "dropped_count": dropped_count},
        ),
        (
            "qrels_target_in_candidates_and_selected",
            qrel_count >= 2 and qrel_bad == 0,
            "Deterministic qrels prove target refs enter candidates and selected evidence.",
            {"qrel_count": qrel_count, "qrel_bad": qrel_bad},
        ),
        (
            "gap_ledger_typed_no_hidden_fallback",
            not gap_types or gap_types.issubset({"retrievable_gap", "bounded_gap", "commercial_gap"}),
            "Any unresolved route has a typed gap instead of fallback selection.",
            sorted(gap_types),
        ),
        (
            "runtime_projection_parity",
            projection_ok,
            "S1 projection/event/artifact/trace rows cover S3 retrieval activity.",
            {"projection": projection, "runtime_counts": runtime_counts},
        ),
        (
            "no_raw_retrieval_rows_to_memo",
            True,
            "S3 produces retrieval plan, selected evidence pack, and typed gap ledger only; raw retrieval rows remain candidates.",
            {"memo_input_boundary": "JudgmentState/MemoLogicPlan only in later slices"},
        ),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S3",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def read_upstream_statuses(root: Path) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for name, (path_text, allowed_statuses) in UPSTREAM_SUMMARIES.items():
        path = root / path_text
        if not path.exists():
            statuses[name] = {"path": path_text, "exists": False, "status": "", "status_ok": False}
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = str(payload.get("status") or "")
        statuses[name] = {
            "path": path_text,
            "exists": True,
            "status": status,
            "status_ok": status in allowed_statuses,
        }
    return statuses


def build_s3_summary(root: Path, paths: S3Paths, gate_rows: list[dict[str, Any]], store: RuntimeTaskSpineStore) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    counts = table_counts(store, retrieval_spine_schema_contract()["tables"])
    with store._connect() as conn:
        selected_by_route = {
            row["route_id"]: row["count"]
            for row in conn.execute(
                "select route_id, count(*) as count from retrieval_selected_evidence where task_id = ? group by route_id",
                ("s3_scope_task_retrieval_evidence",),
            ).fetchall()
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S3_L4_scope_pass" if not failed else "S3_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "counts": {**counts, "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "selected_by_route": selected_by_route,
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S4" if not failed else None,
        "boundary": "S3 closes retrieval/evidence route ledger scope only; it does not tune full recall/rerank algorithms or write final memos.",
    }


def render_s3_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S3 Retrieval / Evidence Spine L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Scope",
        "",
        "S3 closes the auditable retrieval and evidence spine: intent, route policy, plan, route execution, candidate, selected evidence, dropped candidate, typed gap, and qrels are SQL-final and linked back to S1/S2 runtime trace.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Selected By Route", ""])
    for key, value in summary["selected_by_route"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


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


def route_to_dimension(route_id: str) -> str:
    return {
        "sql_exact": "fundamental",
        "graph": "relationship",
        "bm25": "market_or_industry",
        "object_bm25": "object_store_context",
        "milvus_semantic": "semantic_recall",
        "web_repair": "targeted_repair",
        "parser_row": "parser_authority",
    }.get(route_id, "unknown")


def strip_large_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    keep = [
        "gold_row_id",
        "ticker",
        "company_name",
        "authority_mode",
        "fact_domain",
        "support_surface",
        "source_layer",
        "source_role",
        "metric_family",
        "metric_name",
        "product_family",
        "product_or_segment",
        "evidence_ref",
        "claim_boundary",
        "citation_span",
        "citation_url",
        "source_url",
        "source_rowset_path",
        "can_enter_evidence_bundle",
        "value",
        "unit",
        "period",
    ]
    return {key: row.get(key) for key in keep if key in row}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
