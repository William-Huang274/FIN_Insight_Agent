# Workbench Backend Release Quality Metrics

Date: 2026-06-05

## Context

The Workbench backend branch already had CI, Docker smoke, frontend smoke, and a small real DeepSeek pressure run, but the evidence was scattered across chat, GitHub Actions, local screenshots, and pressure output directories. For interview and release-readiness discussion, the backend needs a single report shape that separates correctness, performance, token/cost, and reliability signals without overstating a small pressure smoke as a full soak test.

## Changes

- Added `scripts/workbench/generate_backend_release_quality_report.py`.
- The report generator reads `pressure_summary.json` and child `real_chain_eval_summary.json` files, then emits:
  - backend quality gate status;
  - p50/p95/max latency;
  - throughput and concurrency gain;
  - total and per-case token estimates;
  - local validation records;
  - optional GitHub PR checks via `gh pr checks --json`;
  - caveats for sample size and incomplete input/output token splits.
- Added unit tests in `tests/test_workbench_release_quality_report.py`.
- Generated a local ignored report under `reports/quality/workbench_release/20260605_workbench_backend_release_quality_pressure_smoke_v0_1.md`.
- Recorded the durable run summary in `reports/model_runs/20260605_workbench_backend_release_quality_pressure_smoke_v0_1.md`.

## Result

The generated report status is `pass`:

| Metric | Result |
| --- | ---: |
| Concurrent users | `2` |
| Case runs | `4` |
| Pass / fail / timeout | `4 / 0 / 0` |
| Wall time | `473.1s` |
| Latency p50 / p95 / max | `211.3s / 261.7s / 261.7s` |
| Concurrency gain | `1.97x` |
| Total tokens | `125,552` |
| Avg tokens/run | `31,388` |
| CI checks | `3/3` pass |

## Decision

Use this report format as the backend release-quality narrative:

1. CI smoke proves deployment and API contract do not regress.
2. Representative real LLM pressure smoke proves the backend can run concurrent Workbench/agent workloads without timeout.
3. Token and latency tables expose cost/performance tradeoffs by path.
4. Caveats explicitly prevent claiming full production soak from a small sample.

## Follow-Up

- Add a 5-6 case manual release pressure profile that covers focused, standard, heavy/deep, English/Chinese, and multi-turn paths.
- Only run full17 as manual `workflow_dispatch` or local release-candidate soak after the representative suite remains stable.
- Normalize child summaries so all LLM components expose `input_tokens`, `output_tokens`, and `total_tokens`.
