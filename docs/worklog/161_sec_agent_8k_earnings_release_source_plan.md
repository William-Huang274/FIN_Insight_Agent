# SEC Agent 8-K Earnings Release Source Plan

Date: 2026-05-25

## Problem Or Prompt

进入 P1 信息源扩展：在当前 `SEC_PRIMARY_MIXED_RECENT` 的 10-K + latest 10-Q 链路基础上，规划接入 SEC 8-K earnings release / Exhibit 99.1。目标是在正式引入新信息源之前，先明确 source contract、采集方式、schema、检索、ledger 使用边界、coverage/gate、pilot 和 rollback。

## Reasoning And Decision

P1 应先接 SEC EDGAR 路径下的 8-K earnings release，而不是直接接 IR 网页、新闻或市场数据。原因是它仍来自 SEC filing archive，source provenance 清楚，能补充 10-K/10-Q 中缺少的最新季度解释、guidance、non-GAAP 桥接和管理层叙述，同时不会立刻引入第三方授权和新闻噪声。

核心决策：

- 新 source policy 命名为 `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`。
- 新 source tier 命名为 `company_authored_unaudited_sec_filing`。
- 8-K/Ex-99.1 默认只进入 qualitative evidence 和 retrieval context，不进入 audited Exact-Value Ledger。
- 如果后续确实要抽取 non-GAAP 或 guidance 数字，必须进入单独的 unaudited numeric evidence/ledger，并在 renderer 中明确标注 `unaudited / management view / non-GAAP`。
- 先做 5 公司 pilot，不直接扩 full30。

## Source Planning: SEC 8-K Earnings Release / Exhibit 99.1

### Purpose

- 投研问题类型：
  - 最新季度业绩解读。
  - 10-Q 数值和 earnings release 管理层解释之间的一致性检查。
  - guidance / outlook / demand commentary / capex commentary / AI product progress。
  - watch items 和 counterarguments 的证据补充。
- 预期补充的证据缺口：
  - 10-Q 表格能给出数值，但常缺少管理层对增长、margin、capex、订单、客户需求和下一季度展望的解释。
  - 当前 mixed 链路对利润率、capex return、RPO/订单趋势、AI capex 解释偏保守，8-K earnings release 可以补 qualitative context。
- 不解决的问题：
  - 不解决实时股价、估值、市场反应。
  - 不解决第三方 consensus / analyst estimate。
  - 不替代 10-K/10-Q audited or filed financial facts。

### Source Contract

- `source_tier`: `company_authored_unaudited_sec_filing`
- `source_policy`: `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`
- `form_type`: `8-K`
- `source_type`: `8-K`
- audited / unaudited / third-party:
  - company-authored, SEC-filed/furnished, unaudited.
  - `Item 2.02` materials are often furnished rather than filed; renderer must not present them as audited financial statement evidence.
- freshness field:
  - `filing_date`
  - `acceptance_datetime`
  - `publication_date` derived from filing date unless a release date is parsed from the exhibit.
  - `as_of_date` is not used for P1; reserve it for future market snapshot.
- required metadata:
  - ticker, company, CIK, accession_number, filing_url, filing_date, acceptance_datetime.
  - filing_items from SEC submissions when available, especially `2.02` and `9.01`.
  - primary_document.
  - exhibit_document, exhibit_type, exhibit_sequence, exhibit_description.
  - exhibit_url and local_exhibit_path.
  - source_tier, source_policy, license_scope, redistributable.
  - earnings_release_candidate_reason.
- allowed claim types:
  - management commentary.
  - reported quarterly highlights when explicitly attributed to the earnings release.
  - guidance/outlook/watch items when explicitly stated in the exhibit.
  - non-GAAP discussion only with boundary labels.
  - qualitative explanations of capex, demand, cloud/AI trends, product progress, and business segment commentary.
