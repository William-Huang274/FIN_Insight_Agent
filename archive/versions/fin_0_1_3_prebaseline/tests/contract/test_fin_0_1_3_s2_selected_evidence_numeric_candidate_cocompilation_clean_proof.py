from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_digest,
)


PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_independent_proof_v1_0.json"
)
FAILURE_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_proof_attempt_r1_failure_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_digest(payload: dict) -> None:
    body = {key: value for key, value in payload.items() if key != "result_digest"}
    assert payload["result_digest"] == canonical_digest(body)


def test_failed_r1_is_preserved_as_proof_harness_failure_only() -> None:
    failure = _load(FAILURE_PATH)
    _assert_digest(failure)
    assert failure["status"] == "terminal_failed_proof_harness_only"
    assert failure["failure_code"] == "clean_proof_harness_result_field_path_invalid"
    assert failure["scope"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "business_runtime_changed": False,
        "private_input_persisted_to_repository": False,
    }
    assert failure["successor_attempt"].endswith("clean_proof_r2")


def test_r2_used_two_clean_archives_and_is_byte_equivalent() -> None:
    proof = _load(PROOF_PATH)
    _assert_digest(proof)
    assert proof["status"] == (
        "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible"
    )
    assert proof["attempt_id"].endswith("clean_proof_r2")
    assert proof["clean_git_archives"] == 2
    assert proof["fresh_python_processes"] == 2
    assert proof["fresh_worker_count"] == 2
    assert proof["workers_byte_equivalent"] is True
    assert proof["temporary_roots_removed"] is True
    assert proof["private_input_bundle"]["persisted_to_repository"] is False
    assert proof["private_input_bundle"]["worker_injections_byte_identical"] is True
    assert proof["credential_environment_variables_present_each_worker"] == 0


def test_clean_case_matrix_matches_frozen_implementation() -> None:
    proof = _load(PROOF_PATH)
    implementation = _load(IMPLEMENTATION_PATH)
    _assert_digest(implementation)
    assert proof["implementation_result_digest"] == implementation["result_digest"]
    assert proof["case_matrix"] == implementation["case_matrix"]
    assert set(proof["case_matrix"]) == {"DELL", "MU", "NVDA", "ORCL", "ASML", "ANET"}
    assert all(row["conflicts"] == 0 for row in proof["case_matrix"].values())


def test_zero_call_guard_mutations_and_private_successor_boundary_pass() -> None:
    proof = _load(PROOF_PATH)
    assert proof["observed_calls"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
    }
    assert all(proof["mutations"].values())
    assert proof["successor"]["raw_source_material_count"] == 27
    assert proof["successor"]["raw_source_content_in_model_input"] is False
    assert proof["successor"]["source_text_field_absent"] is True
    assert proof["successor"]["known_raw_sentence_absent"] is True


def test_clean_proof_does_not_predeclare_product_acceptance() -> None:
    stage = _load(PROOF_PATH)["stage_acceptance"]
    assert stage["runtime_implementation"] is True
    assert stage["six_case_deterministic_replay"] is True
    assert stage["clean_independent_proof"] is True
    assert stage["natural_model_canary"] is False
    assert stage["dell_delivery_pass"] is False
    assert stage["owner_acceptance"] is False
    assert stage["release"] is False
