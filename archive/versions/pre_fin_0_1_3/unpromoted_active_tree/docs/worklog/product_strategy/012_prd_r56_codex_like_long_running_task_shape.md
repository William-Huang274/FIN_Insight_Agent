# PRD / R56 Codex-like Long-running Task Shape

日期：2026-06-28

## Prompt

用户要求把“复杂研究任务应像 Codex / Claude Code / OpenCode 类工具一样，不断切分任务、更新结果、repair、验证直到完成”的产品形态补进 PRD / R56 文档中，然后继续讨论知识图谱和 skill。

## Reasoning And Decision

原 PRD 已经定义 B 端工作台、Workpaper、Deliverable Studio 和协作型 multi-agent，但还不够明确地区分：

- 简单问答；
- 中等 focused memo；
- 复杂 deep research workpaper；
- 持续 watchlist；
- Research-to-Quant。

R56 原文也定义了 RuntimeFacade / ToolGateway / ContextEngine，但还缺 `Codex-like long-running task runner` 的状态机和产品层 progress projection。为避免后续实现退化成 fixed fanout，本轮把产品执行形态和 runtime contract 同步补齐。

## Work Completed

- 更新 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：
  - 新增 `4.1 任务执行形态：Codex-like 长程研究任务`；
  - 新增 `4.2 任务模式`；
  - 新增 `4.3 工作台交互布局`；
  - 明确复杂任务的核心产物是 `ResearchTask / WorkpaperEvent / WorkpaperPack / EvidencePack / GapLedger / JudgmentState / DeliverablePlan / FactorHypothesis / FactorCard / EvalTrace`，答案只是投影。
- 更新 `docs/architecture/agent_graph_vnext/31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`：
  - 新增 `3.9 Codex-like 长程任务执行，不等于一次 fanout`；
  - 新增 `TaskProgressProjection`；
  - 新增 runtime 状态机；
  - R56 acceptance gate 增加 task progress projection 和 repair-subgraph 要求。
- 更新 `docs/worklog/README.md` 索引。

## Result

产品形态已明确：

```text
Quick Answer
Focused Memo
Deep Research Workpaper
Watchlist / Monitoring
Research-to-Quant
```

复杂任务必须支持：

```text
create_run
append_event
get_current_view
pause_for_human
resume_run
repair_subgraph
replay_run
export_deliverable
```

这把后续实现从“Lead 一次派单 + specialist fanout + writer 汇总”约束为“长程 ResearchTask + event stream + Lead 多 checkpoint + targeted repair + human review + deliverable projection”。

## Verification

- Docs-only change。
- 本轮未运行 runtime、parser、DB、frontend、LangGraph 或 eval 测试。
- closeout 前仍需跑 `git diff --check` 和候选文档 secret scan。

## Follow-Up

- 下一步讨论知识图谱和 skill：需要明确哪些图谱对象进入 Research Lead planning，哪些进入 specialist skill，哪些作为 ContextEngine 可检索上下文，哪些只能作为 visualization / reasoning support。
