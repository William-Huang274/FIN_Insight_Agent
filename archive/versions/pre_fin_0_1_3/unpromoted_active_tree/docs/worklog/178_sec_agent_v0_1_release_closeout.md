# 178 SEC Agent v0.1 Release Closeout

Date: 2026-05-26

## Problem

The first resume-facing version needs a final release checklist, real planner acceptance evidence, clean public/private boundaries, demo/runbook entrypoints, final verification, and a local merge to `main`.

## Decision

Treat the release as `v0.1.0-resume-demo`: a constrained evidence-grounded demo, not a production multi-worker service. Private SEC/provider data and indexes remain out of Git; public artifacts are code, tests, eval contracts, durable docs, and summarized model-run ledgers.

## Work Completed

- Added the final release checklist: `docs/release/sec_agent_v0_1_pre_release_checklist.md`.
- Added the cloud full-source deployment/runbook: `docs/deployment/sec_agent_cloud_full_source_runbook_v1.md`.
- Updated the root `README.md` with the first-version agent chain, readiness commands, demo commands, and current filing-scope boundary.
- Fixed the closeout planner eval contract and planner repair path:
  - aligned expected years to the accepted manifest scope, FY2023-FY2026;
  - counted source-boundary terms in caveat/forbidden-claim fields;
  - stripped unrequested analyst-consensus/macro/geopolitical tasks from planner contracts.
- Ran the real DeepSeek closeout planner-contract eval on cloud:
  - report: `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_eval_20260526_r3.json`
  - result: `5/5` pass, `meets_step1_acceptance=true`, `source_boundary_violation_rate=0.0`
- Recorded the run in `reports/model_runs/20260526_sec_agent_release_deepseek_planner_contract_eval_v1.md` and `reports/model_runs/model_run_index.md`.

## Validation

Final validation evidence is recorded in the release checklist and model-run ledgers:

- cloud readiness report `reports/quality/resume_closeout/20260526_202136_resume_closeout_readiness_local_v1.json`: blocker failures `0`, P0 readiness `pass=6/6`;
- real DeepSeek planner report `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_eval_20260526_r3.json`: accepted;
- local syntax and JSONL checks passed;
- local pytest passed: `58 passed`;
- local readiness report `reports/quality/resume_closeout/20260526_210019_resume_closeout_readiness_local_v1.json` had `blocker_fail_count=0`;
- tracked-file public/private scope scan and secret scan had no matches after scrubbing a transient cloud endpoint from an older handoff note.

## Boundaries

- Current full30 accepted manifest contains FY2023-FY2025 10-K and latest FY2026 10-Q/8-K rows. Do not claim FY2027 coverage unless a manifest contains FY2027 rows.
- JSON-backed ContextManager state is validated for local/single-process demo and small pressure smoke only.
- Market snapshot is non-real-time and must display `snapshot_id` and `as_of_date`.
- The public repository must not include private filings, provider outputs, indexes, generated quality reports, API keys, SSH passwords, or `.env`.
