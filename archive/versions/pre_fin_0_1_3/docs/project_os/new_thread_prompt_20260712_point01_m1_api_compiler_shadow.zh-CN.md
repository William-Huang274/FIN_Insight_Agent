# 新窗口启动 Prompt（已 superseded）

> 状态：`rebaselined_20260712`。旧 M1A/M1B 指令已 supersede。当前执行入口是 `POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md` 第 26 节：先补 M1.3 retry/multi-attempt，再按 M2.3-M2.10 推进。

你正在继续 `D:\FIN_Insight_Agent` 的 P38 Point 01 工程实现。本窗口只负责工程执行；原窗口保留用于产品方向规划、架构讨论和审计。

开始前先完整读取：

1. `D:\FIN_Insight_Agent\docs\project_os\thread_handoff_20260712_point01_m1_api_compiler_shadow.zh-CN.md`
2. `D:\FIN_Insight_Agent\docs\project_os\current_context_pack.zh-CN.md`
3. `D:\FIN_Insight_Agent\docs\project_os\capability_status_ledger.jsonl`
4. `D:\FIN_Insight_Agent\docs\project_os\root_cause_issue_ledger.jsonl`
5. handoff 文档列出的 Point 01、SCHEMA_01、DB_01、API_01、MIGRATION_01、ADR 和 worklog 133。

当前事实：

- M1.1/M1.2 与 M2.1/M2.2 已达到 fixture proof；最新 focused/adjacent tests 为 `39 passed`，但 M1/M2 milestone 均未完成。
- 已实现 15-object Pydantic/JSON Schema、SQLite WAL repository、portable object store、minimal RuntimeFacade、default-off shadow flag、replay 和 rollback fixture。
- Legacy TaskRun 仍 authoritative；DecisionSurface 仅 shadow；当前 bundle 是 fixture 直接构造，不是模型 compiler 输出。
- 当前分支 `codex/layered-data-source-expansion` 有大量前序 staged/dirty 文件。不得 reset/clean/revert 用户改动，不得 `git add .` 或做混合 commit。

当前任务只能是 **M1.3 retry/multi-attempt execution semantics**。必须先修复 `retryable=true` 仍将 WorkUnit 置为 terminal failed、无法启动 Attempt N+1 的缺口；不得直接进入 M3、model-backed compiler 或 shadow node run。

当前 M1.3 任务为：

1. 冻结 retry state transition、Attempt N+1 identity/attempt_no、max attempts、retry budget 和 terminal/nonterminal policy。
2. 实现同一 WorkUnit 在 retryable failure 后创建新 Attempt，保持旧 Attempt immutable；permanent/poison/max-attempt failure 必须 terminal/dead-letter typed。
3. 补 transient/permanent/poison、duplicate retry、stale state、budget exhausted、kill-switch 和 replay fixtures。
4. 运行 Point01 contract tests，以及 `tests/test_runtime_bridge_contracts.py`、`tests/test_r53_r60_runtime_task_spine.py` 相邻回归。
5. 更新 Point 01 M1.3 状态和 Project OS；只有 M1.5 closeout gate 可宣布 M1 complete。

本 slice 不实现 M2.3-M2.10、comparison/reviewer/cutover、model compiler、Evidence/Numeric/Judgment/Writer、Workbench UI、paid LLM 或 full-chain。

遵循 root-cause-first：测试发现问题时修最早错误来源，不放宽唯一约束或增加弱 fallback 让测试变绿。使用 `apply_patch` 编辑；只暂存本 slice 精确路径。

完成后返回：M1.3 实现清单、未实现清单、测试结果、retry/terminal/rollback 边界、Git 状态，以及 M1.5 closeout 和 M2.3 准入前还缺什么。
