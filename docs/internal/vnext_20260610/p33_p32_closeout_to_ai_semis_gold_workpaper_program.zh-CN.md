# P33 P32 Closeout -> AI/Semis Gold Workpaper Execution Program

日期：2026-07-05

## 1. 定位

P33 是 P32 之后的执行程序，不是新的学习资料收集阶段。

P32 已经把金融研究方法和 agent 工程模式做成了 learning ledger、L2 extraction、L3 contract translation、L4 no-paid deterministic fixture 和 registry promotion gate。P33 的任务是把这些合同从“证明过的设计”收敛成一个真正可用的 AI/Semis analyst workpaper 闭环。

核心目标：

1. 先把 P32 的五个 deferred contracts 逐个用 no-paid deterministic fixture 证明或退回。
2. 再把已证明合同接入 Research Lead、ContextEngine、ProductIntelligenceGraph、JudgmentCard、MemoLogicPlan、Workbench 等 runtime。
3. 最后用一个 AI/Semis deep case 产出可审阅、可追责、可复盘的 gold workpaper，作为后续扩行业、扩 case、扩产品面的样板。

P33 的通过口径仍然是 `L4_scope_pass`：每个阶段只在自身范围达到企业级稳定、可回放、可追责、可测试后才算通过。`L1/L2/L3`、smoke、mock、diagnostic-only 都只能作为中间门控。

## 2. 当前事实

Project OS 当前记录的事实：

- P31 Project OS baseline 已完成。
- P32 learning gate 当前为 `in_progress_registry_promotion_gate_pass`。
- P32 已有 `21` 个 L1 sources、`15` 个 L2 extractions、`15` 个 L3 contracts。
- `15` 个 P32/P33 fixture 证明过的合同进入 `active_registry_ready`，但只允许 feature-flagged 或 runtime-alignment-only。
- 当前剩余 `0` 个合同仍为 `deferred_pending_l4_fixture`。
- P30 仍有 open root-cause blockers：真实单 case 新 artifact proof、memo insight-density proof、paid full-chain overuse risk。

因此 P33 不允许直接扩大 20-50 case，也不允许用 paid full-chain 发现 deterministic/node-level 能发现的问题。

## 3. Source Of Truth

P33 的长期维护文件：

- 人读执行程序：`docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- AI/Semis 研究质量尺子：`docs/internal/vnext_20260610/p33_ai_semis_research_judgment_ruler.zh-CN.md`
- AI/Semis 人工 gold case：`docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md`
- Humanmade gold set 规格：`docs/internal/vnext_20260610/p33_humanmade_gold_set_spec_v0_1.zh-CN.md`
- Humanmade gold set 机器可读规格：`docs/project_os/humanmade_gold_set_spec_v0_1.json`
- Humanmade gold set 答案样例：`docs/internal/vnext_20260610/p33_humanmade_gold_set_answer_exemplars_v0_2.zh-CN.md`
- Humanmade gold set 答案样例 JSON：`docs/project_os/humanmade_gold_set_answer_exemplars_v0_2.json`
- 机器执行 ledger：`docs/project_os/p33_execution_plan_ledger.jsonl`
- 工作日志：`docs/worklog/product_strategy/074_p33_p32_closeout_to_gold_workpaper_program.md`
- 相关上游：`docs/internal/vnext_20260610/r53_r60_p32_method_pattern_learning_gate.zh-CN.md`
- 相关 Project OS ledger：
  - `docs/project_os/current_context_pack.zh-CN.md`
  - `docs/project_os/capability_status_ledger.jsonl`
  - `docs/project_os/root_cause_issue_ledger.jsonl`
  - `docs/project_os/p32_active_registry_promotion_ledger.jsonl`

后续每完成一个 P33 阶段，必须更新：

1. 本文档对应阶段状态；
2. `p33_execution_plan_ledger.jsonl`；
3. `capability_status_ledger.jsonl` 或 root-cause ledger；
4. P32 promotion ledger 或相关 registry；
5. stage-aware worklog。

## 4. 总执行顺序

```text
P33-0 Governance / context handoff
 -> P33-1 P32 deferred fixture closeout
 -> P33-2 Runtime assimilation
 -> P33-3 AI/Semis gold workpaper case
 -> P33-4 Workbench dogfood
 -> P33-5 Model comparison
 -> P33-6 Vertical lane expansion
 -> P33-7 Enterprise productization path
