from __future__ import annotations

from sec_agent.humanmade_gold_set_runtime import (
    build_goldset_source_runtime_assimilation_matrix,
)


def test_goldset_source_runtime_matrix_covers_all_cases_and_rows() -> None:
    matrix = build_goldset_source_runtime_assimilation_matrix()

    assert matrix["matrix_integrity_status"] == "pass"
    assert matrix["status"] == "partial_artifact_scope_pass_live_runtime_pending"
    assert matrix["metrics"]["case_count"] == 15
    assert matrix["metrics"]["row_count"] > 0
    assert len(matrix["case_summaries"]) == 15
    assert matrix["metrics"]["live_runtime_pending_case_count"] > 0
    assert matrix["pre_writer_decision"]["allow_paid_memo_writer"] is False


def test_ai_semis_gold_rows_are_runtime_artifacts_not_live_parser_proof() -> None:
    matrix = build_goldset_source_runtime_assimilation_matrix()
    ai_rows = [row for row in matrix["rows"] if row["case_id"] == "ai_semis_dell_nvda_anchor_v0_1"]

    assert len(ai_rows) == 20
    assert {row["status"] for row in ai_rows} == {"runtime_artifact_ready_source_route_unverified"}
    assert {row["runtime_row_status"] for row in ai_rows} == {"gold_depth_runtime_artifact_row_ready"}
    assert all(row["crawler_or_fetcher_status"] == "not_proven_by_live_crawler_or_fetcher" for row in ai_rows)
    assert all("live fetch/crawl" in row["next_action"] for row in ai_rows)


def test_rubric_gold_rows_remain_artifact_only_until_live_routes_exist() -> None:
    matrix = build_goldset_source_runtime_assimilation_matrix()
    rubric_rows = [row for row in matrix["rows"] if row["case_type"] == "rubric_gold_case"]

    assert rubric_rows
    assert {row["status"] for row in rubric_rows} == {"artifact_only_live_runtime_pending"}
    assert {row["crawler_or_fetcher_status"] for row in rubric_rows} == {"not_run"}
    assert {row["parser_or_adapter_status"] for row in rubric_rows} == {"not_run"}
    assert all("not a live crawler/parser row" in row["authority_boundary"] for row in rubric_rows)


def test_negative_gold_rows_are_failure_fixtures_not_source_evidence() -> None:
    matrix = build_goldset_source_runtime_assimilation_matrix()
    negative_rows = [row for row in matrix["rows"] if row["case_type"] == "negative_gold_case"]

    assert len(negative_rows) == 6
    assert {row["status"] for row in negative_rows} == {"failure_fixture_ready_not_source_evidence"}
    assert {row["runtime_row_status"] for row in negative_rows} == {"failure_gate_fixture_ready"}
    assert all("not source evidence" in row["authority_boundary"] for row in negative_rows)
    assert all("Keep as deterministic failure fixture" in row["next_action"] for row in negative_rows)


def test_source_runtime_case_summary_exposes_live_pending_by_case() -> None:
    matrix = build_goldset_source_runtime_assimilation_matrix()
    summaries = {row["case_id"]: row for row in matrix["case_summaries"]}

    assert summaries["ai_semis_dell_nvda_anchor_v0_1"]["status"] == "live_runtime_pending"
    assert summaries["ai_semis_dell_nvda_anchor_v0_1"]["source_route_unverified_runtime_artifact_row_count"] == 20
    assert summaries["semicap_cycle_rubric_v0_1"]["status"] == "live_runtime_pending"
    assert summaries["semicap_cycle_rubric_v0_1"]["artifact_only_live_runtime_pending_row_count"] >= 1
    assert (
        summaries["negative_sku_revenue_missing_not_product_failure_v0_1"]["status"]
        == "failure_fixture_only_not_source_evidence"
    )
