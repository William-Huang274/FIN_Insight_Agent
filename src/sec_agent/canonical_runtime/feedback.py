from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .session import canonical_digest, validate_runtime_artifact


def _receipt(
    *,
    session_id: str,
    source_node_id: str,
    target_node_id: str,
    failure_class: str,
    failure_code: str,
    owning_plane: str,
    owning_stage: str,
    artifact_refs: Sequence[str],
    model_visible_summary: str,
    permitted_next_actions: Sequence[str],
    forbidden_interpretations: Sequence[str],
    created_at: str,
    identity_suffix: str,
) -> dict[str, Any]:
    identity = {
        "session_id": session_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "failure_code": failure_code,
        "artifact_refs": list(artifact_refs),
        "identity_suffix": identity_suffix,
    }
    body = {
        "feedback_id": "FEEDBACK::" + canonical_digest(identity)[:24].upper(),
        "session_id": session_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "failure_class": failure_class,
        "failure_code": failure_code,
        "owning_plane": owning_plane,
        "owning_stage": owning_stage,
        "artifact_refs": list(artifact_refs),
        "model_visible_summary": model_visible_summary,
        "permitted_next_actions": list(permitted_next_actions),
        "forbidden_interpretations": list(forbidden_interpretations),
        "created_at": created_at,
    }
    validated = validate_runtime_artifact("FeedbackReceipt", body)
    return {**validated, "feedback_digest": canonical_digest(validated)}