```

## 5. P33-0 Governance / Context Handoff

### 5.1 目标

保证 P33 跨多轮、跨上下文压缩后不偏离方向。

### 5.2 执行规则

每轮开始：

1. 读取 `current_context_pack.zh-CN.md`。
2. 读取 `capability_status_ledger.jsonl`。
3. 读取 `root_cause_issue_ledger.jsonl`。
4. 读取 `p33_execution_plan_ledger.jsonl`。
5. 检查最新 worklog 是否有比 source doc 更新的状态。

每个阶段结束：

1. 更新本文档的阶段状态。
2. 更新机器 ledger 中该阶段的 `status`、`evidence_refs`、`remaining_gaps`。
3. 新增或更新 worklog。
4. 如涉及 capability，更新 Project OS capability ledger。
5. 如发现 root-cause，更新 root-cause ledger。

### 5.3 上下文压缩交接规则

当任务较长或即将进入压缩时，必须写一个 compact handoff 段落到 worklog，包含：

- 当前目标；
- 已完成阶段；
- 最新通过/失败的 gate；
- 修改过的文件；
- 当前 blocker；
- 下一步唯一推荐动作；
- 禁止误解事项。

注意：不能声称知道精确上下文窗口百分比；只能在明显长任务或用户要求时主动维护 checkpoint。

### 5.4 Subagent 使用规则

如果当前 Codex 环境支持 subagent，多 agent 使用规则如下：

- 主 agent 只负责方向、source-of-truth、integration review、gate decision。
- subagent 只能领取单个 bounded execution ticket，例如一个 deterministic fixture、一个 parser lineage audit、一个 Workbench drilldown test。
- subagent 必须收到最小 handoff pack：目标、输入文件、禁止事项、通过条件、输出路径。
- subagent 不能单独宣布阶段完成，不能改 Project OS source-of-truth，不能绕过 root-cause-first。
- subagent 输出必须回到主 agent 审查后，才可进入 source doc / ledger。

如果当前环境不能维持长期 subagent，则把 subagent 的状态写入 repo ledger，不能依赖另一个聊天上下文的记忆。

## 6. P33-1 P32 Deferred Fixture Closeout

### 6.1 目标

把五个 `deferred_pending_l4_fixture` 合同逐个证明、降级或阻塞：

1. `enterprise_rag_data_pipeline`
2. `sandbox_resource_scheduler`
3. `capital_market_feedback`
4. `workbench_artifact_review_surface`
5. `research_to_quant_factor_handoff`

### 6.2 执行步骤

1. 为每个合同建立 no-paid deterministic fixture。
2. 每个 fixture 必须有输入 contract、输出 artifact、acceptance gate、failure reason。
3. 按依赖顺序执行：
   - 先做 RAG/data lineage，因为它决定 evidence 是否可信；
   - 再做 sandbox/resource，因为它决定工具和模型调用能否安全执行；
   - 再做 capital-market，因为它决定二级市场信号如何进入 judgment；
   - 再做 Workbench surface，因为它要展示 evidence/claim/gap/gate；
   - 最后做 research-to-quant，因为它依赖 JudgmentCard 和 human approval 边界。
4. 每个 fixture 通过后更新 promotion ledger。
5. 未通过的合同只能保持 deferred 或 blocked，并写清楚 owned defect / public boundary / infra missing / product scope mismatch。

### 6.3 通过条件

- 每个合同都有 deterministic fixture artifact。
- 每个合同有明确 promotion decision：`active_registry_ready`、`active_registry_ready_feature_flagged`、`runtime_alignment_only`、`blocked_or_deferred_with_reason`。
- 没有合同因为“看起来合理”直接进 runtime。
- parser / locator / route / data contract 问题不能写成 public source absent。

### 6.4 禁止事项

- 禁止跑 paid full-chain 来证明这五个合同。
- 禁止把 source learning 当 runtime 完成。
- 禁止用 gate/fallback 隐藏 fixture 失败。

### 6.5 当前执行状态：P33-1.1 Enterprise RAG/Data Pipeline

状态：`L4_scope_pass`。

已完成：

- 新增 deterministic fixture：
  - `src/sec_agent/p33_enterprise_rag_data_pipeline_fixture.py`
  - `scripts/engineering/run_p33_enterprise_rag_data_pipeline_fixture.py`
  - `tests/test_p33_enterprise_rag_data_pipeline_fixture.py`
- 生成证据：
  - `data/manifests/p33_enterprise_rag_data_pipeline_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_enterprise_rag_data_pipeline_fixture_report.zh-CN.md`
- 更新 `docs/project_os/p32_active_registry_promotion_ledger.jsonl`：
  - `l3_enterprise_rag_data_pipeline_contract_v0_1` 从 `deferred_pending_l4_fixture` 晋升为 `active_registry_ready_runtime_alignment_only`。

验收结果：

- `8` 条 promoted evidence rows 全部可追溯到 raw source、parser execution、parsed object、retrieval index 和 authority。
- parser failure 被记录为 `parser_gap`，且 `public_source_absent=false`，不能进入 context 或 Claim/JudgmentCard。
- Milvus / vector hit 仍是 recall support，不允许覆盖 exact-first source authority。
- refresh status 和 quality probe 均可见。
- 未使用 paid LLM 或 full-chain。

边界：

- 该结果只证明 enterprise RAG/data pipeline contract 的 runtime alignment。
- 不证明 broad crawler coverage、paid-model memo quality、生产 p95/p99 SLA，也不证明所有 live graph nodes 已经消费 P14 strategy pack。

### 6.6 当前执行状态：P33-1.2 Sandbox / Resource Scheduler

状态：`L4_scope_pass`。

已完成：

- 新增 deterministic fixture：
  - `src/sec_agent/p33_sandbox_resource_scheduler_fixture.py`
  - `scripts/engineering/run_p33_sandbox_resource_scheduler_fixture.py`
  - `tests/test_p33_sandbox_resource_scheduler_fixture.py`
- 生成证据：
  - `data/manifests/p33_sandbox_resource_scheduler_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_sandbox_resource_scheduler_fixture_report.zh-CN.md`
- 修复上游 S2 owned bug：
  - `blocked_tool_calls_ledgered` 原先把整张 `tool_invocations` 历史总数和本轮 decisions 比较；
  - 真实 repo SQLite 有历史工具调用行，导致 S2 误判 `S2_blocked`；
  - 现在改为按 `s2_scope_task_tool_sandbox` task-scoped persisted rows 校验，并新增历史行污染回归测试。
- 更新 `docs/project_os/p32_active_registry_promotion_ledger.jsonl`：
  - `l3_sandbox_resource_scheduler_contract_v0_1` 从 `deferred_pending_l4_fixture` 晋升为 `active_registry_ready_runtime_alignment_only`。

验收结果：

- Forbidden tool / domain / path / credential / unknown tool 均 fail closed 并写入 `ToolInvocationLedger`。
- 高风险本地执行必须有 human approval event 后才能 allow。
- P12 route policy、queue event 和 budget row 可追溯。
- R5 BGE scheduler 同时覆盖 `cuda slot -> cpu spillover` 和 `cuda queue wait` 两种路径。
- AgentInformationEconomy preflight 会在 paid call 之前拦截高 token / 多 specialist fanout。
- Project OS preflight 仍因 P30 full-chain blockers 返回 `blocked`，这是正确边界：它阻止 paid full-chain，但不阻止本 no-paid contract fixture closeout。

边界：

- 该结果只证明 sandbox/resource scheduler contract 的 runtime alignment。
- 不证明 cloud / Kubernetes / vLLM 生产调度，不证明所有 production tools 已接入，也不证明 paid full-chain readiness。

### 6.7 当前执行状态：P33-1.3 Capital Market Feedback

状态：`L4_scope_pass`。

已完成：

- 新增 deterministic fixture：
  - `src/sec_agent/p33_capital_market_feedback_fixture.py`
  - `scripts/engineering/run_p33_capital_market_feedback_fixture.py`
  - `tests/test_p33_capital_market_feedback_fixture.py`
- 生成证据：
  - `data/manifests/p33_capital_market_feedback_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_capital_market_feedback_fixture_report.zh-CN.md`
- 修复上游 S8 owned bug：
  - `insert_signal` 原先在 source row 自带 `forbidden_claims` 时只照抄 source-specific 禁止项；
  - 真实 603 公司输出中部分 market / holder / exact credit / statement rows 缺少 role/authority 默认禁止外推边界；
  - 现在 S8 信号会合并 source-specific forbidden claims 与 role/authority 默认 forbidden claims，避免后续 Research Lead / writer 把二级市场或资本反馈信号冒充为基本面、实时资金流或投资建议。
- 更新 `docs/project_os/p32_active_registry_promotion_ledger.jsonl`：
  - `l3_capital_market_feedback_contract_v0_1` 从 `deferred_pending_l4_fixture` 晋升为 `active_registry_ready_runtime_alignment_only`。

验收结果：

- S8 capital feedback 仍为 `S8_L4_scope_pass`，603 issuer packs、14,706 signals、634 typed gaps、4,221 graph edges。
- 21 个 source roles 均有 authority、frequency、lag policy、commercial boundary 和 forbidden claims。
- 3,487 条 market / holder proxy rows 均不能提权为基本面、产品 KPI、实时资金流或投资建议。
- 1,678 条 lagged holder rows 均禁止写成实时买盘或 current buying pressure。
- 4,670 条 exact filing / exact financial statement rows 均与投资建议和市场隐含推断分离。
- 634 个 missing market-depth rows 保持 typed gap。
- writer-facing judgment material 有 evidence/gap refs、allowed/forbidden claims、cannot_promote_to 和 writer instruction。

边界：

- 该结果只证明 `CapitalMarketFeedbackPack` / `CapitalFeedbackSignal` / `CapitalFeedbackGapItem` / graph edge 的 runtime alignment。
- 二级市场、持仓、估值、衍生品和信用 proxy 只能做 bounded thesis driver；不能替代公司基本面、产品 KPI、实时 OPRA、borrow cost、dealer gamma、实时资金流或对外投资建议。

### 6.8 当前执行状态：P33-1.4 Workbench Artifact Review Surface

状态：`L4_scope_pass`。

已完成：

- 新增 deterministic fixture：
  - `src/sec_agent/p33_workbench_artifact_review_surface_fixture.py`
  - `scripts/engineering/run_p33_workbench_artifact_review_surface_fixture.py`
  - `tests/test_p33_workbench_artifact_review_surface_fixture.py`
- 生成证据：
  - `data/manifests/p33_workbench_artifact_review_surface_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_workbench_artifact_review_surface_fixture_report.zh-CN.md`
- 修复 Workbench review action contract：
  - `append_review_action` 现在支持 `accept`、`reject`、`supersede`；
  - review action 可携带 `review_target_type`、`review_target_id` 和 `idempotency_key`；
  - fixture 可重复运行而不重复写入同一批审查动作；
  - 每条审查动作必须落为 append-only `WorkpaperEvent`，不能只存在前端 local state 或 chat transcript。
- 更新 `docs/project_os/p32_active_registry_promotion_ledger.jsonl`：
  - `l3_workbench_artifact_review_surface_contract_v0_1` 从 `deferred_pending_l4_fixture` 晋升为 `active_registry_ready_runtime_alignment_only`。

验收结果：

- S6 Workbench 与 S7 Deliverable/Dashboard projection 均保持 L4-scope pass。
- Workbench drilldown 能追踪 task -> evidence-backed ClaimCards -> typed gaps -> gates -> artifacts。
- JudgmentState refs 被 Workbench 可见的 ClaimCards 和 typed gaps 覆盖。
- `accept`、`reject`、`supersede` 三类 reviewer action 均写入 `workbench_review_actions_s6`，并关联 append-only `workpaper_events`。
- Deliverable 和 dashboard projection refs 均来自 SQL-backed artifact refs。
- Ops trace、token/cost 字段和 rollback ref 可从 SQL-final replay 中看到。
- Frontend local state 和 chat transcript 不作为最终审计源。

边界：

- 该结果只证明 Workbench artifact-review surface contract 的 runtime alignment。
- 不证明多日真实 reviewer adoption、生产 RBAC/SLA 或最终前端 UX polish；这些仍留给 P33-4 Workbench dogfood 和后续产品化阶段。

### 6.9 当前执行状态：P33-1.5 Research-to-Quant Factor Handoff

状态：`L4_scope_pass`。

已完成：

- 修复 S9 Research-to-Quant handoff payload contract：
  - 新增一等 SQL runtime table `research_judgment_cards_s9`，用于记录 Research-to-Quant handoff 前的判断卡 source refs、authority boundary、counter-view、failure-view 和 forbidden claims。
  - Factor / signal payload 现在显式物化 `judgment_card_ids`、`signal_definition`、`candidate_feature_refs`、`point_in_time_data_manifest` 和 `human_approval_policy`。
  - `judgment_card_ids` 必须指向 `research_judgment_cards_s9`，不能再用 `thesis_driver_id` 作为弱替代。
  - Approved dataset plan 现在显式物化 `backtest_plan_id` 和 no-live/no-advice backtest policy。
  - Blocked dataset plan 现在显式物化 `blocked_before_backtest_plan=true`，避免后续把未批准候选误读成可回测。
- 新增 deterministic fixture：
  - `src/sec_agent/p33_research_to_quant_factor_handoff_fixture.py`
  - `scripts/engineering/run_p33_research_to_quant_factor_handoff_fixture.py`
  - `tests/test_p33_research_to_quant_factor_handoff_fixture.py`
- 生成证据：
  - `data/manifests/p33_research_to_quant_factor_handoff_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_research_to_quant_factor_handoff_fixture_report.zh-CN.md`
- 更新 `docs/project_os/p32_active_registry_promotion_ledger.jsonl`：
  - `l3_research_to_quant_factor_handoff_contract_v0_1` 从 `deferred_pending_l4_fixture` 晋升为 `active_registry_ready_runtime_alignment_only`。

验收结果：

- S9 Research-to-Quant 仍为 `S9_L4_scope_pass`。
- 3 个候选均带 L3 input contract：`judgment_card_ids`、signal definition、feature refs、PIT manifest、approval policy、source refs。
- 3 个 `judgment_card_ids` 均可解析到 `research_judgment_cards_s9`；`direct_thesis_id_substitute_count=0`，且每张卡都有 source refs、authority boundary、counter-view、failure-view、no-advice / no-live-trading forbidden claims。
- 2 个 approved candidates 均带 L3 output contract：factor id、signal refs、`backtest_plan_id`、leakage result、validation status、approval state、ResearchExperienceRecord。
- 1 个 unapproved derivatives candidate 在没有 approved source / approval 时 fail closed：无 PIT rows、无 backtest plan/result、无 paper/live trading。
- PIT rows 有 publish/available/asof/tradable/label timestamps；backtests 必须先有 passed leakage guard。
- FactorCard 和 ResearchExperienceRecord 已写入，可作为后续内部经验沉淀候选；所有 backtest / FactorCard 均保留 no-investment-advice boundary。

边界：

- 该结果只证明 Research-to-Quant factor handoff contract 的 runtime alignment。
- 不证明真实可交易 alpha、生产 PIT security master、交易成本/容量/滑点建模、paper trading adoption 或任何对外投资建议。

P33-1 closeout 结论：

- 五个 deferred contracts 均已完成 no-paid deterministic fixture。
- Registry 最新状态为 `active_registry_ready_count=15`、`deferred_count=0`。
- 下一步进入 `P33-2 Runtime Assimilation`。

## 7. P33-2 Runtime Assimilation

### 7.1 目标

把 P32/P33 已证明合同真正接进 agent 链路，让 agent 工作方式改变，而不是只在文档里存在。

### 7.2 必接组件

1. Research Lead：
   - 读取 active registry；
   - 产出 `thesis_path`、`required_item_plan`、`evidence_role_plan`、`repair_plan`；
   - 能判断哪些缺口是 retrievable、bounded、commercial、not material。
2. ContextEngine：
   - 按角色选择和压缩 pack；
   - 不把 raw evidence dump 给所有 specialist；
   - 每次注入有 source、authority、TTL、compression artifact。
3. Evidence packs：
   - `ProductIntelligenceGraph`
   - `FundamentalStatementPack`
   - `CapitalMarketFeedbackPack`
   - `CustomerDeploymentPack`
   - `IndustryPlaybook`
4. Judgment layer：
   - ClaimCard 升级为 JudgmentCard；
   - 每条 judgment 必须说明支持的判断、强度、边界、反证、不能外推什么。
5. MemoLogicPlan：
   - writer 主输入必须是 writer-ready judgment material；
   - 禁止 writer 从大包 evidence dump 自己找逻辑。
6. Workbench：
   - 能追踪 task -> evidence -> JudgmentCard -> gap -> gate -> artifact -> review action。

### 7.3 通过条件

- deterministic artifact 证明 Research Lead 输出 thesis path，而不是只列任务。
- Product / financial / industry / capital / customer evidence 都能进入主判断骨架。
- writer payload 有 role-specific compression artifact。
- memo 如果说“缺证据”，必须能追溯到上游确实没有或被正确 typed gap。
- Workbench drilldown 能看见 evidence、JudgmentCard、gap、gate 和 artifact refs。

### 7.4 禁止事项

- 禁止 specialist 无 required item 宽扇出。
- 禁止 writer 继续直接吃 raw evidence dump。
- 禁止 memo 把已有证据写成缺失。

### 7.5 当前执行状态：P33-2 Runtime Assimilation

状态：`L4_scope_pass`。

已完成：

- 修复 `ContextEngine.resolve()` 的角色上下文拆分逻辑：
  - `agent_data_views` 现在按单个角色生成 `role_context` snapshot；
  - specialist 只拿到自身 role-scoped context；
  - memo writer 不再看到 specialist 私有 role_context。
- 新增 deterministic fixture：
  - `src/sec_agent/p33_runtime_assimilation_fixture.py`
  - `scripts/engineering/run_p33_runtime_assimilation_fixture.py`
  - `tests/test_p33_runtime_assimilation_fixture.py`
- 生成证据：
  - `data/manifests/p33_runtime_assimilation_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_runtime_assimilation_fixture_report.zh-CN.md`

验收结果：

- 15 个 `active_registry_ready` contracts 全部进入 `runtime_contract_registry`，缺失合同数为 `0`。
- Research Lead runtime plan 产出：
  - `thesis_path`：6 个 path nodes，4 条 mechanism edges；
  - `required_item_plan`：4 个 AI/Semis 必答项；
  - `evidence_role_plan`：5 类 evidence role；
  - `repair_plan`：只保留 typed exact-KPI / order-value gap，不触发 full-chain。
- `ProductIntelligenceGraph`、`FundamentalStatementPack`、`CapitalMarketFeedbackPack`、`CustomerDeploymentPack`、`IndustryPlaybook` 全部进入主判断骨架。
- `ContextEngine` 生成 6 个 injection plans，specialist role context 互不相同，writer raw dump 被阻断。
- `JudgmentState` 为 `ready`，`MemoLogicPlan.validation.status=pass`，writer 只允许使用 `judgment_state`、`memo_logic_plan`、verified claims 和 bounded gaps。
- Workbench trace projection 可以从 task 追到 evidence、typed gaps、JudgmentCards、context injection plans、MemoLogicPlan 和 artifact refs。
- 未使用 paid LLM 或 full-chain。

边界：

- 该结果证明 runtime assimilation contract 已经在 deterministic 层可传导。
- 不证明付费模型最终 memo 质量，也不证明 AI/Semis gold workpaper 已经可接受。
- P33-3 仍必须只选择一个 AI/Semis gold workpaper case，并在 Project OS / token / provider / real-evidence / AIE preflight 通过后再运行。

## 8. P33-3 AI/Semis Gold Workpaper Case

### 8.1 目标

产出第一个真正可用的 AI/Semis gold workpaper 样板。

### 8.2 候选 case

优先从以下 case 选一个：

1. NVDA / AMD / GOOGL TPU 竞争与 AI accelerator 架构差异。
2. DELL AI server margin、NVIDIA GPU 供应链和 hyperscaler capex read-through。
3. ASML / LRCX / AMAT / KLAC 半导体设备周期、订单、积压、出口限制。

### 8.3 执行步骤

1. 先写 case objective contract。
2. 运行 no-paid deterministic preflight。
3. 检查 active registry、data lineage、token budget、provider health、real-evidence mode。
4. 如果 deterministic/node-level artifact 不合格，先修，不跑 paid。
5. 只在 preflight 通过后跑一个 real-evidence paid case。
6. 渲染 final memo / workpaper。
7. 人工审阅 memo 是否达到 analyst workpaper 标准。
8. 把通过版本标记为 gold candidate；不合格则写 root-cause，不扩 case。

### 8.4 Gold Workpaper 通过条件

必须同时满足：

- 开头有明确判断，不是背景总结。
- 分析维度至少覆盖：基本面、产品/架构、客户部署、供应链/竞争、资本市场/预期、反证和 what-would-change。
- 每个核心判断能追到 evidence / graph edge / typed gap。
- 没有 SKU revenue 时，产品层仍能用 spec、architecture、deployment、supply-chain、performance proxy 做 bounded judgment。
- 不把 proxy 当 exact fact。
- 不把 gap 写成主结论。
- token-to-judgment yield 合理，不能高 token 低 insight。

### 8.5 当前执行状态：P33-3 No-paid Preflight

状态：`preflight_contract_pass_ready_for_scoped_paid_run_preflights`。

已完成：

- 冻结单个 AI/Semis gold case：`p33_3_ai_semis_accelerator_dell_gold_case_v0_1`。
- 选择范围：NVDA / AMD / GOOGL TPU 竞争与 DELL AI server margin、NVIDIA GPU 供应链、hyperscaler capex read-through 合并为一个深度 case。
- 新增 deterministic preflight：
  - `src/sec_agent/p33_ai_semis_gold_workpaper_preflight.py`
  - `scripts/engineering/run_p33_ai_semis_gold_workpaper_preflight.py`
  - `tests/test_p33_ai_semis_gold_workpaper_preflight.py`
- 生成证据：
  - `data/manifests/p33_ai_semis_gold_workpaper_preflight_v0_1.json`
  - `docs/internal/vnext_20260610/p33_ai_semis_gold_workpaper_preflight_report.zh-CN.md`

验收结果：

- deterministic preflight `pass`，`gate_fail_count=0`。
- P33-2 runtime assimilation artifact 被验证为可用输入：P33-2 `status=pass`、`closeout_level=L4_scope_pass`、`gate_fail_count=0`。
- 单 case objective contract 已冻结，required dimensions 覆盖：
  - opening thesis；
  - fundamentals；
  - product / architecture；
  - customer deployment；
  - industry / supply-chain；
  - capital-market feedback；
  - counter-thesis / what-would-change。
- 上游 writer-ready material 已确认存在：
  - `ProductIntelligenceGraph`；
  - `FundamentalStatementPack`；
  - `CapitalMarketFeedbackPack`；
  - `CustomerDeploymentPack`；
  - `IndustryPlaybook`；
  - 6 条 required evidence refs；
  - 6 张 JudgmentCards；
  - 2 个 typed gaps；
  - MemoLogicPlan ref。
- fail conditions 和 targeted repair triggers 已机器可读，包括：
  - 不能把“没有 SKU revenue”写成产品层无法判断；
  - 不能把 cloud capex 写成供应商 exact revenue；
  - 不能把 customer deployment 写成 order amount；
  - 不能把 boundary-heavy memo / search summary 当 gold；
  - 如果 memo 说缺证据但上游 JudgmentCard 存在，必须 fail 并回溯最早 faulty artifact。

边界：

- 该结果只证明 P33-3 paid run 前的 case contract / upstream material / fail conditions / Project OS preflight enforcement 已准备好。
- Project OS scoped preflight 现在对 `p33_single_gold_case` 返回 `pass`，open blocker count 为 `0`；broad full-chain / case expansion / release eval 仍不得跳过 P33-3。
- token budget preflight 返回 `allowed=true`，估算 `68,500` tokens / `7` paid calls / `max_paid_calls=8`。
- 已运行过一次 scoped paid diagnostic attempt，但早停在 plan reflection gate，未进入 evidence operators / specialists / writer。
- P33-3 还不是 `L4_scope_pass`，gold workpaper 尚未生成。

### 8.6 当前执行状态：Scoped Paid Attempt Root-cause Repair

状态：`plan_reflection_root_cause_fixed_no_paid_rerun_yet`。

已发生的 scoped paid attempt：

- run id：`p33_gold_case_deepseek_full_chain_r1`。
- 输出目录：`eval/sec_cases/outputs/p33_gold_case_runs/p33_gold_case_deepseek_full_chain_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1`。
- 早停节点：`load_session_state -> research_lead_plan -> validate_activation_plan -> plan_reflection_gate`。
- `loop_break_reason=plan_reflection_gate_failed`。
- 实际 paid 使用很小：provider preflight 约 `49` tokens，Research Lead 约 `4,540` tokens；未调用 specialists / memo writer / verifier。

根因判断：

- 这不是模型输出质量问题，也不是数据源缺失问题，而是 Research Lead activation / evidence-route / plan-reflection 合同归一化不稳定。
- LLM 或 evidence requirement 可以提出 `relationship_graph` / supply-chain read-through 需求，但旧代码在 query contract 未显式声明 relationship scope 时会先把 relationship evidence 剪掉，或在 evidence-route alignment 后新增 `relationship_graph` / `universe_relationship` 却未再次补齐 `relationship_scope_rationale`。
- case score 在早停时没有 `multi_agent_summary.json`，旧 scoring 只看 summary 中的 route diagnostics，导致 Research Lead 明明已调用却可能被误投影为 `llm_invoked=false`。
- P33 fixture 旧版未显式要求 `require_plan_reflection_gate`，导致 plan gate 早停和 vnext audit 语义不一致。

本轮 root-cause repair：

- `src/sec_agent/research_lead_llm.py`
  - 增加 plan-reflection contract normalizer：在 evidence route / source alignment 后统一修正 relationship scope、required source metadata、deep-research mode 和 `relationship_scope_rationale`。
  - 扩展 relationship intent 识别：`read-through`、`supply-chain`、`deployment`、`capex to` 等投研表达能触发关系图谱范围，而普通无关系意图的产品/财务查询仍会被 overroute prune。
  - 让 evidence requirement 自身的 supply-chain/read-through 语义可保留 relationship route，不再被前置 policy 误删。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - early-stop scoring 会回看 `result.research_lead_model_diagnostics`，不再把已调用 Research Lead 误报为未调用。
  - `vnext_contract_audit.required` 现在反映任一子合同要求，而不是只看 `require_vnext_contract` 总开关。
- `tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl`
  - 增加 `require_plan_reflection_gate=true`。

已验证：

```powershell
python -m pytest tests/test_multi_agent_research_lead_llm.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_scoring_reports_plan_reflection_early_stop_without_hiding_lead_call tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_scoring_accepts_vnext_contract_summary tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_scoring_rejects_milvus_exact_authority_misuse -q
python -m py_compile src/sec_agent/research_lead_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
python scripts/engineering/run_p33_ai_semis_gold_workpaper_preflight.py --root .
python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --run-scope p33_single_gold_case
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl --run-id p33_gold_case_token_budget_preflight_after_plan_gate_fix_20260705_r1 --output-dir eval/sec_cases/outputs/p33_gold_case_runs --project-os-run-scope p33_single_gold_case --token-budget-preflight-only --real-evidence-operators
```

当前边界：

- 本轮未重新跑 paid full-chain。
- 还没有 rendered memo / gold workpaper。
- 下一次 paid run 之前仍需 provider preflight / real-evidence mode / AIE 检查，且只允许 `p33_single_gold_case` 范围。

### 8.7 当前执行状态：Risk / Counterevidence Dimension 与 Writer Cost Root-cause Repair

状态：`risk_counterevidence_writer_root_cause_fixed_no_paid_rerun_yet`。

已发生的 scoped paid attempt：

- run id：`p33_gold_case_deepseek_full_chain_after_milvus_available_semantics_fix_20260705_r1`。
- 输出目录：`eval/sec_cases/outputs/p33_gold_case_runs/p33_gold_case_deepseek_full_chain_after_milvus_available_semantics_fix_20260705_r1`。
- 结果：`gate_status=fail`、`diagnostic_only=true`。
- 这次已经通过 Research Lead、plan reflection、real evidence operators 和 specialist quality；失败点后移到 Memo Writer / verifier。

关键观测：

- `real_specialist_quality_passed=1`，specialist evidence quality 不是本轮 blocker。
- `memo_writer.route_result.status=fallback`，失败原因为 `analyst_depth_required_dimensions_not_carried`，缺失 `risk_and_counterevidence`。
- Memo Writer 尝试 `3` 次，`repair_attempts=2`，总计约 `44,255` tokens；这是结构性重试烧 token，而不是单纯模型慢。
- `risk_counterevidence_analyst` 被 paid specialist whitelist 剪掉，但 `memo_logic_plan.section_order` 仍要求 `risk_and_counterevidence`。
- `thesis_driver_pack` / `judgment_state` 中 risk/counter 维度有文字摘要或 conflict，但缺少可追踪 `counter_claim_ids` / `counter_driver_ids`，writer/verifier 无法把它投影成正式 memo dimension。
- old salvage 会重排/替换维度，不能稳定保留 `risk_and_counterevidence` 和原 section order。

根因判断：

- 这不是 Milvus 是否可用的问题，不是 provider 连通性问题，也不是公开源缺失问题。
- 根因是内部合同与投影链条不完整：counter/conflict material 没有从 dimension section 贯穿到 JudgmentState、Memo Writer、memo_claim 和 verifier projection。
- writer retry 只是把 owned contract bug 放大成 token 成本问题；正确修法是先在 paid writer 前发现 impossible required-dimension contract，或者让 required dimension 有 traceable material。

本轮 root-cause repair：

- `src/sec_agent/multi_agent_contracts.py`
  - `dimension_sections` 现在保留 `counter_claim_ids` 和 `counter_driver_ids`。
  - `build_judgment_state()` 现在把 required dimensions 和 counter ids 写入 JudgmentState。
  - JudgmentState validation 会报告 required dimension 是否缺 writer material。
- `src/sec_agent/memo_llm.py`
  - Memo Writer 调用前新增 `_pre_writer_required_dimension_material_gate()`，required dimension 没有任何 claim / counter / gap / evidence / summary / counter text 时 fail closed，避免 paid retry。
  - verified judgment completion 现在先补 memo claims，再补/enrich dimension analyses，再回填 claims，避免 stale refs。
  - deterministic salvage 改为合并已有维度和 required-item rows，并按 `MemoLogicPlan.section_order` 排序，不再粗暴替换维度。
  - `risk_and_counterevidence` 如果只有 counter/gap text 但无原始 trace，会显式投影为 low-confidence `gap_untraced_dimension_*`，不能静默消失。
  - memo claims 现在继承 source ClaimCard 的 `analysis_dimension` / `dimension_id`。
  - dimension evidence refs 优先使用当前 ClaimCard refs，避免 stale section refs。
  - 语言归一化与 verified-judgment completion 元数据在 dimension normalizer 中保留，不再被二次归一化丢弃。

已验证：

```powershell
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py -q
python -m py_compile src/sec_agent/multi_agent_contracts.py src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py
python scripts/engineering/run_p33_ai_semis_gold_workpaper_preflight.py --root .
python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --run-scope p33_single_gold_case
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl --run-id p33_gold_case_token_budget_preflight_after_risk_dimension_fix_20260705_r1 --output-dir eval/sec_cases/outputs/p33_gold_case_runs --project-os-run-scope p33_single_gold_case --token-budget-preflight-only --real-evidence-operators
git diff --check
```

Observed：

- `tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py`：`120 passed`。
- `tests/test_multi_agent_real_llm_chain_eval.py`：`91 passed`。
- py_compile：pass。
- P33 no-paid preflight：`deterministic_preflight_status=pass`、`gate_fail_count=0`。
- Project OS scoped preflight：`status=pass` for `run_scope=p33_single_gold_case`。
- token budget preflight：`allowed=true`、`estimated_total_tokens=68500`、`estimated_paid_call_count=7`。
- `git diff --check`：无 whitespace error，仅历史 CRLF/LF warning。

当前边界：

- 本轮没有 paid rerun。
- 还没有 accepted gold workpaper。
- 下一次只允许重跑一个 scoped paid AI/Semis case；仍必须先确认 provider / real-evidence / AIE preflight。
- 如果 paid case 再失败，继续从最早 faulty artifact 定位；不得扩到 20-50 case，不得用模型替换或 broad eval 掩盖问题。

### 8.8 P33-3A Method-to-Runtime Observability & Attribution Layer

状态：`L4_scope_pass_node_level_consumption_no_paid`。

插入原因：

- P32 / P33 已经把金融研究方法、AI/Semis playbook、agent 工程模式写入 registry / contract / fixture，但这不等于 runtime 能力已经形成。
- 最近输出质量问题说明：方法可能停留在文档或 registry，真实 Research Lead / specialist / JudgmentCard / ProductIntelligenceGraph / writer 仍按旧泛化路径工作。
- 因此 P33-3 paid rerun 前必须插入 P33-3A，先证明“方法进入节点并被消费”，不能再用 paid full-chain 发现本可 node-level 测出的传导问题。

P33-3A 要解决的 owned root cause：

1. `method_absorbed_but_not_runtime_active`：
   - 不能再把 source learning / registry / fixture pass 误称为 runtime active。
   - 每个方法必须有 injection point、消费节点、deterministic test 和输出质量证据。
2. `research_lead_is_router_not_thesis_lead`：
   - Research Lead 必须产出 thesis path、required item plan、evidence role plan、specialist assignment rationale、retrievable gap、bounded/commercial gap 和 writer order。
3. `specialist_is_material_collector_not_judgment_builder`：
   - specialist 必须按角色 playbook 回答 must-answer items，并输出 writer-ready `judgment_candidates`。
4. `claim_card_is_evidence_card_not_judgment_card`：
   - JudgmentCandidate 必须转成 Claim/JudgmentCard，并保留 required item、business mechanism、financial bridge、counter read、cannot infer、what would change view、graph edge refs。
5. `product_graph_is_context_not_investment_projection`：
   - ProductIntelligenceGraph 边必须投影为 `edge_investment_role`，例如 demand validation、adoption signal、supply constraint、competitive substitution，并声明 cannot infer / needed confirmation。
6. `writer_is_researcher_not_expression_layer`：
   - Writer 只能使用 MemoLogicPlan、JudgmentCards、dimension judgments、typed gaps 和 refs；上游没有 judgment material 时必须 fail 或回到 targeted repair。

本轮已做的 runtime injection：

- 新增 `src/sec_agent/method_runtime.py`，作为 method-to-runtime pack 生成器。
- Research Lead prompt 已注入 compact `method_runtime_pack`，并要求输出 thesis-path planning contract。
- Specialist request / prompt / output contract 已注入 `method_runtime_pack`、`specialist_runtime_rubric` 和 `judgment_candidates` 合同。
- `normalize_specialist_memolet()` / `aggregate_specialist_judgment_plan()` 已支持 `judgment_candidates`。
- ProductIntelligenceGraph relationship rows 已投影 `edge_investment_role`、`supports_judgment`、`cannot_infer`、`needed_confirmation`。
- Memo writer skill 已更新为优先使用 thesis_path / JudgmentCards / JudgmentCandidates / MemoLogicPlan，不再把 raw evidence dump 当主输入。
- Codex global stewardship / Project OS skill 已加入 Method-to-Runtime lifecycle，要求 `documented -> registry_only -> contract_translated -> fixture_proven -> runtime_injected -> node_level_consumed -> paid_artifact_proven -> dogfood_accepted`。

本轮新发现并修复的投影缺陷：

- `JudgmentCandidate` 没有显式 `memo_slot` 时，旧投影会先归一成 `evidence_gap`，导致 role slot mismatch；现改为缺省使用该 specialist 的默认 slot。
- `JudgmentCandidate` 的 `analyst_depth` 在 `_claim_card_annotations()` 后会被通用 depth annotation 覆盖，导致 `graph_edge_refs` / `cannot_infer` / `what_would_change_view` 等 writer-ready 字段丢失；现改为保留并合并已有 depth 字段。

P33-3A 通过条件：

- Research Lead prompt 有 `method_runtime_pack`，system schema 明确 `thesis_path`。
- Specialist request 有 role-specific `specialist_runtime_rubric`，output contract 要求 `judgment_candidates`。
- JudgmentCandidate 可通过 validation，并能变成 writer-ready JudgmentCard。
- ProductIntelligenceGraph relationship rows 带投资含义和边界。
- 以上都有 deterministic/node-level test；没有 paid LLM 或 full-chain run。

验证结果：

```powershell
python -m pytest tests/test_method_runtime.py tests/test_multi_agent_contracts.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_specialist_llm.py tests/test_product_spec_pack.py -q
python -m py_compile src/sec_agent/method_runtime.py src/sec_agent/research_lead_llm.py src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_contracts.py src/sec_agent/product_intelligence_runtime.py
git diff --check
```

Observed：

- targeted deterministic suite：`143 passed`。
- py_compile：pass。
- `git diff --check`：pass，仅有既有 CRLF/LF warning。

当前边界：

- P33-3A 仍不是 P33-3 gold workpaper closeout。
- 当前只证明 runtime injection 和 node-level consumption，不证明 paid memo 质量。
- 下一步只能回到 scoped P33 single-case paid preflight / provider / real-evidence / AIE 检查；不得 broad full-chain、case expansion 或 release eval。

### 8.9 P33-3 Stepwise Research Lead Plan Node

状态：`research_lead_plan_node_paid_smoke_pass_downstream_not_run`。

执行原因：

- 用户要求不要再一口气跑 full-chain，而是利用 checkpoint / stop-after-node 逐节点验证。
- 本节点只验证 P33-3 gold case 的 `research_lead_plan` 是否已经从 routing lead 升级为 thesis lead。
- 该节点不验证 evidence operators、specialists、JudgmentState、Memo Writer、Verifier 或 Workbench dogfood。

本轮 root-cause 修复：

1. `retrieval_plan.ALLOWED_RETRIEVAL_ROUTES` 以前没有 `relationship_graph`，导致 Research Lead 明确要求客户部署 / 供应链 read-through 时，final evidence plan 仍可能把 relationship route 剪掉。
2. `_routes_for_task()` 以前不会从 `relationship_graph` source tier 和 relationship/supply-chain/customer/deployment 语义中推导 relationship route。
3. `_query_contract_for_evidence()` 以前保留原始 query contract 的 SEC/8-K source scope，忽略 evidence payload 请求的 source family / route-derived source family，导致 relationship requirement 被 source-family mismatch 污染。
4. Stepwise scoring 以前只看 `agent_activation_validation`，而 `research_lead_plan` 原生 checkpoint artifact 使用 `research_lead_validation` / `research_lead.validation`，导致节点已 pass 时 score projection 仍可能显示 validation fail。

代码修复范围：

- `src/sec_agent/retrieval_plan.py`
  - 新增 `relationship_graph` route。
  - 增加 relationship terms 和 route inference。
  - 为 relationship route 增加 source tier / section hints。
- `src/sec_agent/research_lead_llm.py`
  - `_query_contract_for_evidence()` 合并 evidence payload 请求的 source families。
  - `relationship_graph` 不再被原始 SEC-only query contract 剪掉。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - scoring / audit 对 stepwise native checkpoint artifact 增加 `research_lead_validation` fallback。
- `tests/test_multi_agent_research_lead_llm.py`
  - 增加 regression：`req_customer_deployment` / `req_supply_chain` 必须保留 `relationship_graph` route / source family / route intent。
- `tests/test_multi_agent_real_llm_chain_eval.py`
  - 增加 regression：stepwise artifact 只有 `research_lead_validation` 时，Research Lead validation 仍应被计为 pass。

节点运行：

```powershell
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl --run-id p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5 --output-dir eval/sec_cases/outputs/p33_gold_case_runs --project-os-run-scope p33_single_gold_case --real-evidence-operators --skip-provider-preflight --stop-after-node research_lead_plan
```

Artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/stepwise_node_result.json
```

