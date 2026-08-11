# 16 L4 弱信号架构与 L1-L3 纵向细分执行框架

日期：2026-06-17

## 背景

15 文档把 source layer 能力审计、L1-L3 第一批真实接入和 analyst-first 输出方向落下来了，但当前推进方式仍有一个结构性问题：如果继续按全局 source type 补齐，比如“电商”“招聘”“新闻”“官方 API”，系统会越来越像通用搜索引擎，难以覆盖 600+ 公司在行业、商业模式、产品形态和财务科目上的差异。

下一阶段必须把 source-layer 扩容从“横向补数据源”升级成“纵向补行业/公司类别/产品线能力”。每个细分领域都要有自己的 L1 强事实、L2 可信补充、L3 市场 proxy 和 L4 discovery 边界，完成一个 lane 后再推进下一个 lane。

本文件不替代 15 文档；15 记录当前 source-layer 能力和已经物化的数据，16 定义后续 L4 架构以及 L1-L3 的 lane 化完成口径。

## 核心决策

1. L4 不是新的证据层，而是 discovery / exclusion / repair trigger 层。
2. L4 不允许直接生成 ClaimCard，不允许直接进入核心 thesis。
3. L4 唯一的价值是发现可能存在的官方源、可信源、商业缺口或异常线索，然后触发 L1/L2/L3 targeted repair。
4. L1-L3 不再按单一全局 source list 推进，而是按 vertical source lane 推进。
5. 每个 lane 必须先建立行业 playbook / source playbook / product taxonomy / KPI and accounting focus，不能让 Research Lead 靠通用常识猜。

## L4 架构

### L4 Source Scope

当前 audit 中的 L4 包括：

| source_id | 当前状态 | 后续定位 |
| --- | --- | --- |
| `common_crawl_index` | `structured_not_promoted` | web-scale discovery，用于发现官方产品页、IR 页、供应商/客户关系候选，不支持结论。 |
| `yahoo_chart` | `structured_not_promoted` | market reaction / price sanity lead；在没有正式 market data contract 前不进入核心估值判断。 |
| `unverified_self_media_forums` | `not_registered` | 无验证社媒、论坛、二手转述，只能做 rumor/discovery lead 或排除项。 |
| `commercial_market_data_and_consensus` | `blocked_by_auth_or_policy` | 不是弱信号；它是商业缺口登记层，不用公开源冒充。 |

注意：验证过的官方社媒账号不属于 L4，应按 L2 `official_social_accounts` 处理；未验证账号、二手截图、论坛讨论才是 L4。

### L4 Runtime Objects

L4 不写 ClaimCard，只写以下对象：

```text
WeakSignalLead
- lead_id
- source_id
- source_url
- source_domain
- source_quality_class
- observed_at
- ticker_candidates
- product_candidates
- counterparty_candidates
- extracted_hint
- suggested_repair_routes
- required_verification_source_layers
- expiry_at
- disallowed_claim_scopes

WeakSignalExclusionNote
- note_id
- lead_id
- exclusion_reason
- checked_routes
- why_not_promoted
- next_possible_source

L4PromotionAttempt
- attempt_id
- lead_id
- target_layer: L1 | L2 | L3
- target_source_class
- fetch_result
- parser_result
- entity_binding_result
- promotion_status: promoted | not_found | blocked | parser_failed | entity_unresolved
- promoted_evidence_ref
```

### L4 Pipeline

1. `L4SourceClassifier`
   - 判断输入是否为 L4、L2 official account、L3 platform proxy 或 blocked commercial source。
   - 未通过 source quality classifier 的内容只能进入 `WeakSignalLead`。

2. `WeakSignalExtractor`
   - 只抽实体、产品名、事件词、可能的官方源路径、可能的商业缺口。
   - 不抽“公司结论”。

3. `LeadDeduperAndTTL`
   - 按 ticker / product / event / source / time 去重。
   - L4 lead 必须有 TTL；过期 lead 自动降权或淘汰。

4. `TargetedRepairRouter`
   - 把 lead 转成 L1/L2/L3 repair plan：
     - 官方披露 / IR / local filing；
     - 官方产品页 / 文档；
     - 主流新闻 / 监管 / 行业协会；
     - 公开 API；
     - L3 platform / marketplace / job / public order。

5. `PromotionGate`
   - 只有 repair 后得到 L1/L2/L3 parser-backed row，才允许进入 evidence graph。
   - 原始 L4 内容只作为 repair provenance，不作为 memo citation。

6. `MemoUseGate`
   - Memo 正文默认不展示 L4。
   - 只有在“风险线索/待验证事项”小节可以写成：“存在未验证线索，已尝试验证但未找到可信公开源”，且不能支撑核心判断。

### L4 禁止事项

- 禁止 L4 直接支持收入、销量、订单、市占率、产品成功、客户采用、技术领先、管理层意图等判断。
- 禁止把 Reddit、X、小红书、雪球、无来源论坛等内容作为核心引用。
- 禁止把二手搬运的 chart / screenshot 当作数据源。
- 禁止 L4 因“多处都这么说”而提权；数量不能替代 source authority。
- 禁止把商业源缺口用 L4 代理补成“方向性强结论”。

### L4 完成门控

L4 架构完成不等于 L4 可支撑研报结论。完成口径是：

1. L4 object schema 和 runtime store 可写入 `WeakSignalLead` / `WeakSignalExclusionNote` / `L4PromotionAttempt`。
2. L4 source classifier 能区分 official social、unverified social、forum、search snippet、common-crawl discovery、market chart lead、commercial gap。
3. Targeted repair 能从 L4 lead 触发 L1/L2/L3 source route。
4. Verifier / Memo gate 能证明 L4 没有被写成 ClaimCard 或核心 thesis。
5. Eval 中加入反例：给模型 L4 rumor，只允许生成 repair plan 或 exclusion note，不允许写成判断。

## L1-L3 纵向细分方法

### VerticalSourceLaneRegistry

后续不再只维护 source registry，还要维护 vertical source lane registry。

```text
VerticalSourceLane
- lane_id
- lane_name
- industry_schema
- subvertical
- company_archetype
- ticker_universe
- representative_tickers
- product_taxonomy_scope
- key_products_or_services
- L1_required_facts
- L1_financial_statement_focus
- L1_company_disclosed_kpi_focus
- L2_trusted_context_sources
- L2_regulatory_or_official_sources
- L2_official_product_surface_sources
- L3_proxy_sources
- L4_discovery_sources
- public_data_ceiling
- expected_commercial_gaps
- analyst_playbook_path
- source_playbook_path
- completion_gates
```

每个 lane 进入实施前，必须先生成两个 brief：

