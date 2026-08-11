# R53-R60 P32 Method & Pattern Learning Gate

日期：2026-07-04

## 1. 目标

P32 解决两个问题：

1. 金融业务理解不能靠 Codex 泛化常识，而要沉淀成可执行的 playbook、authority model、thesis path 和 eval rubric。
2. Agent 工程经验不能靠列举框架名，而要把外部成熟模式吸收成 FIN_Insight_Agent 的合同、运行时、上下文、工具、eval 和 Workbench 设计。

P32 不是普通资料搜集，也不是“看几篇网页后总结”。它是一个学习门控：`source discovery -> evidence extraction -> project problem mapping -> contract translation -> deterministic proof -> registry promotion`。

## 2. 当前项目事实

Project OS 当前记录了三个阻止 broad / paid full-chain 的 open blockers：

- `RC-P30-001-real-single-case-artifact-proof-pending`
- `RC-P30-002-memo-quality-insight-density-not-proven`
- `RC-P30-003-paid-full-chain-overuse-risk`

这说明下一步不能直接跑更多 full-chain。必须先证明：

- Research Lead 能把金融问题组织成 thesis path；
- ProductIntelligenceGraph / Fundamental / Capital / CustomerDeployment / Industry evidence 能进入主判断骨架；
- ClaimCard / JudgmentCard / MemoLogicPlan 能成为 writer 主输入；
- Agent 工程上的上下文选择、工具调用、checkpoint、human review、observability 和 eval 能支撑长流程任务。

## 3. P32 学习范围

### 3.1 金融研究方法

吸收对象包括：

- buyside investment memo / workpaper；
- sell-side / broker industry research 的方向、覆盖广度和深度；
- sector / thematic research 的研究地图；
- 行业 playbook；
- 证据权威和可提权边界；
- thesis / counter-thesis / catalyst / valuation / risk / what-would-change-view。

输出不是 sell-side 长报告格式，而是可审计、可复盘、适合 B 端投研/行研团队内部使用的 buyside-style memo / workpaper。

### 3.2 Agent 工程模式

吸收对象包括：

- Codex / Claude Code-style workspace agent；
- LangGraph checkpoint / interrupt / resume / time travel；
- MCP tools / resources / prompts；
- Temporal durable workflow / human signal / replayable history；
- Hermes-style ContextEngine；
- OpenTelemetry / Langfuse / Phoenix-style trace / eval / token / tool observability；
- Dify / RAGFlow / Glean / Hebbia / enterprise workbench-style RAG and workflow UI。

原则：吸收模式，不整体套框架。每个模式必须回答：

- 解决 FIN 项目哪个实际问题；
- 吸收到哪个 runtime contract；
- 不吸收什么；
- 如何验收；
- 如果后续表现不好，如何降级或删除。

## 4. Learning Gate 阶段

| 阶段 | 名称 | 产物 | 通过条件 |
| --- | --- | --- | --- |
| P32-L0 | Project Failure Inventory | 当前失败类型清单 | 覆盖 P30/P31 ledger 中的 owned blockers 和质量问题 |
| P32-L1 | Source Discovery & Qualification | `financial_research_method_learning_ledger.jsonl` / `agent_engineering_pattern_learning_ledger.jsonl` | 每条 source 有 URL、source type、为什么相关、不能吸收什么 |
| P32-L2 | Method / Pattern Extraction | extracted method rows | 不摘抄长文，只抽取方法、结构和机制 |
| P32-L3 | Contract Translation | playbook schema / pattern contract schema | 每条方法映射到 FIN 的 pack、agent、graph、tool、eval 或 Workbench 对象 |
| P32-L4 | AI/Semis No-Paid Deterministic Proof | Research Lead / specialist / MemoLogicPlan fixture | 不调用 LLM，证明 playbook 能改变 thesis path 和 required items |
| P32-L5 | Registry Promotion | `FinancialResearchMethodRegistry v0.2` / `ExternalPatternRegistry v0.2` | 只有通过 L4 proof 的方法进入 active registry |
| P32-L6 | Closeout Review | worklog + Project OS ledger update | 明确哪些未覆盖、哪些需要继续学、哪些可进入下一轮实现 |

## 5. FinancialResearchMethodRegistry v0.2 schema 草案

