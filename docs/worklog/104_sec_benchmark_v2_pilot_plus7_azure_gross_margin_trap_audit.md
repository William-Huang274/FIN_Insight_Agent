# SEC Benchmark v2 Pilot Plus7 Azure Gross-Margin Trap Audit

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry starts the v2 pilot plus7 expansion. The target case is
`MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001`, a pipeline-only
metric-scope source-policy trap. It tests whether the system refuses exact
Azure gross margin when Microsoft SEC evidence only supports broader Microsoft
Cloud proxy disclosures.

## Governance

- Hypothesis: after plus6 passed the Microsoft Cloud proxy case, the useful
  next diagnostic is the adjacent not-found trap: the pipeline must say exact
  Azure gross margin is not disclosed and must not substitute Microsoft Cloud
  gross margin as exact Azure gross margin.
- Decision target: plus7 artifacts must pass readiness, reviewed-gold mainline
  for the unchanged plus6 non-trap set, trap-smoke with both traps, exact-value
  ledger, and ledger-unit gates. The full route must then pass with
  `qwen_answer_ratio=1.0` for all non-trap cases, no non-trap fallback, no
  ledger repair, and active post-gates including caveat/claim, v2 semantic,
  answer-vs-plan, metric-source grounding, and ledger-unit.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus6 Microsoft Cloud proxy BGE-M3 + Judgment Plan + RTX 5090
  Qwen9B run passed final post-gates.
- Split/leakage guard: no new reviewed numeric facts enter the ledger; the new
  trap is pipeline-only and has no gold context requirement.
- Stop condition: any trap refusal failure, required-not-found failure,
  caveat/claim violation, source-policy hard failure, non-trap fallback, ledger
  repair, semantic hard failure, answer-vs-plan failure, or metric-source
  grounding failure blocks further expansion.
- Decision label: diagnostic-only proceed.

## Planned Work

- Build plus7 manifest and partial approval with
  `scripts/build_sec_benchmark_v2_pilot_plus7_reviewed_gold.py`.
- Add a deterministic `required_not_found_missing` semantic check so the new
  trap is not only covered by generic trap smoke.
- Run local deterministic plus7 gates.
- If gates pass, sync plus7 artifacts to the RTX 5090 remote workspace and run
  BGE-M3 pipeline-context, Judgment Plan, Qwen9B synthesis, and post-gates.

## Work Completed

- Added `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001` to
  `eval/sec_cases/test_cases_v2_pilot_plus7_seed.jsonl`.
- Added `scripts/build_sec_benchmark_v2_pilot_plus7_reviewed_gold.py`.
- Added `required_not_found_missing` enforcement to
  `scripts/validate_sec_benchmark_v2_semantic_contracts.py`.
- Updated the contract trap answer path so the Azure gross-margin trap returns
  an explicit exact-metric not-found answer instead of a generic unsupported
  claim.
- Ran local deterministic gates, a two-trap contract microtest, then the full
  remote BGE-M3 + Judgment Plan + RTX 5090 Qwen9B pipeline.

## Results

- Artifact/gate setup:
  - plus7 manifest: 13 total cases, 11 reviewed non-trap cases, 2 trap cases.
  - new Azure trap: pipeline-context only; no reviewed gold context or facts.
  - exact-value ledger: 104 rows.
  - readiness: 13/13 pass
  - reviewed-gold mainline: 11/11 pass
  - trap smoke: 2 pass, 11 skipped
  - ledger-unit: 104/104 pass
- Local trap contract microtest:
  - trap-smoke: 2/2 pass
  - caveat/claim: 3/3 required caveats, 0/5 disallowed violations
  - v2 semantic: `required_not_found_missing`, `source_policy_violation`, and
    `proxy_as_direct_metric` checks active with no failures
- BGE-M3 trace:
  - 13/13 cases reached `context_prepared`
  - final selector: `BAAI/bge-reranker-v2-m3`
  - BM25/ObjectBM25/requirement BM25 used only as candidate generators
- Judgment Plan:
  - 11 plans, 15 drivers, 2 proxy drivers
  - 3 plans with downgrades
  - gate 11/11 pass
  - 6 non-blocking `supporting_evidence_id_not_seen_in_trace` warnings
- Qwen synthesis:
  - `answered_qwen9b`: 11
  - `answered_contract_fallback`: 2 traps
  - Qwen ledger repairs: 0
  - model load: 39.3596 sec
  - total synthesis elapsed: 552.7836 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 57 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0, warning count 1
  - ledger-missing consistency: pass
  - abstract judgment: pass, 4/4 required dimensions on the checked case
  - caveat/claim: pass, 30/30 required caveats, 0/37 disallowed violations
  - v2 semantic contract: pass, 12/12 checked cases, including
    `required_not_found_missing=1`
  - answer-vs-Judgment-Plan: pass, 11/11 checked cases
  - metric-source grounding: pass, 11 checked cases, 43 checked locations,
    162 metric references
  - ledger-unit: pass, 104/104

## Key Artifacts

- Full model-run ledger:
  `reports/model_runs/20260520_sec_benchmark_v2_pilot_plus7_azure_gross_margin_trap_bge_m3_qwen9b_5090.md`
- Final post-gate summary:
  `reports/quality/local_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`
- BGE-M3 trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_context_bge_m3_top160_object8_local`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus7_judgment_plans_trace_seed.json`
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`

## Decision

plus7 is accepted as a diagnostic-only reviewed/trap expansion. The benchmark
can now move to the remaining text-heavy NVDA/SNOW risk cases or to an MVP
freeze-readiness coverage review. It is still not a full v2 benchmark.

## Safety Notes

- No password, private token, or temporary credential should be written to this
  worklog or model-run records.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
