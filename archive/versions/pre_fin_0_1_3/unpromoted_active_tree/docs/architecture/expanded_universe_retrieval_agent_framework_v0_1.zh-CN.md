# 扩容后检索与多智能体架构执行文档 v0.1

本文档承接 `layered_data_source_expansion_execution_plan.zh-CN.md`。前一阶段已经把公司池从 full238 扩到 Tier1+Tier2 `603` 家，并开始重建 SEC 主披露、数值台账、市场快照、行业快照和 Milvus typed semantic recall。本阶段目标不是马上跑 full-chain，而是先把新增数据接入多智能体链路的节点、权限、上下文和门控重新定清楚。

## 当前数据资产状态

主证据：

- Tier1+Tier2 SEC full-source mixed evidence：`231842` rows，覆盖 `581` 个 ticker。
- BM25 evidence index：`231842` records。
- Object SQLite FTS：`7493637` records。
- Exact-value ledger：已验证 Tier1 full ledger `4810839` facts，Tier2 SEC ledger `392015` facts；combined `6789032` facts 是架构草案口径，本轮未在云端定位到可验证 DuckDB，使用前必须先定位或重建。
- S0 chunk audit：已通过；仍需关注长表格 chunk、少量 zero-overlap split pair 和部分 core item 缺口。

Milvus：

- 本地 1000-row smoke 已通过，BGE-M3 走 CUDA。
- 云端 full evidence build 已通过，`231842` evidence rows 生成 `662908` typed vectors。
- typed vector 分布：`narrative_chunk=231842`、`paraphrase_context=217709`、`table_chunk=107007`、`relationship_context=106350`。
- retrieval-only A/B 已完成：12-case `12/12` pass；exact lookup `2/2`、sector-depth `6/6`、relationship `2/2`、paraphrase `2/2`。
- expanded Object SQLite FTS baseline 已完成并接入 retrieval-only A/B：`20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3` 12-case `12/12` pass，ObjectBM25 enabled `12`，exact object metric hit `2/2`；旧的 empty `object_hybrid_v0_1/v0_2` 目录不能作为通过证据。
- Milvus 只作为 typed semantic recall layer，不替代 BM25、ObjectBM25 和 exact-value ledger。

市场：

- 603 个目标 ticker 和 SPY/QQQ 的 Yahoo 1Y 日线已下载。
- 标准化 market snapshot：`603` rows。
- market analytics：`603` rows。
- market evidence pack：`603` rows。
- Market catalog DuckDB 已生成。
- FMP key-metrics 小样本可用，但全量并发触发 429；当前不把 FMP 作为全量估值源，只保留为后续低速分批或 bulk/provider 替换任务。
- 非美本地交易所代码不能直接走 FMP free key，后续用当地交易所、公司披露或可合规 provider 补估值。

行业：

- EIA 快照已接入：`10315` observations、`2` evidence rows、无失败。
- FRED 快照已接入：`17435` observations、`21` evidence rows。
- FRED 仍有 `11` 个慢源缺口，主要是 DGS10、DGS2、BAA10Y、PCE、UMCSENT、WTI、Brent、Henry Hub、部分 PPI 和 30Y mortgage。缺口写入 metadata，不允许模型用记忆补。
- FRED+EIA merged 快照：`27750` observations、`23` evidence rows。

Workbench / source bundle：

- Profile/source bundle 已预留行业快照入口：`industry_evidence_path`、`industry_snapshot_db_path`、`industry_snapshot_id`、`industry_as_of_date`。
- Source readiness 会统计行业 evidence 的 source family、provider 和 as-of date。
- Data build step 支持 provider/source-family/series 过滤，方便把慢源作为缺口记录后继续推进。

当前云端门控状态：

- 扩容后 A2/S3 Evidence Operators 云端诊断已用 full combined ledger + 603-company market/industry 资产通过：`20260607_expanded_a2_cloud_full_combined_603_assets_operator_gate_v0_1`，`4/4` pass。
- 扩容后 A3/S4 Coverage / Reflection 云端诊断已用同一 full assets 通过：`20260607_expanded_a3_cloud_full_combined_603_assets_coverage_reflection_gate_v0_1`，`4/4` pass。
- A4/S5 Specialist 已在修复 stale relationship artifact root 后通过：`20260607_expanded_a4_cloud_full_combined_603_assets_specialist_gate_deepseek_v0_2`，`2/2` pass，real-evidence quality `2/2`。
- A5/S6-S8 Judgment/Memo/Verifier 已通过：`20260607_expanded_a5_cloud_full_combined_603_assets_judgment_memo_gate_deepseek_v0_1`，`2/2` pass，Verifier `2/2`。
- 当前结论仍限于 A2-A5 分层 gate；A6 10-20 case full-chain / multi-turn 未跑前，不能把 expanded path 设为默认 agent 主路径。

