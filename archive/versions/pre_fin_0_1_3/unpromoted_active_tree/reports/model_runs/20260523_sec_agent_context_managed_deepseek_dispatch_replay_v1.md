# SEC Agent Context-Managed DeepSeek Dispatch Replay v1

## Run Metadata
- Date: 2026-05-23
- Run ID: `20260523_sec_agent_context_managed_deepseek_dispatch_replay_v1`
- Type: tool-call controller route + harness dispatch replay
- Model: DeepSeek `deepseek-v4-pro`
- Entry point: `scripts/evaluate_sec_agent_context_managed_dispatch_replay.py`
- Mode: route-only LLM decision followed by fixture harness dispatch; no real SEC DAG execution; no GPU workload

## Purpose
- Validate the full context-managed control loop short of real graph execution:
  - build context snapshot from persisted session JSON;
  - route with DeepSeek tool calls;
  - dispatch the selected harness tool against fixture artifacts;
  - apply tool result back into ContextManager;
  - rebuild post-turn snapshot and validate state.

## Inputs
- Eval set: `eval_sets/sec_agent_multiturn_noncontiguous_followup_eval_v1.json`
- Scope: `6` scenarios / `23` turns
- Fixture sessions:
  - `s_tool_002`
  - `s_tool_003`
  - `s_tool_004_a`
  - `s_tool_004_b`
  - `s_tool_005`

## Results
- Local heuristic:
  - Output: `reports/quality/local_context_managed_dispatch_replay_heuristic_v1.json`
  - Result: tool pass `23/23`, arg pass `23/23`, snapshot pass `23/23`, dispatch pass `23/23`, context update pass `23/23`.
- Cloud heuristic:
  - Output: `reports/quality/cloud_context_managed_dispatch_replay_heuristic_v1.json`
  - Result: tool/arg/snapshot/dispatch/context update all `23/23`.
- Cloud DeepSeek:
  - Output: `reports/quality/cloud_context_managed_dispatch_replay_deepseek_v1.json`
  - Result: tool pass `23/23`, arg pass `23/23`, snapshot pass `23/23`, dispatch pass `23/23`, context update pass `23/23`, `failure_count=0`.

## Interpretation
- The controller no longer depends on hand-built eval context for this suite.
- DeepSeek can route from ContextManager snapshots, and the selected tool can be dispatched against session-scoped fixture artifacts.
- `ContextManager.apply_tool_result()` keeps post-turn snapshots valid, including reformat invalidation and evidence-reference updates.
- `resume_analysis` uses fixture-level downstream completion to avoid running the real graph while still testing post-resume evidence follow-ups.

## Safety
- No API key or cloud password is stored in this ledger.
- The replay does not execute SEC retrieval, BGE reranking, synthesis, gates, or rendering through the real graph.
