# R56 Agent Runtime Stack Framework Draft

日期：2026-06-28

## Prompt

用户要求把当前讨论出的 R56 runtime / framework 借鉴原则记录到 R56 草稿中，并按可持续维护文档处理；需要注明参考出处，方便后续外部平台更新能力时同步维护。写完后继续讨论这些借鉴内容如何落地、能解决项目中的哪些问题。

## Reasoning And Decision

本轮不进入实现。R53/R54/R55 目前均停在 framework layer，等待 R56-R60 底座确定后再拆具体需求单。因此 R56 也先作为 framework-level living registry：

- 记录外部平台和框架参考来源；
- 明确哪些能力吸收、哪些不采用；
- 保持 FinSight 自研业务 runtime facade，而不是让通用 agent framework 反客为主；
- 把 LangGraph、MCP-style ToolGateway、Hermes-style ContextEngine、Temporal-style durable workflow、OpenTelemetry/Langfuse/Phoenix-style observability、Java/Workbench 产品层分别定位；
- 冻结 actor/tool/context/checkpoint/trace/resource queue 的对象和 acceptance gate。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，加入 R56 文档索引和总原则第 20 条。
- 更新 `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`，把 R56 草案加入关联文档，并记录 R56 仍是 framework layer、尚未实现 D01-D09。
- 更新 `docs/worklog/00_internal_master_checklist.md`，补充 R56 framework draft 状态和剩余实现项。
- 更新 `docs/worklog/README.md`，加入本工作日志索引。

## External References Recorded

R56 文档记录了以下参考方向和出处：

- Codex / Claude Code-style harness：workspace scoped execution、approval、hooks、sandbox。
- LangGraph：persistence、interrupt/resume、time travel。
- Temporal-style durable execution：long-running workflow、workflow history、human signal。
- Hermes：ContextEngine 插件化和 config-driven selection。
- MCP：tools/resources/prompts 标准协议。
- OpenAI Agents SDK：handoffs、guardrails、tracing。
- Microsoft Agent Framework / Google ADK：typed contracts、middleware、telemetry、enterprise deployment。
- Dify / RAGFlow：workflow UI、RAG pipeline、运营面板。
- Feishu / DingTalk：企业工作流入口、审批、通知、组织空间、文档表格协同。
- OpenTelemetry / Langfuse / Phoenix-style observability：trace/eval export 方向。

## Result

R56 当前结论：

```text
自研 FinSightRuntimeFacade
 + LangGraph research graph
 + MCP-style ToolGateway
 + Hermes-style ContextEngine interface
 + Temporal-style durable workflow optional
 + OpenTelemetry / Langfuse / Phoenix-style trace/eval export
 + Java backend / Workbench enterprise frontdoor
```

该方案用于解决当前全链路复盘困难、工具权限散乱、上下文注入漂移、多入口状态不一致、writer 越权补事实、长任务恢复不足、资源/模型调度不可见和 eval/observability 脱节等问题。

## Verification

- Docs-only change。
- 本轮未运行 runtime、parser、DB、frontend、LangGraph 或 eval 测试。
- 后续 closeout 前仍需跑 `git diff --check` 和候选文档 secret scan。

## Follow-Up

- 继续讨论 R56 落地方式：先落 Python RuntimeFacade 还是 Java + Python 双端 contract。
- R57 / R58 / R59 / R60 文档需要继续补齐，之后再统一拆 R53-R60 demand tickets。
- R56-D01-D09 实现需求尚未开始。
