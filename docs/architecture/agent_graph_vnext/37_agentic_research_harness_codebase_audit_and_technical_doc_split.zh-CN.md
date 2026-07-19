# P37：Agentic Research Harness 代码库审计与技术文档拆分建议

日期：2026-07-09

状态：代码库静态审计 + PRD 对齐建议。本文不表示 runtime 修复完成，不表示 P36 blocker 关闭，不表示已运行 paid LLM、true full-chain、MCP server、source ingestion 或新 eval harness。

关联 PRD：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`

关联 P36 记录：

- `docs/worklog/product_strategy/117_p36_codex_as_paid_model_manual_full_chain_dogfood.md`
- `docs/project_os/p36_manual_full_chain_node_ledger_v0_1.json`
- `docs/project_os/p36_verifier_workbench_review_v0_1.json`

## 1. 审计结论

FIN_Insight_Agent 现在不是空壳。代码库已经有大量真实能力：

- Workbench backend / frontend；
- multi-agent orchestration；
- Research Lead / specialist / writer / verifier；
- tool controller / MCP contracts / tool registry；
- run audit store / WorkpaperEvent / Workbench store；
- source route / parser / exact-value / public-web context parser；
- ProductIntelligenceGraph / relationship graph / capital feedback；
- Project OS ledgers / preflight；
- P32-P36 deterministic fixtures、audit runners 和 tests。

但这些能力目前仍以 P33 / P34 / R53-R60 / P36 的局部 contract、fixture、gate、manual dogfood 形态分布。它们还没有被统一编译成新 PRD 需要的 `DecisionSurfaceContract -> Agentic Search -> Evidence Gate -> DecisionSurfacePack -> Writer no-source -> Workbench cell review -> Harness eval` 主链路。

所以当前工程任务不是“从零做 agentic research”，而是把已有资产重组为：

```text
Decision-surface-first runtime
+ shared Evidence Layer
+ Agentic Research Harness
+ cell-level Workbench review
```

## 2. Git / 仓库状态审计

当前分支：

```text
codex/layered-data-source-expansion
```

当前状态特征：

- 已有大量 tracked modified 文件，覆盖 `src/`、`tests/`、`scripts/`、`configs/`、`data/manifests/`、`docs/`、`apps/workbench/`；
- `docs/project_os/` 当前为 untracked，但属于项目运行 OS 的 durable source-of-truth，应纳入 Git；
- `docs/worklog/product_strategy/053-117` 当前为 untracked，但多数是 P26-P36 的 durable worklog，应纳入 Git；
- `reports/r53_r60_*` 是运行输出，不应纳入 Git，本轮已补 `.gitignore`；
- `.tmp_*`、`eval/`、大多数 `reports/*`、`data/manifests/*.jsonl`、private data、indexes、venv、cache 已有 ignore 规则。

本轮清理判断：

| 类型 | 判断 | 处理 |
| --- | --- | --- |
| 源码 / tests / scripts / configs | 当前实现资产 | 应 stage |
| `docs/product` / `docs/architecture` / `docs/internal` / `docs/worklog` | durable docs | 应 stage |
| `docs/project_os` | 项目 OS、ledger、policy、root cause、capability source-of-truth | 应 stage |
| 小型 `data/manifests/*.json` summary / fixture / report | deterministic fixture / contract / gate summary | 应 stage |
| `data/manifests/*.jsonl` 大行集 | 一般不应新增 stage；若已 tracked 修改，按历史 gate row 处理 | 谨慎 stage |
| `reports/r53_r60_*` | 运行输出 | ignore |
| `.tmp_*`、`.ruff_cache`、`.pytest_cache` | 本地临时产物 | ignore |

本轮实际执行结果：

- 已补 `.gitignore`：`/reports/r53_r60_*/`、`.ruff_cache/`；
- 已确认 `reports/r53_r60_p20_deepseek_smoke/`、`reports/r53_r60_p24_b04_product_acceptance_browser_e2e/`、`reports/r53_r60_p30_full_chain_ai_semis/` 和 `.ruff_cache/` 被 ignore；
- 已按路径 stage：`.gitignore`、`apps/`、`configs/`、`data/manifests/`、`docs/`、`scripts/`、`src/`、`tests/`；
- staged 文件数：420；
- `git diff --cached --check` 通过；
- `python -m compileall -q src scripts` 通过；
- 未 commit / push，未删除文件，未运行 `git clean` 或 revert。

## 3. 已实现功能审计

### 3.1 Workbench / 产品界面

主要代码：

- `apps/workbench/backend/app.py`
- `apps/workbench/frontend/vite/src/main.tsx`
- `apps/workbench/frontend/vite/src/workbench.css`
- `src/sec_agent/workbench/*.py`

已实现能力：

- FastAPI backend；
- health / system status；
- profile / source bundle 管理；
- data build preview / run；
- run list / run status / run cancel / run events / SSE event stream；
- session turn / agent ask / smoke run / eval run；
- R53-R60 task center、task detail、events、artifacts、drilldown；
- review queue、append-only review action；
- resume / cancel；
- ops projection、deliverables、dashboard projection；
- pilot dashboard、pilot cases、reviewer action ledger；
- product acceptance evidence / reviewer package。

与 PRD 对齐：

- 对齐第 6 章 Dashboard、Research Task Center、Evidence Workbench、Deliverable Studio、Human Review / Approval、Admin / Governance；
- 部分对齐第 7.8 Harness 的 run events / checkpoint / review action。

主要差距：

- 还没有 `decision_surface_cell` 作为 Workbench 一等 review target；
- 还没有 `DecisionSurfacePack` / `ArtifactConsistencyGraph` 原生 projection；
- 现有 review surface 偏 claim / gap / artifact / task，而不是 chain segment x decision cell；
- 没有把 claim provenance graph 可视化成 reviewer 可点的链路。

### 3.2 Runtime / durable state / audit

主要代码：

- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/run_audit_store.py`
- `src/sec_agent/r53_r60_runtime_task_spine.py`
- `src/sec_agent/r53_r60_durable_runtime_hil_resource_router.py`
- `src/sec_agent/tool_call_ledger.py`
- `src/sec_agent/ledger_store.py`
- `src/sec_agent/workbench/store.py`
- `src/sec_agent/workbench/job_runner.py`

已实现能力：

- LangGraph-style orchestration；
- run audit SQLite materialization；
- run / node / artifact / evidence / retrieval task / tool call / claim / gap / gate / repair / model call / resource usage / context event rows；
- Workbench job runner、job status、event log；
- R53-R60 durable runtime / HIL / resource router gate；
- append-only review and audit patterns。

与 PRD 对齐：

- 强对齐第 7.8 `Durable Run State` 的方向；
- 已经有 `run_audit_store`，可以作为 `TaskRun / NodeAttempt / ToolInvocation / Observation / EvidenceCandidate / PromotionDecision / Artifact / ReviewAction` 的技术基座。

主要差距：

- 状态对象尚未统一命名为新 PRD 的 Harness schema；
- checkpoint / replay 存在，但没有围绕 `DecisionSurfaceContract` 和 cell-level repair 定义；
- durable state 与 Workbench cell review、Evidence Gate、Provenance Graph 的 schema 尚未统一；
- LangGraph checkpoint / SQL audit / WorkpaperEvent 边界需要正式 TECH 文档裁定。

### 3.3 Tool / MCP / sandbox / permission

主要代码：

- `src/sec_agent/mcp_contracts.py`
- `src/sec_agent/mcp_tool_registry.py`
- `src/sec_agent/mcp_runtime.py`
- `src/sec_agent/mcp_server.py`
- `src/sec_agent/tool_capability_registry.py`
- `src/sec_agent/tool_controller.py`
- `src/sec_agent/tool_harness.py`
- `src/sec_agent/r53_r60_tool_sandbox_spine.py`
- `configs/mcp/sec_agent_mcp_tool_contracts_v0_1.json`

已实现能力：

- MCP tool contract listing / validation / export；
- MCP runtime/server skeleton；
- tool registry / capability registry；
- tool controller with guarded tool name, argument canonicalization, heuristic fallback, runtime-context compaction；
- tool sandbox trace gate；
- tests for MCP contracts and runtime tools。

与 PRD 对齐：

- 部分对齐第 7.6 `Tool Registry / Evidence Tool Planner / Evidence Gate`；
- 部分对齐第 7.8 `MCP / ToolGateway` 和 `Guardrails / Capability Security`。

主要差距：

- ToolGateway 还没有成为所有 DB / RAG / graph / parser / crawler / market connector 的唯一入口；
- permission gate、sandbox、approval、source role、authority、forbidden claims 分散在多个模块；
- `Evidence Tool Planner` 还不是明确对象；
- tool observation 不能稳定追到 claim-level provenance；
- Writer no-source 有 prompt / gate 边界，但还没有统一 capability security schema。

### 3.4 Context / memory / method runtime

主要代码：

- `src/sec_agent/context_engine.py`
- `src/sec_agent/context_manager.py`
- `src/sec_agent/context_store.py`
- `src/sec_agent/context_api.py`
- `src/sec_agent/method_runtime.py`
- `src/sec_agent/research_skills.py`
- `src/sec_agent/r53_r60_context_graph_skill_registry.py`
- `src/sec_agent/r53_r60_graph_skill_memory_lifecycle.py`

已实现能力：

- ContextEngine select / compress / inject / write_memory；
- role-scoped context injection；
- context snapshot rows in run audit store；
- method runtime pack；
- specialist runtime rubric；
- skill / graph lifecycle gates；
- Project OS method-to-runtime ledgers。

与 PRD 对齐：

- 部分对齐第 7.8 `ContextEngine / self-compaction`；
- 部分对齐第 7.8 `Skills / Progressive Disclosure`。

主要差距：

- 还没有 `Pinned Governance Context` 一等对象；
- compaction 没有 `CompactionEvent`、dropped refs、preserved constraints、governance decay 检查；
- writer no-source、source authority、permission policy、supervisor supplement boundary 尚未作为不可丢失 pinned constraints 统一注入；
- skills 仍主要是 prompt / method material，未完全进入 runtime registry / schema / gate。

### 3.5 Data / source / retrieval / parser / evidence

主要代码：

- `src/sec_agent/retrieval_plan.py`
- `src/sec_agent/retrieval_index_registry.py`
- `src/sec_agent/source_route_registry_v2.py`
- `src/sec_agent/source_capability_router.py`
- `src/sec_agent/source_authority_coverage.py`
- `src/sec_agent/source_coverage_gate.py`
- `src/sec_agent/runtime_source_context_store.py`
- `src/sec_agent/public_web_context_parser.py`
- `src/sec_agent/parser_quality_ledger.py`
- `src/sec_agent/exact_slot_contracts.py`
- `src/sec_agent/d_series_database_store.py`
- `src/sec_agent/d_series_fact_selection.py`
- `src/sec_agent/official_issuer_repair.py`
- `src/sec_agent/p34_lane_quality_runtime.py`

已实现能力：

- source route registry；
- public source authority / coverage gate；
- public web context parser；
- exact slot contracts；
- D-series database store and fact selection；
- parser quality ledger；
- P34 AI/Semis source route plan、adapter fixtures、live route attempts、no-paid quality audit、scoped writer payload；
- official issuer repair utilities。

与 PRD 对齐：

- 部分对齐第 7.3-7.6 Evidence Layer、SourceHunter、工具栈和 Evidence Gate；
- 支撑第 7.7 RAG / KB 作为 candidate generator / source index / metadata filter；
- 支撑 P36 发现中的 source supplement ingestion / parser promotion repair。

主要差距：

- `SourceHunterLoop` 还不是统一 runtime loop；
- P36 supervisor supplement ledger 尚未转成 official-first route attempt、parser lineage、accepted runtime rows；
- `DocumentMetadataIndex` 还不是一等 retrieval filter contract；
- RAG / ObjectBM25 / DB rows 到 `DecisionSurfaceCell` 的 accepted evidence conversion 不稳定；
- parser promotion 仍偏基础财务，业务线经济性、AI server margin、HBM-only economics、CoWoS、semicap backlog/bookings 仍弱。

### 3.6 Graph / product / relationship / capital market

主要代码：

- `src/sec_agent/relationship_graph.py`
- `src/sec_agent/product_intelligence_graph.py`
- `src/sec_agent/product_intelligence_runtime.py`
- `src/sec_agent/product_spec_pack.py`
- `src/sec_agent/product_family_source_routes.py`
- `src/sec_agent/product_intelligence_depth.py`
- `src/sec_agent/research_graph_store.py`
- `src/sec_agent/capital_macro_pack.py`
- `src/sec_agent/capital_macro_source_adapters.py`
- `src/sec_agent/market_snapshot.py`
- `src/sec_agent/r53_r60_secondary_market_capital_feedback.py`

已实现能力：

- relationship graph lookup；
- ProductIntelligenceGraph company packs and context rows；
- product spec pack；
- product family source routes；
- research graph store；
- capital macro pack；
- market snapshot；
- secondary market / capital feedback fixture and graph edges。

与 PRD 对齐：

- 对齐第 5.2、5.4、6.6、7.3、7.7；
- 是 FIN 相比普通 report generator 的重要差异化资产。

主要差距：

- 缺 `GraphToDecisionCellProjection`；
- ProductIntelligenceGraph 没有稳定投射成 HBM、CoWoS、AI server margin、semicap、deployment、risk、price-in decision cells；
- market snapshot、ownership、CapitalMacroPack、P33 capital feedback 没有统一进入 price-in / crowding / valuation risk surface；
- relationship graph 多用于 scope / hypothesis，不是 writer-ready value-capture conclusion。

### 3.7 Multi-agent / Lead / specialist / writer / verifier

主要代码：

- `src/sec_agent/research_lead_llm.py`
- `src/sec_agent/specialist_llm.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/multi_agent_contracts.py`
- `src/sec_agent/multi_agent_router.py`
- `src/sec_agent/agent_registry.py`
- `src/sec_agent/agent_contracts.py`
- `src/sec_agent/memo_logic_plan.py`
- `src/sec_agent/memo_llm.py`
- `src/sec_agent/claim_evidence_ledger.py`
- `src/sec_agent/claim_verifier.py`
- `src/sec_agent/prompts/skills/*.md`

已实现能力：

- Research Lead activation and planning；
- specialist routing and fanout；
- role-specific prompt rows；
- ProductSpecPack / CapitalMacroPack / FundamentalStatementPack compaction；
- specialist memolet output contracts；
- aggregate judgment plan；
- JudgmentState、JudgmentCards、thesis path、MemoLogicPlan；
- Memo Writer with repair / verifier / salvage constraints；
- claim evidence ledger and typed gap ledger；
- writer forbidden tool boundary exists in aggregate/writer layer。

与 PRD 对齐：

- 对齐第 4.1、7.1、7.2、7.3、7.8；
- 是现有 agentic research 的核心 runtime。

主要差距：

- Research Lead 尚未原生输出 `DecisionSurfaceContract`；
- specialist 仍主要按 role / source family / memo slot 工作，不是按 `decision_surface_cell_id` 工作；
- `RepairTicket` 不是一等跨节点对象；
- subagents 不是独立上下文 `agents-as-tools`，更像 LangGraph node / prompt role；
- `DecisionSurfaceAdjudicator` / `DecisionSurfacePack` 缺失；
- MemoLogicPlan 可保留 thesis path，但会把 forced chain dimensions 折回 generic dimensions；
- writer 仍无法从 runtime-only material 生成完整 P36 五链条报告。

### 3.8 Eval / Project OS / self-hardening

主要代码和文档：

- `src/sec_agent/project_os_preflight.py`
- `docs/project_os/*.json`
- `docs/project_os/*.jsonl`
- `scripts/eval_multi_agent/*.py`
- `scripts/engineering/run_p32_*.py`
- `scripts/engineering/run_p33_*.py`
- `tests/test_project_os_preflight.py`
- `tests/test_p32_*.py`
- `tests/test_p33_*.py`
- `tests/test_p34_*.py`
- `tests/test_p35_*.py`

已实现能力：

- capability ledger；
- root-cause issue ledger；
- external pattern registry；
- financial research method registry；
- full-chain preflight；
- P32 method / pattern learning gate；
- P33 runtime assimilation fixtures；
- P34 source route / adapter / live route / quality audit；
- P35 supervisor dogfood；
- P36 manual dogfood ledgers；
- many deterministic tests。

与 PRD 对齐：

- 强对齐第 7.8 `Harness Self-Improvement` 的基础；
- 强对齐第 9.7 验收中的 no-paid deterministic proof 和 preflight。

主要差距：

- trace-driven recurring issue clustering 还不是自动化 harness；
- root-cause ledgers 是 durable，但未与 trace corpus 自动联动；
- trajectory eval 没有统一 schema；
- self-improvement 可以建议 patch，但目前仍靠人工 / Codex 手工组织。

## 4. 新 PRD 对齐总表

| PRD 模块 | 当前实现状态 | 主要代码资产 | 缺口 |
| --- | --- | --- | --- |
| DecisionSurfaceContract | documented / partial fixture | P35 framework, P36 ledgers | Research Lead runtime 原生 contract 缺失 |
| Evidence Layer | partial runtime | source route, parser, exact slots, P34 runtime | EvidenceRequest / EvidenceResponse / Evidence Gate 未统一 |
| SourceHunterLoop | partial / manual supplement | P34 live attempts, official_issuer_repair, P36 supplement ledger | P36 supplement -> runtime rows 未实现 |
| Tool Registry / MCP | partial runtime | mcp_contracts, mcp_tool_registry, tool_controller | 所有工具未统一经过 ToolGateway |
| ContextEngine | partial runtime | context_engine, context_manager, method_runtime | pinned governance / compaction event / governance decay 缺失 |
| Durable state | partial runtime | run_audit_store, Workbench store, job_runner | 新 Harness schema 与 DecisionSurface 未统一 |
| Subagents-as-tools | partial | LangGraph nodes, specialist_llm | 独立上下文 agent-as-tool/handoff schema 缺失 |
| Product/Graph projection | partial | product_intelligence_runtime, relationship_graph | GraphToDecisionCellProjection 缺失 |
| Market/Capital projection | partial | market_snapshot, capital_macro_pack, S8 capital feedback | price-in/crowding/valuation risk cell pack 缺失 |
| Risk Matrix | partial | risk skill, specialist selection, CapitalMacroPack | RiskMatrixPack / risk-specific projection 缺失 |
| DecisionSurfacePack | missing | aggregate judgment plan, MemoLogicPlan | DecisionSurfaceAdjudicator 缺失 |
| Writer no-source | partial runtime | memo_llm, memo_logic_plan, multi_agent_contracts | writer package 还不是 DecisionSurfacePack-first |
| Workbench cell review | missing / partial | Workbench review queue, artifact review | decision_surface_cell target 缺失 |
| Provenance Graph | partial | claim_evidence_ledger, run_audit_store | claim->tool observation->parser/numeric lineage 链路未统一 |
| Trajectory eval | partial | P33/P34 runners, eval scripts | unified trajectory/eval schema 缺失 |
| Harness self-improvement | documented / partial process | Project OS ledgers | trace clustering / patch proposal loop 缺失 |

## 5. 技术文档拆分建议

不要把后续技术方案写成一个巨型 TECH。建议拆成 10 个文档，每个文档都能对应一组可实现 demand tickets 和 deterministic tests。

2026-07-09 追加修订：PRD 已显式要求 `Agentic Search / Agentic Research / bounded ReAct`，所以 `TECH-01` 不能只是 DecisionSurface schema 文档，而必须作为从 one-shot node graph 转向 agentic research loop 的总控合同。修订后的 canonical index 已落到：

- `docs/architecture/agent_graph_vnext/TECH_00_agentic_research_technical_index.zh-CN.md`

修订后的 TECH 划分如下：

1. `TECH_01_agentic_research_loop_decision_surface_contract.zh-CN.md`
2. `TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md`
3. `TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`
4. `TECH_04_numeric_program_trace_parser_promotion.zh-CN.md`
5. `TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`
6. `TECH_06_durable_harness_runtime_permission_state.zh-CN.md`
7. `TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
8. `TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`
9. `TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`
10. `TECH_10_trajectory_eval_self_improvement.zh-CN.md`

### TECH-01：Agentic Research Loop / DecisionSurface Runtime Contract

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_01_agentic_research_loop_decision_surface_contract.zh-CN.md`

范围：

- `AgenticResearchLoop`
- `ReActStep`
- `DecisionSurfaceContract`
- `DecisionSurfaceCell`
- `EvidenceRequirement`
- `RepairTicket`
- `DecisionSurfacePack`
- Lead output contract
- Specialist cell pack refs
- MemoLogicPlan consumption boundary

当前代码锚点：

- `src/sec_agent/research_lead_llm.py`
- `src/sec_agent/multi_agent_contracts.py`
- `src/sec_agent/memo_logic_plan.py`
- `src/sec_agent/p35_ai_infra_supervisor_dogfood.py`

第一批改造：

1. 增加 agentic research loop / ReActStep / DecisionSurface schema、dataclass、normalizer；
2. Research Lead 输出 decision surface、loop budget、repair policy 和 stop condition；
3. Aggregate 保留 `decision_surface_cell_id`；
4. MemoLogicPlan 从 DecisionSurfacePack 而不是 generic dimensions 生成 writer brief；
5. 添加 verifier gate，阻止 decision-surface query 落回 generic memo only。

### TECH-02：Agentic Search / Evidence Layer / SourceHunterLoop / ToolGateway

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md`

范围：

- `EvidenceRequest`
- `EvidenceResponse`
- `AgenticSearchLoop`
- `Evidence Tool Planner`
- `SourceHunterLoop`
- `Tool Registry`
- `ToolInvocationLedger`
- `Evidence Gate`
- supplement ledger promotion

当前代码锚点：

- `src/sec_agent/mcp_tool_registry.py`
- `src/sec_agent/tool_controller.py`
- `src/sec_agent/retrieval_plan.py`
- `src/sec_agent/source_route_registry_v2.py`
- `src/sec_agent/official_issuer_repair.py`
- `src/sec_agent/p34_lane_quality_runtime.py`

第一批改造：

1. 定义统一 tool contract；
2. 把 DB / RAG / graph / parser / web / market connector 接入同一 ToolGateway facade；
3. 把 P36 supplement ledger 转成 official-first source route attempts；
4. 记录 rejected candidates 和 typed failures；
5. Evidence Gate 统一 promotion status。

### TECH-03：DocumentMetadataIndex / RAG / Knowledge Layer

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`

范围：

- Source Index；
- Candidate Generator；
- Metadata Filter；
- Parsed Evidence Store；
- Accepted Research Memory；
- Method / Playbook KB；
- Institutional Context；
- Repair Cache；
- Context Router。

当前代码锚点：

- `src/sec_agent/retrieval_index_registry.py`
- `src/sec_agent/runtime_source_context_store.py`
- `src/sec_agent/context_engine.py`
- `docs/project_os/*registry*.jsonl`

第一批改造：

1. 明确 KB layer type；
2. metadata 进入 retrieval filter，而不是只做 reranker feature；
3. RAG hit 只作为 candidate；
4. 建立 RAG hit -> accepted evidence conversion eval；
5. 防止 method KB 被引用为事实。

### TECH-04：NumericProgramTrace / Parser Promotion / Fact Table Surface

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_04_numeric_program_trace_parser_promotion.zh-CN.md`

范围：

- exact row selection；
- headline selector；
- unit / period / row label sanity；
- business-line promotion；
- growth / margin / CAGR / bridge / comp / valuation multiple trace；
- analyst fact table blocks。

当前代码锚点：

- `src/sec_agent/d_series_fact_selection.py`
- `src/sec_agent/derived_metric_layer.py`
- `src/sec_agent/exact_slot_contracts.py`
- `src/sec_agent/parser_quality_ledger.py`
- `src/sec_agent/p34_lane_quality_runtime.py`

第一批改造：

1. 把 P34 fact-table projection 泛化；
2. 加 NumericProgramTrace schema；
3. 为 AI server margin、HBM economics、CoWoS、semicap backlog 建 parser/promotion fixtures；
4. 在 Workbench 展示 numeric trace；
5. Verifier 阻止未经 trace 的派生数字。

### TECH-05：Domain Evidence Operator / Decision Surface Projections

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`

范围：

- Domain evidence operator；
- FundamentalDecisionCellPack；
- ProductIndustryDecisionSurfaceProjection；
- GraphToDecisionCellProjection；
- MarketCapitalDecisionSurfaceProjection；
- RiskMatrixPack。

当前代码锚点：

- `src/sec_agent/product_intelligence_runtime.py`
- `src/sec_agent/relationship_graph.py`
- `src/sec_agent/capital_macro_pack.py`
- `src/sec_agent/r53_r60_secondary_market_capital_feedback.py`
- `src/sec_agent/specialist_llm.py`

第一批改造：

1. 五链条 x 决策格 projection fixture；
2. Product / Industry selector 按 chain balanced；
3. Market / Capital 把 ownership、valuation、price action、capital feedback 投到 price-in cells；
4. Risk 把 product / capital / market / gap 投到 counter-thesis cells；
5. specialist 输入变成 cell pack，而不是 bounded row dump。

### TECH-06：Durable Harness Runtime / Permission / State

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_06_durable_harness_runtime_permission_state.zh-CN.md`

范围：

- `TaskRun`
- `NodeAttempt`
- `ToolInvocation`
- `Observation`
- `EvidenceCandidate`
- `PromotionDecision`
- `Artifact`
- `ReviewAction`
- checkpoint / replay / resume
- HITL
- cancellation / timeout
- permission gate / sandbox / budget

当前代码锚点：

- `src/sec_agent/run_audit_store.py`
- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/r53_r60_runtime_task_spine.py`
- `src/sec_agent/workbench/job_runner.py`

第一批改造：

1. 把 run audit schema 映射到新 Harness schema；
2. 定义 idempotency / checkpoint / partial rerun；
3. 约束 full-chain rerun 只作为最后路径；
4. Workbench 读取 Harness state 而不是零散 projection；
5. 增加 checkpoint replay tests。

### TECH-07：ContextEngine / Skills / Compaction Governance

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_07_context_engine_skills_compaction_governance.zh-CN.md`

范围：

- Pinned Governance Context；
- Case Working Context；
- Role Context Pack；
- Artifact Context；
- Institutional Context；
- CompactionEvent；
- context rot / governance decay eval；
- skills progressive disclosure。

当前代码锚点：

- `src/sec_agent/context_engine.py`
- `src/sec_agent/context_manager.py`
- `src/sec_agent/method_runtime.py`
- `src/sec_agent/prompts/skills/*.md`

第一批改造：

1. pinned governance schema；
2. compaction event ledger；
3. writer no-source / source authority / supplement boundary preservation tests；
4. skill registry / role loading policy；
5. Context eval。

### TECH-08：Subagents-as-Tools / Handoff Contract

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`

范围：

- ExploreAgent；
- PlanAgent；
- EvidenceAgent；
- DomainOperator；
- WriterPresentationAgent；
- VerifierAgent；
- artifact-only handoff；
- isolated context policy。

当前代码锚点：

- `src/sec_agent/multi_agent_router.py`
- `src/sec_agent/specialist_llm.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/agent_registry.py`

第一批改造：

1. 区分 node、agent-as-tool、subgraph；
2. 定义 handoff input/output schema；
3. 防止 private scratchpad 进入 evidence；
4. Lead 调用 subagent 只获得 artifact refs；
5. subagent trajectory eval。

### TECH-09：Trace / Provenance / Workbench / ArtifactConsistencyGraph

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`

范围：

- TraceSpan；
- ClaimProvenanceGraph；
- tool observation lineage；
- parser/numeric lineage；
- decision_surface_cell review target；
- memo / PPT / Excel / dashboard consistency；
- citation clickthrough。

当前代码锚点：

- `src/sec_agent/run_audit_store.py`
- `src/sec_agent/claim_evidence_ledger.py`
- `src/sec_agent/claim_verifier.py`
- `src/sec_agent/p33_memo_projection_replay.py`
- `src/sec_agent/r53_r60_deliverable_studio_dashboard.py`

第一批改造：

1. claim -> evidence -> tool observation -> parser/numeric trace 链路 schema；
2. ArtifactConsistencyGraph；
3. Workbench trace drawer；
4. citation clickthrough test；
5. renderer/projection consistency gate。

### TECH-10：Trajectory Eval / Harness Self-Improvement

建议路径：

- `docs/architecture/agent_graph_vnext/TECH_10_trajectory_eval_self_improvement.zh-CN.md`

范围：

- trajectory eval；
- execution eval；
- provenance eval；
- context eval；
- permission eval；
- AIE eval；
- recurring issue clustering；
- patch proposal；
- deterministic fixture gate。

当前代码锚点：

- `scripts/eval_multi_agent/*.py`
- `src/sec_agent/project_os_preflight.py`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/capability_status_ledger.jsonl`
- `src/sec_agent/agent_information_economy.py`

第一批改造：

1. 统一 trajectory eval schema；
2. 每个 P36 blocker 生成 no-paid fixture；
3. trace corpus -> recurring issue proposal；
4. patch proposal 不自动合并；
5. capability ledger 自动候选更新，但需人工确认。

## 6. 建议落地需求包

### Package A：Decision Surface Spine

目标：让 Research Lead、specialist、aggregate、writer、Workbench 都能识别同一批 decision cells。

包含：

- `DecisionSurfaceContract` schema；
- `DecisionSurfaceCell` IDs；
- `RepairTicket`；
- `DecisionSurfacePack`；
- MemoLogicPlan projection；
- Workbench read-only cell matrix。

验收：

- no-paid fixture 能把 P36 五链条 x 决策维度保留到 writer payload；
- generic dimension fallback 被 verifier 阻止；
- Workbench 能列出 cell status。

### Package B：Evidence ToolGateway + SourceHunterLoop

目标：把 P36 supervisor supplement 转成 runtime 可审 candidate / accepted / gap。

包含：

- ToolGateway facade；
- EvidenceRequest / EvidenceResponse；
- P36 supplement source route attempts；
- official IR / PDF parser fixtures；
- rejected candidate ledger；
- typed failure taxonomy。

验收：

- supplement rows 不能直接进 writer；
- 每个 supplement row 至少有 route attempt / parser lineage / accepted row / typed gap 之一；
- Writer 仍无 source tool 权限。

### Package C：Domain Projection Packs

目标：把现有 graph/product/market/risk/fundamental 资产投到 decision cells。

包含：

- FundamentalDecisionCellPack；
- ProductIndustryDecisionSurfaceProjection；
- GraphToDecisionCellProjection；
- MarketCapitalDecisionSurfaceProjection；
- RiskMatrixPack。

验收：

- Product / Industry 不是 48 条 taxonomy-heavy row dump；
- Market specialist 能看到 capital/ownership/P33 feedback；
- Risk 能看到 ownership positions、product risks、relationship conflicts；
- 每个 pack 都带 source boundary 和 cannot-infer。

### Package D：Harness Runtime / Context / Trace

目标：把已有 run audit、ContextEngine、Workbench events 升级成 unified harness。

包含：

- Harness schema；
- checkpoint replay；
- pinned governance context；
- CompactionEvent；
- ClaimProvenanceGraph；
- permission gates。

验收：

- writer no-source / supplement boundary 在 compaction 后仍存在；
- 每个 claim 可追到 evidence/tool/parser/numeric；
- 越权工具 fail-closed；
- checkpoint replay 不需要 full-chain rerun。

### Package E：Workbench Cell Review + Artifact Consistency

目标：让用户审的是 decision cell 和 artifact consistency，不只是 memo claim。

包含：

- decision_surface_cell review target；
- cell status actions；
- numeric trace drawer；
- source/citation drawer；
- ArtifactConsistencyGraph；
- repair queue。

验收：

- reviewer 可 accept/reject/needs_source/needs_parser/estimate_only/commercial_gap；
- review actions append-only；
- memo/dashboard/PPT/Excel 数字和引用一致性可检查。

### Package F：Trajectory Eval + Self-Improvement

目标：把 P36 类失败转成可重复 eval 和 repair proposal。

包含：

- trajectory eval schema；
- context eval；
- permission eval；
- provenance eval；
- recurring issue clustering；
- patch proposal workflow。

验收：

- P36 Node02-11 的 root-cause 都有 fixture；
- harness 能发现 recurring issue，但不能自动 merge；
- capability ledger 只在 deterministic proof 后更新状态。

## 7. 不建议的路径

不建议：

- 先把所有工具 MCP 化，再回头做 Evidence Gate；
- 先跑 paid full-chain 或模型对比证明质量；
- 让每个 specialist 私有化 DB / RAG / web；
- 让 Writer 自己补源；
- 直接训练 reranker 掩盖 source-route / metadata / parser / promotion 问题；
- 用更多 gate 包住上游错误而不修 earliest faulty artifact；
- 把 P36 supervisor supplement 写成 runtime capability；
- 把 worklog 当作技术合同替代品。

## 8. 当前应 stage / ignore 建议

应 stage：

- `.gitignore`；
- `apps/` Workbench 源码；
- `configs/` schema / source contract；
- `src/` runtime 源码；
- `scripts/` deterministic runner / audit scripts；
- `tests/` deterministic tests；
- `docs/product/` PRD；
- `docs/architecture/` 本审计报告和相关执行计划；
- `docs/internal/` P32-P36 报告；
- `docs/project_os/` ledgers / registries / policies；
- `docs/worklog/` worklogs；
- small `data/manifests/*.json` contract / summary / fixture。

应 ignore / 不 stage：

- `reports/r53_r60_*`；
- `eval/` runtime outputs；
- `.tmp_*`；
- `.ruff_cache/`；
- `.pytest_cache/`；
- private/raw/index/model outputs；
- unreviewed large row dumps unless已有 tracked contract 依赖。

## 9. 本轮未做

- 未运行 paid LLM；
- 未运行 true full-chain；
- 未运行 MCP server；
- 未执行 source ingestion；
- 未做 parser promotion；
- 未跑完整 pytest；
- 未提交 commit；
- 未删除文件或清理目录。
