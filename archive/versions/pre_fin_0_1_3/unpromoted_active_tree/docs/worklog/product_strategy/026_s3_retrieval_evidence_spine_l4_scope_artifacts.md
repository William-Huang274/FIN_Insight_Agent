# 026 S3 Retrieval Evidence Spine L4 Scope Artifacts

日期：2026-06-29

## 问题

S0 / S1 / S2 已经分别完成 unified backlog、runtime task spine 和 tool / sandbox / trace spine，但 R58 所要求的 DB exact、BM25/ObjectBM25、Milvus、graph、web repair、parser rows 仍需要一个运行时可审计的 retrieval / evidence 主账本。

如果 S3 不先闭环，后续 ContextEngine、Workpaper、Memo Writer 和前端 drilldown 会继续面对散装查询结果，难以复盘 target-in-candidates、rerank/selection、dropped reason、typed gap 和 source authority boundary。

## 决策

本轮不做 full recall/rerank 调参，也不重建 Milvus。S3 的范围定义为 retrieval / evidence spine：

- `RetrievalIntent`
- `RoutePolicyMatrix`
- `RetrievalPlan`
- `RetrievalRouteExecution`
- `RetrievalCandidate`
- `SelectedEvidence`
- `DroppedCandidate`
- `TypedGapLedger`
- `RetrievalEvalQrel`

S3 只允许 `exact_company_fact_authority` 和 `bounded_thesis_driver_authority` 进入 selected evidence；raw retrieval hit、planning/gap-only row、semantic hit 和 web snapshot 不能直接进入 Memo Writer。

## 完成内容

新增文件：

- `src/sec_agent/r53_r60_retrieval_evidence_spine.py`
- `scripts/engineering/build_r53_r60_s3_retrieval_evidence_spine.py`
- `tests/test_r53_r60_retrieval_evidence_spine.py`

更新文件：

- `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

生成合同 / gate artifact：

- `configs/r53_r60/s3_retrieval_evidence_spine_schema_v0_1.json`
- `data/manifests/r53_r60_s3_retrieval_evidence_spine_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s3_retrieval_evidence_spine_l4_scope_pass.zh-CN.md`

SQLite store 复用 S1/S2 主账本：

- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`

## 真实构建结果

命令：

```powershell
python scripts\engineering\build_r53_r60_s3_retrieval_evidence_spine.py --root .
```

结果：

- release decision：`S3_L4_scope_pass`
- closeout level：`L4_scope_pass`
- required routes：`sql_exact`、`graph`、`bm25`、`object_bm25`、`milvus_semantic`、`web_repair`、`parser_row`
- retrieval candidates：`49`
- selected evidence：`15`
- dropped candidates：`34`
- qrels：`2`
- typed gaps：`0`
- gate rows：`12 pass / 0 fail`
- next slice unlocked：`S4`

## 关键修复

1. 第一次真实构建时 qrels 只有 1 条。根因是 Gold Mart 文件自然顺序先填满 AMD route quota，导致 NVDA 目标 query 没有优先进入 selected evidence。修复为按目标 ticker 顺序、authority rank、support surface rank 读取 rows，避免目标公司被文件顺序挤掉。
2. 第二次真实构建时尝试删除旧 `research_tasks` 会触发 `workpaper_events_append_only_delete_forbidden`。这是正确的 S1 约束，修复为 S3 repeat build 使用 `resume_task` 新 run，只重建 S3 自身 retrieval tables，不删除 append-only WorkpaperEvent。

## 验证

已通过：

```powershell
python -m py_compile src\sec_agent\r53_r60_retrieval_evidence_spine.py scripts\engineering\build_r53_r60_s3_retrieval_evidence_spine.py
python -m pytest tests\test_r53_r60_retrieval_evidence_spine.py -q
python scripts\engineering\build_r53_r60_s3_retrieval_evidence_spine.py --root .
```

后续 closeout 前还需跑 S0-S3 targeted regression、`git diff --check` 和 secret scan。

## 边界

S3 只证明 retrieval / evidence route ledger 在自身范围达到 enterprise-grade。它不证明：

- 全量 recall/rerank 已调优完成；
- Milvus 已重建或线上服务可用；
- Memo Writer 可以直接消费 candidates；
- Workpaper 已能产出可审阅底稿。

这些后续进入 S4 / S5 / S6。
