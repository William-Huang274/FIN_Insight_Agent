# P36 Node 07 Market / Capital / Price-in Specialist Manual Run

日期：2026-07-09

## 节点定位

节点：`node_07_market_capital_price_in_specialist`

目标：检查当前 `market_valuation_analyst` 以及相关 capital / ownership / valuation / price-in 数据资产，能否支撑 AI 基建五链条报告里的资本市场判断：

- 哪些链条已经被市场明显 price-in。
- 哪些公司存在 valuation premium / crowding / momentum unwind 风险。
- 13F / ownership / capital structure / liquidity / derivatives / valuation rows 能否变成 bounded thesis drivers。
- 这些资本市场信号能否与 Accelerator、Server OEM、Foundry/Packaging、HBM、Semicap 的 real demand / demand proxy / profit quality 绑定。

本节点不写最终报告，不补外源，不调用 paid LLM，也不运行 true runtime full-chain。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/prompts/skills/market_valuation_analysis_skill_v0_2.md`
- `src/sec_agent/agent_registry.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/capital_macro_pack.py`
- `data/processed_private/market/evidence_packs/20260624_market_yahoo_chart_603_3m_v1_3m_market_evidence.jsonl`
- `data/processed_private/market/evidence_packs/20260528_market_yahoo_chart_full78_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- `Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/capital_ownership_rows.jsonl`
- `data/manifests/p33_capital_market_feedback_fixture_v0_1.json`
- `build_agent_data_view("market_valuation_analyst", state)` local probe
- `build_capital_macro_pack(state)` local probe

说明：这些本地 probes 是 Codex supervisor 为了模拟 runtime data view 和 specialist 输入而调用；不是 `market_valuation_analyst` 自己可调用的工具，也不是 writer runtime 自补源。

## 节点允许与禁止

允许：

- Market Specialist 使用 bounded `market_snapshot` rows 写非实时价格反应、波动率、相对表现、估值上下文、事件窗口和 market expectation context。
- 如果输入明确提供公司 rows，可把 market reaction 和 filed evidence 做 bounded divergence discussion。
- Capital / ownership rows 如果通过上游 pack 或 bounded rows 明确给到，可写 lagged ownership context、capital structure context、credit/liquidity context、valuation price-in context。

禁止：

- 不调用工具或补源。
- 不把 market snapshot 写成实时行情或投资建议。
- 不用 market data 证明收入、毛利、订单、市场份额、客户需求或基本面改善。
- 不把 13F 写成实时资金流、完整持仓或买卖压力。
- 不把 P33 capital feedback fixture 的 judgment material 伪装成 `market_valuation_analyst` runtime 已消费。
- 不让 writer 阶段自发补源。

## Runtime skill / registry 观察

Market skill 本身方向是对的：

- 要求从 `source_family_bundle.selected_source_families` 和 `assigned_task_card.relevant_requirements` 出发。
- 明确识别 market snapshot fields：event-window return、relative return、drawdown、volatility、volume、valuation multiple、snapshot id、as-of date。
- 明确要求 market reaction 只能作为 expectation context，不能证明 fundamentals。
- 明确 forbidden：不实时、不报目标价、不用市场数据证明收入/利润/现金流。

但 registry / data view 过窄：

- `market_valuation_analyst` 是 `inspect_only`，`allowed_tools=[]`。
- `allowed_data_views=["bounded_rows"]`。
- `source_families=["market_snapshot"]`。
- `multi_agent_runtime._bounded_rows_for_agent_data_view()` 对 market 节点只读取 `state.market_snapshot_rows` 和 `context_rows` 中 `source_family=market_snapshot` 的 rows。
- `capital_macro_pack` 只给 `fundamental_analyst`、`industry_supply_chain_analyst`、`risk_counterevidence_analyst`，不给 `market_valuation_analyst`。

结论：当前 Market Specialist 不是 Market / Capital / Price-in Specialist。它实际上只是 Market Snapshot Specialist。

## 数据资产实测

### Market snapshot coverage

`20260624_market_yahoo_chart_603_3m_v1` 覆盖本 case 13 个 tickers：

`NVDA, AMD, DELL, SMCI, HPE, TSM, ASML, AMAT, LRCX, KLAC, MU, 000660.KS, 005930.KS`

可用字段：

- `return_3m`
- `relative_return_vs_benchmark_3m`
- `max_drawdown_3m`
- `volatility_3m`
- `derived_signals`
- `as_of_date`
- `snapshot_id`

