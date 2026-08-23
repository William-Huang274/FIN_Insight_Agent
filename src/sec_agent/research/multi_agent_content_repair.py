from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime import canonical_digest


CONTENT_ASSESSMENT_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_content_assessment_v1_0"
)


class MultiAgentContentRepairError(ValueError):
    """Fail-closed error for independent multi-agent content repair inputs."""


def expected_content_repair_budget() -> dict[str, int]:
    """Exact shared budget for five role repairs and one Lead review."""

    return {
        "maximum_new_model_calls": 12,
        "maximum_new_transport_attempts": 12,
        "role_repair_drafts": 5,
        "role_repair_submissions": 5,
        "lead_coordination_drafts": 1,
        "lead_coordination_submissions": 1,
        "maximum_role_repairs": 5,
        "maximum_lead_rounds": 1,
        "maximum_new_s1_s2_requests": 0,
        "maximum_new_retrieval_rounds": 0,
        "maximum_external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def expected_content_repair_submission_resume_budget() -> dict[str, int]:
    """Exact R8 ceiling after two repairs and one natural draft are reusable."""

    return {
        "maximum_new_model_calls": 7,
        "maximum_new_transport_attempts": 7,
        "demand_repair_submissions": 1,
        "remaining_role_repair_drafts": 2,
        "remaining_role_repair_submissions": 2,
        "lead_coordination_drafts": 1,
        "lead_coordination_submissions": 1,
        "maximum_new_role_repairs": 3,
        "maximum_lead_rounds": 1,
        "maximum_new_s1_s2_requests": 0,
        "maximum_new_retrieval_rounds": 0,
        "maximum_external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MultiAgentContentRepairError(code)


COMMON_SEMANTIC_RELATION_RULES: tuple[str, ...] = (
    "同一期间出现的订单、收入、利润或现金只证明共现；没有 cohort、转化率或因果关系卡时不得写成已完成转化或因果贡献。",
    "贡献桥必须保留正负方向和百分点：正贡献、负贡献与净变化不得用未经确定性关系卡支持的百分比份额替代。",
    "来源所有者、研究主体和关系方向必须分开；相关公司的客户结构、政策风险或库存不能自动变成本案公司的结构或暴露。",
)


ROLE_SEMANTIC_RELATION_RULES: dict[str, tuple[str, ...]] = {
    "AGENT::DEMAND_QUALITY": (
        "保供、提前锁量或更长采购期只支持可能的 pull-forward；没有规模、订单 cohort 或后续消化证据时不得写成已发生或必然发生的消化。",
        "仅纳入公司认定不可取消订单通常提高 backlog 的取消质量；公司判断、账龄和实际兑现仍可作为单独限制，但不得混为同一弱点。",
    ),
    "AGENT::OPERATING_PERFORMANCE": (
        "经营利润率桥按 毛利率贡献减费用率贡献 表达；费用率下降可为唯一正贡献，但不得把其正百分点错误写成净改善的约百分之百。",
        "同季订单与确认收入不是同一订单 cohort 的转化证据；只有显式 cohort、交付或转化率关系才能支持转换判断。",
    ),
    "AGENT::VALUE_CAPTURE": (
        "公司毛利率是价格、数量、产品组合与成本的净结果，不能单独证明或证伪某产品定价能力；产品级价格、成本、单位与组合桥仍是必要输入。",
        "公司或分部经营杠杆不授予 AI 产品利润权威；贡献桥必须写出毛利与费用的相反方向，而不是模糊贡献比例。",
    ),
    "AGENT::CASH_CONVERSION": (
        "应收、库存和应付的期末余额变化只是资产负债表营运资金代理；没有现金流调节表时不得把代理变化写成精确现金吸收或释放。",
        "公司现金流与营运资金代理均不得自动归因于 AI 产品、客户或 GPU 预付款。",
    ),
    "AGENT::SUPPLY_RELATIONSHIP": (
        "上游产能或瓶颈只能形成来源所有者范围内的事实和对本案的有界情景；没有直接点名、分配或交付关系时不得升级为本案暴露。",
    ),
    "AGENT::COUNTEREVIDENCE": (
        "发行人直接反证与相关公司 read-through 必须分开；两个公司各自存在集中度不证明客户结构同构或同一交易对手重合。",
        "相关公司的出口管制、库存或客户结构只能形成本案情景；没有地区、产品、订单或关系映射时不得称为本案已证实暴露。",
    ),
}


def semantic_relation_rules(agent_id: str) -> list[str]:
    _require(
        agent_id in ROLE_SEMANTIC_RELATION_RULES,
        "multi_agent_content_repair_agent_unknown",
    )
    return [
        *COMMON_SEMANTIC_RELATION_RULES,
        *ROLE_SEMANTIC_RELATION_RULES[agent_id],
    ]


def rebind_workpaper_context_semantic_rules(
    context: Mapping[str, Any], *, expected_agent_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Migrate one immutable model context to the current semantic rules.

    The migration changes instructions only. Evidence, numeric, relation, gap,
    graph, reflection and case authority remain byte-for-byte identical.
    """

    source = deepcopy(dict(context))
    source_digest = str(source.pop("context_digest", ""))
    _require(
        bool(source_digest)
        and source_digest == canonical_digest(source)
        and str(source.get("agent", {}).get("agent_id") or "")
        == expected_agent_id,
        "multi_agent_content_repair_context_invalid",
    )
    prior_rules = [str(row) for row in source.get("rules") or ()]
    additions = [
        row
        for row in semantic_relation_rules(expected_agent_id)
        if row not in prior_rules
    ]
    source["rules"] = [*prior_rules, *additions]
    rebound = {**source, "context_digest": canonical_digest(source)}
    receipt_body = {
        "schema_version": "fin_ia_workpaper_semantic_rule_migration_receipt_v1_0",
        "agent_id": expected_agent_id,
        "source_context_digest": source_digest,
        "rebound_context_digest": rebound["context_digest"],
        "added_rules": additions,
        "evidence_numeric_relation_gap_graph_and_case_authority_changed": False,
        "model_judgment_changed": False,
    }
    return rebound, {
        **receipt_body,
        "receipt_digest": canonical_digest(receipt_body),
    }


def compile_independent_content_challenges(
    *,
    assessment: Mapping[str, Any],
    workpapers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert one independent assessment into role-local repair challenges."""

    _require(
        assessment.get("schema_version") == CONTENT_ASSESSMENT_SCHEMA_VERSION
        and assessment.get("case_key") == "DELL"
        and assessment.get("status")
        == "dynamic_multi_agent_contract_pass_financial_truth_and_evidence_authority_fail_writer_not_eligible",
        "multi_agent_content_repair_assessment_invalid",
    )
    by_agent = {
        str(row.get("agent_id") or ""): deepcopy(dict(row))
        for row in workpapers
    }
    findings = [
        deepcopy(dict(row))
        for row in assessment.get("material_findings") or ()
    ]
    issue_ids = [str(row.get("issue_id") or "") for row in findings]
    _require(
        len(findings) == 7
        and all(issue_ids)
        and len(issue_ids) == len(set(issue_ids)),
        "multi_agent_content_repair_findings_invalid",
    )
    challenges: list[dict[str, Any]] = []
    for finding in findings:
        target = str(finding.get("target_agent_id") or "")
        workpaper = by_agent.get(target)
        _require(
            workpaper is not None
            and target != "AGENT::SUPPLY_RELATIONSHIP"
            and str(workpaper.get("workpaper_digest") or ""),
            "multi_agent_content_repair_target_invalid",
        )
        body = {
            "source_agent_id": "S3.INDEPENDENT_CONTENT_VERIFIER",
            "target_agent_id": target,
            "source_workpaper_digest": str(workpaper["workpaper_digest"]),
            "challenge": (
                "独立内容验收拒绝当前判断。问题："
                + str(finding.get("finding") or "")
                + " 必须恢复的边界："
                + str(finding.get("required_boundary") or "")
            ),
            "material_reason": str(finding.get("business_impact") or ""),
            "requested_action": "repair_independent_financial_truth_finding",
            "assessment_issue_id": str(finding["issue_id"]),
            "affected_surfaces": [
                str(row) for row in finding.get("locations") or ()
            ],
        }
        challenge_id = "CHALLENGE::" + canonical_digest(body)[:24].upper()
        challenges.append({"challenge_id": challenge_id, **body})
    _require(
        {row["target_agent_id"] for row in challenges}
        == {
            "AGENT::DEMAND_QUALITY",
            "AGENT::OPERATING_PERFORMANCE",
            "AGENT::VALUE_CAPTURE",
            "AGENT::CASH_CONVERSION",
            "AGENT::COUNTEREVIDENCE",
        },
        "multi_agent_content_repair_target_set_invalid",
    )
    return challenges


__all__ = [
    "COMMON_SEMANTIC_RELATION_RULES",
    "CONTENT_ASSESSMENT_SCHEMA_VERSION",
    "MultiAgentContentRepairError",
    "ROLE_SEMANTIC_RELATION_RULES",
    "compile_independent_content_challenges",
    "expected_content_repair_budget",
    "rebind_workpaper_context_semantic_rules",
    "semantic_relation_rules",
]
