# 118 - P37 Git hygiene / 代码库审计 / PRD 对齐

记录时间：2026-07-09

## 用户要求

用户确认当前 PRD 规划方向可接受，要求进入工程问题：

- 先做一次 git 清理；
- 不用的代码 / 产物 ignore；
- 要用的内容 stage；
- 整理当前项目已实现功能；
- 输出完整审计报告；
- 与新 PRD 对齐，明确后续具体怎么改。

## 本轮判断

当前仓库不是干净小改动状态，而是一个长期累积的工程分支：

- tracked modified 覆盖 `apps/`、`configs/`、`data/manifests/`、`docs/`、`scripts/`、`src/`、`tests/`；
- untracked 覆盖 `docs/project_os/`、P32-P36 internal docs、P33-P35/P36 scripts、tests、fixture JSON、worklogs；
- `reports/r53_r60_*` 是明显 runtime / browser / full-chain 输出目录，不应进入 Git；
- `docs/project_os/` 是 Project OS durable source-of-truth，不应 ignore；
- P32-P36 docs / ledgers / tests / scripts / source files构成当前已实现能力和审计证据，应该 stage，但仍不能说这些都是 runtime 已闭环。

## Git hygiene 操作

本轮已更新 `.gitignore`：

- 增加 `/reports/r53_r60_*/`；
- 增加 `.ruff_cache/`。

原因：

- `reports/r53_r60_p20_deepseek_smoke/`、`reports/r53_r60_p24_b04_product_acceptance_browser_e2e/`、`reports/r53_r60_p30_full_chain_ai_semis/` 是运行输出；
- `.ruff_cache/` 是本地缓存；
- 这些不应进入 Git。

本轮已完成 staging：

- staged 路径：`.gitignore`、`apps/`、`configs/`、`data/manifests/`、`docs/`、`scripts/`、`src/`、`tests/`；
- staged 文件数：420；
- 已确认 `reports/` 与 `.ruff_cache/` 未进入 staged diff；
- `git diff --cached --check` 通过；
- `python -m compileall -q src scripts` 通过；
- 严格密钥扫描未发现真实 key，仅命中测试/文档中的敏感词检查样例。

未做：

- 未删除任何文件；
- 未运行 `git clean`；
- 未 revert；
- 未使用 `git add .`，只按可用资产路径 staging；
- 未 commit / push。

## 代码库审计结果

新增审计报告：

- `docs/architecture/agent_graph_vnext/37_agentic_research_harness_codebase_audit_and_technical_doc_split.zh-CN.md`

报告覆盖：

1. Git / 仓库状态；
2. 已实现功能审计；
3. 新 PRD 对齐总表；
4. 技术文档拆分建议；
5. 后续落地需求包；
6. 不建议路径；
7. stage / ignore 建议；
8. 当前未运行边界。

## 当前已实现能力摘要

静态审计确认当前项目已有以下能力资产：

- Workbench backend / frontend；
- profile / source bundle / data build / run events / session turn / eval run；
- R53-R60 task center、review queue、resume / cancel、ops projection、deliverables、dashboard projection；
- LangGraph-style orchestration；
- run audit store；
- WorkpaperEvent / review action / job runner；
- MCP contracts / MCP runtime / tool registry / tool controller；
- ContextEngine / method runtime / skill prompts；
- source route / public web parser / exact slot / parser quality / P34 live route attempt；
- ProductIntelligenceGraph / relationship graph / capital macro pack / secondary market capital feedback；
- Research Lead / specialist / aggregate / MemoLogicPlan / Memo Writer / verifier；
- Project OS ledgers / preflight；
- P32-P36 deterministic fixtures, runners and tests。

## 与新 PRD 的主要差距

P36 后的新 PRD 要求是 decision-surface-first + harness-first。当前代码资产很多，但关键桥梁尚未闭环：

- Research Lead 尚未原生输出 `DecisionSurfaceContract`；
- specialist 仍按 role / source family / memo slot 工作，不按 `decision_surface_cell_id` 工作；
- `DecisionSurfacePack` 和 `DecisionSurfaceAdjudicator` 缺失；
- `SourceHunterLoop` 尚未把 P36 supervisor supplement ledger 变成 runtime rows / typed gaps；
- ToolGateway / Evidence Gate / permission gate 尚未成为所有工具的唯一入口；
- ContextEngine 尚未有 pinned governance / CompactionEvent / governance decay gate；
- Product / graph / market / risk / fundamental assets 未投射成五链条 decision cells；
- Workbench 缺 `decision_surface_cell` review surface；
- Provenance 还没统一到 claim -> tool observation -> parser/numeric lineage；
- trajectory eval 和 harness self-improvement 仍是分散 runner / ledger，不是统一 harness。

## 技术文档拆分建议

审计报告初版建议拆 10 份 TECH。2026-07-09 后续讨论发现必须把 `Agentic Search / Agentic Research / bounded ReAct` 显式纳入 TECH 主线，因此 canonical 拆分已修订为：

0. `TECH_00_agentic_research_technical_index.zh-CN.md`
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

## 后续落地包建议

建议按 6 个 package 组织需求：

1. `Package A - Decision Surface Spine`
2. `Package B - Evidence ToolGateway + SourceHunterLoop`
3. `Package C - Domain Projection Packs`
4. `Package D - Harness Runtime / Context / Trace`
5. `Package E - Workbench Cell Review + Artifact Consistency`
6. `Package F - Trajectory Eval + Self-Improvement`

## 当前边界

- 本轮是 git hygiene + 静态审计 + 文档整理；
- 未运行 paid LLM；
- 未运行 true runtime full-chain；
- 未运行 MCP server；
- 未运行 source ingestion；
- 未做 parser promotion；
- 未跑完整 pytest；
- 本轮新增报告和 `.gitignore` 不代表任何 runtime blocker 已关闭。
