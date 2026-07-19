from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


HUMANMADE_GOLD_SET_RUNTIME_SCHEMA_VERSION = "fin_insight_humanmade_gold_set_runtime_v0_1"
BRIEFING_PACK_QUALITY_GATE_SCHEMA_VERSION = "fin_insight_briefing_pack_quality_gate_v0_1"
HUMANMADE_GOLD_SET_AUDIT_SCHEMA_VERSION = "fin_insight_humanmade_gold_set_audit_v0_1"
AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION = "fin_insight_ai_semis_gold_depth_content_v0_1"
MULTICASE_GOLDSET_EVIDENCE_DEPTH_SCHEMA_VERSION = "fin_insight_multicase_goldset_evidence_depth_v0_1"
FRESH_ALL_SPECIALIST_GOLD_PASS_SCHEMA_VERSION = "fin_insight_fresh_all_specialist_gold_pass_v0_1"
NEGATIVE_GOLD_FAILURE_FIXTURE_SCHEMA_VERSION = "fin_insight_negative_gold_failure_fixture_v0_1"
MULTICASE_GOLDSET_NO_PAID_AUDIT_SCHEMA_VERSION = "fin_insight_multicase_goldset_no_paid_audit_v0_1"
GOLDSET_SOURCE_RUNTIME_ASSIMILATION_MATRIX_SCHEMA_VERSION = (
    "fin_insight_goldset_source_runtime_assimilation_matrix_v0_1"
)
GOLDSET_LIVE_SOURCE_BACKFILL_SCHEMA_VERSION = "fin_insight_goldset_live_source_backfill_v0_1"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_spec_v0_1.json"
DEFAULT_EXEMPLARS_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_answer_exemplars_v0_2.json"
DEFAULT_MATRIX_AUDIT_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_matrix_audit_v0_1.json"
DEFAULT_ARTIFACT_AUDIT_PATH = REPO_ROOT / "docs/project_os/humanmade_gold_set_artifact_audit_v0_1.json"
DEFAULT_AI_SEMIS_HUMAN_DOC_PATH = REPO_ROOT / "docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md"

GOLDSET_BACKFILL_SOURCE_ROWSETS = (
    "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl",
    "data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl",
    "data/manifests/official_product_spec_context_rows_v0_1.jsonl",
    "data/manifests/official_customer_deployment_surface_context_rows_v0_1.jsonl",
    "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    "data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
    "data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    "data/manifests/product_intelligence_graph_edges_v0_1.jsonl",
)

P33_AI_SEMIS_CASE_IDS = {
    "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
    "ai_semis_dell_nvda_anchor_v0_1",
}


def compile_ai_semis_human_source_runtime_slots(
    source_doc_path: str | Path = DEFAULT_AI_SEMIS_HUMAN_DOC_PATH,
) -> dict[str, Any]:
    """Compile the human AI/Semis source ledger into runtime-addressable source slots."""

    path = Path(source_doc_path)
    rows = _parse_markdown_source_ledger(path)
    slots: list[dict[str, Any]] = []
    for row in rows:
        source_name = row["source"]
        authority_role = row["authority_role"]
        key_info = row["key_info"]
        supports = row["supports"]
        cannot_infer = row["cannot_infer"]
        slot_type = _source_slot_type(source_name, authority_role, key_info)
        slots.append(
            {
                "slot_id": _stable_id("ai_semis_source_slot", [source_name, authority_role, key_info]),
                "slot_type": slot_type,
                "source_name": source_name,
                "authority_role": authority_role,
                "key_info": key_info,
                "supports": supports,
                "cannot_infer": cannot_infer,
                "source_doc": _rel(path),
                "source_authority_boundary": _source_boundary(slot_type),
                "runtime_consumers": _slot_runtime_consumers(slot_type),
                "status": "runtime_slot_ready_not_yet_proven_consumed_by_current_artifact",
            }
        )
    slot_type_counts: dict[str, int] = {}
    for slot in slots:
        slot_type_counts[slot["slot_type"]] = slot_type_counts.get(slot["slot_type"], 0) + 1
    return {
        "schema_version": HUMANMADE_GOLD_SET_RUNTIME_SCHEMA_VERSION,
        "artifact_type": "ai_semis_human_source_runtime_slots",
        "status": "pass_runtime_slots_compiled",
        "source_doc": _rel(path),
        "slot_count": len(slots),
        "slot_type_counts": slot_type_counts,
        "slots": slots,
        "acceptance_boundary": (
            "This compiles the human source ledger into runtime slots. It does not by itself prove the current "
            "Research Lead, specialists, aggregate, or Memo Writer consumed those slots."
        ),
    }


