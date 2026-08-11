from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_r4_exact_live_execution_failure_"
    "result_v1_0.json"
)
PROGRAM = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAIL = (
    ROOT
    / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = (
    ROOT / "docs/project_os/capability_status_ledger.jsonl"
)
R4_NEXT = (
    "S4-T06-MU-R4-NUMERIC-NARRATIVE-L1-PROJECT-BLOCK-OR-"
    "SCOPE-REPLACEMENT-DECISION"
)
CURRENT_NEXT = (
    "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
CURRENT_RUNTIME_NEXT = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_issue(issue_id: str) -> dict:
    return [
        json.loads(line)
        for line in ROOT_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["issue_id"] == issue_id
    ][-1]


def test_r4_result_binds_immutable_execution_evidence() -> None:
    result = _load(RESULT)
    assert result["status"] == (
        "terminal_failed_new_numeric_narrative_L1_no_R5_"
        "no_paired_no_owner"
    )
    for ref_key, digest_key in (
        ("fresh_proof_ref", "fresh_proof_sha256"),
        ("admission_ref", "admission_sha256"),
        ("issuance_ref", "issuance_sha256"),
        ("runtime_result_ref", "runtime_result_sha256"),
        ("supervision_launch_ref", "supervision_launch_sha256"),
        ("supervision_exit_ref", "supervision_exit_sha256"),
    ):
        assert _sha256(ROOT / result["source_bindings"][ref_key]) == (
            result["source_bindings"][digest_key]
        )


def test_r4_terminal_truth_usage_and_first_failure_are_exact() -> None:
    result = _load(RESULT)
    terminal = result["canonical_terminal_truth"]
    provider = result["provider_execution"]
    failure = result["first_credible_failure"]
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["artifact_count"] == 0
    assert terminal["orphaned_run"] is False
    assert [
        provider["semantic_model_calls"],
        provider["provider_calls"],
        provider["network_calls"],
        provider["usage_receipts"],
        provider["restricted_captures"],
    ] == [4, 4, 4, 4, 4]
    assert [
        provider["input_tokens"],
        provider["output_tokens"],
        provider["total_tokens"],
    ] == [24474, 2527, 27001]
    assert provider["estimated_cost_usd"] == 0.01284468
    assert failure == {
        "stage": "domain_specialist:value_and_profit_capture",
        "segment": "facts_explanation_and_terminal",
        "lifecycle_phase": "node_envelope_accounting",
        "failure_code": (
            "s4_case_numeric_authority_provider_narrative_invalid"
        ),
        "failure_family": "case_numeric_authority",
        "failure_subtype": "provider_authored_numeric_token",
        "field_id": "explanation_layer",
        "failing_item_count": 2,
        "acceptance_layer": "L1_hard_integrity",
        "raw_text_persisted_in_result": False,
        "private_reasoning_persisted": False,
        "credential_persisted": False,
    }


def test_r4_closes_identity_predecessor_but_stops_without_r5() -> None:
    result = _load(RESULT)
    identity = result["R3_identity_boundary_reproof"]
    assert identity["R3_failure_code_recurred"] is False
    assert identity["first_specialist_completed"] is True
    assert identity["provider_outputs_scanned_before_failure"] == 4
    assert result["sequence_disposition"]["S4_T06"] == "blocked"
    assert result["sequence_disposition"]["S4_T07"] == "not_entered"
    assert result["sequence_disposition"][
        "paired_L1_to_L4_assessment"
    ] == "not_eligible_not_performed"
    assert result["stop_rule"]["automatic_R5_or_micro_patch_performed"] is False
    assert result["next_action"] == R4_NEXT


def test_backlogs_and_ledgers_publish_r4_stop_as_current_truth() -> None:
    program = _load(PROGRAM)
    detail = _load(DETAIL)
    assert program["next_action"]["item_id"] == CURRENT_RUNTIME_NEXT
    assert detail["current_next_action"] == CURRENT_RUNTIME_NEXT
    assert program["next_action"]["identity_boundary_R4_artifacts"] == 0
    assert program["next_action"][
        "identity_boundary_R4_failure_code"
    ] == "s4_case_numeric_authority_provider_narrative_invalid"
    assert _latest_issue(
        "RC-P36-079-s4-t06-current-case-identity-token-policy-"
        "overconstraint-and-fixture-blind-spot"
    )["status"] == "closed_v2_fixture_and_live_positive_path_reproof_pass"
    rc_080 = _latest_issue(
        "RC-P36-080-s4-t06-provider-authored-numeric-token-in-"
        "specialist-explanation-layer"
    )
    assert rc_080["status"] == "open"
    assert rc_080["disposition_status"] in {
        (
            "classifier_v2_fresh_proof_pass_R5_admission_issuance_"
            "authorized_not_issued"
        ),
        (
            "classifier_v2_R5_admission_issued_unconsumed_exact_live_"
            "authority_pending"
        ),
        (
            "classifier_v2_R5_exact_once_execution_authorized_not_"
            "started_live_reproof_pending"
        ),
        "R5_live_recurrence_temporal_planning_date_taxonomy_and_"
        "authority_gap_no_R6",
    }
    assert rc_080["full_chain_blocker"] is True
    capability = [
        json.loads(line)
        for line in CAPABILITY_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and json.loads(line).get("capability_id")
        == "fin_0_1_s4_t06_MU_R4_current_case_identity_v2_live_"
        "pass_numeric_narrative_L1_failure"
    ][-1]
    assert capability["current_next"] == R4_NEXT
    assert capability["stage_acceptance"]["S4_T06"] == (
        "blocked_after_R4_new_L1"
    )
