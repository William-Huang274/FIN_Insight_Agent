# 15 源层能力审计与 Analyst-First 输出优化小阶段

日期：2026-06-15

## 背景

R12 真实 case 暴露的核心问题不是单一 Memo Writer 文风问题，而是 agent graph 的目标函数和证据进入规则偏成了“审计式缺口暴露”。当前链路能较好防止弱证据乱提权，但容易把可信补充源、市场 proxy 和公开线索挡在事实门外后直接写成“无法判断”，导致研报像搜索结果与 caveat 拼贴，缺少投研判断密度。

下一阶段目标不是放松事实门控，而是把目标重写为：

> 在可信数据边界内，优先寻找可成立的、有投资含义的 bounded judgment；无法提权的证据也要分层进入 evidence graph，作为 context / proxy / lead / gap 使用，并在报告中清楚标注边界。

## 要修的五类问题

1. 上游证据不够丰富：产品、竞品、行业、供应链、渠道、开发者生态、公开订单、招聘、主流新闻等 2/3 层 proxy 没有充分进入。
2. Parser 没把网页 / PDF / XLS / HTML 表格转成结构化 facts：抓到了页面，但没有变成可分析、可引用、可 gate 的数据。
3. Research Lead 没有像主分析师一样追问缺口：它应判断“公开源理论上能补吗”，能补就 targeted repair，不能补才暴露 bounded/commercial gap。
4. Memo Writer 过度泄露审计边界：它应写判断、依据、反证、缺口和触发条件，而不是通篇“不能判断”。
5. 2/3/4 层源能力没有系统审计：需要逐源检查当前是否接入、能否爬、能否解析、能否结构化、能否进入 specialist 和 memo。

## 源层定义

| 层级 | 名称 | 可支持内容 | 禁止内容 |
| --- | --- | --- | --- |
| L1 | 强事实层 | SEC、公司年报/IR、交易所文件、监管数据、官方统计、XBRL、结构化表格；可支持精确财务、披露口径、管理层说法、官方产品线。 | 未披露产品销量、渠道库存、市场份额、实时交易意图。 |
| L2 | 可信补充层 | 主流财经媒体、行业协会、政府/监管数据库、交易所公告、公司官方博客/产品页、供应商/客户官方新闻、论文/专利/ClinicalTrials/openFDA/NHTSA/EIA/FRED；可支持行业背景、产品存在性、研发/审批/技术路线、供应链关系、需求 proxy。 | 直接当作公司收入、份额、利润率、真实销量。 |
| L3 | 市场 proxy 层 | 电商平台、App Store 排名、GitHub/npm/PyPI/HuggingFace、招聘、渠道报价、公开招投标、公开订单信息、平台评论/下载排名；可支持方向性判断。 | 直接当作公司收入、份额、销量、ASP 或库存事实。 |
| L4 | 弱信号 / 排除层 | 营销号、自媒体转述、无来源论坛、二手搬运、无法验证社媒；只能做 discovery lead 或反向排除。 | 进入核心判断或作为证据卡支撑 thesis。 |

## SL0 Source-Layer Capability Audit

目标：先把数据源现状查清楚，回答每类源到底是没接、能爬不能解析、能解析不能结构化、能结构化但不能提权、还是能进入 memo 但被 selector/writer 没用好。

执行：

1. 合并现有公开源资产：
   - `configs/data_sources/public_source_coverage_v0_1.yaml`
   - `data/manifests/public_source_full_availability_audit_v0_1.jsonl`
   - `data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl`
   - `data/manifests/public_source_inventory_adapter_summary_v0_1.json`
2. 生成 `source_layer_capability_audit`：
   - `source_id`
   - `layer_id`
   - `acquisition_status`
   - `crawler_status`
   - `parser_status`
   - `structured_fact_status`
   - `evidence_graph_status`
   - `claim_boundary`
   - `allowed_claim_scopes`
   - `forbidden_claim_scopes`
   - `specialist_slots`
   - `memo_usage`
   - `blocking_reason`
   - `next_action`
3. 对截图所列 L2/L3/L4 典型源补 expected-but-missing rows，不能只审计当前 32 个已有源。

通过条件：

- 每个已配置公开源都有能力行。
- L2/L3/L4 典型源即使未接入，也必须以 `not_registered` 或 `missing_runtime_route` 暴露，而不是消失。
- 报告必须区分 `not_connected`、`crawlable_not_parsed`、`parsed_not_structured`、`structured_not_promoted`、`runtime_ready_context`、`exact_authority_ready`。

## SL1 Evidence Graph 进入策略

目标：正常可信源应能进入 evidence graph，但 claim authority 不放松。

规则：

1. L1 可在 parser / citation / period / unit gate 后进入强事实。
2. L2 默认进入 context/proxy，不证明公司财务或产品销量；若是公司官方披露并通过 parser，可升级为强事实。
3. L3 默认进入 directional proxy / market signal / channel signal，不证明收入、份额、销量或库存。
4. L4 默认只进入 discovery lead 或 exclusion note，不进入核心判断。
5. `commercial_gap` 只在公开可得源和正常可信源都查不到后暴露。

通过条件：

- SourceCapabilityRouter / ToolCapabilityRegistry 能表达 L1-L4 source layer。
- Specialist 输入能看到 L2/L3 context rows，不再因不能提权而直接丢弃。
- Verifier 仍能阻止 L2/L3/L4 被写成强事实。

## SL2 Research Lead Targeted Repair 升级

目标：LeadReviewCheckpoint 不只看 gap checklist，而是对照 SL0 矩阵判断缺口是否 retrievable。

执行：

1. 每个 gap 必须标注：
   - `missing_dimension`
   - `needed_claim_scope`
   - `candidate_source_layers`
   - `retrievability`
   - `repair_route`
   - `expected_claim_boundary`
