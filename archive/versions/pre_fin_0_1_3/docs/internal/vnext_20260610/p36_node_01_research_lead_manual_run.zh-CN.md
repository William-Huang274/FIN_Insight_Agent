# P36 Node 01 Research Lead Manual Run

日期：2026-07-09

## 节点定位

节点：`node_01_research_lead`

目标：按现有 Research Lead 约束产出 thesis path、required items、source-route plan、specialist assignments、missing-but-retrievable list、bounded gaps 和 writer order。Research Lead 不执行检索，不写最终 memo，不做最终投资结论。

## 已读取的 runtime / prompt / skill

- `src/sec_agent/prompts/skills/research_lead_planning_skill_v0_1.md`
- `src/sec_agent/prompts/skills/evidence_requirement_and_sufficiency_skill_v0_1.md`
- `src/sec_agent/prompts/skills/fundamental_analysis_skill_v0_2.md`
- `src/sec_agent/prompts/skills/industry_supply_chain_analysis_skill_v0_2.md`
- `src/sec_agent/prompts/skills/market_valuation_analysis_skill_v0_2.md`
- `docs/project_os/p35_ai_infra_decision_surface_framework_v0_1.json`
- `docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json`

## 节点允许与禁止

允许：

- 分类任务类型。
- 生成 thesis path。
- 定义 required items。
- 规划 source families / evidence routes。
- 分配 specialists。
- 标记 missing-but-retrievable 与 bounded/commercial gaps。
- 设定 writer order。

禁止：

- 不执行实际检索。
- 不调用 web 或补源。
- 不给最终投资结论。
- 不让 Memo Writer 或 Verifier 拥有检索权限。
- 不把 market / industry / relationship context 当成 company-reported facts。

## 输入快照

用户题面要求 5 条产业链：

- Accelerator: NVDA / AMD / custom silicon
- Server OEM: Dell / SMCI / HPE
- Foundry / Packaging: TSMC / CoWoS / advanced packaging
- HBM: SK hynix / Samsung / Micron
- Semicap: ASML / AMAT / LRCX / KLAC

P35 已定义 12 个决策维度：

- demand proof
- capture mechanism
- revenue evidence
- profit quality
- bottleneck monetization
- margin dilution
- capex digestion
- export control
- price-in
- counter-thesis
- source grade
- numeric sanity

P35 gap audit 显示当前 P34 runtime rows 的主要缺口：

- HBM producers 不是一等 segment rows。
- SMCI / HPE 不是一等 server OEM peer rows。
- CoWoS capacity / pricing / customer allocation 没有 exact rows。
- Semicap 缺完整 ASML / AMAT / LRCX / KLAC peer panel。
- Price-in 仍是 bounded fixture / context，未接完整 market / holder / valuation pack。

## Codex-as-paid-model Research Lead 输出

### Task Classification

`deep_research`

理由：用户问题要求跨产业链、跨公司、跨 source grade、跨财务/经营/资本市场证据判断，不是 deterministic lookup 或 focused answer。

### Initial View

本 case 的 Research Lead 初始视角不是“AI demand 是否存在”，而是“AI demand 的 value capture 在不同链条中质量不同”。

需要检验的主路径：

1. HBM / TSMC advanced node-packaging / NVDA accelerator 是否已经把 AI demand 转成高质量收入和利润。
2. Server OEM 是否只是 demand proxy，或 Dell / HPE 是否已经出现比 SMCI 更高质量的捕获机制。
3. Semicap 是否是高质量但滞后的 capex read-through，而非实时需求温度计。
4. Hyperscaler capex digestion、export control、supply bottleneck、margin dilution 和 price-in 是否改变上述排序。

Research Lead 不把这写成最终结论，只把它作为后续 specialists 和 source route 的 thesis path。

### Required Items

