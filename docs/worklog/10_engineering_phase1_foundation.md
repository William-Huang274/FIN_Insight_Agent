# Phase 1 Foundation Worklog

## 2026-05-15 Repository Initialization

Problem or prompt:
Start Phase 1 by creating the project skeleton, setting up Git main/feature
branches, and testing SEC data download feasibility.

Reasoning and decision:
Keep the first implementation focused on SEC filings and evidence retrieval.
Use a private local cache for SEC downloads and generated indexes. Avoid
starting the full agent workflow until retrieval can be evaluated.

Work completed:
- Initialized local Git repository on `main`.
- Added a data-safety `.gitignore` baseline on `main`.
- Created feature branch `feature/phase1-sec-foundation`.
- Added Phase 1 repository skeleton, config files, and worklog scaffold.

Result and evidence:
- Repository is now on `feature/phase1-sec-foundation`.
- EvidenceObject JSONL smoke test wrote and read
  `JPM_2024_10K_ITEM7_CHUNK_0001`.
- SEC smoke test downloaded JPM 2024 10-K:
  - CIK: `0000019617`
  - Report date: `2024-12-31`
  - Filing date: `2025-02-14`
  - Accession: `0000019617-25-000270`
  - Primary document: `jpm-20241231.htm`
  - Local cache: `data/raw_private/sec/JPM/2024/10-K.html`
- Important connector finding: JPM 2024 10-K was not present in the
  `filings.recent` block because SEC had moved it into historical submission
  files. The connector now searches `filings.files` when recent filings do not
  contain the target report year.

Follow-up and safety notes:
- Generated private data remains under `data/raw_private/`,
  `data/processed_private/`, and `data/indexes/`, which are ignored by Git.

## 2026-05-15 SEC Candidate Universe Scan

Problem or prompt:
Assess whether using 2023-2025 SEC filings for Nasdaq technology companies is
feasible for the next data collection step.

Reasoning and decision:
Use SEC 10-K metadata availability as the first feasibility gate before
downloading many large HTML filings. Interpret 2023-2025 by fiscal/report year,
not filing calendar year, because calendar-year companies file FY2025 reports
in early 2026.

Work completed:
- Scanned 10-K metadata for 22 tickers across fiscal years 2023, 2024, and
  2025: `MSFT`, `AAPL`, `NVDA`, `GOOGL`, `META`, `AMZN`, `AVGO`, `ADBE`,
  `CSCO`, `INTC`, `AMD`, `QCOM`, `TXN`, `AMAT`, `MU`, `INTU`, `ADP`, `PANW`,
  `CRWD`, `MDB`, `SNOW`, and `TEAM`.

Result and evidence:
- All 66 ticker-year combinations were found in SEC metadata.
- The scan used metadata lookup only and did not download all filing HTMLs.
- This supports a Phase 1 data scope of a small, sector-diverse Nasdaq tech
  sample before scaling to the full candidate list.

Follow-up and safety notes:
- Recommended first download batch: 8-10 companies across software, internet,
  semiconductors, hardware, cloud, and cybersecurity.
- Keep the first retrieval benchmark smaller than the full 22-company universe
  until parsing and evaluation are stable.
