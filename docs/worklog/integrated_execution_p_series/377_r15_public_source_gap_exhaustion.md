# 377 R15 Public Source Gap Exhaustion

## Problem

用户要求把剩余 L1/L2/L3 source-role 与 Product-KPI exact-slot 缺口补到“公开源确实补不了”的状态，而不是把已有 attempt、URL existence、blocked page、搜索摘要或弱 proxy 当作完成。

本阶段以 `docs/architecture/agent_graph_vnext/20_r15_public_source_gap_exhaustion_execution_plan.zh-CN.md` 为执行锚点，按 R15-1 到 R15-5 逐阶段验收。每阶段未通过前不进入下一阶段。

## Baseline

- Input docket: `data/manifests/company_gap_docket_v0_1.jsonl`
- Audit ledger: `data/manifests/r15_public_source_gap_exhaustion_ledger_v0_1.jsonl`
- Summary: `data/manifests/r15_public_source_gap_exhaustion_summary_v0_1.json`
- Report: `docs/internal/vnext_20260610/vertical_lanes/r15_public_source_gap_exhaustion.zh-CN.md`

Frozen baseline:

- `row_count=486`
- `source_role_row_count=109`
- `product_kpi_row_count=377`
- `pending_gap_count=241`
- `pending_gap_by_stage.r15_1=102`
- `pending_gap_by_stage.r15_2=139`
- `pending_gap_by_stage.r15_3=0`
- `source_role_open_gap_without_attempt_count=14`

Important interpretation:

- `attempted_not_exhausted` is not accepted as a terminal state for R15.
- A row is terminal only if it is `runtime_ready`, `final_public_boundary`, `not_applicable`, or `rerouted`.
- R15-3 reroute rows can pass only because their Product-KPI role is invalid and they have a safer target slot; they cannot become Product-KPI exact evidence.

## Stage Plan

1. R15-1 source-role public-source exhaustion.
   - Re-run or deepen source-role adapters for developer official seed, channel/distributor, app/store, public order/local tender, hiring, supply chain, and technology research.
   - Pass gate: no source-role row remains `open_gap_needs_repair` or `attempted_not_exhausted`.
2. R15-2 Product-KPI exact repair.
   - Re-run source-specific Product-KPI verifier, non-US local disclosure parser, IR deck / annual report locator where available, sentence relation and period/column-group validators.
   - Pass gate: every repairable Product-KPI row either becomes exact runtime row or has source-ladder-backed final boundary.
3. R15-3 Product-KPI reroute validation.
   - Validate business segment, industry operating metric, percentage/change, region-only, and non-product total rows stay out of Product-KPI exact evidence.
4. R15-4 long-tail closeout.
   - For any remaining row, write a concrete final reason and source ladder evidence; generic `not found` is not allowed.
5. R15-5 runtime backfill and final gate.
   - Rebuild exact-slot matrix, closeout ledger, company gap docket, Product-KPI diagnostic, and R15 ledger.

## R15-0 Verification

Commands run:

```powershell
python -m py_compile scripts\data_expansion\build_r15_public_source_gap_exhaustion_ledger.py
python scripts\data_expansion\build_r15_public_source_gap_exhaustion_ledger.py
```

Result:

- Script compiled.
- R15 ledger generated with `row_count=486`.
- `pending_gap_count=241`; R15 is not complete.

## Open Work

- Completed. Final R15 ledger has `pending_gap_count=0` and `open_gap_count=0`.

## Safety Notes

- Do not promote closeout rows as evidence.
- Do not promote blocked pages, URL-only locators, issuer-mismatched rows, or weak proxy rows.
- Do not classify a row as `final_public_boundary` unless an applicable source ladder attempt exists.

## R15-1 Result

Commands / gates:

```powershell
python scripts\data_expansion\build_exact_slot_coverage_matrix.py
python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict
python scripts\data_expansion\build_company_gap_docket.py --strict
python scripts\data_expansion\build_r15_source_role_boundary_attempts.py --strict
python scripts\data_expansion\build_r15_public_source_gap_exhaustion_ledger.py --stage r15_1 --strict
```

Result:

- Source-role rows after final matrix rebuild: `108`.
- R15 source-role terminal attempt rows: `25`.
- `public_order_proxy=8`: jurisdiction public tender / contract portal boundary attempts; no supplier-bound structured award row.
- `technology_research_proxy=17`: OpenAlex / PatentsView boundary attempts; PatentsView key unavailable in current runtime, so no URL-only patent rows are promoted.
- `source_role_open_gap_without_attempt_count=0`.