1. `AnalystPlaybook`
   - 这个行业怎么赚钱；
   - 关键产品 / 服务 / 产线；
   - 财务三表中重点科目；
   - 公司披露 KPI 的常见口径；
   - 哪些指标是强事实，哪些只能 proxy；
   - 典型误判和不能写的结论。

2. `SourcePlaybook`
   - L1 可用披露和监管文件；
   - L2 官方/监管/行业/论文/专利/产品页；
   - L3 市场 proxy；
   - L4 discovery；
   - source-specific parser / resolver；
   - 公开源天花板和商业 tracker gap。

Research Lead 不需要背所有行业知识；它读取 lane brief 后再做任务规划。

### Lane Completion Definition

一个 lane 不能因为“跑了几个 URL”就算完成。完成口径：

1. `ticker_universe` 已冻结，至少覆盖该 lane 的目标公司集合。
2. 每个 ticker 有 L1 filing / financial statement / company-disclosed KPI 覆盖状态。
3. 每个 ticker 有 product taxonomy / official product surface 覆盖状态，缺失必须有原因。
4. lane-required L2 source route 已接入或明确 gap。
5. lane-required L3 proxy route 已接入或明确 gap。
6. L4 只产生 lead / exclusion / repair attempt，没有直接进入 ClaimCard。
7. Source coverage gate 对 lane-specific requirements 可审计。
8. 至少 2-3 个 lane representative case 能跑出维度化 judgment，而不是证据清单或 caveat 拼贴。
9. 所有剩余缺口必须分类为：
   - `retrievable_gap`
   - `parser_or_resolver_gap`
   - `bounded_public_gap`
   - `commercial_gap`
   - `not_material_for_current_question`

## 第一版 Vertical Lanes

### V1 Semiconductors / AI Infrastructure

代表公司：

- NVDA, AMD, INTC, QCOM, AVGO
- ASML, TSM, AMAT, LRCX, KLAC
- DELL, SMCI, HPE, ANET, MRVL

重点产品：

- GPU / accelerator / CPU / NIC / networking / ASIC
- wafer fab / foundry / advanced packaging
- lithography / deposition / etch / metrology
- AI server / rack / networking system

L1：

- revenue by segment / product line
- inventory, purchase commitments, capex, gross margin
- customer concentration, backlog/order comments
- non-US annual reports / 20-F / 6-K / local filings

L2：

- official product pages and spec sheets
- supplier/customer official news
- export control / regulatory context
- PatentsView / OpenAlex topic only after assignee/topic resolver
- industry association and official trade/statistics

L3：

- CDW/channel offer for workstation/server products
- public contracts / awards
- hiring for AI infra / datacenter / networking
- developer ecosystem for CUDA / ROCm / software stack

L4：

- forum/rumor only for discovery of official launch, allocation, export-control or supply-chain source.

### V2 Consumer Electronics / Hardware Devices

代表公司：

- AAPL, MSFT, GOOGL, DELL, HPQ, LNVGY, SONY, SSNLF

重点产品：

- phones, tablets, PCs, wearables, gaming hardware, smart devices

L1：

- segment revenue, unit commentary if disclosed, warranty, inventory, channel comments

L2：

- official product pages/specs
- regulatory certification where available
- mainstream launch/news context

L3：

- channel offer / ecommerce price / availability
- app marketplace for device ecosystem where relevant
- review/ranking proxy

L4：

- launch rumor and supply-chain chatter only as repair lead.

### V3 SaaS / Cloud / Developer Products

代表公司：

- MSFT, AMZN, GOOGL, CRM, NOW, ADBE, SNOW, DDOG, NET, PLTR, MDB, TEAM

重点产品：

- cloud infra, AI service, observability, data platform, security, workflow, marketplace apps

L1：

- revenue by segment, RPO / cRPO / billings when disclosed, deferred revenue, sales efficiency, capex/lease if infra-heavy

L2：

- official docs, pricing pages, status pages, product release notes, customer/partner official news

L3：

- GitHub/npm/PyPI/HuggingFace
- hiring / capacity
- public contracts
- App Store / marketplace listing where relevant

L4：

- developer forum issue/chatter only to discover official docs, release notes or outage reports.

### V4 Pharma / Biotech / Medtech

代表公司：

- LLY, NVO, PFE, AMGN, MRK, JNJ, ISRG, BSX, SYK, ZTS

重点产品：

- approved drugs, pipeline indications, devices, procedures, trials

L1：

- product sales if disclosed, pipeline table, R&D, acquired IPR&D, milestone obligations

L2：

- ClinicalTrials, openFDA, CMS, labels, advisory committee materials, official press releases

L3：

- hiring, public tenders/contracts, hospital/procedure public leads where available

L4：

- patient/community discussion only as risk/discovery lead, never efficacy/safety fact.

### V5 Auto / Mobility / Transport Platforms

代表公司：

- TSLA, GM, F, RIVN, LCID, TM, MBG, UBER, LYFT

重点产品：

- vehicle model, platform, battery/charging, autonomy, mobility marketplace

L1：

- deliveries, ASP commentary if disclosed, inventory, warranty, capex, deferred revenue, credit/regulatory credits

L2：

- NHTSA vPIC / recalls / complaints, official model pages, charging network official data, regulatory filings

L3：

- used/new listing proxy, app marketplace, hiring, public incentives/contracts

L4：

- owner forum issues only for targeted official recall/service bulletin repair.

### V6 Banks / Financials / Capital Markets

代表公司：

- JPM, BAC, WFC, C, GS, MS, BLK, SCHW, CBOE

重点业务：

- net interest income, deposits, loans, trading, wealth/AUM, capital markets, exchange volumes

L1：

- call reports / SEC filings / Basel capital / deposits / loan categories / charge-offs / AUM

L2：

- FDIC / FRED / regulatory releases / official exchange statistics

L3：

- app marketplace only as digital engagement proxy; market reaction as bounded context

L4：

- social/news chatter only to discover regulatory or official event source.

### V7 Energy / Utilities / Industrials

代表公司：

- XOM, CVX, COP, SLB, NEE, DUK, SO, XEL, ED, GE, CAT, DE

重点产品 / 资产：

- upstream/downstream, oilfield services, generation assets, regulated utility territories, industrial equipment

L1：

- production, reserves, capex, regulated rate base, fuel costs, backlog/order book when disclosed

L2：

- EIA, FERC/state utility filings where available, official project pages, environmental/regulatory data

L3：

- public tenders/contracts, hiring, dealer/channel listings for equipment

L4：

- local chatter only to find official project/regulatory filings.

### V8 Retail / CPG / Restaurants / Travel

代表公司：

- WMT, COST, TGT, HD, LOW, PG, KO, PEP, NKE, SBUX, MCD, BKNG, ABNB

重点产品 / 业务：

- store/channel, category mix, menu/product SKUs, pricing/promotion, traffic, membership/loyalty

L1：