- disallowed claim types:
  - audited financial statement claim.
  - exact SEC ledger replacement.
  - valuation/price/market reaction claim.
  - consensus/analyst estimate claim.
  - precise non-GAAP metric claim without exhibit ID and unaudited label.

### Acquisition

- source domain / API / SEC path:
  - Use existing SEC submissions API for filing discovery.
  - Filter `form=8-K`.
  - Prefer rows with `items` containing `2.02`; also allow `9.01` when the exhibit description confirms earnings release.
  - Use SEC archive filing detail JSON, expected path shape:
    - `https://www.sec.gov/Archives/edgar/data/<cik_no_leading_zero>/<accession_no_dashes>/index.json`
  - From filing detail, select exhibit documents matching:
    - type: `EX-99.1`, `EX-99`, `EX-99.01`, or equivalent normalized exhibit type.
    - description contains `earnings`, `results`, `press release`, `financial results`, or company-specific earnings-release phrasing.
  - Exclude investor presentations in P1 unless the exhibit description is clearly the earnings release; presentations belong to P2 IR/materials.
- auth requirement:
  - No API key.
  - Must use `SEC_USER_AGENT`.
- rate limit / retry:
  - Reuse existing SEC connector rate limit.
  - Do not add aggressive parallel SEC downloads in pilot.
- cache path:
  - Raw filing primary document:
    - `data/raw_private/sec_8k_earnings/<filing_year>/<category_slug>/<ticker>/<accession_number>/primary.html`
  - Raw exhibit:
    - `data/raw_private/sec_8k_earnings/<filing_year>/<category_slug>/<ticker>/<accession_number>/<exhibit_filename>`
  - Metadata:
    - `data/raw_private/sec_8k_earnings/<filing_year>/<category_slug>/<ticker>/<accession_number>/metadata.json`
- processed artifact path:
  - Manifest:
    - `data/processed_private/manifests/sec_tech_8k_earnings_pilot_manifest_2026_2027.jsonl`
  - Chunks:
    - `data/processed_private/chunks/sec_tech_8k_earnings_pilot_chunks_2026_2027.jsonl`
  - Evidence:
    - `data/processed_private/evidence/sec_tech_8k_earnings_pilot_evidence_2026_2027.jsonl`
  - BM25:
    - `data/indexes/bm25/sec_tech_8k_earnings_pilot_2026_2027`
  - Mixed-with-8K artifact:
    - `data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_pilot_manifest_fy2023_2027.jsonl`
- privacy / license notes:
  - SEC archive is public, but `redistributable=false` remains the default repository stance.
  - Do not commit raw SEC HTML, exhibits, processed private evidence, or indexes.

### Parsing And Schema

- parser entry point:
  - Add a dedicated 8-K earnings-release parser instead of forcing it through 10-K/10-Q item section splitting.
  - Proposed module: `src/ingestion/sec_8k_earnings_parser.py`.
  - Proposed script: `scripts/build_sec_8k_earnings_chunks.py`.
- output schema:
  - Reuse `SecFilingManifestRecord` where possible, but add metadata fields for exhibit document identity.
  - Reuse `SecFilingChunk` for chunk output, with:
    - `form_type=8-K`
    - `source_type=8-K`
    - `source_tier=company_authored_unaudited_sec_filing`
    - `item_code=2.02` or `exhibit_99_1`
    - `section=Item 2.02 Results of Operations and Financial Condition` or `Exhibit 99.1 Earnings Release`
  - Reuse `EvidenceObject`, but widen `SourceTier` to allow `company_authored_unaudited_sec_filing`.
- IDs:
  - `evidence_id` should include source family and accession:
    - `8K_EARNINGS::<ticker>::<accession>::<exhibit_or_item>::<chunk_index>`
  - `block_id` should include accession and exhibit filename, so evidence can trace back to the exact attachment.
