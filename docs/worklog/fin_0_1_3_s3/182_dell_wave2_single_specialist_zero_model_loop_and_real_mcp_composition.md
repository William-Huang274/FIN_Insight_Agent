# Dell Wave 2 单 Specialist scripted qualification 与真实本地 MCP 组合

日期：2026-09-04
代码提交：`469484a04127c2d5f993c8b2749a6bcf406c8a04`
状态：`WAVE2_Q1_SPECIALIST_SCRIPTED_ZERO_CALL_REAL_IN_PROCESS_MCP_QUALIFICATION_PASS_BOUNDED`

## 1. 本工作包解决什么

本工作包只实现 Dell 完整纵切 Wave 2 的第一小段：证明一个固定 Q1 Specialist 可以在真实 LangGraph 循环中多轮选择 Evidence/Finance 动作、接收 typed observation/feedback、修正请求，并在现有 S1/S2 权威合同下生成 source-bound submission 或 terminal human-review artifact。

它不是 Wave 0B/r8 的继续。r8 证明的是 Agent Server 本地控制面、FIN identity、restart/resume、SSE 与 LangSmith；本工作包证明的是尚未进入 serving graph 的 Specialist 内循环候选。两者不能合并成同一个 PASS。

## 2. 成熟栈优先与自研边界

本轮复用：

- LangGraph `StateGraph` 作为循环执行框架；
- 官方 MCP Python SDK 2.1.1 与现有单一 MCP server；
- `open_dell_approved_data_composition`；
- 现有 SourceFamilyCompiler 与 `SourceFamilyCompilationReceipt`；
- 现有 Reviewed Evidence mandatory reread/filter 与 `ReviewedEvidenceFilterReceipt`；
- 现有 S2 `NumericFactProjection`；
- Pydantic strict schema。

本轮没有新增：

- retriever、向量库或 reranker；
- 第二个 MCP server；
- 数据库、队列或 checkpointer；
- 自研 model SDK；
- 新 receipt store、RuntimeScope、route authority 或 handoff store；
- runtime fallback。

未来真实模型执行必须复用 canonical `ActionAttempt`、现有 `DeepSeekStructuredAgentAdapter`、LangSmith/audit capture 与 Agent Server/PostgreSQL identity binding；不得为 Specialist 再造一套平行执行协议。

## 3. 实际拓扑

当前 graph 是真正的循环，而不是一次性 wrapper：

```text
initialize
  -> scripted semantic action
  -> request_evidence / request_finance
  -> existing in-process MCP
  -> typed observation / feedback
  -> scripted revise
  -> validate source-bound submission
  -> END

任一显式人工请求或 model/tool ceiling
  -> terminal review artifact
  -> END
```

当前没有 native `interrupt/resume`。terminal review 只表示本次 qualification 图停止；artifact 写死：

- `continuation_authorized=false`；
- `required_resume_authority=canonical_intervention_authority_unavailable`；
- `server_checkpoint_binding_state=qualification_terminal_not_server_bound`。

因此不能称其为 durable HITL。

## 4. scripted turn 与模型执行的隔离

初版审计发现 model callable 能同时返回 action 与自造 `RuntimeReceipt`，从而把没有发生的模型调用写成成功模型轮次。修正后：

- model port 只接受一个 strict `SpecialistAction`；
- 夹带 `runtime_receipt` 会在任何 tool dispatch 前被 schema 拒绝；
- Notebook turn 固定为 `turn_source=scripted_qualification`；
- `model_execution_evidence=false`；
- 没有 provider/model/profile、token usage 或模型成功声明。

这使本轮记录只能证明脚本化语义动作的 graph 行为，不能被投影为模型 execution receipt。

## 5. qualification composition 的产品边界

初版 composition 虽将模型权限字段写成 false，却公开暴露可由 `dataclasses.replace` 替换的 raw dependencies。修正后：

- 类型改为 `DellSpecialistScriptedQualificationComposition`；
- factory 改为 `open_dell_specialist_scripted_qualification_composition`；
- 文档和字段明确 `non-product / zero-call / scripted qualification`；
- 对外只给 compiled graph、graph input 与 current authority digests；
- 不暴露 raw dependencies；
- 没有 production/model composition 入口。

## 6. current disclosure 边界

current-state progressive disclosure 需要 sealed `RuntimeScope`、current scope/catalog/ledger/context resolvers；这些尚未接入本图。为避免 caller 自报 available：

- `SpecialistL0Context.disclosure_runtime_state` 目前只有 `current_state_authority_unavailable_fail_closed` 一个合法值；
- `request_disclosure` 已从 provider `SpecialistAction` union 移除；
- 它不在 `allowed_actions`；
- graph 没有 disclosure dispatch node；
- caller 篡改为 available 或 model 返回 disclosure action 都会在工具调用前失败。

未来接入 progressive disclosure 时必须作为新 schema/runtime successor，不能把本轮 unavailable 字段原地放宽成 caller authority。

## 7. S1 required route 的真实权威链

required route 不能由“检索有结果”或 tool 自报完成。当前真实 MCP composition 只有在以下条件同时成立时才产生 graph-local `SpecialistRouteCompletion`：

1. exact current Owner data-gate decision digest；
2. exact current inventory digest；
3. exact current source-route catalog digest；
4. current baseline source-plan digest；
5. exact required route/branch/route digest；
6. 唯一且 accepted 的 `SourceFamilyCompilationReceipt`；
7. 全部 expected Reviewed Evidence targets；
8. 每个 target 的 mandatory ID reread；
9. exact `ReviewedEvidenceFilterReceipt` 与 current reviewed-index digest；
10. expected/observed target exact coverage；
11. writer-citable Evidence IDs 与 source-family 集合。

