# SEC Agent v0.1 Pre-Release Checklist

Date: 2026-05-26

## Release Scope

First resume-facing release for the constrained SEC investment-research agent:

- Source tiers: SEC 10-K, latest SEC 10-Q, SEC 8-K earnings release, offline market snapshot.
- Company scope: full30 private cloud artifact set.
- Current filing coverage: FY2023-FY2025 10-K plus latest FY2026 10-Q/8-K rows in the accepted manifest.
- Market snapshot: `20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1`, `as_of_date=2026-05-22`.

## Checklist

- [x] Real LLM planner-contract eval:
  - Cloud report: `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_eval_20260526_r3.json`
  - Result: `5/5` pass, `meets_step1_acceptance=true`
  - Metrics: `task_type_accuracy=1.0`, `required_task_coverage=1.0`, `metric_family_recall=0.96`, `year_compliance=1.0`, `source_boundary_violation_rate=0.0`, `schema_validation_pass_rate=1.0`
  - Root-cause fix before acceptance: aligned closeout planner eval to manifest-proven FY2023-FY2026 scope; counted boundary terms in caveat/forbidden-claim fields; stripped unrequested analyst-consensus/macro/geopolitical tasks from planner contracts.

- [x] Public scope and secret-scan contract:
  - Public: `src/`, `scripts/`, `configs/`, `tests/`, `eval_sets/`, `docs/`, `reports/model_runs/`, `.env.example`, metadata/config files.
  - Private/ignored: `data/raw_private/`, `data/processed_private/`, `data/indexes/`, `data/models_private/`, `eval/`, `reports/quality/`, `reports/query_contracts/`, cloud scratch files, `.env`, API keys, SSH passwords.
  - `.gitignore` already excludes these private/generated paths.
  - Final tracked-file scans had no matches for private data/index paths, cloud endpoints, API-key literals, SSH passwords, FMP key literals, or private-key blocks.

- [x] README and demo entrypoints:
  - Root README now describes the first-version constrained agent chain, closeout readiness command, cloud full-source demo, session demo, and non-secret credential handling.
  - Detailed demo entrypoints remain in `docs/demo/sec_agent_demo_entrypoints_v1.md`.

- [x] Cloud deployment and index rebuild runbook:
  - Runbook: `docs/deployment/sec_agent_cloud_full_source_runbook_v1.md`
  - Includes private artifact contract, full30 ObjectBM25 rebuild command, real DeepSeek planner gate command, and saved-run readiness command.

- [x] Final verification before merge:
  - Local JSONL and Python syntax checks passed.
  - Local pytest: `58 passed`.
  - Local readiness: `reports/quality/resume_closeout/20260526_210019_resume_closeout_readiness_local_v1.json`, `blocker_fail_count=0`; local warnings are expected because private full-source artifacts are not in the public workspace.
  - Cloud full-source readiness had blocker failures `0`, P0 readiness `pass=6/6`.
  - Real DeepSeek planner gate passed after root-cause fixes.

- [x] Version commit, tag, and main merge:
  - Release changes are committed on `codex/api-model-call-architecture`.
  - Release tag target: `v0.1.0-resume-demo`.
  - Merge target: local `main`.

## Remaining Non-Blocking Follow-Ups

- Replace JSON-store request locking with DB/Redis/file-lock backed transactions before any production concurrency claim.
- Validate true stage-level resume from a real partial production run, not only fixture-backed resume.
- Add a provider capability registry for price-only versus valuation-capable market snapshots.
- Keep private full-source artifacts out of the public repository; publish only reproducible commands and summarized model-run evidence.
