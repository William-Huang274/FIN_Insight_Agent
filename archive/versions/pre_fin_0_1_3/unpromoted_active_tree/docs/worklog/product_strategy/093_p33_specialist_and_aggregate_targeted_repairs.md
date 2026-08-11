# 093 P33 Specialist And Aggregate Targeted Repairs

日期：2026-07-05

## 背景

本轮继续 P33 单个 AI/Semis gold case 的逐节点验证。上一个 accepted checkpoint 是：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/coverage_reflection_compact_state.json
```

用户要求不要直接跑 full-chain，也不要用更多 paid runs 发现 deterministic / node-level 可以定位的问题。本轮只处理：

1. `optional_specialist_subgraph`
2. `aggregate_judgment_plan`

未运行 Memo Writer、Verifier、Workbench dogfood、模型对比或 broad full-chain。

## 问题一：specialist capex 证据传导不稳

现象：

- all-specialist r3 gate pass，但人工审计发现 `risk_counterevidence_analyst` 仍说 hyperscaler capex 证据不足。
- 上游和 market/fusion material 已有 AMZN / MSFT capex，因此这不是公开源缺失，也不是模型单纯理解差。

根因：

- role-specific selector 按 row count 保留 `req_hyperscaler_capex`，AMZN QTD/YTD 多行会填满 quota。
- MSFT capex 行被挤掉后，risk / fundamental specialist 看不到 issuer-diverse capex context。
- 同样问题存在于 `specialist_llm.py` 的 prompt row 构造。

修复：

```text
src/sec_agent/multi_agent_runtime.py
src/sec_agent/specialist_llm.py
tests/test_multi_agent_specialist_llm.py
```

- 新增 distinct-ticker preservation helper。
- 对 `req_hyperscaler_capex` 在 fundamental / risk selector 和 prompt rows 中至少保留 `2` 个 ticker。
- 回归测试要求 AMZN 和 MSFT capex 同时出现在 risk / fundamental request。

验证：

```powershell
python -m pytest tests/test_multi_agent_specialist_llm.py -k "fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows or risk_specialist_request_keeps_required_exact_financial_rows or product_specialist_request_includes_relationship" -q
python -m pytest tests/test_multi_agent_specialist_llm.py -k "fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows or risk_specialist_request_keeps_required_exact_financial_rows or product_specialist_request_includes_relationship or product_specialist_request_balances or comparative_focus_ticker_prompt_rows or soft_balances_comparative_prompt_rows" -q
python -m pytest tests/test_multi_agent_evidence_requirements.py -k "specialist_data_view_reads_compact_fusion_bundle_rows or risk_specialist_activation_uses_research_objective_contract_required_item or product_data_view" -q
python -m py_compile src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/agent_registry.py
```

结果：

- focused specialist tests：`3 passed`
- broader specialist tests：`6 passed`
- evidence requirement tests：`6 passed`
- py_compile：pass

Targeted paid node runs：

```text
p33_stepwise_optional_specialist_risk_after_hyperscaler_issuer_diversity_fix_20260705_r1
p33_stepwise_optional_specialist_fundamental_after_hyperscaler_issuer_diversity_fix_20260705_r1
```

结果：

- risk specialist 现在能同时使用 MSFT YTD capex 和 AMZN QTD capex，形成 `capex digestion risk`，并保留 “不能直接推断供应商收入” 的边界。
- fundamental specialist 现在能把 MSFT / AMZN capex 与 DELL margin / operating bridge 结合，形成 demand signal + margin quality gap 的判断材料。

为避免重新烧一次 all-specialist 54k token，本轮生成 provenance-marked composite checkpoint：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_summary.json
```

Composite 状态：

