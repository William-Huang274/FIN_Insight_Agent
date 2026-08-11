from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


POLICY_SCHEMA = "fin_ia_0_1_3_s3_research_quality_gate_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_research_quality_gate_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.eight_dimension_verifier_paired_quality:v1"
CASES = ("DELL", "MU", "NVDA")
DIMENSIONS = tuple(f"Q{index}" for index in range(1, 9))
CORE_DIMENSIONS = ("Q1", "Q2", "Q3", "Q8")
REF_TYPES = ("claim", "section", "evidence", "numeric", "wwc")


class S3ResearchQualityGateError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s3_research_quality_gate_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    thresholds = policy.get("thresholds") or {}
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or tuple(row.get("dimension_id") for row in policy.get("dimensions") or ()) != DIMENSIONS
        or thresholds.get("total_minimum") != 24
        or thresholds.get("Q1_to_Q7_minimum") != 2
        or thresholds.get("core_dimension_minimum") != 3
        or tuple(thresholds.get("core_dimensions") or ()) != CORE_DIMENSIONS
        or thresholds.get("dimensions_at_or_above_three_minimum") != 4
        or thresholds.get("paired_material_gain_dimensions_minimum") != 3
    ):
        raise S3ResearchQualityGateError("s3_quality_policy_invalid")
    boundary = policy.get("authority_boundary") or {}
    if (
        boundary.get("L1_L2_must_pass_before_scoring") is not True
        or boundary.get("fixture_mixed_may_be_formally_scored") is not False
        or boundary.get("case_averaging_allowed") is not False
        or boundary.get("LLM_judge_may_sign_acceptance") is not False
        or boundary.get("qualified_human_content_acceptance_required") is not True
        or boundary.get("workflow_acceptance_is_content_acceptance") is not False
    ):
        raise S3ResearchQualityGateError("s3_quality_authority_policy_invalid")
    return policy


