# P38 VT1 P02.5 Execution Controls And Activity

日期：2026-07-18

## 1. 目标与范围

本增量把 P02.1-P02.4 已存在的 Case 和 accepted DecisionSurface 接到第一个真实消费者 WorkUnit，但保持为无执行副作用的内部 fixture 纵向：

- accepted plan 才能创建 WorkUnit；
- 每个 Case 只允许一个 VT1 WorkUnit；
- 状态只覆盖 `none -> pending -> cancelled`；
- cancel 只允许作用于 pending WorkUnit；
- Activity 必须从持久化事件恢复，而不是依赖浏览器内存；
- 不创建 Attempt 或 Artifact，不调用 scheduler/worker/model/tool/provider/network。

P02.5 的 resume、retry 和 SSE，以及 P02.6 的 10-20 cell、SaaS/Bank calibration，不属于本列车增量。

## 2. 产品能力增量

分析师现在可以在浏览器完成以下连续动作：

1. 创建并打开 Case；
2. 编译固定 P36 三-cell、六 EvidenceSlot 的 DecisionSurface；
3. 接受当前版本；
4. 从 Case Overview 打开 Activity；
5. 创建一个 `p36_evidence_fixture_entry` WorkUnit；
6. 查看 queued/pending 状态和 canonical Activity event；
7. 取消 pending WorkUnit；
8. 查看 `analyst_cancelled_fixture_work_unit` typed stop；
9. 刷新页面后从 API/SQLite 恢复相同 WorkUnit 与事件序列。

这是真实 browser -> typed client -> API -> ExecutionService -> RuntimeFacade -> SQLite/ObjectStore 纵向，不是静态 UI 或纯合同 skeleton。

## 3. 实现合同

Backend：

- `GET/POST /api/v1/cases/{case_id}/work-units`
- `POST /api/v1/cases/{case_id}/work-units/{work_unit_id}/cancel`
- `GET /api/v1/cases/{case_id}/activity`
- WorkUnit ID 由 tenant/project/case/accepted contract 确定性生成；
- start command 绑定 latest accepted planning checkpoint 和 `canonical_digest((contract_version_id,))`；
- `max_attempts=1`、`retry_budget=0`、`retry_policy_ref=retry:none`；
- fixture cancel 使用固定无租约 fencing token `fixture-no-lease`；
- Activity 仅返回当前 Case 的 WorkUnit events，并把 cancel event 投影为 typed stop。

Frontend：

- 新增 `/cases/:caseId/activity`；
- accepted plan 且 WorkUnit 数为 0 时才显示 Start；
- 仅 pending WorkUnit 显示 Cancel；
- 浏览器按 canonical JSON `[contract_version_id]` 计算 SHA-256；
- loading、empty、offline、permission、conflict、stale 与 error 状态均有明确投影；
- 页面刷新通过 REST 恢复，不引入 localStorage 或 SSE。

## 4. 变更文件

Backend：

- `apps/workbench/backend/application/execution_service.py`
- `apps/workbench/backend/api/v1/execution.py`
- `apps/workbench/backend/app.py`

Frontend：

- `apps/workbench/frontend/vite/src/api/execution.ts`
- `apps/workbench/frontend/vite/src/features/activity-trace/ActivityTrace.tsx`
- `apps/workbench/frontend/vite/src/app/AppShell.tsx`
- `apps/workbench/frontend/vite/src/features/case-overview/CaseOverview.tsx`
- `apps/workbench/frontend/vite/src/app/p02-shell.css`

Tests：

- `tests/contract/test_point02_execution_fixture_api.py`
- `tests/contract/test_point02_frontend_execution_contract.py`

## 5. 父线程独立验证

- Point 02 全量合同测试加选定 Point 01 回归：`45 passed in 20.30s`；
- Python compileall：通过；
- TypeScript `tsc --noEmit`：通过；
- Vite production build：通过，`1681 modules transformed`；
- desktop `1440` 和 mobile `390`：无横向溢出、遮挡或布局跳动；
- browser vertical：accepted plan -> start -> pending -> cancel -> typed stop -> reload restore 通过；
- SQLite integrity 和 outbox recovery：通过。

浏览器验证 Case：`case_80e72a9c276a5f29fc0d1c75`。

持久化计数：

- WorkUnit versions：`2`；
- latest WorkUnits：`1`；
- WorkUnit events：`WORK_UNIT_CREATED`、`WORK_UNIT_CANCELLED`；
- Attempt：`0`；
- Artifact：`0`；
- external calls：`0`。

父线程曾修正两个 Playwright locator（`Demand reality` 与 `Return to overview`），它们是测试脚本定位错误，不是产品缺陷，因此本增量产品 repair 次数为 `0`。

## 6. 成熟度与边界

Disposition：`P02_5_CURRENT_TRAIN_FULL_APPROVED_POINT02_FORMAL_CLOSEOUT_DEFERRED_TO_VT2`。

- P02.1-P02.5：VT1 current-train full；
- P02.5 resume/retry/SSE：deferred to VT2；
- P02.6 calibrated owner closeout：deferred to VT2；
- Point 02：VT1 阶段完成，不宣称正式 Point closeout；
- runtime admission：`not_granted`；
- operational qualification：`not_qualified_deferred_to_REL_PROD_001_RG1`；
- production readiness：`not_admitted`；
- legacy global authority：`retained`。

## 7. 下一产品步骤

按纵向版本列车进入 P03.0/P03.1：冻结最小 Evidence contract subset，并实现 deterministic nonexecuting planner。P03 必须消费已有 Case、DecisionSurface cell、EvidenceSlot 和 WorkUnit identity，形成第一条 EvidenceRequest 计划；不得先在 Point 03 内部铺完整 owner-local 能力，也不得提前拉回 P02.6 calibration。