- base run：`p33_stepwise_optional_specialist_all_after_product_fundamental_risk_projection_fix_20260705_r3`
- replaced agents：`risk_counterevidence_analyst`、`fundamental_analyst`
- unchanged agents：`product_technology_analyst`、`industry_supply_chain_analyst`、`market_valuation_analyst`
- `writer_allowed=true`
- `supported_claim_count=16`
- `unsupported_claim_count=7`
- `conflict_count=1`

边界：

- 这是 accepted specialist checkpoint，但不是 fresh all-specialist rerun。
- base all-specialist r3 只能作为 diagnostic / superseded artifact，不能作为下游 source-of-truth。

## 问题二：aggregate 把 supported market judgment 放进 evidence_gap

现象：

- aggregate r1/r2 中，`market_valuation_analyst` 有 supported judgment。
- 但 `memo_outline.market_valuation` 仍是 `missing_or_partial`，而 market judgment 被放进 `evidence_gap`。

根因：

- `JudgmentCandidate` / observation normalization 把空 `memo_slot` 默认成 `evidence_gap`。
- 已生成的 stale market memolet 即使满足 `market_valuation_analyst + capital_market_price_in + evidence refs + 非 gap 文本`，也没有 recovery 到 market slot。

修复：

```text
src/sec_agent/multi_agent_contracts.py
tests/test_multi_agent_contracts.py
scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
```

- 保留空 `memo_slot`，不在 normalization 阶段过早改成 `evidence_gap`。
- observation aggregation 阶段按 agent expected slot 默认。
- 对 stale market gap slot 增加兼容 recovery。
- 新增 aggregate-only runner，从 accepted specialist checkpoint 直接 replay aggregate node，避免重跑 paid specialists。

验证：

```powershell
python -m pytest tests/test_multi_agent_contracts.py -k "market_judgment_candidate_without_explicit_slot_defaults_to_market_slot or market_judgment_candidate_with_stale_gap_slot_recovers_to_market_slot or product_technology_claim_card_uses_product_memo_slot" -q
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py -k "market_judgment_candidate_without_explicit_slot_defaults_to_market_slot or market_judgment_candidate_with_stale_gap_slot_recovers_to_market_slot or product_technology_claim_card_uses_product_memo_slot or judgment_candidate_becomes_writer_ready_judgment_card or fundamental_request_keeps_required_non_focus_hyperscaler_capex_rows or risk_specialist_request_keeps_required_exact_financial_rows or product_specialist_request_includes_relationship or product_specialist_request_balances or comparative_focus_ticker_prompt_rows or soft_balances_comparative_prompt_rows" -q
python -m pytest tests/test_multi_agent_evidence_requirements.py -k "specialist_data_view_reads_compact_fusion_bundle_rows or risk_specialist_activation_uses_research_objective_contract_required_item or product_data_view" -q
python -m py_compile src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py src/sec_agent/agent_registry.py src/sec_agent/multi_agent_contracts.py scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
```

结果：

- focused contract tests：`3 passed`
- broader contract/specialist tests：`10 passed`
- evidence requirement tests：`6 passed`
- py_compile：pass

Accepted aggregate checkpoint：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_market_gap_slot_recovery_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_market_gap_slot_recovery_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_summary.json
```

节点结果：

- `specialist_verification.status=pass`
- `judgment_state.status=ready`
- `memo_thesis_plan.status=ready`
- `thesis_driver_pack.status=ready`
- `thesis_path.status=ready`
- `supported_claim_count=26`
- `high_materiality_claim_count=6`
- `memo_ready_claim_count=11`
- `supported_memo_slot_count=7`
- `judgment_cards=12`
- `unsupported_claim_count=7`
- `conflict_count=1`

质量判断：

- 现在 aggregate 已经能把 product / financial / industry / market / risk / gap 组织成 7 个 memo slots。
- `market_valuation` 现在是 supported slot，使用 AMZN / MSFT capex 作为 market / expectation context。
- valuation / positioning / price-in 缺口仍保持 typed gap，不冒充已解决。

## 当前状态

已经 accepted 的最新 source-of-truth：

```text
optional_specialist_subgraph:
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_node_result.json