缺口：

- 所有 13 个 ticker 在该 pack 中均缺 `market_cap`、`enterprise_value`、`pe_ttm`、`ev_sales_ttm`、`ev_ebitda_ttm`。
- 该 pack 没有 event window rows。

代表性信号：

- AMD 3M return `1.52293`，relative vs benchmark `1.29337`，volatility `0.81438`。
- DELL 3M return `1.45404`，volatility `0.96340`。
- MU 3M return `1.62788`，relative vs benchmark `1.39831`，volatility `1.00509`。
- SMCI 3M return `0.48605`，max drawdown `-0.44628`，volatility `1.15255`。
- NVDA 3M return `0.14654`，relative vs benchmark `-0.08303`，volatility `0.41628`。

这些足以写 price action / momentum / volatility context，但不足以写估值高低、price-in 程度或 crowding。

### FMP valuation-enriched market pack

`20260528_market_yahoo_chart_full78_3m_fmp_valuation_v1` 只覆盖本 case 4 个 tickers：

- NVDA
- AMD
- AMAT
- MU

其中 NVDA / AMD 有估值字段和事件窗口：

- NVDA：`pe_ttm=32.29197`，`ev_sales_ttm=20.27638`。
- AMD：`pe_ttm=161.76661`，`ev_sales_ttm=21.58165`，并有 `valuation_premium_vs_peers` signal。

AMAT / MU 有 event-window / drawdown / volatility，但估值字段仍缺。

结论：估值增强资产存在，但覆盖窄，且与 2026-06-24 全覆盖 pack 没有统一成当前 case 的 valuation panel。

### 13F / ownership / capital rows

`capital_ownership_rows.jsonl` 对本 case 的 rows 数：

- NVDA: `59`
- AMD: `23`
- DELL: `10`
- SMCI: `6`
- HPE: `5`
- ASML: `5`
- AMAT: `9`
- LRCX: `4`
- KLAC: `16`
- MU: `17`

缺：

- TSM
- SK hynix `000660.KS`
- Samsung `005930.KS`

说明：

- 文件名虽然叫 ownership rows，但实际混合了 13F、capital structure、credit facility 等不同资本上下文。
- 13F rows 的 `claim_scope=lagged_ownership_context_only`，`not_realtime_flag=true`，不能写实时资金流或完整持仓。
- 非美 ticker 缺 13F 并不等于没有资本市场信息；只是当前 adapter 没有覆盖对应来源。

### CapitalMacroPack probe

我把 154 条本 case 资本/持仓 rows 输入 `build_capital_macro_pack(state)`：

- pack status: `pass`
- `input_row_count=154`
- `capital_structure_count=8`
- `debt_instrument_count=16`
- `credit_facility_count=22`
- `ownership_position_count=24`
- `rejected_object_count=0`

这个结果说明资本数据不是没有，也不是全不可用。问题是它没有进入 `market_valuation_analyst`，也没有按 five-chain price-in / crowding / capital-risk decision cells 投射。

### P33 capital-market feedback fixture

`p33_capital_market_feedback_fixture_v0_1.json` 已经证明过：

- `signal_count=14706`
- `graph_edge_count=4221`
- `judgment_material=42`
- 每个 covered ticker 有 7 类 judgment role：
  - secondary market capital flow
  - ownership and holder
  - credit funding
  - corporate action
  - liquidity and positioning
  - valuation price-in
  - derivatives market signal

本 case 覆盖：

- NVDA: 7 roles
- AMD: 7 roles
- DELL: 7 roles
- ASML: 7 roles
- SK hynix: 7 roles, 其中 ownership / corporate action 有 gap
- Samsung: 7 roles, 其中 ownership / corporate action 有 gap

缺：

- SMCI
- HPE
- TSM
- AMAT
- LRCX
- KLAC
- MU

结论：P33 capital feedback 是一个真实潜在优势，但仍是 fixture / runtime-alignment-only 资产。它没有成为当前 market specialist 的 source family，也没有覆盖全部五链条公司。

## Runtime data-view 实测

我构造最小 state：

- 13 个 case tickers。
- 17 条 market snapshot rows：13 条 2026-06-24 pack + 4 条 2026-05-27 FMP valuation pack。
- 154 条 capital / ownership rows。

调用 `build_agent_data_view("market_valuation_analyst", state)` 后：

