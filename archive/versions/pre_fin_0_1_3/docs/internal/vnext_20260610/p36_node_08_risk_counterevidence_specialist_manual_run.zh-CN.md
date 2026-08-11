# P36 Node 08 Risk / Counterevidence Specialist Manual Run

日期：2026-07-09

## 节点定位

节点：`node_08_risk_counterevidence_specialist`

目标：检查 `risk_counterevidence_analyst` 在当前 agent 链路里，能否把前面节点暴露的缺口、冲突、边界和反证组织成 AI 基建五链条报告需要的风险矩阵：

- Server OEM margin dilution。
- HBM / CoWoS / packaging supply bottleneck。
- Hyperscaler capex digestion。
- Export control / China exposure。
- Price-in / crowding / valuation risk。
- Semicap last-baton / backlog lag risk。

本节点不写最终报告，不补外源，不调用 paid LLM，也不运行 true runtime full-chain。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/prompts/skills/risk_counterevidence_skill_v0_2.md`
- `src/sec_agent/prompts/skills/shared_evidence_boundary_skill_v0_1.md`
- `src/sec_agent/agent_registry.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/specialist_llm.py`
- `src/sec_agent/dimension_evidence_portfolio.py`
- `src/sec_agent/capital_macro_pack.py`
- `data/processed_private/market/evidence_packs/20260624_market_yahoo_chart_603_3m_v1_3m_market_evidence.jsonl`
- `data/processed_private/market/evidence_packs/20260528_market_yahoo_chart_full78_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- `Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/capital_ownership_rows.jsonl`
- `product_intelligence_context_rows_for_state(...)` local probe
- `build_agent_data_view("risk_counterevidence_analyst", state)` local probe

说明：本地 probes 是 Codex supervisor 为了模拟 runtime data view 和 specialist 输入而调用；不是 `risk_counterevidence_analyst` 自己可调用的工具，也不是 writer runtime 自补源。

## 节点允许与禁止

允许：

- Risk Specialist 使用 bounded evidence rows、bounded gap refs、capital macro pack、source family bundle、required claim slots、counterclaim slots。
- 可以写 supported risk observations、unsupported thesis components、direct conflicts。
- 可以把 context-only rows 标成 caveated risk 或 unsupported claim，而不是当作事实。
- 可以生成 `judgment_candidates`，说明风险如何约束 memo。

禁止：

- 不调用工具或补源。
- 不从记忆引入新风险。
- 不列泛泛的风险清单。
- 不把 market / industry / relationship rows 当成公司 reported facts。
- 不把 gap 当成事实。
- 不解决冲突时“择优”或平均。

## Runtime skill 观察

Risk skill 本身方向是对的：

- 要求 stress-test strongest actual thesis components，而不是列所有缺失项。
- 要求区分 supported risk observations、unsupported thesis components、direct conflicts。
- 明确 AI/Semis strong pass 要 stress-test capex digestion、export control、customer concentration、margin dilution、supply bottleneck、pricing pressure、product/deployment delay、missing-but-retrievable evidence。
- 要求 `judgment_candidates` 包含 judgment、required item、evidence refs、business mechanism、counter read、cannot infer、what-would-change。

这说明 risk 节点并不是天生只会写边界。它的设计目标是成为最终报告的反证/约束层。

## Registry / data-view 观察

`risk_counterevidence_analyst`：

- `tool_permission=inspect_only`
- `allowed_tools=[]`
- `allowed_data_views=["bounded_rows", "coverage_summary"]`
- `source_families` 覆盖：
  - primary SEC filing
  - company-authored unaudited filing
  - company product evidence graph
  - public source context
  - live public web context
  - milvus semantic
  - market snapshot
  - industry snapshot

Runtime data view 对 risk 节点：

- 读取 `runtime_ledger_rows`
- 读取 `context_rows`
- 读取 `market_snapshot_rows`
- 读取 `industry_snapshot_rows`
- 读取 `derived_metric_layer`
- 读取 `product_evidence_rows`
- 读取 `public_source_context_rows`
- 若无 rows，读取 fused role rows
- 不主动调用 `product_intelligence_context_rows_for_state(...)`
- 不追加 `_relationship_rows_from_state(...)`，因为 `agent_id == risk_counterevidence_analyst` 时跳过 relationship rows
- 会附 `capital_macro_pack`

关键含义：

- Risk 节点理论上比 Market 节点宽。
- 但它不会自动加载 PIG；除非上游把 PIG rows 投到 `product_evidence_rows`，否则 risk 看不到产品/产业链材料。
- 它也不会拿到 relationship rows，除非那些 rows 已经在 `context_rows` / `product_evidence_rows` / other state rows 中。

## Prompt projection 观察

`specialist_llm.py` 里 risk prompt rows 的选择有两层：

1. 先对 `req_dell_margin_quality`、`req_hyperscaler_capex`、`req_supply_chain`、`req_customer_deployment` 做有限保底。
2. 再保留少量 `relationship_graph`、`market_snapshot`、`industry_snapshot`。
3. 再按 focus ticker 做 balanced prompt rows。

问题：