- date/fiscal-period handling:
  - `filing_date` and `acceptance_datetime` are source freshness fields.
  - Do not infer `fiscal_year` from filing date alone for analytical claims.
  - `fiscal_year` can be used as filing-year grouping only unless the exhibit explicitly states fiscal period.
  - If the exhibit title/body includes `quarter ended <date>` or `fiscal <period> <year>`, store parsed `reported_period_end`, `reported_fiscal_period`, and `reported_fiscal_year` in metadata.
- numeric value policy:
  - P1 does not promote 8-K numeric facts into audited Exact-Value Ledger.
  - Structured extraction may retain tables for retrieval and citation, but output must label them as unaudited company-authored values.
  - Non-GAAP values require metadata tags:
    - `numeric_basis=non_gaap`
    - `unaudited=true`
    - `management_view=true`
- qualitative text policy:
  - Extract headline, quarterly highlights, segment commentary, guidance/outlook, forward-looking statements, and reconciliation/disclaimer sections as separate blocks when identifiable.
  - Forward-looking statement and non-GAAP reconciliation sections should be retained for caveats, but not dominate retrieval results.

### Retrieval And Ledger Use

- BM25 / object-BM25 / vector path:
  - Build a separate pilot BM25 index for 8-K earnings evidence.
  - Do not merge into the accepted mixed 10-K/10-Q index until pilot gates pass.
  - Later mixed-with-8K mode can query both primary SEC BM25/object-BM25 and 8-K earnings BM25.
- whether Exact-Value Ledger may use it:
  - Default: no.
  - Allowed only in a future explicit `unaudited_company_value_ledger` or `management_metric_ledger` after separate tests.
- source weighting:
  - SEC 10-K/10-Q audited/filed facts remain higher authority for exact financial values.
  - 8-K earnings release has high authority for management commentary and latest company guidance, lower authority for exact audited facts.
- source conflict rule:
  - If 8-K and 10-Q exact values conflict, 10-Q wins for filed financial values.
  - 8-K can explain differences only if the answer explicitly labels the source boundary.
  - If 8-K guidance conflicts with later 10-Q/10-K, later filing wins or the answer must state timing.

### Query Contract / Coverage / Gates

- Query Contract fields:
  - allow `filing_types=["10-K","10-Q","8-K"]` under `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`.
  - allow `source_tiers=["primary_sec_filing","company_authored_unaudited_sec_filing"]`.
  - add/source-normalize qualitative facets:
    - `management_commentary`
    - `guidance`
    - `demand_commentary`
    - `capex_commentary`
    - `non_gaap_bridge`
    - `forward_looking_statement`
- Evidence Coverage Matrix changes:
  - Track source-tier coverage separately.
  - A task requiring exact values is not complete from 8-K alone.
  - A task requiring management commentary can be complete from 8-K evidence.
  - Missing 8-K should appear as source gap, not trigger replacement by model memory.
- deterministic gates:
  - `source_policy_gate` must recognize the new source policy.
  - Add unaudited boundary gate: any claim sourced to `company_authored_unaudited_sec_filing` must render unaudited/company-authored boundary.
  - Add exact-value authority gate: audited/exact-value claims cannot cite only 8-K earnings evidence.
  - Add market-data gate: answers still cannot mention price, valuation, market cap, or consensus unless market/consensus sources are present.
- renderer boundary labels:
  - Display source tag examples:
    - `8-K Ex-99.1 earnings release, company-authored unaudited, filed/furnished <filing_date>`
    - `management outlook; not audited financial statement evidence`
  - In Chinese output, use:
    - `公司8-K业绩新闻稿（Ex-99.1，未审计/管理层口径）`
    - `该信息不能替代10-K/10-Q财务报表数值`

### Pilot

- tickers:
  - `MSFT`, `AMZN`, `GOOGL`, `META`, `NVDA`
- years / periods:
  - Pilot collection range: 2026-2027 filing years, latest earnings-related 8-K after each company's latest accepted annual 10-K or latest 10-Q.
  - Do not assume all companies share the same fiscal quarter.