节点结果：

- `status=stopped_after_node`，符合 stepwise 预期。
- `research_lead.route_status=pass`。
- `research_lead.validation.status=pass`。
- Provider call：`deepseek / deepseek-v4-pro`，`call_count=1`，latency `17,791ms`，token `input=4,942 / output=1,461 / total=6,403`。
- `thesis_path.path_nodes=6`。
- `evidence_role_plan` 覆盖：
  - `product_architecture_competition`
  - `customer_deployment_adoption`
  - `supply_chain_readthrough`
  - `fundamental_financial_bridge`
  - `capital_market_price_in`
  - `risk_and_counterevidence`
- `writer_order` 覆盖：
  - `opening_thesis`
  - `product_architecture`
  - `customer_deployment`
  - `industry_supply_chain`
  - `fundamentals`
  - `capital_market_feedback`
  - `counter_thesis_and_what_would_change`
- Final `evidence_requirement_plan` 已保留 relationship route：
  - `req_customer_deployment.evidence_routes` 包含 `relationship_graph`，route intent 指向 `universe_relationship / relationship_graph_lookup`。
  - `req_supply_chain.evidence_routes` 包含 `relationship_graph`，route intent 指向 `universe_relationship / relationship_graph_lookup`。

验证命令：

```powershell
python -m pytest tests/test_multi_agent_research_lead_llm.py -q
python -m pytest tests/test_multi_agent_langgraph_routing.py -q
python -m pytest tests/test_multi_agent_contracts.py tests/test_method_runtime.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py -q
python -m py_compile src/sec_agent/retrieval_plan.py src/sec_agent/agent_contracts.py src/sec_agent/research_lead_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
```

Observed：

- Research Lead LLM suite：`36 passed`。
- LangGraph routing suite：`31 passed`。
- Contract / method runtime suite：`44 passed`。
- Real LLM chain eval suite：`92 passed`。
- py_compile：pass。

当前边界：

- 这是 P33 single gold case 的 `research_lead_plan` 节点级 paid smoke，不是 gold workpaper closeout。
- `gate_status=fail` / downstream checks false 是 `--stop-after-node research_lead_plan` 的预期结果，不代表 downstream 质量。
- r5 artifact 的 `stepwise_score_focus.research_lead.validation_pass` 曾因 scoring fallback 缺失显示不完整；已用 deterministic regression 修复，未为节省 token 重新跑 paid。
- 下一节点应为 `validate_activation_plan`，然后才是 `plan_reflection_gate`；不得直接跳到 full-chain memo。

### 8.10 P33-3 Stepwise Validate Activation Plan Node

状态：`validate_activation_plan_node_pass_no_paid_no_downstream`。

执行原因：

- `validate_activation_plan` 是 deterministic 节点，本身不需要 LLM。
- 现有 `eval_multi_agent_real_llm_chain.py` 支持 `--stop-after-node`，但没有暴露从 multi-agent checkpoint 原生 resume 的 CLI。
- `langgraph_node_checkpoints.json` inspect 结果为 `resume_supported=false / no_next_node`，说明当前 artifact 不能直接原生续跑 multi-agent graph。
- 因此本轮不重复 paid 调 Research Lead，而是使用上一节点 artifact 中的 `agent_activation_plan` 调用同一套 `validate_agent_activation_plan()` 合同，并生成单节点 validation artifact。

输入 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/stepwise_node_result.json
```

输出 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_validate_activation_plan_from_research_lead_r5_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/validate_activation_plan_node_result.json
```

节点结果：

- `status=node_pass`。
- `validation.status=pass`。
- `error_count=0`。
- `warning_count=0`。
- `agent_count=15`。
- `source_family_count=7`。
- `relationship_graph_present=true`。
- `product_intelligence_runtime_status=enabled`。
- `next_node=plan_reflection_gate`。

执行边界：

- 无 LLM 调用。
- 无 evidence operators。
- 无 specialist。
- 无 JudgmentState / Memo Writer / Verifier。
- 该结果只证明 Research Lead 输出的 activation plan 可被当前 agent contract 接受，并且 product intelligence / relationship graph 路由在 validation 后仍未被剪掉。

当前边界：

- 这不是 P33-3 gold workpaper closeout。
- 这不是 graph 原生 resume proof；它是基于上一个 checkpoint artifact 的 deterministic node replay。
- 下一节点是 `plan_reflection_gate`，应优先用同一个 activation plan 做 deterministic plan-reflection，不要直接跳 full-chain。

### 8.11 P33-3 Stepwise Plan Reflection Gate Node

状态：`plan_reflection_gate_node_pass_no_paid_no_downstream`。

执行原因：

- `plan_reflection_gate` 是 Research Lead / activation plan 之后的硬门控，目标不是再调模型，而是确认第一轮研究骨架是否足以进入下游证据和 specialist。
- 本轮使用 `must_answer/risk` 修复后的 Research Lead artifact 和对应 `validate_activation_plan` artifact 做 deterministic replay。
- 这一步专门防止过去的失败模式：Research Lead 看似通过，但 required item 没有 `must_answer`、risk/counterevidence 没有激活，或者 plan reflection 只做形式检查。

输入 artifacts：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_research_lead_after_must_answer_risk_fix_deepseek_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/stepwise_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_validate_activation_plan_after_must_answer_risk_fix_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/validate_activation_plan_node_result.json
```

输出 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_plan_reflection_gate_after_must_answer_risk_fix_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/plan_reflection_gate_node_result.json
```

节点结果：

- `status=node_pass`。
- `plan_reflection_report.status=pass`。
- `error_count=0`。
- `warning_count=0`。
- `required_item_count=6`。
- `must_answer_missing_count=0`。
- `active_agent_count=16`。
- `specialist_agent_count=5`。
- `risk_counterevidence_active=true`。
- `next_node=universe_relationship_expand`。

执行边界：

- 无新增 LLM 调用。
- 无 evidence operators。
- 无 specialist。
- 无 JudgmentState / Memo Writer / Verifier。

当前边界：

- 这只证明 Research Lead 的研究骨架和任务合同能通过 plan reflection hard gate。
- 这还不证明下游证据真的能被召回，也不证明 specialist 会产出 JudgmentCard。
- 下一节点是 `universe_relationship_expand`，不能直接跳到 specialist 或 Memo Writer。

### 8.12 P33-3 Stepwise Universe Relationship Expand Node

状态：`universe_relationship_node_pass_graph_adapter_fixed_no_paid_no_specialist`。

执行原因：

- P33 gold case 的关键问题之一是产品、客户部署、供应链、竞争关系不能再只是泛同行背景，必须变成可被 Research Lead / specialist 消费的 relationship rows。
- 旧 `universe_relationship` 能读 sector depth，但 ProductRelationshipGraph adapter 不够完整：缺 priority helper、edge type 到 runtime relationship role 的映射、外部客户/counterparty endpoint 支持、metric/source intent 默认值和 forbidden-claim 边界。
- 本轮先修 adapter/contract，再用 deterministic replay 跑节点，避免用 paid specialist 去发现关系图谱输入缺陷。

输出 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_universe_relationship_after_graph_contract_fix_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/universe_relationship_node_result.json
```

节点结果：

- `status=node_pass`。
- `validation_status=pass`。
- `error_count=0`。
- `warning_count=0`。
- `relationship_count=24`。
- `relationship_graph_rows=413`。
- `sector_depth_rows=24`。
- `relationship_type_counts={"supplier":12,"customer":12}`。
- `original_relationship_type_counts` 包含：
  - `OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP=8`；
  - `PUBLIC_ORDER_OR_TENDER_CONTEXT=10`；
  - `OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT=2`；
  - `INFRASTRUCTURE_SUPPLIER_TO=2`；
  - `COMPONENT_INPUT_TO=2`。
- `inference_level_counts={"disclosed_indirect":10,"curated_input_unverified":12,"category_inferred":2}`。
- `expanded_tickers=["ASML","AMAT","AMZN","TSM","LRCX","KLAC","MSFT"]`。
- `included_tickers=["NVDA","AMD","GOOGL","DELL","ASML","AMAT","AMZN","TSM","LRCX","KLAC","MSFT"]`。
- `external_entity_edge_count=20`。
- `direct_or_parser_backed_relationship_count=22`。
- `relationship_rows_with_metric_intent=24`。

本轮 root-cause 修复：

- `ProductRelationshipGraph` 默认关系边只在未显式配置 sector pack / relationship graph 时启用，避免污染旧 sector-depth tests。
- 关系图谱 rows 按 focus/scope 和 allowed universe 过滤，避免 `AAPL`、非目标海外 ticker 或非本轮 inventory ticker 漏入 universe。
- 从 `company_product_family:TICKER:family` 节点解析 ticker；外部客户或 counterparty endpoint 保留为 `related_entity_id`，不强行扩展成 ticker。
- 保留 `from_node_id`、`to_node_id`、`related_entity_id`、`original_relationship_type`、`evidence_refs`、`forbidden_claims`。
- 将产品图谱 edge type 映射为 runtime roles：
  - `COMPETES_WITH -> competitor`；
  - official customer / order / tender context -> `customer`；
  - official supply-chain / infrastructure supplier / manufacturing dependency / component input / production enablement -> `supplier`；
  - channel / complement / input context -> `other`。
- authority inference 使用 original edge type，而不是映射后的 role，避免 `OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP` 被降成普通 `supplier` 后丢失 `disclosed_indirect` / parser-backed status。
- 增加 relationship priority，使 official customer / supply / order edges 排在 same-family / sector candidates 前。
- 为 customer / supplier / competitor / channel-like edges 补 `metrics_to_check` 和 `evidence_source_needed`，并明确不能外推 revenue、shipment、market share、sell-through 或 ASP。
- `UniverseRelationshipPlan` endpoint validator 现在允许 `from_ticker + related_entity_id`，使客户、渠道、项目、平台等外部实体可以成为合法 endpoint，但不污染 ticker universe。
- 修复 optional second-pass injected retrieval 分支未写 `second_pass_result` 的审计缺口；后续 targeted repair 的 row delta、authority delta、closed/open gaps 和 loop-break reason 可回放。

验证：

```text
python -m pytest tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py -q
# 112 passed

python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_agent_information_economy.py -q
# 103 passed

python -m py_compile src/sec_agent/relationship_graph.py src/sec_agent/multi_agent_contracts.py src/sec_agent/langgraph_orchestrator.py
# pass
```

当前边界：

- 这一步仍无 paid LLM 调用，也不是 specialist / JudgmentCard / Memo Writer 质量证明。
- 这一步证明的是：P33 gold case 下游关系图谱入口现在能进入 runtime relationship rows，并带有 source / metric / forbidden-claim 边界。
- 当前 stepwise artifacts 仍未持久化完整 graph `state_payload`，所以不是 graph-native resume proof。本轮通过手工重建 minimal state 做 deterministic replay；这已记录为后续 runtime issue。
- 下一步只能继续 `route_by_execution_mode -> compile_evidence_requirements`，验证 relationship/product/fundamental/capital/customer-deployment intent 是否进入 evidence requirements，而不是直接跑 specialist 或 Memo Writer。

### 8.13 P33-3 Stepwise Route / Compile Evidence Requirements Node

状态：`route_compile_evidence_requirements_node_pass_after_relationship_route_coalescing_fix`。

执行原因：

- `universe_relationship_expand` pass 后，仍必须确认 Research Lead 的 required items 和 relationship graph plan 能进入可执行 retrieval routes。
- 不能因为 `evidence_requirement_plan` 表面有 `relationship_graph` route，就默认 retrieval plan 会保留这些路线；本轮实际发现了一个 route budget / coalescing 的 owned root-cause。

输出 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_route_compile_evidence_requirements_after_universe_graph_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/route_compile_evidence_requirements_node_result.json
```

