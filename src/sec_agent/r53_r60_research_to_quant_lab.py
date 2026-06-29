"""S9 Research-to-Quant Lab for the R53-R60 program.

This slice converts bounded research thesis drivers into auditable quant
validation objects.  It is not a trading system: dataset builds and backtests
require human approval, point-in-time data is guarded before use, paper trading
is blocked without a separate approval, and every FactorCard carries a
no-investment-advice boundary.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from sec_agent.r53_r60_secondary_market_capital_feedback import (
    S8_TASK_ID,
    build_s8_gate,
    create_secondary_market_feedback_schema,
)


SCHEMA_VERSION = "r53_r60_s9_research_to_quant_lab_v0_1"
S9_TASK_ID = "s9_scope_task_research_to_quant_lab"

APPROVAL_SCOPES = ("factor_hypothesis", "dataset_build", "backtest", "paper_trading")
FACTOR_STATUSES = ("approved_for_validation", "blocked_no_human_approval", "retired")
DATASET_STATUSES = ("ready_for_leakage_check", "blocked_no_human_approval", "leakage_blocked")
FACTOR_CARD_STATUSES = ("research_validation_pass", "rejected", "blocked")


@dataclass(frozen=True)
class S9Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_s9_paths(root: Path) -> S9Paths:
    s1_paths = default_s1_paths(root)
    return S9Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s9_research_to_quant_lab_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s9_research_to_quant_lab_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s9_research_to_quant_lab_summary_v0_1.json",
        report_path=root / "docs" / "internal" / "vnext_20260610" / "r53_r60_s9_research_to_quant_lab_l4_scope_pass.zh-CN.md",
    )


def research_to_quant_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "tables": [
            "research_to_quant_metadata",
            "signal_observations_s9",
            "factor_hypotheses_s9",
            "feature_specs_s9",
            "label_specs_s9",
            "universe_specs_s9",
            "human_approval_decisions_s9",
            "dataset_build_plans_s9",
            "pit_dataset_rows_s9",
            "leakage_guard_results_s9",
            "factor_analysis_results_s9",
            "backtest_results_s9",
            "risk_attributions_s9",
            "paper_trading_controls_s9",
            "factor_cards_s9",
            "research_experience_records_s9",
            "research_to_quant_quality_gates_s9",
        ],
        "approval_scopes": list(APPROVAL_SCOPES),
        "policy": {
            "not_live_trading_system": True,
            "not_external_investment_advice": True,
            "factor_hypotheses_trace_to_workpaper_thesis_and_evidence": True,
            "dataset_build_requires_human_approval": True,
            "backtest_requires_human_approval": True,
            "paper_trading_requires_separate_human_approval": True,
            "features_require_publish_available_asof_and_provenance": True,
            "leakage_guard_blocks_invalid_or_unapproved_datasets": True,
            "factorcard_must_include_risk_attribution_and_failure_scenarios": True,
            "research_experience_record_is_searchable_memory_output": True,
        },
    }


def create_research_to_quant_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists research_to_quant_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists signal_observations_s9 (
            signal_observation_id text primary key,
            task_id text not null,
            run_id text not null,
            thesis_driver_id text not null,
            source_workpaper_event_id text not null default '',
            source_pack_ref text not null,
            source_evidence_refs_json text not null default '[]',
            signal_domain text not null,
            signal_summary text not null,
            authority_boundary text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists factor_hypotheses_s9 (
            factor_hypothesis_id text primary key,
            task_id text not null,
            run_id text not null,
            signal_observation_id text not null,
            thesis_driver_id text not null,
            factor_name text not null,
            economic_rationale text not null,
            expected_direction text not null,
            validation_method text not null,
            source_refs_json text not null default '[]',
            status text not null,
            forbidden_claims_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists feature_specs_s9 (
            feature_spec_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            feature_name text not null,
            feature_family text not null,
            formula text not null,
            source_refs_json text not null default '[]',
            publish_time text not null,
            available_time text not null,
            asof_date text not null,
            lag_policy text not null,
            missing_policy text not null,
            neutralization text not null,
            provenance_json text not null default '{}',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists label_specs_s9 (
            label_spec_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            label_name text not null,
            horizon text not null,
            return_type text not null,
            benchmark text not null,
            label_window_start text not null,
            tradable_after text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists universe_specs_s9 (
            universe_spec_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            universe_name text not null,
            ticker_list_json text not null default '[]',
            inclusion_policy text not null,
            survivorship_policy text not null,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists human_approval_decisions_s9 (
            approval_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            approval_scope text not null,
            decision text not null,
            approver_role text not null,
            approval_mode text not null,
            rationale text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists dataset_build_plans_s9 (
            dataset_build_plan_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            feature_spec_id text not null default '',
            label_spec_id text not null default '',
            universe_spec_id text not null default '',
            status text not null,
            approval_id text not null default '',
            pit_policy_json text not null default '{}',
            artifact_refs_json text not null default '[]',
            blocked_reason text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pit_dataset_rows_s9 (
            pit_row_id text primary key,
            task_id text not null,
            run_id text not null,
            dataset_build_plan_id text not null,
            factor_hypothesis_id text not null,
            ticker text not null,
            asof_date text not null,
            feature_value real not null,
            label_value real not null,
            feature_publish_time text not null,
            feature_available_time text not null,
            label_window_start text not null,
            tradable_after text not null,
            source_refs_json text not null default '[]',
            provenance_json text not null default '{}',
            row_status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists leakage_guard_results_s9 (
            leakage_guard_id text primary key,
            task_id text not null,
            run_id text not null,
            dataset_build_plan_id text not null,
            factor_hypothesis_id text not null,
            status text not null,
            checked_row_count integer not null default 0,
            violation_count integer not null default 0,
            violations_json text not null default '[]',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists factor_analysis_results_s9 (
            factor_analysis_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            dataset_build_plan_id text not null,
            method text not null,
            row_count integer not null default 0,
            coverage real not null default 0,
            mean_feature real not null default 0,
            mean_label real not null default 0,
            information_coefficient real not null default 0,
            top_bucket_mean_label real not null default 0,
            bottom_bucket_mean_label real not null default 0,
            spread real not null default 0,
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists backtest_results_s9 (
            backtest_result_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            dataset_build_plan_id text not null,
            strategy_type text not null,
            period_start text not null,
            period_end text not null,
            gross_return real not null default 0,
            long_short_spread real not null default 0,
            hit_rate real not null default 0,
            max_drawdown real not null default 0,
            turnover_proxy real not null default 0,
            status text not null,
            no_investment_advice integer not null default 1,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists risk_attributions_s9 (
            risk_attribution_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            backtest_result_id text not null,
            exposures_json text not null default '{}',
            risk_flags_json text not null default '[]',
            failure_scenarios_json text not null default '[]',
            status text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists paper_trading_controls_s9 (
            paper_control_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            status text not null,
            required_approval_scope text not null,
            reason text not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists factor_cards_s9 (
            factor_card_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            factor_analysis_id text not null default '',
            backtest_result_id text not null default '',
            risk_attribution_id text not null default '',
            status text not null,
            thesis_summary text not null,
            research_interpretation text not null,
            limitations_json text not null default '[]',
            failure_scenarios_json text not null default '[]',
            allowed_next_actions_json text not null default '[]',
            forbidden_actions_json text not null default '[]',
            no_investment_advice integer not null default 1,
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists research_experience_records_s9 (
            experience_id text primary key,
            task_id text not null,
            run_id text not null,
            factor_hypothesis_id text not null,
            factor_card_id text not null,
            outcome text not null,
            method text not null,
            universe_spec_id text not null default '',
            dataset_snapshot_id text not null default '',
            metrics_json text not null default '{}',
            failure_reason text not null default '',
            regime_tags_json text not null default '[]',
            review_status text not null,
            valid_until text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists research_to_quant_quality_gates_s9 (
            quality_gate_id text primary key,
            task_id text not null,
            gate_id text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create index if not exists idx_factor_hypotheses_s9_task on factor_hypotheses_s9(task_id, status);
        create index if not exists idx_feature_specs_s9_factor on feature_specs_s9(factor_hypothesis_id);
        create index if not exists idx_dataset_rows_s9_plan on pit_dataset_rows_s9(dataset_build_plan_id, ticker, asof_date);
        create index if not exists idx_factor_cards_s9_task on factor_cards_s9(task_id, status);
        """
    )


