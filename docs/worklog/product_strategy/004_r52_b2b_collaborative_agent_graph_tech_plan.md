# R52 B2B Collaborative Agent Graph Tech Plan

日期：2026-06-28

## Prompt

用户要求开始拆 R52，讨论协作型 agent graph 怎么跑，以及 agent 如何嵌入公司工作流。用户指出当前 multi-agent 更像主 agent 并发发出几个调用请求，再做一次二次调用后进入审查和写作，缺少有效、高效的 agent 间通信/协作，也缺少 human / lead agent in the loop。

## Decision

将 R52 技术方案定义为 `Shared Workpaper Event Ledger + Research Lead supervision + Specialist Workstreams + Human Review / Approval`。

关键决策：

- 内部 specialist 协作不使用 A2A，也不做自由 agent-to-agent chat。
- 协作中心从聊天历史切换为 `WorkpaperPack` 和 append-only `WorkpaperEvent`。
- Research Lead 是常驻 supervising analyst，负责合同、分派、审查、repair、合并和 DeliverablePlan。
- Specialist 只写 role-scoped contribution，默认不能直接查新事实。
- Human reviewer 是正式 actor，合同审批、底稿评论、证据降权、交付物批准都进入 event ledger。
- Java 后端负责企业 workflow、task、permission、approval、SSE、queue 和 trace；Python / LangGraph 保留研究执行。
- R52 不能退化成 `Lead 派单 -> specialist 并发 -> Lead repair 一次 -> writer 输出`；必须支持 Lead 多轮 checkpoint、specialist workstream、cross-specialist structured communication、event-driven rework 和 human comment / approval resume。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，加入 26 文档索引。
- 26 文档定义：
  - B 端企业工作流嵌入方式；
  - 10 阶段 collaborative graph；
  - `WorkpaperPack`、`WorkpaperEvent`、projection views；
  - Research Lead / Evidence Operator / Specialist / Deliverable Composer / Verifier / Human Reviewer 职责边界；
  - async / sync barrier；
  - repair loop；
  - ContextEngine 和 tool permission；
  - task / workpaper / section / gap 状态机；
  - Java / Python / DB 映射；
  - collaboration eval；
  - R52.0-R52.6 迁移路径；
  - R53 Research-to-Quant 接口。
- 本轮继续扩展 26 文档，补入：
  - R52 防退化原则；
  - B 端 Dashboard / Company Workspace / Project Workspace / Data Room / Evidence Workbench / Workpaper / Graph View / Deliverable Studio / Review Queue / Eval Audit 嵌入点；
  - `WorkpaperEvent` 作为审计、状态迁移、调度触发和 projection source；
  - `QuestionToRole`、`ChallengeToClaim`、`DependencyRequest`、`ReworkDirective`、`ConflictNotice`、`CounterThesisRequest` 等结构化跨 specialist 通信；
  - Research Lead 七个 checkpoint；
  - specialist workstream 状态机；
  - R52.3 collaborative graph runtime 通过条件收紧。

## Result And Evidence

- 技术方案路径：
  - `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- 架构索引已更新：
  - `docs/architecture/agent_graph_vnext/README.zh-CN.md`

## Verification

- `git diff --check` 已通过。
- 本轮未运行 runtime、agent graph、LLM、parser、DB、frontend 或 full-chain 测试，因为变更范围是技术方案文档和索引。

## Follow-up

后续实现建议从 R52.0-R52.2 开始：

1. 冻结 ResearchTask / WorkpaperPack / WorkpaperEvent schema。
2. 实现 event ledger 和 projection。
3. 把现有 ClaimCards / JudgmentState / DimensionEvidencePortfolio 投影为 WorkpaperPack。
4. 再接 LeadReview barrier、human approval 和 Deliverable Composer 权限。
