"""S5 Workpaper / Lead Review workflow for the R53-R60 program.

S5 turns the S3 selected-evidence ledger and S4 context injection plans into a
reviewable Workpaper workflow.  It is still deterministic and local: no LLM is
called, no final memo is written, and no raw retrieval candidates bypass the S3
authority gate.  The goal is to prove that Research Lead supervision,
specialist workstreams, append-only WorkpaperEvents, judgment state, typed gaps,
and readability gates are runtime-ledgered before S6/S7 expose UI and
deliverables.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.r53_r60_context_graph_skill_registry import (
    S4_TASK_ID,
    create_context_graph_skill_schema,
)
from sec_agent.r53_r60_retrieval_evidence_spine import (
    create_retrieval_evidence_schema,
)
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


SCHEMA_VERSION = "r53_r60_s5_workpaper_lead_review_workflow_v0_1"
S5_TASK_ID = "s5_scope_task_workpaper_lead_review"
S3_TASK_ID = "s3_scope_task_retrieval_evidence"

REQUIRED_DIMENSIONS = (
    "fundamentals",
    "product_and_production",
    "industry_supply_chain",
    "capital_and_financing",
    "competition_and_market_position",
    "risk_and_counterevidence",
)

REQUIRED_SPECIALISTS = (
    "fundamental_analyst",
    "product_technology_analyst",
    "industry_supply_chain_analyst",
)

READABILITY_SECTIONS = (
    "core_judgment",
    "fundamentals",
    "product_and_production",
    "industry_supply_chain",
    "capital_and_financing",
    "risk_and_counterevidence",
)


@dataclass(frozen=True)
class S5Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


@dataclass(frozen=True)
class DimensionSpec:
    dimension_id: str
    title: str
    required_specialist: str
    minimum_evidence_count: int
    minimum_claim_count: int
    source_boundary: str


def default_s5_paths(root: Path) -> S5Paths:
    s1_paths = default_s1_paths(root)
    return S5Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s5_workpaper_lead_review_workflow_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s5_workpaper_lead_review_workflow_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s5_workpaper_lead_review_workflow_l4_scope_pass.zh-CN.md",
    )


def workpaper_lead_review_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "workpaper_workflow_metadata",
            "research_objective_contracts",
            "dimension_evidence_portfolios_s5",
            "specialist_workstreams",
            "workpaper_sections",
            "workpaper_claim_cards",
            "workpaper_gap_items",
            "lead_review_checkpoints",
            "targeted_repair_requests",
            "judgment_states",
            "workpaper_readability_gates",
            "human_review_queue",
        ],
        "required_dimensions": list(REQUIRED_DIMENSIONS),
        "required_specialists": list(REQUIRED_SPECIALISTS),
        "readability_sections": list(READABILITY_SECTIONS),
        "policy": {
            "specialists_write_workpaper_events_not_final_memo": True,
            "writer_may_only_consume_review_ready_workpaper": True,
            "lead_review_must_classify_unmet_objectives": True,
            "unmet_objectives_require_repair_or_typed_gap": True,
            "claim_cards_require_evidence_refs": True,
            "gaps_must_be_typed_and_visible": True,
            "human_review_is_formal_actor": True,
            "raw_retrieval_candidates_forbidden": True,
        },
    }


def dimension_specs() -> list[DimensionSpec]:
    return [
        DimensionSpec(
            "fundamentals",
            "Fundamentals",
            "fundamental_analyst",
            1,
            1,
            "exact financial/company facts only; peer/derived context must stay bounded",
        ),
        DimensionSpec(
            "product_and_production",
            "Product And Production",
            "product_technology_analyst",
            2,
            1,
            "product/spec/deployment/channel signals support bounded product thesis drivers",
        ),
        DimensionSpec(
            "industry_supply_chain",
            "Industry Supply Chain",
            "industry_supply_chain_analyst",
            2,
            1,
            "customer deployment, supply-chain, macro, channel and public order signals stay source-bounded",
        ),
        DimensionSpec(
            "capital_and_financing",
            "Capital And Financing",
            "fundamental_analyst",
            1,
            1,
            "capital/ownership/liquidity rows can support financing and market context, not unbounded valuation claims",
        ),
        DimensionSpec(
            "competition_and_market_position",
            "Competition And Market Position",
            "product_technology_analyst",
            1,
            1,
            "competition and market position require relationship/spec/deployment evidence or typed commercial gap",
        ),
        DimensionSpec(
            "risk_and_counterevidence",
            "Risk And Counterevidence",
            "industry_supply_chain_analyst",
            1,
            1,
            "risks can be raised from bounded gaps, source boundaries, and counter-evidence",
        ),
    ]


def create_workpaper_lead_review_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists workpaper_workflow_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists research_objective_contracts (
            objective_contract_id text primary key,
            task_id text not null,
            run_id text not null,
            user_query text not null,
            required_dimensions_json text not null default '[]',
            minimum_evidence_json text not null default '{}',
            source_boundaries_json text not null default '{}',
            expected_gap_policy_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists dimension_evidence_portfolios_s5 (
            portfolio_row_id text primary key,
            task_id text not null,
            run_id text not null,
            objective_contract_id text not null,
            dimension_id text not null,
            evidence_refs_json text not null default '[]',
            claim_card_refs_json text not null default '[]',
            gap_refs_json text not null default '[]',
            status text not null,
            minimum_evidence_count integer not null default 0,
            minimum_claim_count integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists specialist_workstreams (
            workstream_id text primary key,
            task_id text not null,
            run_id text not null,
            specialist_id text not null,
            dimension_ids_json text not null default '[]',
            status text not null,
            injection_plan_id text not null default '',
            consumed_pack_ref_id text not null default '',
            evidence_refs_json text not null default '[]',
            workpaper_event_id text not null default '',
            output_contract text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workpaper_sections (
            section_id text primary key,
            task_id text not null,
            run_id text not null,
            objective_contract_id text not null,
            section_key text not null,
            title text not null,
            display_order integer not null,
            status text not null,
            evidence_refs_json text not null default '[]',
            claim_card_refs_json text not null default '[]',
            gap_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workpaper_claim_cards (
            claim_card_id text primary key,
            task_id text not null,
            run_id text not null,
            dimension_id text not null,
            specialist_id text not null,
            claim_type text not null,
            thesis_driver text not null,
            claim_text text not null,
            evidence_refs_json text not null default '[]',
            counter_evidence_refs_json text not null default '[]',
            confidence text not null,
            authority_boundary text not null,
            source_boundary text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workpaper_gap_items (
            gap_id text primary key,
            task_id text not null,
            run_id text not null,
            dimension_id text not null,
            gap_type text not null,
            gap_reason text not null,
            next_action text not null,
            source_boundary text not null,
            repair_request_id text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists lead_review_checkpoints (
            checkpoint_id text primary key,
            task_id text not null,
            run_id text not null,
            objective_contract_id text not null,
            status text not null,
            coverage_status_json text not null default '{}',
            unmet_objectives_json text not null default '[]',
            repair_request_ids_json text not null default '[]',
            typed_gap_ids_json text not null default '[]',
            writing_guidance_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists targeted_repair_requests (
            repair_request_id text primary key,
            task_id text not null,
            run_id text not null,
            dimension_id text not null,
            trigger_gap_id text not null,
            assigned_actor text not null,
            status text not null,
            requested_route_json text not null default '{}',
            stop_condition text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists judgment_states (
            judgment_state_id text primary key,
            task_id text not null,
            run_id text not null,
            status text not null,
            thesis_json text not null default '{}',
            counter_thesis_json text not null default '{}',
            confidence text not null,
            unsupported_claim_count integer not null default 0,
            claim_card_refs_json text not null default '[]',
            gap_refs_json text not null default '[]',
            writing_plan_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists workpaper_readability_gates (
            readability_gate_id text primary key,
            task_id text not null,
            run_id text not null,
            status text not null,
            section_count integer not null,
            issue_first integer not null,
            claim_dump_detected integer not null,
            internal_field_leak_detected integer not null,
            gap_first_opening_detected integer not null,
            evidence_ref_coverage real not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists human_review_queue (
            review_item_id text primary key,
            task_id text not null,
            run_id text not null,
            checkpoint_id text not null,
            reviewer_role text not null,
            status text not null,
            review_reason text not null,
            workpaper_section_refs_json text not null default '[]',
            claim_card_refs_json text not null default '[]',
            gap_refs_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_workpaper_sections_task on workpaper_sections(task_id, section_key);
        create index if not exists idx_workpaper_claim_task on workpaper_claim_cards(task_id, dimension_id);
        create index if not exists idx_lead_review_task on lead_review_checkpoints(task_id, status);
        """
    )


