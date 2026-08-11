# SEC Agent Mixed 10-K/10-Q Full30 Period Role And Context Policy

Date: 2026-05-24

## Prompt

Continue the staged 10-Q expansion work: finish `period_role` clarity, expand 10-Q coverage beyond the pilot, test mixed 10-K/10-Q session behavior, and fix actual chain issues instead of adding fallback rules.

## Decision

Stage 1 remains SEC-primary only. The accepted source policy for this path is `SEC_PRIMARY_MIXED_RECENT`, backed by:

- audited annual 10-K evidence for 2023-2025;
- latest available 2026 10-Q evidence where present;
- explicit `period_role` labels so QTD, YTD, TTM, annual, and point-in-time values are not mixed in the ledger or renderer.
- fiscal-year metadata sourced from SEC inline XBRL `DocumentFiscalYearFocus` / `DocumentFiscalPeriodFocus`, not from calendar `reportDate` alone.

Market snapshots, 8-Ks, investor presentations, IR releases, and other company-authored unaudited materials remain deferred.

Important fiscal-year decision:

- `years` in downloader, manifest, query contract, and renderer must be interpreted as fiscal years.
- `reportDate` / `period_end` remains the period-end date; it must not define `fiscal_year` for off-calendar filers.
- The next interim expansion should be expressed as "latest available 10-Q after the latest accepted audited 10-K" or as explicit fiscal-year requests per company. A global `2027 Q1` assumption is not valid for all 30 companies because fiscal calendars differ.

## Work Completed

10-Q parsing and full30 coverage:

- Added `configs/sec_tech_10q_full_2026.yaml` for the current 30-company 10-Q scope.
- Fixed the 10-Q section splitter for nontraditional layouts used by GE and INTC, where the old parser anchored on cross-reference table rows instead of real filing sections.
- Rebuilt 2026 10-Q chunks, evidence, structured objects, and BM25/object-BM25 indexes.
- Rebuilt mixed 10-K/10-Q artifacts from accepted mainline 10-K plus new 2026 10-Q artifacts.

Current artifact contract:

- Mixed manifest rows: `116` total = `90` 10-K + `26` 10-Q.
- Mixed ticker coverage: `30` tickers.
- Mixed chunk/evidence rows: `8461` 10-K + `1567` 10-Q.
- Recovered parser coverage examples: GE `53` chunks, INTC `42` chunks.

Period-role work:

- Extended structured table extraction to assign `period_role` for multi-period columns.
- Propagated `period_role` into runtime Exact-Value Ledger rows and metric IDs.
- Updated renderer metric refs to display filing form, fiscal period, `period_role`, and `period_end` for quarterly/period-specific rows.
- Added tests proving QTD and YTD rows remain separate in ledger and rendered answer support text.

Fiscal-year contract fix:

- Fixed `src/connectors/sec_edgar_connector.py` so filing selection probes candidate filing HTML and matches the requested fiscal year against `DocumentFiscalYearFocus`.
- Fixed `src/connectors/sec_filing_manifest.py` so manifest records use document fiscal-year focus and filter by record fiscal year instead of cache directory year.
- Added metadata fields `fiscal_year_source`, `document_fiscal_year_focus`, `fiscal_period_source`, and `document_fiscal_period_focus` to manifest output.
- Kept prefetched SEC HTML in memory only; it is stripped before metadata is written to disk.
- Added tests for FY2027 Q1-style filings whose `reportDate` is in calendar 2026 but whose `DocumentFiscalYearFocus` is 2027.

Renderer/source-year clarity:

- Added `source_fiscal_year` to runtime ledger rows.
- Kept `fiscal_year` as the value/comparable period year, while `source_fiscal_year` identifies the filing that supplied the table.
- Updated metric refs so prior-year comparative columns from a current 10-Q render as `FY2025 comparable in FY2026 filing`, avoiding the false impression that a separate FY2025 10-Q was retrieved.

Mixed source-policy wiring:

