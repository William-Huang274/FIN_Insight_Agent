# SEC Agent API Memo v1 Plan Alignment All-Green Rerun

## Summary
- Date: 2026-05-22.
- Status: completed.
- Cloud path: `/root/autodl-tmp/FIN_Insight_Agent`.
- Main result: patched current cloud chain reached `5/5` all-gates green on `sec_free_query_memo_quality_eval_v1`.
- Secrets: cloud password and DeepSeek API key were used only at runtime and were not written to repo files.

## Problem
The prior cloud run cleared the previous named-fact failures but still failed `answer_vs_judgment_plan_gate_pass` across the 5-case memo eval. NVDA also failed `v2_semantic_contract_gate_pass`.

Root causes:
- Judgment Plan `supporting_evidence_ids` did not include every ledger row support ID form. It kept one of `source_evidence_id` or `object_id`, while answer grounding could cite both.
- Interactive plan compaction did not carry `object_id` alongside `source_evidence_id` / `evidence_id`.
- Legacy `decision_drivers` derived from memo fields could merge support from multiple Judgment Plan drivers into one answer driver. NVDA mixed INTC and AMD support inside one competitor driver, which caused both answer-vs-plan mismatch and entity-bleed failures.
- `graph-resume-state` restored the DeepSeek route in Python after patching, but the shell wrapper could still pre-start Qwen vLLM before the graph runner inspected state.

## Code Changes
Changed files:
- `scripts/build_sec_benchmark_judgment_plan.py`
- `scripts/cloud/sec_agent_interactive.py`
- `scripts/cloud/sec_agent_interactive.sh`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- Prior hotfix from the same continuation remains:
  - `src/sec_agent/graph_state.py`
  - `src/sec_agent/graph_nodes.py`

Implemented behavior:
- Judgment Plan support IDs now include `source_evidence_id`, `evidence_id`, and `object_id` for ledger rows.
- Interactive plan compaction maps each selected metric ID to all three support ID forms.
- Memo-derived legacy drivers that match multiple Judgment Plan drivers are split into plan-aligned legacy drivers, avoiding mixed peer evidence in a single driver.
- `graph-resume-state` defaults to preserving the synthesizer route from `sec_agent_state.json`.
- The shell wrapper no longer pre-starts Qwen for state-aware resume unless `SEC_AGENT_RESUME_USE_STATE_ROUTE=0`.
- If a resumed state really uses `qwen_vllm`, Python enables Qwen autostart for that route.

## Validation
Local:
- `python -m py_compile scripts/build_sec_benchmark_judgment_plan.py scripts/cloud/sec_agent_interactive.py`
- `python -m py_compile scripts/cloud/sec_agent_interactive.py`
- `python -m py_compile scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- Smoke tests covered:
  - ledger support IDs preserve `source_evidence_id`, `evidence_id`, and `object_id`;
  - resume route restores DeepSeek from `SecAgentState`;
  - qwen state routes enable autostart;
  - multi-plan answer drivers split into plan-aligned legacy drivers.

Cloud:
- Synced changed files.
- Cloud `py_compile` and smoke checks passed.
- Deterministic replay without new API calls:
  - `reports/quality/20260522_api_memo_v1_5case_191918_plan_support_ids_replay/summary.json`
  - Result: `4/5` all-gates green after support-ID plan replay.
  - Remaining NVDA issue isolated to mixed INTC/AMD legacy driver.
- NVDA plan-aligned replay:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_191946_60a9e00112/post_gates_plan_aligned_replay`
  - Result: `pass_count=12`, `failed=[]`.
- Full deterministic plan-aligned replay:
  - `reports/quality/20260522_api_memo_v1_5case_191918_plan_aligned_replay/summary.json`
  - Result: `5/5` all-gates green, `mean_memo_quality=0.8657`.

Provider-route validation:
- A real `graph-resume-state` on JPM restored `llm_backend=deepseek` from state and wrote `qwen/run_summary.json` with:
  - `llm_backend=deepseek`
  - `provider=deepseek`
  - `model=deepseek-v4-pro`
- After the shell wrapper patch, a no-op `graph-resume-state` did not pre-start Qwen.
- Final cloud check showed `0 MiB / 32607 MiB` and no SEC-agent/vLLM processes.

## Official Final 5-Case API Rerun
Command shape:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
export DEEPSEEK_API_KEY='<runtime only>'
bash /tmp/run_sec_agent_5case_memo_eval.sh
```

Run:
- Summary: `/root/autodl-tmp/FIN_Insight_Agent/reports/quality/20260522_api_memo_v1_5case_200727/summary.json`
- Completed count: `5/5`
- All-gates green count: `5/5`
- Mean memo quality: `0.8831200000000001`
- Memo quality count: `5/5`
- Gate failures: none

Case results:
- `memo_nvda_growth_competitors_001`: `pass_count=12`, `memo_quality=0.896`, `total_tokens=53404`, `api_latency_ms=81073`, `elapsed_sec=252.1414`.
- `memo_amzn_aws_capex_002`: `pass_count=12`, `memo_quality=0.8341`, `total_tokens=60871`, `api_latency_ms=74509`, `elapsed_sec=217.1026`.
- `memo_meta_ai_capex_rd_003`: `pass_count=12`, `memo_quality=0.8665`, `total_tokens=55661`, `api_latency_ms=81667`, `elapsed_sec=233.7451`.
- `memo_jpm_rate_credit_004`: `pass_count=12`, `memo_quality=0.92`, `total_tokens=46909`, `api_latency_ms=80179`, `elapsed_sec=239.4338`.
- `memo_lly_growth_quality_005`: `pass_count=12`, `memo_quality=0.899`, `total_tokens=53173`, `api_latency_ms=66420`, `elapsed_sec=216.7953`.

## Decision
- The Step 4/5 memo eval target is met: at least `4/5` all-gates green, actual `5/5`.
- Named-fact, answer-vs-Judgment-Plan, and NVDA semantic entity-bleed blockers are fixed for this eval.
- It is now reasonable to move to the next planned phase: expand validation only after preserving route-aware resume behavior and keeping the plan-alignment contract in place.

## Caveats
- The final green result is still a 5-case memo eval, not a production-quality benchmark.
- Deterministic plan alignment is intentionally conservative for legacy gate fields; user-facing memo fields remain the primary output surface.
- `answer_status_counts` still uses the historical `answered_qwen9b` label even when the provider is DeepSeek; that naming is cosmetic but should eventually be cleaned up.
