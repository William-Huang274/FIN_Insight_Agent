# P36 Node 09 Aggregate / Judgment Planner 手工运行记录

日期：2026-07-09

## 节点定位

本节点模拟 `aggregate_judgment_plan` / `JudgmentState` / `MemoLogicPlan` 这一层在 P36 AI 基建 case 中的真实作用。

本轮仍遵守 P36 约束：

- 不调用 paid LLM。
- 不运行 true runtime full-chain。
- Codex 手工扮演强模型，逐节点判断输入、工具、prompt/skill、合同和输出是否足够。
- writer runtime 不允许补源。
- supervisor 可以补源或做本地 probe，但必须单独记录；本节点没有新增外部补源，只做本地 deterministic probe。

## 本节点读取的运行时代码和文档

- `src/sec_agent/multi_agent_contracts.py`
  - `aggregate_specialist_judgment_plan(...)`
  - `verify_specialist_outputs_for_memo(...)`
  - `attach_judgment_state(...)`
  - `_memo_thesis_plan_from_claims(...)`
  - `_memo_thesis_pack_from_claims(...)`
  - `_thesis_driver_pack_from_claims(...)`
  - `_dimension_sections_from_claims(...)`
  - `_analysis_dimension_for_claim(...)`
  - `_judgment_cards_from_claims(...)`
  - `_thesis_path_from_judgment_cards(...)`
- `src/sec_agent/memo_logic_plan.py`
  - `build_memo_logic_plan(...)`
  - `validate_memo_logic_plan(...)`
- `src/sec_agent/langgraph_orchestrator.py`
  - `_memo_logic_plan_judgment_state_input(...)`
  - lead targeted repair context claim projection
- `src/sec_agent/prompts/skills/judgment_plan_aggregation_skill_v0_1.md`
- `scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py`
- `tests/test_multi_agent_judgment_memo_verifier.py`
- `tests/test_memo_logic_plan.py`
- `tests/test_p33_aggregate_judgment_plan_runner.py`

## 当前聚合层真实能力

### 已有能力

当前聚合层不是简单摘要器。它已经具备几项重要能力：

1. 将 specialist memolets 归一成 `supported_claims`、`unsupported_claims`、`conflicts`。
2. 对 ClaimCard 做 rank / memo-readiness / source-family / analyst-depth 标注。
3. 生成 `memo_outline`、`memo_thesis_plan`、`memo_thesis_pack`、`thesis_driver_pack`。
4. 生成 `judgment_cards` 和 `thesis_path`，要求 writer 按“judgment -> evidence bridge -> business mechanism -> financial bridge -> counter-read -> what would change”写，而不是 dump ClaimCards。
5. `verify_specialist_outputs_for_memo(...)` 会阻止 unsupported specialist claims 进入 memo。
6. `MemoLogicPlan` 明确禁止 writer 使用：
   - `database_query`
   - `live_web_snapshot`
   - `retrieval`
   - `new_fact_generation`

这说明 writer 不得自发补源不是缺陷，而是当前架构已经明确写进合同的正确边界。

### 关键限制

当前聚合层的天然组织方式仍是通用 memo/agent 维度：

- `thesis`
- `fundamentals`
- `product_technology`
- `industry_relationship`
- `market_valuation`
- `risk_counterevidence`

进入 `JudgmentState` 后又投射成通用分析维度：

- `fundamentals`
- `product_and_production`
- `capital_and_financing`
- `competition_and_market_position`
- `industry_supply_chain`
- `risk_and_counterevidence`
- `evidence_gap`

这套结构适合防止 writer 越界，也适合写通用投资 memo；但它不是 P36 这道题需要的决策表面。P36 需要的是：

- 五条链：Accelerator、Server OEM、Foundry/Packaging、HBM、Semicap。
- 每条链若干判断格：收入证据、利润质量、供给瓶颈、margin dilution、capex digestion、export control、price-in。
- 每个格子都要有结论、关键数字、source grade、是否官方、是否估算、numeric sanity、反证和 what-would-change。

