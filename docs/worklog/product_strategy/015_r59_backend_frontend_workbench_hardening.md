# 015 R59 Backend / Frontend Workbench Hardening

日期：2026-06-28

## Prompt

用户要求继续做 R59 文档：先复盘当前前后端已实现部分，再参考市面上成熟、最新、企业级 agent 项目和代码 agent / 非 agent 项目的前后端做法，设计时必须围绕 FinSight 的功能实现，考虑容灾容错、异常监控和兜底能力，并按企业级标准处理。

## Reasoning

本轮判断 R59 不能只是“前端页面规划”或“Java gateway 加壳”。当前项目已经有：

- Java Research Gateway：task / queue / callback / SSE / cancel / resume smoke；
- Python Workbench backend：profiles、source bundles、data build、runs、sessions、evals、checkpoint、artifact inspect；
- React/Vite Workbench：工程调试型 profile/source/data build/run/eval/artifact/job console；
- Runtime bridge / run audit：Java -> Python worker smoke、run/node/artifact/evidence/claim/gap/gate/model ledger。

但这些仍主要是研发型 Workbench，不是 B 端金融研究产品工作台。R59 应将 Java/API Gateway、Python runtime、前端工作台、SQL/ObjectStore、Redis/MQ、R60 eval/incident 之间的职责边界冻结下来。

## Work Completed

新增技术文档：

- `docs/architecture/agent_graph_vnext/34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md`

文档内容包括：

- 当前 Java Research Gateway、Python Workbench backend、React/Vite frontend、runtime bridge / audit 的能力和不足；
- R59 三层目标架构：Frontend Product Workbench、Enterprise Backend Gateway、Python Research Runtime；
- 外部参考台账：
  - LangGraph / LangSmith Agent Server；
  - Temporal HITL durable workflow；
  - Codex hooks / approvals；
  - Claude Code / Agent SDK；
  - Microsoft Copilot Studio；
  - Google Gemini Enterprise Agent Platform；
  - Onyx；
  - Glean；
  - Palantir AIP；
  - Hebbia Matrix；
  - Dify Knowledge Pipeline；
  - RAGFlow Knowledge Graph；
- Backend object model：Tenant、User、ProjectSpace、ResearchTask、TaskRun、TaskEvent、WorkpaperPackRef、EvidenceItemRef、GapCard、ReviewComment、ApprovalDecision、DeliverablePlan、ArtifactRef、DashboardProjection、IncidentRecord；
- API surface 草案：task/run、workpaper/evidence/review、artifact/deliverable/dashboard、admin/ops；
- 前端目标信息架构：Dashboard、Research Task Center、Evidence Workbench、Workpaper Builder、Review Queue、Deliverable Studio、Admin/Ops；
- 容灾容错、incident taxonomy、fallback/degraded mode 原则；
- R59-D01 到 R59-D16 demand 草案和 acceptance gates。

同步更新：

- `docs/architecture/agent_graph_vnext/README.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`

## Result

R59 现在成为 R53-R60 program 中的 active technical source of truth。核心结论：

- Java/API Gateway 应承接企业入口、任务生命周期、权限、事件、artifact、review 和 admin/ops。
- Python Workbench backend 应逐步收敛为 internal runtime/admin service，不再作为最终 B 端 public API 的唯一入口。
- 前端应从 debug console 升级为围绕 Dashboard、Task Center、Evidence Workbench、Workpaper Builder、Review Queue、Deliverable Studio 的金融研究工作流产品。
- Redis/MQ 只做 transient queue / pubsub / heartbeat；SQL/ObjectStore/WorkpaperEvent 才是最终审计主账本。
- fallback 必须显式暴露为 degraded mode / IncidentRecord / RecoveryAttempt，不允许隐藏事实缺口或质量降级。

## Verification

- 本轮为 docs-only 规划更新。
- 未改 runtime 代码。
- 未运行前端 build、后端单测或 full-chain case。
- 后续需要运行 `git diff --check` 和文档 secret scan。

## Follow-up

- R59-D01-D16 仍待和 R60 eval/incident/release gate 一起拆实现 release slice。
- 需要决定 Java gateway 是否升级 Spring Boot / Quarkus / Micronaut，还是先沿用轻量 JDK server 做一版最小企业合同。
- 需要为 Evidence Workbench / Workpaper Builder / Review Queue / Deliverable Studio 选第一批实现顺序。
- 需要设计 load/chaos gate：worker crash、provider timeout、SSE reconnect、artifact write failure、queue backlog、SQL/ObjectStore pressure。
