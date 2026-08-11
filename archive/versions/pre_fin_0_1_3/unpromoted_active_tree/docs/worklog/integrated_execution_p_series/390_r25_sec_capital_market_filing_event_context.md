# 390 R25 SEC Capital Market Filing Event Context

## Prompt

图二第三层要求继续补资本、资金、持仓、治理和市场流动性相关数据源。R23/R24 已把 debt / credit / capital structure / 13F lagged ownership / working-capital liquidity 接入 R18 数据基座，但 SEC submissions metadata 中的 offering、insider、13D/13G、proxy/governance filing-event 仍没有 source-role contract，也没有进入 R18 admission / authority mart。

## Decision

先把 SEC submissions metadata 做成四类 filing-event context source roles，而不是硬提权成 exact financial facts：

- `securities_offering_filing_event`：S-1/S-3/F-1/F-3/424B/FWP 等 offering / registration filing event metadata。
- `insider_transaction_filing_event`：Form 3/4/5/144 filing event metadata。
- `beneficial_ownership_filing_event`：SC/Schedule 13D/13G filing event metadata。
- `proxy_governance_filing_event`：DEF 14A / DEFA14A / PRE 14A / DFAN14A / PX14A6G filing event metadata。

这些 rows 能证明公司有某类 SEC filing event、form、accession、filing date、primary document，但不能证明 offering amount、security terms、dilution、coupon、maturity、insider shares、transaction price、beneficial ownership percentage、activist thesis、proxy vote result、buyback amount 或 compensation outcome。后续需要 source-specific XML/text/table parser 才能进入 exact。

## Work Completed

- 新增 `scripts/data_expansion/build_sec_capital_market_event_context_rows.py`。
  - 输入本地 `data/raw_private/sec/_reference/submissions/CIK*.json`。
  - 输出 `sec_capital_market_event_context_rows_v0_1.jsonl` 和 `sec_capital_market_event_context_summary_v0_1.json`。
  - 按 source role 限定 form family，并写入 forbidden claim scope。
- `src/sec_agent/source_route_registry_v2.py`
  - 注册四个 SEC capital-market filing event source roles。
- `src/sec_agent/source_coverage_gate.py`
  - 增加四类 requirement template。
  - 对这四类 role 启用 strict source-role / runtime-contract matching，避免普通 SEC metadata 泛化满足窄合同。
- `src/sec_agent/company_public_source_coverage_matrix.py`
  - 把四类 role 加入 observed-row-driven dynamic requirement 注入。
- `scripts/data_expansion/build_r18_data_source_admission_ledger.py`
  - 把四类 role 纳入 `capital_funding_ownership_market_liquidity` support surface。
- `src/sec_agent/source_layer_capability_audit.py`
  - 注册 `sec_offering_filing_metadata`、`sec_form_3_4_5_metadata`、`sec_schedule_13d_13g_metadata`、`sec_proxy_governance_metadata` runtime-ready context route，避免 admission ledger 显示 `not_registered`。
- 新增/更新测试：
  - `tests/test_sec_capital_market_event_context_rows.py`
  - `tests/test_source_route_registry_v2.py`
  - `tests/test_source_coverage_gate.py`
  - `tests/test_company_public_source_coverage_matrix.py`

## Result

Rebuilt artifacts:

- `sec_capital_market_event_context_rows_v0_1.jsonl`
- `sec_capital_market_event_context_summary_v0_1.json`
- `source_layer_capability_audit_v0_1.jsonl`
- `company_public_source_coverage_matrix_v0_1.json/jsonl`
- `r18_data_source_admission_ledger_v0_1.jsonl`
- `r18_source_route_registry_v2.json`
- `r18_source_authority_data_mart_rows_v0_1.jsonl`
- `r18_vertical_source_route_gate_rows_v0_1.jsonl`

Metrics:

- SEC capital-market event rows: `7,584` rows / `248` tickers.
- Row split:
  - `insider_transaction_filing_event=1,969`
  - `beneficial_ownership_filing_event=1,965`
  - `proxy_governance_filing_event=1,892`
  - `securities_offering_filing_event=1,758`
- R18 registry: `source_role_count=28`, hard gate all zero.
- R18 authority mart: strict pass, `row_count=7,181`, `evidence_bundle_allowed_count=7,156`, `thesis_driver_authority_count=4,231`, `exact_company_fact_authority_count=2,925`.
- New company/source-role rows in mart:
  - `securities_offering_filing_event=236`
  - `insider_transaction_filing_event=246`
  - `beneficial_ownership_filing_event=247`
  - `proxy_governance_filing_event=239`
- R18 vertical source-route gate remains `600/603` pass; only old `public_order_proxy=3` remains action-required.

Verification:

- `python -m pytest tests/test_sec_capital_market_event_context_rows.py tests/test_source_route_registry_v2.py tests/test_source_coverage_gate.py tests/test_company_public_source_coverage_matrix.py -q` -> `29 passed`.

## Boundary

R25 deliberately stops at filing-event context. The rows are useful for Research Lead / Specialist 判断“公司是否发生某类资本市场/治理披露事件”，但不能直接成为 exact ownership / offering / buyback / insider transaction evidence。

Next exact-parser work:

- Form 3/4/5 XML parser：shares、price、transaction code、ownership change、direct/indirect ownership。
- 13D/13G schedule parser：beneficial ownership percentage、reporting person、event date、activist / passive boundary。
- Offering filing text/table parser：security type、amount、coupon、maturity、conversion terms、use of proceeds、dilution。
- Proxy text/table parser：buyback authorization / actual repurchase、compensation tables、vote outcomes、board/governance changes。
