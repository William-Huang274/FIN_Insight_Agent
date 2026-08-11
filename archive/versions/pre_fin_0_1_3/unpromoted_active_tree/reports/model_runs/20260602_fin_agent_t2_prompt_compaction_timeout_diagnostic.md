# 20260602 Fin Agent T2 Prompt Compaction Timeout Diagnostic

Date: 2026-06-02

## Status

Diagnostic-only. Not accepted as a real full-chain quality/cost gate.

## Purpose

Validate whether Specialist / Universe / Verifier prompt compaction reduces the `fin_full_mt_semis_scope_t2` deep-research token cost without weakening evidence quality.

## Code Gate

Local validation passed:

- `compileall` for touched runtime modules.
- Targeted Specialist / Universe / Memo / LangGraph tests: `87 passed`.
- Broader multi-agent / eval / audit subset: `176 passed`.

## Real Run Attempt

Attempted run:

```text
20260602_fin_agent_t2_prompt_compact_v0_1
```

Command:

```text
python scripts\eval_multi_agent_real_llm_chain.py --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl --case-id fin_full_mt_semis_scope_t2 --run-id 20260602_fin_agent_t2_prompt_compact_v0_1 --real-evidence-operators --strict --timeout-s 240
```

Outcome:

- The command exceeded the outer shell timeout and did not produce final full-chain score artifacts.
- Retrieval artifacts were written, showing SEC/BGE retrieval progressed.
- The remaining Python process stopped making progress and was terminated.
- No runtime credential or raw LLM response was saved.

## Provider Health Check

Tiny DeepSeek JSON health-checks failed:

- Default retry path: `TimeoutError`, `94,202 ms`, `transport_attempt_count=2`.
- No-retry path: `TimeoutError`, `30,880 ms`, `transport_attempt_count=1`.

## Interpretation

The blocked T2 rerun cannot be used to judge memo quality or token efficiency. Current evidence supports only:

- Prompt compaction is syntactically safe under local tests.
- Empty Specialist row fields are no longer sent to the model.
- Artifact observability improved for future real runs.
- DeepSeek endpoint or network transport was unavailable during this validation window.

## Next

Resume with one T2-only run when a tiny DeepSeek health-check succeeds. Do not run the full 17-case suite until T2 passes and cost diagnostics improve.
