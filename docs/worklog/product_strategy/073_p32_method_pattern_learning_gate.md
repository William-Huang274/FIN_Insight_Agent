# P32 Method & Pattern Learning Gate

日期：2026-07-04

## 背景

用户指出，金融业务理解和 agent 工程经验不能靠 Codex 的泛化常识、几个网页总结或越来越长的 skill 来解决。券商长篇行业报告虽然不作为最终输出格式，但它对研究方向、信息范围、行业问题拆解和见解深度有参考价值；同理，外部 agent / RAG / workflow 技术也必须结合 FIN_Insight_Agent 的项目状态吸收，而不是列框架名。

## 决策

新增 P32 学习门控，把“学习”做成项目能力的一部分：

1. 先读项目现状、P30/P31 blockers、PRD/R 系列和 worklog，不靠记忆推进。
2. 外部金融研究方法和 agent 工程模式先进入 learning ledger。
3. 每条 source 必须说明为什么相关、能吸收什么、不能吸收什么、落到哪个 FIN 对象。
4. 只有经过 L2 extraction、L3 contract translation 和 L4 no-paid deterministic proof 的方法/模式，才能进入 active registry 或 runtime。

## 新增/更新文件

- `docs/internal/vnext_20260610/r53_r60_p32_method_pattern_learning_gate.zh-CN.md`
- `docs/project_os/financial_research_method_learning_ledger.jsonl`
- `docs/project_os/agent_engineering_pattern_learning_ledger.jsonl`
- `docs/project_os/README.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/worklog/README.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`

## 首批 source 选择

金融研究方法首批选择：

- Morgan Stanley AI thematic public report：用于 AI/Semis thematic framing、enabler/adopter、rate-of-change 和披露边界。
- Stanford / Addepar investment memo process：用于 Workpaper lifecycle、review、approval、post-decision learning。
- NVIDIA GB200 NVL72 official product page：用于 official product surface、technical fact authority 和 ProductIntelligenceGraph。
- Deloitte semiconductor outlook：用于行业周期和 AI/Semis context。
- Equity research structure public training：只作为基础章节拆分参考，不作为 FIN 输出模板。

Agent 工程模式首批选择：

- LangGraph checkpoint / time travel：用于 targeted repair、checkpoint replay 和避免整链重跑。
- MCP specification：用于 tools/resources/prompts 权限和工具合同边界。
- Temporal human-in-the-loop durable workflow：用于长任务审批、resume 和 workflow history。
- OpenTelemetry GenAI semantic conventions：用于 token/tool/retrieval/eval 可观测性。
- R56/R57 记录的 Hermes-style ContextEngine：用于 context resolve/select/compress/inject/write/invalidate。

## 当前状态

P32 当前达到 `in_progress_l2_extraction_started`。这代表 source discovery / qualification 已启动，并且首批 source 已经抽成候选方法/模式 rows；不代表方法已经吸收完成，更不代表 runtime 或 memo 质量已改善。

新增 L2 extraction ledgers：

- `docs/project_os/financial_research_method_extraction_ledger.jsonl`
- `docs/project_os/agent_engineering_pattern_extraction_ledger.jsonl`

新增 source snapshot 工具：

- `scripts/engineering/build_p32_learning_source_snapshots.py`
- `tests/test_p32_learning_source_snapshots.py`

作用：从 P32 learning ledgers 读取 source URL / local doc path，记录 source 可访问状态、content type、样本 hash 和标题。这个工具只做 provenance snapshot，不负责自动提权、不写 active registry。

验证结果：

- `python -m pytest tests/test_p32_learning_source_snapshots.py -q`：`5 passed`
- offline snapshot：`data/manifests/p32_learning_source_snapshots_offline_v0_1.jsonl`，`10` rows
- online snapshot：`data/manifests/p32_learning_source_snapshots_v0_1.jsonl`，`10` rows，`9` external fetched samples + `1` local file sample

首批 L2 rows：

