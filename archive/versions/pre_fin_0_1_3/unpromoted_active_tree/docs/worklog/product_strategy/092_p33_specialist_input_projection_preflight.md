# 092 P33 Specialist Input Projection Preflight

日期：2026-07-05

## 问题

在 `coverage_reflection` 通过后，下一步理论上是 `optional_specialist_subgraph`。但按 Project OS / Global Stewardship 规则，不能直接烧 paid specialist token；必须先确认 specialist 真的能收到 role-specific、authority-aware、required-item scoped 的输入。

初始 no-paid preflight 暴露 owned root-cause：

- `coverage_reflection_compact_state.json` 中有 `375` 条 `evidence_fusion_bundle.authority_rows`；
- 但 `build_agent_data_view()` 和 specialist shared context 仍主要读取旧 raw rows；
- 结果 fundamental / industry / market specialist 可能看到空 row pack；
- `risk_counterevidence_analyst` 虽然被 Research Objective Contract / thesis_path 要求，但 activation matcher 没消费这些 required items，导致被 skipped。

这不是模型问题，也不是公开数据缺失，而是 compact state -> specialist data view / activation contract 的传导问题。

## 修复

修改：

- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/specialist_llm.py`
- `tests/test_multi_agent_evidence_requirements.py`

核心修复：

1. `build_agent_data_view()` 在 raw rows 缺失时按角色读取 `evidence_fusion_bundle.authority_rows`。
2. specialist source-boundary summary 在 raw rows 缺失时用 fused source-family counts 回填。
3. fused `relationship_graph` rows 可进入 industry specialist 的 `relationship_summary`。
4. `_state_evidence_requirements()` 读取 `research_objective_contract` 和 `thesis_path.required_items`。
5. `_requirement_matches_specialist()` 支持 `primary_agents` / `assigned_agents` 直接激活对应 specialist。
6. 增加两个 deterministic regression tests：
   - `test_specialist_data_view_reads_compact_fusion_bundle_rows`
   - `test_risk_specialist_activation_uses_research_objective_contract_required_item`

## 结果

Accepted preflight artifact：

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_specialist_input_projection_preflight_after_required_item_scope_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/specialist_input_projection_preflight.json
```

结果：

- active specialists：
  - `fundamental_analyst`
  - `product_technology_analyst`
  - `industry_supply_chain_analyst`
  - `market_valuation_analyst`
  - `risk_counterevidence_analyst`
- role-specific row counts：
  - `fundamental_analyst=48`
  - `product_technology_analyst=48`
  - `industry_supply_chain_analyst=48`
  - `market_valuation_analyst=16`
  - `risk_counterevidence_analyst=20`
- `industry_supply_chain_analyst.relationship_summary_count=24`
- source boundaries：
  - `context=76`
  - `ledger=280`
  - `market=9`
  - `industry=10`
  - `fusion_authority=375`

验证：

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_specialist_data_view_reads_compact_fusion_bundle_rows tests/test_multi_agent_evidence_requirements.py::test_risk_specialist_activation_uses_research_objective_contract_required_item -q
python -m py_compile src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py src/sec_agent/langgraph_orchestrator.py
python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py -q
```

结果：

- focused tests：`2 passed`
- related deterministic suite：`181 passed`
- py_compile：pass

## 边界

- 没有运行 paid `optional_specialist_subgraph`。
- 没有生成 specialist `judgment_candidates`。
- 没有生成 JudgmentCards / JudgmentState / Memo / Verifier / Workbench dogfood / accepted gold workpaper。
- 本轮只证明 specialist 输入投影和激活合同已修复。

## 下一步

下一步只能进入 node-level `optional_specialist_subgraph`，并在运行前确认 token / provider / AIE 约束。不得直接跳 Memo Writer、模型对比、broad full-chain 或 case expansion。
