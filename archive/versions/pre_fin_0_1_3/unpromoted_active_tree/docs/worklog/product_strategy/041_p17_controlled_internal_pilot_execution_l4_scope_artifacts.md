# R53-R60 P17 Controlled Internal Pilot Execution L4 Scope Artifacts

Date: 2026-06-30

## Scope

P17 closes the first execution-level gap after P11-P16: P11 proved pilot readiness, but left execution pending. P17 consumes P11-P16 scope-pass artifacts and executes the six P11 pilot cases into SQL-final runtime rows.

P17 is a controlled internal deterministic pilot drill. It is not an external customer pilot, not a sustained cloud SLA window, and not a full `L4_production_pass`.

## Implemented Artifacts

- `src/sec_agent/r53_r60_controlled_internal_pilot_execution.py`
- `scripts/engineering/build_r53_r60_p17_controlled_internal_pilot_execution.py`
- `tests/test_r53_r60_controlled_internal_pilot_execution.py`
- `configs/r53_r60/p17_controlled_internal_pilot_execution_schema_v0_1.json`
- `data/manifests/r53_r60_p17_controlled_internal_pilot_execution_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_p17_controlled_internal_pilot_execution_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_p17_controlled_internal_pilot_execution_l4_scope_pass.zh-CN.md`

## Runtime Contract

P17 adds SQL-final rows for:

- `ControlledPilotMetadata`;
- `PilotExecutionBatch`;
- `PilotCaseExecution`;
- `PilotCaseStageCheckpoint`;
- `PilotCaseWorkpaperOutput`;
- `PilotCaseReviewerAction`;
- `PilotCaseEvalSnapshot`;
- `PilotCaseFeedbackRecord`;
- `PilotCaseDefectRecord`;
- `PilotCaseCostLatencyRecord`;
- `PilotCaseArtifactLink`;
- `PilotCaseReleaseDecision`;
- `PilotExecutionReadinessReport`;
- `PilotExecutionGateResult`.

Each pilot case is also represented as a runtime `ResearchTask` with node execution, trace span, checkpoint, artifact and append-only WorkpaperEvent records. The P17 main task records its own scope-pass WorkpaperEvent and artifacts.

## Verification Result

Real builder output:

- release decision: `P17_L4_scope_pass_controlled_internal_pilot_execution_ready`
- closeout level: `L4_scope_pass`
- dependencies: P11-P16 `6/6 pass`
- pilot batches: `1`
- pilot case executions: `6`
- stage checkpoints: `42`
- workpaper outputs: `6`
- reviewer actions: `18`
- eval snapshots: `6`
- feedback records: `6`
- defect records: `6`
- cost/latency records: `6`
- artifact links: `6`
- release decisions: `6`
- case runtime tasks succeeded: `6`
- total drill cost: `2.42`
- max case latency: `210000ms`
- gate rows: `12 pass / 0 fail`

Targeted verification:

- `python -m pytest tests\test_r53_r60_controlled_internal_pilot_execution.py -q`
- `python scripts\engineering\build_r53_r60_p17_controlled_internal_pilot_execution.py --root .`

## Root-Cause Fixes During Closeout

- P17 tests initially failed in isolated `tmp_path` because S8/S10 market-liquidity fixtures are required upstream. The fix was to reuse the established P11/P16 test fixture chain rather than weakening P17 dependency gates or fabricating upstream rows in P17.
- P17 dependency checks are release-decision based. A file existing on disk is not enough; P11-P16 summaries must all be `status=pass` with the expected release decision.

## Boundaries

P17 does not claim:

- external customer pilot or paid-user production readiness;
- sustained cloud p95/p99 SLA;
- CI/CD provider enforcement;
- polished React frontend browser E2E;
- full product `L4_production_pass`.

Known gaps are intentionally carried into the P17 report:

- `external_customer_pilot_not_run`;
- `sustained_cloud_sla_window_not_run`;
- `polished_frontend_browser_e2e_not_run`.

## Next Step

The next practical slice is P18: run a real internal reviewer dogfood window. P18 should take P17 case executions into the Workbench UI, collect real reviewer actions and friction, promote recurring failures into the P16 regression/gold/failure lifecycle, and begin replacing deterministic pilot drill evidence with real internal workflow evidence.
