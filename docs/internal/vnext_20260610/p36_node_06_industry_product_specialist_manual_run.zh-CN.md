# P36 Node 06 Product / Industry Specialist Manual Run

日期：2026-07-09

## 节点定位

节点：`node_06_industry_product_specialist`

目标：同时检查 `product_technology_analyst` 与 `industry_supply_chain_analyst` 两类 specialist 在真实约束下，能否把 ProductIntelligenceGraph、ProductEvidencePack、relationship graph、deployment / supply-chain / operating rows 转成 AI 基建五链条的产品与产业链判断：

- Accelerator 是否是 real demand。
- Server OEM 是否只是 demand proxy。
- Foundry / Packaging 的 CoWoS / advanced packaging 是否是瓶颈。
- HBM 是否是供给瓶颈和利润池。
- Semicap 是否是滞后但高质量的 capex read-through。

本节点不写最终报告，不补外源，不调用 paid LLM，也不运行 true runtime full-chain。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/prompts/skills/product_technology_analysis_skill_v0_1.md`
- `src/sec_agent/prompts/skills/industry_supply_chain_analysis_skill_v0_2.md`
- `src/sec_agent/product_intelligence_runtime.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/specialist_llm.py`
- `data/workbench_private/research_data/product_intelligence_graph_v0_1.sqlite`
- `build_agent_data_view("product_technology_analyst", state)` local probe
- `build_agent_data_view("industry_supply_chain_analyst", state)` local probe
- `product_intelligence_context_rows_for_state(...)` local probe

说明：这些本地 probes 是 Codex supervisor 为了模拟 runtime data view 和 specialist 输入而调用；不是 specialist 自己可调用的工具，也不是外部补源。

## 节点允许与禁止

允许：

- Product Specialist 可使用 `bounded_evidence_rows`、`product_spec_pack`、`source_family_bundle`、ProductIntelligenceGraph company pack refs。
- Industry Specialist 可使用 `bounded_evidence_rows`、`relationship_summary`、industry / relationship / selected company context rows。
- 产品/产业链节点可以写 taxonomy、architecture、deployment context、supply-chain relationship hypothesis、demand proxy、commercial gap 和 what-would-change。

禁止：

- 不调用工具或补源。
- 不把 product taxonomy / spec / deployment / relationship rows 写成 revenue、shipment、share、allocation、backlog、ASP、margin 或 customer concentration。
- 不把 `relationship_graph` 或 PIG relationship edge 写成 confirmed customer/supplier fact。
- 不把 context-only product rows 当作 exact KPI。
- 不让 writer 阶段自发补源。

## Runtime skill 观察

Product skill 的方向是对的：

- 明确要求先按 authority 分层。
- `company_product_evidence_graph` 且 `promotion_status=runtime_fact_allowed`、`exact_value_authority=true` 才能支撑 product KPI facts。
- taxonomy / ProductSpec / ChannelOffer / FieldInquiry / Deployment / SupplyChainSignal 都有明确 forbidden claims。
- AI/Semis 强 pass 要求即使没有 SKU revenue，也要分析 architecture、generation change、deployment、supply-chain dependency，而不是只写“无证据”。

Industry skill 的方向也对：

- 明确要求 chain map：upstream input、focal company、downstream customer/end-market、peer/competitor、constraint/regulatory layer。
- 明确 relationship graph 是 hypothesis / research scope，不是 reported revenue/margin/order proof。
- AI/Semis 强 pass 要求 map accelerator / server / HBM / CoWoS / foundry / semicap / OEM / power-cooling transmission，并说出确认指标。

结论：两个 skill 都不是“只会写边界”的 prompt。它们已经要求把 bounded rows 转成投资机制，只是不能越权写成公司事实。

## Runtime data-view 实测

我用 13 个 case tickers 构造最小 state：

`NVDA, AMD, DELL, SMCI, HPE, TSM, MU, 000660.KS, 005930.KS, ASML, AMAT, LRCX, KLAC`

### PIG autoload context rows

调用 `product_intelligence_context_rows_for_state(..., max_rows=720)` 后：

- row_count: `592`
- by_source_class:
  - `product_intelligence_product_slot`: `76`
  - `product_intelligence_exact_product_kpi`: `112`
  - `product_intelligence_product_profile_or_spec`: `155`
  - `product_intelligence_relationship_edge`: `174`
  - `official_customer_deployment_event`: `24`
  - `product_intelligence_industry_operating_metric`: `41`
  - `product_intelligence_gap`: `10`
- by_promotion:
  - `runtime_context_taxonomy_only`: `231`
  - `runtime_fact_allowed`: `153`
  - `context_or_lead_available`: `198`
  - `gap_exposed_not_fallback`: `10`

这说明 PIG autoload 本身是有效的，13 个 ticker 都能加载到产品/关系/精确 KPI/缺口 rows。

### Product Specialist data view

调用 `build_agent_data_view("product_technology_analyst", state)` 后：

- bounded rows: `48`
- by_source_class:
  - `product_intelligence_product_slot`: `35`
  - `product_intelligence_product_profile_or_spec`: `7`
  - `product_intelligence_relationship_edge`: `5`
  - `product_intelligence_gap`: `1`
- by_ticker:
  - NVDA / AMD / DELL / SMCI / HPE / TSM / MU / Samsung / ASML / AMAT / LRCX / KLAC 各约 `3` rows
  - SK hynix `000660.KS` 为 `12` rows
- `product_spec_pack_ref.status=pass`
- `product_spec_pack_ref.summary.input_row_count=592`
- `product_spec_pack_ref.summary.product_kpi_ref_count=32`
- `product_spec_pack_ref.summary.customer_deployment_signal_count=32`
- `product_spec_pack_ref.summary.supply_chain_signal_count=29`
- `product_intelligence_pack_ref.pack_count=8`
- `product_evidence_pack_ref.pack_count=8`

关键问题：

- Product Specialist 的 bounded rows 最终主要是 product slots，不是 exact product KPI rows。也就是说 prompt 里能看到很多“产品存在/产品槽”，但不一定看到关键 segment/product revenue rows。
- `product_spec_pack_ref` 总结里有 32 个 product KPI refs，但 bounded rows 里没有足够 exact KPI 直接暴露；模型如果只读 rows，会偏 taxonomy/context。
- `product_intelligence_pack_ref` 和 `product_evidence_pack_ref` 只 compact 前 8 个 packs。由于 ticker 顺序固定，重要 tickers 可能只出现在 ProductSpecPack summary 或 bounded rows，而不在 compact pack refs 里完整展示。

### Industry Specialist data view

调用 `build_agent_data_view("industry_supply_chain_analyst", state)` 后：

- bounded rows: `48`
- by_source_class:
  - `product_intelligence_product_profile_or_spec`: `11`
  - `product_intelligence_relationship_edge`: `37`
- by_ticker:
  - SK hynix `000660.KS`: `25`
  - Samsung `005930.KS`: `23`
- 其它 11 个 ticker 没进入最终 bounded rows。

关键问题：

- Industry bounded rows 被 memory/HBM 相关关系边占满，没有按 accelerator / server OEM / foundry-packaging / HBM / semicap 五条链平衡。
- `product_intelligence_runtime._relationship_row()` 会丢弃 `template_context_edge`；很多 server/rack OEM -> cloud capacity 的模板边不会进入 PIG context rows。若上游没有另外传入 relationship_graph_lookup rows，Industry Specialist 可能看不到 server OEM / foundry / semicap 链条。
- 这不是模型写作问题，而是 role-specific row selector / balancing 没按当前题面的 decision surface 分配预算。

## 项目内证据能支持什么

### Accelerator

可见材料：

- NVDA: Blackwell GPU architecture / CUDA 等 product slots；relationship edges 指向 accelerator 是 AI server/rack OEM 的 component input。
- AMD: AI accelerators / AI acceleration / adaptive SoCs and acceleration cards；Data Center exact product revenue rows。

可支持：

- Accelerator 是最直接的 AI compute demand carrier。
- NVDA / AMD 产品 taxonomy 与 architecture context 可以支撑“真实需求链条”判断。

不能支持：

- GPU units / ASP / allocation。
- NVDA Data Center-only margin。
- Blackwell / Rubin revenue split。
- 出口管制对具体产品收入的影响。

### Server OEM

可见材料：

- DELL: AI Server / Rack OEM product slots；Servers and Networking / ISG operating rows。
- SMCI: Complete Servers / Full Rack Scale Solutions product slots；product exact rows 但 label 存在 Storage Systems 风险。
- HPE: Server / ProLiant Rack / AI-native networking product slots；Server product revenue exact rows。

可支持：

- Server OEM 是 AI infrastructure demand proxy 和 integration layer。
- 产品/业务线 taxonomy 足以让 report 区分 OEM 与 GPU/HBM/Foundry 的利润池差异。

不能支持：

- AI server-only revenue。
- AI server gross margin。
- GPU pass-through / BOM dilution。
- Rack-level backlog, allocation, customer concentration。

### Foundry / Packaging

可见材料：

- TSM: High Performance Computing revenue mix exact rows；3DFabric Alliance deployment / supply-chain context。
- Samsung: foundry / wafer fabrication and DS rows。

可支持：

- Foundry/HPC 暴露是 AI demand 的真实链条。
- 3DFabric / advanced packaging 可作为 CoWoS/packaging bottleneck 的 source-hunter lead。

不能支持：

- CoWoS capacity。
- CoWoS ASP / pricing power。
- Advanced packaging margin。
- Customer allocation / lead time。

### HBM / Memory

可见材料：

- MU: DRAM / GDDR / memory product profile, MCBU/CDBU revenue mix。
- SK hynix: semiconductor segment rows, memory product slots, memory component-input relationship edges。
- Samsung: DS / DRAM / NAND segment rows, memory component-input relationship edges。

可支持：

- Memory/HBM 是 AI server configuration 的 core input 和 supply-chain bottleneck candidate。
- SK hynix / Samsung / MU 的 memory exposure 可以成为 HBM profit-pool 的必查 universe。

不能支持：

- HBM-only revenue。
- HBM-only gross margin。
- HBM3E/HBM4 capacity, yield, allocation。
- NVIDIA / hyperscaler customer split。

### Semicap

可见材料：

- ASML: EUV / DUV / computational lithography product slots，但也有 noisy product slot label。
- AMAT: Semiconductor Systems / services product rows, equipment enables production edges。
- LRCX: deposition / etch / memory/foundry mix rows。
- KLAC: process control / inspection / metrology rows。

可支持：

- Semicap 是 foundry/memory capacity expansion 的 upstream tooling read-through。
- AMAT / LRCX / KLAC / ASML 作为高质量设备 peer universe 是合理的。

不能支持：

- AI-specific bookings/backlog。
- China/export tool mix。
- Last-baton risk 的定量 timing。
- 对 HBM / CoWoS 产能扩张的公司级订单映射。

## 手工模拟 Product / Industry Memolet

在不补源、只使用项目内证据和节点边界下，我能写出一个 partial but useful memolet：

1. Accelerator 是 real demand carrier：NVDA/AMD product taxonomy 与 AMD Data Center revenue rows 支持 AI compute 需求已进入公司产品/分部披露；但产品节点不能证明 GPU units、ASP、allocation 或 margin。
2. Server OEM 是 demand proxy：DELL/SMCI/HPE product slots 和 server / networking revenue rows 支持它们是 AI infrastructure assembly layer；但缺 AI server-only margin 和 GPU pass-through bridge，因此不能把 revenue growth 等同于 profit quality。
3. Foundry/Packaging 是 real demand + bottleneck candidate：TSM HPC revenue mix 和 3DFabric context 支持 AI/HPC exposure；但 CoWoS capacity/pricing/allocation 未进入 runtime rows，只能作为 source-hunter lead。
4. HBM/Memory 是 supply bottleneck candidate：MU/SK/Samsung memory rows 与 component-input relationship edges 支持 HBM universe 和 bottleneck hypothesis；但 HBM-only economics 仍缺。
5. Semicap 是 upstream capex read-through：ASML/AMAT/LRCX/KLAC product slots 和 enables-production edges 支持设备链条定位；但 AI-specific backlog/bookings 与 export-control risk 未被当前 rows 证明。

这个 memolet 比 Node 05 更接近 WorkBuddy 的故事链，但仍只能是 hypothesis / context / exact-KPI 混合材料，不能直接成为最终报告的证据质量矩阵。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | 能讲出五条链的产品/供给机制，但不能完成利润质量和风险定量。 |
| decision_surface_completeness | partial | 五条链都有 product/industry material，但 selector 没按 decision surface 平衡。 |
| financial_and_operating_depth | partial | PIG exact KPI 有些进入 pack，但 Product bounded rows主要是 taxonomy。 |
| capital_market_price_in_depth | fail_for_this_node | 本节点不消费 market / ownership / valuation。 |
| source_grade_and_lineage | pass_with_selector_caveat | PIG rows 边界清晰，但 selector 输出不稳定。 |
| counter_thesis_and_turning_signals | partial | 可以提出缺确认指标和 what-would-change，但 risk/market 节点仍需承接。 |
| writer_readiness | partial | 可给 writer 链条机制，但不能直接给最终 fact table。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | PIG autoload 与 ProductSpecPack 是好机制，但 bounded rows / pack refs 不是 decision-cell-balanced。 |
| output_contract_quality | partial | SpecialistMemolet 结构可用，但没有 cell-level chain map schema。 |
| tool_affordance_fit | partial | Specialist 无工具权限正确；source-hunter / graph projection 应在上游完成。 |
| observability | pass | 能定位到 PIG rows、data view、pack summary、selector skew。 |
| recoverability | partial | 能记录 gaps，但不能自动触发 graph/source repair。 |
| information_economy | partial | 592 rows 被压到 48 rows 时丢掉大量关键 exact KPI / tickers。 |
| marginal_contribution | partial | PIG 是真实差异化，但未被转成用户可见价值面。 |
| human_review_surface | partial | 缺 per-cell product/industry review table。 |
| product_value_over_single_agent | partial | 有结构化资产，能比 single-agent 更可信；但 selector 失衡会让输出不如 single-agent 完整。 |

## Root-cause notes

- Product / Industry skills 本身不是主要坏点。
- PIG autoload 是项目真实优势，但 bounded-row selection / pack compacting 没按当前题面五条链和判断列平衡。
- Product Specialist 看到很多 taxonomy/product slots，却不一定看到 exact product KPI rows；这会导致输出偏“产品存在”和“边界”。
- Industry Specialist 在最小 state 下被 memory relationship rows 占满，说明 `industry_supply_chain_analyst` 的 selector 需要按 supply-chain segment / required item 做 coverage guarantee。
- `template_context_edge` 被过滤是合理的边界，但必须由上游 relationship graph / SourceHunterLoop 补充真实 relationship rows，否则 server OEM / foundry / semicap 链条在 Industry prompt 里可能缺失。
- ProductIntelligence pack refs 当前 `pack_count=8`，对 13-ticker case 会压缩掉部分重要 tickers；这会让强模型看不到完整 universe。
- 当前 multi-agent 相比 WorkBuddy 的应有优势不是“更谨慎”，而是 PIG / graph / exact KPI / gaps 可以给每个 decision cell 一个可审计状态；现在 selector 没把这个优势投射出来。

## 对下一节点的交接

下一节点建议进入 `node_07_market_capital_price_in_specialist`：

1. 检查 market snapshot、valuation、ownership、capital feedback 是否能真正进入 price-in / crowding / capital-market risk cells。
2. 验证 `market_valuation_analyst` 目前只吃 `market_snapshot` 是否过窄。
3. 分开记录：market rows 能支持非实时 price action / valuation context；13F/ownership 是 lagged holder context；capital feedback graph 是 runtime-alignment-only，不能写成实时资金流。
4. 如果 market/capital 数据仍未进入 case payload，应记录为 capital feedback pack to decision surface 的 runtime wiring gap。

## 未运行

- paid LLM API
- true runtime full-chain
- external source supplement
- source ingestion
- parser repair
- model comparison
- case expansion
- release eval
