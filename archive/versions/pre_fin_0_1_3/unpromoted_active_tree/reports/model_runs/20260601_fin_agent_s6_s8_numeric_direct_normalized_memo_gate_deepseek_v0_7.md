# Model Run - 20260601_fin_agent_s6_s8_numeric_direct_normalized_memo_gate_deepseek_v0_7

## Summary

- Run ID: `20260601_fin_agent_s6_s8_numeric_direct_normalized_memo_gate_deepseek_v0_7`
- Date: 2026-06-01
- Type: inference evaluation
- Status: accepted for S6/S7/S8 layered gate
- Model: DeepSeek `deepseek-v4-pro`
- Entry point: `scripts/eval_multi_agent_judgment_memo_gate.py`
- Purpose: reuse accepted S5 Specialist artifacts and validate S6 Aggregator, S7 Memo Writer, and S8 Verifier with numeric-fidelity gates.

## Inputs

- Specialist summary: `eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1/specialist_layer_diagnostic.json`
- Case count: `2`
- Cases:
  - `ma_nvda_amd_market_standard`
  - `ma_ai_capex_supply_chain_deep`
- Execution boundary: S5 artifacts reused; S6 deterministic aggregate computed in runner; graph executed from `memo_writer` to `verifier`.

## Command

```powershell
python scripts\eval_multi_agent_judgment_memo_gate.py `
  --specialist-summary eval\sec_cases\outputs\multi_agent_specialist_layer_diagnostic\20260601_fin_agent_s5_shared_context_slot_aware_compression_deepseek_v0_1\specialist_layer_diagnostic.json `
  --run-id 20260601_fin_agent_s6_s8_numeric_direct_normalized_memo_gate_deepseek_v0_7 `
  --memo-max-tokens 2600 `
  --verifier-max-tokens 1000 `
  --max-repair-attempts 1 `
  --strict
```

## Results

| Metric | Value |
| --- | ---: |
| Gate status | pass |
| Case pass count | 2/2 |
| Memo route pass count | 2/2 |
| Verifier pass count | 2/2 |
| Memo fallback count | 0 |
| Memo repair attempts | 1 |
| Memo Writer tokens | 23,429 |
| Verifier tokens | 8,024 |
| Total tokens | 31,453 |

## Case Notes

### ma_ai_capex_supply_chain_deep

- Route: pass, `1` attempt, `0` repair.
- Tokens: Memo Writer `8,930`, Verifier `4,403`, Total `13,333`.
- Memo output: 5 claims covering AMD accrued capex, AI infrastructure sector-depth relationship hypothesis, AMD valuation/market reaction, MSFT cloud monetization counterevidence, and capex cash-flow risk.
- Verifier: pass, no warnings.

### ma_nvda_amd_market_standard

- Route: pass, `2` attempts, `1` repair.
- Tokens: Memo Writer `14,499`, Verifier `3,621`, Total `18,120`.
- Memo output: 4 claims covering AMD revenue growth, AMD market valuation, AMD risk/counterevidence, and NVDA source-boundary limitation.
- Verifier: pass. Soft warning only for `3M` time-window shorthand in direct answer.
- Numeric fidelity: prior `22.1x -> 2.8x` / `20.7x -> 2.2x` drift no longer appears in accepted output.

## Interpretation

The accepted run validates the S6/S7/S8 artifact-reuse gate. The main quality gain is that final memo writing is now thesis-led and claim-card backed, while numeric values in memo claims and direct answers are checked against source ClaimCards. The trade-off is a residual repair on the NVDA/AMD case and soft warning noise around time-window shorthand.

## Safety And Reproducibility

- Runtime credential was read from environment and not saved.
- Raw LLM responses were not written to this report.
- Generated eval artifacts remain under `eval/sec_cases/outputs/...` and are not promoted as tracked source.
- This run supersedes debugging runs v0.1-v0.6 for the S6/S7/S8 gate.
