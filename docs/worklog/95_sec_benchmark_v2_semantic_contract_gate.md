# SEC Benchmark v2 Semantic Contract Gate Audit

## Summary

Date: 2026-05-19

This entry closes the validator-first step after the six-case v2 pilot run. A
new manifest-aware v2 semantic contract gate now runs inside
`run_sec_benchmark_post_gates.py`. It checks the v2 failure tags that were
previously only documented in the manifest and worklog:

- `entity_bleed_between_peers`
- `proxy_as_direct_metric`
- `non_comparable_metric_comparison`
- `prior_period_as_target_value`
- `percentage_change_as_absolute_value`
- `source_policy_violation`

The gate is active only when a case declares the relevant failure type, has a
peer-comparison shape, has proxy/percentage/period-change ledger rows, or is an
anti-hallucination source-policy trap. Other cases are skipped explicitly.

## Governance

- Hypothesis: before adding more v2 cases, the existing deterministic
  post-gates should emit machine-readable failures for v2 semantic contracts
  rather than relying on manual review notes.
- Decision target: the current v2 pilot must still pass post-gates when the new
  semantic gate is enabled, and the report must expose active checks and
  per-case warnings/failures.
- Ceiling: this validates the six-case pilot and the new gate wiring only. It
  does not prove coverage for all future v2 case types.
- Baseline: previous v2 pilot `contractfix4` post-gates passed without these
  semantic-contract checks.
- Stop condition: any new hard failure on the pilot must be investigated as a
  gate bug, output contract bug, or real model/output issue before expanding
  v2.
- Decision label: diagnostic-only proceed.

## Work Completed

- Added `scripts/validate_sec_benchmark_v2_semantic_contracts.py`.
- Integrated the new gate into `scripts/run_sec_benchmark_post_gates.py`.
- Added `--skip-v2-semantic-contract-gate` for case-filtered or legacy runs.
- Reused existing manifest fields, answer schema, supporting metric/evidence
  IDs, and exact-value ledger roles.
- Fixed an initial false positive in percentage target-value checking: prose
  checks now only fire when a location actually mentions a percentage metric,
  so table-case aggregate drivers are not penalized for carrying both revenue
  and gross-margin metric IDs.

## Results

Standalone semantic-gate smoke:

- output:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_v2_semantic_gate_smoke/sec_benchmark_v2_semantic_contract_gate.json`
- `can_enter_gate=true`
- case count: 6
- checked: 5
- pass: 5
- fail: 0
- skip: 1
- active checks:
  - `entity_bleed_between_peers`: 1
  - `non_comparable_metric_comparison`: 1
  - `percentage_change_as_absolute_value`: 1
  - `proxy_as_direct_metric`: 2
  - `source_policy_violation`: 1

Full post-gates with the new semantic gate enabled:

- summary:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates_v2semantic/sec_benchmark_post_gates_summary.json`
- `v2_semantic_contract_gate_pass=true`
- `qwen_answer_ratio=1.0`
- trap, answer-ledger, metric-role, table-cell, named-fact,
  ledger-missing consistency, caveat/claim, answer-vs-Judgment-Plan, and
  ledger-unit gates all still pass.

## Findings

- The current pilot still passes under the expanded gate set.
- The gate records three `one_sided_peer_comparison_support` warnings on the
  GOOGL/META advertising comparison. These are not hard entity-bleed failures
  because no single-entity claim cites the other entity, and both companies are
  supported elsewhere in the answer. They are useful pressure for the next
  Answer Plan/output organization step: local peer-comparison sentences should
  carry support for both peers or be split into separate per-peer statements.
- `prior_period_as_target_value` is implemented but was not activated by the
  current v2 pilot because the reviewed pilot ledger has no
  `period_change_amount` rows.

## Decision

The validator-first step is complete enough to unblock a small next v2 case
batch. Do not jump to a full 40-case benchmark yet. The next batch should be
chosen to exercise:

- one case with actual `period_change_amount` rows;
- one peer-comparison case where both peers need local support in the same
  conclusion;
- one trap or not-found case that is not the Microsoft/YouTube pattern.

## Safety Notes

- No cloud inference was rerun in this step.
- No credentials were written to logs.
- Existing RTX 4090 and RTX 5090 hardware profiles were not changed.
