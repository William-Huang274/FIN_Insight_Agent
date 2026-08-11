from __future__ import annotations

import json
from pathlib import Path

from sec_agent.parser_quality_ledger import (
    PARSER_OUTPUT_ARTIFACT_LEDGER_SCHEMA_VERSION,
    PARSER_REJECTION_TAXONOMY_SCHEMA_VERSION,
    PARSER_RUN_LEDGER_SCHEMA_VERSION,
    build_parser_quality_ledger,
    discover_parser_artifact_paths,
    discover_parser_summary_paths,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_rd2_reads_parser_summary_outputs_and_rejection_taxonomy(tmp_path: Path) -> None:
    repo = tmp_path
    rows_path = repo / "data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl"
    rejections_path = repo / "data/manifests/company_disclosed_product_business_mix_rejections_v0_1.jsonl"
    _write_jsonl(rows_path, [{"ticker": "NVDA"}, {"ticker": "AMD"}])
    _write_jsonl(rejections_path, [{"reason": "percentage_or_mix_only_no_exact_product_value"}])
    _write_json(
        repo / "data/manifests/company_disclosed_product_business_mix_summary_v0_1.json",
        {
            "schema_version": "fixture_summary",
            "status": "pass",
            "runtime_row_count": 2,
            "runtime_ticker_count": 2,
            "rejection_count": 1,
            "rejection_reason_counts": {"percentage_or_mix_only_no_exact_product_value": 1},
            "outputs": {"rows": str(rows_path), "rejections": str(rejections_path)},
        },
    )

    result = build_parser_quality_ledger(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "pass_with_recorded_rejections"
    run = result["parser_runs"][0]
    assert run["schema_version"] == PARSER_RUN_LEDGER_SCHEMA_VERSION
    assert run["owner_stage"] == "product_kpi_runtime_parser"
    assert run["runtime_row_count"] == 2
    rejection = result["rejection_rows"][0]
    assert rejection["schema_version"] == PARSER_REJECTION_TAXONOMY_SCHEMA_VERSION
    assert rejection["rejection_class"] == "percentage_or_change_only"
    artifacts = {row["artifact_kind"]: row for row in result["artifact_rows"]}
    assert artifacts["runtime_rows"]["schema_version"] == PARSER_OUTPUT_ARTIFACT_LEDGER_SCHEMA_VERSION
    assert artifacts["runtime_rows"]["effective_row_count"] == 2


def test_rd2_marks_missing_declared_output_action_required(tmp_path: Path) -> None:
    repo = tmp_path
    missing_rows = repo / "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"
    _write_json(
        repo / "data/manifests/company_reported_product_operating_metric_runtime_summary_v0_1.json",
        {
            "status": "pass",
            "runtime_row_count": 3,
            "outputs": {"rows": str(missing_rows)},
        },
    )

    result = build_parser_quality_ledger(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "action_required"
    assert result["summary"]["missing_declared_output_count"] == 1
    assert result["parser_runs"][0]["quality_status"] == "action_required_missing_declared_output"


def test_rd2_uses_summary_count_for_large_artifact_without_line_counting(tmp_path: Path) -> None:
    repo = tmp_path
    rows_path = repo / "data/staging/sec_tier1_sp500_annual/structured_objects/fixture_metrics.jsonl"
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows_path.write_bytes(b"{\"a\":1}\n" * 8)
    _write_json(
        repo / "data/staging/sec_tier1_sp500_annual/structured_objects/fixture_structured_summary.json",
        {
            "status": "pass",
            "metric_count": 8,
            "outputs": {"metrics": str(rows_path)},
        },
    )

    result = build_parser_quality_ledger(
        repo,
        generated_at="2026-06-27T00:00:00+00:00",
        max_line_count_bytes=1,
    )
    metric_artifact = next(row for row in result["artifact_rows"] if row["artifact_kind"] == "metric_candidates")

    assert metric_artifact["declared_row_count"] == 8
    assert metric_artifact["line_count_status"] == "not_counted_large_artifact_summary_declared"
    assert metric_artifact["effective_row_count"] == 8


def test_rd2_discovery_excludes_tmp_and_non_parser_summaries(tmp_path: Path) -> None:
    repo = tmp_path
    _write_json(repo / "data/manifests/_tmp_product_summary.json", {"status": "pass", "row_count": 1})
    _write_json(repo / "data/manifests/source_route_attempt_ledger_summary_v0_1.json", {"status": "action_required", "row_count": 1})
    _write_json(repo / "data/manifests/sec_financial_statement_metric_runtime_summary_v0_1.json", {"status": "pass", "runtime_row_count": 1})
    _write_jsonl(repo / "data/manifests/_tmp_product_runtime_rows_v0_1.jsonl", [{"x": 1}])
    _write_jsonl(repo / "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl", [{"x": 1}])

    summaries = {path.name for path in discover_parser_summary_paths(repo)}
    artifacts = {path.name for path in discover_parser_artifact_paths(repo)}

    assert "sec_financial_statement_metric_runtime_summary_v0_1.json" in summaries
    assert "source_route_attempt_ledger_summary_v0_1.json" not in summaries
    assert "_tmp_product_summary.json" not in summaries
    assert "sec_financial_statement_metric_runtime_rows_v0_1.jsonl" in artifacts
    assert "_tmp_product_runtime_rows_v0_1.jsonl" not in artifacts
