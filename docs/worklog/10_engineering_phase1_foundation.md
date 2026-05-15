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

## 2026-05-15 SEC Cache Layout And First Tech Batch

Problem or prompt:
Organize downloaded SEC filings by fiscal year and business category so the
raw data layout supports later category-level retrieval comparisons.

Reasoning and decision:
Use `data/raw_private/sec/<year>/<category_slug>/<ticker>/<form>.html`.
Keep the human-readable category in filing metadata, and use filesystem-safe
slugs for folder names because category labels may contain `/`.

Work completed:
- Added `configs/sec_tech_universe.yaml` with the first 10-company technology
  universe:
  `MSFT`, `AAPL`, `NVDA`, `GOOGL`, `META`, `AMZN`, `AMD`, `ADBE`, `PANW`,
  and `SNOW`.
- Updated the SEC connector cache layout to `year/category/ticker`.
- Added `scripts/download_sec_filings.py` for configured batch downloads.
- Downloaded 30 filings: 10 companies across fiscal years 2023, 2024, and
  2025.

Result and evidence:
- Tech universe raw HTML count: 30.
- Tech universe raw HTML size: 87,434,064 bytes.
- Example path:
  `data/raw_private/sec/2024/mega-cap_software_cloud/MSFT/10-K.html`.
- JPM smoke test also works with the new default uncategorized layout:
  `data/raw_private/sec/2024/uncategorized/JPM/10-K.html`.

Follow-up and safety notes:
- Raw SEC HTML and metadata remain ignored under `data/raw_private/`.
- The earlier JPM banking smoke-test cache under the old layout is harmless
  local generated data and is not part of the tech universe benchmark.

## 2026-05-15 SEC Manifest Builder

Problem or prompt:
Create a stable traversal layer so downstream parsers do not need to scan the
raw SEC folder structure directly.

Reasoning and decision:
Build a JSONL manifest from metadata sidecars using the order
`year -> category_slug -> ticker -> *.metadata.json -> matching HTML`. The
manifest is filtered by `configs/sec_tech_universe.yaml` by default so the JPM
smoke-test filing does not enter the tech benchmark.

Work completed:
- Added `src/connectors/sec_filing_manifest.py`.
- Added `scripts/build_sec_manifest.py`.
- Generated
  `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`.

Result and evidence:
- Manifest record count: 30.
- Years: 2023, 2024, 2025.
- Tickers: `AAPL`, `ADBE`, `AMD`, `AMZN`, `GOOGL`, `META`, `MSFT`, `NVDA`,
  `PANW`, and `SNOW`.
- Filter smoke test for 2024 `MSFT` and `NVDA` returned 2 records.

Follow-up and safety notes:
- The manifest is generated under `data/processed_private/`, which is ignored
  by Git.
- The next parser should read this manifest rather than globbing raw HTML
  files directly.

## 2026-05-15 SEC Parser And Chunk Builder

Problem or prompt:
Implement SEC filing parsing and section-aware chunking for the downloaded
10-K HTML filings.

Reasoning and decision:
Use a conservative parser before building retrieval indexes. Extract visible
HTML text, detect 10-K `Item` sections from cleaned line spans, filter out table
of contents entries by requiring an actual Item 1 body span, and emit only the
Phase 1 target sections: Item 1, Item 1A, Item 7, Item 7A, and Item 8.

Work completed:
- Added `src/ingestion/parse_sec_filing.py`.
- Added `src/ingestion/section_splitter.py`.
- Added `scripts/build_sec_chunks.py`.
- Built a small smoke output for 2024 `MSFT` and `NVDA`.
- Built full tech-universe chunks from 30 filings.

Result and evidence:
- `python -m compileall src scripts` passed.
- Smoke test for 2024 `MSFT` and `NVDA` produced 102 chunks:
  - Item 1: 23
  - Item 1A: 35
  - Item 7: 18
  - Item 7A: 2
  - Item 8: 24
- Full tech-universe run produced 1,829 chunks from 30 filings:
  - Item 1: 255
  - Item 1A: 592
  - Item 7: 290
  - Item 7A: 44
  - Item 8: 648
- Chunk word count summary for the full run:
  - Minimum: 32
  - Median: 925
  - Maximum: 1,630
- Output path:
  `data/processed_private/chunks/sec_tech_10k_chunks.jsonl`.

Follow-up and safety notes:
- Generated chunk JSONL is under `data/processed_private/` and is ignored by
  Git.
- Some companies, such as NVDA, use Item 8 as a short cross-reference to
  consolidated financial statements elsewhere in the filing. The parser keeps
  that short Item 8 record instead of inventing a different citation boundary.
- Next step should convert chunks into `EvidenceObject` records and then build
  the BM25 retrieval baseline.

## 2026-05-15 Semantic Block-Aware Chunking Update

Problem or prompt:
Avoid arbitrary chunk splitting that cuts financial business language apart.
When long same-section content must be split, preserve the larger business
block and section context on every part.

Reasoning and decision:
Use SEC Item sections as hard boundaries, then identify semantic blocks inside
each Item from business headings, risk headings, MD&A headings, market-risk
headings, and financial statement/note headings. Split only when a semantic
block exceeds the target retrieval size, and label every split with the same
`block_id`, `block_heading`, `block_type`, `block_part_index`, and
`block_part_count`.

Work completed:
- Added `SecSemanticBlock`.
- Extended `SecFilingChunk` with parent block and part fields.
- Updated chunk IDs from section-only chunks to block-aware IDs such as
  `MSFT_2024_10K_ITEM7_BLOCK_0008_PART_01_OF_02`.
- Tightened Item 8 heading rules so normal table rows are less likely to
  become standalone semantic blocks.

Result and evidence:
- Smoke test for 2024 `MSFT` and `NVDA` produced:
  - 174 chunks
  - 133 semantic blocks
  - 22 split blocks
- Full tech-universe run produced:
  - 2,919 chunks
  - 2,088 semantic blocks
  - 460 split blocks
- Full run section chunk counts:
  - Item 1: 420
  - Item 1A: 989
  - Item 7: 570
  - Item 7A: 51
  - Item 8: 889
- Full run word count summary:
  - Minimum: 32
  - Median: 448
  - Maximum: 1,683

Follow-up and safety notes:
- Chunk length is now a secondary constraint after semantic boundary
  preservation.
- Some short chunks remain by design where the original filing uses a short
  cross-reference or a concise business heading.
- EvidenceObject builder should map `block_heading` to `subsection` and carry
  the block/part fields in metadata.
