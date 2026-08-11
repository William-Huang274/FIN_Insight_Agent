# SEC Benchmark v2 Full40 Partial Review Gate

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry records the follow-up after the full40 seed-route build: creating a
partial approval file for the cases that already have reviewed gold artifacts
or trap approval, generating review candidates for the remaining seed cases,
and confirming that the full40 mainline gate is still correctly blocked.

## Work Completed

- Added partial approval builder:
  `scripts/build_sec_benchmark_v2_full40_partial_review_approval.py`.
- Generated partial review approval:
  `reports/quality/sec_benchmark_v2_full40_partial_review_approval.json`.
- Generated full40 review candidate files:
  - `eval/sec_cases/full40_review_candidates_context/`
  - `eval/sec_cases/full40_review_candidates_facts/`
- Generated candidate report:
  `reports/quality/sec_benchmark_v2_full40_seed_review_candidates_report.json`.
- Generated triage report:
  `reports/quality/sec_benchmark_v2_full40_seed_review_triage.json`.
- Rebuilt `eval/sec_cases/test_cases_v2_full40_seed.jsonl` after tightening
  numeric-check metric families for new seed cases.

## Gate Results

Approved case-filtered reviewed-gold gate:

- Report:
  `reports/quality/sec_benchmark_v2_full40_reviewed22_mainline_gold_gate.json`
- Result: `can_enter_gate=true`
- Status counts: `pass=22`
- Blockers: none

Approved trap-smoke gate:

- Report:
  `reports/quality/sec_benchmark_v2_full40_trap6_smoke_gate.json`
- Result: `can_enter_gate=true`
- Status counts: `pass=6`
- Blockers: none

Full40 negative control:

- Report:
  `reports/quality/sec_benchmark_v2_full40_all40_mainline_gold_gate_expected_blocked.json`
- Result: `can_enter_gate=false`
- Status counts: `pass=28`, `fail=12`
- Blocker types:
  - `gold_context_missing=12`
  - `manual_review_not_mainline_approved=12`
  - `reviewed_gold_facts_missing=5`

## Review Triage

The 12 seed-only non-trap cases are still blocked from full scored inference.

Triage summary:

- `text_candidate_needs_manual_trim=7`
- `numeric_candidate_reuse_existing_reviewed_facts=3`
- `numeric_candidate_noisy_needs_manual_fact_build=2`

Important numeric finding:

- `AMZN_ADS_SUBSCRIPTION_AWS_MIX_2023_2025_001` initially used an overly broad
  `revenue` metric family in the seed manifest. The builder now uses
  `cloud_revenue` and `advertising_revenue` separately.
- `ADBE_REVENUE_DEFERRED_REVENUE_TABLE_2023_2025_001` needs a direct
  total-revenue fact build; candidate facts include cost-of-revenue noise.
- `AMZN_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001` and
  `MSFT_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001` should reuse reviewed
  `CAPEX_FCF_TABLE_2023_2025_DIAG_001` cash-flow and PPE-purchase facts rather
  than raw ObjectBM25 candidates.

## Decision

The full40 route has advanced from seed-only readiness to a clearer partial
review boundary:

- 22 reviewed non-trap cases are approved for case-filtered mainline gold gates.
- 6 trap cases are approved for case-filtered trap-smoke gates.
- All 40 cases are not approved for full mainline scored Qwen inference.

Do not run full40 BGE-M3 + Judgment Plan + RTX 5090 Qwen9B until the 12 seed
non-trap blockers are resolved.

## Next Step

Build reviewed context/facts for the 12 seed-only cases in two batches:

1. Promote or trim the 7 text-heavy candidates into compact reviewed context.
2. Reuse existing reviewed facts where safe for 3 numeric candidates, and build
   fresh exact facts for the 2 noisy numeric candidates.

After those pass gold gates, build the full40 exact-value ledger and Judgment
Plan seed, then run the full40 BGE-M3 + Qwen route.

## Safety Notes

- No password, private token, SSH credential, or temporary credential is written
  here.
- No model inference was run in this step.
