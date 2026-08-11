from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_"
    "candidate_pool_planner_independent_fresh_agent_proof_failure_"
    "result_v1_0.json"
)
NEXT = (
    "S4-T06-INDEPENDENT-FACT-CANDIDATE-POOL-PROOF-FIRST-"
    "DISPOSABLE-RUNTIME-FAILURE-ROOT-CAUSE-OR-BLOCK-DISPOSITION-DECISION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_failure_result_binds_executed_authority_and_runner() -> None:
    result = _load(RESULT)

    assert _sha256(ROOT / result["authority"]["ref"]) == (
        result["authority"]["sha256"]
    )
    assert _sha256(ROOT / result["proof_generator"]["ref"]) == (
        result["proof_generator"]["sha256"]
    )
    assert result["authority"]["proof_packages_authorized"] == 1
    assert result["authority"]["proof_packages_consumed"] == 1
    assert (
        result["authority"]["automatic_follow_on_or_second_package_authorized"]
        is False
    )


def test_first_disposable_failure_stops_before_second_invocation() -> None:
    result = _load(RESULT)
    generator = result["proof_generator"]
    failure = result["first_credible_failure"]

    assert result["status"].startswith(
        "terminal_failed_first_disposable_runtime_pytest"
    )
    assert generator["planned_disposable_runtime_roots"] == 2
    assert generator["started_disposable_runtime_roots"] == 1
    assert generator["completed_successful_disposable_runtime_roots"] == 0
    assert generator["second_runtime_started"] is False
    assert generator["temporary_runtime_roots_remaining"] == 0
    assert failure["passed_tests"] == 11
    assert failure["failed_tests"] == 9
    assert failure["root_cause_established"] is False
    assert failure["complete_failed_nodeid_list_persisted"] is False
    assert failure["failure_observability_gap"] is True


def test_failure_does_not_claim_model_network_or_business_regression() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]
    boundary = result["boundary_audit"]

    assert failure["shared_runtime_business_contract_regression_established"] is False
    assert failure["model_or_provider_fault_established"] is False
    assert failure["network_fault_established"] is False
    assert boundary["source_runtime_or_profile_repair_during_proof"] is False
    assert boundary["credential_presence_or_value_reads"] == 0
    assert boundary["model_calls"] == 0
    assert boundary["provider_calls"] == 0
    assert boundary["network_calls_observed"] == 0
    assert boundary["exact_live_runs"] == 0
    assert boundary["automatic_retry_or_second_proof"] == 0


def test_target_audit_and_disposition_remain_fail_closed() -> None:
    result = _load(RESULT)
    target = result["target_read_only_audit"]
    disposition = result["proof_disposition"]

    assert target["proof_started_after_latest_target_write"] is True
    assert target["target_write_path_reachable_from_disposable_worker"] is False
    assert target["target_writes_observed"] == 0
    assert disposition["independent_proof_passed"] is False
    assert disposition["RC_P36_084_closed"] is False
    assert disposition["automatic_runner_patch_or_rerun_allowed"] is False
    assert disposition["automatic_runtime_repair_allowed"] is False
    assert disposition["automatic_admission_or_live_allowed"] is False


def test_result_advances_only_to_zero_call_disposition() -> None:
    result = _load(RESULT)
    stage = result["stage_acceptance"]

    assert result["next_action"] == NEXT
    assert result["next_action_authorized"] is False
    assert stage["RC_P36_084"] == "open_independent_proof_not_achieved"
    assert stage["RC_P36_085"] == (
        "open_zero_call_root_cause_or_block_disposition_pending"
    )
    assert stage["S4_T06"] == "engineering_pass_live_product_blocked_not_closed"
    assert stage["S4_T07"] == "not_entered"
