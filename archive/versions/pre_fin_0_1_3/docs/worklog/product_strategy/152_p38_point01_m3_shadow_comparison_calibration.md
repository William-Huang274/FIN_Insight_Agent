# 152 P38 Point 01 M3 Shadow Comparison / Calibration

日期：2026-07-12

状态：`M3_complete / deterministic_shadow_comparison_calibration_only`

## 问题与决策

M2 已完成 deterministic DecisionSurface Planning Shadow，但这不证明新 cell 规划不弱于 legacy required-item/dimension 规划。M3 必须对 FIN compiler 的 shadow output 做语义 comparison 与 calibration；不能把 legacy/shadow 数量相等、WorkBuddy 的 prompt-required 报告结构、或 P36 supervisor supplement 当作通过证据。

本轮按 Point 01 M3.0-M3.8 细粒度矩阵实现可复跑合同。保留 legacy TaskRun authority、DecisionSurface shadow-only、no model/provider/Evidence/Writer/full-chain/M4 cutover。M3.8 被设计为必须人工批准的 fail-closed gate，Codex 不会自批。

## 完成内容

- M3.0：新增 design-freeze manifest、五职责视角结构化审阅和 lint；审阅结论为已完成、等待当前线程 human confirmation。
- M3.1：`LegacyRequiredItemComparator` 以 merge/split/downgrade 对比 legacy semantic coverage，事实 lookup 只能降级为 EvidenceSlot；`count_parity` 明确只保留旧 skeleton helper 身份。
- M3.2：`CellCoverageGranularityAuditor` 对 owner、question kind、semantic duplicate、slot/source policy、WWC、counterevidence owner 与 dependency 做 materiality-weighted audit。
- M3.3：`P36FiveChainEvaluator` 对 Accelerator、Server OEM、Foundry/Packaging、HBM、Semicap 逐链输出 cell/slot/WWC/counterevidence failure attribution；不消费 supervisor supplement。
- M3.4：`MultiSectorCalibrationMatrix` 固定 AI/Semis、SaaS、Healthcare、Banks 四个 positive shadow case 的 mechanism、ontology、report-type 与 source-policy-delta 条件。
- M3.5：relationship scope promotion、parser gap/source-absent 混淆、commercial proxy substitution 三类 negative control 都 fail closed，material escape 为零。
- M3.6：`PatternCandidateAdjudicator` 区分 `prompt_required`、`independently_observed`、`reviewer_inferred`；未独立 corroborate 的 WorkBuddy candidate 不能成为 pack candidate。
- M3.7：`ShadowComparisonReviewService` materialize query -> contract -> cell -> slot trace，保留 append-only action reason、affected cells 与 supersession；fixture reviewer action 不等于 human approval。
- M3.8：新增 aggregate gate 和 human approval record。每次 gate 重跑 M3.0 lint + M3.1-M3.7 fixtures；默认批准记录 pending，因此正确返回 `fail_closed / M3_closeout_pending`。

## 验证

- `python scripts/engineering/run_point01_m3_design_lint.py`：pass。
- `python scripts/engineering/run_point01_m3_calibration_fixtures.py`：M3.1-M3.7 全部 pass。
- `python scripts/engineering/run_point01_m3_closeout_gate.py`：预期 fail-closed，仅未满足 `human_reviewer_approval_pending` 与 `m3_0_design_review_user_confirmation_pending`。
- `python -m pytest -q tests/contract/test_point01_m3_closeout_gate.py tests/contract/test_point01_m3_calibration_fixture_runner.py tests/contract/test_point01_m3_design_freeze.py tests/contract/test_point01_m3_shadow_calibration.py`：`14 passed`。

## M3.8 人工批准与关闭

当前线程 human reviewer 已明确批准 M3 design/audit package，并授权进入 M4 engineering。已更新 M3.0 design review 与 M3 approval record，随后重跑 `run_point01_m3_closeout_gate.py`：`pass / M3_complete`。

批准范围仍是 `approve_m3_shadow_calibration_only`：它关闭 M3 deterministic comparison/calibration，不直接执行任何 M4 authority switch。

## 边界与下一步

- M3 已 complete，但只在 deterministic shadow comparison/calibration 范围。
- 当前 fixtures 证明 deterministic contract、negative controls 和 reviewer read model，不证明真实 Evidence/Writer runtime、paid model comparison、full-chain 或跨行业 agent 泛化。
- 下一步是 M4 case-scoped planning cutover engineering；任何真实 Case authority switch 仍需要 M4.0/M4.8 独立审阅和 pilot receipt。
