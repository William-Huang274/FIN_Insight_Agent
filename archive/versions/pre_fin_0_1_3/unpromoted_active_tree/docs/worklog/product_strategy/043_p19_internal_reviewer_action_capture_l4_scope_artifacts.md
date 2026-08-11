# P19 Internal Reviewer Action Capture L4 Scope Artifacts

## Prompt / Problem

继续推进 R53-R60 下一阶段：P18 已把 P17 controlled pilot execution 转成内部 reviewer dogfood window，但仍是只读 dashboard / assignment / projected action 状态。需要把 reviewer 的真实操作入口、feedback capture、defect triage 和 P16 regression lifecycle 打通，且不能把 deterministic drill 伪装成真实多日人工 dogfood。

## Reasoning And Decision

P19 不做“真实用户已经采用”的结论，而是把 action-capture 自身做成 L4-scope / enterprise-grade：

- reviewer action 必须 append-only；
- Workbench POST action 必须写入 SQL-final row；
- repair action 必须实际写入 P16 `failure_events_p16` / `regression_case_records_p16`；
- approve action 只能进入 gold candidate，必须二次 review，不能直接成为 final gold；
- dashboard 只是 projection，不能作为最终审计源；
- `real_multi_day_human_adoption_status` 和 `full_product_release_status` 必须保留边界。

## Work Completed

- 新增 `src/sec_agent/r53_r60_internal_reviewer_action_capture.py`：
  - `LiveReviewerActionWindow`
  - `LiveReviewerAction`
  - `LiveReviewerFeedbackRecord`
  - `LiveDefectTriageRecord`
  - `LiveRegressionPromotion`
  - `LiveGoldCandidatePromotion`
  - `LivePilotCaseStatus`
  - `LiveReviewerWorkbenchApiContract`
  - `LiveReviewerActionReport`
  - `LiveReviewerGateResult`
- 新增 builder：`scripts/engineering/build_r53_r60_p19_internal_reviewer_action_capture.py`。
- Workbench backend 新增：
  - `GET /api/r53-r60/pilot/actions`
  - `GET /api/r53-r60/pilot/cases/{case_id}/actions`
  - `POST /api/r53-r60/pilot/cases/{case_id}/review-actions`
- Workbench frontend Pilot dogfood window 新增：
  - pilot case selector；
  - reviewer comment；
  - comment / request repair / approve action；
  - P19 live action、case status、regression promotion projection。
- 新增 deterministic/API tests：`tests/test_r53_r60_internal_reviewer_action_capture.py`。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`，加入 P19 closeout。

## Result And Evidence

真实 builder：

```text
python scripts\engineering\build_r53_r60_p19_internal_reviewer_action_capture.py --root .
```

结果：

- release decision：`P19_L4_scope_pass_internal_reviewer_action_capture_ready`
- closeout level：`L4_scope_pass`
- dependency：P16 / P18 `2/2 pass`
- live reviewer actions：`6`
- feedback records：`6`
- defect triage records：`6`
- P16 live failure rows：`3`
- P16 live regression rows：`3`
- gold candidate rows：`2`
- case status rows：`6`
- API contracts：`3`
- gates：`11 pass / 0 fail`

验证：

```text
python -m py_compile src\sec_agent\r53_r60_internal_reviewer_action_capture.py scripts\engineering\build_r53_r60_p19_internal_reviewer_action_capture.py apps\workbench\backend\app.py
python -m pytest tests\test_r53_r60_internal_reviewer_action_capture.py -q
```

结果：P19 tests `5 passed`。

## Follow-up / Boundary

- P19 证明 action-capture 和 P16 regression promotion path 可用，但不证明真实多人多日 dogfood。
- `approve` 只进入 `candidate_pending_second_review`，不能直接成为 final gold。
- 下一步 P20 应该开始真实 reviewer 多轮 dogfood 会话、accepted/rejected feedback、defect close verification、token/cost ROI，以及 P18/P19 前端浏览器视觉 E2E。