## 新的数据合同

### SEC 主披露

用途：

- 支持公司经营、风险、资本开支、现金流、收入、分部、订单、客户/供应商披露等主证据。
- 支持 narrative、table、paraphrase、relationship 四类 typed vector。

禁止：

- 不用 SEC narrative 推断实时股价、新闻或市场一致预期。
- 不把行业暴露写成真实客户/供应商。

### Exact-value ledger

用途：

- 数值型问题优先查 ledger，例如 capex、credit provision、revenue、margin、cash flow、R&D、segment revenue。
- Specialist 和 Memo Writer 只能消费已选出的 ledger rows，不直接扫全库。

禁止：

- 没有单位、period、ticker、form/source 的数值不能进入最终 claim。
- 百分比、金额、增长率不能混排后让模型自行猜字段。

### 市场快照

用途：

- 支持非实时价格、收益率、相对收益、成交量、market reaction 和有限 valuation context。
- 当前主要可靠字段是 price/return/volume；估值字段 coverage 暂不足。

禁止：

- 不作为公司基本面事实。
- 不生成价格目标、实时行情、投资建议。
- FMP 全量估值未通过前，不要求 market specialist 产出完整估值倍数观点。

### 行业快照

用途：

- 支持利率、信用、消费、能源、材料、住房、电力等行业上下文。
- Industry Specialist 可用行业 evidence 解释外部环境如何影响公司披露中的经营变量。

禁止：

- 不覆盖公司披露事实。
- 缺失的 FRED series 必须作为 source gap，不允许模型凭常识补。

### 关系图谱

用途：

- 支持研究范围、上下游假设、行业传导链、同行/供应商/客户候选。
- direct customer/supplier、partner、contract、sector exposure、inferred economic link 必须分开。

禁止：

- 不把 `customer concentration`、地理市场、行业暴露、云泛称写成 named customer/supplier。
- 未被 verified edge 支持的关系只能写成 hypothesis，不能写成事实。

## 节点调整

### 1. `resolve_universe_scope`

输入：

- 用户 query。
- ticker、公司名、别名、CIK、非美本地代码、ADR/local symbol 映射。
- Tier1/Tier2 manifest。

输出：

- `focus_entities`：用户真正问的公司。
- `search_universe`：允许检索的公司池。
- `provider_symbols`：Yahoo/FMP/非美 provider symbol。
- `entity_resolution_warnings`：别名冲突、share class、ADR/local 不一致。

门控：

- query 中明确公司不能丢。
- 不能把 ADR 和本地上市主体混成一个没有来源边界的实体。

### 2. `build_retrieval_intent_plan`

输入：

- query、会话上下文、resolved universe。

输出：

- `intent_types`：exact-value、filing narrative、relationship、market、industry、semantic/paraphrase、multi-turn follow-up。
- `primary_routes`、`supporting_routes`、`conditional_routes`。
- `source_gap_policy`。

门控：

- exact-value 问题必须优先 ledger/ObjectBM25，不先走大范围 semantic。
- market/industry 只有 query 有价格、收益率、估值、行业、宏观、能源、电力、利率等意图才激活。
- sector-depth 不能默认启动所有专家，要区分 primary / supporting / conditional。

### 3. `relationship_graph_expand`

输入：

- focus/search universe。
- relationship edge store。
- sector-depth pack。
- 用户关系意图。

输出：

- `relationship_edges`：已验证关系边。
- `economic_link_map`：经济传导假设。
- `relationship_scope_rationale`：为什么扩展这些公司。
- `relationship_gaps`：需要外部供应链、新闻、官网、海关或商业数据库补的缺口。

门控：

- direct edge 必须有 source text 和 confidence。
- inferred link 必须显式标注为 hypothesis。
- Industry Specialist 在 relationship case 下必须看到并引用 relationship evidence。

### 4. `execute_evidence_operators`

输入：

- retrieval intent plan。
- source inventory。
- route budget。

输出：

- SEC BM25 rows。
- ObjectBM25 / SQLite FTS rows。
- exact ledger rows。
- Milvus semantic rows。
- market rows。
- industry rows。
- relationship rows。
- runtime ledger。

门控：

