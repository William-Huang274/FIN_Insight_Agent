# 042 P18 Internal Reviewer Dogfood Window L4 Scope Artifacts

## Prompt

继续 R53-R60 P 系列执行，在 P17 Controlled Internal Pilot Execution 之后，把 P17 的 deterministic pilot execution 记录接成内部 reviewer dogfood window、Workbench dashboard API、reviewer session、defect promotion 和 feedback-to-regression bridge。

## Decision

P18 不声明真实多人长期 dogfood 已完成。当前 slice 的企业级通过范围是：

- P17 的 6 个 pilot cases 必须全部变成 SQL-final reviewer assignments；
- reviewer session、reviewer action event、dashboard tile、defect promotion、feedback-to-regression link 必须可审计；
- Workbench 必须能读取 pilot dashboard / case list / case detail；
- defect 必须进入 P16 regression lifecycle queue，而不是被 memo boundary 隐藏；
- `real_human_adoption_status` 必须保持 `pending_actual_reviewer_actions`，`full_product_release_status` 必须保持 `not_l4_production_pass`。

## Work Completed

- 新增 runtime contract：`src/sec_agent/r53_r60_internal_reviewer_dogfood_window.py`。
- 新增 builder：`scripts/engineering/build_r53_r60_p18_internal_reviewer_dogfood_window.py`。
- 新增 schema / summary / closeout report：
  - `configs/r53_r60/p18_internal_reviewer_dogfood_window_schema_v0_1.json`
  - `data/manifests/r53_r60_p18_internal_reviewer_dogfood_window_summary_v0_1.json`
  - `docs/internal/vnext_20260610/r53_r60_p18_internal_reviewer_dogfood_window_l4_scope_pass.zh-CN.md`
- 新增 deterministic tests：`tests/test_r53_r60_internal_reviewer_dogfood_window.py`。
- Workbench 后端新增：
  - `GET /api/r53-r60/pilot/dashboard`
  - `GET /api/r53-r60/pilot/cases`
  - `GET /api/r53-r60/pilot/cases/{case_id}`
- Workbench 前端 R53-R60 工作台新增 `Pilot dogfood window` 面板，展示 window status、case assignments、reviewer sessions、defect promotions、P18 gates 和 API contracts。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md` 的 P18 closeout。

## Result

真实构建命令：

```powershell
python scripts\engineering\build_r53_r60_p18_internal_reviewer_dogfood_window.py --root .
```

构建结果：

- release decision：`P18_L4_scope_pass_internal_reviewer_dogfood_window_ready`
- closeout level：`L4_scope_pass`
- dependency：P17 `pass`
- DogfoodWindow：`1`
- DogfoodCaseAssignment：`6`
- ReviewerSessionRecord：`6`
- ReviewerActionEvent：`18`
- PilotDashboardTile：`7`
- PilotDefectPromotion：`6`
- PilotFeedbackToRegression：`6`
- PilotWorkbenchApiContract：`3`
- gate：`11 pass / 0 fail`
- total pilot cost from P17：`2.42` USD
- max case latency from P17：`210000ms`
- real human adoption：`pending_actual_reviewer_actions`
- full product release：`not_l4_production_pass`

## Verification

已运行：

```powershell
python -m py_compile src\sec_agent\r53_r60_internal_reviewer_dogfood_window.py scripts\engineering\build_r53_r60_p18_internal_reviewer_dogfood_window.py apps\workbench\backend\app.py
python -m pytest tests\test_r53_r60_internal_reviewer_dogfood_window.py -q
```

结果：

- `py_compile` passed。
- P18 deterministic tests：`5 passed`。

## Follow-up

- P19 可进入真实人工 reviewer 操作窗口：让 reviewer 真正在 Workbench 内审查 case、提交 comment / repair / approval，并把真实反馈写回 P18/P16 lifecycle。
- P18 前端仍需要浏览器视觉 E2E / screenshot gate 才能声明 polished UI。
- P18 不等于外部客户 pilot，不等于 sustained online eval window，不等于全系统 `L4_production_pass`。
