from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


SCHEMA_VERSION = "fin_ia_0_1_3_s2_shared_benchmark_evidence_freeze_v1_0"
CONTRACT_REF = "fin_0_1_3.S2.same_evidence_reasoning_benchmark:v1"
AS_OF = "2026-08-06"
CASES = ("DELL", "MU", "NVDA")
RUBRIC_REF = "docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md"


class SharedBenchmarkEvidenceError(ValueError):
    pass


SOURCES: tuple[dict[str, Any], ...] = (
    {
        "source_id": "SRC_DELL_Q1_FY27_CALL",
        "publisher": "Dell Technologies",
        "title": "Q1 FY2027 earnings call",
        "published_on": "2026-05-28",
        "authority": "issuer_primary",
        "url": "https://investors.delltechnologies.com/static-files/b63ffff9-b729-403b-a231-c6af05667759",
    },
    {
        "source_id": "SRC_DELL_Q1_FY27_EXHIBIT",
        "publisher": "Dell Technologies",
        "title": "Q1 FY2027 earnings exhibit",
        "published_on": "2026-05-28",
        "authority": "issuer_primary",
        "url": "https://investors.delltechnologies.com/static-files/05af7a65-5059-4955-a4b3-7f79494b664c",
    },
    {
        "source_id": "SRC_DELL_FY26_10K",
        "publisher": "U.S. SEC / Dell Technologies",
        "title": "Dell FY2026 Form 10-K",
        "published_on": "2026-03-16",
        "authority": "regulatory_primary",
        "url": "https://www.sec.gov/Archives/edgar/data/1571996/000157199626000008/dell-20260130.htm",
    },
    {
        "source_id": "SRC_MU_Q3_FY26_RESULTS",
        "publisher": "Micron Technology",
        "title": "Q3 FY2026 financial results",
        "published_on": "2026-06-24",
        "authority": "issuer_primary",
        "url": "https://investors.micron.com/node/50671",
    },
    {
        "source_id": "SRC_MU_Q3_FY26_REMARKS",
        "publisher": "Micron Technology",
        "title": "Q3 FY2026 prepared remarks",
        "published_on": "2026-06-24",
        "authority": "issuer_primary",
        "url": "https://investors.micron.com/static-files/631b1a32-5537-46ae-8f40-82e42fc79dfe",
    },
    {
        "source_id": "SRC_NVDA_Q1_FY27_RESULTS",
        "publisher": "NVIDIA",
        "title": "Q1 FY2027 financial results",
        "published_on": "2026-05-20",
        "authority": "issuer_primary",
        "url": "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx",
    },
    {
        "source_id": "SRC_NVDA_Q1_FY27_10Q",
        "publisher": "U.S. SEC / NVIDIA",
        "title": "NVIDIA Q1 FY2027 Form 10-Q",
        "published_on": "2026-05-22",
        "authority": "regulatory_primary",
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000052/nvda-20260426.htm",
    },
    {
        "source_id": "SRC_MSFT_Q3_FY26_CALL",
        "publisher": "Microsoft",
        "title": "FY2026 Q3 earnings call",
        "published_on": "2026-04-29",
        "authority": "industry_primary",
        "url": "https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q3",
    },
    {
        "source_id": "SRC_TSMC_Q2_2026_RESULTS",
        "publisher": "TSMC",
        "title": "Q2 2026 financial results",
        "published_on": "2026-07-16",
        "authority": "industry_primary",
        "url": "https://investor.tsmc.com/english/quarterly-results/2026/q2",
    },
    {
        "source_id": "SRC_MARKET_SNAPSHOT_20260806",
        "publisher": "FinSight MCP market snapshot",
        "title": "DELL/MU/NVDA market context snapshot",
        "published_on": "2026-08-06",
        "authority": "non_authoritative_market_context",
        "artifact_ref": ".codex_runtime/fin013-codex-gold-research-20260806/mcp/market_snapshot_dell_mu_nvda_20260529.json",
    },
)


def _number(metric: str, value: str, unit: str, *, formula: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"metric": metric, "value": value, "unit": unit}
    if formula:
        row["formula"] = formula
    return row


def _evidence(
    evidence_id: str,
    source_id: str,
    observed_period: str,
    statement: str,
    *,
    topics: Iterable[str],
    numbers: Iterable[dict[str, Any]] = (),
    boundary: str,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "observed_period": observed_period,
        "statement": statement,
        "topics": list(topics),
        "numeric_facts": list(numbers),
        "authority_boundary": boundary,
    }