- `view_status=pass`
- `bounded_rows=16`
- `by_source_family={"market_snapshot":16}`
- `has_capital_macro_pack=false`
- `selected_source_families=["market_snapshot"]`
- `context_only_source_families=["market_snapshot"]`
- `required_claim_slots_count=1`

关键问题：

- 154 条 capital / ownership rows 完全没有进入 market data view。
- `capital_macro_pack` 没有附给 market analyst。
- `market_snapshot` nested fields 经过 `_bounded_row()` 后主要压缩进 `summary`，`market_reaction`、`valuation_context`、`event_window` 不再是结构化可读字段。
- 17 条 market rows 进入后只剩 16 条；NVDA 的 2026-05-27 valuation-enriched row 被压掉，导致 bounded rows 里没有 NVDA valuation multiple。
- AMD 的 valuation row 保留在 summary 中，但结构化 `pe_ttm` / `ev_sales_ttm` 字段没有保留。

工程含义：即使源数据里有估值和事件窗口，market specialist 也只能从压缩 summary 文本中读到一部分；如果 summary 没包含某字段，就等同丢失。

## 本节点能写出的材料

在不补源、只使用当前 runtime 可见材料下，我可以写出以下 partial memolet：

1. AI/Semis 相关 ticker 在 2026-06-24 market snapshot 中普遍已经有强 price action：AMD、DELL、MU、SK hynix、HPE、AMAT、LRCX、KLAC 等 3M / YTD 表现很强，说明市场已经把部分 AI 基建叙事计入价格。
2. Server OEM proxy 的市场反应不等于利润质量：DELL 3M return 很强，SMCI volatility / drawdown 很高；这些支持“市场关注和波动率风险”，但不能证明 AI server gross margin。
3. HBM/memory 链条存在 momentum 与 volatility 双高：MU、SK hynix 的 3M / YTD 表现和波动率显示市场已交易 HBM super-cycle，但 runtime market row 不能证明 HBM-only margin。
4. Accelerator 的 price-in 不能只看 NVDA：NVDA 在该 snapshot 中 3M relative return 低于 benchmark，而 AMD 很强；这更像相对预期差和竞品追赶交易，而不是基本面强弱证明。
5. AMD 的旧 valuation-enriched row 可提示估值溢价：`pe_ttm=161.77`、`ev_sales_ttm=21.58`、`valuation_premium_vs_peers`，但这是 2026-05-27 as-of 的非实时 snapshot，不可当成当前估值。

不能写：

- 不可写实时股价、目标价、买卖建议。
- 不可写“机构正在买入 / 资金持续流入”。
- 不可写“高估值一定回撤”或“低估值安全”。
- 不可写完整 crowding，因为当前没有完整持仓集中度、主动/被动拆分、short interest、options positioning、borrow、flow 或 consensus revision。
- 不可把 price action 反推 revenue quality。

## 对用户问题的贡献

### Accelerator

可支持：

- NVDA / AMD 都有 market snapshot。
- AMD 有 valuation-enriched row，显示估值和事件窗口材料可用于 price-in risk。
- NVDA 2026-06-24 snapshot 显示 positive 3M return 但 relative underperformance，说明不能简单把 accelerator 说成“市场永远最强”。

缺：

- NVDA 的 valuation-enriched row 在 data-view selection 中被压掉。
- 没有 options / short / ownership concentration / consensus revision。

### Server OEM

可支持：

- DELL 3M return / volatility 很强，SMCI drawdown / volatility 高。
- 可写 demand proxy 受市场交易，但利润质量需另证。

缺：

- 当前 market specialist 看不到 DELL/SMCI/HPE 的 lagged ownership / capital structure pack。
- 没有 AI server margin 与 valuation bridge。

### Foundry / Packaging

可支持：

- TSM / ASML 都有 2026-06-24 market snapshot。
- ASML 有 P33 capital feedback covered roles。

缺：

- TSM 不在 P33 judgment material 覆盖内。
- 没有 CoWoS valuation / capacity / pricing / customer allocation 相关 price-in rows。

### HBM / Memory

可支持：

- MU / SK hynix / Samsung 有 market snapshot；MU 和 SK hynix price action / volatility 明显。
- SK hynix / Samsung 在 P33 feedback 有 valuation price-in / secondary market / derivatives role，但 ownership / corporate action 有 gap。

缺：

- MU 不在 P33 judgment material 覆盖内。
- 没有 HBM-only valuation bridge，也没有 analyst revision / consensus margin revision。

### Semicap

可支持：

