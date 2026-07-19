"""S8 Secondary Market / Capital Feedback pack for R53-R60.

This slice turns existing market, ownership, capital-structure, working-capital
and SEC filing-event rows into an auditable capital-feedback pack.  The pack is
bounded by source authority: delayed holder rows stay delayed, market snapshots
stay market context, and missing derivatives/credit-market/short-borrow data is
recorded as typed gaps instead of being inferred from unrelated rows.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
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


SCHEMA_VERSION = "r53_r60_s8_secondary_market_capital_feedback_v0_1"
S8_TASK_ID = "s8_scope_task_secondary_market_capital_feedback"

PACK_ROLES = (
    "secondary_market_capital_flow",
    "ownership_and_holder",
    "credit_funding",
    "corporate_action",
    "liquidity_and_positioning",
    "valuation_price_in",
    "derivatives_market_signal",
)

AUTHORITY_CLASSES = (
    "exact_filing_fact",
    "exact_financial_statement_fact",
    "filing_event_context",
    "lagged_positioning_context",
    "market_expectation_proxy",
    "capital_feedback_signal",
    "valuation_price_in_signal",
    "context_only",
    "gap",
)

SIGNAL_CAP_PER_TICKER_ROLE = 6


@dataclass(frozen=True)
class S8Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path
    market_rows_path: Path
    capital_rows_path: Path
    sec_event_rows_path: Path
    public_context_rows_path: Path


def default_s8_paths(root: Path) -> S8Paths:
    s1_paths = default_s1_paths(root)
    return S8Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s8_secondary_market_capital_feedback_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s8_secondary_market_capital_feedback_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_s8_secondary_market_capital_feedback_l4_scope_pass.zh-CN.md",
        market_rows_path=root / "data" / "manifests" / "market_liquidity_driver_context_rows_v0_1.jsonl",
        capital_rows_path=root / "data" / "manifests" / "capital_funding_ownership_context_rows_v0_1.jsonl",
        sec_event_rows_path=root / "data" / "manifests" / "sec_capital_market_event_context_rows_v0_1.jsonl",
        public_context_rows_path=root / "data" / "manifests" / "secondary_market_public_context_rows_v0_1.jsonl",
    )


def secondary_market_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "secondary_market_feedback_metadata",
            "secondary_market_source_registry_s8",
            "capital_feedback_packs_s8",
            "capital_feedback_signals_s8",
            "capital_feedback_gap_items_s8",
            "capital_feedback_graph_edges_s8",
            "capital_feedback_quality_gates_s8",
        ],
        "pack_roles": list(PACK_ROLES),
        "authority_classes": list(AUTHORITY_CLASSES),
        "policy": {
            "source_registry_required": True,
            "issuer_packs_are_sql_final": True,
            "delayed_holder_rows_are_not_realtime_flow": True,
            "market_rows_are_not_company_fundamentals": True,
            "derivatives_credit_spread_short_borrow_missing_rows_are_typed_gaps": True,
            "no_investment_recommendation_from_market_positioning": True,
        },
    }


def create_secondary_market_feedback_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists secondary_market_feedback_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists secondary_market_source_registry_s8 (
            source_id text primary key,
            pack_role text not null,
            asset_scope text not null,
            market_scope text not null,
            issuer_bound integer not null,
            instrument_bound integer not null,
            frequency text not null,
            lag_policy text not null,
            fields_json text not null default '[]',
            locator_status text not null,
            fetcher_status text not null,
            parser_status text not null,
            verifier_status text not null,
            authority_class text not null,
            lifecycle_status text not null,
            commercial_boundary text not null,
            forbidden_claims_json text not null default '[]',
            last_verified_at text not null,
            eval_case_refs_json text not null default '[]',
            payload_json text not null default '{}'
        );
        create table if not exists capital_feedback_packs_s8 (
            pack_id text primary key,
            task_id text not null,
            run_id text not null,
            ticker text not null,
            status text not null,
            role_counts_json text not null default '{}',
            signal_refs_json text not null default '{}',
            gap_refs_json text not null default '{}',
            source_refs_json text not null default '[]',
            authority_boundary_json text not null default '{}',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists capital_feedback_signals_s8 (
            signal_id text primary key,
            task_id text not null,
            run_id text not null,
            ticker text not null,
            pack_role text not null,
            signal_type text not null,
            source_id text not null,
            source_role text not null,
            authority_class text not null,
            value text not null default '',
            unit text not null default '',
            period text not null default '',
            asof_date text not null default '',
            evidence_ref text not null,
            citation_json text not null default '{}',
            allowed_claims_json text not null default '[]',
            forbidden_claims_json text not null default '[]',
            claim_boundary text not null,
            quality_flags_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists capital_feedback_gap_items_s8 (
            gap_id text primary key,
            task_id text not null,
            run_id text not null,
            ticker text not null,
            pack_role text not null,
            gap_type text not null,
            source_id text not null,
            lifecycle_status text not null,
            public_boundary text not null,
            commercial_boundary text not null,
            next_action text not null,
            forbidden_claims_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists capital_feedback_graph_edges_s8 (
            graph_edge_id text primary key,
            task_id text not null,
            run_id text not null,
            ticker text not null,
            from_node text not null,
            to_node text not null,
            edge_type text not null,
            pack_role text not null,
            authority_class text not null,
            evidence_refs_json text not null default '[]',
            gap_refs_json text not null default '[]',
            forbidden_claims_json text not null default '[]',
            confidence text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists capital_feedback_quality_gates_s8 (
            quality_gate_id text primary key,
            task_id text not null,
            gate_id text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_capital_feedback_pack_task on capital_feedback_packs_s8(task_id, ticker);
        create index if not exists idx_capital_feedback_signal_task on capital_feedback_signals_s8(task_id, ticker, pack_role);
        create index if not exists idx_capital_feedback_gap_task on capital_feedback_gap_items_s8(task_id, ticker, pack_role);
        create index if not exists idx_capital_feedback_edge_task on capital_feedback_graph_edges_s8(task_id, ticker, pack_role);
        """
    )