当前聚合层没有把这些 cell 当成一等 schema。

## 本地 probe A：手工构造高质量 specialist ClaimCards

我手工构造了一组符合当前 memolet 合同的 specialist 输出，模拟 Node05-08 能给出的较好材料：

- Fundamental:
  - Accelerator 有最强直接收入证据，但仍受 margin sustainability / customer capex digestion 约束。
  - Server OEM 是 demand proxy，top-line 不能自动证明高质量利润捕获。
  - HBM 有高质量 economics 假设，但 HBM-only revenue / margin rows 不稳定。
- Product / Industry:
  - Accelerator / HBM / Foundry-Packaging 更接近 Real Demand。
  - Server OEM 更像 assembly-throughput proxy。
  - Semicap 是真实但滞后的 capex-cycle pull-through。
- Market:
  - Accelerator / HBM 领导者存在 price-in 风险。
- Risk:
  - capex digestion、export control、server OEM margin dilution、supply bottleneck、price-in 是主要 falsifiers。

### Probe A 输出摘要

聚合器输出：

- `judgment_status=partial`
- `memo_writer_allowed=true`
- `verification_status=pass`
- `supported_claim_count=9`
- `unsupported_claim_count=1`
- `memo_outline` 支持 `thesis / fundamentals / product_technology / industry_relationship / market_valuation / risk_counterevidence`
- `thesis_driver_dimension_ids` 变成：
  - `fundamentals`
  - `product_and_production`
  - `capital_and_financing`
  - `competition_and_market_position`
  - `industry_supply_chain`
  - `risk_and_counterevidence`
  - `evidence_gap`
- `MemoLogicPlan.writer_forbidden_tools` 正确包含 `database_query / live_web_snapshot / retrieval / new_fact_generation`
- `required_item_answer_plan` 能保留我手工给出的五条链 required items
- 但 `MemoLogicPlan.validation.status=fail`，错误是：
  - `product_section_missing_product_reasoning_frame`

### Probe A 结论

只要给它质量较好的 ClaimCards，当前聚合层能保护 writer、保留风险和缺口，并生成较好的通用 writer plan。

但它不会自然生成五链条 evidence-quality matrix。required items 可以被携带，但它们只是 `required_item_answer_plan`，不是最终 report 的主表面。writer 仍需要自己从通用 dimension moves 里推回用户的五链条矩阵，这会把关键任务压到 writer 表达层。

这解释了为什么最终输出容易变成边界声明：聚合层没有先做“决策格裁决”，writer 收到的是通用维度和缺口，而不是每个 cell 的可写结论。

## 本地 probe B：强行注入五链条 `analysis_dimension`

我进一步构造 ClaimCards，把 `analysis_dimension` 显式写成：

- `chain_accelerator`
- `chain_server_oem`
- `chain_foundry_packaging`
- `chain_hbm`
- `chain_semicap`

目的是测试当前聚合层是否能接受 case-specific dimension。

### Probe B 输出摘要

结果：

- `status=pass`
- `memo_writer_allowed=true`
- `MemoLogicPlan.validation.status=pass`
- 但 `dimension_sections` 没有保留 `chain_*`，仍被归一为：
  - `product_and_production`
  - `capital_and_financing`
  - `competition_and_market_position`
  - `industry_supply_chain`
  - `risk_and_counterevidence`
  - `evidence_gap`
- `memo_logic_sections` 也仍然是同一组通用维度。

### Probe B 结论

当前 `_analysis_dimension_for_claim(...)` 和 ClaimCard depth annotation 会把输入重新归类到硬编码的通用分析维度。也就是说，即使上游 specialist 有意识地写出五链条 claim，聚合层也会把它们折叠回通用维度。

这不是 writer 文风问题，也不是模型没努力；这是合约层没有保留 case-specific decision surface。

## 投研质量评估

### 通过项

