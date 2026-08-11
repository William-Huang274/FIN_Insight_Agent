# R53-R60 P27 B04 Reviewer Acceptance Package

## 状态

- package_status: `ready_for_real_reviewer_execution`
- b04_status_after_p27: `open_product_acceptance_required`
- real_reviewer_evidence_row_count: `0`
- reviewer_session_count: `0`
- ready_reviewer_session_count: `0`
- pending human requirements: `5`
- pending defect closeouts: `8`

P27 只生成真实人工验收的执行包，不写入真实 reviewer evidence ledger，也不关闭 B04。

## Reviewer 执行顺序

### p27_step_reviewer_session

- evidence_type: `reviewer_session`
- action: Open Workbench, select an R53-R60 task/case, review task context and record a completed reviewer session.
- required_fields: `session_id, reviewer_role, started_at, ended_at, task_id, case_id`

### p27_step_deliverable_acceptance

- evidence_type: `deliverable_acceptance`
- action: Open rendered deliverables, accept or reject with artifact reference and reviewer comment.
- required_fields: `decision_status, deliverable_ref, review_comment, artifact_ref_id`

### p27_step_defect_closeout

- evidence_type: `defect_closeout`
- action: Close each pending defect source by repair, regression coverage, or typed-gap acceptance.
- required_fields: `defect_id, closeout_status, repair_ref_or_regression_ref`

### p27_step_visual_acceptance

- evidence_type: `visual_acceptance`
- action: Inspect desktop/mobile Workbench screenshots or live UI and record readability/usability decision.
- required_fields: `browser_screenshot_refs, reviewer_decision, visual_defect_rows`

### p27_step_audit_replay

- evidence_type: `audit_replay`
- action: Trace the final deliverable back through task, Workpaper, artifact refs and trace spans.
- required_fields: `task_id, artifact_ref_ids, trace_or_sql_refs, reviewer_confirmation`

## 写入入口

- Workbench: `http://127.0.0.1:18080` -> R53-R60 工作台 -> Product acceptance evidence
- API: `POST /api/r53-r60/product-acceptance/evidence`
- CLI: `python scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py --help`

## 候选引用

- task / artifact / trace candidate refs: `36`
- evidence templates: `13`

## 输出

- package: `data/manifests/r53_r60_p27_b04_reviewer_acceptance_package_v0_1.json`
- step_rows: `data/manifests/r53_r60_p27_b04_reviewer_acceptance_steps_v0_1.jsonl`
- evidence_template_rows: `data/manifests/r53_r60_p27_b04_reviewer_acceptance_evidence_templates_v0_1.jsonl`
- reviewer_candidate_rows: `data/manifests/r53_r60_p27_b04_reviewer_acceptance_candidate_refs_v0_1.jsonl`
- report: `docs/internal/vnext_20260610/r53_r60_p27_b04_reviewer_acceptance_package.zh-CN.md`

## 关闭条件

B04 只有在真实 reviewer 提交完整 evidence 后，重跑 P24/P21 并看到 `accepted_by_real_human_review` / `closed_by_real_human_product_acceptance` 才能关闭。
