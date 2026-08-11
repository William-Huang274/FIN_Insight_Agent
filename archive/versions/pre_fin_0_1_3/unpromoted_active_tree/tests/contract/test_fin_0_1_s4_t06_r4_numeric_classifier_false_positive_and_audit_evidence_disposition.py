from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_r4_numeric_classifier_"
    "false_positive_and_audit_evidence_separation_disposition_v1_0.json"
)
R4_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_r4_exact_live_execution_failure_"
    "result_v1_0.json"
)
RUNTIME_RESULT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/s4_t06_mu_identity_v2_r4_live_execution_result.json"
)
CAPTURE = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/canonical-runtime/objects/fin01/"
    "provider-output-captures/62/23/"
    "6223bfc2f55ccb8e83733622b071c6e756bf731adbd36aa2f869ea69a12d3c79.json"
)
PROGRAM = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAIL = (
    ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
CURRENT_NEXT = (
    "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
CURRENT_RUNTIME_NEXT = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
NUMERIC_TOKEN = re.compile(
    r"(?<![A-Za-z_])[+\-]?(?:\d+(?:[.,]\d+)?|\.\d+)(?![A-Za-z_])"
    r"|[%％$¥￥]"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest(path: Path, key: str, value: str) -> dict:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row.get(key) == value][-1]


def test_disposition_binds_immutable_r4_and_restricted_capture() -> None:
    decision = _load(DECISION)
    source = decision["source_evidence"]
    assert _sha256(R4_RESULT) == source["immutable_R4_result_sha256"]
    assert _sha256(RUNTIME_RESULT) == source["runtime_result_sha256"]
    assert _sha256(CAPTURE) == source["restricted_capture_sha256"]
    assert source["capture_sequence"] == 4
    assert source["assistant_final_output_persisted"] is True
    assert source["raw_provider_envelope_persisted"] is False
    assert source["private_reasoning_persisted"] is False
    assert source["credential_persisted"] is False


def test_r4_two_failures_are_two_period_bearing_narrative_values() -> None:
    capture = _load(CAPTURE)
    output = json.loads(capture["assistant_output_text"])
    candidates = [
        ("$.fact_layer[0].statement", output["fact_layer"][0]["statement"]),
        ("$.explanation_layer[0]", output["explanation_layer"][0]),
    ]
    matched = [
        (path, text)
        for path, text in candidates
        if NUMERIC_TOKEN.search(text)
    ]
    assert [path for path, _ in matched] == [
        "$.fact_layer[0].statement",
        "$.explanation_layer[0]",
    ]
    assert all("FQ3 2026" in text for _, text in matched)
    assert all(
        symbol not in text
        for _, text in matched
        for symbol in ("$", "¥", "￥", "%", "％")
    )

    decision = _load(DECISION)["R4_reclassification"]
    assert decision["matched_narrative_value_count"] == len(matched) == 2
    assert decision["semantic_class"] == "reporting_period_label"
    assert decision["material_financial_numeric_hallucination_established"] is False
    assert decision["owned_project_classifier_false_positive_established"] is True


def test_audit_contract_separates_restricted_evidence_from_promotion() -> None:
    contract = _load(DECISION)["audit_contract"]
    promotion = contract["promotion_boundary"]
    assert contract["principle"] == (
        "validation rejection blocks promotion but must not destroy auditable evidence"
    )
    assert promotion["restricted_failed_output_may_be_used_for_audit"] is True
    assert promotion["restricted_failed_output_may_become_business_Artifact"] is False
    assert promotion["restricted_failed_output_may_become_financial_fact"] is False
    assert promotion[
        "restricted_failed_output_may_be_replayed_as_inference_automatically"
    ] is False
    assert contract["atomicity"][
        "failure_telemetry_must_not_veto_core_capture_or_terminal_truth"
    ] is True
    assert any("authorization" in item for item in contract["never_persist"])
    assert any("private_reasoning" in item for item in contract["never_persist"])


def test_contract_does_not_overclaim_unimplemented_request_capture() -> None:
    status = _load(DECISION)["current_runtime_conformance"]
    assert status["assistant_final_output_restricted_capture"] == (
        "implemented_and_R4_replay_proven"
    )
    assert status["exact_model_visible_request_capture"] == (
        "not_implemented_runtime_gap"
    )
    assert status["safe_rule_match_path_and_semantic_class_index"] == (
        "not_implemented_runtime_gap"
    )


def test_project_os_and_backlogs_publish_corrected_current_next() -> None:
    program = _load(PROGRAM)
    detail = _load(DETAIL)
    assert program["next_action"]["item_id"] == CURRENT_RUNTIME_NEXT
    assert detail["current_next_action"] == CURRENT_RUNTIME_NEXT

    rc_080 = _latest(
        ROOT_LEDGER,
        "issue_id",
        "RC-P36-080-s4-t06-provider-authored-numeric-token-in-"
        "specialist-explanation-layer",
    )
    assert rc_080["status"] == "open"
    assert rc_080["model_or_provider_fault_established"] is True
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
    rc_081 = _latest(
        ROOT_LEDGER,
        "issue_id",
        "RC-P36-081-s4-runtime-model-visible-request-and-safe-rule-"
        "match-audit-capture-gap",
    )
    assert rc_081["status"].startswith("closed_")
    assert rc_081["full_chain_blocker"] is False

    capability = _latest(
        CAPABILITY_LEDGER,
        "capability_id",
        "fin_0_1_s4_t06_R4_classifier_false_positive_and_audit_"
        "evidence_contract",
    )
    assert capability["current_next"] == CURRENT_NEXT
    assert capability["stage_acceptance"]["S4_T06"] == "blocked"
    assert capability["verification_result"][
        "model_provider_network_calls"
    ] == [0, 0, 0]
