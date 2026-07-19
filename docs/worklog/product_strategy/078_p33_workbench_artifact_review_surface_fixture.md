# 078 P33-1.4 Workbench Artifact Review Surface Fixture

日期：2026-07-05

## 目标

关闭 P32 deferred contract `l3_workbench_artifact_review_surface_contract_v0_1`，用 no-paid deterministic fixture 证明 Workbench 不是前端 local state 或 chat transcript，而是能从 SQL-final rows 回放 task、evidence、Claim/Judgment、typed gap、gate、artifact、deliverable/dashboard、ops trace 和 reviewer action。

## 本轮工作

- 新增 P33-1.4 fixture：
  - `src/sec_agent/p33_workbench_artifact_review_surface_fixture.py`
  - `scripts/engineering/run_p33_workbench_artifact_review_surface_fixture.py`
  - `tests/test_p33_workbench_artifact_review_surface_fixture.py`
- 生成 fixture artifact：
  - `data/manifests/p33_workbench_artifact_review_surface_fixture_v0_1.json`
  - `docs/internal/vnext_20260610/p33_workbench_artifact_review_surface_fixture_report.zh-CN.md`
- 更新 Workbench review action contract：
  - `src/sec_agent/r53_r60_workbench_frontdoor_drilldown.py`
  - `apps/workbench/backend/app.py`
- 更新 registry / source docs / ledgers：
  - `docs/project_os/p32_active_registry_promotion_ledger.jsonl`
  - `docs/project_os/p33_execution_plan_ledger.jsonl`
  - `docs/project_os/capability_status_ledger.jsonl`
  - `docs/project_os/current_context_pack.zh-CN.md`
  - `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
  - `docs/internal/vnext_20260610/r53_r60_p32_method_pattern_learning_gate.zh-CN.md`
  - `docs/worklog/00_internal_master_checklist.md`

## Root-Cause 修复

P33-1.4 的问题不是 Workbench 没有表，而是 review action contract 不够贴近企业审稿语义：

- 旧 `append_review_action` 只支持 `approve`、`request_repair`、`return_to_specialist`、`downgrade_claim`、`comment`。
- P33 contract 需要明确的 analyst reviewer 动作：`accept`、`reject`、`supersede`。
- 旧 action 也没有 `review_target_type` / `review_target_id`，很难证明一个审查动作到底针对 ClaimCard、gap 还是 JudgmentState。
- deterministic fixture 重跑时，如果直接追加同样 action，会污染 WorkpaperEvent ledger。

修复方式：

- `append_review_action` 新增 `accept`、`reject`、`supersede`。
- 新增 `review_target_type`、`review_target_id`、`idempotency_key`。
- 带 `idempotency_key` 的 review action 使用稳定 ID；重复运行 fixture 时返回已有 row，不重复追加 WorkpaperEvent。
- 后端 API request literal 同步允许 `accept`、`reject`、`supersede`。

这是上游 contract 修复，不是靠 Workbench gate 放宽过关。

## 验收结果

P33-1.4 repo fixture 通过：

- S6 Workbench 与 S7 Deliverable/Dashboard projection 均保持 L4-scope pass。
- Workbench drilldown 能追踪 task -> evidence-backed ClaimCards -> typed gaps -> gates -> artifacts。
- JudgmentState refs 被 Workbench 可见的 ClaimCards 和 typed gaps 覆盖。
- `accept`、`reject`、`supersede` 三类 reviewer action 均写入 `workbench_review_actions_s6`，并关联 append-only `workpaper_events`。
- Deliverable 和 dashboard projection refs 均来自 SQL-backed artifact refs。
- Ops trace、token/cost 字段和 rollback ref 可从 SQL-final replay 中看到。
- Frontend local state 和 chat transcript 不作为最终审计源。

Registry 最新状态：

- `active_registry_ready_count=14`
- `deferred_count=1`
- 剩余 deferred contract：`l3_research_to_quant_factor_handoff_contract_v0_1`

## 验证命令

```powershell
python -m pytest tests/test_p33_workbench_artifact_review_surface_fixture.py -q
python -m py_compile src/sec_agent/p33_workbench_artifact_review_surface_fixture.py scripts/engineering/run_p33_workbench_artifact_review_surface_fixture.py tests/test_p33_workbench_artifact_review_surface_fixture.py
python scripts/engineering/run_p33_workbench_artifact_review_surface_fixture.py
python scripts/engineering/validate_p32_registry_promotion.py --output data/manifests/p32_registry_promotion_validation_v0_1.json
python -m pytest tests/test_p32_registry_promotion_validation.py -q
```

结果：

- P33-1.4 fixture tests：`5 passed`
- P33-1.4 fixture script：`status=pass`
- P32 registry promotion validator：`status=pass`，`14/1`
- P32 promotion tests：`4 passed`

## 边界

- 本轮没有调用 paid LLM。
- 本轮没有跑 full-chain。
- 本轮只证明 Workbench artifact-review surface contract 的 runtime alignment。
- 不证明多日真实 reviewer adoption、生产 RBAC/SLA 或最终前端 UX polish；这些仍留给 P33-4 Workbench dogfood 和后续产品化阶段。

## 下一步

P33-1 剩余一个 deferred contract：

1. `P33-1.5 research_to_quant_factor_handoff`

推荐下一步做 Research-to-Quant fixture，因为 P33-2 runtime assimilation 需要知道 JudgmentCard / thesis driver / evidence refs 如何被安全转成 FactorHypothesis / FeatureSpec / BacktestPlan 候选，同时保留 point-in-time、leakage guard、human approval 和 no-trading-advice 边界。
