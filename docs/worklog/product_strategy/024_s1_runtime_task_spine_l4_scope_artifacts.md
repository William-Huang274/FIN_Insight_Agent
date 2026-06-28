# S1 Runtime Task Spine L4 Scope Artifacts

日期：2026-06-29

## 问题

R53-R60 新主线已经完成 S0 backlog / gate matrix，但 S2-S10 不能继续依赖散装 run JSON、Redis / MQ 状态或 Java gateway 局部任务表。需要先把 `ResearchTask`、`TaskRun`、`TaskEvent`、`WorkpaperEvent`、artifact、checkpoint、trace 和 progress projection 固化成 SQL-final 主账本。

## 决策

S1 不替换现有 Java gateway 和 Python Workbench，而是新增 Python-side runtime spine：

- `FinSightResearchRuntimeFacade` 作为后续 Java / Workbench / CLI 的稳定入口；
- SQLite 作为本地 SQL-final 审计源；
- Redis / MQ 只做协作状态，不做最终审计；
- `WorkpaperEvent` 必须 append-only；
- terminal task 不能直接回到 `running`，必须通过显式 `resume_task` 生成新 run；
- Java gateway-style payload 必须能导入 S1 主账本，保证后续桥接迁移有兼容路径。

## 完成

新增或更新：

- `src/sec_agent/r53_r60_runtime_task_spine.py`
- `scripts/engineering/build_r53_r60_s1_runtime_task_spine.py`
- `tests/test_r53_r60_runtime_task_spine.py`
- `configs/r53_r60/s1_runtime_task_spine_schema_v0_1.json`
- `data/manifests/r53_r60_s1_runtime_task_spine_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s1_runtime_task_spine_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s1_runtime_task_spine_l4_scope_pass.zh-CN.md`
- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

运行时私有 SQLite store：

- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`

该 SQLite store 是本地生成镜像，不作为 Git 跟踪目标。

## 结果

真实构建命令：

```powershell
python scripts\engineering\build_r53_r60_s1_runtime_task_spine.py --root .
```

构建结果：

- `release_decision=S1_L4_scope_pass`
- `gate_count=10`
- `gate_fail_count=0`
- `research_tasks=2`
- `task_runs=3`
- `task_events=16`
- `node_executions=1`
- `artifact_refs=2`
- `workpaper_events=1`
- `checkpoint_refs=1`
- `trace_spans=1`
- `task_progress_projection=2`

通过的 gate：

- `schema_tables_present`
- `schema_metadata_version`
- `state_machine_status_values`
- `illegal_transition_blocked`
- `task_run_event_counts`
- `artifact_node_checkpoint_trace_rows`
- `workpaper_append_only`
- `resume_replay_reconstructs_state`
- `gateway_compatibility_rows`
- `projection_parity`

验证命令：

```powershell
python -m py_compile src\sec_agent\r53_r60_runtime_task_spine.py scripts\engineering\build_r53_r60_s1_runtime_task_spine.py
python -m pytest tests\test_r53_r60_runtime_task_spine.py
python scripts\engineering\build_r53_r60_s1_runtime_task_spine.py --root .
```

结果：

- py_compile passed
- `tests/test_r53_r60_runtime_task_spine.py`: `4 passed`
- builder exit code `0`

## 边界

S1 只证明 runtime task spine 在自身范围达到 `L4_scope_pass`，不声明全产品 `L4_production_pass`。

本轮没有把现有 Java gateway 改成直接写 S1 表，也没有改 Workbench UI。S2 / S6 后续需要把 tool ledger、sandbox、Java API / Workbench drilldown 接入该主账本。

## 后续

进入 S2 时应优先做：

- `ToolGateway` / `ToolInvocationLedger` 写入 S1 `task_events`、`artifact_refs`、`trace_spans`；
- `SandboxPolicy` / `ApprovalPolicy` fail-closed；
- tool-call replay 和 forbidden-call deterministic tests；
- Java gateway / Workbench API 在后续 slice 中逐步由兼容导入升级为 native S1 facade 写入。
