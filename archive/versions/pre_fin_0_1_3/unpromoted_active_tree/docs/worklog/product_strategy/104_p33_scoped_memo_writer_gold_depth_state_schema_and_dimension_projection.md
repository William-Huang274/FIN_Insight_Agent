# P33 Scoped Memo Writer Gold-depth State Schema And Dimension Projection

## 背景

P33 的当前目标不是扩大 case 或做模型对比，而是把 AI/Semis humanmade gold set 形成的研究深度真正传到 Memo Writer。上一轮 `Gold-depth Runtime Assimilation Checkpoint` 已证明 `docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json` 能通过 no-paid `HumanmadeGoldSetAudit`，但这只证明 runtime consumption，不证明 paid Memo Writer prose、renderer、verifier 或 Workbench。

本轮只做一个 scoped Memo Writer node 验证。禁止项保持不变：不跑 broad full-chain、不扩 case、不做模型对比、不做 release eval。

## 问题

第一轮 scoped paid Memo Writer node：

- run id: `p33_stepwise_memo_writer_node_from_gold_depth_assimilated_deepseek_20260707_r2`
- 问题：Memo Writer direct answer 过薄后触发多轮 paid repair，第三轮模型输出 `finish_reason=length`。
- token: 约 `49,917`

这不是 source / graph / humanmade gold audit 缺失，而是 writer projection 问题：gold-depth material 已经在 `MemoLogicPlan.required_item_answer_plan`，但没有稳定投影成 user-facing `direct_answer`、`dimension_analyses` 和 action items。

## 根因

1. `SecAgentGraphRuntimeState` 没声明部分 gold-depth runtime fields，LangGraph state 可能裁掉相关 material。
2. Memo Writer completion 只补 direct answer，不够硬；dimension/action 仍可能保留模型生成的薄正文或占位句。
3. repair loop 把“本可从 MemoLogicPlan 确定性补全”的投影问题当成模型写作问题，导致 paid retry 烧 token。

## 修复

代码修复：

- `src/sec_agent/langgraph_orchestrator.py`
  - 声明并保留 `human_source_runtime_rows`、`ai_semis_gold_depth_content_pack`、`product_intelligence_graph_projection`、`gold_specialist_judgment_materials`、`p33_gold_depth_runtime_assimilation` 等 gold-depth runtime fields。
- `src/sec_agent/memo_llm.py`
  - 从 `MemoLogicPlan.required_item_answer_plan` 补全 `direct_answer`。
  - 从同一个 answer plan 补全 / 覆盖 P33 gold-depth required items 对应的 `dimension_analyses`。
  - 从 answer plan 补全 `investment_implications`、`what_would_change_view`、`monitoring_items`、`evidence_gaps_but_actionable`。
  - 对 P33 gold-depth required items，`MemoLogicPlan` 优先于模型薄维度正文。
  - direct-answer-only surface-depth failure 不再触发多轮 paid repair。

测试修复：

- `tests/test_p33_memo_writer_node_runner.py`
- `tests/test_p33_memo_writer_payload_preflight_runner.py`
- `tests/test_p33_humanmade_gold_set_runtime_quality_gate.py`
- `tests/test_multi_agent_memo_llm_repair.py`

## 结果

第二轮 scoped paid Memo Writer node：

- run id: `p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1`
- summary: `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_node_summary.json`
- result: `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_node_result.json`

关键结果：

- `gate_status=pass`
- `memo_route.status=pass`
- `attempt_count=1`
- `repair_attempts=0`
- `total_tokens=17,826`
- `finish_reasons=["stop"]`
- `deterministic_salvage_used=false`
- `hard_check.status=pass`
- `direct_answer_chars=1041`
- `dimension_analysis_count=6`
- `memo_claim_count=6`

确定性验证：

- `python -m pytest tests/test_p33_memo_writer_node_runner.py tests/test_p33_memo_writer_payload_preflight_runner.py tests/test_p33_humanmade_gold_set_runtime_quality_gate.py tests/test_multi_agent_memo_llm_repair.py -q`
  - `97 passed`
- `python -m py_compile src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/run_p33_memo_writer_node_from_aggregate.py scripts/eval_multi_agent/run_p33_memo_writer_payload_preflight_from_aggregate.py`
  - pass

## 边界

这次只证明 scoped Memo Writer node 可以消费 gold-depth `MemoLogicPlan`，并生成有判断的 memo draft。它不证明：

- renderer pass；
- final verifier pass；
- Workbench dogfood；
- human acceptance；
- full-chain pass；
- model comparison；
- case expansion；
- accepted gold workpaper quality。

## 下一步

下一步只能从这个 accepted scoped writer artifact 做 node-level projection 验证：

1. renderer projection replay：确认正文、dimension、action items、evidence refs 不丢、不出现内部字段或占位语。
2. final verifier projection replay：确认 verifier 消费的是 `MemoLogicPlan` / `JudgmentCards` / typed gaps，而不是 raw evidence dump。
3. Workbench projection replay：确认用户能在任务详情里追到 evidence、JudgmentCard、gap、gate、artifact 和 memo section。

在这些完成前，不应再跑 paid writer rerun、broad full-chain、模型对比或扩 case。