- Added mixed session commands in `scripts/cloud/sec_agent_interactive.sh`: `chat-mixed-deepseek`, `ask-mixed-deepseek`, and `session-mixed-deepseek`.
- Made CLI manifest/index paths environment-selectable via `MANIFEST_PATH`, `BM25_INDEX_DIR`, and `OBJECT_BM25_INDEX_DIR`.
- Extended `start_memo_analysis` tool schema to allow `SEC_PRIMARY_MIXED_RECENT`.
- Fixed Query Contract coverage-gap logic so it does not require a cartesian product of all selected years and all selected filing types.

Context/session root-cause fix:

- Reproduced a no-execute mixed session where the controller created `active_scope.source_policy=SEC_ONLY_10K` despite mixed CLI flags.
- Root cause: bootstrap `source_policy` was dropped from the compact runtime context, and `start_memo_analysis` used `setdefault`, so stale controller arguments could override the runtime source policy.
- Fixed `src/sec_agent/tool_controller.py` to preserve bootstrap source policy and treat source policy as runtime configuration for `start_memo_analysis`.
- Fixed `src/sec_agent/context_api.py` to force the runtime bootstrap source policy into new-session `start_memo_analysis` dispatch arguments.
- Fixed Chinese year extraction from prompts such as `2026年10-Q` by replacing Unicode word-boundary matching with digit-boundary matching.

MSFT mixed-run root-cause fix:

- Reproduced a real DeepSeek mixed ask where the manifest and structured objects already showed `MSFT FY2026 Q3`, but `data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026_objects/records.jsonl` still contained stale `Q1` object records.
- Root cause: the mixed structured-object JSONL had been rebuilt, but the exact object-BM25 output path had not been rebuilt; a duplicate output directory with an embedded carriage-return character also existed from an earlier command typo.
- Rebuilt the correct object-BM25 path:

```bash
/root/autodl-tmp/envs/sec-agent-cu128/bin/python scripts/build_object_bm25_index.py \
  --structured-dir data/processed_private/structured_objects \
  --prefix sec_tech_primary_mixed_10k_10q_2023_2026 \
  --output-dir data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026_objects
```

- Rebuild result: `315458` object records = `11013` tables + `230415` metrics + `74030` claims.
- Post-rebuild spot check: MSFT 2026 10-Q object records now show `fiscal_period=Q3` with `QTD` and `YTD` cells.

## Validation

Local checks:

```powershell
python -m py_compile src/sec_agent/tool_controller.py src/sec_agent/context_api.py tests/test_sec_agent_context_source_policy.py
python -m pytest tests/test_sec_agent_context_source_policy.py tests/test_sec_agent_10q_source_contract.py tests/test_sec_benchmark_post_gate_usage.py -q
bash -n scripts/cloud/sec_agent_interactive.sh
```

Result:

- Current targeted local result after fiscal-year and renderer fixes: `25 passed`.
- Shell syntax check returned code `0`.

Cloud checks:

```bash
/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m py_compile \
  src/connectors/sec_edgar_connector.py \
  src/connectors/sec_filing_manifest.py \
  scripts/cloud/sec_agent_interactive.py \
  tests/test_sec_agent_10q_source_contract.py

/root/autodl-tmp/envs/sec-agent-cu128/bin/python -m pytest \
  tests/test_sec_agent_context_source_policy.py \
  tests/test_sec_agent_10q_source_contract.py \
  tests/test_sec_benchmark_post_gate_usage.py -q
```

Result:

- `25 passed`.

Manual no-execute mixed session smoke:

```powershell
$env:SEC_AGENT_SOURCE_POLICY='SEC_PRIMARY_MIXED_RECENT'
python scripts/cloud/sec_agent_context_session_cli.py --controller-backend heuristic --no-execute --source-policy SEC_PRIMARY_MIXED_RECENT --manifest-path data/processed_private/manifests/sec_tech_primary_mixed_10k_10q_manifest_2023_2026.jsonl --bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026 --object-bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026_objects --prompt "比较MSFT 2025年10-K和2026年10-Q的云业务表现"
```

Observed active scope:

```json
{"selected_tickers":["MSFT"],"selected_years":[2025,2026],"source_policy":"SEC_PRIMARY_MIXED_RECENT"}
```

