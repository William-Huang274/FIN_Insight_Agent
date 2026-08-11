# P33 Stepwise Route Compile Evidence Requirements

## Summary

- Scope: P33 single AI/Semis gold case `p33_3_ai_semis_accelerator_dell_gold_case_v0_1`.
- Nodes: `route_by_execution_mode -> compile_evidence_requirements`.
- Result: node-level deterministic pass after fixing relationship route coalescing and route-budget summary projection.
- No paid LLM, specialist, Memo Writer, Verifier, or full-chain run was executed.

## Why This Was Needed

After `universe_relationship_expand` passed, the next question was whether relationship graph intent actually survived into executable retrieval routes. The first replay exposed a real owned defect:

- `req_customer_deployment` and `req_supply_chain` both had `relationship_graph` in the evidence requirement plan.
- The compiled retrieval plan kept only `customer_deployment::relationship_graph`.
- `supply_chain::relationship_graph` was dropped by `universe_relationship` per-agent tool limit.
- The retrieval plan summary still reported stale pre-pruning route counts, so the first artifact looked healthier than the actual route list.

This is exactly the kind of upstream route/compiler problem that should be repaired before specialist or memo calls.

## Root Cause

1. `relationship_graph` route coalescing keyed by ticker scope.
   - Customer deployment route covered focus tickers: `NVDA/AMD/GOOGL/DELL`.
   - Supply-chain route covered upstream/peer tickers: `ASML/LRCX/AMAT/KLAC/TSM`.
   - The compiler treated them as separate physical graph lookups.

2. `universe_relationship` has a per-agent tool limit of `1`.
   - Since the two relationship routes did not coalesce, the second route was pruned.

3. `_cap_retrieval_plan_routes()` recomputed only `route_count` and dropped count.
   - `route_counts`, candidate budget, and rerank budget remained stale after pruning.

## Fix

- `relationship_graph` coalescing now groups by route/year and unions ticker scope, evidence requirement ids, and coalesced route ids.
- The same physical relationship graph lookup can now satisfy both customer deployment and supply-chain required items.
- Route budget remains strict; this is not a budget relaxation.
- Route summary is recomputed from kept routes after pruning.

## Artifact

```text
eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_route_compile_evidence_requirements_after_universe_graph_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/route_compile_evidence_requirements_node_result.json
```

Key result:

- `status=node_pass`
- `evidence_validation_status=pass`
- `evidence_requirement_count=5`
- `retrieval_route_count=9`
- `relationship_requirement_count=2`
- `relationship_retrieval_route_count=1`
- `relationship_route_requirement_ids=["req_customer_deployment","req_supply_chain"]`
- `dropped_relationship_route_count=0`
- `route_counts={"8k_commentary":2,"filing_text":2,"industry_snapshot":1,"ledger_first":2,"market_snapshot":1,"relationship_graph":1}`
- `route_budget_dropped_count=3`

## Verification

```powershell
python -m pytest tests/test_multi_agent_evidence_requirements.py::test_relationship_graph_routes_coalesce_before_universe_tool_budget tests/test_multi_agent_evidence_requirements.py::test_compiled_retrieval_routes_are_capped_by_agent_permission_matrix -q
# 2 passed

python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_contracts.py -q
# 113 passed
```

## Remaining Boundaries

- This proves retrieval planning, not evidence row retrieval.
- `route_budget_dropped_count=3` remains. Dropped routes do not include relationship graph, but the next node must inspect whether dropped non-relationship routes hurt required item coverage.
- `RC-P33-007-stepwise-artifacts-missing-full-state-payload` remains open. This replay still used manually reconstructed minimal state.
- Next allowed node: `execute_evidence_operators`.