- prompts:
  - `结合MSFT最新10-Q和8-K业绩新闻稿，解释云业务增长和管理层对下一季度的表述，明确证据边界。`
  - `AMZN最新季度AWS表现如何？区分10-Q中的数值和8-K新闻稿中的管理层解释。`
  - `GOOGL的AI资本开支和云业务趋势在最新SEC主文件与8-K业绩稿中分别有什么证据？`
  - `META最新业绩稿对AI投入和广告业务趋势怎么说？哪些只是管理层口径？`
  - `NVDA最新8-K/业绩稿是否能补充10-K/10-Q之外的需求或供给解释？`
- success criteria:
  - Manifest includes one selected earnings-release 8-K/Ex-99.1 per pilot ticker when available.
  - Parser emits non-empty chunks with source tier `company_authored_unaudited_sec_filing`.
  - Retrieval returns 8-K evidence for management-commentary prompts.
  - Coverage Matrix distinguishes exact-value tasks from management-commentary tasks.
  - Renderer explicitly labels unaudited/company-authored source boundary.
  - Real mixed-with-8K DeepSeek smoke completes with gates passing or with root-cause-diagnosed gaps.
- failure criteria:
  - 8-K source causes exact-value claims to override 10-Q/10-K ledger.
  - Exhibit selection picks investor presentation or unrelated exhibit as earnings release.
  - Source policy allows market/consensus claims without those sources.
  - Parser emits mostly legal boilerplate or forward-looking disclaimers and misses earnings content.
  - Gates pass only because unsupported claims were silently dropped without source-boundary diagnosis.
- rollback:
  - Keep 8-K artifacts in separate pilot paths.
  - Do not replace `SEC_PRIMARY_MIXED_RECENT` defaults.
  - If pilot fails, disable only `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` commands/configs and keep prior 10-K/10-Q mixed chain intact.

## Implementation Plan

1. Extend source contracts:
   - widen `SourceTier` to include `company_authored_unaudited_sec_filing`.
   - add `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` to supported source policies in context API, tool harness, controller, interactive script, and Query Contract normalization.
   - keep `SEC_PRIMARY_MIXED_RECENT` behavior unchanged.

2. Add 8-K earnings discovery:
   - extend `SecEdgarConnector` with a method that finds latest earnings-related 8-K rows by `items` and filing detail exhibit metadata.
   - add filing detail JSON fetch/cache.
   - select Ex-99.1 earnings release by exhibit type + description rules.

3. Add pilot config and manifest builder:
   - `configs/sec_tech_8k_earnings_pilot_2026_2027.yaml`
   - `scripts/download_sec_8k_earnings.py`
   - `scripts/build_sec_8k_earnings_manifest.py` if the existing manifest builder cannot represent exhibit paths cleanly.

4. Add parser/chunker:
   - parse primary 8-K Item 2.02 and selected Ex-99.1.
   - emit chunks and EvidenceObjects with explicit source tier and exhibit metadata.

5. Add retrieval/index wiring:
   - build separate BM25 pilot index.
   - add mixed-with-8K mode that can include the pilot evidence path without mutating the current mixed artifact.

6. Add gates/rendering:
   - require unaudited boundary rendering for 8-K sourced claims.
   - block 8-K-only exact-value/audited claims.
   - block market/valuation/consensus claims unless future sources are present.

7. Validate:
   - local unit tests for source contract, exhibit selection, parser, retrieval filter, coverage, and renderer boundary.
   - cloud pilot download/index/run for 5 tickers.
   - one real DeepSeek mixed-with-8K smoke before any full30 expansion.

## Experiment Governance Gate

- Hypothesis:
  - Adding SEC 8-K earnings-release evidence will improve management-commentary, guidance, and latest-quarter explanation quality without weakening exact-value constraints.
