# SEC Agent 10-Q And Multi-Source Expansion Plan

## Prompt
- User wants to continue from the current SEC-only 10-K agent toward broader, more recent evidence.
- Target direction from the planning screenshot:
  - Stage 1: add SEC 10-Q first.
  - Stage 2: add company-authored sources such as 8-K earnings releases, investor presentations, shareholder letters, and IR press releases.
  - Stage 3: add non-real-time financial market snapshots with explicit `as_of_date`.
- Requirement: decide the improvement direction and execution steps, write them into durable documentation, then execute according to the documented plan.
- No cloud password or API key should be written into repo files.

## Decision
Proceed with a narrow Stage 1 pilot before touching broader sources.

The first implementation target is:
- Companies: `NVDA`, `AMD`, `MSFT`, `AMZN`, `GOOGL`.
- Source expansion: SEC primary filings only, adding latest available `10-Q` alongside existing `10-K`.
- Source policy name for the broader design: `SEC_PRIMARY_MIXED_RECENT`.
- Stage 1 runtime behavior: still deterministic and SEC-only; no market prices, analyst consensus, news, earnings calls, or model-memory facts.
- Quality goal: prove that 10-Q filings can be downloaded, manifested, parsed into chunks, represented in inventory, and surfaced to planner/query contracts without breaking the existing 10-K path.

## Non-Goals For This Iteration
- Do not add 8-K, investor presentations, IR webpages, or market snapshots yet.
- Do not let DeepSeek provide factual recent data from model memory.
- Do not promote 10-Q exact-value comparisons as production-grade until quarterly/YTD/annual period normalization is validated.
- Do not claim full FY2027 Q1 coverage unless the manifest can show the filing exists for that company and source tier.

## Core Contract Changes
### Source Policy
- Current policy: `SEC_ONLY_10K`.
- Target design policy: `SEC_PRIMARY_MIXED_RECENT`.
- Stage 1 accepted subset:
  - `source_tiers`: `primary_sec_filing`.
  - `filing_types`: `["10-K", "10-Q"]`.
  - `market_snapshot`: not allowed.
  - company-authored unaudited sources: not allowed.

### Query Contract
The planner and deterministic clamps must allow:
- `filing_types=["10-K", "10-Q"]` when inventory contains both.
- `source_tiers=["primary_sec_filing"]` for Stage 1.
- Existing `SEC_ONLY_10K` flows must remain valid and must not silently expand to 10-Q.

### Evidence Coverage Matrix
Add source-tier and filing-type visibility:
- Count available evidence by `source_tier`, `source_type`, `form_type`, ticker, and period.
- Record missing source reasons, especially:
  - `10q_not_in_inventory`
  - `quarterly_period_not_normalized`
  - `unsupported_source_tier`

### Exact-Value Ledger
Carry period metadata through the pipeline:
- `period_end`
- `period_type`: `annual` or `quarterly`
- `duration_months`: `12` for 10-K, `3` as a conservative filing-level default for 10-Q.
- `fiscal_period`: best-effort from metadata or `Q?`; do not overstate if unknown.

Important limitation:
- 10-Q filings often contain both three-month and six/nine-month YTD tables.
- Stage 1 may carry filing-level period metadata, but metric-level QTD/YTD separation is only valid when table/sentence extraction can identify the period label.
- If period labels are ambiguous, deterministic gates must downgrade exact numeric claims instead of mixing annual/QTD/YTD values.

### Deterministic Gates
- Existing source-policy gates must stay strict for `SEC_ONLY_10K`.
- For `SEC_PRIMARY_MIXED_RECENT`, claims must cite an allowed source tier and filing type.
- Market snapshot claims are forbidden until the snapshot object includes `as_of_date`.
- 10-Q numeric claims must preserve period metadata or be caveated as filing-level evidence only.

### Renderer
Answers should visibly label evidence boundaries:
- `审计年报` for 10-K.
- `未经审计季报` for 10-Q.
- Future: `公司材料` for company-authored unaudited sources.
- Future: `市场快照 as_of_date=...` for market data.

