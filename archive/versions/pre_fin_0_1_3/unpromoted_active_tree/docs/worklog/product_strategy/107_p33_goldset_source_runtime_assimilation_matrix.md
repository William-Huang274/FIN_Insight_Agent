# 107 P33 Gold-set Source Runtime Assimilation Matrix

日期：2026-07-07

## 背景

用户追问：当前 15 个 gold-set packs 做完后，现有数据源、已注册数据、爬虫和解析能力是否已经足够。

上一轮 `p33_multicase_goldset_no_paid_audit_v0_1` 只证明 artifact-depth / fresh-specialist / negative-fixture no-paid scope 通过，不证明 live source route / parser / runtime row 已经真实接上。因此本轮先建立 source-runtime assimilation matrix，避免把 gold exemplar 或 human source ledger artifact 误当成真实数据接入完成。

## 完成内容

新增：

- `src/sec_agent/humanmade_gold_set_runtime.py`
  - 新增 `GOLDSET_SOURCE_RUNTIME_ASSIMILATION_MATRIX_SCHEMA_VERSION`
  - 新增 `build_goldset_source_runtime_assimilation_matrix()`
  - 新增 source-runtime row / case summary / metrics 分类 helper
- `scripts/eval_multi_agent/run_p33_goldset_source_runtime_assimilation_matrix.py`
- `tests/test_p33_goldset_source_runtime_assimilation_matrix.py`

生成：

- `docs/project_os/p33_goldset_source_runtime_assimilation_matrix_v0_1.json`
- `docs/internal/vnext_20260610/p33_goldset_source_runtime_assimilation_matrix_v0_1.zh-CN.md`

更新：

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/p33_execution_plan_ledger.jsonl`
- `docs/worklog/README.md`
- `docs/worklog/00_internal_master_checklist.md`

## 结果

矩阵完整性通过，但 live source/runtime 仍未通过：

```text
status = partial_artifact_scope_pass_live_runtime_pending
matrix_integrity_status = pass
case_count = 15
row_count = 68
live_runtime_ready_row_count = 0
source_route_unverified_runtime_artifact_row_count = 20
artifact_only_live_runtime_pending_row_count = 42
failure_fixture_row_count = 6
live_runtime_pending_case_count = 9
registered_source_role_count = 43
```

解释：

- `20` 条 AI/Semis deep case rows 是 gold-depth runtime artifact rows，但仍需要 live source route / crawler-parser lineage 验证。
- `42` 条 rubric rows 是 answer-exemplar-backed required slots，不是 live retrieval/parser rows。
- `6` 条 negative rows 是 deterministic failure fixtures，不是 evidence rows。
- `live_runtime_ready_row_count=0` 是当前诚实结论，说明不能宣称数据源和解析能力已经够。

## 验证

已运行：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_goldset_source_runtime_assimilation_matrix.py
python scripts/eval_multi_agent/run_p33_goldset_source_runtime_assimilation_matrix.py --strict
python -m pytest tests/test_p33_goldset_source_runtime_assimilation_matrix.py -q
python -m pytest tests/test_p33_goldset_source_runtime_assimilation_matrix.py tests/test_p33_multicase_goldset_no_paid_audit.py -q
git diff --check
```

结果：

- py_compile pass
- runner strict pass
- focused pytest `5 passed`
- combined pytest `10 passed`
- `git diff --check` pass，仅有既有 line-ending warnings

## 未运行

本轮未运行：

- paid LLM
- paid specialist
- paid Memo Writer
- full-chain
- 模型对比
- 新 live retrieval
- 新 crawler / parser

## 下一步

进入 `P33-3_live_source_route_parser_backfill_from_goldset_matrix`：

1. AI/Semis deep case：把 20 条 human-ledger runtime artifacts 逐条绑定真实 source route / fetch-crawl / parser / runtime row lineage。
2. Rubric cases：按 vertical source role 补 live route/parser；没有公开源时写 attempt-backed typed gap。
3. Negative cases：只接 aggregate / writer / verifier / Workbench failure gates，不进 evidence bundle。
4. 每完成一批 rows，重新生成 source-runtime matrix，并只在 live row / typed gap 可追踪后进入 specialist runtime replay。