- same-store sales, transactions, ticket, inventory, gross margin, advertising/promotional spend when disclosed

L2：

- official product/menu/store pages, Census retail sales, BLS/CPI, company official news

L3：

- ecommerce listings, app marketplace, reviews/rankings, hiring

L4：

- consumer chatter only as discovery lead; POS/sell-through remains commercial gap.

## 执行顺序

### Step 0: L4 Architecture Runtime Contract

先落 L4 object schema、source classifier、promotion gate 和 eval 反例，不接大规模 L4 数据。

通过条件：

- L4 lead 可以被存储、去重、过期、转 repair plan。
- L4 不能直接变成 ClaimCard。
- Memo / Verifier 有反例测试。

当前实现状态（2026-06-17）：

- 已新增 `src/sec_agent/l4_weak_signal.py`，落地 `WeakSignalLead` / `WeakSignalExclusionNote` / `L4PromotionAttempt` runtime contract。
- 已实现 `classify_l4_source`，能区分 verified official social、unverified social/forum、search snippet、Common Crawl discovery、Yahoo/market chart lead、L2/L3 registered source 和 commercial tracker gap。
- 已实现 TTL / dedupe / `weak_signal_to_targeted_repair_plan`，L4 lead 只能转 L1/L2/L3 targeted repair plan。
- 已实现 `evaluate_l4_promotion_attempt` promotion gate：只有 parser-backed 且 entity-bound 的 L1/L2/L3 row 才能 promoted；L4 direct row、L2/L3 exact-authority row、unbound row 都 fail-closed。
- 已实现 `validate_l4_not_promoted_to_claim_cards` / `validate_memo_l4_usage`，用于 Memo/Verifier 防止 L4 进入 ClaimCard 或核心 thesis。
- 已新增 `tests/test_l4_weak_signal_contract.py`，覆盖 7 个 deterministic anti-promotion cases；当前 `7 passed`。
- 尚未做大规模 L4 ingestion；下一步先做 `VerticalSourceLaneRegistry`，再按 V1 lane 接入真实 L1/L2/L3/L4 source requirements。

### Step 1: Lane Registry Builder

基于 603 公司 universe、现有 industry schema、SEC taxonomy、product evidence graph 和人工 override，生成 `vertical_source_lane_registry_v0_1`。

通过条件：

- 每家公司至少有 primary lane。
- 重点公司可有 secondary lane，例如 MSFT 同时属于 SaaS/cloud、consumer devices、AI infra buyer。
- 每个 lane 有 ticker count、representative tickers、source requirements 和 gap summary。

当前实现状态（2026-06-17）：

- 已新增 `src/sec_agent/vertical_source_lane_registry.py` 和 `scripts/data_expansion/build_vertical_source_lane_registry.py`。
- 已从真实输入生成 `data/manifests/vertical_source_lane_registry_v0_1.json`、`data/manifests/vertical_source_lane_company_assignments_v0_1.jsonl` 和 `docs/internal/vnext_20260610/vertical_source_lane_registry.zh-CN.md`。
- 输入包括：
  - `data/manifests/tier1_tier2_market_universe_v0_1.csv`；
  - `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_nodes_v0_1.jsonl`；
  - `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_v0_1/company_product_evidence_gaps_v0_1.jsonl`；
  - `data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl`；
  - `data/manifests/official_product_surface_context_rows_v0_1.jsonl`；
  - `data/manifests/source_layer_capability_audit_v0_1.jsonl`。
- registry validation `pass`，覆盖 `603`家公司，8 个 lane 分布为：
  - V1 Semiconductors / AI Infrastructure：`43` primary / `57` inclusive；
  - V2 Consumer Electronics / Hardware Devices：`9` primary / `12` inclusive；
  - V3 SaaS / Cloud / Developer Products：`94` primary / `97` inclusive；
  - V4 Pharma / Biotech / Medtech：`68` primary；
  - V5 Auto / Mobility / Transport Platforms：`17` primary；
  - V6 Banks / Financials / Capital Markets：`77` primary；
  - V7 Energy / Utilities / Industrials：`216` primary / `219` inclusive；
  - V8 Retail / CPG / Restaurants / Travel：`79` primary / `80` inclusive。
- 跨 lane 代表公司已做少量 primary override：例如 `MSFT` primary V3、secondary V1/V2；`DELL` primary V1、secondary V2。
- 每个 lane 已写入 product taxonomy scope、L1 财务/披露重点、L2/L3/L4 source requirements、public data ceiling、commercial gap summary 和 registry phase source coverage gate。
- 当前每个 lane 的 source coverage gate 仍为 `gap` 而非 `pass`；这符合预期，因为 Step 1 只冻结 lane registry，不代表各 lane 的 source routes 已完成。下一步应进入 V1 lane playbook / source playbook / coverage closeout。

### Step 2: 选择 V1 Semiconductors / AI Infrastructure 作为第一个完整 lane

原因：

- 当前已有最多实际数据：SEC/product KPI、official product pages、developer ecosystem、public contracts、channel offer、hiring。
- 过去测试 case 反复暴露 AI infra / semicap / capex / supplier validation 问题。
- 产品、财务、供应链、资本开支、客户需求 proxy 都能同时验证。

通过条件：

- V1 lane playbook 完成。
- V1 ticker universe 冻结。
- V1 L1/L2/L3 source coverage gate 可跑。
- 至少 2 个 V1 case 能输出产品、财务、供应链、资本开支和竞争维度判断。

当前实现状态（2026-06-17）：

- 已新增 `scripts/data_expansion/build_v1_semiconductor_ai_infrastructure_lane.py`。
- 已基于真实 `vertical_source_lane_registry_v0_1` 生成 V1 lane package：
  - `docs/internal/vnext_20260610/vertical_lanes/v1_analyst_playbook.zh-CN.md`；
  - `docs/internal/vnext_20260610/vertical_lanes/v1_source_playbook.zh-CN.md`；
  - `docs/internal/vnext_20260610/vertical_lanes/v1_lane_coverage_report.zh-CN.md`；
  - `data/manifests/v1_semiconductors_ai_infrastructure_lane_coverage_v0_1.json`；
  - `tests/fixtures/v1_semiconductors_ai_infrastructure_lane_cases_v0_1.json`。
- V1 package validation `pass`；V1 primary ticker count `43`，secondary-inclusive ticker count `57`。
- V1 representative case 已落 3 个：
  1. `v1_ai_infra_demand_transmission_nvda_dell_hyperscaler_001`；
  2. `v1_semicap_nonus_local_filing_asml_tsm_amat_lrcx_002`；
  3. `v1_ai_server_channel_proxy_boundary_dell_hpe_smci_anet_003`。
