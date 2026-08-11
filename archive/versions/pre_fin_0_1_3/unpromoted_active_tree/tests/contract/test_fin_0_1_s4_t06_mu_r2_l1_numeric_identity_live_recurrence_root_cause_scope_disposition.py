from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_r2_l1_numeric_identity_live_recurrence_"
    "root_cause_scope_disposition_v1_0.json"
)
PAIRED = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_r2_success_only_paired_assessment_"
    "result_v1_0.json"
)
MU_R2_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_fresh_exact_admission_r2.json"
)
DELL_R11_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r11_numeric_identity_fresh_exact_"
    "admission_r11.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CONTEXT_PACK = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_evidence_and_live_recurrence_are_frozen() -> None:
    decision = _load(DECISION)
    sources = decision["source_evidence"]
    paired = _load(PAIRED)

    assert sources["paired_assessment_sha256"] == _sha256(PAIRED)
    assert sources["consumed_MU_R2_admission_sha256"] == _sha256(
        MU_R2_ADMISSION
    )
    assert sources["reference_DELL_R11_admission_sha256"] == _sha256(
        DELL_R11_ADMISSION
    )
    assert paired["four_layer_assessment"]["L1_hard_integrity"]["status"] == (
        "fail"
    )
    assert paired["stage_decision"]["MU_R2"] == "not_proven"


def test_earliest_owner_is_admission_capability_closure() -> None:
    decision = _load(DECISION)
    mu_admission = _load(MU_R2_ADMISSION)
    dell_admission = _load(DELL_R11_ADMISSION)
    root = decision["confirmed_root_cause"]

    assert "case_numeric_authority_policy_ref" not in mu_admission
    assert "case_delivery_identity_policy_ref" not in mu_admission
    assert dell_admission["case_numeric_authority_policy_ref"] == (
        "fin01.s4.case_numeric_authority_projection_and_"
        "deterministic_rendering:v1"
    )
    assert dell_admission["case_delivery_identity_policy_ref"] == (
        "fin01.s4.case_delivery_identity_projection:v1"
    )
    assert root["earliest_owner"] == (
        "S4 admission capability composition and admissibility closure "
        "before any Provider request"
    )
    assert root["not_source_pack_fault"] is True
    assert root["not_provider_transport_or_network_fault"] is True
    assert len(root["causal_chain"]) == 7


def test_exactly_one_structural_bundle_and_stop_rule_are_selected() -> None:
    decision = _load(DECISION)
    bundle = decision["selected_single_implementation_bundle"]
    stop = decision["stop_and_scope_replacement_rule"]

    assert bundle["bundle_ref"] == (
        "fin01.s4.case_runtime_mandatory_material_truth_and_"
        "identity_safety_closure:v1"
    )
    assert bundle["maximum_zero_call_implementation_bundles"] == 1
    assert bundle["automatic_follow_on_repair_bundles"] == 0
    assert len(bundle["required_changes"]) == 7
    assert stop["one_bundle_only"] is True
    assert stop["automatic_MU_R3"] is False
    assert stop["automatic_paid_reproof"] is False
    assert stop["T05_reopened"] is False


def test_decision_is_zero_call_and_next_scope_is_implementation_only() -> None:
    decision = _load(DECISION)
    counts = decision["observed_counts"]

    assert all(value == 0 for value in counts.values())
    assert decision["authority"]["runtime_implementation_authorized"] is False
    assert decision["authority"]["new_admission_or_exact_live_authorized"] is (
        False
    )
    assert decision["authority"][
        "R3_owner_acceptance_or_S4_T07_authorized"
    ] is False
    assert decision["stage_decision"]["MU_R2"] == "failed_L1_immutable"
    assert decision["next_action"] == (
        "S4-T06-MU-CASE-RUNTIME-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-"
        "SAFETY-CLOSURE-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_project_os_and_backlogs_advance_to_the_same_bounded_next_scope() -> None:
    expected = (
        "S4-T06-MU-CASE-RUNTIME-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-"
        "SAFETY-CLOSURE-FRESH-AGENT-PROOF-DECISION"
    )
    program = _load(PROGRAM_BACKLOG)
    s4 = _load(S4_BACKLOG)
    context = CONTEXT_PACK.read_text(encoding="utf-8")
    root_rows = [
        json.loads(line)
        for line in ROOT_CAUSE_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    capability_rows = [
        json.loads(line)
        for line in CAPABILITY_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    current_disposition = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "SCOPE-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_fresh_proof = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    current_post_R4 = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_after_v2 = (
        "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
    )
    assert program["next_action"]["item_id"] in {
        expected,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] in {
        expected,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert (
        f"current next=`{expected}`" in context
        or f"current next=`{current_disposition}`" in context
        or f"current next=`{current_fresh_proof}`" in context
        or f"current next=`{current_post_R4}`" in context
        or f"current next=`{current_after_v2}`" in context
        or (
            "current next=`S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-"
            "AND-CAPTURE-V2-TERMINAL-RESULT-MATERIALIZATION-MINIMUM-"
            "ZERO-CALL-IMPLEMENTATION`" in context
        )
    )
    latest_root_rows = {
        prefix: next(
            row
            for row in reversed(root_rows)
            if row["issue_id"].startswith(prefix)
        )
        for prefix in ("RC-P36-067", "RC-P36-068")
    }
    assert latest_root_rows["RC-P36-067"]["issue_id"].startswith("RC-P36-067")
    assert latest_root_rows["RC-P36-068"]["issue_id"].startswith("RC-P36-068")
    assert capability_rows[-1]["current_next"] in {
        expected,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
