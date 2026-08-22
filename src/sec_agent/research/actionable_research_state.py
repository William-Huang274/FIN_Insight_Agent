from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

from retrieval.source_use_policy import SourceUsePolicy
from sec_agent.canonical_runtime.feedback import compile_s1_feedback_receipts
from sec_agent.canonical_runtime.session import (
    append_session_event,
    apply_accepted_plan_delta,
    canonical_digest,
    create_agent_session,
    create_context_checkpoint,
    resume_agent_session,
    validate_runtime_artifact,
)


ACTIONABLE_RESEARCH_STATE_SCHEMA_VERSION = (
    "fin_ia_actionable_research_state_v1_0"
)
ACTIONABLE_UNCERTAINTY_SCHEMA_VERSION = "fin_ia_actionable_uncertainty_v1_0"
RESEARCH_ACTION_SCHEMA_VERSION = "fin_ia_research_action_v1_0"
TOKEN_BUDGET_BASIS_SCHEMA_VERSION = "fin_ia_token_budget_basis_v1_0"


class ActionableResearchStateError(ValueError):
    """Raised when uncertainty cannot be routed without inventing authority."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ActionableResearchStateError(code)


def _source_class_for_evidence(
    source: Mapping[str, Any], *, case_key: str
) -> str:
    owner = str(source.get("evidence_owner_ticker") or "").upper()
    source_type = str(source.get("source_type") or "").lower()
    tier = str(source.get("source_tier") or "").lower()
    license_scope = str(source.get("license_scope") or "").lower()
    regulatory_filing = (
        source_type in {"10-k", "10-q", "8-k", "20-f", "40-f", "6-k"}
        or "sec_filing" in tier
    )
    if regulatory_filing:
        return (
            "issuer_regulator_or_government_primary"
            if owner == case_key
            else "named_counterparty_or_standards_primary"
        )
    if license_scope not in {
        "",
        "public",
        "public_official_source_research_use",
    }:
        return "licensed_structured_or_user_entitled"
    if owner == case_key and ("company" in tier or "government" in tier):
        return "issuer_regulator_or_government_primary"
    if owner and owner != case_key and (
        "primary" in tier or "company" in tier or "standards" in tier
    ):
        return "named_counterparty_or_standards_primary"
    if any(value in tier for value in ("market", "industry", "government")):
        return "official_market_or_industry_primary"
    return "trusted_media_industry_association_or_public_analyst_context"


def _source_portfolio_snapshot(
    *,
    case_key: str,
    evidence_items: Sequence[Mapping[str, Any]],
    policy: SourceUsePolicy,
) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for raw in evidence_items:
        source = dict(raw.get("source") or {})
        digest = str(
            source.get("source_text_digest")
            or raw.get("evidence_item_digest")
            or ""
        )
        _require(digest, "actionable_source_portfolio_digest_missing")
        source_class = _source_class_for_evidence(source, case_key=case_key)
        source_policy = policy.classes.get(source_class)
        _require(source_policy is not None, "actionable_source_class_unregistered")
        unique.setdefault(
            digest,
            {
                "source_digest": digest,
                "source_class": source_class,
                "source_type": str(source.get("source_type") or ""),
                "evidence_owner_ticker": str(
                    source.get("evidence_owner_ticker") or ""
                ).upper(),
                "license_scope": str(source.get("license_scope") or ""),
                "redistributable_source_flag": source.get("redistributable") is True,
                "rights": {
                    "discovery": source_policy.discovery_right,
                    "internal_analysis": source_policy.internal_analysis_right,
                    "citation": source_policy.citation_right,
                    "redistribution": source_policy.redistribution_right,
                },
            },
        )
    class_counts = Counter(row["source_class"] for row in unique.values())
    source_type_counts = Counter(row["source_type"] for row in unique.values())
    body = {
        "current_source_count": len(unique),
        "source_class_counts": dict(sorted(class_counts.items())),
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "rights_axes": [
            "discovery",
            "internal_analysis",
            "citation",
            "redistribution",
        ],
        "sources": sorted(
            unique.values(), key=lambda row: (row["source_class"], row["source_digest"])
        ),
        "portfolio_boundary": {
            "source_strength_is_not_claim_truth": True,
            "discovery_locator_is_not_evidence": True,
            "citation_permission_does_not_imply_redistribution_permission": True,
            "speaker_and_subject_remain_distinct": True,
        },
    }
    return {**body, "portfolio_digest": canonical_digest(body)}


def _source_portfolio_for_action(
    action_type: str, policy: SourceUsePolicy
) -> list[dict[str, Any]]:
    if action_type != "targeted_source_supplement":
        return []
    requested = (
        (
            "issuer_regulator_or_government_primary",
            "target_company_exact_fact",
        ),
        (
            "named_counterparty_or_standards_primary",
            "speaker_attributed_mechanism",
        ),
        (
            "official_market_or_industry_primary",
            "bounded_market_context",
        ),
        (
            "trusted_media_industry_association_or_public_analyst_context",
            "bounded_target_context",
        ),
        (
            "search_rss_gdelt_or_common_crawl_discovery",
            "discovery_locator",
        ),
    )
    output = []
    for source_class, claim_use in requested:
        row = policy.classes[source_class]
        output.append(
            {
                "source_class": source_class,
                "claim_use": claim_use,
                "rights": {
                    "discovery": row.discovery_right,
                    "internal_analysis": row.internal_analysis_right,
                    "citation": row.citation_right,
                    "redistribution": row.redistribution_right,
                },
                "original_capture_required": row.requires_original_capture,
                "minimum_independent_sources": row.minimum_independent_sources,
            }
        )
    return output


def _uncertainty(
    *,
    case_key: str,
    request_id: str,
    slot_id: str,
    facet_id: str,
    question: str,
    category: str,
    earliest_stage: str,
    owning_plane: str,
    reason_codes: Sequence[str],
    source_gap_id: str | None = None,
) -> dict[str, Any]:
    seed = {
        "case_key": case_key,
        "request_id": request_id,
        "slot_id": slot_id,
        "facet_id": facet_id,
        "category": category,
        "source_gap_id": source_gap_id,
    }
    body = {
        "schema_version": ACTIONABLE_UNCERTAINTY_SCHEMA_VERSION,
        "uncertainty_id": "UNCERTAINTY::" + canonical_digest(seed)[:24].upper(),
        "case_key": case_key,
        "request_id": request_id,
        "slot_id": slot_id,
        "facet_id": facet_id,
        "business_question_zh": question,
        "uncertainty_category": category,
        "earliest_responsible_stage": earliest_stage,
        "owning_plane": owning_plane,
        "reason_codes": sorted(set(str(value) for value in reason_codes if str(value))),
        "declared_gap_id": source_gap_id,
        "information_boundary_state": "not_proved",
        "public_information_gap_authority": False,
        "customer_visible_disposition": "convert_to_research_action_not_disclaimer",
    }
    return {**body, "uncertainty_digest": canonical_digest(body)}


def _research_action(
    *,
    uncertainty: Mapping[str, Any],
    action_type: str,
    owner_stage: str,
    owning_plane: str,
    tool_or_gate: str,
    objective_zh: str,
    input_refs: Sequence[str],
    success_criteria: Sequence[str],
    stop_conditions: Sequence[str],
    source_policy: SourceUsePolicy,
) -> dict[str, Any]:
    seed = {
        "uncertainty_id": uncertainty["uncertainty_id"],
        "action_type": action_type,
        "tool_or_gate": tool_or_gate,
    }
    body = {
        "schema_version": RESEARCH_ACTION_SCHEMA_VERSION,
        "action_id": "ACTION::" + canonical_digest(seed)[:24].upper(),
        "uncertainty_ref": uncertainty["uncertainty_id"],
        "case_key": uncertainty["case_key"],
        "request_id": uncertainty["request_id"],
        "slot_id": uncertainty["slot_id"],
        "facet_id": uncertainty["facet_id"],
        "action_type": action_type,
        "owner_stage": owner_stage,
        "owning_plane": owning_plane,
        "tool_or_gate": tool_or_gate,
        "objective_zh": objective_zh,
        "input_refs": sorted(set(str(value) for value in input_refs if str(value))),
        "success_criteria": list(success_criteria),
        "stop_conditions": list(stop_conditions),
        "preferred_source_portfolio": _source_portfolio_for_action(
            action_type, source_policy
        ),
        "execution_state": "authorized_next_step_not_yet_executed",
        "candidate_promotion_authority": False,
        "numeric_fact_authority": False,
        "public_information_gap_authority": False,
    }
    _require(
        body["success_criteria"] and body["stop_conditions"],
        "research_action_termination_contract_missing",
    )
    return {**body, "action_digest": canonical_digest(body)}


def _state_action_pair(
    *,
    case_key: str,
    request: Mapping[str, Any],
    policy: SourceUsePolicy,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    state = str(request.get("readiness_state") or "")
    if state == "ready_for_current_scope":
        return None
    request_id = str(request.get("request_id") or "")
    slot = str(request.get("slot_id") or "")
    facet = str(request.get("facet_id") or "")
    question = str(request.get("business_question_zh") or request_id)
    route = dict(request.get("route_execution_state") or {})
    if state == "blocked_by_candidate_coverage":
        source_required = route.get("source_supplement_route_required") is True
        source_exhausted = (
            route.get("official_or_external_supplement_route_exhausted") is True
        )
        if source_required and not source_exhausted:
            category = "reachable_source_route_not_terminal"
            action_type = "targeted_source_supplement"
            tool = "S1.SourceRouteExecutor"
            objective = "执行当前命题允许的来源组合，先 capture 原始资料，再进入解析和 Evidence Gate。"
            criteria = (
                "每条 required route 获得 executed、terminal failure 或 exhausted receipt",
                "新材料保持 speaker、subject、期间、来源类型和原始 capture 绑定",
            )
        else:
            category = "local_candidate_coverage_or_ranking_failure"
            action_type = "replay_local_candidate_pipeline"
            tool = "S1.TypedRetrieval"
            objective = "在相同请求下复查对象化、query facets、召回、排序和 Evidence Role 的最早丢失层。"
            criteria = (
                "每个 material requirement 获得候选或明确的最早本地损失层",
                "错公司、错期、错关系方向候选仍保持零晋升",
            )
        uncertainty = _uncertainty(
            case_key=case_key,
            request_id=request_id,
            slot_id=slot,
            facet_id=facet,
            question=question,
            category=category,
            earliest_stage="S1",
            owning_plane="infrastructure_and_tool_plane",
            reason_codes=(state, *request.get("unexecuted_or_unavailable_routes", ())),
        )
        action = _research_action(
            uncertainty=uncertainty,
            action_type=action_type,
            owner_stage="S1",
            owning_plane="infrastructure_and_tool_plane",
            tool_or_gate=tool,
            objective_zh=objective,
            input_refs=(f"request://{request_id}",),
            success_criteria=criteria,
            stop_conditions=(
                "不得因一次空结果宣告公开信息不存在",
                "route、parse、object、index 或 ranking failure 必须返回其 owning layer",
            ),
            source_policy=policy,
        )
        return uncertainty, action
    if state == "blocked_by_evidence_admission":
        uncertainty = _uncertainty(
            case_key=case_key,
            request_id=request_id,
            slot_id=slot,
            facet_id=facet,
            question=question,
            category="candidate_present_evidence_authority_pending",
            earliest_stage="S1",
            owning_plane="harness_control_plane",
            reason_codes=(state, "reviewed_evidence_admission_pending"),
        )
        action = _research_action(
            uncertainty=uncertainty,
            action_type="adjudicate_candidate_to_evidence",
            owner_stage="S1",
            owning_plane="harness_control_plane",
            tool_or_gate="S1.EvidenceGate",
            objective_zh="逐条裁决已有候选与命题、来源、期间和 Evidence Role 的绑定。",
            input_refs=(f"request://{request_id}",),
            success_criteria=(
                "每个 material requirement 获得 accept、reject 或 needs-review 回执",
                "只有 accept 且 exact binding 通过的对象进入 reviewed Evidence Pack",
            ),
            stop_conditions=(
                "排名或语义相似不得自动晋升 Evidence",
                "Evidence admission 不得自动触发无界 broad search",
            ),
            source_policy=policy,
        )
        return uncertainty, action
    if state == "partial_with_material_gaps":
        uncertainty = _uncertainty(
            case_key=case_key,
            request_id=request_id,
            slot_id=slot,
            facet_id=facet,
            question=question,
            category="partial_answer_numeric_or_material_support_open",
            earliest_stage="S2",
            owning_plane="infrastructure_and_tool_plane",
            reason_codes=(state, str(request.get("numeric_authority_state", {}).get("state") or "")),
        )
        action = _research_action(
            uncertainty=uncertainty,
            action_type="resolve_numeric_fact_or_bridge",
            owner_stage="S2",
            owning_plane="infrastructure_and_tool_plane",
            tool_or_gate="S2.NumericFactTool",
            objective_zh="按同公司、同期间、同单位和同口径查询 NumericFact，并区分事实、派生、估计和情景。",
            input_refs=(f"request://{request_id}",),
            success_criteria=(
                "每个 typed fact request 形成 resolved、typed gap 或 typed conflict",
                "派生指标携带公式和输入 NumericFact refs",
            ),
            stop_conditions=(
                "typed gap 不得改写为公开信息不存在",
                "模型不得从冲突数字中挑选更符合叙事的一项",
            ),
            source_policy=policy,
        )
        return uncertainty, action
    uncertainty = _uncertainty(
        case_key=case_key,
        request_id=request_id,
        slot_id=slot,
        facet_id=facet,
        question=question,
        category="typed_readiness_failure",
        earliest_stage="S1",
        owning_plane="infrastructure_and_tool_plane",
        reason_codes=(state or "readiness_state_missing",),
    )
    action = _research_action(
        uncertainty=uncertainty,
        action_type="repair_earliest_typed_failure",
        owner_stage="S1",
        owning_plane="infrastructure_and_tool_plane",
        tool_or_gate="S1.EarliestResponsibleLayer",
        objective_zh="读取 typed readiness 与 provenance，只修复最早责任层。",
        input_refs=(f"request://{request_id}",),
        success_criteria=("当前 request 获得可审计的新 readiness 终态",),
        stop_conditions=("不得把本地工具失败改写为 Agent 或公开信息失败",),
        source_policy=policy,
    )
    return uncertainty, action


def _gap_action_pair(
    *,
    case_key: str,
    gap: Mapping[str, Any],
    matching_request: Mapping[str, Any] | None,
    policy: SourceUsePolicy,
) -> tuple[dict[str, Any], dict[str, Any]]:
    gap_id = str(gap.get("gap_id") or "")
    slot = str(gap.get("slot_id") or "")
    facet = str(gap.get("facet_id") or "")
    request_id = str((matching_request or {}).get("request_id") or f"GAP::{gap_id}")
    question = str(
        (matching_request or {}).get("business_question_zh")
        or gap.get("business_reason_zh")
        or gap_id
    )
    gap_code = str(gap.get("gap_code") or "declared_pack_gap")
    method_markers = ("threshold", "monitor", "what_would_change", "risk_tolerance")
    is_method = any(marker in gap_code.lower() for marker in method_markers)
    if is_method:
        category = "research_method_parameter_missing"
        stage = "S3"
        plane = "agent_work_mode_plane"
        action_type = "set_research_method_threshold"
        tool = "S3.ResearchMethod"
        objective = "把已知监控指标转成可观察的失效阈值、时间窗和升级条件。"
        criteria = (
            "阈值绑定当前 thesis、指标、方向、观察窗口和 What-Would-Change",
            "阈值不是来源 gap，也不由 Writer 代填",
        )
    else:
        category = "declared_gap_free_source_exhaustion_not_proved"
        stage = "S1"
        plane = "infrastructure_and_tool_plane"
        action_type = "targeted_source_supplement"
        tool = "S1.SourceRouteExecutor"
        objective = str(
            gap.get("supplement_direction_zh")
            or "按命题和 Evidence Slot 定向补充来源，不做无界网页堆积。"
        )
        criteria = (
            "新增原始 capture 能支持该命题、反方或明确收窄结论",
            "若仍无结果，所有免费可达路线都有终态且 GapEligibility 重新裁决",
        )
    uncertainty = _uncertainty(
        case_key=case_key,
        request_id=request_id,
        slot_id=slot,
        facet_id=facet,
        question=question,
        category=category,
        earliest_stage=stage,
        owning_plane=plane,
        reason_codes=(gap_code, "declared_gap_without_public_boundary_authority"),
        source_gap_id=gap_id,
    )
    action = _research_action(
        uncertainty=uncertainty,
        action_type=action_type,
        owner_stage=stage,
        owning_plane=plane,
        tool_or_gate=tool,
        objective_zh=objective,
        input_refs=(f"gap://{gap_id}", f"request://{request_id}"),
        success_criteria=criteria,
        stop_conditions=(
            "只有 GapEligibilityReceipt 通过才能标记真实公开信息边界",
            "失败路线、未执行路线、预算不足或模型未发起请求不得冒充边界",
        ),
        source_policy=policy,
    )
    return uncertainty, action


def _token_budget_basis(
    *,
    case_key: str,
    evidence_items: Sequence[Mapping[str, Any]],
    uncertainties: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    feedback: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    input_chars = sum(
        len(str((item.get("source") or {}).get("reviewed_source_excerpt") or ""))
        for item in evidence_items
    )
    required_output_units = {
        "coverage_reflections": len(uncertainties),
        "action_dispositions": len(actions),
        "feedback_responses": len(feedback),
        "plan_delta": 1,
        "stop_decision": 1,
    }
    minimum_visible_tokens = max(
        1800,
        700
        + 180 * len(uncertainties)
        + 140 * len(actions)
        + 80 * len(feedback),
    )
    body = {
        "schema_version": TOKEN_BUDGET_BASIS_SCHEMA_VERSION,
        "basis_id": "TOKENBASIS::"
        + canonical_digest(
            {
                "case_key": case_key,
                "input_chars": input_chars,
                "required_output_units": required_output_units,
            }
        )[:24].upper(),
        "node_purpose": "consume_typed_feedback_and_submit_bounded_research_plan_delta",
        "case_key": case_key,
        "input_scale": {
            "reviewed_evidence_item_count": len(evidence_items),
            "reviewed_evidence_visible_char_count": input_chars,
            "actionable_uncertainty_count": len(uncertainties),
            "research_action_count": len(actions),
            "feedback_receipt_count": len(feedback),
        },
        "required_outputs": required_output_units,
        "schema_burden": {
            "analysis_and_strict_submission_are_separate": True,
            "required_contracts": ["PlanDelta", "GraphDelta", "StopDecision"],
        },
        "materiality_and_quality_risk": "high_financial_research_plan_may_change_search_and_judgment_scope",
        "comparable_run_evidence": [
            "DELL_multi_agent_preview_reasoning_output_competition",
            "DELL_fragment_analysis_then_non_thinking_submission_successor",
        ],
        "reasoning_profile": {
            "analysis": "provider_neutral_deep_reasoning",
            "strict_submission": "non_thinking_contract_mapping",
        },
        "capacity_basis": {
            "minimum_visible_output_tokens": minimum_visible_tokens,
            "formula": "max(1800,700+180*uncertainties+140*actions+80*feedback)",
            "headroom_must_be_recalibrated_from_actual_usage": True,
        },
        "stop_or_truncation_behavior": {
            "truncation_is_failure": True,
            "budget_insufficient_returns_typed_deferral": True,
            "required_research_actions_may_not_be_silently_dropped": True,
        },
        "cost_and_latency_are_secondary_constraints": True,
        "execution_authority": False,
        "model_calls": 0,
        "paid_tool_calls": 0,
    }
    return {**body, "token_budget_basis_digest": canonical_digest(body)}


def compile_actionable_research_state(
    *,
    case_key: str,
    product_readiness: Mapping[str, Any],
    residual_gaps: Sequence[Mapping[str, Any]],
    evidence_items: Sequence[Mapping[str, Any]],
    quantitative_authority: Mapping[str, Any],
    source_use_policy: SourceUsePolicy,
    recorded_at: str,
) -> dict[str, Any]:
    """Connect current S1/S2 truth to durable feedback, plan and resume state."""

    normalized_case = str(case_key).strip().upper()
    _require(
        normalized_case
        and product_readiness.get("case_key") == normalized_case
        and quantitative_authority.get("case_key") == normalized_case,
        "actionable_research_case_binding_invalid",
    )
    requests = [dict(row) for row in product_readiness.get("requests") or ()]
    _require(requests, "actionable_research_requests_missing")
    uncertainties: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for request in requests:
        pair = _state_action_pair(
            case_key=normalized_case,
            request=request,
            policy=source_use_policy,
        )
        if pair is not None:
            uncertainty, action = pair
            uncertainties.append(uncertainty)
            actions.append(action)

    request_by_exact = {
        (str(row.get("slot_id") or ""), str(row.get("facet_id") or "")): row
        for row in requests
    }
    request_by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in requests:
        request_by_slot[str(row.get("slot_id") or "")].append(row)
    for raw_gap in residual_gaps:
        gap = dict(raw_gap)
        key = (str(gap.get("slot_id") or ""), str(gap.get("facet_id") or ""))
        matching = request_by_exact.get(key)
        if matching is None:
            choices = request_by_slot.get(key[0]) or []
            matching = choices[0] if len(choices) == 1 else None
        uncertainty, action = _gap_action_pair(
            case_key=normalized_case,
            gap=gap,
            matching_request=matching,
            policy=source_use_policy,
        )
        uncertainties.append(uncertainty)
        actions.append(action)

    uncertainty_ids = [row["uncertainty_id"] for row in uncertainties]
    action_ids = [row["action_id"] for row in actions]
    _require(
        len(uncertainty_ids) == len(set(uncertainty_ids))
        and len(action_ids) == len(set(action_ids)),
        "actionable_research_identity_collision",
    )
    source_portfolio = _source_portfolio_snapshot(
        case_key=normalized_case,
        evidence_items=evidence_items,
        policy=source_use_policy,
    )
    readiness_ref = "readiness://" + str(product_readiness.get("result_digest") or "")
    session_seed = {
        "case_key": normalized_case,
        "readiness_ref": readiness_ref,
        "quantitative_authority_digest": quantitative_authority.get(
            "quantitative_authority_digest"
        ),
    }
    session_id = "SESSION::" + canonical_digest(session_seed)[:24].upper()
    base_plan = {
        "case_key": normalized_case,
        "ready_request_ids": sorted(
            str(row["request_id"])
            for row in requests
            if row.get("readiness_state") == "ready_for_current_scope"
        ),
        "pending_action_ids": [],
    }
    base_plan_digest = canonical_digest(base_plan)
    session = create_agent_session(
        session_id=session_id,
        run_id="RUN::" + canonical_digest(session_seed)[:24].upper(),
        case_id=f"case_{normalized_case.lower()}_current",
        case_version="FIN_0_1_3",
        as_of_date=str(product_readiness.get("research_as_of") or "2026-08-06"),
        objective_ref=f"objective://{normalized_case}/current-research-readiness",
        active_plan_ref="PLAN::" + base_plan_digest[:24].upper(),
        created_at=recorded_at,
    )
    feedback = compile_s1_feedback_receipts(
        readiness=product_readiness,
        session_id=session_id,
        artifact_ref=readiness_ref,
        created_at=recorded_at,
    )
    _require(feedback, "actionable_research_feedback_missing")
    feedback_refs = [row["feedback_id"] for row in feedback]
    plan_delta_body = {
        "plan_delta_id": "PLANDELTA::"
        + canonical_digest(
            {
                "session_id": session_id,
                "feedback_refs": feedback_refs,
                "action_ids": action_ids,
            }
        )[:24].upper(),
        "session_id": session_id,
        "base_plan_digest": base_plan_digest,
        "proposed_by_agent_id": "HARNESS::ACTIONABLE-STATE-COMPILER",
        "reason_feedback_refs": feedback_refs,
        "add_actions": [
            {
                "action_ref": row["action_id"],
                "owner_stage": row["owner_stage"],
                "tool_or_gate": row["tool_or_gate"],
            }
            for row in actions
        ],
        "modify_actions": [],
        "defer_actions": [],
        "cancel_actions": [],
        "expected_information_gain": "close_earliest_responsible_layer_or_prove_typed_boundary",
        "budget_impact": {
            "model_calls_authorized": 0,
            "paid_tool_calls_authorized": 0,
            "tool_and_human_actions": len(actions),
        },
        "validation_status": "accepted",
    }
    plan_delta = validate_runtime_artifact("PlanDelta", plan_delta_body)
    plan_delta = {**plan_delta, "plan_delta_digest": canonical_digest(plan_delta)}
    accepted_plan = {
        **base_plan,
        "pending_action_ids": action_ids,
        "reason_feedback_refs": feedback_refs,
    }
    accepted_plan_digest = canonical_digest(accepted_plan)
    accepted_plan_ref = "PLAN::" + accepted_plan_digest[:24].upper()
    session = apply_accepted_plan_delta(
        session=session,
        plan_delta=plan_delta,
        expected_base_plan_digest=base_plan_digest,
        accepted_plan_digest=accepted_plan_digest,
        accepted_plan_ref=accepted_plan_ref,
        updated_at=recorded_at,
    )
    graph_delta_body = {
        "graph_delta_id": "GRAPHDELTA::"
        + canonical_digest(
            {"session_id": session_id, "actions": action_ids}
        )[:24].upper(),
        "session_id": session_id,
        "base_graph_digest": canonical_digest(
            {"case_key": normalized_case, "graph_state": "current_reviewed_graph"}
        ),
        "proposed_by_agent_id": "HARNESS::ACTIONABLE-STATE-COMPILER",
        "edge_additions": [],
        "edge_corrections": [],
        "edge_retractions": [],
        "supporting_evidence_refs": [],
        "hypothesis_only_edges": [],
        "validation_status": "accepted",
        "disposition": "no_graph_mutation_without_reviewed_relationship_evidence",
    }
    graph_delta = validate_runtime_artifact("GraphDelta", graph_delta_body)
    graph_delta = {**graph_delta, "graph_delta_digest": canonical_digest(graph_delta)}
    stop_body = {
        "stop_decision_id": "STOP::"
        + canonical_digest(
            {"session_id": session_id, "actions": action_ids, "gaps": uncertainty_ids}
        )[:24].upper(),
        "session_id": session_id,
        "decided_by_agent_id": "HARNESS::ACTIONABLE-STATE-COMPILER",
        "decision": "continue" if actions else "stop_sufficient",
        "reason_codes": (
            ["actionable_research_actions_pending"]
            if actions
            else ["current_scope_coverage_sufficient"]
        ),
        "coverage_state_refs": uncertainty_ids,
        "unresolved_feedback_refs": feedback_refs,
        "remaining_gap_refs": sorted(
            str(row.get("gap_id") or "") for row in residual_gaps if row.get("gap_id")
        ),
        "budget_state": {
            "model_calls_used": 0,
            "paid_tool_calls_used": 0,
            "required_actions_silently_dropped": False,
        },
        "quality_risk": "high_while_material_actions_or_unproved_gaps_remain",
        "harness_validation_status": "accepted",
    }
    stop_decision = validate_runtime_artifact("StopDecision", stop_body)
    stop_decision = {
        **stop_decision,
        "stop_decision_digest": canonical_digest(stop_decision),
    }

    events: list[dict[str, Any]] = []
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="session_created",
            actor_id="S0.CanonicalRuntime",
            occurred_at=recorded_at,
            output_refs=(session_id,),
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="feedback_issued",
            actor_id="S1.ProductPackReadiness",
            occurred_at=recorded_at,
            input_refs=(readiness_ref,),
            output_refs=feedback_refs,
            feedback_refs=feedback_refs,
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="plan_delta_submitted",
            actor_id="HARNESS::ACTIONABLE-STATE-COMPILER",
            occurred_at=recorded_at,
            input_refs=feedback_refs,
            output_refs=(plan_delta["plan_delta_id"],),
            feedback_refs=feedback_refs,
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="plan_delta_accepted",
            actor_id="S0.PlanDeltaValidator",
            occurred_at=recorded_at,
            input_refs=(plan_delta["plan_delta_id"],),
            output_refs=(accepted_plan_ref,),
            feedback_refs=feedback_refs,
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="graph_delta_submitted",
            actor_id="HARNESS::ACTIONABLE-STATE-COMPILER",
            occurred_at=recorded_at,
            input_refs=feedback_refs,
            output_refs=(graph_delta["graph_delta_id"],),
            feedback_refs=feedback_refs,
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="graph_delta_accepted",
            actor_id="S0.GraphDeltaValidator",
            occurred_at=recorded_at,
            input_refs=(graph_delta["graph_delta_id"],),
            output_refs=(graph_delta["graph_delta_id"],),
            feedback_refs=feedback_refs,
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="stop_decided",
            actor_id="S0.StopDecisionValidator",
            occurred_at=recorded_at,
            input_refs=(accepted_plan_ref,),
            output_refs=(stop_decision["stop_decision_id"],),
            feedback_refs=feedback_refs,
        )
    )
    checkpoint_id = "CHECKPOINT::" + canonical_digest(
        {"session_id": session_id, "plan": accepted_plan_digest}
    )[:24].upper()
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="checkpoint_created",
            actor_id="S0.ContextCheckpoint",
            occurred_at=recorded_at,
            input_refs=(accepted_plan_ref, stop_decision["stop_decision_id"]),
            output_refs=(checkpoint_id,),
            feedback_refs=feedback_refs,
        )
    )
    evidence_refs = sorted(
        str(row.get("evidence_item_digest") or "")
        for row in evidence_items
        if row.get("evidence_item_digest")
    )
    numeric_refs = sorted(
        str(row.get("authority_ref") or "")
        for row in quantitative_authority.get("reported_facts") or ()
        if row.get("authority_ref")
    )
    derived_refs = sorted(
        str(row.get("authority_ref") or "")
        for row in quantitative_authority.get("deterministic_derived_metrics") or ()
        if row.get("authority_ref")
    )
    counterevidence_refs = sorted(
        str(row.get("evidence_item_digest") or "")
        for row in evidence_items
        if "counter" in str(row.get("evidence_role") or "").lower()
        and row.get("evidence_item_digest")
    )
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id=checkpoint_id,
        objective_digest=canonical_digest(
            {"case_key": normalized_case, "objective": "current_research_readiness"}
        ),
        plan_digest=accepted_plan_digest,
        research_graph_digest=graph_delta["base_graph_digest"],
        accepted_evidence_refs=evidence_refs,
        numeric_fact_refs=numeric_refs,
        open_gap_refs=uncertainty_ids,
        unresolved_feedback_refs=feedback_refs,
        agent_local_state_refs=action_ids,
        authority_refs=[*numeric_refs, *derived_refs],
        counterevidence_refs=counterevidence_refs,
        open_question_refs=sorted(
            str(row.get("request_id") or "")
            for row in requests
            if row.get("readiness_state") != "ready_for_current_scope"
        ),
    )
    resume_receipt = resume_agent_session(
        session=session,
        events=events,
        checkpoint=checkpoint,
        expected_case_id=session["case_id"],
        expected_case_version=session["case_version"],
        expected_as_of_date=session["as_of_date"],
        expected_active_plan_ref=accepted_plan_ref,
        resumed_at=recorded_at,
        required_authority_refs=[*numeric_refs, *derived_refs],
        required_open_gap_refs=uncertainty_ids,
        required_unresolved_feedback_refs=feedback_refs,
        required_counterevidence_refs=counterevidence_refs,
        required_open_question_refs=checkpoint["open_question_refs"],
    )
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type="session_resumed",
            actor_id="S0.ContextCheckpoint",
            occurred_at=recorded_at,
            input_refs=(checkpoint_id,),
            output_refs=(resume_receipt["resume_receipt_digest"],),
            feedback_refs=feedback_refs,
        )
    )
    token_basis = _token_budget_basis(
        case_key=normalized_case,
        evidence_items=evidence_items,
        uncertainties=uncertainties,
        actions=actions,
        feedback=feedback,
    )
    unsigned = {
        "schema_version": ACTIONABLE_RESEARCH_STATE_SCHEMA_VERSION,
        "status": "runtime_injected_current_data_replay",
        "case_key": normalized_case,
        "recorded_at": recorded_at,
        "readiness_ref": readiness_ref,
        "source_portfolio_snapshot": source_portfolio,
        "quantitative_authority_ref": quantitative_authority[
            "quantitative_authority_digest"
        ],
        "actionable_uncertainties": uncertainties,
        "research_actions": actions,
        "feedback_receipts": feedback,
        "accepted_plan_delta": plan_delta,
        "accepted_plan": {
            **accepted_plan,
            "plan_digest": accepted_plan_digest,
            "plan_ref": accepted_plan_ref,
        },
        "graph_delta": graph_delta,
        "stop_decision": stop_decision,
        "session": session,
        "session_events": events,
        "context_checkpoint": checkpoint,
        "resume_receipt": resume_receipt,
        "next_natural_node_token_budget_basis": token_basis,
        "summary": {
            "actionable_uncertainty_count": len(uncertainties),
            "research_action_count": len(actions),
            "feedback_receipt_count": len(feedback),
            "current_source_count": source_portfolio["current_source_count"],
            "reported_fact_count": quantitative_authority["summary"][
                "reported_fact_count"
            ],
            "deterministic_derived_metric_count": quantitative_authority[
                "summary"
            ]["deterministic_derived_metric_count"],
            "public_information_gap_authorized_count": 0,
        },
        "authority": {
            "candidate_auto_promotion": False,
            "numeric_fact_authority_remains_with_S2": True,
            "estimate_and_scenario_are_not_fact": True,
            "public_information_gap_authority": False,
            "natural_model_calls": 0,
            "paid_tool_calls": 0,
            "natural_agent_consumption_proven": False,
            "S1_qualification_claimed": False,
            "S3_acceptance_claimed": False,
            "product_publication": False,
        },
    }
    return {**unsigned, "actionable_state_digest": canonical_digest(unsigned)}


__all__ = [
    "ACTIONABLE_RESEARCH_STATE_SCHEMA_VERSION",
    "ACTIONABLE_UNCERTAINTY_SCHEMA_VERSION",
    "RESEARCH_ACTION_SCHEMA_VERSION",
    "TOKEN_BUDGET_BASIS_SCHEMA_VERSION",
    "ActionableResearchStateError",
    "compile_actionable_research_state",
]
