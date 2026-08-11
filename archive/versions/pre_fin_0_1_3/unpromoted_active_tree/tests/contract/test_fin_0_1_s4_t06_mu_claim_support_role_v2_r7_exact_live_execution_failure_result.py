from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_"
    "exact_live_execution_failure_result_v1_0.json"
)
RUNTIME_RESULT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-"
    "validation-r1/s4_t06_mu_claim_support_role_v2_r7_"
    "live_execution_result.json"
)
RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1"
)
RUNTIME_DB = RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
EXECUTION = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-R7-"
    "EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
NEXT = (
    "S4-T06-MU-R7-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-"
    "DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION"
)
AFTER_DISPOSITION = (
    "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-"
    "FINAL-SELECTION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_path(digest: str) -> Path:
    return (
        RUNTIME_ROOT
        / "canonical-runtime/objects/fin01/provider-output-captures"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.json"
    )


def test_R7_result_binds_authority_admission_issuance_and_runtime() -> None:
    result = _load(RESULT)
    source = result["source_authority"]
    supervision = result["supervision_and_runner_observation"]

    for ref_key, sha_key in (
        ("execution_authority_ref", "execution_authority_sha256"),
        ("admission_ref", "admission_sha256"),
        ("issuance_ref", "issuance_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    for ref_key, sha_key in (
        ("launch_receipt_ref", "launch_receipt_sha256"),
        ("exit_receipt_ref", "exit_receipt_sha256"),
        ("runtime_result_ref", "runtime_result_sha256"),
    ):
        assert _sha256(ROOT / supervision[ref_key]) == supervision[sha_key]
    assert supervision["runner_exit_code"] == 0
    assert supervision["typed_unhandled_failure_code"] is None
    assert supervision["runtime_materialization_findings"] == []


def test_R7_terminal_truth_is_consistent_failed_and_no_artifact() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    target = result["execution_identity"]
    terminal = result["terminal_truth"]

    assert runtime["status"] == "terminal_failed_admission_consumed_no_retry"
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["terminal_states_consistent"] is True
    assert terminal["target_run_artifacts"] == 0
    assert runtime["artifact_payloads"] == {}

    connection = sqlite3.connect(
        f"file:{RUNTIME_DB.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        for table, logical_id in (
            ("canonical_work_units", target["work_unit_id"]),
            ("canonical_attempts", target["attempt_id"]),
            (
                "canonical_research_run_versions",
                target["research_run_id"],
            ),
        ):
            rows = connection.execute(
                f"SELECT payload_json FROM {table} "
                "WHERE logical_id = ? ORDER BY row_id",
                (logical_id,),
            ).fetchall()
            assert rows
            assert json.loads(rows[-1][0])["state"] == "failed"
    finally:
        connection.close()


def test_R7_failure_is_project_owned_WWC_cardinality_drift() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]
    digest = failure["restricted_failure_capture_digest"]
    capture_path = _capture_path(digest)
    capture = _load(capture_path)

    assert _sha256(capture_path) == digest
    assert capture["capture_sequence"] == 3
    assert capture["assistant_output_present"] is True
    output = json.loads(capture["assistant_output_text"])
    assert set(output) == {"program_cell_id", "what_would_change_atoms"}
    assert len(output["what_would_change_atoms"]) == 6
    request = json.loads(capture["model_visible_request"][1]["content"])
    assert request["output_constraints"]["provider_candidate_maximum"] == 6

    assert failure["provider_returned_WWC_candidate_count"] == 6
    assert failure["model_visible_provider_candidate_maximum"] == 6
    assert failure["executed_local_WWC_accepted_maximum"] == 3
    assert failure[
        "executed_local_WWC_selection_before_shape_rejection"
    ] is False
    assert failure["project_owned_cross_layer_contract_drift_established"] is True
    assert failure[
        "model_field_level_instruction_noncompliance_established"
    ] is False
    assert failure[
        "transport_JSON_finish_or_truncation_failure_established"
    ] is False


def test_R7_usage_captures_and_stop_contract_are_exact() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    usage = result["usage_and_budget"]
    captures = result["capture_v2_evidence"]
    stop = result["stop_contract_observation"]

    assert [usage["semantic_model_calls"], usage["provider_calls"], usage["network_calls"]] == [3, 3, 3]
    assert [usage["input_tokens"], usage["output_tokens"], usage["total_tokens"]] == [13108, 1120, 14228]
    assert usage["estimated_cost_usd"] == 0.00667638
    assert [usage["retry_count"], usage["fallback_count"], usage["replay_count"], usage["relaunch_count"], usage["rerun_count"]] == [0, 0, 0, 0, 0]
    assert captures["capture_count"] == 3
    assert captures["content_addressed_digest_matches"] == 3
    for digest in captures["capture_object_digests"]:
        assert _sha256(_capture_path(digest)) == digest
    assert runtime["boundary_observation"]["credential_value_persisted"] is False
    assert runtime["boundary_observation"]["private_chain_of_thought_persisted"] is False
    assert stop["admission_consumed_exactly_once"] is True
    assert stop["first_credible_failure_stopped_execution"] is True
    assert stop["automatic_retry_fallback_replay_relaunch_patch_or_rerun"] is False


def test_R7_failure_forbids_paired_owner_T07_and_R8() -> None:
    result = _load(RESULT)
    acceptance = result["acceptance_disposition"]
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(S4_BACKLOG)

    assert acceptance["coherent_terminal_success"] is False
    assert acceptance["paired_assessment_eligible"] is False
    assert acceptance["paired_assessment_performed"] is False
    assert acceptance["owner_acceptance_performed"] is False
    assert acceptance["S4_T06_passed"] is False
    assert acceptance["S4_T07_entered"] is False
    assert acceptance["automatic_R8_authorized_or_performed"] is False
    assert result["stop_contract_observation"]["next_action"] == NEXT
    assert program["next_action"]["item_id"] in {
        EXECUTION,
        NEXT,
        AFTER_DISPOSITION,
    }
    assert detailed["current_next_action"] in {
        EXECUTION,
        NEXT,
        AFTER_DISPOSITION,
    }