- 每个 case 都要求 fundamentals、product_and_production、capital_and_financing、industry_supply_chain、competition_and_market_position、risk_and_counterevidence 六个维度，并包含 `L4_direct_claim_forbidden`、`commercial_gap_exposed_not_filled_by_proxy` 等 deterministic eval gate。
- 当前 V1 `lane_source_coverage_gate.status = gap`，不是 `pass`。这表示 V1 lane 已具备 planning / eval / source requirement runtime package，但后续仍需按 coverage gate 补齐 lane-specific L2/L3 route coverage，不能把 gap 写成已覆盖。

### Step 3: 每个 lane 内按 L1 -> L2 -> L3 -> L4 顺序闭环

1. L1：先做财务三表、披露产品 KPI、segment、company-disclosed operating metrics。
2. L2：再做官方产品页、监管/行业/论文/专利/官方新闻和 resolver。
3. L3：再做渠道、开发者、招聘、公开合同、app/ecommerce/review proxy。
4. L4：最后接 discovery lead，不影响强事实和 bounded proxy。

通过条件：

- L1 不完整时，不准用 L2/L3 替代基本面判断。
- L2/L3 只能补充机制、产品存在性、技术路线、需求 proxy、供应链线索。
- L4 只能触发 repair，不进入核心判断。

### Step 4: Lane 完成后再进入下一 lane

一个 lane 结束时必须写：

- lane coverage report；
- source gap ledger；
- commercial gap ledger；
- 2-3 个 representative case eval；
- Research Lead planning skill 更新；
- Specialist skill / playbook 更新；
- runtime source manifest / DB path 更新。

### Step 5: 回扫 09-15 Completion Gaps

当前实现状态（2026-06-17）：

- 已新增 [17 09-15 Completion Gap Register](17_09_15_completion_gap_register.zh-CN.md)，对 09-15 文档和 master checklist 做系统回扫。
- 该 register 将剩余事项分成 `runtime_gap`、`eval_gap`、`source_gap`、`prod_hardening_gap`、`known_boundary`，避免把“已有框架”“已有 smoke”“已产品化”混在一起。
- 当前最先需要处理的三类缺口是：
  1. V1 `lane_source_coverage_gate.status=gap` 的 source coverage closeout；
  2. R12 12-case successor / 10-20 broader release gate 和 failure/gold lifecycle；
  3. 后端 DB/Redis/ObjectStore/SSE/cancel/resume/load 的产品化 gate。
- V2-V8 lane packages 尚未开始，必须在 V1 coverage closeout 之后按 lane 闭环推进，不能回到全局零散补源。

### Step 6: V1 Source Coverage Closeout

当前实现状态（2026-06-17）：

- 已新增 `src/sec_agent/vertical_source_lane_closeout.py` 和 `scripts/data_expansion/build_v1_source_coverage_closeout.py`。
- 已完成 V1 source repair tranche，新增公开源 runtime rows：
  - `scripts/data_expansion/build_public_contract_award_context_rows.py` 扩展 DELL/HPE/NVDA/INTC/AMD/QCOM USAspending probes，修复 `public_order_proxy` 和 `supply_chain_official_relationship` primary V1 row gap；
  - `scripts/data_expansion/build_hiring_capacity_context_rows.py` 新增 Workday ATS provider，接入 NVDA/HPE 官方 Workday CXS rows，修复 `hiring_capacity_proxy`；
  - `scripts/data_expansion/build_v1_openalex_technology_research_context_rows.py` 新增 OpenAlex works search issuer/topic 双绑定 rows，修复 `technology_research_proxy`；
  - `scripts/data_expansion/build_v1_trusted_external_context_rows.py` 新增 SIA/SEMI 官方行业协会 L2 rows，修复 `trusted_external_context`；
  - `scripts/data_expansion/build_v1_macro_official_exposure_context_rows.py` 从 FRED/EIA 官方上下文生成显式 `company_exposure_to_macro_driver` bridge rows，修复 `macro_official_context`。
- 已生成：
  - `data/manifests/v1_semiconductors_ai_infrastructure_source_closeout_v0_1.json`；
  - `docs/internal/vnext_20260610/vertical_lanes/v1_source_coverage_closeout.zh-CN.md`。
- repair 后真实 closeout 结果：
  - `status=pass`；
  - `requirement_count=10`；
  - `pass_requirement_count=10`；
  - `source_gap_requirement_count=0`；
  - `observed_runtime_row_count=475`；
  - `observed_primary_ticker_count=15/43`；
  - `commercial_gap_count=15`。
- 10 个 V1 requirement 均已有 primary V1 parser-backed runtime rows：
  - `primary_company_disclosure`；
  - `official_product_surface`；
  - `trusted_external_context`；
  - `supply_chain_official_relationship`；
  - `developer_ecosystem_proxy`；
  - `channel_offer_proxy`；
  - `public_order_proxy`；
  - `hiring_capacity_proxy`；
  - `macro_official_context`；
  - `technology_research_proxy`。
- 这一步把 V1 source coverage 从“registry gap / closeout gap”推进到 `source_gap=0`，但不代表商业 tracker 缺口被解决。`commercial_gap_count=15` 仍保留为明确边界，公开 proxy 只能支持 context、directional verification 和 research leads，不能替代 IDC/Counterpoint/Omdia/Gartner、S&P Mobility、IQVIA、POS/channel tracker、consensus 等商业数据。
- 新增 lane-level / bridge rows 必须遵守：
  - SIA/SEMI trusted external rows 的 ticker 只是 `v1_lane_context_routed_to_representative_ticker`，不是 issuer-specific fact；
  - FRED/EIA macro rows 通过 `v1_company_exposure_to_macro_driver_bridge` 暴露宏观驱动，不证明公司收入、销量、margin、份额或需求；
  - OpenAlex rows 只有 issuer term 和 technology topic 同时在快照中出现时才 materialize，仍只是 research/IP proxy；
  - Workday ATS、USAspending、CDW、developer ecosystem 等 L3 rows 均保持 context-only 和 forbidden claim gate。

### Step 7: V2-V8 Lane Packages and Source Closeout

当前实现状态（2026-06-17）：

- 已把 V1 专用 closeout 泛化为所有 vertical lane 可复用的 runtime source closeout：
  - `src/sec_agent/vertical_source_lane_closeout.py` 新增 `build_lane_source_coverage_closeout` / `write_lane_source_coverage_closeout`；
  - `scripts/data_expansion/build_vertical_lane_source_closeouts.py` 可直接生成 8 个 lane 的 closeout JSON/report；
  - closeout 默认读取 L1 product KPI、official product surface、public official API、developer ecosystem、app marketplace、hiring、public contract、channel offer、V1 lane rows 和新增 vertical lane public rows。
- 已新增通用 lane package builder：
  - `src/sec_agent/vertical_source_lane_package.py`；
  - `scripts/data_expansion/build_vertical_lane_packages.py`。