Real cloud DeepSeek mixed ask after object-index rebuild and renderer fix:

```bash
PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python \
QUERY_PLANNER=llm USER_OUTPUT=1 BGE_DEVICE=cuda \
EVIDENCE_TOP_K=5 OBJECT_TOP_K=8 MAX_TOKENS=3000 YEARS=2025,2026 \
bash scripts/cloud/sec_agent_interactive.sh ask-mixed-deepseek \
  "比较MSFT 2025年10-K和2026年10-Q的云业务表现，重点说明10-Q季度口径和证据边界。"
```

Result:

- Artifacts: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_213644_fd4bf4e50f`
- Gates: `ok=True`, `pass=12`, `fail=[]`.
- Ledger rows: `5`.
- Elapsed: `119.96 sec`.
- Output now renders MSFT cloud revenue as:
  - `MSFT FY2026 10-Q Q3 YTD period_end=2026-03-31 ... 92,329（百万美元）`
  - `MSFT FY2025 comparable in FY2026 filing 10-Q Q3 YTD period_end=2026-03-31 ... 70,557（百万美元）`

## 2026-05-24 Latest 10-Q Mixed Mainline Rebuild

Problem:

- The previous mixed artifact name hid the fiscal-year-aware source contract.
- MSFT 10-Q cache could remain polluted as "new accession metadata + old quarter HTML", which made manifest/index rows vulnerable to Q2/Q3 metadata mixing.
- The real DeepSeek chain initially reached renderer output but post gates failed because the API memo contract allowed unsupported peer/counterargument candidates, and then overclaimed recurring/subscription quality from cloud/services revenue.

Root-cause fixes:

- Added `scripts/build_sec_mixed_latest_manifest.py` to compose mixed SEC sources as selected annual 10-K fiscal years plus each ticker's latest available 10-Q after its latest selected 10-K.
- Tightened `src/connectors/sec_edgar_connector.py` cache-hit validation: cached metadata must match requested accession/primary document/filing URL, and cached HTML fiscal year/period focus must match the selected filing before reuse.
- Fixed inline XBRL fiscal focus parsing when `DocumentFiscalYearFocus` / `DocumentFiscalPeriodFocus` values contain nested tags.
- Tightened API memo synthesis contract: unsupported `peer_readthrough` / `counterarguments` / memo claims without current IDs are dropped before claim verification, and cloud/services revenue can no longer be phrased as ARR, subscription revenue, recurring-quality, or renewal-quality evidence without explicit supporting metric families.

Current mixed artifact contract:

- Annual manifest: `data/processed_private/manifests/sec_tech_10k_manifest_fy2023_2026.jsonl`
- Interim manifest: `data/processed_private/manifests/sec_tech_10q_manifest_fy2026_2027.jsonl`
- Mixed manifest: `data/processed_private/manifests/sec_tech_primary_mixed_10k_latest_10q_manifest_fy2023_2027.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027`
- Object BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects`

Rebuild results:

- Mixed manifest: `119` rows = `93` 10-K + `26` latest 10-Q, `30` tickers.
- Latest interim gaps: `CRWD`, `NVDA`, `SNOW`, `WMT`, because their latest selected 10-K is already FY2026 and no later 10-Q is currently available in the requested FY2026/FY2027 pull.
- Evidence objects: `10297` rows = `8730` 10-K + `1567` 10-Q.
- Structured objects: `323257` rows = `11216` tables + `235189` metrics + `76852` claims.
- MSFT object-index spot check: `2450` FY2026 10-Q object records, all sampled rows showed `fiscal_period=Q3`; metric period roles included `qtd`, `ytd`, `instant`, and `annual`.

Validation:

