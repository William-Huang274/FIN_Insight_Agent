# R53-R60 P16 Quality Engineering / Online Eval Platform L4 Scope Artifacts

Date: 2026-06-30

## Scope

P16 closes the post-S10 `full_eval_observability_quality_engineering` gap at slice scope. It turns the R60 quality-engineering plan into SQL-final runtime rows: eval registry, node/full-chain gates, token/cost ledger, parser/retrieval/tool metrics, failure/gold/regression lifecycle, QA acceptance, sandbox regression, BudgetExceededGate, CI gate records, dashboard projections and reference governance.

P16 is not a sustained production monitoring window and does not configure a CI/CD provider or polished frontend eval dashboard.

## Implemented Artifacts

- `src/sec_agent/r53_r60_quality_engineering_online_eval.py`
- `scripts/engineering/build_r53_r60_p16_quality_engineering_online_eval.py`
- `tests/test_r53_r60_quality_engineering_online_eval.py`
- `configs/r53_r60/p16_quality_engineering_online_eval_schema_v0_1.json`
- `data/manifests/r53_r60_p16_quality_engineering_online_eval_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p16_quality_engineering_online_eval_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_p16_quality_engineering_online_eval_l4_scope_pass.zh-CN.md`

## Runtime Contract

P16 adds first-class SQL rows for:

- `EvalDataset`, `EvalCase`, `EvalRun`, `EvalMetricResult`, `EvalGateResult`;
- E0-E12 `NodeEvalGateRecord`;
- `TraceSpan`, `ModelCallMetric`, `TokenCostLedger`, `RetrievalMetric`, `ParserMetric`, `ToolMetric`;
- `FailureEvent`, `RegressionCaseRecord`, `GoldPromotionRecord`;
- `QAExecutionPlan`, `DefectRecord`, `DemandAcceptanceRecord`;
- `SandboxRegressionRecord`, `BudgetExceededGate`, `CIGateRecord`;
- `EvalDashboardProjection`, `IncidentRecord`;
- `ReferenceSourceLedger`, `ReferenceChangeLedger`, `ReferenceAdoptionPerformanceProfile`;
- `QualityReadinessReport`, `QualityEngineeringGateResult`.

## Verification Result

Real builder output:

- release decision: `P16_L4_scope_pass_quality_engineering_online_eval_ready`
- closeout level: `L4_scope_pass`
- eval cases: `6`
- eval run: `1`
- E0-E12 node gates: `13`
- trace spans: `12`
- model metrics: `5`
- token/cost ledgers: `5`
- retrieval metrics: `5`
- parser metrics: `6`
- tool metrics: `8`
- failures: `4`
- regression cases: `3`
- gold records: `2`
- QA plans: `3`
- defects: `4`
- R60 demand acceptance: `18/18 pass`
- sandbox regressions: `4`
- BudgetExceededGate rows: `2`
- dashboard projections: `4`
- incidents: `6`
- reference ledgers: `7` source / `7` change / `7` performance
- gate rows: `12 pass / 0 fail`

Targeted verification:

- `python -m py_compile src\sec_agent\r53_r60_quality_engineering_online_eval.py scripts\engineering\build_r53_r60_p16_quality_engineering_online_eval.py`
- `python -m pytest tests\test_r53_r60_quality_engineering_online_eval.py -q`
- `python scripts\engineering\build_r53_r60_p16_quality_engineering_online_eval.py --root .`

## Root-Cause Fixes During Closeout

- Aligned P16 trace projection with the real S1 `trace_spans.span_id` primary key instead of the obsolete `trace_span_id` assumption.
- Added script-level `src` path injection so the standalone engineering builder runs outside pytest.
- Fixed the P16 test report reader to use `sqlite3.Row` when asserting readiness report fields.

## Boundaries

P16 does not claim:

- sustained production online-eval monitoring over real pilot traffic;
- CI/CD provider integration such as GitHub Actions release blocking;
- polished frontend eval dashboard and browser visual QA.

Those remain explicit downstream gaps. The next practical work is to connect P16 dashboard projections to the Workbench Admin/Ops UI, feed real P11 pilot failures into the failure/regression/gold lifecycle, enforce BudgetExceededGate in live model routing, and run a broader 10-20 case release gate after real pilot data exists.