| Required item | 目的 | 主要 segments | 需要的 source / routes | Owner |
| --- | --- | --- | --- | --- |
| `req_decision_surface_cells` | 生成 5 x 12 decision cells，不让报告退化为证据摘要 | all | P35 framework, runtime rows, supplement ledger, specialist outputs | Research Lead / Aggregate |
| `req_hyperscaler_capex_pool` | 证明需求池和 capex digestion 风险 | accelerator, foundry, server OEM, semicap | company official filings/earnings, capex/FCF rows, market/industry context | Fundamental + Industry + Market |
| `req_accelerator_revenue_profit` | 验证 accelerator 收入和利润质量 | accelerator | NVDA / AMD official financials, segment rows, gross margin, China/export assumptions | Fundamental |
| `req_server_oem_peer_panel` | 区分 Dell / SMCI / HPE revenue quality、margin dilution、cash conversion | server OEM | official earnings, orders/backlog, gross margin, OCF/FCF, inventory/working capital | Fundamental |
| `req_tsmc_foundry_packaging_bridge` | 连接 advanced node / HPC / CoWoS 与利润质量 | foundry_packaging | TSMC official financials, HPC mix, advanced-node mix, CoWoS estimates separately graded | Fundamental + Industry |
| `req_hbm_peer_panel` | 把 SK hynix / Samsung / Micron 纳入一等分析 | HBM | non-US official IR / press / presentation, HBM product-cycle evidence, margins | Fundamental + Product |
| `req_semicap_peer_panel` | 判断 semicap 是 real demand 还是 lagged read-through | semicap | ASML / AMAT / LRCX / KLAC official revenue, margin, bookings/backlog, China exposure | Fundamental + Industry |
| `req_export_control_cross_risk` | 对 NVDA / AMD / semicap / China exposure 建风险矩阵 | accelerator, semicap, HBM | BIS/Federal Register, company China assumptions, risk factors | Risk |
| `req_price_in_capital_market` | 回答“好业务是否还有赔率” | all | market snapshot, valuation, 13F/ownership, event reaction, revision context | Market |
| `req_counter_thesis` | 防止单边 AI supercycle 叙事 | all | capex ROI, customer digestion, supply expansion, substitution, export, margin compression | Risk + Aggregate |
| `req_source_grade_numeric_sanity` | 每个 cell 都标注 source grade 和 numeric sanity | all | parser lineage, source supplement ledger, typed gaps | Source Quality / Aggregate |
| `req_writer_decision_surface_first` | writer 先写 decision surface，再写正文和边界 | all | aggregate decision cells, fact tables, gaps | Writer |

### Evidence Role Plan

| Evidence role | 计划用途 | 优先级 |
| --- | --- | --- |
| official issuer financials | revenue, margin, orders, backlog, cash flow, capex | highest |
| official non-US issuer disclosure | HBM / TSMC / Samsung / SK hynix 等非 SEC 主披露 | highest |
| government / regulatory source | export control 和政策约束 | highest |
| market / valuation snapshot | price-in、估值、事件反应、持仓拥挤 | high |
| relationship / graph context | customer-supplier / bottleneck / pass-through / lag 机制 | medium-high |
| secondary estimates | CoWoS capacity/ASP/customer allocation 等官方不披露项 | medium, must label |
| public context / industry snapshot | 只做背景和机制，不可证明公司财务事实 | bounded |

### Specialist Assignment

| Specialist | Assignment | 必须回答 |
| --- | --- | --- |
| Fundamental Analyst | 五链条 peer financial panel | revenue evidence、profit quality、margin dilution、cash conversion、capex intensity |
| Industry / Product / Supply Chain Analyst | value-chain transmission and bottleneck rent | capture mechanism、bottleneck monetization、real demand vs proxy vs lag |
| Market / Valuation Analyst | price-in and capital market feedback | valuation/ownership/event reaction/market skepticism/positioning gaps |
| Risk / Counterevidence Analyst | downside and falsifiers | capex digestion、export control、substitution、supply expansion、what-would-change |
| Source Quality / Numeric Sanity Reviewer | claim/source discipline | official vs estimate vs inference、numeric sanity、typed gaps |
| Aggregate / Judgment Planner | segment ranking and writer-ready plan | conflict resolution、evidence strength ranking、decision surface completeness |

### Missing But Retrievable

这些不应直接写成“公开源没有”，而应进入 source hunter / retrieval / parser repair：