节点结果：

- `status=node_pass`。
- `route_by_execution_mode.execution_mode=deep_research`。
- `compile_evidence_requirements.mode=compiled`。
- `evidence_validation_status=pass`。
- `source_router_status=pass`。
- `entity_count=11`。
- `evidence_requirement_count=5`。
- `retrieval_route_count=9`。
- `relationship_requirement_count=2`。
- `relationship_retrieval_route_count=1`。
- `relationship_route_requirement_ids=["req_customer_deployment","req_supply_chain"]`。
- `dropped_relationship_route_count=0`。
- `route_counts={"8k_commentary":2,"filing_text":2,"industry_snapshot":1,"ledger_first":2,"market_snapshot":1,"relationship_graph":1}`。
- `route_budget_dropped_count=3`，但 dropped routes 不含 `relationship_graph`。

本轮 root-cause 修复：

- 初始 replay 显示 `req_supply_chain.evidence_routes` 虽有 `relationship_graph`，但 retrieval plan 中的 `supply_chain::relationship_graph` 被 `universe_relationship` per-agent tool limit 剪掉。
- 这不是外部数据问题，也不是模型问题，而是我们自己的 route compiler 问题：`relationship_graph` route coalescing keyed by ticker scope，导致 customer deployment 和 supply-chain 被当成两个物理 graph lookup；随后 budget pruning 只保留一个。
- 同时 `_cap_retrieval_plan_routes()` 剪枝后只更新 `route_count` 和 `route_budget_dropped_count`，没有重算 `route_counts` / budget totals，导致 summary 与真实 routes 不一致。
- 修复后：
  - `relationship_graph` routes 按 route/year 合并，tickers 和 evidence requirement ids 在合并后的 route 中 union；
  - 一个 `relationship_graph` route 同时覆盖 `req_customer_deployment` 和 `req_supply_chain`；
  - route budget 仍保持 `universe_relationship=1`，不是通过放宽预算掩盖问题；
  - route summary 在 pruning 后按 kept routes 重算。

验证：

```text
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_relationship_graph_routes_coalesce_before_universe_tool_budget tests/test_multi_agent_evidence_requirements.py::test_compiled_retrieval_routes_are_capped_by_agent_permission_matrix -q
# 2 passed

python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py -q
# 113 passed
```

当前边界：

- 这是 retrieval planning / evidence requirement compilation proof。
- r3 只能作为 relationship route coalescing 修复证据，不能作为最新 route compile closeout。
- 审计后发现新的 owned root cause：route budget 仍按 logical route 计数，而 `execute_evidence_operators` 会把多个 SEC text routes 合并为一个 physical `sec_search_filings` 调用，导致 DELL margin / supply-chain 的非 relationship routes 在 r3 被不必要裁剪。
- 已新增 r4 route compile artifact：`eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_route_compile_evidence_requirements_after_physical_tool_budget_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/route_compile_evidence_requirements_node_result.json`。
- r4 结果：`status=node_pass`、`evidence_requirement_count=5`、`retrieval_route_count=12`、`route_budget_dropped_count=0`；DELL margin `ledger_first / filing_text`、supply-chain `ledger_first / filing_text` 均保留。
- 这一步仍不证明 evidence operators 真的取回了足够 evidence rows。
- 它不证明 specialist JudgmentCards、Memo Writer、Verifier、Workbench dogfood 或 accepted gold workpaper。

### 8.14 P33-3 Stepwise Execute Evidence Operators Node

状态：`execute_evidence_operators_node_pass_real_evidence_with_typed_boundaries`。

执行原因：

- route compile r4 通过后，必须验证这些 route 是否真的能驱动本地工具取回 evidence rows。
- 这一步使用 real evidence operators，但不调用 paid LLM，不进入 specialist / JudgmentState / Memo Writer。
- 目标是先看 data / retrieval / tool 层是否能支撑下一步 role-specific fusion。

输入 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_route_compile_evidence_requirements_after_physical_tool_budget_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/route_compile_evidence_requirements_node_result.json
```

输出 artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_real_after_physical_budget_fix_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_real_after_physical_budget_fix_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_compact_state.json
```

节点结果：

- `status=node_pass`
- `elapsed_sec=78.177`
- `tool_observation_count=12`
- `tool_status_counts={ok:7,cached:5}`
- `sec_query_exact_value_ledger=356` rows
- `sec_search_filings=182` rows
- `relationship_graph_lookup=24` rows
- `market_get_snapshot=9` rows
- `industry_get_snapshot=10` rows
- `context_rows=120`
- `runtime_ledger_rows=387`
- `source_gap_count=4`

Required-item coverage：

- `req_hyperscaler_capex`: ledger / filing text / market snapshot 均有 rows。
- `req_customer_deployment`: 8-K commentary、relationship graph 有 rows；filing_text route 通过 grouped cache 复用但本 route 自身 row_count 为 0，需要在 fusion 阶段看是否由 relationship/deployment rows 足够支撑。
- `req_supply_chain`: ledger / filing text / relationship graph 均有 rows。
- `req_dell_margin_quality`: ledger / filing text / 8-K commentary 均有 rows。
- `req_accelerator_architecture`: industry snapshot 有 rows，但 `product_evidence_rows=0`，说明产品图谱/规格证据是否被正确投影仍要在 fusion 阶段验证。

记录的边界：

- `product_evidence_rows=0`、`public_source_context_rows=0`。这不是本节点失败，但说明 ProductIntelligenceGraph 是否真正进入 writer-ready product evidence 还没有被证明。
- ASML / TSM 的 2026 `10-Q` / `8-K` 不在 active SEC manifest 中。该缺口不能写成 `public_source_absent`；如果后续需要 ASML/TSM 主证据，应转向 20-F / 6-K、company IR、local exchange filing 或 typed route gap。
- grouped SEC text route 使用了本地 CUDA BGE reranker，`context_resource_load_ms=56289`，后续若频繁运行需继续观察资源队列和 cache 命中。

当前边界：

- 这一步只证明本地 evidence operator 可取回真实 rows。
- 它不证明 evidence fusion、specialist 判断质量、JudgmentState、Memo Writer、Verifier、Workbench dogfood 或 accepted gold workpaper。
- 下一节点只能是 `evidence_fusion_selector`，重点检查：ProductIntelligenceGraph / relationship rows / ledger rows / text rows 是否被压成 role-specific、authority-aware、writer-ready evidence bundles；不能直接跳到 Memo Writer 或模型对比。

### 8.15 P33-3 Stepwise Evidence Fusion Selector Node

执行 `evidence_fusion_selector` 前先发现并修复两个 owned root-cause：

1. source gap register 双算：ASML / TSM 的 4 个 SEC manifest gaps 既从 `source_gaps` 进入 register，又通过 authority row projection 再进入一次，导致 r1/r2 早期检查出现 gap 数不稳定。修复为按 `source_family + gap_type + ticker + metric + product_or_segment + bounded_reason` 做 semantic dedupe，并让 `bounded_gap_reason` 进入 gap type / reason 检测。
2. required-item trace 丢失：retrieval routes 有 `evidence_requirement_id`，但 `execute_evidence_operators` 输出的 rows 没稳定带下 `req_*`，fusion 只能看到 `fundamental / supply_chain / customer_deployment` 等 role labels。修复为 route execution 时向 rows 注入 `evidence_requirement_id(s)`、`selection_task_ids`、`selection_route_ids` 和 `retrieval_routes`；grouped SEC search rows 再通过 `selection_route_ids` 回填具体 requirement。

修复和验证：

```text
src/sec_agent/multi_agent_runtime.py
tests/test_multi_agent_evidence_requirements.py
```

Focused tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_execute_evidence_operator_preserves_requirement_trace_from_route tests/test_multi_agent_evidence_requirements.py::test_evidence_fusion_preserves_required_item_trace_fields tests/test_multi_agent_evidence_requirements.py::test_evidence_fusion_dedupes_source_gap_authority_projection -q
```

结果：`3 passed`。

Broader targeted tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py -q
```

结果：`118 passed`。

Trace-repaired execute artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_trace_repaired_from_real_rows_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_trace_repaired_from_real_rows_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_compact_state.json
```

该 replay 没有重新跑 paid LLM 或 evidence tools，只使用 8.14 已接受的真实 rows 并补 lineage。保留结果：

- `runtime_ledger_row_count=387`
- `context_row_count=120`
- `market_snapshot_row_count=9`
- `industry_snapshot_row_count=10`
- `source_gap_count=4`
- required trace：`req_hyperscaler_capex=97`、`req_dell_margin_quality=145`、`req_supply_chain=129`、`req_customer_deployment=60`、`req_accelerator_architecture=10`

Superseded artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_real_after_requirement_trace_fix_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/DO_NOT_USE_SUPERSEDED.txt
```

该直接工具重跑缺 full graph `state_context`，产生 route skips / source gaps，不能作为 accepted evidence。

Accepted fusion artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_evidence_fusion_selector_after_requirement_trace_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/evidence_fusion_selector_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_evidence_fusion_selector_after_requirement_trace_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/evidence_fusion_selector_compact_state.json
```

节点结果：

- `status=node_pass`
- `row_count=375`
- `primary_exact_value=232`
- `company_disclosed_context=96`
- `context_or_proxy=43`
- `gap_only=4`
- `bounded_gap_count=4`
- `public_exact_authority_violation_count=0`
- `semantic_exact_authority_violation_count=0`
- required trace：`req_hyperscaler_capex=42`、`req_dell_margin_quality=99`、`req_supply_chain=75`、`req_customer_deployment=60`、`req_accelerator_architecture=10`

仍保留的边界：

- `relationship_graph` rows 仍是 `scope_or_hypothesis_only`，不能直接证明 company-reported facts。
- `market_snapshot` / `industry_snapshot` 只能做 context/proxy，不能覆盖 SEC facts。
- `product_runtime_fact_count=0`，说明本节点没有 company_product_evidence_graph exact product runtime facts；后续 specialist 必须把产品/架构/客户部署作为 bounded judgment material，而不能把它冒充 SKU revenue / shipment / ASP exact。
- ASML / TSM SEC manifest gaps 是 SEC route scope 的 `retrievable_gap`，不是 `public_source_absent`。

当前边界：

- 这一步只证明 evidence fusion / authority boundary / required-item trace。
- 它不证明 specialist JudgmentCards、JudgmentState、Memo Writer、Verifier、Workbench dogfood、模型对比或 accepted gold workpaper。
- 下一节点只能是 `coverage_reflection`，检查 required-item evidence coverage、typed gaps、authority boundaries 和 product-runtime exact gap 对 specialist 输入的影响。

### 8.16 P33-3 Stepwise Coverage Reflection Node

状态：`coverage_reflection_node_pass_after_fusion_aware_coverage_fix`。

执行原因：

- `evidence_fusion_selector` pass 后，仍不能直接进 specialist。必须先确认 fused rows 是否真正覆盖 Research Lead 的 required items，以及哪些只能作为 bounded context。
- 初始 coverage r1/r2 暴露一个 owned root-cause：`req_customer_deployment` 已有 60 条 fused rows，但 `customer_deployment::filing_text` supplemental route 为 `no_rows`，coverage gate 仍把该 required item 判为 missing。

本轮 root-cause 修复：

- coverage reflection 不能只按单条 route / source family 判断缺口；应先消费 `evidence_fusion_bundle.authority_rows`，按 `req_*` required item 判断是否已有 authority coverage。
- coalesced `relationship_graph` route 的 `evidence_requirement_id` 可能是 `req_customer_deployment,req_supply_chain`，必须拆成多个 req keys，否则 fallback coverage 会误认为它是一个新 requirement。
- 新增 `reflection_report_from_evidence_fusion_bundle`，并让 `_node_coverage_reflection` 在有 fusion bundle 时优先使用它；没有 fusion bundle 时才回退到旧的 tool-observation path。

修复和验证：

```text
src/sec_agent/multi_agent_runtime.py
src/sec_agent/langgraph_orchestrator.py
tests/test_multi_agent_evidence_requirements.py
```

Focused tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_coverage_reflection_uses_fused_rows_before_supplemental_route_gaps tests/test_multi_agent_evidence_requirements.py::test_coverage_reflection_splits_coalesced_relationship_requirement_ids -q
```

结果：`2 passed`。

Accepted coverage artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/coverage_reflection_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/coverage_reflection_compact_state.json
```

节点结果：

- `status=node_pass`
- `sufficiency_level=partial`
- `missing_requirement_count=0`
- `second_pass_request_count=0`
- `source_family_gap_count=0`
- `quality_gap_count=1`
- `bounded_answer_allowed=true`
- `bounded_gap_count=4`
- `fused_row_count=375`
- `product_runtime_fact_count=0`
- `active_specialist_count=5`
- `expected_next_node=specialists`

当前质量边界：

- 唯一 quality gap 是 `req_accelerator_architecture`：只有 `industry_snapshot` 的 `context_or_proxy` rows。
- 这说明产品/架构方向可以作为 bounded product context 进入 Product Specialist，但不能提权为 exact product KPI、公司官方 SKU/spec fact、shipment、ASP、share 或 revenue 证据。
- ASML/TSM 的 SEC manifest gaps 仍保留在 bounded gap register，但不再造成 required-item missing。

当前边界：

- 这一步只证明 coverage reflection / required-item sufficiency / bounded context boundary。
- 它不证明 specialist JudgmentCards、JudgmentState、Memo Writer、Verifier、Workbench dogfood、模型对比或 accepted gold workpaper。
- 下一节点只能是 `optional_specialist_subgraph`，并且 specialist 必须消费 `req_accelerator_architecture` 的 bounded-context 边界。

### 8.17 P33-3 Specialist Input Projection Preflight

状态：`specialist_input_projection_preflight_pass_after_fusion_view_and_risk_contract_fix`。

执行原因：

- `coverage_reflection` pass 后不能直接调用 paid specialist。
- 必须先证明 compact state 里的 fused authority rows 能被 role-specific specialist data view 消费，并且 Research Lead 的 risk/counterevidence required item 不会在 fanout 前被静默剪掉。
- 这一步仍是 no-paid preflight，不产出 JudgmentCards。

初始问题：

- compact state 只保留 `evidence_fusion_bundle.authority_rows`，没有完整 raw `runtime_ledger_rows`、`context_rows`、`market_snapshot_rows`、`industry_snapshot_rows`。
- `build_agent_data_view()` 和 specialist shared context 仍优先读取旧 raw row fields，导致 initial preflight 中 `fundamental_analyst=0`、`industry_supply_chain_analyst=0`、`market_valuation_analyst=0`。
- `risk_counterevidence_analyst` 虽然在 Research Objective Contract / thesis path 里是必需角色，但 activation matcher 没消费这些 required items，因此被判为 skipped。

根因：

- 这是 owned data-contract / method-to-runtime defect，不是公开源缺失，也不是模型能力问题。
- `coverage_reflection_compact_state.json` 的正确 source-of-truth 是 fused authority rows；specialist data view / source boundary / activation matcher 没和 compact state 合同对齐。

修复：

```text
src/sec_agent/multi_agent_runtime.py
src/sec_agent/specialist_llm.py
tests/test_multi_agent_evidence_requirements.py
```

- `build_agent_data_view()` 在 raw rows 缺失时按 agent role 从 `evidence_fusion_bundle.authority_rows` 读取 fused rows。
- `source_boundaries_from_state()` 在 raw rows 缺失时用 fused source-family counts 回填 context / ledger / market / industry / fusion authority counts。
- `_relationship_rows_from_state()` 读取 fused `relationship_graph` rows，使 industry specialist 能看到 relationship summary。
- `_state_evidence_requirements()` 新增 Research Objective Contract 和 thesis_path required items。
- `_requirement_matches_specialist()` 支持 `primary_agents` / `assigned_agents` 直接匹配，risk/counterevidence 不再被静默剪掉。

Accepted preflight artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_specialist_input_projection_preflight_after_required_item_scope_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/specialist_input_projection_preflight.json
```

节点前检查结果：

- active specialists：`fundamental_analyst`、`product_technology_analyst`、`industry_supply_chain_analyst`、`market_valuation_analyst`、`risk_counterevidence_analyst`。
- role-specific row counts：
  - `fundamental_analyst=48`
  - `product_technology_analyst=48`
  - `industry_supply_chain_analyst=48`
  - `market_valuation_analyst=16`
  - `risk_counterevidence_analyst=20`
- `industry_supply_chain_analyst.relationship_summary_count=24`。
- source boundaries：`context=76`、`ledger=280`、`market=9`、`industry=10`、`fusion_authority=375`。
- matched requirement counts：`fundamental=4`、`product=5`、`industry=6`、`market=3`、`risk=2`。

验证：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_specialist_data_view_reads_compact_fusion_bundle_rows tests/test_multi_agent_evidence_requirements.py::test_risk_specialist_activation_uses_research_objective_contract_required_item -q
python -m py_compile src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py src/sec_agent/langgraph_orchestrator.py
python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py -q
```

结果：

- focused tests：`2 passed`
- related deterministic suite：`181 passed`
- py_compile：pass

当前边界：

- 这一步只证明 specialist 输入投影和激活合同。
- 还没有运行 paid `optional_specialist_subgraph`。
- 还没有 specialist `judgment_candidates` / JudgmentCards / JudgmentState / Memo Writer / Verifier / Workbench dogfood / accepted gold workpaper。
- 下一步只能进入 node-level `optional_specialist_subgraph`；运行前仍需确认 token / provider / AIE 约束，且不得直接跳 Memo Writer 或 full-chain。

### 8.18 P33-3 Stepwise Optional Specialist Subgraph

状态：`optional_specialist_subgraph_targeted_repair_composite_pass`。

执行原因：

- `coverage_reflection` 和 specialist input projection 已证明 5 个 specialist 应该被激活，但还没有证明它们能产出 writer-ready `judgment_candidates`。
- 用户明确要求逐节点运行，不再一口气跑 full-chain；因此本节点只验证 specialist reasoning 和 role-specific evidence selection。

本轮 root-cause 修复：

1. `req_hyperscaler_capex` issuer diversity 丢失：
   - all-specialist r3 gate 虽然 pass，但 `risk_counterevidence_analyst` / `fundamental_analyst` 只稳定看见 AMZN capex，不稳定看见 MSFT capex。
   - 根因不是公开源缺失，也不是模型问题，而是 role-specific selector 以 row count 填满 requirement quota，AMZN QTD/YTD 多行挤掉 MSFT。
   - 修复：`multi_agent_runtime.py` 和 `specialist_llm.py` 为 `req_hyperscaler_capex` 增加至少 `2` 个 distinct ticker rows 的保留逻辑。
2. 避免重复烧 token：
   - 没有重新跑完整 all-specialist fanout。
   - 只 targeted rerun `risk_counterevidence_analyst` 和 `fundamental_analyst`，再生成带 provenance 的 composite checkpoint。

Accepted specialist checkpoint：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_summary.json
```