CASE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "case_key": "DELL",
        "issuer": {"ticker": "DELL", "legal_name": "Dell Technologies Inc.", "cik": "0001571996"},
        "research_objective": "评估 Dell AI 基础设施业务的需求真实性与持续性、利润和现金价值捕获、供应与客户风险、市场预期及可证伪条件。",
        "evidence_items": [
            _evidence(
                "DELL_E01", "SRC_DELL_Q1_FY27_CALL", "Q1 FY2027",
                "Dell 披露 AI 服务器订单 244 亿美元、AI 服务器收入 161 亿美元、期末 AI backlog 513 亿美元，AI 客户超过 5,000。",
                topics=("orders", "revenue", "backlog", "customers"),
                numbers=(_number("ai_orders", "24.4", "USD_billion"), _number("ai_server_revenue", "16.1", "USD_billion"), _number("ai_backlog", "51.3", "USD_billion"), _number("ai_customers", "5000", "count_lower_bound")),
                boundary="订单、收入、backlog 与客户数口径不同；不能把 backlog 视为不可撤销收入，也不能由客户数推出收入集中度。",
            ),
            _evidence(
                "DELL_E02", "SRC_DELL_Q1_FY27_EXHIBIT", "Q1 FY2027",
                "公司收入 438.42 亿美元；ISG 收入 290.09 亿美元、营业利润 30.55 亿美元；经营现金流 40.81 亿美元。",
                topics=("company_financials", "segment_profit", "cash_flow"),
                numbers=(_number("revenue", "43.842", "USD_billion"), _number("isg_revenue", "29.009", "USD_billion"), _number("isg_operating_income", "3.055", "USD_billion"), _number("operating_cash_flow", "4.081", "USD_billion")),
                boundary="ISG 包含 AI server、传统 server、networking 与 storage；分部利润不能直接当作 AI server 独立利润。",
            ),
            _evidence(
                "DELL_E03", "SRC_DELL_Q1_FY27_CALL", "Q1 FY2027",
                "管理层称 AI server profitability 符合中个位数营业利润率目标，并称 Dell IP storage 是 ISG 盈利的重要驱动。",
                topics=("unit_economics", "storage", "profitability"),
                numbers=(),
                boundary="这是方向性管理层披露，不是可重算的 AI server 独立 gross margin、operating income 或 FCF。",
            ),
            _evidence(
                "DELL_E04", "SRC_DELL_Q1_FY27_CALL", "Q1 FY2027",
                "管理层称 memory 是主要供应约束、需求超过供给，并承认客户存在 buy-ahead 或 pull-forward。",
                topics=("supply", "memory", "order_timing"),
                boundary="不能由供应约束单独量化未来订单、取消率、部署利用率或约束持续期。",
            ),
            _evidence(
                "DELL_E05", "SRC_DELL_FY26_10K", "FY2026",
                "Dell 披露 AI 需求到出货具有非线性，业务组合向 AI-optimized servers 转移会降低 gross-margin rate，并影响 inventory、receivables 与 payables。",
                topics=("mix", "gross_margin", "working_capital", "timing"),
                boundary="披露说明机制与风险，不提供 Q1 FY2027 AI 独立利润或未来营运资本结果。",
            ),
            _evidence(
                "DELL_E06", "SRC_DELL_Q1_FY27_CALL", "FY2027 guidance",
                "Dell 给出 FY2027 约 600 亿美元 AI server revenue guidance。",
                topics=("guidance", "expectations"),
                numbers=(_number("ai_server_revenue_guidance", "60", "USD_billion"),),
                boundary="公司 guidance 不是已实现收入；需要后续订单转换、利润率与现金流验证。",
            ),
            _evidence(
                "DELL_E07", "SRC_MSFT_Q3_FY26_CALL", "calendar 2026 outlook",
                "Microsoft 预计 2026 年资本开支约 1,900 亿美元，称至少到 2026 年仍有容量约束，并继续采购多家加速器与服务器基础设施。",
                topics=("downstream_capex", "capacity", "industry_demand"),
                numbers=(_number("microsoft_2026_capex", "190", "USD_billion"),),
                boundary="Microsoft 的行业需求披露不证明其为 Dell 客户，也不能直接映射 Dell 收入。",
            ),
            _evidence(
                "DELL_E08", "SRC_MU_Q3_FY26_REMARKS", "Q3 FY2026",
                "Micron 披露 DRAM 与 NAND 价格大幅环比上涨，而 bit shipments 仅低至中个位数增长。",
                topics=("memory_pricing", "component_cost", "industry_supply"),
                boundary="Micron 的价格和出货数据说明内存市场背景，不能直接给出 Dell 采购价、转嫁能力或毛利影响。",
            ),
            _evidence(
                "DELL_E09", "SRC_MARKET_SNAPSHOT_20260806", "2026-08-06 snapshot",
                "市场快照记录 DELL 价格 450.50 美元、市值约 2,966 亿美元、静态 P/E 约 36.0 倍。",
                topics=("market_context", "price_in"),
                numbers=(_number("share_price", "450.50", "USD_per_share"), _number("market_cap", "296.6", "USD_billion"), _number("trailing_pe", "36.0", "multiple")),
                boundary="快照为非权威时点语境，不是 forward valuation、目标价或交易建议。",
            ),
        ],
        "derived_numeric": [
            _number("ai_server_revenue_share_of_company", "36.72", "percent", formula="16.1/43.842*100"),
            _number("ai_server_revenue_share_of_isg", "55.50", "percent", formula="16.1/29.009*100"),
            _number("isg_operating_margin", "10.53", "percent", formula="3.055/29.009*100"),
            _number("operating_cash_flow_margin", "9.31", "percent", formula="4.081/43.842*100"),
            _number("orders_to_revenue", "1.52", "ratio", formula="24.4/16.1"),
            _number("backlog_to_quarter_revenue", "3.19", "ratio", formula="51.3/16.1"),
        ],
        "explicit_gaps": [
            {"gap_id": "DELL_G01", "statement": "缺少 AI server 独立 gross margin、精确 operating margin 与 FCF。"},
            {"gap_id": "DELL_G02", "statement": "缺少 backlog 取消权、融资条件、客户集中与交付时间分布。"},
            {"gap_id": "DELL_G03", "statement": "缺少独立可审计的部署利用率与终端业务价值数据。"},
            {"gap_id": "DELL_G04", "statement": "缺少一致口径的 forward EV/EBITDA、同行和情景估值面板。"},
        ],
    },
    {
        "case_key": "MU",
        "issuer": {"ticker": "MU", "legal_name": "Micron Technology, Inc.", "cik": "0000723125"},
        "research_objective": "评估 Micron HBM 与数据中心内存增长的结构性和周期性来源、价格/出货/利润/现金传导、长期协议质量、供给响应和市场预期。",
        "evidence_items": [
            _evidence(
                "MU_E01", "SRC_MU_Q3_FY26_RESULTS", "Q3 FY2026",
                "Micron 披露收入 414.56 亿美元、GAAP gross margin 84.6%、GAAP operating margin 80.4%、adjusted FCF 183 亿美元、capex 71 亿美元。",
                topics=("company_financials", "margin", "cash_flow", "capex"),
                numbers=(_number("revenue", "41.456", "USD_billion"), _number("gaap_gross_margin", "84.6", "percent"), _number("gaap_operating_margin", "80.4", "percent"), _number("adjusted_fcf", "18.3", "USD_billion"), _number("capex", "7.1", "USD_billion")),
                boundary="单季历史高利润不能直接代表中周期盈利；adjusted FCF 口径需与融资性 deposits 区分。",
            ),
            _evidence(
                "MU_E02", "SRC_MU_Q3_FY26_RESULTS", "Q3 FY2026",
                "Cloud 与 Core Data Center 合计收入 252.93 亿美元。",
                topics=("data_center", "business_mix"),
                numbers=(_number("cloud_plus_core_data_center_revenue", "25.293", "USD_billion"),),
                boundary="业务单元收入不是 HBM 独立收入，不能直接归因于单一产品或客户。",
            ),
            _evidence(
                "MU_E03", "SRC_MU_Q3_FY26_REMARKS", "Q3 FY2026",
                "DRAM 收入约 313 亿美元、占总收入 76%；环比 bit shipments 低个位数增长，价格上涨低 60% 区间。",
                topics=("dram", "price_volume_mix"),
                numbers=(_number("dram_revenue", "31.3", "USD_billion"), _number("dram_revenue_share", "76", "percent")),
                boundary="DRAM 总量包含 HBM 与非 HBM；区间描述不能被伪装为精确百分比。",
            ),
            _evidence(
                "MU_E04", "SRC_MU_Q3_FY26_REMARKS", "Q3 FY2026",
                "NAND 收入约 99 亿美元、占总收入 24%；环比 bit shipments 中个位数增长，价格上涨中 80% 区间。",
                topics=("nand", "price_volume_mix"),
                numbers=(_number("nand_revenue", "9.9", "USD_billion"), _number("nand_revenue_share", "24", "percent")),
                boundary="NAND 价格/出货区间是公司披露，不代表未来价格或行业精确份额。",
            ),
            _evidence(
                "MU_E05", "SRC_MU_Q3_FY26_REMARKS", "current agreements",
                "Micron 披露 16 份通常为五年且带 take-or-pay 的 Strategic Customer Agreements，约 1,000 亿美元 RPO 和约 220 亿美元 deposits/financial commitments；约覆盖期间 DRAM volume 的 20% 和 NAND volume 的三分之一。",
                topics=("contracts", "rpo", "deposits", "volume_visibility"),
                numbers=(_number("strategic_customer_agreements", "16", "count"), _number("rpo", "100", "USD_billion_approx"), _number("deposits_and_commitments", "22", "USD_billion_approx"), _number("dram_volume_coverage", "20", "percent_approx"), _number("nand_volume_coverage", "33.33", "percent_approx")),
                boundary="RPO 是最低量价口径，不等于总收入、不可撤销利润、固定毛利率或自由现金流。",
            ),
            _evidence(
                "MU_E06", "SRC_MU_Q3_FY26_REMARKS", "current product roadmap",
                "Micron 披露 HBM4 已面向 lead customer 平台高量出货并向多个终端客户送样，HBM4 ramp 速度约为 HBM3E 的两倍且收入已超过 10 亿美元；HBM4E 预计 2027 年量产。",
                topics=("hbm4", "qualification", "roadmap"),
                numbers=(_number("hbm4_revenue", "1", "USD_billion_lower_bound"),),
                boundary="不披露 HBM 独立 gross margin、份额、客户身份或长期资格结果；lead customer 不等于唯一客户。",
            ),
            _evidence(
                "MU_E07", "SRC_NVDA_Q1_FY27_10Q", "FY2027 roadmap",
                "NVIDIA 预计 Rubin 在 FY2027 下半年推出。",
                topics=("customer_platform_roadmap", "product_timing"),
                boundary="NVIDIA 路线图提供需求时点语境，不证明 Micron 的指定份额、资格或收入。",
            ),
            _evidence(
                "MU_E08", "SRC_DELL_Q1_FY27_CALL", "Q1 FY2027",
                "Dell 称 memory 是 AI 与传统服务器的主要供应约束，客户正在更长周期锁定基础设施。",
                topics=("downstream_demand", "memory_supply"),
                boundary="Dell 的供应评论不是 Micron 订单、客户或价格的直接证明。",
            ),
            _evidence(
                "MU_E09", "SRC_MSFT_Q3_FY26_CALL", "calendar 2026 outlook",
                "Microsoft 预计 2026 年资本开支约 1,900 亿美元，其中约 250 亿美元与更高组件价格有关，并称容量至少到 2026 年仍受限。",
                topics=("downstream_capex", "component_pricing", "capacity"),
                numbers=(_number("microsoft_2026_capex", "190", "USD_billion"), _number("higher_component_price_effect", "25", "USD_billion_approx")),
                boundary="行业下游披露不证明 Micron 具体客户、合同或收入归因。",
            ),
            _evidence(
                "MU_E10", "SRC_TSMC_Q2_2026_RESULTS", "Q2 2026",
                "TSMC 披露收入 402 亿美元、gross margin 67.7%，并继续扩张先进制程与先进封装。",
                topics=("upstream_capacity", "advanced_packaging", "industry_supply"),
                numbers=(_number("tsmc_revenue", "40.2", "USD_billion"), _number("tsmc_gross_margin", "67.7", "percent")),
                boundary="TSMC 数据是 AI 供应链扩容语境，不能直接量化 Micron HBM 产能、良率或份额。",
            ),
            _evidence(
                "MU_E11", "SRC_MARKET_SNAPSHOT_20260806", "2026-08-06 snapshot",
                "市场快照记录 MU 价格 898.90 美元、市值约 1.030 万亿美元、静态 P/E 约 20.4 倍。",
                topics=("market_context", "price_in"),
                numbers=(_number("share_price", "898.90", "USD_per_share"), _number("market_cap", "1030", "USD_billion"), _number("trailing_pe", "20.4", "multiple")),
                boundary="静态 P/E 使用周期高位盈利，不能直接代表中周期估值或目标价。",
            ),
        ],
        "derived_numeric": [
            _number("adjusted_fcf_margin", "44.14", "percent", formula="18.3/41.456*100"),
            _number("capex_to_revenue", "17.13", "percent", formula="7.1/41.456*100"),
            _number("cloud_plus_core_data_center_share", "61.01", "percent", formula="25.293/41.456*100"),
        ],
        "explicit_gaps": [
            {"gap_id": "MU_G01", "statement": "缺少 HBM 独立收入、gross margin、客户集中和份额。"},
            {"gap_id": "MU_G02", "statement": "缺少 SCA 客户、floor/ceiling、取消条款和产品级利润口径。"},
            {"gap_id": "MU_G03", "statement": "缺少 SK hynix、Samsung 同期同口径 HBM 供给/份额面板。"},
            {"gap_id": "MU_G04", "statement": "缺少 2027–2028 DRAM/NAND 有效产能、库存和中周期估值模型。"},
        ],
    },
    {
        "case_key": "NVDA",
        "issuer": {"ticker": "NVDA", "legal_name": "NVIDIA Corporation", "cik": "0001045810"},
        "research_objective": "评估 NVIDIA AI 基础设施需求与平台价值、利润和现金捕获、客户及供应集中、生态与政策风险、市场预期及可证伪条件。",
        "evidence_items": [
            _evidence(
                "NVDA_E01", "SRC_NVDA_Q1_FY27_RESULTS", "Q1 FY2027",
                "NVIDIA 披露收入 816.15 亿美元，Data Center 收入 752 亿美元，其中 compute 604 亿美元、networking 148 亿美元。",
                topics=("revenue", "data_center", "compute", "networking"),
                numbers=(_number("revenue", "81.615", "USD_billion"), _number("data_center_revenue", "75.2", "USD_billion"), _number("data_center_compute", "60.4", "USD_billion"), _number("data_center_networking", "14.8", "USD_billion")),
                boundary="Data Center 收入不等于终端应用 ROI，也不单独证明未来增速。",
            ),
            _evidence(
                "NVDA_E02", "SRC_NVDA_Q1_FY27_RESULTS", "Q1 FY2027",
                "GAAP gross margin 为 74.9%，GAAP operating income 为 535.36 亿美元，operating cash flow 为 503.44 亿美元。",
                topics=("margin", "operating_income", "cash_flow"),
                numbers=(_number("gaap_gross_margin", "74.9", "percent"), _number("gaap_operating_income", "53.536", "USD_billion"), _number("operating_cash_flow", "50.344", "USD_billion")),
                boundary="当季利润与现金质量不保证长期 margin、客户资本回报或估值回报。",
            ),
            _evidence(
                "NVDA_E03", "SRC_NVDA_Q1_FY27_RESULTS", "Q2 FY2027 outlook",
                "NVIDIA 给出 Q2 FY2027 收入 910 亿美元±2% 的展望，且未假设中国 Data Center compute 收入。",
                topics=("guidance", "china", "expectations"),
                numbers=(_number("q2_revenue_outlook", "91", "USD_billion"), _number("outlook_range", "2", "percent_plus_minus")),
                boundary="展望不是已实现收入；不包含中国 DC compute 的假设也不消除其他政策风险。",
            ),
            _evidence(
                "NVDA_E04", "SRC_NVDA_Q1_FY27_10Q", "Q1 FY2027",
                "三个直接客户分别占收入 21%、17% 和 16%，合计 54%。",
                topics=("customer_concentration", "credit", "demand_timing"),
                numbers=(_number("direct_customer_1_share", "21", "percent"), _number("direct_customer_2_share", "17", "percent"), _number("direct_customer_3_share", "16", "percent"), _number("top_three_direct_customer_share", "54", "percent", formula="21+17+16")),
                boundary="直接客户可能是云厂商、ODM 或分销渠道，不能自动映射到最终客户身份或终端需求集中。",
            ),
            _evidence(
                "NVDA_E05", "SRC_NVDA_Q1_FY27_10Q", "Q1 FY2027",
                "期末 inventory 为 257.97 亿美元、环比增长约 20.5%；excess inventory purchase obligations 为 31.21 亿美元。",
                topics=("inventory", "purchase_commitments", "supply_demand_mismatch"),
                numbers=(_number("inventory", "25.797", "USD_billion"), _number("inventory_qoq_growth", "20.5", "percent_approx"), _number("excess_inventory_purchase_obligations", "3.121", "USD_billion")),
                boundary="库存增长可来自增长备货或错配；仅凭余额不能判定减值概率。",
            ),
            _evidence(
                "NVDA_E06", "SRC_NVDA_Q1_FY27_10Q", "Q1 FY2027",
                "NVIDIA 披露本季对 private companies 与 infrastructure funds 的投资约 186 亿美元。",
                topics=("ecosystem_investment", "capital_allocation"),
                numbers=(_number("private_company_and_infrastructure_fund_investment", "18.6", "USD_billion_approx"),),
                boundary="披露不提供被投对象采购 NVIDIA 的完整映射，不能由投资额推出收入因果或循环融资规模。",
            ),
            _evidence(
                "NVDA_E07", "SRC_NVDA_Q1_FY27_10Q", "prior policy impact and current risks",
                "公司披露此前 H20 出口限制造成 45 亿美元 excess inventory/purchase obligation charge，并警告非取消采购承诺和提前下单会放大需求估计错误。",
                topics=("export_controls", "inventory_charge", "commitments"),
                numbers=(_number("h20_charge", "4.5", "USD_billion"),),
                boundary="历史 charge 证明政策可产生财务影响，但不量化未来规则、许可或损失。",
            ),
            _evidence(
                "NVDA_E08", "SRC_NVDA_Q1_FY27_10Q", "FY2027 roadmap",
                "公司预计 Rubin 在 FY2027 下半年推出；Blackwell 已成为 Data Center 主要架构。",
                topics=("product_cadence", "architecture_transition"),
                boundary="路线图不保证量产时点、良率、客户采用、旧产品库存或每次转代的 margin。",
            ),
            _evidence(
                "NVDA_E09", "SRC_DELL_Q1_FY27_CALL", "Q1 FY2027",
                "Dell 披露 AI orders 244 亿美元、AI server revenue 161 亿美元、AI backlog 513 亿美元。",
                topics=("downstream_system_demand", "orders", "deployment_chain"),
                numbers=(_number("dell_ai_orders", "24.4", "USD_billion"), _number("dell_ai_server_revenue", "16.1", "USD_billion"), _number("dell_ai_backlog", "51.3", "USD_billion")),
                boundary="Dell 的下游系统数据不等于 NVIDIA 最终客户利用率、应用收入或订单归因。",
            ),
            _evidence(
                "NVDA_E10", "SRC_MU_Q3_FY26_REMARKS", "current product roadmap",
                "Micron 披露 HBM4 已面向 lead customer 平台高量出货。",
                topics=("hbm_supply", "platform_readiness"),
                boundary="Micron 未在该披露中确认 NVIDIA 客户映射、份额或供给量。",
            ),
            _evidence(
                "NVDA_E11", "SRC_MSFT_Q3_FY26_CALL", "calendar 2026 outlook",
                "Microsoft 预计 2026 年资本开支约 1,900 亿美元且容量至少到 2026 年仍受限。",
                topics=("hyperscaler_capex", "capacity", "downstream_demand"),
                numbers=(_number("microsoft_2026_capex", "190", "USD_billion"),),
                boundary="Microsoft 的资本开支不能完整映射到 NVIDIA 收入或终端 AI 应用回报。",
            ),
            _evidence(
                "NVDA_E12", "SRC_TSMC_Q2_2026_RESULTS", "Q2 2026",
                "TSMC 披露收入 402 亿美元、gross margin 67.7%，并继续扩张先进制程与先进封装。",
                topics=("foundry", "advanced_packaging", "capacity"),
                numbers=(_number("tsmc_revenue", "40.2", "USD_billion"), _number("tsmc_gross_margin", "67.7", "percent")),
                boundary="TSMC 扩容是产业供给语境，不直接证明 NVIDIA 获得的产能、成本、良率或长期 margin。",
            ),
            _evidence(
                "NVDA_E13", "SRC_MARKET_SNAPSHOT_20260806", "2026-08-06 snapshot",
                "市场快照记录 NVDA 价格 219.70 美元、市值约 5.359 万亿美元、静态 P/E 约 33.4 倍。",
                topics=("market_context", "price_in"),
                numbers=(_number("share_price", "219.70", "USD_per_share"), _number("market_cap", "5359", "USD_billion"), _number("trailing_pe", "33.4", "multiple")),
                boundary="快照不能替代 forward FCF、资本成本、情景概率或目标价。",
            ),
        ],
        "derived_numeric": [
            _number("data_center_share_of_revenue", "92.14", "percent", formula="75.2/81.615*100"),
            _number("gaap_operating_margin", "65.60", "percent", formula="53.536/81.615*100"),
            _number("operating_cash_flow_margin", "61.68", "percent", formula="50.344/81.615*100"),
        ],
        "explicit_gaps": [
            {"gap_id": "NVDA_G01", "statement": "缺少直接客户到最终客户的完整映射、信用和付款条件。"},
            {"gap_id": "NVDA_G02", "statement": "缺少统一可审计的 GPU/ASIC 利用率、token economics 与客户 AI ROI 面板。"},
            {"gap_id": "NVDA_G03", "statement": "缺少生态投资与被投对象 NVIDIA 采购之间的因果和金额映射。"},
            {"gap_id": "NVDA_G04", "statement": "缺少一致口径的 forward FCF、资本成本和情景估值面板。"},
        ],
    },
)