- 这些 required ids 是 P33/P34 老 case 的 required item，不是本 P36 五链条 decision surface 的原生 risk cells。
- 当前 case 需要的 risk cells 应该是 margin dilution、supply bottleneck、capex digestion、export control、price-in、last-baton/backlog risk，而不是只围绕 `req_dell_margin_quality` 和 `req_hyperscaler_capex`。

CapitalMacroPack 对 risk 的 prompt projection 也有问题：

- `risk_counterevidence_analyst` included sections 是：
  - `debt_instruments`
  - `macro_drivers`
  - `rejected_objects`
- 排除了：
  - `ownership_positions`
  - `insider_transactions`
  - `company_exposure_edges`
  - `vertical_official_objects`

这使得 risk 节点即使拿到 CapitalMacroPack，也很难做 ownership / crowding / positioning 风险。对当前 AI/Semis price-in 问题，这是明显过窄。

## Runtime-like data-view probes

我构造两个 state：

### Probe A：minimal no product rows

输入：

- 13 个 case tickers。
- 17 条 market rows。
- 154 条 capital / ownership rows。
- 5 条 synthetic source gaps：
  - DELL AI server margin bridge。
  - HBM-only economics。
  - CoWoS capacity/pricing/allocation。
  - Semicap AI-specific backlog/export mix。
  - Price-in crowding/positioning。

结果：

- `bounded_rows=16`
- `bounded_by_source_family={"market_snapshot":16}`
- `has_capital_macro_pack=true`
- `bounded_gap_refs=5`
- `capital_macro_pack_ref.summary.input_row_count=154`
- `capital_structure_count=8`
- `debt_instrument_count=16`
- `credit_facility_count=16`
- `ownership_position_count=16`

但 bounded rows 全是 market snapshot。Risk 可以写 price-action / volatility / market context，也能看到 gap refs 和 compact capital pack summary；但无法从 bounded rows 写 AI server margin、HBM economics、CoWoS、semicap backlog/export 或 product-supply counterevidence。

### Probe B：with supervisor-projected product rows

我把 Node 06 的 PIG rows 手工放进 `product_evidence_rows`。

输入：

- Probe A 全部输入。
- `product_evidence_rows=592` PIG rows。

结果：

- `bounded_rows=16`
- `has_capital_macro_pack=true`
- `bounded_gap_refs=5`
- `by_source_family`：
  - `company_product_evidence_graph=12`
  - `market_snapshot=3`
  - `live_public_web_context=1`
- `by_metric`：
  - `product revenue=5`
  - `revenue mix percent=4`
  - `segment revenue=1`
  - `revenue=1`
  - `product_or_business_line_profile=1`
  - `product_or_service_profile=1`
  - `unknown=3`

代表性 rows：

- AMD Data Center product revenue。
- DELL Consumer product revenue row。
- SMCI Storage Systems product revenue row。
- HPE Server product revenue。
- TSM High Performance Computing revenue mix。
- ASML / AMAT / LRCX / KLAC product or revenue-mix rows。
- SK hynix semiconductor segment revenue。
- market snapshot rows for SK hynix / Samsung / AMAT。

关键问题：

- risk bounded rows 变得更“有数据”，但仍不是 risk-specific。很多 rows 是产品/收入槽，不是直接风险、冲突或反证。
- DELL row 进入的是 Consumer revenue，不是 AI server margin risk。
- SMCI row 进入的是 Storage Systems label，存在与 AI server thesis 不匹配的 risk。
- TSM / HBM / Semicap rows 可支撑“暴露存在”，但不能直接证明 bottleneck、margin、export-control 或 backlog risk。
- market rows 因 max_rows / balanced selection 只剩 3 条，price-in risk 反而被稀释。

## 本节点能写出的材料

在不补源、只使用 runtime-like 输入下，我可以写出 partial but useful risk memolet：

1. **Server OEM margin dilution 是最重要 unsupported thesis component**：DELL / SMCI / HPE 有 server / product / market rows，但没有 AI server-only gross margin、GPU pass-through、rack BOM bridge 或 backlog margin rows。结论是：Server OEM revenue growth 不能被当作 high-quality profit proof。
2. **Price-in risk 可被 bounded market rows 支撑，但不能完整化**：DELL、AMD、MU、SK hynix、AMAT/LRCX/KLAC 等有强 price action / volatility；SMCI 有高 volatility 和大 drawdown。这可以约束 writer：强叙事可能已部分计价，尤其 memory / OEM / semicap beta，但不能写完整 crowding。
3. **HBM / CoWoS profit-pool thesis 缺关键公司级经济性**：PIG / segment rows 支持 memory/HPC exposure，但 HBM-only revenue/margin/yield/allocation 和 CoWoS pricing/capacity/allocation 缺失。风险不是“没有需求”，而是“公开 runtime 不能证明利润池分配和持续性”。
4. **Semicap last-baton / export-control risk 当前不能充分支撑**：ASML/AMAT/LRCX/KLAC 有 product / revenue-mix / market rows，但缺 AI-specific backlog/bookings、China exposure、export-control order impact。Risk 节点应该把这列为 missing-but-material，而不是直接写强结论。
5. **Capex digestion 风险在本节点输入中不完整**：当前 risk data view 没有 hyperscaler capex/revenue rows 或 customer spending capacity bridge；即使题面要求 capex digestion，也只能列为 key missing test，不能写成已证明的风险。

