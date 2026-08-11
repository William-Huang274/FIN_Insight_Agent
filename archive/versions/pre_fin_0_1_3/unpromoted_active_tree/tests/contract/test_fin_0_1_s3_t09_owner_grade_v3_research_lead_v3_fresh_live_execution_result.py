from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v3_"
    "fresh_live_execution_result_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
RUN_ID = "research_run_fin01_e418d7086d4a1d253e9b2c9b"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _run_events() -> list[dict[str, object]]:
    database = RUNTIME / "canonical-runtime" / "canonical.sqlite"
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    try:
        columns = [
            row[1]
            for row in connection.execute("pragma table_info(canonical_events)")
        ]
        payload_column = "payload_json" if "payload_json" in columns else "payload"
        rows = connection.execute(
            f"""
            select event_type, {payload_column}
            from canonical_events
            where task_run_id = ?
            order by row_id
            """,
            (RUN_ID,),
        ).fetchall()
        return [
            {"event_type": str(event_type), "payload": json.loads(str(payload))}
            for event_type, payload in rows
        ]
    finally:
        connection.close()


def test_exact_admission_was_consumed_once_but_run_is_orphaned_running() -> None:
    result = _load(RESULT)
    identity = result["identity"]
    assert identity["research_run_id"] == RUN_ID
    work_unit = _latest("canonical_work_units", identity["work_unit_id"])
    attempt = _latest("canonical_attempts", identity["attempt_id"])
    run = _latest("canonical_research_run_versions", RUN_ID)
    assert [work_unit["state"], attempt["state"], run["state"]] == [
        "running",
        "running",
        "running",
    ]
    truth = result["canonical_terminal_truth"]
    assert truth["orphaned_run"] is True
    assert truth["artifact_count"] == 0
    assert [row["event_type"] for row in _run_events()] == truth["run_event_types"]


def test_provider_reached_writer_once_and_never_called_verifier_or_retried() -> None:
    provider = _load(RESULT)["provider_execution"]
    assert [
        provider["model_calls"],
        provider["provider_calls"],
        provider["network_calls"],
        provider["transport_attempt_count"],
    ] == [11, 11, 11, 11]
    assert provider["completed_specialist_segment_count"] == 9
    assert provider["research_lead_called"] is True
    assert provider["memo_writer_called"] is True
    assert provider["verifier_called"] is False
    assert [
        provider["retry_count"],
        provider["fallback_count"],
        provider["rerun_count"],
    ] == [0, 0, 0]
    assert provider["exact_estimated_cost_usd"] is None
    assert provider["maximum_reconstructable_cost_usd"] < 0.1


def test_writer_failure_and_terminalization_failure_are_distinct_and_typed() -> None:
    result = _load(RESULT)
    live = result["live_repair_observation"]
    assert live["immediate_failure_code"] == (
        "s3_owner_grade_writer_claim_surface_violation"
    )
    assert live["exact_writer_validator_subbranch"].startswith("not_reconstructable")
    closeout = result["terminalization_failure"]
    assert closeout["failure_code"] == (
        "research_run_failure_observation_not_secret_safe"
    )
    assert closeout["observed_writer_failure_code_namespace"] == "s3_owner_grade_"
    assert closeout["accepted_failure_code_namespaces"] == [
        "bounded_agent_",
        "s3_bounded_",
    ]


def test_failed_closeout_did_not_persist_current_run_assistant_outputs() -> None:
    capture = _load(RESULT)["provider_output_capture"]
    assert capture["expected_in_memory_capture_count_before_closeout"] == 11
    assert capture["durably_persisted_capture_count_for_this_run"] == 0
    assert capture["assistant_final_output_text_replayable"] is False
    object_root = (
        RUNTIME
        / "canonical-runtime"
        / "objects"
        / "fin01"
        / "provider-output-captures"
    )
    assert all(
        RUN_ID not in path.read_text(encoding="utf-8")
        for path in object_root.rglob("*.json")
    )


def test_project_os_stops_at_zero_call_root_cause_decision() -> None:
    expected = (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-WRITER-CLAIM-SURFACE-"
        "AND-ORPHANED-RUN-ZERO-CALL-ROOT-CAUSE-DECISION"
    )
    result = _load(RESULT)
    backlog = _load(BACKLOG)
    assert result["next_action"] == expected
    assert backlog["next_action"]["item_id"] == expected
    next_action = backlog["next_action"]
    assert next_action["research_lead_v3_fresh_exact_admission_consumed"] is True
    assert next_action["research_lead_v3_fresh_exact_live_execution_authorized"] is True
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["orphaned_run_typed_closeout_authorized"] is False
    assert next_action["writer_validator_repair_authorized"] is False


def test_result_hashes_runtime_evidence_and_contains_no_plaintext_secret_or_body() -> None:
    result = _load(RESULT)
    for ref_key, hash_key in (
        ("runtime_preflight_ref", "runtime_preflight_sha256"),
        ("runtime_inspection_ref", "runtime_inspection_sha256"),
    ):
        path = ROOT / result[ref_key]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == result[hash_key]
    rendered = RESULT.read_text(encoding="utf-8")
    assert '"assistant_output_text":' not in rendered
    assert "sk-" not in rendered.lower()
    assert "DEEPSEEK_API_KEY" not in rendered
