# 153 P38 Point 01 M4 Case-Scoped Planning Cutover

日期：2026-07-12

状态：`M4.0-M4.7 deterministic implementation pass; M4.0 human design review accepted; M4.8 rejected_pending_repair`

## 决策

M3 已在 deterministic shadow comparison/calibration 范围完成，但其批准不等于真实 authority switch。M4 只实现一个可审计的 Case-scoped planning pilot：legacy TaskRun 仍是执行与历史 authority；只有已批准 Case 的 DecisionSurface planning read head 可临时成为 `canonical_for_lane`，并且 legacy consumer 只读取 compatibility projection。

## 完成内容

- M4.0：新增 M4 design manifest、五职责结构化审阅与 lint；当前线程 human reviewer 已明确通过设计审阅。该确认不等于真实 Case authority switch。
- M4.1：`CutoverScope` / `LaneEligibilityPolicy` 只允许 `scope_kind=case`，consumer inventory 或 legacy projection 不完备时拒绝。
- M4.2：`LaneCutoverRequest` / `CutoverApprovalReceipt` 将 schema、policy、artifact、comparison 四个 digest 与 expiry 绑定；缺失、过期或 hash mismatch 均拒绝。
- M4.3：实现 canonical planning read 和 `LegacyRequiredItemProjection`；projection 为 read-only，且每个 mapping 带 information-loss tags。`RuntimeFacade` 的 Case/WorkUnit/recovery read view 也只从 `CaseControlSummaryVersion` 解析 authority，fixture cutover/rollback 两侧均有回归断言。
- M4.4：`PlanningLaneCutoverService` 在同一 transaction 写入 requested/executed `LaneCutoverDecision`、新的 `CaseControlSummaryVersion`、ResearchCase lane status、authority event 和 outbox；无 dual authoritative write。
- M4.5：实现只读 Workbench projection，明确显示 legacy/canonical authority、contract/cell/slot/gap/version 和 cutover decision。
- M4.6：rollback 创建新 decision/control version，不删除历史；kill switch 下普通 mutation 仍拒绝，只有带 reason 的 rollback-control transaction 可把 planning authority 恢复为 legacy。
- M4.7：临时 store 验证 tenant isolation、recovery/outbox，且引用 M1 PostgreSQL conformance artifact；这不是生产 PostgreSQL load/failover 证明。
- M4.8：真实 persistent Case mutation 当前被 human reviewer 标为 `rejected_pending_repair`。后续 154 已修复 exact entity binding、execute-time expiry/revocation recheck、approved-version read lock 与 receipt alignment，并创建 synthetic read-only preflight；这些不执行真实 cutover，也不关闭 M4.8。

## 验证

- `python scripts/engineering/run_point01_m4_design_lint.py`：pass。
- `python scripts/engineering/run_point01_m4_cutover_fixtures.py`：M4.1-M4.7 全部 pass。
- `python scripts/engineering/run_point01_m4_closeout_gate.py`：预期 `fail_closed / M4_closeout_pending`，仅未满足 human pilot approval 与 real-case execution evidence。
- `python -m pytest -q tests/contract/test_point01_m4_planning_cutover.py tests/contract/test_point01_m4_design_freeze.py tests/contract/test_point01_m4_cutover_fixture_runner.py tests/contract/test_point01_m4_closeout_gate.py`：通过。

## 未做与安全边界

- 没有对任何真实 Case、sector、tenant 或 global scope 执行 cutover。
- 没有变更 legacy TaskRun authority，兼容 projection 不可写。
- 没有启用 Evidence/Writer、provider/model、full-chain 或 M5+ runtime。
- M4.8 仅在 reviewer 明确指定真实 `case_id`、`lane_id` 并签发 `approve_case_scoped_planning_cutover_only` 后才可关闭；该批准仍不授权 sector/global rollout。
