from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_SPEC_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_spec_v0_1.json"
DEFAULT_EXEMPLARS_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_answer_exemplars_v0_2.json"
DEFAULT_ARTIFACT_AUDIT_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_artifact_audit_v0_1.json"
DEFAULT_JSON_OUT = REPO_ROOT / "docs/project_os/humanmade_gold_set_matrix_audit_v0_1.json"
DEFAULT_MD_OUT = REPO_ROOT / "docs/internal/vnext_20260610/p33_humanmade_gold_set_matrix_audit_v0_1.zh-CN.md"


@dataclass(frozen=True)
class CaseAuditTemplate:
    status: str
    audit_scope: str
    story_role: str
    problem_pattern: str
    likely_faulty_layers: list[str]
    next_repair: list[str]


RUBRIC_CASE_TEMPLATES: dict[str, CaseAuditTemplate] = {
    "semicap_cycle_rubric_v0_1": CaseAuditTemplate(
        status="partial_from_ai_semis_deep_case_unproven_as_standalone_runtime_case",
        audit_scope="inferred_from_ai_semis_deep_artifact_plus_gold_exemplar",
        story_role="AI/Semis deep case already shows semicap read-through exists as mechanism, but not yet as bookings/backlog/customer-cycle proof.",
        problem_pattern="The system can name ASML/AMAT/LRCX/KLAC and explain the broad semicap mechanism, but current rows are still too close to peer-scope/context. The gold answer needs bookings, backlog, shipment, service mix, customer cycle and China/export exposure.",
        likely_faulty_layers=[
            "FPI/company_IR/local_disclosure_parser",
            "semicap_playbook_to_specialist_contract",
            "ProductIntelligenceGraph edge investment projection",
            "BriefingPackQualityGate missing semicap depth checks",
        ],
        next_repair=[
            "Ingest ASML/AMAT/LRCX/KLAC/TEL official results and IR tables into semicap exact/context slots.",
            "Add semicap-specific required evidence roles: bookings, backlog, WFE/tool exposure, customer cycle, service mix, China/export risk.",
            "Require industry_supply_chain_analyst to separate peer scope from cycle proof.",
        ],
    ),
    "cloud_saas_ai_monetization_rubric_v0_1": CaseAuditTemplate(
        status="catalog_ready_runtime_artifact_missing",
        audit_scope="rubric_only_no_case_artifact",
        story_role="This case tests whether AI capex is translated into monetization instead of being treated as automatically positive.",
        problem_pattern="The project has capex and product/source layers, but this rubric has not been proven as a runtime workpaper. The likely failure is treating AI product launch or capex growth as growth proof without RPO/ARR/usage/margin/depreciation bridge.",
        likely_faulty_layers=[
            "Research Lead required-item planning for monetization versus cost burden",
            "FundamentalStatementPack SaaS/cloud operating metric slots",
            "CapitalMarketFeedback price-in and capex burden projection",
            "specialist answer-exemplar contract",
        ],
        next_repair=[
            "Add cloud/SaaS fixture with capex, cloud revenue, RPO/ARR/deferred revenue, margin and depreciation bridge.",
            "Require Product/SaaS analyst to separate product adoption from monetized revenue.",
            "Require Fundamental analyst to compute or explain AI capex return path and FCF/margin pressure.",
        ],
    ),
    "financials_rate_credit_capital_rubric_v0_1": CaseAuditTemplate(
        status="catalog_ready_runtime_artifact_missing",
        audit_scope="rubric_only_no_case_artifact",
        story_role="This case tests whether the system can switch from product-led analysis to balance-sheet-led financials analysis.",
        problem_pattern="The current AI/Semis evidence path does not prove bank/financials behavior. The likely failure is analyzing banks like industrial companies, using revenue/EPS while underweighting deposits, NIM, loan growth, provisions, capital and liquidity.",
        likely_faulty_layers=[
            "financials industry playbook not runtime-proven",
            "FundamentalStatementPack bank-specific KPI slots",
            "macro/rate context to issuer financial bridge",
            "Research Lead industry routing",
        ],
        next_repair=[
            "Add financials fixture requiring deposit cost/mix, loan balance, NIM, provision, capital ratio and liquidity.",
            "Make Research Lead route banks to balance-sheet-first analysis.",
            "Prevent FRED/FDIC macro context from being promoted to issuer-level NIM or credit facts.",
        ],
    ),
    "healthcare_regulated_product_adoption_rubric_v0_1": CaseAuditTemplate(
        status="catalog_ready_runtime_artifact_missing",
        audit_scope="rubric_only_no_case_artifact",
        story_role="This case tests whether regulatory/product evidence can be used without pretending it is sales evidence.",
        problem_pattern="The system has ClinicalTrials/openFDA source concepts, but no audited runtime case proving trial/FDA/product/adoption/reimbursement facts become a product-performance briefing.",
        likely_faulty_layers=[
            "regulated product context adapter depth",
            "healthcare product-to-commercialization playbook",
            "ProductIntelligenceGraph product indication and adoption edges",
            "commercial tracker boundary gate",
        ],
        next_repair=[
            "Add healthcare fixture with product/indication, trial/FDA status, adoption/procedure proxy, reimbursement/access and revenue bridge/gap.",
            "Force distinction between regulatory eligibility and commercial performance.",
            "Classify missing prescription/procedure/share data as commercial/public boundary only after source-route attempts.",
        ],
    ),
    "energy_utilities_power_demand_rubric_v0_1": CaseAuditTemplate(
        status="catalog_ready_runtime_artifact_missing",
        audit_scope="rubric_only_no_case_artifact",
        story_role="This case tests whether AI power demand is converted into regulated return, capex and financing analysis.",
        problem_pattern="The system has macro/regulatory source ideas and capital packs, but no runtime proof that load growth, rate base, allowed ROE, capex, debt and cash flow are analyzed together.",
        likely_faulty_layers=[
            "utility industry operating metric slots",
            "EIA/regulatory data adapter to issuer exposure bridge",
            "capital/debt/FCF bridge projection",
            "Research Lead utility playbook injection",
        ],
        next_repair=[
            "Add utility fixture requiring load growth, generation/asset exposure, rate case/RAB, capex/debt and cash-flow quality.",
            "Prevent AI power-demand headlines from being promoted to EPS or ROE proof.",
            "Connect rate-case/regulatory evidence to financing and capex pressure.",
        ],
    ),
    "retail_consumer_traffic_margin_rubric_v0_1": CaseAuditTemplate(
        status="catalog_ready_runtime_artifact_missing",
        audit_scope="rubric_only_no_case_artifact",
        story_role="This case tests whether consumer growth is decomposed into traffic, ticket, price/mix, units, inventory and margin.",
        problem_pattern="The system likely has revenue and company-disclosed KPI rows for some issuers, but has not proven it can avoid writing consumer/retail as generic revenue growth.",
        likely_faulty_layers=[
            "retail operating metric slot normalization",
            "commercial POS/channel boundary",
            "Fundamental analyst operating decomposition skill",
            "MemoLogicPlan dimension requirements",
        ],
        next_repair=[
            "Add retail fixture requiring same-store sales, traffic/ticket, price/mix, inventory, promotion and gross margin.",
            "Keep POS/sell-through exact as commercial gap unless public rows exist.",
            "Require revenue growth to be decomposed before memo pass.",
        ],
    ),
    "auto_ev_industrial_cycle_rubric_v0_1": CaseAuditTemplate(
        status="catalog_ready_runtime_artifact_missing",
        audit_scope="rubric_only_no_case_artifact",
        story_role="This case tests whether volume growth is separated from profit quality.",
        problem_pattern="The system has NHTSA/source concepts and product layers, but no proof that deliveries, ASP, inventory, recall, capacity utilization and financing sensitivity are bridged to margin quality.",
        likely_faulty_layers=[
            "auto/industrial operating metric slots",
            "NHTSA and recall context projection",
            "channel/inventory parser routes",
            "specialist product-to-margin bridge",
        ],
        next_repair=[
            "Add auto/industrial fixture requiring delivery/volume, ASP/mix, inventory/channel, recall/quality, capacity and financing sensitivity.",
            "Prevent deliveries alone from being written as margin-quality proof.",
            "Route recall/quality context to product risk, not revenue proof.",
        ],
    ),
    "capital_market_feedback_price_in_rubric_v0_1": CaseAuditTemplate(
        status="partial_platform_foundation_but_case_pack_missing",
        audit_scope="capability_exists_no_gold_case_artifact",
        story_role="This case tests whether the system can say not only what improved, but whether the market already paid for it.",
        problem_pattern="S8 capital feedback exists at platform level, but the AI/Semis audit shows NVDA/AMD/GOOGL/DELL valuation, positioning and crowding rows were missing for the concrete case.",
        likely_faulty_layers=[
            "CapitalMarketFeedback case-specific pack selection",
            "valuation/ownership/liquidity source routing",
            "market_valuation_analyst required-item contract",
            "MemoLogicPlan price-in dimension",
        ],
        next_repair=[
            "Add price-in fixture requiring valuation/peer context, holder/ownership, liquidity/short/options context, credit/debt and event/corporate-action rows.",
            "Make market feedback a bounded second-order layer, not a trade recommendation.",
            "Require price-in section to state what is already reflected and what evidence is missing.",
        ],
    ),
}