- 能保留 supported / unsupported / conflict，不会让 unsupported claims 进入主 memo。
- 能为 writer 生成 thesis path、judgment cards、source boundary 和 what-would-change。
- 能明确禁止 writer 自己补源。
- 能把通用投资 memo 的结构整理到比 raw evidence 更可写的状态。

### 不足项

- 没有五链条 x 判断列的 matrix。
- 没有链条 ranking / evidence quality ranking。
- 没有 Real Demand vs Demand Proxy 的结构化分类字段。
- 没有每个 cell 的 source grade、official / estimate / commercial gap / numeric sanity check 字段。
- 没有把 price-in / valuation / ownership / capital feedback 变成按链条归属的风险格。
- 没有把 HBM / CoWoS / AI server margin / semicap backlog 的缺口组织成可补源任务和 writer-visible bounded conclusion。
- `MemoLogicPlan` 可以携带 required items，但它不负责 adjudicate required items 的答案质量。

### 对 WorkBuddy 对比的含义

WorkBuddy 的优势不是它更“严谨”，而是它先产出用户能看懂的 decision surface，然后再加边界。

我们当前聚合层更像“证据治理和 writer 安全层”。这有必要，但如果缺少 `DecisionSurfaceAdjudicator`，用户看到的就会是治理痕迹多、主判断少。

因此，我们的优势不能只是 lineage / graph / RAG / SQL 存在；必须把这些能力投射成每个决策格的强弱判断、可写结论、反证和补源路线。

## Agent 产品工程评估

| 维度 | 评估 | 说明 |
|---|---|---|
| input_contract_quality | partial | specialist memolet 合同清楚，但没有 `decision_surface_cell_id` / `chain_segment_id` |
| output_contract_quality | partial | 通用 memo 输出很强，P36 case-specific output 不足 |
| tool_affordance_fit | pass_for_writer_safety | writer 禁工具正确；aggregate 本身不应补源 |
| observability | pass | supported / unsupported / conflict / judgment cards / memo logic plan 都可审计 |
| recoverability | partial | required item 可以保留，但不能定位到每个 decision cell 的修复动作 |
| information_economy | partial | 能压缩 evidence，但会把 cell 信息折叠成通用维度 |
| marginal_contribution | partial | 相比 single-agent，强在安全和可追溯；弱在决策面表达 |
| human_review_surface | partial | reviewer 可看 ClaimCards/JudgmentCards，但不能直接审 five-chain matrix |
| product_value_over_single_agent | partial | 需要 DecisionSurfacePack 才能明显超过联网 single-agent |

## 根因判断

本节点新增的核心 root cause：

`RC-P36-029-aggregate-judgment-planner-preserves-claims-but-not-decision-surface-adjudication`

具体表现：

1. `aggregate_specialist_judgment_plan(...)` 以通用 memo slots 和 analysis dimensions 为中心，而不是以用户题面的 decision cells 为中心。
2. ClaimCard 没有一等字段表示：
   - `decision_surface_id`
   - `chain_segment_id`
   - `decision_cell_id`
   - `evidence_quality_grade`
   - `real_demand_vs_proxy`
   - `value_capture_rank`
   - `numeric_sanity_status`
   - `source_authority_grade`
   - `cell_conclusion`
3. `_analysis_dimension_for_claim(...)` 会把 case-specific chain dimension 折叠为通用维度。
4. `MemoLogicPlan` 的 `required_item_answer_plan` 能提示 writer 回答问题，但它不是裁决表；无法防止 writer 把 required items 变成零散段落。
5. `product_reasoning_frame` 缺失时会导致 validation fail；它应该由上游 Product/DecisionSurfaceProjection 自动生成，而不是依赖手工注入。
6. 当前聚合层保留 gap，但没有把 gap 绑定到“哪条链、哪个格子、缺哪个源、下次补源优先级”的结构化修复 surface。

## 该节点能否写出高质量材料

在当前约束下，我能写出一份边界正确、结构完整的通用投研 memo plan；但不能仅靠当前 aggregate 输出稳定写出用户预期的 WorkBuddy-style 决策矩阵。

