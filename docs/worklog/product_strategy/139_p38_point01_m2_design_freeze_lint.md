# P38 Point 01 M2.0 Compiler/Pack Child Design Freeze

日期：2026-07-12

状态：`initial_design_freeze_snapshot / superseded_by_140_role_separated_review / m2_open`

## 目标与决策

在 M1.5 reviewer-approved closeout 后，按 Point 01 第 26.3 节先冻结 M2.1-M2.10 的 child contracts，而不是把现有预填 cell fixture 误当完整 compiler。设计 lint 是 M2.0 的 fixture gate；跨 owner review 仍是 calibration 待办。

## 完成

- 新增 `configs/engineering_handoff/point01_m2_design_freeze_manifest_v1_0.json`：为 M2.1-M2.10 固化唯一 owner、owned object、input/output contracts、dependency 和 acceptance boundary。
- 新增 `scripts/engineering/run_point01_m2_design_lint.py`：fail-close 检查 child 点完整性、owner/object 冲突、未知/自引用/环依赖、M2.10 聚合覆盖、authority boundary 和 M2.8 model admission。
- 新增 `tests/contract/test_point01_m2_design_freeze.py`：覆盖正常设计、object 多 owner + dependency cycle + 错误 model admission 的拒绝路径，以及 CLI machine-readable output。
- 发现并修复 lint 自身把 M2.1 空 dependency list 误判为缺字段的问题；dependencies 可以为空，但字段仍被要求存在。

## 验证

```text
python scripts/engineering/run_point01_m2_design_lint.py
status=pass; child_contract_count=10; owner_count=10; dependency_edge_count=29

python -m pytest -q -m fast_contract tests/contract/test_point01_m2_design_freeze.py
3 passed

python -m compileall -q scripts/engineering/run_point01_m2_design_lint.py tests/contract/test_point01_m2_design_freeze.py
pass
```

## 边界与下一步

本 slice 不实现 M2.1-M2.10 任一 child，不调用模型、Web 或 paid/full-chain，不更改 legacy TaskRun authority。M2.8 保持 denied-path only；M3/M4 仍禁止。下一步按设计依赖进入 M2.1，补齐 10–20 cell policy、DAG/owner/slot/stop/source/forbidden validators 的 full implementation；cross-owner design review 仍需在 M2.0 calibration 前单独完成。

> 后续状态：该初始 freeze 的跨职责审阅已由 `140_p38_point01_m2_cross_owner_design_review.md` 完成并修复五项设计缺口；其结果待用户确认，不再保持本文件写入时的 `pending` 状态。