HIDDEN_SCORING: tuple[dict[str, Any], ...] = (
    {
        "case_key": "DELL",
        "expected_thesis": "需求已由订单、收入、backlog 与客户广度共同验证，但投资争议转向低利润 AI server mix、storage/service attach、营运资本和现金转换。",
        "strongest_counter_thesis": "backlog 可能含供应恐慌和提前采购，主要经济租流向上游；若供应缓解后订单、margin 与现金转弱，Dell 会重新按周期性 OEM 定价。",
        "required_insights": [
            {"target_id": "DELL_T01", "dimensions": ["Q1", "Q2"], "evidence_ids": ["DELL_E01", "DELL_E07"], "expected_insight": "区分 Dell 自身订单/收入证据与 Microsoft 产业背景，不虚构客户映射。"},
            {"target_id": "DELL_T02", "dimensions": ["Q3", "Q4"], "evidence_ids": ["DELL_E02", "DELL_E03"], "expected_insight": "区分 10.5% ISG margin 与中个位数 AI server profitability，并解释 storage 对利润捕获的重要性。"},
            {"target_id": "DELL_T03", "dimensions": ["Q5", "Q6"], "evidence_ids": ["DELL_E04", "DELL_E05", "DELL_E08"], "expected_insight": "同时处理供应约束带来的收入可见度、pull-forward、mix 和营运资本风险。"},
            {"target_id": "DELL_T04", "dimensions": ["Q3", "Q7"], "evidence_ids": ["DELL_E06", "DELL_E09"], "expected_insight": "把 600 亿美元 guidance 与静态估值写成待验证预期，不给目标价。"},
        ],
        "required_conflict": "业务需求强与当前风险回报未必强必须同时成立并被裁决。",
        "required_wwc": ["backlog 转收入和取消/延期", "ISG/AI margin 与 FCF/营运资本", "企业/主权重复采购与 attach", "供应缓解后的订单韧性"],
        "disallowed_shortcuts": ["backlog 按 100% 转收入", "把 ISG margin 当 AI server margin", "把 Microsoft 写成 Dell 客户", "仅凭静态 P/E 给目标价"],
    },
    {
        "case_key": "MU",
        "expected_thesis": "HBM 产品升级和客户承诺具有结构性，但 Q3 盈利爆发首先由 DRAM/NAND 价格而非 bit growth 驱动；协议缓冲周期而不消灭周期。",
        "strongest_counter_thesis": "极端毛利率主要来自短缺，微弱 bit 增长和高价格会刺激供给响应；一旦 ASP 回落，峰值盈利下的静态估值会迅速失真。",
        "required_insights": [
            {"target_id": "MU_T01", "dimensions": ["Q2", "Q3", "Q4"], "evidence_ids": ["MU_E01", "MU_E03", "MU_E04"], "expected_insight": "用 DRAM/NAND 量价分解证明当季增长以价格为主，不把全部利润归因 HBM。"},
            {"target_id": "MU_T02", "dimensions": ["Q1", "Q6"], "evidence_ids": ["MU_E02", "MU_E06", "MU_E07"], "expected_insight": "承认 HBM4 产品验证，同时保留 HBM 独立利润、份额和多客户资格缺口。"},
            {"target_id": "MU_T03", "dimensions": ["Q5", "Q6"], "evidence_ids": ["MU_E05"], "expected_insight": "解释 take-or-pay/RPO/deposit 增强可见度但不保证全部收入、固定 margin 或 FCF。"},
            {"target_id": "MU_T04", "dimensions": ["Q4", "Q7"], "evidence_ids": ["MU_E08", "MU_E09", "MU_E10", "MU_E11"], "expected_insight": "同时写出下游紧张与上游扩容，并以价格、bit、资格、产能/库存和中周期盈利作为 WWC。"},
        ],
        "required_conflict": "HBM 结构升级与传统内存价格周期必须同时进入 thesis，不能二选一。",
        "required_wwc": ["价格与 bit growth 的接棒", "HBM4/HBM4E 多客户资格和利润池", "SCA 实际确认与重谈", "2027–2028 有效供给、库存和 capex"],
        "disallowed_shortcuts": ["把 DRAM 总收入当 HBM 收入", "把 RPO 当全部收入或利润", "把 84.6% margin 永续化", "用峰值静态 P/E 直接称便宜"],
    },
    {
        "case_key": "NVDA",
        "expected_thesis": "平台收入、利润和现金质量强，争议已转向客户集中、生态投资反身性、供应承诺、出口、转代和终端 ROI 是否达到高估值门槛。",
        "strongest_counter_thesis": "少数云厂商和模型公司驱动并受产业资本支持的 capex 可能在利用率或应用 ROI 不及预期时减速，叠加库存和不可取消承诺形成双重下修。",
        "required_insights": [
            {"target_id": "NVDA_T01", "dimensions": ["Q1", "Q2", "Q3"], "evidence_ids": ["NVDA_E01", "NVDA_E02", "NVDA_E09", "NVDA_E11"], "expected_insight": "以发行人收入/利润/现金和下游系统/capex 互证需求，但不把 capex 等同终端 ROI。"},
            {"target_id": "NVDA_T02", "dimensions": ["Q3", "Q4"], "evidence_ids": ["NVDA_E01", "NVDA_E08"], "expected_insight": "用 networking 与系统迭代说明平台价值不只是单颗 GPU，同时保留转代风险。"},
            {"target_id": "NVDA_T03", "dimensions": ["Q5", "Q6"], "evidence_ids": ["NVDA_E04", "NVDA_E06"], "expected_insight": "直接客户 54% 集中与生态投资反身性必须进入主 thesis，且不得虚构最终客户映射或采购因果。"},
            {"target_id": "NVDA_T04", "dimensions": ["Q6", "Q7"], "evidence_ids": ["NVDA_E05", "NVDA_E07", "NVDA_E10", "NVDA_E12", "NVDA_E13"], "expected_insight": "把供给扩容、库存/承诺、出口和高绝对估值写成不同时间尺度的 WWC，而不是抽象风险清单。"},
        ],
        "required_conflict": "强业务、强现金与强集中、强预期必须同时成立；收入确认不能替代终端 ROI 证明。",
        "required_wwc": ["客户/终端分散和利用率", "networking/software attach 与 Rubin 转代", "库存/承诺相对需求", "出口政策", "自研 ASIC 对价格和 margin 的影响"],
        "disallowed_shortcuts": ["把 Dell/Microsoft 直接写成 NVIDIA 收入归因", "把直接客户当最终客户", "把投资额当循环采购证明", "把当前增长直接等同估值上行"],
    },
)