def compile_s1_feedback_receipts(
    *,
    readiness: Mapping[str, Any],
    session_id: str,
    artifact_ref: str,
    created_at: str,
) -> list[dict[str, Any]]:
    """Turn current S1 readiness failures into bounded, actionable feedback.

    The compiler intentionally consumes summaries and state codes only. Candidate
    text is neither exposed to the model nor promoted to Evidence here.
    """

    case_key = str(readiness.get("case_key") or "").upper()
    requests = list(readiness.get("requests") or ())
    receipts: list[dict[str, Any]] = []
    for raw in requests:
        row = deepcopy(dict(raw))
        state = str(row.get("readiness_state") or "")
        if state == "ready_for_current_scope":
            continue
        request_id = str(row.get("request_id") or "")
        question = str(row.get("business_question_zh") or request_id)
        route = dict(
            row.get("source_route_execution_truth")
            or row.get("route_execution_state")
            or {}
        )
        source_assets = dict(row.get("source_asset_reconciliation") or {})
        pending_admission = [
            str(item)
            for item in row.get("pending_evidence_admission_requirement_ids") or ()
            if str(item)
        ]
        common_forbidden = [
            "不得把未执行、未配置或传输失败的来源路线解释为公开信息不存在",
            "不得把 Candidate、排名或摘要直接解释为 reviewed Evidence",
            "不得用模型记忆补写事实、数字、期间、来源或引用",
        ]
        if state == "blocked_by_candidate_coverage":
            local_source_present = bool(source_assets) and not source_assets.get(
                "official_source_acquisition_required"
            )
            route_required = (
                route.get("source_supplement_route_required") is True
                and not local_source_present
            )
            route_exhausted = (
                route.get("official_or_external_supplement_route_exhausted") is True
            )
            if route_required and not route_exhausted:
                code = "source_route_not_executed_or_not_terminal"
                target = "S1.source_route_executor"
                actions = [
                    "执行当前 requirement 已允许且可用的官方来源路线并先保存原始 capture",
                    "若 exact official route 尚未注册，先注册绑定公司、期间和文档类型的路线",
                    "传输或解析失败时保存 terminal receipt，再返回同一命题的来源状态",
                ]
                summary = (
                    f"{case_key} 的“{question}”候选材料不完整；至少一条所需官方路线尚未形成"
                    "执行终态，因此当前失败属于 S1 来源/工具层，不是模型能力或公开信息边界。"
                )
            else:
                code = (
                    "source_present_candidate_material_requirement_not_recalled"
                    if local_source_present
                    else "candidate_material_requirement_not_recalled"
                )
                target = "S1.query_recall_ranking"
                actions = [
                    "检查对象、期间、来源角色和关系方向硬过滤是否错误排除了候选",
                    "在同一冻结请求下复核 query facets、召回池和 material requirement 覆盖",
                    "若所有合格路线均有终态，再由 GapEligibility 单独裁决边界",
                ]
                summary = (
                    f"{case_key} 的“{question}”仍缺少至少一个材料角色；当前期间的官方来源"
                    "已经存在于本地对象快照，应回查对象化、查询、召回、排序或 Evidence Role，"
                    "不能重复下载同一披露，也不能让模型自行补全。"
                    if local_source_present
                    else f"{case_key} 的“{question}”仍缺少至少一个材料角色；来源路线已无明显"
                    "未执行项，应回查对象、查询、召回或排序，而不是让模型自行补全。"
                )
            receipts.append(
                _receipt(
                    session_id=session_id,
                    source_node_id="S1.ProductPackReadiness",
                    target_node_id=target,
                    failure_class="source_query_recall_or_route_execution_failure",
                    failure_code=code,
                    owning_plane="infrastructure_and_tool_plane",
                    owning_stage="S1",
                    artifact_refs=(artifact_ref, f"request://{request_id}"),
                    model_visible_summary=summary,
                    permitted_next_actions=actions,
                    forbidden_interpretations=common_forbidden,
                    created_at=created_at,
                    identity_suffix=request_id,
                )
            )
        elif state == "blocked_by_evidence_admission":
            receipts.append(
                _receipt(
                    session_id=session_id,
                    source_node_id="S1.ProductPackReadiness",
                    target_node_id="S1.EvidenceGate",
                    failure_class="evidence_authority_and_admission_failure",
                    failure_code="reviewed_evidence_admission_pending",
                    owning_plane="harness_control_plane",
                    owning_stage="S1",
                    artifact_refs=(artifact_ref, f"request://{request_id}"),
                    model_visible_summary=(
                        f"{case_key} 的“{question}”已有候选材料，但至少一个材料角色尚未绑定正式"
                        " Evidence 决策；继续扩大网页搜索不会自动获得证据权威。"
                    ),
                    permitted_next_actions=(
                        "由合格评审者在 source、期间、公司身份、命题和 Evidence Role 绑定下作 accept/reject/needs-review",
                        "复用已经 reviewed 且 exact-object 或同源命题绑定成立的 Evidence",
                        "若候选确实不适合作为 Evidence，保留拒绝并返回真实 residual requirement",
                    ),
                    forbidden_interpretations=(
                        *common_forbidden,
                        "不得因排名靠前、语义相似或包含数字而自动晋升 Evidence",
                        "Evidence admission 失败不得自动触发 broad search",
                    ),
                    created_at=created_at,
                    identity_suffix=request_id,
                )
            )
        elif state == "blocked_by_numeric_or_bridge_authority":
            receipts.append(
                _receipt(
                    session_id=session_id,
                    source_node_id="S1.ProductPackReadiness",
                    target_node_id="S2.NumericFactTool",
                    failure_class="numeric_fact_or_comparable_bridge_authority_failure",
                    failure_code="numeric_fact_or_bridge_unresolved",
                    owning_plane="infrastructure_and_tool_plane",
                    owning_stage="S2",
                    artifact_refs=(artifact_ref, f"request://{request_id}"),
                    model_visible_summary=(
                        f"{case_key} 的“{question}”叙事材料可继续保留，但精确数字或同口径桥尚未由"
                        " S2 解决；文本候选不能替代 SQL/NumericFact 权威。"
                    ),
                    permitted_next_actions=(
                        "用同公司、同期间、同单位、同口径的 typed fact request 重新查询 S2",
                        "若存在权威冲突，保留冲突并请求本地事实裁决",
                    ),
                    forbidden_interpretations=(
                        *common_forbidden,
                        "不得让模型从叙事片段选择或重算权威财务数字",
                    ),
                    created_at=created_at,
                    identity_suffix=request_id,
                )
            )
        elif state == "partial_with_material_gaps":
            receipts.append(
                _receipt(
                    session_id=session_id,
                    source_node_id="S1.ProductPackReadiness",
                    target_node_id="S1.GapEligibilityGate",
                    failure_class="material_gap_without_information_boundary_authority",
                    failure_code="material_gap_not_public_boundary",
                    owning_plane="harness_control_plane",
                    owning_stage="S1",
                    artifact_refs=(artifact_ref, f"request://{request_id}"),
                    model_visible_summary=(
                        f"{case_key} 的“{question}”只能形成部分判断；仍有材料缺口，但当前没有"
                        " GapEligibility 权威证明这是公开信息边界。"
                    ),
                    permitted_next_actions=(
                        "读取 GapEligibilityReceipt 的 blockers 并只处理最早责任层",
                        "若未执行路线仍存在，返回来源执行；若候选存在，返回 Evidence admission",
                    ),
                    forbidden_interpretations=common_forbidden,
                    created_at=created_at,
                    identity_suffix=request_id,
                )
            )
        else:
            owner = (
                "infrastructure_and_tool_plane"
                if state
                in {
                    "blocked_by_local_data_materialization",
                    "blocked_by_retrieval_quality",
                    "blocked_by_source_access",
                }
                else "harness_control_plane"
            )
            receipts.append(
                _receipt(
                    session_id=session_id,
                    source_node_id="S1.ProductPackReadiness",
                    target_node_id="S1.earliest_responsible_layer",
                    failure_class="s1_readiness_failure",
                    failure_code=state or "s1_readiness_state_missing",
                    owning_plane=owner,
                    owning_stage="S1",
                    artifact_refs=(artifact_ref, f"request://{request_id}"),
                    model_visible_summary=(
                        f"{case_key} 的“{question}”未达到当前任务就绪，状态为 {state or 'unknown'}；"
                        "必须先由 S1 本地工具或控制面给出明确处置。"
                    ),
                    permitted_next_actions=(
                        "读取该请求的 typed readiness、route 和 decision receipts",
                        "只修复最早拥有责任的 S1 层",
                    ),
                    forbidden_interpretations=common_forbidden,
                    created_at=created_at,
                    identity_suffix=request_id,
                )
            )
        if pending_admission and state != "blocked_by_evidence_admission":
            receipts.append(
                _receipt(
                    session_id=session_id,
                    source_node_id="S1.ProductPackReadiness",
                    target_node_id="S1.EvidenceGate",
                    failure_class="evidence_authority_and_admission_failure",
                    failure_code="reviewed_evidence_admission_pending_alongside_other_blocker",
                    owning_plane="harness_control_plane",
                    owning_stage="S1",
                    artifact_refs=(
                        artifact_ref,
                        f"request://{request_id}",
                        *(f"requirement://{item}" for item in pending_admission),
                    ),
                    model_visible_summary=(
                        f"{case_key} 的“{question}”除当前主阻断外，还有 {len(pending_admission)} 条"
                        "材料命题已有候选但未完成 Evidence admission；这些候选不得因另一个缺口"
                        "存在而被遗漏或自动晋升。"
                    ),
                    permitted_next_actions=(
                        "由合格评审者逐个检查候选—命题—来源—期间—Evidence Role 绑定",
                        "保存 accept/reject/needs-review 的 digest-bound receipt",
                    ),
                    forbidden_interpretations=(
                        *common_forbidden,
                        "不得把混合阻断压缩成单一来源问题",
                    ),
                    created_at=created_at,
                    identity_suffix=f"{request_id}:parallel-admission",
                )
            )
    return receipts


