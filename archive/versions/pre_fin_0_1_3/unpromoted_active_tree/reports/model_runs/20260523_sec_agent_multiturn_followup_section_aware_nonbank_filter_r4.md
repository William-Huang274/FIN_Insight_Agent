# Model Run: 20260523_sec_agent_multiturn_followup_section_aware_nonbank_filter_r4

## Summary
- Purpose: Validate the section-aware `explain_evidence` fix, non-bank Query Contract filtering, and memo-aware v2 semantic gate on the real multi-turn scope-revision full chain.
- Status: completed
- Run type: inference evaluation
- Timestamp: 2026-05-23 Asia/Shanghai
- Environment: SeeTaCloud RTX 4090D, host driver `570.124.04`, venv `/root/autodl-tmp/envs/sec-agent-cu128`, BGE reranker on CUDA.

## Code And Command
- Entry point: `scripts/cloud/run_sec_agent_multiturn_full_chain_scenario.py`
- Scenario: `multiturn_tool_scope_revision_001`
- Command shape:

```bash
DEEPSEEK_API_KEY=<env> /root/autodl-tmp/envs/sec-agent-cu128/bin/python \
  scripts/cloud/run_sec_agent_multiturn_full_chain_scenario.py \
  --eval-path eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json \
  --scenario-id multiturn_tool_scope_revision_001 \
  --output-dir reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128 \
  --session-root reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/session_harness \
  --python /root/autodl-tmp/envs/sec-agent-cu128/bin/python \
  --controller-backend deepseek \
  --llm-backend deepseek \
  --base-url https://api.deepseek.com \
  --chat-completions-path /chat/completions \
  --model deepseek-v4-pro \
  --api-key-env DEEPSEEK_API_KEY \
  --query-planner llm \
  --bge-device cuda
```

- Relevant changed files:
  - `src/sec_agent/tool_harness.py`
  - `src/sec_agent/tool_controller.py`
  - `src/sec_agent/query_contract.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
  - `scripts/evaluate_sec_agent_tool_harness_dispatch_fixtures.py`

## Inputs
- Eval set: `eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json`
- Scenario: continuous scope revision, `start_memo_analysis -> revise_memo_scope -> inspect_coverage -> explain_evidence`
- Source policy: `SEC_ONLY_10K`
- Main revised scope: `NVDA / 2024`

## Outputs
- Summary: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/summary.json`
- Post-gate summary: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/t2_sec_benchmark_post_gates_summary.json`
- Coverage matrix: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/t2_runtime_evidence_coverage_matrix.json`
- Query contract: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/t2_query_contract.json`
- Evidence replay: `reports/quality/cloud_multiturn_full_chain_scope_revision_20260523_r4_nonbank_filter_cu128/explain_evidence_recheck_v2.json`

## Results
- Full-chain runner:
  - `turn_count=4`
  - `tool_pass_count=4`
  - `dispatch_pass_count=4`
  - `failure_count=0`
  - `all_pass=true`
  - `elapsed_sec=405.771`
- Revised NVDA-only coverage:
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
  - `answer_status=complete`
  - `task_count=7`
  - `missing_metric_families=["semiconductor_solutions","subscription_revenue"]`
  - No banking-only metric families remain in the NVDA scope.
- Post-gates after memo-aware validator replay:
  - `answer_ledger_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `v2_semantic_contract_gate_pass=true`
  - `answer_vs_judgment_plan_gate_pass=true`
  - `metric_source_grounding_gate_pass=true`
  - `ledger_unit_gate_pass=true`
  - `qwen_answer_gate_pass=true`
- Evidence follow-up replay:
  - Target resolved to `why_it_matters[2]`.
  - Metric IDs: NVDA 2024 gross margin and operating cash flow.
  - Evidence IDs: 4 SEC evidence IDs from NVDA 2024 10-K Item 7.
  - `ledger_match_count=3`
  - `judgment_plan_match_count=1`
  - `rerun_required=false`

## Experiment Governance
- Hypothesis: section-aware evidence resolution plus deterministic scope filtering can make non-rerun follow-up evidence questions reliable after a real scope revision.
- Decision target: real DeepSeek/BGE full-chain scenario passes routing, dispatch, active scope, coverage, post-gates, and evidence replay.
- Baselines: prior r2 passed tool/dispatch but evidence payload was empty; r3 fixed evidence and semantic gate but exposed banking-task contamination in NVDA coverage.
- Stop conditions: empty evidence payload, banking metric families in non-bank coverage, or any deterministic gate failure after replay.
- Decision label: proceed
- Mainline decision: Accept this as the current multi-turn follow-up baseline before considering multi-source expansion.

## Runtime Efficiency
- Wall time: `405.771s`.
- t1 and t2 true graph runs dominate wall time; t3/t4 artifact reads remain interactive.
- Serving implication: non-rerun evidence/coverage tools are suitable for low-latency follow-up; scope revision remains batch-like until retrieval/model calls are persisted.

## Caveats And Next Step
- The graph-run stdout initially showed `v2_semantic_contract_gate_pass=false` before the gate validator fix; the same output was replayed after the validator fix and passed.
- The current result covers one real continuous scope-revision scenario plus local/cloud route/fixture tests, not a full production reliability estimate.
- Multi-source expansion remains deferred until this baseline is preserved across a broader non-contiguous follow-up suite.
