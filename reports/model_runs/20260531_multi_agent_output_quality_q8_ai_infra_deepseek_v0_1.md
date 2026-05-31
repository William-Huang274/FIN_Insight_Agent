# Model Run: 20260531_multi_agent_output_quality_q8_ai_infra_deepseek_v0_1

## Summary

- Purpose: validate Q8 fixes for Step17 full-chain output quality after Q7 exposed Universe relationship pack leakage, Specialist JSON/truncation failures, and high token cost.
- Status: accepted for diagnostic AI infrastructure single-case gate; not a production memo-quality claim.
- Run type: inference evaluation.
- Timestamp: Q8 run elapsed `300113 ms`.
- Environment: local Windows / PowerShell workspace, DeepSeek API, in-process retrieval runner, BGE rerank configured for CUDA.
- Owner / agent: Codex.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Command shape:

```powershell
$env:DEEPSEEK_API_KEY="<redacted>"
python scripts/eval_multi_agent_real_llm_chain.py `
  --case-id ma_real_sector_ai_infra_full_chain_real_retrieval `
  --run-id 20260531_ai_infra_full_chain_real_retrieval_quality_q8_single_deepseek_v0_1 `
  --real-evidence-operators `
  --bge-device cuda `
  --research-lead-max-tokens 2600 `
  --specialist-max-tokens 3000 `
  --memo-max-tokens 2600 `
  --verifier-max-tokens 1200 `
  --timeout-s 240
```

- Summary output: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_ai_infra_full_chain_real_retrieval_quality_q8_single_deepseek_v0_1/real_chain_eval_summary.json`
- API key handling: read from environment variable only; plaintext key and raw LLM responses were not saved.
- Git state: dirty worktree with ongoing multi-agent source, eval, and worklog changes.

## Inputs

- Fixture: `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
- Case: `ma_real_sector_ai_infra_full_chain_real_retrieval`
- Scope: AI infrastructure sector-depth pack; focus tickers `NVDA`, `DELL`; search scope `NVDA`, `DELL`, `ANET`, `VRT`.
- Expected relationship pack: `technology_ai_infrastructure_depth`.
- Retrieval boundary: real evidence operators enabled; SEC search used BM25/ObjectBM25/BGE rerank through the in-process context runner.

## Model Parameters

- Provider/model: DeepSeek `deepseek-v4-pro`.
- BGE config: `bge_device=cuda`, `bge_model_ref=953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, candidate limit `160`, top-k `32`, batch size `8`, max length `512`.
- Raw LLM response saved: false.

## Results

Primary metrics:

| Metric | Value |
| --- | ---: |
| Case count | 1 |
| Passed | 1 |
| Failed | 0 |
| Pass rate | 1.0 |
| Total tool calls | 10 |
| Real retrieval required cases | 1 |
| Real Specialist quality required cases | 1 |
| Real Specialist quality passed | 1 |
| Total tokens | 98,180 |

Layer outcome:

- Research Lead: pass; execution mode `deep_research`.
- Universe / Relationship: pass; direct lookup called and expected pack filter applied.
- Evidence Operators: pass; SEC search was not dry-run, BM25 candidates and BGE rerank were present, and runtime ledger rows were present.
- Specialist layer: route success and real evidence quality both pass.
- Memo Writer / Verifier: both pass with `finish_reason=stop`.
- Payload safety: pass; no raw API key marker, private path marker, or raw payload leakage in summary artifacts.

Relationship and evidence checks:

- Industry Specialist available/cited pack IDs: `technology_ai_infrastructure_depth` only.
- No `energy_infrastructure_depth` relationship refs remained in the AI infra case.
- SEC routes reported positive `runtime_ledger_row_count` values, including `13` and `17` on key routes.
- BGE runtime metadata reported `bge_device=cuda` and `cuda_available=true`; candidate rerank counts were positive.

Agent token and route behavior:

| Agent | Status | Attempts | Repair | Finish reasons | Tokens |
| --- | --- | ---: | ---: | --- | ---: |
| Research Lead | pass | 1 | 0 | stop | 6,567 |
| Universe / Relationship | pass | 1 | 0 | stop | 5,241 |
| Fundamental Specialist | pass | 2 | 1 | length, stop | 18,201 |
| Industry Specialist | pass | 1 | 0 | stop | 8,797 |
| Market Specialist | pass | 1 | 0 | stop | 6,023 |
| Risk Specialist | pass | 1 | 0 | stop | 9,785 |
| Memo Writer | pass | 1 | 0 | stop | 21,618 |
| Verifier | pass | 1 | 0 | stop | 21,948 |

## Comparison To Q7

- Q7 run `20260531_ai_infra_full_chain_real_retrieval_quality_q7_single_deepseek_v0_1` failed; Q8 passed.
- Q7 total tokens: `131893`; Q8 total tokens: `98180`, about 26% lower.
- Q7 failed because relationship lookup leaked `energy_infrastructure_depth`, Fundamental/Risk Specialist JSON parsing failed, and real evidence quality did not pass.
- Q8 fixed expected-pack propagation into Universe lookup, added Specialist compact repair, and exposed Specialist finish/token diagnostics.

## Experiment Governance

- Hypothesis: passing expected relationship pack IDs into the Universe lookup and using compact Specialist repair for parse/truncation failures should convert the AI infra case from route-only progress to full-chain real-evidence pass while reducing wasted tokens.
- Decision target: AI infra single case passes real retrieval, real Specialist evidence quality, Memo Writer, Verifier, and payload safety gates; total tokens lower than Q7.
- Ceiling: one sector-depth case only; this does not prove stability across banking, healthcare, energy, utilities, or multi-turn cases.
- Baseline: Q7 failed with `gate_status=fail`, relationship pack leakage, Specialist parse failures, and `131893` tokens.
- Stop conditions: stop or debug if relationship refs include non-expected packs, Specialist route fails, SEC retrieval is dry-run, runtime ledger rows are absent, or Memo Writer/Verifier truncate.
- Efficiency gate: total tokens should decline versus Q7; BGE should report CUDA availability and positive candidate counts.
- Decision label: proceed for AI infra diagnostic single-case gate; run a cheaper artifact-observability patch before expanding batch.

## Caveats And Next Step

- The Q8 run still has high token cost, mainly Memo Writer and Verifier.
- Fundamental Specialist still needed one compact repair after an initial `length` finish; first-pass Specialist prompt should be tightened.
- The Q8 audit showed `Claim cards=0` because the summary artifact did not yet persist `claim_card_stats`; this was addressed after the run in the summary/audit observability patch and should be verified on the next run.
- Next step: run one more AI infra single case after the summary patch only if claim-card stats are needed, then expand to banking / healthcare / energy-utilities once token cost is acceptable.