def compile_s3_research_quality_gate_program(
    *,
    policy: Mapping[str, Any],
    writer_decision: Mapping[str, Any],
    claim_decision: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        writer_decision.get("acceptance", {}).get("S3_04") != "engineering_pass"
        or claim_decision.get("acceptance", {}).get("S3_02") != "engineering_pass"
        or not _record_digest_ok(writer_decision)
        or not _record_digest_ok(claim_decision)
    ):
        raise S3ResearchQualityGateError("s3_quality_upstream_invalid")
    workpapers = writer_decision["workpaper_writer_content_program"]["case_workpapers"]
    cards = claim_decision["claim_quality_program"]["core_claim_cards"]
    contexts = []
    dispositions = []
    for workpaper in workpapers:
        case_key = str(workpaper["case_key"])
        case_cards = [row for row in cards if row.get("case_key") == case_key]
        context = _compile_candidate_context(workpaper=workpaper, cards=case_cards)
        contexts.append(context)
        reasons = _scoreability_reasons(context)
        dispositions.append(
            {
                "case_key": case_key,
                "candidate_context_digest": context["candidate_context_digest"],
                "scoreability": "ineligible_not_scored" if reasons else "eligible_pending_formal_score",
                "reasons": reasons,
                "dimension_scores": None,
                "total_score": None,
                "formal_case_pass": False,
                "qualified_human_content_acceptance": False,
            }
        )
    observed = {
        "case_contexts": 3,
        "dimension_slots_compiled": 24,
        "formally_scoreable_cases": sum(not row["reasons"] for row in dispositions),
        "fixture_mixed_cases_rejected_before_scoring": sum(
            "fixture_mixed_authority" in row["reasons"] for row in dispositions
        ),
        "formal_case_scores": 0,
        "formal_case_passes": 0,
        "paired_assessments": 0,
        "qualified_human_content_acceptances": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "upstream_digests": {
            "S3_02": claim_decision["record_digest"],
            "S3_04": writer_decision["record_digest"],
        },
        "rubric_contract": {
            "dimension_ids": list(DIMENSIONS),
            "maximum_score": 32,
            "thresholds": deepcopy(policy["thresholds"]),
            "formal_scoring_object": "final_verifier_bound_product_delivery",
            "reason_reference_types": list(REF_TYPES),
            "case_averaging_allowed": False,
        },
        "candidate_contexts": contexts,
        "current_case_dispositions": dispositions,
        "paired_contract": deepcopy(policy["paired_contract"]),
        "qualified_human_contract": deepcopy(policy["qualified_human_contract"]),
        "observed_counts": observed,
        "stage_boundary": {
            "S3_05": "deterministic_quality_gate_engineering_pass_formal_candidate_pending",
            "current_fixture_previews_scored": False,
            "formal_full_chain_authorized": False,
            "formal_case_passes": 0,
            "paired_assessment": False,
            "qualified_human_content_acceptance": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_research_quality_gate_program(program, policy=policy)
    return program


def validate_s3_research_quality_gate_program(
    program: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3ResearchQualityGateError("s3_quality_program_binding_invalid")
    contexts = program.get("candidate_contexts") or []
    dispositions = program.get("current_case_dispositions") or []
    if [row.get("case_key") for row in contexts] != list(CASES) or [row.get("case_key") for row in dispositions] != list(CASES):
        raise S3ResearchQualityGateError("s3_quality_case_surface_invalid")
    for context, disposition in zip(contexts, dispositions, strict=True):
        _validate_candidate_context(context)
        reasons = _scoreability_reasons(context)
        if (
            disposition.get("candidate_context_digest") != context.get("candidate_context_digest")
            or disposition.get("reasons") != reasons
            or disposition.get("scoreability") != "ineligible_not_scored"
            or disposition.get("dimension_scores") is not None
            or disposition.get("total_score") is not None
            or disposition.get("formal_case_pass") is not False
        ):
            raise S3ResearchQualityGateError("s3_quality_fixture_disposition_invalid")
    expected = {
        "case_contexts": 3,
        "dimension_slots_compiled": 24,
        "formally_scoreable_cases": sum(not _scoreability_reasons(row) for row in contexts),
        "fixture_mixed_cases_rejected_before_scoring": sum(
            "fixture_mixed_authority" in _scoreability_reasons(row) for row in contexts
        ),
        "formal_case_scores": 0,
        "formal_case_passes": 0,
        "paired_assessments": 0,
        "qualified_human_content_acceptances": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    if program.get("observed_counts") != expected:
        raise S3ResearchQualityGateError("s3_quality_observed_counts_invalid")


def validate_case_score_packet(
    packet: Mapping[str, Any], *, policy: Mapping[str, Any], candidate_context: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_candidate_context(candidate_context)
    reasons = _scoreability_reasons(candidate_context)
    if reasons:
        raise S3ResearchQualityGateError("s3_quality_candidate_not_scoreable")
    if (
        packet.get("case_key") != candidate_context.get("case_key")
        or packet.get("candidate_context_digest") != candidate_context.get("candidate_context_digest")
        or packet.get("workpaper_digest") != candidate_context.get("workpaper_digest")
        or packet.get("final_delivery_digest") != candidate_context.get("final_delivery_digest")
        or packet.get("verifier_binding_digest") != candidate_context.get("verifier_binding_digest")
        or packet.get("rubric_version") != policy.get("rubric_version")
    ):
        raise S3ResearchQualityGateError("s3_quality_score_binding_invalid")
    findings = packet.get("financial_truth_findings") or []
    if candidate_context.get("L1_status") != "pass" or findings:
        raise S3ResearchQualityGateError("s3_quality_L1_must_pass")
    if candidate_context.get("L2_status") != "pass":
        raise S3ResearchQualityGateError("s3_quality_L2_must_pass")
    rows = packet.get("dimensions") or []
    if [row.get("dimension_id") for row in rows] != list(DIMENSIONS):
        raise S3ResearchQualityGateError("s3_quality_dimension_surface_invalid")
    allowed = candidate_context["allowed_reason_refs"]
    scores: dict[str, int] = {}
    dimension_rules = {str(row["dimension_id"]): row for row in policy["dimensions"]}
    for row in rows:
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or score < 0 or score > 4:
            raise S3ResearchQualityGateError("s3_quality_dimension_score_invalid")
        if len(str(row.get("reason") or "").strip()) < 24:
            raise S3ResearchQualityGateError("s3_quality_dimension_reason_missing")
        refs = row.get("reason_refs") or []
        if not refs:
            raise S3ResearchQualityGateError("s3_quality_dimension_reason_refs_missing")
        seen_ref_types = set()
        for ref in refs:
            ref_type = str(ref.get("ref_type") or "")
            ref_id = str(ref.get("ref_id") or "")
            if ref_type not in REF_TYPES or ref_id not in set(allowed.get(ref_type) or []):
                raise S3ResearchQualityGateError("s3_quality_reason_ref_invalid")
            seen_ref_types.add(ref_type)
        required_ref_types = set(dimension_rules[str(row["dimension_id"])]["required_reason_ref_types"])
        if not seen_ref_types.intersection(required_ref_types):
            raise S3ResearchQualityGateError("s3_quality_dimension_specific_ref_missing")
        scores[str(row["dimension_id"])] = score
    total = sum(scores.values())
    thresholds = policy["thresholds"]
    formal_pass = (
        total >= thresholds["total_minimum"]
        and all(scores[f"Q{index}"] >= thresholds["Q1_to_Q7_minimum"] for index in range(1, 8))
        and all(scores[key] >= thresholds["core_dimension_minimum"] for key in CORE_DIMENSIONS)
        and sum(value >= 3 for value in scores.values()) >= thresholds["dimensions_at_or_above_three_minimum"]
        and _valid_presence_binding(packet.get("strongest_counter_thesis"), allowed, {"claim", "section"})
        and _valid_presence_binding(packet.get("adjudicated_dependency_or_conflict"), allowed, {"section"})
        and _valid_presence_binding(packet.get("actionable_WWC"), allowed, {"wwc"})
    )
    if packet.get("total_score") != total or packet.get("formal_pass") is not formal_pass:
        raise S3ResearchQualityGateError("s3_quality_score_result_invalid")
    summary_body = {
        "case_key": packet["case_key"],
        "candidate_context_digest": packet["candidate_context_digest"],
        "score_packet_digest": canonical_digest(packet),
        "scores": scores,
        "total_score": total,
        "formal_pass": formal_pass,
        "L1_status": "pass",
        "L2_status": "pass",
    }
    return {**summary_body, "summary_digest": canonical_digest(summary_body)}


def validate_paired_assessment(
    assessment: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    baseline_context: Mapping[str, Any],
    agent_context: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = validate_case_score_packet(assessment["baseline_score_packet"], policy=policy, candidate_context=baseline_context)
    agent = validate_case_score_packet(assessment["agent_score_packet"], policy=policy, candidate_context=agent_context)
    if (
        assessment.get("case_key") != baseline["case_key"]
        or agent["case_key"] != baseline["case_key"]
        or baseline_context.get("input_head_digest") != agent_context.get("input_head_digest")
        or baseline_context.get("run_id") == agent_context.get("run_id")
        or baseline_context.get("artifact_digest") == agent_context.get("artifact_digest")
    ):
        raise S3ResearchQualityGateError("s3_quality_paired_identity_invalid")
    gains = assessment.get("material_gains") or []
    gain_dimensions = set()
    for row in gains:
        dim = str(row.get("dimension_id") or "")
        if (
            dim not in DIMENSIONS
            or row.get("baseline_score") != baseline["scores"].get(dim)
            or row.get("agent_score") != agent["scores"].get(dim)
            or row.get("agent_score", 0) <= row.get("baseline_score", 0)
            or row.get("reviewer_confirmed") is not True
            or len(str(row.get("reason") or "").strip()) < 24
        ):
            raise S3ResearchQualityGateError("s3_quality_material_gain_invalid")
        for ref in row.get("reason_refs") or []:
            if str(ref.get("ref_id") or "") not in set(agent_context["allowed_reason_refs"].get(str(ref.get("ref_type") or "")) or []):
                raise S3ResearchQualityGateError("s3_quality_material_gain_ref_invalid")
        if not row.get("reason_refs"):
            raise S3ResearchQualityGateError("s3_quality_material_gain_ref_invalid")
        gain_dimensions.add(dim)
    pair_pass = agent["formal_pass"] and len(gain_dimensions) >= policy["thresholds"]["paired_material_gain_dimensions_minimum"]
    if assessment.get("paired_pass") is not pair_pass:
        raise S3ResearchQualityGateError("s3_quality_paired_result_invalid")
    result = {
        "case_key": agent["case_key"],
        "baseline_summary_digest": baseline["summary_digest"],
        "agent_summary_digest": agent["summary_digest"],
        "agent_score_packet_digest": agent["score_packet_digest"],
        "material_gain_dimensions": sorted(gain_dimensions),
        "paired_pass": pair_pass,
    }
    return {**result, "paired_digest": canonical_digest(result)}


def validate_qualified_human_content_acceptance(
    decision: Mapping[str, Any], *, paired_result: Mapping[str, Any], agent_context: Mapping[str, Any]
) -> dict[str, Any]:
    actor = str(decision.get("reviewer_identity") or "").strip().lower()
    if (
        not actor
        or any(token in actor for token in ("codex", "assistant", "automation", "bot"))
        or decision.get("reviewer_role") != "qualified_research_reviewer"
        or not _digest_like(decision.get("authenticated_session_digest"))
        or decision.get("separate_from_workflow_acceptance") is not True
        or decision.get("case_key") != paired_result.get("case_key")
        or decision.get("final_delivery_digest") != agent_context.get("final_delivery_digest")
        or decision.get("paired_digest") != paired_result.get("paired_digest")
        or decision.get("score_packet_digest") != paired_result.get("agent_score_packet_digest")
        or decision.get("action") not in {"accept_content", "return_for_research_repair"}
        or len(str(decision.get("reason") or "").strip()) < 24
    ):
        raise S3ResearchQualityGateError("s3_quality_human_decision_invalid")
    refs = decision.get("reason_refs") or []
    if not refs:
        raise S3ResearchQualityGateError("s3_quality_human_decision_ref_invalid")
    for ref in refs:
        if str(ref.get("ref_id") or "") not in set(agent_context["allowed_reason_refs"].get(str(ref.get("ref_type") or "")) or []):
            raise S3ResearchQualityGateError("s3_quality_human_decision_ref_invalid")
    if decision.get("action") == "accept_content" and paired_result.get("paired_pass") is not True:
        raise S3ResearchQualityGateError("s3_quality_human_accept_without_pair")
    body = {key: deepcopy(value) for key, value in decision.items() if key != "decision_digest"}
    if decision.get("decision_digest") != canonical_digest(body):
        raise S3ResearchQualityGateError("s3_quality_human_decision_digest_invalid")
    return dict(decision)


def _compile_candidate_context(*, workpaper: Mapping[str, Any], cards: list[Mapping[str, Any]]) -> dict[str, Any]:
    allowed = {key: [] for key in REF_TYPES}
    allowed["claim"] = sorted(str(row["claim_card_id"]) for row in cards)
    allowed["section"] = sorted(str(row["lens_id"]) for row in workpaper["sections"])
    allowed["evidence"] = sorted(
        {str(value) for row in cards for value in (row.get("support_candidate_ids") or []) + (row.get("counterevidence_candidate_ids") or [])}
    )
    allowed["numeric"] = sorted(
        {str(fact["candidate_id"]) for row in cards for fact in row.get("numeric_facts") or []}
    )
    allowed["wwc"] = sorted(
        {str(item["alias"]) for row in cards for item in row.get("what_would_change") or []}
    )
    body = {
        "case_key": workpaper["case_key"],
        "workpaper_id": workpaper["workpaper_id"],
        "workpaper_digest": workpaper["workpaper_digest"],
        "authority": workpaper["workpaper_authority"],
        "generic_precheck_status": "pass",
        "L1_status": "not_performed",
        "L2_status": "not_performed",
        "final_delivery_digest": None,
        "verifier_binding_digest": None,
        "identity_sealed": False,
        "input_head_digest": None,
        "run_id": None,
        "artifact_digest": None,
        "allowed_reason_refs": allowed,
    }
    return {**body, "candidate_context_digest": canonical_digest(body)}


def _validate_candidate_context(context: Mapping[str, Any]) -> None:
    body = {key: deepcopy(value) for key, value in context.items() if key != "candidate_context_digest"}
    if context.get("case_key") not in CASES or context.get("candidate_context_digest") != canonical_digest(body):
        raise S3ResearchQualityGateError("s3_quality_candidate_context_invalid")
    allowed = context.get("allowed_reason_refs") or {}
    if tuple(sorted(allowed)) != tuple(sorted(REF_TYPES)) or not allowed.get("claim") or len(allowed.get("section") or []) != 8:
        raise S3ResearchQualityGateError("s3_quality_candidate_refs_invalid")
    if any(len(values) != len(set(values)) for values in allowed.values()):
        raise S3ResearchQualityGateError("s3_quality_candidate_refs_duplicate")


def _scoreability_reasons(context: Mapping[str, Any]) -> list[str]:
    reasons = []
    if context.get("authority") != "all_natural_candidate":
        reasons.append("fixture_mixed_authority")
    if context.get("generic_precheck_status") != "pass":
        reasons.append("generic_or_coverage_precheck_failed")
    if context.get("L1_status") != "pass":
        reasons.append("L1_not_passed")
    if context.get("L2_status") != "pass":
        reasons.append("L2_not_passed")
    if not _digest_like(context.get("final_delivery_digest")):
        reasons.append("final_delivery_not_bound")
    if not _digest_like(context.get("verifier_binding_digest")):
        reasons.append("verifier_binding_missing")
    if context.get("identity_sealed") is not True:
        reasons.append("reviewer_packet_identity_not_sealed")
    if not _digest_like(context.get("input_head_digest")) or not context.get("run_id") or not _digest_like(context.get("artifact_digest")):
        reasons.append("run_artifact_identity_incomplete")
    return reasons


def _digest_like(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _valid_presence_binding(value: Any, allowed: Mapping[str, list[str]], required_types: set[str]) -> bool:
    if not isinstance(value, Mapping) or value.get("present") is not True:
        return False
    refs = value.get("refs") or []
    seen = set()
    for ref in refs:
        ref_type = str(ref.get("ref_type") or "")
        ref_id = str(ref.get("ref_id") or "")
        if ref_id not in set(allowed.get(ref_type) or []):
            return False
        seen.add(ref_type)
    return bool(seen.intersection(required_types))


def _record_digest_ok(record: Mapping[str, Any]) -> bool:
    body = {key: deepcopy(value) for key, value in record.items() if key != "record_digest"}
    return record.get("record_digest") == canonical_digest(body)