- 已为 V2-V8 生成 AnalystPlaybook / SourcePlaybook / CoverageReport / Coverage JSON / 3 个 representative case：
  - V2 Consumer Electronics / Hardware Devices；
  - V3 SaaS / Cloud / Developer Products；
  - V4 Pharma / Biotech / Medtech；
  - V5 Auto / Mobility / Transport Platforms；
  - V6 Banks / Financials / Capital Markets；
  - V7 Energy / Utilities / Industrials；
  - V8 Retail / CPG / Restaurants / Travel。
- 已新增 `scripts/data_expansion/build_vertical_lane_public_context_rows.py`，将 V2-V8 的 lane-scoped 公开源补成 bounded context rows：
  - L2 trusted external / industry association rows：CTA、CNCF、PhRMA、Alliance for Automotive Innovation、SIFMA、EEI、NRF；
  - L2 macro / official bridge rows：FRED、EIA 已物化官方行投影到 lane exposure bridge；
  - L3 public proxy rows：Apple Jobs、Apple Lookup、Pfizer Careers、Uber Careers、Chevrolet official model page、GE Vernova Careers、Starbucks menu、Airbnb Apple Lookup；
  - L3 public order / contract rows：USAspending for PFE/JNJ/GM/F/TSLA；
  - L3 technology research rows：OpenAlex for LLY/NVO/PFE。
- 新增输出：
  - `data/manifests/vertical_lane_public_context_rows_v0_1.jsonl`：`77` 条 parser-backed lane-scoped bounded context rows；
  - `data/manifests/vertical_lane_public_context_summary_v0_1.json`；
  - `data/manifests/vertical_lane_package_summary_v0_1.json`；
  - `data/manifests/vertical_lane_source_closeouts_v0_1.json`；
  - `docs/internal/vnext_20260610/vertical_lanes/vertical_lane_source_closeouts_summary.zh-CN.md`。
- V2-V8 package validation 均为 `pass`，每个 lane 均有 `3` 个 deterministic representative case。
- 最新全 lane closeout：
  - `status=pass`；
  - `lane_count=8`；
  - `by_status={"pass": 8}`；
  - 所有 lane 的 `source_gap_requirement_count=0`。
- 各 lane runtime closeout：
  - V1：`10/10` requirements pass，`475` observed runtime rows，`15` commercial gaps retained；
  - V2：`8/8` requirements pass，`250` observed runtime rows，`16` commercial gaps retained；
  - V3：`9/9` requirements pass，`687` observed runtime rows，`16` commercial gaps retained；
  - V4：`8/8` requirements pass，`939` observed runtime rows，`6` commercial gaps retained；
  - V5：`9/9` requirements pass，`376` observed runtime rows，`15` commercial gaps retained；
  - V6：`4/4` requirements pass，`632` observed runtime rows，`7` commercial gaps retained；
  - V7：`7/7` requirements pass，`2,514` observed runtime rows，`16` commercial gaps retained；
  - V8：`7/7` requirements pass，`921` observed runtime rows，`10` commercial gaps retained。

边界：

- `source_gap_requirement_count=0` 表示每个 lane-required route 至少有 primary-lane parser-backed runtime rows 可供 specialist 使用；它不表示每个 ticker / product / SKU / indication / model 都已完整覆盖。
- `commercial_gap_count` 仍保留为公开源天花板：shipments/share/ASP/POS/sell-through/channel inventory/registration/VIO/scripts/prescriptions/consensus/private flows 等不能用公开 proxy 兜底。
- 新增 vertical lane public rows 全部为 `context_only=true`、`can_support_company_exact_fact=false`、`exact_value_authority=false`，并带 `lane_id` / `vertical_lane_id`，防止跨 lane 泄漏。
- 对 V5，Tesla 官方 careers/configurator URL 在脚本初版中出现 403；最终改用 Uber Careers、Chevrolet official model page、USAspending 和 FRED bridge 补齐 lane route。这是 lane source coverage，不代表 Tesla 单公司 product/channel 覆盖完整。
- 对 V7，GE Vernova careers 初版 URL 错误，已改为 `https://careers.gevernova.com/jobs` 后 materialized。

验收：

- `python -m py_compile src\sec_agent\vertical_source_lane_closeout.py src\sec_agent\vertical_source_lane_package.py scripts\data_expansion\build_vertical_lane_packages.py scripts\data_expansion\build_vertical_lane_public_context_rows.py scripts\data_expansion\build_vertical_lane_source_closeouts.py` 通过；
- `python -m pytest tests\test_vertical_source_lane_package_and_closeout.py tests\test_v1_semiconductor_ai_infrastructure_lane.py tests\test_vertical_source_lane_registry.py -q`：`6 passed`；
- `python scripts\data_expansion\build_vertical_lane_source_closeouts.py`：8/8 lane closeout pass。

### Step 8: 603 Company Public Source Coverage Matrix

当前实现状态（2026-06-18）：

- 已新增 company-level coverage matrix，不再把 lane route pass 等同于每家公司覆盖完成：
  - `src/sec_agent/company_public_source_coverage_matrix.py`；
  - `scripts/data_expansion/build_company_public_source_coverage_matrix.py`；
  - `tests/test_company_public_source_coverage_matrix.py`。
- 该矩阵把每个 ticker 的 primary lane requirements 下钻成：
  - `primary_company_disclosure`；
  - `official_product_surface`；
  - lane-specific L2 trusted / regulatory / macro context；
  - lane-specific L3 public proxy；
  - parser-backed row count；
  - issuer / product / counterparty binding status；
  - exact-authority violation gate；
  - `source_gap` / `parser_gap` / `resolver_gap` / `source_boundary_violation`；
  - repair priority 和 next action。
- 已生成：
  - `data/manifests/company_public_source_coverage_matrix_v0_1.json`；
  - `data/manifests/company_public_source_coverage_matrix_v0_1.jsonl`；
  - `data/manifests/company_public_source_repair_queue_v0_1.jsonl`；
  - `docs/internal/vnext_20260610/vertical_lanes/company_public_source_coverage_matrix.zh-CN.md`。
- 首次 603 公司审计结果：
  - `company_count=603`；
  - `requirement_count=4,418`；
  - `pass_requirement_count=432`；
  - `gap_requirement_count=3,986`；
  - `fail_requirement_count=0`；
  - `public_interface_ready_company_count=1`；
  - `partial_public_interface_company_count=220`；
  - `public_interface_gap_company_count=382`；
  - `repair_queue_count=3,986`。
- 当前 gap 全部落在 `source_gap`，没有发现 parser-backed rows 的 parser/resolver 大规模失败：
  - `company_specific_runtime_row_missing=3,569`；
  - `sec_or_company_disclosure_runtime_row_missing=402`；
  - `non_us_public_filing_or_company_ir_runtime_row_missing=15`。
