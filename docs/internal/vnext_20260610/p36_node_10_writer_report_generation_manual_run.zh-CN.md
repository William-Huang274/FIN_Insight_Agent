# P36 Node 10 Writer / Report Generation 手工运行记录

日期：2026-07-09

## 节点定位

本节点模拟 Memo Writer 在 P36 AI 基建五链条 case 中的真实处境：writer 不能检索、不能打开 web、不能生成新事实，只能消费上游已经交付的 judgment material / MemoLogicPlan / bounded rows / typed gaps。

本轮仍遵守 P36 约束：

- 不调用 paid LLM。
- 不运行 true runtime full-chain。
- writer runtime 不允许自发补源。
- Codex supervisor 可以补源，但必须单独 ledger，不能伪装成 agent runtime 能力。
- 公开源补充只进入 `docs/project_os/p36_supervisor_source_supplement_ledger_v0_1.json`。

## Writer 可使用的 runtime 材料

严格按 Node01-09，writer 可使用的是：

1. Research Lead 的手工 thesis path / required items / source route plan，但它依赖 P35 decision surface 的 supervisor 手工注入，不是原生 runtime contract。
2. Node02 的 P34 accepted runtime rows、RAG / market / ownership 候选探针结论，但这些候选没有按 decision cell 晋升为 accepted runtime rows。
3. Node03 的 exact-value / parser 探针结论：基础财务 exact rows 可用，但 HBM-only、CoWoS、AI server margin、semicap AI-specific backlog 与 numeric sanity 仍不足。
4. Node04 的 graph / PIG / research graph / capital feedback 资产结论：资产丰富，但没有 `DecisionSurfaceGraphProjection`。
5. Node05-08 的 specialist 手工 memolet 与本地 runtime-like probes：可写 partial observations，不能当作线上 specialist pass。
6. Node09 的 Aggregate / JudgmentPlanner 结论：writer-safety、unsupported 排除、thesis path 可用，但没有五链条 `DecisionSurfacePack`。

Writer 禁止使用：

- `database_query`
- `live_web_snapshot`
- `retrieval`
- `new_fact_generation`
- 本节点临时补源

## Runtime-only writer 尝试

如果只用上述 runtime-allowed material，我可以写出一份边界正确的 bounded report：

- Accelerator / NVIDIA 方向有最强收入与毛利事实，但出口、capex digestion、price-in 仍是核心风险。
- Server OEM 是真实收入 + 利润质量分化，Dell/HPE 方向改善，SMCI 风险显著。
- Foundry / Packaging 里 TSMC 是高质量 bottleneck capture，但 CoWoS exact capacity/pricing/allocation 不足。
- HBM 很可能是强利润捕获环节，但 runtime rows 没有把 SK hynix / Samsung / Micron 作为完整 HBM peer panel 送到 writer。
- Semicap 公司质量强，但 AI-specific bookings / backlog / export mix 不完整，更多是 capex lag read-through。

但 runtime-only writer 不能稳定交付用户期望的 WorkBuddy-style five-chain decision matrix。原因不是 writer 文风，而是 writer 输入没有：

- 五链条 x 判断列的 `DecisionSurfacePack`。
- 每个 cell 的 key facts / source grade / numeric sanity / official-vs-estimate / cannot-infer。
- HBM / CoWoS / AI server margin / semicap peer panel 的 official source rows。
- price-in / valuation / ownership / crowding / derivative risk cells。
- risk-specific falsifier rows 与 `RiskMatrixPack`。

因此，runtime-only 输出应降级为 `bounded_partial_report`，不应被记为完整研究报告或 paid writer pass。

## Supervisor supplement

为完成用户可读研究报告，Codex supervisor 重新核验并记录了公开源补充：

- `docs/project_os/p36_supervisor_source_supplement_ledger_v0_1.json`

该 ledger 覆盖：

