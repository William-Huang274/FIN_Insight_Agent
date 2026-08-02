from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_current_evidence_reconciliation_"
    "independent_assessment_and_closeout_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_8.json"
)
HISTORICAL_ASSESSMENT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_assessment_v1_0.json"
)
HISTORICAL_CLOSEOUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_closeout_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_closeout_consumes_only_the_authorized_assessment_package() -> None:
    closeout = _load(CLOSEOUT)
    authority = closeout["authority"]

    assert closeout["status"] == "pass_current_S1_closed_S2_stage_plan_next"
    assert authority["maximum_runtime_implementation_bundles"] == 0
    assert authority["maximum_new_hermetic_or_clean_environment_proof_packages"] == 0
    assert authority["maximum_current_assessment_and_closeout_packages"] == 1
    assert authority["assessment_and_closeout_packages_consumed"] == 1
    assert closeout["observed_counts"]["runtime_implementation_bundles"] == 0
    assert closeout["observed_counts"]["model_calls"] == 0


def test_current_host_and_formal_evidence_are_both_green() -> None:
    closeout = _load(CLOSEOUT)
    host = closeout["independent_current_host_assessment"]
    formal = closeout["reused_formal_evidence"]["formal_result"]

    assert (host["passed"], host["failed"], host["collection_errors"]) == (56, 0, 0)
    assert sum(family["collected"] for family in host["families"]) == 56
    assert formal["disposable_runtime_count"] == 2
    assert formal["each_disposable_passed"] == 58
    assert formal["each_disposable_failed"] == 0
    assert formal["realistic_three_case_tests_each_disposable"] == 31
    assert formal["semantic_parity"] is True
    assert formal["raw_parity"] is True


def test_all_critical_assets_still_match_the_assessed_bytes() -> None:
    closeout = _load(CLOSEOUT)
    reconciliation = closeout["critical_asset_reconciliation"]

    assert reconciliation["status"] == "pass_all_current_bytes_equal_formal_package"
    assert reconciliation["asset_count"] == len(reconciliation["assets"]) == 8
    for asset in reconciliation["assets"]:
        assert _sha256(ROOT / asset["ref"]) == asset["sha256"]


def test_historical_failed_assessment_and_closeout_remain_immutable() -> None:
    closeout = _load(CLOSEOUT)

    assert _sha256(HISTORICAL_ASSESSMENT) == (
        "f4487ad883f911862a47b10946afa73b694755049671edd65bed6fb3228c7c9e"
    )
    assert _sha256(HISTORICAL_CLOSEOUT) == (
        "91fa819f69aebb95dcfe3303031aba0a7f46553c0049bc528ced67c6a5fe0a5c"
    )
    assert closeout["historical_preservation"]["historical_S1_T03_T04_failures_rewritten"] is False
    assert closeout["historical_preservation"]["historical_assessment_or_closeout_rewritten"] is False


def test_only_S1_engineering_gates_close_and_product_truth_does_not_inflate() -> None:
    closeout = _load(CLOSEOUT)
    gates = closeout["gate_assessment"]
    stages = closeout["stage_acceptance"]

    assert gates["G0_scope_and_owner"].startswith("pass_")
    assert gates["G1_contract_closure"].startswith("pass_")
    assert gates["G2_deterministic_proof"].startswith("pass_")
    assert gates["G4_failure_observability"].startswith("pass_")
    assert gates["G6_current_assessment_and_closeout"] == "pass"
    assert gates["G3_natural_canary"] == "not_run_owned_by_S2"
    assert gates["G5_product_proof"] == "not_run_owned_by_S2_to_S4"
    assert stages["FIN_0_1_2_S1"] == "pass_closed_current_consolidated_baseline"
    assert stages["FIN_0_1_2_S2"] == "not_started_stage_plan_next"
    assert stages["release_qualified"] is False


def test_projection_binds_closeout_and_routes_to_S2_planning_without_call_authority() -> None:
    closeout = _load(CLOSEOUT)
    projection = _load(PROJECTION)

    assert projection["decision_binding"]["ref"] == CLOSEOUT.relative_to(ROOT).as_posix()
    assert projection["decision_binding"]["sha256"] == _sha256(CLOSEOUT)
    assert projection["current_truth"]["stage"] == "S2"
    assert projection["current_truth"]["downstream_stages_started"]["S2"] is False
    assert projection["current_truth"]["release_qualified"] is False
    assert projection["current_truth"]["S2_stage_plan_authorized"] is True
    assert projection["current_truth"]["S2_model_canary_authorized"] is False
    assert projection["execution_authority"][
        "credential_model_provider_network_business_authorized"
    ] is False
    assert projection["current_truth"]["current_next_action"] == closeout["next_action"]
