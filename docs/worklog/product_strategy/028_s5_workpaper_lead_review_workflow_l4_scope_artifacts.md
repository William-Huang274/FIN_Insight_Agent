# 028 S5 Workpaper / Lead Review Workflow L4 Scope Artifacts

## Prompt

继续推进 R53-R60 release slices，在 S4 Context / Graph / Skill Registry 已经达到 `L4_scope_pass` 后，落地 S5 Workpaper / Lead Review Workflow。

## Decision

S5 的职责是把 S3 selected evidence 和 S4 context / consumed pack refs 组织成 B 端可审阅、可追责、可复盘的 Workpaper workflow。它不是最终 Memo，也不是 UI 或 Deliverable Studio。S5 必须证明 Research Lead 常驻监督、specialist 通过 append-only WorkpaperEvent 提交贡献、LeadReview 能把未满足目标转成 targeted repair 或 visible typed gap。

本轮按以下边界实现：

- `ResearchObjectiveContract` 先定义 core question、required dimensions、minimum evidence 和 source boundaries；
- `DimensionEvidencePortfolio` 在 S5 范围内落 SQL，要求每个 required dimension 有 ClaimCard 或 visible gap；
- specialist workstreams 必须写入 append-only `WorkpaperEvent`；
- Workpaper sections 按研究问题组织，不允许 claim-card dump；
- ClaimCards 必须带 evidence refs、authority boundary 和 source boundary；
- retrievable / bounded / commercial gaps 必须可见，retrievable gap 必须生成 targeted repair request；
- LeadReviewCheckpoint 生成 writing guidance；
- JudgmentState 成为 writer 后续可消费的边界对象；
- HumanReviewQueue 将 senior analyst review 作为正式 actor。

## Work Completed

新增：

- `src/sec_agent/r53_r60_workpaper_lead_review_workflow.py`
- `scripts/engineering/build_r53_r60_s5_workpaper_lead_review_workflow.py`
- `tests/test_r53_r60_workpaper_lead_review_workflow.py`
- `configs/r53_r60/s5_workpaper_lead_review_workflow_schema_v0_1.json`
- `data/manifests/r53_r60_s5_workpaper_lead_review_workflow_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s5_workpaper_lead_review_workflow_l4_scope_pass.zh-CN.md`

更新：

- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

真实构建结果：

- ResearchObjectiveContract：`1`
- DimensionEvidencePortfolio rows：`6`
- Specialist workstreams：`3`
- Workpaper sections：`6`
- ClaimCards：`6`
- GapItems：`3`
- TargetedRepairRequest：`1`
- LeadReviewCheckpoint：`1`，状态 `review_ready_with_visible_gaps`
- JudgmentState：`1`，状态 `ready_for_writer`
- HumanReviewQueue：`1`
- S5 gates：`12 pass / 0 fail`
- Release decision：`S5_L4_scope_pass`
- Next slice：`S6`

## Verification

已运行：

- `python -m py_compile src\sec_agent\r53_r60_workpaper_lead_review_workflow.py scripts\engineering\build_r53_r60_s5_workpaper_lead_review_workflow.py`
- `python -m pytest tests\test_r53_r60_workpaper_lead_review_workflow.py -q`
- `python scripts\engineering\build_r53_r60_s5_workpaper_lead_review_workflow.py --root .`

后续 closeout 前还需与 S0-S5 regression、`git diff --check`、secret scan 一起跑。

## Notes

本轮修复一个实现问题：

- 初版 `insert_specialist_workstreams` 在打开 SQLite 连接后又调用 `append_workpaper_event`，导致嵌套写连接触发 `database is locked`。已改成先 append WorkpaperEvent 并收集 event ids，再单独写入 specialist_workstreams 表。

S5 边界：本轮不调用 LLM、不生成 Memo、不做 Workbench UI、不生成 Markdown/Word/PPT/Excel deliverables、不跑 full-chain answer quality eval。S6 负责 Workbench frontdoor / drilldown，S7 负责 Deliverable Studio / Dashboard Projection。
