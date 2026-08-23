from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping

from sec_agent.canonical_runtime import (
    canonical_digest,
    compile_verifier_feedback_receipts,
    validate_runtime_artifact,
)

from .multi_agent_preview import (
    specialist_workpaper_tool,
    validate_specialist_workpaper,
)


SEMANTIC_REPAIR_CONTEXT_SCHEMA_VERSION = (
    "fin_ia_dynamic_single_unit_semantic_repair_context_v1_0"
)
SEMANTIC_REPAIR_PLAN_SCHEMA_VERSION = (
    "fin_ia_dynamic_single_unit_semantic_repair_plan_v1_0"
)
SEMANTIC_REPAIR_PATCH_SCHEMA_VERSION = (
    "fin_ia_dynamic_single_unit_semantic_repair_patch_v1_0"
)

REPAIRABLE_SURFACES = ("thesis", "sourced_claims", "mechanism")
LOCKED_WORKPAPER_FIELDS = (
    "confidence",
    "alternative_explanations",
    "strongest_counterarguments",
    "remaining_gap_refs",
    "what_would_change",
    "cross_role_challenges",
    "stop_reason",
)

_RESOLUTION_POLICY: dict[str, dict[str, Any]] = {
    "management_target_promoted_to_reliable_realized_conversion_rate": {
        "resolution_action": "downgrade_management_assertion",
        "affected_surfaces": ("thesis", "sourced_claims", "mechanism"),
        "semantic_commitment": "issuer_target_not_verified_realized_rate",
    },
    "historical_mix_explanation_projected_into_current_quarter": {
        "resolution_action": "restore_historical_period_boundary",
        "affected_surfaces": ("thesis", "sourced_claims", "mechanism"),
        "semantic_commitment": "historical_context_not_current_period_cause",
    },
    "unsupported_value_pool_allocation_promoted_from_graph_hypothesis": {
        "resolution_action": "restore_unresolved_hypothesis",
        "affected_surfaces": ("mechanism",),
        "semantic_commitment": "value_pool_allocation_unresolved",
    },
    "current_profit_growth_internal_contradiction": {
        "resolution_action": "separate_company_metrics_and_product_causality",
        "affected_surfaces": ("thesis", "sourced_claims", "mechanism"),
        "semantic_commitment": "gross_profit_and_operating_income_separated",
    },
    "unsupported_component_and_cash_timing_specificity": {
        "resolution_action": "remove_unsupported_mechanism_specificity",
        "affected_surfaces": ("sourced_claims", "mechanism"),
        "semantic_commitment": "general_key_components_only_cash_timing_unresolved",
    },
}