NEGATIVE_CASE_TEMPLATES: dict[str, CaseAuditTemplate] = {
    "negative_sku_revenue_missing_not_product_failure_v0_1": CaseAuditTemplate(
        status="open_guard_needed_ai_semis_currently_fails_depth",
        audit_scope="negative_pattern_relevant_to_ai_semis_artifact",
        story_role="This negative case is the clearest symptom of the current product-layer weakness.",
        problem_pattern="The system should keep product analysis alive without SKU revenue, but the current AI/Semis artifact still lacks product runtime facts and risks reducing product judgment to exact-KPI absence.",
        likely_faulty_layers=[
            "product source runtime ingestion",
            "ProductIntelligenceGraph product fact projection",
            "product specialist answer contract",
            "BriefingPackQualityGate product-depth check",
        ],
        next_repair=[
            "Add product fact slots for official specs, architecture generation, benchmark/performance proxy, OEM/cloud config and deployment evidence.",
            "Add negative gate: missing SKU revenue cannot make product section fail if technical/deployment evidence exists.",
        ],
    ),
    "negative_demand_pool_not_supplier_allocation_v0_1": CaseAuditTemplate(
        status="partial_guard_present_needs_machine_check",
        audit_scope="negative_pattern_relevant_to_ai_semis_artifact",
        story_role="This negative case is mostly understood, but not yet hardened as a matrix gate.",
        problem_pattern="MSFT/AMZN capex is treated as demand-pool evidence and not direct supplier allocation in the audit, but future writer/specialist outputs still need a deterministic check.",
        likely_faulty_layers=[
            "Research Lead evidence role plan",
            "specialist cannot-infer boundary",
            "Memo Writer source-role projection",
        ],
        next_repair=[
            "Add audit rule that hyperscaler capex can support demand pool but not supplier allocation exact.",
            "Require what-would-upgrade evidence: customer deployment, purchase/order, supplier revenue/order/backlog.",
        ],
    ),
    "negative_relationship_graph_not_financial_fact_v0_1": CaseAuditTemplate(
        status="partial_guard_present_projection_needs_investment_roles",
        audit_scope="negative_pattern_relevant_to_ai_semis_artifact",
        story_role="This negative case exposes why graph quality is not the same as analysis quality.",
        problem_pattern="Current graph rows are mostly treated as scope/hypothesis, which avoids direct financial over-promotion, but they still lack stable investment-role projection.",
        likely_faulty_layers=[
            "ProductIntelligenceGraph investment-role projection",
            "relationship_graph edge authority schema",
            "JudgmentCard graph_edge_refs",
        ],
        next_repair=[
            "Attach edge_investment_role such as demand_validation, adoption_signal, supply_constraint, margin_pressure, substitution or customer_concentration.",
            "Force every graph edge used in a memo to state cannot-infer financial facts.",
        ],
    ),
    "negative_parser_gap_not_public_source_absent_v0_1": CaseAuditTemplate(
        status="partial_guard_present_not_generalized",
        audit_scope="negative_pattern_relevant_to_ai_semis_artifact",
        story_role="This negative case is how source gaps stop being fake public-data gaps.",
        problem_pattern="ASML/TSM SEC manifest gaps are now typed as retrievable route gaps, but this does not prove non-US/local disclosure parser discipline across all cases.",
        likely_faulty_layers=[
            "FPI/company_IR/local_exchange source router",
            "table/PDF parser attribution",
            "gap taxonomy",
        ],
        next_repair=[
            "Add audit rule: located source plus failed extraction must become parser_gap or local_adapter_gap, never public_source_absent.",
            "Add sample local/FPI filings to parser-boundary fixtures.",
        ],
    ),
    "negative_available_evidence_not_used_v0_1": CaseAuditTemplate(
        status="open_guard_needed_old_memo_showed_symptom",
        audit_scope="negative_pattern_relevant_to_old_paid_memo_and_writer_payload",
        story_role="This negative case connects data transmission failures to bad final prose.",
        problem_pattern="Previous outputs could say data was missing or remain generic even when aggregate or payload contained relevant DELL/LRCX financial rows. That is not a source gap; it is selector/projection/writer consumption failure.",
        likely_faulty_layers=[
            "selected claim bridge",
            "MemoLogicPlan required_item_answer_plan consumption",
            "Memo Writer evidence ref inventory",
            "Verifier contradiction check",
        ],
        next_repair=[
            "Add audit rule comparing aggregate/payload available facts with final memo missing-data claims.",
            "Fail hard when final memo says evidence is missing while upstream accepted artifact contains it.",
        ],
    ),
    "negative_commercial_tracker_boundary_v0_1": CaseAuditTemplate(
        status="contract_defined_runtime_guard_unproven",
        audit_scope="negative_pattern_no_case_artifact",
        story_role="This negative case protects the product from becoming either overconfident or useless.",
        problem_pattern="The platform has commercial/public-boundary concepts, but no matrix audit has proven that public proxy keeps research value without being promoted to exact sales/share/flow.",
        likely_faulty_layers=[
            "source authority model",
            "commercial_gap taxonomy",
            "Memo Writer proxy wording",
            "Verifier proxy-to-exact misuse gate",
        ],
        next_repair=[
            "Add audit rule that public proxy can support direction/context but not exact commercial tracker metrics.",
            "Require memos to preserve bounded proxy value instead of refusing the whole section.",
        ],
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def case_by_id(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(case["case_id"]): case for case in cases}


def exemplar_by_id(cases: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for case in cases:
        case_id = str(case["case_id"])
        result[case_id] = str(case.get("answer_example") or case.get("correct_response_pattern") or "")
    return result


def audit_deep_case(case: dict[str, Any], exemplar: str, artifact_audit: dict[str, Any]) -> dict[str, Any]:
    gold_results = artifact_audit.get("gold_item_results", [])
    failing = [item for item in gold_results if str(item.get("status", "")).startswith("fail")]
    partial = [item for item in gold_results if "partial" in str(item.get("status", ""))]
    pass_like = [item for item in gold_results if "pass" in str(item.get("status", ""))]
    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "vertical": case.get("vertical"),
        "status": "artifact_backed_fail_for_gold_depth",
        "audit_scope": "direct_artifact_audit",
        "story_role": "The deep case proves the system can build a chain-shaped artifact, but also proves the chain is not yet strong enough to become an analyst workpaper.",
        "answer_exemplar": exemplar,
        "evidence_basis": {
            "gold_item_count": len(gold_results),
            "fail_count": len(failing),
            "partial_count": len(partial),
            "pass_like_count": len(pass_like),
            "artifact_metrics": artifact_audit.get("artifact_metrics", {}),
        },
        "problem_pattern": "Trace and shape exist, but product architecture, customer deployment, Dell margin bridge, semicap read-through, market price-in and counter-thesis are not all gold-depth.",
        "likely_faulty_layers": [
            "source_runtime_ingestion",
            "ProductIntelligenceGraph projection",
            "Coverage depth gate",
            "specialist answer-exemplar contract",
            "Research Lead post-specialist veto",
            "writer semantic material selection",
        ],
        "next_repair": artifact_audit.get("next_repair_order", []),
    }


def audit_template_case(case: dict[str, Any], exemplar: str, template: CaseAuditTemplate) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "vertical": case.get("vertical"),
        "status": template.status,
        "audit_scope": template.audit_scope,
        "story_role": template.story_role,
        "answer_exemplar": exemplar,
        "must_answer_items": case.get("must_answer_items", []),
        "evidence_roles": case.get("evidence_roles", []),
        "problem_pattern": template.problem_pattern,
        "likely_faulty_layers": template.likely_faulty_layers,
        "next_repair": template.next_repair,
    }


def build_matrix_audit(spec: dict[str, Any], exemplars: dict[str, Any], artifact_audit: dict[str, Any]) -> dict[str, Any]:
    cases = spec.get("cases", [])
    cases_by_id = case_by_id(cases)
    exemplars_by_id = exemplar_by_id(exemplars.get("cases", []))
    matrix: list[dict[str, Any]] = []

    deep_case_id = "ai_semis_dell_nvda_anchor_v0_1"
    matrix.append(audit_deep_case(cases_by_id[deep_case_id], exemplars_by_id.get(deep_case_id, ""), artifact_audit))

    for case_id, template in RUBRIC_CASE_TEMPLATES.items():
        matrix.append(audit_template_case(cases_by_id[case_id], exemplars_by_id.get(case_id, ""), template))

    for case_id, template in NEGATIVE_CASE_TEMPLATES.items():
        matrix.append(audit_template_case(cases_by_id[case_id], exemplars_by_id.get(case_id, ""), template))

    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in matrix:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        type_counts[row["case_type"]] = type_counts.get(row["case_type"], 0) + 1

    story_chapters = [
        {
            "chapter": "1_engineering_chain_exists_but_research_chain_is_thin",
            "finding": "The project no longer fails because there is no graph or no evidence path. It fails because the evidence path still turns into context, boundaries and generic anchors before it becomes an analyst-grade judgment.",
            "supported_by_cases": ["ai_semis_dell_nvda_anchor_v0_1"],
        },
        {
            "chapter": "2_deep_case_exposes_the_first_faulty_floor",
            "finding": "AI/Semis shows the earliest hard failure at gold-depth source rows and product graph projection: product_runtime_fact_count=0 and several required items remain context/proxy even though route/shape gates pass.",
            "supported_by_cases": ["ai_semis_dell_nvda_anchor_v0_1", "negative_sku_revenue_missing_not_product_failure_v0_1"],
        },
        {
            "chapter": "3_rubric_cases_show_this_will_generalize_unless_methods_become_runtime_contracts",
            "finding": "Semicap, Cloud/SaaS, Financials, Healthcare, Energy, Retail, Auto and Secondary-market cases each require different operating metrics and evidence bridges. Current P33 success on AI/Semis structure does not prove those vertical methods are runtime-active.",
            "supported_by_cases": list(RUBRIC_CASE_TEMPLATES.keys()),
        },
        {
            "chapter": "4_negative_cases_define_the_failure_modes_that_must_be_machine_checked",
            "finding": "The most dangerous failures are not empty answers. They are over-promotion, false source absence, available evidence not used, and public proxy pretending to be exact. These need gates tied to artifacts, not reviewer memory.",
            "supported_by_cases": list(NEGATIVE_CASE_TEMPLATES.keys()),
        },
        {
            "chapter": "5_next_repair_must_compile_gold_set_into_runtime",
            "finding": "The next useful engineering step is not another model run. It is to compile the gold set into HumanmadeGoldSetAudit, BriefingPackQualityGate, source ingestion, graph projection, specialist contracts and Research Lead veto.",
            "supported_by_cases": [row["case_id"] for row in matrix],
        },
    ]

    return {
        "schema_version": "fin_insight_humanmade_gold_set_matrix_audit_v0_1",
        "updated_at": "2026-07-06",
        "status": "no_paid_matrix_audit_completed_findings_open",
        "scope": {
            "audit_mode": "no_paid_gold_set_matrix_audit",
            "deep_gold_case_count": type_counts.get("deep_gold_case", 0),
            "rubric_gold_case_count": type_counts.get("rubric_gold_case", 0),
            "negative_gold_case_count": type_counts.get("negative_gold_case", 0),
            "not_run": ["paid_llm", "full_chain", "model_comparison", "new_retrieval", "crawler_or_parser"],
        },
        "input_documents": {
            "gold_set_spec": str(DEFAULT_SPEC_PATH.relative_to(REPO_ROOT)),
            "answer_exemplars": str(DEFAULT_EXEMPLARS_PATH.relative_to(REPO_ROOT)),
            "artifact_audit": str(DEFAULT_ARTIFACT_AUDIT_PATH.relative_to(REPO_ROOT)),
        },
        "status_counts": status_counts,
        "case_results": matrix,
        "story_chapters": story_chapters,
        "cross_case_conclusion": {
            "short_form": "The project has moved past basic orchestration failure, but has not yet converted vertical research methods and public-source evidence into reusable runtime judgment assets.",
            "why_ai_semis_matters": "AI/Semis is the first deep artifact-backed proof that shape/trace can pass while research depth still fails.",
            "why_rubric_cases_matter": "The rubric cases show the same weakness would reappear across sectors unless each vertical's method, operating metrics and authority boundaries are compiled into runtime contracts.",
            "why_negative_cases_matter": "The negative cases define the exact ways a financial agent can sound plausible while being wrong: over-promotion, false missing-data claims, parser/source confusion and proxy/exact misuse.",
        },
        "next_repair_order": [
            "Implement artifact-backed HumanmadeGoldSetAudit runner output as a required pre-writer gate.",
            "Add BriefingPackQualityGate with per-gold-case depth checks.",
            "Ingest AI/Semis human source ledger into runtime slots first; do not expand paid cases.",
            "Compile rubric cases into vertical playbook runtime contracts before claiming cross-sector readiness.",
            "Compile negative cases into deterministic failure gates against aggregate, writer payload and final memo.",
        ],
    }


CASE_STORY_ZH: dict[str, str] = {
    "ai_semis_dell_nvda_anchor_v0_1": "真实 AI/Semis artifact 已经能证明工程链路有形状、有 trace，但产品架构、客户部署、DELL 利润质量桥、semicap read-through、market price-in 和反证还没有达到 humanmade gold answer depth。",
    "semicap_cycle_rubric_v0_1": "系统能识别 ASML/AMAT/LRCX/KLAC 和半导体设备周期，但当前证据仍偏 peer scope / context；合格答案需要 bookings、backlog、shipment、service mix、客户晶圆厂周期和 China/export exposure。",
    "cloud_saas_ai_monetization_rubric_v0_1": "系统有 capex、产品和 source 层，但还没有 runtime 证明能把 AI 产品发布 / AI capex 转成云和 SaaS 的 RPO、ARR、usage、margin、depreciation 和 FCF 回报分析。",
    "financials_rate_credit_capital_rubric_v0_1": "当前 AI/Semis 路径不能证明金融行业能力；银行/金融股必须从 deposits、NIM、loan growth、provision、capital、liquidity 和 funding cost 出发，不能按工业公司的收入/EPS 模板分析。",
    "healthcare_regulated_product_adoption_rubric_v0_1": "系统有 ClinicalTrials/openFDA 等 source 概念，但还没有证明 trial、FDA、产品适应症、adoption、reimbursement 能进入产品表现 briefing。",
    "energy_utilities_power_demand_rubric_v0_1": "系统有宏观/监管和资本包概念，但还没有证明能把 load growth、rate base、allowed ROE、capex、debt、cash flow 放在同一条公用事业分析链里。",
    "retail_consumer_traffic_margin_rubric_v0_1": "系统可能能拿到部分收入和公司披露 KPI，但还没证明能避免把零售/消费写成泛泛 revenue growth；合格答案需要 traffic、ticket、mix、promo、inventory、shrink 和 margin bridge。",
    "auto_ev_industrial_cycle_rubric_v0_1": "系统有 NHTSA 和产品层概念，但还没证明能把 deliveries、ASP、inventory、recall、capacity utilization、financing sensitivity 桥到 margin quality。",
    "capital_market_feedback_price_in_rubric_v0_1": "S8 资本市场反馈在平台层已存在，但 AI/Semis 具体 case 里 NVDA/AMD/GOOGL/DELL 的 valuation、positioning、crowding 和 price-in 证据仍缺 case-specific pack。",
    "negative_sku_revenue_missing_not_product_failure_v0_1": "没有 SKU revenue 不能等于产品层失败；但当前 AI/Semis artifact 仍缺 runtime product facts，容易把产品判断压扁成 exact KPI 缺口。",
    "negative_demand_pool_not_supplier_allocation_v0_1": "MSFT/AMZN capex 只能证明 demand pool，不能直接证明 DELL/NVDA supplier allocation；未来 writer / specialist 必须有机器检查防止提权。",
    "negative_relationship_graph_not_financial_fact_v0_1": "relationship graph 不能直接当财务事实；当前大体避免了直接提权，但图谱边还缺稳定 investment-role projection。",
    "negative_parser_gap_not_public_source_absent_v0_1": "ASML/TSM SEC manifest gaps 已被写成 retrievable route gaps，但这还不能证明非美/FPI/local disclosure parser 在所有 case 中都能正确归因。",
    "negative_available_evidence_not_used_v0_1": "如果 aggregate / writer payload 已有 DELL/LRCX 财务或经营证据，memo 仍写成缺失，这不是 source gap，而是 selector / projection / writer consumption failure。",
    "negative_commercial_tracker_boundary_v0_1": "公开 proxy 可以保留研究价值，但不能冒充 exact sales/share/flow；当前 boundary 概念已有，尚未被 matrix audit 证明为可执行 runtime guard。",
}


NEXT_REPAIR_ZH: dict[str, str] = {
    "Implement artifact-backed HumanmadeGoldSetAudit runner output as a required pre-writer gate.": "实现 artifact-backed `HumanmadeGoldSetAudit`，并把它接成 Memo Writer 前的必过审计。",
    "Add BriefingPackQualityGate with per-gold-case depth checks.": "新增 `BriefingPackQualityGate`，按 deep/rubric/negative gold case 检查 briefing pack 的研究深度。",
    "Ingest AI/Semis human source ledger into runtime slots first; do not expand paid cases.": "先把 AI/Semis human source ledger 接进 runtime slots，不先扩 paid cases。",
    "Compile rubric cases into vertical playbook runtime contracts before claiming cross-sector readiness.": "把 rubric cases 编译成 vertical playbook runtime contracts，再声明跨行业能力。",
    "Compile negative cases into deterministic failure gates against aggregate, writer payload and final memo.": "把 negative cases 编译成 aggregate、writer payload、final memo 的 deterministic failure gates。",
}


def render_markdown(audit: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# P33 Humanmade Gold Set Matrix Audit v0.1")
    lines.append("")
    lines.append("日期：2026-07-06")
    lines.append("")
    lines.append("## 1. 审计口径")
    lines.append("")
    lines.append("这轮不是继续跑模型，也不是把 AI/Semis 单 case 的问题直接外推成全行业结论。")
    lines.append("本轮做的是 no-paid matrix audit：把 1 个 Deep Gold Case、8 个 Rubric Gold Case 和 6 个 Negative Gold Case 放在同一张矩阵里，判断当前项目已经证明了什么、还只是文档/规则、以及哪些风险会跨行业复现。")
    lines.append("")
    lines.append("未运行：paid LLM、full-chain、模型对比、新检索、爬虫或 parser。")
    lines.append("")
    lines.append("## 2. 故事线")
    lines.append("")
    lines.append("这次审计串起来看，故事不是“某个节点又坏了”，而是项目进入了一个更关键的阶段：工程链路已经能把任务跑成 required items、JudgmentCandidates、MemoLogicPlan 和 writer payload，但这条链路还没有稳定把金融研究方法和公开源证据转成成熟 analyst briefing。")
    lines.append("")
    for idx, chapter in enumerate(audit["story_chapters"], 1):
        lines.append(f"### 2.{idx} {chapter['chapter']}")
        lines.append("")
        if chapter["chapter"] == "1_engineering_chain_exists_but_research_chain_is_thin":
            lines.append("项目现在不是没有图谱、证据路径或 agent 节点，而是这些路径在进入最终判断前仍会变成 context、边界说明和泛化锚点，没有稳定形成 analyst-grade judgment。")
        elif chapter["chapter"] == "2_deep_case_exposes_the_first_faulty_floor":
            lines.append("AI/Semis deep case 暴露的最早硬问题在 gold-depth source rows 和产品图谱投影：`product_runtime_fact_count=0`，多个 required item 仍是 context/proxy，即使 route 和 shape gate 已经通过。")
        elif chapter["chapter"] == "3_rubric_cases_show_this_will_generalize_unless_methods_become_runtime_contracts":
            lines.append("Semicap、Cloud/SaaS、Financials、Healthcare、Energy、Retail、Auto 和 Secondary-market 每个行业都要求不同 operating metrics 和证据桥。AI/Semis 上的结构性通过，不能证明这些 vertical method 已经 runtime-active。")
        elif chapter["chapter"] == "4_negative_cases_define_the_failure_modes_that_must_be_machine_checked":
            lines.append("最危险的失败不是空答案，而是过度提权、虚假 source absence、已有 evidence 未使用、public proxy 冒充 exact。这些必须绑定 artifact 做机器检查，不能依赖 reviewer 记忆。")
        elif chapter["chapter"] == "5_next_repair_must_compile_gold_set_into_runtime":
            lines.append("下一步不是继续跑模型，而是把 gold set 编译进 `HumanmadeGoldSetAudit`、`BriefingPackQualityGate`、source ingestion、graph projection、specialist contracts 和 Research Lead veto。")
        else:
            lines.append(chapter["finding"])
        lines.append("")
        lines.append("支撑 case：`" + "`, `".join(chapter["supported_by_cases"]) + "`。")
        lines.append("")
    lines.append("## 3. Case 矩阵审计")
    lines.append("")
    lines.append("| Case | 类型 | 当前状态 | 问题模式 | 最可能的早期故障层 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in audit["case_results"]:
        layers = ", ".join(row["likely_faulty_layers"][:3])
        problem_pattern = CASE_STORY_ZH.get(row["case_id"], row["problem_pattern"])
        lines.append(
            f"| `{row['case_id']}` | `{row['case_type']}` | `{row['status']}` | {problem_pattern} | {layers} |"
        )
    lines.append("")
    lines.append("## 4. 审计后的总体判断")
    lines.append("")
    conclusion = audit["cross_case_conclusion"]
    lines.append("项目已经越过了最基础的编排失败阶段，但还没有把 vertical research methods 和公开源证据稳定转成可复用的 runtime judgment assets。")
    lines.append("")
    lines.append("AI/Semis deep case 的价值在于，它不是抽象规则，而是真实暴露了当前链路的断层：shape/trace 可以通过，但 product architecture、customer deployment、financial bridge、semicap read-through、market price-in 和 counter-thesis 还不能形成 gold answer。")
    lines.append("")
    lines.append("8 个 Rubric Gold Case 的价值在于，它们说明这个问题不是 AI/Semis 独有。每个行业都有自己的“正确分析语言”：银行要资产负债表和信用周期，公用事业要 rate base / capex / debt，零售要 traffic / ticket / mix / inventory，医疗要 clinical / regulatory / adoption / reimbursement。只要这些方法没有进入 runtime contract，换行业后就会重新退化成证据摘要。")
    lines.append("")
    lines.append("6 个 Negative Gold Case 的价值在于，它们定义了金融 agent 最危险的坏输出：不是答不出来，而是把 proxy 写成 exact，把 graph 写成财务事实，把 parser gap 写成公开源没有，把上游已有证据写成缺失。")
    lines.append("")
    lines.append("## 5. 下一步")
    lines.append("")
    for item in audit["next_repair_order"]:
        lines.append(f"- {NEXT_REPAIR_ZH.get(item, item)}")
    lines.append("")
    lines.append("当前仍不得直接 paid Memo Writer、full-chain、模型对比或扩 case。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run no-paid P33 Humanmade Gold Set matrix audit.")
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC_PATH)
    parser.add_argument("--exemplars", type=Path, default=DEFAULT_EXEMPLARS_PATH)
    parser.add_argument("--artifact-audit", type=Path, default=DEFAULT_ARTIFACT_AUDIT_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args()

    spec = load_json(args.spec)
    exemplars = load_json(args.exemplars)
    artifact_audit = load_json(args.artifact_audit)
    audit = build_matrix_audit(spec, exemplars, artifact_audit)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({"status": audit["status"], "json_out": str(args.json_out), "md_out": str(args.md_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
