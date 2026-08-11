# 226 - Fin Agent T2 Prompt Compaction And Timeout Diagnostic

Date: 2026-06-02

## Context

After the first full-chain / multi-turn smoke, `fin_full_mt_semis_scope_t2` passed functionally but carried a `high_total_token_cost` flag:

- Prior accepted T2 total tokens: `80,293`.
- Largest contributors: Specialists `39,904`, Memo Writer `15,653`, Universe Relationship `10,581`, Verifier `7,235`, Research Lead `6,875`.
- Biggest Specialist inputs: Industry `13,000`, Fundamental `8,657`, Risk `8,060`.

The next step was to reduce deep-research prompt waste without lowering evidence quality or broadening test execution prematurely.

## Changes

Implemented low-risk prompt compaction and observability changes:

- Specialist LLM prompts now serialize input JSON and schema hints with compact separators instead of pretty JSON.
- Specialist row payloads now remove empty prompt fields such as blank `snapshot_id` and `as_of_date` before model input.
- Direct `route_specialist_memolet_llm()` calls now apply the same row projection as `build_specialist_request_from_state()`.
- Universe Relationship LLM prompt input and schema hint now use compact JSON.
- Verifier LLM minimal projection input now uses compact JSON.
- `multi_agent_summary.json` now preserves Specialist request diagnostics from state:
  - `prompt_bounded_evidence_row_count`
  - `prompt_relationship_summary_row_count`
  - `prompt_row_distribution`
  - `input_coverage_summary`

## Local Verification

Passed:

```text
python -m compileall src\sec_agent\specialist_llm.py src\sec_agent\universe_relationship_llm.py src\sec_agent\memo_llm.py src\sec_agent\langgraph_orchestrator.py
pytest tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_universe_relationship_llm.py tests\test_multi_agent_memo_llm_repair.py -q
87 passed
pytest tests\test_fin_agent_layer_quality_audit.py tests\test_multi_agent_output_quality_audit.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_memo_llm_repair.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_contracts.py tests\test_sec_agent_langgraph_orchestrator.py -q
176 passed
```

Synthetic prompt diagnostic confirmed empty row keys are removed from deep-research Specialist payloads:

- Fundamental synthetic prompt rows: `16`, blank `snapshot_id/as_of_date` keys: `0/0`.
- Risk synthetic prompt rows: `16`, blank `snapshot_id/as_of_date` keys: `0/0`.

## Real DeepSeek Status

Attempted a one-case real T2 rerun:

```text
python scripts\eval_multi_agent_real_llm_chain.py --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl --case-id fin_full_mt_semis_scope_t2 --run-id 20260602_fin_agent_t2_prompt_compact_v0_1 --real-evidence-operators --strict --timeout-s 240
```

Result:

- The shell command timed out after roughly 15 minutes.
- A Python child process remained alive but made no CPU progress and no artifact updates for more than 10 minutes; it was terminated.
- Retrieval artifacts were produced under `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260602_fin_agent_t2_prompt_compact_v0_1/fin_full_mt_semis_scope_t2/mcp_retrieval/`.
- No final `multi_agent_summary.json`, case score, or full-chain pass/fail artifact was produced.

DeepSeek transport health-checks then timed out even for a tiny JSON response:

- 45s timeout with default one retry: `TimeoutError`, total `94,202 ms`, `transport_attempt_count=2`.
- 30s timeout with `LLM_GATEWAY_TRANSPORT_RETRIES=0`: `TimeoutError`, total `30,880 ms`, `transport_attempt_count=1`.

Conclusion: this iteration is locally verified but not accepted as a real quality/cost gate. The real T2 token delta is unknown until the DeepSeek endpoint is responsive again.

## Next Recovery Step

When the API health-check returns normally, rerun only T2 first:

```powershell
if (-not $env:DEEPSEEK_API_KEY) { $env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User') }
$env:LLM_GATEWAY_TRANSPORT_RETRIES = '0'
python scripts\eval_multi_agent_real_llm_chain.py --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl --case-id fin_full_mt_semis_scope_t2 --run-id 20260602_fin_agent_t2_prompt_compact_v0_2 --real-evidence-operators --strict --timeout-s 120
```

Acceptance checks for the recovery run:

- Gate status stays `pass`.
- Specialist request diagnostics appear in `multi_agent_summary.json`.
- T2 total token cost falls materially versus `80,293`, with no decline in memo claims, relationship evidence citation, or verifier status.
- If DeepSeek remains unstable, do not expand to the remaining 14 cases.