- BM25/ObjectBM25/exact ledger 是可验证主路径；Milvus 是补召回，不是唯一证据。
- Milvus route 必须带 typed filter：`narrative`、`table_chunk`、`paraphrase`、`relationship`。
- exact lookup 命中率不能因为 Milvus 接入下降。
- runtime ledger 必须记录每个 operator 的输入、输出行数、过滤条件、失败原因和耗时。

### 5. `evidence_fusion_selector`

输入：

- 各 route rows。
- query intent。
- Specialist task-card。

输出：

- 面向各 specialist 的 row bundle。
- shared context digest。
- coverage / source gap 摘要。

门控：

- 不再把所有 rows 平均塞给所有专家。
- Fundamental：ledger + SEC table/narrative 优先。
- Market：market evidence + 少量 SEC context。
- Industry：relationship + industry + SEC operating context。
- Risk：risk/counterevidence rows + 相关行业/市场 context。
- 每个 bundle 必须有 source-family 分布诊断。

### 6. `specialist_dispatch`

输入：

- activation plan。
- specialist task-card。
- row bundle。
- shared context。

输出：

- ClaimCard。
- unsupported / conflict / source gap。
- confidence。

门控：

- Specialist 不能自己调工具。
- ClaimCard 必须包含 source refs、claim type、support strength、limits。
- market/industry context 只能支持 context claim，不得写成公司披露事实。

### 7. `judgment_aggregator`

输入：

- Specialist ClaimCards。
- coverage / gap。
- verifier pre-check。

输出：

- `memo_thesis_plan`。
- thesis slots：核心判断、支持证据、反证风险、缺口、下一步验证。

门控：

- 不把 Specialist 的证据摘要直接拼成 memo。
- 没有足够证据的 thesis slot 必须降级为 bounded observation 或 source gap。

### 8. `memo_writer`

输入：

- `memo_thesis_plan`。
- 已验证 ClaimCards。
- source boundary。
- response language/profile。

输出：

- 面向用户的中文或英文投研回答。

门控：

- 结构要像投研结论，不像证据清单。
- 数值必须来自 ClaimCard 或 ledger row。
- 对 coverage 不足的地方要讲清楚为什么不能下结论。

### 9. `verifier_quality_gate`

输入：

- memo draft。
- ClaimCards。
- source boundary。
- runtime ledger。

输出：

- pass / repair / bounded block。
- unsupported claim 列表。
- source misuse 列表。

门控：

- 不只检查“有没有乱说”，也检查“有没有把核心问题答出来”。
- market、industry、relationship 的 source boundary 违反时必须 repair。
- 多轮上下文引用必须能回到当前或前轮通过 gate 的 artifact。

## Role-specific skill vNext

### Research Lead

要学会：

- 判断问题是不是只需要 focused answer、standard memo、expanded memo 或 deep research。
- 区分 primary/supporting/conditional agent。
- 把市场、行业、关系、Milvus 作为有成本的数据源，而不是全量启动。
- 对 source gap 给出路线，而不是硬编答案。

### Universe / Relationship

要学会：

- 用 edge schema 区分 direct、partner、contract、exposure、inferred link。
- 给出关系扩展的商业理由。
- 把没有外部数据支持的客户/供应商关系保持为假设。

### Fundamental Specialist

要学会：

- ledger-first。
- 处理 period、单位、currency 和 value role。
- 把数字转成经营判断，而不是列数。

### Market Specialist

要学会：

- 使用 snapshot 的 as-of date。
- 区分价格表现、相对收益、成交量和估值字段缺失。
- 不做价格目标和实时行情。

### Industry / Supply-chain Specialist

要学会：

- 同时消费 relationship evidence、industry snapshot 和 SEC operating evidence。
- 解释行业变量如何传导到公司变量。
- 在关系证据不足时明确说只能支持传导假设。

### Risk Specialist

要学会：

- 找反证，不重复 Fundamental 的支持性证据。
- 把行业/市场波动作为风险 context，不当作公司事实。

### Memo Writer

要学会：

- 先写 thesis，再组织证据。
- 对证据强的点下判断，对证据薄的点做限定。
- 输出中文时使用自然中文，不把 JSON 字段机械翻译出来。

## 分阶段门控

### A0 数据资产门控

通过条件：

- SEC mixed S0 chunk audit pass。
- market snapshot validation pass。
- industry merged snapshot 有 observations/evidence rows，失败源写 metadata。
- Milvus build 完成后能出 retrieval-only A/B 报告。

### A1 路由门控

通过条件：

- exact、market、industry、relationship、sector-depth、multi-turn cases 的 agent 激活符合预期。
- 不再粗暴全量激活所有 Specialist。
- route ledger 记录 primary/supporting/conditional。

### A2 检索门控

通过条件：