aggregate_judgment_plan:
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_market_gap_slot_recovery_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json
```

Superseded / diagnostic-only：

- `p33_stepwise_optional_specialist_all_after_product_fundamental_risk_projection_fix_20260705_r3`：可用于审计，但不是下游 accepted specialist input。
- aggregate r1/r2：market slot projection bug 修复前产物，不能作为当前 memo planning source-of-truth。

下一步：

1. 先审计 aggregate payload 是否足以进入 `MemoLogicPlan / Memo Writer`。
2. 只做 node-level MemoLogicPlan / Memo Writer 验证。
3. 不跑 broad full-chain，不扩 case，不做模型对比。
4. 如果 writer 输出仍像 evidence summary，先定位最早 faulty artifact：aggregate payload、MemoLogicPlan projection、writer prompt/renderer，而不是加 gate 或换模型。

## Addendum：aggregate payload 不能直接进 writer 的二次修复

继续审计 aggregate payload 时发现：r3 虽然 aggregate gate pass，但 runner 没有把 graph node 中已经生成的 `memo_logic_plan / lead_review_checkpoint / research_objective_contract` 持久化到 `aggregate_judgment_plan_node_result.json`。这意味着如果直接进 writer，writer 无法稳定消费计划层，只能退回 judgment/evidence 物料。

第一次修复后 r4/r5 又暴露第二个问题：`memo_logic_plan` 已经持久化，但 `required_question_items` / `required_item_answer_plan` 缺失或不完整。根因不是模型，而是 stepwise compact state 丢掉了 case fixture 的 `prompt / focus_tickers / required_answer_moves`；runner 回填后又因为 `SecAgentGraphRuntimeState` 没声明这些字段，被 LangGraph 状态通道丢弃。最终 `_required_question_items_for_contract()` 只能靠 query 关键词规则生成少量 items，没把 case 的 required-answer contract 带给 writer。

修复：

```text
scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
src/sec_agent/langgraph_orchestrator.py
tests/test_p33_aggregate_judgment_plan_runner.py
tests/test_memo_logic_plan.py
```

- aggregate runner 从 P33 fixture 按 `case_id` 回填 case contract。
- `SecAgentGraphRuntimeState` 新增 `case_contract / prompt / focus_tickers / search_scope_tickers / required_dimensions / required_answer_moves / expected_gap_types / eval_focus`。
- `_required_question_items_for_contract()` 将 `required_answer_moves` 编译为 required question items，并与 query-derived items 去重合并。
- aggregate runner gate 加硬：缺 `memo_logic_plan`、缺 validation pass、缺 required question items、缺 required item answer plan 都不能 pass。
- node_result 持久化 case contract 和 required moves，方便 Workbench / 后续审计追踪。

验证：

```powershell
python -m pytest tests/test_p33_aggregate_judgment_plan_runner.py tests/test_memo_logic_plan.py -q
python -m py_compile src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py
python scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py --run-id p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7 --strict
```

结果：

- tests：`13 passed`
- py_compile：pass
- r7 aggregate replay：pass

当前 accepted aggregate source-of-truth：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_summary.json
```

r7 关键指标：

- `gate_status=pass`
- `supported_claim_count=26`
- `unsupported_claim_count=7`
- `conflict_count=1`
- `memo_outline_count=7`
- `judgment_card_count=14`
- `judgment_state_card_count=12`
- `memo_logic_plan.validation.status=pass`
- `required_question_item_count=10`
- `required_item_answer_plan_count=10`
- `persisted_required_answer_moves=7`

边界：

- r7 supersedes aggregate r3/r4/r5/r6。
- 仍未运行 Memo Writer、Verifier、Workbench dogfood、模型对比或 broad full-chain。
- 下一步只能从 r7 做 node-level Memo Writer / writer payload 检查。