2. 如果 SL0 显示源可爬/可解析/可结构化，Research Lead 必须先发起 targeted repair。
3. 如果 SL0 显示源未接入或商业源才可得，才暴露 bounded/commercial gap。

通过条件：

- 两个 full-chain case 中，产品/行业/供应链/市场 proxy 缺口不会直接跳到“不能判断”。
- Targeted repair artifact 记录查了哪些源、为什么成功/失败、失败后是什么 gap。

## SL3 Role-Specific Selector 与 Specialist 使用

目标：产品、市场、资本、供应链 specialist 必须拿到对应 source layer 的证据配额。

执行：

1. Product specialist：L1 公司产品指标 + L2 官方产品页/监管/专利 + L3 渠道/开发者/电商 proxy。
2. Market specialist：L1 披露财务 + L2 主流媒体/官方行业数据 + L3 市场/价格/排名 proxy。
3. Industry / supply chain：L1 披露关系 + L2 供应商/客户官方新闻/监管/贸易数据 + L3 公开订单/招标/招聘 proxy。
4. Capital specialist：L1 debt/offering/13F/insider + L2 ownership/regulatory + L3 market reaction proxy。

通过条件：

- role-visible row distribution 中每个激活 specialist 至少暴露 source layer 分布。
- 缺 layer 时写入 selector gap，而不是静默 cap。

## SL4 Memo Writer Analyst-First Surface

目标：报告先写判断，再写依据和边界；缺口要收敛到“什么会改变判断”，不能主导全文。

执行：

1. `MemoLogicPlan` 增加 `bounded_judgments`、`evidence_roles`、`source_layer_mix`、`what_would_change_view`。
2. Writer 禁止正文渲染内部字段，如 `机制：`、`source_family`、`claim_type`。
3. 每个维度必须包含：
   - 当前判断；
   - 支撑证据；
   - 反证或不确定性；
   - 投资含义；
   - 若缺证据，说明缺口对判断的影响，而不是只说不能判断。

通过条件：

- Eval 增加 `insight_density`、`caveat_dominance`、`judgment_first`、`dimension_comparison_depth`。
- 如果报告通篇以“无法判断”为主，即使 factual gate 通过也不能通过 memo-quality gate。

## SL5 验收顺序

1. 先跑 SL0 deterministic audit，不调用 LLM。
2. 再接 SL1/SL2 deterministic contracts 和 targeted repair smoke。
3. 再做 SL3 selector distribution tests。
4. 再做 SL4 memo-quality eval gate。
5. 最后只跑 1-2 个 full-chain case 验收，失败先修 root cause，不连续烧 token。

## 本轮落地状态

本轮已完成的部分：

1. SL0 已落地为 deterministic source-layer audit：
   - `src/sec_agent/source_layer_capability_audit.py`
   - `scripts/data_expansion/audit_source_layer_capabilities.py`
   - `data/manifests/source_layer_capability_audit_v0_1.jsonl`
   - `data/manifests/source_layer_capability_audit_summary_v0_1.json`
   - `docs/internal/vnext_20260610/source_layer_capability_audit.zh-CN.md`
2. SL1 / SL2 已接入 Research Lead：
   - LangGraph state 读取 `source_layer_capability_audit`。
   - `LeadReviewCheckpoint.dimension_reviews[]` 暴露 `candidate_source_layers` 和 `source_layer_repairability`。
   - 产品、行业、资本等维度在存在 `structured_not_promoted` / `staging_parser_gate_pending` / `runtime_ready_context` 源时先标成 `retrievable_gap`，不直接 bounded。
3. SL4 已补 eval 侧质量 gate：
   - 拒绝“通篇缺口说明”的 memo surface。
   - 拒绝正文泄露 `financial_metric:` / `product_kpi:` / `source_family` 等内部字段。
   - 拒绝产品 section 把 cash flow、cost of revenue、investment proceeds 等财务科目当作产品成功证据。
   - 新增 `source_layer_capability` eval gate，检查 L2/L3/L4 是否被审计、是否暴露状态分布、是否没有被提权为 exact authority。
4. SL3 第一段已落地为 role-specific source-layer selector distribution：
   - `role_evidence_selector` 新增 `build_role_source_layer_distribution`。
   - `specialist_llm` 的 shared context、request payload、route summary 和 fanout barrier 均暴露各 specialist 的 L1/L2/L3/L4 候选分布。
   - Eval 新增 `role_source_layer_distribution` gate：允许显式 selector gap，但禁止 L2/L3/L4 exact authority 提权和静默空分布。
5. 官方 web repair context rows 已补 source-layer metadata：
   - `source_layer_id`
   - `parser_status=snapshot_context_parser_pass`
   - `structured_fact_status=context_row_materialized`
   - `evidence_graph_status=runtime_ready_context`
   - `can_support_company_exact_fact=false`
   - 这只表示官方/可信公开源可以进入 context/proxy，不表示产品销量、订单、份额、ASP、库存等 exact facts 已可用。
