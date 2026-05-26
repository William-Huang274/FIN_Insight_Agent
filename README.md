# FinSight-Agent

Evidence-grounded financial research agent foundation.

Phase 1 focuses on retrieval quality before building a full agent:

1. Download and cache SEC filings.
2. Parse filings into section-aware evidence objects.
3. Build sparse, dense, and hybrid retrieval baselines.
4. Evaluate retrieval with gold evidence queries.

## Current Scope

This repository currently contains the Phase 1 skeleton, the
`EvidenceObject` schema, a SEC EDGAR connector, section/table-aware SEC
chunking, and first BM25/dense retrieval smoke baselines.

The current resume-facing SEC agent path extends that foundation with:

- SEC 10-K/latest 10-Q/8-K evidence retrieval and exact-value ledger checks.
- Offline market snapshot evidence with `snapshot_id` and `as_of_date`.
- ContextManager-backed multi-turn sessions, artifact inspection, reformat, and resume checks.
- Closeout readiness evaluation in `scripts/evaluate_sec_agent_resume_closeout_readiness.py`.

Demo and release-scope entrypoints are documented in
`docs/demo/sec_agent_demo_entrypoints_v1.md`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set a real SEC User-Agent contact before
larger runs.

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
