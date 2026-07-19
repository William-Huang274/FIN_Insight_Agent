from __future__ import annotations

from sec_agent.p34_lane_quality_runtime import (
    NORMALIZED_RUNTIME_ROW_FIELDS,
    P34_PRIORITY_ADAPTER_FAMILIES,
    build_ai_semis_adapter_fixture_report,
)


def test_p34_adapter_fixtures_cover_priority_families() -> None:
    report = build_ai_semis_adapter_fixture_report()
    families = {row["adapter_family"] for row in report["family_results"]}

    assert report["schema_version"] == "fin_insight_p34_ai_semis_adapter_fixture_report_v0_1"
    assert report["status"] == "adapter_fixture_parser_contract_pass_live_fetch_pending"
    assert families == set(P34_PRIORITY_ADAPTER_FAMILIES)
    assert report["metrics"]["adapter_family_count"] == 3
    assert report["metrics"]["fixture_count"] == 9


def test_p34_adapter_fixtures_emit_normalized_rows_with_lineage() -> None:
    report = build_ai_semis_adapter_fixture_report()

    assert report["metrics"]["runtime_row_count"] >= 9
    assert report["metrics"]["typed_gap_count"] == 0
    for row in report["runtime_rows"]:
        for field in NORMALIZED_RUNTIME_ROW_FIELDS:
            assert field in row
            assert row[field] not in ("", [], None)
        assert row["parser_lineage"]["adapter_family"] in P34_PRIORITY_ADAPTER_FAMILIES
        assert row["promotion_status"] == "fixture_parser_contract_pass_live_fetch_pending"


def test_p34_adapter_fixtures_preserve_quality_boundaries() -> None:
    report = build_ai_semis_adapter_fixture_report()
    rows_by_id = {row["row_id"]: row for row in report["runtime_rows"]}

    assert rows_by_id["p34_fixture_row::dell_fy26_ai_orders_shipments_backlog"]["authority_scope"] == (
        "issuer_exact_operating_metric_with_margin_gap"
    )
    assert "AI server gross margin" in rows_by_id["p34_fixture_row::dell_fy26_ai_orders_shipments_backlog"]["cannot_infer"]
    assert rows_by_id["p34_fixture_row::nvda_gb200_nvl72_architecture"]["authority_scope"] == (
        "official_technical_fact_not_revenue_or_share"
    )
    assert "GB200 SKU revenue" in rows_by_id["p34_fixture_row::nvda_gb200_nvl72_architecture"]["cannot_infer"]


def test_p34_adapter_fixtures_reject_known_false_substitutes() -> None:
    report = build_ai_semis_adapter_fixture_report()
    rejected_types = {row["candidate_type"] for row in report["rejected_candidates"]}

    assert report["metrics"]["rejected_candidate_count"] == 9
    assert "consolidated_revenue_substitute" in rejected_types
    assert "marketing_page_without_spec_slot" in rejected_types
    assert "peer_group_scope_substitute" in rejected_types
    assert all(row["typed_gap_if_no_better_source"] == "parser_gap" for row in report["rejected_candidates"])