def compile_s2_feedback_receipt(
    *,
    result: Mapping[str, Any],
    session_id: str,
    source_node_id: str,
    artifact_ref: str,
    created_at: str,
) -> dict[str, Any] | None:
    status = str(result.get("status") or "")
    if status == "resolved":
        return None
    request_id = str(result.get("fact_request_id") or "")
    ticker = str(result.get("ticker") or "").upper()
    metric = str(result.get("metric_id") or "")
    if status == "typed_conflict":
        detail = dict(result.get("typed_conflict") or {})
        code = str(detail.get("conflict_code") or "authoritative_numeric_fact_conflict")
        summary = (
            f"{ticker} 的 {metric} 存在多个无法自动合并的权威数值/期间候选；"
            "模型不得自行挑选一个数字继续写作。"
        )
        actions = (
            "核对来源 accession、期间角色、单位、财年口径和 supersession",
            "由 S2 本地事实权威裁决或保留 typed conflict",
        )
    else:
        detail = dict(result.get("typed_gap") or {})
        code = str(detail.get("gap_code") or "typed_fact_gap_unclassified")
        summary = (
            f"{ticker} 的 {metric} 未从当前 S2 mart 按请求期间和口径解析出来；"
            "该状态只证明 typed lookup 未解决，不证明公开信息不存在。"
        )
        actions = (
            "检查 SQL mart、对象化、公司身份、期间、单位和来源绑定",
            "必要时请求已授权的官方来源路线并重新物化事实观察",
            "只有独立 GapEligibilityReceipt 通过后才可声明信息边界",
        )
    return _receipt(
        session_id=session_id,
        source_node_id=source_node_id,
        target_node_id="S2.NumericFactAuthority",
        failure_class="numeric_fact_lookup_or_authority_failure",
        failure_code=code,
        owning_plane="infrastructure_and_tool_plane",
        owning_stage="S2",
        artifact_refs=(artifact_ref, f"fact-request://{request_id}"),
        model_visible_summary=summary,
        permitted_next_actions=actions,
        forbidden_interpretations=(
            "不得用模型记忆、文本片段或其他公司的数字补空",
            "不得把 typed gap 自动解释为公开信息边界",
            "不得在冲突未关闭时选择更符合叙事的数字",
        ),
        created_at=created_at,
        identity_suffix=request_id,
    )