VISIBLE_FORBIDDEN_KEYS = {
    "expected_thesis",
    "strongest_counter_thesis",
    "required_insights",
    "required_conflict",
    "required_wwc",
    "disallowed_shortcuts",
    "expected_insight",
    "score_targets",
    "answer_key",
    "gold_answer",
}

VISIBLE_FORBIDDEN_PHRASES = (
    "业务需求强与当前风险回报未必强",
    "协议缓冲周期而不消灭周期",
    "强业务、强现金与强集中、强预期",
    "平台收入、利润和现金质量强，争议已转向",
)


def compile_shared_benchmark_evidence_freeze() -> dict[str, Any]:
    source_rows = deepcopy(list(SOURCES))
    source_ids = {row["source_id"] for row in source_rows}
    case_rows: list[dict[str, Any]] = []
    blind_cases: list[dict[str, Any]] = []
    all_evidence_ids: set[str] = set()
    for source in source_rows:
        source["source_digest"] = canonical_digest(source)
    for raw_case in CASE_DEFINITIONS:
        case_row = deepcopy(raw_case)
        for evidence in case_row["evidence_items"]:
            if evidence["source_id"] not in source_ids:
                raise SharedBenchmarkEvidenceError("s2_04_source_ref_unknown")
            if evidence["evidence_id"] in all_evidence_ids:
                raise SharedBenchmarkEvidenceError("s2_04_evidence_id_duplicate")
            all_evidence_ids.add(evidence["evidence_id"])
            evidence["evidence_digest"] = canonical_digest(evidence)
        case_row["case_evidence_digest"] = canonical_digest(
            {key: value for key, value in case_row.items() if key != "case_evidence_digest"}
        )
        case_rows.append(case_row)
        blind_body = {
            "case_key": case_row["case_key"],
            "issuer": deepcopy(case_row["issuer"]),
            "as_of": AS_OF,
            "research_objective": case_row["research_objective"],
            "instructions": [
                "只使用本输入中的 Evidence、Numeric、来源边界和明确 gap；不得补充外部事实。",
                "区分事实、bounded inference、cannot infer 和需要补证的判断。",
                "形成公司专属 thesis、最强反方、跨证据冲突/依赖、price-in 边界和可观测 What-Would-Change。",
                "引用 Evidence ID；不得把 source boundary 或 gap 改写成正面事实。",
            ],
            "evidence_items": deepcopy(case_row["evidence_items"]),
            "derived_numeric": deepcopy(case_row["derived_numeric"]),
            "explicit_gaps": deepcopy(case_row["explicit_gaps"]),
            "rubric_ref": RUBRIC_REF,
            "tool_access": "none_experiment_A_same_evidence_only",
        }
        blind_cases.append({**blind_body, "model_visible_digest": canonical_digest(blind_body)})
    visible_body = {
        "schema_version": SCHEMA_VERSION,
        "contract_ref": CONTRACT_REF,
        "as_of": AS_OF,
        "status": "shared_model_visible_evidence_frozen",
        "source_registry": source_rows,
        "cases": case_rows,
        "visibility_policy": {
            "model_visible": True,
            "contains_gold_thesis_or_scores": False,
            "tool_access": "none",
            "writer_may_add_facts": False,
        },
    }
    visible_pack = {**visible_body, "pack_digest": canonical_digest(visible_body)}
    blind_body = {
        "schema_version": SCHEMA_VERSION,
        "contract_ref": CONTRACT_REF,
        "shared_pack_digest": visible_pack["pack_digest"],
        "cases": blind_cases,
        "visibility_policy": {
            "model_visible": True,
            "hidden_scoring_objects_included": False,
            "gold_reports_included": False,
        },
    }
    blind_inputs = {**blind_body, "blind_input_digest": canonical_digest(blind_body)}
    hidden_cases = deepcopy(list(HIDDEN_SCORING))
    for row in hidden_cases:
        row["hidden_case_digest"] = canonical_digest(row)
    hidden_body = {
        "schema_version": SCHEMA_VERSION,
        "contract_ref": CONTRACT_REF,
        "shared_pack_digest": visible_pack["pack_digest"],
        "blind_input_digest": blind_inputs["blind_input_digest"],
        "access_scope": "evaluator_only_never_model_visible",
        "rubric_ref": RUBRIC_REF,
        "cases": hidden_cases,
    }
    hidden_scoring = {**hidden_body, "hidden_scoring_digest": canonical_digest(hidden_body)}
    manifest_body = {
        "schema_version": SCHEMA_VERSION,
        "contract_ref": CONTRACT_REF,
        "status": "S2_04_frozen_experiment_A_admission_not_issued",
        "as_of": AS_OF,
        "cases": list(CASES),
        "shared_pack_digest": visible_pack["pack_digest"],
        "blind_input_digest": blind_inputs["blind_input_digest"],
        "hidden_scoring_digest": hidden_scoring["hidden_scoring_digest"],
        "artifact_refs": {
            "model_visible": [
                "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json",
                "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/experiment_a_blind_inputs_v1.json",
            ],
            "evaluator_only": "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json",
        },
        "gold_candidate_refs": [
            "docs/research/fin_0_1_3_gold_candidates/DELL_research_gold_candidate_20260806.zh-CN.md",
            "docs/research/fin_0_1_3_gold_candidates/MU_research_gold_candidate_20260806.zh-CN.md",
            "docs/research/fin_0_1_3_gold_candidates/NVDA_research_gold_candidate_20260806.zh-CN.md",
        ],
        "fairness": {
            "same_objective_as_of_source_authority": True,
            "gold_reasoning_visible_to_model": False,
            "hidden_scores_visible_to_model": False,
            "external_tools_enabled": False,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "mcp_calls": 0,
        },
        "observed_counts": {
            "sources": len(source_rows),
            "cases": len(case_rows),
            "evidence_items": sum(len(row["evidence_items"]) for row in case_rows),
            "derived_numeric": sum(len(row["derived_numeric"]) for row in case_rows),
            "explicit_gaps": sum(len(row["explicit_gaps"]) for row in case_rows),
            "hidden_targets": sum(len(row["required_insights"]) for row in hidden_cases),
        },
        "next_action": "S2_05_EXPERIMENT_A_DEEPSEEK_SAME_EVIDENCE_ADMISSION_AUTHORITY_DECISION",
    }
    manifest = {**manifest_body, "manifest_digest": canonical_digest(manifest_body)}
    bundle = {
        "visible_pack": visible_pack,
        "blind_inputs": blind_inputs,
        "hidden_scoring": hidden_scoring,
        "manifest": manifest,
    }
    validate_shared_benchmark_evidence_freeze(bundle)
    return bundle