Composite provenance：

- base run：`p33_stepwise_optional_specialist_all_after_product_fundamental_risk_projection_fix_20260705_r3`
- replaced agents：
  - `risk_counterevidence_analyst` <- `p33_stepwise_optional_specialist_risk_after_hyperscaler_issuer_diversity_fix_20260705_r1`
  - `fundamental_analyst` <- `p33_stepwise_optional_specialist_fundamental_after_hyperscaler_issuer_diversity_fix_20260705_r1`
- unchanged agents：
  - `product_technology_analyst`
  - `industry_supply_chain_analyst`
  - `market_valuation_analyst`

节点结果：

- `verification_status=pass`
- `writer_allowed=true`
- `supported_claim_count=16`
- `unsupported_claim_count=7`
- `conflict_count=1`

代表性判断变化：

- risk specialist 现在能同时看到 MSFT / AMZN hyperscaler capex，并把它组织成 `capex digestion risk`，而不是误判为 capex 证据不足。
- fundamental specialist 现在能把 MSFT / AMZN capex 与 DELL margin / operating bridge 放在一起，形成 demand signal + margin quality gap 的判断材料。
- product / industry / market specialist 仍沿用 r3 中已通过的输出，但 r3 base artifact 不再是 accepted downstream input。

验证：

```powershell
python -m pytest tests/test_multi_agent_specialist_llm.py -k "fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows or risk_specialist_request_keeps_required_exact_financial_rows or product_specialist_request_includes_relationship" -q
python -m pytest tests/test_multi_agent_specialist_llm.py -k "fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows or risk_specialist_request_keeps_required_exact_financial_rows or product_specialist_request_includes_relationship or product_specialist_request_balances or comparative_focus_ticker_prompt_rows or soft_balances_comparative_prompt_rows" -q
python -m pytest tests/test_multi_agent_evidence_requirements.py -k "specialist_data_view_reads_compact_fusion_bundle_rows or risk_specialist_activation_uses_research_objective_contract_required_item or product_data_view" -q
python -m py_compile src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/agent_registry.py
```

结果：

- focused specialist tests：`3 passed`
- broader specialist tests：`6 passed`
- evidence requirement tests：`6 passed`
- py_compile：pass

当前边界：

- 这是 targeted repaired composite checkpoint，不是 fresh all-specialist rerun。
- 它证明 specialist 层可以给 aggregate 节点提供 JudgmentCandidate material。
- 它不证明 MemoLogicPlan / Memo Writer / Verifier / Workbench dogfood / 模型对比 / accepted gold workpaper。

### 8.19 P33-3 Stepwise Aggregate Judgment Plan

状态：`aggregate_judgment_plan_node_pass_after_market_slot_recovery_fix`。

执行原因：

- specialist composite pass 后，下一步必须验证 aggregator 是否能把 specialist 输出组织成 thesis path / JudgmentState / MemoThesisPlan，而不是把 supported judgments 丢到 gap 或 evidence summary。
- 这是 deterministic node replay，不需要再调用 paid specialist。

本轮 root-cause 修复：

1. `market_valuation` judgment 被误归入 `evidence_gap`：
   - aggregate r1/r2 中，market analyst 有 supported judgment，但 memo outline 中 `market_valuation` 仍是 `missing_or_partial`。
   - 根因是 JudgmentCandidate / observation normalization 把空 `memo_slot` 默认成 `evidence_gap`；旧 memolet 即使来自 `market_valuation_analyst`，也没有 recovery。
   - 修复：保留空 memo_slot，aggregation 时按 agent expected slot 默认；对 stale market gap slot 在满足 supported/non-gap/evidence refs 时恢复为 `market_valuation`。
2. 缺少 aggregate-only runner：
   - 为避免从 specialist 重新烧 token，新增 `run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py`，从 accepted specialist checkpoint 直接 replay aggregate 节点。

Accepted aggregate checkpoint：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_market_gap_slot_recovery_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_market_gap_slot_recovery_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_summary.json
```

节点结果：

- `specialist_verification.status=pass`
- `judgment_state.status=ready`
- `memo_thesis_plan.status=ready`
- `thesis_driver_pack.status=ready`
- `thesis_path.status=ready`
- `supported_claim_count=26`
- `high_materiality_claim_count=6`
- `memo_ready_claim_count=11`
- `supported_memo_slot_count=7`
- `judgment_cards=12`
- `unsupported_claim_count=7`
- `conflict_count=1`

Memo outline 现在覆盖：

- `thesis`
- `fundamentals`
- `product_technology`
- `industry_relationship`
- `market_valuation`
- `risk_counterevidence`
- `evidence_gap`

关键质量点：

- `market_valuation` 现在不是 gap：它用 AMZN / MSFT capex 支撑 market/expectation context。
- valuation / positioning / price-in 缺口仍留在 typed gap，不冒充已解决。
- `evidence_gap` 仍保留 unsupported / cannot-infer material，writer 后续必须有边界表达。

验证：

```powershell
python -m pytest tests/test_multi_agent_contracts.py -k "market_judgment_candidate_without_explicit_slot_defaults_to_market_slot or market_judgment_candidate_with_stale_gap_slot_recovers_to_market_slot or product_technology_claim_card_uses_product_memo_slot" -q
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py -k "market_judgment_candidate_without_explicit_slot_defaults_to_market_slot or market_judgment_candidate_with_stale_gap_slot_recovers_to_market_slot or product_technology_claim_card_uses_product_memo_slot or judgment_candidate_becomes_writer_ready_judgment_card or fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows or risk_specialist_request_keeps_required_exact_financial_rows or product_specialist_request_includes_relationship or product_specialist_request_balances or comparative_focus_ticker_prompt_rows or soft_balances_comparative_prompt_rows" -q
python -m pytest tests/test_multi_agent_evidence_requirements.py -k "specialist_data_view_reads_compact_fusion_bundle_rows or risk_specialist_activation_uses_research_objective_contract_required_item or product_data_view" -q
python -m py_compile src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/agent_registry.py src/sec_agent/multi_agent_contracts.py scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
```

结果：

- focused contract tests：`3 passed`
- broader contract/specialist tests：`10 passed`
- evidence requirement tests：`6 passed`
- py_compile：pass

当前边界：

- 这一步证明 aggregate JudgmentState / MemoThesisPlan / ThesisDriverPack ready。
- 它仍不证明 MemoLogicPlan / Memo Writer / Verifier / Workbench dogfood / 模型对比 / accepted gold workpaper。
- 下一步只能先检查 aggregate payload，然后进入 node-level `MemoLogicPlan / Memo Writer`；不得直接跳 broad full-chain、case expansion 或模型对比。

### 8.20 aggregate payload / MemoLogicPlan required-item projection closeout

8.19 的 r3 后续被降级为 superseded diagnostic：它修复了 `market_valuation` slot，但 aggregate runner 的 node_result 只持久化了 `judgment_plan / specialist_verification`，没有把 graph node 已生成的 `memo_logic_plan / lead_review_checkpoint / research_objective_contract` 写入 checkpoint。继续用 r3 会让 writer 看不到计划层。

进一步审计发现 r4/r5 也不能作为最终 source-of-truth：虽然已持久化 `memo_logic_plan`，但 `required_question_items` / `required_item_answer_plan` 为空或不完整。根因是 stepwise compact state 没保留 case fixture 的 `prompt / focus_tickers / required_answer_moves`，runner 即使回填也会被 LangGraph state schema 丢弃；同时 `_required_question_items_for_contract()` 没把 `required_answer_moves` 编译为必答项。

本轮修复：

```text
scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
src/sec_agent/langgraph_orchestrator.py
tests/test_p33_aggregate_judgment_plan_runner.py
tests/test_memo_logic_plan.py
```

关键改动：

- aggregate runner 按 `case_id` 从 P33 fixture 回填 `prompt / focus_tickers / search_scope_tickers / required_dimensions / required_answer_moves`。
- `SecAgentGraphRuntimeState` 新增 case-level 字段，防止 LangGraph 节点间丢弃 case contract。
- `_required_question_items_for_contract()` 将 `required_answer_moves` 编译为 writer-auditable required items，并与 query-derived items 去重合并。
- aggregate runner gate 加硬：`MemoLogicPlan` 必须存在、validation pass、`required_question_items` 非空、`required_item_answer_plan` 非空。
- node_result 持久化 `case_contract`、`required_answer_moves`、`memo_logic_plan`、`lead_review_checkpoint`、`research_objective_contract` 和治理层 artifacts。

Accepted aggregate source-of-truth：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_summary.json
```

r7 结果：

- `gate_status=pass`
- `specialist_verification.status=pass`
- `supported_claim_count=26`
- `unsupported_claim_count=7`
- `conflict_count=1`
- `memo_outline_count=7`
- `judgment_card_count=14`
- `judgment_state_card_count=12`
- `memo_logic_plan.validation.status=pass`
- `required_question_item_count=10`
- `required_item_answer_plan_count=10`
- `persisted_required_answer_moves=7`

验证：

```powershell
python -m pytest tests/test_p33_aggregate_judgment_plan_runner.py tests/test_memo_logic_plan.py -q
python -m py_compile src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
python scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py --run-id p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7 --strict
```

结果：

- tests：`13 passed`
- py_compile：pass
- aggregate replay：pass

当前边界：

- r7 证明 aggregate JudgmentState 和 MemoLogicPlan projection 可供下一节点消费。
- 它仍不证明 Memo Writer 的自然语言质量、Verifier、Workbench dogfood、模型对比或 accepted gold workpaper。
- r3/r4/r5/r6 均为 superseded / diagnostic-only，不得作为 downstream source-of-truth。

### 8.21 Memo Writer source-coverage / surface-quality hardening

状态：`memo_writer_payload_preflight_pass_no_paid_rerun`。

执行原因：

- 旧 paid Memo Writer artifact 曾技术性通过，但人工审阅发现输出仍偏浅、低密度、模板化。
- 继续 paid rerun 之前必须先定位 deterministic/root-cause：writer 是否把 source coverage rows 当主 claim、dimension section 是否被错误主张污染、verifier 是否会阻断低密度 deep-research 表面。
- 本轮不跑 paid Memo Writer，不跑 full-chain，不做模型对比。

本轮发现的 root cause：

1. `official_issuer_context` / `lead_targeted_repair_claim:issuer_official:*` 这类 source-coverage rows 以前可能被标成 `memo_ready`。
2. `_dimension_sections_from_claims()` 以前按 `claims[0]` 选 primary claim，source coverage context 可能成为 product / fundamental thesis。
3. Memo Writer claim selector 对 source coverage 没有足够惩罚，可能把“找到了披露路径”写成正式投资判断。
4. 中文 salvage / action-item 模板会生成“继续判断投资含义”“同口径更新，并补订单”等低密度泛化句子。
5. deep-research profile 下 direct answer 过短以前主要是 warning；旧弱 memo 不会被 hard fail。
6. gap-boundary detector 过于激进，可能把有边界但有判断的长 opening 覆盖成短 salvage 摘要。

本轮修复：

- `src/sec_agent/multi_agent_contracts.py`
  - 新增 source-coverage claim type 识别。
  - source coverage 强制降权到 `evidence_summary_or_gap`，并记录 `source_coverage_context_not_main_claim`。
  - dimension section grouping 排除 source coverage context，避免其成为 primary thesis。
  - dimension claim sort / comparison basis 跳过 source coverage 与大块 issuer JSON。
  - analyst-depth gate 对 `standard / expanded / deep_research` direct answer 设置硬下限；deep-research 太短会 fail。
- `src/sec_agent/memo_llm.py`
  - Memo claim selection / context priority / missing-data classification 对 source coverage 显式降权。
  - source coverage salvage 只说明官方披露路径、parser/locator 边界和下一步精确抽取动作，不冒充投资 claim。
  - action items 改成 dimension-specific，不再输出低密度泛化模板。
  - gap-boundary detector 保留有判断、有反证、有触发条件的长 direct answer。

验证：

```powershell
python -m py_compile src/sec_agent/memo_llm.py src/sec_agent/multi_agent_contracts.py
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py -q
python -m pytest tests/test_p33_memo_writer_payload_preflight_runner.py tests/test_p33_memo_writer_node_runner.py -q
python scripts/eval_multi_agent/run_p33_memo_writer_payload_preflight_from_aggregate.py --aggregate-node-result eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json --output-root eval/sec_cases/outputs/p33_gold_case_runs --run-id p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1 --strict
```

Observed：

- contract / memo repair suite：`129 passed`。
- P33 Memo Writer runner suite：`2 passed`。
- py_compile：pass。
- no-paid payload preflight：`gate_status=pass`。
- preflight artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_payload_preflight_summary.json
```

关键结果：

- `compact_required_item_count=10`
- `compact_section_count=7`
- `compact_supported_claim_count=8`
- `approx_total_prompt_chars_with_scaffold=56016`
- 旧 aggregate r7 经新 selector 选择的 8 条 memo claims 中，`source_coverage_selected=[]`。
- 旧 paid DeepSeek memo artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_from_aggregate_r7_deepseek_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_node_result.json
```

在新 verifier 下返回：

```json
{"status":"fail","error_types":["analyst_depth_generic_template_language","analyst_depth_direct_answer_too_thin_for_profile"]}
```

当前边界：

- 本轮只证明 Memo Writer payload selection / surface verifier hardening。
- 没有 paid Memo Writer rerun，没有 rendered memo，没有 accepted gold workpaper。
- prompt 仍约 `56k` chars，后续仍需做 payload compression / token-to-judgment yield 优化，但不能用压缩替代质量修复。
- 下一步不能直接 paid Memo Writer。必须先按 `docs/internal/vnext_20260610/p33_ai_semis_research_judgment_ruler.zh-CN.md` 做 no-paid `ResearchJudgmentRulerAudit`，审计 accepted aggregate r7 和 Memo Writer payload 是否已经回答 AI/Semis gold case 的核心研究问题。只有 ruler audit 为 `pass_or_bounded_pass` 后，才允许从 accepted aggregate r7 跑单个 Memo Writer node。

### 8.22 AI/Semis Research Judgment Ruler

状态：`research_judgment_ruler_documented_pending_no_paid_audit`。

插入原因：

- 用户指出关键问题不是继续把工程节点跑通，而是 Codex 必须先作为“懂金融的程序员”写下自己对 AI/Semis case 的深度理解，并把它当作评判 agent 节点表现的尺子。
- 过去 P32/P33 的方法吸收、runtime assimilation 和 stepwise gate 能证明“结构存在”，但仍可能放过研究质量问题：节点有输出、JudgmentCard 有数量、MemoLogicPlan validation pass，但没有回答 DELL AI server 利润质量、NVDA/AMD/TPU 产品竞争、hyperscaler capex 到供应链的传导、semicap cycle 和 price-in 等核心问题。
- 因此 Memo Writer paid rerun 前必须新增一层 no-paid 研究质量审计，避免再次用 token 发现本可由节点级材料审计发现的问题。

新增 source-of-truth：

```text
docs/internal/vnext_20260610/p33_ai_semis_research_judgment_ruler.zh-CN.md
```

该尺子规定：

1. AI/Semis gold case 的核心问题不是“AI 需求强不强”，而是 AI 基建需求是否真实转化为 accelerator、server OEM、foundry/packaging、HBM、semicap 公司的高质量收入和利润。
2. 合格 workpaper 必须围绕以下链条组织判断：
   - AI workload / cloud capex；
   - accelerator product capability and supply allocation；
   - cloud/OEM/customer deployment；
   - server OEM revenue quality and gross-margin bridge；
   - foundry / packaging / HBM / semicap read-through；
   - market expectation / price-in；
   - counter-thesis and what-would-change.
3. Product / Architecture、Customer Deployment、Supply Chain、Financial Quality、Market Expectation、Risk / Counter-thesis 六类 lane 都有强证据、中等证据、proxy、不能外推和失败条件。
4. Research Lead、Evidence Fusion、Coverage Reflection、Specialist、Aggregate / JudgmentState、MemoLogicPlan / Memo Writer 都有节点级研究质量失败条件。
5. 如果关键问题没有被回答，不能因为工程 gate pass、writer 有输出或 JudgmentCard 数量够就把 P33-3 记为 gold case 通过。

新增执行要求：

1. 下一步先做 no-paid `ResearchJudgmentRulerAudit`。
2. 审计对象：
   - accepted aggregate r7；
   - Memo Writer payload preflight；
   - required item answer plan；
   - JudgmentCards / unsupported claims / typed gaps；
   - ProductIntelligenceGraph / CustomerDeployment / Fundamental / Capital / Industry packs 的实际进入情况。
3. 审计必须回答：
   - 哪些 gold questions 已被 JudgmentCards 支撑；
   - 哪些只有 proxy；
   - 哪些缺少 source/parser/runtime material；
   - 哪些属于公开源边界或 commercial gap；
   - writer payload 是否仍含低价值上下文或 evidence dump。
4. 审计未通过时，不跑 paid Memo Writer；先修 source route、parser、specialist skill、JudgmentCard projection 或 writer payload。

当前边界：

- 本轮只落了研究尺子和 P33 source doc 对齐。
- 尚未实现 `ResearchJudgmentRulerAudit` 脚本或 runner。
- 尚未审计 aggregate r7 / writer payload，也未跑 paid Memo Writer。

### 8.23 AI/Semis Humanmade Gold Case v0.2

状态：`humanmade_gold_case_v0_2_polished_memo_updated_no_paid_run`。

插入原因：

