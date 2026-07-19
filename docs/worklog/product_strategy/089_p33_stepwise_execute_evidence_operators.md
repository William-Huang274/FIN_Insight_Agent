# 089 P33 Stepwise Execute Evidence Operators

日期：2026-07-05

阶段：P33-3 AI/Semis single gold workpaper case

## 背景

用户要求 P33 gold case 不再一口气跑 full-chain，而是按 checkpoint / stop-after-node 逐节点验证。上一轮 `route_by_execution_mode -> compile_evidence_requirements` 已证明 relationship route 不再被 coalescing bug 剪掉，但 r3 artifact 仍显示 `route_budget_dropped_count=3`，其中包括 DELL margin 和 supply-chain 的非 relationship routes。

## Root Cause

`_cap_retrieval_plan_routes` 原来按 logical route 计数；但 `execute_evidence_operators` 实际会把多个 SEC text routes 通过 `grouped_sec_search_route_reuse_v0_1` 合并为一个 physical `sec_search_filings` 调用。

结果是：r3 compile 看似通过，但 budget gate 会在 evidence operators 前误剪核心 route。

本轮新增 `RC-P33-009-sec-text-physical-tool-budget-pruning`，并修复为按 physical tool call 计数。

## 修复

- `src/sec_agent/multi_agent_runtime.py`
  - `SEC_SEARCH_TEXT_ROUTES` 共享 grouped physical call key。
  - `_cap_retrieval_plan_routes` 改为按 `_route_budget_physical_call_key()` 计数。
  - summary 写入 physical-call counting policy 和 kept physical call counts。
- `tests/test_multi_agent_evidence_requirements.py`
  - 更新 route budget 测试，避免用可 grouped SEC text route 错测 pruning。
  - 新增 SEC text route grouped budget regression。
  - 新增 P33-style core route survival regression。

## 验证

Focused tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_compiled_retrieval_routes_are_capped_by_agent_permission_matrix tests/test_multi_agent_evidence_requirements.py::test_sec_text_routes_are_budgeted_as_grouped_physical_call tests/test_multi_agent_evidence_requirements.py::test_ai_semis_core_routes_survive_physical_call_budgeting tests/test_multi_agent_evidence_requirements.py::test_relationship_graph_routes_coalesce_before_universe_tool_budget -q
```

结果：`4 passed`。

Broader targeted tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py -q
```

结果：`115 passed`。

## Route Compile r4

Artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_route_compile_evidence_requirements_after_physical_tool_budget_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/route_compile_evidence_requirements_node_result.json
```

结果：

- `status=node_pass`
- `evidence_requirement_count=5`
- `retrieval_route_count=12`
- `route_budget_dropped_count=0`
- DELL margin `ledger_first / filing_text` 保留。
- supply-chain `ledger_first / filing_text` 保留。

## Execute Evidence Operators

Artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_real_after_physical_budget_fix_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_execute_evidence_operators_real_after_physical_budget_fix_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/execute_evidence_operators_compact_state.json
```

结果：

- `status=node_pass`
- `elapsed_sec=78.177`
- `tool_observation_count=12`
- `tool_status_counts={ok:7,cached:5}`
- `sec_query_exact_value_ledger=356` rows
- `sec_search_filings=182` rows
- `relationship_graph_lookup=24` rows
- `market_get_snapshot=9` rows
- `industry_get_snapshot=10` rows
- `context_rows=120`
- `runtime_ledger_rows=387`
- `source_gap_count=4`

Required-item coverage：

- `req_hyperscaler_capex`: ledger / filing text / market snapshot 有 rows。
- `req_customer_deployment`: 8-K commentary / relationship graph 有 rows；plain filing_text route 通过 grouped cache 复用但自身 row_count 为 0，后续 fusion 需判断是否足够。
- `req_supply_chain`: ledger / filing text / relationship graph 有 rows。
- `req_dell_margin_quality`: ledger / filing text / 8-K commentary 有 rows。
- `req_accelerator_architecture`: industry snapshot 有 rows，但 `product_evidence_rows=0`，后续 fusion 必须检查 ProductIntelligenceGraph 是否进入主证据包。

## 边界

- 这不是 P33 gold workpaper closeout。
- 这不证明 specialist JudgmentCards、JudgmentState、Memo Writer、Verifier 或 Workbench dogfood。
- `product_evidence_rows=0` 和 `public_source_context_rows=0` 需要在 `evidence_fusion_selector` 中继续验证。
- ASML / TSM 2026 `10-Q` / `8-K` SEC manifest gaps 不能写成 `public_source_absent`；如需要它们作为主证据，应接 20-F / 6-K、company IR、local exchange filing 或 typed route gap。

## 下一步

唯一允许下一节点：`evidence_fusion_selector`。

检查重点：

- retrieved rows 是否被压成 role-specific evidence bundle；
- ProductIntelligenceGraph relationship rows 是否投影成 bounded product/supply-chain judgment material；
- ASML / TSM SEC manifest gaps 是否被正确 typed，而不是误写公开源不存在；
- 是否能在 specialist 前形成足够清晰的 evidence role / authority boundary。
