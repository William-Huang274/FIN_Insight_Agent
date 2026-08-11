from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


RELEASES = ROOT / "configs/releases"
PROOF = RELEASES / (
    "fin_ia_0_1_3_s2_provider_neutral_numeric_presentation_"
    "local_renderer_clean_independent_proof_v1_0.json"
)
DECISION = RELEASES / (
    "fin_ia_0_1_3_s2_bounded_closeout_autonomy_grant_and_"
    "s3_entry_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _assert_canonical(value: dict) -> None:
    body = {key: row for key, row in value.items() if key != "result_digest"}
    assert value["result_digest"] == canonical_digest(body)


def test_clean_proof_is_canonical_two_worker_and_zero_call() -> None:
    proof = _load(PROOF)
    _assert_canonical(proof)

    workers = proof["worker_results"]
    assert len(workers) == 2
    assert {row["proof_digest"] for row in workers} == {
        "ba5e4ecf9772b588f5c6d0dc6e46c08055a5aec81feac6563e838f6285a004c1"
    }
    assert proof["replay_result"]["byte_equivalent"] is True
    assert proof["replay_result"]["provider_specific_rule_used"] is False
    assert proof["observed_calls"] == {
        "fallbacks": 0,
        "model_calls": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "retries": 0,
        "source_calls": 0,
    }
    assert proof["immutability"]["historical_exact_live_terminal_remains_failed"]
    assert proof["immutability"]["second_model_canary_executed"] is False


def test_clean_proof_records_private_hydration_precondition_honestly() -> None:
    proof = _load(PROOF)
    discovery = proof["precondition_discovery"]

    assert discovery["code"] == "changed_input_corrected_pack_artifact_drift"
    assert discovery["project_or_model_defect"] is False
    assert len(proof["archive_protocol"]["private_inputs_hydrated_after_archive"]) == 3
    assert proof["archive_protocol"]["private_inputs_committed_to_git"] is False
    assert proof["archive_protocol"]["temporary_workers_removed"] is True


def test_decision_grants_bounded_atoms_but_not_full_report_autonomy() -> None:
    decision = _load(DECISION)
    _assert_canonical(decision)

    assert decision["autonomy_grant"]["grant_level"] == (
        "bounded_judgment_atom_and_evidence_selection"
    )
    assert decision["autonomy_grant"]["provider_neutral_core_contract"] is True
    assert decision["autonomy_grant"]["unrestricted_full_report_autonomy"] is False
    stage = decision["stage_disposition"]
    assert stage["S2_bounded_capability_closeout"] is True
    assert stage["S2_product_report_acceptance"] is False
    assert stage["RC_P36_170_numeric_control_plane"] == "closed"
    assert stage["RC_P36_172_wwc_mechanism_and_density"] == (
        "open_owned_by_S3"
    )
    assert decision["S3_entry"]["eligible"] is True
    assert decision["S3_entry"]["formal_model_or_tool_execution_authorized"] is False
    assert decision["stage_disposition"]["owner_acceptance"] is False
    assert decision["stage_disposition"]["release"] is False


def test_decision_binds_the_exact_clean_proof_and_old_failed_terminal() -> None:
    decision = _load(DECISION)
    proof = _load(PROOF)

    assert decision["evidence"]["local_renderer_clean_proof_digest"] == (
        proof["result_digest"]
    )
    terminal = _load(ROOT / decision["evidence"]["natural_canary_terminal_ref"])
    assert terminal["result_digest"] == decision["evidence"][
        "natural_canary_terminal_digest"
    ]
    assert terminal["formal_terminal"]["status"] == "failed"
    assert decision["stage_disposition"]["historical_exact_live_terminal"] == (
        "failed_immutable"
    )