6. L2/L3 parser/backfill foundation 已落地：
   - 新增 `src/sec_agent/public_web_context_parser.py`，把 allowed public web snapshots 解析成 bounded structured context rows。
   - `official_issuer_repair` fetch 成功后会额外产出 parser-backed rows，字段包括 `source_specific_parser`、`bounded_structured_context`、`structured_context_type`、`structured_context_summary`、`parser_claim_boundary`。
   - 先覆盖官方产品页/产品规格语句、HTML table rows、SEC submissions JSON filing presence、market proxy/supply-chain/capital/issuer 关键词句子。
   - `lead_supervision` / `official_issuer_repair` 的 L3 allowlist 已扩展到 App Store / marketplace、电商、developer ecosystem、公开招投标、招聘、渠道报价、平台评论/排名等 source class，避免进入 repair plan 前被静默挡掉。
   - L3 adapter smoke 已补 URL pattern expansion：GitHub / npm / PyPI / HuggingFace / App Store URL 可派生到公开 JSON API，并解析为 `developer_ecosystem_context` 或 `app_store_marketplace_context` proxy rows；GitHub + App Store live smoke 已通过，且修复了 GitHub JSON `name` 被误识别为 issuer identity 的污染问题。
   - L3 JSON-LD / microdata parser 已补：电商/渠道 offer、CDW reseller tag-data/microdata、JobPosting 招聘、公开 tender/contract、平台 rating/review 可从网页结构化数据进入 `channel_offer_context`、`hiring_signal_context`、`public_tender_contract_context`、`platform_review_ranking_context`；这些仍全部是 L3 bounded proxy/context。
   - Research Lead 的 targeted repair ClaimCard 会携带 `bounded parsed context includes ...`，不再只表达“页面已到达”。
7. L2 trusted news / supplier-customer official news parser smoke 已落地：
   - `mainstream_financial_news_article` 被加入 market proxy repair allowlist，但只有 Reuters / FT / WSJ / NYT / Nikkei / AP / CNBC / MarketWatch / 财新 / 新华等可信主流新闻域名通过 URL gate，其他新闻/博客域名在 fetch 前拦截。
   - `supplier_customer_official_news` 被加入 supply-chain repair allowlist，用于供应商/客户/合作伙伴官方新闻和公告。
   - `public_web_context_parser` 可从 HTML title、meta description / published time 和正文关键句解析 `trusted_news_event_context`、`official_supply_chain_news_context`，作为 L2 context / verification lead 进入 evidence graph。
   - `source_layer_capability_audit` 已同步把 `mainstream_financial_news`、`supplier_customer_official_news` 从 `not_registered` 改为 `runtime_ready_context` + `article_parser_smoke_pass`；后续 developer ecosystem、App Store lookup、ATS hiring、USAspending public award、CDW channel offer / review 接入后 strict audit 当前为 `expected_missing_count=4`、`runtime_ready_count=13`。
   - 这些 rows 明确 `exact_value_authority=false`、`can_support_company_exact_fact=false`，只能支持行业事件、竞争语境、供应链关系或验证线索，不能直接证明 issuer 财务、产品 KPI、销量、份额、订单量、allocation 或 shipment。
8. L2/L3 parser row entity-binding metadata 已落地：
   - 每条 public web parser row 增加 `entity_binding`、`issuer_binding_status`、`product_binding_status`、`counterparty_binding_status`、`source_entity_role` 和 `entity_binding_claim_boundary`。
   - 绑定状态区分 `issuer_mentioned_in_snapshot`、`company_domain_bound`、`repair_plan_ticker_bound_unverified_in_snapshot`、`product_mentioned_in_snapshot`、`relationship_context_candidate` 等，避免 Specialist 把“repair plan 指向某 ticker”误读为“快照已验证 issuer”。
   - 这只是 selector / Specialist 消费 context 的路由诊断，不是完整 entity master，不会提升 exact-value authority。
9. Role-visible selector / Specialist prompt 已接入 entity-binding metadata：
   - `multi_agent_runtime._bounded_row` 保留 `source_class`、`structured_context_type`、`source_entity_role`、issuer/product/counterparty binding status 和 `entity_binding` compact 字段。
   - `bounded_row_distribution` / Specialist `prompt_row_distribution` 增加 source entity role 与三类 binding status 统计，方便 run trace 复盘“专家到底看见了哪些 L2/L3 context”。
   - `industry_supply_chain_analyst` 的 source-family policy、row filter 和激活信号已纳入 `live_public_web_context`，供应商/客户官方新闻和 targeted web repair rows 不再被静默过滤。
   - `role_evidence_selector` 与 Specialist prompt 的 `source_layer_distribution.selected_sources` 保留 source role / binding status，方便专家按角色理解 source-layer rows。
10. Source Coverage Gate 已落地为真实接入前后的覆盖门控：
   - 新增 `src/sec_agent/source_coverage_gate.py`，按行业维护 required source matrix，覆盖 `generic_public_research`、半导体/硬件、消费电子、SaaS、医药/器械、汽车、银行、能源/公用事业、零售/CPG。
   - 新增 `scripts/data_expansion/audit_source_coverage_gate.py`，可在 `registry` 阶段只审计 source capability，也可在 `runtime_case` 阶段审计实际 evidence/context rows、parser rows、entity binding rows 和 specialist-visible rows。
   - 每个 requirement 都写明候选 `source_ids`、`layer_ids`、`specialist_roles`、`claim_boundary`、`next_action` 和 gap type；后续真实 adapter/backfill 完成后，必须让对应 requirement 从 `source_not_registered_or_blocked` / `source_parser_or_mapping_not_runtime_ready` 下降到 runtime case pass，或保留为明确 source gap。
   - 当前 registry gate 结果：`9` 个行业 schema 全部为 `gap`，共 `66` 个 requirement、`13` 个 gap、`0` 个 fail、`0` 个 L2/L3 exact-authority violation。developer ecosystem、App Store lookup、ATS hiring、USAspending public award、CDW channel offer / review 已由 `not_registered` 推进到 `runtime_ready_context`；主要剩余 gap 集中在官方产品页/产品 KPI registry route、NHTSA/ClinicalTrials/openFDA/FDIC/EIA/FRED/OpenAlex/PatentsView entity resolver、Google Play/其他 marketplace、主流新闻/供应商客户官方新闻真实 backfill，以及 Amazon/BestBuy/Walmart 等大型电商平台合规访问/反爬缺口。
   - `software_saas` schema 已补 `public_order_proxy` requirement，因为 PLTR/MSFT/AMZN/ORCL 等软件/云/政府技术公司需要公开政府合同 award 路径；这不会放宽 revenue/backlog/order-volume gate。
   - 这回答了“如何保证真实接入时不会漏”：后续每接一个真实源，都先在 source registry 里注册，再跑 coverage gate 验证行业 required source 是否具备 runtime route、parser-backed row、entity binding 和 specialist visibility；未通过不能被 silently skipped。