- exact lookup ledger 命中率不下降。
- BM25/ObjectBM25/BGE/Milvus 各自有可解释输入输出。
- Milvus 在 sector-depth / relationship / paraphrase case 提升 usable evidence rows，但不污染 exact case。

### A3 上下文门控

通过条件：

- Specialist row bundle 的 source-family 分布符合角色任务。
- shared context 可复用，且不会把上一轮过期范围带入新问题。
- market/industry/relationship rows 进入对应 Specialist，而不是被 data view 截断。

### A4 Specialist 门控

通过条件：

- 每个 Specialist 能把上游任务转成 ClaimCard。
- ClaimCard 至少包含 claim、supporting refs、limits、confidence。
- relationship case 下 Industry Specialist 必须引用 relationship evidence。

### A5 Memo/Verifier 门控

通过条件：

- Memo 是 thesis-led 投研回答，不是 evidence list。
- Verifier 同时检查 factuality、source boundary、answer completeness。
- 中文输出自然，数值不漂移。

### A6 Full-chain 门控

通过条件：

- 单轮：exact、focused、standard、expanded、sector-depth 都过。
- 多轮：上下文继承、范围变化、预算控制都过。
- runtime ledger 可解释每个 node / agent 为什么激活、输入是什么、输出是否有效。

## 下一步执行顺序

1. ~~重建 expanded ObjectBM25 / SQLite FTS 可用的结构化对象 baseline，补 exact/metric retrieval 对照。~~ 已由 `20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3` 完成 retrieval-only diagnostic gate。
2. ~~把 market/industry merged artifacts 写入 source inventory，保持 context-only source boundary。~~ 已由 `248_market_industry_source_inventory_context_boundary.md` 完成；`market_snapshot` / `industry_snapshot` 只通过 `available_source_families` 和 `source_boundaries` 暴露，不混入 SEC filing coverage 计数。
3. ~~更新 `execute_evidence_operators`，加入 Milvus typed semantic route 和 market/industry expanded catalog path。~~ 已由 `249_execute_evidence_operators_milvus_and_expanded_catalog_paths.md` 完成到 runtime contract / wiring / diagnostic gate；`milvus_semantic` 是显式补召回 route，不是默认 exact/ledger 路径。
4. ~~更新 Evidence Fusion Selector，让不同 Specialist 看到不同 source-family bundle。~~ 已由 `250_evidence_fusion_selector_source_family_bundles.md` 完成到 data-view / Specialist prompt contract；`milvus_semantic` bounded rows 只作为 typed SEC semantic recall supplement，不能单独证明 exact value。
5. ~~更新 Research Lead prompt/skill，让它按成本和问题类型选择 route。~~ 已由 `251_research_lead_cost_aware_route_selection.md` 完成到 prompt / skill / route metadata contract；每条 evidence requirement 保留 `route_selection_reason`、`route_cost_tier` 和 `route_selection_policy`。
6. ~~更新 Specialist skill vNext，特别是 Market 和 Industry 的 source boundary。~~ 已由 `252_specialist_market_industry_source_boundary_vnext.md` 完成到 Market / Industry skill 和 Specialist prompt contract；Specialist 必须先用 `source_family_bundle` 执行 selected/context-only/forbidden-claim 边界。
7. ~~先跑 A1-A5 分层 gate，不直接跑 full-chain。~~ 当前状态：`253_expanded_a1_a5_local_layered_gate_and_cloud_blocker.md` 完成 local full238 A1-A5 regression；`255_expanded_cloud_full_combined_603_assets_a2_a5_gate.md` 完成 true expanded cloud A2-A5 layered gate，full combined ledger / 603 market / merged industry 产物均已进入云端 gate。
8. 只有分层 gate 通过后，跑 10-20 case full-chain / multi-turn。当前下一步就是 A6 小批 full-chain / multi-turn expanded gate。

## 当前必须记录的缺口

- FMP 全量估值暂不可用：并发会触发 429，非美本地代码 free key 不支持。
- FRED 若干关键 series 下载慢，当前 merged 快照保留缺口，不允许模型补写。
- 非美官方披露 parser 仍未完全接入：DART/EDINET 需要 key，MOPS/HKEX/CNINFO 需要 profile-specific downloader/parser。
- 关系图谱仍主要来自 SEC 披露；真实外部供应链数据库、新闻、官网 partner/customer 页和海关数据尚未进入主证据。
- Milvus retrieval-only gate 已过，operator contract 已接入 expanded cloud A2-A5；但 A6 full-chain / multi-turn 尚未跑，不能直接设为默认 agent 主路径。