class DynamicSingleUnitRepairError(ValueError):
    """Fail-closed semantic repair contract error."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DynamicSingleUnitRepairError(code)


def _all_prior_refs(workpaper: Mapping[str, Any], field: str) -> set[str]:
    return {
        str(ref)
        for row in workpaper.get("sourced_claims") or ()
        for ref in row.get(field) or ()
    }


def compile_semantic_repair_context(
    *,
    prior_full_result: Mapping[str, Any],
    assessment: Mapping[str, Any],
    assessment_ref: str,
    prior_result_ref: str,
    created_at: str,
) -> dict[str, Any]:
    """Compile one immutable R5 workpaper into an actionable repair context."""

    prior = deepcopy(dict(prior_full_result))
    source_workpaper = deepcopy(dict(prior.get("workpaper") or {}))
    full_context = deepcopy(dict(prior.get("workpaper_context") or {}))
    workpaper_body = {
        key: item
        for key, item in source_workpaper.items()
        if key != "workpaper_digest"
    }
    validator_digest = canonical_digest(workpaper_body)
    legacy_runner_digest = canonical_digest(
        {**workpaper_body, "workpaper_digest": validator_digest}
    )
    persisted_digest = str(source_workpaper.get("workpaper_digest") or "")
    _require(
        prior.get("status")
        == "completed_current_dynamic_single_unit_contract_valid_assessment_pending"
        and source_workpaper.get("agent_id") == "AGENT::VALUE_CAPTURE"
        and persisted_digest in {validator_digest, legacy_runner_digest}
        and str(source_workpaper.get("context_digest") or "")
        == str(full_context.get("context_digest") or ""),
        "dynamic_semantic_repair_predecessor_invalid",
    )
    l1 = assessment.get("l1_financial_truth") or {}
    findings = list(l1.get("material_findings") or ())
    finding_codes = [str(row.get("code") or "") for row in findings]
    _require(
        assessment.get("case_key") == "DELL"
        and assessment.get("cell_id") == "CELL::value_capture"
        and l1.get("status") == "fail"
        and len(findings) == len(_RESOLUTION_POLICY)
        and set(finding_codes) == set(_RESOLUTION_POLICY),
        "dynamic_semantic_repair_assessment_invalid",
    )
    session_id = "SESSION::DELL::VALUE_CAPTURE::SEMANTIC_REPAIR::" + canonical_digest(
        {
            "prior_workpaper_digest": source_workpaper["workpaper_digest"],
            "assessment": assessment,
        }
    )[:20].upper()
    verifier_findings = []
    for row in findings:
        code = str(row["code"])
        policy = _RESOLUTION_POLICY[code]
        verifier_findings.append(
            {
                "finding_code": code,
                "location": str(row.get("surface") or ""),
                "target_node_id": "AGENT::VALUE_CAPTURE",
                "model_visible_summary": (
                    "独立内容审计拒绝了当前判断。问题："
                    + str(row.get("finding") or "")
                    + " 必须恢复的边界："
                    + str(row.get("required_boundary") or "")
                ),
                "permitted_next_actions": [
                    "先在 PlanDelta 中逐条承认该问题并说明如何修订",
                    "仅修改 " + ", ".join(policy["affected_surfaces"]),
                    "按承诺 " + str(policy["semantic_commitment"]) + " 降级或删除越界判断",
                ],
                "forbidden_interpretations": [
                    "不得重新检索、引入新 Evidence 或扩大研究范围",
                    "不得把管理层目标、历史背景或图假设升级为已验证事实",
                    "不得修改已经锁定的反方、缺口、WWC、置信度或停止理由",
                ],
            }
        )
    receipts = compile_verifier_feedback_receipts(
        findings=verifier_findings,
        session_id=session_id,
        source_node_id="S3.IndependentContentVerifier",
        artifact_ref=assessment_ref,
        created_at=created_at,
    )
    _require(
        len(receipts) == len(_RESOLUTION_POLICY)
        and len({row["feedback_id"] for row in receipts}) == len(receipts)
        and all(row["target_node_id"] == "AGENT::VALUE_CAPTURE" for row in receipts),
        "dynamic_semantic_repair_feedback_invalid",
    )
    policy_rows = []
    for finding, receipt in zip(findings, receipts, strict=True):
        code = str(finding["code"])
        policy_rows.append(
            {
                "finding_code": code,
                "feedback_id": receipt["feedback_id"],
                **deepcopy(_RESOLUTION_POLICY[code]),
            }
        )
    locked = {
        field: deepcopy(source_workpaper[field]) for field in LOCKED_WORKPAPER_FIELDS
    }
    predecessor_session = deepcopy(dict(prior.get("session") or {}))
    repair_base_plan = {
        "predecessor_active_plan_ref": str(
            predecessor_session.get("active_plan_ref") or ""
        ),
        "prior_workpaper_digest": source_workpaper["workpaper_digest"],
        "repair_state": "semantic_feedback_unresolved",
        "active_feedback_ids": sorted(
            str(row["feedback_id"]) for row in receipts
        ),
    }
    body = {
        "schema_version": SEMANTIC_REPAIR_CONTEXT_SCHEMA_VERSION,
        "session_id": session_id,
        "case_identity": deepcopy(full_context.get("case_identity") or {}),
        "agent": deepcopy(full_context.get("agent") or {}),
        "prior_result_ref": prior_result_ref,
        "prior_workpaper": source_workpaper,
        "prior_workpaper_digest": source_workpaper["workpaper_digest"],
        "prior_workpaper_validator_digest": validator_digest,
        "prior_workpaper_digest_style": (
            "legacy_runner_double_digest"
            if persisted_digest == legacy_runner_digest
            else "canonical_validator_digest"
        ),
        "full_workpaper_context": full_context,
        "full_workpaper_context_digest": full_context["context_digest"],
        "assessment_ref": assessment_ref,
        "assessment_digest": canonical_digest(assessment),
        "feedback_receipts": receipts,
        "resolution_policy": policy_rows,
        "repair_base_plan": repair_base_plan,
        "repair_base_plan_digest": canonical_digest(repair_base_plan),
        "repairable_surfaces": list(REPAIRABLE_SURFACES),
        "locked_surfaces": locked,
        "locked_surfaces_digest": canonical_digest(locked),
        "authority": {
            "same_agent_must_consume_all_feedback": True,
            "plan_delta_required_before_patch": True,
            "retrieval_or_new_evidence_forbidden": True,
            "harness_may_merge_but_not_write_research_judgment": True,
            "independent_L1_L2_reassessment_required": True,
        },
    }
    return {**body, "context_digest": canonical_digest(body)}


def semantic_repair_plan_tool(context: Mapping[str, Any]) -> dict[str, Any]:
    feedback_ids = [str(row["feedback_id"]) for row in context["feedback_receipts"]]
    actions = sorted({str(row["resolution_action"]) for row in context["resolution_policy"]})
    commitments = sorted({str(row["semantic_commitment"]) for row in context["resolution_policy"]})
    return {
        "type": "function",
        "function": {
            "name": "submit_semantic_repair_plan",
            "description": "Acknowledge every active semantic finding and submit a bounded repair plan.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "agent_id",
                    "prior_workpaper_digest",
                    "feedback_resolutions",
                    "ready_to_resubmit",
                ],
                "properties": {
                    "schema_version": {"type": "string", "enum": [SEMANTIC_REPAIR_PLAN_SCHEMA_VERSION]},
                    "agent_id": {"type": "string", "enum": ["AGENT::VALUE_CAPTURE"]},
                    "prior_workpaper_digest": {"type": "string", "enum": [context["prior_workpaper_digest"]]},
                    "feedback_resolutions": {
                        "type": "array",
                        "minItems": len(feedback_ids),
                        "maxItems": len(feedback_ids),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["feedback_id", "resolution_action", "affected_surfaces", "semantic_commitment", "resolution_summary"],
                            "properties": {
                                "feedback_id": {"type": "string", "enum": feedback_ids},
                                "resolution_action": {"type": "string", "enum": actions},
                                "affected_surfaces": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": len(REPAIRABLE_SURFACES),
                                    "uniqueItems": True,
                                    "items": {"type": "string", "enum": list(REPAIRABLE_SURFACES)},
                                },
                                "semantic_commitment": {"type": "string", "enum": commitments},
                                "resolution_summary": {"type": "string", "minLength": 30, "maxLength": 800},
                            },
                        },
                    },
                    "ready_to_resubmit": {"type": "boolean", "enum": [True]},
                },
            },
        },
    }


def compile_semantic_repair_plan_messages(
    context: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    compact = {
        "case_identity": context["case_identity"],
        "agent": context["agent"],
        "prior_workpaper": {
            field: deepcopy(context["prior_workpaper"][field])
            for field in REPAIRABLE_SURFACES
        },
        "prior_workpaper_digest": context["prior_workpaper_digest"],
        "feedback_receipts": deepcopy(context["feedback_receipts"]),
        "resolution_policy": deepcopy(context["resolution_policy"]),
        "locked_surfaces_receipt": {
            "fields": list(LOCKED_WORKPAPER_FIELDS),
            "digest": context["locked_surfaces_digest"],
        },
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the same value-capture specialist whose prior workpaper was rejected by an independent financial-truth review. "
                "Read every FeedbackReceipt. Submit a repair plan covering every feedback_id exactly once. Do not defend the old wording, retrieve evidence, add authority, or rewrite locked surfaces. This call plans the repair; it does not submit the revised workpaper."
            ),
        },
        {"role": "user", "content": json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
    )


def validate_semantic_repair_plan(
    payload: Mapping[str, Any], *, context: Mapping[str, Any]
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _require(
        set(value)
        == {"schema_version", "agent_id", "prior_workpaper_digest", "feedback_resolutions", "ready_to_resubmit"}
        and value.get("schema_version") == SEMANTIC_REPAIR_PLAN_SCHEMA_VERSION
        and value.get("agent_id") == "AGENT::VALUE_CAPTURE"
        and value.get("prior_workpaper_digest") == context.get("prior_workpaper_digest")
        and value.get("ready_to_resubmit") is True,
        "dynamic_semantic_repair_plan_identity_invalid",
    )
    expected = {str(row["feedback_id"]): row for row in context["resolution_policy"]}
    resolutions = value.get("feedback_resolutions")
    _require(
        isinstance(resolutions, list)
        and len(resolutions) == len(expected)
        and {str(row.get("feedback_id") or "") for row in resolutions} == set(expected),
        "dynamic_semantic_repair_plan_feedback_coverage_invalid",
    )
    normalized = []
    for raw in resolutions:
        row = deepcopy(dict(raw))
        _require(
            set(row)
            == {"feedback_id", "resolution_action", "affected_surfaces", "semantic_commitment", "resolution_summary"},
            "dynamic_semantic_repair_plan_resolution_shape_invalid",
        )
        policy = expected[str(row["feedback_id"])]
        summary = str(row.get("resolution_summary") or "").strip()
        surfaces = tuple(sorted(str(item) for item in row.get("affected_surfaces") or ()))
        _require(
            row.get("resolution_action") == policy["resolution_action"]
            and row.get("semantic_commitment") == policy["semantic_commitment"]
            and surfaces == tuple(sorted(policy["affected_surfaces"]))
            and 30 <= len(summary) <= 800,
            "dynamic_semantic_repair_plan_resolution_invalid",
        )
        normalized.append({**row, "affected_surfaces": list(surfaces), "resolution_summary": summary})
    normalized.sort(key=lambda row: row["feedback_id"])
    value["feedback_resolutions"] = normalized
    value["plan_digest"] = canonical_digest(value)
    return value


def compile_semantic_plan_delta(
    plan: Mapping[str, Any], *, context: Mapping[str, Any]
) -> dict[str, Any]:
    _require(
        str(plan.get("plan_digest") or "")
        == canonical_digest({key: item for key, item in plan.items() if key != "plan_digest"}),
        "dynamic_semantic_repair_plan_digest_invalid",
    )
    delta_body = {
        "plan_delta_id": "PLANDELTA::" + canonical_digest(plan)[:24].upper(),
        "session_id": context["session_id"],
        "base_plan_digest": context["repair_base_plan_digest"],
        "proposed_by_agent_id": "AGENT::VALUE_CAPTURE",
        "reason_feedback_refs": [row["feedback_id"] for row in plan["feedback_resolutions"]],
        "add_actions": [],
        "modify_actions": deepcopy(plan["feedback_resolutions"]),
        "defer_actions": [],
        "cancel_actions": [],
        "expected_information_gain": "Remove five known semantic-authority errors without changing evidence or unaffected workpaper surfaces.",
        "budget_impact": {"retrieval_rounds": 0, "new_evidence": 0, "remaining_model_calls": 1},
        "validation_status": "accepted",
    }
    validated = validate_runtime_artifact("PlanDelta", delta_body)
    return {**validated, "plan_delta_digest": canonical_digest(validated)}


def semantic_repair_patch_tool(
    context: Mapping[str, Any], plan_delta: Mapping[str, Any]
) -> dict[str, Any]:
    base = specialist_workpaper_tool(
        agent_id="AGENT::VALUE_CAPTURE",
        context=context["full_workpaper_context"],
    )["function"]["parameters"]["properties"]
    feedback_ids = [str(row["feedback_id"]) for row in context["feedback_receipts"]]
    commitments = [str(row["semantic_commitment"]) for row in context["resolution_policy"]]
    return {
        "type": "function",
        "function": {
            "name": "submit_semantic_repair_patch",
            "description": "Submit only the three repaired workpaper surfaces after an accepted PlanDelta.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "agent_id", "plan_delta_digest", "resolved_feedback_ids", "semantic_commitments", "thesis", "sourced_claims", "mechanism"],
                "properties": {
                    "schema_version": {"type": "string", "enum": [SEMANTIC_REPAIR_PATCH_SCHEMA_VERSION]},
                    "agent_id": {"type": "string", "enum": ["AGENT::VALUE_CAPTURE"]},
                    "plan_delta_digest": {"type": "string", "enum": [plan_delta["plan_delta_digest"]]},
                    "resolved_feedback_ids": {
                        "type": "array", "minItems": len(feedback_ids), "maxItems": len(feedback_ids), "uniqueItems": True,
                        "items": {"type": "string", "enum": feedback_ids},
                    },
                    "semantic_commitments": {
                        "type": "array", "minItems": len(commitments), "maxItems": len(commitments), "uniqueItems": True,
                        "items": {"type": "string", "enum": commitments},
                    },
                    "thesis": deepcopy(base["thesis"]),
                    "sourced_claims": deepcopy(base["sourced_claims"]),
                    "mechanism": deepcopy(base["mechanism"]),
                },
            },
        },
    }


def compile_semantic_repair_patch_messages(
    context: Mapping[str, Any], plan: Mapping[str, Any], plan_delta: Mapping[str, Any]
) -> tuple[dict[str, str], ...]:
    full = context["full_workpaper_context"]
    analysis = full["cell_analysis_view"]
    compact_authority = {
        "case_identity": context["case_identity"],
        "agent": context["agent"],
        "reviewed_evidence": deepcopy(analysis.get("evidence_fact_catalog") or []),
        "numeric_facts": deepcopy(analysis.get("numeric_fact_catalog") or []),
        "numeric_relations": deepcopy(analysis.get("numeric_relation_catalog") or []),
        "residual_gaps": deepcopy(analysis["cell"].get("residual_gap_cards") or []),
        "prior_repairable_surfaces": {
            field: deepcopy(context["prior_workpaper"][field]) for field in REPAIRABLE_SURFACES
        },
        "feedback_receipts": deepcopy(context["feedback_receipts"]),
        "accepted_repair_plan": deepcopy(plan),
        "plan_delta": deepcopy(plan_delta),
        "locked_surfaces_receipt": {
            "fields": list(LOCKED_WORKPAPER_FIELDS),
            "digest": context["locked_surfaces_digest"],
            "values_are_merged_locally_and_must_not_be_returned": True,
        },
    }
    return (
        {
            "role": "system",
            "content": (
                "You are submitting the bounded repair you already planned. Return only thesis, sourced_claims and mechanism plus the required repair receipts. Preserve source periods, issuer-assertion status, unresolved hypotheses, metric scope and unsupported mechanism boundaries exactly as committed. Do not add evidence, change locked fields, or output a full workpaper. Submit exactly one repair tool call."
            ),
        },
        {"role": "user", "content": json.dumps(compact_authority, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
    )


def validate_and_merge_semantic_repair_patch(
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    plan_delta: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _require(
        set(value)
        == {"schema_version", "agent_id", "plan_delta_digest", "resolved_feedback_ids", "semantic_commitments", "thesis", "sourced_claims", "mechanism"}
        and value.get("schema_version") == SEMANTIC_REPAIR_PATCH_SCHEMA_VERSION
        and value.get("agent_id") == "AGENT::VALUE_CAPTURE"
        and value.get("plan_delta_digest") == plan_delta.get("plan_delta_digest"),
        "dynamic_semantic_repair_patch_identity_invalid",
    )
    expected_feedback = {str(row["feedback_id"]) for row in context["feedback_receipts"]}
    expected_commitments = {str(row["semantic_commitment"]) for row in context["resolution_policy"]}
    _require(
        set(str(item) for item in value.get("resolved_feedback_ids") or ()) == expected_feedback
        and len(value.get("resolved_feedback_ids") or ()) == len(expected_feedback)
        and set(str(item) for item in value.get("semantic_commitments") or ()) == expected_commitments
        and len(value.get("semantic_commitments") or ()) == len(expected_commitments),
        "dynamic_semantic_repair_patch_feedback_invalid",
    )
    prior = context["prior_workpaper"]
    merged_payload = {
        "schema_version": prior["schema_version"],
        "agent_id": prior["agent_id"],
        "thesis": value["thesis"],
        "confidence": prior["confidence"],
        "sourced_claims": value["sourced_claims"],
        "mechanism": value["mechanism"],
        **{field: deepcopy(prior[field]) for field in LOCKED_WORKPAPER_FIELDS if field != "confidence"},
    }
    validated = validate_specialist_workpaper(
        merged_payload,
        context=context["full_workpaper_context"],
        expected_agent_id="AGENT::VALUE_CAPTURE",
    )
    for ref_field in ("evidence_refs", "numeric_refs", "numeric_relation_refs"):
        prior_refs = _all_prior_refs(prior, ref_field)
        repaired_refs = _all_prior_refs(validated, ref_field)
        _require(
            repaired_refs.issubset(prior_refs),
            "dynamic_semantic_repair_patch_new_reference_forbidden",
        )
    locked_after = {field: deepcopy(validated[field]) for field in LOCKED_WORKPAPER_FIELDS}
    _require(
        canonical_digest(locked_after) == context["locked_surfaces_digest"],
        "dynamic_semantic_repair_locked_surface_drift",
    )
    repair_receipt = {
        "schema_version": "fin_ia_dynamic_single_unit_semantic_repair_receipt_v1_0",
        "prior_workpaper_digest": context["prior_workpaper_digest"],
        "repaired_workpaper_digest": validated["workpaper_digest"],
        "plan_delta_digest": plan_delta["plan_delta_digest"],
        "resolved_feedback_ids": sorted(expected_feedback),
        "semantic_commitments": sorted(expected_commitments),
        "modified_surfaces": list(REPAIRABLE_SURFACES),
        "locked_surfaces_digest": context["locked_surfaces_digest"],
        "new_reference_count": 0,
        "retrieval_round_count": 0,
        "candidate_promotion_count": 0,
        "independent_L1_L2_reassessment_required": True,
    }
    return {
        "workpaper": validated,
        "repair_receipt": {
            **repair_receipt,
            "repair_receipt_digest": canonical_digest(repair_receipt),
        },
    }


__all__ = [
    "DynamicSingleUnitRepairError",
    "LOCKED_WORKPAPER_FIELDS",
    "REPAIRABLE_SURFACES",
    "SEMANTIC_REPAIR_CONTEXT_SCHEMA_VERSION",
    "SEMANTIC_REPAIR_PATCH_SCHEMA_VERSION",
    "SEMANTIC_REPAIR_PLAN_SCHEMA_VERSION",
    "compile_semantic_plan_delta",
    "compile_semantic_repair_context",
    "compile_semantic_repair_patch_messages",
    "compile_semantic_repair_plan_messages",
    "semantic_repair_patch_tool",
    "semantic_repair_plan_tool",
    "validate_and_merge_semantic_repair_patch",
    "validate_semantic_repair_plan",
]
