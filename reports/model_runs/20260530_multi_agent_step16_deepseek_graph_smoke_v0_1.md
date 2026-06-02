# 20260530 Multi-agent Step16 DeepSeek Graph Smoke v0.1

Date: 2026-05-30

## Scope

Real DeepSeek `deepseek-v4-pro` smoke for the feature-flagged multi-agent graph after Step 15 Workbench/profile wiring and Step 16 graph release gates.

Secrets were injected only through temporary process environment variables. No API key, raw model response, private path, or raw evidence payload was written to this report.

## Configuration

- `SEC_AGENT_MULTI_AGENT_GRAPH=enabled`
- `SEC_AGENT_MULTI_AGENT_LEAD_ROUTER=llm`
- `SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER=llm`
- `SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER=llm`
- `SEC_AGENT_MULTI_AGENT_MEMO_ROUTER=llm`
- `MODEL_NAME=deepseek-v4-pro`
- Research Lead max tokens: `2400`
- Specialist max tokens: `1400`
- Universe max tokens: `1300`
- Memo max tokens: `1600`
- Verifier max tokens: `900`

## Results

### Full 3-case Graph Smoke v0.3

Output:

- `eval/sec_cases/outputs/multi_agent_graph_smoke/codex_step16_real_llm_graph_smoke_v0_3/step16_graph_smoke_summary.json`

Aggregate:

- case count: `3`
- passed: `3`
- failed: `0`
- gate status: `pass`

Cases:

- `step16_focused_management_commentary`
  - execution mode: `focused_answer`
  - activation validation: `pass`
  - claim verification: `pass`
  - tool calls: `3`
  - rendered answer: non-empty
- `step16_standard_peer_memo`
  - execution mode: `standard_memo`
  - specialist verification: `fail`
  - memo status: `blocked_by_specialist_verification`
  - claim verification: `pass`
  - bounded answer allowed: `true`
  - tool calls: `3`
- `step16_deep_relationship_scope`
  - execution mode: `deep_research`
  - Universe validation: `pass`
  - specialist count: `4`
  - specialist verification: `fail`
  - memo status: `blocked_by_specialist_verification`
  - claim verification: `pass`
  - tool calls: `11`

### Post Per-agent Budget Fix Deep Probe v0.4

Output:

- `eval/sec_cases/outputs/multi_agent_graph_smoke/codex_step16_deep_budget_probe_v0_4/step16_deep_budget_probe.json`

Result:

- gate status: `pass`
- status: `completed`
- execution mode: `deep_research`
- Universe validation: `pass`
- claim verification: `pass`
- specialist verification: `fail`
- memo status: `blocked_by_specialist_verification`
- bounded answer allowed: `true`
- loop break reason: empty
- tool calls: `11`
- retrieval routes: `10`
- route pruning: `1` route dropped by `max_tool_calls_per_agent`

## Deterministic Chain Performance Eval

Output:

- `reports/eval/multi_agent_chain_performance/codex_v0_3/chain_performance_summary.json`

Result:

- cases: `7`
- passed: `7`
- failed: `0`
- pass rate: `1.0`
- gate status: `pass`

Coverage categories:

- exact lookup
- focused answer
- standard memo
- deep relationship
- run artifact
- specialist unsupported block
- verifier repair loop

## Validation Commands

- `pytest tests/test_workbench_artifacts.py tests/test_workbench_profiles.py tests/test_multi_agent_langgraph_routing.py -q`
  - `15 passed`
- `pytest tests/test_multi_agent_chain_performance_eval.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_universe_relationship_llm.py tests/test_multi_agent_langgraph_routing.py -q`
  - `37 passed`
- `pytest -q`
  - `366 passed in 11.85s`

## Status

Accepted as Step 16 diagnostic release gate. The multi-agent graph remains feature-flagged / diagnostic-only until real evidence-row specialist quality is evaluated beyond dry-run bounded rows.