- 用户进一步明确：P33 不应该先从 agent 节点继续往后冲，而应该先做一个 humanmade gold case，展示一个人类 analyst 在公开数据前提下会怎样拆问题、搜证据、形成 workpaper 和成稿。
- 只有先有人工 gold case，才能倒推 Research Lead、specialist skill、JudgmentCard、ProductIntelligenceGraph、MemoLogicPlan、writer 和 verifier 应该怎样实现；否则容易继续把“有工程输出”误判成“有研究质量”。
- 该文档同时记录公开数据源上限：哪些证据足以支撑有边界判断，哪些只能做 proxy，哪些必须暴露为 issuer-not-disclosed / commercial-tracker / parser / runtime-projection gap。

新增 source-of-truth：

```text
docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md
```

该 humanmade gold case 已完成：

1. 用官方/高质量公开源建立 AI/Semis source ledger。
2. 把研究范围限定为：
   - AI workload / hyperscaler capex；
   - accelerator product capability / supply；
   - cloud/OEM/customer deployment；
   - server OEM revenue quality / margin bridge；
   - foundry / packaging / HBM / semicap read-through；
   - market expectation / price-in；
   - counter-thesis and what-would-change。
3. 写出人类 analyst workflow：
   - Research Lead 先产出 thesis path，而不是先派 agent；
   - specialist 必须回答业务机制，而不是只列证据；
   - evidence strength 被分为 strong / medium / proxy / cannot infer；
   - writer 只能在 JudgmentCard / MemoLogicPlan 支撑下表达。
4. 写出 human workpaper v0.1 和 polished memo v0.2。v0.2 不再是分散结论清单，而是沿 `demand pool -> accelerator / product architecture -> Dell revenue visibility vs margin quality -> foundry / semicap read-through -> market price-in -> counter-thesis` 组织的连续 analyst memo。
5. 写出倒推工程要求：
   - Research Lead 必须生成 thesis path / required items / evidence-role plan；
   - specialist output 必须是 judgment candidate；
   - ProductIntelligenceGraph edge 必须投影为 investment role；
   - Memo Writer 只能消费 compressed judgment material；
   - 若上游未形成判断，writer 必须 fail，不得自己从 raw evidence dump 硬写。

更新执行要求：

1. `ResearchJudgmentRulerAudit` 不再只对照抽象 ruler；必须先把 humanmade gold case 转成 machine-readable `HumanmadeGoldCaseSpec`。
2. 后续 no-paid audit 必须逐项比较：
   - human expectation；
   - current agent artifact；
   - missing / weak / proxy / cannot-infer item；
   - root cause：data / parser / runtime projection / specialist skill / aggregation / writer。
3. audit 未通过时，不跑 paid Memo Writer，也不做模型对比；先修最早 faulty layer。

当前边界：

- 本轮只建立 humanmade gold case v0.2 和治理状态。
- 尚未把 humanmade gold case 转成 machine-readable spec。
- 尚未用它审计 aggregate r7 / Memo Writer payload。
- 尚未证明 agent 输出已经达到 humanmade gold case 质量。

### 8.24 Humanmade Gold Set Spec v0.1

状态：`gold_set_catalog_schema_documented_pending_user_review`。

新增 source-of-truth：

```text
docs/internal/vnext_20260610/p33_humanmade_gold_set_spec_v0_1.zh-CN.md
docs/project_os/humanmade_gold_set_spec_v0_1.json
```

插入原因：

- 单个 AI/Semis humanmade gold case 能作为当前深度样板，但不能防止后续 runtime 只对这个 case 过拟合。
- P33 需要先把“人类投研质量”拆成多粒度 gold set：一个 deep case 用于当前主链路审计，多个 rubric case 用于横向泛化，多个 negative case 用于防止错误提权和错误缺口归因。
- 这一步仍然是质量标准层，不是 runtime proof；它只定义下一步 no-paid audit 应该拿什么尺子去量 accepted aggregate r7 / Memo Writer payload。

本轮完成 1-4 项：

1. 建立 `HumanmadeGoldSetSpec v0.1`：包含 catalog、case schema、case type、通用研究方法 rubric 和通过标准。
2. 把当前 AI/Semis case 登记为第一个 `Deep Gold Case`：`ai_semis_dell_nvda_anchor_v0_1`，source doc 指向 `p33_ai_semis_humanmade_gold_case.zh-CN.md`。
3. 新增 8 个 `Rubric Gold Case`：
   - `semicap_cycle_rubric_v0_1`
   - `cloud_saas_ai_monetization_rubric_v0_1`
   - `financials_rate_credit_capital_rubric_v0_1`
   - `healthcare_regulated_product_adoption_rubric_v0_1`
   - `energy_utilities_power_demand_rubric_v0_1`
   - `retail_consumer_traffic_margin_rubric_v0_1`
   - `auto_ev_industrial_cycle_rubric_v0_1`
   - `capital_market_feedback_price_in_rubric_v0_1`
4. 新增 6 个 `Negative Gold Case`：
   - `negative_sku_revenue_missing_not_product_failure_v0_1`
   - `negative_demand_pool_not_supplier_allocation_v0_1`
   - `negative_relationship_graph_not_financial_fact_v0_1`
   - `negative_parser_gap_not_public_source_absent_v0_1`
   - `negative_available_evidence_not_used_v0_1`
   - `negative_commercial_tracker_boundary_v0_1`

当前边界：

- 这不是 `HumanmadeGoldCaseAudit`。
- 这不是 accepted aggregate r7 / Memo Writer payload 审计。
- 这不是 paid Memo Writer 许可。
- 这不是 full-chain、模型对比或 release eval 许可。
- 第五项必须等用户审阅 Gold Set 后再做：`P33-3_humanmade_gold_set_audit_spec_and_runner`。

### 8.25 Humanmade Gold Set Answer Exemplars v0.2

状态：`answer_exemplars_documented_pending_user_review`。

新增 source-of-truth：

```text
docs/internal/vnext_20260610/p33_humanmade_gold_set_answer_exemplars_v0_2.zh-CN.md
docs/project_os/humanmade_gold_set_answer_exemplars_v0_2.json
```

插入原因：

- 用户指出 v0.1 仍然偏 rules，不是合理答案；例如“没有 SKU revenue 但仍可从产品规格/部署/供应链判断”最多是泛答案，不足以约束 agent 写出真实 analyst memo。
- P33 gold set 必须记录 answer-level exemplar，让后续 Research Lead、specialist、JudgmentCard、MemoLogicPlan 和 Memo Writer 知道“合格答案应该怎么写”，而不是只知道“哪些不能写”。
- 这也是为了防止 Codex 或 agent 在后续上下文压缩后只记住规则门控，忘掉真实投研表达。

本轮完成：

1. 给 8 个 Rubric Gold Case 补充可直接放入 memo 的 answer exemplar：
   - semicap cycle / backlog / export control；
   - cloud/SaaS AI monetization and capex tradeoff；
   - financials rate / credit / capital return；
   - healthcare product approval / adoption / reimbursement；
   - energy/utilities power demand and balance sheet；
   - retail/consumer traffic / price / margin；
   - auto/EV/industrial cycle；
   - secondary-market price-in / capital feedback。
2. 给 6 个 Negative Gold Case 补充 correct response pattern：
   - SKU revenue 缺失时如何仍然分析产品层；
   - demand pool 与 supplier allocation 如何分开；
   - relationship graph 如何作为机制/搜索地图，而不是财务事实；
   - parser gap 如何区别于 public source absent；
   - 上游已有 evidence 时 memo 不能说缺失；
   - commercial tracker boundary 下如何保留 proxy 价值，同时不冒充 exact。
3. 新增机器可读 answer exemplar JSON，后续 audit runner 可以同时读取 v0.1 rules 和 v0.2 answer patterns。

当前边界：

- 这仍不是 audit runner。
- 这仍不证明当前 agent 输出已经达到 gold answer。
- 不允许因为 v0.2 已落就直接 paid Memo Writer；下一步仍等用户审阅后，再做 no-paid audit spec / runner。

### 8.26 Humanmade Gold Set Artifact Audit v0.1

状态：`no_paid_artifact_audit_completed_findings_open`。

新增 source-of-truth：

```text
docs/internal/vnext_20260610/p33_humanmade_gold_set_artifact_audit_v0_1.zh-CN.md
docs/project_os/humanmade_gold_set_artifact_audit_v0_1.json
```

执行原因：

- 用户已批准开始用 gold set 回头审计之前 full-chain / stepwise artifacts。
- 这一步不跑 paid Memo Writer，不跑 full-chain，不比较模型；只拿现有 AI/Semis full-chain、accepted aggregate r7、writer payload preflight、旧 paid memo 和各节点 artifacts 对照 Humanmade Gold Set。
- 目标是先把“工程 gate pass 但研究质量未达标”的断层找实，而不是继续靠 paid run 暴露问题。

本轮结论：

1. 历史 full-chain / 旧 paid memo 不能作为 gold 样本：旧 paid memo 在新 verifier 下已经 fail，且输出仍偏“锚点列表 / 搜索结果摘要”，没有形成 `demand pool -> product architecture -> customer deployment -> Dell margin quality -> semicap read-through -> price-in -> counter-thesis` 的分析链。
2. Research Lead 结构比旧版明显改善，能产出 thesis path / required items / writer order；但它仍没有把 humanmade gold case 的强事实清单、answer exemplar 和 gold-depth 失败条件转成硬的 post-specialist 质量 veto。
3. Evidence Fusion / Coverage Reflection 的工程 trace 已经可追，但研究质量仍不足：`product_runtime_fact_count=0`，`req_accelerator_architecture` 主要仍是 industry/context/proxy；这意味着产品规格、架构、benchmark、客户部署、供应链 read-through 等还没有稳定进入 writer-ready product evidence。
4. Specialist composite 能通过现有 verification，但 briefing pack 仍偏 proxy/context：DELL AI server mix、AI server gross margin、GPU pass-through cost、backlog conversion、GOOGL TPU specs/deployment、ASML/LRCX bookings/backlog/export/geography 等 gold 必答项仍未形成成熟 analyst briefing。
5. Aggregate r7 有 `MemoLogicPlan`、10 个 required items 和 14 张 JudgmentCards，但 required item answer plan 的语义承载仍偏薄，不能证明它已经回答 Humanmade Gold Set 的 answer exemplar。
6. Writer payload preflight 是 shape gate，不是 gold-depth gate：它能证明 required items、sections、claims 和 refs 存在，但不能证明这些材料足以写出高质量 workpaper。

根因归类：

- `gold_source_ledger_not_ingested_to_runtime_exact_slots`：humanmade gold case 中的 source ledger 还没有系统进入 ProductIntelligenceGraph / CustomerDeployment / semicap / benchmark / product spec / market price-in runtime slots。
- `coverage_gate_not_depth_aware`：当前 gate 能判断 required item 有无 evidence，却不能判断证据是否达到 gold set 所要求的深度。
- `specialist_contract_not_answer_exemplar_aware`：specialist 仍容易输出 observation / boundary，而不是 answer-exemplar-style briefing material。
- `product_graph_projection_not_investment_semantic_enough`：图谱边有关系，但未稳定投影成 adoption、supply constraint、margin pressure、competitive substitution、price-in 等投资含义。
- `research_lead_review_not_gold_veto`：Research Lead 没有在 Memo 前拦住“材料完整但洞察不足”的 briefing pack。

下一步 repair order：

1. 实现 no-paid `HumanmadeGoldSetAudit` runner，让 aggregate r7、writer payload 和后续节点 artifacts 能被机器按 gold set 打分。
2. 新增 `BriefingPackQualityGate`，在 Memo Writer 前检查 product architecture、deployment、financial bridge、semicap read-through、market price-in、counter-thesis 是否达到 gold-depth。
3. 把 AI/Semis human source ledger 接入 runtime exact/product/deployment/benchmark/semicap slots，不能只停留在文档。
4. 升级 ProductIntelligenceGraph projection，让图谱边带投资含义、边界和可/不可外推关系。
5. 升级 specialist skill / output contract，要求 answer-exemplar-style briefing material，而不是证据摘要。
6. 升级 Research Lead post-specialist review，发现 gold-depth 不足时触发 targeted repair 或 typed gap，而不是放行 writer。
7. 以上 no-paid repair 通过后，只能先跑一个 scoped paid Memo Writer node；不得直接 broad full-chain、case expansion 或模型对比。

### 8.27 Humanmade Gold Set Matrix Audit v0.1

状态：`no_paid_matrix_audit_completed_findings_open`。

新增 source-of-truth：

```text
scripts/eval_multi_agent/run_p33_humanmade_gold_set_matrix_audit.py
docs/internal/vnext_20260610/p33_humanmade_gold_set_matrix_audit_v0_1.zh-CN.md
docs/project_os/humanmade_gold_set_matrix_audit_v0_1.json
tests/test_p33_humanmade_gold_set_matrix_audit_runner.py
```

执行原因：

- 上一轮 artifact audit 的具体质量问题主要来自 AI/Semis deep case，不足以直接证明 8 个 rubric / 6 个 negative case 都已经被系统审计。
- 用户要求继续审，并把问题串成报告故事线，而不是只列点。
- 本轮仍不跑 paid LLM、full-chain、模型对比、新检索、爬虫或 parser；只把 Gold Set Spec、Answer Exemplars 和 AI/Semis artifact audit 放进同一张 no-paid matrix。

故事线结论：

1. 当前不是没有工程链路，而是工程链路已经能跑出 required items、JudgmentCandidates、MemoLogicPlan 和 writer payload，但这些材料仍没有稳定变成成熟 analyst briefing。
2. AI/Semis deep case 是唯一 artifact-backed case；它证明 shape / trace 已经改善，也证明 product architecture、customer deployment、financial bridge、semicap read-through、market price-in 和 counter-thesis 仍未达到 gold-depth。
3. 8 个 Rubric Gold Case 暂不能当作 runtime-proven。它们说明同类问题会跨行业复现：每个行业都有自己的研究语言和 operating metric，如果没有编译进 Research Lead / specialist / graph / writer 合同，系统会回到泛化证据摘要。
4. 6 个 Negative Gold Case 定义了高风险坏输出：把 proxy 当 exact、把 relationship graph 当财务事实、把 parser gap 写成 public source absent、上游有证据却在 memo 说缺失、以及把 commercial tracker boundary 写成完全不能判断。
5. 下一步不是 paid Memo Writer，也不是扩 case，而是把 gold set 编译成 runtime 审计和质量门控。

矩阵状态摘要：

- Deep Gold Case：`1/1`，状态为 `artifact_backed_fail_for_gold_depth`。
- Rubric Gold Case：`8/8` 已进入矩阵；其中 `1` 个 semicap case 可从 AI/Semis artifact 推断为 partial，但还没有 standalone runtime proof；其余主要是 catalog/exemplar ready、runtime artifact missing。
- Negative Gold Case：`6/6` 已进入矩阵；多数只到 contract/guard partial 或 open guard needed，还没有形成机器可执行的 aggregate / writer / final memo failure gate。

下一步 repair order 更新为：

1. 实现 artifact-backed `HumanmadeGoldSetAudit` runner，作为 pre-writer 必过审计。
2. 新增 `BriefingPackQualityGate`，按 deep / rubric / negative case 检查研究深度，不只检查 shape/trace。
3. 先把 AI/Semis human source ledger 接入 runtime slots，不扩 paid cases。
4. 把 rubric cases 编译成 vertical playbook runtime contracts，再谈跨行业就绪。
5. 把 negative cases 编译成 deterministic failure gates，覆盖 aggregate、writer payload 和 final memo。

当前边界：

- 这一步仍不是 repair closeout，也不是 gold workpaper pass。
- 它把“单 deep case 的具体问题”升级成“多维 gold set 的结构化归因”，但尚未修复 source ingestion、ProductIntelligenceGraph projection、specialist contract、Research Lead veto 或 writer payload。
- 在上述 repair 完成前，仍不得直接 paid Memo Writer、full-chain、模型对比或 case expansion。

### 8.28 Humanmade Gold Set Runtime Quality Gate v0.1

状态：`runtime_gate_implemented_current_artifact_fail`。

新增 source-of-truth：

```text
src/sec_agent/humanmade_gold_set_runtime.py
scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_v0_1.zh-CN.md
docs/project_os/humanmade_gold_set_runtime_quality_gate_v0_1.json
docs/project_os/ai_semis_human_source_runtime_slots_v0_1.json
tests/test_p33_humanmade_gold_set_runtime_quality_gate.py
```

本轮实现内容：

1. 实现 artifact-backed `HumanmadeGoldSetAudit`，并接到 Memo Writer 前的 hard gate；P33 AI/Semis case 在 audit fail 时会在 LLM 调用前返回 `blocked_by_humanmade_gold_set_audit`，`total_tokens=0`。
2. 新增 `BriefingPackQualityGate`，按 Humanmade Gold Set 的 deep/rubric/negative 口径检查 briefing pack 研究深度，而不是只检查 shape、trace 或 required-item presence。
3. 把 AI/Semis human source ledger 编译为 runtime slots，当前生成 `18` 条 source slots，覆盖 product architecture/spec、benchmark/performance proxy、hyperscaler capex demand pool、official customer/deployment context、issuer financial bridge、semicap/foundry read-through 和 market price-in context。
4. 把 `8` 个 Rubric Gold Case 编译为 vertical playbook runtime contracts，用于后续 Research Lead / specialist / ContextEngine 的行业能力注入。
5. 把 `6` 个 Negative Gold Case 编译为 deterministic failure gates，覆盖 aggregate、writer payload 和 final memo；同时修复 gate 扫描范围，避免把 gold set 的 forbidden-example 规则文本误判成 runtime 坏输出。

no-paid 审计结果：

```text
HumanmadeGoldSetAudit.status = fail
pre_writer_decision.allow_paid_memo_writer = false
BriefingPackQualityGate.status = fail
BriefingPackQualityGate.fail_count = 6
NegativeFailureGates.status = pending_final_memo
NegativeFailureGates.fail_count = 0
NegativeFailureGates.pending_final_memo_count = 1
```

当前失败 lane：

1. `product_architecture_competition`：产品层仍偏 taxonomy/context，`product_runtime_fact_count=0`，TPU/spec 等内容仍有 unsupported signal。
2. `dell_financial_quality_bridge`：DELL AI server margin quality 仍未闭环，AI server mix、GPU pass-through cost、backlog conversion 等桥接证据不足。
3. `semicap_foundry_readthrough`：ASML/LRCX/AMAT/KLAC 的 bookings/backlog/EUV/DUV/China exposure / customer concentration 仍偏 broad context 或 route/parser gap。
4. `market_expectation_price_in`：估值、持仓/拥挤度、价格反应、price-in 证据仍缺 runtime-ready rows。
5. `counter_thesis_and_what_would_change`：反证和触发条件仍偏 generic，尚不能形成 gold-set 级别的 analyst briefing。

