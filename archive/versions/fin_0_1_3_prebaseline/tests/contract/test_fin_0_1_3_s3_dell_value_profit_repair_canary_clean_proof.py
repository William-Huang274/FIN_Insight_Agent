from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_independent_proof_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_digest(payload: dict) -> None:
    body = {key: value for key, value in payload.items() if key != "result_digest"}
    assert payload["result_digest"] == canonical_digest(body)


def test_proof_is_two_clean_archives_two_fresh_processes_and_byte_equivalent() -> None:
    proof = _load(PROOF_PATH)
    _assert_digest(proof)
    assert proof["status"] == (
        "pass_two_clean_archives_two_fresh_processes_"
        "zero_external_call_reproducible"
    )
    assert proof["implementation_commit"] == (
        "d925aa89d8e289ca4d477437a636dd24d32155ec"
    )
    assert proof["clean_git_archives"] == 2
    assert proof["fresh_python_processes"] == 2
    assert proof["workers_byte_equivalent"] is True
    assert proof["temporary_roots_removed"] is True
    assert proof["credential_environment_variables_present_each_worker"] == 0


def test_workers_recompile_the_exact_current_pack_repair_canary() -> None:
    proof = _load(PROOF_PATH)
    implementation = _load(IMPLEMENTATION_PATH)
    _assert_digest(implementation)
    assert proof["implementation_result_digest"] == implementation["result_digest"]
    compiled = proof["compiled_canary"]
    assert compiled["compiled_input_digest"] == (
        implementation["compiled_canary"]["compiled_input_digest"]
    )
    assert compiled["request_digest"] == (
        implementation["compiled_canary"]["request_digest"]
    )
    assert compiled["request_characters"] == 17343
    assert compiled["evidence_aliases"] == ["E002", "E008", "E021", "E023"]
    assert compiled["affected_cell_ids"] == (
        implementation["compiled_canary"]["affected_cell_ids"]
    )
    assert compiled["raw_source_text_in_model_input"] is False
    assert len(proof["private_artifact_injections"]) == 2
    assert proof["private_artifacts_persisted_to_repository"] is False


def test_runtime_preserves_capture_exact_once_and_all_failure_phases() -> None:
    outcomes = _load(PROOF_PATH)["runtime_outcomes"]
    assert outcomes == {
        "business_artifact_promotion": False,
        "full_transport_response_capture_preserved": True,
        "invalid_json": "s3_repair_canary_invalid_json",
        "invalid_semantics": "s3_repair_canary_evidence_semantics_invalid",
        "length": "s3_repair_canary_incomplete_finish_reason_length",
        "same_admission_second_consumption_rejected": True,
        "success": "s3_repair_canary_pass",
        "transport": "s3_repair_canary_provider_failure:provider_error",
    }


def test_mutations_preserve_financial_and_affected_cell_boundaries() -> None:
    mutations = _load(PROOF_PATH)["mutations"]
    assert all(mutations.values())
    assert mutations["valid_partial_resolution_passes"] is True
    assert mutations["segment_evidence_cannot_replace_product_profit"] is True
    assert mutations["cash_gap_cannot_be_dropped"] is True
    assert mutations["model_numeric_surface_fails_closed"] is True
    assert mutations[
        "valuation_expectations_cell_cannot_be_falsely_reopened"
    ] is True


def test_proof_has_zero_external_calls_and_no_predeclared_acceptance() -> None:
    proof = _load(PROOF_PATH)
    calls = proof["observed_calls"]
    assert {
        key: calls[key]
        for key in (
            "model_calls",
            "provider_calls",
            "network_calls",
            "source_calls",
            "retries",
        )
    } == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
    }
    assert calls["fixture_provider_invocations_per_worker"] == 5
    assert calls["fixture_provider_invocations_total"] == 10
    stage = proof["stage_acceptance"]
    assert stage["canary_clean_proof"] is True
    assert stage["natural_model_canary"] is False
    assert stage["dell_delivery_pass"] is False
    assert stage["qualified_human_acceptance"] is False
    assert stage["owner_acceptance"] is False
    assert stage["release"] is False
