# 389 R24 Working Capital Liquidity Source Role

## Prompt

图二第三层要求补资本、资金、持仓和市场流动性相关数据源。R23 已把 debt / credit / capital structure / 13F rows 接入 R18 数据基座，但营运资本、流动性和现金转换相关的 SEC structured financial statement rows 仍只停留在普通基本面科目，没有作为资本资金层 source role 进入 Research Lead / specialist / eval / frontend trace。

## Decision

把营运资本和流动性拆成独立 source role `working_capital_liquidity`，而不是继续混在 `capital_structure_disclosure`。该 role 只允许支持 AR、inventory、AP、deferred revenue、current assets / current liabilities、short-term debt、cash、operating cash flow、capex、financing cash flow 等公司披露事实和流动性分析，不允许证明产品需求、产品销量、ASP、市场份额、渠道库存、sell-through、backlog 或未披露融资条款。

同时修复一个 gate 风险：`capital_structure_disclosure` 不能只靠宽泛的 `sec_financial_statement_data_sets` source id 被普通财报行满足；对容易被宽 source id 污染的 source roles 启用 strict source-role / runtime-contract / structured-context matching。

## Work Completed

- `scripts/data_expansion/build_sec_financial_statement_metric_runtime_rows.py`
  - 扩展 canonical metric family：`accounts_receivable`、`inventory`、`accounts_payable`、`deferred_revenue`、`current_assets`、`current_liabilities`、`cash_and_equivalents`、`short_term_debt`。
  - 默认 `max_metrics_per_ticker` 从 `13` 提高到 `24`，避免新增科目被上游 cap 掉。
- `scripts/data_expansion/build_capital_funding_ownership_context_rows.py`
  - 新增 `WorkingCapitalLiquidityRow` projection。
  - 继续保留 `capital_structure_disclosure` 和 `lagged_ownership_context` 的 source boundary。
- `src/sec_agent/source_route_registry_v2.py`
  - 新增 `working_capital_liquidity` SourceRouteContract。
- `src/sec_agent/source_coverage_gate.py`
  - 新增 `working_capital_liquidity` requirement template。
  - 新增 strict role matching，覆盖 `technical_product_spec`、`product_generation_edge`、`product_benchmark_proxy`、`customer_deployment_proxy`、`official_customer_order_or_deployment_event`、`capital_structure_disclosure`、`lagged_ownership_context`、`working_capital_liquidity`。
- `src/sec_agent/company_public_source_coverage_matrix.py`
  - 将 `working_capital_liquidity` 加入 observed-row-driven dynamic source role injection。
- `scripts/data_expansion/build_r18_data_source_admission_ledger.py`
  - 将 `working_capital_liquidity` 纳入 company-specific requirement 和 `capital_funding_ownership_market_liquidity` support surface。
- 测试新增：
  - SEC projector 支持 working-capital metrics。
  - capital projection 区分 working-capital / debt / lagged ownership。
  - source coverage gate 禁止泛化 FSD 行满足 capital structure。
  - R18 source registry 注册 capital/funding/ownership 三类 source roles。

## Result

Rebuilt artifacts:

- `sec_financial_statement_metric_runtime_rows_v0_1.jsonl`
- `capital_funding_ownership_context_rows_v0_1.jsonl`
- `company_public_source_coverage_matrix_v0_1.json/jsonl`
- `r18_data_source_admission_ledger_v0_1.jsonl`
- `r18_source_route_registry_v2.json`
- `r18_source_authority_data_mart_rows_v0_1.jsonl`
- `r18_vertical_source_route_gate_rows_v0_1.jsonl`

Metrics:

- SEC financial statement runtime rows: `10,146` rows / `587` companies.
- Newly admitted metric families include:
  - `accounts_payable=472`
  - `accounts_receivable=456`
  - `inventory=343`
  - `deferred_revenue=383`
  - `current_assets=485`
  - `current_liabilities=485`
  - `cash_and_equivalents=564`
  - `short_term_debt=352`
- `capital_funding_ownership_context_rows_v0_1`: `13,185` rows:
  - `capital_structure_disclosure=2,956`
  - `lagged_ownership_context=5,000`
  - `working_capital_liquidity=5,229`
- R18 registry: `source_role_count=24`, hard gate all zero.
- R18 admission ledger: strict pass, `row_count=6,213`, `can_enter_evidence_bundle_count=6,188`.
- R18 source authority data mart: strict pass, `row_count=6,213`, `evidence_bundle_allowed_count=6,188`, `working_capital_liquidity_fact=1,174`.
- R18 vertical source-route gate remains `600/603` pass; only old `public_order_proxy=3` remains action-required.

Verification:

- `python -m pytest tests/test_source_coverage_gate.py tests/test_company_public_source_coverage_matrix.py tests/test_source_route_registry_v2.py tests/test_capital_funding_ownership_context_rows.py tests/test_sec_financial_statement_metric_runtime_rows.py -q` -> `31 passed`.

## Boundary

R24 still does not complete the full capital / funding / ownership / market-liquidity layer. Remaining source roles need future contracts and parser-backed rows:

- offering / S-1 / S-3 / 424B / 8-K / exhibit financing events.
- Form 3/4/5 insider transactions.
- 13D / 13G activist and beneficial ownership.
- N-PORT / fund holdings beyond 13F.
- buyback authorization and actual repurchase rows.
- short interest, volume/turnover, options IV.
- credit spread, rates, ETF/factor flows.

All future rows must keep authority boundaries: working-capital facts are exact company facts, but they are not product demand proof; 13F remains lagged context; market liquidity sources are not company operating facts.