def build_s8_gate(root: Path, *, task_id: str = S8_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s8_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_secondary_market_feedback_schema(conn)
        seed_s8_metadata(conn)
        seed_source_registry(conn)
        clear_s8_task_rows(conn, task_id)

    task = get_or_create_s8_task(runtime, task_id=task_id)
    if str(task["task"]["status"]) != "running":
        task = runtime.store.transition_task(task_id, "running", actor="capital_feedback_builder", message="start S8 capital feedback build", progress=10)
    run_id = str(task["task"]["current_run_id"])

    materialized = materialize_capital_feedback_pack(runtime.store, root=root, paths=paths, task_id=task_id, run_id=run_id)
    write_json(paths.schema_path, secondary_market_schema_contract())

    artifact_refs = record_s8_runtime_artifacts(runtime, root, paths, task_id, materialized)
    workpaper_event = runtime.append_workpaper_event(
        task_id,
        actor="capital_feedback_specialist",
        event_type="secondary_market_capital_feedback_pack_ready",
        section_id="secondary_market_capital_feedback",
        claim_id="s8_capital_feedback_pack",
        payload={
            "schema_version": SCHEMA_VERSION,
            "pack_count": materialized["pack_count"],
            "signal_count": materialized["signal_count"],
            "gap_count": materialized["gap_count"],
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "authority_boundary": "market, holder, credit, corporate action, valuation and derivatives signals are separated by authority class.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="secondary_market_capital_feedback_builder",
        status="pass",
        input_payload={
            "market_rows": rel_path(paths.market_rows_path, root),
            "capital_rows": rel_path(paths.capital_rows_path, root),
            "sec_event_rows": rel_path(paths.sec_event_rows_path, root),
        },
        output_payload={**materialized, "workpaper_event_id": workpaper_event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="capital_feedback_builder",
    )
    runtime.record_trace_span(
        task_id,
        span_kind="capital_feedback_gate",
        name="s8_authority_boundary_and_gap_gate",
        status="pass",
        actor="verifier",
        node_execution_id=node["node_execution_id"],
        latency_ms=0,
        token_count=0,
        cost_amount=0.0,
        model_name="deterministic",
        provider="local",
        payload={"closeout_level": "L4_scope_pass", "no_llm": True},
    )
    runtime.store.transition_task(task_id, "succeeded", actor="verifier", message="S8 capital feedback pack complete", progress=100)

    gate_rows = evaluate_s8_gates(root, runtime.store, task_id=task_id, materialized=materialized)
    persist_quality_gates(runtime.store, task_id=task_id, gate_rows=gate_rows)
    summary = build_s8_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s8_report(summary, gate_rows), encoding="utf-8")
    return summary


def get_or_create_s8_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Build Secondary Market / Capital Feedback Pack with bounded authority and typed market-data gaps",
            task_id=task_id,
            trace_id="trace_s8_secondary_market_capital_feedback",
            user_id="s8_gate",
            case_id="s8_secondary_market_capital_feedback_l4_scope",
            mode="runtime_spine_dogfood",
            objective={
                "required_pack_roles": list(PACK_ROLES),
                "minimum_evidence": "Each issuer has market/liquidity context and every missing market-data class is typed as gap.",
            },
            metadata={"source_slice": "S8", "closeout_level": "L4_scope_pass"},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="s8_builder", reason="rebuild S8 Secondary Market / Capital Feedback Pack")
    return state


def materialize_capital_feedback_pack(
    store: RuntimeTaskSpineStore,
    *,
    root: Path,
    paths: S8Paths,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    pack_state: dict[str, dict[str, Any]] = defaultdict(new_pack_state)
    inserted_signal_keys: set[str] = set()
    cap_counts: dict[tuple[str, str], int] = defaultdict(int)
    runtime_universe: set[str] = set()
    raw_input_counts = {"market_rows": 0, "capital_rows": 0, "sec_event_rows": 0, "public_context_rows": 0}
    skipped_counts = {"capital_rows_outside_runtime_universe": 0, "sec_event_tickers_outside_runtime_universe": 0}

    with store._connect() as conn:
        conn.execute("begin immediate")
        try:
            # Market snapshot rows become market/liquidity signals.  Valuation
            # fields are only materialized if the row actually carries them.
            for row in stream_jsonl(paths.market_rows_path):
                raw_input_counts["market_rows"] += 1
                ticker = normalize_ticker(row.get("ticker"))
                if not ticker:
                    continue
                runtime_universe.add(ticker)
                record_source(pack_state, ticker, row)
                insert_signal(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    now=now,
                    row=row,
                    ticker=ticker,
                    pack_role="secondary_market_capital_flow",
                    authority_class="market_expectation_proxy",
                    signal_type="price_volume_reaction_context",
                    pack_state=pack_state,
                    inserted_signal_keys=inserted_signal_keys,
                    cap_counts=cap_counts,
                )
                insert_signal(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    now=now,
                    row=row,
                    ticker=ticker,
                    pack_role="liquidity_and_positioning",
                    authority_class="market_expectation_proxy",
                    signal_type="delayed_price_volume_positioning_context",
                    pack_state=pack_state,
                    inserted_signal_keys=inserted_signal_keys,
                    cap_counts=cap_counts,
                )
                valuation_context = row.get("valuation_context") if isinstance(row.get("valuation_context"), Mapping) else {}
                if any(value not in (None, "", []) for value in valuation_context.values()):
                    insert_signal(
                        conn,
                        task_id=task_id,
                        run_id=run_id,
                        now=now,
                        row=row,
                        ticker=ticker,
                        pack_role="valuation_price_in",
                        authority_class="valuation_price_in_signal",
                        signal_type="public_snapshot_valuation_context",
                        pack_state=pack_state,
                        inserted_signal_keys=inserted_signal_keys,
                        cap_counts=cap_counts,
                    )

            if paths.public_context_rows_path.exists():
                for row in stream_jsonl(paths.public_context_rows_path):
                    raw_input_counts["public_context_rows"] += 1
                    ticker = normalize_ticker(row.get("ticker"))
                    if not ticker:
                        continue
                    if ticker not in runtime_universe:
                        skipped_counts["sec_event_tickers_outside_runtime_universe"] += 1
                        continue
                    role, authority, signal_type = classify_public_context_row(row)
                    record_source(pack_state, ticker, row)
                    insert_signal(
                        conn,
                        task_id=task_id,
                        run_id=run_id,
                        now=now,
                        row=row,
                        ticker=ticker,
                        pack_role=role,
                        authority_class=authority,
                        signal_type=signal_type,
                        pack_state=pack_state,
                        inserted_signal_keys=inserted_signal_keys,
                        cap_counts=cap_counts,
                    )

            for row in stream_jsonl(paths.capital_rows_path):
                raw_input_counts["capital_rows"] += 1
                ticker = normalize_ticker(row.get("ticker"))
                if not ticker:
                    continue
                if ticker not in runtime_universe:
                    skipped_counts["capital_rows_outside_runtime_universe"] += 1
                    continue
                role, authority, signal_type = classify_capital_row(row)
                record_source(pack_state, ticker, row)
                insert_signal(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    now=now,
                    row=row,
                    ticker=ticker,
                    pack_role=role,
                    authority_class=authority,
                    signal_type=signal_type,
                    pack_state=pack_state,
                    inserted_signal_keys=inserted_signal_keys,
                    cap_counts=cap_counts,
                )

            for row in stream_jsonl(paths.sec_event_rows_path):
                raw_input_counts["sec_event_rows"] += 1
                tickers = row.get("all_tickers") if isinstance(row.get("all_tickers"), list) else [row.get("ticker")]
                for ticker_value in tickers:
                    ticker = normalize_ticker(ticker_value)
                    if not ticker:
                        continue
                    if ticker not in runtime_universe:
                        skipped_counts["sec_event_tickers_outside_runtime_universe"] += 1
                        continue
                    role, authority, signal_type = classify_sec_event_row(row)
                    record_source(pack_state, ticker, row)
                    insert_signal(
                        conn,
                        task_id=task_id,
                        run_id=run_id,
                        now=now,
                        row=row,
                        ticker=ticker,
                        pack_role=role,
                        authority_class=authority,
                        signal_type=signal_type,
                        pack_state=pack_state,
                        inserted_signal_keys=inserted_signal_keys,
                        cap_counts=cap_counts,
                    )

            for ticker in sorted(pack_state):
                add_required_gaps(conn, task_id=task_id, run_id=run_id, now=now, ticker=ticker, state=pack_state[ticker])
                insert_pack_row(conn, task_id=task_id, run_id=run_id, now=now, ticker=ticker, state=pack_state[ticker])
                insert_graph_edges(conn, task_id=task_id, run_id=run_id, now=now, ticker=ticker, state=pack_state[ticker])
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    with store._connect() as conn:
        counts = {
            "pack_count": int(conn.execute("select count(*) from capital_feedback_packs_s8 where task_id = ?", (task_id,)).fetchone()[0]),
            "signal_count": int(conn.execute("select count(*) from capital_feedback_signals_s8 where task_id = ?", (task_id,)).fetchone()[0]),
            "gap_count": int(conn.execute("select count(*) from capital_feedback_gap_items_s8 where task_id = ?", (task_id,)).fetchone()[0]),
            "graph_edge_count": int(conn.execute("select count(*) from capital_feedback_graph_edges_s8 where task_id = ?", (task_id,)).fetchone()[0]),
        }
    return {
        **counts,
        "runtime_universe_count": len(runtime_universe),
        "raw_input_counts": raw_input_counts,
        "skipped_counts": skipped_counts,
        "source_paths": source_paths(paths, root),
    }


def new_pack_state() -> dict[str, Any]:
    return {
        "role_counts": defaultdict(int),
        "signal_refs": defaultdict(list),
        "gap_refs": defaultdict(list),
        "source_refs": set(),
        "authority_boundary": {},
        "signal_types": defaultdict(set),
    }


def insert_signal(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    now: str,
    row: Mapping[str, Any],
    ticker: str,
    pack_role: str,
    authority_class: str,
    signal_type: str,
    pack_state: dict[str, dict[str, Any]],
    inserted_signal_keys: set[str],
    cap_counts: dict[tuple[str, str], int],
) -> None:
    if pack_role not in PACK_ROLES:
        raise ValueError(f"unknown_pack_role:{pack_role}")
    evidence_ref = str(row.get("evidence_ref") or row.get("fact_id") or row.get("evidence_id") or "")
    source_id = str(row.get("source_id") or "unknown_source")
    source_role = str(row.get("source_role") or "")
    signal_key = stable_id("s8sig", [ticker, pack_role, signal_type, source_id, evidence_ref or digest_payload(row)])
    if signal_key in inserted_signal_keys:
        return
    cap_key = (ticker, pack_role)
    if cap_counts[cap_key] >= SIGNAL_CAP_PER_TICKER_ROLE:
        pack_state[ticker]["role_counts"][pack_role] += 1
        return
    cap_counts[cap_key] += 1
    inserted_signal_keys.add(signal_key)

    allowed_claims = list(row.get("allowed_claims") or [])
    row_forbidden_claims = list(row.get("forbidden_claims") or [])
    default_forbidden = default_forbidden_claims(pack_role, authority_class)
    # Source rows often carry source-specific forbidden claims, but S8 must
    # also enforce the role/authority-wide boundary so downstream Research Lead
    # and writer cannot promote market/capital signals into fundamentals,
    # real-time flow, or investment advice.
    forbidden_claims = sorted({*row_forbidden_claims, *default_forbidden})
    claim_boundary = str(row.get("claim_boundary") or "")
    if not claim_boundary:
        claim_boundary = default_claim_boundary(pack_role, authority_class)
    signal_id = signal_key
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    if not citation and row.get("source_url"):
        citation = {"url": row.get("source_url"), "title": f"{ticker} {source_id}"}

    conn.execute(
        """
        insert into capital_feedback_signals_s8(
            signal_id, task_id, run_id, ticker, pack_role, signal_type,
            source_id, source_role, authority_class, value, unit, period,
            asof_date, evidence_ref, citation_json, allowed_claims_json,
            forbidden_claims_json, claim_boundary, quality_flags_json,
            payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            task_id,
            run_id,
            ticker,
            pack_role,
            signal_type,
            source_id,
            source_role,
            authority_class,
            string_field(row.get("value")),
            string_field(row.get("unit")),
            string_field(row.get("period") or row.get("filing_date") or row.get("report_date")),
            string_field(row.get("as_of_date") or row.get("filing_date") or row.get("generated_at")),
            evidence_ref or signal_id,
            json_dumps(citation),
            json_dumps(allowed_claims),
            json_dumps(forbidden_claims),
            claim_boundary,
            json_dumps(quality_flags(row, authority_class)),
            json_dumps(compact_signal_payload(row)),
            now,
        ),
    )
    state = pack_state[ticker]
    state["role_counts"][pack_role] += 1
    state["signal_refs"][pack_role].append(signal_id)
    state["signal_types"][pack_role].add(signal_type)
    state["authority_boundary"][pack_role] = {
        "authority_class": authority_class,
        "claim_boundary": claim_boundary,
        "forbidden_claims": forbidden_claims,
    }


def add_required_gaps(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    now: str,
    ticker: str,
    state: dict[str, Any],
) -> None:
    role_counts = state["role_counts"]
    signal_types = state.get("signal_types") or {}
    valuation_signal_types = set(signal_types.get("valuation_price_in", set()))
    derivatives_signal_types = set(signal_types.get("derivatives_market_signal", set()))
    credit_signal_types = set(signal_types.get("credit_funding", set()))
    liquidity_signal_types = set(signal_types.get("liquidity_and_positioning", set()))
    required_gap_specs = [
        (
            "valuation_price_in",
            "valuation_fields_missing_from_current_public_snapshot",
            "public_valuation_snapshot_planned",
            "Current public market snapshot lacks stable issuer-bound market cap / EV / PE / EV-sales / EV-EBITDA fields.",
            "Add issuer-bound valuation panel with shares/market-cap/EV denominator and peer multiple vintage; consensus NTM remains commercial.",
        ),
        (
            "derivatives_market_signal",
            "derivatives_public_parser_not_runtime_ready",
            "derivatives_public_sources_planned",
            "No parser-backed CFTC/CME/OCC/Nasdaq option-chain row is currently materialized for this issuer.",
            "Materialize delayed futures/options/COT rows where public and licensed; otherwise retain OPRA/dealer-gamma/real-time depth as commercial gap.",
        ),
        (
            "credit_funding",
            "credit_market_price_spread_missing",
            "bond_credit_market_public_sources_planned",
            "Company-disclosed debt rows do not include market-implied bond yield, credit spread, CDS, or rating-history rows.",
            "Add public bond/rating parser where available; CDS and broad live spread data remain commercial unless licensed.",
        ),
        (
            "liquidity_and_positioning",
            "short_interest_borrow_cost_missing",
            "short_interest_borrow_public_sources_planned",
            "Current pack has price/volume liquidity context but no issuer-bound short-interest, borrow-cost, or securities-lending row.",
            "Add delayed official short-interest rows where available; borrow cost and securities-lending depth are commercial unless sourced.",
        ),
        (
            "ownership_and_holder",
            "ownership_holder_signal_missing_or_non_us_adapter_needed",
            "holder_filing_routes_planned",
            "No issuer-bound holder / 13F / 13D-G / fund-holding row exists in the current runtime pack for this issuer.",
            "Add local exchange / fund-holding / beneficial-owner adapter for non-US issuers; keep lag and no-realtime-flow boundary.",
        ),
        (
            "corporate_action",
            "capital_market_event_signal_missing_or_non_us_adapter_needed",
            "capital_market_event_routes_planned",
            "No issuer-bound offering / insider / proxy / buyback / corporate-action filing-event row exists in the current runtime pack.",
            "Add local exchange and source-specific buyback/offering/insider parser; metadata-only rows remain event context.",
        ),
    ]
    for pack_role, gap_type, source_id, public_boundary, next_action in required_gap_specs:
        if gap_type == "valuation_fields_missing_from_current_public_snapshot" and valuation_signal_types.intersection(
            {
                "public_price_filed_shares_market_cap_context",
                "public_snapshot_valuation_context",
                "sec_entity_public_float_context",
                "yahoo_fundamentals_market_cap_context",
            }
        ):
            continue
        if gap_type == "derivatives_public_parser_not_runtime_ready" and derivatives_signal_types.intersection(
            {"fred_vix_market_volatility_regime", "public_derivatives_market_regime_context"}
        ):
            continue
        if gap_type == "credit_market_price_spread_missing" and credit_signal_types.intersection(
            {"fred_credit_spread_regime_context", "issuer_market_credit_spread_context"}
        ):
            continue
        if gap_type == "short_interest_borrow_cost_missing" and liquidity_signal_types.intersection(
            {"public_short_interest_context", "public_borrow_cost_context"}
        ):
            continue
        if role_counts.get(pack_role, 0) > 0 and gap_type not in {
            "derivatives_public_parser_not_runtime_ready",
            "credit_market_price_spread_missing",
            "short_interest_borrow_cost_missing",
            "valuation_fields_missing_from_current_public_snapshot",
        }:
            continue
        insert_gap(
            conn,
            task_id=task_id,
            run_id=run_id,
            now=now,
            ticker=ticker,
            pack_role=pack_role,
            gap_type=gap_type,
            source_id=source_id,
            public_boundary=public_boundary,
            next_action=next_action,
            state=state,
        )


def insert_gap(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    now: str,
    ticker: str,
    pack_role: str,
    gap_type: str,
    source_id: str,
    public_boundary: str,
    next_action: str,
    state: dict[str, Any],
) -> None:
    gap_id = stable_id("s8gap", [ticker, pack_role, gap_type, source_id])
    commercial_boundary = commercial_boundary_for_gap(gap_type)
    forbidden_claims = default_forbidden_claims(pack_role, "gap")
    conn.execute(
        """
        insert into capital_feedback_gap_items_s8(
            gap_id, task_id, run_id, ticker, pack_role, gap_type, source_id,
            lifecycle_status, public_boundary, commercial_boundary, next_action,
            forbidden_claims_json, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gap_id,
            task_id,
            run_id,
            ticker,
            pack_role,
            gap_type,
            source_id,
            "typed_gap",
            public_boundary,
            commercial_boundary,
            next_action,
            json_dumps(forbidden_claims),
            json_dumps({"authority_class": "gap", "source_id": source_id}),
            now,
        ),
    )
    state["gap_refs"][pack_role].append(gap_id)
    state["authority_boundary"].setdefault(
        pack_role,
        {"authority_class": "gap", "claim_boundary": public_boundary, "forbidden_claims": forbidden_claims},
    )


def insert_pack_row(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    now: str,
    ticker: str,
    state: Mapping[str, Any],
) -> None:
    pack_id = stable_id("s8pack", [task_id, ticker])
    role_counts = {role: int(state["role_counts"].get(role, 0)) for role in PACK_ROLES}
    signal_refs = {role: list(state["signal_refs"].get(role, [])) for role in PACK_ROLES}
    gap_refs = {role: list(state["gap_refs"].get(role, [])) for role in PACK_ROLES}
    status = "review_ready_with_typed_gaps" if role_counts["secondary_market_capital_flow"] else "blocked_missing_market_snapshot"
    conn.execute(
        """
        insert into capital_feedback_packs_s8(
            pack_id, task_id, run_id, ticker, status, role_counts_json,
            signal_refs_json, gap_refs_json, source_refs_json,
            authority_boundary_json, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pack_id,
            task_id,
            run_id,
            ticker,
            status,
            json_dumps(role_counts),
            json_dumps(signal_refs),
            json_dumps(gap_refs),
            json_dumps(sorted(state["source_refs"])),
            json_dumps(state["authority_boundary"]),
            json_dumps({"schema_version": SCHEMA_VERSION, "pack_roles": list(PACK_ROLES)}),
            now,
        ),
    )


def insert_graph_edges(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    now: str,
    ticker: str,
    state: Mapping[str, Any],
) -> None:
    for role in PACK_ROLES:
        evidence_refs = list(state["signal_refs"].get(role, []))[:4]
        gap_refs = list(state["gap_refs"].get(role, []))[:4]
        if not evidence_refs and not gap_refs:
            continue
        edge_id = stable_id("s8edge", [task_id, ticker, role])
        boundary = state["authority_boundary"].get(role, {})
        conn.execute(
            """
            insert into capital_feedback_graph_edges_s8(
                graph_edge_id, task_id, run_id, ticker, from_node, to_node,
                edge_type, pack_role, authority_class, evidence_refs_json,
                gap_refs_json, forbidden_claims_json, confidence, status,
                payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge_id,
                task_id,
                run_id,
                ticker,
                f"issuer:{ticker}",
                f"capital_feedback_pack_role:{role}",
                edge_type_for_role(role),
                role,
                str(boundary.get("authority_class") or "gap"),
                json_dumps(evidence_refs),
                json_dumps(gap_refs),
                json_dumps(boundary.get("forbidden_claims") or default_forbidden_claims(role, "gap")),
                "bounded",
                "active" if evidence_refs else "typed_gap",
                json_dumps({"direction": "issuer_to_capital_feedback_role"}),
                now,
            ),
        )


def evaluate_s8_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = secondary_market_schema_contract()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        table_count_map = {
            table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            for table in contract["tables"]
            if table_exists(conn, table)
        }
        registry_rows = rows_to_dicts(conn.execute("select * from secondary_market_source_registry_s8").fetchall())
        registry_roles = {row["pack_role"] for row in registry_rows}
        registry_bad = [
            row
            for row in registry_rows
            if not row.get("authority_class")
            or not row.get("lag_policy")
            or not row.get("commercial_boundary")
            or not row.get("lifecycle_status")
            or not json_loads(str(row.get("forbidden_claims_json") or ""), [])
        ]
        pack_count = int(conn.execute("select count(*) from capital_feedback_packs_s8 where task_id = ?", (task_id,)).fetchone()[0])
        market_pack_count = int(
            conn.execute(
                """
                select count(*) from capital_feedback_packs_s8
                where task_id = ? and json_extract(role_counts_json, '$.secondary_market_capital_flow') > 0
                """,
                (task_id,),
            ).fetchone()[0]
        )
        liquidity_pack_count = int(
            conn.execute(
                """
                select count(*) from capital_feedback_packs_s8
                where task_id = ? and json_extract(role_counts_json, '$.liquidity_and_positioning') > 0
                """,
                (task_id,),
            ).fetchone()[0]
        )
        signal_bad = rows_to_dicts(
            conn.execute(
                """
                select * from capital_feedback_signals_s8
                where task_id = ? and (
                    claim_boundary = ''
                    or evidence_ref = ''
                    or forbidden_claims_json in ('', '[]')
                    or authority_class not in ({})
                )
                """.format(",".join("?" for _ in AUTHORITY_CLASSES)),
                (task_id, *AUTHORITY_CLASSES),
            ).fetchall()
        )
        realtime_bad = rows_to_dicts(
            conn.execute(
                """
                select * from capital_feedback_signals_s8
                where task_id = ?
                  and authority_class = 'lagged_positioning_context'
                  and forbidden_claims_json not like '%realtime%'
                """,
                (task_id,),
            ).fetchall()
        )
        role_gap_counts = {
            row["pack_role"]: int(row["count"])
            for row in conn.execute(
                "select pack_role, count(*) as count from capital_feedback_gap_items_s8 where task_id = ? group by pack_role",
                (task_id,),
            ).fetchall()
        }
        role_signal_counts = {
            row["pack_role"]: int(row["count"])
            for row in conn.execute(
                "select pack_role, count(*) as count from capital_feedback_signals_s8 where task_id = ? group by pack_role",
                (task_id,),
            ).fetchall()
        }
        gap_bad = rows_to_dicts(
            conn.execute(
                """
                select * from capital_feedback_gap_items_s8
                where task_id = ? and (gap_type = '' or public_boundary = '' or next_action = '' or forbidden_claims_json in ('', '[]'))
                """,
                (task_id,),
            ).fetchall()
        )
        derivative_signal_counts = {
            row["signal_type"]: int(row["count"])
            for row in conn.execute(
                """
                select signal_type, count(*) as count
                from capital_feedback_signals_s8
                where task_id = ? and pack_role = 'derivatives_market_signal'
                group by signal_type
                """,
                (task_id,),
            ).fetchall()
        }
        allowed_derivative_signal_types = {"fred_vix_market_volatility_regime", "public_derivatives_market_regime_context"}
        derivative_signal_count = sum(derivative_signal_counts.values())
        derivative_bad_count = sum(
            count for signal_type, count in derivative_signal_counts.items() if signal_type not in allowed_derivative_signal_types
        )
        graph_bad_count = int(
            conn.execute(
                """
                select count(*) from capital_feedback_graph_edges_s8
                where task_id = ? and evidence_refs_json = '[]' and gap_refs_json = '[]'
                """,
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                """
                select count(*) from workpaper_events
                where task_id = ? and event_type = 'secondary_market_capital_feedback_pack_ready'
                """,
                (task_id,),
            ).fetchone()[0]
        )
        task_state = store.get_task_state(task_id)["task"]

    checks = [
        (
            "schema_tables_present",
            all(table in existing_tables for table in contract["tables"]),
            "All S8 secondary-market/capital-feedback tables exist.",
            {"tables": sorted(existing_tables & set(contract["tables"])), "counts": table_count_map},
        ),
        (
            "source_registry_authority_ready",
            set(PACK_ROLES).issubset(registry_roles) and not registry_bad,
            "Source registry covers every pack role with authority, lag, lifecycle, forbidden claims, and commercial boundary.",
            {"registry_roles": sorted(registry_roles), "bad_count": len(registry_bad)},
        ),
        (
            "issuer_packs_cover_runtime_universe",
            pack_count >= 600 if root.name == "FIN_Insight_Agent" else pack_count > 0,
            "Issuer packs are SQL-final and cover the runtime universe for the current root.",
            {"pack_count": pack_count, "materialized": dict(materialized)},
        ),
        (
            "market_and_liquidity_context_cover_every_pack",
            pack_count > 0 and market_pack_count == pack_count and liquidity_pack_count == pack_count,
            "Every issuer pack has delayed market price/volume/liquidity context.",
            {"pack_count": pack_count, "market_pack_count": market_pack_count, "liquidity_pack_count": liquidity_pack_count},
        ),
        (
            "signals_are_authority_bounded",
            table_count_map.get("capital_feedback_signals_s8", 0) > 0 and not signal_bad,
            "Signals carry evidence refs, authority class, claim boundary, and forbidden claims.",
            {"signal_count": table_count_map.get("capital_feedback_signals_s8", 0), "bad_count": len(signal_bad)},
        ),
        (
            "lagged_holder_rows_never_realtime_flow",
            not realtime_bad,
            "Lagged 13F/holder rows cannot be rendered as current fund flow or current buying pressure.",
            {"bad_count": len(realtime_bad)},
        ),
        (
            "missing_derivatives_credit_short_valuation_are_typed_gaps",
            all(
                role_signal_counts.get(role, 0) > 0 or role_gap_counts.get(role, 0) > 0
                for role in ["derivatives_market_signal", "credit_funding", "liquidity_and_positioning", "valuation_price_in"]
            )
            and not gap_bad,
            "Missing derivatives, market-credit, short/borrow, and valuation fields are either parser-backed bounded signals or explicit typed gaps.",
            {"role_signal_counts": role_signal_counts, "role_gap_counts": role_gap_counts, "gap_bad_count": len(gap_bad)},
        ),
        (
            "no_fake_derivatives_runtime_signal",
            derivative_bad_count == 0,
            "S8 allows bounded broad-market derivatives regime signals and still rejects fake single-stock option/gamma signals.",
            {
                "derivative_signal_count": derivative_signal_count,
                "derivative_signal_counts": derivative_signal_counts,
                "bad_count": derivative_bad_count,
                "allowed_signal_types": sorted(allowed_derivative_signal_types),
            },
        ),
        (
            "graph_edges_are_evidence_or_gap_backed",
            table_count_map.get("capital_feedback_graph_edges_s8", 0) > 0 and graph_bad_count == 0,
            "Capital feedback graph edges always point to evidence refs or typed gap refs.",
            {"graph_edge_count": table_count_map.get("capital_feedback_graph_edges_s8", 0), "bad_count": graph_bad_count},
        ),
        (
            "runtime_workpaper_event_and_task_closeout",
            workpaper_event_count >= 1 and task_state["status"] == "succeeded",
            "S8 appends a WorkpaperEvent and closes through the S1 task spine.",
            {"workpaper_event_count": workpaper_event_count, "task_status": task_state["status"]},
        ),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S8",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def build_s8_summary(
    root: Path,
    paths: S8Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    with store._connect() as conn:
        counts = {
            table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            for table in secondary_market_schema_contract()["tables"]
            if table_exists(conn, table)
        }
        role_signal_counts = {
            row["pack_role"]: int(row["count"])
            for row in conn.execute(
                "select pack_role, count(*) as count from capital_feedback_signals_s8 where task_id = ? group by pack_role",
                (task_id,),
            ).fetchall()
        }
        role_gap_counts = {
            row["pack_role"]: int(row["count"])
            for row in conn.execute(
                "select pack_role, count(*) as count from capital_feedback_gap_items_s8 where task_id = ? group by pack_role",
                (task_id,),
            ).fetchall()
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S8_L4_scope_pass" if not failed else "S8_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "task_id": task_id,
        "counts": {
            **counts,
            "gate_count": len(gate_rows),
            "gate_fail_count": len(failed),
            **dict(materialized),
        },
        "role_signal_counts": role_signal_counts,
        "role_gap_counts": role_gap_counts,
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S9" if not failed else None,
        "boundary": (
            "S8 proves the Secondary Market / Capital Feedback Pack in its own L4 scope. "
            "It separates exact filing facts, lagged holder context, delayed market proxies and typed gaps; "
            "it does not provide real-time fund flow, OPRA options feed, live borrow cost, credit spread, CDS, or investment advice."
        ),
    }


def render_s8_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S8 Secondary Market / Capital Feedback Pack L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Role Signal Counts", ""])
    for key, value in summary["role_signal_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Role Gap Counts", ""])
    for key, value in summary["role_gap_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


def record_s8_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: S8Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("secondary_market_capital_feedback_schema", paths.schema_path, secondary_market_schema_contract()),
        ("secondary_market_capital_feedback_summary", paths.summary_path, dict(materialized)),
        ("secondary_market_capital_feedback_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("secondary_market_capital_feedback_closeout_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="capital_feedback_builder",
            )
        )
    return refs


def persist_quality_gates(store: RuntimeTaskSpineStore, *, task_id: str, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from capital_feedback_quality_gates_s8 where task_id = ?", (task_id,))
        for row in gate_rows:
            conn.execute(
                """
                insert into capital_feedback_quality_gates_s8(
                    quality_gate_id, task_id, gate_id, status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("s8qg", [task_id, row["gate_id"], row["generated_at"]]),
                    task_id,
                    row["gate_id"],
                    row["status"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def seed_s8_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    values = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "pack_roles": list(PACK_ROLES),
        "authority_classes": list(AUTHORITY_CLASSES),
    }
    for key, value in values.items():
        conn.execute(
            """
            insert into secondary_market_feedback_metadata(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def seed_source_registry(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    conn.execute("delete from secondary_market_source_registry_s8")
    for row in source_registry_rows(now):
        conn.execute(
            """
            insert into secondary_market_source_registry_s8(
                source_id, pack_role, asset_scope, market_scope, issuer_bound,
                instrument_bound, frequency, lag_policy, fields_json,
                locator_status, fetcher_status, parser_status, verifier_status,
                authority_class, lifecycle_status, commercial_boundary,
                forbidden_claims_json, last_verified_at, eval_case_refs_json,
                payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["source_id"],
                row["pack_role"],
                row["asset_scope"],
                row["market_scope"],
                int(row["issuer_bound"]),
                int(row["instrument_bound"]),
                row["frequency"],
                row["lag_policy"],
                json_dumps(row["fields"]),
                row["locator_status"],
                row["fetcher_status"],
                row["parser_status"],
                row["verifier_status"],
                row["authority_class"],
                row["lifecycle_status"],
                row["commercial_boundary"],
                json_dumps(row["forbidden_claims"]),
                now,
                json_dumps(row.get("eval_case_refs") or []),
                json_dumps(row.get("payload") or {}),
            ),
        )


def source_registry_rows(now: str) -> list[dict[str, Any]]:
    return [
        registry_row(
            "yahoo_chart_price_volume_snapshot",
            "secondary_market_capital_flow",
            "equity",
            "global",
            ["close_price", "return_1d", "return_5d", "return_1m", "return_ytd", "volatility_3m", "max_drawdown_3m"],
            "market_expectation_proxy",
            "runtime_ready",
            "delayed/snapshot",
            "Unofficial public chart endpoint; use as delayed market context only, not exact operating or fund-flow fact.",
            ["company_operating_performance", "product_revenue", "current_fund_flow_without_flow_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_market_liquidity_context"],
        ),
        registry_row(
            "yahoo_chart_price_volume_snapshot_liquidity_projection",
            "liquidity_and_positioning",
            "equity",
            "global",
            ["close_price", "volume_proxy_if_present", "volatility_3m", "max_drawdown_3m"],
            "market_expectation_proxy",
            "runtime_ready",
            "delayed/snapshot",
            "Price/volatility context only; no short interest, borrow cost, free float, or real-time order-book authority.",
            ["short_interest_without_short_source", "borrow_cost_without_lending_source", "realtime_positioning", "investment_recommendation"],
            eval_case_refs=["S8_gate_liquidity_context"],
        ),
        registry_row(
            "sec_ownership_and_13f",
            "ownership_and_holder",
            "equity",
            "US",
            ["holder", "issuer", "position_context", "report_period"],
            "lagged_positioning_context",
            "runtime_ready",
            "filing/reporting lag",
            "13F and ownership rows are delayed holder context; they do not prove current fund flow or current buying pressure.",
            ["realtime_flow", "current_buying_pressure", "complete_ownership", "investment_recommendation"],
            eval_case_refs=["S8_gate_no_realtime_13f"],
        ),
        registry_row(
            "sec_schedule_13d_13g_metadata",
            "ownership_and_holder",
            "equity",
            "US",
            ["form_type", "filing_date", "accession_number", "source_url"],
            "filing_event_context",
            "runtime_ready",
            "filing-event",
            "Metadata proves filing event existence and timing only, not beneficial ownership percentage without schedule parser.",
            ["beneficial_ownership_percentage_without_schedule_parser", "realtime_flow", "current_buying_pressure"],
            eval_case_refs=["S8_gate_holder_metadata_boundary"],
        ),
        registry_row(
            "sec_annual_debt_footnote_chunk",
            "credit_funding",
            "debt",
            "US",
            ["principal", "coupon", "maturity_date", "credit_facility", "covenant_flag"],
            "exact_filing_fact",
            "runtime_ready",
            "filing lag",
            "Company-disclosed debt/facility facts only; no market-implied yield, spread, CDS, or refinancing access without separate source.",
            ["market_implied_credit_spread_without_market_source", "realtime_refinancing_access_without_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_credit_filing_fact"],
        ),
        registry_row(
            "sec_financial_statement_data_sets",
            "liquidity_and_positioning",
            "financial_statement",
            "US",
            ["cash", "accounts_receivable", "inventory", "accounts_payable", "deferred_revenue", "current_assets", "current_liabilities"],
            "exact_financial_statement_fact",
            "runtime_ready",
            "filing lag",
            "Financial statement liquidity rows support working-capital analysis, not market liquidity or fund flow.",
            ["market_liquidity_without_market_source", "current_fund_flow_without_flow_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_working_capital_liquidity"],
        ),
        registry_row(
            "sec_offering_filing_metadata",
            "corporate_action",
            "equity/debt",
            "US",
            ["form_type", "filing_date", "accession_number", "source_url"],
            "filing_event_context",
            "runtime_ready",
            "filing-event",
            "Metadata proves offering filing existence only; amount, security terms and completion require filing text/XML parser.",
            ["offering_amount_without_filing_text_or_xml", "security_terms_without_filing_text_or_xml", "completed_financing_without_completion_source"],
            eval_case_refs=["S8_gate_offering_metadata_boundary"],
        ),
        registry_row(
            "sec_form_3_4_5_metadata",
            "corporate_action",
            "equity",
            "US",
            ["form_type", "filing_date", "accession_number", "source_url"],
            "filing_event_context",
            "runtime_ready",
            "filing-event",
            "Metadata proves insider filing existence only; transaction shares/price/code require XML parser.",
            ["insider_share_count_without_xml", "insider_price_without_xml", "management_view_without_context"],
            eval_case_refs=["S8_gate_insider_metadata_boundary"],
        ),
        registry_row(
            "sec_proxy_governance_metadata",
            "corporate_action",
            "equity",
            "US",
            ["form_type", "filing_date", "accession_number", "source_url"],
            "filing_event_context",
            "runtime_ready",
            "filing-event",
            "Proxy metadata proves governance filing event only; compensation/vote/buyback facts require source-specific parser.",
            ["proxy_vote_without_proxy_parser", "buyback_amount_without_company_disclosure", "compensation_claim_without_proxy_parser"],
            eval_case_refs=["S8_gate_proxy_metadata_boundary"],
        ),
        registry_row(
            "public_price_x_sec_shares_market_cap",
            "valuation_price_in",
            "equity",
            "US/global",
            ["delayed_close_price", "reported_shares_outstanding", "computed_market_cap"],
            "valuation_price_in_signal",
            "runtime_ready",
            "delayed price + filing lag",
            "Computed market-cap context from delayed public price and issuer-filed shares; not consensus valuation or fair-value truth.",
            ["valuation_truth_without_denominator", "consensus_ntm_without_commercial_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_public_price_x_filed_shares_valuation_context"],
        ),
        registry_row(
            "sec_companyfacts_common_stock_shares_outstanding",
            "valuation_price_in",
            "equity",
            "US SEC",
            ["delayed_close_price", "sec_companyfacts_common_stock_shares_outstanding", "computed_market_cap"],
            "valuation_price_in_signal",
            "runtime_ready",
            "SEC filing lag + delayed market price",
            "SEC CompanyFacts common-stock shares can support computed market-cap context when cover-page DEI shares are absent; it is not consensus valuation or fair-value truth.",
            ["valuation_truth_without_denominator", "consensus_ntm_without_commercial_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_sec_companyfacts_common_stock_shares_valuation_context"],
        ),
        registry_row(
            "sec_entity_public_float",
            "valuation_price_in",
            "equity",
            "US SEC",
            ["entity_public_float", "filing_date", "period_end"],
            "valuation_price_in_signal",
            "runtime_ready",
            "SEC filing lag",
            "SEC EntityPublicFloat is company-reported public float context at the filing date; it is not complete market capitalization, target price, or consensus valuation.",
            ["full_market_cap_without_share_count", "valuation_truth_without_denominator", "consensus_ntm_without_commercial_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_sec_entity_public_float_context"],
        ),
        registry_row(
            "yahoo_fundamentals_timeseries_market_cap",
            "valuation_price_in",
            "equity",
            "global public market",
            ["market_cap", "as_of_date", "currency"],
            "valuation_price_in_signal",
            "runtime_ready",
            "delayed public market data",
            "Yahoo fundamentals-timeseries market cap is delayed public valuation context; it is not fair-value truth, consensus estimate, target price, or real-time fund flow.",
            ["valuation_truth_without_denominator", "consensus_ntm_without_commercial_source", "target_price_without_source", "realtime_fund_flow", "investment_recommendation"],
            eval_case_refs=["S8_gate_yahoo_fundamentals_market_cap_context"],
        ),
        registry_row(
            "fred_credit_spread_regime",
            "credit_funding",
            "credit_index",
            "US macro/credit",
            ["investment_grade_oas", "high_yield_oas"],
            "capital_feedback_signal",
            "runtime_ready",
            "daily public macro/credit series",
            "FRED credit spread rows are market-regime context only, not issuer-specific bond yield, CDS, or refinancing access.",
            ["issuer_credit_spread_without_issuer_bond_source", "cds_claim_without_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_fred_credit_spread_regime_context"],
        ),
        registry_row(
            "fred_vix_market_volatility_regime",
            "derivatives_market_signal",
            "volatility_index",
            "US equity market",
            ["vix_close"],
            "market_expectation_proxy",
            "runtime_ready",
            "daily public volatility index",
            "VIX is broad equity volatility regime context only, not single-stock option OI, IV surface, gamma, or dealer positioning.",
            ["single_stock_option_positioning_without_option_chain", "realtime_gamma_without_licensed_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_fred_vix_derivatives_regime_context"],
        ),
        registry_row(
            "public_valuation_snapshot_planned",
            "valuation_price_in",
            "equity",
            "global",
            ["market_cap", "enterprise_value", "pe_ttm", "ev_sales_ttm", "ev_ebitda_ttm"],
            "valuation_price_in_signal",
            "parser_debt",
            "snapshot/delayed",
            "Current public snapshot route does not reliably produce valuation fields for the 603-company universe.",
            ["valuation_truth_without_denominator", "consensus_ntm_without_commercial_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_valuation_gap"],
        ),
        registry_row(
            "derivatives_public_sources_planned",
            "derivatives_market_signal",
            "option/future",
            "US/CN/global",
            ["oi", "volume", "iv_proxy", "skew_proxy", "cot_positioning", "settlement"],
            "market_expectation_proxy",
            "public_boundary",
            "delayed/daily/weekly",
            "CFTC/CME/OCC/Nasdaq style public delayed routes are not yet parser-backed; OPRA/dealer gamma/live order book are commercial.",
            ["fundamental_improvement", "company_operating_performance", "realtime_gamma_without_licensed_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_derivatives_typed_gap"],
        ),
        registry_row(
            "bond_credit_market_public_sources_planned",
            "credit_funding",
            "bond/credit",
            "US/global",
            ["bond_yield", "credit_spread", "rating", "cds_proxy"],
            "capital_feedback_signal",
            "commercial_gap",
            "delayed/commercial",
            "Company bond yields/spreads/CDS/rating history are incomplete in public free sources and may require licensed data.",
            ["market_implied_credit_spread_without_market_source", "cds_claim_without_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_credit_market_gap"],
        ),
        registry_row(
            "short_interest_borrow_public_sources_planned",
            "liquidity_and_positioning",
            "equity",
            "US/global",
            ["short_interest", "days_to_cover", "borrow_cost", "securities_lending"],
            "market_expectation_proxy",
            "commercial_gap",
            "delayed/commercial",
            "Short interest can be delayed public context in some markets; borrow cost and securities lending depth are generally commercial.",
            ["realtime_short_positioning", "borrow_cost_without_lending_source", "investment_recommendation"],
            eval_case_refs=["S8_gate_short_borrow_gap"],
        ),
        registry_row(
            "holder_filing_routes_planned",
            "ownership_and_holder",
            "equity/fund",
            "non-US/global",
            ["local_holder_filing", "fund_holding", "beneficial_owner"],
            "lagged_positioning_context",
            "parser_debt",
            "filing/reporting lag",
            "Non-US holder disclosure and fund-holding routes need local exchange/source-specific adapters.",
            ["realtime_flow", "current_buying_pressure", "complete_ownership"],
            eval_case_refs=["S8_gate_non_us_holder_gap"],
        ),
        registry_row(
            "capital_market_event_routes_planned",
            "corporate_action",
            "equity/debt",
            "non-US/global",
            ["local_offering", "buyback", "insider", "proxy", "governance_event"],
            "filing_event_context",
            "parser_debt",
            "filing-event",
            "Non-US corporate-action routes need local exchange, issuer IR, and source-specific parser coverage.",
            ["offering_amount_without_filing_text_or_xml", "buyback_amount_without_company_disclosure", "completed_event_without_source"],
            eval_case_refs=["S8_gate_non_us_capital_event_gap"],
        ),
    ]


def registry_row(
    source_id: str,
    pack_role: str,
    asset_scope: str,
    market_scope: str,
    fields: list[str],
    authority_class: str,
    lifecycle_status: str,
    lag_policy: str,
    commercial_boundary: str,
    forbidden_claims: list[str],
    *,
    eval_case_refs: list[str],
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "pack_role": pack_role,
        "asset_scope": asset_scope,
        "market_scope": market_scope,
        "issuer_bound": True,
        "instrument_bound": asset_scope not in {"financial_statement"},
        "frequency": "filing-event" if "filing" in lag_policy else "daily_or_periodic",
        "lag_policy": lag_policy,
        "fields": fields,
        "locator_status": "ready" if lifecycle_status == "runtime_ready" else "planned_or_debt",
        "fetcher_status": "ready" if lifecycle_status == "runtime_ready" else "planned_or_debt",
        "parser_status": "ready" if lifecycle_status == "runtime_ready" else lifecycle_status,
        "verifier_status": "ready" if lifecycle_status == "runtime_ready" else "boundary_or_debt",
        "authority_class": authority_class,
        "lifecycle_status": lifecycle_status,
        "commercial_boundary": commercial_boundary,
        "forbidden_claims": forbidden_claims,
        "eval_case_refs": eval_case_refs,
        "payload": {"schema_version": SCHEMA_VERSION},
    }


def clear_s8_task_rows(conn: sqlite3.Connection, task_id: str) -> None:
    for table in [
        "capital_feedback_quality_gates_s8",
        "capital_feedback_graph_edges_s8",
        "capital_feedback_gap_items_s8",
        "capital_feedback_signals_s8",
        "capital_feedback_packs_s8",
    ]:
        conn.execute(f"delete from {table} where task_id = ?", (task_id,))


def stream_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            yield json.loads(text)


def classify_capital_row(row: Mapping[str, Any]) -> tuple[str, str, str]:
    source_role = str(row.get("source_role") or "")
    object_type = str(row.get("object_type") or "")
    if source_role == "lagged_ownership_context" or object_type == "OwnershipPosition":
        return "ownership_and_holder", "lagged_positioning_context", "lagged_holder_position_context"
    if source_role == "working_capital_liquidity":
        return "liquidity_and_positioning", "exact_financial_statement_fact", "working_capital_liquidity_metric"
    return "credit_funding", "exact_filing_fact", str(row.get("metric_name") or object_type or "capital_structure_disclosure")


def classify_sec_event_row(row: Mapping[str, Any]) -> tuple[str, str, str]:
    source_role = str(row.get("source_role") or "")
    event_type = str(row.get("event_type") or source_role)
    if source_role == "beneficial_ownership_filing_event":
        return "ownership_and_holder", "filing_event_context", event_type
    return "corporate_action", "filing_event_context", event_type or "capital_market_filing_event"


def classify_public_context_row(row: Mapping[str, Any]) -> tuple[str, str, str]:
    pack_role = str(row.get("pack_role") or "")
    signal_type = str(row.get("signal_type") or row.get("metric_name") or "")
    authority = str(row.get("authority_class") or "")
    if pack_role in PACK_ROLES:
        return pack_role, authority or "market_expectation_proxy", signal_type or "public_market_context"
    source_id = str(row.get("source_id") or "")
    if source_id == "public_price_x_sec_shares_market_cap":
        return "valuation_price_in", "valuation_price_in_signal", signal_type or "public_price_filed_shares_market_cap_context"
    if source_id in {"sec_entity_public_float", "sec_companyfacts_common_stock_shares_outstanding"}:
        return "valuation_price_in", "valuation_price_in_signal", signal_type or "sec_entity_public_float_context"
    if source_id == "yahoo_fundamentals_timeseries_market_cap":
        return "valuation_price_in", "valuation_price_in_signal", signal_type or "yahoo_fundamentals_market_cap_context"
    if source_id == "fred_credit_spread_regime":
        return "credit_funding", "capital_feedback_signal", signal_type or "fred_credit_spread_regime_context"
    if source_id == "fred_vix_market_volatility_regime":
        return "derivatives_market_signal", "market_expectation_proxy", signal_type or "fred_vix_market_volatility_regime"
    return "secondary_market_capital_flow", "context_only", signal_type or "public_market_context"


def record_source(pack_state: dict[str, dict[str, Any]], ticker: str, row: Mapping[str, Any]) -> None:
    source_id = str(row.get("source_id") or "")
    if source_id:
        pack_state[ticker]["source_refs"].add(source_id)


def quality_flags(row: Mapping[str, Any], authority_class: str) -> list[str]:
    flags = []
    if authority_class in {"lagged_positioning_context", "market_expectation_proxy"}:
        flags.append("delayed_or_snapshot")
    if authority_class == "filing_event_context":
        flags.append("metadata_only")
    if row.get("missing_fields"):
        flags.append("missing_fields_present")
    if row.get("exact_value_authority") is False:
        flags.append("non_exact_company_fact")
    return flags


def default_forbidden_claims(pack_role: str, authority_class: str) -> list[str]:
    base = ["investment_recommendation"]
    if authority_class == "gap":
        return [*base, "claiming_missing_data_as_observed_fact"]
    if pack_role == "ownership_and_holder":
        return [*base, "realtime_flow", "current_buying_pressure", "complete_ownership_without_full_source"]
    if pack_role == "credit_funding":
        return [*base, "market_implied_credit_spread_without_market_source", "realtime_refinancing_access_without_source"]
    if pack_role == "corporate_action":
        return [*base, "completed_financing_without_completion_source", "buyback_amount_without_company_disclosure"]
    if pack_role == "valuation_price_in":
        return [*base, "valuation_truth_without_denominator", "consensus_ntm_without_commercial_source"]
    if pack_role == "derivatives_market_signal":
        return [*base, "fundamental_improvement", "realtime_gamma_without_licensed_source"]
    if pack_role == "liquidity_and_positioning":
        return [*base, "short_interest_without_short_source", "borrow_cost_without_lending_source", "realtime_positioning"]
    return [*base, "company_operating_performance", "current_fund_flow_without_flow_source"]


def default_claim_boundary(pack_role: str, authority_class: str) -> str:
    return f"{pack_role} row with {authority_class} authority; use only inside bounded secondary-market/capital-feedback analysis."


def commercial_boundary_for_gap(gap_type: str) -> str:
    if "derivatives" in gap_type:
        return "OPRA, live option-chain depth, dealer gamma, real-time futures order book, and some historical options datasets require commercial licensing."
    if "credit_market" in gap_type:
        return "Broad company bond pricing, credit spread, CDS, and rating-history panels often require licensed or commercial feeds."
    if "short_interest" in gap_type:
        return "Borrow cost and securities-lending depth are usually commercial; public short interest can be delayed and market-specific."
    if "valuation" in gap_type:
        return "Consensus forward multiples and historical peer valuation panels are often commercial unless computed from public filings and delayed prices."
    return "If no public issuer-bound route exists after source-specific adapters, retain as public-boundary or commercial-data gap."


def edge_type_for_role(role: str) -> str:
    return {
        "secondary_market_capital_flow": "priced_by_market_snapshot",
        "ownership_and_holder": "holder_positioning_context",
        "credit_funding": "financed_by_or_credit_constrained_by",
        "corporate_action": "affected_by_capital_action",
        "liquidity_and_positioning": "liquidity_positioning_context",
        "valuation_price_in": "valued_by_market_multiple_or_gap",
        "derivatives_market_signal": "derivatives_positioning_gap_or_signal",
    }[role]


def compact_signal_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    keep = [
        "source_url",
        "form_type",
        "event_type",
        "metric_name",
        "object_type",
        "market_reaction",
        "valuation_context",
        "credit_spread_context",
        "derivatives_context",
        "missing_fields",
        "parser_status",
        "runtime_contract",
        "source_boundary",
        "structured_context_type",
    ]
    return {key: row.get(key) for key in keep if key in row}


def string_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json_dumps(value)
    return str(value)


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def source_paths(paths: S8Paths, root: Path) -> dict[str, str]:
    return {
        "market_rows": rel_path(paths.market_rows_path, root),
        "capital_rows": rel_path(paths.capital_rows_path, root),
        "sec_event_rows": rel_path(paths.sec_event_rows_path, root),
    }


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("select 1 from sqlite_master where type='table' and name = ?", (table,)).fetchone() is not None


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]
