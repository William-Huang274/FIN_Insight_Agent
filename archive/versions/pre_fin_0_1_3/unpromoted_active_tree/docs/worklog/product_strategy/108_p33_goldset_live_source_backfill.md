# 108 P33 Gold-set Live Source Backfill

日期：2026-07-07

## Prompt

用户要求把 15 个 Humanmade Gold Set packs 逐个接到真实 source route / parser / specialist runtime，建立 `case -> required evidence slot -> registered source -> crawler/parser -> runtime row -> authority boundary` 矩阵。上一轮已经完成 source-runtime assimilation matrix，但只是说明哪些 rows pending。本轮目标是先用现有已物化 manifests 做 live source backfill，检查哪些 rows 已经可以安全进入 runtime evidence。

## Reasoning

这一步不能直接跑 paid full-chain。原因是当前主要 blocker 不是模型写作，而是 gold-set evidence slot 是否真的有 parser-backed runtime row。若直接跑模型，会继续把 parser/locator 缺口包装成“模型判断差”或“memo 写得差”。

本轮按照 Project OS / Global Stewardship 规则处理：

- 先定位 earliest owned artifact：`p33_goldset_source_runtime_assimilation_matrix_v0_1` 的 live rows 仍未绑定。
- 只用现有 manifests 做 deterministic backfill，不跑 paid LLM、full-chain、新爬虫或新 parser。
- 严格区分 `live_runtime_ready`、`route_candidate_only_parser_lineage_pending`、`source_route_candidate_weak_not_bound`、`case_binding_required_before_live_lookup` 和 `not_applicable_failure_fixture`。
- 初版宽松匹配曾产生 `18` 条 live-ready 候选，但复核发现 false positives，所以改为更严格绑定规则。

## Work Completed

新增 / 修改：

- `src/sec_agent/humanmade_gold_set_runtime.py`
  - 增加 `GOLDSET_LIVE_SOURCE_BACKFILL_SCHEMA_VERSION`。
  - 增加 `GOLDSET_BACKFILL_SOURCE_ROWSETS`，覆盖 gold fact/signal mart、source authority mart、official product spec/customer deployment rows、company product operating metrics、business mix、non-US local disclosure、ProductIntelligenceGraph edges。
  - 在 deep case evidence rows 和 source-runtime matrix rows 中保留 `issuer`、`product_or_family`、`source_name`、`metric_or_attribute`、`value`、`unit`、`period_or_version`。
  - 新增 `build_goldset_live_source_backfill()` 及 source index、candidate scoring、authority family、role compatibility、parser lineage 和 specificity helpers。
  - 收紧 promotion gate：必须同 issuer、role/authority 兼容、有 product/metric/source specificity，并有 parser/source lineage。
- `scripts/eval_multi_agent/run_p33_goldset_live_source_backfill.py`
  - 生成 JSON 和 Markdown report。
- `tests/test_p33_goldset_live_source_backfill.py`
  - 覆盖 row field preservation、68-row backfill、negative fixture exclusion、rubric rows 不直接绑定、AI/Semis 候选存在。
- `docs/project_os/p33_goldset_live_source_backfill_v0_1.json`
- `docs/internal/vnext_20260610/p33_goldset_live_source_backfill_v0_1.zh-CN.md`
- 更新：
  - `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
  - `docs/project_os/capability_status_ledger.jsonl`
  - `docs/project_os/root_cause_issue_ledger.jsonl`
  - `docs/project_os/p33_execution_plan_ledger.jsonl`
  - `docs/worklog/README.md`
  - `docs/worklog/00_internal_master_checklist.md`

## Result

最终接受的严格结果：

```text
status = partial_live_backfill_pass_remaining_route_parser_work
case_count = 15
row_count = 68
live_runtime_ready_row_count = 4
route_candidate_only_parser_lineage_pending_count = 1
source_route_candidate_weak_not_bound_count = 13
case_binding_required_count = 44
failure_fixture_count = 6
remaining_action_required_row_count = 58
indexed_row_count = 154484
indexed_ticker_count = 603
```

可以安全进入 live runtime 的 `4` 条：

- `nvda_gb200_nvl72_rack_architecture`
- `amzn_aws_demand_pool_context`
- `tsmc_advanced_node_hpc_ai_readthrough`
- `amat_semiconductor_systems_mix`

不能晋升的主要情况：

- `dell_ai_server_orders_shipments_backlog` 只有 semantically compatible candidate，但 parser/source lineage 不足。
- DELL AI server margin / PowerEdge config、NVDA Data Center、AMD MI300X / MLPerf、Google TPU / A4X、MSFT/META capex、ASML/LRCX read-through 等 13 条仍是 weak candidates。
- 44 条 rubric rows 还只是行业/问题级 gold slot，必须绑定到具体 issuer / lane 后才能做 live lookup。
- 6 条 negative rows 只是 failure fixture，永远不进 evidence bundle。

## False Positive Rejection

本轮最重要的质量修正是拒绝了宽松 `18` 条 live-ready 结果。被拒绝的典型 false positives 包括：

- 用 SEC `Contract with Customer` 或 consolidated revenue 替代 DELL AI server / PowerEdge / margin bridge。
- 用 AMD Ryzen desktop spec 替代 MI300X / MI355X accelerator spec。
- 用 Google Services revenue 替代 TPU / A4X / GB200 cloud deployment。
- 用 generic partnership / source authority row 替代 semicap bookings / backlog / EUV / DUV / China exposure read-through。
- 用 ordinary revenue / OCF / working-capital row 替代 hyperscaler capex 或 AI server demand pool。

这些候选现在都被降为 `source_route_candidate_weak_not_bound` 或 `route_candidate_only_parser_lineage_pending`，不得进入正式 evidence bundle。

## Verification

已运行：

```text
python -m py_compile src/sec_agent/humanmade_gold_set_runtime.py scripts/eval_multi_agent/run_p33_goldset_live_source_backfill.py
python scripts/eval_multi_agent/run_p33_goldset_live_source_backfill.py --strict
python -m pytest tests/test_p33_goldset_live_source_backfill.py -q
```

结果：

- `py_compile`: pass
- runner strict: pass
- focused tests: `5 passed`

未运行：

- paid LLM
- paid specialist LLM
- paid Memo Writer
- full-chain
- model comparison
- new live retrieval
- crawler/parser execution

## Follow-up

RC-P33-019 继续 open。下一步不是跑模型，而是：

1. `P33-AI/Semis-source-specific-parser-locator-backfill`
   - DELL 8-K / earnings release / exhibit table / PowerEdge spec。
   - NVDA Data Center / Blackwell / GB200 product and segment rows。
   - AMD MI300X / MI355X / MLPerf。
   - Google TPU / A4X / GB200 cloud deployment。
   - MSFT / AMZN / GOOGL / META capex and infrastructure spend rows。
   - ASML / LRCX / AMAT / KLAC / TSMC semicap read-through rows。
2. `P33-rubric-case-issuer-lane-binding-and-live-route-backfill`
   - 把 44 条 rubric slots 绑定到 representative issuer / lane / source route。
3. `P33-attempt-backed-typed-gap-closeout`
   - 对仍无法公开取得或 parser 无法稳定解析的 slot，记录 source absent / parser gap / credential gap / commercial tracker gap / product-form gap。

安全边界：在以上三项完成前，不应跑 broad full-chain、模型对比、case expansion 或 release eval。
