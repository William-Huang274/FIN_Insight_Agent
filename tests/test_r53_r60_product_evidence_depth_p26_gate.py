from __future__ import annotations

import json
from pathlib import Path

from sec_agent.r53_r60_pack_depth_b05_gate import build_pack_assessment_rows, load_p25_inputs
from sec_agent.r53_r60_product_evidence_depth_p26_gate import (
    build_p26_product_evidence_depth_gate,
    default_p26_paths,
)
from test_r53_r60_pack_depth_b05_gate import seed_p25_inputs


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def seed_p26_inputs(
    root: Path,
    *,
    company_count: int = 3,
    product_kpi_ready_count: int = 2,
    product_kpi_gap_count: int = 1,
    customer_ready_count: int = 3,
    customer_gap_count: int = 0,
    capital_gap_count: int = 0,
) -> None:
    manifest_dir = root / "data" / "manifests"
    product_gap_classes = {}
    if product_kpi_gap_count:
        product_gap_classes = {
            "official_product_surface_available_but_company_disclosed_product_kpi_absent": product_kpi_gap_count
        }
    _write_json(
        manifest_dir / "second_third_layer_depth_parity_summary_v0_1.json",
        {
            "status": "pass",
            "parity_status": "fail" if product_kpi_gap_count or customer_gap_count or capital_gap_count else "pass",
            "company_count": company_count,
            "checks": {"all_missing_depth_is_classified": True},
            "metrics": {
                "full_depth_target_met_company_count": company_count - max(customer_gap_count, capital_gap_count),
                "full_depth_target_gap_company_count": max(product_kpi_gap_count, customer_gap_count, capital_gap_count),
                "dimension_target_met_counts": {
                    "product_spec_depth": company_count,
                    "product_kpi_depth": product_kpi_ready_count,
                    "customer_deployment_depth": customer_ready_count,
                    "capital_market_detail_depth": company_count - capital_gap_count,
                    "market_liquidity_depth": company_count,
                },
                "dimension_gap_counts": {
                    "product_kpi_depth": product_kpi_gap_count,
                    "customer_deployment_depth": customer_gap_count,
                    "capital_market_detail_depth": capital_gap_count,
                    "product_spec_depth": 0,
                    "market_liquidity_depth": 0,
                },
                "dimension_gap_class_counts": {
                    "product_kpi_depth": product_gap_classes,
                    "customer_deployment_depth": {"customer_deployment_public_source_gap": customer_gap_count}
                    if customer_gap_count
                    else {},
                    "capital_market_detail_depth": {"capital_market_detail_source_gap": capital_gap_count}
                    if capital_gap_count
                    else {},
                },
            },
        },
    )
    _write_json(
        manifest_dir / "product_intelligence_graph_summary_v0_1.json",
        {
            "status": "pass",
            "company_count": company_count,
            "company_pack_count": company_count,
            "node_count": 12,
            "edge_count": 20,
            "gap_count": product_kpi_gap_count + customer_gap_count,
            "dangling_edge_count": 0,
            "invalid_evidence_edge_count": 0,
            "edge_type_counts": {"COMPETES_WITH": 3},
            "authority_type_counts": {"technical_fact_authority": 6},
        },
    )


def _product_pack_row(root: Path) -> dict:
    inputs = load_p25_inputs(root)
    rows = build_pack_assessment_rows(root, inputs)
    return next(row for row in rows if row["pack_id"] == "product_evidence_pack_all_universe")


def test_p26_product_kpi_exact_gap_is_claim_scope_not_product_pack_blocker(tmp_path: Path) -> None:
    seed_p26_inputs(
        tmp_path,
        company_count=3,
        product_kpi_ready_count=2,
        product_kpi_gap_count=1,
        customer_ready_count=3,
        customer_gap_count=0,
    )

    summary = build_p26_product_evidence_depth_gate(tmp_path)

    assert summary["status"] == "pass"
    assert summary["broad_full_chain_product_pack_ready"] is True
    assert summary["layer_readiness"]["product_kpi_exact_boundary"] == "ready_with_typed_exact_kpi_gaps"
    assert "p26_product_kpi_exact_typed_gap" not in summary["blocking_gap_ids"]
    product_kpi_gap = next(row for row in summary["known_gaps"] if row["gap"] == "p26_product_kpi_exact_typed_gap")
    assert product_kpi_gap["blocker_scope"] == "exact_product_kpi_claims_only"


def test_p26_customer_deployment_gap_blocks_product_pack(tmp_path: Path) -> None:
    seed_p26_inputs(
        tmp_path,
        company_count=3,
        product_kpi_ready_count=3,
        product_kpi_gap_count=0,
        customer_ready_count=2,
        customer_gap_count=1,
    )

    summary = build_p26_product_evidence_depth_gate(tmp_path)

    assert summary["status"] == "pass_with_product_pack_blocker_registered"
    assert summary["product_pack_readiness_status"] == "blocked_customer_deployment_signal_gap"
    assert summary["broad_full_chain_product_pack_ready"] is False
    assert summary["blocking_gap_ids"] == ["p26_customer_deployment_signal_gap"]


def test_p26_sql_and_artifacts_are_written(tmp_path: Path) -> None:
    seed_p26_inputs(tmp_path, customer_gap_count=1, customer_ready_count=2)

    summary = build_p26_product_evidence_depth_gate(tmp_path)
    paths = default_p26_paths(tmp_path)

    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert paths.schema_path.exists()
    assert paths.layer_rows_path.exists()
    assert paths.gap_rows_path.exists()
    assert paths.gate_rows_path.exists()
    assert paths.report_path.exists()


def test_p25_uses_p26_summary_for_product_evidence_pack(tmp_path: Path) -> None:
    seed_p25_inputs(tmp_path)
    seed_p26_inputs(
        tmp_path,
        company_count=3,
        product_kpi_ready_count=2,
        product_kpi_gap_count=1,
        customer_ready_count=3,
        customer_gap_count=0,
    )
    build_p26_product_evidence_depth_gate(tmp_path)

    product_pack = _product_pack_row(tmp_path)

    assert product_pack["readiness_status"] == "ready"
    assert product_pack["broad_full_chain_ready"] is True
    assert product_pack["evidence_summary"]["p26_layer_readiness"]["product_kpi_exact_boundary"] == (
        "ready_with_typed_exact_kpi_gaps"
    )
    assert product_pack["evidence_summary"]["legacy_depth_snapshot"]["full_depth_target_gap_company_count"] == 1


def test_p25_preserves_p26_customer_deployment_blocker(tmp_path: Path) -> None:
    seed_p25_inputs(tmp_path)
    seed_p26_inputs(
        tmp_path,
        company_count=3,
        product_kpi_ready_count=3,
        product_kpi_gap_count=0,
        customer_ready_count=2,
        customer_gap_count=1,
    )
    build_p26_product_evidence_depth_gate(tmp_path)

    product_pack = _product_pack_row(tmp_path)

    assert product_pack["readiness_status"] == "blocked_customer_deployment_signal_gap"
    assert product_pack["broad_full_chain_ready"] is False
    assert product_pack["blocker_summary"]["p26_blocking_gap_ids"] == ["p26_customer_deployment_signal_gap"]