- Local targeted tests: `31 passed`.
- Cloud targeted tests: `31 passed`.
- Real cloud DeepSeek mixed ask:
  - Command shape: `QUERY_PLANNER=llm USER_OUTPUT=1 BGE_DEVICE=cuda EVIDENCE_TOP_K=5 OBJECT_TOP_K=8 MAX_TOKENS=3000 YEARS=2025,2026 bash scripts/cloud/sec_agent_interactive.sh ask-mixed-deepseek "比较MSFT 2025年10-K和2026年10-Q的云业务表现，重点说明10-Q季度口径和证据边界。"`
  - Artifacts: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_225025_fd4bf4e50f`
  - Gates: `ok=True`, `pass=12`, `fail=[]`.
  - Ledger rows: `74`.
  - Elapsed: `129.94 sec`.

## 2026-05-24 Mixed Retrieval Context Root-Cause Fix

Problem:

- Mixed 10-K/latest-10-Q runs could show `[context] rows=0` even when the runtime exact-value ledger had rows.
- Root cause was not answer rendering. `scripts/run_sec_benchmark_eval.py` still treated the requested `ticker x year x form_type` Cartesian product as mandatory. Under `SEC_PRIMARY_MIXED_RECENT`, that is wrong because annual 10-K rows and the latest available 10-Q are intentionally sparse by form/year. The resolver could mark normal 10-Q gaps as `source_missing`, skip retrieval, and leave synthesis with ledger-only structured evidence.
- Retrieval requirement queries also overused generic guardrail text such as "Do not use non-SEC sources" as BM25 queries, which polluted candidate context and reduced useful qualitative evidence.
- Some metric-family names were semantically equivalent but not treated as equivalent by coverage, e.g. query contracts could request `capex` while ledger rows used `capital_expenditure_proxy`.

Fixes:

- `run_sec_benchmark_eval.py` now records source resolver status/counts and only treats missing filings as fatal when the source policy requires complete inventory. `SEC_PRIMARY_MIXED_RECENT` proceeds when at least one requested primary filing exists and leaves sparse 10-Q/10-K gaps to the coverage matrix.
- Requirement-query generation now prioritizes `query_contract.qualitative_queries`, decomposed task text, and facets; generic policy/trap text is filtered out unless it contains domain-specific evidence terms.
- Object-BM25 aliases now cover `arr_or_recurring_proxy`, `rpo`, `deferred_revenue`, `capex`, and `free_cash_flow_proxy`.
- Interactive AI ledger allowlists now include visibility/cash-flow families (`arr_or_recurring_proxy`, `deferred_revenue`, `rpo`, `free_cash_flow_proxy`) and merge task-required metric families into `ledger_rules.allowed_metric_families`.
- Coverage matrix now treats `capex`/`capital_expenditure_proxy`/`ppe_purchases`, `cash_flow`/`operating_cash_flow`/`free_cash_flow_proxy`, and ARR/RPO/deferred/subscription visibility families as equivalent for support accounting while preserving the actual ledger family in output.

Validation:

```powershell
python -m pytest tests/test_sec_benchmark_eval_mixed_context.py -q
python -m pytest tests/test_sec_agent_10q_source_contract.py tests/test_build_sec_mixed_latest_manifest.py tests/test_sec_agent_context_source_policy.py -q
python -m py_compile scripts/run_sec_benchmark_eval.py scripts/cloud/sec_agent_interactive.py src/sec_agent/coverage_matrix.py
git diff --check -- scripts/run_sec_benchmark_eval.py scripts/cloud/sec_agent_interactive.py src/sec_agent/coverage_matrix.py tests/test_sec_benchmark_eval_mixed_context.py
```

Result:

- New mixed context/source-policy tests: `4 passed`.
- Existing 10-Q/source-policy targeted tests: `29 passed`.
- `py_compile` and `git diff --check` passed.

Effect:

- The fix addresses the actual `context rows=0` failure path for mixed source policy rather than adding synthesis fallback text.
- Conservative answers should now improve when the source inventory contains profitability, capex, RPO/deferred/subscription, or cash-flow evidence because retrieval and coverage can actually surface those rows. The answer should still stay conservative when the source inventory genuinely lacks those metrics.

## 2026-05-25 Peer Scope And Cash-Flow Ledger Fix

Problem:

- A single-company period comparison such as "MSFT 10-K vs 10-Q" could still be treated as peer comparison because generic comparison words were mixed with peer-intent detection.
- `source_coverage_gaps` could report unrelated tickers from the full search universe for a focused one-company question.
- MSFT 2026 10-Q cash-flow and capex rows existed in the structured object index, but the runtime ledger missed or blurred them because table parsing, metric-family aliases, period-role repair, and cash-flow sign normalization were incomplete.
- User-facing output could still include unsupported-value cleanup artifacts such as "当前引用未保留..." after model JSON repair.

Root-cause fixes:

- Split peer intent from generic comparison intent, and enforce the Query Contract boundary so `peer_readthrough` is cleared unless the prompt/contract actually asks for peers or competitors.
- Scoped source-gap reporting to `focus_tickers` plus task-required/peer tickers, instead of the whole selected search universe.
- Mapped `net cash from operations` to `operating_cash_flow`, added capex aliases for `additions to property and equipment`, and allowed visibility/cash-flow families in the interactive ledger path.
- Repaired 10-Q cash-flow table period metadata for QTD/YTD columns, including legacy standalone-parenthesis table parses.
- Normalized parenthesized capex cash outflows as negative values and added deterministic `free_cash_flow_proxy = operating_cash_flow + capex` rows with source metric/evidence IDs.
- Updated table parsing so standalone `)` cells join the previous numeric token rather than becoming a separate column.
- Cleaned rendered output to remove unsupported-value placeholder phrasing while preserving evidence-boundary caveats.

Validation:

```powershell
python -m pytest tests/test_sec_agent_10q_source_contract.py -q
python -m pytest tests/test_sec_benchmark_eval_mixed_context.py tests/test_sec_agent_10q_source_contract.py tests/test_build_sec_mixed_latest_manifest.py tests/test_sec_agent_context_source_policy.py -q
python -m py_compile scripts/cloud/sec_agent_interactive.py scripts/run_sec_eval_synthesis_qwen9b_backend.py src/sec_agent/query_contract.py src/evidence/structured_extractor.py
git diff --check -- scripts/cloud/sec_agent_interactive.py scripts/run_sec_eval_synthesis_qwen9b_backend.py src/sec_agent/query_contract.py src/evidence/structured_extractor.py tests/test_sec_agent_10q_source_contract.py
```

Result:

- Local targeted test bundle: `41 passed`.
- Cloud targeted test bundle: `41 passed`.
- Real cloud DeepSeek mixed runs after the fix:
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260525_003325_6500b1f7bd`
  - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260525_004227_6500b1f7bd`
- Latest inspected artifact had `gates ok=True`, `pass=12`, `fail=[]`, `context rows=120`, `coverage complete=true`, `primary_complete=true`, `source_coverage_gap_count=0`, and `peer_readthrough count=0`.
- Ledger rows included MSFT 10-Q `operating_cash_flow`, `capital_expenditure_proxy`, and derived `free_cash_flow_proxy` with explicit QTD/YTD period roles.
- Rendered answer no longer contained `period_unknown` or unsupported-value placeholder text.

Effect:

- The two observed issues are now addressed at the retrieval/contract/ledger layer: focused mixed-period questions no longer create peer leakage, and cash-flow/capex/FCF facts can enter the answer when they exist in SEC structured evidence.
- The answer remains intentionally conservative for profitability, RPO, deferred revenue, subscription, and market-snapshot questions unless those sources are present in the current SEC-primary inventory.

## Follow-Up

- The fiscal-year-aware interim source contract has been implemented for the latest-10-Q mixed mainline. Keep the older `sec_tech_primary_mixed_10k_10q_2023_2026` artifact as historical only.
- Continue hardening `period_role` for TTM and point-in-time rows; QTD/YTD/annual are now explicitly represented in the main mixed path, while TTM coverage still depends on source text/table labels.
- Remove or quarantine the malformed duplicate object-index directory with an embedded carriage-return character during a cleanup pass; do not rely on it for any run.
- Do not add fallback rules if the next cloud run fails. First inspect source policy propagation, manifest/index selection, parser output, and ledger period metadata.

No API keys, passwords, or cloud credentials were written to repository files.
