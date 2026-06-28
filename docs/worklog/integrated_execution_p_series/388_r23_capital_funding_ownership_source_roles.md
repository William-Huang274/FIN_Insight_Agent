# 388 R23 Capital Funding Ownership Source Roles

## Prompt

图二第三层要求补资本、资金、持仓和市场流动性相关数据源。用户明确提到公司投融资图谱、借贷成本、流动资产、长短期负债、基金/私募持仓、宏观货币政策、二级市场资金规模等因素。当前 K5/K6 已有 CapitalMacroExposurePack 和 adapter rows，但还没有全部进入 R18 source-role data mart。

## Decision

先把已有 K5/K6 adapter 中已经 parser-backed 的 debt / credit facility / capital structure / 13F ownership rows 投影到统一 source-role runtime rows。

本轮不把资本层变成 603 公司硬 requirement，因为：

- 有些公司没有债务或可解析 debt footnote rows。
- 13F/ownership 数据是 lagged context，不应该成为所有公司 release gate 的硬需求。
- 当前目标是让已有资本/持仓 rows 能被 Research Lead、specialist、eval、frontend trace 读到，而不是制造新的全市场 source gaps。

## Work Completed

- 新增 source roles：
  - `capital_structure_disclosure`
  - `lagged_ownership_context`
- `src/sec_agent/source_coverage_gate.py`
  - 新增两个 source coverage requirement templates。
  - `capital_structure_disclosure` 为 L1 公司披露资本结构/债务/credit facility context。
  - `lagged_ownership_context` 为 L3 13F/ownership lagged context。
- `src/sec_agent/source_route_registry_v2.py`
  - 新增两个 SourceRouteContract。
  - `capital_structure_disclosure` 使用 `exact_company_fact_authority`，但只限公司披露的债务、credit facility、cash/debt/net-debt、maturity/coupon/covenant context。
  - `lagged_ownership_context` 使用 `bounded_thesis_driver_authority`，明确禁止 `realtime_flow`、current buying pressure、complete ownership、intraday positioning。
- `src/sec_agent/company_public_source_coverage_matrix.py`
  - 新增 observed-row-driven dynamic source role injection。
  - 只有真实 observed parser-backed rows 存在的公司才加入 capital/ownership source roles；未覆盖公司不新增 release gap。
- `scripts/data_expansion/build_capital_funding_ownership_context_rows.py`
  - 新增 projection 脚本，从 K5/K6 `capital_macro_source_adapter_v0_1/capital_ownership_rows.jsonl` 生成 R18 可读 context rows。
- `scripts/data_expansion/build_company_public_source_coverage_matrix.py`
  - 默认 observed rows 加入 `capital_funding_ownership_context_rows_v0_1.jsonl`。
- `scripts/data_expansion/build_r18_data_source_admission_ledger.py`
  - 新 source roles 纳入 company-specific requirement 和 support-surface mapping。

## Result

Projection:

- `capital_funding_ownership_context_rows_v0_1.jsonl`
- `capital_funding_ownership_context_summary_v0_1.json`
- Row count: `7,956`
- Split:
  - `capital_structure_disclosure=2,956`
  - `lagged_ownership_context=5,000`

Rebuilt:

- `company_public_source_coverage_matrix_v0_1.json/jsonl`
- `r18_data_source_admission_ledger_v0_1.jsonl`
- `r18_source_route_registry_v2.json`
- `r18_source_authority_data_mart_rows_v0_1.jsonl`
- `r18_vertical_source_route_gate_rows_v0_1.jsonl`

Metrics:

- Company matrix remains `578` pass / `25` gap; no new hard gaps were introduced.
- R18 registry: `source_role_count=23`.
- R18 admission ledger: strict pass, `row_count=5,039`.
- R18 source authority data mart: strict pass, `row_count=5,039`, `evidence_bundle_allowed_count=5,014`.
- Data mart source-role counts:
  - `capital_structure_disclosure=914`
  - `lagged_ownership_context=409`
- R18 vertical source-route gate remains `600/603` pass; only old `public_order_proxy` gaps remain.

Verification:

- `python -m pytest tests/test_capital_funding_ownership_context_rows.py tests/test_company_public_source_coverage_matrix.py tests/test_source_route_registry_v2.py tests/test_r18_data_source_admission_ledger.py tests/test_r18_vertical_source_route_gate.py tests/test_capital_macro_pack.py tests/test_capital_macro_source_adapters.py -q` -> `39 passed`.
- `py_compile` on touched scripts/source -> pass.

## Boundary

This is a first tranche, not complete capital market coverage.

Remaining capital/funding/ownership/market-liquidity source roles still need contracts and rows:

- offering / S-1 / S-3 / 424B / 8-K / exhibit financing events.
- Form 3/4/5 insider transactions.
- 13D / 13G beneficial ownership and activist context.
- N-PORT / fund holdings beyond 13F.
- buyback authorization and actual repurchase rows.
- short interest, volume/turnover, options IV.
- credit spread, rates, ETF/factor flows.
- working-capital liquidity rows from financial statement analysis: AR, inventory, AP, deferred revenue, current liabilities, short-term debt, CFO, FCF, cash conversion cycle.

All future rows must preserve source boundaries: 13F is lagged context, market liquidity is not company operating fact, and rates/spreads cannot prove company revenue or margins.
