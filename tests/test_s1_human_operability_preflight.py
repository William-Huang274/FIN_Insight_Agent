from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from retrieval.evidence_admission import (
    candidate_binding_index,
    compile_qualified_human_admission_packet,
)
from retrieval.human_operability import (
    HumanOperabilityError,
    compile_human_operability_preflight,
    load_human_operability_program,
    validate_external_blind_qualification_receipt,
    validate_qualified_human_evidence_receipts,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_human_operability_and_blind_gate_program_v1_0.json"
)


def test_current_s1_human_operability_is_actionable_but_not_qualified() -> None:
    result = compile_human_operability_preflight(
        repo_root=ROOT,
        program=load_human_operability_program(PROGRAM_PATH),
        recorded_at="2026-08-19T12:00:00+08:00",
    )

    assert result["gate_states"] == {
        "ai_free_human_operability": "engineering_pass",
        "remaining_official_source_execution": "pass",
        "evidence_admission": "pending_qualified_human",
        "replacement_blind_qualification": "pending_external",
    }
    assert result["summary"] == {
        "development_case_count": 3,
        "request_count": 24,
        "remaining_source_request_count": 0,
        "evidence_admission_request_count": 16,
        "evidence_admission_requirement_count": 22,
        "public_information_gap_eligible_request_count": 0,
        "generation_model_calls": 0,
    }
    assert result["authority"]["S1_qualified_stable"] is False
    assert result["authority"]["candidate_is_evidence"] is False
    assert result["external_authority"]["disclosed_regression_cases_cannot_support_blind_claim"] is True


def test_current_business_failures_are_explained_as_actions_not_only_counts() -> None:
    result = compile_human_operability_preflight(
        repo_root=ROOT,
        program=load_human_operability_program(PROGRAM_PATH),
        recorded_at="2026-08-19T12:00:00+08:00",
    )
    by_case = {row["case_key"]: row for row in result["cases"]}
    dell = by_case["DELL"]
    mu = by_case["MU"]
    nvda = by_case["NVDA"]

    assert sum(row["failure_class"] == "candidate_not_admitted" for row in dell["requests"]) == 4
    assert sum(
        row["failure_class"] == "source_present_candidate_coverage_failure"
        for row in mu["requests"]
    ) == 4
    assert sum(
        row["failure_class"] == "source_present_candidate_coverage_failure"
        for row in nvda["requests"]
    ) == 3
    assert all(row["business_question_zh"] for case in result["cases"] for row in case["requests"])
    assert all(row["operator_actionable"] for case in result["cases"] for row in case["requests"])
    assert any("不要重复下载" in row["operator_action_zh"] for row in mu["requests"])
    assert any("合格评审者" in row["operator_action_zh"] for row in dell["requests"])


def test_bound_artifact_digest_drift_fails_closed() -> None:
    program = deepcopy(load_human_operability_program(PROGRAM_PATH))
    program["development_case_readiness"][0]["sha256"] = "0" * 64

    with pytest.raises(HumanOperabilityError, match="human_operability_bound_digest_drift"):
        compile_human_operability_preflight(
            repo_root=ROOT,
            program=program,
            recorded_at="2026-08-19T12:00:00+08:00",
        )


def test_external_blind_gate_forbids_observed_cases_and_git_labels() -> None:
    program = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
    blind = program["external_authority_gates"]["replacement_blind_qualification"]

    assert blind["state"] == "pending_external"
    assert blind["labels_must_remain_outside_git"] is True
    assert {"DELL", "MU", "NVDA", "COST", "JPM", "CAT", "NVO", "SHEL", "0700.HK"} == set(
        blind["observed_or_disclosed_cases_forbidden"]
    )


