from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.case_service import CaseService
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
)


RELEASES = ROOT / "configs" / "releases"
RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v4_"
    "fresh_live_execution_result_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
RUN_ID = "research_run_fin01_0e2b6e9698ebbf61288708a9"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v4_exact_run_is_consistently_failed_without_artifacts_or_retry() -> None:
    result = _load(RESULT)
    truth = result["canonical_terminal_truth"]
    assert [
        truth["work_unit_state"],
        truth["attempt_state"],
        truth["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert truth["artifact_count"] == 0
    assert truth["orphaned_run"] is False
    provider = result["provider_execution"]
    assert [provider["model_calls"], provider["provider_calls"], provider["network_calls"]] == [3, 3, 3]
    assert [provider["retry_count"], provider["fallback_count"], provider["rerun_count"]] == [0, 0, 0]


def test_restricted_raw_answers_replay_and_explain_exact_budget_failure() -> None:
    result = _load(RESULT)
    diagnosis = result["zero_call_replay_diagnosis"]
    assert [row["canonical_json_utf8_bytes"] for row in diagnosis["segments"]] == [1166, 1519, 3445]
    assert [diagnosis["assembled_canonical_json_utf8_bytes"], diagnosis["specialist_assembled_output_budget_bytes"], diagnosis["over_budget_bytes"]] == [6010, 6000, 10]
    assert diagnosis["project_owned_segment_to_assembly_budget_mismatch"] is True
    service = CaseService.for_fixture_root(RUNTIME / "canonical-runtime", repo_root=ROOT)
    captures = service._facade.read_research_run_provider_output_captures(RUN_ID)
    assert len(captures) == 3
    assert [row["capture_sequence"] for row in captures] == [1, 2, 3]
    assert result["provider_output_capture"]["object_digests"] == [
        "4bf51db4f0d35d0233fa7919dfbd5bf059b99f7b9c1bd0eabfd1413453ebad8b",
        "6482538efa4285ff771706131ee6a8c4798096b7bbbc3aaae0dfcf6a30929288",
        "6b6fe21c21d0e840ed1d55bec0443d0f9ec6049e74bffec48f3e0ee456eba643",
    ]
    assert all(isinstance(row["assistant_output_text"], str) for row in captures)
    assert '"assistant_output_text":' not in RESULT.read_text(encoding="utf-8")


def test_v4_identity_is_consumed_once_and_project_os_stops_at_zero_call_decision() -> None:
    snapshot = _logical_snapshot(
        RUNTIME / "canonical-runtime" / "canonical.sqlite",
        "case_ac6fce120bf27977a1b45832",
    )
    assert [
        len(snapshot["work_unit_ids"]),
        len(snapshot["attempt_ids"]),
        len(snapshot["research_run_ids"]),
        len(snapshot["artifact_refs"]),
    ] == [9, 9, 9, 13]
    assert RUN_ID in snapshot["research_run_ids"]
    next_action = _load(BACKLOG)["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["transport_v4_fresh_exact_admission_consumed"] is True
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False


def test_v4_result_has_no_plaintext_credential_or_answer_body() -> None:
    rendered = RESULT.read_text(encoding="utf-8")
    assert "sk-" not in rendered.lower()
    assert "DEEPSEEK_API_KEY" not in rendered
    assert '"raw_provider_response_persisted": false' in rendered
    assert '"private_chain_of_thought_persisted": false' in rendered