- SK hynix / Samsung / Micron HBM revenue/margin/product-cycle rows。
- SMCI / HPE official orders/backlog/margin/cash-flow rows。
- TSMC CoWoS / advanced packaging official-adjacent rows and secondary estimates with source grade。
- ASML / AMAT / LRCX / KLAC bookings/backlog / China exposure / WFE peer table。
- NVDA / AMD export-control assumptions and China exposure rows。
- 13F / ownership / valuation / market reaction / options or short-interest context for price-in cells。

### Bounded Or Commercial Gaps

这些可以支持结论，但必须标注估算或商业边界：

- exact CoWoS ASP / capacity / utilization / customer allocation。
- exact HBM customer contract pricing。
- real-time fund flow、borrow、dealer gamma、live option positioning。
- sell-side consensus revision detail if no free/local source exists。
- company-specific AI server GPU BOM margin bridge if issuer does not disclose exact mix.

### Writer Order

1. TL;DR one paragraph.
2. Evidence quality / decision surface matrix.
3. Segment ranking and real demand vs proxy vs lagged read-through.
4. Five segment deep dive.
5. Risk matrix: margin dilution, bottleneck, capex digestion, export, price-in.
6. Capital-market / price-in table.
7. Source-grade / numeric-sanity appendix.
8. Typed gaps and what would change.

## 节点评价

### Research Quality Ruler

| 维度 | 评分 | 说明 |
| --- | --- | --- |
| question_answerability | pass | Research Lead 能把问题转成五链条和价值捕获判断。 |
| decision_surface_completeness | pass | P35 framework 让 Research Lead 可以规划 60 cells。 |
| financial_and_operating_depth | partial | 能规划财务/经营指标，但还没实际取数。 |
| capital_market_price_in_depth | partial | 能识别 price-in 需求，但当前 runtime 未接足 market/ownership/valuation pack。 |
| source_grade_and_lineage | pass | 已要求 source grade / numeric sanity / typed gaps。 |
| counter_thesis_and_turning_signals | pass | 已规划 counter-thesis 和 what-would-change。 |
| writer_readiness | partial | 有 writer order，但必须等下游 evidence/specialists 补齐。 |

### Agent Product Engineering Ruler

| 维度 | 评分 | 说明 |
| --- | --- | --- |
| input_contract_quality | partial | P35 framework 很强，但不是现有 Research Lead runtime 原生输入；P34 rows 对当前题面仍不完整。 |
| output_contract_quality | partial | 本手工输出结构化，但现有 Research Lead prompt 尚未强制输出 P35 60-cell contract。 |
| tool_affordance_fit | pass_for_planning | Research Lead 禁止检索是合理的；但必须把 source hunter 作为后续显式节点。 |
| observability | pass | 本节点可记录 required items、routes、gaps 和 assignments。 |
| recoverability | pass | 缺口能转给 source hunter / parser / specialist，而不是重跑全链。 |
| information_economy | pass | 输出是任务分解和优先级，不是证据 dump。 |
| marginal_contribution | pass | 真正决定后续节点目标，不应删除。 |
| human_review_surface | partial | required items 可 review，但还缺 cell-level Workbench schema。 |
| product_value_over_single_agent | partial | 如果 P35 decision surface 进入 runtime，则有明显价值；当前还只是手工注入。 |

## 节点 root-cause notes

1. Research Lead 节点本身方向正确，但缺少原生 `DecisionSurfaceContract` 字段。P35 framework 现在是外部补充，不是 runtime contract。
2. Research Lead prompt 要求 AI/Semis 检验 product/spec、customer deployment、financial quality、capital-market price-in、risk/counterevidence，但当前 P35 用户题面更宽，需要把 HBM、SMCI/HPE、CoWoS、semicap peer panel 明确变成 required items。
3. 现有规划规则强调 source routes，但还没有明确 `SourceHunterLoop` 节点来补 missing cells。
4. 仅凭 Research Lead，无法证明工具好不好用；下一节点必须实际尝试 project-native retrieval / RAG / SQL / source route。

## 下一步

进入 `node_02_retrieval_rag_sql_source_route`：

- 先用项目现有 artifacts / source-route / ledger / SQL/RAG 可用面尝试按 required items 找证据。
- 比较项目内检索结果和 Codex/manual public-source supplement 的差距。
- 记录 top results 的 source-grade、相关性、可解析性和 rerank 质量。
