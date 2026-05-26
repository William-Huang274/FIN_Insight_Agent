# SEC Benchmark v2 Pilot Plus6 MSFT Cloud Proxy Reviewed-Gold Audit

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry starts the v2 pilot plus6 expansion. The target case is
`MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001`, built as a Microsoft-only split from
the reviewed broad cloud-profitability artifact. The case tests whether the
pipeline can use Microsoft Cloud revenue and Microsoft Cloud gross margin as
broad proxy evidence without treating them as exact Azure revenue, exact Azure
gross margin, or cloud segment operating income.

## Governance

- Hypothesis: after plus5 passed the clean AMZN/GOOGL comparable segment case,
  the next useful diagnostic is the Microsoft disclosure-boundary counterpart:
  Microsoft Cloud is a broad proxy metric and must not be compared one-for-one
  with AWS/Google Cloud segment operating income.
- Decision target: plus6 reviewed artifacts must pass readiness, reviewed-gold
  mainline, trap-smoke, exact-value ledger, and ledger-unit gates before any
  cloud Qwen run. If those pass, the full BGE-M3 pipeline-context route must
  pass with `qwen_answer_ratio=1.0`, no non-trap fallback, no ledger repair, and
  active post-gates including caveat/claim, v2 semantic, answer-vs-plan,
  metric-source grounding, and ledger-unit.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus5 AMZN/GOOGL BGE-M3 + Judgment Plan + RTX 5090 Qwen9B run
  passed final `contractfix1` post-gates.
- Split/leakage guard: source facts and context are copied only from reviewed
  `CLOUD_PROFITABILITY_2023_2025_DIAG_001` rows where ticker is MSFT; AMZN and
  GOOGL segment rows are excluded by construction.
- Stop condition: any artifact coverage mismatch, non-MSFT row leakage,
  reviewed gate failure, ledger-unit failure, non-trap fallback, semantic hard
  failure, caveat/claim violation, answer-vs-plan failure, or metric-source
  grounding failure blocks further expansion.
- Decision label: diagnostic-only proceed.

## Planned Work

- Build plus6 manifest, reviewed context/facts, partial approval, and build
  report with `scripts/build_sec_benchmark_v2_pilot_plus6_reviewed_gold.py`.
- Run local deterministic plus6 gates.
- If gates pass, sync plus6 artifacts to the RTX 5090 remote workspace and run
  BGE-M3 pipeline-context, Judgment Plan, Qwen9B synthesis, and post-gates.

## Work Completed

- Added `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001` to
  `eval/sec_cases/test_cases_v2_pilot_plus6_seed.jsonl`.
- Split reviewed context/facts from `CLOUD_PROFITABILITY_2023_2025_DIAG_001`
  using strict MSFT-only filtering:
  - reviewed context:
    `eval/sec_cases/reviewed_gold_context/MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001.jsonl`
  - reviewed facts:
    `eval/sec_cases/reviewed_gold_facts/MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001.json`
- Built plus6 partial approval, build report, readiness report, reviewed-gold
  mainline gate, trap-smoke gate, exact-value ledger, and ledger-unit gate.
- Synced the plus6 artifact/code delta to the remote RTX 5090 workspace, ran
  BGE-M3 pipeline-context retrieval, built trace-aware Judgment Plans, ran
  Qwen9B synthesis through vLLM, and pulled the final post-gates back locally.

## Results

- Reviewed artifact:
  - plus6 manifest: 12 total cases, 11 reviewed non-trap cases, 1 trap case.
  - new MSFT case: 6 reviewed facts and 7 reviewed context rows.
  - split policy: strict MSFT subset excluding AMZN/GOOGL segment rows.
  - metric families: `cloud_revenue_proxy`, `gross_margin`.
  - comparability caveat rows: 1.
- Deterministic reviewed gates:
  - readiness: 12/12 pass
  - reviewed-gold mainline: 11/11 pass
  - trap smoke: 1 pass, 11 skipped
  - exact-value ledger: 104 rows
  - ledger-unit: 104/104 pass
- BGE-M3 trace:
  - 12/12 cases reached `context_prepared`
  - final selector: `BAAI/bge-reranker-v2-m3`
  - BM25/ObjectBM25/requirement BM25 used only as candidate generators
- Judgment Plan:
  - 11 plans, 15 drivers, 2 proxy drivers
  - 3 plans with downgrades
  - gate 11/11 pass
  - 6 non-blocking `supporting_evidence_id_not_seen_in_trace` warnings
- Qwen synthesis:
  - `answered_qwen9b`: 11
  - `answered_contract_fallback`: 1 trap
  - Qwen ledger repairs: 0
  - model load: 52.3665 sec
  - total synthesis elapsed: 570.7566 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 57 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0, warning count 1
  - ledger-missing consistency: pass
  - abstract judgment: pass, 4/4 required dimensions on the checked case
  - caveat/claim: pass, 28/28 required caveats, 0/34 disallowed violations
  - v2 semantic contract: pass, 11/11 checked cases
  - answer-vs-Judgment-Plan: pass, 11/11 checked cases
  - metric-source grounding: pass, 11 checked cases, 43 checked locations,
    162 metric references
  - ledger-unit: pass, 104/104

## Key Artifacts

- Full model-run ledger:
  `reports/model_runs/20260520_sec_benchmark_v2_pilot_plus6_msft_cloud_proxy_bge_m3_qwen9b_5090.md`
- Final post-gate summary:
  `reports/quality/local_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`
- BGE-M3 trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_context_bge_m3_top160_object8_local`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus6_judgment_plans_trace_seed.json`
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`

## Decision

plus6 is accepted as a diagnostic-only reviewed expansion. The pipeline can
move to the Azure gross-margin metric-scope not-found trap, but the current
evidence still does not justify calling v2 a frozen MVP pack.

## Safety Notes

- No password, private token, or temporary credential should be written to this
  worklog or model-run records.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