```json
{
  "method_id": "ai_semis_product_financial_bridge_v0_1",
  "research_domain": "ai_semis",
  "source_basis": ["source ids"],
  "core_question_set": [],
  "required_packs": [],
  "evidence_authority_rules": [],
  "promotable_claim_scopes": [],
  "forbidden_claim_scopes": [],
  "thesis_path_template": {},
  "specialist_task_rubric": {},
  "writer_output_requirements": {},
  "eval_gate_requirements": {},
  "status": "candidate | active | rejected | superseded"
}
```

必须区分：

- `exact_financial_fact`
- `operating_kpi_exact`
- `technical_fact`
- `deployment_signal`
- `supply_chain_signal`
- `market_expectation_signal`
- `capital_feedback_signal`
- `scope_hypothesis`
- `commercial_tracker_gap`

## 6. AgentEngineeringPatternLedger schema 草案

```json
{
  "pattern_id": "langgraph_checkpoint_targeted_repair_v0_1",
  "source_basis": ["source ids"],
  "project_problem": [],
  "absorbed_design": [],
  "rejected_design": [],
  "target_contracts": [],
  "runtime_implication": [],
  "eval_gate": [],
  "status": "candidate | active | rejected | superseded"
}
```

## 7. 首轮外部资料边界

本轮只登记首批强相关资料，不宣称 source discovery 完成。后续必须继续扩展：

- 更多公开 sell-side / thematic / sector report；
- 更多 buyside memo / investment committee / portfolio review workflow；
- 更多 agent engineering reference implementation；
- 具体 AI/Semis 行业 playbook 资料，例如 GPU、HBM、CoWoS、WFE、EUV/DUV、cloud capex、server OEM 和 export-control。

## 8. 下一步

1. 继续扩 `financial_research_method_learning_ledger` 和 `agent_engineering_pattern_learning_ledger`。
2. 对首批 source 做 L2 extraction，不直接改 agent。
3. 先做 AI/Semis playbook candidate。
4. 写 no-paid deterministic fixture，验证 Research Lead 是否能输出更好的 thesis path。

## 9. L2 Extraction 已启动

首批 L2 extraction rows 已落入：

- `docs/project_os/financial_research_method_extraction_ledger.jsonl`
- `docs/project_os/agent_engineering_pattern_extraction_ledger.jsonl`

当前抽出的金融研究方法包括：

- AI exposure / materiality / rate-of-change map；
- investment memo / workpaper review lifecycle；
- official product architecture -> competitive-position bridge；
- semiconductor cycle / structural divergence frame；
- thesis / catalyst / valuation / risk baseline structure。

当前抽出的 agent 工程模式包括：

- checkpointed targeted repair；
- typed tools/resources/prompts boundary；
- durable human-in-the-loop workflow history；
- GenAI observability tied to quality and cost；
- ContextEngine resolve/select/compress/inject/write/invalidate lifecycle。

这些 rows 仍是 `candidate_l2_extracted`，不能直接当作 active playbook 或 runtime 改造完成。下一步必须进入 L3 contract translation：把它们转成具体 schema、agent contract、tool policy、Trace/Eval rows 和 deterministic proof。

## 10. Source Snapshot Tool

新增：

- `scripts/engineering/build_p32_learning_source_snapshots.py`
- `tests/test_p32_learning_source_snapshots.py`

用途：

- 读取 P32 learning ledgers；
- 对本地文档记录存在性、样本 hash；
- 对外部 URL 可选抓取小样本，记录 HTTP 状态、content type、样本 hash 和标题；
- 输出 `data/manifests/p32_learning_source_snapshots_v0_1.jsonl`。

边界：

- snapshot 只证明 source addressable / sampled，不证明 source 方法正确；
- snapshot 不进入 active registry；
- 失败状态必须保留为 source/provenance 问题，不能静默兜底成“已学习”。

本轮验证：

- `python -m pytest tests/test_p32_learning_source_snapshots.py -q`：`5 passed`
- `python scripts/engineering/build_p32_learning_source_snapshots.py --offline --output data/manifests/p32_learning_source_snapshots_offline_v0_1.jsonl`：`10` rows
- `python scripts/engineering/build_p32_learning_source_snapshots.py --output data/manifests/p32_learning_source_snapshots_v0_1.jsonl --timeout 20 --max-bytes 65536`：`10` rows，其中 `9` 条外部 URL 为 `fetched_sample`，`1` 条本地 R57 参考为 `local_file_sampled`

## 11. L1 Coverage Matrix

新增 `docs/project_os/p32_l1_coverage_matrix.jsonl`。

