# P33 Stepwise Validate Activation Plan

## 背景

P33 gold case 已改为逐节点执行。上一节点 `research_lead_plan` 已通过 paid node smoke，并确认 Research Lead 产出 thesis path、required items、writer order，且 relationship graph route 已保留到 final evidence plan。

本轮只验证下一节点：`validate_activation_plan`。

## 执行方式

没有直接 rerun paid full-chain，也没有重新调用 Research Lead。

原因：

- `validate_activation_plan` 是 deterministic contract validation 节点。
- `eval_multi_agent_real_llm_chain.py` 当前支持 `--stop-after-node`，但没有暴露 multi-agent checkpoint resume 参数。
- `langgraph_node_checkpoints.json` inspect 结果显示 `resume_supported=false` / `blocked_reasons=["no_next_node"]`。
- 因此本轮使用上一节点 artifact 中的 `agent_activation_plan`，直接调用同一套 `validate_agent_activation_plan()` 合同，并记录为 deterministic node replay。

## 输入

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/stepwise_node_result.json
```

## 输出

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_validate_activation_plan_from_research_lead_r5_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/validate_activation_plan_node_result.json
```

## 结果

- `status=node_pass`
- `validation.status=pass`
- `error_count=0`
- `warning_count=0`
- `agent_count=15`
- `source_family_count=7`
- `relationship_graph_present=true`
- `product_intelligence_runtime_status=enabled`
- `next_node=plan_reflection_gate`
- LLM call：`0`

## 判断

这个节点说明：

1. Research Lead 输出的 activation plan 已经能被当前 agent registry / source-family registry / loop-budget contract 接受。
2. `relationship_graph` 没有在 activation validation 后丢失。
3. ProductIntelligence runtime 仍会启用。

这个节点不说明：

1. graph 原生 resume 已经可用。
2. evidence operators 已能正确拉证据。
3. specialist 能形成高质量 judgment。
4. Memo Writer 能形成 accepted gold workpaper。

## 下一步

下一节点是 `plan_reflection_gate`。

要求：

- 仍然使用同一个 P33 gold case。
- 优先 deterministic / node-level 方式。
- 不直接跳 full-chain / Memo Writer。
- 如果 plan reflection 失败，先定位是 activation plan 问题、source capability 问题、relationship scope 问题还是 scoring projection 问题。

## 更新的 source-of-truth

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/p33_execution_plan_ledger.jsonl`