11. 官方产品页第一批 runtime backfill 已通过：
   - 新增 `scripts/data_expansion/build_official_product_surface_context_rows.py`，把已物化的 `company_product_pages` 页面转成 parser-backed bounded context rows。
   - 当前真实物化页覆盖 `AAPL` / `NVDA` / `AMD`，生成 `23` 条 rows，类型为 `official_product_taxonomy_context` 和 `product_spec_context`。
   - 新增 `data/manifests/official_product_surface_context_rows_v0_1.jsonl`、`data/manifests/official_product_surface_context_rows_summary_v0_1.json`、`data/manifests/official_product_surface_runtime_coverage_gate_v0_1.json`。
   - `runtime_case` coverage gate 中 `official_product_surface` requirement 已达到 `pass`，且所有 rows 均为 `exact_value_authority=false`、`can_support_company_exact_fact=false`。
   - 这只解决“官方产品页能进入产品 taxonomy/spec context 并被 specialist 看见”，不解决产品收入、销量、份额、ASP、库存、sell-through 或 company-reported product KPI 的 exact parser。
12. 公司披露产品 KPI / operating metric runtime projection 已接入：
   - 新增 `scripts/data_expansion/build_company_reported_product_operating_metric_runtime_rows.py`，把 Z 盘已通过 value / unit / period / product / citation parser gate 的 product KPI facts 投影成 runtime rows。
   - 当前输入 `company_product_kpi_facts_parser_verified_with_quality_operating_repair_v0_1.jsonl` 共 `5,976` 条，全部生成 `company_reported_product_operating_metrics` L1 exact runtime rows，覆盖 `186` 个 ticker。
   - metric family 分布：`product_revenue=5,682`、`production_or_throughput=239`、`unit_sales_or_deliveries=47`、`backlog_or_orders=6`、`subscribers_or_arpu=2`。
   - repair 分布：`baseline_parser_verified=5,922`、`monotonic_repair_promoted=45`、`operating_metric_repair_promoted=9`。
   - 新增 `data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl`、`data/manifests/company_reported_product_operating_metric_runtime_summary_v0_1.json`、`data/manifests/company_reported_product_operating_metric_runtime_coverage_gate_v0_1.json`。
   - `runtime_case` coverage gate 中 `primary_company_disclosure` 和 `official_product_surface` 均达到 `pass`，且 claim boundary 限定在公司已披露产品/segment、metric、period、unit、value 和 citation span 内。
   - 这不解决剩余未验证公司：旧 product evidence graph 仍有 `417` 家 `company_disclosed_product_kpi_not_verified` gap；也不解决市场份额、渠道库存、sell-through、ASP、app revenue、POS 或 consensus / tracker 缺口。
13. 官方 API normalized snapshot context projector 已接入：
   - 新增 `scripts/data_expansion/build_public_official_api_context_rows.py`，把 `public_source_normalized_materialized_v0_3/normalized_records.jsonl` 中的真实 normalized records 投影成 bounded runtime context rows。
   - 当前覆盖 `10` 个官方源：`clinicaltrials_api`、`openfda_api`、`cms_public_data`、`nhtsa_vpic_api`、`fdic_bankfind_api`、`eia_open_data`、`fred_api`、`fred_graph_csv`、`openalex_api`、`patentsview_api`。
   - 生成 `150` 条 parser-backed rows：宏观/FRED `62`、CMS `50`、EIA `9`、NHTSA `8`、ClinicalTrials `5`、openFDA `5`、FDIC `5`、OpenAlex `5`、PatentsView `1`。
   - Coverage smoke 结果：`macro_official_context=pass`、`auto_product_identity_context=pass`、`regulated_product_context=pass`；`financial_regulatory_context=gap`、`energy_utility_context=gap`、`technology_research_proxy=gap`，后 3 个主要卡在 issuer/product/asset/topic resolver。
   - 修正 `source_coverage_gate` 的 entity-binding gate：当 requirement 声明 `issuer+product` 或 `issuer+counterparty` 时必须全部强绑定，不能只靠单边 product 或 issuer 误通过。
   - 修正官方 API issuer resolver：禁止单字母 ticker 等短 alias 参与 substring fuzzy match，避免 `A` 被误绑定到 FDIC/CMS/ClinicalTrials 等无关 rows。
   - 这些 rows 全部是 context/proxy，不支持公司 revenue、market share、sales volume、approval success、commercial uptake 或 durable moat 结论。
14. SLR0 Runtime Source Context Store 已接入：
   - 新增 `src/sec_agent/runtime_source_context_store.py`，统一读取 L1 product KPI、官方产品页 context、官方 API context manifest，按 ticker scope / source budget 去重和选择。
   - L1 `company_product_evidence_graph` rows 进入 `product_evidence_rows`；L2/L3 `public_source_context` / `live_public_web_context` rows 进入 `public_source_context_rows`；不复制到 `context_rows`，避免 evidence fusion 双计数。
   - LangGraph 第一轮 `execute_evidence_operators` 已修复 `product_evidence_rows` / `public_source_context_rows` 合并断点；此前这两类 rows 主要只在 second pass 合并。
   - `runtime_source_context_store` 已进入 graph state / checkpoint keys，Research Lead、Specialist data view、evidence fusion 后续可审计其 summary。
   - 该接入仍是 runtime-state / manifest-backed store，不等于 D-series SQL persistent graph / DB reader 已完成。