- Decision target:
  - In the 5-company pilot, at least 4/5 prompts should retrieve relevant 8-K evidence and render explicit unaudited/source-boundary labels while retaining 10-K/10-Q ledger authority for exact values.
- Ceiling:
  - If a company has no earnings-related 8-K/Ex-99.1 in the selected period, the pilot can only report source gaps for that ticker; it must not synthesize from model memory.
- Baselines:
  - Current `SEC_PRIMARY_MIXED_RECENT` 10-K/latest-10-Q chain.
  - Same prompt with 8-K source disabled.
- Split and leakage guard:
  - Pilot is source-integration validation, not benchmark promotion.
  - Do not use output quality from this pilot to retune general gates unless failures are traced to source-contract bugs.
- Stop conditions:
  - Stop if exhibit selection precision is poor, source tier leaks into audited ledger, or renderer cannot reliably show unaudited boundary.
- Efficiency gate:
  - Pilot should keep retrieval context bounded and not add more than one selected earnings-release filing per ticker initially.
- Decision label:
  - `proceed` for planning; implementation remains gated by the source-specific tests above.

## Work Completed

- Created the P1 source-specific plan.
- Implemented the first source-contract slice:
  - widened `EvidenceObject.SourceTier` to allow `company_authored_unaudited_sec_filing`;
  - added `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` to Query Contract source-policy inference, Context API, tool harness, controller routing defaults, and interactive planner/runtime policy helpers;
  - added `configs/sec_tech_8k_earnings_pilot_2026_2027.yaml` for the 5-company pilot scope.
- Implemented connector-side 8-K earnings-release discovery:
  - `SecEdgarConnector.find_earnings_release_8k(...)` finds `8-K` rows for a filing year, requires earnings-related filing items, fetches filing detail `index.json`, parses the primary 8-K exhibit table, and selects an earnings-release `EX-99.1` / `EX-99.01` / `EX-99` exhibit by type and description;
  - investor-presentation, slide, webcast, and transcript exhibits are explicitly rejected in this selector;
  - selected metadata carries `source_tier=company_authored_unaudited_sec_filing`, `source_policy=SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`, exhibit URL, accession, filing date, and unaudited/current-report period metadata.
- Added pilot download/manifest entry points:
  - `scripts/download_sec_8k_earnings.py` reads `configs/sec_tech_8k_earnings_pilot_2026_2027.yaml`, selects one earnings-release 8-K exhibit per ticker/year, and writes raw SEC HTML/metadata under private cache layout `data/raw_private/sec_8k_earnings/<filing_year>/<category>/<ticker>/<accession>/`;
  - `scripts/build_sec_8k_earnings_manifest.py` converts the private cache metadata into a `SecFilingManifestRecord` JSONL manifest at `data/processed_private/manifests/sec_tech_8k_earnings_pilot_manifest_2026_2027.jsonl`;
  - both paths stay under private ignored directories for raw SEC artifacts and generated manifests.
- Added parser/chunker support:
  - `src/ingestion/sec_8k_earnings_parser.py` parses the selected earnings-release exhibit instead of forcing it through 10-K/10-Q Item splitting;
  - `scripts/build_sec_8k_earnings_chunks.py` converts the 8-K earnings manifest into source-bounded `SecFilingChunk` JSONL;
  - chunks carry `source_boundary=company_authored_unaudited_sec_filing`, `unaudited=true`, `management_view=true`, and `exclude_from_exact_value_ledger=true`;
  - reported period hints such as quarter ended date, fiscal quarter, and fiscal year are captured as metadata when present.
- Added runtime source-boundary gate text for `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` so cases explicitly forbid treating 8-K earnings-release evidence as audited 10-K/10-Q financial statement evidence.
- Cloud pilot selector issue found and fixed:
  - first real SEC download selected a Microsoft `Item 5.02,9.01` press release because the selector treated `9.01 + press release` as sufficient;
  - fixed the root selector rule so P1 requires `Item 2.02` for earnings-release discovery;
  - `scripts/build_sec_8k_earnings_manifest.py` now also filters cached records without `Item 2.02`, so stale pilot cache cannot pollute downstream chunks.
