# Model Run: 20260526_market_snapshot_full30_full_source_deepseek_gate_policy_fix_v1

## Summary

- Purpose: Validate full30 10-K + latest 10-Q + 8-K earnings release + FMP-enriched market snapshot after semantic-gate and Coverage Matrix policy fixes.
- Status: completed
- Run type: inference smoke
- Timestamp: 2026-05-26
- Environment: cloud 5090 host, `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Entry point: `scripts/cloud/sec_agent_interactive.py`
- Model: DeepSeek `deepseek-v4-pro`
- Planner: `QUERY_PLANNER=llm`
- BGE rerank: `BGE_DEVICE=cuda`
- API key handling: environment variable only; no key written to repo files.
- Output root: `eval/sec_cases/outputs/full_source_deepseek_yahoo_fmp_latest_coverage_fix_benchmark`
- Final run path: `eval/sec_cases/outputs/full_source_deepseek_yahoo_fmp_latest_coverage_fix_benchmark/20260526_024807_3fbff2951a`
- Dirty source files at run time included local/cloud-synced changes in:
  - `scripts/cloud/sec_agent_interactive.py`
  - `src/sec_agent/coverage_matrix.py`
  - `src/sec_agent/market_snapshot.py`
  - `src/connectors/sec_filing_manifest.py`
  - `scripts/market/07_enrich_market_snapshot_valuation_fmp.py`
  - `scripts/market/09_download_fmp_historical_snapshot.py`
  - related tests

Command profile, secrets redacted:

```bash
DEEPSEEK_API_KEY=<env> \
SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_EARNINGS \
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl \
MARKET_SNAPSHOT_ID=20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1 \
MARKET_AS_OF_DATE=2026-05-22 \
python scripts/cloud/sec_agent_interactive.py \
  --llm-backend deepseek \
  --model deepseek-v4-pro \
  --query-planner llm \
  --planner-max-tokens 4000 \
  --max-tokens 8000 \
  --bge-device cuda \
  --manifest-path data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl \
  --source-gap-path data/processed_private/source_gaps/sec_tech_8k_earnings_full30_source_gaps_merged_2026_2027.jsonl \
  --bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027 \
  --object-bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects \
  --tickers <full30> \
  --years 2025,2026
```

## Inputs

- Source policy: `SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT`
- SEC manifest: `data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl`
- Market evidence: `data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- Market snapshot as-of date: `2026-05-22`
- Universe: full30 tickers
- Fiscal years requested: `2025, 2026`
- Forms: `10-K`, `10-Q`, `8-K`

## Results

- Answer status: `answered_api_model`
- Planner status: `llm:deepseek:ok`
- Runtime ledger rows: `48`
- Context rows: `150`
- Market context rows: `30`
- Coverage:
  - `coverage_complete=true`
  - `primary_task_support_complete=true`
  - `market_snapshot_support_complete=true`
  - `missing_source_tiers=[]`
- Semantic gate:
  - `company_coverage=selected_companies`
  - `require_company_coverage=false`
  - `v2_semantic_contract_gate_pass=true`
- Post-gates: all 12 deterministic gates passed.
- Gold-style score: `gold_mean_score_pct=0.88`

## Runtime Efficiency

- End-to-end elapsed: `248.9719 sec`
- DeepSeek synthesizer latency: `56993 ms`
- Tokens:
  - input: `75426`
  - output: `2662`
  - total: `78088`
- Main observed cost remains retrieval/rerank plus very large synthesis context; the API synthesis call itself is about 57 seconds.

## Interpretation

The full-source chain can now run end-to-end with:

- mixed SEC filed fundamentals,
- unaudited 8-K management commentary,
- stamped market snapshot / valuation / event-window evidence,
- deterministic source and metric gates,
- broad-scan semantic coverage that does not require all 30 companies to appear unless the prompt explicitly asks for exhaustive coverage.

The final answer used a selected-company broad-scan memo style rather than an exhaustive table. This is correct under the current `selected_companies` contract, but a future exhaustive company table should use a different planner intent and renderer mode.

## Caveats And Next Step

- FMP valuation fields remain incomplete for some companies; the renderer correctly reports the gap.
- `missing_filing_types=["10-K"]` still appears in the coverage summary due to task-level filing scope inheritance. It did not fail gates, but should be cleaned up with task-intent-aware filing requirements.
- Continue with planner intent split:
  - broad scan / select winners and divergences,
  - exhaustive full-universe table,
  - focused peer comparison.