15. SLR1 官方 API resolver 第一批已落地为强规则和诊断 gate：
   - `scripts/data_expansion/build_public_official_api_context_rows.py` 新增 `resolve_source_binding`，按 source-specific 字段解析 FDIC、EIA、NHTSA、ClinicalTrials/openFDA/CMS、OpenAlex/PatentsView 的 issuer / product / topic binding。
   - 每条官方 API context row 新增 `source_specific_resolver`、`resolver_status`、`resolver_reason`、`source_entity_role`，并把 matched terms 写入 `entity_binding`，便于后续 Research Lead targeted repair 判断“是源没覆盖，还是 resolver 没映射”。
   - `resolver_status` 区分 `issuer_product_bound`、`issuer_bound`、`driver_only`、`topic_only`、`product_bound_issuer_unresolved`、`unresolved`；`technology_topic_bound` 只作为技术 proxy 的 product/topic binding，不具备 exact-value authority。
   - Fixture gate 已覆盖：FDIC holding-company / bank-name -> JPM，EIA utility -> XEL，OpenAlex institution + topic -> NVDA；同时覆盖 FDIC 短 alias 不误绑、EIA generic driver-only 不通过、OpenAlex topic-only 不通过。
   - 真实当前 normalized snapshot 重建后仍保持 `financial_regulatory_context=gap`、`energy_utility_context=gap`、`technology_research_proxy=gap`，原因是当前样本本身缺少强绑定字段：FDIC 是 5 个地方银行样本，EIA 是区域 cooling degree-days，OpenAlex 是 topic search 论文，PatentsView 只有 USPTO 迁移 metadata。
   - 最新 `public_official_api_context_summary_v0_1.json`：`150` rows，`issuer_product_bound=10`、`macro_driver_only=62`、`product_bound_issuer_unresolved=58`、`driver_only=9`、`topic_only=6`、`unresolved=5`；`0` 个 L2/L3 exact-authority violation。
16. SLR2 官方产品页扩容第一批已落地：
   - 新增 `scripts/data_expansion/materialize_official_product_surface_pages.py`，从 `official_issuer_repair.ISSUER_PROFILES` 的官方产品页 URL 抓取并物化到 Z 盘 `company_product_pages.materialized.jsonl`，保留 raw HTML、clean text、status、title、fetch attempt summary。
   - materializer 加入官方域名 allowlist、短正文 gate、blocked / access denied / captcha 等 unusable-response gate 和 `--prune-unusable-existing`，避免把被拦截页面或空 shell 页面当作产品页证据。
   - `official_issuer_repair` 新增一批官方产品页 profile：MSFT、AMZN、GOOGL、TSLA、LLY、PFE、CRM、NOW、AVGO、INTC、QCOM；其中 live materialization 成功的有效页覆盖 AMZN、CRM、GOOGL、MSFT、PFE，并和已有 AAPL/NVDA/AMD/ASML/TSM/NVO 合并。
   - 当前有效物化结果：`14` 页、`11` 个 ticker：AAPL、AMD、AMZN、ASML、CRM、GOOGL、MSFT、NVDA、NVO、PFE、TSM。
   - 当前失败 / 拒绝路径：AVGO 页面过短、QCOM 页面过短、MSFT Microsoft 365 返回 blocked page、INTC/TSLA 为 403、LLY 为 403/404、NOW 读取超时；这些保留在 materialization summary，后续需要换官方 URL、API/站点适配或暴露为 source gap。
   - 重建 `official_product_surface_context_rows_v0_1.jsonl` 后，官方产品页 runtime rows 从 `23` 增至 `96`，覆盖 `11` 个 ticker；`official_product_surface` runtime coverage gate 仍为 `pass`，`entity_bound_row_count=57`，且所有 rows 仍为 bounded context，不具备销量、份额、ASP、库存或 sell-through authority。
17. SLR3a developer ecosystem 第一批真实 backfill 已落地：
   - 新增 `scripts/data_expansion/build_developer_ecosystem_context_rows.py`，把 GitHub / npm / PyPI / HuggingFace 的公开页面 URL 派生到官方公开 JSON API，下载 raw JSON 到 Z 盘，并通过 `public_web_context_parser` 解析为 bounded L3 context rows。
   - 当前真实物化 `10/10` 个 API probe，覆盖 `5` 个 ticker：AMZN、CRM、GOOGL、MSFT、NVDA；生成 `13` 条 parser-backed rows，其中 GitHub `5`、npm `4`、PyPI `3`、HuggingFace `1`。
   - `developer_ecosystem_runtime_coverage_gate_v0_1.json` 中 `developer_ecosystem_proxy=pass`，`observed_row_count=13`、`parser_row_count=13`、`entity_bound_row_count=13`、`specialist_visible_row_count=26`，且 source registry 已更新为 `runtime_ready_context`。
   - `RuntimeSourceContextStore` 默认路径已加入 `developer_ecosystem_context_rows_v0_1.jsonl`；同时修复了 public-source budget 下只选官方产品页、挤掉 developer rows 的 source-diversity bug，当前 smoke 能在 MSFT/AMZN/GOOGL/NVDA/CRM scope 下选中 developer ecosystem rows。
   - materializer 增加 fetch retry，用于处理 npm registry 等公开 API 的 transient `IncompleteRead`；连续失败仍会写入真实 `fetch_failed` attempt，不用旧缓存兜底。
   - 这些 rows 全部是 L3 developer activity / package / model attention proxy，只能帮助产品/技术与生态热度方向性判断，不能证明公司收入、市占率、销量、客户采用、订单或 durable moat。