- Cloud mixed-chain contract issue found and fixed:
  - first mixed-with-8K DeepSeek run had 8-K rows in the combined BM25 context, but the final Query Contract was normalized back to `source_tiers=["primary_sec_filing"]`;
  - root cause was `_normalize_llm_query_contract(...)` ignoring planner-provided `source_tiers`, plus source coverage checking every requested tier against every filing type;
  - fixed interactive contract normalization/repair to preserve mixed source tiers, and fixed Query Contract coverage so 10-K/10-Q require `primary_sec_filing` while 8-K requires `company_authored_unaudited_sec_filing`.
- Added local tests for:
  - EvidenceObject accepting the unaudited 8-K source tier;
  - Query Contract recognizing mixed 10-K/10-Q/8-K with the new source policy and caveat;
  - Context API and tool harness accepting the new policy without executing the graph;
  - runtime case generation injecting the 8-K unaudited source-boundary gate;
  - SEC connector selecting an earnings-release Ex-99.1, downloading its exhibit cache, and rejecting an investor-presentation Ex-99.1;
  - SEC connector rejecting generic `9.01` press releases that are not `Item 2.02` earnings releases;
  - 8-K earnings manifest builder preserving exhibit HTML paths, current-report period metadata, and unaudited source tier;
  - 8-K earnings manifest builder rejecting cached non-`Item 2.02` press releases;
  - 8-K earnings parser producing source-bounded chunks and EvidenceObject records;
  - LLM Query Contract normalization preserving 8-K source tiers through repair/validation.
- Rendered-answer source-boundary display checks remain open.
- Raw SEC 8-K data was downloaded only on the cloud private ignored paths during validation; no raw SEC HTML or processed private artifacts were committed.

Validation:

```powershell
python -m pytest tests/test_sec_agent_8k_earnings_source.py tests/test_sec_agent_context_source_policy.py tests/test_sec_agent_10q_source_contract.py tests/test_sec_benchmark_eval_mixed_context.py -q
python -m py_compile src/connectors/sec_edgar_connector.py src/evidence/schema.py src/evidence/evidence_builder.py src/ingestion/sec_8k_earnings_parser.py src/ingestion/__init__.py src/sec_agent/query_contract.py src/sec_agent/tool_harness.py src/sec_agent/tool_controller.py src/sec_agent/context_api.py scripts/cloud/sec_agent_interactive.py scripts/download_sec_8k_earnings.py scripts/build_sec_8k_earnings_manifest.py scripts/build_sec_8k_earnings_chunks.py
git diff --check -- src/connectors/sec_edgar_connector.py src/evidence/schema.py src/evidence/evidence_builder.py src/ingestion/sec_8k_earnings_parser.py src/ingestion/__init__.py src/sec_agent/query_contract.py src/sec_agent/tool_harness.py src/sec_agent/tool_controller.py src/sec_agent/context_api.py scripts/cloud/sec_agent_interactive.py tests/test_sec_agent_8k_earnings_source.py configs/sec_tech_8k_earnings_pilot_2026_2027.yaml scripts/download_sec_8k_earnings.py scripts/build_sec_8k_earnings_manifest.py scripts/build_sec_8k_earnings_chunks.py docs/worklog/161_sec_agent_8k_earnings_release_source_plan.md docs/worklog/README.md docs/worklog/00_internal_master_checklist.md
```

Result:

- Targeted local tests: `51 passed`.
- `py_compile` passed.
- `git diff --check` passed.

## Cloud Pilot Validation

Date: 2026-05-25

Environment:

