# SEC Benchmark v2 Full40 Seed Route

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry records the first full-v2 route step after plus8 post-freeze
hardening: building a 40-case seed manifest with explicit target buckets and
running deterministic readiness gates. This is a seed/design gate, not a full
mainline scored benchmark approval.

## Governance Gate

- Hypothesis: expanding from the plus8 MVP diagnostic pack to a governed
  40-case seed will expose source, schema, retrieval, and coverage risks before
  spending GPU time on full BGE-M3 plus Qwen runs.
- Decision target: 40/40 manifest readiness pass with no hard failures, target
  bucket counts satisfied, and reviewed-gold context smoke passing for all cases
  that claim reviewed artifacts.
- Ceiling: the local SEC universe still contains only 10 companies
  (`AAPL`, `ADBE`, `AMD`, `AMZN`, `GOOGL`, `META`, `MSFT`, `NVDA`, `PANW`,
  `SNOW`). Only 22 full40 cases have reviewed-gold context/facts available.
  Therefore the 40-case seed can support readiness/retrieval pressure testing,
  but cannot support a full mainline scored BGE-M3 + Qwen benchmark claim yet.
- Baselines: frozen plus8 MVP diagnostic pack, plus8 expanded abstract-rubric
  gate, and plus8 active gold-vs-pipeline parity gate.
- Split and leakage guard: no new model outputs or thresholds are tuned on this
  step. The build only creates a manifest and deterministic reports from
  existing SEC filings, reviewed artifacts, and seed case definitions.
- Stop conditions: stop before full scored Qwen if any full40 case has schema,
  filing, source, section, or structured-metric hard failures; stop before
  mainline claims until seed-only non-trap cases have reviewed context/facts and
  trap seeds have explicit approval.
- Efficiency gate: deterministic local build/readiness should complete in
  minutes; no RTX 5090 inference is allowed for mainline full40 until review
  blockers are cleared.
- Decision label: `proceed_to_seed_readiness_only`.

## Work Completed

- Added builder:
  `scripts/build_sec_benchmark_v2_full40_seed.py`.
- Generated manifest:
  `eval/sec_cases/test_cases_v2_full40_seed.jsonl`.
- Generated build report:
  `reports/quality/sec_benchmark_v2_full40_seed_build_report.json`.
- Ran full40 readiness plus BM25 smoke:
  `reports/quality/sec_benchmark_v2_full40_seed_readiness_bm25_smoke.json`.
- Ran reviewed-gold context smoke for the 22 reviewed-gold cases:
  `reports/quality/sec_benchmark_v2_full40_reviewed22_context_smoke_gate.json`.

## Full40 Composition

Target bucket counts are satisfied:

| Bucket | Count |
|---|---:|
| L2 single-company single-year summary | 8 |
| L3 single-company cross-year trend | 10 |
| Numeric/table cell gold | 10 |
| L4 two-company peer comparison | 6 |
| Trap/not-found/source-policy | 6 |

Reviewed status counts:

| Status | Count |
|---|---:|
| reviewed_gold_available | 22 |
| pipeline_trap | 4 |
| pipeline_trap_seed | 2 |
| seed_needs_review | 12 |

The builder intentionally defers two reviewed legacy cases from the full40
target manifest:

- `CLOUD_PROFITABILITY_2023_2025_DIAG_001`: broad AMZN/GOOGL/MSFT comparison
  has known disclosure asymmetry; plus8 already split this into AMZN/GOOGL
  comparable cloud and MSFT cloud-proxy cases.
- `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`: 3-company recurring-quality
  comparison mixes platform and SaaS disclosure definitions and needs a
  narrower split before full-v2 promotion.

## Results

Full40 seed build:

- case count: 40
- target bucket counts: passed
- duplicate case IDs: none
- BGE-M3 policy preserved: final context selector is `BAAI/bge-reranker-v2-m3`;
  BM25 remains candidate generation only.

Readiness plus BM25 smoke:

- `case_count=40`
- `pass_count=40`
- `fail_count=0`
- hard failure types: none
- warning types: `gold_context_missing=12`

Reviewed-gold context smoke:

- case filter: 22 cases with `reviewed_gold_available`
- `can_enter_gate=true`
- `status_counts={"pass": 22}`
- blocker types: none
- warning types: none

## Decision

The full40 seed/design gate passes. It is now valid to use
`eval/sec_cases/test_cases_v2_full40_seed.jsonl` for source coverage,
retrieval, schema, and review-planning work.

It is not valid yet to claim a full40 mainline scored benchmark, because 12
non-trap cases still need reviewed gold context/facts before full BGE-M3 +
Judgment Plan + Qwen inference.

## Next Step

1. Review/approve the 12 seed-only non-trap cases.
2. Build the full40 exact-value ledger and Judgment Plan seed only after review
   blockers are cleared.
3. Run full40 BGE-M3 + Judgment Plan + RTX 5090 Qwen9B and deterministic
   post-gates after the reviewed artifacts exist.
4. After full40 passes as a reviewed pipeline, expand beyond the current
   10-company SEC universe by updating `eval/sec_cases/companies.yaml`,
   downloading filings, rebuilding manifests/evidence/structured objects, and
   rebuilding BM25/ObjectBM25 indexes.

## Safety Notes

- No password, private token, SSH credential, or temporary credential is written
  here.
- No model inference was run in this step.