18. SLR3b App Store marketplace lookup 第一批真实 backfill 已落地：
   - 新增 `scripts/data_expansion/build_app_marketplace_context_rows.py`，把 Apple App Store URL 派生到 iTunes Lookup API，下载 raw JSON 到 Z 盘，并解析为 `app_store_marketplace_context` rows。
   - 当前真实物化 `11/11` 个 App Store lookup probe，覆盖 `5` 个 ticker：AAPL、GOOGL、META、MSFT、NFLX；生成 `11` 条 parser-backed rows，全部为 `app_store_marketplace_context`。
   - `app_marketplace_runtime_coverage_gate_v0_1.json` 中 `app_rank_store_proxy=pass`，`observed_row_count=11`、`parser_row_count=11`、`entity_bound_row_count=11`、`specialist_visible_row_count=22`。
   - `RuntimeSourceContextStore` 默认路径已加入 `app_marketplace_context_rows_v0_1.jsonl`；当前 smoke 在 AAPL/GOOGL/META/MSFT/NFLX scope 下能选中 `7` 条 App Store rows，且 `public_exact_authority_violation_count=0`。
   - 为避免 JSON lookup 被 generic sentence parser 放大成噪声，materializer 默认每个 app 只保留 `1` 条结构化 lookup row；这不是降低覆盖，而是控制 L3 proxy 输入质量。
   - Google Play 暂未接入一方公开 lookup API，不能把 Apple App Store coverage 冒充成完整 app marketplace coverage；继续暴露为后续 source gap。
   - 这些 rows 只支持 app listing、rating count、rating、version、release recency 等方向性 marketplace proxy，不能证明下载量、收入、市场份额、销售、客户采用或 moat。
19. SLR3c hiring / capacity 第一批真实 backfill 已落地：
   - 新增 `scripts/data_expansion/build_hiring_capacity_context_rows.py`，从 Greenhouse / Lever 官方公开 ATS API 拉取职位 JSON，保存 raw JSON 到 Z 盘，并转换成标准 `JobPosting` JSON-LD 交给 `public_web_context_parser`。
   - 当前真实物化 `9/9` 个 company ATS probe，覆盖 `9` 个 ticker：ABNB、ASAN、COIN、DASH、DDOG、LYFT、NET、PLTR、RBLX；生成 `45` 条 parser-backed `hiring_signal_context` rows。
   - `hiring_capacity_runtime_coverage_gate_v0_1.json` 中 `hiring_capacity_proxy=pass`，`observed_row_count=45`、`parser_row_count=45`、`entity_bound_row_count=45`、`specialist_visible_row_count=135`。
   - `RuntimeSourceContextStore` 默认路径已加入 `hiring_capacity_context_rows_v0_1.jsonl`；当前 smoke 在 9 个 ticker scope 下能选中 `45` 条 hiring rows，且 `public_exact_authority_violation_count=0`。
   - 这些 rows 只支持 hiring / role focus / geography / capacity direction proxy，不能证明 headcount、真实需求、订单、收入、产能投放结果或利润率。
20. SLR3d public contract / order 第一批真实 backfill 已落地：
   - 新增 `scripts/data_expansion/build_public_contract_award_context_rows.py`，用 USAspending `spending_by_award` 公开 API 查询 contract award type `A/B/C/D`，保存 raw JSON 到 Z 盘，并转换成 public tender / contract JSON-LD rows。
   - 当前真实物化 `6/6` 个 issuer probe，覆盖 `6` 个 ticker：AMZN、IBM、LDOS、MSFT、ORCL、PLTR；生成 `18` 条 parser-backed `public_tender_contract_context` rows。
   - `public_contract_award_runtime_coverage_gate_v0_1.json` 中 `public_order_proxy=pass`，`observed_row_count=18`、`parser_row_count=18`、`entity_bound_row_count=18`、`specialist_visible_row_count=54`，且 `counterparty_mentioned_in_snapshot=18`。
   - `RuntimeSourceContextStore` 默认路径已加入 `public_contract_award_context_rows_v0_1.jsonl`；当前 smoke 在 PLTR/MSFT/AMZN/ORCL/IBM/LDOS scope 下能选中 `14` 条 public contract rows，且 `public_exact_authority_violation_count=0`。
   - 这些 rows 只支持单条公开 award / agency relationship existence proxy，不能外推为公司总订单、backlog、收入、销售、需求或市占率。
21. SLR3e channel offer / platform review 第一批真实 backfill 已落地：
   - 新增 `scripts/data_expansion/build_channel_offer_context_rows.py`，从 CDW 公开搜索页发现产品 URL，抓取公开产品页 raw HTML 到 Z 盘，并通过 `public_web_context_parser` 解析 CDW tag-data / schema.org microdata。
   - `public_web_context_parser` 新增 commerce microdata 分支，能从 `window.cdwTagManagementData`、`itemprop=offers`、`price`、`priceCurrency`、`availability`、`total_review_count`、`average_overall_rating` 生成 bounded L3 rows。
   - 当前真实物化覆盖 `6` 个 ticker：AAPL、DELL、HPQ、LNVGY、MSFT、NVDA；生成 `12` 条 parser-backed rows，其中 `channel_offer_context=11`、`platform_review_ranking_context=1`。
   - `channel_offer_runtime_coverage_gate_v0_1.json` 中 `channel_offer_proxy=pass`，`observed_row_count=11`、`parser_row_count=11`、`entity_bound_row_count=11`、`specialist_visible_row_count=22`；`platform_review_proxy=pass`，`observed_row_count=1`、`entity_bound_row_count=1`、`specialist_visible_row_count=3`。
   - `RuntimeSourceContextStore` 默认路径已加入 `channel_offer_context_rows_v0_1.jsonl`；source registry 已把 `channel_pricing_quotations` 和 `platform_reviews_rankings_downloads` 推进到 `runtime_ready_context`。
   - product resolver 明确 fail-closed：DELL 搜索里 Kingston / Axiom / Total Micro 这类第三方兼容件会被标成 `skipped_product_mismatch`，不会因为标题含 Dell/PowerEdge 就绑定成 DELL 产品。
   - Amazon / BestBuy / Walmart / B&H / Newegg 等大型消费电商在 smoke 中出现 robot、403 或超时，暂不冒充已接入；这类继续暴露为合规访问/反爬 source gap。
   - 这些 rows 只支持产品 listing、SKU/配置、公开渠道报价、availability / lead-time 和 review/rating proxy，不能证明 ASP、sell-through、渠道库存、销量、收入、市占率、真实需求或 durable moat。