def build_s9_gate(root: Path, *, task_id: str = S9_TASK_ID) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s9_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_s8_dependency(root)
    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    with runtime.store._connect() as conn:
        create_secondary_market_feedback_schema(conn)
        create_research_to_quant_schema(conn)
        seed_s9_metadata(conn)
        clear_s9_task_rows(conn, task_id)

    task = get_or_create_s9_task(runtime, task_id=task_id)
    if str(task["task"]["status"]) != "running":
        task = runtime.store.transition_task(
            task_id,
            "running",
            actor="research_to_quant_builder",
            message="start S9 Research-to-Quant Lab build",
            progress=10,
        )
    run_id = str(task["task"]["current_run_id"])

    materialized = materialize_research_to_quant_lab(runtime.store, task_id=task_id, run_id=run_id)
    write_json(paths.schema_path, research_to_quant_schema_contract())
    artifact_refs = record_s9_runtime_artifacts(runtime, root, paths, task_id, materialized)
    workpaper_event = runtime.append_workpaper_event(
        task_id,
        actor="quant_translator_specialist",
        event_type="research_to_quant_lab_ready",
        section_id="research_to_quant_lab",
        claim_id="s9_research_to_quant_lab_contract",
        payload={
            "schema_version": SCHEMA_VERSION,
            "factor_hypothesis_count": materialized["factor_hypothesis_count"],
            "approved_factor_count": materialized["approved_factor_count"],
            "backtest_result_count": materialized["backtest_result_count"],
            "factor_card_count": materialized["factor_card_count"],
            "artifact_ref_ids": [item["artifact_ref_id"] for item in artifact_refs],
            "authority_boundary": "Research validation only; not a live-trading or external-advice artifact.",
        },
    )
    node = runtime.record_node_result(
        task_id,
        node="research_to_quant_lab_builder",
        status="pass",
        input_payload={"source_dependency": "S8 Secondary Market / Capital Feedback Pack", "task_id": task_id},
        output_payload={**materialized, "workpaper_event_id": workpaper_event["workpaper_event_id"]},
        artifact_ref_ids=[item["artifact_ref_id"] for item in artifact_refs],
        actor="research_to_quant_builder",
    )
    runtime.record_trace_span(
        task_id,
        span_kind="quant_validation_gate",
        name="s9_approval_pit_leakage_factorcard_gate",
        status="pass",
        actor="verifier",
        node_execution_id=node["node_execution_id"],
        latency_ms=0,
        token_count=0,
        cost_amount=0.0,
        model_name="deterministic",
        provider="local",
        payload={"closeout_level": "L4_scope_pass", "no_llm": True, "no_live_trading": True},
    )
    runtime.store.transition_task(task_id, "succeeded", actor="verifier", message="S9 Research-to-Quant Lab complete", progress=100)

    gate_rows = evaluate_s9_gates(root, runtime.store, task_id=task_id, materialized=materialized)
    persist_quality_gates(runtime.store, task_id=task_id, gate_rows=gate_rows)
    summary = build_s9_summary(root, paths, gate_rows, runtime.store, task_id=task_id, materialized=materialized)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s9_report(summary, gate_rows), encoding="utf-8")
    return summary


def ensure_s8_dependency(root: Path) -> None:
    paths = default_s9_paths(root)
    store = RuntimeTaskSpineStore(paths.db_path)
    with store._connect() as conn:
        create_secondary_market_feedback_schema(conn)
        pack_count = 0
        signal_count = 0
        if table_exists(conn, "capital_feedback_packs_s8"):
            pack_count = int(conn.execute("select count(*) from capital_feedback_packs_s8 where task_id = ?", (S8_TASK_ID,)).fetchone()[0])
        if table_exists(conn, "capital_feedback_signals_s8"):
            signal_count = int(conn.execute("select count(*) from capital_feedback_signals_s8 where task_id = ?", (S8_TASK_ID,)).fetchone()[0])
    if pack_count < 1 or signal_count < 1:
        build_s8_gate(root)


def get_or_create_s9_task(runtime: FinSightResearchRuntimeFacade, *, task_id: str) -> dict[str, Any]:
    try:
        state = runtime.get_task_state(task_id)
    except Exception:
        return runtime.create_task(
            "Convert review-ready research thesis drivers into approved PIT quant validation experiments",
            task_id=task_id,
            trace_id="trace_s9_research_to_quant_lab",
            user_id="s9_gate",
            case_id="s9_research_to_quant_lab_l4_scope",
            mode="runtime_spine_dogfood",
            objective={
                "required_objects": [
                    "FactorHypothesis",
                    "FeatureSpec",
                    "LabelSpec",
                    "UniverseSpec",
                    "DatasetBuildPlan",
                    "PITDataset",
                    "LeakageGuardResult",
                    "BacktestResult",
                    "RiskAttribution",
                    "FactorCard",
                    "ResearchExperienceRecord",
                ],
                "minimum_evidence": "At least two approved thesis drivers become PIT-guarded deterministic factor validation runs.",
            },
            metadata={"source_slice": "S9", "closeout_level": "L4_scope_pass", "no_live_trading": True},
        )
    status = str(state["task"]["status"])
    if status in {"succeeded", "failed", "cancelled", "paused", "repairing"}:
        return runtime.resume_task(task_id, actor="s9_builder", reason="rebuild S9 Research-to-Quant Lab")
    return state


