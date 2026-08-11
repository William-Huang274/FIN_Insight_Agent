from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary_runner import (
    build_bound_compiler,
)
from test_fin_0_1_2_s2_t03_wwc_consolidated_zero_call_implementation import (
    test_claim_binding_is_row_local_for_one_claim_multi_claim_and_truncation,
    test_date_negative_matrix_fails_typed_after_capture,
    test_date_positive_matrix_covers_every_alias_and_relative_cadence,
    test_flash_and_pro_receive_byte_identical_recompiled_wwc_requests,
    test_one_declarative_date_rule_is_visible_to_all_contract_consumers,
    test_provider_permutation_does_not_change_selection_or_claim_binding,
    test_sanitized_restricted_pro_shape_replay_no_longer_false_greens,
    test_three_case_full_fake_preserves_local_truth_and_audit_chain,
)


IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_wwc_contract_parity_and_"
    "row_local_binding_consolidated_zero_call_implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_wwc_v12_independent_zero_call_"
    "proof_and_replacement_pair_conditional_authority_decision_v1_0.json"
)
V11_SOURCE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "source_v1_1.json"
)
V11_BINDING = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "binding_v1_1.json"
)
CURRENT_ACTION = (
    "FIN-0.1.2-S2-T03-WWC-V2-INDEPENDENT-ZERO-CALL-PROOF-AND-"
    "AFFECTED-FAMILY-REPLACEMENT-PAIR-AUTHORITY-DECISION"
)
NEXT_ACTION = (
    "FIN-0.1.2-S2-T03-WWC-V1.2-REPLACEMENT-PAIR-BOUND-RUNNER-"
    "ATOMIC-CAPTURE-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION"
)
WWC_FAMILY = "what_would_change_atoms"
RECORDED_AT = "2026-08-03T10:54:54+08:00"


