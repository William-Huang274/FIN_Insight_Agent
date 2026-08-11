# Model Run: 20260605_workbench_backend_release_quality_pressure_smoke_v0_1

## Summary

- Purpose: summarize Workbench backend CI, Docker smoke, frontend smoke, and bounded real DeepSeek pressure metrics for interview-facing release-quality reporting.
- Status: accepted bounded pressure smoke; not a full 17-case soak test.
- Run type: inference pressure smoke / backend release-quality report.
- Timestamp: 2026-06-05 Asia/Shanghai.
- Environment: local Windows workspace, Docker Desktop, GitHub Actions, real DeepSeek API via `DEEPSEEK_API_KEY` environment variable. API key and raw LLM responses were not saved.

## Code And Command

- Pressure entry point: `scripts/eval_multi_agent/benchmark_real_llm_chain_pressure.py`
- Report entry point: `scripts/workbench/generate_backend_release_quality_report.py`
- Pressure command:
  - `python scripts/eval_multi_agent/benchmark_real_llm_chain_pressure.py --users 2 --iterations 1 --timeout-per-case-s 1200 --data-repo-root D:\FIN_Insight_Agent`
- Report command:
  - `python scripts/workbench/generate_backend_release_quality_report.py --pressure-summary eval/sec_cases/outputs/multi_agent_real_llm_pressure/20260605T135830Z_fin_agent_real_llm_pressure/pressure_summary.json --report-id 20260605_workbench_backend_release_quality_pressure_smoke_v0_1 --validation "workbench_pytest|pass|72 passed: backend/job_runner/profiles/artifacts/docker_config" --validation "frontend_playwright_local|pass|Workbench page smoke passed with no console error" --validation "docker_workbench_image_smoke|pass|CI-equivalent workbench image build plus health/ready/contracts and Playwright smoke" --fetch-pr-checks --repo William-Huang274/FIN_Insight_Agent --pr-number 1`
- Generated report:
  - `reports/quality/workbench_release/20260605_workbench_backend_release_quality_pressure_smoke_v0_1.md`
  - `reports/quality/workbench_release/20260605_workbench_backend_release_quality_pressure_smoke_v0_1.json`

## Inputs

- Source fixture: `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`
- Historical source: `20260602_fin_agent_full17_unrun_first_deepseek_v0_1` reported `8/17` pass. The bounded pressure smoke selected two cases from the passing focused/standard subset:
  - `fin_full_focused_amzn_margin_management_zh`
  - `fin_full_standard_nvda_amd_market_zh`
- Data root: `D:\FIN_Insight_Agent` for private data, indexes, ledger, market/industry evidence, and sector-depth config.
- Runtime safety: API key was passed by environment variable name only; the pressure summary records `api_key_saved=false` and `raw_llm_response_saved=false`.

## Results

| Metric | Result |
| --- | ---: |
| Overall release-quality report status | `pass` |
| Concurrent users | `2` |
| Iterations per user | `1` |
| Case runs | `4` |
| Passed / failed / timeout | `4 / 0 / 0` |
| Wall time | `473.1s` |
| Latency p50 / p95 / max | `211.3s / 261.7s / 261.7s` |
| Successful runs/hour | `30.44` |
| Concurrency gain | `1.97x` |
| Parallel efficiency | `98.6%` |
| Total tokens | `125,552` |
| Avg tokens/run | `31,388` |
| Token p50 / p95 / max | `17,971 / 47,070 / 47,070` |
| Total tool calls | `14` |

### Per-Case Results

| Case | Runs | Pass rate | Avg latency | Avg tokens | Avg tool calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| `fin_full_focused_amzn_margin_management_zh` | `2` | `100%` | `210.8s` | `17,644` | `3.0` |
| `fin_full_standard_nvda_amd_market_zh` | `2` | `100%` | `255.8s` | `45,132` | `4.0` |

### CI And Local Validation

| Check | Result |
| --- | --- |
| Workbench backend pytest | `72 passed` |
| Local Playwright frontend smoke | pass, no console error |
| Local CI-equivalent Docker `workbench` image smoke | pass |
| GitHub Actions `workbench-backend` | pass |
| GitHub Actions `workbench-docker` | pass |
| GitHub Actions `workbench-windows-helper` | pass |

## Interpretation

- Correctness signal: the selected real LLM runs, Workbench backend tests, Docker smoke, and PR checks were all green.
- Performance signal: two concurrent users achieved near-2x concurrency gain without timeout or exit failure.
- Cost signal: standard memo cases are materially more expensive than focused cases (`45.1k` vs `17.6k` tokens/run), mostly due Specialist activation and Memo Writer payload.
- Reliability signal: pressure child summaries and Workbench smoke artifacts are sufficient for release-quality reporting, but not yet for full soak claims.

## Caveats And Next Step

- This is a bounded 2-case pressure smoke, not a full 17-case soak test.
- The sample size is too small for stable p95 latency claims; p95 is reported as an engineering smoke metric only.
- Token totals are component-level estimates; Research Lead, Memo Writer, and Verifier currently expose total tokens but not complete input/output splits.
- Next release gate should run a 5-6 case representative pressure suite before spending tokens on full17 low-concurrency soak.