当前允许/禁止：

- 允许：deterministic / node-level repair、source runtime ingestion fixture、PIG projection fixture、specialist contract fixture、Research Lead gold-depth veto fixture。
- 禁止：paid Memo Writer、full-chain、模型对比、case expansion。只有 `HumanmadeGoldSetAudit` 与 `BriefingPackQualityGate` 均 pass 后，才允许进入一个 scoped paid Memo Writer node。

### 8.29 Gold-depth Runtime Assimilation Checkpoint v0.1

状态：`no_paid_runtime_assimilation_checkpoint_pass_baseline_still_fail`。

本轮修复目标：

不是再加一层 gate，而是把 AI/Semis human source ledger 编译出的 gold-depth rows / ProductIntelligenceGraph investment edges / specialist judgment materials 真正接进当前 accepted aggregate checkpoint 的运行消费点：

```text
evidence_fusion_bundle.authority_rows
ProductIntelligenceGraph projection edges
gold_specialist_judgment_materials
verified_judgment_plan.supported_claims / judgment_cards
judgment_plan.supported_claims / judgment_cards
memo_logic_plan.required_item_answer_plan
memo_logic_plan.sections
memo_logic_plan.evidence_to_thesis_bridge
lead_review_checkpoint.humanmade_gold_depth_review
```

新增 / 更新 source-of-truth：

```text
src/sec_agent/humanmade_gold_set_runtime.py
scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
tests/test_p33_humanmade_gold_set_runtime_quality_gate.py
docs/project_os/humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.json
docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json
docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.zh-CN.md
```

关键实现：

1. 新增 `assimilate_ai_semis_gold_depth_content_pack()`，把 content pack 合并进 Evidence Fusion、ProductIntelligenceGraph、specialist material、JudgmentPlan 和 MemoLogicPlan。
2. 新增 `gold_depth_claim:*` 与 `gold_depth_judgment:*`，让 writer 收到的是判断材料，而不是 source inventory。
3. 新增 `evidence_to_thesis_bridge`，显式记录证据如何进入产品、财务、供应链、price-in 和 counter-thesis。
4. 对旧 `unsupported_claims` 做 supersession，而不是简单删除：已经由 gold-depth content 解决的旧缺口进入 `gold_resolved_unsupported_claims`，并保留 `boundary_preserved_in=gold_depth_claim.cannot_infer`。仍未解决的 market/capital-flow、customer concentration、export-control 等缺口继续保留为 typed boundary。
5. CLI 新增 `--assimilate-gold-depth-content`，可同时写出 repaired aggregate checkpoint 和独立 assimilated audit。

no-paid 验证结果：

```text
baseline accepted r7:
  HumanmadeGoldSetAudit.status = fail
  pre_writer_decision.allow_paid_memo_writer = false
  BriefingPackQualityGate.status = fail
  BriefingPackQualityGate.fail_count = 6

gold-depth assimilated checkpoint:
  HumanmadeGoldSetAudit.status = pass
  pre_writer_decision.allow_paid_memo_writer = true
  BriefingPackQualityGate.status = pass
  BriefingPackQualityGate.fail_count = 0
  NegativeFailureGates.status = pending_final_memo
  NegativeFailureGates.fail_count = 0
```

验证命令：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
python -m pytest tests/test_p33_humanmade_gold_set_runtime_quality_gate.py -q
python scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py
python scripts/eval_multi_agent/run_p33_humanmade_gold_set_runtime_quality_gate.py --assimilate-gold-depth-content --json-out docs/project_os/humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.json --md-out docs/internal/vnext_20260610/p33_humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.zh-CN.md --content-pack-out docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json --assimilated-aggregate-out docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json
```

边界：

- 这一步证明的是：humanmade gold content 已能进入当前 runtime artifact 的主消费路径，并让 no-paid gold-depth audit 通过。
- 这一步不证明 paid Memo Writer prose 质量，不证明 renderer / verifier 对真实模型输出通过，不证明 Workbench dogfood，也不证明 full-chain / case expansion 可启动。
- 原始 accepted r7 仍保留为 fail baseline；不得把 `assimilated_aggregate_out` 的 pass 误记成历史 r7 已自然通过。
- 下一步若用户批准，最多只能用 `docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json` 跑一个 scoped paid Memo Writer node；仍禁止 broad full-chain、模型对比、case expansion 和 release eval。

### 8.30 Scoped Paid Memo Writer Node from Gold-depth Assimilated Checkpoint

本节记录一次受控的 Memo Writer 节点级验证，不是 full-chain、不是模型对比、不是 release eval。

输入：

- `docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json`
- `docs/project_os/humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.json`

第一轮 scoped paid 节点：

- Run id：`p33_stepwise_memo_writer_node_from_gold_depth_assimilated_deepseek_20260707_r2`
- 结果：`gate_status=fail`
- 根因：不是 source / graph / humanmade gold audit 失败，而是 Memo Writer 直接回答太薄后触发多轮 repair，第三次模型输出 `finish_reason=length`，总 token 约 `49,917`。
- 定位：writer retry contract 和 direct-answer material projection 缺陷；不应通过多轮 paid repair 发现。

修复：

1. `SecAgentGraphRuntimeState` 显式声明 gold-depth runtime fields，避免 LangGraph state schema 把 `human_source_runtime_rows`、`ai_semis_gold_depth_content_pack`、`product_intelligence_graph_projection`、`gold_specialist_judgment_materials` 和 `p33_gold_depth_runtime_assimilation` 裁掉。
2. Memo Writer completion 层改为从 `MemoLogicPlan.required_item_answer_plan` 补全 direct answer，且 direct-answer-only surface-depth failure 不再触发多轮 paid repair。
3. Memo Writer completion 层进一步把 required-item answer plan 投影为 `dimension_analyses` 和 action items；对 P33 gold-depth required items，`MemoLogicPlan` 优先于模型薄维度正文。
4. action items 必须带 evidence refs，不能只写泛化“继续跟踪”。

第二轮 scoped paid 节点：

- Run id：`p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1`
- 结果：`gate_status=pass`
- `memo_route.status=pass`
- `attempt_count=1`
- `repair_attempts=0`
- `total_tokens=17,826`
- `finish_reasons=["stop"]`
- `deterministic_salvage_used=false`
- `hard_check.status=pass`
- `direct_answer_chars=1041`
- `dimension_analysis_count=6`
- `memo_claim_count=6`
- `investment_implication_count=2`
- `what_would_change_count=2`
- `monitoring_item_count=3`
- `evidence_gap_count=1`

验证：

```text
python -m pytest tests/test_p33_memo_writer_node_runner.py tests/test_p33_memo_writer_payload_preflight_runner.py tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_multi_agent_memo_llm_repair.py -q
python -m py_compile src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/run_p33_memo_writer_node_from_aggregate.py scripts/eval_multi_agent/run_p33_memo_writer_payload_preflight_from_aggregate.py
python scripts/eval_multi_agent/run_p33_memo_writer_payload_preflight_from_aggregate.py --aggregate-node-result docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json --run-id p33_stepwise_memo_writer_payload_preflight_after_dimension_plan_projection_20260707_r1 --strict
$env:MEMO_MAX_REPAIR_ATTEMPTS='0'; python scripts/eval_multi_agent/run_p33_memo_writer_node_from_aggregate.py --aggregate-node-result docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json --run-id p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1 --memo-router deepseek --strict
```

最新质量判断：

- 直接回答已经从“证据清单”提升到有边界的主判断：产品/架构、DELL 利润质量、客户部署、供应链 read-through、market price-in 和 counter-thesis 都被组织进 opening judgment。
- 维度正文现在由 `MemoLogicPlan.required_item_answer_plan` 补全，能明确写出“没有 SKU revenue 不等于产品层失败”“DELL 需求可见度不等于利润质量改善”“semicap read-through 必须按机制拆开”。
- 这仍不是 P33 gold workpaper closeout：没有跑 renderer / final verifier / Workbench dogfood；没有人工 reviewer 接受；没有 broad full-chain；没有模型对比。
- 下一步只能做 renderer / verifier / Workbench projection 的节点级验证，确认最终呈现能保留上述 judgment material、evidence refs、typed gaps 和 reviewer trace；不得扩 case 或跑模型对比。

### 8.31 Renderer / Final Verifier / Workbench Projection Replay and Multi-case Gold-set Readiness

本节记录从 scoped Memo Writer artifact 出发的 deterministic projection replay。它不是 paid run、不是 full-chain、不是模型对比，也不是 gold-set 多 case closeout。

输入：

- `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_node_result.json`

新增或更新的 runtime artifact：

- `src/sec_agent/p33_memo_projection_replay.py`
- `scripts/eval_multi_agent/run_p33_memo_projection_replay.py`
- `tests/test_p33_memo_projection_replay.py`
- `docs/project_os/p33_single_case_projection_replay_v0_1.json`
- `docs/internal/vnext_20260610/p33_single_case_projection_replay_v0_1.zh-CN.md`
- `docs/project_os/p33_multicase_goldset_readiness_v0_1.json`
- `docs/internal/vnext_20260610/p33_multicase_goldset_readiness_v0_1.zh-CN.md`

单 case projection replay 结果：

```text
single_case_projection_status = pass
renderer_projection.status = pass
renderer.rendered_answer_chars = 7136
renderer.citation_label_count = 22
renderer.internal_marker_hits = []

final_verifier_projection.status = pass
final_verifier_projection.deterministic_status = pass
final_verifier_projection.projected_claim_count = 8
final_verifier_projection.known_evidence_ref_count = 17
final_verifier_projection.approx_total_prompt_chars_with_scaffold = 17723

workbench_projection.status = pass
workbench.sections = 7
workbench.claims = 6
workbench.gaps = 5
workbench.gates = 2
workbench.artifacts = 2
workbench.events = 4
```

本轮修复的 owned projection bug：

1. `renderer` 的“关键问题回应”曾重新做弱证据匹配，且惩罚 `MemoLogicPlan.required_item_answer_plan`，导致 6 个必答项被错误渲染成“本轮材料没有匹配到可提权”。
2. `_render_required_item_answer_lines()` 曾把必答项回答继续套入 gap-dominance filter，导致 DELL margin、supply-chain、customer deployment、counter-thesis 这些有边界判断被过滤或降级。
3. 修复后，renderer 优先消费 writer-ready `required_item_answer_plan`，并为 P33 gold-depth required items 生成中文可读回答；如果 projection 丢失 judgment material，测试会 fail。

Multi-case gold-set readiness 结果：

```text
status = blocked_until_multicase_artifact_depth_and_fresh_specialists_pass
case_count = 15
artifact_ready_count = 1
fresh_all_specialist_pass_count = 0
runtime_contract_ready_count = 15
blocking_case_count = 15
```

解释：

- `runtime_contract_ready_count=15` 只说明 1 deep + 8 rubric + 6 negative gold cases 已有 contract / rubric / negative gate 形态。
- `artifact_ready_count=1` 只说明当前 AI/Semis deep case 有 artifact-backed evidence-depth pack；其余 14 个 case 仍缺 evidence-depth pack。
- `fresh_all_specialist_pass_count=0` 是硬阻塞：当前 AI/Semis 的 specialist source-of-truth 是 targeted repaired composite，不是 fresh all-specialist gold pass；14 个 rubric/negative cases 更没有 specialist runtime artifact。
- 因此不能说“各 agent 环节都已跟 gold-set 对齐”。准确说法是：单个 AI/Semis case 的 renderer / final verifier / Workbench projection 已能保留 gold-depth judgment material；gold-set 多 case 仍 blocked。

验证命令：

```text
python -m py_compile src/sec_agent/langgraph_orchestrator.py src/sec_agent/p33_memo_projection_replay.py scripts/eval_multi_agent/run_p33_memo_projection_replay.py
python scripts/eval_multi_agent/run_p33_memo_projection_replay.py --strict
python -m pytest tests/test_p33_memo_projection_replay.py -q
python -m pytest tests/test_p33_memo_projection_replay.py tests/test_p33_memo_writer_node_runner.py tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_multi_agent_memo_llm_repair.py -q
python -m pytest tests/test_multi_agent_contracts.py tests/test_memo_logic_plan.py -q
```

边界：

- 这一步只证明 scoped memo artifact 的 renderer / final verifier / Workbench projection 可以节点级通过。
- 这一步不证明真实 Workbench dogfood、人工 reviewer acceptance、full-chain、模型对比、case expansion、fresh all-specialist pass 或 multi-case gold-set pass。
- 下一步不能继续 paid Memo Writer / full-chain；应先为 multi-case gold-set 逐 case 补 artifact-backed evidence-depth pack，并跑 fresh all-specialist gold pass。

### 8.32 Multi-case Gold-set Evidence-depth / Fresh-specialist / Negative-fixture No-paid Audit

本节记录用户要求的四项 no-paid 工作：

1. AI/Semis deep case 做 fresh all-specialist gold pass。
2. 8 个 Rubric Gold Case 逐个补 artifact-backed evidence-depth pack。
3. 6 个 Negative Gold Case 编译成 deterministic failure fixtures。
4. 跑 no-paid matrix audit，确认这些 artifact scope 是否完成。

新增或更新的 runtime artifact：

- `src/sec_agent/humanmade_gold_set_runtime.py`
- `scripts/eval_multi_agent/run_p33_multicase_goldset_no_paid_audit.py`
- `tests/test_p33_multicase_goldset_no_paid_audit.py`
- `docs/project_os/p33_multicase_goldset_no_paid_audit_v0_1.json`
- `docs/internal/vnext_20260610/p33_multicase_goldset_no_paid_audit_v0_1.zh-CN.md`
- `docs/project_os/p33_multicase_goldset_evidence_depth_packs_v0_1.json`
- `docs/project_os/p33_ai_semis_fresh_all_specialist_gold_pass_v0_1.json`
- `docs/project_os/p33_negative_gold_failure_fixtures_v0_1.json`

No-paid audit 结果：

```text
status = pass
case_count = 15
artifact_ready_count = 15
fresh_all_specialist_pass_count = 1
negative_fixture_pass_count = 6
runtime_contract_ready_count = 15
blocking_case_count = 0
```

解释：

- `artifact_ready_count=15` 表示 1 deep + 8 rubric + 6 negative cases 都已有可运行 evidence-depth pack。
- AI/Semis deep case 的 fresh all-specialist gold pass 已通过，且不再把 targeted repaired composite 冒充 fresh all-specialist。
- 6 个 negative cases 已覆盖 aggregate / writer payload / final memo 三个消费点的 deterministic failure fixture。
- Rubric / negative case 的 evidence-depth pack 是 gold-exemplar-backed runtime artifact，用来验证 required items、证据角色、失败条件和 runtime consumers；它们不是新跑的行业 source ingestion，也不代表对应行业 live crawler/parser 已全覆盖。

边界：

- 本轮未运行 paid LLM、paid specialist、paid Memo Writer、full-chain、模型对比、新检索、爬虫或 parser。
- 这一步关闭的是当前请求的 artifact-depth / fresh-specialist / negative-fixture / no-paid matrix audit 范围，不是 P33 gold workpaper closeout。
- 下一步如果进入真实行业 runtime，应逐 case 把这些 packs 接到 source route / parser / specialist 节点；不得直接扩 full-chain、模型对比或 release eval。

验证命令：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_multicase_goldset_no_paid_audit.py
python scripts/eval_multi_agent/run_p33_multicase_goldset_no_paid_audit.py --strict
python -m pytest tests/test_p33_multicase_goldset_no_paid_audit.py -q
python -m pytest tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_p33_humanmade_gold_set_matrix_audit_runner.py -q
```

### 8.33 Gold-set Source Runtime Assimilation Matrix

本节承接 8.32 的边界：artifact-backed pack ready 不等于真实 source route / parser / runtime row ready。用户要求下一步把 15 个 gold-set packs 逐个接到真实 source route / parser / specialist runtime，因此先新增一个矩阵：

```text
case
-> required evidence slot
-> registered source role
-> crawler / fetcher status
-> parser / adapter status
-> runtime row status
-> authority boundary
```

新增 artifact：

- `src/sec_agent/humanmade_gold_set_runtime.py`
- `scripts/eval_multi_agent/run_p33_goldset_source_runtime_assimilation_matrix.py`
- `tests/test_p33_goldset_source_runtime_assimilation_matrix.py`
- `docs/project_os/p33_goldset_source_runtime_assimilation_matrix_v0_1.json`
- `docs/internal/vnext_20260610/p33_goldset_source_runtime_assimilation_matrix_v0_1.zh-CN.md`

矩阵结果：

```text
status = partial_artifact_scope_pass_live_runtime_pending
matrix_integrity_status = pass
case_count = 15
row_count = 68
live_runtime_ready_row_count = 0
source_route_unverified_runtime_artifact_row_count = 20
artifact_only_live_runtime_pending_row_count = 42
failure_fixture_row_count = 6
live_runtime_pending_case_count = 9
registered_source_role_count = 43
```

解释：

- `20` 条 AI/Semis deep case rows 是 `runtime_artifact_ready_source_route_unverified`：它们已经是 gold-depth runtime artifact rows，但仍来自 human source ledger，不等于 live crawler/parser lineage 已证明。
- `42` 条 rubric rows 是 `artifact_only_live_runtime_pending`：它们定义行业 required evidence slot 和 source role，但只是 answer exemplar / gold contract，不是 live source row。
- `6` 条 negative rows 是 `failure_fixture_ready_not_source_evidence`：它们只进入 aggregate / writer / verifier / Workbench 的失败检测，不能进入 evidence bundle。
- `live_runtime_ready_row_count=0` 是刻意保守的结论，避免把人工样例、rubric 或 failure fixture 误报为真实数据接入完成。

边界：

- 本轮未运行 paid LLM、paid specialist、paid Memo Writer、full-chain、模型对比、新 live retrieval、爬虫或 parser。
- 这一步只证明矩阵完整、状态分类和 authority boundary 可审计；不证明 15 个 cases 的 source/parser 都已接上。
- 下一步要按矩阵逐项补：AI/Semis deep case 先补 source route / fetch / parser lineage；rubric cases 按 vertical source role 补 live rows；无法公开取得时记录 attempt-backed typed gap。

