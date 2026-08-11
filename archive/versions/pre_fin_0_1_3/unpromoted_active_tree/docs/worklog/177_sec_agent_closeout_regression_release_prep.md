# 177 SEC Agent Closeout Regression And Release Prep

Date: 2026-05-26

## Problem

Before making a first resume-facing version closeout, the project needs a reproducible regression entry rather than a single ad hoc full-source run. The closeout should test query-to-renderer continuity, ContextManager short/long memory, small request pressure, non-LLM latency, source-boundary behavior, and P0 production-readiness gaps.

## Decision

Extend the existing closeout readiness framework instead of adding a separate one-off script. The readiness report remains the single local pre-commit entry, with optional saved full-source DeepSeek run inspection for cloud artifacts.

## Work Completed

- Expanded `eval_sets/sec_agent_resume_closeout_eval_v1.json` with P0 dimensions and additional closeout cases:
  - cross-industry full-source query outside the AI-only cohort;
  - short/long memory multi-turn context case;
  - request-level small pressure case;
  - public scope and demo documentation case.
- Updated `scripts/evaluate_sec_agent_resume_closeout_readiness.py` to add:
  - multi-case main-chain suite;
  - ContextManager API small pressure smoke;
  - local latency profile integration;
  - `p0_readiness` summary in the aggregate report.
- Updated `scripts/market/60_smoke_market_snapshot_main_chain.py` so the same smoke can validate SEC-only negative-control prompts where market data must not be attached.
- Added public/demo scope documentation at `docs/demo/sec_agent_demo_entrypoints_v1.md`.
- Updated the closeout eval doc and master checklist.

## Validation

Completed local validation:

- `python -m json.tool eval_sets/sec_agent_resume_closeout_eval_v1.json`
- `python -m py_compile scripts/evaluate_sec_agent_resume_closeout_readiness.py scripts/market/60_smoke_market_snapshot_main_chain.py src/sec_agent/tool_controller.py`
- `python -m pytest tests/test_resume_closeout_readiness.py tests/test_sec_agent_context_source_policy.py -q`: `20 passed`
- `python scripts/evaluate_sec_agent_context_managed_dispatch_replay.py --fixture-root reports/quality/manual_context_dispatch_fix_check_2 --output-path reports/quality/manual_context_dispatch_fix_check_2.json --controller-backend heuristic --clean-fixtures`: `23/23` all pass
- SEC-only negative-control local smoke confirmed `market_requested=false`, `market_context_row_count=0`, status `pass`
- Full local closeout readiness:
  - Output: `reports/quality/resume_closeout/20260526_191827_resume_closeout_readiness_local_v1.json`
  - Overall: `warn`
  - Blocker failures: `0`
  - Status counts: `pass=8`, `warn=3`, `skipped=1`
  - Critical checks: all pass

Warn/skipped causes:

- `source_inventory_artifacts`: local workspace does not contain the private full-source 8-K manifest/index directories.
- `saved_full_source_deepseek_run`: no saved cloud run directory was attached to this local command.
- `planner_contract_eval_local`: heuristic planner diagnostic is intentionally weaker than LLM planner and missed expected years/task terms.
- `main_chain_case_suite_local`: executed 2 local mixed/market cases and skipped 3 full-source cases because local full-source private artifacts are absent.

Optional cloud validation still pending:

- Completed on cloud after syncing the two missing request-level context API check scripts and rebuilding the full30 ObjectBM25 index from the existing full-source evidence object store.
- Cloud readiness command profile:
  - `scripts/evaluate_sec_agent_resume_closeout_readiness.py`
  - `--require-full-source-artifacts`
  - `--latency-profile-case-path eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b/case.jsonl`
- Latest interactive full-source saved run:
  - Saved run: `eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b`
  - Readiness report: `reports/quality/resume_closeout/20260526_201655_resume_closeout_readiness_local_v1.json`
  - Overall: `warn`; blocker failures: `0`; status counts: `pass=11`, `warn=1`, `skipped=0`; P0 readiness: `pass=6/6`
  - Saved DeepSeek run: completed all stages, passed all saved-run gates, attached 2 market snapshot rows, and had no fallback answers.
- Full30 benchmark saved run:
  - Saved run: `eval/sec_cases/outputs/full_source_deepseek_yahoo_fmp_latest_coverage_fix_benchmark/20260526_024807_3fbff2951a`
  - Readiness report: `reports/quality/resume_closeout/20260526_202136_resume_closeout_readiness_local_v1.json`
  - Overall: `warn`; blocker failures: `0`; status counts: `pass=11`, `warn=1`, `skipped=0`; P0 readiness: `pass=6/6`
  - Saved DeepSeek run: completed all stages, attached 30 market snapshot rows, passed all saved-run gates, had `coverage_complete=true`, `primary_task_support_complete=true`, and had no fallback answers.
- Remaining warning:
  - `planner_contract_eval_local` is the heuristic local diagnostic, not the production DeepSeek planner. It remains useful for schema/source-boundary smoke, but should not be interpreted as the true LLM planner acceptance result.

## P0 Interpretation

Current P0 status should be read as:

- Performance/resource: cloud non-LLM latency profile is tracked and passed with explicit BM25/ObjectBM25 init/search, ledger cache, market attach, and coverage timing.
- Observability: saved full-source DeepSeek runs now prove completed stage statuses, elapsed time, market snapshot coverage, and post-gate outcomes through readiness.
- Data/index versioning: full-source 10-K/latest 10-Q/8-K/market artifact presence is checked, including the rebuilt full30 ObjectBM25 index and market evidence fields.
- State consistency: request-level context API smoke and small pressure smoke passed on cloud; this remains single-process JSON-store validation, not a multi-worker database-backed serving claim.
- Failure recovery: fixture partial-resume checks pass; true stage-level resume from an earlier production partial run remains a separate follow-up before production serving claims.

## Follow-Up

- Run the local readiness entry after code changes.
- Keep the cloud full-source ObjectBM25 index generation reproducible in deployment notes; the index was rebuilt from existing private evidence objects rather than faked.
- Add a real LLM planner-contract cloud eval if this readiness report needs to move from `warn` to `pass`.
- Do not stage generated `reports/quality/` outputs unless a specific report is promoted into `reports/model_runs/`.
