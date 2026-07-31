from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.case_service import CaseService


RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v2_"
    "fresh_live_execution_result_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
RUN_ID = "research_run_fin01_641650afe6bb1062f9ae135e"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_exact_run_is_terminal_failed_consistently_without_retry() -> None:
    result = _load(RESULT)
    truth = result["canonical_terminal_truth"]
    assert [
        truth["work_unit_state"],
        truth["attempt_state"],
        truth["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert truth["failure_code"] == (
        "s3_bounded_research_lead_v2_assembly_canonical_validation_failed"
    )
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


def test_lead_v2_capacity_passes_before_fact_presence_scope_failure() -> None:
    observation = _load(RESULT)["live_repair_observation"]
    assert observation["all_three_specialists_and_nine_segments_completed"] is True
    assert observation["research_lead_finish_reason"] == "stop"
    assert [
        observation["research_lead_observed_output_tokens"],
        observation["research_lead_output_token_limit"],
    ] == [1094, 1800]
    assert observation["research_lead_truncation_repeated"] is False
    assert observation[
        "research_lead_v2_top_level_shape_cardinality_text_authority_and_provider_byte_validation"
    ] == "pass"
    assert observation["research_lead_provider_utf8_bytes"] < 6000
    assert observation["research_lead_assembled_utf8_bytes"] < 8192
    assert observation["restricted_replay_exact_canonical_error"] == (
        "s3_owner_grade_lead_fact_presence_mismatch"
    )


def test_restricted_replay_identifies_global_vs_conflict_scope_mismatch() -> None:
    root = _load(RESULT)["root_cause_observation"]
    assert root["global_specialist_fact_count"] == 2
    assert root["specialist_fact_counts_by_cell_order"] == [0, 2, 0]
    assert root["conflict_fact_presence_summaries"] == [
        "no_facts_present",
        "mixed_fact_presence",
        "no_facts_present",
    ]
    assert root["involved_claim_support_fact_counts"] == [[0, 0], [0, 0], [0]]
    assert root["legacy_global_no_facts_rejection_flags"] == [True, False, True]
    assert root["provider_change_justified"] is False
    assert root["cap_increase_justified"] is False
    assert root["retry_or_rerun_justified"] is False


def test_runtime_result_hash_and_restricted_captures_are_replayable() -> None:
    result = _load(RESULT)
    runtime_result = ROOT / result["runtime_result_ref"]
    inspection = ROOT / result["runtime_inspection_ref"]
    assert _sha256(runtime_result) == result["runtime_result_sha256"]
    assert _sha256(inspection) == result["runtime_inspection_sha256"]
    with tempfile.TemporaryDirectory(
        prefix="fin01-s3-t09-lead-v2-capture-replay-"
    ) as temp_dir:
        clone_root = Path(temp_dir) / "canonical-runtime"
        shutil.copytree(RUNTIME / "canonical-runtime", clone_root)
        case_service = CaseService.for_fixture_root(clone_root, repo_root=ROOT)
        captures = case_service._facade.read_research_run_provider_output_captures(
            RUN_ID
        )
        terminal_events = [
            row
            for row in case_service._facade.store.list_events()
            if row.get("task_run_id") == RUN_ID
            and row.get("event_type") == "RESEARCH_RUN_FAILED"
        ]
    assert len(captures) == 10
    assert [row["capture_sequence"] for row in captures] == list(range(1, 11))
    assert len(terminal_events) == 1
    capture_refs = terminal_events[0]["payload"]["provider_output_capture_refs"]
    assert [row["object_digest"] for row in capture_refs] == result[
        "provider_output_capture"
    ]["object_digests"]
    rendered = RESULT.read_text(encoding="utf-8")
    assert '"assistant_output_text":' not in rendered
    assert "sk-" not in rendered.lower()
    assert "DEEPSEEK_API_KEY" not in rendered


def test_identity_is_consumed_once_and_project_os_advances_after_scope_decision() -> None:
    counts, run_ids = _logical_counts()
    assert list(counts.values()) == [11, 11, 11, 13]
    assert RUN_ID in run_ids
    next_action = _load(BACKLOG)["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-WRITER-CLAIM-SURFACE-"
        "AND-ORPHANED-RUN-ZERO-CALL-ROOT-CAUSE-DECISION"
    )
    assert next_action[
        "research_lead_v2_fresh_exact_admission_consumed"
    ] is True
    assert next_action[
        "research_lead_v2_conflict_fact_presence_scope_root_cause_decision_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_conflict_local_direct_support_implementation_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_fresh_agent_proof_decision_authorized"
    ] is True
    assert next_action[
        "research_lead_v3_fresh_exact_admission_issuance_authorized"
    ] is True
    assert next_action["research_lead_v3_fresh_exact_admission_issued"] is True
    assert next_action["research_lead_v3_fresh_exact_admission_consumed"] is True
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False
