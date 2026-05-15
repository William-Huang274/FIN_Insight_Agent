# FinSight-Agent

Evidence-grounded financial research agent foundation.

Phase 1 focuses on retrieval quality before building a full agent:

1. Download and cache SEC filings.
2. Parse filings into section-aware evidence objects.
3. Build sparse, dense, and hybrid retrieval baselines.
4. Evaluate retrieval with gold evidence queries.

## Current Scope

This repository currently contains the Phase 1 skeleton, the
`EvidenceObject` schema, and a SEC EDGAR connector smoke test.

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

Generated SEC cache and indexes are intentionally excluded from Git.
