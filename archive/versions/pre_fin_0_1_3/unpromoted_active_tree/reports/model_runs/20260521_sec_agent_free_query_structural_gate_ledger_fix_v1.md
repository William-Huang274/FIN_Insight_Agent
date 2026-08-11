# Model Run: 20260521_sec_agent_free_query_structural_gate_ledger_fix_v1

## Summary
- Purpose: validate structural fixes for full30 SEC free-query semantic gating, runtime ledger breadth, and user-visible synthesis output.
- Status: completed local validation; no new model inference was run.
- Run type: evaluation / offline replay.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: local Windows workspace `D:\FIN_Insight_Agent`; replay artifacts synced from cloud.

## Code And Command
- Entry points:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- Commands:
  - `python -m py_compile scripts\cloud\sec_agent_interactive.py scripts\run_sec_eval_synthesis_qwen9b_backend.py scripts\validate_sec_benchmark_v2_semantic_contracts.py src\sec_agent\claim_verifier.py scripts\run_sec_benchmark_eval.py`
  - `bash -n scripts/cloud/sec_agent_interactive.sh`
  - `python scripts\cloud\sec_agent_interactive.py --plan-only --tickers ALL --years 2023,2024,2025 --prompt "<broad AI SEC free query>"`
  - `python scripts\validate_sec_benchmark_v2_semantic_contracts.py --run-dir eval\sec_cases\outputs\interactive_sec_agent\20260521_162939_b38c717195\qwen --cases-path eval\sec_cases\outputs\interactive_sec_agent\20260521_162939_b38c717195\case.jsonl --ledger-path eval\sec_cases\outputs\interactive_sec_agent\20260521_162939_b38c717195\runtime_exact_value_ledger.json --output-path eval\sec_cases\outputs\interactive_sec_agent\20260521_162939_b38c717195\post_gates\sec_benchmark_v2_semantic_contract_gate_replay_after_structural_fixes.json`
- Config:
  - full30 inventory, 2023-2025, 10-K only.
  - Broad AI free-query task type: `ai_industry_financial_trend`.
- Dirty files: local worktree contains many historical untracked experiment artifacts; this run changed only the current SEC-agent scripts and logs.

## Inputs
- Prior replay run: `eval/sec_cases/outputs/interactive_sec_agent/20260521_162939_b38c717195`
- User query:
  - `你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Inventory:
  - digest `e413b6c9ccd0`
  - 30 companies
  - 90 filings
  - years `2023,2024,2025`
  - filing type `10-K`

## Outputs
- Semantic replay report:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_162939_b38c717195/post_gates/sec_benchmark_v2_semantic_contract_gate_replay_after_structural_fixes.json`
- Worklog:
  - `docs/worklog/129_sec_agent_free_query_structural_fixes.md`

## Results
- Semantic gate replay:
  - `can_enter_gate=true`
  - `pass_count=1`
  - `fail_count=0`
  - active checks: `decomposed_task_coverage`, `proxy_as_direct_metric`, `source_policy_violation`
- Offline runtime ledger replay:
  - row count `36`
  - family distribution: `cloud_revenue=10`, `capital_expenditure_proxy=8`, `operating_income=7`, `data_center_revenue=6`, `semiconductor_systems=3`, `semiconductor_solutions=2`
  - cleaned examples: removed tax/goodwill/segment-assets noise, mixed profitability-as-revenue rows, duplicate same ticker/family/year rows, and prior-period comparison leakage.
- Prompt/rendering:
  - broad AI synthesis cap raised to 8 decision drivers and 8 key points.
  - terminal renderer now prints decision drivers with metric/evidence support.
  - future interactive runs write `qwen/input_output.md` with user query, final answer JSON, and raw model output.

## Decision
- Proceed to cloud rerun after syncing code.
- Treat this as a structural validation, not a model-quality claim, because no fresh Qwen9B or DeepSeek inference was executed after the patch.

## Safety Notes
- No API key, SSH password, token, or temporary credential was written to logs.
- The DeepSeek/Qwen output-quality comparison should use newly generated post-patch `input_output.md` artifacts before making production route decisions.
