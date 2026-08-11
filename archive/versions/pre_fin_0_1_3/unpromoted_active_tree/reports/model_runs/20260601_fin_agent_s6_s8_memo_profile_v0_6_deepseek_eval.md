# Model Run: 20260601_fin_agent_s6_s8_memo_profile_v0_6_deepseek_eval

## Summary
- Purpose: Evaluate Memo Writer v0.6 profile-driven output contract after replacing the fixed short bounded memo contract.
- Status: pass.
- Run type: inference evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows / Python; DeepSeek API via environment variable only; API key not saved.

## Code And Command
- Entry point: `scripts/eval_multi_agent_judgment_memo_gate.py`.
- Changed surface: `src/sec_agent/memo_llm.py`, `src/sec_agent/multi_agent_contracts.py`, `src/sec_agent/langgraph_orchestrator.py`, `scripts/eval_multi_agent_judgment_memo_gate.py`.
- Commands:
  - `python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_temporal_gate_nvda_amd_deepseek_v0_5/specialist_layer_diagnostic.json --run-id 20260601_fin_agent_s6_s8_memo_profile_v0_6_nvda_amd_deepseek_v0_4 --memo-max-tokens 3600 --verifier-max-tokens 1200 --max-repair-attempts 1 --strict`
  - `python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_energy_risk_industry_prompt_floor_deepseek_v0_5/specialist_layer_diagnostic.json --run-id 20260601_fin_agent_s6_s8_memo_profile_v0_6_energy_deepseek_v0_2 --memo-max-tokens 3800 --verifier-max-tokens 1200 --max-repair-attempts 1 --strict`
  - `python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2/specialist_layer_diagnostic.json --run-id 20260601_fin_agent_s6_s8_memo_profile_v0_6_banking_deepseek_v0_2 --case-id ma_banking_deposit_credit_standard --memo-max-tokens 3800 --verifier-max-tokens 1200 --max-repair-attempts 1 --strict`
  - `python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2/specialist_layer_diagnostic.json --run-id 20260601_fin_agent_s6_s8_memo_profile_v0_6_utilities_deepseek_v0_5 --case-id ma_utilities_power_load_deep --memo-max-tokens 4600 --verifier-max-tokens 1200 --max-repair-attempts 1 --strict`

## Inputs
- Upstream artifacts:
  - NVDA/AMD S5: `20260601_fin_agent_s5_temporal_gate_nvda_amd_deepseek_v0_5`
  - Energy S5: `20260601_fin_agent_s5_energy_risk_industry_prompt_floor_deepseek_v0_5`
  - Banking/utilities S5: `20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2`
- Candidate boundary: passed S5 Specialist outputs only; no raw rows or new retrieval inside Memo Writer / Verifier.
- Leakage guard: Memo Writer consumes shared memo context, verified judgment plan, and specialist verification only.

## Results
| Case | Industry / depth | Gate | Profile | Direct chars | Memo claims | Ref count | Action fields | Repairs | Tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| `ma_nvda_amd_market_standard` | semiconductor / standard comparative | pass | `expanded` | 1126 | 5 | 5 | 3 implications / 3 change-view / 4 watch / 3 gaps | 0 | 18,190 |
| `ma_energy_capex_commodity_standard` | energy / standard with source gaps | pass | `expanded` | 1186 | 5 | 3 | 3 implications / 3 change-view / 4 watch / 2 gaps | 0 | 14,873 |
| `ma_banking_deposit_credit_standard` | banking / standard | pass | `expanded` | 1142 | 5 | 4 | 3 implications / 3 change-view / 4 watch / 3 gaps | 0 | 17,356 |
| `ma_utilities_power_load_deep` | utilities / sector-depth | pass | `deep_research` | 1754 | 8 | 9 | 3 implications / 3 change-view / 3 watch / 2 gaps | 0 | 21,485 |

## Interpretation
- Memo Writer v0.6 successfully moved standard/deep cases away from the fixed short contract. Standard cases now select `expanded`; utilities sector-depth selects `deep_research`.
- The first NVDA/AMD real run exposed direct-answer surface problems: internal `ClaimCard` language and repeated claim sentences. Deterministic gates now block internal labels, pipe-joined claims, repeated direct-answer sentences, and missing action fields for non-compact profiles.
- Energy still has a real source coverage boundary: local evidence supports commodity context and CVX filing evidence, but XOM hard rows and management commodity outlook remain incomplete. The profile can be expanded, but the memo must remain caveated.
- Verifier remained a safety gate: all final pass runs had deterministic verifier pass and LLM verifier pass, with no raw-row or tool-call leakage.

## Efficiency
- Total S6-S8 tokens across the four final pass runs: 71,904.
- Memo repairs in final pass runs: 0.
- Token use is higher than compact memo mode but now buys materially denser output: profile-specific direct answers, 5-8 memo claims, action fields, and source-gap handling.

## Follow-up
- Add healthcare standard/deep Specialist case before claiming healthcare memo quality.
- Add profile-aware token budget policy so `expanded` and `deep_research` do not overpay when ClaimCard density is only marginal.
- Add renderer product-surface evaluation for the new action fields outside S6-S8 artifact summaries.