- `ai_rate_of_change_exposure_materiality_method_v0_1`
- `workpaper_investment_committee_lifecycle_v0_1`
- `official_product_architecture_to_competitive_position_v0_1`
- `semiconductor_cycle_structural_divergence_method_v0_1`
- `thesis_catalyst_valuation_risk_baseline_structure_v0_1`
- `checkpoint_targeted_repair_pattern_v0_1`
- `tool_resource_prompt_boundary_pattern_v0_1`
- `durable_hitl_workflow_pattern_v0_1`
- `genai_observability_quality_cost_pattern_v0_1`
- `context_engine_lifecycle_pattern_v0_1`

新增 L1 coverage / L3 contract ledgers：

- `docs/project_os/p32_l1_coverage_matrix.jsonl`
- `docs/project_os/p32_l3_contract_translation_ledger.jsonl`

新增 deterministic consistency gate：

- `scripts/engineering/validate_p32_learning_gate.py`
- `tests/test_p32_learning_gate_validation.py`

验证结果：

- P32 tests：`8 passed`
- `data/manifests/p32_learning_gate_validation_v0_1.json`：`status=pass`，`source_count=10`，`extraction_count=10`，`coverage_domain_count=15`，`contract_count=10`，`error_count=0`
- coverage split：`sufficient_for_initial_l3=6`、`partial_needs_more_l1=4`、`gap_needs_l1=5`

Coverage 口径：

- 当前 L1 不算完整，只够推进 AI/Semis 初始 proof 和 agent-runtime 初始 L3。
- capital/market feedback、research-to-quant、enterprise RAG/data pipeline、Workbench product surface、sandbox/resource scheduler 都仍是 L1 source gap，不进入当前 proof。

L3 当前候选合同：

- AI theme exposure thesis path；
- Workpaper lifecycle event；
- Product architecture competitive bridge；
- Semis cycle value-chain playbook；
- Thesis-led memo output；
- Checkpoint targeted repair；
- ToolGateway/MCP boundary；
- Durable HITL task event；
- GenAI trace quality/cost；
- ContextEngine injection。

## 下一步

1. 扩展金融研究方法 source，不局限于 AI/Semis，但先用 AI/Semis 做 proof。
2. 继续扩展 L2 extraction，避免只覆盖 AI/Semis 和少数 agent 框架。
3. 做 AI/Semis no-paid deterministic fixture，证明新方法能改变 thesis path 和 required-item plan。
4. 继续补 L1 coverage matrix 中的 gap domains，尤其 capital/market feedback、research-to-quant、enterprise RAG/data pipeline、Workbench product surface、sandbox/resource scheduler。

## 边界

本轮不跑 full-chain、不调用付费模型、不把外部资料摘要当成项目能力完成。P32 的第一目标是让后续学习和方法吸收可审计、可复用、可淘汰。

## 2026-07-04 L4 No-Paid Fixture Update

新增并通过 P32-L4 AI/Semis no-paid deterministic fixture：

- `scripts/engineering/run_p32_l4_ai_semis_deterministic_fixture.py`
- `tests/test_p32_l4_ai_semis_deterministic_fixture.py`
- `data/manifests/p32_l4_ai_semis_deterministic_fixture_v0_1.json`
- `docs/internal/vnext_20260610/p32_l4_ai_semis_deterministic_fixture_report.zh-CN.md`

验证对象：

1. `p32_l4_ai_infra_nvda_dell_capex`
2. `p32_l4_semicap_asml_lrcx_cycle`

验证结果：

- `python -m pytest tests/test_p32_l4_ai_semis_deterministic_fixture.py -q`：`4 passed`
- `python scripts/engineering/run_p32_l4_ai_semis_deterministic_fixture.py`：`status=pass`，`case_count=2`，`passed_case_count=2`

结论：

- P32 L3 contracts 能把 AI/Semis case 从 baseline 的 evidence list / evidence dump，提升成 thesis path、required-item answer plan、JudgmentCards 和 writer-ready judgment material。
- 产品层不再被 `Product-KPI exact` 单一门槛压制：没有 SKU revenue / shipment / booking exact 时，产品规格、架构、部署、供应链/value-chain 仍可作为 bounded thesis driver。
- Agent 工程吸收不是新造 LangGraph/MCP/HIL/trace/ContextEngine，而是把 PRD/R/S/P 里已规划或部分实现的能力转成 case-level runtime alignment，并用 deterministic gate 检查是否进入 Research Lead 和 writer 输入。

