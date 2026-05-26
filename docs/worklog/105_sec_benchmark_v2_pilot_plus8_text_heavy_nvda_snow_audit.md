# SEC Benchmark v2 Pilot Plus8 Text-Heavy NVDA/SNOW Audit

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry starts the v2 pilot plus8 expansion. The target cases are
`NVDA_DATACENTER_2023_2025_001` and `SNOW_RISK_2023_2025_001`, both reviewed
text-heavy cases with no exact-value target facts. The goal is to test
SEC-only qualitative support, year-specific disclosure separation, no-ledger
numeric restraint, and risk-language calibration after the plus7 trap run.

## Governance

- Hypothesis: after plus7 passed the Azure gross-margin not-found trap, the
  next useful diagnostic is whether the BGE-M3 + Judgment Plan + Qwen9B route
  can answer reviewed text-heavy cases without inventing unsupported numeric,
  market-share, stock, customer-count, NRR, or retention facts.
- Decision target: plus8 artifacts must pass readiness, reviewed-gold mainline
  gate, trap-smoke for the unchanged traps, exact-value ledger build, and
  ledger-unit gates. The full route must then pass with `qwen_answer_ratio=1.0`
  for non-trap eligible cases, no non-trap fallback, no ledger repair, and
  active post-gates including abstract judgment, caveat/claim, v2 semantic,
  answer-vs-plan where a plan exists, named-fact support, metric-source
  grounding, and ledger-unit.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus7 BGE-M3 + Judgment Plan + RTX 5090 Qwen9B run passed final
  post-gates with 11 non-trap Qwen answers and 2 contract fallback traps.
- Split/leakage guard: the two new cases reuse existing reviewed text context
  and reviewed no-numeric-fact files. They add no exact-value ledger rows.
- Stop condition: any readiness failure, reviewed-gold gate failure,
  unsupported text claim, required caveat miss, source-policy failure, abstract
  rubric failure, non-trap fallback, ledger repair, or post-gate failure blocks
  further expansion.
- Decision label: diagnostic-only proceed.

## Planned Work

- Build plus8 manifest and partial approval with
  `scripts/build_sec_benchmark_v2_pilot_plus8_reviewed_gold.py`.
- Run local deterministic plus8 gates.
- If gates pass, sync plus8 artifacts to the RTX 5090 remote workspace and run
  BGE-M3 pipeline-context, trace-aware Judgment Plan, Qwen9B synthesis, and
  post-gates.

## Work Completed

- Added `scripts/build_sec_benchmark_v2_pilot_plus8_reviewed_gold.py`.
- Added `NVDA_DATACENTER_2023_2025_001` and `SNOW_RISK_2023_2025_001` to
  `eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl`.
- Reused existing reviewed text artifacts:
  - NVDA: 12 reviewed context rows, 0 target numeric facts.
  - SNOW: 9 reviewed context rows, 0 target numeric facts.
- Ran local and remote deterministic gates, then the full remote BGE-M3 +
  Judgment Plan + RTX 5090 Qwen9B pipeline.

## Results

- Artifact/gate setup:
  - plus8 manifest: 15 total cases, 13 reviewed non-trap cases, 2 trap cases.
  - exact-value ledger remains 104 rows.
  - readiness: 15/15 pass
  - reviewed-gold mainline: 13/13 pass
  - trap smoke: 2 pass, 13 skipped
  - ledger-unit: 104/104 pass
- BGE-M3 trace:
  - 15/15 cases reached `context_prepared`
  - final selector: `BAAI/bge-reranker-v2-m3`
  - BM25/ObjectBM25/requirement BM25 used only as candidate generators
- Judgment Plan:
  - 11 plans, 15 drivers, 2 proxy drivers
  - 3 plans with downgrades
  - gate 11/11 pass
  - 6 non-blocking `supporting_evidence_id_not_seen_in_trace` warnings
- Qwen synthesis:
  - `answered_qwen9b`: 13
  - `answered_contract_fallback`: 2 traps
  - Qwen ledger repairs: 0
  - model load: 38.3242 sec
  - total synthesis elapsed: 619.6674 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 57 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0, warning count 1
  - ledger-missing consistency: pass
  - abstract judgment: pass, 3 checked cases, 12/12 required dimensions
  - caveat/claim: pass, 37/37 required caveats, 0/43 disallowed violations
  - v2 semantic contract: pass, 14/14 checked cases
  - answer-vs-Judgment-Plan: pass, 11/11 checked cases
  - metric-source grounding: pass, 13 pass, 2 skipped traps, 162 metric refs
  - ledger-unit: pass, 104/104

## Key Artifacts

- Full model-run ledger:
  `reports/model_runs/20260520_sec_benchmark_v2_pilot_plus8_text_heavy_nvda_snow_bge_m3_qwen9b_5090.md`
- Final post-gate summary:
  `reports/quality/local_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`
- BGE-M3 trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_context_bge_m3_top160_object8_local`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json`
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`

## Decision

plus8 is accepted as a diagnostic-only reviewed expansion. The current v2
pilot now contains the staged MVP-extension batch: 15 total cases, 13 reviewed
non-trap cases, and 2 pipeline-only traps. The next sound step is an MVP
freeze-readiness coverage review before adding more cases or claiming a broader
v2 benchmark.

## Safety Notes

- No password, private token, or temporary credential should be written to this
  worklog or model-run records.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
