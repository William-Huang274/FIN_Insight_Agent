# 269 Product Taxonomy Normalization And KPI Parser

Date: 2026-06-11

## Prompt

Continue after the product evidence strategy: implement industry taxonomy normalization and a value/unit/period/product KPI parser without weakening the public-evidence research direction.

## Decision

Keep the runtime promotion boundary strict. Normalized taxonomy can support product structure and product-KPI linking, but raw taxonomy candidates cannot enter runtime. KPI rows can become facts only when product node, metric, value, unit, period, source URL, source document id, and citation span pass deterministic gates. Direct chunk scan is useful for recall diagnostics, but it is not promoted until table/list and attribution parsing are stronger.

## Work Completed

- Added `configs/data_sources/product_taxonomy_normalization_rules_v0_1.yaml`.
- Added `scripts/data_expansion/build_product_taxonomy_kpi_parser.py`.
- Added `tests/test_product_taxonomy_kpi_parser.py`.
- Built Z-drive product evidence artifacts under `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/`.
- Added strict rejection gates for generic labels, issuer-name labels, cross-sentence product/value links, ambiguous currency scale, ambiguous percent allocation, table-layout rows, customer/channel share, stock issuance sales, and change-only values.

## Results

Formal runtime-safe output:

- Normalized taxonomy nodes: `5,594`.
- Normalized taxonomy ticker coverage: `566/577` (`98.09%`).
- Taxonomy alias rows: `10,824`.
- Taxonomy review queue: `2,888`.
- Balanced KPI candidates parsed: `6,663`.
- Parser-verified KPI facts accepted for runtime: `1`.
- KPI rejection rows: `6,662`.

Diagnostic direct chunk scan:

- Direct chunk candidates: `43,851`.
- Diagnostic parser-accepted rows before spot-audit rejection: `201`.
- Status: `not_promoted_to_runtime`, because spot audit found product/value misattribution in cross-sentence windows and non-table-aware list/table contexts.

## Evidence

- Unit tests: `python -m pytest tests\test_product_taxonomy_kpi_parser.py` -> `9 passed`.
- Syntax: `python -m py_compile scripts\data_expansion\build_product_taxonomy_kpi_parser.py` -> pass.
- YAML parse check passed for `product_taxonomy_normalization_rules_v0_1.yaml`.

## Follow-Up

- Add high-value taxonomy override and table-context repairs for tickers where normalized product nodes are missing or too generic.
- Improve table unit/header parsing for source-specific physical units, for example utility deliveries and oil/gas production units.
- Add industry-specific taxonomy overrides for high-value false reviews and generic labels.
- Only after those gates pass should product KPI facts be wired into runtime Evidence Fusion or agent memo writing.

## Safety Notes

- Large outputs are on Z because D had no usable free space during the first run.
- Direct scan output is explicitly diagnostic-only and must not be used as runtime facts.

## 2026-06-11 Structured Table Parser Iteration

### Prompt

Continue with the table/list-aware parser instead of weakening the direct text-window rules.

### Decision

Use the existing structured MetricObject SQLite FTS as the candidate generator and hydrate source URL / citation text from chunk manifests by `source_evidence_id == chunk_id`. Promote only rows that pass row/column period-cell gates, product-node matching, value/unit normalization, source URL, source document id, and chunk-level citation context. Compact SQLite records often lack `source_url` and `table_object_id`, so source URL is hydrated from chunks and missing table id is retained as provenance rather than fabricated.

### Work Completed

- Extended `scripts/data_expansion/build_product_taxonomy_kpi_parser.py` with `--enable-structured-metric-kpi-scan` and `--structured-object-sqlite`.
- Added FTS-first structured scan over Tier1/Tier2 annual MetricObject SQLite indexes, with full-scan fallback for small test SQLite fixtures.
- Added structured gates for:
  - table-row-only records;
  - change / variation / decomposition columns;
  - explicit period requirement;
  - currency scale inference from structured units and table context;
  - product revenue strong context;
  - raw numeric cell atomicity;
  - currency/percent unit conflicts;
  - non-revenue KPI family unit compatibility.
- Tightened taxonomy rejects for metric/generic labels such as `revenues`, `operating revenue(s)`, and `growth`.
- Added structured parser tests and regression tests for source hydration, change columns, decomposition columns, currency/percent conflicts, currency-as-delivery false positives, and non-atomic raw cells.

### Final Materialized Output

Artifacts written to `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/`:

- `company_product_taxonomy_normalized_v0_1.jsonl`
- `company_product_taxonomy_aliases_v0_1.jsonl`
- `company_product_taxonomy_review_queue_v0_1.jsonl`
- `company_product_kpi_facts_parser_verified_with_structured_v0_1.jsonl`
- `company_product_kpi_rejections_with_structured_v0_1.jsonl`
- `company_product_taxonomy_kpi_parser_with_structured_summary_v0_1.json`

Final strict run:

- Normalized taxonomy nodes: `5,590`.
- Alias rows: `10,817`.
- Review rows: `2,895`.
- Structured SQLite metric rows scanned by FTS: `488,975`.
- Preselected structured product metric rows: `15,904`.
- Structured parser-verified facts: `6,161`.
- Combined parser-verified facts including the prior balanced text fact: `6,162`.
- Combined parser-verified ticker count: `179`.
- Structured fact families: `product_revenue=5,836`, `production_or_throughput=239`, `unit_sales_or_deliveries=80`, `backlog_or_orders=6`.
- Structured rejections: `10,111`; leading reasons are `no_period=3,401`, `no_valid_metric_context=2,703`, `no_value_unit_match=2,126`, `percent_value_without_revenue_share_context=1,329`, `non_period_or_decomposition_column=212`, `unit_value_conflict=207`, `raw_value_not_atomic_numeric_cell=91`.

### Spot Audit Notes

- Positive examples now include AAPL product-category net sales, TSLA automotive / energy revenues, CAT sales and revenues, MSI segment net sales, EMR/NOC backlog rows, APA production volume rows, and ED delivered volume rows.
- False-positive classes found during audit were fixed before the final run: AAPL revenue rows misclassified as backlog, CAT sales-volume/price-realization decomposition columns promoted as revenue, LLY currency rows mislabeled as percent-of-revenue, revenue dollars promoted as production or deliveries, and long sentence/table text cells parsed as shipment values.
- Remaining gaps are real parser/taxonomy gaps, not fallback candidates: NVDA and MSFT still have `0` promoted structured product KPI facts in this run because the normalized product nodes and compact structured table context do not form a strict row/column/product match.
- Some non-revenue physical units remain generic `units` where source tables do not expose a machine-readable unit in the compact MetricObject; these are usable as company-disclosed quantity facts but need unit-specific table-header enrichment before high-confidence downstream financial judgment.

### Evidence

- `python -m pytest tests\test_product_taxonomy_kpi_parser.py` -> `17 passed`.
- `python -m pytest tests\test_product_taxonomy_kpi_parser.py tests\test_product_evidence_strategy_artifacts.py tests\test_public_source_extended_materialization.py tests\test_public_source_strength_materialization_report.py` -> `27 passed`.
- `python -m py_compile scripts\data_expansion\build_product_taxonomy_kpi_parser.py` -> pass.
- `git diff --check` -> pass.
