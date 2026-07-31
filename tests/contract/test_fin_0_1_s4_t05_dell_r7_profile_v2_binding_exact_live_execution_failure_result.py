from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r7_failure_result_binds_immutable_authority_and_preparation_chain() -> None:
    result = _load(RESULT_PATH)
    refs_and_hashes = (
        (result["authority"]["decision_ref"], result["authority"]["decision_sha256"]),
        (
            result["preparation_chain"]["fresh_proof_ref"],
            result["preparation_chain"]["fresh_proof_sha256"],
        ),
        (
            result["preparation_chain"]["admission_ref"],
            result["preparation_chain"]["admission_file_sha256"],
        ),
        (
            result["preparation_chain"]["issuance_ref"],
            result["preparation_chain"]["issuance_sha256"],
        ),
    )
    for ref, expected_hash in refs_and_hashes:
        path = ROOT / ref
        assert path.is_file()
        assert _sha256(path) == expected_hash

    assert result["preparation_chain"]["issued"] is True
    assert result["preparation_chain"]["consumed"] is True
    assert result["authority"]["second_R7_execution_authorized"] is False


def test_r7_failure_result_records_canonical_terminal_truth_and_gateway_calls() -> None:
    result = _load(RESULT_PATH)
    terminal = result["canonical_terminal_truth"]
    gateway = result["gateway_ledger_audit"]

    assert result["status"] == (
        "terminal_failed_post_verifier_untyped_ValueError_admission_consumed_no_retry"
    )
    assert (
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ) == ("failed", "failed", "failed")
    assert terminal["terminal_reason"] == "bounded_agent_profile_error:ValueError"
    assert terminal["artifact_count"] == 0
    assert terminal["orphaned_run"] is False

    assert gateway["model_call_started_count"] == 12
    assert gateway["model_call_finished_count"] == 12
    assert gateway["completed_ok_count"] == 12
    assert gateway["finish_reason_stop_count"] == 12
    assert gateway["finish_reason_length_count"] == 0
    assert gateway["transport_failure_count"] == 0
    assert gateway["input_tokens"] == 69697
    assert gateway["output_tokens"] == 6658
    assert gateway["total_tokens"] == 76355
    assert gateway["completed_role_counts"] == {
        "specialist_segments": 9,
        "research_lead": 1,
        "memo_writer": 1,
        "verifier": 1,
    }
    assert gateway["verifier_completed_ok_stop"] is True
    assert gateway["model_instruction_noncompliance_established"] is False


def test_r7_failure_result_preserves_stop_boundary_and_selects_zero_call_next_action() -> None:
    result = _load(RESULT_PATH)
    failure = result["first_credible_failure"]
    observation = result["runtime_observability_contradiction"]
    stop = result["stop_contract_observation"]

    assert failure["failure_code"] == (
        "post_verifier_untyped_ValueError_with_lost_12_call_failure_observation"
    )
    assert failure["exact_throw_site_known"] is False
    assert failure["provider_transport_or_credential_failure"] is False
    assert observation["gateway_proven_completed_model_calls"] == 12
    assert observation["runtime_usage_receipt_count"] == 0
    assert observation["raw_ValueError_message_persisted"] is False
    assert all(
        stop[key] == 0
        for key in (
            "automatic_retry_count",
            "fallback_count",
            "replay_count",
            "relaunch_count",
            "rerun_count",
            "monitor_mutations",
            "signals_sent",
        )
    )
    assert stop["paired_assessment_performed"] is False
    assert stop["S4_T06_entered"] is False
    assert stop["DELL_R2_proven"] is False
    assert result["next_action"] == (
        "S4-T05-DELL-R7-POST-VERIFIER-UNTYPED-VALUEERROR-AND-LOST-FAILURE-"
        "OBSERVABILITY-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION"
    )
