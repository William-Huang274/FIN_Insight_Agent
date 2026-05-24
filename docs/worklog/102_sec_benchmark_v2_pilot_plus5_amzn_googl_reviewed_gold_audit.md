# SEC Benchmark v2 Pilot Plus5 AMZN/GOOGL Reviewed-Gold Audit

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry starts the v2 pilot plus5 expansion. The target case is
`AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001`, built as a strict
AMZN/GOOGL split from the reviewed broad cloud-profitability artifact. The run
must exclude Microsoft Cloud proxy rows so the case tests comparable cloud
segment revenue and operating income only.

## Governance

- Hypothesis: after plus4 passed BGE-M3 + Judgment Plan + Qwen9B post-gates, a
  clean AMZN/GOOGL peer case is the next useful diagnostic because it stresses
  entity separation, comparable metric scope, and segment operating-income
  interpretation without Microsoft disclosure asymmetry.
- Decision target: plus5 reviewed artifacts must pass readiness, reviewed-gold
  mainline, trap-smoke, exact-value ledger, and ledger-unit gates before any
  cloud Qwen run. If those pass, the full BGE-M3 pipeline-context route must
  pass with `qwen_answer_ratio=1.0`, no non-trap fallback, no ledger repair, and
  active post-gates including metric-source grounding.
- Ceiling: diagnostic-only staged expansion. This does not establish a full v2
  benchmark or MVP frozen pack.
- Baseline: plus4 BGE-M3 + Judgment Plan + RTX 5090 Qwen9B completed with all
  active post-gates passing.
- Split/leakage guard: source facts and context are copied only from reviewed
  `CLOUD_PROFITABILITY_2023_2025_DIAG_001` rows where ticker is AMZN or GOOGL;
  MSFT proxy and gross-margin rows are excluded by construction.
- Stop condition: any artifact coverage mismatch, MSFT row leakage, reviewed
  gate failure, ledger-unit failure, non-trap fallback, semantic hard failure,
  caveat/claim violation, answer-vs-plan failure, or metric-source grounding
  failure blocks further expansion.
- Decision label: diagnostic-only proceed.

## Planned Work

- Build plus5 manifest, reviewed context/facts, partial approval, and build
  report with `scripts/build_sec_benchmark_v2_pilot_plus5_reviewed_gold.py`.
- Run local deterministic plus5 gates.
- If gates pass, sync plus5 artifacts to the RTX 5090 remote workspace and run
  BGE-M3 pipeline-context, Judgment Plan, Qwen9B synthesis, and post-gates.

## Work Completed

- Added `scripts/build_sec_benchmark_v2_pilot_plus5_reviewed_gold.py`.
- Built plus5 reviewed artifacts:
  - `eval/sec_cases/test_cases_v2_pilot_plus5_seed.jsonl`
  - `eval/sec_cases/reviewed_gold_context/AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001.jsonl`
  - `eval/sec_cases/reviewed_gold_facts/AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus5_reviewed_gold_partial_approval.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus5_reviewed_gold_build_report.json`
- Re-ran local and remote deterministic reviewed gates before Qwen inference.
- Synced plus5 artifacts to the remote RTX 5090 workspace after a remote backup:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260520_v2_pilot_plus5_sync_before_qwen_003157.tgz`
- Ran BGE-M3 pipeline-context retrieval, trace-aware Judgment Plan, RTX 5090
  true-Qwen synthesis, and final post-gates.
- Pulled final remote outputs back into the local workspace.

## Results

- Reviewed artifact:
  - plus5 manifest: 11 total cases, 10 reviewed non-trap cases, 1 trap case.
  - new case facts/context: 12 reviewed facts and 12 reviewed context rows.
  - source split: AMZN/GOOGL rows only from `CLOUD_PROFITABILITY_2023_2025_DIAG_001`; Microsoft proxy rows excluded.
- Deterministic reviewed gates:
  - readiness: 11/11 pass
  - reviewed-gold mainline: 10/10 pass
  - trap smoke: 1 pass, 10 skipped
  - exact-value ledger: 98 rows
  - ledger-unit: 98/98 pass
- BGE-M3 trace:
  - 11/11 `context_prepared`
  - final selector: BGE-M3
  - candidate generators: BM25/ObjectBM25/requirement BM25
  - `bm25_only_allowed_for_this_run=false`
- Judgment Plan:
  - 10 plans
  - 14 drivers
  - 1 proxy driver
  - 2 plans with downgrades
  - gate 10/10 pass with 6 non-blocking trace-support warnings
- Qwen synthesis:
  - `answered_qwen9b`: 10
  - `answered_contract_fallback`: 1 trap
  - Qwen ledger repairs: 0
  - model load: 40.4665 sec
  - total synthesis elapsed: 528.1113 sec
- Final post-gates:
  - trap: pass
  - answer-ledger: pass, 53 exact-value hits
  - metric-role: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0
  - ledger-missing consistency: pass
  - abstract judgment: pass
  - caveat/claim: pass, 25/25 required caveats, 0/29 disallowed violations
  - v2 semantic contract: pass, 10/10 checked cases
  - answer-vs-Judgment-Plan: pass, 10/10 checked cases
  - metric-source grounding: pass, 10 checked cases, 42 checked locations, 159 metric references
  - ledger-unit: pass, 98/98
  - qwen answer ratio: 1.0

## Deterministic Contract Fix

The first post-gate run flagged one disallowed market-share pattern on the new
AMZN/GOOGL case. The answer said segment revenue growth does not represent
overall market share or customer growth, so this was a manifest allow-list false
positive rather than a model violation. The plus5 builder now allows
`does not represent` / `不代表` near the market-share pattern. Qwen was not
rerun; only deterministic post-gates were rerun into:

- `reports/quality/local_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates`

The initial failing post-gate directory is preserved separately for audit:

- `reports/quality/local_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates`

## Decision

Plus5 passes as a staged diagnostic expansion. The AMZN/GOOGL peer cloud case
is now a reviewed and pipeline-tested v2 case, with BGE-M3 still fixed as the
final pipeline-context selector.

Proceed next to `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001` from the Microsoft
subset of the broad cloud reviewed artifact. Keep it separate from AMZN/GOOGL
because Microsoft Cloud revenue and gross margin are broad proxy disclosures,
not directly comparable segment operating income.

## Safety Notes

- No password, private token, or temporary credential should be written to this
  worklog or model-run records.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
- This run remains diagnostic-only; it does not establish full v2 benchmark or
  MVP frozen-pack readiness.
