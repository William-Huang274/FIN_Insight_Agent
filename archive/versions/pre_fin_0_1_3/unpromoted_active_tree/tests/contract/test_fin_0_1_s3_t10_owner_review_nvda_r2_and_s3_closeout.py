from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
ASSESSMENT = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_"
    "final_exact_live_and_paired_assessment_v1_0.json"
)
CLOSEOUT = RELEASES / "fin_ia_0_1_s3_t10_owner_review_nvda_r2_and_s3_closeout_v1_0.json"
POLICY = RELEASES / "fin_ia_0_1_s3_t10_d07b_nvda_initial_calibration_policy_v2_0.json"
MANIFEST = RELEASES / "fin_ia_0_1_s3_to_s4_early_delivery_carry_forward_manifest_v1_0.json"
CONTRACT = RELEASES / "fin_ia_0_1_cross_slice_early_delivery_carry_forward_contract_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slice(backlog: dict, slice_id: str) -> dict:
    return next(item for item in backlog["slices"] if item["slice_id"] == slice_id)


def _task(slice_contract: dict, item_id: str) -> dict:
    return next(item for item in slice_contract["items"] if item["item_id"] == item_id)


def test_owner_acceptance_is_bound_to_exact_assessment_and_nine_artifacts() -> None:
    assessment = _load(ASSESSMENT)
    closeout = _load(CLOSEOUT)

    assert closeout["status"] == "pass_owner_accepted_NVDA_R2_S3_closed_S4_entry_ready"
    assert closeout["authority"]["owner_instruction"] == "放行"
    assert closeout["accepted_product"]["assessment_sha256"] == _sha256(ASSESSMENT)
    assert closeout["accepted_product"]["research_run_id"] == assessment["identity"][
        "research_run_id"
    ]
    assert closeout["accepted_product"]["artifact_manifest"] == assessment[
        "artifact_manifest"
    ]
    assert len(closeout["accepted_product"]["artifact_manifest"]) == 9
    assert closeout["owner_review"]["this_record_is_owner_acceptance"] is True
    assert closeout["owner_review"]["machine_verifier_is_owner_acceptance"] is False


def test_D07B_v2_is_NVDA_R2_calibration_without_maturity_inflation() -> None:
    policy = _load(POLICY)
    closeout = _load(CLOSEOUT)

    assert policy["policy_ref"] == "fin01.d07b.NVDA_initial_calibration:v2"
    assert policy["authority"]["owner_instruction"] == "放行"
    assert policy["scope"]["maturity"] == "R2_calibrated_research_output"
    assert policy["scope"]["universal_or_cross_case_calibration_claimed"] is False
    assert [row["program_cell_id"] for row in policy["calibrated_cell_policy"]] == [
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    ]
    assert policy["S4_calibration_boundary"]["case_scope"] == ["NVDA", "DELL", "MU"]
    assert policy["non_inflation"] == {
        "NVDA_R2": True,
        "qualified_senior_R3": False,
        "Alpha": False,
        "release_qualified": False,
        "production_ready": False,
    }
    assert closeout["D07B_initial_calibration"]["policy_sha256"] == _sha256(POLICY)


def test_final_manifest_has_every_required_domain_field_and_disposition() -> None:
    manifest = _load(MANIFEST)
    contract = _load(CONTRACT)
    required_fields = set(contract["required_manifest_item_fields"])
    required_domains = set(contract["required_capability_domains"])
    allowed_maturity = set(contract["allowed_maturity_states"])
    allowed_dispositions = set(
        contract["consumer_contract"]["allowed_later_slice_dispositions"]
    )

    assert manifest["status"] == "final_frozen_by_S3_T10_owner_review_and_closeout"
    assert len(manifest["items"]) == 8
    assert {row["capability_domain"] for row in manifest["items"]} == required_domains
    assert all(required_fields <= set(row) for row in manifest["items"])
    assert all(row["maturity_state"] in allowed_maturity for row in manifest["items"])
    assert all(
        row["later_slice_disposition"] in allowed_dispositions
        for row in manifest["items"]
    )
    assert all(row["do_not_repeat_without_new_evidence"] for row in manifest["items"])
    assert manifest["non_inflation"]["S3_NVDA_R2_owner_accepted"] is True
    assert manifest["non_inflation"]["qualified_senior_R3"] is False
    assert _load(CLOSEOUT)["carry_forward"]["manifest_sha256"] == _sha256(MANIFEST)


