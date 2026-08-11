# 090 P33 Stepwise Evidence Fusion Selector

日期：2026-07-05

## 背景

本轮继续 P33 单个 AI/Semis gold case 的逐节点执行。上一节点 `execute_evidence_operators` 已取回真实 rows，但按 Project OS 规则不能直接跳 specialist / Memo Writer，必须先验证 `evidence_fusion_selector` 是否能把 evidence rows 压成带 authority boundary 和 required-item trace 的融合证据包。

Case：

```text
p33_3_ai_semis_accelerator_dell_gold_case_v0_1
```

## 发现的问题

第一轮 fusion replay 暴露两个 owned root-cause：

1. `source_gaps` 被双算。
   - ASML / TSM 的 SEC manifest gaps 既从 state 进入 bounded gap register，又从 authority row projection 再进入一次。
   - 结果会把 4 个真实 route gaps 膨胀成 8 个 register gaps。

2. required-item trace 丢失。
   - retrieval route 层有 `evidence_requirement_id=req_*`。
   - 但 `execute_evidence_operators` 输出的 context/runtime/market/industry rows 没稳定保留这些 ids。
   - fusion 后只能看到 `fundamental / supply_chain / customer_deployment` 这类 role labels，不能追到具体 `req_hyperscaler_capex`、`req_dell_margin_quality` 等必答项。

这不是模型问题，也不是公开数据缺失，是 row lineage / fusion projection 的工程问题。

## 修复

代码：

```text
src/sec_agent/multi_agent_runtime.py
tests/test_multi_agent_evidence_requirements.py
```

修复内容：

- `bounded_gap_register` 改为按 semantic key 去重：
  `source_family + gap_type + ticker + metric + product_or_segment + bounded_reason`。
- `bounded_gap_reason` 纳入 gap type / reason 判断。
- `_bounded_row` 保留 trace fields：
  `evidence_requirement_id(s)`、`selection_task_id(s)`、`selection_route_id(s)`、`retrieval_routes`。
- `execute_evidence_operator_plan` 在 route execution 阶段向 rows 注入 route-level trace。
- grouped SEC search rows 通过 `selection_route_ids / selection_routes` 回填具体 `req_*`。
- 新增回归测试覆盖：
  - source gap / authority projection dedupe；
  - fusion trace preservation；
  - evidence operator row-level requirement trace preservation。

## 验证

Focused tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_execute_evidence_operator_preserves_requirement_trace_from_route tests/test_multi_agent_evidence_requirements.py::test_evidence_fusion_preserves_required_item_trace_fields tests/test_multi_agent_evidence_requirements.py::test_evidence_fusion_dedupes_source_gap_authority_projection -q
```

结果：`3 passed`。

Broader targeted tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py -q
```

结果：`118 passed`。

`py_compile`：

```powershell
python -m py_compile src/sec_agent/multi_agent_runtime.py
```

结果：通过。

## Accepted Artifacts

Trace-repaired execute replay：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_trace_repaired_from_real_rows_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_trace_repaired_from_real_rows_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_compact_state.json
```

结果：

- `runtime_ledger_row_count=387`
- `context_row_count=120`
- `market_snapshot_row_count=9`
- `industry_snapshot_row_count=10`
- `source_gap_count=4`
- `required_like_counts` 全覆盖：
  - `req_hyperscaler_capex=97`
  - `req_dell_margin_quality=145`
  - `req_supply_chain=129`
  - `req_customer_deployment=60`
  - `req_accelerator_architecture=10`

Accepted fusion replay：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_evidence_fusion_selector_after_requirement_trace_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/evidence_fusion_selector_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_evidence_fusion_selector_after_requirement_trace_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/evidence_fusion_selector_compact_state.json
```

结果：

- `status=node_pass`
- `row_count=375`
- `exact_authority_row_count=232`
- `context_only_row_count=139`
- `gap_only_row_count=4`
- `bounded_gap_count=4`
- `public_exact_authority_violation_count=0`
- `semantic_exact_authority_violation_count=0`
- required trace 全覆盖：
  - `req_hyperscaler_capex=42`
  - `req_dell_margin_quality=99`
  - `req_supply_chain=75`
  - `req_customer_deployment=60`
  - `req_accelerator_architecture=10`

## Superseded Artifact

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_real_after_requirement_trace_fix_20260705_r2/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/DO_NOT_USE_SUPERSEDED.txt
```

该 artifact 是一次直接工具重跑，但缺 full graph `state_context`，导致 route skips / source gaps。它不能作为 accepted evidence，只保留 superseded 标记，防止误用。

## 当前边界

- 本轮只证明 `evidence_fusion_selector` 的 authority boundary、typed gap、required-item trace。
- 还没有证明 specialist JudgmentCards、JudgmentState、Memo Writer、Verifier、Workbench dogfood 或 accepted gold workpaper。
- `relationship_graph` rows 仍是 `scope_or_hypothesis_only`。
- `market_snapshot` / `industry_snapshot` 仍是 context/proxy。
- `product_runtime_fact_count=0`，说明本 fused bundle 还没有 exact company_product_evidence_graph product runtime facts。

## 下一步

唯一允许下一节点：`coverage_reflection`。

检查重点：

- required-item coverage 是否足以进入 specialist；
- typed gaps 是否正确；
- product_runtime exact gap 是否会导致 product specialist 输入薄；
- relationship / market / industry proxy 是否保持 bounded context，不被提权成 exact fact；
- 仍然不得跳 Memo Writer / model comparison / broad full-chain。