## R15-2 Result

Fixes:

- Restored `non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl` after a targeted 4-ticker rerun had overwritten the default output with `0` rows.
- Re-ran non-US Product-KPI parser for the complete fallback 15-ticker target universe; restored `70` runtime rows across `11/15` target tickers and `26` rejection rows with exact rejection reasons.
- Fixed `build_product_kpi_source_specific_verifier.py` target selection after docket cluster split; verifier again covers `272` target tickers and `21,822` candidates.
- Added idempotent `build_r15_product_kpi_exhaustion_attempts.py`.

Gates:

```powershell
python scripts\data_expansion\build_product_kpi_source_specific_verifier.py --strict
python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict
python scripts\data_expansion\build_r15_product_kpi_exhaustion_attempts.py --strict
python scripts\data_expansion\build_r15_public_source_gap_exhaustion_ledger.py --stage r15_2 --strict
```

Result:

- R15-2 terminal attempt rows: `139/139`.
- `product_kpi_ir_deck_annual_report_locator=101`: official product/taxonomy surface exists, but no company-disclosed Product-KPI candidate with value/unit/period/product/citation was found in current public disclosure scan.
- `product_kpi_column_group_schema_verifier=18`: mixed segment/financial columns are not promotable to Product-KPI exact without safe product/category revenue isolation.
- `product_kpi_sentence_relation_verifier=9`: local product-value relation not verified.
- `product_kpi_period_version_schema_verifier=7`: period/version conflict not promotable.
- `product_kpi_non_us_ir_local_exchange_parser=4`: non-US local/IR reports parsed; only geography, mix, description, stale, or non-exact rows survived as rejections.

## R15-3 / R15-4 Result

R15-3 strict gate:

- `product_kpi_business_segment_boundary=107` rerouted to business mix / fundamental analysis.
- `product_kpi_industry_operating_metric_slot_router=32` rerouted to industry operating metric slots.
- `product_kpi_percentage_change_rejection_gate=72` kept out of exact revenue unless paired with a currency level value.
- `product_kpi_region_dimension_or_rejection_gate=15` rerouted to geographic exposure or rejection.
- `product_kpi_non_product_total_rejection_gate=12` rejected or left for product-family table search.

R15-4 strict gate:

- No long-tail rows remain after R15-1 through R15-3.
- `r15_4_pending_gap_count=0`.

## R15-5 Final Gate

Commands:

```powershell
python scripts\data_expansion\build_exact_slot_coverage_matrix.py
python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict
python scripts\data_expansion\build_product_kpi_source_specific_verifier.py --strict
python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict
python scripts\data_expansion\build_company_gap_docket.py --strict
python scripts\data_expansion\build_r15_source_role_boundary_attempts.py --strict
python scripts\data_expansion\build_r15_product_kpi_exhaustion_attempts.py --strict
python scripts\data_expansion\build_r15_public_source_gap_exhaustion_ledger.py --stage all --strict
```

Final metrics:

- `exact_slot_coverage_matrix.validation.status=pass`
- `exact_slot_row_count=35,247`
- `exact_slot_gap_count=108`
- `primary_company_disclosure.ready_count=603`
- `company_ir_reports=87`
- `company_gap_docket.docket_count=485`
- `company_gap_docket.source_role_gap_docket_count=108`
- `company_gap_docket.product_kpi_gap_docket_count=377`
- `product_kpi_source_specific_verifier.unclassified_candidate_count=0`
- `product_kpi_source_specific_verifier.promotable_product_metric_count=0`
- `product_kpi_deep_gap_diagnostic.unclassified_count=0`
- `r15_public_source_gap_exhaustion.row_count=485`
- `r15_public_source_gap_exhaustion.pending_gap_count=0`
- `r15_public_source_gap_exhaustion.open_gap_count=0`
- `r15_public_source_gap_exhaustion.by_terminal_state.final_public_boundary=246`
- `r15_public_source_gap_exhaustion.by_terminal_state.not_applicable=1`
- `r15_public_source_gap_exhaustion.by_terminal_state.rerouted=238`

Remaining boundary:

- R15 completion does not mean every company has product-level sales / ASP / sell-through / market share / inventory / channel / backlog exact data.
- Product-KPI exact remains strict: only company-disclosed value/unit/period/product/citation rows can enter evidence.
- Missing product-level commercial metrics remain explicit public-source/commercial-tracker gaps rather than weak L3 proxy evidence.