如果 supervisor 手工补一个 `DecisionSurfacePack`，我可以写出高质量报告；但那是 supervisor 能力，不是当前 agent runtime 能力。

## 修复方向

### 必须新增的中间产物

新增 `DecisionSurfacePack`，位置应在 specialist outputs 之后、MemoLogicPlan 之前：

```text
specialist memolets
  -> AggregateJudgmentPlan
  -> DecisionSurfaceAdjudicator
  -> DecisionSurfacePack
  -> MemoLogicPlan
  -> Memo Writer
```

`DecisionSurfacePack` 最小字段：

- `case_id`
- `surface_type=ai_infra_supply_chain_quality`
- `chain_segments`
  - `accelerator`
  - `server_oem`
  - `foundry_packaging`
  - `hbm`
  - `semicap`
- `decision_cells`
  - `revenue_evidence`
  - `profit_quality`
  - `supply_bottleneck`
  - `margin_dilution`
  - `capex_digestion`
  - `export_control`
  - `price_in`
- 每个 cell：
  - `cell_conclusion`
  - `evidence_refs`
  - `source_families`
  - `official_source_count`
  - `estimate_or_proxy_count`
  - `numeric_sanity_status`
  - `bounded_gap_refs`
  - `confidence`
  - `claim_boundary`
  - `what_would_change`
- 汇总层：
  - `evidence_chain_ranking`
  - `real_demand_vs_proxy_classification`
  - `top_counter_thesis`
  - `turning_signals`
  - `writer_matrix_rows`

### 需要修改的合同

1. Specialist output schema 允许并鼓励输出 `decision_surface_cell_refs`。
2. Aggregator 不应覆盖 case-specific surface fields。
3. `MemoLogicPlan` 应把 `DecisionSurfacePack` 作为 writer allowed input。
4. Writer 首屏必须先写 `DecisionSurfacePack.writer_matrix_rows`，再写通用 thesis path。
5. Verifier 增加 gate：
   - 用户问题要求 matrix / ranking / proxy classification 时，缺 `DecisionSurfacePack` 则阻止 paid writer 或降级为 bounded answer。

### 需要的 deterministic tests

- `test_aggregate_preserves_decision_surface_cell_refs`
- `test_decision_surface_pack_builds_five_chain_matrix_from_specialist_claims`
- `test_memo_logic_plan_projects_decision_surface_pack_to_writer_skeleton`
- `test_writer_forbidden_to_create_new_decision_cells_without_pack_refs`
- `test_p36_ai_infra_surface_gate_blocks_generic_dimension_only_plan`

## 对 multi-agent 价值的判断

当前 aggregate 层证明 multi-agent 不是完全无意义：它已经能做 single-agent 很难稳定做到的 ClaimCard 治理、unsupported 排除、writer 禁工具、source boundary 和 thesis path。

但它还没有把这些治理优势转成用户可见的商业价值。真正的产品价值应该是：

- 单 agent：能快速联网讲一个 70-80 分故事，但 lineage、numeric sanity 和 replayability 不稳定。
- 我们：应该先生成同样直观的 decision surface，再在每个 cell 上提供 source-grade、lineage、numeric sanity、graph/path、typed gaps 和补源计划。

如果没有 `DecisionSurfacePack / Adjudicator`，multi-agent 就容易退化成更复杂的 DAG；有了它，multi-agent 才能把 RAG、SQL、图谱、parser、capital data、risk specialist 的差异化投射到报告主干。

## 下一步

进入 `node_10_writer_report_generation_manual_run`：

1. 明确 writer 不能补源。
2. 用 Node01-09 已有材料作为 runtime-allowed input。
3. 如发现材料不足以写出合格研究报告，由 Codex supervisor 单独补源并另建 supplement ledger。
4. 最终报告必须分清：
   - runtime materials can support
   - supervisor supplement used
   - current agent runtime gaps
   - product/engineering repair backlog