def validate_shared_benchmark_evidence_freeze(bundle: Mapping[str, Any]) -> None:
    visible = deepcopy(bundle.get("visible_pack") or {})
    blind = deepcopy(bundle.get("blind_inputs") or {})
    hidden = deepcopy(bundle.get("hidden_scoring") or {})
    manifest = deepcopy(bundle.get("manifest") or {})
    _validate_digest(visible, "pack_digest", "s2_04_visible_pack_digest_invalid")
    _validate_digest(blind, "blind_input_digest", "s2_04_blind_input_digest_invalid")
    _validate_digest(hidden, "hidden_scoring_digest", "s2_04_hidden_scoring_digest_invalid")
    _validate_digest(manifest, "manifest_digest", "s2_04_manifest_digest_invalid")
    if any(row.get("schema_version") != SCHEMA_VERSION for row in (visible, blind, hidden, manifest)):
        raise SharedBenchmarkEvidenceError("s2_04_schema_invalid")
    if any(row.get("contract_ref") != CONTRACT_REF for row in (visible, blind, hidden, manifest)):
        raise SharedBenchmarkEvidenceError("s2_04_contract_ref_invalid")
    if blind.get("shared_pack_digest") != visible.get("pack_digest"):
        raise SharedBenchmarkEvidenceError("s2_04_blind_visible_binding_invalid")
    if hidden.get("shared_pack_digest") != visible.get("pack_digest") or hidden.get("blind_input_digest") != blind.get("blind_input_digest"):
        raise SharedBenchmarkEvidenceError("s2_04_hidden_binding_invalid")
    if manifest.get("shared_pack_digest") != visible.get("pack_digest") or manifest.get("blind_input_digest") != blind.get("blind_input_digest") or manifest.get("hidden_scoring_digest") != hidden.get("hidden_scoring_digest"):
        raise SharedBenchmarkEvidenceError("s2_04_manifest_binding_invalid")
    source_rows = visible.get("source_registry") or []
    source_ids = {row.get("source_id") for row in source_rows}
    if len(source_rows) != len(source_ids) or None in source_ids:
        raise SharedBenchmarkEvidenceError("s2_04_source_registry_invalid")
    for source in source_rows:
        _validate_digest(source, "source_digest", "s2_04_source_digest_invalid")
        if date.fromisoformat(source["published_on"]) > date.fromisoformat(AS_OF):
            raise SharedBenchmarkEvidenceError("s2_04_future_source_invalid")
    visible_cases = visible.get("cases") or []
    blind_cases = blind.get("cases") or []
    hidden_cases = hidden.get("cases") or []
    if [row.get("case_key") for row in visible_cases] != list(CASES) or [row.get("case_key") for row in blind_cases] != list(CASES) or [row.get("case_key") for row in hidden_cases] != list(CASES):
        raise SharedBenchmarkEvidenceError("s2_04_case_surface_invalid")
    all_evidence_ids: set[str] = set()
    case_evidence_ids: dict[str, set[str]] = {}
    for visible_case, blind_case in zip(visible_cases, blind_cases, strict=True):
        _validate_digest(visible_case, "case_evidence_digest", "s2_04_case_digest_invalid")
        _validate_digest(blind_case, "model_visible_digest", "s2_04_model_visible_digest_invalid")
        if visible_case["case_key"] != blind_case["case_key"] or visible_case["issuer"] != blind_case["issuer"] or visible_case["research_objective"] != blind_case["research_objective"]:
            raise SharedBenchmarkEvidenceError("s2_04_case_identity_or_objective_drift")
        if visible_case["evidence_items"] != blind_case["evidence_items"] or visible_case["derived_numeric"] != blind_case["derived_numeric"] or visible_case["explicit_gaps"] != blind_case["explicit_gaps"]:
            raise SharedBenchmarkEvidenceError("s2_04_model_visible_evidence_drift")
        prefix = visible_case["case_key"] + "_"
        case_evidence_ids[visible_case["case_key"]] = set()
        for evidence in visible_case["evidence_items"]:
            _validate_digest(evidence, "evidence_digest", "s2_04_evidence_digest_invalid")
            evidence_id = evidence.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id.startswith(prefix) or evidence_id in all_evidence_ids:
                raise SharedBenchmarkEvidenceError("s2_04_cross_case_or_duplicate_evidence")
            all_evidence_ids.add(evidence_id)
            case_evidence_ids[visible_case["case_key"]].add(evidence_id)
            if evidence.get("source_id") not in source_ids or not evidence.get("authority_boundary"):
                raise SharedBenchmarkEvidenceError("s2_04_evidence_authority_invalid")
            _validate_numeric_rows(evidence.get("numeric_facts") or [])
        for gap in visible_case["explicit_gaps"]:
            if not str(gap.get("gap_id", "")).startswith(prefix) or not gap.get("statement"):
                raise SharedBenchmarkEvidenceError("s2_04_gap_surface_invalid")
        _validate_numeric_rows(visible_case.get("derived_numeric") or [])
    _assert_no_forbidden_visible_content(visible)
    _assert_no_forbidden_visible_content(blind)
    for hidden_case in hidden_cases:
        _validate_digest(hidden_case, "hidden_case_digest", "s2_04_hidden_case_digest_invalid")
        for target in hidden_case.get("required_insights") or []:
            evidence_ids = target.get("evidence_ids") or []
            if not evidence_ids or any(
                evidence_id not in case_evidence_ids[hidden_case["case_key"]]
                for evidence_id in evidence_ids
            ):
                raise SharedBenchmarkEvidenceError("s2_04_hidden_target_evidence_invalid")
    counts = manifest.get("observed_counts") or {}
    actual_counts = {
        "sources": len(source_rows),
        "cases": len(visible_cases),
        "evidence_items": sum(len(row["evidence_items"]) for row in visible_cases),
        "derived_numeric": sum(len(row["derived_numeric"]) for row in visible_cases),
        "explicit_gaps": sum(len(row["explicit_gaps"]) for row in visible_cases),
        "hidden_targets": sum(len(row["required_insights"]) for row in hidden_cases),
    }
    if counts != actual_counts or manifest.get("status") != "S2_04_frozen_experiment_A_admission_not_issued":
        raise SharedBenchmarkEvidenceError("s2_04_manifest_counts_or_status_invalid")
    refs = manifest.get("artifact_refs") or {}
    if not refs.get("model_visible") or any("/model_visible/" not in ref for ref in refs["model_visible"]):
        raise SharedBenchmarkEvidenceError("s2_04_model_visible_path_invalid")
    if "/evaluator_only/" not in str(refs.get("evaluator_only", "")):
        raise SharedBenchmarkEvidenceError("s2_04_hidden_path_invalid")
    if refs["evaluator_only"] in refs["model_visible"]:
        raise SharedBenchmarkEvidenceError("s2_04_visibility_path_overlap")


