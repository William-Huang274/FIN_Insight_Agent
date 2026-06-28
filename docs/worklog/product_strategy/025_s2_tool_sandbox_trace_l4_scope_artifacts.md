# S2 Tool / Sandbox / Trace Spine L4 Scope Artifacts

日期：2026-06-29

## 问题

S1 已建立 SQL-final runtime task spine，但后续检索、爬虫、parser、renderer、Python analysis、backtest 等工具如果继续由 agent 直接调用，会出现：

- writer / composer 越权取新证据；
- web / filesystem / credential 边界不可审计；
- blocked tool call 被隐藏，无法复盘；
- tool output 没有 artifact ref / trace span；
- Redis / MQ 或局部 JSON 变成事实审计源。

S2 目标是把工具调用变成受控企业能力，并接入 S1 主账本。

## 决策

新增 S1-native `FinSightToolGateway`，并将三类 policy 分开：

- `ToolDefinition`：定义工具 id、类别、输入输出 schema、允许 actor、source boundary、artifact type；
- `SandboxPolicy`：定义 network allowlist、workspace / artifact path scope、credential access、timeout / output limit；
- `ApprovalPolicy`：定义自动允许还是需要 human approval。

所有 allowed / blocked call 都进入 `tool_invocations`，并同步写入 S1：

- `task_events`
- `trace_spans`
- allowed call 的 `artifact_refs`

## 完成

新增或更新：

- `src/sec_agent/r53_r60_tool_sandbox_spine.py`
- `scripts/engineering/build_r53_r60_s2_tool_sandbox_trace_spine.py`
- `tests/test_r53_r60_tool_sandbox_spine.py`
- `configs/r53_r60/s2_tool_sandbox_trace_schema_v0_1.json`
- `data/manifests/r53_r60_s2_tool_sandbox_trace_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s2_tool_sandbox_trace_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s2_tool_sandbox_trace_l4_scope_pass.zh-CN.md`
- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

运行时私有 SQLite store：

- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`

该 SQLite store 是本地生成镜像，不作为 Git 跟踪目标。

## 结果

真实构建命令：

```powershell
python scripts\engineering\build_r53_r60_s2_tool_sandbox_trace_spine.py --root .
```

构建结果：

- `release_decision=S2_L4_scope_pass`
- `gate_count=12`
- `gate_fail_count=0`
- `tool_policy_bindings=6`
- `sandbox_policies=5`
- `approval_policies=6`
- `approval_decisions=1`
- `tool_invocations=9`

通过的 gate：

- `schema_tables_present`
- `policy_registry_seeded`
- `allowed_tool_artifact_trace`
- `blocked_tool_calls_ledgered`
- `writer_fetch_forbidden`
- `network_domain_allowlist_enforced`
- `workspace_path_scope_enforced`
- `credential_argument_blocked`
- `human_approval_required_and_recorded`
- `unknown_tool_fail_closed`
- `runtime_projection_parity`
- `no_secret_persisted`

验证命令：

```powershell
python -m py_compile src\sec_agent\r53_r60_tool_sandbox_spine.py scripts\engineering\build_r53_r60_s2_tool_sandbox_trace_spine.py
python -m pytest tests\test_r53_r60_tool_sandbox_spine.py tests\test_r53_r60_runtime_task_spine.py tests\test_r53_r60_unified_backlog.py
python scripts\engineering\build_r53_r60_s2_tool_sandbox_trace_spine.py --root .
```

结果：

- py_compile passed
- S0/S1/S2 targeted tests：`12 passed`
- builder exit code `0`

## Root Cause Fix

S2 首次真实构建时出现 `blocked_tool_calls_ledgered` gate fail。原因不是 policy 缺口，而是 `python_analysis` 在未审批阻断和审批后允许两次调用中使用了相同 deterministic `tool_call_id`，第二次 `insert or replace` 覆盖了第一次 blocked attempt。

修复：`tool_call_id` 纳入 `approval_decision_id` / `no_approval` marker，确保审批态变化下的同参调用分别保留。

该问题已通过 `test_tool_gateway_records_pre_and_post_approval_attempts_separately` 固化。

## 边界

S2 只证明工具权限、sandbox policy、approval gate 和 tool trace / ledger 在自身范围达到 `L4_scope_pass`。本轮不执行真实 web crawling、document parsing、Python analysis 或 quant backtest。

## 后续

进入 S3 时应优先做：

- 将 DB exact、BM25/ObjectBM25、Milvus、graph、web repair、parser rows 纳入 `ToolGateway`；
- 生成 `RetrievalExecutionLedger`；
- 对 selected / dropped evidence 做 source-boundary 和 rerank audit；
- 让 S3 的 retrieval / data lineage gate 复用 S2 的 policy / trace spine。
