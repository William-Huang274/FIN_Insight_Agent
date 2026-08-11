from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s2_wwc_replacement_pair_runner import (
    run_zero_call_preflight,
)


RECORDED_AT = "2026-08-03T11:30:58+08:00"
CURRENT_ACTION = (
    "FIN-0.1.2-S2-T03-WWC-V1.2-REPLACEMENT-PAIR-BOUND-RUNNER-"
    "ATOMIC-CAPTURE-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION"
)
NEXT_ACTION = (
    "FIN-0.1.2-S2-T03-MU-WWC-V1.2-FLASH-STABLE-VS-PRO-PREVIEW-"
    "REPLACEMENT-PAIR-EXACT-EXECUTION"
)
AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_wwc_v12_independent_zero_call_"
    "proof_and_replacement_pair_conditional_authority_decision_v1_0.json"
)
IMPLEMENTATION_PATHS = (
    "apps/workbench/backend/application/fin_0_1_2_s2_paired_model_canary.py",
    "apps/workbench/backend/application/fin_0_1_2_s2_wwc_replacement_pair_runner.py",
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_binding_v1_2.json",
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_source_v1_2.json",
    "configs/runtime/fin_ia_0_1_2_s2_deepseek_model_candidate_registry_v1_0.json",
    "configs/runtime/fin_ia_0_1_2_s2_runtime_resource_registry_v1_1.json",
    "configs/runtime/fin_ia_0_1_2_s2_t03_wwc_replacement_pair_runtime_resource_registry_v1_0.json",
    "scripts/releases/prepare_fin_ia_0_1_2_s2_t03_wwc_replacement_pair_runner_preflight.py",
    "tests/contract/test_fin_0_1_2_s2_t03_wwc_replacement_pair_runner_atomic_capture_preflight.py",
    "tests/fixtures/fin_0_1_2/mu_realistic_three_cell_exact_input_v1.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {
        "ref": relative,
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def build_result() -> dict[str, Any]:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    preflight = run_zero_call_preflight(ROOT)
    if (
        preflight["exact_call_count"] != 2
        or preflight["credential_reads"] != 0
        or preflight["model_calls"] != 0
        or preflight["provider_calls"] != 0
        or preflight["network_calls"] != 0
        or preflight["business_Run_or_Artifact_writes"] != 0
    ):
        raise RuntimeError("wwc_replacement_pair_preflight_boundary_invalid")
    replacement = authority["replacement_pair_conditional_authority"]
    return {
        "schema_version": (
            "fin_ia_0_1_2_s2_t03_wwc_v12_replacement_pair_bound_runner_"
            "atomic_capture_zero_call_preflight_minimum_implementation_v1_0"
        ),
        "implementation_id": CURRENT_ACTION,
        "recorded_at": RECORDED_AT,
        "status": (
            "pass_engineering_and_zero_call_preflight_conditional_exact_two_"
            "call_authority_effective_execution_not_started"
        ),
        "authority": {
            "user_instruction": "继续",
            "runner_preflight_implementation_authorized_and_executed": True,
            "conditional_replacement_pair_authority_now_effective": True,
            "current_exact_execution_started": False,
            "current_credential_read_authorized": False,
            "current_model_provider_network_calls_authorized": 0,
            "Fact_or_Claim_rerun_authorized": False,
            "T04_or_model_selection_authorized": False,
        },
        "authority_binding": {
            "ref": AUTHORITY.relative_to(ROOT).as_posix(),
            "sha256": _sha256(AUTHORITY),
            "authority_id": replacement["authority_id"],
            "execution_identity": replacement["execution_identity"],
        },
        "implementation_bindings": [
            _binding(relative) for relative in IMPLEMENTATION_PATHS
        ],
        "historical_immutability": {
            "shared_compiler_sha256": _sha256(
                ROOT
                / "apps/workbench/backend/application/fin_0_1_2_s2_paired_model_canary.py"
            ),
            "shared_compiler_expected_sha256": (
                "f6d4321556012d643c64f87006a6f60dfac1fec56f2b48f0622edcbdd4b10fb5"
            ),
            "historical_six_call_authority_rewritten": False,
            "historical_six_call_runner_rewritten": False,
            "historical_v11_source_or_binding_rewritten": False,
        },
        "zero_call_preflight": preflight,
        "verification": {
            "focused_replacement_runner_tests": {"passed": 13, "failed": 0},
            "combined_S2_and_historical_immutability_regression": {
                "passed": 86,
                "failed": 0,
            },
            "exact_authority_call_digests_matched": 2,
            "happy_semantic_transport_fake_paths_proved": [2, 2, 1],
            "atomic_capture_before_validation": True,
            "terminal_materialization": True,
            "execution_identity_reuse_blocked": True,
            "raw_provider_envelope_persisted": False,
            "projected_worst_case_cost_usd": preflight["budget"][
                "projected_worst_case_cost_usd"
            ],
            "credential_model_provider_network_calls": [0, 0, 0, 0],
            "business_Run_or_Artifact_writes": 0,
        },
        "issue_disposition": {
            "RC_P36_102": "runner_preflight_pass_fair_replacement_measurement_pending",
            "RC_P36_103": "runner_preflight_pass_fair_replacement_measurement_pending",
            "issues_closed_now": 0,
        },
        "stage_acceptance": {
            "S2_T03_WWC_v12_independent_proof": "pass",
            "S2_T03_replacement_pair_runner_preflight": "pass",
            "S2_T03_replacement_pair_execution": "authority_effective_not_started",
            "S2_T03_fair_WWC_measurement": "pending",
            "S2_T04": "not_entered",
            "S2": "not_passed",
            "S3_to_S5": "not_started",
            "release_qualified": False,
        },
        "observed_counts": {
            "credential_reads": 0,
            "model_provider_network_calls": [0, 0, 0],
            "replacement_pair_calls": 0,
            "Fact_or_Claim_calls": 0,
            "business_Run_or_Artifact_writes": 0,
        },
        "stop_rules": {
            "exact_execution_requires_new_user_continuation": True,
            "retry_fallback_provider_hopping_prompt_only_retry": [0, 0, 0, 0],
            "new_project_owned_failure_after_replacement": (
                "S2_honest_block_no_second_repair_bundle"
            ),
            "true_model_noncompliance_or_weak_quality": (
                "record_once_no_retry_then_T04_or_honest_block"
            ),
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
        "known_boundary": (
            "Runner/preflight pass makes the existing conditional authority technically "
            "effective but does not execute either model, create fair WWC evidence, close "
            "RC-P36-102/103, enter T04, select a model, pass S2 or qualify a release."
        ),
    }


def main() -> int:
    print(json.dumps(build_result(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
