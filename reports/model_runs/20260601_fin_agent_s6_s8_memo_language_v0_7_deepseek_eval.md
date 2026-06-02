# Model Run: 20260601_fin_agent_s6_s8_memo_language_v0_7_deepseek_eval

## Summary

- Purpose: validate chain-level `response_language` for S6/S7/S8 Judgment / Memo / Verifier artifacts.
- Status: pass.
- Run type: inference / evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, DeepSeek API via `DEEPSEEK_API_KEY` environment variable.

## Code And Command

- Entry point: `scripts/eval_multi_agent_judgment_memo_gate.py`.
- Contract changes: Memo Writer v0.7 response-language context, zh-CN verifier gate, Chinese renderer labels, numeric parser support for Chinese units/ranges.
- Commands:

```powershell
python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_temporal_gate_nvda_amd_deepseek_v0_5/specialist_layer_diagnostic.json --run-id 20260601_fin_agent_s6_s8_memo_language_v0_7_nvda_amd_deepseek_v0_4 --memo-max-tokens 3600 --verifier-max-tokens 1100 --max-repair-attempts 1 --strict
python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2/specialist_layer_diagnostic.json --case-id ma_utilities_power_load_deep --run-id 20260601_fin_agent_s6_s8_memo_language_v0_7_utilities_deepseek_v0_1 --memo-max-tokens 4600 --verifier-max-tokens 1200 --max-repair-attempts 1 --strict
python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2/specialist_layer_diagnostic.json --case-id ma_banking_deposit_credit_standard --run-id 20260601_fin_agent_s6_s8_memo_language_v0_7_banking_deepseek_v0_1 --memo-max-tokens 3800 --verifier-max-tokens 1100 --max-repair-attempts 1 --strict
python scripts/eval_multi_agent_judgment_memo_gate.py --specialist-summary eval/sec_cases/outputs/multi_agent_specialist_layer_diagnostic/20260601_fin_agent_s5_energy_risk_industry_prompt_floor_deepseek_v0_5/specialist_layer_diagnostic.json --case-id ma_energy_capex_commodity_standard --run-id 20260601_fin_agent_s6_s8_memo_language_v0_7_energy_deepseek_v0_3 --memo-max-tokens 3800 --verifier-max-tokens 1100 --max-repair-attempts 1 --strict
```

## Inputs

- Source artifacts: passed S5 Specialist layer summaries from NVDA/AMD, utilities, banking, and energy cases.
- Candidate boundary: S6-S8 artifact reuse only; no S1-S5 rerun.
- Leakage guard: Memo Writer receives compact verified judgment plan, shared memo context, and specialist verification only; no raw rows or tool calls.

## Results

| Case | Output path | Status | Profile | Memo tokens | Verifier tokens | Repairs |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `ma_nvda_amd_market_standard` | `eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260601_fin_agent_s6_s8_memo_language_v0_7_nvda_amd_deepseek_v0_4` | pass | expanded | 12,003 | 6,085 | 0 |
| `ma_utilities_power_load_deep` | `eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260601_fin_agent_s6_s8_memo_language_v0_7_utilities_deepseek_v0_1` | pass | deep_research | 15,078 | 7,108 | 0 |
| `ma_banking_deposit_credit_standard` | `eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260601_fin_agent_s6_s8_memo_language_v0_7_banking_deepseek_v0_1` | pass | expanded | 11,864 | 5,590 | 0 |
| `ma_energy_capex_commodity_standard` | `eval/sec_cases/outputs/multi_agent_judgment_memo_diagnostic/20260601_fin_agent_s6_s8_memo_language_v0_7_energy_deepseek_v0_3` | pass | expanded | 10,643 | 4,775 | 0 |

Aggregate:

- Case pass: `4/4`.
- Memo route pass: `4/4`.
- Verifier pass: `4/4`.
- Fallback: `0/4`.
- Repair attempts: `0`.
- Total tokens across accepted runs: `73,146`.

## Diagnosis

- The first NVDA/AMD attempts failed because English ClaimCard prose entered zh-CN memo claims, and the previous numeric-fidelity fallback could replace Chinese model prose with English source claims.
- The energy attempts failed because source-boundary enum text remained English and numeric range parsing did not treat `$14.5-$15.5B` as equivalent to `145-155亿美元`.
- Both were contract/normalizer issues, not evidence coverage issues.

## Decision

Proceed with v0.7 response-language contract for S6-S8. Next validation should run full-chain and multi-turn surfaces with Chinese rendered answer checks.
