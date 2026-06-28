from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_retrieval_evidence_spine import (
    REQUIRED_ROUTES,
    build_s3_gate,
    default_s3_paths,
    retrieval_spine_schema_contract,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def seed_s3_fixture(root: Path) -> None:
    summaries = {
        "gold_fact_signal_mart_summary_v0_1.json": {"status": "pass", "row_count": 8, "company_count": 4, "sqlite_row_count": 8},
        "retrieval_index_registry_summary_v0_1.json": {"status": "pass", "index_snapshot_count": 7, "source_lineage_count": 7},
        "agent_runtime_consumption_contract_summary_v0_1.json": {"status": "pass", "role_evidence_pack_count": 24},
        "research_graph_summary_v0_1.json": {"status": "pass", "node_count": 100, "edge_count": 200},
        "product_intelligence_graph_summary_v0_1.json": {"status": "pass", "company_count": 4, "node_count": 50, "edge_count": 90},
        "data_quality_release_eval_gate_summary_v0_1.json": {
            "status": "pass_with_warnings",
            "release_decision": "release_allowed_with_recorded_warnings",
        },
    }
    for name, payload in summaries.items():
        write_json(root / "data" / "manifests" / name, payload)

    rows = [
        gold_row(
            "nvda_financial_revenue",
            "NVDA",
            "Nvidia",
            "exact_company_fact_authority",
            "financial_statement_fact",
            "fundamental_company_disclosure",
            "L1",
            "",
            "revenue",
            "Consolidated company",
            value="130497000000",
            unit="USD",
            period="FY2025-FY",
        ),
        gold_row(
            "amd_product_spec",
            "AMD",
            "Advanced Micro Devices",
            "bounded_thesis_driver_authority",
            "product_profile_or_spec_fact",
            "product_spec_and_capability",
            "L2",
            "technical_product_spec",
            "",
            "MI300 accelerator",
        ),
        gold_row(
            "nvda_product_spec",
            "NVDA",
            "Nvidia",
            "bounded_thesis_driver_authority",
            "product_profile_or_spec_fact",
            "product_spec_and_capability",
            "L2",
            "technical_product_spec",
            "",
            "Blackwell accelerator",
        ),
        gold_row(
            "msft_deployment_signal",
            "MSFT",
            "Microsoft",
            "bounded_thesis_driver_authority",
            "customer_deployment_or_order_signal",
            "official_customer_deployment_signal",
            "L3",
            "official_customer_case_study",
            "",
            "Azure AI infrastructure deployment",
        ),
        gold_row(
            "asml_macro_driver",
            "ASML",
            "ASML HOLDING NV",
            "bounded_thesis_driver_authority",
            "macro_industry_driver_signal",
            "macro_industry_driver",
            "L2",
            "official_industry_statistic",
            "",
            "EUV lithography demand driver",
        ),
        gold_row(
            "nvda_capital_l3",
            "NVDA",
            "Nvidia",
            "bounded_thesis_driver_authority",
            "capital_funding_ownership_fact",
            "capital_funding_ownership_market_liquidity",
            "L3",
            "lagged_ownership_context",
            "",
            "institutional ownership context",
        ),
        gold_row(
            "nvda_channel_proxy",
            "NVDA",
            "Nvidia",
            "bounded_thesis_driver_authority",
            "channel_offer_or_availability_signal",
            "channel_offer_availability_proxy",
            "L3",
            "official_channel_listing",
            "",
            "GPU channel availability proxy",
        ),
    ]
    write_jsonl(root / "data" / "manifests" / "gold_fact_signal_mart_rows_v0_1.jsonl", rows)


def gold_row(
    row_id: str,
    ticker: str,
    company_name: str,
    authority_mode: str,
    fact_domain: str,
    support_surface: str,
    source_layer: str,
    source_role: str,
    metric_family: str,
    product_or_segment: str,
    *,
    value: str = "",
    unit: str = "",
    period: str = "FY2025",
) -> dict:
    return {
        "gold_row_id": row_id,
        "ticker": ticker,
        "company_name": company_name,
        "authority_mode": authority_mode,
        "fact_domain": fact_domain,
        "support_surface": support_surface,
        "source_layer": source_layer,
        "source_role": source_role,
        "metric_family": metric_family,
        "metric_name": metric_family or "product signal",
        "product_family": product_or_segment,
        "product_or_segment": product_or_segment,
        "evidence_ref": f"fixture:{row_id}",
        "claim_boundary": "fixture authority boundary",
        "citation_span": f"{company_name} fixture citation",
        "citation_url": f"https://example.com/{row_id}",
        "source_rowset_path": "data/manifests/fixture_source.jsonl",
        "source_url": f"https://example.com/{row_id}",
        "can_enter_evidence_bundle": True,
        "value": value,
        "unit": unit,
        "period": period,
    }


def test_build_s3_gate_outputs_l4_scope_pass(tmp_path):
    seed_s3_fixture(tmp_path)
    summary = build_s3_gate(tmp_path)

    assert summary["release_decision"] == "S3_L4_scope_pass"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["retrieval_selected_evidence"] >= 2
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_s3_route_policy_and_plan_cover_all_required_routes(tmp_path):
    seed_s3_fixture(tmp_path)
    build_s3_gate(tmp_path)
    db_path = default_s3_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        route_ids = {row[0] for row in conn.execute("select route_id from retrieval_route_policy_matrix").fetchall()}
        plan_routes = json.loads(
            conn.execute("select route_ids_json from retrieval_plans where task_id = 's3_scope_task_retrieval_evidence'").fetchone()[0]
        )
        route_exec_count = conn.execute(
            "select count(*) from retrieval_route_executions where task_id = 's3_scope_task_retrieval_evidence'"
        ).fetchone()[0]

    assert set(REQUIRED_ROUTES).issubset(route_ids)
    assert set(REQUIRED_ROUTES).issubset(set(plan_routes))
    assert route_exec_count == len(REQUIRED_ROUTES)


def test_s3_selected_evidence_never_contains_planning_gap_or_raw_hit(tmp_path):
    seed_s3_fixture(tmp_path)
    build_s3_gate(tmp_path)
    db_path = default_s3_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        bad = conn.execute(
            """
            select count(*) from retrieval_selected_evidence
            where authority_mode not in ('exact_company_fact_authority','bounded_thesis_driver_authority')
               or evidence_ref = ''
            """
        ).fetchone()[0]
        dropped_reasons = {row[0] for row in conn.execute("select drop_reason from retrieval_dropped_candidates").fetchall()}

    assert bad == 0
    assert "authority_not_promotable" in dropped_reasons
    assert "duplicate_evidence_ref" in dropped_reasons


def test_s3_schema_contract_forbids_raw_retrieval_rows_to_memo():
    contract = retrieval_spine_schema_contract()

    assert contract["closeout_level"] == "L4_scope_pass"
    assert contract["policy"]["raw_retrieval_hit_cannot_enter_memo"] is True
    assert "retrieval_candidates" in contract["tables"]
    assert "retrieval_selected_evidence" in contract["tables"]


def test_s3_builder_is_rerunnable_without_deleting_append_only_workpaper_events(tmp_path):
    seed_s3_fixture(tmp_path)

    first = build_s3_gate(tmp_path)
    second = build_s3_gate(tmp_path)

    assert first["release_decision"] == "S3_L4_scope_pass"
    assert second["release_decision"] == "S3_L4_scope_pass"
    with sqlite3.connect(default_s3_paths(tmp_path).db_path) as conn:
        workpaper_events = conn.execute(
            "select count(*) from workpaper_events where task_id = 's3_scope_task_retrieval_evidence'"
        ).fetchone()[0]
        route_execs = conn.execute(
            "select count(*) from retrieval_route_executions where task_id = 's3_scope_task_retrieval_evidence'"
        ).fetchone()[0]

    assert workpaper_events == 2
    assert route_execs == len(REQUIRED_ROUTES)