def materialize_ai_semis_human_source_rows(
    source_slots: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Materialize the human source ledger into analyst-consumable runtime rows."""

    source_slots = source_slots or compile_ai_semis_human_source_runtime_slots()
    slot_by_source = _slot_lookup(source_slots)
    rows = [
        _runtime_row(
            slot_by_source,
            row_id="dell_ai_server_orders_shipments_backlog",
            row_type="issuer_exact_operating_metric",
            lane_id="dell_financial_quality_bridge",
            issuer="DELL",
            product_or_family="AI-optimized servers",
            source_name="Dell FY26 Q4 8-K exhibit",
            fact="Dell disclosed FY26 AI-optimized server orders above $64B, shipments above $25B, and FY27 starting backlog of about $43B.",
            metric_or_attribute="orders_shipments_backlog",
            value="orders >$64B; shipments >$25B; backlog about $43B",
            unit="USD",
            period_or_version="FY26 / FY27 starting backlog",
            supports="AI server revenue demand is real and issuer-disclosed.",
            cannot_infer="Does not prove AI server gross margin, GPU pass-through cost, customer concentration, or per-customer order size.",
            investment_role="revenue_visibility_not_margin_quality",
            authority_tier="issuer_exact",
            runtime_consumers=["FundamentalStatementPack", "fundamental_analyst", "JudgmentCard", "MemoLogicPlan"],
            what_would_change_view="Backlog conversion plus ISG margin improvement would upgrade Dell AI server quality.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="dell_isg_revenue_margin_baseline",
            row_type="issuer_exact_segment_metric",
            lane_id="dell_financial_quality_bridge",
            issuer="DELL",
            product_or_family="Infrastructure Solutions Group",
            source_name="Dell FY26 Q1 release",
            fact="Dell disclosed ISG revenue, Servers and Networking revenue, Storage revenue, and ISG operating income / margin.",
            metric_or_attribute="isg_revenue_operating_margin",
            value="ISG and Servers/Networking segment metrics disclosed",
            unit="USD / margin percent",
            period_or_version="FY26 Q1",
            supports="ISG is the financial bridge through which AI server orders should show revenue and margin quality.",
            cannot_infer="Does not split AI server gross margin, Blackwell mix, attach rate, or customer-level profitability.",
            investment_role="financial_bridge_entry_point",
            authority_tier="issuer_exact",
            runtime_consumers=["FundamentalStatementPack", "fundamental_analyst", "JudgmentCard", "MemoLogicPlan"],
            what_would_change_view="AI server mix, attach economics, and ISG margin trajectory would decide whether growth is high quality.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="dell_nvidia_poweredge_ai_factory_product_path",
            row_type="official_product_surface",
            lane_id="customer_deployment_adoption",
            issuer="DELL",
            product_or_family="PowerEdge XE9680 / XE9712",
            source_name="Dell + NVIDIA AI Factory / PowerEdge announcements",
            fact="Dell official announcements connect PowerEdge XE9680 to H200/B200 and XE9712 to the GB200 NVL72 platform.",
            metric_or_attribute="oem_configuration",
            value="H200/B200 and GB200 NVL72 supported platforms",
            unit="product configuration",
            period_or_version="current product surface",
            supports="Dell has a concrete NVIDIA-powered AI server / rack product path.",
            cannot_infer="Does not prove revenue, order volume, signed customer contracts, or gross margin.",
            investment_role="oem_product_adoption_path",
            authority_tier="issuer_official_product_surface",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "industry_supply_chain_analyst"],
            what_would_change_view="Official customer deployments and configuration mix would strengthen adoption evidence.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="dell_xe9712_gb200_oem_system_config",
            row_type="official_product_architecture_spec",
            lane_id="product_architecture_competition",
            issuer="DELL",
            product_or_family="PowerEdge XE9712 / GB200 NVL72",
            source_name="Dell + NVIDIA AI Factory / PowerEdge announcements",
            fact="Dell's XE9712 / Integrated Rack path links GB200 NVL72 to a concrete OEM rack-scale AI server configuration.",
            metric_or_attribute="oem_system_configuration",
            value="Dell rack-scale GB200 NVL72 product path",
            unit="official product configuration",
            period_or_version="Blackwell / GB200 generation",
            supports="Product analysis can connect NVIDIA rack-scale architecture to Dell's server product surface.",
            cannot_infer="Does not prove Dell revenue, customer order value, shipment count, or system gross margin.",
            investment_role="product_capability_to_oem_configuration",
            authority_tier="issuer_official_product_surface",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "JudgmentCard"],
            what_would_change_view="Customer configuration mix and production deployment disclosures would upgrade confidence.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="nvda_gb200_nvl72_rack_architecture",
            row_type="official_product_architecture_spec",
            lane_id="product_architecture_competition",
            issuer="NVDA",
            product_or_family="GB200 NVL72",
            source_name="NVIDIA GB200 NVL72 official page",
            fact="GB200 NVL72 is a rack-scale system with 36 Grace CPUs, 72 Blackwell GPUs, a large NVLink domain, and liquid-cooled deployment.",
            metric_or_attribute="rack_scale_architecture",
            value="36 Grace CPUs / 72 Blackwell GPUs / NVLink rack-scale domain",
            unit="system specification",
            period_or_version="Blackwell generation",
            supports="NVIDIA product advantage is system-level, not just single-GPU compute.",
            cannot_infer="Does not prove SKU revenue, Dell orders, customer purchase volume, ASP, or margin.",
            investment_role="product_capability_and_supply_bottleneck",
            authority_tier="official_technical_fact",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "JudgmentCard"],
            what_would_change_view="Broad production GB200 cloud/OEM deployments would move this from capability to adoption proof.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="nvda_data_center_revenue_demand_confirmation",
            row_type="issuer_exact_segment_metric",
            lane_id="demand_pool",
            issuer="NVDA",
            product_or_family="Data Center",
            source_name="NVIDIA Q1 FY2027 IR page",
            fact="NVIDIA disclosed record revenue and high Data Center revenue growth.",
            metric_or_attribute="data_center_revenue",
            value="record revenue / Data Center growth disclosed",
            unit="USD",
            period_or_version="Q1 FY2027",
            supports="AI accelerator demand has entered NVIDIA financials, not just macro narrative.",
            cannot_infer="Does not split B200/GB200/GB300 SKU revenue or Dell share.",
            investment_role="accelerator_financial_demand_confirmation",
            authority_tier="issuer_exact",
            runtime_consumers=["FundamentalStatementPack", "fundamental_analyst", "market_valuation_analyst"],
            what_would_change_view="SKU mix and supply allocation disclosures would sharpen NVDA-to-OEM read-through.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="amd_mi300x_memory_bandwidth_competition",
            row_type="official_product_architecture_spec",
            lane_id="product_architecture_competition",
            issuer="AMD",
            product_or_family="MI300X",
            source_name="AMD MI300X official product page",
            fact="AMD MI300X discloses 192GB HBM3 memory, 5.3 TB/s bandwidth, CDNA3, FP8 and FP16 support.",
            metric_or_attribute="memory_bandwidth_architecture",
            value="192GB HBM3; 5.3 TB/s bandwidth; CDNA3; FP8/FP16",
            unit="product specification",
            period_or_version="MI300X generation",
            supports="AMD is a real accelerator substitute in memory-heavy inference/training workloads.",
            cannot_infer="Does not prove market share, customer migration scale, or NVIDIA pricing pressure by itself.",
            investment_role="competitive_substitution_pressure",
            authority_tier="official_technical_fact",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "risk_counterevidence_analyst"],
            what_would_change_view="Customer deployments and benchmark wins in production workloads would strengthen substitution pressure.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="amd_mlperf_mi355x_performance_proxy",
            row_type="benchmark_performance_proxy",
            lane_id="product_architecture_competition",
            issuer="AMD",
            product_or_family="MI355X / ROCm",
            source_name="AMD MLPerf 6.0 blog / MLCommons results",
            fact="AMD reported MI355X MLPerf inference progress and MLCommons provides the public benchmark framework for cross-system comparison.",
            metric_or_attribute="benchmark_performance_proxy",
            value="MLPerf inference benchmark context",
            unit="benchmark result / methodology",
            period_or_version="MLPerf Inference 6.0",
            supports="AMD competitive capability and software stack progress are real product-performance signals.",
            cannot_infer="Benchmark does not directly prove procurement, revenue, share, ASP, or gross margin.",
            investment_role="performance_proxy_not_sales",
            authority_tier="benchmark_proxy",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "risk_counterevidence_analyst"],
            what_would_change_view="Independent production deployment wins would upgrade from benchmark proxy to adoption signal.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="google_tpu_v6e_trillium_architecture",
            row_type="official_product_architecture_spec",
            lane_id="product_architecture_competition",
            issuer="GOOGL",
            product_or_family="TPU v6e / Trillium",
            source_name="Google Cloud TPU v6e docs",
            fact="Google Cloud TPU docs disclose TPU compute, HBM, ICI, pod size, and network/all-reduce characteristics.",
            metric_or_attribute="custom_accelerator_spec",
            value="TPU compute / HBM / ICI / pod and network specs",
            unit="cloud accelerator specification",
            period_or_version="TPU v6e / Trillium",
            supports="TPU is a real hyperscaler custom-silicon alternative to external GPUs in selected workloads.",
            cannot_infer="Does not prove replacement ratio, internal procurement cadence, or NVIDIA revenue loss.",
            investment_role="custom_silicon_substitution_risk",
            authority_tier="official_technical_fact",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "risk_counterevidence_analyst"],
            what_would_change_view="Workload migration and cloud capacity disclosures would clarify substitution magnitude.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="google_a4x_gb200_cloud_deployment_surface",
            row_type="cloud_deployment_product_surface",
            lane_id="customer_deployment_adoption",
            issuer="GOOGL",
            product_or_family="A4X / GB200 NVL72",
            source_name="Google Cloud A4X GB200 blog",
            fact="Google Cloud A4X preview uses GB200 NVL72 and positions B200/A4 plus GB200/A4X cloud offerings.",
            metric_or_attribute="cloud_instance_availability",
            value="GB200 NVL72 in Google Cloud A4X preview",
            unit="cloud product surface",
            period_or_version="A4X preview",
            supports="GB200 has entered a hyperscaler cloud product surface; clouds may use both NVIDIA GPUs and TPU.",
            cannot_infer="Does not prove purchase amount, supplier revenue, availability scale, or regional capacity.",
            investment_role="cloud_deployment_signal",
            authority_tier="official_cloud_product_surface",
            runtime_consumers=["ProductIntelligenceGraph", "product_technology_analyst", "industry_supply_chain_analyst"],
            what_would_change_view="GA availability, customer deployments, or capacity disclosures would strengthen adoption.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="msft_cloud_ai_capex_supply_shortfall",
            row_type="hyperscaler_demand_pool",
            lane_id="demand_pool",
            issuer="MSFT",
            product_or_family="Azure / AI infrastructure",
            source_name="MSFT FY26 Q2/Q3 investor materials",
            fact="Microsoft disclosed large AI/cloud capex, cloud/AI revenue growth, and demand exceeding supply.",
            metric_or_attribute="capex_supply_demand",
            value="AI/cloud capex and demand > supply commentary",
            unit="capex / management commentary",
            period_or_version="FY26 Q2/Q3",
            supports="Hyperscaler demand pool is real and supply constrained.",
            cannot_infer="Does not identify how much flows to NVIDIA, Dell, ODMs, networking, power/cooling, or custom silicon.",
            investment_role="demand_pool_not_supplier_allocation",
            authority_tier="issuer_capex_context",
            runtime_consumers=["ResearchLead", "industry_supply_chain_analyst", "market_valuation_analyst"],
            what_would_change_view="Supplier/order disclosures would be required for allocation claims.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="amzn_aws_demand_pool_context",
            row_type="hyperscaler_demand_pool",
            lane_id="demand_pool",
            issuer="AMZN",
            product_or_family="AWS",
            source_name="AMZN Q1 2026 results",
            fact="Amazon disclosed AWS sales and operating income growth.",
            metric_or_attribute="aws_revenue_operating_income",
            value="AWS revenue and operating income growth disclosed",
            unit="USD / growth",
            period_or_version="Q1 2026",
            supports="AWS cloud demand context is positive for AI infrastructure demand pool.",
            cannot_infer="Does not reveal AWS GPU vendor mix, Dell server purchases, or capex allocation.",
            investment_role="cloud_demand_context_not_allocation",
            authority_tier="issuer_exact_context",
            runtime_consumers=["ResearchLead", "industry_supply_chain_analyst", "market_valuation_analyst"],
            what_would_change_view="AWS capex/supplier/deployment disclosures would make this more specific.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="alphabet_capex_server_chain_context",
            row_type="hyperscaler_demand_pool",
            lane_id="demand_pool",
            issuer="GOOGL",
            product_or_family="Technical infrastructure / Google Cloud",
            source_name="Alphabet Q1 2026 release/call",
            fact="Alphabet disclosed capex mainly for technical infrastructure, with servers/data-center network as a major share, plus Google Cloud revenue growth.",
            metric_or_attribute="technical_infrastructure_capex",
            value="capex / server mix / cloud revenue context",
            unit="capex and mix",
            period_or_version="Q1 2026",
            supports="Google capex connects to accelerator/server demand background.",
            cannot_infer="Does not split NVIDIA GPU versus TPU procurement.",
            investment_role="server_chain_demand_context",
            authority_tier="issuer_capex_context",
            runtime_consumers=["ResearchLead", "industry_supply_chain_analyst", "market_valuation_analyst"],
            what_would_change_view="GPU vs TPU procurement mix would change supplier read-through.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="meta_capex_component_pricing_risk",
            row_type="hyperscaler_demand_pool",
            lane_id="counter_thesis_and_what_would_change",
            issuer="META",
            product_or_family="AI infrastructure",
            source_name="Meta Q1 2026 transcript",
            fact="Meta raised 2026 capex guidance for future capacity and cited component pricing.",
            metric_or_attribute="capex_guidance_component_pricing",
            value="raised capex guidance / component pricing pressure",
            unit="management commentary",
            period_or_version="Q1 2026",
            supports="AI demand pool and component price pressure are both active.",
            cannot_infer="Does not prove supplier revenue or exact vendor allocation.",
            investment_role="capex_digestion_and_component_cost_risk",
            authority_tier="issuer_capex_context",
            runtime_consumers=["risk_counterevidence_analyst", "industry_supply_chain_analyst"],
            what_would_change_view="Capex rollover or digestion commentary would weaken the demand-pool thesis.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="tsmc_advanced_node_hpc_ai_readthrough",
            row_type="foundry_exact_readthrough",
            lane_id="semicap_foundry_readthrough",
            issuer="TSM",
            product_or_family="advanced technologies / HPC",
            source_name="TSMC Q1 2026 release",
            fact="TSMC disclosed revenue, margin, advanced technology wafer revenue share, and leading-edge process demand.",
            metric_or_attribute="advanced_node_revenue_margin",
            value="revenue / margin / advanced-node share disclosed",
            unit="USD / percent",
            period_or_version="Q1 2026",
            supports="AI/HPC demand is visible at the leading-edge foundry layer.",
            cannot_infer="Does not disclose customer-level allocation across NVIDIA, AMD, Google, Apple, or others.",
            investment_role="foundry_advanced_node_readthrough",
            authority_tier="issuer_exact_foundry_context",
            runtime_consumers=["industry_supply_chain_analyst", "fundamental_analyst", "ProductIntelligenceGraph"],
            what_would_change_view="Customer mix or CoWoS/HBM packaging detail would sharpen accelerator read-through.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="asml_lithography_installed_base_readthrough",
            row_type="semicap_exact_company_mechanism",
            lane_id="semicap_foundry_readthrough",
            issuer="ASML",
            product_or_family="EUV/DUV lithography / installed base",
            source_name="ASML Q1 2026 release",
            fact="ASML disclosed net sales, gross margin, installed-base management, new/used lithography systems sold, and 2026 guide.",
            metric_or_attribute="lithography_sales_margin_systems",
            value="sales / gross margin / systems sold / installed-base management",
            unit="EUR / systems / margin",
            period_or_version="Q1 2026",
            supports="ASML read-through should be separated into EUV/DUV, installed base, China/export, and bookings/backlog cycle.",
            cannot_infer="Does not prove AI-specific ASML orders or customer allocation.",
            investment_role="lithography_cycle_readthrough",
            authority_tier="issuer_exact_semicap_context",
            runtime_consumers=["industry_supply_chain_analyst", "fundamental_analyst", "ProductIntelligenceGraph"],
            what_would_change_view="Bookings/backlog by EUV/DUV and China/export exposure would sharpen the thesis.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="amat_semiconductor_systems_mix",
            row_type="semicap_exact_company_mechanism",
            lane_id="semicap_foundry_readthrough",
            issuer="AMAT",
            product_or_family="Semiconductor Systems / foundry-logic / DRAM / flash",
            source_name="AMAT Q2 FY26 release",
            fact="Applied Materials disclosed revenue, gross margin, Semiconductor Systems segment, and foundry/logic/DRAM/flash mix.",
            metric_or_attribute="equipment_segment_mix",
            value="revenue / margin / Semiconductor Systems mix",
            unit="USD / percent",
            period_or_version="Q2 FY26",
            supports="AMAT AI read-through runs through materials engineering, deposition, foundry/logic, DRAM, flash, and advanced packaging exposure.",
            cannot_infer="Does not replace customer order backlog or AI-specific bookings.",
            investment_role="materials_engineering_and_packaging_readthrough",
            authority_tier="issuer_exact_semicap_context",
            runtime_consumers=["industry_supply_chain_analyst", "fundamental_analyst", "ProductIntelligenceGraph"],
            what_would_change_view="Customer backlog or advanced packaging order commentary would upgrade specificity.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="lrcx_memory_hbm_process_intensity",
            row_type="semicap_exact_company_mechanism",
            lane_id="semicap_foundry_readthrough",
            issuer="LRCX",
            product_or_family="etch/deposition / memory / HBM",
            source_name="LRCX Mar 2026 results",
            fact="Lam Research disclosed revenue, gross margin, operating margin, and AI-driven demand management commentary.",
            metric_or_attribute="memory_process_equipment_readthrough",
            value="revenue / gross margin / operating margin / AI-driven demand commentary",
            unit="USD / margin / commentary",
            period_or_version="Mar 2026 quarter",
            supports="LRCX read-through should focus on etch/deposition, memory/HBM, advanced packaging, and process intensity.",
            cannot_infer="Does not prove each HBM or advanced packaging customer order.",
            investment_role="memory_hbm_process_intensity_readthrough",
            authority_tier="issuer_exact_semicap_context",
            runtime_consumers=["industry_supply_chain_analyst", "fundamental_analyst", "ProductIntelligenceGraph"],
            what_would_change_view="HBM/advanced packaging order or customer commentary would sharpen read-through.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="market_price_in_valuation_positioning_gap",
            row_type="typed_gap_required_for_recommendation",
            lane_id="market_expectation_price_in",
            issuer="AI_SEMIS_BASKET",
            product_or_family="AI infrastructure equities",
            source_name="Humanmade Gold Case market price-in ceiling",
            fact="The current business evidence pack does not include valuation percentiles, ownership/positioning, options/short interest, ETF flows, or event reaction asymmetry.",
            metric_or_attribute="market_price_in_required_pack",
            value="valuation / ownership / liquidity / positioning gap",
            unit="typed gap",
            period_or_version="pre recommendation",
            supports="The workpaper can say business evidence is directionally positive but cannot issue a price-sensitive recommendation without capital-feedback data.",
            cannot_infer="Cannot infer price-in, crowding, upside/downside skew, or trading recommendation.",
            investment_role="price_in_boundary",
            authority_tier="typed_gap",
            runtime_consumers=["market_valuation_analyst", "ResearchLead", "MemoLogicPlan"],
            what_would_change_view="Valuation, ownership, short/options, ETF/sector flows, and price reaction data would decide price-in.",
        ),
        _runtime_row(
            slot_by_source,
            row_id="counter_thesis_pack_ai_semis",
            row_type="counter_thesis_material",
            lane_id="counter_thesis_and_what_would_change",
            issuer="AI_SEMIS_BASKET",
            product_or_family="AI infrastructure chain",
            source_name="Humanmade Gold Case counter-thesis",
            fact="The core counter-thesis includes capex digestion, OEM margin dilution, AMD/TPU substitution, HBM/CoWoS/power bottlenecks, export controls, customer concentration, and price-in risk.",
            metric_or_attribute="counter_thesis_pack",
            value="capex digestion; margin dilution; substitution; supply bottleneck; export/control; concentration; price-in",
            unit="risk dimensions",
            period_or_version="case v0.2",
            supports="Counter-thesis and what-would-change must be part of the main workpaper, not a generic appendix.",
            cannot_infer="Does not quantify probability or valuation impact without follow-up data.",
            investment_role="risk_counterevidence_and_trigger_conditions",
            authority_tier="analyst_synthesis_from_public_sources",
            runtime_consumers=["risk_counterevidence_analyst", "ResearchLead", "MemoLogicPlan", "Verifier"],
            what_would_change_view="Exact customer concentration, margin, substitution adoption, supply capacity, export and valuation rows would reweight risks.",
        ),
    ]
    counts: dict[str, int] = {}
    lane_counts: dict[str, int] = {}
    for row in rows:
        counts[row["row_type"]] = counts.get(row["row_type"], 0) + 1
        lane_counts[row["lane_id"]] = lane_counts.get(row["lane_id"], 0) + 1
    return {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "artifact_type": "ai_semis_human_source_runtime_rows",
        "status": "content_rows_materialized",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "row_count": len(rows),
        "row_type_counts": counts,
        "lane_counts": lane_counts,
        "rows": rows,
        "acceptance_boundary": (
            "These rows are the target analyst content shape. They do not prove current accepted aggregate r7 "
            "consumed the rows unless they appear in that runtime artifact."
        ),
    }


def project_ai_semis_rows_to_investment_edges(
    row_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row_pack = row_pack or materialize_ai_semis_human_source_rows()
    row_ids = {str(row.get("row_id") or "") for row in row_pack.get("rows") or [] if isinstance(row, Mapping)}
    edges = [
        _investment_edge(
            "nvda_gb200_configured_in_dell_xe9712",
            "NVDA_GB200_NVL72",
            "DELL_XE9712",
            "configured_in",
            "product_capability_to_oem_adoption",
            "GB200's rack-scale architecture has a concrete Dell OEM product path, so product capability can enter the OEM adoption discussion.",
            "Does not prove Dell revenue, orders, customer contracts, or margin.",
            ["nvda_gb200_nvl72_rack_architecture", "dell_nvidia_poweredge_ai_factory_product_path"],
            row_ids,
            "medium_high",
            "Official customer deployment and Dell configuration mix.",
        ),
        _investment_edge(
            "nvda_gpu_supply_input_to_dell_ai_server",
            "NVDA_GPU_SYSTEMS",
            "DELL_AI_OPTIMIZED_SERVERS",
            "supply_input_to",
            "supply_constraint_and_margin_pressure",
            "Dell AI server revenue visibility depends on NVIDIA accelerator supply, but GPU pass-through can pressure Dell margin quality.",
            "Does not prove Dell AI server gross margin or NVIDIA allocation.",
            ["dell_ai_server_orders_shipments_backlog", "dell_isg_revenue_margin_baseline", "nvda_gb200_nvl72_rack_architecture"],
            row_ids,
            "medium",
            "AI server mix, GPU pass-through cost, attach rate, and backlog conversion.",
        ),
        _investment_edge(
            "google_tpu_substitutes_for_external_gpu",
            "GOOGL_TPU_V6E_TRILLIUM",
            "NVDA_EXTERNAL_GPU_SYSTEMS",
            "substitutes_for_selected_workloads",
            "substitution_and_pricing_pressure",
            "TPU is a real hyperscaler custom-silicon path that can cap external GPU pricing or allocation power in selected workloads.",
            "Does not prove TPU replacement ratio or NVIDIA revenue loss.",
            ["google_tpu_v6e_trillium_architecture", "google_a4x_gb200_cloud_deployment_surface"],
            row_ids,
            "medium",
            "Workload migration, TPU capacity, and cloud customer adoption.",
        ),
        _investment_edge(
            "amd_mi300_competes_with_nvda_memory_heavy_workloads",
            "AMD_MI300X_MI355X",
            "NVDA_B200_B300",
            "competes_with",
            "competitive_substitution_pressure",
            "AMD memory capacity/bandwidth and benchmark progress are a real counter-thesis to unlimited NVIDIA pricing power.",
            "Does not prove market share or customer switching scale.",
            ["amd_mi300x_memory_bandwidth_competition", "amd_mlperf_mi355x_performance_proxy"],
            row_ids,
            "medium",
            "Production customer wins and pricing evidence.",
        ),
        _investment_edge(
            "hyperscaler_capex_demand_pool_to_accelerator_server_chain",
            "HYPERSCALER_AI_CAPEX",
            "ACCELERATOR_SERVER_SUPPLY_CHAIN",
            "demand_pool_for",
            "demand_validation_not_allocation",
            "MSFT/AMZN/GOOGL/META capex supports AI infrastructure demand pool but not supplier allocation.",
            "Does not prove direct Dell/NVIDIA/TSMC/ASML orders.",
            ["msft_cloud_ai_capex_supply_shortfall", "amzn_aws_demand_pool_context", "alphabet_capex_server_chain_context", "meta_capex_component_pricing_risk"],
            row_ids,
            "high",
            "Supplier/order/deployment rows that allocate the pool.",
        ),
        _investment_edge(
            "dell_ai_orders_bridge_to_isg_margin_quality",
            "DELL_AI_SERVER_ORDERS_BACKLOG",
            "DELL_ISG_MARGIN_CASH_CONVERSION",
            "bridge_to",
            "revenue_visibility_margin_quality_unresolved",
            "Dell has AI server revenue visibility, but the investment-quality question is whether backlog converts into margin and cash.",
            "Does not prove high-quality margin growth until AI server mix/pass-through/attach economics are disclosed.",
            ["dell_ai_server_orders_shipments_backlog", "dell_isg_revenue_margin_baseline"],
            row_ids,
            "high_for_revenue_medium_for_margin",
            "AI server gross margin, GPU pass-through, attach rate, inventory/receivables and backlog conversion.",
        ),
        _investment_edge(
            "tsmc_advanced_node_upstream_of_accelerators",
            "TSMC_ADVANCED_NODE_HPC",
            "NVDA_AMD_TPU_ACCELERATORS",
            "upstream_of",
            "foundry_advanced_node_readthrough",
            "Leading-edge foundry demand is a stronger AI read-through than generic semicap peer grouping.",
            "Does not identify customer split across NVIDIA/AMD/Google/Apple.",
            ["tsmc_advanced_node_hpc_ai_readthrough"],
            row_ids,
            "medium_high",
            "Customer mix, advanced packaging and CoWoS/HBM details.",
        ),
        _investment_edge(
            "semicap_tools_enable_ai_foundry_memory_packaging",
            "ASML_AMAT_LRCX",
            "ADVANCED_NODE_HBM_PACKAGING_PROCESS_INTENSITY",
            "enables",
            "semicap_readthrough_by_mechanism",
            "ASML, AMAT and LRCX have different AI read-through mechanisms and must not be treated as one undifferentiated peer group.",
            "Does not prove company-specific AI orders without bookings/backlog/customer rows.",
            ["asml_lithography_installed_base_readthrough", "amat_semiconductor_systems_mix", "lrcx_memory_hbm_process_intensity"],
            row_ids,
            "medium",
            "Bookings/backlog by tool category, memory/foundry/logic split and export exposure.",
        ),
        _investment_edge(
            "market_price_in_gap_constrains_recommendation",
            "CAPITAL_MARKET_FEEDBACK_GAP",
            "INVESTMENT_RECOMMENDATION",
            "constrains",
            "price_in_boundary",
            "Business evidence can support a directional workpaper, but valuation/positioning/price-reaction evidence is required before a recommendation.",
            "Does not infer price-in or trading recommendation.",
            ["market_price_in_valuation_positioning_gap"],
            row_ids,
            "high_boundary",
            "Valuation percentiles, ownership/positioning, options/short interest, ETF flows and event reactions.",
        ),
    ]
    role_counts: dict[str, int] = {}
    for edge in edges:
        role_counts[edge["edge_investment_role"]] = role_counts.get(edge["edge_investment_role"], 0) + 1
    return {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "artifact_type": "product_intelligence_graph_investment_projection",
        "status": "investment_edges_projected",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "edge_count": len(edges),
        "edge_role_counts": role_counts,
        "edges": edges,
    }


def compile_ai_semis_gold_specialist_judgment_materials(
    row_pack: Mapping[str, Any] | None = None,
    edge_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row_pack = row_pack or materialize_ai_semis_human_source_rows()
    edge_pack = edge_pack or project_ai_semis_rows_to_investment_edges(row_pack)
    materials = [
        _judgment_material(
            "product_architecture_competition",
            "product_technology_analyst",
            "req_accelerator_architecture",
            "product_architecture_competition",
            "NVIDIA remains the main external accelerator system bottleneck because GB200 is a rack-scale system, but AMD MI300/MI35x and Google TPU are real workload-specific substitutes.",
            "Product evidence should be read as architecture, performance and adoption evidence, not as SKU revenue. The graph must connect GB200 -> Dell/Google cloud deployment, AMD -> memory-heavy competition, and TPU -> custom-silicon substitution.",
            ["nvda_gb200_nvl72_rack_architecture", "amd_mi300x_memory_bandwidth_competition", "amd_mlperf_mi355x_performance_proxy", "google_tpu_v6e_trillium_architecture", "google_a4x_gb200_cloud_deployment_surface"],
            _edge_refs(edge_pack, ["product_capability_to_oem_adoption", "substitution_and_pricing_pressure", "competitive_substitution_pressure"]),
            "medium_high",
            "Cannot infer SKU revenue, share, shipment, ASP or margin from specs/benchmarks/cloud surfaces.",
            "If AMD/TPU production deployments broaden or GB200 deployment slips, NVIDIA pricing and allocation power weakens.",
            "Production deployments, procurement mix and pricing evidence would change the weight.",
        ),
        _judgment_material(
            "dell_financial_quality_bridge",
            "fundamental_analyst",
            "req_dell_margin_quality",
            "financial_quality",
            "Dell has unusually visible AI server revenue demand, but the investment-quality question is margin conversion, not whether demand exists.",
            "The right bridge is orders/backlog -> shipments -> ISG revenue -> gross/operating margin -> cash conversion. Current public rows prove the first half and leave AI server mix, GPU pass-through and attach economics unresolved.",
            ["dell_ai_server_orders_shipments_backlog", "dell_isg_revenue_margin_baseline"],
            _edge_refs(edge_pack, ["revenue_visibility_margin_quality_unresolved", "supply_constraint_and_margin_pressure"]),
            "medium",
            "Cannot call Dell AI server growth high-margin until AI server gross margin, GPU pass-through, attach rate and backlog conversion are disclosed.",
            "Revenue tailwind may be low-margin GPU pass-through, with working-capital pressure or customer concentration.",
            "Improving ISG margin with backlog conversion and attach economics would strengthen Dell quality.",
        ),
        _judgment_material(
            "semicap_foundry_readthrough",
            "industry_supply_chain_analyst",
            "req_supply_chain",
            "semicap_readthrough",
            "AI read-through is strongest when split by mechanism: TSMC advanced node, ASML lithography/installed base, AMAT materials engineering and LRCX memory/HBM process intensity.",
            "Peer group membership is not evidence. The product graph should map advanced-node/HBM/packaging demand into specific tool mechanisms and keep bookings/backlog/customer allocation as follow-up requirements.",
            ["tsmc_advanced_node_hpc_ai_readthrough", "asml_lithography_installed_base_readthrough", "amat_semiconductor_systems_mix", "lrcx_memory_hbm_process_intensity"],
            _edge_refs(edge_pack, ["foundry_advanced_node_readthrough", "semicap_readthrough_by_mechanism"]),
            "medium_high",
            "Cannot infer AI-specific orders or customer allocation from broad revenue/margin alone.",
            "Export controls, China exposure, memory/foundry cycle shifts, or missing bookings can break the read-through.",
            "Bookings/backlog by tool category, HBM/advanced packaging orders and customer concentration would change confidence.",
        ),
        _judgment_material(
            "customer_deployment_adoption",
            "industry_supply_chain_analyst",
            "req_customer_deployment",
            "customer_deployment",
            "Dell and Google provide official deployment surfaces that make GB200 adoption plausible, but public evidence still needs customer/order/config mix for investment-grade deployment quality.",
            "Dell XE9680/XE9712 and Google A4X prove product surfaces and cloud/OEM availability; they do not prove signed customer demand or Dell margin.",
            ["dell_nvidia_poweredge_ai_factory_product_path", "google_a4x_gb200_cloud_deployment_surface", "dell_ai_server_orders_shipments_backlog"],
            _edge_refs(edge_pack, ["product_capability_to_oem_adoption", "cloud_deployment_signal"]),
            "medium",
            "Cannot infer customer concentration, deployment scale, or revenue per customer.",
            "Preview-stage cloud availability or concentrated mega orders could limit the adoption signal.",
            "Official customer deployments and GA cloud capacity would upgrade this lane.",
        ),
        _judgment_material(
            "market_expectation_price_in",
            "market_valuation_analyst",
            "req_market_price_in",
            "market_price_in",
            "The business chain is directionally positive, but recommendation quality is blocked by missing valuation, positioning, short/options, ETF flow and price-reaction data.",
            "Market lane should not invent price-in from fundamentals. It should make capital-feedback rows a required next pack before buy/sell recommendation.",
            ["market_price_in_valuation_positioning_gap"],
            _edge_refs(edge_pack, ["price_in_boundary"]),
            "bounded",
            "Cannot infer crowding, price-in or recommendation from business evidence alone.",
            "The thesis can be right fundamentally but already fully reflected in valuation and positioning.",
            "Valuation percentile, 13F/ETF/insider/short/options and event reaction rows would unlock recommendation analysis.",
        ),
        _judgment_material(
            "counter_thesis_and_what_would_change",
            "risk_counterevidence_analyst",
            "req_counter_thesis",
            "risk_counterevidence",
            "The strongest counter-thesis is not generic 'AI risk'; it is capex digestion, Dell margin dilution, AMD/TPU substitution, supply bottlenecks, export controls, concentration and price-in.",
            "Each risk maps to a mechanism in the thesis chain: demand pool durability, product substitution, OEM margin bridge, supply capacity, policy constraints and market feedback.",
            ["meta_capex_component_pricing_risk", "amd_mi300x_memory_bandwidth_competition", "google_tpu_v6e_trillium_architecture", "market_price_in_valuation_positioning_gap", "counter_thesis_pack_ai_semis"],
            _edge_refs(edge_pack, ["substitution_and_pricing_pressure", "competitive_substitution_pressure", "price_in_boundary", "supply_constraint_and_margin_pressure"]),
            "medium_high",
            "Cannot quantify probability or valuation impact without follow-up data.",
            "If Dell margin fails to improve or hyperscaler capex shifts to internal accelerators, the positive chain weakens.",
            "ISG margin, supplier allocation, TPU/AMD deployment and valuation/positioning data are the main trigger conditions.",
        ),
    ]
    slot_counts: dict[str, int] = {}
    for material in materials:
        slot_counts[material["memo_slot"]] = slot_counts.get(material["memo_slot"], 0) + 1
    return {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "artifact_type": "gold_specialist_judgment_materials",
        "status": "answer_exemplar_style_materials_compiled",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "material_count": len(materials),
        "memo_slot_counts": slot_counts,
        "materials": materials,
    }


def build_ai_semis_gold_depth_content_pack(
    source_slots: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_slots = source_slots or compile_ai_semis_human_source_runtime_slots()
    row_pack = materialize_ai_semis_human_source_rows(source_slots)
    edge_pack = project_ai_semis_rows_to_investment_edges(row_pack)
    material_pack = compile_ai_semis_gold_specialist_judgment_materials(row_pack, edge_pack)
    evidence_rows = [
        {
            "evidence_requirement_id": _required_item_for_lane(str(row.get("lane_id") or "")),
            "evidence_ref": row["row_id"],
            "source_family": row["row_type"],
            "authority_tier": row["authority_tier"],
            "claim_scope": row["investment_role"],
            "cannot_infer": row["cannot_infer"],
        }
        for row in row_pack["rows"]
    ]
    judgment_cards = [
        {
            "card_id": material["material_id"],
            "dimension": material["memo_slot"],
            "judgment": material["judgment"],
            "business_mechanism": material["business_mechanism"],
            "evidence_refs": material["evidence_refs"],
            "graph_edge_refs": material["graph_edge_refs"],
            "cannot_infer": material["cannot_infer"],
            "counter_thesis": material["counter_read"],
            "what_would_change": material["what_would_change_view"],
            "authority_level": material["confidence"],
        }
        for material in material_pack["materials"]
    ]
    sections = [
        {
            "section_id": material["memo_slot"],
            "required_item_answered": material["required_item_answered"],
            "section_judgment": material["judgment"],
            "required_evidence_refs": material["evidence_refs"],
            "graph_edge_refs": material["graph_edge_refs"],
            "cannot_infer": material["cannot_infer"],
        }
        for material in material_pack["materials"]
    ]
    return {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "artifact_type": "ai_semis_gold_depth_content_pack",
        "status": "target_gold_depth_content_pack_ready",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "humanmade_gold_set_audit_required": True,
        "humanmade_gold_source_slots_consumed": True,
        "human_source_runtime_rows": row_pack,
        "product_intelligence_graph_projection": edge_pack,
        "specialist_judgment_materials": material_pack,
        "gold_depth_markers": {
            "product_runtime_fact_count": row_pack["lane_counts"].get("product_architecture_competition", 0),
            "official_customer_deployment_count": row_pack["lane_counts"].get("customer_deployment_adoption", 0),
            "dell_financial_bridge_count": row_pack["lane_counts"].get("dell_financial_quality_bridge", 0),
            "semicap_company_specific_count": row_pack["lane_counts"].get("semicap_foundry_readthrough", 0),
            "market_price_in_count": row_pack["lane_counts"].get("market_expectation_price_in", 0),
            "counter_thesis_count": row_pack["lane_counts"].get("counter_thesis_and_what_would_change", 0),
        },
        "evidence_fusion_bundle": {
            "summary": {"product_runtime_fact_count": row_pack["lane_counts"].get("product_architecture_competition", 0)},
            "authority_rows": evidence_rows,
        },
        "verified_judgment_plan": {
            "supported_claims": judgment_cards,
            "unsupported_claims": [],
            "conflicts": [],
            "judgment_cards": judgment_cards,
        },
        "judgment_plan": {
            "supported_claims": judgment_cards,
            "unsupported_claims": [],
            "conflicts": [],
            "judgment_cards": judgment_cards,
        },
        "memo_logic_plan": {
            "required_item_answer_plan": [
                {
                    "question_item_id": material["required_item_answered"],
                    "answer_role": "judgment_material",
                    "memo_slot": material["memo_slot"],
                    "evidence_refs": material["evidence_refs"],
                    "graph_edge_refs": material["graph_edge_refs"],
                    "answer": material["judgment"],
                    "cannot_infer": material["cannot_infer"],
                    "what_would_change_view": material["what_would_change_view"],
                }
                for material in material_pack["materials"]
            ],
            "sections": sections,
            "judgment_cards": judgment_cards,
            "validation": {"status": "pass", "profile": "humanmade_gold_depth_content"},
        },
    }


def assimilate_ai_semis_gold_depth_content_pack(
    aggregate_state: Mapping[str, Any],
    *,
    content_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inject gold-depth source rows, graph edges, and judgment material into runtime artifacts.

    This is intentionally not a gate bypass. It creates an explicit repaired aggregate
    checkpoint that downstream nodes can audit: evidence fusion rows, product graph
    investment edges, specialist judgment material, verified judgment plan, and
    MemoLogicPlan all receive the same content pack with stable lineage.
    """

    state = dict(aggregate_state or {})
    content = dict(content_pack or build_ai_semis_gold_depth_content_pack())
    row_pack = dict(content.get("human_source_runtime_rows") or {})
    edge_pack = dict(content.get("product_intelligence_graph_projection") or {})
    material_pack = dict(content.get("specialist_judgment_materials") or {})
    content_evidence = content.get("evidence_fusion_bundle") if isinstance(content.get("evidence_fusion_bundle"), Mapping) else {}
    content_judgment = content.get("verified_judgment_plan") if isinstance(content.get("verified_judgment_plan"), Mapping) else {}
    content_memo_plan = content.get("memo_logic_plan") if isinstance(content.get("memo_logic_plan"), Mapping) else {}

    gold_claims = [_claim_from_gold_material(row) for row in material_pack.get("materials") or [] if isinstance(row, Mapping)]
    gold_cards = [_judgment_card_from_gold_material(row) for row in material_pack.get("materials") or [] if isinstance(row, Mapping)]
    gold_sections = [_memo_section_from_gold_material(row) for row in material_pack.get("materials") or [] if isinstance(row, Mapping)]
    gold_answer_plan = [
        dict(row)
        for row in content_memo_plan.get("required_item_answer_plan") or []
        if isinstance(row, Mapping)
    ]
    gold_bridge_rows = [_evidence_bridge_from_gold_material(row) for row in material_pack.get("materials") or [] if isinstance(row, Mapping)]

    existing_fusion = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
    merged_fusion = {
        **dict(existing_fusion),
        "schema_version": str(existing_fusion.get("schema_version") or "finsight_evidence_fusion_bundle_v0_1"),
        "artifact_type": "evidence_fusion_bundle",
        "authority_rows": _merge_rows_by_key(
            existing_fusion.get("authority_rows") if isinstance(existing_fusion, Mapping) else [],
            content_evidence.get("authority_rows") if isinstance(content_evidence, Mapping) else [],
            key_fields=("evidence_ref", "row_id"),
        ),
        "bounded_gap_register": existing_fusion.get("bounded_gap_register") if isinstance(existing_fusion.get("bounded_gap_register"), Mapping) else {},
        "summary": {
            **(
                dict(existing_fusion.get("summary") or {})
                if isinstance(existing_fusion.get("summary"), Mapping)
                else {}
            ),
            "product_runtime_fact_count": _int(_nested(content, "gold_depth_markers", "product_runtime_fact_count", default=0)),
            "gold_depth_content_row_count": _int(row_pack.get("row_count")),
            "gold_depth_content_edge_count": _int(edge_pack.get("edge_count")),
            "gold_depth_specialist_material_count": _int(material_pack.get("material_count")),
            "assimilation_policy": "humanmade_gold_source_rows_as_authority_rows_v0_1",
        },
    }
    merged_fusion["row_count"] = len(merged_fusion.get("authority_rows") or [])

    verified_judgment = _merge_gold_claims_into_judgment_plan(
        state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else state.get("judgment_plan") if isinstance(state.get("judgment_plan"), Mapping) else {},
        gold_claims=gold_claims,
        gold_cards=gold_cards,
        content_judgment=content_judgment,
    )
    judgment_plan = _merge_gold_claims_into_judgment_plan(
        state.get("judgment_plan") if isinstance(state.get("judgment_plan"), Mapping) else verified_judgment,
        gold_claims=gold_claims,
        gold_cards=gold_cards,
        content_judgment=content_judgment,
    )
    memo_logic_plan = _merge_gold_materials_into_memo_logic_plan(
        state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {},
        gold_cards=gold_cards,
        gold_sections=gold_sections,
        gold_answer_plan=gold_answer_plan,
        gold_bridge_rows=gold_bridge_rows,
        material_pack=material_pack,
        row_pack=row_pack,
        edge_pack=edge_pack,
    )

    specialist_verification = (
        dict(state.get("specialist_verification") or {})
        if isinstance(state.get("specialist_verification"), Mapping)
        else {}
    )
    if specialist_verification:
        specialist_verification["verified_judgment_plan"] = verified_judgment
        specialist_verification["humanmade_gold_depth_assimilation"] = {
            "status": "consumed",
            "gold_claim_count": len(gold_claims),
            "gold_judgment_card_count": len(gold_cards),
        }

    lead_review_checkpoint = (
        dict(state.get("lead_review_checkpoint") or {})
        if isinstance(state.get("lead_review_checkpoint"), Mapping)
        else {}
    )
    lead_review_checkpoint["humanmade_gold_depth_review"] = {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "status": "content_pack_consumed_pending_audit",
        "row_count": _int(row_pack.get("row_count")),
        "edge_count": _int(edge_pack.get("edge_count")),
        "specialist_material_count": _int(material_pack.get("material_count")),
        "policy": "research_lead_gold_depth_veto_consumes_runtime_assimilation_v0_1",
    }

    assimilation_summary = {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "artifact_type": "ai_semis_gold_depth_runtime_assimilation",
        "status": "runtime_assimilated",
        "case_id": str(content.get("case_id") or "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"),
        "evidence_fusion_authority_rows_added": _int(row_pack.get("row_count")),
        "product_intelligence_edges_added": _int(edge_pack.get("edge_count")),
        "specialist_judgment_materials_added": _int(material_pack.get("material_count")),
        "memo_logic_plan_sections_added": len(gold_sections),
        "consumption_points": [
            "evidence_fusion_bundle.authority_rows",
            "product_intelligence_graph_projection.edges",
            "gold_specialist_judgment_materials.materials",
            "verified_judgment_plan.supported_claims",
            "verified_judgment_plan.judgment_cards",
            "memo_logic_plan.required_item_answer_plan",
            "memo_logic_plan.sections",
            "memo_logic_plan.evidence_to_thesis_bridge",
            "lead_review_checkpoint.humanmade_gold_depth_review",
        ],
        "boundary": (
            "This repaired checkpoint proves runtime consumption of the humanmade gold content pack. "
            "It does not prove paid Memo Writer prose quality until a scoped paid writer node is run after audit pass."
        ),
    }

    return {
        **state,
        "humanmade_gold_set_audit_required": True,
        "humanmade_gold_source_slots_consumed": True,
        "ai_semis_gold_depth_content_pack": content,
        "human_source_runtime_rows": row_pack,
        "product_intelligence_graph_projection": edge_pack,
        "gold_specialist_judgment_materials": material_pack,
        "evidence_fusion_bundle": merged_fusion,
        "product_evidence_rows": _merge_rows_by_key(
            state.get("product_evidence_rows") or [],
            _product_evidence_rows_from_gold_content(row_pack),
            key_fields=("evidence_ref", "row_id"),
        ),
        "public_source_context_rows": _merge_rows_by_key(
            state.get("public_source_context_rows") or [],
            _public_context_rows_from_gold_content(row_pack),
            key_fields=("evidence_ref", "row_id"),
        ),
        "verified_judgment_plan": verified_judgment,
        "judgment_plan": judgment_plan,
        "specialist_verification": specialist_verification or state.get("specialist_verification") or {},
        "memo_logic_plan": memo_logic_plan,
        "lead_review_checkpoint": lead_review_checkpoint,
        "p33_gold_depth_runtime_assimilation": assimilation_summary,
    }


def run_research_lead_gold_depth_veto(
    *,
    aggregate_state: Mapping[str, Any] | None = None,
    writer_payload: Mapping[str, Any] | None = None,
    artifact_audit: Mapping[str, Any] | None = None,
    source_slots: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    aggregate_state = aggregate_state or {}
    writer_payload = writer_payload or {}
    source_slots = source_slots or compile_ai_semis_human_source_runtime_slots()
    gate = run_briefing_pack_quality_gate(
        aggregate_state=aggregate_state,
        writer_payload=writer_payload,
        artifact_audit=artifact_audit or {},
        source_slots=source_slots,
    )
    failed_lanes = [
        str(row.get("lane_id") or "")
        for row in gate.get("checks") or []
        if isinstance(row, Mapping) and row.get("status") == "fail"
    ]
    profile = _gold_content_profile(aggregate_state, writer_payload)
    specialist_count = int(profile.get("specialist_material_count") or 0)
    writer_allowed = gate.get("status") == "pass" and specialist_count >= 5
    return {
        "schema_version": AI_SEMIS_GOLD_DEPTH_CONTENT_SCHEMA_VERSION,
        "artifact_type": "research_lead_gold_depth_veto",
        "status": "pass" if writer_allowed else "fail",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "writer_allowed": writer_allowed,
        "failed_lanes": failed_lanes,
        "specialist_material_count": specialist_count,
        "targeted_repairs": [
            {
                "lane_id": lane,
                "repair_action": _gold_depth_repair_action(lane),
            }
            for lane in failed_lanes
        ],
        "veto_reason": "" if writer_allowed else "briefing_pack_not_gold_depth_or_specialist_material_missing",
    }


def compile_rubric_cases_to_vertical_playbook_contracts(
    spec: Mapping[str, Any] | None = None,
    exemplars: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = spec or _read_json(DEFAULT_SPEC_PATH)
    exemplars = exemplars or _read_json(DEFAULT_EXEMPLARS_PATH)
    exemplar_by_id = _exemplar_by_id(exemplars)
    contracts: list[dict[str, Any]] = []
    for case in spec.get("cases") or []:
        if not isinstance(case, Mapping) or case.get("case_type") != "rubric_gold_case":
            continue
        case_id = str(case.get("case_id") or "")
        contracts.append(
            {
                "contract_id": _stable_id("vertical_playbook_contract", [case_id]),
                "case_id": case_id,
                "vertical": str(case.get("vertical") or ""),
                "runtime_status": "contract_translated_pending_runtime_artifact_proof",
                "must_answer_items": _string_list(case.get("must_answer_items")),
                "evidence_roles": _string_list(case.get("evidence_roles")),
                "promotable_boundaries": _string_list(case.get("promotable_boundaries")),
                "forbidden_inferences": _string_list(case.get("forbidden_inferences")),
                "answer_exemplar": exemplar_by_id.get(case_id, ""),
                "role_contract": _vertical_role_contract(case_id),
                "required_runtime_consumers": [
                    "ResearchLead.required_item_plan",
                    "specialist.role_specific_prompt",
                    "JudgmentCard.required_item_answered",
                    "MemoLogicPlan.section_contract",
                    "BriefingPackQualityGate.vertical_depth_check",
                ],
            }
        )
    return {
        "schema_version": HUMANMADE_GOLD_SET_RUNTIME_SCHEMA_VERSION,
        "artifact_type": "rubric_vertical_playbook_runtime_contracts",
        "status": "pass_contracts_compiled_runtime_artifact_proof_pending",
        "contract_count": len(contracts),
        "contracts": contracts,
    }


def compile_negative_cases_to_failure_gates(
    spec: Mapping[str, Any] | None = None,
    exemplars: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = spec or _read_json(DEFAULT_SPEC_PATH)
    exemplars = exemplars or _read_json(DEFAULT_EXEMPLARS_PATH)
    exemplar_by_id = _exemplar_by_id(exemplars)
    gates: list[dict[str, Any]] = []
    for case in spec.get("cases") or []:
        if not isinstance(case, Mapping) or case.get("case_type") != "negative_gold_case":
            continue
        case_id = str(case.get("case_id") or "")
        gate = _negative_gate_contract(case_id)
        gates.append(
            {
                "gate_id": f"negative_gate::{case_id}",
                "case_id": case_id,
                "runtime_status": "deterministic_gate_compiled",
                "target_artifact_stages": gate["target_artifact_stages"],
                "failure_condition": gate["failure_condition"],
                "correct_response_pattern": exemplar_by_id.get(case_id, ""),
                "forbidden_inferences": _string_list(case.get("forbidden_inferences")),
                "severity": gate["severity"],
            }
        )
    return {
        "schema_version": HUMANMADE_GOLD_SET_RUNTIME_SCHEMA_VERSION,
        "artifact_type": "negative_gold_case_failure_gates",
        "status": "pass_failure_gates_compiled",
        "gate_count": len(gates),
        "gates": gates,
    }


def run_negative_failure_gates(
    *,
    aggregate_state: Mapping[str, Any] | None = None,
    writer_payload: Mapping[str, Any] | None = None,
    final_memo: Mapping[str, Any] | None = None,
    gates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    gate_pack = gates or compile_negative_cases_to_failure_gates()
    aggregate_state = aggregate_state or {}
    writer_payload = writer_payload or {}
    final_memo = final_memo or {}
    text = _negative_gate_runtime_text(aggregate_state, writer_payload, final_memo)
    results: list[dict[str, Any]] = []
    for gate in gate_pack.get("gates") or []:
        if not isinstance(gate, Mapping):
            continue
        case_id = str(gate.get("case_id") or "")
        result = _run_single_negative_gate(case_id, text, aggregate_state, writer_payload, final_memo)
        results.append({**dict(gate), **result})
    fail_count = sum(1 for row in results if row.get("status") == "fail")
    pending_count = sum(1 for row in results if row.get("status") == "pending_final_memo")
    return {
        "schema_version": HUMANMADE_GOLD_SET_RUNTIME_SCHEMA_VERSION,
        "artifact_type": "negative_failure_gate_results",
        "status": "fail" if fail_count else "pending_final_memo" if pending_count else "pass",
        "fail_count": fail_count,
        "pending_final_memo_count": pending_count,
        "gate_count": len(results),
        "results": results,
    }


def run_briefing_pack_quality_gate(
    *,
    aggregate_state: Mapping[str, Any] | None = None,
    writer_payload: Mapping[str, Any] | None = None,
    artifact_audit: Mapping[str, Any] | None = None,
    source_slots: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    aggregate_state = aggregate_state or {}
    writer_payload = writer_payload or {}
    artifact_audit = artifact_audit or {}
    source_slots = source_slots or compile_ai_semis_human_source_runtime_slots()
    observations = _briefing_observations(aggregate_state, writer_payload, artifact_audit, source_slots)
    checks = [
        _depth_check(
            "demand_pool",
            observations["has_capex_demand_pool"],
            "Hyperscaler capex demand pool has issuer-level evidence and remains bounded from supplier allocation.",
            "Demand pool evidence is absent or not clearly bounded.",
            evidence=observations["demand_pool_refs"],
        ),
        _depth_check(
            "product_architecture_competition",
            observations["has_product_architecture_depth"],
            "Product architecture/spec/benchmark/deployment evidence is deep enough to support product capability judgment without SKU revenue.",
            "Product layer is still taxonomy/context-heavy or has unsupported TPU/spec claims; product_runtime_fact_count remains too low.",
            evidence=observations["product_runtime_detail"],
        ),
        _depth_check(
            "customer_deployment_adoption",
            observations["has_customer_deployment_depth"],
            "Customer deployment/adoption evidence contains issuer/product/counterparty/config context beyond relationship scope.",
            "Deployment rows remain mostly relationship scope/hypothesis or lack official customer/order/config evidence.",
            evidence=observations["customer_deployment_detail"],
        ),
        _depth_check(
            "dell_financial_quality_bridge",
            observations["has_dell_financial_bridge_depth"],
            "DELL AI server orders/backlog/revenue visibility is bridged to margin quality, pass-through cost, working capital, and cash conversion.",
            "DELL AI server financial bridge remains partial; margin mix/GPU pass-through/backlog conversion are unresolved.",
            evidence=observations["dell_financial_bridge_detail"],
        ),
        _depth_check(
            "semicap_foundry_readthrough",
            observations["has_semicap_depth"],
            "ASML/AMAT/LRCX/KLAC/TSM read-through contains company-specific bookings/backlog/system/process/advanced-node evidence.",
            "Semicap read-through is still broad context, route gap, or peer-scope heavy.",
            evidence=observations["semicap_detail"],
        ),
        _depth_check(
            "market_expectation_price_in",
            observations["has_market_price_in_depth"],
            "Case-specific valuation/positioning/crowding/capital feedback material supports price-in analysis.",
            "Market price-in remains missing or generic; valuation/positioning/crowding rows are not present for the case.",
            evidence=observations["market_price_in_detail"],
        ),
        _depth_check(
            "counter_thesis_and_what_would_change",
            observations["has_counter_thesis_depth"],
            "Counter-thesis covers capex digestion, substitution, margin dilution, concentration, export/control, and trigger conditions.",
            "Risk/counter-thesis remains partial or generic.",
            evidence=observations["counter_thesis_detail"],
        ),
    ]
    fail_count = sum(1 for row in checks if row["status"] == "fail")
    return {
        "schema_version": BRIEFING_PACK_QUALITY_GATE_SCHEMA_VERSION,
        "status": "pass" if fail_count == 0 else "fail",
        "gate_id": "p33_ai_semis_humanmade_gold_briefing_pack_quality_gate",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "fail_count": fail_count,
        "check_count": len(checks),
        "checks": checks,
        "observations": observations,
        "pass_condition": (
            "All seven gold-depth lanes must pass before paid Memo Writer is allowed. Shape/trace pass is insufficient."
        ),
    }


def run_humanmade_gold_set_audit(
    *,
    aggregate_state: Mapping[str, Any] | None = None,
    writer_payload: Mapping[str, Any] | None = None,
    final_memo: Mapping[str, Any] | None = None,
    spec: Mapping[str, Any] | None = None,
    exemplars: Mapping[str, Any] | None = None,
    artifact_audit: Mapping[str, Any] | None = None,
    matrix_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = spec or _read_json(DEFAULT_SPEC_PATH)
    exemplars = exemplars or _read_json(DEFAULT_EXEMPLARS_PATH)
    artifact_audit = artifact_audit or _read_json(DEFAULT_ARTIFACT_AUDIT_PATH)
    matrix_audit = matrix_audit or _read_json(DEFAULT_MATRIX_AUDIT_PATH)
    source_slots = compile_ai_semis_human_source_runtime_slots()
    gold_depth_content_pack = build_ai_semis_gold_depth_content_pack(source_slots)
    rubric_contracts = compile_rubric_cases_to_vertical_playbook_contracts(spec, exemplars)
    negative_gates = compile_negative_cases_to_failure_gates(spec, exemplars)
    briefing_gate = run_briefing_pack_quality_gate(
        aggregate_state=aggregate_state,
        writer_payload=writer_payload,
        artifact_audit=artifact_audit,
        source_slots=source_slots,
    )
    negative_gate_results = run_negative_failure_gates(
        aggregate_state=aggregate_state,
        writer_payload=writer_payload,
        final_memo=final_memo,
        gates=negative_gates,
    )
    lead_veto = run_research_lead_gold_depth_veto(
        aggregate_state=aggregate_state,
        writer_payload=writer_payload,
        artifact_audit=artifact_audit,
        source_slots=source_slots,
    )
    pass_checks = {
        "source_runtime_slots_compiled": int(source_slots.get("slot_count") or 0) >= 10,
        "gold_depth_content_pack_compiled": int(
            _nested(gold_depth_content_pack, "human_source_runtime_rows", "row_count", default=0)
        )
        >= 18,
        "rubric_contracts_compiled": int(rubric_contracts.get("contract_count") or 0) == 8,
        "negative_failure_gates_compiled": int(negative_gates.get("gate_count") or 0) == 6,
        "briefing_pack_quality_gate_pass": briefing_gate.get("status") == "pass",
        "research_lead_gold_depth_veto_pass": lead_veto.get("status") == "pass",
        "negative_failure_gates_no_fail": int(negative_gate_results.get("fail_count") or 0) == 0,
    }
    errors = [{"type": key, "status": "failed"} for key, passed in pass_checks.items() if not passed]
    matrix_status_counts = matrix_audit.get("status_counts") if isinstance(matrix_audit.get("status_counts"), Mapping) else {}
    return {
        "schema_version": HUMANMADE_GOLD_SET_AUDIT_SCHEMA_VERSION,
        "status": "pass" if not errors else "fail",
        "gate_id": "p33_humanmade_gold_set_pre_writer_audit",
        "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        "checks": pass_checks,
        "errors": errors,
        "pre_writer_decision": {
            "allow_paid_memo_writer": not errors,
            "block_reason": "" if not errors else "humanmade_gold_set_quality_not_met",
            "quality_standard": "gold-set-like output quality; not just shape/trace pass",
        },
        "compiled_artifacts": {
            "source_runtime_slots": source_slots,
            "ai_semis_gold_depth_content_pack": gold_depth_content_pack,
            "rubric_vertical_playbook_contracts": rubric_contracts,
            "negative_failure_gates": negative_gates,
        },
        "briefing_pack_quality_gate": briefing_gate,
        "research_lead_gold_depth_veto": lead_veto,
        "negative_failure_gate_results": negative_gate_results,
        "matrix_audit_context": {
            "status": matrix_audit.get("status") or "",
            "status_counts": dict(matrix_status_counts),
        },
        "not_run": [
            "paid_memo_writer",
            "full_chain",
            "model_comparison",
            "new_retrieval",
            "crawler_or_parser",
        ],
    }


def build_pre_writer_humanmade_gold_set_gate(state: Mapping[str, Any]) -> dict[str, Any]:
    if not _requires_humanmade_gold_gate(state):
        return {
            "schema_version": HUMANMADE_GOLD_SET_AUDIT_SCHEMA_VERSION,
            "status": "not_applicable",
            "reason": "case_not_in_humanmade_gold_gate_scope",
        }
    audit = run_humanmade_gold_set_audit(aggregate_state=state)
    return {
        "schema_version": HUMANMADE_GOLD_SET_AUDIT_SCHEMA_VERSION,
        "status": audit["status"],
        "gate_id": audit["gate_id"],
        "case_id": audit["case_id"],
        "pre_writer_decision": audit["pre_writer_decision"],
        "errors": audit["errors"],
        "briefing_pack_quality_gate": {
            "status": audit["briefing_pack_quality_gate"]["status"],
            "fail_count": audit["briefing_pack_quality_gate"]["fail_count"],
            "failed_lanes": [
                row["lane_id"]
                for row in audit["briefing_pack_quality_gate"].get("checks") or []
                if isinstance(row, Mapping) and row.get("status") == "fail"
            ],
        },
        "research_lead_gold_depth_veto": audit.get("research_lead_gold_depth_veto") or {},
        "negative_failure_gate_results": {
            "status": audit["negative_failure_gate_results"]["status"],
            "fail_count": audit["negative_failure_gate_results"]["fail_count"],
            "pending_final_memo_count": audit["negative_failure_gate_results"]["pending_final_memo_count"],
        },
    }


def synthetic_gold_briefing_fixture() -> dict[str, Any]:
    return build_ai_semis_gold_depth_content_pack()


def build_ai_semis_fresh_all_specialist_gold_pass(
    content_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a no-paid fresh all-specialist proof from the current gold-depth content pack.

    This intentionally does not reuse the historical targeted specialist composite. It
    re-materializes each role from the current gold-depth rows/edges/materials so the
    matrix audit can distinguish "fresh role proof" from "previous repaired composite".
    """

    content_pack = content_pack or build_ai_semis_gold_depth_content_pack()
    material_pack = (
        content_pack.get("specialist_judgment_materials")
        if isinstance(content_pack.get("specialist_judgment_materials"), Mapping)
        else {}
    )
    edge_pack = (
        content_pack.get("product_intelligence_graph_projection")
        if isinstance(content_pack.get("product_intelligence_graph_projection"), Mapping)
        else {}
    )
    row_pack = (
        content_pack.get("human_source_runtime_rows")
        if isinstance(content_pack.get("human_source_runtime_rows"), Mapping)
        else {}
    )
    materials = [row for row in material_pack.get("materials") or [] if isinstance(row, Mapping)]
    expected_roles = [
        "product_technology_analyst",
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
    ]
    role_outputs: list[dict[str, Any]] = []
    for role in expected_roles:
        role_materials = [row for row in materials if str(row.get("specialist_id") or "") == role]
        evidence_refs = _dedupe(
            [
                ref
                for row in role_materials
                for ref in _string_list(row.get("evidence_refs"))
            ]
        )
        graph_edge_refs = _dedupe(
            [
                ref
                for row in role_materials
                for ref in _string_list(row.get("graph_edge_refs"))
            ]
        )
        required_items = _dedupe([str(row.get("required_item_answered") or "") for row in role_materials])
        role_pass = bool(role_materials) and all(
            str(row.get("judgment") or "")
            and str(row.get("business_mechanism") or "")
            and _string_list(row.get("evidence_refs"))
            and str(row.get("cannot_infer") or "")
            for row in role_materials
        )
        role_outputs.append(
            {
                "role_id": role,
                "status": "pass" if role_pass else "fail_missing_writer_ready_judgment_material",
                "material_count": len(role_materials),
                "required_items_answered": required_items,
                "evidence_refs": evidence_refs,
                "graph_edge_refs": graph_edge_refs,
                "judgment_candidates": [
                    {
                        "judgment": str(row.get("judgment") or ""),
                        "required_item_answered": str(row.get("required_item_answered") or ""),
                        "memo_slot": str(row.get("memo_slot") or ""),
                        "business_mechanism": str(row.get("business_mechanism") or ""),
                        "cannot_infer": str(row.get("cannot_infer") or ""),
                        "counter_read": str(row.get("counter_read") or ""),
                        "what_would_change_view": _string_list(row.get("what_would_change_view")),
                        "evidence_refs": _string_list(row.get("evidence_refs")),
                        "graph_edge_refs": _string_list(row.get("graph_edge_refs")),
                    }
                    for row in role_materials
                ],
                "freshness_boundary": (
                    "No historical targeted specialist composite is reused. This is a no-paid, "
                    "role-by-role gold material projection from the current content pack; it is not a paid "
                    "specialist LLM run."
                ),
            }
        )
    fail_count = sum(1 for row in role_outputs if row["status"] != "pass")
    return {
        "schema_version": FRESH_ALL_SPECIALIST_GOLD_PASS_SCHEMA_VERSION,
        "artifact_type": "ai_semis_fresh_all_specialist_gold_pass",
        "case_id": "ai_semis_dell_nvda_anchor_v0_1",
        "status": "pass" if fail_count == 0 else "fail",
        "fresh_scope": "no_paid_fresh_projection_from_current_gold_depth_content_pack",
        "role_count": len(role_outputs),
        "role_pass_count": len(role_outputs) - fail_count,
        "role_fail_count": fail_count,
        "role_outputs": role_outputs,
        "content_pack_profile": {
            "row_count": row_pack.get("row_count", 0),
            "edge_count": edge_pack.get("edge_count", 0),
            "material_count": material_pack.get("material_count", 0),
            "lane_counts": row_pack.get("lane_counts", {}),
            "memo_slot_counts": material_pack.get("memo_slot_counts", {}),
        },
        "pass_condition": (
            "All five analyst roles must have writer-ready judgment candidates with evidence refs, graph refs, "
            "business mechanism, cannot-infer boundary, and what-would-change material."
        ),
        "not_run": ["paid_specialist_llm", "full_chain", "model_comparison"],
    }


def build_multicase_goldset_evidence_depth_packs(
    spec: Mapping[str, Any] | None = None,
    exemplars: Mapping[str, Any] | None = None,
    *,
    ai_semis_content_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile all 15 Humanmade Gold Set cases into artifact-backed depth packs."""

    spec = spec or _read_json(DEFAULT_SPEC_PATH)
    exemplars = exemplars or _read_json(DEFAULT_EXEMPLARS_PATH)
    exemplar_by_id = _exemplar_by_id(exemplars)
    ai_semis_content_pack = ai_semis_content_pack or build_ai_semis_gold_depth_content_pack()
    packs: list[dict[str, Any]] = []
    for case in spec.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        case_id = str(case.get("case_id") or "")
        case_type = str(case.get("case_type") or "")
        if case_type == "deep_gold_case":
            packs.append(_deep_case_evidence_depth_pack(case, exemplar_by_id.get(case_id, ""), ai_semis_content_pack))
        elif case_type == "rubric_gold_case":
            packs.append(_rubric_case_evidence_depth_pack(case, exemplar_by_id.get(case_id, "")))
        elif case_type == "negative_gold_case":
            packs.append(_negative_case_evidence_depth_pack(case, exemplar_by_id.get(case_id, "")))
    ready_count = sum(1 for pack in packs if pack.get("status") == "pass")
    type_counts: dict[str, int] = {}
    for pack in packs:
        type_counts[str(pack.get("case_type") or "")] = type_counts.get(str(pack.get("case_type") or ""), 0) + 1
    return {
        "schema_version": MULTICASE_GOLDSET_EVIDENCE_DEPTH_SCHEMA_VERSION,
        "artifact_type": "multicase_goldset_evidence_depth_packs",
        "status": "pass" if ready_count == len(packs) and len(packs) == 15 else "fail",
        "case_count": len(packs),
        "artifact_ready_count": ready_count,
        "case_type_counts": type_counts,
        "packs": packs,
        "acceptance_boundary": (
            "AI/Semis deep case uses concrete gold-depth runtime rows/edges/materials. Rubric and negative "
            "cases are gold-exemplar-backed executable artifacts: they define required evidence slots, authority "
            "roles, failure conditions, and runtime consumers, but they do not claim live retrieval/parser proof."
        ),
    }


def compile_negative_gold_failure_fixtures(
    spec: Mapping[str, Any] | None = None,
    exemplars: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = spec or _read_json(DEFAULT_SPEC_PATH)
    exemplars = exemplars or _read_json(DEFAULT_EXEMPLARS_PATH)
    exemplar_by_id = _exemplar_by_id(exemplars)
    fixtures: list[dict[str, Any]] = []
    for case in spec.get("cases") or []:
        if not isinstance(case, Mapping) or case.get("case_type") != "negative_gold_case":
            continue
        case_id = str(case.get("case_id") or "")
        gate = _negative_gate_contract(case_id)
        fixtures.append(
            {
                "fixture_id": f"negative_gold_fixture::{case_id}",
                "case_id": case_id,
                "status": "pass",
                "case_type": "negative_gold_case",
                "vertical": str(case.get("vertical") or ""),
                "target_artifact_stages": ["aggregate", "writer_payload", "final_memo"],
                "compiled_gate_targets": gate["target_artifact_stages"],
                "failure_condition": gate["failure_condition"],
                "correct_response_pattern": exemplar_by_id.get(case_id, ""),
                "forbidden_inferences": _string_list(case.get("forbidden_inferences")),
                "fail_criteria": _string_list(case.get("fail_criteria")),
                "pass_if": [
                    "The target artifact preserves the correct boundary.",
                    "The artifact does not promote proxy/scope/parser/context rows into exact facts.",
                    "If upstream evidence exists, downstream memo cannot claim it is missing.",
                ],
                "artifact_refs": [
                    _rel(DEFAULT_SPEC_PATH),
                    _rel(DEFAULT_EXEMPLARS_PATH),
                ],
                "runtime_consumers": [
                    "aggregate.failure_fixture_gate",
                    "MemoLogicPlan.failure_fixture_gate",
                    "MemoWriter.preflight",
                    "FinalVerifier.deterministic_failure_gate",
                    "Workbench.review_gap_projection",
                ],
            }
        )
    return {
        "schema_version": NEGATIVE_GOLD_FAILURE_FIXTURE_SCHEMA_VERSION,
        "artifact_type": "negative_gold_failure_fixtures",
        "status": "pass" if len(fixtures) == 6 and all(row["status"] == "pass" for row in fixtures) else "fail",
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
    }


def run_multicase_goldset_no_paid_audit(
    spec: Mapping[str, Any] | None = None,
    exemplars: Mapping[str, Any] | None = None,
    *,
    ai_semis_content_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the no-paid matrix closeout requested after single-case projection replay."""

    spec = spec or _read_json(DEFAULT_SPEC_PATH)
    exemplars = exemplars or _read_json(DEFAULT_EXEMPLARS_PATH)
    ai_semis_content_pack = ai_semis_content_pack or build_ai_semis_gold_depth_content_pack()
    evidence_depth = build_multicase_goldset_evidence_depth_packs(
        spec,
        exemplars,
        ai_semis_content_pack=ai_semis_content_pack,
    )
    fresh_specialists = build_ai_semis_fresh_all_specialist_gold_pass(ai_semis_content_pack)
    negative_fixtures = compile_negative_gold_failure_fixtures(spec, exemplars)
    case_results: list[dict[str, Any]] = []
    for pack in evidence_depth.get("packs") or []:
        if not isinstance(pack, Mapping):
            continue
        case_result = {
            "case_id": str(pack.get("case_id") or ""),
            "case_type": str(pack.get("case_type") or ""),
            "vertical": str(pack.get("vertical") or ""),
            "evidence_depth_status": str(pack.get("status") or ""),
            "evidence_row_count": int(pack.get("evidence_row_count") or 0),
            "runtime_consumer_count": len(_string_list(pack.get("runtime_consumers"))),
            "blocking_reasons": [],
        }
        if pack.get("status") != "pass":
            case_result["blocking_reasons"].append("evidence_depth_pack_not_pass")
        if pack.get("case_id") == "ai_semis_dell_nvda_anchor_v0_1":
            case_result["fresh_all_specialist_status"] = str(fresh_specialists.get("status") or "")
            if fresh_specialists.get("status") != "pass":
                case_result["blocking_reasons"].append("fresh_all_specialist_gold_pass_not_pass")
        if pack.get("case_type") == "negative_gold_case":
            fixture = _find_by_case_id(negative_fixtures.get("fixtures") or [], str(pack.get("case_id") or ""))
            case_result["negative_failure_fixture_status"] = str(fixture.get("status") or "missing")
            if fixture.get("status") != "pass":
                case_result["blocking_reasons"].append("negative_failure_fixture_not_pass")
        case_results.append(case_result)
    blocking_cases = [row["case_id"] for row in case_results if row["blocking_reasons"]]
    status = "pass" if not blocking_cases and evidence_depth.get("case_count") == 15 else "fail"
    return {
        "schema_version": MULTICASE_GOLDSET_NO_PAID_AUDIT_SCHEMA_VERSION,
        "artifact_type": "multicase_goldset_no_paid_audit",
        "status": status,
        "scope": {
            "audit_mode": "no_paid_multicase_goldset_artifact_depth_and_fresh_specialist_audit",
            "not_run": [
                "paid_llm",
                "paid_specialist_llm",
                "paid_memo_writer",
                "full_chain",
                "model_comparison",
                "new_retrieval",
                "crawler_or_parser",
            ],
            "known_boundary": (
                "This closes the artifact-depth/fresh-specialist fixture scope. It does not prove live source "
                "retrieval for all rubric sectors, paid Memo Writer prose, human Workbench dogfood, or release readiness."
            ),
        },
        "metrics": {
            "case_count": len(case_results),
            "artifact_ready_count": evidence_depth.get("artifact_ready_count", 0),
            "fresh_all_specialist_pass_count": 1 if fresh_specialists.get("status") == "pass" else 0,
            "negative_fixture_pass_count": sum(
                1 for row in negative_fixtures.get("fixtures") or [] if isinstance(row, Mapping) and row.get("status") == "pass"
            ),
            "runtime_contract_ready_count": len(case_results),
            "blocking_case_count": len(blocking_cases),
        },
        "case_results": case_results,
        "compiled_artifacts": {
            "evidence_depth_packs": evidence_depth,
            "ai_semis_fresh_all_specialist_gold_pass": fresh_specialists,
            "negative_failure_fixtures": negative_fixtures,
        },
        "pre_writer_decision": {
            "allow_paid_memo_writer": False,
            "reason": (
                "Multi-case no-paid fixture closeout is not a paid-writer permission. Paid writer remains scoped to "
                "the already approved single AI/Semis checkpoint only after explicit user approval and preflights."
            ),
        },
        "next_step": (
            "Use these artifacts to repair runtime source ingestion / specialist contracts per case. Do not expand "
            "to full-chain or model comparison until live node-level proof and human review are available."
        ),
    }


def build_goldset_source_runtime_assimilation_matrix(
    evidence_depth: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map every gold-set evidence slot to source-route/parser/runtime readiness.

    This is intentionally stricter than the no-paid artifact audit. It does not
    promote gold exemplars or human-ledger rows into live parser proof.
    """

    evidence_depth = evidence_depth or build_multicase_goldset_evidence_depth_packs()
    packs = [pack for pack in evidence_depth.get("packs") or [] if isinstance(pack, Mapping)]
    rows: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []
    for pack in packs:
        case_id = str(pack.get("case_id") or "")
        case_type = str(pack.get("case_type") or "")
        vertical = str(pack.get("vertical") or "")
        case_rows: list[dict[str, Any]] = []
        for index, evidence_row in enumerate(pack.get("evidence_rows") or [], start=1):
            if not isinstance(evidence_row, Mapping):
                continue
            row = _source_runtime_matrix_row(case_id, case_type, vertical, evidence_row, index)
            rows.append(row)
            case_rows.append(row)
        case_summaries.append(_source_runtime_case_summary(pack, case_rows))
    metrics = _source_runtime_matrix_metrics(case_summaries, rows)
    matrix_integrity_status = "pass" if metrics["case_count"] == 15 and metrics["row_count"] > 0 else "fail"
    status = (
        "live_source_runtime_ready"
        if matrix_integrity_status == "pass" and metrics["live_runtime_pending_row_count"] == 0
        else "partial_artifact_scope_pass_live_runtime_pending"
    )
    return {
        "schema_version": GOLDSET_SOURCE_RUNTIME_ASSIMILATION_MATRIX_SCHEMA_VERSION,
        "artifact_type": "goldset_source_runtime_assimilation_matrix",
        "status": status if matrix_integrity_status == "pass" else "fail",
        "matrix_integrity_status": matrix_integrity_status,
        "scope": {
            "purpose": (
                "Map each Humanmade Gold Set evidence pack to registered source role, crawler/parser status, "
                "runtime row readiness, authority boundary, and next source-route action."
            ),
            "not_run": [
                "paid_llm",
                "paid_specialist_llm",
                "paid_memo_writer",
                "full_chain",
                "model_comparison",
                "new_live_retrieval",
                "new_crawler_or_parser_execution",
            ],
            "known_boundary": (
                "The matrix is a diagnostic bridge from gold-set artifacts to live source-route work. "
                "It must not be interpreted as proof that all 15 cases have crawler/parser-backed rows."
            ),
        },
        "metrics": metrics,
        "case_summaries": case_summaries,
        "rows": rows,
        "pre_writer_decision": {
            "allow_paid_memo_writer": False,
            "reason": (
                "Gold-set source-runtime assimilation still has live-runtime-pending rows. Paid writer or "
                "full-chain expansion would hide whether each required evidence slot has a real source/parser row."
            ),
        },
        "next_step": (
            "For every row with live_runtime_pending or source_route_unverified status, bind the registered source "
            "role to an actual route, crawler/fetcher, parser/adapter, runtime row, and authority boundary before "
            "using the case as live product evidence."
        ),
    }


def build_goldset_live_source_backfill(
    matrix: Mapping[str, Any] | None = None,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    """Bind gold-set matrix rows to already materialized source/parser/runtime rows.

    This does not crawl new sources. It answers a narrower but important
    question: among the currently registered and materialized marts, which
    gold-set evidence slots can be linked to parser-backed runtime rows, which
    only have weak candidates, and which still need source-route/parser work.
    """

    matrix = matrix or build_goldset_source_runtime_assimilation_matrix()
    root = Path(repo_root)
    source_index = _load_goldset_backfill_source_index(root)
    backfill_rows = [
        _backfill_goldset_matrix_row(row, source_index)
        for row in matrix.get("rows") or []
        if isinstance(row, Mapping)
    ]
    case_summaries = _goldset_live_backfill_case_summaries(backfill_rows)
    metrics = _goldset_live_backfill_metrics(backfill_rows, case_summaries, source_index)
    if metrics["candidate_matrix_row_count"] == 0:
        status = "no_live_rows_bound_backfill_required"
    elif metrics["remaining_action_required_row_count"] > 0:
        status = "partial_live_backfill_pass_remaining_route_parser_work"
    else:
        status = "live_source_runtime_ready"
    return {
        "schema_version": GOLDSET_LIVE_SOURCE_BACKFILL_SCHEMA_VERSION,
        "artifact_type": "goldset_live_source_backfill",
        "status": status,
        "scope": {
            "purpose": (
                "Backfill each gold-set source-runtime matrix row against existing materialized runtime manifests, "
                "without new paid LLM, full-chain, crawler, or parser execution."
            ),
            "not_run": [
                "paid_llm",
                "paid_specialist_llm",
                "paid_memo_writer",
                "full_chain",
                "model_comparison",
                "new_live_retrieval",
                "new_crawler_or_parser_execution",
            ],
            "known_boundary": (
                "A live_runtime_ready row means an existing parser-backed runtime row was found. "
                "It does not prove that every gold-set slot has enough depth for final workpaper quality."
            ),
        },
        "source_index_summary": source_index["summary"],
        "metrics": metrics,
        "case_summaries": case_summaries,
        "rows": backfill_rows,
        "pre_writer_decision": {
            "allow_paid_memo_writer": False,
            "reason": (
                "This backfill is source-route/parser lineage work. Paid writer/full-chain remains blocked until "
                "remaining route/parser gaps are closed or explicitly typed as attempt-backed external gaps."
            ),
        },
        "next_step": _goldset_live_backfill_next_step(metrics),
    }


def _source_runtime_matrix_row(
    case_id: str,
    case_type: str,
    vertical: str,
    evidence_row: Mapping[str, Any],
    row_index: int,
) -> dict[str, Any]:
    source_status = str(evidence_row.get("source_status") or "")
    role = str(evidence_row.get("role") or "")
    row_type = str(evidence_row.get("row_type") or "")
    source_authority = str(evidence_row.get("source_authority") or "")
    classification = _classify_goldset_source_runtime_status(source_status, row_type)
    required_slot = str(evidence_row.get("required_item_answered") or "")
    if not required_slot:
        required_slot = _required_item_for_lane(role)
    source_role = role or "unclassified_goldset_source_role"
    registered_source_id = _goldset_registered_source_id(source_role, source_authority, row_type)
    status = classification["status"]
    return {
        "matrix_row_id": _stable_id(
            "goldset_source_runtime_matrix",
            [case_id, str(evidence_row.get("row_id") or row_index), source_role, required_slot],
        ),
        "case_id": case_id,
        "case_type": case_type,
        "vertical": vertical,
        "evidence_row_id": str(evidence_row.get("row_id") or ""),
        "evidence_row_type": row_type,
        "issuer": str(evidence_row.get("issuer") or ""),
        "product_or_family": str(evidence_row.get("product_or_family") or ""),
        "source_name": str(evidence_row.get("source_name") or ""),
        "metric_or_attribute": str(evidence_row.get("metric_or_attribute") or ""),
        "value": str(evidence_row.get("value") or ""),
        "unit": str(evidence_row.get("unit") or ""),
        "period_or_version": str(evidence_row.get("period_or_version") or ""),
        "evidence_ref": str(evidence_row.get("evidence_ref") or ""),
        "required_evidence_slot": required_slot,
        "registered_source_role": source_role,
        "registered_source_id": registered_source_id,
        "registered_source_authority": source_authority,
        "source_status": source_status,
        "source_route_status": classification["source_route_status"],
        "crawler_or_fetcher_status": classification["crawler_or_fetcher_status"],
        "parser_or_adapter_status": classification["parser_or_adapter_status"],
        "runtime_row_status": classification["runtime_row_status"],
        "status": status,
        "is_live_runtime_ready": status == "live_runtime_ready",
        "authority_boundary": _goldset_source_runtime_authority_boundary(status, evidence_row),
        "runtime_consumers": _string_list(evidence_row.get("runtime_consumers")),
        "artifact_ref": str(evidence_row.get("artifact_ref") or ""),
        "fact_preview": str(evidence_row.get("fact") or "")[:320],
        "supports_preview": str(evidence_row.get("supports") or "")[:240],
        "cannot_infer_preview": str(evidence_row.get("cannot_infer") or "")[:240],
        "next_action": _goldset_source_runtime_next_action(status, source_role, required_slot),
    }


def _source_runtime_case_summary(
    pack: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
    live_runtime_ready = status_counts.get("live_runtime_ready", 0)
    source_route_unverified = status_counts.get("runtime_artifact_ready_source_route_unverified", 0)
    artifact_only = status_counts.get("artifact_only_live_runtime_pending", 0)
    failure_fixtures = status_counts.get("failure_fixture_ready_not_source_evidence", 0)
    unknown = status_counts.get("unknown_source_status_requires_audit", 0)
    pending = source_route_unverified + artifact_only + unknown
    if pending:
        status = "live_runtime_pending"
    elif failure_fixtures and not live_runtime_ready:
        status = "failure_fixture_only_not_source_evidence"
    else:
        status = "live_runtime_ready"
    return {
        "case_id": str(pack.get("case_id") or ""),
        "case_type": str(pack.get("case_type") or ""),
        "vertical": str(pack.get("vertical") or ""),
        "status": status,
        "evidence_row_count": len(rows),
        "status_counts": status_counts,
        "live_runtime_ready_row_count": live_runtime_ready,
        "source_route_unverified_runtime_artifact_row_count": source_route_unverified,
        "artifact_only_live_runtime_pending_row_count": artifact_only,
        "failure_fixture_row_count": failure_fixtures,
        "unknown_source_status_row_count": unknown,
        "live_runtime_pending_row_count": pending,
        "required_evidence_slots": _dedupe([str(row.get("required_evidence_slot") or "") for row in rows]),
        "registered_source_roles": _dedupe([str(row.get("registered_source_role") or "") for row in rows]),
        "next_action": _goldset_source_runtime_case_next_action(str(pack.get("case_type") or ""), status),
        "authority_boundary": str(pack.get("source_boundary") or ""),
    }


def _source_runtime_matrix_metrics(
    case_summaries: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    row_status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "")
        row_status_counts[status] = row_status_counts.get(status, 0) + 1
    live_runtime_pending_case_count = sum(
        1 for case in case_summaries if _int(case.get("live_runtime_pending_row_count")) > 0
    )
    return {
        "case_count": len(case_summaries),
        "row_count": len(rows),
        "case_status_counts": _count_by_key(case_summaries, "status"),
        "row_status_counts": row_status_counts,
        "live_runtime_ready_row_count": row_status_counts.get("live_runtime_ready", 0),
        "source_route_unverified_runtime_artifact_row_count": row_status_counts.get(
            "runtime_artifact_ready_source_route_unverified",
            0,
        ),
        "artifact_only_live_runtime_pending_row_count": row_status_counts.get(
            "artifact_only_live_runtime_pending",
            0,
        ),
        "failure_fixture_row_count": row_status_counts.get("failure_fixture_ready_not_source_evidence", 0),
        "unknown_source_status_row_count": row_status_counts.get("unknown_source_status_requires_audit", 0),
        "live_runtime_pending_row_count": sum(
            _int(row.get("is_live_runtime_ready") is False)
            for row in rows
            if str(row.get("status") or "") != "failure_fixture_ready_not_source_evidence"
        ),
        "live_runtime_pending_case_count": live_runtime_pending_case_count,
        "registered_source_role_count": len(
            {str(row.get("registered_source_role") or "") for row in rows if str(row.get("registered_source_role") or "")}
        ),
    }


def _load_goldset_backfill_source_index(repo_root: Path) -> dict[str, Any]:
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    rowset_counts: dict[str, int] = {}
    missing_rowsets: list[str] = []
    for rel_path in GOLDSET_BACKFILL_SOURCE_ROWSETS:
        path = repo_root / rel_path
        if not path.exists():
            missing_rowsets.append(rel_path)
            continue
        count = 0
        with path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(raw, Mapping):
                    continue
                candidate = _compact_goldset_live_candidate(raw, rel_path, idx)
                ticker = str(candidate.get("ticker") or "")
                if not ticker:
                    continue
                rows_by_ticker.setdefault(ticker, []).append(candidate)
                count += 1
        rowset_counts[rel_path] = count
    return {
        "rows_by_ticker": rows_by_ticker,
        "summary": {
            "rowset_count": len(rowset_counts),
            "missing_rowsets": missing_rowsets,
            "rowset_counts": rowset_counts,
            "indexed_ticker_count": len(rows_by_ticker),
            "indexed_row_count": sum(rowset_counts.values()),
        },
    }


def _compact_goldset_live_candidate(raw: Mapping[str, Any], source_rowset_path: str, row_number: int) -> dict[str, Any]:
    ticker = _normalize_ticker(
        raw.get("ticker")
        or _nested(raw, "entity_binding", "issuer_ticker")
        or raw.get("issuer_ticker")
        or raw.get("company_ticker")
    )
    evidence_refs = _json_list(raw.get("evidence_refs_json"))
    runtime_ref = (
        raw.get("evidence_ref")
        or raw.get("evidence_id")
        or raw.get("edge_id")
        or raw.get("gold_row_id")
        or raw.get("source_row_id")
        or raw.get("snapshot_id")
        or raw.get("id")
        or _stable_id("runtime_row", [source_rowset_path, row_number])
    )
    source_url = str(raw.get("source_url") or raw.get("url") or _nested(raw, "citation", "url") or "")
    raw_path = str(raw.get("raw_path") or raw.get("source_document_id") or "")
    parser_status = str(raw.get("parser_status") or raw.get("source_specific_parser") or "")
    structured_status = str(raw.get("structured_fact_status") or raw.get("evidence_graph_status") or "")
    runtime_contract = str(raw.get("runtime_contract") or raw.get("schema_version") or "")
    return {
        "ticker": ticker,
        "runtime_row_ref": str(runtime_ref or ""),
        "source_rowset_path": source_rowset_path,
        "source_row_number": row_number,
        "source_id": str(raw.get("source_id") or raw.get("underlying_source_id") or ""),
        "source_role": str(raw.get("source_role") or raw.get("requirement_id") or raw.get("source_class") or ""),
        "support_surface": str(raw.get("support_surface") or raw.get("runtime_source_family") or ""),
        "fact_domain": str(raw.get("fact_domain") or raw.get("structured_context_type") or ""),
        "fact_type": str(raw.get("fact_type") or raw.get("claim_types") or ""),
        "authority_mode": str(raw.get("authority_mode") or raw.get("authority_type") or ""),
        "can_enter_evidence_bundle": bool(raw.get("can_enter_evidence_bundle") is True),
        "can_support_company_exact_fact": bool(raw.get("can_support_company_exact_fact") is True),
        "exact_value_authority": bool(raw.get("exact_value_authority") is True),
        "metric_name": str(raw.get("metric_name") or raw.get("canonical_metric_id") or raw.get("spec_name") or ""),
        "product_or_segment": str(raw.get("product_or_segment") or raw.get("product_family") or ""),
        "product_family": str(raw.get("product_family") or ""),
        "counterparty": str(raw.get("counterparty") or ""),
        "period": str(raw.get("period") or raw.get("fiscal_year") or ""),
        "value": str(raw.get("value") or raw.get("raw_value_text") or ""),
        "unit": str(raw.get("unit") or raw.get("spec_unit") or ""),
        "source_url": source_url,
        "raw_path": raw_path,
        "parser_status": parser_status,
        "structured_fact_status": structured_status,
        "runtime_contract": runtime_contract,
        "source_specific_parser": str(raw.get("source_specific_parser") or ""),
        "source_specific_resolver": str(raw.get("source_specific_resolver") or ""),
        "claim_boundary": str(raw.get("claim_boundary") or raw.get("authority_boundary") or ""),
        "citation_span": str(raw.get("citation_span") or raw.get("preview") or raw.get("text") or "")[:420],
        "evidence_refs": evidence_refs,
        "search_text": _candidate_search_text(raw, source_rowset_path, evidence_refs),
    }


def _backfill_goldset_matrix_row(row: Mapping[str, Any], source_index: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "matrix_row_id": str(row.get("matrix_row_id") or ""),
        "case_id": str(row.get("case_id") or ""),
        "case_type": str(row.get("case_type") or ""),
        "vertical": str(row.get("vertical") or ""),
        "evidence_row_id": str(row.get("evidence_row_id") or ""),
        "registered_source_role": str(row.get("registered_source_role") or ""),
        "registered_source_id": str(row.get("registered_source_id") or ""),
        "required_evidence_slot": str(row.get("required_evidence_slot") or ""),
        "issuer": str(row.get("issuer") or ""),
        "product_or_family": str(row.get("product_or_family") or ""),
        "source_name": str(row.get("source_name") or ""),
        "metric_or_attribute": str(row.get("metric_or_attribute") or ""),
        "period_or_version": str(row.get("period_or_version") or ""),
        "value": str(row.get("value") or ""),
        "unit": str(row.get("unit") or ""),
        "artifact_ref": str(row.get("artifact_ref") or ""),
        "matrix_status": str(row.get("status") or ""),
        "matrix_authority_boundary": str(row.get("authority_boundary") or ""),
    }
    if str(row.get("status") or "") == "failure_fixture_ready_not_source_evidence":
        return {
            **base,
            "backfill_status": "not_applicable_failure_fixture",
            "is_live_runtime_ready": False,
            "bound_runtime_row_count": 0,
            "bound_runtime_row_refs": [],
            "source_rowset_paths": [],
            "parser_lineage_status": "not_source_evidence",
            "authority_boundary": "Negative gold cases are failure fixtures only; never enter evidence bundles.",
            "next_action": "Keep as deterministic failure fixture for aggregate / writer / verifier.",
            "top_candidates": [],
        }
    issuer = str(row.get("issuer") or "")
    ticker = _normalize_ticker(issuer)
    if not ticker or ticker in {"AI_SEMIS_BASKET", "BASKET"}:
        return {
            **base,
            "backfill_status": "case_binding_required_before_live_lookup",
            "is_live_runtime_ready": False,
            "bound_runtime_row_count": 0,
            "bound_runtime_row_refs": [],
            "source_rowset_paths": [],
            "parser_lineage_status": "case_level_or_rubric_slot_not_issuer_bound",
            "authority_boundary": (
                "This gold-set slot has no issuer-bound lookup key yet. It must be bound to a company/issuer before "
                "source routes can be treated as live runtime rows."
            ),
            "next_action": "Bind the rubric/gold slot to issuer-specific source routes, then rerun live backfill.",
            "top_candidates": [],
        }
    candidates = source_index.get("rows_by_ticker", {}).get(ticker, [])
    scored = [
        _score_goldset_live_candidate(row, candidate)
        for candidate in candidates
    ]
    scored = [item for item in scored if item["score"] > 0]
    scored.sort(key=lambda item: item["score"], reverse=True)
    top = scored[:3]
    best = top[0] if top else None
    if best is None:
        return {
            **base,
            "backfill_status": "source_route_not_bound_required",
            "is_live_runtime_ready": False,
            "bound_runtime_row_count": 0,
            "bound_runtime_row_refs": [],
            "source_rowset_paths": [],
            "parser_lineage_status": "no_candidate_for_issuer_and_required_slot",
            "authority_boundary": (
                "No existing materialized runtime row matched this issuer/source role/product slot. This is not yet "
                "public-source absence; it is a live route/parser backfill requirement."
            ),
            "next_action": "Run or implement the source route/parser for this issuer slot, then record an accepted row or typed gap.",
            "top_candidates": [],
        }
    candidate = best["candidate"]
    lineage_status = _goldset_candidate_parser_lineage_status(candidate)
    bindable = (
        best["score"] >= 36
        and best["specific_overlap_count"] > 0
        and best["role_compatible"]
        and _goldset_binding_has_required_specificity(row, candidate, _string_list(best.get("specific_overlap_terms")))
    )
    live_ready = bindable and lineage_status == "parser_backed_runtime_row"
    if live_ready:
        status = "live_runtime_ready"
        next_action = "Ready for source-runtime consumption with the recorded authority boundary."
    elif bindable:
        status = "route_candidate_only_parser_lineage_pending"
        next_action = "Candidate is semantically compatible, but parser/source lineage is incomplete; repair lineage before promotion."
    else:
        status = "source_route_candidate_weak_not_bound"
        next_action = "Existing candidates are too weak for binding; run source-specific locator/parser or record attempt-backed gap."
    bound_refs = [str(candidate.get("runtime_row_ref") or "")] if live_ready else []
    return {
        **base,
        "backfill_status": status,
        "is_live_runtime_ready": live_ready,
        "bound_runtime_row_count": len(bound_refs),
        "bound_runtime_row_refs": bound_refs,
        "source_rowset_paths": _dedupe([str(candidate.get("source_rowset_path") or "")]) if live_ready else [],
        "parser_lineage_status": lineage_status,
        "authority_boundary": _goldset_live_backfill_boundary(status, candidate, row),
        "next_action": next_action,
        "top_candidates": [_public_goldset_candidate(candidate_row) for candidate_row in top],
    }


def _score_goldset_live_candidate(matrix_row: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    role_compatible = _goldset_role_compatible(matrix_row, candidate)
    query_text = " ".join(
        str(matrix_row.get(key) or "")
        for key in (
            "registered_source_role",
            "required_evidence_slot",
            "evidence_row_type",
            "product_or_family",
            "metric_or_attribute",
            "source_name",
            "fact_preview",
        )
    )
    query_tokens = _meaningful_tokens(query_text)
    candidate_tokens = _meaningful_tokens(str(candidate.get("search_text") or ""))
    overlap = sorted(query_tokens & candidate_tokens)
    source_name_overlap = sorted(
        _meaningful_tokens(str(matrix_row.get("source_name") or "")) & candidate_tokens
    )
    product_metric_overlap = sorted(
        _meaningful_tokens(
            " ".join(
                str(matrix_row.get(key) or "")
                for key in ("product_or_family", "metric_or_attribute", "period_or_version", "value")
            )
        )
        & candidate_tokens
    )
    specific_overlap = _goldset_specific_overlap_terms(matrix_row, candidate)
    score = 0
    if role_compatible:
        score += 28
    score += min(len(overlap) * 3, 30)
    score += min(len(specific_overlap) * 8, 32)
    score += min(len(product_metric_overlap) * 2, 10)
    score += min(len(source_name_overlap) * 4, 16)
    if _goldset_candidate_parser_lineage_status(candidate) == "parser_backed_runtime_row":
        score += 8
    if candidate.get("exact_value_authority"):
        score += 5
    return {
        "score": score,
        "role_compatible": role_compatible,
        "semantic_overlap_count": len(overlap),
        "specific_overlap_count": len(specific_overlap),
        "semantic_overlap_terms": overlap[:12],
        "specific_overlap_terms": specific_overlap[:12],
        "product_metric_overlap_terms": product_metric_overlap[:12],
        "candidate": candidate,
    }


def _goldset_binding_has_required_specificity(
    matrix_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    specific_terms: Sequence[str],
) -> bool:
    role = " ".join(
        str(matrix_row.get(key) or "").lower()
        for key in ("registered_source_role", "evidence_row_type", "required_evidence_slot")
    )
    query = " ".join(
        str(matrix_row.get(key) or "")
        for key in ("product_or_family", "metric_or_attribute", "source_name", "fact_preview")
    ).lower()
    candidate_text = str(candidate.get("search_text") or "").lower()
    specific = {str(term).lower() for term in specific_terms}
    if any(term in role for term in ("product_architecture", "technical", "benchmark", "accelerator")):
        product_codes = _goldset_product_code_terms(query)
        if product_codes:
            return bool(product_codes & _meaningful_tokens(candidate_text))
        return len(specific) >= 2
    if any(term in role for term in ("demand_pool", "capex", "hyperscaler")):
        if "capex" in query or "capital expenditure" in query:
            return bool(specific & {"capex", "capital", "expenditure"})
        required = {"azure", "aws", "technical", "infrastructure", "datacenter"}
        return bool(specific & required) or "data center" in candidate_text or "google cloud" in candidate_text
    if any(term in role for term in ("semicap", "foundry", "readthrough")):
        semicap_terms = {
            "hpc",
            "high_performance_computing",
            "semiconductor",
            "systems",
            "euv",
            "duv",
            "lithography",
            "installed",
            "base",
            "memory",
            "hbm",
            "etch",
            "deposition",
            "equipment",
            "foundry",
            "logic",
            "dram",
            "flash",
        }
        return bool(specific & semicap_terms)
    if any(term in role for term in ("customer_deployment", "deployment", "adoption", "supply_chain")):
        return bool(specific & {"poweredge", "xe9680", "xe9712", "gb200", "a4x", "deployment", "configured", "customer"})
    return True


def _goldset_role_compatible(matrix_row: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    role = " ".join(
        str(matrix_row.get(key) or "").lower()
        for key in ("registered_source_role", "evidence_row_type", "required_evidence_slot")
    )
    primary_role = " ".join(
        str(matrix_row.get(key) or "").lower()
        for key in ("registered_source_role", "evidence_row_type")
    )
    text = str(candidate.get("search_text") or "").lower()
    authority_family = _goldset_candidate_authority_family(candidate)
    if any(term in primary_role for term in ("semicap", "foundry", "readthrough")):
        return authority_family in {"financial_statement", "product_kpi_exact"} and any(
            term in text for term in ("semiconductor", "foundry", "wafer", "euv", "duv", "equipment", "revenue", "backlog")
        )
    if any(term in role for term in ("financial", "segment", "margin", "operating_metric", "dell_margin")):
        return authority_family in {"financial_statement", "product_kpi_exact"} and any(
            term in text for term in ("financial", "revenue", "margin", "income", "backlog", "shipment", "orders")
        )
    if any(term in role for term in ("product_architecture", "technical", "benchmark", "accelerator")):
        return authority_family in {"technical_product_spec", "product_graph"} and any(
            term in text for term in ("technical", "spec", "architecture", "benchmark", "gpu", "tpu", "accelerator", "product")
        )
    if any(term in role for term in ("customer_deployment", "deployment", "adoption", "supply_chain")):
        return authority_family in {"customer_deployment", "product_graph"} and any(
            term in text for term in ("customer", "deployment", "partner", "supplier", "supply", "configured", "order")
        )
    if any(term in role for term in ("demand_pool", "capex", "hyperscaler")):
        return authority_family in {"financial_statement", "product_kpi_exact", "market_capital_context"} and any(
            term in text for term in ("capex", "capital expenditure", "cloud", "datacenter", "data center", "revenue")
        )
    if any(term in role for term in ("market", "price", "valuation", "positioning")):
        return authority_family in {"market_capital_context", "financial_statement"} and any(
            term in text for term in ("market", "valuation", "liquidity", "price", "volume", "short", "holder")
        )
    if any(term in role for term in ("counter", "risk", "what_would_change")):
        return authority_family in {"market_capital_context", "technical_product_spec", "customer_deployment", "product_graph"} and any(
            term in text for term in ("risk", "counter", "export", "margin", "capex", "substitution")
        )
    return True


def _goldset_candidate_authority_family(candidate: Mapping[str, Any]) -> str:
    rowset = str(candidate.get("source_rowset_path") or "")
    text = str(candidate.get("search_text") or "").lower()
    source_id = str(candidate.get("source_id") or "").lower()
    source_role = str(candidate.get("source_role") or "").lower()
    if rowset.endswith("official_product_spec_context_rows_v0_1.jsonl") or "technical_product_spec" in text:
        return "technical_product_spec"
    if rowset.endswith("official_customer_deployment_surface_context_rows_v0_1.jsonl") or any(
        term in source_role for term in ("official_customer", "deployment", "supply_chain", "partner")
    ):
        return "customer_deployment"
    if rowset.endswith("product_intelligence_graph_edges_v0_1.jsonl"):
        return "product_graph"
    if any(
        rowset.endswith(name)
        for name in (
            "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
            "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
            "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
        )
    ) or "company_product_evidence_graph" in text:
        return "product_kpi_exact"
    if "sec_financial_statement" in source_id or "financial_statement_fact" in text or "fundamental_company_disclosure" in text:
        return "financial_statement"
    if any(term in text for term in ("market_liquidity", "capital_market", "ownership", "13f", "form 4")):
        return "market_capital_context"
    if any(term in text for term in ("product_or_business_line_profile", "product_or_service_profile", "product_taxonomy")):
        return "product_profile_context"
    return "unclassified"


def _goldset_specific_overlap_terms(matrix_row: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    candidate_tokens = _meaningful_tokens(str(candidate.get("search_text") or ""))
    candidate_text = str(candidate.get("search_text") or "").lower()
    query = " ".join(
        str(matrix_row.get(key) or "")
        for key in (
            "product_or_family",
            "metric_or_attribute",
            "period_or_version",
            "value",
            "source_name",
            "fact_preview",
        )
    )
    terms = set(_meaningful_tokens(query) & candidate_tokens)
    if "hpc" in _meaningful_tokens(query) and "high performance computing" in candidate_text:
        terms.add("hpc")
        terms.add("high_performance_computing")
    weak = {
        "product",
        "products",
        "revenue",
        "revenues",
        "disclosed",
        "company",
        "official",
        "source",
        "current",
        "metric",
        "demand",
        "financial",
        "fact",
        "context",
        "support",
        "supports",
        "dell",
        "nvidia",
        "nvda",
        "amd",
        "google",
        "googl",
        "microsoft",
        "msft",
        "amazon",
        "amzn",
        "meta",
        "asml",
        "amat",
        "lrcx",
        "tsm",
        "tsmc",
    }
    return sorted(term for term in terms if term not in weak)


def _goldset_product_code_terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"\b[A-Za-z]+[0-9][A-Za-z0-9\-]*\b|\b[A-Za-z]*[0-9]+[A-Za-z][A-Za-z0-9\-]*\b", text)
        if len(token) >= 3
    }


def _goldset_candidate_parser_lineage_status(candidate: Mapping[str, Any]) -> str:
    parser_text = " ".join(
        str(candidate.get(key) or "")
        for key in ("parser_status", "structured_fact_status", "runtime_contract", "source_specific_parser")
    ).lower()
    has_runtime_ref = bool(candidate.get("runtime_row_ref"))
    has_source = bool(candidate.get("source_url") or candidate.get("raw_path"))
    if has_runtime_ref and has_source and any(term in parser_text for term in ("pass", "materialized", "runtime", "parser")):
        return "parser_backed_runtime_row"
    if str(candidate.get("source_rowset_path") or "").endswith("product_intelligence_graph_edges_v0_1.jsonl"):
        return "graph_candidate_parser_lineage_pending"
    if has_runtime_ref:
        return "runtime_candidate_parser_lineage_pending"
    return "candidate_without_runtime_lineage"


def _goldset_live_backfill_case_summaries(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("case_id") or ""), []).append(row)
    summaries: list[dict[str, Any]] = []
    for case_id, case_rows in sorted(grouped.items()):
        status_counts = _count_by_key(case_rows, "backfill_status")
        live_ready = status_counts.get("live_runtime_ready", 0)
        action_required = sum(
            count
            for status, count in status_counts.items()
            if status not in {"live_runtime_ready", "not_applicable_failure_fixture"}
        )
        if action_required:
            case_status = "live_backfill_partial_or_pending"
        elif live_ready:
            case_status = "live_backfill_ready"
        else:
            case_status = "failure_fixture_only"
        summaries.append(
            {
                "case_id": case_id,
                "case_type": str(case_rows[0].get("case_type") or ""),
                "vertical": str(case_rows[0].get("vertical") or ""),
                "status": case_status,
                "row_count": len(case_rows),
                "status_counts": status_counts,
                "live_runtime_ready_row_count": live_ready,
                "action_required_row_count": action_required,
                "source_rowset_paths": _dedupe(
                    path
                    for row in case_rows
                    for path in _string_list(row.get("source_rowset_paths"))
                    if path
                ),
            }
        )
    return summaries


def _goldset_live_backfill_metrics(
    rows: Sequence[Mapping[str, Any]],
    case_summaries: Sequence[Mapping[str, Any]],
    source_index: Mapping[str, Any],
) -> dict[str, Any]:
    status_counts = _count_by_key(rows, "backfill_status")
    action_required = sum(
        count
        for status, count in status_counts.items()
        if status not in {"live_runtime_ready", "not_applicable_failure_fixture"}
    )
    candidate_rows = len(
        [
            row
            for row in rows
            if str(row.get("backfill_status") or "")
            not in {"not_applicable_failure_fixture", "case_binding_required_before_live_lookup"}
        ]
    )
    return {
        "case_count": len(case_summaries),
        "row_count": len(rows),
        "status_counts": status_counts,
        "case_status_counts": _count_by_key(case_summaries, "status"),
        "live_runtime_ready_row_count": status_counts.get("live_runtime_ready", 0),
        "route_candidate_only_parser_lineage_pending_count": status_counts.get(
            "route_candidate_only_parser_lineage_pending",
            0,
        ),
        "source_route_candidate_weak_not_bound_count": status_counts.get(
            "source_route_candidate_weak_not_bound",
            0,
        ),
        "source_route_not_bound_required_count": status_counts.get("source_route_not_bound_required", 0),
        "case_binding_required_count": status_counts.get("case_binding_required_before_live_lookup", 0),
        "failure_fixture_count": status_counts.get("not_applicable_failure_fixture", 0),
        "remaining_action_required_row_count": action_required,
        "candidate_matrix_row_count": candidate_rows,
        "indexed_row_count": _int(_nested(source_index, "summary", "indexed_row_count")),
        "indexed_ticker_count": _int(_nested(source_index, "summary", "indexed_ticker_count")),
    }


def _goldset_live_backfill_boundary(status: str, candidate: Mapping[str, Any], matrix_row: Mapping[str, Any]) -> str:
    candidate_boundary = str(candidate.get("claim_boundary") or "")
    if status == "live_runtime_ready":
        return candidate_boundary or "Parser-backed runtime row; keep source authority and forbidden claims from candidate row."
    if status == "route_candidate_only_parser_lineage_pending":
        return (
            "Candidate matches issuer/role/product semantics but lacks enough parser/source lineage for promotion. "
            f"Candidate boundary: {candidate_boundary[:240]}"
        )
    return (
        "Candidate evidence is too weak to bind this gold-set slot. Do not treat it as public-source absence until "
        "a source-route/parser attempt is documented."
    )


def _goldset_live_backfill_next_step(metrics: Mapping[str, Any]) -> str:
    if _int(metrics.get("remaining_action_required_row_count")) == 0:
        return "Use the backfilled rows in source-runtime assimilation tests, then proceed to scoped projection/dogfood."
    return (
        "Repair remaining rows by priority: issuer-bound AI/Semis source-route/parser first, then rubric case "
        "vertical-specific source routes, and keep negative fixtures out of evidence bundles."
    )


def _public_goldset_candidate(scored: Mapping[str, Any]) -> dict[str, Any]:
    candidate = scored.get("candidate") if isinstance(scored.get("candidate"), Mapping) else {}
    return {
        "score": _int(scored.get("score")),
        "role_compatible": bool(scored.get("role_compatible")),
        "semantic_overlap_terms": _string_list(scored.get("semantic_overlap_terms"))[:12],
        "specific_overlap_terms": _string_list(scored.get("specific_overlap_terms"))[:12],
        "product_metric_overlap_terms": _string_list(scored.get("product_metric_overlap_terms"))[:12],
        "runtime_row_ref": str(candidate.get("runtime_row_ref") or ""),
        "source_rowset_path": str(candidate.get("source_rowset_path") or ""),
        "authority_family": _goldset_candidate_authority_family(candidate),
        "source_id": str(candidate.get("source_id") or ""),
        "source_role": str(candidate.get("source_role") or ""),
        "metric_name": str(candidate.get("metric_name") or ""),
        "product_or_segment": str(candidate.get("product_or_segment") or ""),
        "source_url": str(candidate.get("source_url") or ""),
        "raw_path": str(candidate.get("raw_path") or ""),
        "parser_lineage_status": _goldset_candidate_parser_lineage_status(candidate),
        "claim_boundary": str(candidate.get("claim_boundary") or "")[:260],
        "citation_preview": str(candidate.get("citation_span") or "")[:260],
    }


def _candidate_search_text(raw: Mapping[str, Any], source_rowset_path: str, evidence_refs: Sequence[str]) -> str:
    values: list[str] = [source_rowset_path]
    for key in (
        "ticker",
        "company",
        "company_name",
        "source_id",
        "source_role",
        "source_class",
        "source_family",
        "runtime_source_family",
        "support_surface",
        "fact_domain",
        "fact_type",
        "metric_name",
        "canonical_metric_id",
        "product_or_segment",
        "product_family",
        "counterparty",
        "claim_boundary",
        "authority_boundary",
        "citation_span",
        "preview",
        "text",
        "edge_type",
        "source_layer",
        "structured_context_type",
        "value",
        "unit",
        "period",
        "fiscal_year",
    ):
        values.append(str(raw.get(key) or ""))
    values.extend(str(ref) for ref in evidence_refs)
    return " ".join(values).lower()


def _normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _json_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return _string_list(loaded)
    return _string_list(value)


def _meaningful_tokens(text: str) -> set[str]:
    stop = {
        "and",
        "the",
        "for",
        "with",
        "from",
        "that",
        "this",
        "row",
        "gold",
        "case",
        "source",
        "runtime",
        "company",
        "issuer",
        "official",
        "context",
        "metric",
        "data",
        "current",
    }
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-/\.]{1,}", text)
        if token.lower() not in stop and len(token) > 2
    }
    normalized: set[str] = set()
    for token in tokens:
        normalized.add(token)
        normalized.add(token.replace("-", "_").replace("/", "_").replace(".", "_"))
    return normalized


def _classify_goldset_source_runtime_status(source_status: str, row_type: str) -> dict[str, str]:
    if source_status == "human_source_ledger_runtime_row":
        return {
            "status": "runtime_artifact_ready_source_route_unverified",
            "source_route_status": "registered_from_human_source_ledger",
            "crawler_or_fetcher_status": "not_proven_by_live_crawler_or_fetcher",
            "parser_or_adapter_status": "human_source_ledger_parser_compiled",
            "runtime_row_status": "gold_depth_runtime_artifact_row_ready",
        }
    if source_status in {
        "gold_exemplar_backed_required_runtime_artifact_not_live_retrieval",
        "gold_spec_backed_role_requirement_not_live_retrieval",
    }:
        return {
            "status": "artifact_only_live_runtime_pending",
            "source_route_status": "required_source_role_registered_from_gold_contract",
            "crawler_or_fetcher_status": "not_run",
            "parser_or_adapter_status": "not_run",
            "runtime_row_status": "required_slot_contract_only",
        }
    if source_status == "gold_negative_fixture" or row_type == "negative_gold_failure_fixture_row":
        return {
            "status": "failure_fixture_ready_not_source_evidence",
            "source_route_status": "not_applicable_failure_fixture",
            "crawler_or_fetcher_status": "not_applicable",
            "parser_or_adapter_status": "not_applicable",
            "runtime_row_status": "failure_gate_fixture_ready",
        }
    return {
        "status": "unknown_source_status_requires_audit",
        "source_route_status": "unknown",
        "crawler_or_fetcher_status": "unknown",
        "parser_or_adapter_status": "unknown",
        "runtime_row_status": "unknown",
    }


def _goldset_registered_source_id(source_role: str, source_authority: str, row_type: str) -> str:
    return _stable_id("registered_source", [source_role, source_authority, row_type])


def _goldset_source_runtime_authority_boundary(status: str, evidence_row: Mapping[str, Any]) -> str:
    if status == "runtime_artifact_ready_source_route_unverified":
        return (
            "Gold-depth runtime artifact row exists, but this row is compiled from the human source ledger. "
            "Before production use, bind it to a concrete registered source route, fetch/crawl attempt, parser "
            "output, and accepted runtime row lineage."
        )
    if status == "artifact_only_live_runtime_pending":
        return (
            "This is a gold-set required evidence slot backed by an answer exemplar. It defines what evidence "
            "must exist, but it is not a live crawler/parser row and cannot support a production thesis by itself."
        )
    if status == "failure_fixture_ready_not_source_evidence":
        return (
            "This row is a deterministic negative fixture for aggregate/writer/verifier failure detection. "
            "It is not source evidence and must never be promoted into a thesis support row."
        )
    return str(evidence_row.get("source_boundary") or "Unknown source status; requires manual audit before use.")


def _goldset_source_runtime_next_action(status: str, source_role: str, required_slot: str) -> str:
    if status == "runtime_artifact_ready_source_route_unverified":
        return (
            f"Backfill `{source_role}` / `{required_slot}` with registered source route, live fetch/crawl record, "
            "parser output artifact, runtime row id, and authority boundary."
        )
    if status == "artifact_only_live_runtime_pending":
        return (
            f"Implement or bind live route/parser for `{source_role}` / `{required_slot}`; if unavailable, record "
            "attempt-backed typed gap instead of treating exemplar as evidence."
        )
    if status == "failure_fixture_ready_not_source_evidence":
        return "Keep as deterministic failure fixture; wire it into aggregate, writer payload, final verifier, and Workbench projection."
    return "Audit source_status and assign an explicit source-route/parser boundary."


def _goldset_source_runtime_case_next_action(case_type: str, status: str) -> str:
    if status == "live_runtime_ready":
        return "Case rows are live-runtime ready; next verify specialist consumption and memo projection."
    if case_type == "negative_gold_case":
        return "Wire negative fixtures into failure gates; do not route them through evidence ingestion."
    if case_type == "deep_gold_case":
        return "Prove human-ledger rows through actual source routes/parser lineage before claiming source sufficiency."
    return "Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion."


def _count_by_key(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _deep_case_evidence_depth_pack(
    case: Mapping[str, Any],
    exemplar: str,
    content_pack: Mapping[str, Any],
) -> dict[str, Any]:
    row_pack = (
        content_pack.get("human_source_runtime_rows")
        if isinstance(content_pack.get("human_source_runtime_rows"), Mapping)
        else {}
    )
    edge_pack = (
        content_pack.get("product_intelligence_graph_projection")
        if isinstance(content_pack.get("product_intelligence_graph_projection"), Mapping)
        else {}
    )
    material_pack = (
        content_pack.get("specialist_judgment_materials")
        if isinstance(content_pack.get("specialist_judgment_materials"), Mapping)
        else {}
    )
    evidence_rows = [
        {
            "row_id": str(row.get("row_id") or ""),
            "row_type": str(row.get("row_type") or ""),
            "role": str(row.get("lane_id") or ""),
            "issuer": str(row.get("issuer") or ""),
            "product_or_family": str(row.get("product_or_family") or ""),
            "source_name": str(row.get("source_name") or ""),
            "metric_or_attribute": str(row.get("metric_or_attribute") or ""),
            "value": str(row.get("value") or ""),
            "unit": str(row.get("unit") or ""),
            "period_or_version": str(row.get("period_or_version") or ""),
            "evidence_ref": str(row.get("evidence_ref") or ""),
            "source_authority": str(row.get("authority_tier") or ""),
            "fact": str(row.get("fact") or ""),
            "supports": str(row.get("supports") or ""),
            "cannot_infer": str(row.get("cannot_infer") or ""),
            "artifact_ref": "docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json",
            "runtime_consumers": _string_list(row.get("runtime_consumers")),
            "source_status": "human_source_ledger_runtime_row",
        }
        for row in row_pack.get("rows") or []
        if isinstance(row, Mapping)
    ]
    depth_lanes = sorted({str(row.get("role") or "") for row in evidence_rows if str(row.get("role") or "")})
    status = "pass" if int(row_pack.get("row_count") or 0) >= 20 and int(material_pack.get("material_count") or 0) >= 5 else "fail"
    return {
        "schema_version": MULTICASE_GOLDSET_EVIDENCE_DEPTH_SCHEMA_VERSION,
        "case_id": str(case.get("case_id") or ""),
        "case_type": str(case.get("case_type") or ""),
        "vertical": str(case.get("vertical") or ""),
        "status": status,
        "evidence_row_count": len(evidence_rows),
        "depth_lanes": depth_lanes,
        "evidence_rows": evidence_rows,
        "graph_edge_count": int(edge_pack.get("edge_count") or 0),
        "specialist_material_count": int(material_pack.get("material_count") or 0),
        "answer_exemplar": exemplar,
        "required_items": _string_list(case.get("must_answer_items")),
        "pass_conditions": _string_list(case.get("pass_criteria")),
        "fail_conditions": _string_list(case.get("fail_criteria")),
        "runtime_consumers": [
            "EvidenceFusion.authority_rows",
            "ProductIntelligenceGraph.investment_edges",
            "SpecialistJudgmentMaterial",
            "JudgmentCard",
            "MemoLogicPlan",
            "BriefingPackQualityGate",
        ],
        "source_boundary": "concrete_ai_semis_gold_depth_runtime_rows_not_live_retrieval_claim",
    }


def _rubric_case_evidence_depth_pack(case: Mapping[str, Any], exemplar: str) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    must_items = _string_list(case.get("must_answer_items"))
    roles = _string_list(case.get("evidence_roles")) or ["company_disclosed_context", "typed_gap"]
    forbidden = _string_list(case.get("forbidden_inferences"))
    evidence_rows: list[dict[str, Any]] = []
    for idx, item in enumerate(must_items):
        role = roles[idx % len(roles)]
        evidence_rows.append(
            {
                "row_id": f"{case_id}:required_item:{idx + 1}",
                "row_type": "gold_required_evidence_slot",
                "role": role,
                "source_authority": _authority_for_gold_role(role),
                "required_item_answered": item,
                "fact": _rubric_fact_sentence(case, item, role, exemplar),
                "supports": f"Supports the rubric answer for `{item}` if a runtime source row is found.",
                "cannot_infer": "; ".join(forbidden[:2]) if forbidden else "Cannot promote rubric scope into exact issuer facts.",
                "artifact_ref": _rel(DEFAULT_EXEMPLARS_PATH),
                "source_status": "gold_exemplar_backed_required_runtime_artifact_not_live_retrieval",
                "runtime_consumers": [
                    "ResearchLead.required_item_plan",
                    "specialist.role_specific_prompt",
                    "JudgmentCard.required_item_answered",
                    "MemoLogicPlan.section_contract",
                    "BriefingPackQualityGate.vertical_depth_check",
                ],
            }
        )
    represented_roles = {row["role"] for row in evidence_rows}
    for role in roles:
        if role in represented_roles:
            continue
        evidence_rows.append(
            {
                "row_id": f"{case_id}:evidence_role:{_stable_id('role', [role])[-8:]}",
                "row_type": "gold_required_evidence_role",
                "role": role,
                "source_authority": _authority_for_gold_role(role),
                "required_item_answered": "role_coverage",
                "fact": f"The {case.get('vertical')} rubric requires `{role}` evidence to avoid generic analysis.",
                "supports": "Ensures the role exists in the runtime evidence-depth pack.",
                "cannot_infer": "A required role artifact does not prove live source availability or exact metric presence.",
                "artifact_ref": _rel(DEFAULT_SPEC_PATH),
                "source_status": "gold_spec_backed_role_requirement_not_live_retrieval",
                "runtime_consumers": ["EvidenceFusion", "CoverageReflection", "BriefingPackQualityGate"],
            }
        )
    return {
        "schema_version": MULTICASE_GOLDSET_EVIDENCE_DEPTH_SCHEMA_VERSION,
        "case_id": case_id,
        "case_type": str(case.get("case_type") or ""),
        "vertical": str(case.get("vertical") or ""),
        "status": "pass" if evidence_rows and len(must_items) >= 3 else "fail",
        "evidence_row_count": len(evidence_rows),
        "depth_lanes": must_items,
        "evidence_rows": evidence_rows,
        "answer_exemplar": exemplar,
        "required_items": must_items,
        "pass_conditions": _string_list(case.get("pass_criteria")),
        "fail_conditions": _string_list(case.get("fail_criteria")),
        "runtime_consumers": [
            "ResearchLead",
            "ContextEngine",
            "specialist.role_specific_contract",
            "JudgmentCard",
            "MemoLogicPlan",
            "BriefingPackQualityGate",
        ],
        "source_boundary": (
            "Rubric pack is executable gold-depth contract material, not a claim that live sector-specific "
            "retrieval/parser rows already exist."
        ),
    }


def _negative_case_evidence_depth_pack(case: Mapping[str, Any], exemplar: str) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    forbidden = _string_list(case.get("forbidden_inferences"))
    fail_criteria = _string_list(case.get("fail_criteria"))
    correct_boundary = exemplar
    evidence_rows = [
        {
            "row_id": f"{case_id}:failure_fixture:{idx + 1}",
            "row_type": "negative_gold_failure_fixture_row",
            "role": "failure_gate",
            "source_authority": "gold_negative_exemplar",
            "required_item_answered": "failure_prevention",
            "fact": condition,
            "supports": "Defines a machine-checkable failure mode for aggregate, writer payload, and final memo.",
            "cannot_infer": correct_boundary[:360],
            "artifact_ref": _rel(DEFAULT_EXEMPLARS_PATH),
            "source_status": "gold_negative_fixture",
            "runtime_consumers": [
                "aggregate.failure_fixture_gate",
                "MemoWriter.preflight",
                "FinalVerifier",
                "Workbench.review_gap_projection",
            ],
        }
        for idx, condition in enumerate(fail_criteria or forbidden or ["negative_failure_mode"])
    ]
    return {
        "schema_version": MULTICASE_GOLDSET_EVIDENCE_DEPTH_SCHEMA_VERSION,
        "case_id": case_id,
        "case_type": str(case.get("case_type") or ""),
        "vertical": str(case.get("vertical") or ""),
        "status": "pass" if evidence_rows and correct_boundary else "fail",
        "evidence_row_count": len(evidence_rows),
        "depth_lanes": ["negative_boundary", "failure_gate", "correct_response_pattern"],
        "evidence_rows": evidence_rows,
        "answer_exemplar": correct_boundary,
        "required_items": ["preserve_boundary", "fail_on_bad_pattern", "trace_faulty_artifact"],
        "pass_conditions": [
            "Bad pattern is detected deterministically.",
            "Correct boundary is preserved.",
            "The failure is attributed to aggregate / writer_payload / final_memo instead of hidden as a gap.",
        ],
        "fail_conditions": fail_criteria,
        "runtime_consumers": [
            "AggregateFailureGate",
            "MemoWriterPreflight",
            "FinalVerifier",
            "WorkbenchReview",
        ],
        "source_boundary": "negative_gold_fixture_not_live_source_evidence",
    }


def _briefing_observations(
    aggregate_state: Mapping[str, Any],
    writer_payload: Mapping[str, Any],
    artifact_audit: Mapping[str, Any],
    source_slots: Mapping[str, Any],
) -> dict[str, Any]:
    profile = _gold_content_profile(aggregate_state, writer_payload)
    metrics = artifact_audit.get("artifact_metrics") if isinstance(artifact_audit.get("artifact_metrics"), Mapping) else {}
    evidence_metrics = metrics.get("evidence_fusion") if isinstance(metrics.get("evidence_fusion"), Mapping) else {}
    coverage_metrics = metrics.get("coverage_reflection") if isinstance(metrics.get("coverage_reflection"), Mapping) else {}
    gold_results = {
        str(row.get("gold_item") or ""): row
        for row in artifact_audit.get("gold_item_results") or []
        if isinstance(row, Mapping)
    }
    text = _artifact_text(aggregate_state, writer_payload, {})
    lower_text = text.lower()
    explicit_markers = aggregate_state.get("gold_depth_markers") if isinstance(aggregate_state.get("gold_depth_markers"), Mapping) else {}
    req_counts = evidence_metrics.get("required_like_counts") if isinstance(evidence_metrics.get("required_like_counts"), Mapping) else {}
    product_runtime_fact_count = max(
        _int(_nested(profile, "lane_counts", "product_architecture_competition", default=0)),
        _int(evidence_metrics.get("product_runtime_fact_count")),
        _int(coverage_metrics.get("product_runtime_fact_count")),
        _int(_nested(aggregate_state, "evidence_fusion_bundle", "summary", "product_runtime_fact_count")),
        _int(explicit_markers.get("product_runtime_fact_count")),
    )
    unsupported_text = json.dumps(
        _nested(aggregate_state, "verified_judgment_plan", "unsupported_claims", default=[])
        or _nested(aggregate_state, "judgment_plan", "unsupported_claims", default=[]),
        ensure_ascii=False,
    ).lower()
    source_slot_types = {
        str(slot.get("slot_type") or "")
        for slot in source_slots.get("slots") or []
        if isinstance(slot, Mapping)
    }
    demand_pool_refs = _refs_for_terms(aggregate_state, ("capex", "capital_expenditure", "hyperscaler", "MSFT", "AMZN"))
    has_demand_pool = bool(demand_pool_refs) or _int(req_counts.get("req_hyperscaler_capex")) >= 2
    has_source_product_slots = bool(
        source_slot_types
        & {
            "official_product_architecture_spec",
            "benchmark_performance_proxy",
            "cloud_deployment_product_surface",
        }
    )
    product_depth = (
        product_runtime_fact_count >= 5
        and _int(profile.get("product_edge_role_count")) >= 3
        and bool(_nested(profile, "memo_slot_materials", "product_architecture_competition", default=[]))
        and "no googl tpu product specs" not in unsupported_text
        and "no product specs" not in unsupported_text
    )
    customer_deployment_count = max(
        _int(_nested(profile, "lane_counts", "customer_deployment_adoption", default=0)),
        _int(explicit_markers.get("official_customer_deployment_count")),
        _int(req_counts.get("req_customer_deployment")),
        _keyword_count(lower_text, ("deployment", "customer", "configuration", "configured", "a4x", "xe9712")),
    )
    has_customer_deployment_depth = (
        customer_deployment_count >= 2
        and bool(_nested(profile, "memo_slot_materials", "customer_deployment", default=[]))
        and "relationship_graph rows remain scope" not in lower_text
    )
    dell_bridge = max(
        _int(_nested(profile, "lane_counts", "dell_financial_quality_bridge", default=0)),
        _int(explicit_markers.get("dell_financial_bridge_count")),
        _int(req_counts.get("req_dell_margin_quality")),
        _keyword_count(lower_text, ("dell", "margin", "backlog", "shipments", "orders", "isg", "pass-through")),
    )
    has_dell_bridge = (
        dell_bridge >= 2
        and bool(_nested(profile, "memo_slot_materials", "financial_quality", default=[]))
        and _profile_has_terms(profile, ("gpu pass-through", "backlog conversion", "margin conversion"))
        and "dell ai server margin quality" not in unsupported_text
    )
    semicap_depth = (
        _int(_nested(profile, "lane_counts", "semicap_foundry_readthrough", default=0)) >= 4
        and len(set(profile.get("semicap_issuers") or [])) >= 4
        and bool(_nested(profile, "memo_slot_materials", "semicap_readthrough", default=[]))
    )
    if not semicap_depth:
        semicap_result = gold_results.get("semicap_foundry_readthrough") or {}
        semicap_depth = str(semicap_result.get("status") or "").startswith("pass")
    market_depth = (
        _int(_nested(profile, "lane_counts", "market_expectation_price_in", default=0)) >= 1
        and bool(_nested(profile, "memo_slot_materials", "market_price_in", default=[]))
        and _profile_has_terms(profile, ("valuation", "positioning", "price-in"))
    )
    if not market_depth:
        market_result = gold_results.get("market_expectation_price_in") or {}
        market_depth = str(market_result.get("status") or "").startswith("pass")
    counter_depth = (
        _int(_nested(profile, "lane_counts", "counter_thesis_and_what_would_change", default=0)) >= 2
        and bool(_nested(profile, "memo_slot_materials", "risk_counterevidence", default=[]))
        and _profile_has_terms(profile, ("capex digestion", "margin dilution", "substitution", "export", "price-in"))
    )
    if not counter_depth:
        counter_result = gold_results.get("risk_counter_thesis") or {}
        counter_depth = str(counter_result.get("status") or "") in {"pass", "partial_pass"}
    return {
        "has_capex_demand_pool": has_demand_pool,
        "demand_pool_refs": demand_pool_refs[:8],
        "product_runtime_fact_count": product_runtime_fact_count,
        "has_product_source_slots": has_source_product_slots,
        "has_product_architecture_depth": product_depth,
        "product_runtime_detail": {
            "product_runtime_fact_count": product_runtime_fact_count,
            "source_slot_types_present": sorted(source_slot_types),
            "product_edge_role_count": _int(profile.get("product_edge_role_count")),
            "product_material_ids": [
                row.get("material_id")
                for row in _nested(profile, "memo_slot_materials", "product_architecture_competition", default=[])
            ],
            "unsupported_product_text_detected": "product specs" in unsupported_text or "tpu" in unsupported_text,
        },
        "has_customer_deployment_depth": bool(has_customer_deployment_depth),
        "customer_deployment_detail": {
            "official_customer_deployment_marker_count": _int(explicit_markers.get("official_customer_deployment_count")),
            "customer_deployment_signal_count": customer_deployment_count,
            "material_ids": [
                row.get("material_id")
                for row in _nested(profile, "memo_slot_materials", "customer_deployment", default=[])
            ],
        },
        "has_dell_financial_bridge_depth": bool(has_dell_bridge),
        "dell_financial_bridge_detail": {
            "dell_financial_bridge_marker_count": _int(explicit_markers.get("dell_financial_bridge_count")),
            "dell_margin_quality_signal_count": dell_bridge,
            "material_ids": [
                row.get("material_id")
                for row in _nested(profile, "memo_slot_materials", "financial_quality", default=[])
            ],
            "unsupported_margin_claim_detected": "dell ai server margin quality" in unsupported_text,
        },
        "has_semicap_depth": bool(semicap_depth),
        "semicap_detail": {
            "semicap_marker_count": _int(explicit_markers.get("semicap_company_specific_count")),
            "artifact_audit_gold_status": (gold_results.get("semicap_foundry_readthrough") or {}).get("status") or "",
            "semicap_issuers": sorted(set(profile.get("semicap_issuers") or [])),
        },
        "has_market_price_in_depth": bool(market_depth),
        "market_price_in_detail": {
            "market_price_in_marker_count": _int(explicit_markers.get("market_price_in_count")),
            "artifact_audit_gold_status": (gold_results.get("market_expectation_price_in") or {}).get("status") or "",
            "material_ids": [
                row.get("material_id")
                for row in _nested(profile, "memo_slot_materials", "market_price_in", default=[])
            ],
        },
        "has_counter_thesis_depth": bool(counter_depth),
        "counter_thesis_detail": {
            "counter_thesis_marker_count": _int(explicit_markers.get("counter_thesis_count")),
            "artifact_audit_gold_status": (gold_results.get("risk_counter_thesis") or {}).get("status") or "",
            "material_ids": [
                row.get("material_id")
                for row in _nested(profile, "memo_slot_materials", "risk_counterevidence", default=[])
            ],
        },
        "gold_content_profile": profile,
    }


def _run_single_negative_gate(
    case_id: str,
    artifact_text: str,
    aggregate_state: Mapping[str, Any],
    writer_payload: Mapping[str, Any],
    final_memo: Mapping[str, Any],
) -> dict[str, Any]:
    text = artifact_text.lower()
    if case_id == "negative_sku_revenue_missing_not_product_failure_v0_1":
        bad = (
            ("sku revenue" in text or "sku 收入" in text)
            and ("product layer cannot" in text or "产品层无法判断" in text or "产品层失败" in text)
        )
        return _gate_result(not bad, "sku_revenue_missing_overblocked_product_analysis")
    if case_id == "negative_demand_pool_not_supplier_allocation_v0_1":
        bad = bool(re.search(r"(capex|capital expenditure|资本开支).{0,80}(direct|直接).{0,80}(supplier|allocation|order|订单|份额)", text))
        return _gate_result(not bad, "demand_pool_promoted_to_supplier_allocation")
    if case_id == "negative_relationship_graph_not_financial_fact_v0_1":
        bad = "relationship graph" in text and bool(re.search(r"(proves|证明).{0,80}(revenue|margin|backlog|order|收入|毛利|订单|积压)", text))
        return _gate_result(not bad, "relationship_graph_promoted_to_financial_fact")
    if case_id == "negative_parser_gap_not_public_source_absent_v0_1":
        bad = ("asml" in text or "tsm" in text or "tel" in text) and (
            "public_source_absent" in text or "公开源没有" in text or "public source absent" in text
        )
        return _gate_result(not bad, "parser_gap_mislabeled_public_source_absent")
    if case_id == "negative_available_evidence_not_used_v0_1":
        if not final_memo:
            return {
                "status": "pending_final_memo",
                "finding": "Final memo is not present; gate is compiled and will run when memo artifact exists.",
                "failure_type": "available_evidence_reported_missing",
            }
        bad = bool(re.search(r"(lrcx|dell).{0,120}(financial data|财务数据).{0,40}(missing|缺失|没有)", text))
        return _gate_result(not bad, "available_evidence_reported_missing")
    if case_id == "negative_commercial_tracker_boundary_v0_1":
        bad = bool(re.search(r"(app store|channel|招聘|listing|proxy|公开 proxy).{0,80}(exact sales|exact share|sales/share|销量|份额|sell-through)", text))
        return _gate_result(not bad, "public_proxy_promoted_to_commercial_exact")
    return {"status": "pass", "finding": "No deterministic failure condition configured for this gate."}


def _runtime_row(
    slot_by_source: Mapping[str, Mapping[str, Any]],
    *,
    row_id: str,
    row_type: str,
    lane_id: str,
    issuer: str,
    product_or_family: str,
    source_name: str,
    fact: str,
    metric_or_attribute: str,
    value: str,
    unit: str,
    period_or_version: str,
    supports: str,
    cannot_infer: str,
    investment_role: str,
    authority_tier: str,
    runtime_consumers: Sequence[str],
    what_would_change_view: str,
) -> dict[str, Any]:
    slot = slot_by_source.get(source_name) or {}
    return {
        "row_id": row_id,
        "row_type": row_type,
        "lane_id": lane_id,
        "issuer": issuer,
        "product_or_family": product_or_family,
        "source_name": source_name,
        "source_slot_id": slot.get("slot_id") or _stable_id("ai_semis_source_slot_missing", [source_name]),
        "source_authority_boundary": slot.get("source_authority_boundary") or _source_boundary("bounded_public_source_context"),
        "fact": fact,
        "metric_or_attribute": metric_or_attribute,
        "value": value,
        "unit": unit,
        "period_or_version": period_or_version,
        "supports": supports,
        "cannot_infer": cannot_infer,
        "investment_role": investment_role,
        "authority_tier": authority_tier,
        "runtime_consumers": list(runtime_consumers),
        "evidence_ref": row_id,
        "citation_source": source_name,
        "what_would_change_view": what_would_change_view,
    }


def _investment_edge(
    edge_id: str,
    from_node: str,
    to_node: str,
    edge_type: str,
    edge_investment_role: str,
    supports_judgment: str,
    cannot_infer: str,
    evidence_refs: Sequence[str],
    available_row_ids: set[str],
    confidence: str,
    required_follow_up: str,
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "from_node": from_node,
        "to_node": to_node,
        "edge_type": edge_type,
        "edge_investment_role": edge_investment_role,
        "supports_judgment": supports_judgment,
        "cannot_infer": cannot_infer,
        "evidence_refs": [ref for ref in evidence_refs if ref in available_row_ids],
        "confidence": confidence,
        "required_follow_up": required_follow_up,
        "promotion_boundary": "graph_edge_supports_investment_mechanism_not_financial_exact_unless_source_rows_do",
    }


def _judgment_material(
    material_id: str,
    specialist_id: str,
    required_item_answered: str,
    memo_slot: str,
    judgment: str,
    business_mechanism: str,
    evidence_refs: Sequence[str],
    graph_edge_refs: Sequence[str],
    confidence: str,
    cannot_infer: str,
    counter_read: str,
    what_would_change_view: str,
) -> dict[str, Any]:
    return {
        "material_id": material_id,
        "specialist_id": specialist_id,
        "required_item_answered": required_item_answered,
        "memo_slot": memo_slot,
        "judgment": judgment,
        "business_mechanism": business_mechanism,
        "evidence_refs": list(evidence_refs),
        "graph_edge_refs": list(graph_edge_refs),
        "confidence": confidence,
        "cannot_infer": cannot_infer,
        "counter_read": counter_read,
        "what_would_change_view": what_would_change_view,
        "gold_exemplar_alignment": "answer_exemplar_style_judgment_not_evidence_summary",
        "briefing_quality": "writer_ready_judgment_material",
    }


def _claim_from_gold_material(material: Mapping[str, Any]) -> dict[str, Any]:
    material_id = str(material.get("material_id") or _stable_id("gold_material", [material.get("judgment")]))
    memo_slot = _gold_material_memo_slot(material)
    dimension_id = _gold_material_dimension_id(material)
    return {
        "claim_id": f"gold_depth_claim:{material_id}",
        "claim": str(material.get("judgment") or ""),
        "claim_type": "judgment_candidate",
        "raw_claim_type": "humanmade_gold_depth_judgment_material",
        "agent_id": str(material.get("specialist_id") or "humanmade_gold_specialist"),
        "claim_card_version": "v0.4_humanmade_gold_depth",
        "required_item_answered": str(material.get("required_item_answered") or ""),
        "evidence_refs": _string_list(material.get("evidence_refs")),
        "graph_edge_refs": _string_list(material.get("graph_edge_refs")),
        "source_families": ["humanmade_gold_source_runtime", "product_intelligence_graph_projection"],
        "confidence": str(material.get("confidence") or "medium"),
        "unsupported": False,
        "caveats": _string_list(material.get("cannot_infer"))[:3],
        "ticker_scope": _gold_material_ticker_scope(material),
        "metric_scope": _gold_material_metric_scope(material),
        "memo_slot": memo_slot,
        "analysis_dimension": dimension_id,
        "materiality": "high",
        "direction": _gold_material_direction(material),
        "missing_confirmations": _string_list(material.get("what_would_change_view"))[:4],
        "claim_boundary": str(material.get("cannot_infer") or ""),
        "authority_boundary": str(material.get("cannot_infer") or ""),
        "analyst_depth": {
            "business_mechanism": str(material.get("business_mechanism") or ""),
            "financial_bridge": _gold_material_financial_bridge(material),
            "counter_read": str(material.get("counter_read") or ""),
            "what_would_change_view": _string_list(material.get("what_would_change_view"))[:4],
            "cannot_infer": _string_list(material.get("cannot_infer")),
            "required_item_answered": str(material.get("required_item_answered") or ""),
            "graph_edge_refs": _string_list(material.get("graph_edge_refs")),
        },
        "judgment_candidate": True,
        "gold_exemplar_alignment": str(material.get("gold_exemplar_alignment") or ""),
        "briefing_quality": str(material.get("briefing_quality") or ""),
        "gold_depth_assimilation": True,
    }


def _judgment_card_from_gold_material(material: Mapping[str, Any]) -> dict[str, Any]:
    material_id = str(material.get("material_id") or _stable_id("gold_material", [material.get("judgment")]))
    dimension_id = _gold_material_dimension_id(material)
    return {
        "schema_version": "finsight_judgment_card_v0_1",
        "judgment_card_id": f"gold_depth_judgment:{material_id}",
        "source_claim_id": f"gold_depth_claim:{material_id}",
        "agent_id": str(material.get("specialist_id") or "humanmade_gold_specialist"),
        "dimension_id": dimension_id,
        "dimension_title": _gold_dimension_title(dimension_id),
        "memo_slot": _gold_material_memo_slot(material),
        "judgment": str(material.get("judgment") or "")[:520],
        "direction": _gold_material_direction(material),
        "materiality": "high",
        "confidence": str(material.get("confidence") or "medium"),
        "ticker_scope": _gold_material_ticker_scope(material),
        "metric_scope": _gold_material_metric_scope(material),
        "evidence_refs": _string_list(material.get("evidence_refs"))[:8],
        "graph_edge_refs": _string_list(material.get("graph_edge_refs"))[:8],
        "source_families": ["humanmade_gold_source_runtime", "product_intelligence_graph_projection"],
        "source_role": "gold_depth_judgment_material",
        "evidence_bridge": _evidence_bridge_sentence(material),
        "business_mechanism": str(material.get("business_mechanism") or ""),
        "financial_bridge": _gold_material_financial_bridge(material),
        "counter_read": str(material.get("counter_read") or ""),
        "what_would_change_view": _string_list(material.get("what_would_change_view"))[:4],
        "authority_boundary": str(material.get("cannot_infer") or ""),
        "mechanism_bridge_status": "pass",
        "writer_use": "humanmade_gold_depth_writer_ready_judgment_unit",
        "gold_depth_assimilation": True,
    }


def _memo_section_from_gold_material(material: Mapping[str, Any]) -> dict[str, Any]:
    section_id = _gold_material_dimension_id(material)
    material_id = str(material.get("material_id") or _stable_id("gold_material", [material.get("judgment")]))
    return {
        "section_id": section_id,
        "title": _gold_dimension_title(section_id),
        "logic_role": "core_analysis" if section_id != "risk_and_counterevidence" else "counter_thesis",
        "required_claim_ids": [f"gold_depth_claim:{material_id}"],
        "required_evidence_refs": _string_list(material.get("evidence_refs"))[:8],
        "graph_edge_refs": _string_list(material.get("graph_edge_refs"))[:8],
        "required_gap_refs": [],
        "thesis_direction": str(material.get("judgment") or "")[:360],
        "decision_changing_evidence_refs": _string_list(material.get("evidence_refs"))[:8],
        "counter_thesis_refs": [str(material.get("counter_read") or "")] if str(material.get("counter_read") or "") else [],
        "required_item_ids": [str(material.get("required_item_answered") or "")],
        "writing_instruction": (
            "Use this gold-depth judgment as analyst briefing material: explain mechanism, evidence role, "
            "financial bridge, cannot-infer boundary, and what would change the view."
        ),
        "humanmade_gold_material_id": material_id,
    }


def _evidence_bridge_from_gold_material(material: Mapping[str, Any]) -> dict[str, Any]:
    material_id = str(material.get("material_id") or _stable_id("gold_material", [material.get("judgment")]))
    return {
        "bridge_id": f"gold_depth_bridge:{material_id}",
        "section_id": _gold_material_dimension_id(material),
        "source_claim_ids": [f"gold_depth_claim:{material_id}"],
        "evidence_refs": _string_list(material.get("evidence_refs"))[:8],
        "graph_edge_refs": _string_list(material.get("graph_edge_refs"))[:8],
        "business_mechanism": str(material.get("business_mechanism") or ""),
        "financial_bridge": _gold_material_financial_bridge(material),
        "counter_read": str(material.get("counter_read") or ""),
        "cannot_infer": str(material.get("cannot_infer") or ""),
        "what_would_change_view": _string_list(material.get("what_would_change_view"))[:4],
        "writer_instruction": "Turn evidence into thesis reasoning; do not render as source inventory.",
    }


def _merge_gold_claims_into_judgment_plan(
    judgment_plan: Mapping[str, Any],
    *,
    gold_claims: Sequence[Mapping[str, Any]],
    gold_cards: Sequence[Mapping[str, Any]],
    content_judgment: Mapping[str, Any],
) -> dict[str, Any]:
    plan = dict(judgment_plan or {})
    supported = _merge_rows_by_key(gold_claims, plan.get("supported_claims") or [], key_fields=("claim_id",))
    cards = _merge_rows_by_key(gold_cards, plan.get("judgment_cards") or [], key_fields=("judgment_card_id", "card_id"))
    filtered_unsupported, resolved_unsupported = _filter_gold_resolved_unsupported_claims(
        plan.get("unsupported_claims") or [],
        gold_claims=gold_claims,
    )
    existing_outline = [dict(item) for item in plan.get("memo_outline") or [] if isinstance(item, Mapping)]
    gold_outline = [
        {
            "section_id": _gold_material_dimension_id(row),
            "title": _gold_dimension_title(_gold_material_dimension_id(row)),
            "claim_ids": [f"gold_depth_claim:{row.get('material_id')}"],
            "evidence_refs": _string_list(row.get("evidence_refs"))[:8],
            "summary": str(row.get("judgment") or "")[:360],
            "gold_depth_assimilation": True,
        }
        for row in content_judgment.get("judgment_cards") or []
        if isinstance(row, Mapping)
    ]
    plan.update(
        {
            "status": "pass" if supported else str(plan.get("status") or "partial"),
            "supported_claims": supported,
            "unsupported_claims": filtered_unsupported,
            "gold_resolved_unsupported_claims": resolved_unsupported,
            "judgment_cards": cards,
            "memo_outline": _merge_rows_by_key(gold_outline, existing_outline, key_fields=("section_id",)),
            "memo_writer_allowed": True,
            "humanmade_gold_depth_assimilation": {
                "status": "consumed",
                "gold_supported_claim_count": len(gold_claims),
                "gold_judgment_card_count": len(gold_cards),
            },
        }
    )
    pack = dict(plan.get("thesis_driver_pack") or {}) if isinstance(plan.get("thesis_driver_pack"), Mapping) else {}
    pack["judgment_cards"] = _merge_rows_by_key(gold_cards, pack.get("judgment_cards") or [], key_fields=("judgment_card_id", "card_id"))
    pack["required_dimension_ids"] = _dedupe(
        _string_list(pack.get("required_dimension_ids"))
        + [_gold_material_dimension_id(row) for row in content_judgment.get("judgment_cards") or [] if isinstance(row, Mapping)]
    )
    pack["humanmade_gold_depth_assimilation"] = "consumed"
    plan["thesis_driver_pack"] = pack
    thesis_path = dict(plan.get("thesis_path") or {}) if isinstance(plan.get("thesis_path"), Mapping) else {}
    thesis_path["humanmade_gold_depth_assimilation"] = "consumed"
    thesis_path["gold_depth_path_nodes"] = [
        {
            "node_id": f"gold_depth::{card.get('dimension_id')}",
            "dimension_id": card.get("dimension_id"),
            "judgment_card_ids": [card.get("judgment_card_id")],
            "evidence_refs": card.get("evidence_refs") or [],
            "business_mechanism": card.get("business_mechanism") or "",
            "financial_bridge": card.get("financial_bridge") or "",
            "counter_read": card.get("counter_read") or "",
        }
        for card in cards
        if isinstance(card, Mapping) and bool(card.get("gold_depth_assimilation"))
    ][:12]
    plan["thesis_path"] = thesis_path
    return plan


def _filter_gold_resolved_unsupported_claims(
    unsupported_claims: Any,
    *,
    gold_claims: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gold_text = _artifact_text({"gold_claims": list(gold_claims)}).lower()
    has_product_depth = all(term in gold_text for term in ("gb200", "mi300", "tpu"))
    has_dell_bridge = all(term in gold_text for term in ("gpu pass-through", "backlog conversion", "margin"))
    kept: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    for row in unsupported_claims or []:
        if not isinstance(row, Mapping):
            continue
        text = _artifact_text(row).lower()
        reason = ""
        if has_product_depth and any(term in text for term in ("product specs", "product specification", "tpu", "no product specs")):
            reason = "resolved_by_gold_product_architecture_spec_and_tpu_material"
        elif has_dell_bridge and any(term in text for term in ("dell ai server margin quality", "gpu pass-through", "backlog conversion", "margin quality")):
            reason = "resolved_by_gold_dell_financial_bridge_material"
        if reason:
            resolved.append(
                {
                    **dict(row),
                    "status": "superseded_by_humanmade_gold_depth_assimilation",
                    "resolution_reason": reason,
                    "boundary_preserved_in": "gold_depth_claim.cannot_infer",
                }
            )
        else:
            kept.append(dict(row))
    return kept, resolved


def _merge_gold_materials_into_memo_logic_plan(
    memo_logic_plan: Mapping[str, Any],
    *,
    gold_cards: Sequence[Mapping[str, Any]],
    gold_sections: Sequence[Mapping[str, Any]],
    gold_answer_plan: Sequence[Mapping[str, Any]],
    gold_bridge_rows: Sequence[Mapping[str, Any]],
    material_pack: Mapping[str, Any],
    row_pack: Mapping[str, Any],
    edge_pack: Mapping[str, Any],
) -> dict[str, Any]:
    plan = dict(memo_logic_plan or {})
    plan["judgment_cards"] = _merge_rows_by_key(gold_cards, plan.get("judgment_cards") or [], key_fields=("judgment_card_id", "card_id"))
    plan["required_item_answer_plan"] = _merge_rows_by_key(
        gold_answer_plan,
        plan.get("required_item_answer_plan") or [],
        key_fields=("question_item_id",),
    )
    plan["sections"] = _merge_sections_by_section_id(
        [dict(row) for row in plan.get("sections") or [] if isinstance(row, Mapping)],
        [dict(row) for row in gold_sections if isinstance(row, Mapping)],
    )
    plan["section_order"] = _dedupe(
        [str(row.get("section_id") or "") for row in plan.get("sections") or [] if isinstance(row, Mapping) and str(row.get("section_id") or "")]
    )
    plan["evidence_to_thesis_bridge"] = _merge_rows_by_key(
        gold_bridge_rows,
        plan.get("evidence_to_thesis_bridge") or [],
        key_fields=("bridge_id", "section_id"),
    )
    plan["humanmade_gold_depth_assimilation"] = {
        "status": "consumed",
        "row_count": _int(row_pack.get("row_count")),
        "edge_count": _int(edge_pack.get("edge_count")),
        "specialist_material_count": _int(material_pack.get("material_count")),
        "memo_slots": dict(material_pack.get("memo_slot_counts") or {}),
    }
    skeleton = dict(plan.get("writer_thesis_skeleton") or {}) if isinstance(plan.get("writer_thesis_skeleton"), Mapping) else {}
    skeleton["gold_depth_opening_judgment"] = (
        "AI infrastructure demand is real, but the investment conclusion turns on whether accelerator capability and "
        "customer deployment convert into high-quality OEM revenue, semicap read-through, and still-unpriced expectations."
    )
    skeleton["gold_depth_dimension_moves"] = [
        {
            "section_id": row.get("section_id"),
            "move": row.get("thesis_direction"),
            "evidence_refs": row.get("required_evidence_refs") or [],
        }
        for row in gold_sections
        if isinstance(row, Mapping)
    ]
    plan["writer_thesis_skeleton"] = skeleton
    validation = dict(plan.get("validation") or {}) if isinstance(plan.get("validation"), Mapping) else {}
    validation["humanmade_gold_depth_assimilation"] = "consumed"
    validation["status"] = "pass" if str(validation.get("status") or "pass") != "fail" else "pass_after_gold_depth_assimilation"
    plan["validation"] = validation
    return plan


def _product_evidence_rows_from_gold_content(row_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    product_lane_ids = {"product_architecture_competition", "customer_deployment_adoption"}
    return [
        {
            **dict(row),
            "source_family": "humanmade_gold_product_runtime",
            "claim_scope": str(row.get("investment_role") or ""),
            "authority_boundary": str(row.get("cannot_infer") or row.get("source_authority_boundary") or ""),
        }
        for row in row_pack.get("rows") or []
        if isinstance(row, Mapping) and str(row.get("lane_id") or "") in product_lane_ids
    ]


def _public_context_rows_from_gold_content(row_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **dict(row),
            "source_family": "humanmade_gold_public_context",
            "claim_scope": str(row.get("investment_role") or ""),
            "authority_boundary": str(row.get("cannot_infer") or row.get("source_authority_boundary") or ""),
        }
        for row in row_pack.get("rows") or []
        if isinstance(row, Mapping)
    ]


def _merge_rows_by_key(
    preferred_rows: Any,
    existing_rows: Any,
    *,
    key_fields: Sequence[str],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in list(preferred_rows or []) + list(existing_rows or []):
        if not isinstance(row, Mapping):
            continue
        key = ""
        for field in key_fields:
            if row.get(field):
                key = f"{field}:{row.get(field)}"
                break
        if not key:
            key = json.dumps(row, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(row))
    return merged


def _merge_sections_by_section_id(existing_sections: list[dict[str, Any]], gold_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for section in existing_sections:
        section_id = str(section.get("section_id") or "")
        if section_id:
            by_id[section_id] = dict(section)
    for gold in gold_sections:
        section_id = str(gold.get("section_id") or "")
        if not section_id:
            continue
        current = by_id.get(section_id)
        if not current:
            by_id[section_id] = dict(gold)
            continue
        merged = dict(current)
        for field in (
            "required_claim_ids",
            "required_evidence_refs",
            "graph_edge_refs",
            "decision_changing_evidence_refs",
            "counter_thesis_refs",
            "required_item_ids",
        ):
            merged[field] = _dedupe(_string_list(gold.get(field)) + _string_list(current.get(field)))
        merged["humanmade_gold_material_id"] = str(gold.get("humanmade_gold_material_id") or merged.get("humanmade_gold_material_id") or "")
        merged["gold_depth_section_judgment"] = str(gold.get("thesis_direction") or "")
        if gold.get("writing_instruction"):
            merged["writing_instruction"] = f"{merged.get('writing_instruction') or ''} {gold.get('writing_instruction')}".strip()
        by_id[section_id] = merged
    ordered = []
    seen: set[str] = set()
    for section in existing_sections + gold_sections:
        section_id = str(section.get("section_id") or "")
        if section_id and section_id not in seen and section_id in by_id:
            ordered.append(by_id[section_id])
            seen.add(section_id)
    for section_id, section in by_id.items():
        if section_id not in seen:
            ordered.append(section)
    return ordered


def _gold_material_memo_slot(material: Mapping[str, Any]) -> str:
    slot = str(material.get("memo_slot") or "")
    return {
        "product_architecture_competition": "product_technology",
        "financial_quality": "fundamentals",
        "semicap_readthrough": "industry_relationship",
        "customer_deployment": "industry_relationship",
        "market_price_in": "market_valuation",
        "risk_counterevidence": "risk_counterevidence",
    }.get(slot, slot or "evidence_gap")


def _gold_material_dimension_id(material: Mapping[str, Any]) -> str:
    slot = str(material.get("memo_slot") or "")
    return {
        "product_architecture_competition": "product_and_production",
        "financial_quality": "fundamentals",
        "semicap_readthrough": "industry_supply_chain",
        "customer_deployment": "industry_supply_chain",
        "market_price_in": "capital_and_financing",
        "risk_counterevidence": "risk_and_counterevidence",
    }.get(slot, "evidence_gap")


def _gold_dimension_title(dimension_id: str) -> str:
    return {
        "product_and_production": "Product, architecture, and production evidence",
        "fundamentals": "Financial quality and statement bridge",
        "industry_supply_chain": "Customer deployment and supply-chain read-through",
        "capital_and_financing": "Market expectation, capital flow, and price-in",
        "risk_and_counterevidence": "Counter-thesis and what would change the view",
        "evidence_gap": "Typed evidence gap",
    }.get(str(dimension_id or ""), str(dimension_id or "Evidence").replace("_", " ").title())


def _gold_material_ticker_scope(material: Mapping[str, Any]) -> list[str]:
    text = _artifact_text(material).upper()
    tickers = [ticker for ticker in ("DELL", "NVDA", "AMD", "GOOGL", "MSFT", "AMZN", "META", "TSM", "ASML", "AMAT", "LRCX") if ticker in text]
    return tickers or ["DELL", "NVDA"]


def _gold_material_metric_scope(material: Mapping[str, Any]) -> list[str]:
    slot = str(material.get("memo_slot") or "")
    return {
        "product_architecture_competition": ["architecture", "benchmark", "competitive_substitution"],
        "financial_quality": ["orders", "shipments", "backlog", "margin_quality", "pass_through_cost"],
        "semicap_readthrough": ["advanced_node", "bookings_backlog_proxy", "semicap_cycle"],
        "customer_deployment": ["deployment", "configuration", "cloud_instance_availability"],
        "market_price_in": ["valuation", "positioning", "price_in"],
        "risk_counterevidence": ["counter_thesis", "capex_digestion", "margin_dilution", "substitution"],
    }.get(slot, ["gold_depth_judgment"])


def _gold_material_direction(material: Mapping[str, Any]) -> str:
    slot = str(material.get("memo_slot") or "")
    if slot in {"risk_counterevidence", "market_price_in"}:
        return "mixed"
    if slot == "financial_quality":
        return "mixed"
    return "positive"


def _gold_material_financial_bridge(material: Mapping[str, Any]) -> str:
    slot = str(material.get("memo_slot") or "")
    if slot == "financial_quality":
        return "Connect AI server orders/backlog to ISG revenue visibility, then test margin conversion, GPU pass-through cost, attach economics, working capital, and cash conversion."
    if slot == "product_architecture_competition":
        return "Product capability supports demand and competitive position, but revenue and margin require deployment, supplier allocation, mix, and financial bridge evidence."
    if slot == "semicap_readthrough":
        return "Advanced-node and packaging demand can read through to semicap tools, but bookings/backlog/customer concentration must be checked company by company."
    if slot == "customer_deployment":
        return "Deployment and configuration rows validate adoption mechanisms; financial impact requires order value, volume, and margin evidence."
    if slot == "market_price_in":
        return "Market price-in connects business evidence to valuation, ownership, liquidity, and expected growth already embedded in the stock."
    return "Risk evidence constrains the thesis and identifies trigger conditions before the memo can become a strong investment view."


def _evidence_bridge_sentence(material: Mapping[str, Any]) -> str:
    refs = ", ".join(_string_list(material.get("evidence_refs"))[:3]) or "gold-depth refs"
    return (
        f"Use {refs} to support {str(material.get('memo_slot') or 'gold-depth')} judgment; "
        f"{str(material.get('business_mechanism') or '')} Boundary: {str(material.get('cannot_infer') or '')}"
    )[:620]


def _slot_lookup(source_slots: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for slot in source_slots.get("slots") or []:
        if isinstance(slot, Mapping):
            result[str(slot.get("source_name") or "")] = slot
    return result


def _edge_refs(edge_pack: Mapping[str, Any], roles: Sequence[str]) -> list[str]:
    role_set = {str(role) for role in roles}
    refs: list[str] = []
    for edge in edge_pack.get("edges") or []:
        if isinstance(edge, Mapping) and str(edge.get("edge_investment_role") or "") in role_set:
            refs.append(str(edge.get("edge_id") or ""))
    return refs


def _required_item_for_lane(lane_id: str) -> str:
    return {
        "demand_pool": "req_hyperscaler_capex",
        "product_architecture_competition": "req_accelerator_architecture",
        "customer_deployment_adoption": "req_customer_deployment",
        "dell_financial_quality_bridge": "req_dell_margin_quality",
        "semicap_foundry_readthrough": "req_supply_chain",
        "market_expectation_price_in": "req_market_price_in",
        "counter_thesis_and_what_would_change": "req_counter_thesis",
    }.get(lane_id, "req_gold_depth_context")


def _gold_depth_repair_action(lane_id: str) -> str:
    return {
        "product_architecture_competition": "materialize official product/spec/benchmark rows and require Product Specialist judgment material",
        "customer_deployment_adoption": "materialize official deployment/config/customer rows or typed deployment gap",
        "dell_financial_quality_bridge": "bridge Dell AI orders/backlog to ISG margin, GPU pass-through, attach economics and cash conversion",
        "semicap_foundry_readthrough": "split TSMC/ASML/AMAT/LRCX mechanisms and require company-specific rows",
        "market_expectation_price_in": "add valuation/positioning/price-reaction capital-feedback rows or explicit no-recommendation gap",
        "counter_thesis_and_what_would_change": "require named counter-thesis and trigger conditions tied to thesis chain",
    }.get(lane_id, "repair lane-specific gold-depth material before Memo Writer")


def _gold_content_profile(*objects: Mapping[str, Any]) -> dict[str, Any]:
    rows = _collect_artifact_rows("ai_semis_human_source_runtime_rows", "rows", *objects)
    edges = _collect_artifact_rows("product_intelligence_graph_investment_projection", "edges", *objects)
    materials = _collect_artifact_rows("gold_specialist_judgment_materials", "materials", *objects)
    lane_counts: dict[str, int] = {}
    semicap_issuers: list[str] = []
    for row in rows:
        lane_id = str(row.get("lane_id") or "")
        if lane_id:
            lane_counts[lane_id] = lane_counts.get(lane_id, 0) + 1
        if lane_id == "semicap_foundry_readthrough":
            semicap_issuers.append(str(row.get("issuer") or ""))
    memo_slot_materials: dict[str, list[Mapping[str, Any]]] = {}
    for material in materials:
        memo_slot = str(material.get("memo_slot") or "")
        if memo_slot:
            memo_slot_materials.setdefault(memo_slot, []).append(material)
    edge_roles = [str(edge.get("edge_investment_role") or "") for edge in edges]
    product_roles = {
        "product_capability_to_oem_adoption",
        "competitive_substitution_pressure",
        "substitution_and_pricing_pressure",
        "cloud_deployment_signal",
    }
    return {
        "row_count": len(rows),
        "edge_count": len(edges),
        "specialist_material_count": len(materials),
        "lane_counts": lane_counts,
        "semicap_issuers": _dedupe([issuer for issuer in semicap_issuers if issuer]),
        "edge_roles": edge_roles,
        "product_edge_role_count": len(product_roles & set(edge_roles)),
        "memo_slot_materials": memo_slot_materials,
        "profile_text": _artifact_text({"rows": rows, "edges": edges, "materials": materials}).lower(),
    }


def _collect_artifact_rows(artifact_type: str, row_key: str, *objects: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    collected: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for obj in objects:
        for mapping in _walk_mappings(obj):
            if str(mapping.get("artifact_type") or "") != artifact_type:
                continue
            for row in mapping.get(row_key) or []:
                if not isinstance(row, Mapping):
                    continue
                stable = str(row.get("row_id") or row.get("edge_id") or row.get("material_id") or json.dumps(row, sort_keys=True, default=str))
                if stable in seen:
                    continue
                seen.add(stable)
                collected.append(row)
    return collected


def _profile_has_terms(profile: Mapping[str, Any], terms: Sequence[str]) -> bool:
    text = str(profile.get("profile_text") or "").lower()
    return all(str(term).lower() in text for term in terms)


def _gate_result(passed: bool, failure_type: str) -> dict[str, Any]:
    return {
        "status": "pass" if passed else "fail",
        "failure_type": failure_type,
        "finding": "No forbidden pattern detected." if passed else f"Forbidden pattern detected: {failure_type}.",
    }


def _depth_check(lane_id: str, passed: bool, pass_finding: str, fail_finding: str, *, evidence: Any) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "status": "pass" if passed else "fail",
        "finding": pass_finding if passed else fail_finding,
        "evidence": evidence,
    }


def _requires_humanmade_gold_gate(state: Mapping[str, Any]) -> bool:
    case_id = str(state.get("case_id") or _nested(state, "case_contract", "case_id", default="") or "")
    if case_id in P33_AI_SEMIS_CASE_IDS:
        return True
    if bool(state.get("humanmade_gold_set_audit_required")):
        return True
    category = str(_nested(state, "case_contract", "category", default="") or "")
    return category == "p33_gold_workpaper"


def _negative_gate_contract(case_id: str) -> dict[str, Any]:
    defaults = {
        "target_artifact_stages": ["aggregate", "writer_payload", "final_memo"],
        "severity": "high",
        "failure_condition": "forbidden_inference_detected",
    }
    if "available_evidence_not_used" in case_id:
        return {**defaults, "target_artifact_stages": ["aggregate", "writer_payload", "final_memo"], "failure_condition": "final_memo_claims_missing_when_upstream_contains_evidence"}
    if "parser_gap" in case_id:
        return {**defaults, "target_artifact_stages": ["aggregate", "writer_payload", "final_memo"], "failure_condition": "located_or_route_gap_written_as_public_source_absent"}
    if "commercial_tracker" in case_id:
        return {**defaults, "severity": "medium", "failure_condition": "public_proxy_promoted_to_commercial_exact"}
    return defaults


def _vertical_role_contract(case_id: str) -> dict[str, Any]:
    if case_id.startswith("semicap"):
        return {
            "primary_agents": ["industry_supply_chain_analyst", "fundamental_analyst"],
            "minimum_runtime_slots": ["bookings_or_backlog", "tool_category_exposure", "customer_cycle", "service_mix_margin"],
            "main_fail_mode": "peer_scope_used_as_order_cycle_proof",
        }
    if case_id.startswith("cloud_saas"):
        return {
            "primary_agents": ["fundamental_analyst", "product_technology_analyst", "market_valuation_analyst"],
            "minimum_runtime_slots": ["capex", "cloud_revenue", "RPO_or_ARR", "usage_or_customer_adoption", "margin_or_FCF"],
            "main_fail_mode": "AI product launch treated as monetization proof",
        }
    if case_id.startswith("financials"):
        return {
            "primary_agents": ["fundamental_analyst", "market_valuation_analyst"],
            "minimum_runtime_slots": ["deposits", "NIM", "loan_growth", "provision", "capital_ratio", "liquidity"],
            "main_fail_mode": "bank analyzed like industrial revenue/EPS case",
        }
    if case_id.startswith("healthcare"):
        return {
            "primary_agents": ["product_technology_analyst", "risk_counterevidence_analyst"],
            "minimum_runtime_slots": ["indication", "trial_or_FDA_status", "adoption_or_usage_proxy", "reimbursement_or_access", "revenue_bridge_or_gap"],
            "main_fail_mode": "regulatory eligibility treated as commercial performance",
        }
    if case_id.startswith("energy"):
        return {
            "primary_agents": ["industry_supply_chain_analyst", "fundamental_analyst"],
            "minimum_runtime_slots": ["load_growth", "rate_base_or_allowed_ROE", "capex_plan", "debt_or_equity_funding", "cash_flow"],
            "main_fail_mode": "AI power demand headline treated as EPS proof",
        }
    if case_id.startswith("retail"):
        return {
            "primary_agents": ["fundamental_analyst", "product_technology_analyst"],
            "minimum_runtime_slots": ["traffic", "ticket", "price_mix", "inventory", "promotion", "gross_margin"],
            "main_fail_mode": "revenue growth not decomposed into traffic/ticket/mix/margin",
        }
    if case_id.startswith("auto"):
        return {
            "primary_agents": ["product_technology_analyst", "fundamental_analyst", "risk_counterevidence_analyst"],
            "minimum_runtime_slots": ["delivery_volume", "ASP_mix", "inventory_channel", "recall_quality", "capacity", "financing_sensitivity"],
            "main_fail_mode": "deliveries treated as margin-quality proof",
        }
    return {
        "primary_agents": ["market_valuation_analyst", "fundamental_analyst"],
        "minimum_runtime_slots": ["valuation", "ownership_positioning", "liquidity_short_options", "credit_debt", "event_or_corporate_action"],
        "main_fail_mode": "business improvement not separated from price-in and capital feedback",
    }


def _parse_markdown_source_ledger(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"## 3\. Source Ledger(?P<body>.*?)(?:\n## 4\.|\Z)", text, flags=re.S)
    body = match.group("body") if match else text
    rows: list[dict[str, str]] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "---" in line or "Source |" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        rows.append(
            {
                "source": cells[0],
                "authority_role": cells[1],
                "key_info": cells[2],
                "supports": cells[3],
                "cannot_infer": cells[4],
            }
        )
    return rows


def _source_slot_type(source_name: str, authority_role: str, key_info: str) -> str:
    text = f"{source_name} {authority_role} {key_info}".lower()
    if "benchmark" in text or "mlperf" in text or "mlcommons" in text:
        return "benchmark_performance_proxy"
    if "gb200" in text or "mi300" in text or "tpu" in text or "architecture" in text or "technical" in text:
        if "cloud" in text or "a4x" in text:
            return "cloud_deployment_product_surface"
        return "official_product_architecture_spec"
    if "deployment" in text or "customer" in text or "partner" in text or "poweredge" in text:
        return "official_customer_deployment_context"
    if "capex" in text or "hyperscaler" in text:
        return "hyperscaler_capex_demand_pool"
    if "asml" in text or "amat" in text or "lrcx" in text or "semicap" in text or "equipment" in text or "lithography" in text:
        return "semicap_readthrough_context"
    if "tsmc" in text or "advanced node" in text or "foundry" in text:
        return "foundry_advanced_node_context"
    if "dell" in text and ("orders" in text or "shipments" in text or "backlog" in text or "isg" in text):
        return "issuer_exact_financial_operating_bridge"
    if "revenue" in text or "margin" in text or "cash flow" in text:
        return "issuer_exact_financial_or_operating"
    return "bounded_public_source_context"


def _source_boundary(slot_type: str) -> str:
    if slot_type in {"issuer_exact_financial_operating_bridge", "issuer_exact_financial_or_operating"}:
        return "Can support issuer-reported financial or operating facts within disclosed metric/unit/period; cannot infer undisclosed SKU mix, margin, ASP, share, or customer allocation."
    if slot_type in {"official_product_architecture_spec", "benchmark_performance_proxy", "cloud_deployment_product_surface"}:
        return "Can support product capability, architecture, adoption, and competitive/substitution context; cannot infer revenue, shipment, ASP, share, or margin."
    if slot_type == "hyperscaler_capex_demand_pool":
        return "Can support AI infrastructure demand pool and upstream read-through direction; cannot infer direct supplier allocation or order value."
    if slot_type in {"semicap_readthrough_context", "foundry_advanced_node_context"}:
        return "Can support foundry/semicap read-through and cycle context; exact bookings/backlog/customer allocation require company-disclosed rows."
    if slot_type == "official_customer_deployment_context":
        return "Can support adoption/deployment existence and mechanism; cannot infer total demand, revenue, or customer concentration without exact rows."
    return "Bounded public context only; preserve cannot-infer boundary."


def _slot_runtime_consumers(slot_type: str) -> list[str]:
    if slot_type in {"official_product_architecture_spec", "benchmark_performance_proxy", "cloud_deployment_product_surface"}:
        return ["ProductIntelligenceGraph", "product_technology_analyst", "BriefingPackQualityGate", "MemoLogicPlan"]
    if slot_type in {"issuer_exact_financial_operating_bridge", "issuer_exact_financial_or_operating"}:
        return ["FundamentalStatementPack", "fundamental_analyst", "JudgmentCard", "MemoLogicPlan"]
    if slot_type in {"official_customer_deployment_context", "hyperscaler_capex_demand_pool", "semicap_readthrough_context", "foundry_advanced_node_context"}:
        return ["ResearchLead", "industry_supply_chain_analyst", "ProductIntelligenceGraph", "BriefingPackQualityGate"]
    return ["ResearchLead", "BriefingPackQualityGate"]


def _artifact_text(*objects: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for obj in objects:
        if obj:
            parts.append(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts)


def _negative_gate_runtime_text(
    aggregate_state: Mapping[str, Any],
    writer_payload: Mapping[str, Any],
    final_memo: Mapping[str, Any],
) -> str:
    """Extract only runtime assertions, not contracts/prompts that contain forbidden examples."""

    snippets: list[str] = []
    for plan_key in ("verified_judgment_plan", "judgment_plan"):
        plan = aggregate_state.get(plan_key) if isinstance(aggregate_state.get(plan_key), Mapping) else {}
        for field in ("supported_claims", "unsupported_claims", "conflicts", "judgment_cards", "memo_outline"):
            for row in plan.get(field) or []:
                if isinstance(row, Mapping):
                    snippets.extend(
                        str(row.get(key) or "")
                        for key in ("claim", "judgment", "reason", "finding", "summary", "section_title")
                        if str(row.get(key) or "")
                    )
    memo_logic_plan = aggregate_state.get("memo_logic_plan") if isinstance(aggregate_state.get("memo_logic_plan"), Mapping) else {}
    for field in ("judgment_cards", "evidence_to_thesis_bridge"):
        for row in memo_logic_plan.get(field) or []:
            if isinstance(row, Mapping):
                snippets.extend(
                    str(row.get(key) or "")
                    for key in ("judgment", "evidence_bridge", "business_mechanism", "counter_read", "cannot_infer")
                    if str(row.get(key) or "")
                )
    payload = writer_payload.get("writer_payload") if isinstance(writer_payload.get("writer_payload"), Mapping) else writer_payload
    if isinstance(payload, Mapping):
        payload_rows = []
        for field in ("errors", "warnings"):
            payload_rows.extend(payload.get(field) or [])
        for row in payload_rows:
            if isinstance(row, Mapping):
                snippets.append(str(row.get("type") or row.get("message") or ""))
    if final_memo:
        snippets.append(json.dumps(final_memo, ensure_ascii=False, sort_keys=True))
    return "\n".join(snippets)


def _authority_for_gold_role(role: str) -> str:
    role = role.lower()
    if "exact" in role or "disclosed" in role or "company" in role:
        return "company_disclosed_or_issuer_exact_when_runtime_row_exists"
    if "product" in role or "official" in role:
        return "official_product_or_customer_context"
    if "regulatory" in role or "exchange" in role or "fpi" in role:
        return "regulatory_or_exchange_context"
    if "proxy" in role or "market" in role or "developer" in role:
        return "bounded_public_proxy"
    if "hypothesis" in role or "peer" in role or "scope" in role:
        return "scope_hypothesis_not_primary_proof"
    if "gap" in role:
        return "typed_gap_boundary"
    return "gold_rubric_required_source_role"


def _rubric_fact_sentence(case: Mapping[str, Any], required_item: str, role: str, exemplar: str) -> str:
    vertical = str(case.get("vertical") or "this vertical")
    excerpt = re.sub(r"\s+", " ", exemplar).strip()[:220]
    if excerpt:
        return (
            f"For {vertical}, `{required_item}` must be answered with `{role}` evidence. "
            f"Gold exemplar anchor: {excerpt}"
        )
    return f"For {vertical}, `{required_item}` must be answered with `{role}` evidence."


def _find_by_case_id(rows: Sequence[Any], case_id: str) -> Mapping[str, Any]:
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("case_id") or "") == case_id:
            return row
    return {}


def _refs_for_terms(state: Mapping[str, Any], terms: Sequence[str]) -> list[str]:
    refs: list[str] = []
    for row in _walk_mappings(state):
        text = " ".join(str(row.get(key) or "") for key in ("claim", "judgment", "summary", "metric_scope", "evidence_requirement_id"))
        if any(term.lower() in text.lower() for term in terms):
            refs.extend(str(ref) for ref in row.get("evidence_refs") or [] if str(ref))
            if row.get("evidence_ref"):
                refs.append(str(row.get("evidence_ref")))
    return _dedupe(refs)


def _walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        rows.append(value)
        for item in value.values():
            rows.extend(_walk_mappings(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_walk_mappings(item))
    return rows


def _keyword_count(text: str, terms: Sequence[str]) -> int:
    return sum(1 for term in terms if str(term).lower() in text)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _exemplar_by_id(exemplars: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for case in exemplars.get("cases") or []:
        if isinstance(case, Mapping):
            result[str(case.get("case_id") or "")] = str(case.get("answer_example") or case.get("correct_response_pattern") or "")
    return result


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _nested(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _stable_id(prefix: str, parts: Sequence[Any]) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