## Execution Steps
### Step 1: Local Contract And Ingestion Support
1. Update universe/config loading so scripts accept `form_types` while preserving `form_type` backward compatibility.
2. Add a small 10-Q pilot config for the five selected companies; mixed manifests can combine these new 10-Q files with the existing 10-K cache.
3. Update SEC download loop to iterate multiple form types.
4. Update manifest records to carry filing-level period metadata.
5. Update chunk/evidence metadata to preserve period fields.
6. Add a form-aware section splitter entry point:
   - Keep existing 10-K item splitter.
   - Add initial 10-Q item splitter for common quarterly sections.
   - If section labels are not found, fail closed with zero chunks rather than pretending 10-K sections exist.

### Step 2: Local Validation
Run without cloud credentials first:
1. `python -m compileall -q src scripts`
2. 10-K regression dry run/build path still works.
3. Pilot dry run prints `10-Q` planned downloads for selected companies; manifest builder accepts `--form-types 10-K,10-Q` for mixed indexing once both caches exist.
4. Manifest builder accepts `--form-types 10-K,10-Q`.

### Step 3: Cloud Pilot
On the cloud node only after local validation:
1. Sync code.
2. Run pilot download for the five companies, preferably for latest available 10-Q report year.
3. Build mixed manifest.
4. Parse mixed filings.
5. Inspect chunk counts by form type and ticker.
6. Record any missing 10-Q filings or parser failures as source coverage gaps.

### Step 4: Planner/Agent Integration
Only after ingestion succeeds:
1. Update project inventory prompt wording from 10-K-only to inventory-derived allowed filings.
2. Extend tool/source policy schema to allow `SEC_PRIMARY_MIXED_RECENT` in a controlled path.
3. Add a small smoke prompt that asks for latest quarterly context and requires the answer to label 10-Q as unaudited quarterly evidence.

## Acceptance Criteria
- Existing 10-K-only local syntax and script paths still pass.
- Pilot config can plan both 10-K and 10-Q downloads.
- Manifest records include `period_end`, `period_type`, `duration_months`, and `fiscal_period` fields.
- 10-Q chunks do not reuse 10-K section labels incorrectly.
- The system can report coverage gaps instead of filling them with model memory.
- Worklog and README are updated with the decision and run status.

## Current Status
- Decision: `proceed` for Stage 1 local contract and ingestion support.
- Stage 2 and Stage 3 are deferred until Stage 1 source coverage and parser behavior are measured.
- Local contract and ingestion support has been implemented.
- Cloud 10-Q pilot has been run for the five-company target set.

## First Implementation Batch
- Implement Step 1 local support.
- Run Step 2 local validation.
- If local validation passes, run a narrow cloud pilot and append results here.

## Implementation Update
### Local Changes
- Added `form_types` support while preserving legacy `form_type`.
- Added `configs/sec_tech_primary_mixed_pilot.yaml` for the Stage 1 10-Q pilot.
- Updated SEC download script to iterate multiple configured form types and added `--allow-missing` for coverage-gap pilots.
- Added filing-level period fields to manifest/chunk/evidence/structured-object contracts:
  - `source_tier`
  - `period_end`
  - `period_type`
  - `duration_months`
  - `fiscal_period`
- Added a form-aware section splitter:
  - 10-K keeps the existing Item 1/1A/7/7A/8 splitter.
  - 10-Q uses quarterly Item 1/2/3/4/1A definitions.
  - 10-Q parsing fails closed when section headings cannot be found.
- Added AMD 10-Q heading support for `Item 1 | Condensed Consolidated Financial Statements`.
- Updated project inventory to expose `source_tiers` and to warn that 10-Q is unaudited quarterly evidence.

### Local Validation
Commands:
```powershell
python -m compileall -q src scripts
python scripts\download_sec_filings.py --dry-run --limit 3
python scripts\download_sec_filings.py --config configs/sec_tech_primary_mixed_pilot.yaml --dry-run --limit 10 --allow-missing
python scripts\build_sec_manifest.py --output data/processed_private/manifests/local_10k_manifest_regression.jsonl --form-types 10-K
python scripts\build_sec_chunks.py --manifest data/processed_private/manifests/local_10k_manifest_regression.jsonl --output data/processed_private/chunks/local_10k_chunks_regression.jsonl --limit 2
python scripts\build_evidence_store.py --chunks data/processed_private/chunks/local_10k_chunks_regression.jsonl --output data/processed_private/evidence_objects/local_10k_evidence_regression.jsonl
```