- ASML / AMAT / LRCX / KLAC 都有 2026-06-24 market snapshot。
- AMAT 有旧 market event-window row。
- ASML 有 P33 capital feedback covered roles。

缺：

- AMAT / LRCX / KLAC 不在 P33 judgment material 覆盖内。
- 没有 AI-specific backlog / China exposure / export-control discount 与 valuation 的结构化桥。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | 能回答 market reaction / momentum / volatility 的一部分，不能完整回答 price-in / crowding / valuation risk。 |
| decision_surface_completeness | partial | 五链条都有 market snapshot，但估值、持仓、资本反馈覆盖不平衡。 |
| financial_and_operating_depth | fail_for_this_node | Market 节点不能证明基本面，只能与其它节点材料做 divergence。 |
| capital_market_price_in_depth | partial | 数据资产有，但 market data view 只看 market snapshot，不看 capital pack。 |
| source_grade_and_lineage | pass_with_boundary | market rows 有 snapshot/as-of/source boundary，13F rows 有 lag policy；但 data-view 会压缩嵌套字段。 |
| counter_thesis_and_turning_signals | partial | 可提示 momentum unwind / volatility / premium risk，不能形成完整 turning-signal watchlist。 |
| writer_readiness | partial | 可以给 writer 一段 price action context，但不能给完整 price-in matrix。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | Market input contract 很清楚，但过窄；资本市场问题需要 capital + market 联合合同。 |
| output_contract_quality | partial | SpecialistMemolet 结构可用，但缺 price-in cell schema。 |
| tool_affordance_fit | fail_for_price_in | 节点无工具权限且只接 market_snapshot，不能完成 price-in / capital feedback analysis。 |
| observability | pass | source_family_bundle / bounded_distribution 能看出只进了 market_snapshot。 |
| recoverability | partial | 可通过上游 projection 修复，但当前节点自己不能恢复。 |
| information_economy | partial | `_bounded_row()` 压缩后丢嵌套字段，节省输入但损失结构化估值/事件窗口。 |
| marginal_contribution | partial | 对 price action 有贡献；对资本市场完整 thesis driver 贡献不足。 |
| human_review_surface | partial | 能审 market rows，但不能审 capital feedback cells。 |
| product_value_over_single_agent | partial | 如果 capital feedback / ownership / valuation graph 不接入，优势不明显。 |

## Root Cause

本节点 root cause 不是“资本市场数据没有”，而是三层断点：

1. `market_valuation_analyst` 被设计成 market snapshot specialist，不是 capital / price-in specialist。
2. CapitalMacroPack / P33 capital feedback / 13F ownership rows 没有投射成五链条 price-in decision cells，也没有接入 market specialist。
3. `_bounded_row()` 对 market rows 的结构化字段保留不足，导致估值、事件窗口、market reaction 主要进入 summary 文本，后续模型可读性和可审计性下降。

## 需要的修复方向

1. 新增 `MarketCapitalDecisionSurfaceProjection`：
   - segment: Accelerator / Server OEM / Foundry-Packaging / HBM / Semicap
   - dimensions: price action, valuation premium, ownership positioning, liquidity/capital structure, derivatives/volatility, event-window reaction, gap
2. 拆分或升级 analyst：
   - `market_snapshot_analyst`: 只负责非实时 price action / volatility / event window。
   - `capital_positioning_analyst`: 负责 13F / holder / capital structure / credit / liquidity。
   - `price_in_risk_analyst`: 汇总 valuation premium、crowding、momentum unwind、what-would-change。
3. 让 `market_valuation_analyst` 至少接收 `capital_macro_pack_ref` 和 P33 `judgment_material` 的 bounded projection。
4. `_bounded_row()` 对 market rows 保留结构化字段：
   - `market_reaction`
   - `valuation_context`
   - `event_window`
   - `derived_signals`
   - `field_status`
   - `missing_fields`
5. 按 case ticker 和 five-chain segment 做 balanced selection，避免 valuation-enriched rows 被 summary-only / dedupe / max-row selection 压掉。

## 结论

Market / Capital / Price-in 是当前系统里“数据有，但能力没有组合起来”的典型例子。

如果只看现有 `market_valuation_analyst` runtime 约束，我能写出比边界声明更有用的 price action memolet，但写不出 WorkBuddy 式的 price-in / valuation / crowding 风险矩阵。真正的差距不在模型是否愿意分析，而在我们把资本市场数据资产拆成 market snapshot、capital macro pack、P33 fixture、ownership rows 后，没有给它们一个共同的 decision-surface output contract。