用途：

- 不把“已有 10 条 source”误判成 L1 完成；
- 按能力域记录当前 source 是否足够支撑初始 L3；
- 把缺口写成可继续补 source 的明确任务；
- 决定哪些域能进入 AI/Semis proof，哪些域必须继续停留在 L1。

当前判断：

- 可支撑初始 L3：`buyside_workpaper_memo_lifecycle`、`product_architecture_competitive_position`、`graph_orchestration_checkpoint_repair`、`tool_protocol_gateway_permission`、`durable_runtime_hil_workflow`、`observability_eval_cost_quality`。
- 可支撑 AI/Semis 初始 proof 但仍需扩源：`sell_side_sector_thematic_research_method`、`ai_semis_industry_playbook`、`thesis_catalyst_valuation_risk_structure`、`context_memory_lifecycle`。
- 暂不进入当前 proof：`capital_market_funding_ownership_flow`、`research_to_quant_handoff`、`enterprise_rag_data_pipeline`、`workbench_ui_task_product_surface`、`sandbox_security_resource_scheduler`。

## 12. L3 Contract Translation

新增 `docs/project_os/p32_l3_contract_translation_ledger.jsonl`。

用途：

- 把 L2 extraction rows 翻译成 FIN 的具体 runtime / agent / data / eval 合同；
- 明确每个合同的输入、输出、非 LLM 验收 gate；
- 防止“学习资料”停留在散文总结。

当前 L3 合同覆盖：

- AI theme exposure / materiality -> `ThemeExposureMap` / `ThesisPathTemplate`；
- Workpaper lifecycle -> `WorkpaperPack` / `WorkpaperEvent` / `ReviewActionLedger`；
- Product architecture -> `ProductIntelligenceGraph` / `ProductSpec` / `JudgmentCard`；
- Semiconductor cycle -> `AI_Semis_IndustryPlaybook`；
- Thesis-led writer -> `MemoLogicPlan` / `WriterOutputRubric`；
- Checkpointed repair -> `LeadReviewCheckpoint` / `ProjectOSPreflight`；
- Tool boundary -> `ToolGateway` / `ToolInvocationLedger` / `SandboxPolicy`；
- Durable HITL -> `TaskRun` / `HumanApprovalEvent`；
- GenAI observability -> `TraceSpan` / `AIE` / `EvalRun`；
- ContextEngine -> role-scoped context selection / compression / injection。

边界：这些都是 `candidate_l3_translated`，仍未通过 L4 no-paid deterministic proof，不能直接进入 active registry。

## 13. Deterministic Consistency Gate

新增：

- `scripts/engineering/validate_p32_learning_gate.py`
- `tests/test_p32_learning_gate_validation.py`

检查内容：

- L2 extraction rows 引用的 `source_ids` 必须存在于 L1 learning ledger；
- coverage matrix 的 `current_source_ids` 必须存在；
- `gap_needs_l1` 不能声明支持下一轮 proof；
- L3 contract rows 引用的 `source_extraction_ids` 必须存在；
- L3 contract rows 必须有 target runtime object、target agent node、input/output required fields 和 non-LLM acceptance gate。

这个 gate 只检查学习门的引用闭环和合同完整性，不证明方法质量或 memo 输出质量。

验证结果：

- `python -m pytest tests/test_p32_learning_source_snapshots.py tests/test_p32_learning_gate_validation.py -q`：`8 passed`
- `python scripts/engineering/validate_p32_learning_gate.py --output data/manifests/p32_learning_gate_validation_v0_1.json`：`status=pass`
- validation summary：`source_count=10`、`extraction_count=10`、`coverage_domain_count=15`、`contract_count=10`、`error_count=0`

Coverage summary：

- `sufficient_for_initial_l3=6`
- `partial_needs_more_l1=4`
- `gap_needs_l1=5`

## 14. L4 AI/Semis No-Paid Deterministic Fixture

新增：

- `scripts/engineering/run_p32_l4_ai_semis_deterministic_fixture.py`
- `tests/test_p32_l4_ai_semis_deterministic_fixture.py`
- `data/manifests/p32_l4_ai_semis_deterministic_fixture_v0_1.json`
- `docs/internal/vnext_20260610/p32_l4_ai_semis_deterministic_fixture_report.zh-CN.md`

目的：

- 不调用 LLM；
- 不跑 full-chain；
- 不重新检索；
- 用固定 AI/Semis case 验证 L3 contracts 是否能改变链路形状。