- repair queue 已接入 Z 盘 product evidence graph seed：
  - `seed_available=1,584`；
  - `seed_missing=2,402`；
  - high-priority queue 中 `primary_company_disclosure` 为 `417/417` 有 seed；
  - `official_product_surface` 为 `208/214` 有 seed。
- repair queue 排名前几类：
  - `trusted_external_context=567`；
  - `macro_official_context=566`；
  - `hiring_capacity_proxy=515`；
  - `public_order_proxy=421`；
  - `primary_company_disclosure=417`；
  - `official_product_surface=214`。

边界：

- Step 7 的 `8/8 lane pass` 表示每个 lane-required route 至少有 primary-lane parser-backed runtime rows，可供 specialist 使用。
- Step 8 的 company matrix 是更严格的 issuer-level coverage gate：每家公司必须自己有对应 source role 的 runtime row，或者进入 repair queue / commercial boundary。
- 当前最大问题不是 parser 质量，而是大量公司还没有 company-specific runtime materialization。
- 对 Research Lead 而言，后续 full-chain 不能只读 lane closeout；必须优先读取 company matrix：
  1. 该 ticker / requirement 已 pass，直接允许 specialist 使用；
  2. `source_gap`，触发对应 source adapter / live repair；
  3. `parser_gap`，触发 parser/schema repair；
  4. `resolver_gap`，触发 issuer/product/counterparty resolver；
  5. 仍无法公开源补齐，才暴露 `bounded_public_gap` 或 `commercial_gap`。

下一步执行：

1. 按 `company_public_source_repair_queue_v0_1.jsonl` 分 lane / requirement / source_id 做 repair tranche。
2. 第一优先级补 `primary_company_disclosure` 和 `official_product_surface`，因为它们决定产品-财务桥接的强事实底座。
3. 第二优先级补各 lane 的 L2 trusted / macro / regulatory bridge。
4. 第三优先级补 L3 public proxy，继续保持 context-only，不替代商业 tracker。
5. 每个 tranche 完成后重跑 company matrix，观察 `public_interface_ready_company_count`、`partial_public_interface_company_count`、`repair_queue_count` 和 gap type 分布。

### Step 9: ProductFamilyLaneRegistry / CompanyProductFamilyAssignment / FamilySourceRoutePlan

当前实现状态（2026-06-18）：

- 已把 603-company company matrix 继续下钻到 `Company x ProductFamily x SourceRoute`：
  - `src/sec_agent/product_family_source_routes.py`；
  - `scripts/data_expansion/build_product_family_source_route_plan.py`；
  - `tests/test_product_family_source_routes.py`。
- 已生成：
  - `data/manifests/product_family_lane_registry_v0_1.json`；
  - `data/manifests/company_product_family_assignments_v0_1.jsonl`；
  - `data/manifests/family_source_route_plan_v0_1.jsonl`；
  - `data/manifests/family_source_fetch_audit_v0_1.json`；
  - `docs/internal/vnext_20260610/vertical_lanes/product_family_source_route_plan.zh-CN.md`。
- `ProductFamilyLaneRegistry` 当前覆盖 `45` 个 family，先把 V1 拆到 `GPU/accelerator`、`EDA/IP`、`foundry`、`semicap equipment`、`memory`、`networking`、`server OEM`、`power/cooling`，V2-V8 也有对应 family/fallback。
- `CompanyProductFamilyAssignment` 对 `603/603` 公司均有 assignment 和 route plan；为了避免污染，assignment 只允许使用 issuer-bound company/product rows 和强关键词，弱词如 `ip/node/power/rack/server/cloud/vehicle/mobility` 不再单独触发 family。
- 当前全量结果：
  - `company_count=603`；
  - `family_assignment_count=799`；
  - `route_plan_count=3,132`；
  - `runtime_family_row_available=141`；
  - `runtime_company_row_available=460`；
  - `seed_available_not_materialized=1,360`；
  - `not_materialized=1,171`。
- 抽样核验：
  - `NVDA -> gpu_accelerator / networking`；
  - `ASML -> semicap_equipment`；
  - `TSM -> foundry`；
  - `DELL/SMCI -> server_oem`；
  - `ANET -> networking`；
  - `VRT -> power_grid_cooling`；
  - `AAPL -> smartphones_tablets / pcs_peripherals / wearables_devices`；
  - `TSLA -> ev_vehicle_platform / battery_charging_autonomy`；
  - `LLY -> glp1_metabolic / oncology_immunology`。
- 已修复两个会污染 full-chain 的问题：
  - official product page materialized snapshot 只能满足 `official_product_surface`，不能替 `channel_offer/public_order/developer` 等 L3 route 背书；
  - trusted external / macro / peer-context row 不能参与 company product family assignment，否则会把行业对标词误识别为公司产品族。

边界：

- Step 9 保证每家公司都有 family assignment 和 route plan，且已有 rows / seed / missing 被显式分类。
- Step 9 不代表所有 L2/L3 非 SEC 源都已经抓取并解析；`seed_available_not_materialized` 和 `not_materialized` 是下一轮 family-scoped source repair 队列。
- Full-chain Research Lead 后续必须优先读取 `family_source_route_plan_v0_1.jsonl`，按 family route 去查，不再用泛行业 L2/L3 route 盲搜。
- `runtime_company_row_available` 只能表示该 company-route 有 row，若未命中 family term，Specialist 只能当公司级上下文或触发 family binding repair，不能直接写成产品族证据。

下一步执行：

1. 先处理 `seed_available_not_materialized`：从 product graph / company matrix seed 解析真实 URL / raw snapshot，按 family route fetch + parse 成 runtime rows。
2. 再处理 `not_materialized`：按 family route policy 做官方源 / 可信源 / proxy 源发现，不直接兜底成 bounded gap。
3. 每轮 repair 后重跑 `build_product_family_source_route_plan.py`，要求 route status 从 `seed_available_not_materialized/not_materialized` 转为 `runtime_family_row_available` 或明确 `bounded_public_gap/commercial_gap`。
4. 每个 lane 至少抽样 5-10 个代表公司人工核验 family assignment 和 sample URLs，避免 full-chain 时才发现检索方向错。

### Step 10: Company Product Slot / Relationship Graph Runtime Closeout

当前实现状态（2026-06-18）：

- 已把 Step 9 的 route plan 下钻成可供 runtime 使用的公司-产品槽位和产品关系图谱：
  - `src/sec_agent/product_slot_relationship_graph.py`；
  - `scripts/data_expansion/build_product_slot_relationship_graph.py`；
  - `tests/test_product_slot_relationship_graph.py`。