## 不能写的内容

- 不能写“AI server 毛利已被证明恶化”，除非有 AI server-only margin bridge。
- 不能写“HBM 已确认 55-60% gross margin”，除非有 official/company or clearly attributed estimate rows。
- 不能写“CoWoS bottleneck 直接决定 TSMC margin”，除非有 capacity/pricing/allocation rows。
- 不能写“export controls 是 ASML/LRCX/AMAT 当前订单的量化冲击”，除非有 company-disclosed China/export/tool mix rows。
- 不能写“机构拥挤/正在流入”，因为 risk role projection 当前不保留 ownership positions，且没有 realtime flow / short / options / borrow。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | 能识别关键反证和 unsupported thesis components，但不能完成完整风险矩阵。 |
| decision_surface_completeness | partial | skill 知道 AI/Semis risk menu，但 runtime selector 未按五链条 risk cells 组织。 |
| financial_and_operating_depth | partial | 若上游传入 PIG/product rows，可指出 margin/economics 缺口；但缺 AI-server/HBM/CoWoS/semicap-specific rows。 |
| capital_market_price_in_depth | partial | market rows 和 capital pack 存在，但 ownership/crowding 在 risk prompt projection 中被排除。 |
| source_grade_and_lineage | pass | bounded rows、gap refs、capital pack 都有边界；不会越权。 |
| counter_thesis_and_turning_signals | partial | 能列 material gaps 和 what-would-change，但缺直接 conflict rows。 |
| writer_readiness | partial | 可给 writer 风险约束段落，但不是完整 risk/counterevidence matrix。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | source families 宽，但缺 P36 risk-cell input contract。 |
| output_contract_quality | pass_partial | skill 要求 judgment_candidates，方向正确。 |
| tool_affordance_fit | partial | inspect-only 合理，但上游必须投射 risk-specific rows；当前不能自恢复。 |
| observability | pass | bounded_distribution、capital pack ref、gap refs 可审。 |
| recoverability | partial | 可通过 selector / projection 修复，无需重写 skill。 |
| information_economy | partial | max 16 rows 降噪，但选到的不是最风险相关 rows。 |
| marginal_contribution | partial | 节点能约束主 thesis，但当前容易重复 gaps。 |
| human_review_surface | partial | gap refs 可审，但缺 risk-cell review table。 |
| product_value_over_single_agent | partial | 若有 risk-cell projection，会明显强于单 agent；当前增益未完全释放。 |

## Root Cause

本节点 root cause 不是 risk prompt 不会分析，而是 risk-specific material projection 不成熟：

1. Risk data view 不自动加载 ProductIntelligenceGraph，除非上游把 PIG rows 投到 `product_evidence_rows`。
2. Risk data view 不追加 relationship rows，导致 supply-chain / customer / graph conflicts 依赖上游显式传递。
3. Risk prompt row selector 使用旧 required ids，而非当前 P36 五链条 risk cells。
4. CapitalMacroPack 的 risk role projection 排除了 ownership positions，削弱 price-in / crowding / positioning risk。
5. `max_rows=16` 下，balanced selection 能保证 ticker 覆盖，但不能保证每个 risk dimension 都有最相关 rows。

## 需要的修复方向

1. 新增 `RiskCounterevidenceDecisionSurfaceProjection`：
   - segment: Accelerator / Server OEM / Foundry-Packaging / HBM / Semicap
   - risk dimensions: margin dilution, supply bottleneck, capex digestion, export control, price-in, customer concentration, timing/backlog, missing-but-retrievable。
2. 让 risk 节点接收：
   - PIG / product rows 的 risk-specific projection。
   - relationship graph conflicts / weak links。
   - capital macro pack 中的 ownership positions / positioning rows。
   - market price-in rows。
   - bounded gap register。
3. 把 hardcoded P33 required ids 升级为 query-specific decision cell ids。
4. 在 writer 前生成 `RiskMatrixPack`，每格包含：
   - risk claim
   - supporting rows
   - unsupported thesis component
   - cannot infer
   - what would change
   - repair route
5. Workbench 要能按 risk cell 审核：支持、反证、缺口、边界、是否需要补源。

## 结论

Risk / Counterevidence 是 multi-agent 最应该产生增益的节点之一，因为它能把“单 agent 顺手写出来的乐观故事”压回投资纪律。但当前系统只是具备了这个节点和 prompt，尚未把前面所有节点的 material gaps、capital signals、product graph、relationship graph、market price action 投射成 risk decision surface。

所以它现在能产出比 generic disclaimer 更好的风险 memolet，但还不能稳定产出 WorkBuddy 报告里那种清晰的 risk ranking / falsifier / price-in / margin-dilution matrix。要让 multi-agent 真正有商业价值，这个节点必须从“看 bounded rows 的风险专家”升级为“decision-cell risk adjudicator”。