def test_qualified_human_receipt_requires_exact_requirement_and_authority_binding() -> None:
    program = load_human_operability_program(PROGRAM_PATH)
    unsigned = {
        "reviewer_id": "reviewer-1",
        "reviewer_qualification_basis": "qualified financial research reviewer",
        "case_key": "DELL",
        "request_id": "REQ::1",
        "requirement_id": "MER::1",
        "candidate_or_evidence_ref": "EV::1",
        "candidate_admission_item_digest": "a" * 64,
        "source_lineage_digest": "b" * 64,
        "decision": "accepted",
        "source_period_role_and_proposition_binding": {
            "case_identity_bound": True,
            "source_bound": True,
            "period_bound": True,
            "evidence_role_bound": True,
            "proposition_bound": True,
        },
        "decision_reason": "source-bound direct evidence",
        "reviewed_at": "2026-08-19T12:00:00+08:00",
    }
    receipt = {**unsigned, "receipt_digest": __import__(
        "retrieval.query_plan", fromlist=["canonical_digest"]
    ).canonical_digest(unsigned)}
    result = validate_qualified_human_evidence_receipts(
        program=program,
        receipts=[receipt],
        valid_candidate_bindings={
            ("DELL", "REQ::1", "MER::1", "EV::1"): {
                "candidate_admission_item_digest": "a" * 64,
                "source_lineage_digest": "b" * 64,
            }
        },
    )
    assert result["decision_counts"]["accepted"] == 1
    assert result["all_candidate_bindings_reviewed"] is True
    assert result["admission_gate_state"] == "complete"
    assert result["current_readiness_must_be_rematerialized_after_decisions"] is True


def test_valid_partial_human_receipt_batch_cannot_close_admission_gate() -> None:
    program = load_human_operability_program(PROGRAM_PATH)
    unsigned = {
        "reviewer_id": "reviewer-1",
        "reviewer_qualification_basis": "qualified financial research reviewer",
        "case_key": "DELL",
        "request_id": "REQ::1",
        "requirement_id": "MER::1",
        "candidate_or_evidence_ref": "EV::1",
        "candidate_admission_item_digest": "a" * 64,
        "source_lineage_digest": "b" * 64,
        "decision": "accepted",
        "source_period_role_and_proposition_binding": {
            "case_identity_bound": True,
            "source_bound": True,
            "period_bound": True,
            "evidence_role_bound": True,
            "proposition_bound": True,
        },
        "decision_reason": "source-bound direct evidence",
        "reviewed_at": "2026-08-19T12:00:00+08:00",
    }
    receipt = {**unsigned, "receipt_digest": __import__(
        "retrieval.query_plan", fromlist=["canonical_digest"]
    ).canonical_digest(unsigned)}
    result = validate_qualified_human_evidence_receipts(
        program=program,
        receipts=[receipt],
        valid_candidate_bindings={
            ("DELL", "REQ::1", "MER::1", "EV::1"): {
                "candidate_admission_item_digest": "a" * 64,
                "source_lineage_digest": "b" * 64,
            },
            ("DELL", "REQ::2", "MER::2", "EV::2"): {
                "candidate_admission_item_digest": "c" * 64,
                "source_lineage_digest": "d" * 64,
            },
        },
    )

    assert result["all_candidate_bindings_reviewed"] is False
    assert result["unreviewed_candidate_binding_count"] == 1
    assert result["admission_gate_state"] == "pending"