- 已生成：
  - `data/manifests/company_product_slots_v0_1.jsonl`；
  - `data/manifests/product_relationship_graph_nodes_v0_1.jsonl`；
  - `data/manifests/product_relationship_graph_edges_v0_1.jsonl`；
  - `data/manifests/product_relationship_graph_summary_v0_1.json`；
  - `data/manifests/product_family_runtime_gap_closeout_v0_1.jsonl`；
  - `data/manifests/product_family_runtime_gap_closeout_summary_v0_1.json`；
  - `docs/internal/vnext_20260610/vertical_lanes/product_slot_relationship_graph.zh-CN.md`。
- 最新 graph closeout：
  - `company_count=603`；
  - `product_family_count=79`；
  - `product_slot_count=6,454`；
  - `with_family_bound_runtime_slot_count=6,454`；
  - `with_url_slot_count=6,454`；
  - `official_surface_slot=4,432`；
  - `filings_taxonomy_slot=1,899`；
  - `product_kpi_exact_slot=114`；
  - `bounded_context_slot=9`；
  - `seed_needs_locator=0`；
  - `company_route_needs_family_binding=0`；
  - graph edges `24,237`，其中 `COMPETES_WITH=3,358`，supply-chain / complement template edges 仍是 analyst-context edges，不代表订单、份额、销量或客户集中度。
- 本轮修复了可实际验证的 product/source gaps：
  - 补 `MSFT` official AI / Copilot pages，并修复 ticker override 优先于通用 blocked-domain 过滤，否则 `microsoft.com` 会被错误清除；
  - 补 `BYD` EV / energy / Battery-Box official sources；
  - 补 `DISCO` English product / solution pages，去掉 `discousa.com` 对 `6146.T` 的干扰；
  - 补 `ENLT` project / renewable energy official pages；
  - 补 `TTWO` games / IR official pages；
  - 补 `SWKS` 和 `PLTR` official sitemap catalog，作为产品 URL catalog context，只支持产品存在和检索规划，不支持 KPI；
  - 补 `TSCO` corporate official pages，并把 TSCO 从错误 `auto_aftermarket_retail` 改到 `farm_ranch_rural_retail`；
  - 把 `CSGP` 从粗粒度 REIT 改到 `real_estate_data_marketplace`；
  - 给 `META/PSKY` digital media family 补 Facebook / Instagram / WhatsApp / Paramount+ / CBS / Nickelodeon 等 product aliases，使 app/marketplace proxy 能进正确 family，但仍不能支持 AI platform 或广告收入结论。
- 剩余未提权项已写入 `product_family_runtime_gap_closeout_v0_1`：
  - `bounded_public_gap=22`；
  - `not_promotable_context_gap=4`；
  - 主要原因是官方站点 403 / bot challenge / 429 / HTTP 567 / timeout / system down，或已有 row 只是公司级、宏观级、车型级、open research proxy，不能安全绑定到目标 product family。
- 2026-06-18 追加 repair ladder / browser-backed materialization：
  - 新增 `src/sec_agent/product_family_gap_repair.py`；
  - 新增 `scripts/data_expansion/repair_product_family_runtime_gaps.py`；
  - `materialize_official_product_surface_pages.py` 新增 `PlaywrightBrowserFetcher` / `HttpThenBrowserFetcher`，优先 HTTP，遇到 blocked/non-content 页面再使用本机 Chrome/Edge 正常浏览器渲染；
  - 新增 `tests/test_product_family_gap_repair.py`，验证未走完 ladder 的 row 不能 final closeout，修复后可进入 runtime row。
- repair ladder 运行结果：
  - 输入原 `26` 条 closeout row；
  - 第一轮 `attempted_count=144`，新增 materialized official pages `38` 条，把 `14/26` 提权到 runtime-ready；
  - 后续修复 URL candidate 截断、subdomain 生成、ticker-family taxonomy whitelist、官方 ecommerce/catalog/IR 路径和 `LLY` oncology 专项路由；
  - 最终完整 ledger：`fixed_to_runtime_row=26`、`adapter_needed_not_final_gap=0`、`final_gap_allowed_count=0`；
  - 最新 materialized official pages `891` rows / `432` tickers，official product surface context rows `2,131` rows / `432` tickers，已重建并进入 product graph；
  - 这批原 closeout rows 现在都可作为 bounded runtime context / taxonomy / official surface slot 使用，但仍不支持 sales/share/ASP/sell-through/库存/未披露产品 KPI。
- 新增 repair artifacts：
  - `data/manifests/product_family_runtime_gap_repair_ledger_v0_1.jsonl`；
  - `data/manifests/product_family_runtime_gap_repair_summary_v0_1.json`。
- 已从 26 条中修复到 runtime-ready 的 ticker-family：
  - `2317.TW / electronics_manufacturing_services`；
  - `3231.TW / electronics_manufacturing_services`；
  - `2382.TW / electronics_manufacturing_services`；
  - `AEE / regulated_utility_power`；
  - `BHP / mining_materials_commodities`；
  - `C / banking_credit_deposits`；
  - `C / capital_markets_trading`；
  - `CAH / healthcare_distribution_services`；
  - `CSGP / real_estate_data_marketplace`；
  - `DIOD / analog_embedded_semiconductors`；
  - `DIOD / power_semiconductor_components`；
  - `FANG / upstream_oil_gas`；
  - `FDXF / logistics_transportation`；
  - `INTC / gpu_accelerator`；
  - `INVH / real_estate_infrastructure_reit`；
  - `LLY / oncology_immunology`；
  - `LVS / lodging_resorts_cruise`；
  - `LULU / apparel_athletic_retail`；
  - `META / ai_platform`；
  - `MPWR / power_semiconductor_components`；
  - `NIO / ev_vehicle_platform`；
  - `ORLY / auto_aftermarket_retail`；
  - `PSKY / digital_media_content`；
  - `TEL / connectivity_semiconductor_components`；
  - `TSLA / battery_charging_autonomy`；
  - `UHS / healthcare_facilities_services`。
- 关键修复原因：
  - 多域名 issuer 的 candidate URL 现在按 `path x domain` 轮询，避免主域 403 把专门 product/pipeline 域名截断；
  - `ir.*`、`medical.*`、`shop.*` 等多级官方子域不再错误生成 `www.ir.*`；
  - `LLY / oncology_immunology` 通过 Lilly 官方 oncology pipeline 和 medical oncology 页面进入 `official_surface_slot`；
  - `AEE/DIOD/INVH/LULU/ORLY/TSLA/UHS` 等通过严格 ticker-family whitelist 或官方 surface row 完成 family binding；
  - 所有仍弱的页面只能作为 bounded context / taxonomy / retrieval planning，不能转成产品收入、销量、市场份额或订单证据。
