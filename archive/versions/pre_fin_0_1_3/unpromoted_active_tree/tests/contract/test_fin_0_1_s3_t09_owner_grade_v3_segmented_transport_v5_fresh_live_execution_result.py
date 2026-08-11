from __future__ import annotations

import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_"
    "fresh_live_execution_result_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
RUN_ID = "research_run_fin01_1736461952f90e35f104f478"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _logical_counts() -> tuple[dict[str, int], set[str]]:
    database = RUNTIME / "canonical-runtime" / "canonical.sqlite"
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    case_id = "case_ac6fce120bf27977a1b45832"
    try:
        counts: dict[str, int] = {}
        run_ids: set[str] = set()
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        ):
            latest: dict[str, dict[str, object]] = {}
            for logical_id, payload_json in connection.execute(
                f"select logical_id, payload_json from {table} order by row_id"
            ):
                payload = json.loads(str(payload_json))
                if payload.get("case_id") == case_id:
                    latest[str(logical_id)] = payload
            counts[table] = len(latest)
            if table == "canonical_research_run_versions":
                run_ids = set(latest)
        return counts, run_ids
    finally:
        connection.close()


def test_v5_exact_run_is_consistently_failed_at_lead_without_retry() -> None:
    result = _load(RESULT)
    truth = result["canonical_terminal_truth"]
    assert [
        truth["work_unit_state"],
        truth["attempt_state"],
        truth["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert truth["failure_code"] == "s3_bounded_node_output_truncated"
    assert truth["artifact_count"] == 0
    assert truth["orphaned_run"] is False
    provider = result["provider_execution"]
    assert [
        provider["model_calls"],
        provider["provider_calls"],
        provider["network_calls"],
    ] == [10, 10, 10]
    assert [
        provider["retry_count"],
        provider["fallback_count"],
        provider["rerun_count"],
    ] == [0, 0, 0]


def test_v5_live_proves_assembly_then_stops_at_exact_lead_cap() -> None:
    observation = _load(RESULT)["live_repair_observation"]
    assert observation["all_three_specialists_and_nine_segments_completed"] is True
    assert observation["transport_v5_bounded_assembly_repair_live_proven"] is True
    assert observation["transport_v4_6010_over_6000_failure_repeated"] is False
    assert [
        observation["research_lead_observed_output_tokens"],
        observation["research_lead_output_token_limit"],
    ] == [1200, 1200]
    assert observation["research_lead_finish_reason"] == "length"
    assert observation["writer_called"] is False
    assert observation["verifier_called"] is False
    assert observation["token_budget_is_only_observed_current_failure"] is True
    assert observation["token_budget_is_only_possible_remaining_product_issue"] is False


def test_v5_captures_are_content_addressed_without_tracked_answer_body() -> None:
    result = _load(RESULT)
    capture = result["provider_output_capture"]
    assert capture["capture_count"] == 10
    assert capture["restricted_readback_count"] == 10
    object_root = RUNTIME / "canonical-runtime" / "objects" / "fin01" / (
        "provider-output-captures"
    )
    for digest in capture["object_digests"]:
        path = object_root / digest[:2] / digest[2:4] / f"{digest}.json"
        assert path.is_file()
    rendered = RESULT.read_text(encoding="utf-8")
    assert '"assistant_output_text":' not in rendered
    assert "sk-" not in rendered.lower()
    assert "DEEPSEEK_API_KEY" not in rendered


def test_v5_identity_is_consumed_once_and_project_os_advances_only_after_decision() -> None:
    counts, run_ids = _logical_counts()
    assert list(counts.values()) == [10, 10, 10, 13]
    assert RUN_ID in run_ids
    next_action = _load(BACKLOG)["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-CONFLICT-LOCAL-"
        "DIRECT-SUPPORT-ZERO-CALL-IMPLEMENTATION"
    )
    assert next_action["transport_v5_fresh_exact_admission_consumed"] is True
    assert next_action["research_lead_truncation_root_cause_decision_authorized"] is True
    assert next_action["research_lead_zero_call_implementation_authorized"] is True
    assert next_action[
        "research_lead_v2_conflict_fact_presence_scope_root_cause_decision_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_conflict_local_direct_support_implementation_authorized"
    ] is False
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False
