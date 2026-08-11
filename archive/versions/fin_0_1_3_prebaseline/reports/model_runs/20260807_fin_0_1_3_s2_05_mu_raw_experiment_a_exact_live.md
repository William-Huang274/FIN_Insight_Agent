# Model Run: 20260807_MU_S2_05_same_evidence_raw_Experiment_A_exact_live_r1

## Summary

- Purpose: measure DeepSeek Pro's autonomous MU financial-research reasoning on the frozen same-evidence pack.
- Status: `raw chain complete / hidden-scoreable / quality fail / no business promotion`.
- Run type: inference and post-hoc evaluation.
- Timestamp: 2026-08-07 01:27:51Z.
- Environment: local Windows workspace; network used only by the authorized Provider calls.

## Code And Command

- Execution commit: `ddbaf2cde43b171f8956d8625bb16b117a62c208`.
- Entry point: `scripts/releases/run_fin_ia_0_1_3_s2_05_experiment_a.py`.
- Runtime policy: `configs/runtime/fin_ia_0_1_3_s2_05_experiment_a_runtime_policy_v1_0.json`.
- Admission: one Git-ignored MU admission, exact-once consumed.
- Provider/model: DeepSeek / `deepseek-v4-pro`, temperature 0, thinking disabled.

## Inputs

- Case: MU, as-of 2026-08-06.
- Frozen input digest: `55b47486...61688`; MU case digest: `c11bbfab...6393`.
- Input surface: 11 Evidence, 3 derived Numeric and 4 explicit gaps.
- Tools/search: none. DELL raw/correction and hidden Gold were not visible.
- Leakage guard: same production runtime, policy and model-visible blind input used for DELL.

## Outputs And Efficiency

- Lead / Specialist / Synthesis / Writer / Verifier: `1 / 6 / 1 / 1 / 1`.
- Calls/captures: `10/10`; all `ok/stop`.
- Input/output/total tokens: `32,372 / 7,019 / 39,391`.
- Estimated policy-rate cost: USD `0.0313555`.
- Retry/fallback/supervisor/business promotion: `0/0/0/0`.
- Observed wall time: approximately 97 seconds.
- Terminal digest: `b3dd5a26...aba27`; exact-once receipt: `afadd614...b8b7`.
- Raw captures are private, Git-ignored and passed the credential-pattern scan.

## Result

The model completed the entire typed chain. It produced six MU-specific research units, linked HBM product progress to memory pricing, cash flow, valuation, gaps and counter-thesis, and generated a readable case-local Writer output.

The candidate nevertheless failed financial-research quality. Final evaluator v1.3 found `6 L1 / 2 L2 / 14 L3`:

- trailing/static P/E was recast as a single-quarter earnings multiple in two surfaces;
- the combined deposits-and-financial-commitments scope was recast as cash/refundable prepayment in three surfaces;
- average FCF margin was used as marginal revenue sensitivity once;
- Verifier missed both the financial-semantic failures and the material-failure state;
- all six Specialists omitted explicit counterevidence;
- six thresholds and two historical valuation references were uncalibrated.

Runtime evaluator v1.1 initially over-reported `10 L1` because it did not recognize approximate/lower-bound unit families. v1.2 removed that noise but also showed the semantic-evaluator gap. v1.3 added general accounting/valuation invariants and was replayed on the unchanged DELL and MU captures. DELL remained `2 L1 / 1 L2 / 23 L3`; MU settled at `6 / 2 / 14`.

## Experiment Governance

- Hypothesis: MU may show different reasoning strengths/failures from DELL under the same visible contract.
- Decision target: complete raw candidate with L1/L2 and hidden-Gold diagnostic coverage, without supervisor contamination.
- Result: raw measurement complete but quality fail.
- Formal score: not issued because L1/L2 failed and raw output is not a final verifier-bound product packet.
- Mainline decision: preserve raw, compile 22-row correction ledger, do not correct MU before the three-case raw campaign completes.

## Caveats And Next Step

- This run measures reasoning against the frozen pack; it does not independently re-prove the pack's external source truth.
- No corrected candidate, paired assessment, qualified-human acceptance, Workbench delivery or release claim was created.
- NVDA may only enter a separate authority decision. No automatic next-case or supervisor action is authorized.