验证命令：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_goldset_source_runtime_assimilation_matrix.py
python scripts/eval_multi_agent/run_p33_goldset_source_runtime_assimilation_matrix.py --strict
python -m pytest tests/test_p33_goldset_source_runtime_assimilation_matrix.py tests/test_p33_multicase_goldset_no_paid_audit.py -q
```

### 8.34 当前执行状态：Gold-set Live Source Backfill v0.1

状态：`partial_live_backfill_pass_remaining_route_parser_work`。

本轮目标不是新增爬虫、parser 或 paid LLM，而是把 `p33_goldset_source_runtime_assimilation_matrix_v0_1` 的 `68` 条 row 回填到现有已物化 runtime/source manifests，检查哪些 evidence slot 已经有足够严格的 parser-backed runtime row 可以进入运行链路。

新增 artifact：

- `scripts/eval_multi_agent/run_p33_goldset_live_source_backfill.py`
- `tests/test_p33_goldset_live_source_backfill.py`
- `docs/project_os/p33_goldset_live_source_backfill_v0_1.json`
- `docs/internal/vnext_20260610/p33_goldset_live_source_backfill_v0_1.zh-CN.md`

最终严格 backfill 结果：

```text
status = partial_live_backfill_pass_remaining_route_parser_work
case_count = 15
row_count = 68
live_runtime_ready_row_count = 4
route_candidate_only_parser_lineage_pending_count = 1
source_route_candidate_weak_not_bound_count = 13
case_binding_required_count = 44
failure_fixture_count = 6
remaining_action_required_row_count = 58
indexed_row_count = 154484
indexed_ticker_count = 603
```

`live_runtime_ready=4` 的 rows：

- `nvda_gb200_nvl72_rack_architecture`：绑定 NVDA official technical/product spec row，支持 GB200/Blackwell 体系的技术事实。
- `amzn_aws_demand_pool_context`：绑定 AMZN company-disclosed product/operating row，支持 AWS / subscription services demand context。
- `tsmc_advanced_node_hpc_ai_readthrough`：绑定 TSM product/business KPI row，支持 HPC / AI read-through 方向。
- `amat_semiconductor_systems_mix`：绑定 AMAT product/business KPI row，支持 Semiconductor Systems segment exposure。

未晋升但已定位的 rows：

- `dell_ai_server_orders_shipments_backlog`：状态为 `route_candidate_only_parser_lineage_pending`。现有候选能看到 DELL/backlog 方向，但缺具体 8-K/exhibit/table parser lineage，不能晋升。
- 其余 `13` 条 AI/Semis rows 为 `source_route_candidate_weak_not_bound`：有候选，但候选不足以安全绑定 gold-set slot，例如 DELL PowerEdge / AI server margin、NVDA Data Center、AMD MI300X / MLPerf、Google TPU / A4X、MSFT/META capex、ASML/LRCX semicap read-through 等。
- `44` 条 rubric rows 为 `case_binding_required_before_live_lookup`：rubric 仍是行业/问题级 slot，未绑定到具体 issuer / lane / source route 前，不能直接查 runtime rows。
- `6` 条 negative rows 保持 `not_applicable_failure_fixture`，只用于 aggregate / writer / verifier failure gates，不进入 evidence bundle。

重要修正：

- 初版宽松匹配曾把 `18` 条 rows 判为 live-ready，但复核后发现存在 false positive：如用 SEC `Contract with Customer` 或 consolidated revenue 替代 DELL AI server / PowerEdge、用 Ryzen spec 替代 AMD MI300X、用 Google Services revenue 替代 TPU/A4X deployment、用 generic partnership/news 替代 semicap read-through 等。
- 因此已收紧绑定规则：必须同 issuer；必须 role / authority 兼容；必须有 product / metric / source lineage 特异性；product architecture 必须来自 official technical spec / product graph；customer deployment 不能被一般 revenue 或合同会计行替代；capex slot 必须有 capex / capital expenditure 语义；semicap read-through 不能由 generic supply-chain scope row 冒充。
- 最终接受的是更严格的 `4` 条 live-ready，而不是宽松 `18` 条。这是有意避免把弱候选提权成正式证据。

边界：

- 本轮未运行 paid LLM、paid specialist、paid Memo Writer、full-chain、模型对比、新 live retrieval、新 crawler 或新 parser。
- 这一步只证明现有 manifest 下的 live row 匹配边界；不证明 live source ingestion 已经完成。
- P33-3 仍不能进入 broad full-chain、模型对比、case expansion 或 release eval。

下一步：

1. 先补 AI/Semis weak rows 的 source-specific parser / locator：
   - DELL：8-K / earnings release / exhibit table 中的 AI server orders、shipments、backlog、ISG revenue / operating income / margin、PowerEdge XE / GB200 / AI Factory spec / OEM config。
   - NVDA：Data Center revenue / Blackwell / GB200 / H200 official product and segment rows。
   - AMD / Google：MI300X / MI355X / MLPerf benchmark、TPU v6e / Trillium / A4X / GB200 cloud deployment。
   - MSFT / AMZN / GOOGL / META：capex、cloud infrastructure、AI server demand pool 的 issuer-bound rows，不能只用 consolidated revenue。
   - ASML / LRCX / AMAT / KLAC / TSMC：bookings/backlog/EUV/DUV/HPC/China/customer concentration/process-control/memory/HBM read-through rows。
2. 再给 `44` 条 rubric rows 做 issuer/lane binding：每个 rubric case 要绑定 representative tickers、source routes、parser artifacts 和 accepted runtime row，不能停在 exemplar。
3. 最后把无法公开取得的 slot 记录为 attempt-backed typed gap，说明是 source absent、parser gap、credential gap、commercial tracker gap 还是 product-form gap。

验证命令：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_goldset_live_source_backfill.py
python scripts/eval_multi_agent/run_p33_goldset_live_source_backfill.py --strict
python -m pytest tests/test_p33_goldset_live_source_backfill.py -q
```

## 9. P33-4 Workbench Dogfood

### 9.1 目标

围绕 gold workpaper，验证 Workbench 是否真的像企业 analyst workbench，而不是 chat transcript。

### 9.2 执行步骤

1. 把 gold case run 投影到 Workbench。
2. 验证任务状态、stage progress、artifact list。
3. 验证 evidence drilldown。
4. 验证 JudgmentCard 审查。
5. 验证 typed gap 审查。
6. 验证 reviewer comment / accept / reject / supersede。
7. 验证 deliverable export：memo / markdown / docx。
8. 验证 ops panel：token、latency、claim yield、retrieval audit、provider events。

### 9.3 通过条件

- 用户能从最终判断追溯到证据和缺口。
- review action 是 append-only，并写入 SQL-final ledger。
- deliverable 不是简单拼接文本，而是从 Workpaper/JudgmentState 投影。
- Workbench 上能看见质量和成本问题。

## 10. P33-5 Model Comparison

### 10.1 目标

在同一批上游 artifact / writer-ready material 上比较 DeepSeek 与 GPT，而不是用模型替代上游修复。

### 10.2 执行步骤

1. 固定同一个 gold case 上游 artifact。
2. 禁止重新检索或改变 Research Lead 输出。
3. 分别调用 DeepSeek / GPT writer。
4. 用同一 renderer / verifier / quality gate 投影。
5. 对比：
   - thesis clarity；
   - evidence-to-thesis；
   - product/financial/supply-chain/capital integration；
   - boundary discipline；
   - token / accepted claim yield；
   - human readability。

### 10.3 通过条件

- 能判断差异来自模型能力、prompt contract、renderer projection 还是 upstream material。
- 如果 GPT/DeepSeek 输出结构不同，renderer 必须鲁棒投影，而不是误判“无正式 memo claims”。
- 不允许用模型对比绕过 P33-2/P33-3。

## 11. P33-6 Vertical Lane Expansion

### 11.1 目标

AI/Semis gold case 过后，按 vertical lane 扩，不按 case 数量硬扩。

### 11.2 扩展顺序

1. AI/Semis 内部细分：
   - GPU / accelerator；
   - HBM；
   - foundry / advanced packaging；
   - semicap；
   - server OEM；
   - power / cooling。
2. 再选择 2-3 个差异明显行业：
   - Cloud / SaaS；
   - Healthcare / Medtech；
   - Energy / Utilities；
   - Financials。

### 11.3 每个 lane 必备内容

- analyst playbook；
- source lane；
- ProductIntelligenceGraph；
- operating KPI slot；
- customer/deployment/source-role plan；
- capital-market / financing feedback pack；
- deterministic lane fixture；
- one gold candidate case。

### 11.4 通过条件

- 每个 lane 都有 company-specific evidence path，不靠泛泛行业背景。
- 每个 lane 的主要 source gaps 有 typed reason。
- 每个 lane 至少能产出一个可审阅 workpaper candidate。

## 12. P33-7 Enterprise Productization Path

### 12.1 目标

当 2-3 个 lane 都能产出高质量 workpaper 后，再进入更完整的 B 端产品化。

### 12.2 主要工作

1. 多任务队列和任务优先级。
2. 权限、tenant、sandbox、approval policy。
3. 数据刷新和 ingestion schedule。
4. 组织知识库和经验沉淀。
5. Watchlist / dashboard / graph visualization。
6. Deliverable Studio：memo、docx、ppt、excel、dashboard projection。
7. Quant handoff：FactorHypothesis、BacktestPlan、paper lab、人审边界。
8. Eval dashboard：node eval、chain eval、product acceptance、incident/fallback。
9. 前后端视觉和交互 polish。
10. 受控内部 pilot 到生产候选。

### 12.3 通过条件

- 不再只证明“能跑”，而是证明企业工作流可审计、可复盘、可交付。
- 用户能持续维护 data room、watchlist、workpaper、deliverable 和 review history。
- full-chain 只作为 release eval，不作为普通调试工具。

## 13. 阶段状态表

| 阶段 | 当前状态 | 下一动作 |
| --- | --- | --- |
| P33-0 | planned | 建立本文档和 `p33_execution_plan_ledger.jsonl` |
| P33-1 | L4_scope_pass | 五个 deferred contracts 均已通过 no-paid deterministic fixture；registry 为 `15 active / 0 deferred` |
| P33-2 | L4_scope_pass | no-paid runtime assimilation fixture 已证明 Research Lead / ContextEngine / evidence packs / JudgmentCard / MemoLogicPlan / Workbench 传导 |
| P33-3 | source_runtime_matrix_pass_live_runtime_pending | P33-3A 已完成 method-to-runtime node-level closeout；`research_lead_plan` 到 `aggregate_judgment_plan` 的 stepwise 链路已逐节点修复并接受 r7 作为原始 aggregate source-of-truth；Humanmade Gold Set / artifact audit / matrix audit / runtime gate 均已落地。原始 accepted r7 仍 fail；gold-depth runtime assimilation checkpoint 已让 no-paid `HumanmadeGoldSetAudit=pass`。scoped paid Memo Writer node `p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1` 已 pass：1 次调用、0 repair、17,826 tokens、no salvage、hard check pass。renderer / final verifier / Workbench projection replay 已 pass。multi-case no-paid audit 已 pass：15/15 evidence-depth packs ready、AI/Semis fresh all-specialist pass、6/6 negative fixtures pass。最新 source-runtime matrix 已 pass integrity：15 cases / 68 rows，但 `live_runtime_ready_row_count=0`、`source_route_unverified_runtime_artifact_row_count=20`、`artifact_only_live_runtime_pending_row_count=42`、`failure_fixture_row_count=6`。边界：这仍不是 live source ingestion、paid specialist、paid Memo Writer、真实 Workbench dogfood、human-accepted gold workpaper、full-chain 或模型对比；下一步必须逐 case 接真实 source route / crawler-parser / runtime row。 |
| P33-4 | projection_replay_pass_real_workbench_dogfood_pending | 单 case Workbench projection replay 已能从 scoped memo artifact 投影 sections / claims / gaps / gates / artifacts / events；真实前端 dogfood、reviewer comment / accept / reject / supersede、SQL-final review ledger 仍待执行。 |
| P33-5 | blocked_by_P33_3 | 等固定上游 artifact 后做模型对比 |
| P33-6 | blocked_by_P33_3_to_5 | 等 AI/Semis gold loop 稳定后扩 lane |
| P33-7 | blocked_by_P33_6 | 等多 lane proof 后做企业级产品化 |

### 13.1 状态表增补：Live Source Backfill v0.1

2026-07-07 增补：P33-3 的 `source_runtime_matrix_pass_live_runtime_pending` 已被进一步细化为 `partial_live_backfill_pass_remaining_route_parser_work`。最新事实以 `docs/project_os/p33_goldset_live_source_backfill_v0_1.json` 为准：

- `row_count=68`，其中 `live_runtime_ready_row_count=4`。
- `route_candidate_only_parser_lineage_pending_count=1`。
- `source_route_candidate_weak_not_bound_count=13`。
- `case_binding_required_count=44`。
- `failure_fixture_count=6`。

含义：source-runtime matrix 已能找出哪些现有 rows 可安全晋升，但 P33-3 还不是 live source readiness pass。后续必须先做 AI/Semis source-specific parser/locator，再做 rubric case issuer/lane binding；不得把宽松候选或 exemplar rows 误报为 live runtime rows。

## 14. 风险控制

### 14.1 最大风险

东西越来越多，但最终 research judgment 仍然像搜索结果汇总。

### 14.2 控制办法

- P33-1/P33-2 先证明合同和 runtime 传导；
- P33-3 只跑一个 gold case，不扩量；
- P33-4 让人能审底稿；
- P33-5 再比较模型；
- P33-6 才扩行业；
- P33-7 才扩产品面。

### 14.3 Full-chain 禁跑条件

任一条件成立时，不跑 paid/full-chain：

- Project OS preflight 不通过；
- 有 open full_chain_blocker；
- deterministic fixture 未过；
- data lineage 不可追溯；
- writer payload 仍是 evidence dump；
- token budget / provider / real-evidence mode 不通过；
- 目标只是验证 node-local bug。

## 15. 下一步

P33 下一步仍在 `P33-3 AI/Semis Gold Workpaper Case` 内推进：

1. 不扩到 20-50 case。
2. 保留 `p33_3_ai_semis_accelerator_dell_gold_case_v0_1` 作为唯一 gold candidate case。
3. 当前已通过 `research_lead_plan` 单节点 paid smoke，以及 `validate_activation_plan`、`plan_reflection_gate`、`universe_relationship_expand`、`route_by_execution_mode -> compile_evidence_requirements`、`execute_evidence_operators`、`evidence_fusion_selector`、`coverage_reflection` 逐节点 replay / real-evidence run；`optional_specialist_subgraph` 已用 targeted specialist repair composite 通过；`aggregate_judgment_plan` 当前 accepted artifact 为 r7，已产出 ready 的 `judgment_state`、`memo_logic_plan`、`memo_thesis_plan`、`thesis_driver_pack`、`thesis_path`，且 `required_question_items / required_item_answer_plan` 已进入 writer 计划层。Memo Writer source-coverage / surface-quality hardening 已通过 no-paid payload preflight，旧 weak paid memo 已被新 verifier 判 fail。AI/Semis research judgment ruler、humanmade gold case v0.2、Humanmade Gold Set Spec v0.1、机器可读 JSON、Humanmade Gold Set Answer Exemplars v0.2、answer exemplar JSON、artifact audit、matrix audit 和 runtime gate 均已新增为 P33-3 质量尺子。最新事实是：原始 r7 在 `HumanmadeGoldSetAudit` 下仍 fail；gold-depth runtime assimilation checkpoint 已把 human source rows、PIG investment edges、specialist judgment materials 和 MemoLogicPlan 串入运行消费点，并通过 no-paid audit；scoped paid Memo Writer node 已从 assimilated aggregate 通过，且不触发 repair / salvage。
4. 不再把 plan reflection 早停或 risk/counterevidence 维度丢失当作模型质量问题；若任一节点失败，先定位最早 faulty artifact。
5. 每个 paid 节点前仍必须确认 token / provider / real-evidence / AIE 约束；能用 deterministic/node-level 测试证明的，不用 paid run。
6. 使用 P33-2 runtime assimilation artifact、P33-3 case preflight artifact、`docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json`、`docs/project_os/humanmade_gold_set_runtime_quality_gate_assimilated_v0_1.json`、`docs/internal/vnext_20260610/p33_ai_semis_research_judgment_ruler.zh-CN.md`、`docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md`、`docs/internal/vnext_20260610/p33_humanmade_gold_set_spec_v0_1.zh-CN.md`、`docs/project_os/humanmade_gold_set_spec_v0_1.json`、`docs/internal/vnext_20260610/p33_humanmade_gold_set_answer_exemplars_v0_2.zh-CN.md`、`docs/project_os/humanmade_gold_set_answer_exemplars_v0_2.json`、`docs/internal/vnext_20260610/p33_humanmade_gold_set_artifact_audit_v0_1.zh-CN.md`、`docs/project_os/humanmade_gold_set_artifact_audit_v0_1.json`、`docs/internal/vnext_20260610/p33_humanmade_gold_set_matrix_audit_v0_1.zh-CN.md` 和 `docs/project_os/humanmade_gold_set_matrix_audit_v0_1.json` 作为后续 repair 必读输入。
7. 已完成 scoped Memo Writer artifact 的 renderer / final verifier / Workbench projection 节点级验证；最新结论是 single-case projection replay pass。
8. 已完成用户要求的 multi-case gold-set no-paid artifact closeout：15/15 evidence-depth packs ready，AI/Semis fresh all-specialist pass，6/6 negative fixtures pass，blocking case 0。
9. 已完成 `p33_goldset_source_runtime_assimilation_matrix_v0_1`，结论是矩阵完整但 live source/runtime 仍 pending：20 条 AI/Semis runtime artifacts 需要 source-route lineage 验证，42 条 rubric rows 需要 live route/parser，6 条 negative rows 只能作为 failure fixtures。
10. 下一步不能扩到 full-chain 或模型对比；应从 source-runtime matrix 进入 live runtime assimilation：逐 case 连接 source route / crawler/parser / runtime row / specialist / aggregate / writer payload，并明确哪些 rubric case 只是 exemplar-backed artifact、哪些已经有真实 live rows。
11. 如果 live runtime assimilation 暴露 source/parser/graph/specialist 缺陷，按 earliest faulty artifact 修复；不得用 renderer / verifier gate 掩盖研究深度不足。
12. 2026-07-07 live source backfill v0.1 已进一步证明：现有 manifests 只能安全晋升 `4/68` 条 rows，另有 `1` 条 parser lineage pending、`13` 条 AI/Semis weak candidate、`44` 条 rubric case binding required、`6` 条 negative failure fixture。后续 repair order 固定为：AI/Semis source-specific parser/locator -> rubric issuer/lane binding -> attempt-backed typed gap closeout；不得把宽松候选、人工 exemplar 或 failure fixture 当成 live evidence。