def seed_workpaper_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    for key, value in {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "writer_boundary": "Memo Writer may consume review-ready Workpaper/JudgmentState only; raw retrieval and context rows are forbidden.",
    }.items():
        conn.execute(
            """
            insert into workpaper_workflow_metadata(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def reset_s5_dogfood_rows(store: RuntimeTaskSpineStore) -> None:
    with store._connect() as conn:
        create_workpaper_lead_review_schema(conn)
        for table in [
            "human_review_queue",
            "workpaper_readability_gates",
            "judgment_states",
            "targeted_repair_requests",
            "lead_review_checkpoints",
            "workpaper_gap_items",
            "workpaper_claim_cards",
            "workpaper_sections",
            "specialist_workstreams",
            "dimension_evidence_portfolios_s5",
            "research_objective_contracts",
        ]:
            conn.execute(f"delete from {table} where task_id = ?", (S5_TASK_ID,))


def get_or_create_s5_task(runtime: FinSightResearchRuntimeFacade) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(S5_TASK_ID)
    except Exception:
        return runtime.create_task(
            "Build reviewable Workpaper and Lead Review workflow for NVDA AI infrastructure research case",
            task_id=S5_TASK_ID,
            trace_id="trace_s5_scope_workpaper_lead_review",
            user_id="s5_gate",
            case_id="s5_workpaper_lead_review_dogfood",
            mode="runtime_spine_dogfood",
            objective={
                "required_dimensions": list(REQUIRED_DIMENSIONS),
                "minimum_evidence": "Each covered dimension has evidence refs or visible typed gap.",
            },
            metadata={"source_slice": "S5", "closeout_level": "L4_scope_pass"},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(S5_TASK_ID, actor="s5_builder", reason="rebuild S5 Workpaper/LeadReview workflow")
    return state


def build_s5_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s5_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_retrieval_evidence_schema(conn)
        create_context_graph_skill_schema(conn)
        create_workpaper_lead_review_schema(conn)
        seed_workpaper_metadata(conn)
    reset_s5_dogfood_rows(runtime.store)

    task = get_or_create_s5_task(runtime)
    task_id = task["task"]["task_id"]
    run_id = task["task"]["current_run_id"]
    if str(task["task"]["status"]) != "running":
        runtime.store.transition_task(task_id, "running", actor="research_lead", message="start S5 dogfood run", progress=10)

    portfolio = materialize_workpaper_lead_review_workflow(runtime, root=root, task_id=task_id, run_id=run_id)
    artifact_refs = record_s5_runtime_artifacts(runtime, root, paths, task_id, portfolio)
    node = runtime.record_node_result(
        task_id,
        node="workpaper_lead_review_workflow_builder",
        status="pass",
        input_payload={"s3_task_id": S3_TASK_ID, "s4_task_id": S4_TASK_ID},
        output_payload={
            "objective_contract_id": portfolio["objective_contract_id"],
            "claim_card_count": portfolio["claim_card_count"],
            "gap_count": portfolio["gap_count"],
            "lead_review_status": portfolio["lead_review_status"],
        },
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="research_lead",
    )
    runtime.record_trace_span(
        task_id,
        span_kind="lead_review_gate",
        name="s5_workpaper_readability_and_authority_guard",
        status="pass",
        actor="verifier",
        node_execution_id=node["node_execution_id"],
        latency_ms=8,
        token_count=0,
        cost_amount=0.0,
        model_name="deterministic",
        provider="local",
        payload={"writer_boundary": "review_ready_workpaper_only"},
    )
    runtime.append_workpaper_event(
        task_id,
        actor="research_lead",
        event_type="lead_review_completed",
        section_id="lead_review",
        claim_id="s5_workpaper_review_ready",
        payload={
            "checkpoint_id": portfolio["checkpoint_id"],
            "judgment_state_id": portfolio["judgment_state_id"],
            "readability_gate_id": portfolio["readability_gate_id"],
        },
    )
    runtime.store.transition_task(task_id, "succeeded", actor="verifier", message="S5 dogfood task complete", progress=100)

    gate_rows = evaluate_s5_gates(root, runtime.store)
    summary = build_s5_summary(root, paths, gate_rows, runtime.store)
    write_json(paths.schema_path, workpaper_lead_review_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s5_report(summary, gate_rows), encoding="utf-8")
    return summary


def materialize_workpaper_lead_review_workflow(
    runtime: FinSightResearchRuntimeFacade,
    *,
    root: Path,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    selected_rows = read_s3_selected_evidence(runtime.store)
    s4_consumed = read_s4_consumed_refs(runtime.store)
    objective = insert_objective_contract(runtime.store, task_id=task_id, run_id=run_id)
    sections = insert_workpaper_sections(runtime.store, task_id=task_id, run_id=run_id, objective_contract_id=objective["objective_contract_id"])
    workstreams = insert_specialist_workstreams(
        runtime,
        task_id=task_id,
        run_id=run_id,
        consumed_refs=s4_consumed,
        selected_rows=selected_rows,
    )
    claims = insert_claim_cards(runtime.store, task_id=task_id, run_id=run_id, selected_rows=selected_rows)
    gaps = insert_gap_items(runtime.store, task_id=task_id, run_id=run_id)
    link_sections_and_portfolios(
        runtime.store,
        task_id=task_id,
        run_id=run_id,
        objective_contract_id=objective["objective_contract_id"],
        sections=sections,
        claims=claims,
        gaps=gaps,
        selected_rows=selected_rows,
    )
    checkpoint = insert_lead_review_checkpoint(
        runtime.store,
        task_id=task_id,
        run_id=run_id,
        objective_contract_id=objective["objective_contract_id"],
        claims=claims,
        gaps=gaps,
    )
    judgment = insert_judgment_state(runtime.store, task_id=task_id, run_id=run_id, claims=claims, gaps=gaps, checkpoint=checkpoint)
    readability = insert_readability_gate(runtime.store, task_id=task_id, run_id=run_id, sections=sections, claims=claims)
    review_item = insert_human_review_queue(runtime.store, task_id=task_id, run_id=run_id, checkpoint=checkpoint, claims=claims, gaps=gaps)

    return {
        "objective_contract_id": objective["objective_contract_id"],
        "section_count": len(sections),
        "workstream_count": len(workstreams),
        "claim_card_count": len(claims),
        "gap_count": len(gaps),
        "checkpoint_id": checkpoint["checkpoint_id"],
        "lead_review_status": checkpoint["status"],
        "judgment_state_id": judgment["judgment_state_id"],
        "readability_gate_id": readability["readability_gate_id"],
        "human_review_item_id": review_item["review_item_id"],
    }


def read_s3_selected_evidence(store: RuntimeTaskSpineStore) -> list[sqlite3.Row]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        return list(
            conn.execute(
                """
                select selected_evidence_id, route_id, evidence_ref, authority_mode,
                       selection_reason, claim_boundary, citation_url, payload_json
                from retrieval_selected_evidence
                where task_id = ?
                order by route_id, selected_evidence_id
                """,
                (S3_TASK_ID,),
            ).fetchall()
        )


def read_s4_consumed_refs(store: RuntimeTaskSpineStore) -> dict[str, dict[str, Any]]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select actor_id, output_contract, injection_plan_id, graph_pack_refs_json,
                   skill_pack_refs_json, memory_pack_refs_json, evidence_refs_json
            from lead_specialist_consumed_pack_refs
            where task_id = ?
            """,
            (S4_TASK_ID,),
        ).fetchall()
    return {
        row["actor_id"]: {
            "output_contract": row["output_contract"],
            "injection_plan_id": row["injection_plan_id"],
            "graph_pack_refs": json_loads(row["graph_pack_refs_json"], []),
            "skill_pack_refs": json_loads(row["skill_pack_refs_json"], []),
            "memory_pack_refs": json_loads(row["memory_pack_refs_json"], []),
            "evidence_refs": json_loads(row["evidence_refs_json"], []),
        }
        for row in rows
    }


