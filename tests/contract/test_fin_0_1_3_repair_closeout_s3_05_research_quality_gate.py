from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_research_quality_gate import (  # noqa: E402
    S3ResearchQualityGateError,
    compile_s3_research_quality_gate_program,
    load_s3_research_quality_gate_policy,
    validate_case_score_packet,
    validate_paired_assessment,
    validate_qualified_human_content_acceptance,
    validate_s3_research_quality_gate_program,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_research_quality_gate_policy_v1_0.json"
CLAIM_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json"
WRITER_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content_v1_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_05_research_quality_gate_v1_0.json"
ACTIVE_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_05_active_test_suite_successor_v1_0.json"


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _compile() -> tuple[dict, dict]:
    policy = load_s3_research_quality_gate_policy(POLICY_PATH)
    program = compile_s3_research_quality_gate_program(
        policy=policy,
        claim_decision=json.loads(CLAIM_PATH.read_text(encoding="utf-8")),
        writer_decision=json.loads(WRITER_PATH.read_text(encoding="utf-8")),
    )
    return program, policy


def _reseal_context(context: dict) -> dict:
    context["candidate_context_digest"] = canonical_digest(
        {key: value for key, value in context.items() if key != "candidate_context_digest"}
    )
    return context


def _eligible_context(context: dict, label: str) -> dict:
    value = deepcopy(context)
    value.update(
        {
            "authority": "all_natural_candidate",
            "generic_precheck_status": "pass",
            "L1_status": "pass",
            "L2_status": "pass",
            "final_delivery_digest": _hex(label + ":delivery"),
            "verifier_binding_digest": _hex(label + ":verifier"),
            "identity_sealed": True,
            "input_head_digest": _hex("shared-input-head"),
            "run_id": "run_" + label,
            "artifact_digest": _hex(label + ":artifact"),
        }
    )
    return _reseal_context(value)


def _score_packet(context: dict, scores: dict[str, int] | None = None) -> dict:
    scores = scores or {f"Q{index}": 3 for index in range(1, 9)}
    ref_type_by_dimension = {
        "Q1": "claim", "Q2": "evidence", "Q3": "numeric", "Q4": "claim",
        "Q5": "section", "Q6": "section", "Q7": "wwc", "Q8": "section",
    }
    rows = [
        {
            "dimension_id": f"Q{index}",
            "score": scores[f"Q{index}"],
            "reason": f"{context['case_key']} Q{index} 的结论、边界与决策影响由当前案例绑定材料具体支持。",
            "reason_refs": [{
                "ref_type": ref_type_by_dimension[f"Q{index}"],
                "ref_id": context["allowed_reason_refs"][ref_type_by_dimension[f"Q{index}"]][0],
            }],
        }
        for index in range(1, 9)
    ]
    total = sum(scores.values())
    formal_pass = (
        total >= 24
        and all(scores[f"Q{index}"] >= 2 for index in range(1, 8))
        and all(scores[key] >= 3 for key in ("Q1", "Q2", "Q3", "Q8"))
        and sum(value >= 3 for value in scores.values()) >= 4
    )
    return {
        "case_key": context["case_key"],
        "candidate_context_digest": context["candidate_context_digest"],
        "workpaper_digest": context["workpaper_digest"],
        "final_delivery_digest": context["final_delivery_digest"],
        "verifier_binding_digest": context["verifier_binding_digest"],
        "rubric_version": "FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806",
        "financial_truth_findings": [],
        "dimensions": rows,
        "total_score": total,
        "strongest_counter_thesis": {
            "present": True,
            "refs": [{"ref_type": "section", "ref_id": "risk_and_counter_thesis"}],
        },
        "adjudicated_dependency_or_conflict": {
            "present": True,
            "refs": [{"ref_type": "section", "ref_id": "executive_thesis"}],
        },
        "actionable_WWC": {
            "present": True,
            "refs": [{"ref_type": "wwc", "ref_id": context["allowed_reason_refs"]["wwc"][0]}],
        },
        "formal_pass": formal_pass,
    }


def _valid_pair(program: dict, policy: dict) -> tuple[dict, dict, dict, dict]:
    baseline_context = _eligible_context(program["candidate_contexts"][0], "baseline")
    agent_context = _eligible_context(program["candidate_contexts"][0], "agent")
    baseline_packet = _score_packet(baseline_context, {f"Q{index}": 2 for index in range(1, 9)})
    agent_packet = _score_packet(agent_context)
    claim_ref = agent_context["allowed_reason_refs"]["claim"][0]
    gains = [
        {
            "dimension_id": dimension,
            "baseline_score": 2,
            "agent_score": 3,
            "reviewer_confirmed": True,
            "reason": f"{dimension} 在公司专属机制、论证或决策边界上出现可核验的实质改善。",
            "reason_refs": [{"ref_type": "claim", "ref_id": claim_ref}],
        }
        for dimension in ("Q1", "Q2", "Q3")
    ]
    assessment = {
        "case_key": "DELL",
        "baseline_score_packet": baseline_packet,
        "agent_score_packet": agent_packet,
        "material_gains": gains,
        "paired_pass": True,
    }
    result = validate_paired_assessment(
        assessment, policy=policy, baseline_context=baseline_context, agent_context=agent_context
    )
    return assessment, result, baseline_context, agent_context


def test_current_fixture_mixed_cases_are_ineligible_and_not_formally_scored() -> None:
    program, policy = _compile()
    validate_s3_research_quality_gate_program(program, policy=policy)
    assert program["observed_counts"]["dimension_slots_compiled"] == 24
    assert program["observed_counts"]["fixture_mixed_cases_rejected_before_scoring"] == 3
    assert program["observed_counts"]["formal_case_scores"] == 0
    assert all(row["scoreability"] == "ineligible_not_scored" for row in program["current_case_dispositions"])
    assert all("fixture_mixed_authority" in row["reasons"] for row in program["current_case_dispositions"])


def test_eight_dimension_absolute_threshold_passes_only_on_scoreable_final_delivery() -> None:
    program, policy = _compile()
    context = _eligible_context(program["candidate_contexts"][0], "absolute-pass")
    result = validate_case_score_packet(_score_packet(context), policy=policy, candidate_context=context)
    assert result["total_score"] == 24
    assert result["formal_pass"] is True


def test_core_dimension_floor_blocks_case_even_when_total_is_24_and_no_averaging_exists() -> None:
    program, policy = _compile()
    context = _eligible_context(program["candidate_contexts"][1], "core-floor")
    scores = {f"Q{index}": 3 for index in range(1, 9)}
    scores["Q3"] = 2
    scores["Q4"] = 4
    result = validate_case_score_packet(_score_packet(context, scores), policy=policy, candidate_context=context)
    assert result["total_score"] == 24
    assert result["formal_pass"] is False
    assert policy["authority_boundary"]["case_averaging_allowed"] is False


def test_dell_period_duration_financial_truth_error_blocks_scoring_before_L3() -> None:
    program, policy = _compile()
    context = _eligible_context(program["candidate_contexts"][0], "dell-period-error")
    packet = _score_packet(context)
    packet["financial_truth_findings"] = [
        {"code": "annual_duration_mismatch", "detail": "91-day quarter mislabeled as annual"}
    ]
    with pytest.raises(S3ResearchQualityGateError, match="L1_must_pass"):
        validate_case_score_packet(packet, policy=policy, candidate_context=context)


def test_generic_precheck_and_cross_case_reason_reference_fail_closed() -> None:
    program, policy = _compile()
    context = _eligible_context(program["candidate_contexts"][0], "generic")
    context["generic_precheck_status"] = "fail_generic_high_count_content"
    _reseal_context(context)
    with pytest.raises(S3ResearchQualityGateError, match="candidate_not_scoreable"):
        validate_case_score_packet(_score_packet(context), policy=policy, candidate_context=context)

    context = _eligible_context(program["candidate_contexts"][0], "cross-case")
    packet = _score_packet(context)
    packet["dimensions"][0]["reason_refs"][0]["ref_id"] = program["candidate_contexts"][1]["allowed_reason_refs"]["claim"][0]
    with pytest.raises(S3ResearchQualityGateError, match="reason_ref_invalid"):
        validate_case_score_packet(packet, policy=policy, candidate_context=context)


def test_paired_assessment_requires_distinct_identity_and_three_material_gains() -> None:
    program, policy = _compile()
    assessment, result, baseline_context, agent_context = _valid_pair(program, policy)
    assert result["paired_pass"] is True
    assert result["material_gain_dimensions"] == ["Q1", "Q2", "Q3"]

    mutated = deepcopy(assessment)
    mutated["material_gains"] = mutated["material_gains"][:2]
    mutated["paired_pass"] = False
    result = validate_paired_assessment(
        mutated, policy=policy, baseline_context=baseline_context, agent_context=agent_context
    )
    assert result["paired_pass"] is False

    same_identity = deepcopy(agent_context)
    same_identity["run_id"] = baseline_context["run_id"]
    _reseal_context(same_identity)
    mutated = deepcopy(assessment)
    mutated["agent_score_packet"] = _score_packet(same_identity)
    with pytest.raises(S3ResearchQualityGateError, match="paired_identity_invalid"):
        validate_paired_assessment(
            mutated, policy=policy, baseline_context=baseline_context, agent_context=same_identity
        )


def test_qualified_human_content_acceptance_is_separate_and_cannot_be_codex_signed() -> None:
    program, policy = _compile()
    _, paired, _, agent_context = _valid_pair(program, policy)
    decision = {
        "case_key": "DELL",
        "reviewer_identity": "FIN_OWNER_A",
        "reviewer_role": "qualified_research_reviewer",
        "authenticated_session_digest": _hex("session"),
        "score_packet_digest": paired["agent_score_packet_digest"],
        "paired_digest": paired["paired_digest"],
        "final_delivery_digest": agent_context["final_delivery_digest"],
        "separate_from_workflow_acceptance": True,
        "action": "accept_content",
        "reason": "研究内容能够用于继续复核，且公司专属机制、数字含义和反方边界均清晰。",
        "reason_refs": [{"ref_type": "claim", "ref_id": agent_context["allowed_reason_refs"]["claim"][0]}],
    }
    decision["decision_digest"] = canonical_digest(decision)
    assert validate_qualified_human_content_acceptance(
        decision, paired_result=paired, agent_context=agent_context
    )["action"] == "accept_content"
    mutated = deepcopy(decision)
    mutated["reviewer_identity"] = "Codex automation"
    mutated["decision_digest"] = canonical_digest({key: value for key, value in mutated.items() if key != "decision_digest"})
    with pytest.raises(S3ResearchQualityGateError, match="human_decision_invalid"):
        validate_qualified_human_content_acceptance(mutated, paired_result=paired, agent_context=agent_context)


def test_materialized_decision_and_active_suite_are_digest_bound_and_honest() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "record_digest"}
    )
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert active["observed_result"] == "234 passed / 1 historical assertion deselected"
    assert decision["acceptance"]["S3_05_deterministic_gate"] == "engineering_pass"
    assert decision["acceptance"]["current_fixture_previews_formally_scored"] == 0
    assert decision["admission_disposition"]["formal_full_chain_authorized_now"] is False
    assert decision["stage_boundary"]["qualified_human_content_acceptance"] is False
