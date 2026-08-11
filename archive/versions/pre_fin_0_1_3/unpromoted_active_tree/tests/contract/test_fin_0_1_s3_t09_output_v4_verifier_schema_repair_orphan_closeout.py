from __future__ import annotations

import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
    "orphan_typed_closeout_result_v1_0.json"
)
RUNTIME = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1"
)


def _load() -> dict[str, object]:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def _latest(table: str, logical_id: str) -> dict[str, object]:
    database = RUNTIME / "canonical-runtime" / "canonical.sqlite"
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    try:
        row = connection.execute(
            f"""
            select payload_json
            from {table}
            where logical_id = ?
            order by row_id desc
            limit 1
            """,
            (logical_id,),
        ).fetchone()
        assert row is not None
        return json.loads(str(row[0]))
    finally:
        connection.close()


def test_closeout_records_completed_provider_path_without_claiming_artifacts() -> None:
    result = _load()
    assert result["status"] == "typed_orphan_closeout_succeeded_zero_call"
    execution = result["completed_provider_execution"]
    assert [
        execution["model_calls"],
        execution["provider_calls"],
        execution["network_calls"],
        execution["transport_attempts"],
        execution["transport_failures"],
    ] == [12, 12, 12, 12, 0]
    assert execution["finish_reasons"] == ["stop"]
    assert execution["stages"][-3:] == ["research_lead", "memo_writer", "verifier"]
    assert [
        execution["input_tokens"],
        execution["output_tokens"],
        execution["total_tokens"],
    ] == [55186, 6422, 61608]
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert result["t09_acceptance_eligible"] is False


def test_closeout_terminalizes_exact_identity_and_does_not_rerun() -> None:
    result = _load()
    identity = result["identity"]
    work_unit = _latest("canonical_work_units", identity["work_unit_id"])
    attempt = _latest("canonical_attempts", identity["attempt_id"])
    run = _latest("canonical_research_run_versions", identity["research_run_id"])
    assert [work_unit["state"], attempt["state"], run["state"]] == [
        "failed",
        "failed",
        "failed",
    ]
    assert run["terminal_reason"] == result["terminal_reason"]
    assert result["canonical_terminal_truth"]["orphaned_run"] is False
    assert result["closeout_model_provider_network_calls"] == [0, 0, 0]
    assert [
        result["retry_count"],
        result["fallback_count"],
        result["rerun_count"],
    ] == [0, 0, 0]


def test_restricted_captures_remain_audit_only_and_secret_safe() -> None:
    result = _load()
    capture = result["provider_output_capture"]
    assert [
        capture["capture_count"],
        capture["restricted_readback_count"],
        capture["assistant_output_present_count"],
    ] == [12, 12, 12]
    assert capture["recoverable_for_audit_only"] is True
    assert capture["replayed_or_promoted_to_business_artifacts"] is False
    assert result["exact_usage_receipts_available"] is False
    rendered = RESULT.read_text(encoding="utf-8")
    assert '"assistant_output_text":' not in rendered
    assert "DEEPSEEK_API_KEY" not in rendered
    assert "sk-" not in rendered.lower()
