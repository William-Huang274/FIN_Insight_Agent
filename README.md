# FinSight-Agent

Evidence-grounded financial research agent for SEC filing analysis, company-authored earnings-release context, offline market snapshots, and multi-turn investment-research sessions.

The current first-version demo path is a constrained agent, not bare model chat:

```text
User prompt
  -> Query Contract planner
  -> SEC / 8-K / market-snapshot source selection
  -> BM25/ObjectBM25/BGE retrieval
  -> Runtime Exact-Value Ledger
  -> Evidence Coverage Matrix
  -> Judgment Plan
  -> DeepSeek synthesis
  -> deterministic gates
  -> rendered answer + ContextManager session state
```

## Current Scope

The public repository contains code, tests, small eval contracts, and durable run documentation. Private SEC/provider data, indexes, cloud run outputs, and API credentials are intentionally excluded from Git.

The resume-facing SEC agent path supports:

- SEC 10-K/latest 10-Q/8-K evidence retrieval and Exact-Value Ledger checks.
- Offline market snapshot evidence with `snapshot_id`, `as_of_date`, returns, event windows, and FMP-enriched valuation fields when available.
- ContextManager-backed multi-turn sessions, artifact inspection, reformat, and resume checks.
- Closeout readiness evaluation in `scripts/evaluate_sec_agent_resume_closeout_readiness.py`.

Demo and release-scope entrypoints are documented in
`docs/demo/sec_agent_demo_entrypoints_v1.md`.

Release checklist and cloud deployment notes:

- `docs/release/sec_agent_v0_1_pre_release_checklist.md`
- `docs/deployment/sec_agent_cloud_full_source_runbook_v1.md`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a real SEC User-Agent contact before larger SEC collection runs. Never commit `.env`, API keys, cloud passwords, private data, or generated indexes.

## Closeout Readiness

Local deterministic readiness, no API key required:

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

Cloud full-source readiness after a real DeepSeek run exists:

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir /root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

The first release scope is FY2023-FY2025 annual 10-K plus latest available FY2026 10-Q/8-K evidence in the current full30 artifact set. Do not claim FY2027 coverage unless the manifest itself contains FY2027 filings for the selected companies.

## Demo Entrypoints

Cloud one-shot full-source DeepSeek demo:

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

Cloud two-turn session demo:

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

Inside the session, use `/state`, `/context`, `/answer`, and `/exit`.

## SEC Smoke Test

```powershell
python scripts/smoke_test_sec.py --ticker JPM --year 2024
```

Expected local cache:

```text
data/raw_private/sec/2024/uncategorized/JPM/10-K.html
data/raw_private/sec/2024/uncategorized/JPM/10-K.metadata.json
```

Batch download the first technology universe:

```powershell
python scripts/download_sec_filings.py --config configs/sec_tech_universe.yaml
```

The technology universe cache is organized by fiscal year, category, and ticker:

```text
data/raw_private/sec/2024/mega-cap_software_cloud/MSFT/10-K.html
data/raw_private/sec/2024/ai_gpu_semiconductor/NVDA/10-K.html
```

Build a manifest for downstream parsers:

```powershell
python scripts/build_sec_manifest.py
```

Default manifest output:

```text
data/processed_private/manifests/sec_tech_10k_manifest.jsonl
```

Build section-aware chunks from the manifest:

```powershell
python scripts/build_sec_chunks.py
```

Chunks are built with semantic boundaries first. Each chunk keeps its parent
block fields, including `block_id`, `block_heading`, `block_type`,
`block_part_index`, and `block_part_count`, so long sections can be split
without losing their business context.

HTML tables are serialized into atomic `TABLE_START` / `TABLE_END` blocks before
chunking. The chunker does not split inside a table block, and table-bearing
chunks are marked with `contains_table=true`.

Small parser smoke test:

```powershell
python scripts/build_sec_chunks.py --years 2024 --tickers MSFT,NVDA --output data/processed_private/chunks/sec_tech_10k_chunks_smoke.jsonl
```

Convert chunks into the unified EvidenceObject store:

```powershell
python scripts/build_evidence_store.py
```

Default evidence output:

```text
data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl
```

Build and query the BM25 baseline:

```powershell
python scripts/build_bm25_index.py
python scripts/search_bm25.py "What drove Microsoft cloud revenue growth in 2024?" --ticker MSFT --year 2024 --top-k 5
```

Build and query the dense embedding baseline:

```powershell
python scripts/build_dense_index.py --device cuda --batch-size 128
python scripts/search_dense.py "What drove Microsoft cloud revenue growth in 2024?" --ticker MSFT --year 2024 --top-k 5 --device cuda
```

On cloud machines that cannot reach `huggingface.co` directly, set the model
download endpoint before building the dense index:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

Download a Qwen embedding model from ModelScope and build a separate dense
index:

```bash
python scripts/download_modelscope_model.py --model-id Qwen/Qwen3-Embedding-0.6B --cache-dir data/models_private/modelscope
python scripts/build_dense_index.py \
  --model data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B \
  --output-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b \
  --device cuda \
  --batch-size 8 \
  --query-prompt-name query \
  --max-seq-length 4096
```

Evaluate BM25, dense, and hybrid RRF retrieval against the seed diagnostic set:

```powershell
python scripts/evaluate_retrieval.py --retrievers bm25,dense,hybrid --device cuda
```

The seed evaluation set is intentionally small and diagnostic:

```text
eval_sets/sec_tech_10k_seed.jsonl
```

Generated SEC cache and indexes are intentionally excluded from Git.
