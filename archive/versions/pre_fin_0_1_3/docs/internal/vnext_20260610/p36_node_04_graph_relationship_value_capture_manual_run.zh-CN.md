# P36 Node 04 Graph / Relationship / Value-Capture Manual Run

日期：2026-07-09

## 节点定位

节点：`node_04_graph_relationship_value_capture`

目标：检查现有 relationship graph、ProductIntelligenceGraph、Research Graph Store 和 capital-market feedback graph 是否能把 node 02 / node 03 的候选证据组织成“价值捕获链条”：谁从 AI 基建需求中拿收入、谁拿利润、谁只是 demand proxy、哪些风险沿供应链传导。

本节点不写最终报告，不补外源，不运行 paid LLM，也不把图谱边直接升格成销量、订单、ASP、份额、利润率或投资建议。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/relationship_graph.py`
- `src/sec_agent/product_slot_relationship_graph.py`
- `src/sec_agent/product_intelligence_graph.py`
- `src/sec_agent/research_graph_store.py`
- `src/sec_agent/universe_relationship_llm.py`
- `src/sec_agent/agent_registry.py`
- `src/sec_agent/agent_contracts.py`
- `src/sec_agent/specialist_llm.py`
- `tests/test_relationship_graph_lookup.py`
- `tests/test_product_intelligence_graph.py`
- `data/manifests/product_relationship_graph_summary_v0_1.json`
- `data/manifests/product_intelligence_graph_summary_v0_1.json`
- `data/workbench_private/research_data/product_intelligence_graph_v0_1.sqlite`
- `data/manifests/research_graph_summary_v0_1.json`
- `data/workbench_private/research_data/research_graph_store_v0_1.sqlite`
- `data/manifests/p33_capital_market_feedback_fixture_v0_1.json`
- `docs/internal/vnext_20260610/product_intelligence_graph_v0_1.zh-CN.md`
- `docs/internal/vnext_20260610/rd4_research_graph_store.zh-CN.md`
- `docs/internal/vnext_20260610/p33_capital_market_feedback_fixture_report.zh-CN.md`

## 节点允许与禁止

允许：

- 使用 `relationship_graph_lookup` 做 runtime-like 查询。
- 查询 ProductIntelligenceGraph / Research Graph Store 的 SQLite 和 manifest。
- 将图谱边转成“需要验证的经济问题”或 specialist 输入。
- 判断图谱是否比 single-agent 搜索更有产品价值。

禁止：

- 不调用 paid LLM。
- 不运行 true runtime full-chain。
- 不联网补源。
- 不把 relationship graph 的存在当成 direct commercial proof。
- 不把 capital-market / ownership signal 当成实时资金流或投资建议。
- 不让 writer 自行补源；图谱若没有给 writer-ready cell，只能作为上游缺口记录。

## 图谱资产分层

当前项目里实际有四类图谱/准图谱资产：

| 资产 | 规模 | 主要价值 | 当前边界 |
|---|---:|---|---|
| `relationship_graph_lookup` / product relationship graph | 603 companies, 8,187 nodes, 25,251 edges | scope expansion, peer/supply-chain/customer hypothesis | `relationship_graph.py` 明确只能 `scope_or_hypothesis_only`，不能支撑 reported financial facts |
| ProductIntelligenceGraph | 36,046 nodes, 71,034 edges, 603 company packs | 产品槽、产品 KPI、deployment/channel/supply-chain signal、gap ledger | 585/603 company packs 是 `pass_with_gaps`；raw slots / relationship edges 不能单独写 thesis |
| RD4 Research Graph Store | 26,538 nodes, 100,145 edges, 113,199 support rows | 把产品图谱、Gold Mart 财务/产品/资本信号合并成可追溯图 | 不新增事实提权；source-evidence-only 仍保持原边界 |
| P33 Capital Market Feedback Fixture | 14,706 signals, 4,221 graph edges, 42 judgment material rows | 估值、流动性、持仓、融资、市场反应的 bounded thesis-driver | 只是 runtime alignment；不能变成基本面、实时资金流或投资建议 |

结论：图谱资产不是没有，且比 WorkBuddy 单 agent 的公开源搜索更有潜在结构化优势。但它们现在没有统一投射成这个 case 的 decision surface。

## `relationship_graph_lookup` 实测

我用 `mcp_tool_registry.invoke_mcp_tool("relationship_graph_lookup", ...)` 对四组 focus 做查询：

- `NVDA`
- `DELL / SMCI / HPE`
- `TSM / ASML / AMAT / LRCX / KLAC / MU`
- `000660.KS / 005930.KS / MU`

每组都返回 `status=ok`，但有明显可用性问题：

| focus | relationship_count | graph_rows | sector_rows | 主要问题 |
|---|---:|---:|---:|---|
| `NVDA` | 30 | 568 | 5 | 多数 row 的 `related_ticker` 为空，难以直接构建经济链条 |
| `DELL/SMCI/HPE` | 30 | 568 | 12 | 返回很多 broad supply/customer context，但没有 AI server margin 或 GPU pass-through 经济性 |
| `TSM/ASML/AMAT/LRCX/KLAC/MU` | 30 | 568 | 28 | 能识别 semicap / foundry / memory lane，但不回答 CoWoS、HBM 或 backlog |
| `000660.KS/005930.KS/MU` | 30 | 568 | 15 | 关系范围能扩到 memory/server OEM，但不能支撑 HBM 价格/利润/供给 |

关键观察：

- `relationship_graph_lookup` 适合告诉 Research Lead “该看哪些上下游/同行”，但不是 writer-ready evidence。
- 当前 product graph edge 的 `from_node_id/to_node_id` 里有 ticker 和 family，但 lookup 结果里的 `related_ticker` 经常为空，导致 agent 看到的是弱结构关系。
- 不同 focus 都扫出 `568` graph rows，说明过滤/排序过宽。强模型需要再人工读 node id 和 edge type，工程上不是一个好用的 agent tool surface。
- 关系边多数带有正确边界，例如 “not shipment, revenue, allocation, or customer concentration proof”。边界正确，但缺少下一步：把边界后的经济问题发给 source hunter / parser。

## ProductIntelligenceGraph 实测

ProductIntelligenceGraph 是本节点看到的最大真实优势。它不是简单“有图”，而是已经把公司产品槽、产品 KPI、官方产品表面、客户/渠道/供应链信号分层。

本 case 相关 company pack 摘要：

| ticker | status | product slots | exact product KPI | industry operating metrics | deployment signals | supply-chain signals | gap |
|---|---|---:|---:|---:|---:|---:|---:|
| NVDA | `pass_with_gaps` | 35 | 0 | 0 | 3 | 3 | 1 |
| AMD | `pass` | 46 | 29 | 0 | 2 | 4 | 0 |
| DELL | `pass_with_gaps` | 3 | 0 | 25 | 3 | 6 | 1 |
| SMCI | `pass_with_gaps` | 4 | 12 | 0 | 0 | 1 | 1 |
| HPE | `pass_with_gaps` | 6 | 18 | 0 | 3 | 1 | 1 |
| TSM | `pass_with_gaps` | 1 | 15 | 24 | 6 | 6 | 1 |
| ASML | `pass` | 21 | 10 | 25 | 1 | 6 | 0 |
| AMAT | `pass_with_gaps` | 4 | 21 | 0 | 0 | 8 | 1 |
| LRCX | `pass_with_gaps` | 1 | 63 | 5 | 0 | 5 | 1 |
| KLAC | `pass_with_gaps` | 1 | 4 | 0 | 0 | 8 | 1 |
| MU | `pass` | 29 | 18 | 0 | 6 | 8 | 0 |
| SK hynix `000660.KS` | `pass_with_gaps` | 5 | 2 | 0 | 0 | 3 | 1 |
| Samsung `005930.KS` | `pass_with_gaps` | 3 | 12 | 0 | 0 | 3 | 1 |

可用例子：

- NVDA 有 Blackwell product slots、technical spec、deployment / supply-chain signal，但 exact product KPI count 为 `0`。这解释了为什么图谱能证明产品存在和架构上下文，却不能单独证明 accelerator 收入质量。
- DELL 有 `Servers and Networking` revenue rows 和 AI Server / Rack OEM profile，但没有 AI server gross margin bridge。
- TSM 有 HPC revenue-mix、foundry profile、3DFabric alliance / supply-chain relationship signal，但没有 CoWoS pricing / capacity / allocation。
- MU 有 HBM technical spec signal、memory product slots、segment / revenue-mix rows，但不能直接给 HBM-only gross margin。
- SK hynix / Samsung 有本地披露 exact segment rows，但仍是 DRAM/NAND/DS 等更粗粒度，并非 HBM-only economics。
- ASML / LRCX / AMAT / KLAC 有 semicap product KPI / industry rows，但 AI-specific bookings/backlog/WFE/China exposure 还需要二次筛选。

风险例子：

- ASML exact KPI 样例里出现 `product_or_segment` 类似 `€8.2bn`、`€28.3bn` 的值，说明 parser 可能把表格数值当 segment label。
- KLAC 有 `Products and Services` 的 `revenue` 行但 unit 是 `percent_of_revenue`，需要 headline/label sanity。
- NVDA exact product KPI 缺失，但基础财务里应有 Data Center revenue；这说明 graph 与 exact financial ledger 之间没有形成稳定 crosswalk。

判断：ProductIntelligenceGraph 可以成为我们区别于 WorkBuddy 的核心资产，但目前还停在“素材库/图谱资产”层，缺一个 `DecisionSurfaceGraphProjection`：把每个 company pack 投射到 HBM、CoWoS、server OEM margin、semicap lag、price-in 等格子。

## Research Graph Store 实测

RD4 Research Graph Store 把产品图谱和 Gold Mart fact/signal 合并，理论上最接近“统一研究图”。它的优势是证据 support 完整：`unsupported_edge_count=0`。

本 case 相关 ticker 的边类型显示：

- `NVDA`: 有 financial facts、product profile/spec、capital funding/ownership facts、lagged ownership context，但 Data Center product KPI 没通过 ProductIntelligence pack。
- `DELL`: 有 `HAS_INDUSTRY_OPERATING_METRIC`、financial statement facts、product profile/spec、customer deployment/order signal、capital structure disclosure。
- `SMCI/HPE`: 有 product KPI / financial statement / working capital / capital structure rows。
- `TSM`: 有 HPC 等 product KPI、industry operating metrics、financial facts、customer deployment/supply-chain relationship。
- `ASML/LRCX/AMAT/KLAC`: 有 semicap financial/product/ownership rows，但部分行需要 parser sanity。
- `000660.KS`: 查询时出现大量 `HAS_SOURCE_AUTHORITY_ROW` 和 `HAS_MARKET_LIQUIDITY_SIGNAL` fanout，这提示非美 ticker 或 node binding 可能存在过宽连接，需要进一步校验。

判断：Research Graph Store 是一个强底座，但当前 runtime 缺少面向 analyst 的查询 contract。它能证明“边都有 support”，但还不能回答“这个边对利润池归属有什么方向性和强度”。

## Capital Market Feedback 图谱实测

P33 capital-market fixture 本身通过了 gate：

- signals: `14,706`
- graph edges: `4,221`
- judgment material rows: `42`
- source roles 覆盖 valuation / liquidity / ownership / derivatives / credit / corporate action。

但当前 agent registry 里：

- `market_valuation_analyst` 的 source families 只有 `market_snapshot`。
- P33 capital feedback pack / graph 不是本 case 的 first-class source family。
- 因此 price-in / ownership / valuation 只能以 market snapshot 或手工 probe 形式出现，不会自然生成 ticker-level price-in matrix。

这解释了用户的问题：我们明明有财务数据、投融资、基金持仓、估值/衍生指标相关资产，但当前报告没分析出来。原因不是资产绝对不存在，而是没有把这些资产接到本 case 的 analyst contract 和 writer payload。

## 若我在本节点扮演 graph agent，能产出什么

在不补源、只用现有图谱的约束下，我能产出：

- 一张供应链拓扑：semicap -> foundry/packaging -> accelerator/HBM -> server OEM -> hyperscaler capex。
- 一张 peer/family map：accelerator, server OEM, foundry, memory/HBM, semicap equipment。
- 一组 candidate evidence routes：哪些 cell 要去 exact ledger、ProductIntelligence pack、market snapshot、capital feedback、public web source。
- 一组 bounded graph signals：product existence、official product profile、technical spec、supply-chain relationship、deployment/channel/order proxy。
- 一组 typed gaps：HBM-only margin、CoWoS economics、AI server GPU pass-through, AI-specific semicap backlog, real-time price-in/crowding。

我不能在这个节点内合规产出：

- HBM vendor profit ranking。
- CoWoS pricing power quantification。
- Server OEM margin dilution conclusion。
- Semicap “最后一棒”收入质量结论。
- Ticker-level price-in or ownership crowding conclusion。

原因不是模型弱，而是 graph node 合同本来只允许关系/上下文；它没有 authority 把这些上下文变成 business-line economics。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | 能建立产业链拓扑和候选路线，不能回答收入/利润质量。 |
| decision_surface_completeness | partial | 图谱能覆盖五条链，但没有按七个判断列输出 cell projection。 |
| financial_and_operating_depth | partial | Research Graph 有财务/产品/资本边，但缺经济含义排序和 sanity。 |
| capital_market_price_in_depth | partial | P33 capital feedback 存在，但没有接入本 case runtime contract。 |
| source_grade_and_lineage | pass | 图边和 support rows 的边界/来源追踪较强。 |
| counter_thesis_and_turning_signals | partial | 可指向 supply bottleneck / margin dilution / price-in gaps，但不能自己完成判断。 |
| writer_readiness | partial | 能给 writer graph context 和 gaps，不能直接给最终报告的 evidence table。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | 输入是 graph / pack / edge，不是 value-capture cell。 |
| output_contract_quality | partial | relationship lookup 输出对 product edge 的 ticker/related_ticker 解析不够好。 |
| tool_affordance_fit | partial | 需要手工知道 `PYTHONPATH`、SQLite schema、pack JSON key 和图谱边界。 |
| observability | pass | summary、SQLite、support rows、tests 都能定位到问题。 |
| recoverability | partial | 能发现 graph lookup fanout / parser label 错误，但没有自动 repair。 |
| information_economy | partial | 总量很大，但前排不一定高信息密度；需要 cell-level ranking。 |
| marginal_contribution | partial | ProductIntelligenceGraph / Research Graph 有明显潜力，但 runtime 未兑现。 |
| human_review_surface | partial | 缺 per-cell graph projection review，而不是只看 graph summary。 |
| product_value_over_single_agent | partial | 结构化资产可形成优势，但现在还没有把优势转成用户可见报告质量。 |

## Root-cause notes

- 图谱目前更像 `scope graph` / `evidence support graph`，不是 `investment decision graph`。
- `relationship_graph_lookup` 对 product graph edge 的 ticker extraction 和 focus filtering 不够精准，导致结果里 `related_ticker` 常为空、不同 focus 扫出相同大批 row。
- ProductIntelligenceGraph 的 company packs 很有价值，但没有自动投射到本 case 的 decision surface。
- Research Graph Store 能证明证据 support，但不表达 value capture direction、economic materiality、risk transmission strength。
- P33 capital-market feedback graph 已具备独立资产，但没有成为 market_valuation_analyst 的 source family，也没有进入本 case writer payload。
- 图谱边界声明是必要的，但如果没有 `GraphToDecisionCellProjection`，它最终只会增加 bounded-context prose，而不是提升报告主干。

## 对下一节点的交接

给 specialist 的可用输入应该是：

- ProductIntelligence company pack counts and representative rows for all 13 case tickers。
- Relationship graph 仅作拓扑和 source-hunting route，不作事实结论。
- Research Graph financial/product/capital edge counts 仅作 coverage map。
- 明确缺口：HBM-only economics、CoWoS economics、AI server margin bridge、semicap AI-specific backlog/China exposure、full price-in matrix。

下一节点进入 `node_05_fundamental_specialist`。我会先在 specialist 约束下使用 node 02-04 的材料写一份基础财务/利润质量 memolet。如果在该约束下仍写不出，就说明问题已经不是 writer，而是 upstream decision-cell evidence pack 不足。