- NVIDIA Q1 FY2027 官方财报新闻稿。
- Dell Q1 FY2027 官方财报新闻稿。
- SMCI Q3 FY2026 官方财报新闻稿。
- HPE Q2 FY2026 官方 presentation。
- TSMC Q1 2026 earnings release / presentation。
- SK hynix Q1 2026 官方镜像。
- Samsung Q1 2026 官方新闻稿。
- Micron FQ3 2026 官方新闻稿。
- ASML / AMAT / LRCX / KLA 最新官方或官方镜像财报新闻稿。
- BIS 2026 对华半导体出口许可政策。

这些 source rows 是报告补源，不是 runtime evidence operator 输出，也不是 parser-promoted rows。

## 本节点产物

- Supervisor supplement ledger：
  - `docs/project_os/p36_supervisor_source_supplement_ledger_v0_1.json`
- P36 研究报告：
  - `docs/internal/vnext_20260610/p36_ai_infra_manual_writer_research_report.zh-CN.md`
- P36 dogfood 复盘报告：
  - `docs/internal/vnext_20260610/p36_codex_as_paid_model_dogfood_recap_report.zh-CN.md`

## 投研质量评估

| 维度 | runtime-only | supervisor-augmented |
|---|---|---|
| question_answerability | partial | pass_with_boundaries |
| decision_surface_completeness | fail_for_runtime | pass_for_report_not_runtime |
| financial_and_operating_depth | partial | pass_partial |
| capital_market_price_in_depth | partial | partial |
| source_grade_and_lineage | pass_for_runtime_boundary | pass_with_supplement_ledger |
| counter_thesis_and_turning_signals | partial | pass_partial |
| writer_readiness | partial | pass_for_manual_report |

## Agent 产品工程评估

| 维度 | 评估 | 说明 |
|---|---|---|
| input_contract_quality | partial | 上游有大量材料，但没有 report-first `DecisionSurfacePack` |
| output_contract_quality | partial | writer 能写 bounded memo，但完整矩阵依赖 supervisor supplement |
| tool_affordance_fit | pass_for_boundary | writer 禁工具正确；补源应在 writer 前完成 |
| observability | pass | Node01-10 和 supplement ledger 可追溯 |
| recoverability | partial | 缺口能定位到 source hunter / parser / selector / adjudicator，但不能局部重跑 writer 自动修复 |
| information_economy | partial | 多节点材料没有压成用户可扫的 cell matrix |
| marginal_contribution | partial | multi-agent 的治理价值存在，但产品价值仍被 DecisionSurfacePack 缺失压住 |
| human_review_surface | partial | 当前可 review 文档/claims，尚不能逐 cell accept/reject |
| product_value_over_single_agent | partial | 补源后报告可读，但补源不是 runtime 能力 |

## 根因判断

新增 root cause：

`RC-P36-030-writer-report-depends-on-supervisor-supplement-not-runtime-decision-surface`

具体表现：

1. Writer 的 no-source 边界正确，但上游没有交付完整 `DecisionSurfacePack`。
2. Runtime 有 RAG、SQL、market、ownership、PIG、graph、risk skill、aggregate safety，但没有把它们编译成 five-chain cells。
3. 公开源可得；问题是 source hunter / parser / source-route / specialist selector 没有把它们变成 accepted runtime rows。
4. Supervisor 可以写出较完整报告，但这证明的是产品目标形态，不是当前 runtime 能力。

## 下一步

进入 `node_11_verifier_workbench_review` 前，应先明确验证对象：

- 如果验证 runtime-only writer，则应判定 `bounded_partial_report`，不能 pass 完整研究报告。
- 如果验证 supervisor-augmented report，则 verifier 必须检查补源 ledger 分层，不得把 supplement rows 当 runtime accepted rows。
- Workbench review 粒度应提升到 decision cell：每个 cell 可标注 accepted / needs source hunter / needs parser / estimate-only / commercial gap。
