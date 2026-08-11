# P36 Codex-as-Paid-Model Manual Full-Chain Dogfood Execution

日期：2026-07-09

## 目标

本轮不是调用 paid DeepSeek，也不是绕开系统直接写报告，而是由 Codex 亲自扮演“强模型执行体”，按 FIN_Insight_Agent 的现有 agent 链路逐节点完成一次可审计的手工 full-chain dogfood。

核心问题仍是：

> AI 基建需求是否真实转化为 accelerator、server OEM、foundry / packaging、HBM、semicap 公司的高质量收入和利润？哪些链条已有证据，哪些只是 demand proxy，哪些存在 margin dilution、supply bottleneck、capex digestion、export control 或 price-in 风险？

## 强约束

- 不调用 paid LLM API。
- 不把本轮记为 true runtime full-chain pass。
- Codex 可以作为强模型亲自写每个节点的中间材料。
- Writer 阶段不能自发补源。
- Codex 作为 supervisor 可以补源，但补源必须进入单独 supplement ledger，不能伪装为 agent runtime 能力。
- 每个节点评价必须同时使用投研质量尺和 agent 产品工程尺。
- 每个节点必须记录：读了哪些 prompt / skill / graph / runtime artifacts，拿到什么输入，允许什么工具，禁止什么动作，实际能不能写出合格材料。

## 标尺

机器可读标尺：

- `docs/project_os/p36_agent_dogfood_ruler_v0_1.json`

两把尺：

1. Research Quality Ruler：看节点是否推动合格投研判断。
2. Agent Product Engineering Ruler：看节点作为 agent 产品组件是否有存在价值。

## 执行顺序

1. `node_01_research_lead`
2. `node_02_retrieval_rag_sql_source_route`
3. `node_03_parser_evidence_operator`
4. `node_04_graph_relationship_value_capture`
5. `node_05_fundamental_specialist`
6. `node_06_industry_product_specialist`
7. `node_07_capital_market_specialist`
8. `node_08_risk_counterevidence_specialist`
9. `node_09_aggregate_judgment_planner`
10. `node_10_writer`
11. `node_11_verifier_workbench_review`

## 节点产物规则

每个节点至少落以下内容：

- node input snapshot
- prompt / skill / runtime artifact refs
- allowed tools / forbidden actions
- Codex-as-paid-model node output
- missing evidence / weak input
- research-quality score
- agent-product-engineering score
- root-cause notes
- repair suggestions

## 补源规则

补源分三类：

1. `runtime_available`: 现有 runtime / RAG / SQL / source-route rows 已可用。
2. `runtime_missing_supervisor_supplement`: Codex supervisor 通过公开源补到，但 runtime 没有自动拿到。
3. `commercial_or_unavailable_gap`: 需要商业数据库、受限数据或不可公开取得。

任何 `runtime_missing_supervisor_supplement` 不得写成现有 agent 能力；只能作为对 source hunter / parser / ingestion 的修复需求。

## 当前状态

- `node_01_research_lead` 至 `node_11_verifier_workbench_review` 已完成手工记录。
- Node10 产出 runtime-only writer 边界判断、supervisor supplement ledger、supervisor-augmented 研究报告和 dogfood 复盘报告。
- Node11 已审查 verifier / Workbench 边界：runtime-only writer 只能 bounded partial；supervisor-augmented report 可作为人工可读报告，但不证明 runtime 能力；现有 verifier / Workbench 可审 claim / evidence ref / source boundary / gap / artifact，但缺 `decision_surface_cell` 级 review surface。
- 当前禁止把 P36 误记为 paid LLM run、true runtime full-chain pass、source ingestion closeout、parser promotion closeout、model comparison 或 release eval。
- 下一步只允许 no-paid deterministic repair fixtures：`DecisionSurfaceContract`、`SourceHunterLoop`、official IR/parser、supplement-ledger-to-runtime-row、Product/Industry projection、Market/Capital projection、RiskMatrixPack、DecisionSurfacePack-to-MemoLogicPlan 和 Workbench cell-review replay。

## 未运行

- paid DeepSeek / paid LLM
- true runtime full-chain
- model comparison
- case expansion
- release eval