本轮验证的两个 case：

1. `p32_l4_ai_infra_nvda_dell_capex`：NVDA / DELL / hyperscaler capex read-through。
2. `p32_l4_semicap_asml_lrcx_cycle`：ASML / AMAT / LRCX / KLAC semicap cycle / value-chain / order-risk 逻辑。

Fixture 对照：

- baseline：只给 evidence list，writer material 仍是 `evidence_dump`，peer group 容易成为主证据。
- contract-aligned plan：输出 `ThemeExposureMap`、required-item answer plan、JudgmentCards、thesis path、writer-ready judgment material 和 runtime alignment。

当前结果：

- `python -m pytest tests/test_p32_l4_ai_semis_deterministic_fixture.py -q`：`4 passed`
- `python scripts/engineering/run_p32_l4_ai_semis_deterministic_fixture.py`：`status=pass`，`case_count=2`，`passed_case_count=2`
- 两个 case 均满足：
  - required item 有 answer 或 typed gap；
  - product architecture 进入 thesis path；
  - 没有 SKU revenue / product KPI exact 时不会把产品层判为失败；
  - deployment / adoption、supply-chain / value-chain、financial bridge、counter-thesis 都进入判断路径；
  - writer material 是 `writer_ready_judgment_material`，不是 raw evidence dump；
  - checkpoint repair、ToolGateway/MCP boundary、ContextEngine、trace/AIE、durable HIL 以合同形式进入 runtime alignment。

关键结论：

P32-L4 证明的是“方法和工程模式在合同层能改善 AI/Semis 链路形状”：Research Lead 不再只列证据，而是能形成 thesis path、required-item plan 和 writer-ready judgment material；产品规格/架构、客户部署、供应链/value-chain、财务桥和反证能被组织到同一判断路径里。

边界：

- 这不是 paid-model memo 质量证明；
- 这不是 real retrieval / live crawler / full-chain production proof；
- 这不是全域 L1 source 完成；
- 不能据此扩大 20-50 case full-chain。P30 真实单 case artifact proof 和 memo insight-density root cause 仍按 Project OS blocker 管理。

澄清：

LangGraph checkpoint、MCP/tool boundary、durable HIL、OpenTelemetry/trace、ContextEngine 等内容并非本轮从零新引入。它们已在 PRD / R56 / R57 / R58 / R59 / R60 / S-series / P-series 文档和部分 runtime 中出现。本轮 P32-L4 的价值是把这些已规划或已部分实现的能力重新翻译成 AI/Semis case 下可验证的合同，确认它们是否真的改善 Research Lead planning、required-item coverage 和 writer 输入，而不是停留在框架名词。

## 15. L1 Gap Domains 补源和本土化吸收

本轮把原先 5 个 `gap_needs_l1` domain 补成可推进初始 L3 的 qualified source coverage，但不照单全收外部方案：

- `capital_market_funding_ownership_flow`：新增 SEC、FINRA、OCC、CFTC/CME source rows。吸收 ownership/insider/offering/corporate action、short interest/liquidity、options OI/volume、futures/COT/cross-asset proxy。边界是：这些只能进入 capital feedback / market expectation / positioning proxy，不能冒充公司 operating/fundamental fact，也不能替代实时 OPRA、CDS、borrow cost、dealer gamma 或商业资金流。
- `research_to_quant_handoff`：新增 Zipline / Alphalens / vectorbt reference row。吸收 factor hypothesis、event-driven backtest、factor tearsheet、PIT/leakage guard 和 human approval 边界。边界是：不做 library lock-in，不自动交易，不把 backtest 当对外投资建议。
- `enterprise_rag_data_pipeline`：新增 RAGFlow / Dify references。吸收 document pipeline、knowledge pipeline、chunk/index/retrieval lineage、pipeline observability。边界是：FIN 继续保留 exact-first、source authority、WorkpaperEvent 和 SQL-final audit，不让 generic vector search 压过结构化事实。
- `workbench_ui_task_product_surface`：新增 Dify、Codex/Claude Code、OpenAI Agents SDK references。吸收长任务、workflow step、artifact drilldown、review/action、tool/handoff trace。边界是：不复制 code-agent UI，不把 chat transcript 当金融 workbench，不允许 frontend-local state 成为审计源。
- `sandbox_security_resource_scheduler`：新增 Codex/Claude Code、Kubernetes Kueue / NetworkPolicy、Ray/vLLM serving scheduler references。吸收 approval、network allowlist、queue/admission control、GPU/CPU spillover、batching/concurrency concepts。边界是：本地先轻量 fail-closed，不强行引入 Kubernetes/Ray/vLLM 生产依赖。