class Fin012S2T03WWCV12IndependentProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Fin012S2T03WWCV12IndependentProofError(code)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _verify_implementation_bindings(
    implementation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for binding in implementation["implementation_bindings"]:
        path = ROOT / str(binding["ref"])
        _require(path.is_file(), f"implementation_binding_missing:{binding['ref']}")
        _require(
            path.stat().st_size == int(binding["bytes"]),
            f"implementation_binding_bytes_drift:{binding['ref']}",
        )
        _require(
            _sha256(path) == str(binding["sha256"]),
            f"implementation_binding_digest_drift:{binding['ref']}",
        )
        verified.append(dict(binding))
    return verified


def _deny_network(*_: Any, **__: Any) -> Any:
    raise Fin012S2T03WWCV12IndependentProofError(
        "network_forbidden_during_zero_call_proof"
    )


def _run_independent_matrix(disposable_root: Path) -> dict[str, Any]:
    _require(disposable_root.is_dir(), "disposable_root_missing")
    _require(
        not any(
            key.upper().endswith(("API_KEY", "TOKEN", "PASSWORD", "SECRET"))
            for key in os.environ
        ),
        "credential_environment_not_scrubbed",
    )
    socket.create_connection = _deny_network  # type: ignore[assignment]
    socket.socket.connect = _deny_network  # type: ignore[method-assign]

    implementation = _load(IMPLEMENTATION)
    bindings = _verify_implementation_bindings(implementation)
    _require(
        _sha256(V11_SOURCE)
        == "15c4be902cebc72ea8ef24008de0b2177eb1259a5aded0c78e758e8e91ce7501",
        "historical_v11_source_rewritten",
    )
    _require(
        _sha256(V11_BINDING)
        == "2e233d2a58449398774f2b1a21c84b215a82a81b4ef8552d3b86f9876408b420",
        "historical_v11_binding_rewritten",
    )

    test_one_declarative_date_rule_is_visible_to_all_contract_consumers()
    test_flash_and_pro_receive_byte_identical_recompiled_wwc_requests()
    test_date_positive_matrix_covers_every_alias_and_relative_cadence()
    for cadence, alias_mode, expected_code in (
        ("bound_date", "NONE", "s4_compiled_wwc_bound_date_alias_required"),
        (
            "next_reporting_event",
            "KNOWN",
            "s4_compiled_wwc_unbound_date_alias_forbidden",
        ),
        (
            "bound_date",
            "D-CROSS-CASE",
            "s4_compiled_wwc_date_alias_unknown_or_cross_case",
        ),
    ):
        test_date_negative_matrix_fails_typed_after_capture(
            cadence,
            alias_mode,
            expected_code,
        )
    test_claim_binding_is_row_local_for_one_claim_multi_claim_and_truncation()
    test_provider_permutation_does_not_change_selection_or_claim_binding()
    test_sanitized_restricted_pro_shape_replay_no_longer_false_greens()
    for ticker in ("DELL", "MU", "NVDA"):
        test_three_case_full_fake_preserves_local_truth_and_audit_chain(ticker)

    compiler, _ = build_bound_compiler(ROOT)
    calls = compiler.compile_primary_calls()
    pair = [call for call in calls if call.family_id == WWC_FAMILY]
    _require(len(pair) == 2, "replacement_pair_call_count_invalid")
    _require(
        {call.candidate.candidate_id for call in pair}
        == {"flash_stable", "pro_preview"},
        "replacement_pair_candidates_invalid",
    )
    _require(pair[0].messages == pair[1].messages, "replacement_pair_prompt_drift")
    _require(
        len({call.model_visible_request_digest for call in pair}) == 1,
        "replacement_pair_request_digest_drift",
    )
    _require(
        len({call.request_equivalence_digest for call in pair}) == 1,
        "replacement_pair_equivalence_digest_drift",
    )
    outcomes = [
        compiler.materialize_response(call, compiler.fake_provider_response(call))
        for call in pair
    ]
    _require(
        [outcome["status"] for outcome in outcomes] == ["pass", "pass"],
        "replacement_pair_fake_materialization_failed",
    )

    atom_compiler = compiler._compilers[WWC_FAMILY]
    rule = atom_compiler.review_date_alias_binding_contract()
    call_plan = [
        {
            "call_id": (
                "fin012-s2-mu-what_would_change_atoms-"
                f"{call.candidate.candidate_id}-replacement-r1"
            ),
            "family_id": call.family_id,
            "candidate_id": call.candidate.candidate_id,
            "model": call.candidate.model,
            "model_ref": call.candidate.model_ref,
            "model_visible_request_digest": call.model_visible_request_digest,
            "request_equivalence_digest": call.request_equivalence_digest,
        }
        for call in pair
    ]
    binding_fingerprint = _digest(
        [
            {"ref": row["ref"], "sha256": row["sha256"], "bytes": row["bytes"]}
            for row in bindings
        ]
    )
    return {
        "status": "pass",
        "implementation_binding_fingerprint": binding_fingerprint,
        "implementation_sha256": _sha256(IMPLEMENTATION),
        "historical_v11_source_binding_immutable": True,
        "contract_ref": "fin_0_1_2.common_runtime.judgment_atom_family:v1.2.0",
        "date_rule_digest": _digest(rule),
        "date_positive_matrix": "pass",
        "date_negative_typed_capture_first_count": 3,
        "row_local_claim_authority_matrix": "pass",
        "provider_permutation_and_six_to_three_selection": "pass",
        "sanitized_restricted_shape_replay_unique_claim_ids": 2,
        "three_case_full_fake": {ticker: [6, 6] for ticker in ("DELL", "MU", "NVDA")},
        "replacement_pair_fake_statuses": ["pass", "pass"],
        "replacement_pair_call_plan": call_plan,
        "request_digest": pair[0].model_visible_request_digest,
        "equivalence_digest": pair[0].request_equivalence_digest,
        "credential_reads": 0,
        "model_provider_network_calls": [0, 0, 0],
        "business_Run_or_Artifact_writes": 0,
        "disposable_root_used": True,
    }


def _fresh_worker_output(disposable_root: Path) -> dict[str, Any]:
    env = dict(os.environ)
    for key in list(env):
        upper = key.upper()
        if upper.endswith(("API_KEY", "TOKEN", "PASSWORD", "SECRET")):
            env.pop(key, None)
    env["TEMP"] = str(disposable_root)
    env["TMP"] = str(disposable_root)
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--worker",
            str(disposable_root),
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    _require(
        completed.returncode == 0,
        "fresh_worker_failed:" + completed.stderr[-500:],
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise Fin012S2T03WWCV12IndependentProofError(
            "fresh_worker_output_invalid"
        ) from exc


def build_decision() -> dict[str, Any]:
    implementation = _load(IMPLEMENTATION)
    bindings_before = _verify_implementation_bindings(implementation)
    target_before = _digest(bindings_before)
    with tempfile.TemporaryDirectory(prefix="fin012-s2-t03-wwc-proof-a-") as first:
        first_output = _fresh_worker_output(Path(first))
    with tempfile.TemporaryDirectory(prefix="fin012-s2-t03-wwc-proof-b-") as second:
        second_output = _fresh_worker_output(Path(second))
    _require(first_output == second_output, "independent_worker_outputs_differ")
    bindings_after = _verify_implementation_bindings(implementation)
    target_after = _digest(bindings_after)
    _require(target_before == target_after, "target_binding_state_changed")

    generator_ref = _display(Path(__file__))
    implementation_ref = _display(IMPLEMENTATION)
    pair_plan = deepcopy(first_output["replacement_pair_call_plan"])
    return {
        "schema_version": (
            "fin_ia_0_1_2_s2_t03_wwc_v12_independent_zero_call_proof_and_"
            "replacement_pair_conditional_authority_decision_v1_0"
        ),
        "decision_id": CURRENT_ACTION,
        "recorded_at": RECORDED_AT,
        "status": (
            "pass_two_fresh_process_zero_call_proof_replacement_pair_"
            "conditionally_authorized_runner_preflight_pending"
        ),
        "authority": {
            "user_instruction": "继续",
            "independent_zero_call_proof_authorized_and_executed": True,
            "future_replacement_pair_conditionally_authorized": True,
            "conditional_authority_effective_only_after_bound_runner_atomic_capture_preflight": True,
            "current_credential_read_authorized": False,
            "current_model_provider_network_calls_authorized": 0,
            "current_replacement_pair_execution_authorized": False,
            "T04_assessment_or_model_selection_authorized": False,
        },
        "source_bindings": {
            "implementation_ref": implementation_ref,
            "implementation_sha256": _sha256(IMPLEMENTATION),
            "proof_generator_ref": generator_ref,
            "proof_generator_sha256": _sha256(Path(__file__)),
            "verified_implementation_binding_count": len(bindings_before),
            "implementation_binding_fingerprint": first_output[
                "implementation_binding_fingerprint"
            ],
        },
        "independent_proof": {
            "fresh_processes": 2,
            "distinct_disposable_roots": 2,
            "normalized_outputs_byte_equal": _canonical_bytes(first_output)
            == _canonical_bytes(second_output),
            "credential_environment_scrubbed": True,
            "network_guard_installed": True,
            "target_binding_state_before": target_before,
            "target_binding_state_after": target_after,
            "target_binding_state_unchanged": target_before == target_after,
            "result_digest": _digest(first_output),
            "matrix": {
                key: value
                for key, value in first_output.items()
                if key
                not in {
                    "replacement_pair_call_plan",
                    "implementation_binding_fingerprint",
                }
            },
        },
        "replacement_pair_conditional_authority": {
            "authority_id": (
                "FIN-0.1.2-S2-T03-MU-WWC-V1.2-FLASH-STABLE-VS-PRO-"
                "PREVIEW-REPLACEMENT-PAIR-R1"
            ),
            "status": "conditional_future_exact_two_call_authority_issued_unconsumed",
            "execution_identity": "fin012-s2-t03-mu-wwc-v12-replacement-pair-r1",
            "case": "MU",
            "program_cell_id": "demand_authenticity_and_sustainability",
            "family": WWC_FAMILY,
            "exact_call_count": 2,
            "Fact_or_Claim_rerun": False,
            "call_plan": pair_plan,
            "request_digest": first_output["request_digest"],
            "equivalence_digest": first_output["equivalence_digest"],
            "provider_route": {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com/beta",
                "wire_api": "chat_completions_json_object",
                "thinking": "disabled",
                "reasoning_effort": "none",
                "temperature": 0.0,
                "stream": False,
                "timeout_seconds_per_call": 120,
            },
            "hard_budget": {
                "semantic_model_calls": 2,
                "maximum_transport_attempts_per_call": 1,
                "retry_budget": 0,
                "fallback_budget": 0,
                "provider_hopping_budget": 0,
                "prompt_only_retry_budget": 0,
                "maximum_input_tokens": 10000,
                "maximum_output_tokens": 2800,
                "maximum_total_cost_usd": 0.015,
                "maximum_wall_clock_seconds": 300,
                "business_Run_or_Artifact_writes": 0,
            },
            "capture_requirements": {
                "capture_before_local_validation": True,
                "full_model_visible_request_and_final_assistant_output": True,
                "safe_terminal_usage_finish_reason_and_model": True,
                "credentials_headers_cookies_private_reasoning_excluded": True,
                "failed_output_business_promotable": False,
            },
            "preconditions_before_execution": [
                "dedicated_exact_two_call_runner_binds_this_authority_and_v1_2_resources",
                "atomic_restricted_capture_and_terminal_result_zero_call_preflight_passes",
                "fresh_execution_identity_is_unclaimed",
                "credential_presence_is_checked_without_value_persistence",
                "Project_OS_and_budget_preflights_pass",
            ],
            "automatic_execution_now": False,
        },
        "issue_disposition": {
            "RC_P36_102": "independent_proof_pass_fair_replacement_measurement_pending",
            "RC_P36_103": "independent_proof_pass_fair_replacement_measurement_pending",
            "issues_closed_now": 0,
            "reason": "deterministic repair is independently reproduced but no fair natural WWC replacement outputs exist",
        },
        "stage_acceptance": {
            "S2_T03_WWC_v12_independent_proof": "pass",
            "S2_T03_replacement_pair": "conditionally_authorized_not_executed",
            "S2_T03_fair_WWC_measurement": "pending",
            "S2_T04": "not_entered",
            "S2": "not_passed",
            "S3_to_S5": "not_started",
            "release_qualified": False,
        },
        "observed_counts": {
            "fresh_processes": 2,
            "disposable_roots": 2,
            "credential_reads": 0,
            "model_provider_network_calls": [0, 0, 0],
            "replacement_pair_calls": 0,
            "business_Run_or_Artifact_writes": 0,
        },
        "stop_rules": {
            "runner_or_preflight_failure": "stop_no_execution",
            "new_project_owned_failure_after_replacement": "S2_honest_block_no_second_repair_bundle",
            "true_model_noncompliance_or_weak_quality": "record_once_no_retry_then_T04_or_honest_block",
            "automatic_second_repair_or_replacement_pair": False,
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
        "known_boundary": (
            "Independent proof and conditional authority do not execute or qualify either model, "
            "close RC-P36-102/103, enter T04, pass S2, produce business Artifacts, or qualify a release."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker is not None:
        print(_canonical_bytes(_run_independent_matrix(args.worker)).decode("utf-8"))
        return 0
    print(json.dumps(build_decision(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