def test_backlog_preserves_S3_closeout_and_records_current_S4_failure_boundary() -> None:
    backlog = _load(BACKLOG)
    s3 = _slice(backlog, "S3")
    s4 = _slice(backlog, "S4")
    t09 = _task(s3, "S3-T09")
    t10 = _task(s3, "S3-T10")
    current = backlog["next_action"]

    assert s3["status"] == "pass_NVDA_R2_owner_accepted_S3_T10_closeout_complete"
    assert t09["status"] == (
        "pass_exact_current_nine_artifact_product_paired_assessment_"
        "and_owner_acceptance"
    )
    assert t10["status"] == "pass_owner_review_D07B_v2_NVDA_R2_and_S3_closeout"
    assert s4["status"] == (
        "in_progress_T01_T02_T03_T04_pass_T05_RC_P36_063_"
        "profile_overlay_create_app_preflight_implementation_pending"
    )
    assert current["item_id"] == (
        "S4-T05-DELL-R7-PROFILE-V2-VERSIONED-CASE-RUNTIME-BINDING-AND-"
        "CREATE-APP-PREFLIGHT-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert current["current_S4_T01_completed"] is True
    assert current["current_S4_T02_completed"] is True
    assert current["current_S4_T03_authorized"] is True
    assert current["current_S4_T03_completed"] is True
    assert current["current_S4_T04_authorized"] is True
    assert current["current_S4_T04_decision_completed"] is True
    assert current["current_S4_T04_completed"] is True
    assert current["current_S4_case_execution_authorized"] is True
    assert current["current_S4_case_execution_started"] is True
    assert current["current_S4_T05_authorized"] is True
    assert current["current_S4_T05_exact_execution_completed"] is True
    assert current["current_S4_T05_completed"] is False
    assert current["current_S4_T05_paired_assessment_completed"] is False
    assert current["current_S4_T05_DELL_R2_status"] == (
        "not_proven_R5_terminal_failed_RC_P36_062"
    )
    assert current["current_S4_T05_model_provider_network_calls"] == [3, 3, 3]
    assert current["current_S4_T05_artifact_count"] == 0
    assert current["current_S4_T05_root_cause_disposition_completed"] is True
    assert current["current_S4_T05_zero_call_implementation_authorized"] is True
    assert current["current_S4_T05_RC_P36_060_status"] == (
        "closed_R4_live_path_positive_evidence_before_new_failure"
    )
    assert current["current_S4_T05_RC_P36_061_status"] == (
        "R5_consumed_failed_upstream_projection_live_observation_unproven"
    )
    assert current["current_S4_T05_RC_P36_062_status"] == (
        "R6_launch_failed_before_v8_live_observation"
    )
    assert current["current_S4_T05_RC_P36_063_status"] == (
        "root_cause_disposed_versioned_profile_overlay_and_create_app_"
        "preflight_selected_implementation_pending"
    )
    assert current["current_S4_T05_gap_projection_R5_execution_authorized"] is True
    assert current["current_S4_T05_gap_projection_R5_execution_started"] is True
    assert current["current_S4_T05_gap_projection_R5_execution_completed"] is True
    assert current["current_owner_acceptance_write_completed"] is True
    assert current["current_T09_decision"] == (
        "pass_owner_accepted_with_L4_quality_debt"
    )
    assert current["current_S3_T10_closeout_completed"] is True
    assert current["model_provider_execution_authorized_for_consumed_exact_run"] is False
    assert current["release_or_production_authorized"] is False


def test_closeout_is_zero_call_and_does_not_create_research_artifacts() -> None:
    closeout = _load(CLOSEOUT)
    assert closeout["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "new_research_runs": 0,
        "new_business_artifacts": 0,
        "owner_acceptance_records": 1,
    }
    assert closeout["stage_decision"]["qualified_senior_R3"] == "not_claimed"
    assert closeout["stage_decision"]["release"] == "not_authorized"
    assert closeout["stage_decision"]["production"] == "not_authorized"
