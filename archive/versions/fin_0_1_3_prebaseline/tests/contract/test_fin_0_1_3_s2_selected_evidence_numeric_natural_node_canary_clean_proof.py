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
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_independent_proof_v1_0.json"
)
FAILURE_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_proof_attempt_r1_failure_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_digest(payload: dict) -> None:
    body = {key: value for key, value in payload.items() if key != "result_digest"}
    assert payload["result_digest"] == canonical_digest(body)


def test_r1_crlf_lf_failure_is_preserved_and_zero_call() -> None:
    failure = _load(FAILURE_PATH)
    _assert_digest(failure)
    assert failure["attempt_id"].endswith("clean_proof_r1")
    assert failure["status"] == "terminal_failed_clean_portability_binding_only"
    assert failure["failure_code"] == (
        "natural_node_canary_clean_proof_binding_sha256_drift_crlf_lf"
    )
    assert failure["scope"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "fixture_provider_invocations": 0,
        "business_artifact_promotion": False,
    }
    assert failure["temporary_roots_removed"] is True
    assert failure["successor_attempt"].endswith("clean_proof_r2")


def test_r2_is_two_clean_archives_two_fresh_processes_and_byte_equivalent() -> None:
    proof = _load(PROOF_PATH)
    _assert_digest(proof)
    assert proof["attempt_id"].endswith("clean_proof_r2")
    assert proof["status"] == (
        "pass_two_clean_archives_two_fresh_processes_"
        "zero_external_call_reproducible"
    )
    assert proof["clean_git_archives"] == 2
    assert proof["fresh_python_processes"] == 2
    assert proof["fresh_worker_count"] == 2
    assert proof["workers_byte_equivalent"] is True
    assert proof["temporary_roots_removed"] is True
    assert proof["credential_environment_variables_present_each_worker"] == 0


def test_clean_workers_recompile_exact_bounded_canary() -> None:
    proof = _load(PROOF_PATH)
    implementation = _load(IMPLEMENTATION_PATH)
    _assert_digest(implementation)
    assert proof["implementation_result_digest"] == implementation["result_digest"]
    compiled = proof["compiled_canary"]
    assert compiled["compiled_input_digest"] == (
        implementation["compiled_canary"]["compiled_input_digest"]
    )
    assert compiled["request_characters"] == 11838
    assert compiled["evidence_aliases"] == ["E022", "E018", "E023"]
    assert len(compiled["numeric_refs"]) == 4
    assert compiled["raw_source_text_in_model_input"] is False
    assert len(proof["private_artifact_injections"]) == 2
    assert proof["private_artifacts_persisted_to_repository"] is False


def test_clean_runtime_outcomes_preserve_capture_and_exact_once() -> None:
    outcomes = _load(PROOF_PATH)["runtime_outcomes"]
    assert outcomes == {
        "business_artifact_promotion": False,
        "full_transport_response_capture_preserved": True,
        "invalid_json": "natural_node_canary_output_json_invalid",
        "length": "natural_node_canary_incomplete_finish_reason_length",
        "same_admission_second_consumption_rejected": True,
        "success": "natural_node_canary_completed_no_promotion",
        "transport": "natural_node_canary_provider_failure:provider_error",
    }


def test_clean_mutations_preserve_research_and_numeric_boundaries() -> None:
    mutations = _load(PROOF_PATH)["mutations"]
    assert all(mutations.values())
    assert mutations["valid_fy2027_prose_passes"] is True
    assert mutations["unbound_material_money_fails_local_guard"] is True
    assert mutations["competitor_readthrough_as_direct_support_fails_closed"] is True
    assert mutations["missing_durability_boundary_fails_closed"] is True


def test_proof_has_zero_external_calls_and_does_not_predeclare_live_acceptance() -> None:
    proof = _load(PROOF_PATH)
    calls = proof["observed_calls"]
    assert {key: calls[key] for key in (
        "model_calls",
        "provider_calls",
        "network_calls",
        "source_calls",
        "retries",
    )} == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
    }
    assert calls["fixture_provider_invocations_per_worker"] == 4
    assert calls["fixture_provider_invocations_total"] == 8
    stage = proof["stage_acceptance"]
    assert stage["canary_clean_proof"] is True
    assert stage["natural_model_canary"] is False
    assert stage["dell_delivery_pass"] is False
    assert stage["owner_acceptance"] is False
    assert stage["release"] is False
