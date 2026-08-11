# Thread Handoff: Point 01 M1 API Lifecycle -> M2 DecisionSurface Compiler Shadow

日期：2026-07-12

来源窗口用途：产品方向规划、架构讨论与审计。

目标窗口用途：Point 01 工程实现、deterministic verification 与 scoped closeout。

状态：`superseded_after_m1_1_m1_2_m2_1_m2_2_fixture_execution / use_point01_section_26`

> 2026-07-12 supersession：该交接已被执行，不能再作为“从 M1A/M1B 开始”的当前 prompt。现有成果已重归档为 M1.1/M1.2、M2.1/M2.2 fixture proven；后续必须按 Point 01 第 26 节执行，先补 M1.3 retry/multi-attempt，再逐项完成 M2.3-M2.10。

## Current Goal

从已完成的 Point 01 M0 canonical control kernel 继续实施：

```text
M1A RuntimeFacade execution lifecycle completion
  -> M1B DecisionSurface service boundary and validation
  -> M2 deterministic/compiler shadow slice
  -> later M3 comparison/reviewer calibration
  -> later M4 approved case-scoped cutover
```

新窗口首先补齐 compiler 运行必需的 M1A lifecycle/read/recovery APIs，不应一次实现 API_01 的 M3/M4 comparison、review、cutover 或 rollback commands。

## M1A Closeout Addendum（2026-07-12）

本交接中的 M1A 已在原窗口完成，专项实现为 `bind_legacy_task_run`、`complete_attempt`、`fail_attempt`、`cancel_work_unit`、两类 execution view、artifact version digest read 和 fail-closed event replay；typed conflict/state/artifact errors、append-only history/outbox、idempotency/CAS 和 kill-switch read/replay 均有 deterministic coverage。

验证命令：`python -m pytest -q -m fast_contract tests/contract tests/test_runtime_bridge_contracts.py tests/test_r53_r60_runtime_task_spine.py`，结果 `35 passed`。本文件的 M1A scope/acceptance 段保留为审计历史；后续只允许进入 M1B validation/read boundary 和 deterministic compiler input fixture，不能跳到 model-backed compiler、M3/M4 或下游研究 runtime。

## Important Constraints

1. 不运行 paid LLM、full-chain、Writer、Evidence execution/promotion、SourceHunter、Numeric、Judgment、Release、OA 或 Monitoring，除非用户后续明确批准。
2. Legacy TaskRun 仍 authoritative；canonical lane 只能 `shadow`，feature flag 默认 `off`。
3. Writer 不得补源；supervisor supplement 不得伪装为 runtime evidence。
4. 不扩写 `src/sec_agent/r53_r60_runtime_task_spine.py` 建立混合状态模型；legacy 只经 adapter/binding 接入。
5. canonical command 失败必须 fail closed，禁止静默 fallback 为 legacy mutation。
6. 不把 M0 的 schema/fixture/test pass 表述为 DecisionSurface compiler、Agentic Research 或产品 runtime 完成。
7. 当前 Git tree 有大量前序 staged/dirty 文件。不得 `git reset --hard`、`git checkout --`、`git clean`、全量 `git add .` 或无范围 commit；只处理和暂存本 slice 的精确路径。
8. 本窗口保留给方向规划和审计；工程细节、测试和代码变更在新窗口完成后，以 handoff/worklog 回传本窗口审计。

## Required Read Order

1. `D:/FIN_Insight_Agent/docs/project_os/current_context_pack.zh-CN.md`
2. `D:/FIN_Insight_Agent/docs/project_os/capability_status_ledger.jsonl`
3. `D:/FIN_Insight_Agent/docs/project_os/root_cause_issue_ledger.jsonl`
4. `D:/FIN_Insight_Agent/docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md`
5. `D:/FIN_Insight_Agent/docs/architecture/agent_graph_vnext/SCHEMA_01_point01_canonical_object_registry.zh-CN.md`
6. `D:/FIN_Insight_Agent/docs/architecture/agent_graph_vnext/DB_01_point01_canonical_store_transaction_boundary.zh-CN.md`
7. `D:/FIN_Insight_Agent/docs/architecture/agent_graph_vnext/API_01_point01_runtime_command_event_contract.zh-CN.md`
8. `D:/FIN_Insight_Agent/docs/architecture/agent_graph_vnext/MIGRATION_01_point01_legacy_canonical_cutover.zh-CN.md`
9. `D:/FIN_Insight_Agent/docs/architecture/agent_graph_vnext/ADR_01_point01_m0_canonical_control_kernel.zh-CN.md`
10. `D:/FIN_Insight_Agent/docs/worklog/product_strategy/133_p38_point01_m0_canonical_runtime_foundation.md`

然后读取 `src/sec_agent/canonical_runtime/` 和 `tests/contract/test_point01_*.py`，以当前代码而不是聊天记忆为准。

## M0 Implemented Facts

已实现：

- 15 个 frozen canonical Pydantic models + Command/Result envelopes；
- deterministic JSON Schema export；
- `CanonicalStore` / `CanonicalObjectStore` protocols；
- SQLite WAL、显式事务、append-only versions/events、outbox、idempotency、CAS；
- portable content-addressed object store；
- default-off shadow feature flag 和 kill switch；
- `RuntimeFacade.create_research_case`，可在创建 Case 时附带 legacy binding；
- `RuntimeFacade.create_work_unit`；
- `RuntimeFacade.start_attempt`；
- `RuntimeFacade.commit_decision_surface_bundle`，用于原子提交由 fixture 预先构造的 shadow bundle；
- `list_events` 和基础 deterministic `replay_projection`；
- object-store failure、stale write、illegal transition、idempotency、append-only、rollback fixtures。

