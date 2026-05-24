# Model Run: 20260521_sec_agent_interactive_full30_ai_free_query_hotfix

## Summary
- Purpose: Repair and validate the constrained interactive SEC agent on a broad full30 free query about AI industry development from 2023 to 2025.
- Status: completed
- Run type: free-prompt full30 inference + deterministic gates
- Timestamp: 2026-05-21 Asia/Shanghai
- Environment: cloud, RTX 5090 32GB, BGE-first retrieval on GPU, Qwen9B served by vLLM for synthesis.

## Prompt
```text
你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法
```

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.sh`
- Core script: `scripts/cloud/sec_agent_interactive.py`
- Command profile:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
TICKERS=ALL YEARS=2023,2024,2025 \
  bash scripts/cloud/sec_agent_interactive.sh ask-bge-first "你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法"
```
- BGE-first behavior: stop resident Qwen server before retrieval, run BGE-M3 rerank on CUDA, restart Qwen server for synthesis.

## Inputs
- SEC manifest: `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`
- Scope: all 30 SEC companies in the local manifest, fiscal years 2023, 2024, and 2025.
- Query contract: full30 retrieval scope with AI-focused planning over:
  `NVDA, AMD, AVGO, AMAT, MU, INTC, QCOM, MSFT, GOOGL, AMZN, META, ADBE, SNOW`.
- Evidence boundary: retrieved SEC evidence and structured objects only.
- Numeric boundary: final exact values may only come from runtime Exact-Value Ledger.

## Fixes Covered
- Added `plan` / `--plan-only` query contract preview.
- Added AI free-query detection and AI focus ticker contract while preserving full30 retrieval scope.
- Changed AI query `task_type` to `ai_industry_financial_trend`.
- Compacted interactive Judgment Plan payload to top drivers and limited evidence/metric ids.
- Raised default `MAX_TOKENS` to `4000`.
- Filtered low-signal runtime ledger rows: geographic revenue, acquisition/accounting, sales/marketing, cost rows, R&D percentages, and weak capex proxies.
- Added structured object supplement for AI focus segment revenue rows, including NVIDIA data-center / compute-networking rows.
- Converted required caveats into deterministic caveat specs.

## Outputs
- Artifact root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260521_024409_b38c717195`
- Log: `reports/logs/sec_agent_interactive_full30_ai_hotfix_r2.log`
- Trace: `trace/trace_logs.jsonl`
- Runtime ledger: `runtime_exact_value_ledger.json`
- Runtime Judgment Plan: `runtime_judgment_plan.json`
- Qwen outputs: `qwen/agent_outputs.jsonl`, `qwen/raw_model_outputs.jsonl`
- Post-gates: `post_gates/sec_benchmark_post_gates_summary.json`

## Results
- `gates ok`: true
- pass gates: 12
- fail gates: 0
- `qwen_answer_ratio`: 1.0
- ledger rows: 16
- context rows: 360
- elapsed: 233.97 sec

## Quality Notes
- The answer no longer falls back to raw ledger listing and no longer mixes unrelated CSCO/geographic/accounting rows into the thesis.
- The generated answer used ledger-backed drivers such as AMZN AWS revenue, META R&D, NVIDIA data-center proxy revenue, and AMAT gross margin.
- Required caveats were present and passed deterministic caveat checks.
- A cosmetic NVIDIA segment metric-name fix was applied after this full-green run and checked by py_compile plus ledger rebuild, but the full Qwen synthesis was not rerun after that display-only patch.

## Limitations
- This is not a reviewed-gold benchmark case. The ledger is built at runtime from retrieved structured objects and gate-checked, but not manually reviewed.
- Full30 BGE-first interaction remains slow at roughly 4 minutes per wide prompt.
- The free-query planner is now usable for this AI industry trend prompt, but still needs a broader planner evaluation set before production use.

## Safety Notes
- No SSH password, token, or temporary credential is recorded here.
