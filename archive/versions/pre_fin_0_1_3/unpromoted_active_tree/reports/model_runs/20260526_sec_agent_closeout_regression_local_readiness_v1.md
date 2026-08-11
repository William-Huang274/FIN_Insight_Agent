# Model Run: 20260526_sec_agent_closeout_regression_local_readiness_v1

## Summary

- Purpose: first-version resume-closeout local regression and P0 readiness check.
- Status: local critical pass with expected warnings.
- Run type: evaluation / smoke.
- Timestamp: 2026-05-26 19:18 Asia/Shanghai.
- Environment: local Windows workspace, no model API key required.

## Code And Command

- Entry point: `scripts/evaluate_sec_agent_resume_closeout_readiness.py`
- Command: `python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600`
- Output report: `reports/quality/resume_closeout/20260526_191827_resume_closeout_readiness_local_v1.json`
- Git state: dirty working tree; see final git status before commit.

## Inputs

- Eval set: `eval_sets/sec_agent_resume_closeout_eval_v1.json`
- Planner eval subset: `eval_sets/sec_agent_resume_closeout_planner_eval_v1.jsonl`
- Mixed 10-K/latest 10-Q manifest: `data/processed_private/manifests/sec_tech_primary_mixed_10k_latest_10q_manifest_fy2023_2027.jsonl`
- Market evidence pack: `data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- Private full-source 8-K manifest/index paths: absent in local workspace.

## Results

- Overall status: `warn`
- Check count: `12`
- Status counts: `pass=8`, `warn=3`, `skipped=1`
- Blocker failures: `0`
- Critical checks: all pass
- P0 readiness: `warn`

Passing critical checks:

- `context_state_replay`
- `context_api_smoke`
- `context_managed_dispatch_replay`
- `tool_harness_dispatch_fixtures`
- `unit_contract_tests`

Warnings and skips:

- `source_inventory_artifacts`: local full-source 8-K manifest/index directories are missing.
- `saved_full_source_deepseek_run`: no saved cloud run directory was attached.
- `planner_contract_eval_local`: heuristic planner diagnostic is not accepted as a full planner-quality gate.
- `main_chain_case_suite_local`: local suite ran 2 mixed/market cases and skipped 3 full-source cases because local full-source private artifacts are absent.

## Runtime Efficiency

- Local readiness wall time: about 161 seconds.
- Latency profile check: pass.
- Context API small pressure check: pass.
- Non-LLM path now records BM25/ObjectBM25, candidate generation, ledger cache, and coverage timing through the integrated latency profile.

## Interpretation

This run is suitable as a local pre-commit regression gate. It does not replace a cloud full-source DeepSeek run because the local workspace intentionally lacks ignored full-source private artifacts and no saved cloud run was attached.

## Caveats And Next Step

- Cloud full-source readiness should be rerun with `--saved-full-source-run-dir` and `--require-full-source-artifacts` before claiming first-version full-source release readiness.
- Do not stage `reports/quality/` outputs; this ledger records only the summary and ignored report path.