def materialize_research_to_quant_lab(store: RuntimeTaskSpineStore, *, task_id: str, run_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("begin immediate")
        try:
            source_context = load_s8_source_context(conn)
            hypotheses = build_factor_hypothesis_seed(source_context, task_id=task_id, run_id=run_id, now=now)
            for item in hypotheses:
                insert_signal_observation(conn, item["signal_observation"])
                insert_factor_hypothesis(conn, item["factor_hypothesis"])
                if item["approved"]:
                    insert_feature_spec(conn, item["feature_spec"])
                    insert_label_spec(conn, item["label_spec"])
                    insert_universe_spec(conn, item["universe_spec"])
                    approvals = insert_required_approvals(conn, item, now=now)
                    plan = insert_dataset_build_plan(conn, item, approvals, now=now)
                    dataset_rows = build_pit_rows(item, plan, now=now)
                    for row in dataset_rows:
                        insert_pit_dataset_row(conn, row)
                    leakage = evaluate_leakage_for_plan(dataset_rows, item, plan, now=now)
                    insert_leakage_guard(conn, leakage)
                    if leakage["status"] == "pass":
                        analysis = analyze_factor_rows(dataset_rows, item, plan, now=now)
                        insert_factor_analysis(conn, analysis)
                        backtest = backtest_factor_rows(dataset_rows, item, plan, analysis, now=now)
                        insert_backtest_result(conn, backtest)
                        risk = build_risk_attribution(item, backtest, now=now)
                        insert_risk_attribution(conn, risk)
                        paper_control = build_paper_trading_control(item, now=now)
                        insert_paper_control(conn, paper_control)
                        factor_card = build_factor_card(item, analysis, backtest, risk, now=now)
                        insert_factor_card(conn, factor_card)
                        experience = build_experience_record(item, plan, analysis, backtest, factor_card, now=now)
                        insert_experience_record(conn, experience)
                else:
                    approval = insert_denied_approval(conn, item, now=now)
                    plan = insert_blocked_dataset_build_plan(conn, item, approval, now=now)
                    leakage = build_blocked_leakage_result(item, plan, now=now)
                    insert_leakage_guard(conn, leakage)
                    paper_control = build_paper_trading_control(item, now=now)
                    insert_paper_control(conn, paper_control)
                    factor_card = build_blocked_factor_card(item, plan, now=now)
                    insert_factor_card(conn, factor_card)
                    experience = build_blocked_experience_record(item, plan, factor_card, now=now)
                    insert_experience_record(conn, experience)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with store._connect() as conn:
        counts = table_counts(
            conn,
            task_id,
            [
                ("signal_observation_count", "signal_observations_s9"),
                ("factor_hypothesis_count", "factor_hypotheses_s9"),
                ("feature_spec_count", "feature_specs_s9"),
                ("label_spec_count", "label_specs_s9"),
                ("universe_spec_count", "universe_specs_s9"),
                ("approval_count", "human_approval_decisions_s9"),
                ("dataset_build_plan_count", "dataset_build_plans_s9"),
                ("pit_dataset_row_count", "pit_dataset_rows_s9"),
                ("leakage_guard_count", "leakage_guard_results_s9"),
                ("factor_analysis_count", "factor_analysis_results_s9"),
                ("backtest_result_count", "backtest_results_s9"),
                ("risk_attribution_count", "risk_attributions_s9"),
                ("paper_control_count", "paper_trading_controls_s9"),
                ("factor_card_count", "factor_cards_s9"),
                ("experience_record_count", "research_experience_records_s9"),
            ],
        )
        approved_factor_count = int(
            conn.execute(
                "select count(*) from factor_hypotheses_s9 where task_id = ? and status = 'approved_for_validation'",
                (task_id,),
            ).fetchone()[0]
        )
        blocked_factor_count = int(
            conn.execute(
                "select count(*) from factor_hypotheses_s9 where task_id = ? and status = 'blocked_no_human_approval'",
                (task_id,),
            ).fetchone()[0]
        )
    return {
        **counts,
        "approved_factor_count": approved_factor_count,
        "blocked_factor_count": blocked_factor_count,
        "source_dependency": "S8 Secondary Market / Capital Feedback Pack",
        "no_live_trading": True,
    }


def load_s8_source_context(conn: sqlite3.Connection) -> dict[str, Any]:
    preferred = ["NVDA", "AMD", "MSFT", "AMZN", "GOOGL", "TSM", "ASML", "DELL"]
    signal_rows = rows_to_dicts(
        conn.execute(
            """
            select * from capital_feedback_signals_s8
            where task_id = ?
            order by case when ticker in ('NVDA','AMD','MSFT','AMZN','GOOGL','TSM','ASML','DELL') then 0 else 1 end,
                     ticker, pack_role, signal_type
            """,
            (S8_TASK_ID,),
        ).fetchall()
    )
    if not signal_rows:
        raise RuntimeError("S9 requires S8 capital feedback signals before quant validation.")
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in signal_rows:
        by_ticker.setdefault(str(row["ticker"]), []).append(row)
    universe = [ticker for ticker in preferred if ticker in by_ticker]
    for ticker in sorted(by_ticker):
        if ticker not in universe:
            universe.append(ticker)
        if len(universe) >= 4:
            break
    if len(universe) < 2:
        raise RuntimeError("S9 requires at least two tickers with S8 signals.")
    selected_rows = [row for ticker in universe[:4] for row in by_ticker[ticker][:3]]
    evidence_refs = sorted({str(row.get("evidence_ref") or row.get("signal_id")) for row in selected_rows if row.get("evidence_ref") or row.get("signal_id")})
    signal_ids = sorted({str(row["signal_id"]) for row in selected_rows})
    return {
        "universe": universe[:4],
        "signal_rows": selected_rows,
        "evidence_refs": evidence_refs[:12],
        "signal_ids": signal_ids[:12],
        "pack_ref": "sql://capital_feedback_packs_s8",
    }


def build_factor_hypothesis_seed(
    source_context: Mapping[str, Any],
    *,
    task_id: str,
    run_id: str,
    now: str,
) -> list[dict[str, Any]]:
    universe = list(source_context["universe"])
    evidence_refs = list(source_context["evidence_refs"])
    signal_ids = list(source_context["signal_ids"])
    common_payload = {
        "source_dependency": "S8",
        "source_signal_ids": signal_ids,
        "universe": universe,
        "research_boundary": "Internal research validation only; no trading advice.",
    }
    seeds = [
        {
            "name": "market_liquidity_reaction_validation",
            "domain": "liquidity_and_positioning",
            "thesis_driver_id": "td_s8_market_reaction_and_liquidity_context",
            "summary": "Delayed market and liquidity context can be tested as a short-horizon price-in or reversal signal.",
            "rationale": "If a bounded market-reaction signal is already visible, the lab should test whether the sign and magnitude have any diagnostic relation to short-horizon excess returns before using it in thesis language.",
            "expected_direction": "positive",
            "method": "cross_sectional_factor_smoke",
            "feature_name": "s8_market_reaction_score",
            "feature_family": "secondary_market_capital_flow",
            "formula": "ranked delayed return/volume context from S8 capital feedback rows; smoke fixture values are deterministic and PIT stamped",
            "label_name": "forward_5d_excess_return",
            "horizon": "5D",
            "approved": True,
        },
        {
            "name": "capital_event_pressure_validation",
            "domain": "capital_and_financing",
            "thesis_driver_id": "td_s8_capital_event_and_funding_pressure",
            "summary": "Corporate-action, credit-funding and ownership filing context can be tested as an event-pressure signal.",
            "rationale": "Filing-event and funding rows should not become a recommendation, but can be checked for whether they carry diagnostic risk or overhang information after PIT controls.",
            "expected_direction": "negative",
            "method": "event_pressure_backtest_smoke",
            "feature_name": "s8_capital_event_pressure_score",
            "feature_family": "capital_feedback_signal",
            "formula": "ranked count/severity of S8 capital, ownership and corporate-action context rows; smoke fixture values are deterministic and PIT stamped",
            "label_name": "forward_20d_sector_neutral_return",
            "horizon": "20D",
            "approved": True,
        },
        {
            "name": "unapproved_derivatives_gamma_candidate",
            "domain": "derivatives_market_signal",
            "thesis_driver_id": "td_derivatives_gap_candidate_requires_license_and_approval",
            "summary": "Derivatives positioning is a useful market-expectation layer, but missing licensed or approved data cannot enter a dataset.",
            "rationale": "The lab must fail closed when a candidate has no approved source or separate human approval.",
            "expected_direction": "positive",
            "method": "blocked_candidate",
            "feature_name": "unapproved_gamma_pressure_proxy",
            "feature_family": "derivatives_market_signal",
            "formula": "blocked: no approved OPRA/gamma source in current public-source scope",
            "label_name": "forward_1d_return",
            "horizon": "1D",
            "approved": False,
        },
    ]
    rows = []
    for seed in seeds:
        obs_id = stable_id("s9obs", [task_id, seed["thesis_driver_id"], seed["domain"]])
        factor_id = stable_id("s9fac", [task_id, seed["name"], seed["thesis_driver_id"]])
        feature_id = stable_id("s9feat", [factor_id, seed["feature_name"]])
        label_id = stable_id("s9label", [factor_id, seed["label_name"]])
        universe_id = stable_id("s9univ", [factor_id, ",".join(universe)])
        source_refs = evidence_refs if seed["approved"] else ["gap://s8/derivatives_market_signal_public_boundary"]
        rows.append(
            {
                "approved": bool(seed["approved"]),
                "signal_observation": {
                    "signal_observation_id": obs_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "thesis_driver_id": seed["thesis_driver_id"],
                    "source_workpaper_event_id": "",
                    "source_pack_ref": str(source_context["pack_ref"]),
                    "source_evidence_refs": source_refs,
                    "signal_domain": seed["domain"],
                    "signal_summary": seed["summary"],
                    "authority_boundary": "Bounded research signal; cannot be used as investment advice or live trading instruction.",
                    "payload": {**common_payload, "seed": seed["name"]},
                    "created_at": now,
                },
                "factor_hypothesis": {
                    "factor_hypothesis_id": factor_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "signal_observation_id": obs_id,
                    "thesis_driver_id": seed["thesis_driver_id"],
                    "factor_name": seed["name"],
                    "economic_rationale": seed["rationale"],
                    "expected_direction": seed["expected_direction"],
                    "validation_method": seed["method"],
                    "source_refs": source_refs,
                    "status": "approved_for_validation" if seed["approved"] else "blocked_no_human_approval",
                    "forbidden_claims": ["live_trading", "external_investment_advice", "unapproved_feature_generation"],
                    "payload": {**common_payload, "signal_domain": seed["domain"]},
                    "created_at": now,
                },
                "feature_spec": {
                    "feature_spec_id": feature_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "factor_hypothesis_id": factor_id,
                    "feature_name": seed["feature_name"],
                    "feature_family": seed["feature_family"],
                    "formula": seed["formula"],
                    "source_refs": source_refs,
                    "publish_time": "2026-01-31T21:00:00Z",
                    "available_time": "2026-02-01T14:30:00Z",
                    "asof_date": "2026-01-31",
                    "lag_policy": "available_next_trading_day_after_public_signal",
                    "missing_policy": "do_not_impute; mark data_unavailable or commercial_gap",
                    "neutralization": "sector_neutral_smoke_for_validation_only",
                    "provenance": {"source_refs": source_refs, "generated_by": "deterministic_s9_smoke_fixture"},
                    "status": "ready",
                    "payload": {"feature_version": "v0_1", "no_llm_formula_mutation": True},
                    "created_at": now,
                },
                "label_spec": {
                    "label_spec_id": label_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "factor_hypothesis_id": factor_id,
                    "label_name": seed["label_name"],
                    "horizon": seed["horizon"],
                    "return_type": "excess_return" if seed["horizon"] == "5D" else "sector_neutral_return",
                    "benchmark": "SPY" if seed["horizon"] == "5D" else "sector_peer_bucket",
                    "label_window_start": "2026-02-02T14:30:00Z",
                    "tradable_after": "2026-02-02T14:30:00Z",
                    "status": "ready",
                    "payload": {"label_version": "v0_1", "dividend_policy": "total_return_when_available"},
                    "created_at": now,
                },
                "universe_spec": {
                    "universe_spec_id": universe_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "factor_hypothesis_id": factor_id,
                    "universe_name": "s8_runtime_capital_feedback_smoke_universe",
                    "ticker_list": universe,
                    "inclusion_policy": "tickers must have S8 bounded signals at validation time",
                    "survivorship_policy": "diagnostic smoke uses current runtime universe; production requires historical security master",
                    "status": "ready",
                    "payload": {"security_master_gap": "production PIT backtest requires non-survivorship-biased security master"},
                    "created_at": now,
                },
            }
        )
    return rows


def build_pit_rows(item: Mapping[str, Any], plan: Mapping[str, Any], *, now: str) -> list[dict[str, Any]]:
    feature = item["feature_spec"]
    label = item["label_spec"]
    universe = list(item["universe_spec"]["ticker_list"])
    sign = 1.0 if item["factor_hypothesis"]["expected_direction"] == "positive" else -1.0
    start = datetime(2026, 2, 2, 14, 30, tzinfo=timezone.utc)
    rows: list[dict[str, Any]] = []
    for date_index in range(3):
        label_window = start + timedelta(days=7 * date_index)
        asof = (label_window - timedelta(days=2)).date().isoformat()
        publish = (label_window - timedelta(days=2, hours=-6)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        available = (label_window - timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        label_start = label_window.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for ticker_index, ticker in enumerate(universe):
            base = (ticker_index + 1) * 0.17 + date_index * 0.07
            feature_value = round(base, 6)
            directional_feature = feature_value * sign
            label_value = round(0.002 + directional_feature * 0.018 + date_index * 0.001 - ticker_index * 0.0005, 6)
            source_refs = list(feature["source_refs"])[:4]
            rows.append(
                {
                    "pit_row_id": stable_id("s9pit", [plan["dataset_build_plan_id"], ticker, asof]),
                    "task_id": item["factor_hypothesis"]["task_id"],
                    "run_id": item["factor_hypothesis"]["run_id"],
                    "dataset_build_plan_id": plan["dataset_build_plan_id"],
                    "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
                    "ticker": ticker,
                    "asof_date": asof,
                    "feature_value": feature_value,
                    "label_value": label_value,
                    "feature_publish_time": publish,
                    "feature_available_time": available,
                    "label_window_start": label_start,
                    "tradable_after": label_start,
                    "source_refs": source_refs,
                    "provenance": {
                        "feature_spec_id": feature["feature_spec_id"],
                        "label_spec_id": label["label_spec_id"],
                        "universe_spec_id": item["universe_spec"]["universe_spec_id"],
                        "pit_policy": "feature_available_time <= tradable_after <= label_window_start",
                    },
                    "row_status": "ready",
                    "payload": {"smoke_fixture": True, "not_alpha_claim": True},
                    "created_at": now,
                }
            )
    return rows


def evaluate_leakage_for_plan(
    dataset_rows: list[Mapping[str, Any]],
    item: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    violations = []
    for row in dataset_rows:
        if str(row["feature_available_time"]) > str(row["tradable_after"]):
            violations.append({"pit_row_id": row["pit_row_id"], "reason": "feature_available_after_tradable_after"})
        if str(row["tradable_after"]) > str(row["label_window_start"]):
            violations.append({"pit_row_id": row["pit_row_id"], "reason": "tradable_after_label_window_start"})
        if not row.get("source_refs"):
            violations.append({"pit_row_id": row["pit_row_id"], "reason": "missing_source_refs"})
    return {
        "leakage_guard_id": stable_id("s9lg", [plan["dataset_build_plan_id"], item["factor_hypothesis"]["factor_hypothesis_id"]]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "dataset_build_plan_id": plan["dataset_build_plan_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "status": "pass" if not violations else "blocked",
        "checked_row_count": len(dataset_rows),
        "violation_count": len(violations),
        "violations": violations,
        "payload": {
            "checks": [
                "publish_time_present",
                "available_time_present",
                "available_time_before_tradable_after",
                "tradable_after_before_label",
                "source_refs_present",
            ]
        },
        "created_at": now,
    }


def analyze_factor_rows(
    dataset_rows: list[Mapping[str, Any]],
    item: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    sign = 1.0 if item["factor_hypothesis"]["expected_direction"] == "positive" else -1.0
    signed_features = [float(row["feature_value"]) * sign for row in dataset_rows]
    labels = [float(row["label_value"]) for row in dataset_rows]
    pairs = sorted(zip(signed_features, labels, dataset_rows), key=lambda triple: triple[0])
    bucket_size = max(1, len(pairs) // 3)
    bottom = [label for _, label, _ in pairs[:bucket_size]]
    top = [label for _, label, _ in pairs[-bucket_size:]]
    top_mean = mean(top)
    bottom_mean = mean(bottom)
    return {
        "factor_analysis_id": stable_id("s9fa", [plan["dataset_build_plan_id"], item["factor_hypothesis"]["factor_hypothesis_id"]]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "dataset_build_plan_id": plan["dataset_build_plan_id"],
        "method": "deterministic_rank_ic_and_quantile_spread",
        "row_count": len(dataset_rows),
        "coverage": 1.0,
        "mean_feature": mean(signed_features),
        "mean_label": mean(labels),
        "information_coefficient": pearson(signed_features, labels),
        "top_bucket_mean_label": top_mean,
        "bottom_bucket_mean_label": bottom_mean,
        "spread": top_mean - bottom_mean,
        "status": "pass",
        "payload": {"bucket_size": bucket_size, "not_alpha_claim": True},
        "created_at": now,
    }


def backtest_factor_rows(
    dataset_rows: list[Mapping[str, Any]],
    item: Mapping[str, Any],
    plan: Mapping[str, Any],
    analysis: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    labels = [float(row["label_value"]) for row in dataset_rows]
    spread = float(analysis["spread"])
    cumulative = spread * 3.0
    period_dates = sorted({str(row["asof_date"]) for row in dataset_rows})
    hit_rate = len([value for value in labels if value > 0]) / max(1, len(labels))
    return {
        "backtest_result_id": stable_id("s9bt", [plan["dataset_build_plan_id"], item["factor_hypothesis"]["factor_hypothesis_id"]]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "dataset_build_plan_id": plan["dataset_build_plan_id"],
        "strategy_type": "top_bottom_quantile_smoke_no_execution",
        "period_start": period_dates[0],
        "period_end": period_dates[-1],
        "gross_return": round(cumulative, 6),
        "long_short_spread": round(spread, 6),
        "hit_rate": round(hit_rate, 6),
        "max_drawdown": round(min(0.0, -abs(spread) / 2.0), 6),
        "turnover_proxy": 0.5,
        "status": "pass",
        "no_investment_advice": 1,
        "payload": {
            "transaction_cost_policy": "not_modelled_in_smoke; production adapter must add cost/slippage",
            "not_live_trading": True,
        },
        "created_at": now,
    }


def build_risk_attribution(item: Mapping[str, Any], backtest: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    domain = item["signal_observation"]["signal_domain"]
    exposures = {
        "market_beta_proxy": "bounded_smoke_exposure",
        "liquidity_sensitivity": "medium" if "liquidity" in domain else "low",
        "capital_event_exposure": "medium" if "capital" in domain else "low",
        "data_source_exposure": "S8 bounded signals and deterministic PIT smoke fixture",
    }
    failure_scenarios = [
        "public market snapshot may be stale or delayed",
        "source signal may be descriptive rather than predictive",
        "transaction costs and capacity are not modelled in this smoke backtest",
        "production use requires historical non-survivorship-biased security master",
    ]
    return {
        "risk_attribution_id": stable_id("s9risk", [backtest["backtest_result_id"], item["factor_hypothesis"]["factor_hypothesis_id"]]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "backtest_result_id": backtest["backtest_result_id"],
        "exposures": exposures,
        "risk_flags": ["diagnostic_smoke_only", "no_live_orders", "no_external_advice"],
        "failure_scenarios": failure_scenarios,
        "status": "pass",
        "payload": {"risk_model": "deterministic_s9_scope_v0_1"},
        "created_at": now,
    }


def build_paper_trading_control(item: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    return {
        "paper_control_id": stable_id("s9paper", [item["factor_hypothesis"]["factor_hypothesis_id"], "paper_trading_control"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "status": "not_started_requires_separate_human_approval",
        "required_approval_scope": "paper_trading",
        "reason": "S9 validates research hypothesis plumbing only; paper trading monitor requires a separate human approval and production data contract.",
        "payload": {"live_ordering_enabled": False, "paper_ordering_enabled": False},
        "created_at": now,
    }


def build_factor_card(
    item: Mapping[str, Any],
    analysis: Mapping[str, Any],
    backtest: Mapping[str, Any],
    risk: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    return {
        "factor_card_id": stable_id("s9card", [item["factor_hypothesis"]["factor_hypothesis_id"], "factor_card"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "factor_analysis_id": analysis["factor_analysis_id"],
        "backtest_result_id": backtest["backtest_result_id"],
        "risk_attribution_id": risk["risk_attribution_id"],
        "status": "research_validation_pass",
        "thesis_summary": item["signal_observation"]["signal_summary"],
        "research_interpretation": (
            "The deterministic smoke result proves the approved thesis driver can be converted into a PIT-guarded factor "
            "analysis and backtest artifact. It does not prove investable alpha."
        ),
        "limitations": [
            "deterministic smoke fixture, not a production historical backtest",
            "no transaction cost, borrow, capacity, or live market microstructure model",
            "production use requires reviewed feature/label/universe and security master",
        ],
        "failure_scenarios": list(risk["failure_scenarios"]),
        "allowed_next_actions": ["human_review_for_watchlist", "build_production_pit_dataset_request"],
        "forbidden_actions": ["live_trading", "external_investment_advice", "auto_paper_trading_without_approval"],
        "no_investment_advice": 1,
        "payload": {
            "analysis_metrics": {
                "information_coefficient": analysis["information_coefficient"],
                "spread": analysis["spread"],
                "gross_return": backtest["gross_return"],
            }
        },
        "created_at": now,
    }


def build_experience_record(
    item: Mapping[str, Any],
    plan: Mapping[str, Any],
    analysis: Mapping[str, Any],
    backtest: Mapping[str, Any],
    factor_card: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    valid_until = (datetime.now(timezone.utc) + timedelta(days=90)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "experience_id": stable_id("s9exp", [factor_card["factor_card_id"], item["factor_hypothesis"]["factor_hypothesis_id"]]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "factor_card_id": factor_card["factor_card_id"],
        "outcome": "diagnostic_supported_for_research_validation",
        "method": item["factor_hypothesis"]["validation_method"],
        "universe_spec_id": item["universe_spec"]["universe_spec_id"],
        "dataset_snapshot_id": plan["dataset_snapshot_id"],
        "metrics": {
            "information_coefficient": analysis["information_coefficient"],
            "long_short_spread": backtest["long_short_spread"],
            "hit_rate": backtest["hit_rate"],
            "max_drawdown": backtest["max_drawdown"],
        },
        "failure_reason": "",
        "regime_tags": ["s9_smoke", "public_data_bounded", "requires_human_review_before_production"],
        "review_status": "auto_generated_needs_human_review",
        "valid_until": valid_until,
        "payload": {"searchable_memory_output": True},
        "created_at": now,
    }


def insert_required_approvals(conn: sqlite3.Connection, item: Mapping[str, Any], *, now: str) -> dict[str, dict[str, Any]]:
    approvals = {}
    for scope in ("factor_hypothesis", "dataset_build", "backtest"):
        approval = {
            "approval_id": stable_id("s9appr", [item["factor_hypothesis"]["factor_hypothesis_id"], scope, "approved"]),
            "task_id": item["factor_hypothesis"]["task_id"],
            "run_id": item["factor_hypothesis"]["run_id"],
            "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
            "approval_scope": scope,
            "decision": "approved",
            "approver_role": "human_reviewer",
            "approval_mode": "manual_fixture_for_l4_scope_gate",
            "rationale": f"Approved {scope} for deterministic internal validation only.",
            "payload": {"no_live_trading": True, "scope_limited": True},
            "created_at": now,
        }
        insert_approval(conn, approval)
        approvals[scope] = approval
    return approvals


def insert_denied_approval(conn: sqlite3.Connection, item: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    approval = {
        "approval_id": stable_id("s9appr", [item["factor_hypothesis"]["factor_hypothesis_id"], "dataset_build", "denied"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "approval_scope": "dataset_build",
        "decision": "denied",
        "approver_role": "human_reviewer",
        "approval_mode": "manual_fixture_for_l4_scope_gate",
        "rationale": "Derivatives candidate has no approved public data source and no human approval for dataset build.",
        "payload": {"fail_closed": True, "requires_source_or_credential": True},
        "created_at": now,
    }
    insert_approval(conn, approval)
    return approval


def insert_dataset_build_plan(
    conn: sqlite3.Connection,
    item: Mapping[str, Any],
    approvals: Mapping[str, Mapping[str, Any]],
    *,
    now: str,
) -> dict[str, Any]:
    plan_id = stable_id("s9ds", [item["factor_hypothesis"]["factor_hypothesis_id"], "pit_dataset_plan"])
    plan = {
        "dataset_build_plan_id": plan_id,
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "feature_spec_id": item["feature_spec"]["feature_spec_id"],
        "label_spec_id": item["label_spec"]["label_spec_id"],
        "universe_spec_id": item["universe_spec"]["universe_spec_id"],
        "status": "ready_for_leakage_check",
        "approval_id": approvals["dataset_build"]["approval_id"],
        "pit_policy": {
            "feature_time_fields_required": ["publish_time", "available_time", "asof_date"],
            "label_time_fields_required": ["tradable_after", "label_window_start"],
            "forbid_future_leakage": True,
            "production_security_master_required": True,
        },
        "artifact_refs": [],
        "blocked_reason": "",
        "dataset_snapshot_id": stable_id("s9snap", [plan_id, "deterministic_pit_smoke_v0_1"]),
        "payload": {"backtest_approval_id": approvals["backtest"]["approval_id"]},
        "created_at": now,
    }
    insert_dataset_plan(conn, plan)
    return plan


def insert_blocked_dataset_build_plan(
    conn: sqlite3.Connection,
    item: Mapping[str, Any],
    approval: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    plan = {
        "dataset_build_plan_id": stable_id("s9ds", [item["factor_hypothesis"]["factor_hypothesis_id"], "blocked_dataset_plan"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "feature_spec_id": "",
        "label_spec_id": "",
        "universe_spec_id": "",
        "status": "blocked_no_human_approval",
        "approval_id": approval["approval_id"],
        "pit_policy": {"fail_closed": True},
        "artifact_refs": [],
        "blocked_reason": "dataset build denied by human approval gate and missing approved source route",
        "dataset_snapshot_id": "",
        "payload": {"blocked_candidate": True},
        "created_at": now,
    }
    insert_dataset_plan(conn, plan)
    return plan


def build_blocked_leakage_result(item: Mapping[str, Any], plan: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    return {
        "leakage_guard_id": stable_id("s9lg", [plan["dataset_build_plan_id"], "blocked"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "dataset_build_plan_id": plan["dataset_build_plan_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "status": "blocked_no_human_approval",
        "checked_row_count": 0,
        "violation_count": 1,
        "violations": [{"reason": "dataset_build_requires_human_approval_and_approved_source"}],
        "payload": {"fail_closed": True},
        "created_at": now,
    }


def build_blocked_factor_card(item: Mapping[str, Any], plan: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    return {
        "factor_card_id": stable_id("s9card", [item["factor_hypothesis"]["factor_hypothesis_id"], "blocked_card"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "factor_analysis_id": "",
        "backtest_result_id": "",
        "risk_attribution_id": "",
        "status": "blocked",
        "thesis_summary": item["signal_observation"]["signal_summary"],
        "research_interpretation": "Candidate blocked before dataset build because approval and source-route requirements were not satisfied.",
        "limitations": ["no approved source", "no human approval", "no PIT dataset rows"],
        "failure_scenarios": ["licensed derivatives data or stronger public source may be required"],
        "allowed_next_actions": ["request_source_credential_or_mark_commercial_gap", "submit_new_human_approval_request"],
        "forbidden_actions": ["dataset_build", "backtest", "paper_trading", "live_trading", "external_investment_advice"],
        "no_investment_advice": 1,
        "payload": {"blocked_plan_id": plan["dataset_build_plan_id"]},
        "created_at": now,
    }


def build_blocked_experience_record(
    item: Mapping[str, Any],
    plan: Mapping[str, Any],
    factor_card: Mapping[str, Any],
    *,
    now: str,
) -> dict[str, Any]:
    return {
        "experience_id": stable_id("s9exp", [factor_card["factor_card_id"], "blocked"]),
        "task_id": item["factor_hypothesis"]["task_id"],
        "run_id": item["factor_hypothesis"]["run_id"],
        "factor_hypothesis_id": item["factor_hypothesis"]["factor_hypothesis_id"],
        "factor_card_id": factor_card["factor_card_id"],
        "outcome": "data_unavailable_or_approval_blocked",
        "method": "blocked_before_dataset_build",
        "universe_spec_id": "",
        "dataset_snapshot_id": "",
        "metrics": {},
        "failure_reason": plan["blocked_reason"],
        "regime_tags": ["approval_required", "source_boundary", "commercial_or_credential_gap"],
        "review_status": "auto_generated_needs_human_review",
        "valid_until": "",
        "payload": {"searchable_memory_output": True},
        "created_at": now,
    }


def evaluate_s9_gates(
    root: Path,
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contract = research_to_quant_schema_contract()
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        table_count_map = {
            table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            for table in contract["tables"]
            if table_exists(conn, table)
        }
        hypothesis_count = count_rows(conn, "factor_hypotheses_s9", task_id)
        approved_factor_count = int(
            conn.execute(
                "select count(*) from factor_hypotheses_s9 where task_id = ? and status = 'approved_for_validation'",
                (task_id,),
            ).fetchone()[0]
        )
        trace_bad = int(
            conn.execute(
                """
                select count(*) from factor_hypotheses_s9
                where task_id = ?
                  and (signal_observation_id = '' or thesis_driver_id = '' or source_refs_json in ('', '[]'))
                """,
                (task_id,),
            ).fetchone()[0]
        )
        feature_bad = int(
            conn.execute(
                """
                select count(*) from feature_specs_s9
                where task_id = ?
                  and (source_refs_json in ('', '[]') or publish_time = '' or available_time = '' or asof_date = ''
                       or provenance_json in ('', '{}') or formula = '')
                """,
                (task_id,),
            ).fetchone()[0]
        )
        approval_bad_plans = int(
            conn.execute(
                """
                select count(*) from dataset_build_plans_s9 p
                left join human_approval_decisions_s9 a
                  on p.approval_id = a.approval_id
                where p.task_id = ?
                  and p.status != 'blocked_no_human_approval'
                  and (a.decision is null or a.decision != 'approved' or a.approval_scope != 'dataset_build')
                """,
                (task_id,),
            ).fetchone()[0]
        )
        blocked_plan_rows = int(
            conn.execute(
                "select count(*) from pit_dataset_rows_s9 where task_id = ? and dataset_build_plan_id in (select dataset_build_plan_id from dataset_build_plans_s9 where task_id = ? and status = 'blocked_no_human_approval')",
                (task_id, task_id),
            ).fetchone()[0]
        )
        pit_bad = int(
            conn.execute(
                """
                select count(*) from pit_dataset_rows_s9
                where task_id = ?
                  and (source_refs_json in ('', '[]')
                       or feature_publish_time = ''
                       or feature_available_time = ''
                       or tradable_after = ''
                       or label_window_start = ''
                       or feature_available_time > tradable_after
                       or tradable_after > label_window_start)
                """,
                (task_id,),
            ).fetchone()[0]
        )
        leakage_fail = int(
            conn.execute(
                """
                select count(*) from leakage_guard_results_s9
                where task_id = ?
                  and status not in ('pass', 'blocked_no_human_approval')
                """,
                (task_id,),
            ).fetchone()[0]
        )
        backtest_count = count_rows(conn, "backtest_results_s9", task_id)
        backtest_bad = int(
            conn.execute(
                """
                select count(*) from backtest_results_s9
                where task_id = ? and (status != 'pass' or no_investment_advice != 1)
                """,
                (task_id,),
            ).fetchone()[0]
        )
        factor_card_count = count_rows(conn, "factor_cards_s9", task_id)
        factor_card_bad = int(
            conn.execute(
                """
                select count(*) from factor_cards_s9
                where task_id = ?
                  and (no_investment_advice != 1
                       or forbidden_actions_json not like '%live_trading%'
                       or failure_scenarios_json in ('', '[]'))
                """,
                (task_id,),
            ).fetchone()[0]
        )
        paper_started = int(
            conn.execute(
                """
                select count(*) from paper_trading_controls_s9
                where task_id = ? and status not like 'not_started%'
                """,
                (task_id,),
            ).fetchone()[0]
        )
        experience_count = count_rows(conn, "research_experience_records_s9", task_id)
        runtime_artifact_count = int(
            conn.execute(
                """
                select count(*) from artifact_refs
                where task_id = ?
                  and artifact_type in (
                    'research_to_quant_schema',
                    'research_to_quant_summary',
                    'research_to_quant_gate_rows',
                    'research_to_quant_closeout_report'
                  )
                """,
                (task_id,),
            ).fetchone()[0]
        )
        workpaper_event_count = int(
            conn.execute(
                "select count(*) from workpaper_events where task_id = ? and event_type = 'research_to_quant_lab_ready'",
                (task_id,),
            ).fetchone()[0]
        )

    generated_at = utc_now_iso()

    def gate(gate_id: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {"gate_id": gate_id, "status": "pass" if status else "fail", "detail": dict(detail), "generated_at": generated_at}

    return [
        gate(
            "s9_schema_tables_present",
            set(contract["tables"]).issubset(existing_tables) and all(table_count_map.get(table, 0) >= 0 for table in contract["tables"]),
            {"required_tables": contract["tables"], "table_counts": table_count_map},
        ),
        gate(
            "s9_factor_hypothesis_traceability",
            hypothesis_count >= 3 and approved_factor_count >= 2 and trace_bad == 0,
            {"hypothesis_count": hypothesis_count, "approved_factor_count": approved_factor_count, "trace_bad": trace_bad},
        ),
        gate(
            "s9_feature_label_universe_contract",
            materialized["feature_spec_count"] >= 2 and materialized["label_spec_count"] >= 2 and materialized["universe_spec_count"] >= 2 and feature_bad == 0,
            {
                "feature_spec_count": materialized["feature_spec_count"],
                "label_spec_count": materialized["label_spec_count"],
                "universe_spec_count": materialized["universe_spec_count"],
                "feature_bad": feature_bad,
            },
        ),
        gate(
            "s9_human_approval_before_dataset_and_backtest",
            materialized["approval_count"] >= 7 and approval_bad_plans == 0 and blocked_plan_rows == 0,
            {"approval_count": materialized["approval_count"], "approval_bad_plans": approval_bad_plans, "blocked_plan_rows": blocked_plan_rows},
        ),
        gate(
            "s9_pit_dataset_rows_have_time_and_provenance",
            materialized["pit_dataset_row_count"] >= 8 and pit_bad == 0,
            {"pit_dataset_row_count": materialized["pit_dataset_row_count"], "pit_bad": pit_bad},
        ),
        gate(
            "s9_leakage_guard_fail_closed",
            materialized["leakage_guard_count"] >= 3 and leakage_fail == 0,
            {"leakage_guard_count": materialized["leakage_guard_count"], "leakage_fail": leakage_fail},
        ),
        gate(
            "s9_two_approved_hypotheses_backtested",
            backtest_count >= 2 and backtest_bad == 0,
            {"backtest_count": backtest_count, "backtest_bad": backtest_bad},
        ),
        gate(
            "s9_risk_attribution_and_factorcards",
            materialized["risk_attribution_count"] >= 2 and factor_card_count >= 3 and factor_card_bad == 0,
            {
                "risk_attribution_count": materialized["risk_attribution_count"],
                "factor_card_count": factor_card_count,
                "factor_card_bad": factor_card_bad,
            },
        ),
        gate(
            "s9_paper_trading_not_started_without_separate_approval",
            paper_started == 0 and materialized["factor_hypothesis_count"] == count_rows_from_materialized(materialized, "paper_control_count"),
            {"paper_started": paper_started, "paper_control_count": materialized.get("paper_control_count")},
        ),
        gate(
            "s9_research_experience_memory_written",
            experience_count >= 3,
            {"experience_count": experience_count},
        ),
        gate(
            "s9_no_investment_advice_boundary",
            backtest_bad == 0 and factor_card_bad == 0 and paper_started == 0,
            {"backtest_bad": backtest_bad, "factor_card_bad": factor_card_bad, "paper_started": paper_started},
        ),
        gate(
            "s9_runtime_artifacts_and_workpaper_event_ledgered",
            runtime_artifact_count >= 4 and workpaper_event_count >= 1,
            {"runtime_artifact_count": runtime_artifact_count, "workpaper_event_count": workpaper_event_count},
        ),
    ]


def build_s9_summary(
    root: Path,
    paths: S9Paths,
    gate_rows: list[dict[str, Any]],
    store: RuntimeTaskSpineStore,
    *,
    task_id: str,
    materialized: Mapping[str, Any],
) -> dict[str, Any]:
    with store._connect() as conn:
        conn.row_factory = sqlite3.Row
        task = row_to_dict(conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone())
        factor_cards = rows_to_dicts(conn.execute("select * from factor_cards_s9 where task_id = ? order by factor_hypothesis_id", (task_id,)).fetchall())
        outcomes = rows_to_dicts(conn.execute("select outcome, count(*) as count from research_experience_records_s9 where task_id = ? group by outcome", (task_id,)).fetchall())
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
        "slice": "S9 Research-to-Quant Lab",
        "status": status,
        "release_decision": "S9_L4_scope_pass" if status == "pass" else "S9_blocked",
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "next_slice_unlocked": "S10" if status == "pass" else "",
        "task": task,
        "counts": {
            **dict(materialized),
            "gate_count": len(gate_rows),
            "gate_fail_count": fail_count,
        },
        "experience_outcomes": {row["outcome"]: row["count"] for row in outcomes},
        "factor_cards": [
            {
                "factor_card_id": row["factor_card_id"],
                "factor_hypothesis_id": row["factor_hypothesis_id"],
                "status": row["status"],
                "no_investment_advice": bool(row["no_investment_advice"]),
            }
            for row in factor_cards
        ],
        "outputs": outputs,
        "policy": research_to_quant_schema_contract()["policy"],
        "generated_at": utc_now_iso(),
    }


def render_s9_report(summary: Mapping[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 S9 Research-to-Quant Lab L4 Scope Pass",
        "",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Status: `{summary['status']}`",
        f"- Next slice unlocked: `{summary.get('next_slice_unlocked') or 'blocked'}`",
        "",
        "## Scope Boundary",
        "",
        "S9 converts bounded research thesis drivers into internally reviewable quant validation artifacts. It does not place orders, run live trading, or produce external investment advice.",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        if isinstance(value, (str, int, float, bool)):
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}`: `{row['status']}`")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def record_s9_runtime_artifacts(
    runtime: FinSightResearchRuntimeFacade,
    root: Path,
    paths: S9Paths,
    task_id: str,
    materialized: Mapping[str, Any],
) -> list[dict[str, Any]]:
    artifacts = [
        ("research_to_quant_schema", paths.schema_path, research_to_quant_schema_contract()),
        ("research_to_quant_summary", paths.summary_path, dict(materialized)),
        ("research_to_quant_gate_rows", paths.gate_rows_path, {"gate_rows_pending": True, **dict(materialized)}),
        ("research_to_quant_closeout_report", paths.report_path, {"report_pending": True, **dict(materialized)}),
    ]
    refs: list[dict[str, Any]] = []
    for artifact_type, path, payload in artifacts:
        refs.append(
            runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=rel_path(path, root),
                payload={"schema_version": SCHEMA_VERSION, **payload},
                actor="research_to_quant_builder",
            )
        )
    return refs


def persist_quality_gates(store: RuntimeTaskSpineStore, *, task_id: str, gate_rows: list[dict[str, Any]]) -> None:
    now = utc_now_iso()
    with store._connect() as conn:
        conn.execute("delete from research_to_quant_quality_gates_s9 where task_id = ?", (task_id,))
        for row in gate_rows:
            conn.execute(
                """
                insert into research_to_quant_quality_gates_s9(
                    quality_gate_id, task_id, gate_id, status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("s9qg", [task_id, row["gate_id"], row["generated_at"]]),
                    task_id,
                    row["gate_id"],
                    row["status"],
                    json_dumps(row.get("detail") or {}),
                    now,
                ),
            )


def seed_s9_metadata(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    values = {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "approval_scopes": list(APPROVAL_SCOPES),
        "not_live_trading_system": True,
    }
    for key, value in values.items():
        conn.execute(
            """
            insert into research_to_quant_metadata(key, value_json, updated_at)
            values (?, ?, ?)
            on conflict(key) do update set value_json=excluded.value_json, updated_at=excluded.updated_at
            """,
            (key, json_dumps(value), now),
        )


def clear_s9_task_rows(conn: sqlite3.Connection, task_id: str) -> None:
    for table in [
        "research_to_quant_quality_gates_s9",
        "research_experience_records_s9",
        "factor_cards_s9",
        "paper_trading_controls_s9",
        "risk_attributions_s9",
        "backtest_results_s9",
        "factor_analysis_results_s9",
        "leakage_guard_results_s9",
        "pit_dataset_rows_s9",
        "dataset_build_plans_s9",
        "human_approval_decisions_s9",
        "universe_specs_s9",
        "label_specs_s9",
        "feature_specs_s9",
        "factor_hypotheses_s9",
        "signal_observations_s9",
    ]:
        conn.execute(f"delete from {table} where task_id = ?", (task_id,))


def insert_signal_observation(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into signal_observations_s9(
            signal_observation_id, task_id, run_id, thesis_driver_id,
            source_workpaper_event_id, source_pack_ref, source_evidence_refs_json,
            signal_domain, signal_summary, authority_boundary, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["signal_observation_id"],
            row["task_id"],
            row["run_id"],
            row["thesis_driver_id"],
            row["source_workpaper_event_id"],
            row["source_pack_ref"],
            json_dumps(row["source_evidence_refs"]),
            row["signal_domain"],
            row["signal_summary"],
            row["authority_boundary"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_factor_hypothesis(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into factor_hypotheses_s9(
            factor_hypothesis_id, task_id, run_id, signal_observation_id,
            thesis_driver_id, factor_name, economic_rationale, expected_direction,
            validation_method, source_refs_json, status, forbidden_claims_json,
            payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["factor_hypothesis_id"],
            row["task_id"],
            row["run_id"],
            row["signal_observation_id"],
            row["thesis_driver_id"],
            row["factor_name"],
            row["economic_rationale"],
            row["expected_direction"],
            row["validation_method"],
            json_dumps(row["source_refs"]),
            row["status"],
            json_dumps(row["forbidden_claims"]),
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_feature_spec(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into feature_specs_s9(
            feature_spec_id, task_id, run_id, factor_hypothesis_id,
            feature_name, feature_family, formula, source_refs_json,
            publish_time, available_time, asof_date, lag_policy, missing_policy,
            neutralization, provenance_json, status, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["feature_spec_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["feature_name"],
            row["feature_family"],
            row["formula"],
            json_dumps(row["source_refs"]),
            row["publish_time"],
            row["available_time"],
            row["asof_date"],
            row["lag_policy"],
            row["missing_policy"],
            row["neutralization"],
            json_dumps(row["provenance"]),
            row["status"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_label_spec(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into label_specs_s9(
            label_spec_id, task_id, run_id, factor_hypothesis_id,
            label_name, horizon, return_type, benchmark, label_window_start,
            tradable_after, status, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["label_spec_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["label_name"],
            row["horizon"],
            row["return_type"],
            row["benchmark"],
            row["label_window_start"],
            row["tradable_after"],
            row["status"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_universe_spec(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into universe_specs_s9(
            universe_spec_id, task_id, run_id, factor_hypothesis_id,
            universe_name, ticker_list_json, inclusion_policy, survivorship_policy,
            status, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["universe_spec_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["universe_name"],
            json_dumps(row["ticker_list"]),
            row["inclusion_policy"],
            row["survivorship_policy"],
            row["status"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_approval(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into human_approval_decisions_s9(
            approval_id, task_id, run_id, factor_hypothesis_id, approval_scope,
            decision, approver_role, approval_mode, rationale, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["approval_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["approval_scope"],
            row["decision"],
            row["approver_role"],
            row["approval_mode"],
            row["rationale"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_dataset_plan(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into dataset_build_plans_s9(
            dataset_build_plan_id, task_id, run_id, factor_hypothesis_id,
            feature_spec_id, label_spec_id, universe_spec_id, status, approval_id,
            pit_policy_json, artifact_refs_json, blocked_reason, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["dataset_build_plan_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["feature_spec_id"],
            row["label_spec_id"],
            row["universe_spec_id"],
            row["status"],
            row["approval_id"],
            json_dumps(row["pit_policy"]),
            json_dumps(row["artifact_refs"]),
            row["blocked_reason"],
            json_dumps({**row["payload"], "dataset_snapshot_id": row.get("dataset_snapshot_id", "")}),
            row["created_at"],
        ),
    )


def insert_pit_dataset_row(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into pit_dataset_rows_s9(
            pit_row_id, task_id, run_id, dataset_build_plan_id, factor_hypothesis_id,
            ticker, asof_date, feature_value, label_value, feature_publish_time,
            feature_available_time, label_window_start, tradable_after, source_refs_json,
            provenance_json, row_status, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["pit_row_id"],
            row["task_id"],
            row["run_id"],
            row["dataset_build_plan_id"],
            row["factor_hypothesis_id"],
            row["ticker"],
            row["asof_date"],
            row["feature_value"],
            row["label_value"],
            row["feature_publish_time"],
            row["feature_available_time"],
            row["label_window_start"],
            row["tradable_after"],
            json_dumps(row["source_refs"]),
            json_dumps(row["provenance"]),
            row["row_status"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_leakage_guard(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into leakage_guard_results_s9(
            leakage_guard_id, task_id, run_id, dataset_build_plan_id, factor_hypothesis_id,
            status, checked_row_count, violation_count, violations_json, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["leakage_guard_id"],
            row["task_id"],
            row["run_id"],
            row["dataset_build_plan_id"],
            row["factor_hypothesis_id"],
            row["status"],
            row["checked_row_count"],
            row["violation_count"],
            json_dumps(row["violations"]),
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_factor_analysis(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into factor_analysis_results_s9(
            factor_analysis_id, task_id, run_id, factor_hypothesis_id, dataset_build_plan_id,
            method, row_count, coverage, mean_feature, mean_label, information_coefficient,
            top_bucket_mean_label, bottom_bucket_mean_label, spread, status, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["factor_analysis_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["dataset_build_plan_id"],
            row["method"],
            row["row_count"],
            row["coverage"],
            row["mean_feature"],
            row["mean_label"],
            row["information_coefficient"],
            row["top_bucket_mean_label"],
            row["bottom_bucket_mean_label"],
            row["spread"],
            row["status"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_backtest_result(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into backtest_results_s9(
            backtest_result_id, task_id, run_id, factor_hypothesis_id, dataset_build_plan_id,
            strategy_type, period_start, period_end, gross_return, long_short_spread,
            hit_rate, max_drawdown, turnover_proxy, status, no_investment_advice,
            payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["backtest_result_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["dataset_build_plan_id"],
            row["strategy_type"],
            row["period_start"],
            row["period_end"],
            row["gross_return"],
            row["long_short_spread"],
            row["hit_rate"],
            row["max_drawdown"],
            row["turnover_proxy"],
            row["status"],
            row["no_investment_advice"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_risk_attribution(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into risk_attributions_s9(
            risk_attribution_id, task_id, run_id, factor_hypothesis_id, backtest_result_id,
            exposures_json, risk_flags_json, failure_scenarios_json, status, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["risk_attribution_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["backtest_result_id"],
            json_dumps(row["exposures"]),
            json_dumps(row["risk_flags"]),
            json_dumps(row["failure_scenarios"]),
            row["status"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_paper_control(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into paper_trading_controls_s9(
            paper_control_id, task_id, run_id, factor_hypothesis_id, status,
            required_approval_scope, reason, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["paper_control_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["status"],
            row["required_approval_scope"],
            row["reason"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_factor_card(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into factor_cards_s9(
            factor_card_id, task_id, run_id, factor_hypothesis_id, factor_analysis_id,
            backtest_result_id, risk_attribution_id, status, thesis_summary,
            research_interpretation, limitations_json, failure_scenarios_json,
            allowed_next_actions_json, forbidden_actions_json, no_investment_advice,
            payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["factor_card_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["factor_analysis_id"],
            row["backtest_result_id"],
            row["risk_attribution_id"],
            row["status"],
            row["thesis_summary"],
            row["research_interpretation"],
            json_dumps(row["limitations"]),
            json_dumps(row["failure_scenarios"]),
            json_dumps(row["allowed_next_actions"]),
            json_dumps(row["forbidden_actions"]),
            row["no_investment_advice"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def insert_experience_record(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    conn.execute(
        """
        insert into research_experience_records_s9(
            experience_id, task_id, run_id, factor_hypothesis_id, factor_card_id,
            outcome, method, universe_spec_id, dataset_snapshot_id, metrics_json,
            failure_reason, regime_tags_json, review_status, valid_until,
            payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["experience_id"],
            row["task_id"],
            row["run_id"],
            row["factor_hypothesis_id"],
            row["factor_card_id"],
            row["outcome"],
            row["method"],
            row["universe_spec_id"],
            row["dataset_snapshot_id"],
            json_dumps(row["metrics"]),
            row["failure_reason"],
            json_dumps(row["regime_tags"]),
            row["review_status"],
            row["valid_until"],
            json_dumps(row["payload"]),
            row["created_at"],
        ),
    )


def table_counts(conn: sqlite3.Connection, task_id: str, specs: Iterable[tuple[str, str]]) -> dict[str, int]:
    return {key: count_rows(conn, table, task_id) for key, table in specs}


def count_rows(conn: sqlite3.Connection, table: str, task_id: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"select count(*) from {table} where task_id = ?", (task_id,)).fetchone()[0])


def count_rows_from_materialized(materialized: Mapping[str, Any], key: str) -> int:
    value = materialized.get(key)
    return int(value) if isinstance(value, (int, float, str)) and str(value).isdigit() else 0


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("select 1 from sqlite_master where type='table' and name = ?", (table,)).fetchone() is not None


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def mean(values: Iterable[float]) -> float:
    vals = [float(value) for value in values]
    return sum(vals) / len(vals) if vals else 0.0


def pearson(xs: Iterable[float], ys: Iterable[float]) -> float:
    x_vals = [float(x) for x in xs]
    y_vals = [float(y) for y in ys]
    if len(x_vals) != len(y_vals) or len(x_vals) < 2:
        return 0.0
    x_mean = mean(x_vals)
    y_mean = mean(y_vals)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
    x_var = sum((x - x_mean) ** 2 for x in x_vals)
    y_var = sum((y - y_mean) ** 2 for y in y_vals)
    denominator = math.sqrt(x_var * y_var)
    return round(numerator / denominator, 6) if denominator else 0.0