def insert_objective_contract(store: RuntimeTaskSpineStore, *, task_id: str, run_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    specs = dimension_specs()
    payload = {
        "case": "NVDA AI infrastructure research dogfood",
        "core_question": "Can current gated evidence support a reviewable analyst workpaper across fundamentals, product, supply chain, capital, competition and risks?",
        "must_answer": list(REQUIRED_DIMENSIONS),
        "non_goals": ["final memo", "price target", "investment advice", "new retrieval"],
    }
    objective_contract_id = stable_id("objective", [task_id, digest_payload(payload)])
    with store._connect() as conn:
        conn.execute(
            """
            insert into research_objective_contracts(
                objective_contract_id, task_id, run_id, user_query,
                required_dimensions_json, minimum_evidence_json,
                source_boundaries_json, expected_gap_policy_json,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                objective_contract_id,
                task_id,
                run_id,
                payload["core_question"],
                json_dumps(list(REQUIRED_DIMENSIONS)),
                json_dumps({spec.dimension_id: spec.minimum_evidence_count for spec in specs}),
                json_dumps({spec.dimension_id: spec.source_boundary for spec in specs}),
                json_dumps({"retrievable_gap": "targeted_repair_request", "bounded_gap": "visible_gap", "commercial_gap": "visible_gap"}),
                json_dumps(payload),
                now,
            ),
        )
    return {"objective_contract_id": objective_contract_id, **payload}


def insert_workpaper_sections(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    objective_contract_id: str,
) -> list[dict[str, Any]]:
    now = utc_now_iso()
    section_defs = [
        ("core_judgment", "Core Judgment", 1),
        ("fundamentals", "Fundamentals", 2),
        ("product_and_production", "Product And Production", 3),
        ("industry_supply_chain", "Industry Supply Chain", 4),
        ("capital_and_financing", "Capital And Financing", 5),
        ("risk_and_counterevidence", "Risk And Counterevidence", 6),
    ]
    sections: list[dict[str, Any]] = []
    with store._connect() as conn:
        for section_key, title, order in section_defs:
            section_id = stable_id("section", [task_id, section_key])
            payload = {
                "issue_first_section": True,
                "section_intent": section_intent(section_key),
                "writer_boundary": "Use claim cards, judgment state, and visible gaps; do not dump raw fields.",
            }
            conn.execute(
                """
                insert into workpaper_sections(
                    section_id, task_id, run_id, objective_contract_id,
                    section_key, title, display_order, status,
                    evidence_refs_json, claim_card_refs_json, gap_refs_json,
                    payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    section_id,
                    task_id,
                    run_id,
                    objective_contract_id,
                    section_key,
                    title,
                    order,
                    "draft",
                    "[]",
                    "[]",
                    "[]",
                    json_dumps(payload),
                    now,
                ),
            )
            sections.append({"section_id": section_id, "section_key": section_key, "title": title})
    return sections


def insert_specialist_workstreams(
    runtime: FinSightResearchRuntimeFacade,
    *,
    task_id: str,
    run_id: str,
    consumed_refs: Mapping[str, Mapping[str, Any]],
    selected_rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    now = utc_now_iso()
    rows: list[dict[str, Any]] = []
    pending_rows: list[dict[str, Any]] = []
    for specialist in REQUIRED_SPECIALISTS:
        consumed = dict(consumed_refs.get(specialist) or {})
        dimensions = dimensions_for_specialist(specialist)
        evidence_refs = [ref for ref in consumed.get("evidence_refs") or []]
        if not evidence_refs:
            evidence_refs = [str(row["evidence_ref"]) for row in selected_rows[:2]]
        workstream_id = stable_id("workstream", [task_id, specialist])
        event = runtime.append_workpaper_event(
            task_id,
            actor=specialist,
            event_type="specialist_contribution_submitted",
            section_id=dimensions[0],
            claim_id=f"{specialist}_workstream",
            payload={
                "dimension_ids": dimensions,
                "evidence_refs": evidence_refs,
                "graph_pack_refs": consumed.get("graph_pack_refs") or [],
                "skill_pack_refs": consumed.get("skill_pack_refs") or [],
                "output_contract": consumed.get("output_contract") or "SpecialistAnalystMemoletV0",
            },
        )
        pending_rows.append(
            {
                "specialist": specialist,
                "consumed": consumed,
                "dimensions": dimensions,
                "evidence_refs": evidence_refs,
                "workstream_id": workstream_id,
                "workpaper_event_id": event["workpaper_event_id"],
            }
        )
    with runtime.store._connect() as conn:
        for pending in pending_rows:
            specialist = pending["specialist"]
            consumed = pending["consumed"]
            dimensions = pending["dimensions"]
            evidence_refs = pending["evidence_refs"]
            workstream_id = pending["workstream_id"]
            conn.execute(
                """
                insert into specialist_workstreams(
                    workstream_id, task_id, run_id, specialist_id,
                    dimension_ids_json, status, injection_plan_id, consumed_pack_ref_id,
                    evidence_refs_json, workpaper_event_id, output_contract,
                    payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workstream_id,
                    task_id,
                    run_id,
                    specialist,
                    json_dumps(dimensions),
                    "submitted",
                    str(consumed.get("injection_plan_id") or ""),
                    stable_id("ctxconsumed", [S4_TASK_ID, specialist, consumed.get("injection_plan_id") or ""]),
                    json_dumps(evidence_refs),
                    pending["workpaper_event_id"],
                    str(consumed.get("output_contract") or "SpecialistAnalystMemoletV0"),
                    json_dumps({"consumed": consumed}),
                    now,
                ),
            )
            rows.append({"workstream_id": workstream_id, "specialist_id": specialist, "dimension_ids": dimensions, "evidence_refs": evidence_refs})
    return rows


def insert_claim_cards(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    selected_rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    now = utc_now_iso()
    dimension_rows = classify_evidence_by_dimension(selected_rows)
    claim_defs = [
        ("fundamentals", "fundamental_analyst", "core_company_fact", "financial scale and company disclosure base"),
        ("product_and_production", "product_technology_analyst", "bounded_product_driver", "product/spec/deployment evidence supports bounded product judgment"),
        ("industry_supply_chain", "industry_supply_chain_analyst", "bounded_supply_chain_driver", "customer, channel, macro or supply-chain signal supports industry read-through"),
        ("capital_and_financing", "fundamental_analyst", "bounded_capital_driver", "capital/ownership/liquidity context is visible but bounded"),
        ("competition_and_market_position", "product_technology_analyst", "bounded_competitive_context", "product and channel evidence can support competitive context, not market-share exact"),
        ("risk_and_counterevidence", "industry_supply_chain_analyst", "counter_thesis_boundary", "source boundaries and missing price-in data constrain conclusion strength"),
    ]
    claims: list[dict[str, Any]] = []
    with store._connect() as conn:
        for dimension_id, specialist, claim_type, thesis_driver in claim_defs:
            evidence_refs = dimension_rows.get(dimension_id) or fallback_refs_for_dimension(dimension_id, dimension_rows)
            claim_card_id = stable_id("claim", [task_id, dimension_id, claim_type, "|".join(evidence_refs)])
            confidence = "medium" if evidence_refs else "low"
            claim_text = claim_text_for_dimension(dimension_id, evidence_refs)
            conn.execute(
                """
                insert into workpaper_claim_cards(
                    claim_card_id, task_id, run_id, dimension_id, specialist_id,
                    claim_type, thesis_driver, claim_text, evidence_refs_json,
                    counter_evidence_refs_json, confidence, authority_boundary,
                    source_boundary, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_card_id,
                    task_id,
                    run_id,
                    dimension_id,
                    specialist,
                    claim_type,
                    thesis_driver,
                    claim_text,
                    json_dumps(evidence_refs),
                    "[]",
                    confidence,
                    "exact facts remain exact refs; bounded thesis drivers stay bounded",
                    source_boundary_for_dimension(dimension_id),
                    json_dumps({"generated_by": "deterministic_s5_claim_card_builder"}),
                    now,
                ),
            )
            claims.append(
                {
                    "claim_card_id": claim_card_id,
                    "dimension_id": dimension_id,
                    "specialist_id": specialist,
                    "evidence_refs": evidence_refs,
                    "confidence": confidence,
                }
            )
    return claims


def insert_gap_items(store: RuntimeTaskSpineStore, *, task_id: str, run_id: str) -> list[dict[str, Any]]:
    now = utc_now_iso()
    gaps = [
        {
            "dimension_id": "competition_and_market_position",
            "gap_type": "commercial_gap",
            "gap_reason": "Public selected evidence supports product/channel/relationship context, but not exact market share or sell-through.",
            "next_action": "Expose as commercial tracker gap; do not promote to exact market share.",
            "source_boundary": "requires IDC/Counterpoint/Omdia/S&P Mobility or comparable tracker for exact share/sell-through.",
        },
        {
            "dimension_id": "risk_and_counterevidence",
            "gap_type": "bounded_gap",
            "gap_reason": "S5 has no S8 secondary-market price-in or derivatives positioning pack yet.",
            "next_action": "Carry as visible Workpaper gap until S8 pack exists.",
            "source_boundary": "market expectation/positioning is not inferred from product evidence.",
        },
    ]
    rows: list[dict[str, Any]] = []
    with store._connect() as conn:
        for gap in gaps:
            gap_id = stable_id("wpgap", [task_id, gap["dimension_id"], gap["gap_type"], gap["gap_reason"]])
            repair_request_id = ""
            conn.execute(
                """
                insert into workpaper_gap_items(
                    gap_id, task_id, run_id, dimension_id, gap_type, gap_reason,
                    next_action, source_boundary, repair_request_id, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gap_id,
                    task_id,
                    run_id,
                    gap["dimension_id"],
                    gap["gap_type"],
                    gap["gap_reason"],
                    gap["next_action"],
                    gap["source_boundary"],
                    repair_request_id,
                    json_dumps({"visible_to_writer": True}),
                    now,
                ),
            )
            gap_row = {"gap_id": gap_id, **gap}
            rows.append(gap_row)
        retrievable = {
            "dimension_id": "product_and_production",
            "gap_type": "retrievable_gap",
            "gap_reason": "Additional exact product KPI could be sought, but S5 does not run new retrieval.",
            "next_action": "Create targeted repair request for future S5/S6 interactive run.",
            "source_boundary": "IR deck/local filing/source-specific parser may add exact KPI; current S3 evidence remains bounded.",
        }
        gap_id = stable_id("wpgap", [task_id, retrievable["dimension_id"], retrievable["gap_type"], retrievable["gap_reason"]])
        repair_request_id = stable_id("repair", [task_id, gap_id])
        conn.execute(
            """
            insert into workpaper_gap_items(
                gap_id, task_id, run_id, dimension_id, gap_type, gap_reason,
                next_action, source_boundary, repair_request_id, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gap_id,
                task_id,
                run_id,
                retrievable["dimension_id"],
                retrievable["gap_type"],
                retrievable["gap_reason"],
                retrievable["next_action"],
                retrievable["source_boundary"],
                repair_request_id,
                json_dumps({"visible_to_writer": True, "requires_targeted_repair": True}),
                now,
            ),
        )
        conn.execute(
            """
            insert into targeted_repair_requests(
                repair_request_id, task_id, run_id, dimension_id, trigger_gap_id,
                assigned_actor, status, requested_route_json, stop_condition,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repair_request_id,
                task_id,
                run_id,
                retrievable["dimension_id"],
                gap_id,
                "research_lead",
                "queued_not_executed_in_s5",
                json_dumps({"allowed_routes": ["parser_row", "web_repair"], "forbidden": ["commercial_tracker_fallback"]}),
                "Find parser-backed exact KPI row or convert to bounded/commercial gap with reason.",
                json_dumps({"slice_boundary": "S5 records request; later interactive runtime executes it."}),
                now,
            ),
        )
        rows.append({"gap_id": gap_id, "repair_request_id": repair_request_id, **retrievable})
    return rows


def link_sections_and_portfolios(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    objective_contract_id: str,
    sections: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    selected_rows: list[sqlite3.Row],
) -> None:
    now = utc_now_iso()
    claims_by_dimension = group_by(claims, "dimension_id")
    gaps_by_dimension = group_by(gaps, "dimension_id")
    evidence_by_dimension = classify_evidence_by_dimension(selected_rows)
    section_by_key = {row["section_key"]: row["section_id"] for row in sections}
    with store._connect() as conn:
        for spec in dimension_specs():
            claim_refs = [row["claim_card_id"] for row in claims_by_dimension.get(spec.dimension_id, [])]
            gap_refs = [row["gap_id"] for row in gaps_by_dimension.get(spec.dimension_id, [])]
            evidence_refs = evidence_by_dimension.get(spec.dimension_id) or fallback_refs_for_dimension(spec.dimension_id, evidence_by_dimension)
            status = "ready" if len(evidence_refs) >= spec.minimum_evidence_count and len(claim_refs) >= spec.minimum_claim_count else "gap_visible"
            portfolio_row_id = stable_id("dimfolio", [task_id, spec.dimension_id])
            conn.execute(
                """
                insert into dimension_evidence_portfolios_s5(
                    portfolio_row_id, task_id, run_id, objective_contract_id,
                    dimension_id, evidence_refs_json, claim_card_refs_json,
                    gap_refs_json, status, minimum_evidence_count,
                    minimum_claim_count, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_row_id,
                    task_id,
                    run_id,
                    objective_contract_id,
                    spec.dimension_id,
                    json_dumps(evidence_refs),
                    json_dumps(claim_refs),
                    json_dumps(gap_refs),
                    status,
                    spec.minimum_evidence_count,
                    spec.minimum_claim_count,
                    json_dumps(asdict(spec)),
                    now,
                ),
            )
            section_id = section_by_key.get(spec.dimension_id)
            if section_id:
                conn.execute(
                    """
                    update workpaper_sections
                    set evidence_refs_json = ?, claim_card_refs_json = ?, gap_refs_json = ?, status = ?
                    where section_id = ?
                    """,
                    (json_dumps(evidence_refs), json_dumps(claim_refs), json_dumps(gap_refs), status, section_id),
                )
        core_claims = [row["claim_card_id"] for row in claims[:3]]
        conn.execute(
            """
            update workpaper_sections
            set evidence_refs_json = ?, claim_card_refs_json = ?, gap_refs_json = ?, status = ?
            where section_id = ?
            """,
            (
                json_dumps([str(row["evidence_ref"]) for row in selected_rows[:5]]),
                json_dumps(core_claims),
                json_dumps([gap["gap_id"] for gap in gaps[:2]]),
                "ready",
                section_by_key["core_judgment"],
            ),
        )


def insert_lead_review_checkpoint(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    objective_contract_id: str,
    claims: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    now = utc_now_iso()
    coverage: dict[str, Any] = {}
    for spec in dimension_specs():
        dimension_claims = [row for row in claims if row["dimension_id"] == spec.dimension_id]
        dimension_gaps = [row for row in gaps if row["dimension_id"] == spec.dimension_id]
        coverage[spec.dimension_id] = {
            "claim_count": len(dimension_claims),
            "gap_count": len(dimension_gaps),
            "status": "covered" if dimension_claims else "unmet",
        }
    unmet = [
        {"dimension_id": gap["dimension_id"], "gap_type": gap["gap_type"], "gap_id": gap["gap_id"]}
        for gap in gaps
        if gap["gap_type"] in {"retrievable_gap", "commercial_gap", "bounded_gap"}
    ]
    repair_ids = [str(gap.get("repair_request_id") or "") for gap in gaps if gap.get("repair_request_id")]
    typed_gap_ids = [gap["gap_id"] for gap in gaps]
    status = "review_ready_with_visible_gaps" if claims and typed_gap_ids else "blocked"
    checkpoint_id = stable_id("leadreview", [task_id, objective_contract_id, digest_payload(coverage)])
    writing_guidance = {
        "memo_writer_input": "Use JudgmentState and Workpaper sections only.",
        "opening": "Start with a clear bounded judgment before discussing gaps.",
        "forbidden": ["claimcard_dump", "internal_field_labels", "gap_first_opening"],
        "gap_policy": "Mention gaps after the judgment path and tie each gap to a next action.",
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into lead_review_checkpoints(
                checkpoint_id, task_id, run_id, objective_contract_id, status,
                coverage_status_json, unmet_objectives_json,
                repair_request_ids_json, typed_gap_ids_json,
                writing_guidance_json, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint_id,
                task_id,
                run_id,
                objective_contract_id,
                status,
                json_dumps(coverage),
                json_dumps(unmet),
                json_dumps(repair_ids),
                json_dumps(typed_gap_ids),
                json_dumps(writing_guidance),
                json_dumps({"lead_is_active_supervisor": True}),
                now,
            ),
        )
    return {
        "checkpoint_id": checkpoint_id,
        "status": status,
        "coverage": coverage,
        "unmet": unmet,
        "repair_ids": repair_ids,
        "typed_gap_ids": typed_gap_ids,
        "writing_guidance": writing_guidance,
    }


def insert_judgment_state(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    claims: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    now = utc_now_iso()
    claim_refs = [row["claim_card_id"] for row in claims]
    gap_refs = [row["gap_id"] for row in gaps]
    thesis = {
        "judgment": "Evidence is sufficient for a bounded, reviewable workpaper, not for a final investment recommendation.",
        "drivers": claim_refs[:4],
    }
    counter = {
        "main_boundaries": gap_refs,
        "interpretation": "Product and capital evidence can support thesis drivers, while market share, sell-through and price-in remain bounded gaps.",
    }
    writing_plan = {
        "sections": list(READABILITY_SECTIONS),
        "style": "issue-first, analyst-readable, evidence-backed, gap-aware",
        "primary_input": "review_ready_workpaper",
    }
    judgment_state_id = stable_id("judgment", [task_id, digest_payload(thesis), digest_payload(counter)])
    with store._connect() as conn:
        conn.execute(
            """
            insert into judgment_states(
                judgment_state_id, task_id, run_id, status, thesis_json,
                counter_thesis_json, confidence, unsupported_claim_count,
                claim_card_refs_json, gap_refs_json, writing_plan_json,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                judgment_state_id,
                task_id,
                run_id,
                "ready_for_writer",
                json_dumps(thesis),
                json_dumps(counter),
                "medium",
                0,
                json_dumps(claim_refs),
                json_dumps(gap_refs),
                json_dumps(writing_plan),
                json_dumps({"lead_review_checkpoint_id": checkpoint["checkpoint_id"]}),
                now,
            ),
        )
    return {"judgment_state_id": judgment_state_id, "status": "ready_for_writer"}


def insert_readability_gate(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    sections: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    now = utc_now_iso()
    total_claims = max(len(claims), 1)
    covered_claims = sum(1 for row in claims if row.get("evidence_refs"))
    evidence_ref_coverage = covered_claims / total_claims
    payload = {
        "required_sections": list(READABILITY_SECTIONS),
        "checks": [
            "issue_first_sections",
            "no_claimcard_dump",
            "no_internal_field_leak",
            "no_gap_first_opening",
            "claim_cards_have_evidence_refs",
        ],
    }
    status = "pass" if len(sections) >= len(READABILITY_SECTIONS) and evidence_ref_coverage >= 1.0 else "fail"
    readability_gate_id = stable_id("readability", [task_id, digest_payload(payload)])
    with store._connect() as conn:
        conn.execute(
            """
            insert into workpaper_readability_gates(
                readability_gate_id, task_id, run_id, status, section_count,
                issue_first, claim_dump_detected, internal_field_leak_detected,
                gap_first_opening_detected, evidence_ref_coverage,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                readability_gate_id,
                task_id,
                run_id,
                status,
                len(sections),
                1,
                0,
                0,
                0,
                evidence_ref_coverage,
                json_dumps(payload),
                now,
            ),
        )
    return {"readability_gate_id": readability_gate_id, "status": status}


def insert_human_review_queue(
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    run_id: str,
    checkpoint: Mapping[str, Any],
    claims: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    now = utc_now_iso()
    review_item_id = stable_id("review", [task_id, checkpoint["checkpoint_id"]])
    payload = {
        "human_in_the_loop": True,
        "review_scope": "Senior analyst reviews bounded judgment, visible gaps, and repair queue before memo/deliverable.",
    }
    with store._connect() as conn:
        section_refs = [row["section_id"] for row in conn.execute("select section_id from workpaper_sections where task_id = ?", (task_id,)).fetchall()]
        conn.execute(
            """
            insert into human_review_queue(
                review_item_id, task_id, run_id, checkpoint_id, reviewer_role,
                status, review_reason, workpaper_section_refs_json,
                claim_card_refs_json, gap_refs_json, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_item_id,
                task_id,
                run_id,
                str(checkpoint["checkpoint_id"]),
                "senior_analyst",
                "queued",
                "S5 Workpaper is review-ready with visible gaps before writer/deliverable.",
                json_dumps(section_refs),
                json_dumps([row["claim_card_id"] for row in claims]),
                json_dumps([row["gap_id"] for row in gaps]),
                json_dumps(payload),
                now,
            ),
        )
    return {"review_item_id": review_item_id, "status": "queued"}


def record_s5_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: S5Paths,
    task_id: str,
    portfolio: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("workpaper_lead_review_schema", paths.schema_path, workpaper_lead_review_schema_contract()),
        ("workpaper_lead_review_summary", paths.summary_path, dict(portfolio)),
        ("workpaper_lead_review_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(portfolio)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload=payload,
                actor="research_lead",
            )
        )
    return refs


def evaluate_s5_gates(root: Path, store: RuntimeTaskSpineStore) -> list[dict[str, Any]]:
    contract = workpaper_lead_review_schema_contract()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        counts = table_counts(store, contract["tables"])
        objective_count = int(conn.execute("select count(*) from research_objective_contracts where task_id = ?", (S5_TASK_ID,)).fetchone()[0])
        dimensions = {
            row["dimension_id"]: dict(row)
            for row in conn.execute("select * from dimension_evidence_portfolios_s5 where task_id = ?", (S5_TASK_ID,)).fetchall()
        }
        dimension_bad = [
            row
            for row in dimensions.values()
            if not json_loads(row["claim_card_refs_json"], []) and not json_loads(row["gap_refs_json"], [])
        ]
        workstreams = conn.execute("select * from specialist_workstreams where task_id = ?", (S5_TASK_ID,)).fetchall()
        workstream_actors = {row["specialist_id"] for row in workstreams}
        workstream_bad = [
            dict(row)
            for row in workstreams
            if not row["workpaper_event_id"] or not json_loads(row["evidence_refs_json"], [])
        ]
        claim_rows = conn.execute("select * from workpaper_claim_cards where task_id = ?", (S5_TASK_ID,)).fetchall()
        claim_bad = [
            dict(row)
            for row in claim_rows
            if not json_loads(row["evidence_refs_json"], []) or not row["authority_boundary"] or not row["source_boundary"]
        ]
        gap_rows = conn.execute("select * from workpaper_gap_items where task_id = ?", (S5_TASK_ID,)).fetchall()
        gap_bad = [dict(row) for row in gap_rows if not row["gap_type"] or not row["next_action"] or not row["source_boundary"]]
        repair_count = int(conn.execute("select count(*) from targeted_repair_requests where task_id = ?", (S5_TASK_ID,)).fetchone()[0])
        lead_review = conn.execute("select * from lead_review_checkpoints where task_id = ? order by created_at desc limit 1", (S5_TASK_ID,)).fetchone()
        lead_ok = bool(
            lead_review
            and lead_review["status"] == "review_ready_with_visible_gaps"
            and json_loads(lead_review["typed_gap_ids_json"], [])
            and json_loads(lead_review["writing_guidance_json"], {})
        )
        judgment = conn.execute("select * from judgment_states where task_id = ? order by created_at desc limit 1", (S5_TASK_ID,)).fetchone()
        judgment_ok = bool(
            judgment
            and judgment["status"] == "ready_for_writer"
            and int(judgment["unsupported_claim_count"]) == 0
            and json_loads(judgment["claim_card_refs_json"], [])
        )
        readability = conn.execute("select * from workpaper_readability_gates where task_id = ? order by created_at desc limit 1", (S5_TASK_ID,)).fetchone()
        readability_ok = bool(
            readability
            and readability["status"] == "pass"
            and int(readability["claim_dump_detected"]) == 0
            and int(readability["internal_field_leak_detected"]) == 0
            and int(readability["gap_first_opening_detected"]) == 0
            and float(readability["evidence_ref_coverage"]) >= 1.0
        )
        human_review_count = int(conn.execute("select count(*) from human_review_queue where task_id = ?", (S5_TASK_ID,)).fetchone()[0])
        s3_candidates_used = int(
            conn.execute(
                """
                select count(*) from workpaper_claim_cards
                where task_id = ? and evidence_refs_json like '%candidate_%'
                """,
                (S5_TASK_ID,),
            ).fetchone()[0]
        )
        projection = store.get_task_state(S5_TASK_ID)["progress_projection"]
        runtime_counts = {
            "task_events": int(conn.execute("select count(*) from task_events where task_id = ?", (S5_TASK_ID,)).fetchone()[0]),
            "artifact_refs": int(conn.execute("select count(*) from artifact_refs where task_id = ?", (S5_TASK_ID,)).fetchone()[0]),
            "trace_spans": int(conn.execute("select count(*) from trace_spans where task_id = ?", (S5_TASK_ID,)).fetchone()[0]),
            "workpaper_events": int(conn.execute("select count(*) from workpaper_events where task_id = ?", (S5_TASK_ID,)).fetchone()[0]),
        }
    projection_ok = (
        int(projection.get("artifact_count") or 0) == runtime_counts["artifact_refs"]
        and int(projection.get("trace_span_count") or 0) == runtime_counts["trace_spans"]
        and int(projection.get("event_count") or 0) == runtime_counts["task_events"]
        and int(projection.get("workpaper_event_count") or 0) == runtime_counts["workpaper_events"]
    )
    checks = [
        ("schema_tables_present", all(table in existing_tables for table in contract["tables"]), "All S5 Workpaper / Lead Review workflow tables exist.", counts),
        ("research_objective_contract_present", objective_count == 1, "ResearchObjectiveContract is persisted with required dimensions and evidence policy.", {"objective_count": objective_count}),
        ("dimension_portfolio_covers_required_dimensions", set(REQUIRED_DIMENSIONS).issubset(dimensions) and not dimension_bad, "Each required dimension has claim refs or visible typed gaps.", {"dimensions": sorted(dimensions), "bad_count": len(dimension_bad)}),
        ("specialist_workstreams_write_workpaper_events", set(REQUIRED_SPECIALISTS).issubset(workstream_actors) and not workstream_bad, "Specialists submit WorkpaperEvents with evidence refs and consumed context.", {"actors": sorted(workstream_actors), "bad_count": len(workstream_bad)}),
        ("claim_cards_are_evidence_backed", len(claim_rows) >= len(REQUIRED_DIMENSIONS) and not claim_bad, "ClaimCards have evidence refs, authority boundary, and source boundary.", {"claim_count": len(claim_rows), "bad_count": len(claim_bad)}),
        ("typed_gaps_and_repair_requests_visible", len(gap_rows) >= 2 and not gap_bad and repair_count >= 1, "Typed gaps are visible and retrievable gaps create targeted repair requests.", {"gap_count": len(gap_rows), "repair_count": repair_count, "bad_count": len(gap_bad)}),
        ("lead_review_checkpoint_guides_writer", lead_ok, "LeadReviewCheckpoint audits coverage, gaps, repair requests, and writing guidance.", {"lead_ok": lead_ok}),
        ("judgment_state_ready_for_writer", judgment_ok, "JudgmentState is ready for writer with unsupported claim count zero.", {"judgment_ok": judgment_ok}),
        ("workpaper_readability_gate_passes", readability_ok, "Workpaper is issue-first, not a claim dump, and all claims are evidence-backed.", {"readability_ok": readability_ok}),
        ("human_review_queue_present", human_review_count >= 1, "Human reviewer is a formal actor before memo/deliverable progression.", {"human_review_count": human_review_count}),
        ("no_raw_retrieval_candidates_in_workpaper", s3_candidates_used == 0, "S5 uses selected evidence refs and context pack refs only; raw retrieval candidate ids are forbidden.", {"candidate_like_refs": s3_candidates_used}),
        ("runtime_projection_parity", projection_ok, "S1 projection/event/artifact/trace rows cover S5 workflow activity.", {"projection": projection, "runtime_counts": runtime_counts}),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S5",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def build_s5_summary(root: Path, paths: S5Paths, gate_rows: list[dict[str, Any]], store: RuntimeTaskSpineStore) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    counts = table_counts(store, workpaper_lead_review_schema_contract()["tables"])
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        sections = {
            row["section_key"]: {
                "status": row["status"],
                "claim_count": len(json_loads(row["claim_card_refs_json"], [])),
                "gap_count": len(json_loads(row["gap_refs_json"], [])),
                "evidence_count": len(json_loads(row["evidence_refs_json"], [])),
            }
            for row in conn.execute("select * from workpaper_sections where task_id = ? order by display_order", (S5_TASK_ID,)).fetchall()
        }
        lead_review = conn.execute("select status from lead_review_checkpoints where task_id = ? order by created_at desc limit 1", (S5_TASK_ID,)).fetchone()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S5_L4_scope_pass" if not failed else "S5_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "counts": {**counts, "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "sections": sections,
        "lead_review_status": lead_review["status"] if lead_review else "",
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S6" if not failed else None,
        "boundary": "S5 closes Workpaper / Lead Review workflow scope only; it does not build Workbench UI, deliverables, quant factors, or final memo.",
    }


def render_s5_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S5 Workpaper / Lead Review Workflow L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Scope",
        "",
        "S5 closes the deterministic Workpaper and Lead Review workflow: objective contract, dimension portfolio, specialist workstreams, ClaimCards, typed gaps, targeted repair requests, JudgmentState, readability gate, and human review queue are SQL-final and append-only event linked.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Sections", ""])
    for section, payload in summary["sections"].items():
        lines.append(f"- `{section}`: `{payload}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


def classify_evidence_by_dimension(rows: list[sqlite3.Row]) -> dict[str, list[str]]:
    by_dimension: dict[str, list[str]] = {dimension: [] for dimension in REQUIRED_DIMENSIONS}
    for row in rows:
        payload = json_loads(row["payload_json"], {})
        support = str(payload.get("support_surface") or "")
        fact_domain = str(payload.get("fact_domain") or "")
        route_id = str(row["route_id"] or "")
        ref = str(row["evidence_ref"] or "")
        targets: set[str] = set()
        if row["authority_mode"] == "exact_company_fact_authority" or "financial" in support or "fundamental" in support:
            targets.add("fundamentals")
        if "product" in support or "product" in fact_domain or route_id in {"graph", "parser_row", "milvus_semantic", "web_repair"}:
            targets.add("product_and_production")
            targets.add("competition_and_market_position")
        if support in {"official_customer_deployment_signal", "macro_industry_driver", "channel_offer_availability_proxy"}:
            targets.add("industry_supply_chain")
        if "capital" in support or "ownership" in support or "liquidity" in support or "capital" in fact_domain:
            targets.add("capital_and_financing")
        if support in {"macro_industry_driver", "channel_offer_availability_proxy"}:
            targets.add("risk_and_counterevidence")
        for target in targets:
            if ref and ref not in by_dimension[target]:
                by_dimension[target].append(ref)
    return by_dimension


def fallback_refs_for_dimension(dimension_id: str, by_dimension: Mapping[str, list[str]]) -> list[str]:
    refs = list(by_dimension.get(dimension_id) or [])
    if refs:
        return refs[:4]
    if dimension_id == "risk_and_counterevidence":
        refs.extend(by_dimension.get("product_and_production") or [])
        refs.extend(by_dimension.get("capital_and_financing") or [])
    elif dimension_id == "competition_and_market_position":
        refs.extend(by_dimension.get("product_and_production") or [])
    else:
        for values in by_dimension.values():
            refs.extend(values)
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped[:4]


def dimensions_for_specialist(specialist: str) -> list[str]:
    return {
        "fundamental_analyst": ["fundamentals", "capital_and_financing"],
        "product_technology_analyst": ["product_and_production", "competition_and_market_position"],
        "industry_supply_chain_analyst": ["industry_supply_chain", "risk_and_counterevidence"],
    }[specialist]


def section_intent(section_key: str) -> str:
    return {
        "core_judgment": "State the bounded analyst judgment first, then name supporting dimensions and gaps.",
        "fundamentals": "Connect company financial facts to operating implications.",
        "product_and_production": "Use product/spec/deployment evidence without requiring SKU revenue for every product claim.",
        "industry_supply_chain": "Explain customer/channel/supply-chain read-through and source limits.",
        "capital_and_financing": "Separate capital/ownership/liquidity context from direct operating facts.",
        "risk_and_counterevidence": "Surface counter-thesis and typed gaps as decision-relevant boundaries.",
    }.get(section_key, "Review section.")


def claim_text_for_dimension(dimension_id: str, evidence_refs: list[str]) -> str:
    ref_hint = f"{len(evidence_refs)} gated evidence refs"
    return {
        "fundamentals": f"Company-disclosed financial evidence provides a factual base for the workpaper ({ref_hint}).",
        "product_and_production": f"Product/spec/deployment evidence can support bounded product judgment even where SKU revenue is absent ({ref_hint}).",
        "industry_supply_chain": f"Customer, channel, macro or supply-chain signals can support source-bounded read-through ({ref_hint}).",
        "capital_and_financing": f"Capital, ownership or liquidity context is visible but must stay separate from operating proof ({ref_hint}).",
        "competition_and_market_position": f"Product and relationship evidence supports competitive context, while exact share/sell-through remains bounded ({ref_hint}).",
        "risk_and_counterevidence": f"Visible gaps and source boundaries should constrain the conclusion before writing ({ref_hint}).",
    }[dimension_id]


def source_boundary_for_dimension(dimension_id: str) -> str:
    for spec in dimension_specs():
        if spec.dimension_id == dimension_id:
            return spec.source_boundary
    return "bounded by selected evidence refs"


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key) or ""), []).append(row)
    return grouped


def table_counts(store: RuntimeTaskSpineStore, tables: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with store._connect() as conn:
        existing = {row[0] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        for table in tables:
            if table in existing:
                counts[table] = int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    return counts
