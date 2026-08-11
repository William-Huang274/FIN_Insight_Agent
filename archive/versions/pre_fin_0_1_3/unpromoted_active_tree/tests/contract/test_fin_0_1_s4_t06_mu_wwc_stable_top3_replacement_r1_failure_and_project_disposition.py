from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_wwc_stable_top3_"
    "replacement_r1_exact_live_failure_result_v1_0.json"
)
DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_fact_candidate_pool_"
    "local_bounding_project_level_disposition_v1_0.json"
)
RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1"
)
RUNTIME_RESULT = RUNTIME_ROOT / (
    "s4_t06_mu_wwc_stable_top3_replacement_r1_live_execution_result.json"
)
RUNTIME_DB = RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"


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


def test_failure_result_binds_frozen_proof_admission_and_runtime() -> None:
    result = _load(RESULT)
    source = result["source_authority"]
    supervision = result["supervision_and_runner_observation"]

    for ref_key, sha_key in (
        ("fresh_proof_ref", "fresh_proof_sha256"),
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


def test_terminal_truth_is_consistent_failed_and_no_artifact() -> None:
    result = _load(RESULT)
    runtime = _load(RUNTIME_RESULT)
    target = result["execution_identity"]

    assert runtime["status"] == "terminal_failed_admission_consumed_no_retry"
    assert [
        runtime["canonical_terminal_truth"]["work_unit_state"],
        runtime["canonical_terminal_truth"]["attempt_state"],
        runtime["canonical_terminal_truth"]["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert runtime["canonical_terminal_truth"]["artifact_count"] == 0
    assert runtime["artifact_payloads"] == {}

    connection = sqlite3.connect(
        f"file:{RUNTIME_DB.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        for table, logical_id in (
            ("canonical_work_units", target["work_unit_id"]),
            ("canonical_attempts", target["attempt_id"]),
            ("canonical_research_run_versions", target["research_run_id"]),
        ):
            row = connection.execute(
                f"SELECT payload_json FROM {table} "
                "WHERE logical_id = ? ORDER BY row_id DESC LIMIT 1",
                (logical_id,),
            ).fetchone()
            assert row is not None
            assert json.loads(row[0])["state"] == "failed"
    finally:
        connection.close()


def test_failure_capture_proves_twenty_two_atoms_against_maximum_six() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]
    digest = failure["restricted_failure_capture_digest"]
    capture_path = _capture_path(digest)
    capture = _load(capture_path)

    assert _sha256(capture_path) == digest
    assert capture["capture_sequence"] == 4
    assert capture["assistant_output_present"] is True
    output = json.loads(capture["assistant_output_text"])
    request = json.loads(capture["model_visible_request"][1]["content"])

    assert set(output) == {"program_cell_id", "fact_atoms", "terminal_class"}
    assert len(output["fact_atoms"]) == 22
    assert len(request["compiled_judgment_atom_contract"]["allowed_supports"]) == 22
    assert request["output_constraints"]["provider_candidate_maximum"] == 6
    assert len(capture["assistant_output_text"].encode("utf-8")) == 3696
    assert failure["model_cardinality_instruction_noncompliance_established"] is True
    assert failure["project_owned_design_blocker_established"] is True
    assert failure["transport_JSON_finish_or_truncation_failure_established"] is False


def test_usage_capture_and_stop_contract_are_exact() -> None:
    result = _load(RESULT)
    usage = result["usage_and_budget"]
    captures = result["capture_v2_evidence"]
    stop = result["stop_contract_observation"]

    assert [
        usage["semantic_model_calls"],
        usage["provider_calls"],
        usage["network_calls"],
    ] == [4, 4, 4]
    assert [
        usage["input_tokens"],
        usage["output_tokens"],
        usage["total_tokens"],
    ] == [23862, 1855, 25717]
    assert usage["estimated_cost_usd"] == 0.00845999
    assert [
        usage["retry_count"],
        usage["fallback_count"],
        usage["replay_count"],
        usage["relaunch_count"],
        usage["rerun_count"],
    ] == [0, 0, 0, 0, 0]
    assert captures["capture_count"] == 4
    for digest in captures["capture_object_digests"]:
        assert _sha256(_capture_path(digest)) == digest
    assert stop["admission_consumed_exactly_once"] is True
    assert stop["first_credible_failure_stopped_execution"] is True
    assert stop["automatic_retry_fallback_replay_relaunch_patch_or_rerun"] is False


def test_project_disposition_moves_candidate_pool_to_local_planner() -> None:
    disposition = _load(DISPOSITION)
    selected = disposition["selected_structural_boundary"]
    scope = disposition["scope_boundary"]
    successor = disposition["successor_work_item"]

    assert disposition["status"].startswith("project_level_disposition_complete")
    assert selected["contract_family"] == "specialist_fact_atoms"
    assert selected["provider_candidate_generation_blocked"] is True
    assert selected["local_candidate_pool_maximum"] == 6
    assert selected["provider_visible_allowed_support_maximum"] == 6
    assert selected["local_final_selected_maximum"] == 3
    assert selected["silent_truncation_allowed"] is False
    assert selected["validator_weakening_allowed"] is False
    assert selected["provider_retry_for_cardinality_allowed"] is False
    assert scope["T06_additional_exact_live_runs"] == 0
    assert scope["automatic_R8_R9_or_equivalent"] is False
    assert scope["paired_assessment"] == "not_eligible_no_artifacts"
    assert scope["owner_acceptance"] == "not_eligible_no_artifacts"
    assert scope["S4_T07"] == "not_entered"
    assert successor["stage_ownership"] == "shared_runtime_hardening_not_T06_field_patch"
    assert disposition["observed_counts"] == {
        "disposition_model_calls": 0,
        "disposition_provider_calls": 0,
        "disposition_network_calls": 0,
        "additional_exact_live_runs": 0,
        "paired_assessments": 0,
        "owner_acceptances": 0,
        "T07_entries": 0,
    }
