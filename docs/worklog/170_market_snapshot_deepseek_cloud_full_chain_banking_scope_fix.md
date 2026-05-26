# 170 Market Snapshot DeepSeek Cloud Full-Chain Banking Scope Fix

Date: 2026-05-25

## Problem

After the 7-company market snapshot pre-synthesis smoke, the next acceptance step was a real cloud DeepSeek full-chain synthesis using the same market evidence pack. The first cloud run reached synthesis, but exposed a mixed-scope banking issue: when `JPM` appears alongside non-bank companies, banking metric families could enter the global contract/ledger scope and contaminate non-bank Judgment Plan drivers.

## Decision

- Treat this as a contract and ledger-quality bug, not an output fallback problem.
- Keep banking metrics for banking/financial tickers, but make the scope explicit through `ledger_rules.banking_metric_tickers`.
- In mixed industry prompts, add a JPM-only banking task when a banking/financial company is in focus, while keeping global cross-company tasks on general operating metrics.
- Reject banking structured metric rows that have no explicit column label unless they come from the bounded banking context supplement path; this prevents ambiguous table fragments from becoming exact ledger values.

## Work Completed

- Updated `src/sec_agent/query_contract.py`
  - Adds mixed-scope banking normalization.
  - Removes banking families from global `metric_families` when the focus set mixes bank and non-bank tickers.
  - Keeps JPM-only banking tasks intact.
  - Stamps `ledger_rules.banking_metric_tickers=["JPM"]` for the mixed-scope cloud run.

- Updated `scripts/cloud/sec_agent_interactive.py`
  - Adds category-aware `mixed_scope_banking_metrics` task repair for bank tickers in mixed prompts.
  - Enforces `banking_metric_tickers` in runtime ledger filtering.
  - Rejects ambiguous banking structured metric rows without a column label.

- Updated `tests/test_market_snapshot_fixture.py`
  - Verifies mixed JPM + non-bank prompts keep a JPM-only banking task.
  - Verifies non-bank `deposits` rows are rejected while JPM `deposits` rows remain allowed.

## Cloud Setup Notes

The new 5090 cloud copy was not a Git repository and was missing recent local source files. Minimal syncs were applied to:

- `scripts/market/*.py`
- `scripts/cloud/sec_agent_interactive.py`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- `src/sec_agent/*.py`

The cloud `sec-agent-cu128` environment was missing `duckdb`; installed `duckdb==1.5.3` into `/root/autodl-tmp/envs/sec-agent-cu128`. No API key was written to files.

## Verification

Local:

```powershell
python -m py_compile src/sec_agent/query_contract.py scripts/cloud/sec_agent_interactive.py
python -m pytest tests/test_market_snapshot_fixture.py -q
python -m pytest tests -q
```

Results:

- Market tests: `11 passed`
- Full local suite: `100 passed`

Cloud market artifact build:

- Fixture rows: `760`
- Snapshot rows: `7`
- Analytics rows: `7`
- Evidence pack rows: `7`
- Validator: `can_enter_market_snapshot_chain=true`, `error_count=0`
- DuckDB catalog: `market_daily_bars=760`, `market_snapshots=7`, `market_analytics=7`

Cloud pre-synthesis smoke:

- Output root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/market_snapshot_main_chain_smoke/20260525_213808_44f4a210b8`
- `status=pass`
- `context_row_count=339`
- `market_context_row_count=7`
- `ledger_row_count=80`
- `market_snapshot_support_complete=true`

Final real DeepSeek full-chain run:

- Output root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent_market_cloud/20260525_222900_44f4a210b8`
- Backend/model: DeepSeek `deepseek-v4-pro`
- Planner: `llm:deepseek`
- GPU reranker: BGE-M3 on RTX 5090 CUDA
- Market snapshot: `market_pilot_2026-05-25_7co_mixed_coverage_v1`, `as_of_date=2026-05-25`
- `gates ok=True`, `pass=12`, `fail=[]`
- `coverage_complete=true`, `primary_task_support_complete=true`
- `ledger_row_count=48`, `context_row_count=127`
- Claim verification: `verified`, `promoted=9`
- `non_jpm_bank_rows=[]`
- `banking_metric_tickers=["JPM"]`
- LLM gateway: `input_tokens=68573`, `output_tokens=2636`, `latency_ms=56226`
- Total elapsed: `136.8608 sec`

## Remaining Risks

- The final answer is conservative because several non-bank companies still have sparse or proxy ledger coverage in the current 10-Q manifest.
- JPM bank metrics are now scoped correctly, but some parsed bank table rows remain weakly labeled; future parser work should improve column/header binding instead of relying only on runtime filters.
- Market data is still synthetic offline fixture data, suitable for chain validation only, not investment inference.