- 判断规则更新：
  - `product_family_runtime_gap_closeout_v0_1` 现在是 repair 输入的旧 closeout 视图；后续判断必须优先读取 `product_family_runtime_gap_repair_ledger_v0_1`。
  - 默认不允许输出 `public_source_exhausted_gap`。只有官网/浏览器、PDF/catalog、当地交易所/监管、L2/L3 family route、family-binding repair 全部走完并留下审计记录，才允许最终 closeout。
  - 若未来再出现 `adapter_needed_not_final_gap`，它不是不能修，只表示当前 parser/browser/source adapter 还没走完，Research Lead 只能触发 targeted repair 或暴露未完成边界。

Research Lead 使用规则：

1. `product_kpi_exact_slot` 可进入产品/财务桥接，但只能引用对应 metric / period / unit / product。
2. `filings_taxonomy_slot` 可支持公司披露产品 taxonomy 和检索规划，不自动支持产品收入、销量或份额。
3. `official_surface_slot` 可支持产品存在、产品页、规格、URL catalog 和产品 family 检索，不支持销售/份额/ASP/库存。
4. `bounded_context_slot` 只能做方向性 context 和待验证线索。
5. `seed_needs_locator` / `company_route_needs_family_binding` 必须先读 `product_family_runtime_gap_repair_ledger_v0_1`；若 repair state 是 `adapter_needed_not_final_gap` 或仍缺 ladder steps，Research Lead 只能继续 targeted repair 或暴露未完成边界，Memo Writer 不能用弱 fallback 补成结论。

### Step 11: R1-R5 Exact-Slot Data Layer Closeout

当前实现状态（2026-06-18）：

- 已按 18 文档把 source-layer closeout 从 lane-level / context-level 升级为 company-level exact-slot gate：
  - `ExactSlotContractRegistry` 定义 L1/L2/L3 每个 source role 的 required fields、allowed claims、forbidden claims 和 authority boundary；
  - `CompanyExactSlotCoverageMatrix` 覆盖 `603/603` 公司；
  - `exact_slot_gap_ledger_v0_1.jsonl` 和 `exact_slot_gap_closeout_v0_1.jsonl` 记录剩余缺口的 source attempt / resolver / parser / source-profile closeout。
- 最新 matrix：
  - company_count `603`；
  - all-required exact-ready `85`；
  - partial exact-ready `518`；
  - no exact-ready `0`；
  - exact rows `27,276`；
  - exact gaps `1,131`；
  - rows by layer: `L1=20,523`、`L2=4,195`、`L3=2,541`；
  - company coverage by layer: `L1=587`、`L2=603`、`L3=420`。
- R1/R2/R3/R4/R5 的当前状态：
  - R1: exact-slot contract / coverage matrix / gap ledger 已落地；
  - R2: SEC CompanyFacts / FSD 财务科目 exact rows 覆盖 `587/603`，official product surface applicable requirements `310/310` ready；
  - R3: macro / energy / financial regulatory / technology research official or official-API routes 已按 source-role exact/proxy row 接入；
  - R4: trusted external、USAspending、iTunes、ClinicalTrials/openFDA、NHTSA、ATS、CDW 等 L2/L3 routes 已进入 attempts / rows / closeout ledger；
  - R5: product KPI exact closeout 覆盖 `603/603`，其中 `77` 家 ready，`526` 家为 audited product KPI exact gap。
- 最新 closeout：
  - `exact_slot_gap_closeout_summary_v0_1.json` 为 `status=pass`；
  - `unclassified_closeout_count=0`；
  - remaining exact-slot gaps: `public_source_exhausted_gap=957`、`resolver_gap=151`、`parser_or_source_profile_gap=16`、`not_applicable_or_source_gap=7`。
- 当前不能宣称公开源已填满所有 L1/L2/L3：
  - L1 仍有 `16` 家非美 / 非 SEC CompanyFacts company disclosure exact gap，需要当地交易所、公司 IR 或年报表格 parser；
  - L3 仍有 `183` 家没有任何可提权 proxy exact row，主要来自 ATS、channel、developer、app/review、public-award、监管/车型适用性边界；
  - `526` 家没有 company-disclosed product KPI exact slot，不能用 official surface、taxonomy、招聘、渠道、宏观或新闻补成产品表现数据。

Research Lead 使用规则补充：

1. 优先读取 `exact_slot_coverage_matrix_v0_1.jsonl` 决定每个维度是否有 exact-ready 证据。
2. 对 `exact_slot_gap_closeout_v0_1.jsonl` 只能写缺口和边界，不能把 closeout row 提权为 evidence。
3. 对 L3 proxy rows 只能写 source-role 自身事实，例如公开 job row、公开 award、App Store listing、CDW SKU/quote、OpenAlex/PatentsView research signal；不能转写成公司需求、收入、订单、份额或产品成功。
4. 对 product KPI，只有 `product_kpi_exact_slot` 可进入产品-财务桥接；`official_surface_slot` 和 `filings_taxonomy_slot` 只能辅助产品 taxonomy、规格、检索规划和竞争图谱。

## 与 Agent Graph 的关系

Research Lead 的输入需要新增：

- `vertical_source_lane_registry`
- `active_lane_brief`
- `lane_source_coverage_gate`
- `lane_product_taxonomy_scope`
- `lane_financial_statement_focus`
- `lane_public_data_ceiling`

Research Lead 的任务不是学习所有行业细节，而是：

1. 识别问题涉及哪些 lane。
2. 加载 lane brief。
3. 决定哪些 specialist 激活。
4. 检查每个维度的 lane-specific evidence 是否够用。
5. 对 retrievable gap 发起 targeted repair。
6. 对 commercial gap 写边界。

Specialist 的 skill 不应写成泛泛行业百科，而应从 lane playbook 注入：

- 本 lane 核心产品；
- 本 lane 关键财务科目；
- 本 lane 常见 KPI；
- 本 lane L2/L3 source validity rules；
- 本 lane 禁止提权规则；
- 本 lane commercial tracker gap。

Memo Writer 不读取 L4，不自行搜索，不补事实，只按 Research Lead synthesis plan 写成自然语言报告。

## 当前优先级

1. 先落 L4 runtime contract 和 gate，防止后续弱信号污染。
2. 建 `VerticalSourceLaneRegistry`，把 600+ 公司按 lane / subvertical / product scope 分清。
3. 先做 V1 semiconductors / AI infrastructure 的完整闭环。
4. V1 通过后再做 V2 consumer hardware 或 V3 SaaS/cloud，顺序根据测试 case 和缺口严重程度决定。
5. 不再全局零散接源；每次接源必须说明服务哪个 lane、哪个产品/财务判断、哪个 gate。

## 禁止事项

- 不用 L4 替代 L2/L3。
- 不用 L2/L3 替代 L1 基本面。
- 不把所有行业都用一套通用 KPI。
- 不把“有网页可爬”当作 source 完成。
- 不把“有 parser row”当作 lane 完成。
- 不在 lane playbook 缺失时跑 full-chain 深度研究 case。
