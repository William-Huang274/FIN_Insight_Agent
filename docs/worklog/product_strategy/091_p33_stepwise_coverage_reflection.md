# 091 P33 Stepwise Coverage Reflection

日期：2026-07-05

## 背景

本轮继续 P33 单个 AI/Semis gold case 的逐节点执行。`evidence_fusion_selector` 已证明 fused rows 有 authority boundary 和 required-item trace，但按 Project OS 规则仍不能直接进入 specialist / Memo Writer，必须先跑 `coverage_reflection`。

Case：

```text
p33_3_ai_semis_accelerator_dell_gold_case_v0_1
```

## 发现的问题

初始 `coverage_reflection` replay 通过节点 stop，但报告不合理：

- `sufficiency_level=partial`
- `missing_requirement_count=2`
- 两条 missing 都指向 `req_customer_deployment`
- 原因是 `customer_deployment::filing_text:no_rows`

这和上游 fusion 事实冲突：`evidence_fusion_selector` 已有 `req_customer_deployment=60` fused rows，其中包括 `company_authored_unaudited_sec_filing` 和 `relationship_graph` rows。

根因不是数据缺失，而是 coverage gate 的投影逻辑错误：

1. coverage 按单条 route / source family 判断缺口，没有优先看 fused required-item authority rows；
2. coalesced `relationship_graph` route 的 `evidence_requirement_id` 是 `req_customer_deployment,req_supply_chain`，旧 requirement-key 逻辑没有拆开。

## 修复

代码：

```text
src/sec_agent/multi_agent_runtime.py
src/sec_agent/langgraph_orchestrator.py
tests/test_multi_agent_evidence_requirements.py
```

修复内容：

- 新增 `reflection_report_from_evidence_fusion_bundle`。
- `_node_coverage_reflection` 在有 `evidence_fusion_bundle` 时优先从 fused rows 判断 required-item sufficiency。
- `_requirement_keys` / `_route_requirement_key` 支持拆分 `evidence_requirement_id(s)`。
- 没有 fusion bundle 时才回退到旧的 tool-observation coverage path。
- 新增回归：
  - fusion 已覆盖 required item 时，不因 supplemental route `no_rows` 误触发 second pass；
  - coalesced relationship route 的多个 req ids 都能被识别。

## 验证

Focused tests：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_coverage_reflection_uses_fused_rows_before_supplemental_route_gaps tests/test_multi_agent_evidence_requirements.py::test_coverage_reflection_splits_coalesced_relationship_requirement_ids -q
```

结果：`2 passed`。

Accepted artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/coverage_reflection_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/coverage_reflection_compact_state.json
```

结果：

- `status=node_pass`
- `sufficiency_level=partial`
- `missing_requirement_count=0`
- `second_pass_request_count=0`
- `source_family_gap_count=0`
- `quality_gap_count=1`
- `bounded_answer_allowed=true`
- `trigger=coverage_reflection_evidence_fusion_bundle`
- `bounded_gap_count=4`
- `fused_row_count=375`
- `product_runtime_fact_count=0`
- `active_specialist_count=5`
- `expected_next_node=specialists`

## 当前质量边界

唯一 quality gap：

```text
req_accelerator_architecture
```

原因：

- 只有 `industry_snapshot` 的 `context_or_proxy` rows；
- 没有 company_product_evidence_graph exact product runtime facts；
- 可以作为产品/架构 bounded context 进入 Product Specialist；
- 不能提权为 exact product KPI、公司官方 SKU/spec fact、shipment、ASP、market share 或 revenue 证据。

## 当前边界

- 本轮只证明 `coverage_reflection` 的 required-item sufficiency 和 bounded-context boundary。
- 还没有证明 specialist JudgmentCards、JudgmentState、Memo Writer、Verifier、Workbench dogfood、模型对比或 accepted gold workpaper。
- 由于 stepwise compact state 仍缺完整 graph state payload，本轮用 Research Lead accepted artifact 补入 `agent_activation_plan` 后 replay；这仍受 RC-P33-007 约束。

## 下一步

唯一允许下一节点：

```text
optional_specialist_subgraph
```

检查重点：

- specialists 是否消费 `coverage_reflection` 的 bounded product/architecture context；
- Product Specialist 是否把 `req_accelerator_architecture` 写成 bounded architecture / competitive context，而不是 exact product fact；
- Fundamental / Supply-chain / Risk specialists 是否把 fused exact/context rows 转成 JudgmentCandidates；
- 仍然不得跳 Memo Writer / model comparison / broad full-chain。
