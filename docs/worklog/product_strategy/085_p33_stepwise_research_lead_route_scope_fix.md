# P33 Stepwise Research Lead Route Scope Fix

## 背景

用户要求 P33 AI/Semis gold case 不再一口气跑 full-chain，而是按节点逐步执行、逐步检查。当前只推进 `research_lead_plan` 节点，目标是验证 Research Lead 是否已经从“派单 router”升级为能产出 thesis path / required item plan / evidence role plan / writer order 的 supervising analyst。

## 发现的问题

本轮不是模型质量问题，而是 Research Lead 到 EvidenceRequirementPlan 的 route / source scope 传导问题：

1. `relationship_graph` 不在 `retrieval_plan.ALLOWED_RETRIEVAL_ROUTES`，所以即使 Research Lead 要求客户部署、供应链 read-through，后续 plan normalization 仍可能把关系图谱路由剪掉。
2. `_routes_for_task()` 不会从 `relationship_graph` source tier 和 customer / deployment / supply-chain / read-through 等语义推导 relationship route。
3. `_query_contract_for_evidence()` 保留原始 query contract 的 SEC/8-K source scope，没有合并 evidence payload 请求的 source families，导致 relationship requirement 被 source-family mismatch 污染。
4. Stepwise scoring 对原生 checkpoint artifact 的 `research_lead_validation` fallback 不足，节点已 pass 时 score focus 仍可能显示不完整。

这些都属于项目 owned defect，不能写成公开源缺口，也不能用 gate 或 fallback 掩盖。

## 修复

- `src/sec_agent/retrieval_plan.py`
  - 新增 `relationship_graph` route。
  - 增加 relationship terms 和 route inference。
  - 为 relationship route 增加 source tier / section hints。
- `src/sec_agent/research_lead_llm.py`
  - `_query_contract_for_evidence()` 合并 evidence payload 请求的 source families。
  - 防止 customer deployment / supply-chain read-through 的 relationship route 被 SEC-only query contract 剪掉。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - `score_case` / audit 对 stepwise native checkpoint artifact 增加 validation fallback。
- `tests/test_multi_agent_research_lead_llm.py`
  - 增加 regression：`req_customer_deployment` / `req_supply_chain` 必须保留 `relationship_graph` route / source family / route intent。
- `tests/test_multi_agent_real_llm_chain_eval.py`
  - 增加 regression：stepwise artifact 只有 `research_lead_validation` 时，Research Lead validation 仍被计为 pass。

## Paid Node Run

命令：

```powershell
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl --run-id p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5 --output-dir eval/sec_cases/outputs/p33_gold_case_runs --project-os-run-scope p33_single_gold_case --real-evidence-operators --skip-provider-preflight --stop-after-node research_lead_plan
```

Artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/stepwise_node_result.json
```

结果：

- `status=stopped_after_node`，符合 stepwise 预期。
- `research_lead.route_status=pass`。
- `research_lead.validation.status=pass`。
- Provider：`deepseek / deepseek-v4-pro`。
- LLM call：`1` 次。
- Token：`input=4,942 / output=1,461 / total=6,403`。
- Latency：`17,791ms`。
- `thesis_path.path_nodes=6`。
- `evidence_role_plan` 覆盖产品架构、客户部署、供应链传导、基本面桥接、资本市场 price-in、risk/counterevidence。
- `writer_order` 覆盖 opening thesis、product architecture、customer deployment、industry supply-chain、fundamentals、capital-market feedback、counter-thesis。
- `req_customer_deployment` 与 `req_supply_chain` final evidence plan 已保留 `relationship_graph` route，route intent 指向 `universe_relationship / relationship_graph_lookup`。

## 验证

```powershell
python -m pytest tests/test_multi_agent_research_lead_llm.py -q
python -m pytest tests/test_multi_agent_langgraph_routing.py -q
python -m pytest tests/test_multi_agent_contracts.py tests/test_method_runtime.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py -q
python -m py_compile src/sec_agent/retrieval_plan.py src/sec_agent/agent_contracts.py src/sec_agent/research_lead_llm.py src/sec_agent/langgraph_orchestrator.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
```

Observed：

- Research Lead LLM suite：`36 passed`。
- LangGraph routing suite：`31 passed`。
- Contract / method runtime suite：`44 passed`。
- Real LLM chain eval suite：`92 passed`。
- py_compile：pass。

## 边界

- 这是 `research_lead_plan` 节点级 paid smoke，不是 P33-3 gold workpaper closeout。
- downstream evidence operators、specialists、JudgmentState、Memo Writer、Verifier、Workbench dogfood 都没有运行。
- r5 artifact 的 `stepwise_score_focus.research_lead.validation_pass` 曾因 score fallback 缺失不完整；已用 deterministic regression 修复，未为了刷新显示而重新烧 paid token。
- 下一节点只能是 `validate_activation_plan`，再到 `plan_reflection_gate`。不得直接跳 full-chain 或 Memo Writer。

## 更新的 source-of-truth

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/p33_execution_plan_ledger.jsonl`