本轮更新后的 `p32_l1_coverage_matrix.jsonl` 结果：

- `sufficient_for_initial_l3=11`
- `partial_needs_more_l1=4`
- `gap_needs_l1=0`

这只代表 P32 L1 source gap domains 已足够做初始 L3 translation，不代表这些 domain 已经进 runtime 或 paid full-chain。

## 16. 新增 L2 / L3 合同

新增 L2 extraction：

- `capital_market_positioning_feedback_method_v0_1`
- `research_to_quant_factor_validation_method_v0_1`
- `enterprise_rag_ingestion_observability_pattern_v0_1`
- `workbench_artifact_review_surface_pattern_v0_1`
- `sandbox_resource_scheduler_pattern_v0_1`

新增 L3 contract：

- `l3_capital_market_feedback_contract_v0_1`
- `l3_research_to_quant_factor_handoff_contract_v0_1`
- `l3_enterprise_rag_data_pipeline_contract_v0_1`
- `l3_workbench_artifact_review_surface_contract_v0_1`
- `l3_sandbox_resource_scheduler_contract_v0_1`

这些合同全部是 `candidate_l3_translated`，只说明源材料已经被翻译成 FIN 的 pack / agent / data / eval / Workbench 合同。初始状态下它们没有经过对应 L4 fixture，不允许直接进入 active runtime。P33 后续会逐个补 no-paid deterministic fixture，fixture 通过的合同才能晋升为 feature-flagged 或 runtime-alignment-only。

## 17. Registry Promotion Decision

新增：

- `docs/project_os/p32_active_registry_promotion_ledger.jsonl`
- `docs/project_os/financial_research_method_registry.jsonl`：追加 P32-L4 证明过的 5 个金融研究方法，状态为 feature-flagged 或 runtime-alignment-only。
- `docs/project_os/external_pattern_registry.jsonl`：追加 P32-L4 证明过的 5 个 agent 工程模式，状态为 runtime-alignment-only。
- `scripts/engineering/validate_p32_registry_promotion.py`
- `tests/test_p32_registry_promotion_validation.py`
- `data/manifests/p32_registry_promotion_validation_v0_1.json`

Promotion 口径：

- 初始进入 `active_registry_ready` 的只有已经被 `p32_l4_ai_semis_deterministic_fixture_v0_1.json` 覆盖的 10 个旧合同。
- 其中 AI/Semis 业务合同只允许 feature-flagged 使用；runtime governance 合同只允许 runtime-alignment-only 使用。
- 新增 5 个 gap-domain 合同必须分别经过 P33 no-paid deterministic fixture 后才能晋升；未证明前保持 `deferred_pending_l4_fixture`，不能直接进入 runtime。
- 2026-07-05 P33 更新：`l3_enterprise_rag_data_pipeline_contract_v0_1`、`l3_sandbox_resource_scheduler_contract_v0_1`、`l3_capital_market_feedback_contract_v0_1`、`l3_workbench_artifact_review_surface_contract_v0_1` 和 `l3_research_to_quant_factor_handoff_contract_v0_1` 已分别通过 P33-1.1 / P33-1.2 / P33-1.3 / P33-1.4 / P33-1.5 fixture，晋升为 `active_registry_ready_runtime_alignment_only`。当前 `active_registry_ready_count=15`、`deferred_count=0`。

当前 validation：

- `python scripts/engineering/validate_p32_learning_gate.py --output data/manifests/p32_learning_gate_validation_v0_1.json`：`status=pass`，`source_count=21`，`extraction_count=15`，`contract_count=15`。
- `python scripts/engineering/validate_p32_registry_promotion.py --output data/manifests/p32_registry_promotion_validation_v0_1.json`：初始 `status=pass`，`active_registry_ready_count=10`，`deferred_count=5`；P33-1.1 至 P33-1.5 后最新为 `active_registry_ready_count=15`，`deferred_count=0`。

下一步不应直接跑 paid full-chain。P33-1 已关闭，下一步是把 15 个 active registry contracts 接进 runtime assimilation，证明 Research Lead / ContextEngine / JudgmentCard / MemoLogicPlan / Workbench 真正按合同工作。