Results:
- Syntax compile passed.
- Default 10-K dry run remained 10-K-only.
- Pilot dry run planned five 2026 10-Q downloads: `NVDA`, `AMD`, `MSFT`, `AMZN`, `GOOGL`.
- Local 10-K manifest regression built 60 records from the available local cache.
- Local 10-K chunk regression parsed 2 filings into 98 chunks.
- Local evidence regression produced 98 evidence objects with `source_tier=primary_sec_filing` and `period_type=annual`.

### Cloud Pilot
Environment:
- Cloud path: `/root/autodl-tmp/FIN_Insight_Agent`
- Python: `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`
- Credentials were used only for SSH/API runtime access and were not written to repo files.

Commands run on cloud:
```bash
PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python
$PY -m compileall -q src scripts
$PY scripts/download_sec_filings.py --config configs/sec_tech_primary_mixed_pilot.yaml --rate-limit 2.0 --allow-missing
$PY scripts/build_sec_manifest.py --config configs/sec_tech_primary_mixed_pilot.yaml --root data/raw_private/sec --output data/processed_private/manifests/sec_tech_10q_pilot_manifest_2026.jsonl --form-types 10-Q
$PY scripts/build_sec_chunks.py --manifest data/processed_private/manifests/sec_tech_10q_pilot_manifest_2026.jsonl --output data/processed_private/chunks/sec_tech_10q_pilot_chunks_2026.jsonl
$PY scripts/build_evidence_store.py --chunks data/processed_private/chunks/sec_tech_10q_pilot_chunks_2026.jsonl --output data/processed_private/evidence_objects/sec_tech_10q_pilot_evidence_2026.jsonl
```

Cloud 10-Q source coverage:
- Downloaded/cached 2026 10-Q:
  - `AMD`, period_end `2026-03-28`
  - `MSFT`, period_end `2026-03-31`
  - `AMZN`, period_end `2026-03-31`
  - `GOOGL`, period_end `2026-03-31`
- Missing:
  - `NVDA`: SEC submissions lookup returned no 2026 `10-Q` for CIK `0001045810`.

Cloud parse/evidence result:
- 10-Q manifest: 4 records.
- 10-Q chunks: 275.
- 10-Q form chunk counts: `{"10-Q": 275}`.
- Section counts:
  - Item 1: 93
  - Item 1A: 113
  - Item 2: 59
  - Item 3: 5
  - Item 4: 5
- Evidence objects: 275.
- Evidence source counts: `{"10-Q": 275}`.
- Evidence source tier counts: `{"primary_sec_filing": 275}`.
- Evidence period counts: `{"quarterly": 275}`.

Mixed manifest smoke:
```bash
$PY scripts/build_sec_manifest.py --config configs/sec_tech_universe.yaml --root data/raw_private/sec --output data/processed_private/manifests/sec_tech_primary_mixed_pilot_manifest_2023_2026.jsonl --years 2023,2024,2025,2026 --tickers NVDA,AMD,MSFT,AMZN,GOOGL --form-types 10-K,10-Q
```

Result:
- Records: 19.
- Form counts: `10-K=15`, `10-Q=4`.
- Period type counts: `annual=15`, `quarterly=4`.
- 10-K coverage: `AMD`, `AMZN`, `GOOGL`, `MSFT`, `NVDA`.
- 10-Q coverage: `AMD`, `AMZN`, `GOOGL`, `MSFT`.

## Follow-Up
- Add coverage-matrix source gap rows for missing 10-Q filings such as NVDA 2026.
- Add mixed-source query contract/gate support only after the coverage matrix can express source tier and filing type gaps.
- Add metric-level QTD/YTD period extraction before promoting 10-Q exact-value ledger comparisons.
- Then run a constrained prompt requiring recent quarterly evidence and visible `未经审计季报` source labeling.