graph 写入 satisfied route 前再次核对 completion 的 Owner/catalog/inventory 与 Notebook current binding。`direct_tool` observation 即使自算完整 self-digest，也不能携带 route completion。

## 8. S2 authority

Specialist 的 finance action 只是受限 query shape。实际执行仍进入既有 MCP finance tool，再由 canonical `CompanyFinancialFactQuery` 与 S2 mart 决定结果。只有通过 `NumericFactProjection` 且 `numeric_fact_authority=true` 的 row 才能成为 authoritative fact reference。

本轮没有 S2 write、Evidence admission、数字改写或模型授予 authority。

## 9. dispatch 前 fail-closed

以下错误全部在真实 MCP tool 被调用前拒绝：

- stale/wrong Owner data-gate decision digest；
- stale/wrong inventory digest；
- stale/wrong source-route catalog digest；
- foreign、unassigned 或不存在的 evidence route；
- unavailable disclosure；
- model 自签 receipt；
- stale model context digest；
- 重复的相同语义 tool action。

tool exception 被转换成 typed non-gap feedback；它不能被写成 public-information gap。

## 10. 测试与环境证据

锁定环境：

```text
D:\FIN_Insight_Agent\.venv\Scripts\python.exe
Python 3.11.14
mcp 2.1.1
langgraph 1.2.11
pytest 9.1.1
```

直接 Wave 2 suite：

```powershell
& 'D:\FIN_Insight_Agent\.venv\Scripts\python.exe' -m pytest `
  -q -p no:cacheprovider `
  tests/test_dell_specialist_agentic_graph.py `
  tests/test_dell_specialist_agentic_composition.py
```

结果：`30 passed`。其中 graph 文件 23 条；composition 文件 5 个 test function，其中 authority-digest case 参数化为 3 条，实际 7 条。

扩大相邻回归覆盖 Agent Server data/client/live-r8/identity/entry/deployment、current inventory、旧 reference graph/real composition、Owner gate、Reviewed Evidence inventory、SourceFamilyCompiler、progressive disclosure 与新 Specialist：`280 passed`。

目标文件 `compileall`、`git diff --check` 与 candidate secret scan 均通过。环境曾出现一次系统 Python 3.10＋MCP 1.27.2 导致的 2 条误报；在仓库锁定 `.venv` 中 `MCPServer`、`Client` 与全部专项测试均通过，因此该误报不属于代码 failure 或 public gap。

Project OS 定向回归为 `81 passed / 1 failed`。唯一失败仍精确为既存的 `current_dynamic_writer_submission_successor:implementation:3` 对未由本工作包修改的 `src/sec_agent/project_os_preflight.py` sealed SHA drift；同一失败已在工作日志 181 多次保存。本工作包不重签历史 authority、不把它算作 Wave 2 新失败，因此 `full_repository_green=false`，但它不改变上述 30 条专项与 280 条相邻回归的 bounded 结论。

## 11. 独立审计

初轮作者分离只读审计发现四类 P1：

- model receipt 自证；
- zero-model composition 暴露 replaceable callables；
- direct tool completion 可伪造 required-route satisfied；
- terminal artifact 未绑定 server thread/checkpoint。

前三项已按上述结构修正。第四项没有伪装关闭，而是把 artifact 明确降格为 `qualification_terminal_not_server_bound`，正式唯一 entry/recovery 继续由现有 Agent Server client、PostgreSQL identity repository 与 canonical checkpoint负责。

两名独立 reviewer 在最新提交前工作树复审结果均为：`P0=0 / P1=0`。这个清零只针对本工作包的 bounded qualification，不代表 paid readiness 或产品验收。

## 12. 明确没有证明什么

- provider/DeepSeek/model calls：`0`；
- network/live-external calls：`0`；
- paid calls：`0`；
- Agent Server serving graph 消费 Specialist：`false`；
- saved provider response replay：`false`；
- `ContextProjection`/compaction：`false`；
- current progressive disclosure：`false`；
- durable HITL/resume：`false`；
- 非 Q1 Specialist：`false`；
- Lead/Counter/Verifier/dynamic multi-agent：`false`；
- 最终 Dell report、产品、人审：`false`。

`product_capability_delta=none`，`research_quality_delta=none_no_natural_model_judgment`。

## 13. 下一步与停止条件

在任何真实 DeepSeek Specialist shadow 前，按以下顺序执行：

1. 关闭或由 Owner 明确重裁 `RC-S3-107`，补 remote create→FIN bind 的 PENDING/ORPHAN/RECONCILED unknown-outcome lifecycle；
2. 将 Specialist 纳入唯一正式 Agent Server serving graph，并复用现有 durable FIN↔server identity/checkpoint binding；禁止 direct-invoke production fallback；
3. 落最小 `ContextProjection` 与 compaction，实测 model-visible 输入规模；
4. 通过现有 `DeepSeekStructuredAgentAdapter`、canonical `ActionAttempt` 与 LangSmith/audit capture 完成零调用 saved-response replay；
5. 在 clean pushed commit 上冻结新的 `PaidExecutionOwnerDecision` 与 task-specific `TokenBudgetBasis`；
6. 才允许一次 single Specialist、single branch、bounded turns/actions、无 silent retry/fallback 的真实 shadow。

任一前置门失败，停止在其责任层保存 evidence；不得跳到 Lead/multi-agent，不得把失败自动升级为新产品版本，也不得调用 DeepSeek。

本轮没有新增 immutable failed execution attempt，因此不机械新增 root-cause ledger 条目；`RC-S3-107` 保持 open。
