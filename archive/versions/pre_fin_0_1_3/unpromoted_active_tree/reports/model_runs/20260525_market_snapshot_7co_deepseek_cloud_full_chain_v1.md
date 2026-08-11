# Model Run: 20260525_market_snapshot_7co_deepseek_cloud_full_chain_v1

## Summary
- Purpose: Validate real DeepSeek synthesis over the 7-company SEC mixed 10-K/10-Q plus offline market snapshot chain.
- Status: completed
- Run type: inference smoke
- Timestamp: 2026-05-25
- Environment: SeeTaoCloud RTX 5090, `/root/autodl-tmp/envs/sec-agent-cu128`, BGE-M3 CUDA rerank, DeepSeek API.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.py`
- Sanitized command shape:

```bash
DEEPSEEK_API_KEY=<env> PYTHONIOENCODING=utf-8 \
/root/autodl-tmp/envs/sec-agent-cu128/bin/python scripts/cloud/sec_agent_interactive.py \
  --llm-backend deepseek \
  --base-url https://api.deepseek.com \
  --chat-completions-path /chat/completions \
  --model deepseek-v4-pro \
  --api-key-env DEEPSEEK_API_KEY \
  --query-planner llm \
  --planner-max-tokens 4000 \
  --planner-retry-max-tokens 6000 \
  --max-tokens 8000 \
  --temperature 0 \
  --bge-device cuda \
  --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY \
  --years 2025,2026 \
  --manifest-path data/processed_private/manifests/sec_tech_primary_mixed_10k_10q_manifest_2023_2026.jsonl \
  --market-evidence-path data/processed_private/market/evidence_packs/market_pilot_2026-05-25_7co_mixed_coverage_v1_3m_market_evidence.jsonl \
  --market-snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 \
  --market-as-of-date 2026-05-25 \
  --quiet
```

- Git commit before this fix: `6d7bf75`
- Dirty files during final run: `src/sec_agent/query_contract.py`, `scripts/cloud/sec_agent_interactive.py`, `tests/test_market_snapshot_fixture.py`, worklog/model-run docs.
- Seeds: deterministic fixture; model temperature `0`.

## Inputs
- SEC manifest: `data/processed_private/manifests/sec_tech_primary_mixed_10k_10q_manifest_2023_2026.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026`
- Object BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026_objects`
- Market evidence: `data/processed_private/market/evidence_packs/market_pilot_2026-05-25_7co_mixed_coverage_v1_3m_market_evidence.jsonl`
- Snapshot: `market_pilot_2026-05-25_7co_mixed_coverage_v1`, `as_of_date=2026-05-25`
- Tickers: `MSFT, AMZN, GOOGL, JPM, CVX, PG, LLY`
- Years: `2025, 2026`

## Outputs
- Final cloud run: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent_market_cloud/20260525_222900_44f4a210b8`
- Rendered answer: `qwen/rendered_answer.md`
- Runtime ledger: `runtime_exact_value_ledger.json`
- Coverage matrix: `runtime_evidence_coverage_matrix.json`
- Judgment Plan: `runtime_judgment_plan.json`
- Gate summary: `post_gates/sec_benchmark_post_gates_summary.json`

## Results
- Gates: `ok=True`, `pass=12`, `fail=[]`
- Coverage: `coverage_complete=true`, `primary_task_support_complete=true`
- Market support: `market_snapshot_support_complete=true`, `as_of_date=2026-05-25`
- Context rows: `127`
- Ledger rows: `48`
- Banking scope: `banking_metric_tickers=["JPM"]`
- Non-JPM banking rows: `0`
- Claim verification: `verified`, `promoted=9`
- LLM tokens: `input_tokens=68573`, `output_tokens=2636`
- LLM latency: `56226 ms`
- Total elapsed: `136.8608 sec`

## Interpretation
- The real full-chain market snapshot source path works end to end with DeepSeek synthesis.
- Mixed-scope banking contamination was fixed before accepting the final result: JPM banking metrics are scoped to JPM and no non-bank company contributes bank metric rows.
- Ambiguous JPM banking rows without column labels are now rejected from the ledger, preventing a prior bad `net_interest_income=(1)` exact-value claim.

## Safety Notes
- No API key or cloud password is stored in this file.
- Market snapshot data is synthetic offline fixture data and is valid only for chain validation.
- Remaining parser work: improve bank table column/header binding so valid JPM bank rows are recovered directly instead of filtered conservatively.
