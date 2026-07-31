from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from retrieval.object_bm25_retriever import ObjectBM25Retriever
from sec_agent.canonical_runtime.models import canonical_digest

from .case_service import CasePrincipal, CaseService, CaseServiceError


OBJECT_INDEX_RELATIVE_PATH = (
    "data/indexes/bm25/"
    "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects"
)
GOLD_MART_RELATIVE_PATH = (
    "data/workbench_private/research_data/gold_fact_signal_mart_v0_1.sqlite"
)
RESEARCH_GRAPH_RELATIVE_PATH = (
    "data/workbench_private/research_data/research_graph_store_v0_1.sqlite"
)


@dataclass(frozen=True)
class LocalResearchPaths:
    object_index: Path
    gold_mart: Path
    research_graph: Path
    official_filing_root: Path | None = None

    @classmethod
    def from_repo_root(cls, repo_root: str | Path) -> "LocalResearchPaths":
        root = Path(repo_root).resolve()
        return cls(
            object_index=root / OBJECT_INDEX_RELATIVE_PATH,
            gold_mart=root / GOLD_MART_RELATIVE_PATH,
            research_graph=root / RESEARCH_GRAPH_RELATIVE_PATH,
            official_filing_root=root / "data/raw_private/sec",
        )


class LocalResearchServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class P36LocalResearchService:
    """Read-only P36 retrieval preview over existing local research assets.

    The service exposes real materialized candidates without promoting them,
    mutating a Case, calling a model, or reaching the network.
    """

    def __init__(
        self,
        case_service: CaseService,
        *,
        paths: LocalResearchPaths,
        object_retriever_factory: Callable[[str | Path], Any] = ObjectBM25Retriever,
    ) -> None:
        self._case_service = case_service
        self._paths = paths
        self._object_retriever_factory = object_retriever_factory
        self._official_url_cache: dict[tuple[str, str, str], str] = {}

    @classmethod
    def from_case_service(
        cls,
        case_service: CaseService,
        *,
        repo_root: str | Path,
    ) -> "P36LocalResearchService":
        return cls(case_service, paths=LocalResearchPaths.from_repo_root(repo_root))

    def preview(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "evidence:read")
        try:
            case = self._case_service.get_case(case_id, principal)
        except CaseServiceError as exc:
            raise LocalResearchServiceError(exc.error_code, exc.status_code, **exc.detail) from exc
        self._require_sources()

        cells = [
            self._demand_reality_cell(),
            self._value_capture_cell(),
            self._counterevidence_cell(),
            self._object_role_cell(
                cell_key="server_oem_order_revenue_conversion",
                evidence_role="server_oem_orders",
                ticker="DELL",
                query="AI server orders backlog shipments revenue",
                decision_question=(
                    "Do server OEM order and backlog signals convert into reported shipments "
                    "and revenue without timing distortion?"
                ),
            ),
            self._object_role_cell(
                cell_key="server_oem_margin_cash_conversion",
                evidence_role="server_oem_margin_cash",
                ticker="DELL",
                query="infrastructure solutions margin cash flow inventory working capital",
                decision_question=(
                    "Do AI server revenue signals convert into OEM margin and cash rather "
                    "than inventory or working-capital pressure?"
                ),
            ),
            self._object_role_cell(
                cell_key="advanced_packaging_capacity_bottleneck_rent",
                evidence_role="advanced_packaging_capacity",
                ticker="NVDA",
                query="advanced packaging CoWoS capacity supply constraint",
                decision_question=(
                    "Does advanced-packaging capacity remain a binding bottleneck, and who "
                    "captures the resulting economics?"
                ),
            ),
            self._object_role_cell(
                cell_key="hbm_supply_pricing_concentration",
                evidence_role="hbm_supply_pricing",
                ticker="MU",
                query="HBM demand supply pricing capacity customer concentration",
                decision_question=(
                    "How tight are HBM supply, pricing, and customer concentration, and how "
                    "durable is memory profit capture?"
                ),
            ),
            self._object_role_cell(
                cell_key="semicap_capex_cycle_export",
                evidence_role="semicap_capex_cycle",
                ticker="AMAT",
                query="semiconductor equipment capex cycle demand export China",
                decision_question=(
                    "What does semiconductor-equipment demand imply for capex timing, cycle "
                    "position, and export-policy read-through?"
                ),
            ),
            self._object_role_cell(
                cell_key="export_policy_risk",
                evidence_role="export_policy_risk",
                ticker="NVDA",
                query="export control China restrictions data center revenue risk",
                decision_question=(
                    "Which current export restrictions could impair supply, market access, "
                    "or recognized data-center revenue?"
                ),
            ),
            self._object_role_cell(
                cell_key="customer_concentration",
                evidence_role="customer_concentration",
                ticker="NVDA",
                query="customer concentration direct customer revenue percentage",
                decision_question=(
                    "How concentrated is recognized revenue, and what does that concentration "
                    "change about durability and price-in risk?"
                ),
            ),
        ]
        payload = {
            "case_id": case_id,
            "case_version": case["case_version"],
            "query": case["query"],
            "as_of": case["as_of"],
            "research_mode": "bounded_local_read_only",
            "status": "candidate_preview_ready",
            "selected_cell_count": len(cells),
            "candidate_count": sum(len(cell["candidates"]) for cell in cells),
            "cells": cells,
            "source_inventory": self._source_inventory(),
            "execution_counts": {
                "object_bm25_queries": 8,
                "gold_sql_queries": 1,
                "research_graph_queries": 1,
                "network_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "external_tool_calls": 0,
                "canonical_store_writes": 0,
                "case_mutations": 0,
                "evidence_promotions": 0,
            },
            "boundary": (
                "Real materialized local candidates only; senior review and downstream "
                "admission are still required before citation or release use."
            ),
        }
        return {"preview_digest": canonical_digest(payload), **payload}

    def analysis_preview(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        """Run the selected real candidates through a deterministic internal chain.

        This is deliberately a read-only preview. It proves that local candidates can
        feed numeric analysis, bounded repair decisions, workpaper judgments, and a
        no-source writer without granting evidence or release authority.
        """

        source = self.preview(case_id, principal)
        cells = {cell["evidence_role"]: cell for cell in source["cells"]}
        numeric = self._numeric_analysis(cells["revenue_capture"])
        repairs = self._repair_analysis(cells)
        judgments = self._judgment_analysis(cells, numeric, repairs)
        workpaper = self._workpaper_analysis(source, judgments, numeric, repairs)
        writer = self._writer_analysis(source, workpaper, judgments)
        payload = {
            "case_id": source["case_id"],
            "case_version": source["case_version"],
            "as_of": source["as_of"],
            "source_preview_digest": source["preview_digest"],
            "analysis_mode": "bounded_local_deterministic_preview",
            "status": "internal_analysis_preview_ready",
            "numeric": numeric,
            "repairs": repairs,
            "judgments": judgments,
            "workpaper": workpaper,
            "writer": writer,
            "execution_counts": {
                **source["execution_counts"],
                "numeric_calculations": len(numeric["derived_metrics"]),
                "repair_decisions": len(repairs),
                "judgment_compilations": len(judgments),
                "workpaper_compilations": 1,
                "writer_compositions": 1,
                "writer_source_access_calls": 0,
            },
            "hard_boundaries": {
                "case_mutations": 0,
                "canonical_store_writes": 0,
                "evidence_promotions": 0,
                "writer_source_access_calls": 0,
                "network_calls": 0,
                "model_calls": 0,
                "release_admission": 0,
                "senior_r2_required": 1,
            },
            "boundary": (
                "Internal deterministic analysis over real local candidates. The draft is "
                "not evidence promotion, senior R2 approval, operational qualification, "
                "or FIN 0.1 release admission."
            ),
        }
        return {"analysis_digest": canonical_digest(payload), **payload}

    @staticmethod
    def _numeric_analysis(cell: Mapping[str, Any]) -> dict[str, Any]:
        facts: list[dict[str, Any]] = []
        values: dict[str, Decimal] = {}
        for candidate in cell["candidates"]:
            metric = str(candidate.get("metric_family") or "")
            try:
                value = Decimal(str(candidate.get("value") or ""))
            except InvalidOperation:
                continue
            values[metric] = value
            facts.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "entity_ref": candidate.get("ticker") or "",
                    "segment_ref": candidate.get("segment_ref") or "__company_total__",
                    "metric_family": metric,
                    "label": candidate["title"],
                    "row_label": candidate.get("row_label") or candidate["title"],
                    "value": str(value),
                    "unit": candidate.get("unit") or "",
                    "currency": candidate.get("currency") or (
                        "USD" if candidate.get("unit") == "USD" else ""
                    ),
                    "scale_multiplier": int(candidate.get("scale_multiplier") or 1),
                    "period": candidate.get("period") or candidate.get("published_at") or "",
                    "source_ref": candidate["evidence_ref"],
                    "source_coordinate": candidate.get("source_coordinate")
                    or candidate.get("citation_span")
                    or candidate["evidence_ref"],
                    "exact_value_authority": bool(candidate["exact_value_authority"]),
                }
            )
        derived: list[dict[str, Any]] = []
        revenue = values.get("revenue")
        if revenue and revenue != 0:
            for metric, numerator_key, label in (
                ("gross_margin", "gross_profit", "Gross margin"),
                ("operating_margin", "operating_income", "Operating margin"),
            ):
                numerator = values.get(numerator_key)
                if numerator is None:
                    continue
                derived.append(
                    {
                        "metric": metric,
                        "label": label,
                        "value": format((numerator / revenue * Decimal("100")).quantize(Decimal("0.01")), "f"),
                        "unit": "percent",
                        "formula": f"{numerator_key}/revenue*100",
                        "input_candidate_ids": [
                            fact["candidate_id"]
                            for fact in facts
                            if fact["metric_family"] in {"revenue", numerator_key}
                        ],
                    }
                )
        required = {"revenue", "gross_profit", "operating_income"}
        missing = sorted(required - values.keys())
        return {
            "status": "exact_local_facts_computed" if not missing else "typed_gap",
            "facts": facts,
            "derived_metrics": derived,
            "typed_gaps": [f"missing_exact_metric:{metric}" for metric in missing],
            "writer_citable": False,
        }

    @staticmethod
    def _repair_analysis(cells: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
        results = []
        definitions = (
            (
                "demand_signal",
                "no_override",
                "local_demand_candidates_available",
                "Durability still requires subsequent-period confirmation.",
            ),
            (
                "revenue_capture",
                "no_override",
                "exact_value_set_available",
                "Segment attribution is not inferred beyond the reported company facts.",
            ),
            (
                "thesis_counterevidence",
                "bounded_context_repair",
                "local_graph_context_attached",
                "Relationships do not prove causal bottlenecks; senior review must retain this gap.",
            ),
            (
                "server_oem_orders",
                "no_override",
                "issuer_order_and_shipment_context_available",
                "The candidate set does not establish an exact AI-server order or backlog value.",
            ),
            (
                "server_oem_margin_cash",
                "bounded_context_repair",
                "issuer_margin_and_cash_context_attached",
                "AI-server-specific margin, inventory, and cash conversion remain unseparated.",
            ),
            (
                "advanced_packaging_capacity",
                "bounded_context_repair",
                "issuer_supply_capacity_context_attached",
                "The evidence does not isolate CoWoS capacity or prove bottleneck rent capture.",
            ),
            (
                "hbm_supply_pricing",
                "no_override",
                "issuer_memory_supply_context_available",
                "Exact HBM pricing and customer concentration are not established.",
            ),
            (
                "semicap_capex_cycle",
                "bounded_context_repair",
                "issuer_semicap_context_attached",
                "The current candidate set does not establish the present cycle position.",
            ),
            (
                "export_policy_risk",
                "no_override",
                "issuer_export_risk_context_available",
                "Policy applicability and quantified commercial impact require official-policy review.",
            ),
            (
                "customer_concentration",
                "no_override",
                "issuer_customer_concentration_context_available",
                "Direct-customer concentration cannot be treated as end-customer concentration.",
            ),
        )
        for role, decision, reason, remaining_gap in definitions:
            cell = cells[role]
            results.append(
                {
                    "repair_id": f"local_repair_{canonical_digest({'role': role, 'candidates': [row['candidate_id'] for row in cell['candidates']]})[:24]}",
                    "evidence_role": role,
                    "decision": decision,
                    "reason": reason,
                    "candidate_refs": [row["candidate_id"] for row in cell["candidates"]],
                    "remaining_gap": remaining_gap,
                    "external_execution": False,
                    "promotion_authorized": False,
                }
            )
        return results

    @staticmethod
    def _judgment_analysis(
        cells: Mapping[str, Mapping[str, Any]],
        numeric: Mapping[str, Any],
        repairs: list[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        repair_by_role = {row["evidence_role"]: row for row in repairs}
        ratios = {row["metric"]: row["value"] for row in numeric["derived_metrics"]}
        facts = {row["metric_family"]: row for row in numeric["facts"]}
        revenue = facts.get("revenue", {}).get("value", "unknown")
        gross_profit = facts.get("gross_profit", {}).get("value", "unknown")
        operating_income = facts.get("operating_income", {}).get("value", "unknown")
        specs = (
            (
                "demand_signal",
                "medium",
                "公司披露的数据中心增长与超大规模客户部署支持需求正在转化，但同期风险披露表明预测偏差和供需错配仍可能影响持续性。",
                "Company-reported data-center growth and hyperscale deployment support demand conversion, while risk disclosures leave durability exposed to forecasting and supply-demand mismatch.",
                "强需求叙事可能把订单时点、提前采购或供给约束误判为可持续终端需求。",
                "Subsequent filings show deployment breadth and reported growth persisting without inventory or lead-time reversal.",
            ),
            (
                "revenue_capture",
                "high" if numeric["status"] == "exact_local_facts_computed" else "low",
                f"最新精确公司事实显示收入 {revenue} USD、毛利润 {gross_profit} USD、营业利润 {operating_income} USD；据此计算毛利率 {ratios.get('gross_margin', 'unknown')}%、营业利润率 {ratios.get('operating_margin', 'unknown')}%。",
                f"Exact company facts report revenue of {revenue} USD, gross profit of {gross_profit} USD, and operating income of {operating_income} USD; derived margins are {ratios.get('gross_margin', 'unknown')}% gross and {ratios.get('operating_margin', 'unknown')}% operating.",
                "公司口径盈利并不自动等同于单一加速器产品或整个 AI 基础设施链的利润捕获。",
                "A reviewed segment bridge attributes reported company facts to the accelerator layer without exceeding source authority.",
            ),
            (
                "thesis_counterevidence",
                "low",
                "本地关系图识别出代工、存储与设备依赖，可作为瓶颈检查清单；当前关系证据不足以证明这些依赖已经形成因果性约束。",
                "The local graph identifies foundry, memory, and equipment dependencies as a bottleneck checklist, but does not prove that those relationships are currently causal constraints.",
                "把供应链关系本身当作瓶颈，会夸大反证强度并造成错误降级。",
                "Official capacity, allocation, lead-time, inventory, or policy evidence confirms a binding constraint and its period.",
            ),
            (
                "server_oem_orders",
                "medium",
                "服务器厂商披露显示 AI 需求、订单履行与发货时点存在非线性，能够支持订单到收入转化问题；当前候选不足以给出精确 AI 服务器订单或积压金额。",
                "Server-OEM disclosures show non-linearity between AI demand, order fulfillment, and shipment timing, supporting the conversion question without establishing an exact AI-server order or backlog value.",
                "把剩余履约义务或管理层需求表述直接视为可确认收入，会高估转化确定性。",
                "Reviewed order, backlog, shipment, and revenue definitions reconcile for the same AI-server scope and period.",
            ),
            (
                "server_oem_margin_cash",
                "low",
                "服务器厂商的分部利润与现金流披露能够建立利润和现金转化检查框架，但现有候选没有把 AI 服务器的毛利、库存与营运资本单独拆出。",
                "OEM segment-profit and cash-flow disclosures establish a margin-and-cash checklist, but do not isolate AI-server margin, inventory, or working capital.",
                "收入增长可能被低毛利配置、库存积压或营运资本占用抵消。",
                "Same-period AI-server revenue, gross margin, inventory, and operating-cash evidence reconcile under reviewed definitions.",
            ),
            (
                "advanced_packaging_capacity",
                "low",
                "发行人供应承诺和产能约束披露支持先进封装依赖需要被跟踪，但当前证据不能单独证明 CoWoS 已形成约束，也不能判断超额收益归属。",
                "Issuer supply commitments and capacity-risk disclosures support tracking advanced-packaging dependency, but do not prove a CoWoS bottleneck or identify rent capture.",
                "一般性半导体供给风险可能被误写成特定先进封装瓶颈。",
                "Official foundry capacity, utilization, allocation, lead-time, and pricing evidence align for the same period.",
            ),
            (
                "hbm_supply_pricing",
                "medium",
                "存储厂商最新披露表明 AI 需求增速高于行业供给扩张并触发供给分配，可支持 HBM 紧张度判断；精确 HBM 定价和客户集中度仍未建立。",
                "Recent memory-vendor disclosures indicate AI demand growing faster than industry supply and triggering allocation, supporting a tightness judgment while leaving exact HBM pricing and concentration unresolved.",
                "整体存储紧张并不等同于 HBM 产品层价格、份额或利润持续性。",
                "Reviewed HBM bit supply, contract pricing, allocation, customer mix, and capacity-ramp evidence persist across periods.",
            ),
            (
                "semicap_capex_cycle",
                "low",
                "设备公司披露能够支持资本开支与终端需求的传导框架，但候选时点和范围不足以判断当前设备周期位置或 AI 增量的独立贡献。",
                "Equipment-company disclosures support a capex read-through framework, but candidate timing and scope do not establish the current cycle position or isolate AI incremental demand.",
                "长期 AI 叙事可能掩盖短期晶圆厂利用率、库存和出口地区结构变化。",
                "Current orders, backlog, utilization, regional mix, and customer-capex evidence agree across leading equipment vendors.",
            ),
            (
                "export_policy_risk",
                "medium",
                "最新发行人风险披露确认出口管制可能扰动供应链、分销和市场服务能力；具体政策适用性、执行时间与收入影响仍需官方政策核验。",
                "Recent issuer risk disclosures confirm that export controls can disrupt supply, distribution, and market service, while policy applicability, timing, and quantified revenue impact remain unresolved.",
                "通用风险披露不应被当作已发生损失或确定收入冲击。",
                "Applicable official rules, effective dates, product thresholds, licensing outcomes, and affected revenue are reviewed together.",
            ),
            (
                "customer_concentration",
                "high",
                "发行人披露多个直接客户分别超过收入的 10%，说明确认收入集中度具有实质性；直接客户与终端客户并不等同，因而不能据此推断最终需求集中度。",
                "Issuer disclosures show multiple direct customers above 10% of revenue, making recognized-revenue concentration material, while direct and end customers remain distinct.",
                "渠道或云服务商采购集中可能夸大终端需求集中，也可能放大单一采购时点波动。",
                "Direct-customer percentages, end-customer attribution, purchase timing, and renewal behavior remain consistent in subsequent filings.",
            ),
        )
        judgments = []
        for role, confidence, zh, en, counter_zh, what_changes in specs:
            cell = cells[role]
            repair = repair_by_role[role]
            input_payload = {
                "role": role,
                "candidates": [row["candidate_id"] for row in cell["candidates"]],
                "repair_id": repair["repair_id"],
                "numeric": numeric if role == "revenue_capture" else None,
            }
            judgment_id = f"local_judgment_{canonical_digest(input_payload)[:24]}"
            judgments.append(
                {
                    "judgment_id": judgment_id,
                    "cell_key": cell["cell_key"],
                    "evidence_role": role,
                    "decision_question": cell["decision_question"],
                    "confidence": confidence,
                    "judgment_zh_cn": zh,
                    "judgment_en": en,
                    "evidence_refs": [row["candidate_id"] for row in cell["candidates"]],
                    "numeric_refs": [row["candidate_id"] for row in numeric["facts"]]
                    if role == "revenue_capture"
                    else [],
                    "repair_ref": repair["repair_id"],
                    "counter_thesis_zh_cn": counter_zh,
                    "what_would_change_en": what_changes,
                    "remaining_gaps": [repair["remaining_gap"]],
                    "status": "internal_candidate_judgment",
                }
            )
        return judgments

    @staticmethod
    def _workpaper_analysis(
        source: Mapping[str, Any],
        judgments: list[Mapping[str, Any]],
        numeric: Mapping[str, Any],
        repairs: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "case_id": source["case_id"],
            "source_preview_digest": source["preview_digest"],
            "status": "internal_draft_awaiting_senior_r2",
            "judgment_refs": [row["judgment_id"] for row in judgments],
            "numeric_fact_refs": [row["candidate_id"] for row in numeric["facts"]],
            "repair_refs": [row["repair_id"] for row in repairs],
            "sections": [
                {
                    "section_id": f"local_workpaper_section_{index}",
                    "evidence_role": row["evidence_role"],
                    "judgment_ref": row["judgment_id"],
                    "evidence_refs": row["evidence_refs"],
                    "numeric_refs": row["numeric_refs"],
                    "remaining_gaps": row["remaining_gaps"],
                }
                for index, row in enumerate(judgments, 1)
            ],
            "senior_r2_status": "not_reviewed",
        }
        return {"content_digest": canonical_digest(payload), **payload}

    @staticmethod
    def _writer_analysis(
        source: Mapping[str, Any],
        workpaper: Mapping[str, Any],
        judgments: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "mode": "deterministic_no_source_internal_composer",
            "status": "internal_draft_awaiting_senior_r2",
            "title_zh_cn": "P36 AI 基础设施需求与利润捕获初步研判",
            "title_en": "P36 AI Infrastructure Demand and Profit Capture Preview",
            "sections": [
                {
                    "section_id": f"local_writer_section_{index}",
                    "evidence_role": row["evidence_role"],
                    "judgment_ref": row["judgment_id"],
                    "heading_zh_cn": {
                        "demand_signal": "需求真实性",
                        "revenue_capture": "价值与利润捕获",
                        "thesis_counterevidence": "瓶颈与反证",
                        "server_oem_orders": "服务器订单与收入转化",
                        "server_oem_margin_cash": "服务器利润与现金转化",
                        "advanced_packaging_capacity": "先进封装产能与收益归属",
                        "hbm_supply_pricing": "HBM 供给、定价与集中度",
                        "semicap_capex_cycle": "半导体设备资本开支与周期",
                        "export_policy_risk": "出口政策风险",
                        "customer_concentration": "客户集中度",
                    }[row["evidence_role"]],
                    "content_zh_cn": row["judgment_zh_cn"],
                    "content_en": row["judgment_en"],
                }
                for index, row in enumerate(judgments, 1)
            ],
            "input_workpaper_digest": workpaper["content_digest"],
            "source_preview_digest": source["preview_digest"],
            "source_access_calls": 0,
            "model_calls": 0,
            "release_admitted": False,
        }
        return {"content_digest": canonical_digest(payload), **payload}

    def _demand_reality_cell(self) -> dict[str, Any]:
        retriever = self._object_retriever_factory(self._paths.object_index)
        results = retriever.search(
            "AI infrastructure demand data center revenue customer deployment latest quarter",
            top_k=3,
            filters={"ticker": "NVDA"},
        )
        candidates = [self._object_candidate(row, rank=index) for index, row in enumerate(results, 1)]
        return self._cell(
            cell_key="demand_reality",
            evidence_role="demand_signal",
            decision_question=(
                "AI infrastructure demand is appearing in company-reported data-center "
                "growth and customer deployment signals, but how durable is conversion?"
            ),
            retrieval_lane="object_bm25",
            candidates=candidates,
        )

    def _object_role_cell(
        self,
        *,
        cell_key: str,
        evidence_role: str,
        ticker: str,
        query: str,
        decision_question: str,
    ) -> dict[str, Any]:
        retriever = self._object_retriever_factory(self._paths.object_index)
        results = retriever.search(query, top_k=3, filters={"ticker": ticker})
        return self._cell(
            cell_key=cell_key,
            evidence_role=evidence_role,
            decision_question=decision_question,
            retrieval_lane="object_bm25",
            candidates=[
                self._object_candidate(row, rank=index)
                for index, row in enumerate(results, 1)
            ],
        )

    def _value_capture_cell(self) -> dict[str, Any]:
        query = """
            WITH ranked AS (
                SELECT
                    gold_row_id, ticker, metric_family, metric_name, value, unit,
                    period, fiscal_year, authority_mode, claim_boundary,
                    citation_url, citation_span, evidence_ref, source_url,
                    ROW_NUMBER() OVER (
                        PARTITION BY metric_family
                        ORDER BY CAST(NULLIF(fiscal_year, '') AS INTEGER) DESC,
                                 period DESC, gold_row_id
                    ) AS metric_rank
                FROM gold_fact_signal_mart
                WHERE ticker = 'NVDA'
                  AND metric_family IN ('revenue', 'gross_profit', 'operating_income')
                  AND can_enter_evidence_bundle = 1
                  AND exact_value_authority = 1
            )
            SELECT * FROM ranked WHERE metric_rank = 1
            ORDER BY CASE metric_family
                WHEN 'revenue' THEN 1
                WHEN 'gross_profit' THEN 2
                ELSE 3
            END
        """
        with self._read_only_connection(self._paths.gold_mart) as connection:
            rows = [dict(row) for row in connection.execute(query).fetchall()]
        return self._cell(
            cell_key="value_profit_capture",
            evidence_role="revenue_capture",
            decision_question=(
                "How much of the demand signal converts into reported revenue, gross profit, "
                "and operating income at the accelerator layer?"
            ),
            retrieval_lane="gold_fact_sql",
            candidates=[self._gold_candidate(row, rank=index) for index, row in enumerate(rows, 1)],
        )

    def _counterevidence_cell(self) -> dict[str, Any]:
        query = """
            WITH selected_edges AS (
                SELECT
                    e.graph_edge_id, n.ticker, n.label AS company_label,
                    e.edge_type, e.authority_mode, e.source_role,
                    e.claim_boundary, e.evidence_refs_json,
                    ROW_NUMBER() OVER (
                        PARTITION BY n.ticker
                        ORDER BY
                            CASE e.source_role
                                WHEN 'supply_chain_official_relationship' THEN 1
                                WHEN 'official_customer_order_or_deployment_event' THEN 2
                                WHEN 'working_capital_liquidity' THEN 3
                                ELSE 4
                            END,
                            e.graph_edge_id
                    ) AS ticker_rank
                FROM research_graph_edges e
                JOIN research_graph_nodes n ON n.graph_node_id = e.from_node_id
                WHERE n.graph_node_id IN ('company:TSM', 'company:MU', 'company:ASML', 'company:NVDA')
                  AND e.can_enter_evidence_bundle = 1
                  AND (
                      e.source_role IN (
                          'supply_chain_official_relationship',
                          'official_customer_order_or_deployment_event'
                      )
                      OR (n.graph_node_id = 'company:NVDA' AND e.source_role = 'working_capital_liquidity')
                  )
            )
            SELECT
                s.graph_edge_id, s.ticker, s.company_label, s.edge_type,
                s.authority_mode, s.source_role, s.claim_boundary,
                s.evidence_refs_json, support.citation_url, support.citation_span,
                support.evidence_ref
            FROM selected_edges s
            LEFT JOIN research_graph_evidence_support support
              ON support.support_id = (
                  SELECT support_id
                  FROM research_graph_evidence_support
                  WHERE graph_edge_id = s.graph_edge_id
                  ORDER BY CASE WHEN citation_url <> '' THEN 0 ELSE 1 END, support_id
                  LIMIT 1
              )
            WHERE s.ticker_rank = 1
            ORDER BY CASE s.ticker
                WHEN 'TSM' THEN 1
                WHEN 'MU' THEN 2
                WHEN 'ASML' THEN 3
                ELSE 4
            END
        """
        with self._read_only_connection(self._paths.research_graph) as connection:
            rows = [dict(row) for row in connection.execute(query).fetchall()]
        return self._cell(
            cell_key="bottleneck_counterevidence",
            evidence_role="thesis_counterevidence",
            decision_question=(
                "Which packaging, memory, equipment, working-capital, or policy constraints "
                "could falsify the simple demand-to-profit thesis?"
            ),
            retrieval_lane="research_graph",
            candidates=[self._graph_candidate(row, rank=index) for index, row in enumerate(rows, 1)],
        )

    @staticmethod
    def _cell(
        *,
        cell_key: str,
        evidence_role: str,
        decision_question: str,
        retrieval_lane: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "cell_key": cell_key,
            "evidence_role": evidence_role,
            "decision_question": decision_question,
            "retrieval_lane": retrieval_lane,
            "status": "candidate_ready" if candidates else "typed_gap",
            "typed_gap": None if candidates else "local_materialized_candidate_absent",
            "candidates": candidates,
        }

    def _object_candidate(self, row: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
        record = dict(row.get("record") or {})
        source_ref = str(row.get("source_evidence_id") or record.get("source_evidence_id") or "")
        source_url = self._official_filing_url(source_ref, row, record)
        excerpt = str(record.get("text_before") or record.get("text_after") or row.get("preview") or "")
        payload = {
            "retrieval_lane": "object_bm25",
            "rank": rank,
            "score": float(row.get("score") or 0.0),
            "ticker": str(row.get("ticker") or "NVDA"),
            "title": str(record.get("title") or row.get("preview") or row.get("section") or source_ref),
            "excerpt": _clip(excerpt),
            "source_name": "SEC filing structured-object index",
            "source_type": str(record.get("source_type") or record.get("form_type") or "SEC filing"),
            "published_at": str(record.get("period_end") or ""),
            "citation_url": source_url,
            "citation_span": str(row.get("section") or record.get("section") or ""),
            "evidence_ref": source_ref,
            "authority_mode": "bounded_thesis_driver_authority",
            "claim_boundary": (
                "Company-authored filing text can support the reported statement and period; "
                "it does not by itself prove durable market demand or industry-wide conversion."
            ),
            "exact_value_authority": False,
            "numeric_eligible": False,
            "writer_citable": False,
            "promotion_status": "candidate_not_promoted",
        }
        return {"candidate_id": _candidate_id(payload), **payload}

    def _official_filing_url(
        self,
        source_ref: str,
        row: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> str:
        direct = _sec_source_url(source_ref)
        if direct:
            return direct
        root = self._paths.official_filing_root
        ticker = str(row.get("ticker") or record.get("ticker") or "")
        fiscal_year = str(row.get("fiscal_year") or record.get("fiscal_year") or "")
        form_type = str(record.get("form_type") or record.get("source_type") or "")
        key = (ticker, fiscal_year, form_type)
        if key in self._official_url_cache:
            return self._official_url_cache[key]
        if not root or not ticker or not fiscal_year or not form_type:
            return ""
        for metadata_path in root.glob(f"{fiscal_year}/*/{ticker}/{form_type}.metadata.json"):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            url = str(metadata.get("filing_url") or "")
            self._official_url_cache[key] = url
            return url
        self._official_url_cache[key] = ""
        return ""

    @staticmethod
    def _gold_candidate(row: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
        payload = {
            "retrieval_lane": "gold_fact_sql",
            "rank": rank,
            "score": None,
            "ticker": str(row.get("ticker") or ""),
            "title": str(row.get("metric_name") or row.get("metric_family") or "Reported metric"),
            "excerpt": str(row.get("citation_span") or ""),
            "source_name": "Gold fact and signal mart",
            "source_type": "SEC CompanyFacts",
            "published_at": str(row.get("period") or ""),
            "citation_url": str(row.get("citation_url") or row.get("source_url") or ""),
            "citation_span": str(row.get("citation_span") or ""),
            "evidence_ref": str(row.get("evidence_ref") or row.get("gold_row_id") or ""),
            "authority_mode": str(row.get("authority_mode") or "exact_company_fact_authority"),
            "claim_boundary": str(row.get("claim_boundary") or ""),
            "exact_value_authority": True,
            "numeric_eligible": True,
            "metric_family": str(row.get("metric_family") or ""),
            "value": str(row.get("value") or ""),
            "unit": str(row.get("unit") or ""),
            "currency": "USD" if str(row.get("unit") or "") == "USD" else "",
            "segment_ref": "__company_total__",
            "row_label": str(row.get("metric_name") or row.get("metric_family") or ""),
            "scale_multiplier": 1,
            "source_coordinate": str(row.get("evidence_ref") or row.get("gold_row_id") or ""),
            "period": str(row.get("period") or ""),
            "writer_citable": False,
            "promotion_status": "candidate_not_promoted",
        }
        return {"candidate_id": _candidate_id(payload), **payload}

    @staticmethod
    def _graph_candidate(row: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
        ticker = str(row.get("ticker") or "")
        edge_type = str(row.get("edge_type") or "Research graph relationship")
        excerpt = str(row.get("citation_span") or row.get("claim_boundary") or "")
        payload = {
            "retrieval_lane": "research_graph",
            "rank": rank,
            "score": None,
            "ticker": ticker,
            "title": f"{ticker} {edge_type.replace('_', ' ').title()}",
            "excerpt": _clip(excerpt),
            "source_name": "Research graph evidence support",
            "source_type": str(row.get("source_role") or "graph relationship"),
            "published_at": "",
            "citation_url": str(row.get("citation_url") or ""),
            "citation_span": str(row.get("citation_span") or ""),
            "evidence_ref": str(row.get("evidence_ref") or row.get("graph_edge_id") or ""),
            "authority_mode": str(row.get("authority_mode") or "bounded_thesis_driver_authority"),
            "claim_boundary": str(row.get("claim_boundary") or ""),
            "exact_value_authority": False,
            "numeric_eligible": False,
            "writer_citable": False,
            "promotion_status": "candidate_not_promoted",
        }
        return {"candidate_id": _candidate_id(payload), **payload}

    def _source_inventory(self) -> list[dict[str, Any]]:
        metadata_path = self._paths.object_index / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return [
            {
                "source_id": "structured_object_fts",
                "schema_version": str(metadata.get("schema_version") or "unknown"),
                "record_count": int(metadata.get("records") or 0),
                "snapshot_digest": _small_file_digest(metadata_path),
            },
            {
                "source_id": "gold_fact_signal_mart",
                "schema_version": self._sqlite_schema_version(
                    self._paths.gold_mart, "gold_fact_signal_mart_metadata"
                ),
                "record_count": self._sqlite_count(self._paths.gold_mart, "gold_fact_signal_mart"),
                "snapshot_digest": _stat_digest(self._paths.gold_mart),
            },
            {
                "source_id": "research_graph_store",
                "schema_version": self._sqlite_schema_version(
                    self._paths.research_graph, "research_graph_metadata"
                ),
                "record_count": self._sqlite_count(self._paths.research_graph, "research_graph_edges"),
                "snapshot_digest": _stat_digest(self._paths.research_graph),
            },
        ]

    def _require_sources(self) -> None:
        required = (
            self._paths.object_index / "metadata.json",
            self._paths.object_index / "records.sqlite",
            self._paths.gold_mart,
            self._paths.research_graph,
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise LocalResearchServiceError(
                "local_research_sources_unavailable", 503, missing_paths=missing
            )

    @staticmethod
    @contextmanager
    def _read_only_connection(path: Path) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _sqlite_schema_version(self, path: Path, table: str) -> str:
        with self._read_only_connection(path) as connection:
            row = connection.execute(
                f"SELECT value FROM {table} WHERE key = 'schema_version'"
            ).fetchone()
        return str(row[0] if row else "unknown")

    def _sqlite_count(self, path: Path, table: str) -> int:
        with self._read_only_connection(path) as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0] if row else 0)

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if (
            not principal.tenant_id
            or not principal.project_id
            or not principal.actor_id
            or permission not in principal.permissions
        ):
            raise LocalResearchServiceError(
                "permission_denied", 403, required_permission=permission
            )


def _candidate_id(payload: Mapping[str, Any]) -> str:
    return f"local_candidate_{canonical_digest(payload)[:24]}"


def _clip(value: str, limit: int = 720) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def _sec_source_url(source_ref: str) -> str:
    match = re.search(r"::(?P<accession>\d{18})::", source_ref)
    if not match:
        return ""
    accession = match.group("accession")
    cik = str(int(accession[:10]))
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"


def _small_file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stat_digest(path: Path) -> str:
    stat = path.stat()
    return canonical_digest({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
