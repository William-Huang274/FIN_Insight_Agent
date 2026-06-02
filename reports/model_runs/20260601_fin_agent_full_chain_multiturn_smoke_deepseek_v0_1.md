# Model Run: 20260601_fin_agent_full_chain_multiturn_smoke_deepseek_v0_1

## Summary

- Purpose: validate the new full-chain / multi-turn eval fixture before expanding to the full 17-case set.
- Status: functional smoke pass; cost-quality gate still diagnostic.
- Run type: inference / evaluation smoke.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, DeepSeek API via `DEEPSEEK_API_KEY` environment variable, local BGE reranker path used by the interactive retrieval runner.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`.
- Cases path: `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`.
- Eval plan: `docs/eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md`.
- Accepted run ID: `20260601_fin_agent_full_chain_multiturn_smoke_after_lead_prune_v0_1`.

Command:

```powershell
python scripts/eval_multi_agent_real_llm_chain.py `
  --cases-path tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl `
  --output-dir eval/sec_cases/outputs/multi_agent_real_llm_chain_eval `
  --run-id 20260601_fin_agent_full_chain_multiturn_smoke_after_lead_prune_v0_1 `
  --case-id fin_full_exact_msft_capex_zh `
  --case-id fin_full_mt_semis_scope_t1 `
  --case-id fin_full_mt_semis_scope_t2 `
  --real-evidence-operators `
  --evidence-top-k 16 `
  --object-top-k 16 `
  --reranker-candidate-limit 48 `
  --reranker-top-k 10 `
  --memo-max-tokens 4200 `
  --verifier-max-tokens 1200 `
  --strict
```

## Inputs

- Test fixture: `17` designed cases, only first `3` run for controlled smoke.
- Source boundary: local SEC filings / 8-K earnings releases / market snapshot / industry snapshot / relationship graph, according to each case contract.
- Retrieval mode: real evidence operators, not dry-run.
- Leakage guard: runtime credential not saved; raw model response not saved.

## Results

| Case | Mode | Gate | Tool calls | Tokens | Rendered chars | Flags |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `fin_full_exact_msft_capex_zh` | deterministic lookup | pass | 1 | 10,817 | 486 | none |
| `fin_full_mt_semis_scope_t1` | standard memo | pass | 4 | 41,905 | 2,736 | none |
| `fin_full_mt_semis_scope_t2` | deep research | pass | 9 | 80,293 | 4,410 | `high_total_token_cost` |

Aggregate:

- Case pass: `3/3`.
- Total tool calls: `14`.
- Real retrieval required case: `1/1`.
- Memo / Verifier hard gates: pass.
- Response language: pass for Chinese outputs.
- Forbidden scope: T2 did not continue analyzing AMD as a primary object.
- Project layer-quality audit: `pass`, weighted score `3.136`, sole remaining quality flag `high_total_token_cost`.

## Fixes Between Failed And Accepted Runs

- Exact lookup: added runtime ledger fallback through real SEC search / SQLite structured-object rows when no ledger store path is available.
- Memo contract: softened non-material numeric token hard errors and normalized relationship graph claim types.
- Chinese output: added response-language normalization for memo user-facing fields.
- Research Lead: pruned `risk_counterevidence_analyst` when no explicit risk intent exists.
- Output audit: stopped flagging short deterministic lookup answers as low memo chars/token.
- Layer-quality audit: deterministic lookup cases now skip Memo Writer / Verifier stage scoring when those stages are intentionally inactive; Universe / Specialist stages are inferred from activated agents when fixture metadata is not carried into the case score.

## Cost Diagnostic

T2 remains expensive. Token breakdown from the accepted run:

- Research Lead: `6,875`
- Universe Relationship: `10,581`
- Specialists: `39,904`
- Memo Writer: `15,653`
- Verifier: `7,235`

A tighter cap run, `20260601_fin_agent_full_chain_t2_cost_tight_smoke_v0_1`, still passed functionally but worsened total tokens to `88,893` and added efficiency flags. Lowering top-k / output caps alone is not a valid cost fix.

## Decision

Accepted as a functional full-chain / multi-turn smoke and project layer-quality pass. Not yet accepted as a full 17-case closeout because deep-research token cost remains high.

Next mainline decision: optimize deep-research token flow first, then rerun the same 3-case smoke before expanding to the remaining 14 cases.