def compile_verifier_feedback_receipts(
    *,
    findings: Sequence[Mapping[str, Any]],
    session_id: str,
    source_node_id: str,
    artifact_ref: str,
    created_at: str,
) -> list[dict[str, Any]]:
    receipts = []
    harness_codes = {
        "identity_mismatch",
        "period_mismatch",
        "unit_mismatch",
        "source_lineage_invalid",
        "citation_ref_invalid",
        "schema_contract_invalid",
    }
    skill_graph_codes = {
        "wrong_skill_scope",
        "stale_method_pack",
        "unsupported_graph_edge",
    }
    for index, raw in enumerate(findings):
        finding = deepcopy(dict(raw))
        code = str(
            finding.get("finding_code")
            or finding.get("failure_code")
            or finding.get("issue_id")
            or "verifier_finding_unclassified"
        )
        if code in harness_codes:
            plane = "harness_control_plane"
            target = "Harness.contract_or_lineage_owner"
            actions = (
                "提交只修改身份、期间、单位、引用或 schema 绑定的有界修正",
                "保留失败输出和原始 capture，不改写事实权威",
            )
        elif code in skill_graph_codes:
            plane = "skill_graph_overlap_plane"
            target = "S3.skill_graph_selector"
            actions = (
                "请求与当前角色、命题、缺口和计划匹配的最小 Skill/Graph pack",
                "若需新增关系，只提交带 Evidence refs 的 GraphDelta",
            )
        else:
            plane = "agent_work_mode_plane"
            target = str(finding.get("target_node_id") or "S3.originating_research_node")
            actions = (
                "重新读取当前 CaseTruth、reviewed Evidence、NumericFact 和 typed gaps",
                "修正受影响判断；若证据确实不足，再提交有界 EvidenceRequest 或 PlanDelta",
                "只重裁决受影响单元，不重跑无关节点",
            )
        explicit_actions = finding.get("permitted_next_actions")
        if explicit_actions is not None:
            actions = tuple(
                str(value).strip()
                for value in explicit_actions
                if str(value).strip()
            )
            if not actions:
                raise ValueError("verifier_feedback_actions_empty")
        alias = str(finding.get("truth_alias") or "")
        surface = str(finding.get("claim_surface_id") or finding.get("location") or "")
        location = " / ".join(part for part in (surface, alias) if part)
        explicit_summary = str(finding.get("model_visible_summary") or "").strip()
        if explicit_summary:
            summary = explicit_summary
        else:
            summary = f"Verifier 拒绝当前判断：{code}"
            if location:
                summary += f"（{location}）"
            summary += "。该失败必须回到最早责任节点，Verifier 不会代写结论。"
        explicit_forbidden = finding.get("forbidden_interpretations")
        forbidden = (
            tuple(
                str(value).strip()
                for value in explicit_forbidden
                if str(value).strip()
            )
            if explicit_forbidden is not None
            else (
                "不得忽略已审 Evidence 或把 cell-local 不可见升级为 case-level 不存在",
                "不得让 Verifier 或 Harness 补写研究观点",
                "不得把失败 attempt 重新标注为成功",
            )
        )
        if not forbidden:
            raise ValueError("verifier_feedback_forbidden_empty")
        receipts.append(
            _receipt(
                session_id=session_id,
                source_node_id=source_node_id,
                target_node_id=target,
                failure_class="verifier_rejected_research_or_contract_output",
                failure_code=code,
                owning_plane=plane,
                owning_stage="S3",
                artifact_refs=(artifact_ref,),
                model_visible_summary=summary,
                permitted_next_actions=actions,
                forbidden_interpretations=forbidden,
                created_at=created_at,
                identity_suffix=f"{index}:{code}:{location}",
            )
        )
    return receipts


__all__ = [
    "compile_s1_feedback_receipts",
    "compile_s2_feedback_receipt",
    "compile_verifier_feedback_receipts",
]