当前仍未完成、不能冒充已完成的部分：

1. L2/L3 的 source-specific live adapters / resolvers 还没有全量补齐；官方产品页已从 AAPL/NVDA/AMD 扩到 `11` 个 ticker / `96` 条 runtime rows，公司披露产品 KPI 已有 `5,976` 条 verified L1 runtime rows，官方 API normalized snapshot 已有 `150` 条 bounded context rows，GitHub/npm/PyPI/HuggingFace 已有 `13` 条真实 runtime rows，Apple App Store lookup 已有 `11` 条真实 runtime rows，ATS hiring 已有 `45` 条真实 runtime rows，USAspending public award 已有 `18` 条真实 runtime rows，CDW channel/review 已有 `12` 条真实 runtime rows；主流新闻和供应商/客户官方新闻只有 parser smoke，Google Play/其他 marketplace、Amazon/BestBuy/Walmart 等大型电商、真实站点覆盖、实体匹配、页面变体处理、反爬/访问策略和大规模 backfill 仍未完成。
2. 当前 public-web parser 是 bounded context/proxy foundation，不是产品销量、订单、份额、ASP、库存、sell-through 或 commercial tracker 替代品；公司披露 product KPI 只在 `company_reported_product_operating_metrics` exact runtime rows 内成立。
3. Specialist selector 已能暴露 L1/L2/L3/L4 分布，且 L1 product KPI / 官方产品页 / 官方 API / developer ecosystem / App Store lookup / ATS hiring / USAspending award manifest rows 已可通过 `RuntimeSourceContextStore` 接入 graph runtime；这些 rows 已能按 ticker scope 被 runtime store 选中；但还没有把大规模历史 L2/L3 parser/backfill rows 写入持久 runtime evidence graph / SQL DB reader 默认路径。
4. 官方 API rows 的 resolver 强规则已落地，但真实当前 snapshot 仍有数据覆盖缺口：FDIC 当前样本没有 listed bank holding company，EIA 当前样本没有 utility/operator/asset issuer 字段，OpenAlex 当前样本没有 issuer/institution 映射，PatentsView 当前只有 USPTO 迁移页；因此这些 requirement 仍不能冒充已解决，需要下一步 live/backfill 获取可绑定行。
5. Source Coverage Gate 当前只证明“缺口可被机器审计并定位到 requirement”，不证明所有真实站点、所有行业页面变体和实体 resolver 已覆盖。
6. 本轮只跑 deterministic tests、source audit、coverage gate、fixture web repair smoke 和 SLR0 graph/runtime-store 单测，没有烧 DeepSeek 跑新的 full-chain case。

## 下一步执行规划（SLR0-SLR5）

### SLR0 Runtime Evidence Graph / DB Reader 接入

目标：把已经生成的 L1/L2 bounded rows 从 manifest smoke 升级为 runtime 默认可消费输入，避免 Research Lead / Specialist 只能看见旧 SEC context。

执行：

1. 新增 `RuntimeSourceContextStore`，统一读取并去重：
   - `company_reported_product_operating_metric_runtime_rows_v0_1.jsonl`
   - `official_product_surface_context_rows_v0_1.jsonl`
   - `public_official_api_context_rows_v0_1.jsonl`
2. 按 `focus_tickers` / `search_scope_tickers`、`source_family`、`source_layer_id`、`source_id` 做预算选择：
   - L1 product KPI rows 进入 `product_evidence_rows`；
   - L2/L3 官方产品页、官方 API、public proxy rows 进入 `public_source_context_rows`；
   - 不把 L2/L3 rows 同时复制到 `context_rows`，避免 evidence fusion 双计数。
3. 对无 issuer 绑定的宏观/官方序列只保留 source/metric 最新少量 rows，不允许 FRED/EIA 历史全量进入 prompt。
4. LangGraph 第一轮 `execute_evidence_operators` 必须合并 `product_evidence_rows` 和 `public_source_context_rows`，不能只在 second pass 合并。
5. CLI / workbench 可通过显式开关或 state config 启用默认路径；如果路径缺失，写入 runtime source gap，不走 mock fallback。

通过条件：

- loader deterministic test 能在本地默认 manifest 上选出 AAPL/NVDA 等 ticker 的 L1 product KPI、L2 official product surface 和 public official API context。
- graph merge test 证明第一轮 operator result 的 `product_evidence_rows/public_source_context_rows` 会进入 state、evidence fusion、specialist data view。
- `public_source_context` / `live_public_web_context` rows 在 bounded row 中仍为 `exact_value_authority=false`。
- source coverage gate 仍保持 `0` 个 L2/L3 exact-authority violation。

### SLR1 Resolver Repair 第一批

目标：修复当前官方 API rows 里最影响行业判断的实体绑定缺口。

执行顺序：

1. FDIC：bank institution / certificate / RSSD / legal name -> listed issuer / bank holding company。
2. EIA：series / plant / balancing authority / utility territory -> issuer、region、commodity driver。
3. NHTSA：vPIC / recalls / complaints -> ticker、make、model、model year。
4. ClinicalTrials / openFDA / CMS：sponsor、drug/device、condition、procedure -> ticker / product / indication。
5. OpenAlex / PatentsView：assignee / institution / concept -> issuer / product / technology topic。

通过条件：