验证命令与结果：

```powershell
python -m pytest -q -m fast_contract tests/contract tests/test_runtime_bridge_contracts.py tests/test_r53_r60_runtime_task_spine.py
# 31 passed
```

首次测试曾发现同事务批量预构造 events 会获得重复 sequence；已修复为逐 event 分配 sequence 并立即 append。不要删除 `(task_run_id, sequence_no)` 唯一约束。

## M1A Exact Scope

先对 `API_01` 与当前 `RuntimeFacade` 做 machine-readable gap audit，再实现以下 compiler 前置能力：

1. `bind_legacy_task_run`
   - 给既有 Case 建立幂等 binding；
   - 同一 normalized legacy identity 只能有一个 active binding；
   - conflicting Case 必须返回 typed `legacy_binding_conflict`。
2. `complete_attempt`
   - 允许非 bundle-producing attempt 正常完成；
   - output artifact refs 必须已存在并通过 digest/producer binding。
3. `fail_attempt`
   - 保存 typed failure、retryability、terminal reason；
   - 不允许把失败 Attempt 留在 running。
4. `cancel_work_unit`
   - 仅从允许状态取消；
   - append cancellation events，不删除 Attempt/history。
5. `get_case_execution_view`
   - 分开显示 execution state、input currency、output usability、planning authority 和 artifact status。
6. `get_work_unit_execution_view`
   - 返回 exact WorkUnit version/state、attempt history、input refs、terminal reason。
7. `get_artifact_version`
   - 返回 immutable envelope；可选读取 payload并校验 digest；不得暴露绝对本机路径。
8. `replay_projection` v1
   - 从 events/artifacts 重建 Case/WorkUnit/Attempt projection；
   - 不调用模型、web、API、tool 或外部写操作；
   - unknown state-mutating event schema fail closed。

同时补齐 API_01 error taxonomy 到 typed application errors / ResultEnvelope projection，但不要为了“所有错误都返回 succeeded envelope”吞掉异常。

## M1A Non-Goals

本 slice 不实现：

- `compare_with_legacy_plan`、shadow reviewer workflow；
- `request/execute/rollback_planning_lane_cutover`；
- model-backed DecisionSurface compilation；
- EvidenceSlot 执行、取证、promotion；
- Workbench UI；
- PostgreSQL runtime deployment。

这些分别属于 M2/M3/M4 或后续 TECH owner。

## M1A Acceptance Gates

至少新增 deterministic tests：

- standalone binding idempotent / same-key-different-payload conflict / cross-Case identity conflict；
- complete/fail/cancel legal and illegal state transitions；
- terminal Attempt 不可再次完成；
- cancellation/failure 仍保留 append-only event/outbox/history；
- artifact digest mismatch fail closed；
- execution views 不把 shadow 写成 canonical authority；
- event replay projection parity；
- replay external-call count = 0；
- kill switch 下所有新 mutation 被拒绝，read/replay 仍可用；
- legacy runtime bridge 与 spine regression 继续通过。

达到 gate 后更新 Point 01、Project OS capability ledger 和新 worklog，但状态只能是 `M1A execution lifecycle fixture proven`。

## M1B / M2 Follow-up

M1A closeout 后，再设计并实现：

```text
DecisionSurfacePlanningService.validate_decision_surface_bundle
DecisionSurfacePlanningService.get_decision_surface
CompilerInputContract
PackSelectionDecision
CompilerObservation / CompileTimeGap
deterministic compiler fixture
model adapter interface (DeepSeek-first, GPT-ready)
shadow-only model/node run after deterministic gate and explicit approval
```

当前 `commit_decision_surface_bundle` 只证明系统能保存 fixture bundle，不证明 compiler 会理解用户问题、选择 pack 或生成合格 cells。

## Files And Artifacts

核心实现：

- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/models.py`
- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/protocols.py`
- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/store.py`
- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/object_store.py`
- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/feature_flags.py`
- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/facade.py`
- `D:/FIN_Insight_Agent/src/sec_agent/canonical_runtime/schema_export.py`

机器合同与验证：

- `D:/FIN_Insight_Agent/configs/engineering_handoff/point01_generated_json_schemas_v1_0.json`
- `D:/FIN_Insight_Agent/configs/engineering_handoff/point01_m0_test_manifest_v1_0.json`
- `D:/FIN_Insight_Agent/configs/engineering_handoff/point01_m0_implementation_admission_v1_0.json`
- `D:/FIN_Insight_Agent/configs/engineering_handoff/point01_m0_rollback_drill_result_v1_0.json`
- `D:/FIN_Insight_Agent/configs/runtime/point01_feature_flags_v1_0.json`

## Git State

- Branch：`codex/layered-data-source-expansion`。
- M0 相关文件已按精确路径 staged。
- 没有为 M0 创建 commit，因为 index 中已有大量前序 staged 工作，不能混合提交。
- 新窗口开始时先运行 `git status --short --branch`、`git diff --name-only`、`git diff --cached --name-only`，并保护所有既有用户改动。

## Completion Reporting

新窗口完成 M1A 后必须汇报：

- 实现了哪些 API，哪些仍未实现；
- exact files；
- exact tests/commands/results；
- event/state/authority 边界；
- 是否发现并修复 root cause；
- Git staged/commit 状态；
- 下一步 M1B/M2 的准入条件。

不得只报告“接口补齐”或“测试通过”。
