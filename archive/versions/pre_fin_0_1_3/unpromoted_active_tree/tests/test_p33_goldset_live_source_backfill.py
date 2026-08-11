from __future__ import annotations

from sec_agent.humanmade_gold_set_runtime import (
    build_goldset_live_source_backfill,
    build_goldset_source_runtime_assimilation_matrix,
)


def test_goldset_matrix_preserves_deep_case_binding_fields() -> None:
    matrix = build_goldset_source_runtime_assimilation_matrix()
    ai_rows = [row for row in matrix["rows"] if row["case_id"] == "ai_semis_dell_nvda_anchor_v0_1"]

    assert len(ai_rows) == 20
    assert any(row["issuer"] == "DELL" and row["product_or_family"] for row in ai_rows)
    assert any(row["issuer"] == "NVDA" and row["metric_or_attribute"] for row in ai_rows)
    assert any(row["source_name"] for row in ai_rows)
    assert all("issuer" in row for row in ai_rows)


def test_goldset_live_source_backfill_covers_matrix_without_paid_runs() -> None:
    backfill = build_goldset_live_source_backfill()

    assert backfill["schema_version"] == "fin_insight_goldset_live_source_backfill_v0_1"
    assert backfill["metrics"]["row_count"] == 68
    assert len(backfill["case_summaries"]) == 15
    assert backfill["pre_writer_decision"]["allow_paid_memo_writer"] is False
    assert "paid_llm" in backfill["scope"]["not_run"]


def test_goldset_live_source_backfill_keeps_failure_fixtures_out_of_evidence() -> None:
    backfill = build_goldset_live_source_backfill()
    negative_rows = [row for row in backfill["rows"] if row["case_type"] == "negative_gold_case"]

    assert len(negative_rows) == 6
    assert {row["backfill_status"] for row in negative_rows} == {"not_applicable_failure_fixture"}
    assert {row["bound_runtime_row_count"] for row in negative_rows} == {0}
    assert all("failure fixtures" in row["authority_boundary"] for row in negative_rows)


def test_goldset_live_source_backfill_does_not_promote_unbound_rubric_slots() -> None:
    backfill = build_goldset_live_source_backfill()
    rubric_rows = [row for row in backfill["rows"] if row["case_type"] == "rubric_gold_case"]

    assert rubric_rows
    assert "case_binding_required_before_live_lookup" in {row["backfill_status"] for row in rubric_rows}
    assert all(row["is_live_runtime_ready"] is False for row in rubric_rows if not row["issuer"])


def test_goldset_live_source_backfill_finds_existing_ai_semis_candidates() -> None:
    backfill = build_goldset_live_source_backfill()
    ai_rows = [row for row in backfill["rows"] if row["case_id"] == "ai_semis_dell_nvda_anchor_v0_1"]
    candidate_rows = [
        row
        for row in ai_rows
        if row["backfill_status"]
        in {
            "live_runtime_ready",
            "route_candidate_only_parser_lineage_pending",
            "source_route_candidate_weak_not_bound",
        }
    ]

    assert candidate_rows
    assert any(row["top_candidates"] for row in candidate_rows)
    assert backfill["metrics"]["indexed_row_count"] > 0