- 每个 resolver 都有 fixture + real normalized rows smoke。
- resolver 输出必须区分 `issuer_bound`、`product_bound`、`topic_only`、`unresolved`。
- `issuer+product` requirement 仍必须双边强绑定才算 pass。

### SLR2 Official Product Surface 扩容

目标：把官方产品页从 AAPL/NVDA/AMD 第一批扩到重点行业代表公司，优先解决产品 section 空白。

执行：

1. 从 product evidence graph、SEC product taxonomy、company IR URL 中生成 official product URL candidate。
2. 先跑半导体/硬件、消费电子、SaaS、医药/器械、汽车各 5-10 家。
3. 每家公司输出 product taxonomy、model/spec、generation edge、official availability/pricing context。
4. 失败时写明 `robots/auth/paywall/no_product_surface/parser_variant/entity_unresolved`，不直接 bounded gap。

通过条件：

- 每个行业至少有一组官方产品页 rows 通过 parser + entity binding。
- Product specialist data view 能看到 product/spec rows，并且不能把它们写成 sales/share facts。

### SLR3 L3 Public Proxy Backfill 第一批

目标：让可信补充层和市场 proxy 层不再只是骨架，至少形成可测试的真实数据源接入。

执行顺序：

1. developer ecosystem：GitHub / npm / PyPI / HuggingFace。第一批已完成真实 API backfill，覆盖 AMZN/CRM/GOOGL/MSFT/NVDA 的 13 条 L3 rows，并接入 runtime source store；后续扩展重点是 issuer/project resolver coverage、refresh cadence 和更多行业项目映射。
2. app / marketplace：App Store / Marketplace ranking or listing metadata。第一批已完成 Apple App Store/iTunes Lookup backfill，覆盖 AAPL/GOOGL/META/MSFT/NFLX 的 11 条 L3 rows，并接入 runtime source store；后续重点是 Google Play/其他 marketplace policy、rank snapshot、app-to-issuer resolver 和避免 download/revenue 误提权。
3. hiring / capacity：company career pages + major job boards 的公开职位结构化信息。第一批已完成 Greenhouse / Lever 官方 ATS API backfill，覆盖 ABNB/ASAN/COIN/DASH/DDOG/LYFT/NET/PLTR/RBLX 的 45 条 L3 rows，并接入 runtime source store；后续重点是 ATS resolver coverage、role taxonomy normalization、refresh cadence 和不把招聘 proxy 写成 headcount/demand。
4. tender / public orders：公开招投标、政府采购、award portals。第一批已完成 USAspending contract award backfill，覆盖 AMZN/IBM/LDOS/MSFT/ORCL/PLTR 的 18 条 L3 rows，并接入 runtime source store；后续重点是非美/地方/行业采购门户、buyer/supplier/product resolver 和不把单条 award 外推成总订单或 backlog。
5. ecommerce / channel / review：第一批已完成 CDW public reseller channel/review backfill，覆盖 AAPL/DELL/HPQ/LNVGY/MSFT/NVDA 的 12 条 L3 rows，并接入 runtime source store；后续重点是 Amazon / JD / Taobao / Tmall / BestBuy / Walmart / B&H / Newegg 等大型平台的合规访问、页面变体 parser、review/ranking snapshot 和不把渠道报价/评论 proxy 误提权为 ASP、sell-through、库存、销量或份额。

通过条件：

- 每类至少 5-10 个真实 URL smoke，不只跑 fixture。
- parser 产出 bounded structured rows，且每类都有 claim boundary。
- source coverage gate 能把对应 requirement 从 `source_parser_or_mapping_not_runtime_ready` 推进到 runtime observed 或明确 resolver gap。

### SLR4 Research Lead Targeted Repair 接入

目标：Research Lead 不再只分派任务，而是读取 source coverage / runtime source store / Specialist 输出，主动追问“理论上能找到但没找到”的缺口。

执行：

1. LeadReviewCheckpoint 读取 SLR0 rows summary、source coverage gate 和 Specialist row distribution。
2. 对 `retrievable_gap` 生成 targeted repair plan：指定 DB/artifact route、resolver、web source scope、预期 claim type、提权条件。
3. 对 `bounded_gap` / `commercial_gap` 直接登记边界，不让 writer 把缺口扩写成全文。
4. target repair 成功后补入 evidence rows 并重新跑 selector / Specialist 单节点，不直接重跑 full-chain。

通过条件：

- 1-2 个 case 中 Research Lead 能把缺产品/行业/资本 evidence 的原因分成 retrievable / bounded / commercial。
- repair 成功时新增 row 可被 Specialist 看见；失败时 gap ledger 有 source boundary。

### SLR5 Memo / Eval 回归

目标：在 deterministic 接入稳定后再跑少量 full-chain，避免边修边烧 token。

执行：

1. 先跑 loader、resolver、parser、coverage、selector deterministic gates。
2. 再跑 memo-quality eval：`insight_density`、`judgment_first`、`caveat_dominance`、`dimension_comparison_depth`、`evidence_role_consistency`。
3. 只跑 1-2 个全链路 case；失败先定位 node / retrieval / parser / writer root cause。
4. 通过后再讨论扩到 12-case successor 和 50-case catalog。

通过条件：

- memo 不能以“无法判断”主导全文。
- 产品、财务、行业、供应链、资本至少按问题意图形成维度化判断。
- 缺口只进入“什么会改变判断/还需商业数据”部分，不能替代判断本身。

## 禁止事项

- 不用低质量信源凑结论。
- 不把 L2/L3 proxy 提权成公司强事实。
- 不因为 parser 没做就直接把所有公开源写成 bounded gap。
- 不让 Memo Writer 自己联网、查 DB、生成新事实。
- 不把 full-chain case 当调 prompt 的主要手段；必须先用 deterministic audit 定位问题。
