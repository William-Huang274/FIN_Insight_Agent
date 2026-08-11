# SEC Benchmark v2 Pilot Plus8 MVP Freeze-Readiness Review

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry records the freeze-readiness review for the v2 pilot plus8 pack after
the NVDA/SNOW text-heavy expansion and full BGE-M3 + Judgment Plan + RTX 5090
Qwen9B run. The review is a governance checkpoint before adding more cases.

## Governance

- Hypothesis: plus8 has enough reviewed, machine-gated coverage to freeze as an
  MVP diagnostic pack, but not enough breadth to claim a full v2 benchmark.
- Decision target: freeze only if readiness, reviewed/trap/ledger gates, BGE-M3
  context preparation, Judgment Plan validation, Qwen answer ratio, and all
  active post-gates pass with no non-trap fallback or ledger repair.
- Ceiling: 15 cases is an MVP diagnostic pack ceiling. The full v2 target
  remains 40 high-quality cases.
- Baseline: plus8 completed with 15 total cases, 13 reviewed non-trap cases, 2
  pipeline-only traps, and a 104-row exact-value ledger.
- Split/leakage guard: this review uses the frozen plus8 manifest and existing
  post-gate artifacts. It does not tune prompts, add cases, or rerun synthesis.
- Stop condition: a failed active gate, non-trap fallback, ledger repair,
  source-policy violation, or uncovered required caveat would block freeze.
- Decision label: proceed to MVP diagnostic freeze only.

## Work Completed

- Audited plus8 manifest coverage, deterministic gates, BGE-M3 trace, Judgment
  Plan gate, Qwen usage, and final post-gate summary.
- Created a machine-readable review report:
  `reports/quality/sec_benchmark_v2_pilot_plus8_mvp_freeze_readiness_review.json`.
- Classified the pack as frozen-MVP-ready but still blocked from full v2
  benchmark claims.

## Results

- Coverage:
  - 15 cases total: 13 reviewed non-trap cases and 2 pipeline-only traps.
  - Levels: L1=2, L2=1, L3=9, L4=3.
  - 15 unique task types.
  - 10-company coverage: AAPL, ADBE, AMD, AMZN, GOOGL, META, MSFT, NVDA, PANW,
    and SNOW.
  - 11 numeric cases, 2 text-heavy no-ledger cases, and 2 traps.
- Deterministic gates:
  - readiness 15/15 pass.
  - reviewed-gold mainline 13/13 pass.
  - trap smoke 2 pass, 13 skipped.
  - ledger-unit 104/104 pass.
- Pipeline route:
  - BGE-M3 context preparation completed for 15/15 cases.
  - Judgment Plan gate passed 11/11 plans with 15 drivers.
  - Qwen usage: 13/13 eligible non-trap outputs answered by Qwen, 2 traps
    handled by contract fallback, and 0 ledger repairs.
- Active post-gates:
  - qwen answer ratio 1.0.
  - trap, answer-ledger, metric-role term, table-cell, named-fact,
    ledger-missing consistency, abstract judgment, caveat/claim, v2 semantic,
    answer-vs-plan, metric-source grounding, and ledger-unit gates all passed.

## Accepted Warnings And Limits

- Judgment Plan gate has 6 non-blocking
  `supporting_evidence_id_not_seen_in_trace` warnings.
- Named-fact support has 1 non-blocking summary warning while unsupported token
  count remains 0.
- v2 semantic contract has 6 non-blocking one-sided peer-comparison support
  warnings that should guide later answer organization.
- Gold-vs-pipeline comparison is skipped by design in the plus8 pipeline-only
  scored run.
- Abstract-judgment rubric coverage is only 3 cases.
- The two text-heavy no-ledger cases do not receive Judgment Plans under the
  current ledger-driven plan builder.

## Decision

plus8 can be frozen as an MVP diagnostic pack. It should not be described as a
full v2 benchmark, should not enter full mainline scored testing, and should not
be expanded with more cases until the freeze decision is accepted or explicitly
overridden.

The next sound step is to create a plus8 MVP freeze handoff or version alias
that pins the manifest, BGE-M3 route, Judgment Plan behavior, Qwen output, and
post-gate artifact set.

## Safety Notes

- No password, private token, or temporary credential is written here.
- BGE-M3 remains the final context selector for the frozen route.
- BM25, ObjectBM25, and requirement BM25 remain candidate generators only.