def _validate_digest(row: Mapping[str, Any], digest_key: str, error_code: str) -> None:
    body = {key: deepcopy(value) for key, value in row.items() if key != digest_key}
    if row.get(digest_key) != canonical_digest(body):
        raise SharedBenchmarkEvidenceError(error_code)


def _validate_numeric_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    for row in rows:
        try:
            Decimal(str(row["value"]))
        except (InvalidOperation, KeyError, TypeError) as exc:
            raise SharedBenchmarkEvidenceError("s2_04_numeric_value_invalid") from exc
        if not row.get("metric") or not row.get("unit"):
            raise SharedBenchmarkEvidenceError("s2_04_numeric_authority_invalid")
        if row.get("formula") and Decimal(str(row["value"])) != _evaluate_formula(str(row["formula"])):
            raise SharedBenchmarkEvidenceError("s2_04_derived_numeric_recompute_invalid")


def _evaluate_formula(formula: str) -> Decimal:
    multiplier = Decimal("100") if formula.endswith("*100") else Decimal("1")
    core = formula[:-4] if multiplier == Decimal("100") else formula
    try:
        if "/" in core:
            numerator, denominator = core.split("/", 1)
            result = Decimal(numerator) / Decimal(denominator)
        elif "+" in core:
            result = sum((Decimal(value) for value in core.split("+")), Decimal("0"))
        else:
            raise SharedBenchmarkEvidenceError("s2_04_formula_operator_invalid")
    except (InvalidOperation, ZeroDivisionError) as exc:
        raise SharedBenchmarkEvidenceError("s2_04_formula_invalid") from exc
    return (result * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _walk(value: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield None, item
            yield from _walk(item)


def _assert_no_forbidden_visible_content(value: Any) -> None:
    serialized = str(value)
    for key, item in _walk(value):
        if key in VISIBLE_FORBIDDEN_KEYS:
            raise SharedBenchmarkEvidenceError("s2_04_hidden_key_leak")
        if isinstance(item, str) and any(phrase in item for phrase in VISIBLE_FORBIDDEN_PHRASES):
            raise SharedBenchmarkEvidenceError("s2_04_hidden_phrase_leak")
    if "gold_candidate" in serialized or "gold_answer" in serialized:
        raise SharedBenchmarkEvidenceError("s2_04_gold_label_leak")