- Cloud path: `/root/autodl-tmp/FIN_Insight_Agent`
- Python: `/root/autodl-tmp/envs/sec-agent-cu128/bin/python`
- Source policy: `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`
- Pilot companies: `MSFT`, `AMZN`, `GOOGL`, `META`, `NVDA`
- Pilot years: `2026`, `2027`

Validation commands:

```bash
python -m pytest tests/test_sec_agent_8k_earnings_source.py tests/test_sec_agent_context_source_policy.py tests/test_sec_agent_10q_source_contract.py tests/test_sec_benchmark_eval_mixed_context.py -q
python scripts/download_sec_8k_earnings.py --allow-missing --rate-limit 1.0
python scripts/build_sec_8k_earnings_manifest.py
python scripts/build_sec_8k_earnings_chunks.py
python scripts/build_evidence_store.py --chunks data/processed_private/chunks/sec_tech_8k_earnings_pilot_chunks_2026_2027.jsonl --output data/processed_private/evidence/sec_tech_8k_earnings_pilot_evidence_2026_2027.jsonl
python scripts/build_bm25_index.py --evidence data/processed_private/evidence/sec_tech_8k_earnings_pilot_evidence_2026_2027.jsonl --output-dir data/indexes/bm25/sec_tech_8k_earnings_pilot_2026_2027
```

Cloud results:

- Cloud targeted tests: `51 passed`.
- SEC 8-K earnings-release downloader selected valid `Item 2.02,9.01` records for `MSFT` and `AMZN` in filing year 2026.
- `GOOGL`, `META`, `NVDA`, and 2027 pilot rows had no selected `Item 2.02` earnings-release 8-K in this pilot run.
- 8-K manifest: `data/processed_private/manifests/sec_tech_8k_earnings_pilot_manifest_2026_2027.jsonl`, `2` records.
- 8-K chunks: `data/processed_private/chunks/sec_tech_8k_earnings_pilot_chunks_2026_2027.jsonl`, `24` chunks.
- 8-K evidence: `data/processed_private/evidence/sec_tech_8k_earnings_pilot_evidence_2026_2027.jsonl`, `24` EvidenceObjects.
- 8-K BM25: `data/indexes/bm25/sec_tech_8k_earnings_pilot_2026_2027`, `24` records.
- Combined mixed-with-8K evidence: `data/processed_private/evidence_objects/sec_tech_primary_mixed_with_8k_earnings_pilot_evidence_fy2023_2027.jsonl`, `10,321` records.
- Combined mixed-with-8K BM25: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_pilot_fy2023_2027`, `10,321` records.

Real DeepSeek mixed-chain smoke:

- Run path: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260525_021707_490c9357a2`
- Prompt scope: `MSFT,AMZN`, year `2026`, forms `10-Q,8-K`.
- Query Contract source policy: `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`.
- Query Contract source tiers: `primary_sec_filing`, `company_authored_unaudited_sec_filing`.
- Source coverage gaps: `0`.
- Coverage summary: filing types covered `10-Q`, `8-K`; source tiers covered `primary_sec_filing`, `company_authored_unaudited_sec_filing`; context rows `80`; ledger rows `70`.
- Answer behavior: the rendered answer used 10-Q ledger values for exact financial metrics and cited MSFT 8-K earnings-release evidence for management/AI revenue-run-rate commentary.
- Gate status: deterministic coverage completed, but final `qwen_answer_gate_pass` remained false; this is retained as a quality follow-up rather than bypassed.

## Follow-Up

- Add rendered-answer source-boundary display checks for 8-K evidence labels.
- Investigate remaining `qwen_answer_gate_pass` failure on the mixed-with-8K DeepSeek smoke.
- Keep all P1 artifacts in pilot-specific paths until source selection, retrieval, renderer labels, and gates pass.
- Update this document after implementation with concrete artifact paths, row counts, tests, and cloud run IDs.

## Safety Notes

- No API keys, passwords, or cloud credentials were written to this document.
- Raw SEC HTML/exhibit files and processed private evidence must stay out of Git.