def test_current_admission_packet_has_exact_22_candidate_bindings() -> None:
    program = load_human_operability_program(PROGRAM_PATH)
    current_results = []
    for binding in program["development_case_readiness"]:
        public = json.loads((ROOT / binding["ref"]).read_text(encoding="utf-8"))
        current_results.append(
            json.loads(
                (ROOT / public["full_result_ref"]).read_text(encoding="utf-8")
            )
        )
    source_bindings = current_results[0]["source_bindings"]
    compiled = [
        json.loads(line)
        for line in (
            ROOT / source_bindings["compiled_financial_objects"]["ref"]
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records = [
        json.loads(line)
        for line in (
            ROOT / source_bindings["current_source_records"]["ref"]
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    packet = compile_qualified_human_admission_packet(
        current_case_results=current_results,
        compiled_objects=compiled,
        source_records=records,
        recorded_at="2026-08-19T14:00:00+08:00",
    )

    assert packet["pending_request_count"] == 16
    assert packet["pending_requirement_count"] == 22
    assert packet["candidate_binding_count"] == 22
    assert len(candidate_binding_index(packet)) == 22
    assert packet["authority"]["candidate_is_evidence"] is False


def test_external_blind_receipt_rejects_disclosed_case_even_with_valid_digest() -> None:
    program = load_human_operability_program(PROGRAM_PATH)
    contract = program["external_authority_gates"]["replacement_blind_qualification"]
    unsigned = {
        "external_program_id": "BLIND::1",
        "case_keys": ["DELL"],
        "evaluation_program_digest": "3" * 64,
        "candidate_freeze_ref": "external://candidate-freeze",
        "candidate_freeze_digest": "1" * 64,
        "implementation_commit": "a" * 40,
        "reviewer_id": "external-reviewer",
        "reviewer_qualification_basis": "qualified financial research reviewer",
        "label_store_ref": "external://labels",
        "label_store_digest": "2" * 64,
        "label_store_outside_repo": True,
        "label_store_git_tracked": False,
        "runtime_read_reference_before_candidate_freeze": False,
        "case_overlap_check": {"passed": True, "overlap_count": 0},
        "case_design_coverage": {
            key: True for key in contract["required_case_design_dimensions"]
        },
        "hard_gate_results": {
            key: True for key in contract["required_hard_gates"]
        },
        "aggregate_metric_results": {"all_registered_thresholds_passed": True},
        "business_failure_examples": [],
        "reviewed_at": "2026-08-19T12:00:00+08:00",
    }
    receipt = {**unsigned, "receipt_digest": __import__(
        "retrieval.query_plan", fromlist=["canonical_digest"]
    ).canonical_digest(unsigned)}

    with pytest.raises(HumanOperabilityError, match="blind_receipt_case_overlap_invalid"):
        validate_external_blind_qualification_receipt(
            program=program,
            receipt=receipt,
        )


def test_external_blind_receipt_requires_six_dimensions_and_hard_gates() -> None:
    program = load_human_operability_program(PROGRAM_PATH)
    contract = program["external_authority_gates"]["replacement_blind_qualification"]
    unsigned = {
        "external_program_id": "BLIND::2",
        "case_keys": ["B1", "B2", "B3", "B4", "B5", "B6"],
        "evaluation_program_digest": "3" * 64,
        "candidate_freeze_ref": "external://candidate-freeze",
        "candidate_freeze_digest": "1" * 64,
        "implementation_commit": "a" * 40,
        "reviewer_id": "external-reviewer",
        "reviewer_qualification_basis": "qualified financial research reviewer",
        "label_store_ref": "external://labels",
        "label_store_digest": "2" * 64,
        "label_store_outside_repo": True,
        "label_store_git_tracked": False,
        "runtime_read_reference_before_candidate_freeze": False,
        "case_overlap_check": {"passed": True, "overlap_count": 0},
        "case_design_coverage": {
            key: True for key in contract["required_case_design_dimensions"]
        },
        "hard_gate_results": {
            key: True for key in contract["required_hard_gates"]
        },
        "aggregate_metric_results": {"all_registered_thresholds_passed": True},
        "business_failure_examples": [],
        "reviewed_at": "2026-08-19T15:00:00+08:00",
    }
    receipt = {
        **unsigned,
        "receipt_digest": __import__(
            "retrieval.query_plan", fromlist=["canonical_digest"]
        ).canonical_digest(unsigned),
    }

    result = validate_external_blind_qualification_receipt(
        program=program,
        receipt=receipt,
    )
    assert result["case_count"] == 6
    assert result["hard_gate_count"] == 5