边界：

- 本轮没有调用 paid model；
- 本轮没有跑 full-chain；
- 本轮不证明最终 memo 质量；
- 本轮不关闭 P30 real single-case artifact proof / insight-density blocker。

## 2026-07-04 L1 Gap Domains / Registry Promotion Update

本轮继续 P32，目标是补齐 L1 coverage matrix 里的 gap domains，并决定哪些 L3 contracts 可以进入 active registry。

完成内容：

- 金融研究方法 L1 source 新增：
  - SEC EDGAR / ownership / insider / offering / corporate-action public filings；
  - FINRA short interest / margin / market statistics；
  - OCC options volume / open interest；
  - CFTC COT + CME delayed futures data；
  - Zipline / Alphalens / vectorbt quant research stack。
- Agent 工程模式 L1 source 新增：
  - RAGFlow document intelligence / grounded RAG；
  - Dify workflow / knowledge pipeline；
  - Codex / Claude Code workspace agent / approval / sandbox patterns；
  - OpenAI Agents SDK trace / handoff / guardrail patterns；
  - Kubernetes Kueue / NetworkPolicy resource governance；
  - Ray Serve LLM / vLLM batching and serving scheduler patterns。
- L2 extraction 新增 5 条：
  - `capital_market_positioning_feedback_method_v0_1`
  - `research_to_quant_factor_validation_method_v0_1`
  - `enterprise_rag_ingestion_observability_pattern_v0_1`
  - `workbench_artifact_review_surface_pattern_v0_1`
  - `sandbox_resource_scheduler_pattern_v0_1`
- L3 contract 新增 5 条：
  - `l3_capital_market_feedback_contract_v0_1`
  - `l3_research_to_quant_factor_handoff_contract_v0_1`
  - `l3_enterprise_rag_data_pipeline_contract_v0_1`
  - `l3_workbench_artifact_review_surface_contract_v0_1`
  - `l3_sandbox_resource_scheduler_contract_v0_1`
- 新增 registry promotion ledger 和 validator：
  - `docs/project_os/p32_active_registry_promotion_ledger.jsonl`
  - `scripts/engineering/validate_p32_registry_promotion.py`
  - `tests/test_p32_registry_promotion_validation.py`
- 同步 active registry：
  - `docs/project_os/financial_research_method_registry.jsonl` 追加 5 个 P32-L4 证明过的金融研究方法；
  - `docs/project_os/external_pattern_registry.jsonl` 追加 5 个 P32-L4 证明过的 agent 工程模式。

关键判断：

- 本轮不是照单全收外部资料。SEC/FINRA/OCC/CFTC/CME 只进入 capital feedback / market expectation / positioning proxy，不进入公司 fundamental exact；RAGFlow/Dify 只吸收 pipeline/workflow 设计，不替代 FIN exact-first + SQL-final audit；Codex/Claude Code 只吸收长任务、权限、审查和 artifact drilldown 形态；Kueue/Ray/vLLM 只吸收资源调度思想，不作为当前生产依赖。
- L1 coverage matrix 从 `gap_needs_l1=5` 变为 `gap_needs_l1=0`，但这只代表初始 L3 translation 可推进，不代表 runtime 完成。
- 通过 P32-L4 fixture 的 10 个旧合同进入 `active_registry_ready`，且必须 feature-flagged 或 runtime-alignment-only。
- 新增 5 个 gap-domain 合同全部保持 `deferred_pending_l4_fixture`，不得直接进入 runtime。

验证：

- `python scripts\engineering\validate_p32_learning_gate.py --output data\manifests\p32_learning_gate_validation_v0_1.json`：`status=pass`，`source_count=21`，`extraction_count=15`，`contract_count=15`。
- `python scripts\engineering\validate_p32_registry_promotion.py --output data\manifests\p32_registry_promotion_validation_v0_1.json`：`status=pass`，`active_registry_ready_count=10`，`deferred_count=5`。

边界：

- 没有调用 paid LLM。
- 没有跑 full-chain。
- 新增 5 个合同未通过 L4 fixture 前不能被标记为 active runtime。
