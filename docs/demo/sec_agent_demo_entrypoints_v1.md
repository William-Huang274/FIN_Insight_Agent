# SEC Agent Demo Entrypoints v1

[中文版本](sec_agent_demo_entrypoints_v1.zh-CN.md)

## Public Repo Scope

Keep public:

- Source code: `src/`, `scripts/`, `configs/`.
- Small test/eval contracts: `tests/`, `eval_sets/`, `docs/eval/`.
- Durable engineering logs and run ledgers that contain paths and summaries only: `docs/worklog/`, `reports/model_runs/`.
- Small synthetic fixtures that contain no private filings, no raw provider output, and no credentials.

Keep private or ignored:

- SEC/raw/provider data: `data/raw_private/`, `data/processed_private/`.
- Search indexes and model caches: `data/indexes/`, `data/models_private/`.
- Runtime outputs: `eval/`, `reports/quality/`, `reports/demo/`, `reports/logs/`.
- API keys, SSH passwords, provider tokens, `.env`, cloud scratch files.

## Local Closeout Smoke

This is the default pre-commit readiness entry. It uses local fixtures, deterministic contracts, and non-LLM main-chain checks. It should run without API keys.

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

For a faster contract-only check:

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

Outputs are written under `reports/quality/resume_closeout/` and are intentionally ignored by Git.

## Cloud Full-Source DeepSeek Check

Use this when cloud private SEC/8-K/market artifacts and a model API key are available. Inject keys through environment variables only.

```bash
export DEEPSEEK_API_KEY="<set-in-shell-only>"
cd /root/autodl-tmp/FIN_Insight_Agent

PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python \
BGE_DEVICE=cuda \
QUERY_PLANNER=llm \
SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT \
MANIFEST_PATH=data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl \
BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027 \
OBJECT_BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects \
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl \
MARKET_SNAPSHOT_ID=20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1 \
MARKET_AS_OF_DATE=2026-05-22 \
bash scripts/cloud/sec_agent_interactive.sh ask-deepseek \
"结合SEC 10-K、最新10-Q、8-K earnings release 和最近三个月 market snapshot，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。"
```

After the run completes, attach its saved run directory to the readiness aggregator:

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

## Real Session Demo

Use this for the two-turn context-management demo. It runs a ContextManager-backed session; follow-up prompts reuse the same active session and artifact refs.

```bash
export DEEPSEEK_API_KEY="<set-in-shell-only>"
cd /root/autodl-tmp/FIN_Insight_Agent

PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python \
BGE_DEVICE=cuda \
QUERY_PLANNER=llm \
SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT \
MANIFEST_PATH=data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl \
BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027 \
OBJECT_BM25_INDEX_DIR=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects \
MARKET_EVIDENCE_PATH=data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl \
MARKET_SNAPSHOT_ID=20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1 \
MARKET_AS_OF_DATE=2026-05-22 \
bash scripts/cloud/sec_agent_interactive.sh session-deepseek
```

Useful commands inside the session:

```text
/state
/context
/answer
/exit
```

## Demo Narrative

The first public demo should show these boundaries clearly:

- Query starts as free-form Chinese investment research.
- Planner selects SEC 10-K/latest 10-Q/8-K/market snapshot source tiers.
- Tools perform retrieval, exact-value ledger construction, market snapshot attachment, coverage, Judgment Plan, synthesis, gates, and rendering.
- Follow-up turn reuses ContextManager active answer instead of starting an unrelated run.
- Renderer labels SEC audited/unaudited boundaries, company-authored 8-K boundaries, and market snapshot `as_of_date`.

## Current Non-Production Boundaries

- JSON-backed session state is acceptable for local and single-process demo, not multi-process serving.
- Private data and indexes are required for full-source quality but are not part of the public repo.
- DeepSeek output speed is controlled by the provider and model route; local P0 work focuses on non-LLM retrieval, ledger, coverage, and session overhead.
- Market snapshot is non-real-time and must be shown with `snapshot_id` and `as_of_date`.
