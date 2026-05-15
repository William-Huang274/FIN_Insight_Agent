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
data/raw_private/sec/JPM/2024/10-K.html
data/raw_private/sec/JPM/2024/10-K.metadata.json
```

Generated SEC cache and indexes are intentionally excluded from Git.
