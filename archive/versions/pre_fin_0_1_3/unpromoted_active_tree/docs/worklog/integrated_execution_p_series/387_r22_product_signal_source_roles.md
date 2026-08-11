# 387 R22 Product Signal Source Roles

## Prompt

图二第二层要求继续补 Product-KPI / product spec 数据源、产品关系图谱和强信号源。用户强调产品参数、规格、代际、竞品对比、供应链/客户部署信号应进入投研分析，而不能只用财务 exact fact 压制这些信息。

## Decision

先不做泛化爬虫扩张，而是先修通当前已经存在的 R17 product-family evidence rows 到统一 R18 数据基座的链路。

原因：

- R17 已有 NVDA H100/Blackwell 技术规格、benchmark、代际 edge、xAI customer deployment rows。
- 这些 rows 已有 `NonFinancialSignalAuthority` 支持，但没有进入 SourceRouteRegistry / CompanySourceMatrix / R18 Admission / SourceAuthorityDataMart 的统一 source-role 口径。
- 如果先扩全行业爬虫而不修这个 contract 断点，后续新增数据仍会散落在小表里，Research Lead / specialist / eval 不能稳定读取。

## Work Completed

- 新增 source roles：
  - `technical_product_spec`
  - `product_generation_edge`
  - `product_benchmark_proxy`
  - `customer_deployment_proxy`
- `scripts/data_expansion/build_r17_product_family_evidence_rows.py`
  - R17 rows 补 `parser_status=parser_pass`、`structured_fact_status=bounded_context_fact_materialized`。
  - 补 issuer/product/counterparty binding status，避免 matrix gate 因缺 metadata 拒绝 parser-backed rows。
- `src/sec_agent/source_coverage_gate.py`
  - 新增四个 product signal requirement templates。
  - `required_dimensions` 支持显式 requirement id，即 targeted gate 可单独检查动态 source role。
  - 收紧 `technical_product_spec` / `product_generation_edge` source ids，不接受泛化 `company_product_pages`，避免普通产品页误满足技术规格 role。
- `src/sec_agent/source_route_registry_v2.py`
  - 新增四个 SourceRouteContract，全部为 bounded thesis driver，不支持 revenue / ASP / share / sell-through / backlog / inventory / order value exact。
- `src/sec_agent/product_family_source_routes.py`
  - 新增 route definitions。
  - route plan 动态注入上述 route：只有 runtime row 已存在的 ticker/family 才加入，不把 603 家全量硬要求化。
- `scripts/data_expansion/build_r18_data_source_admission_ledger.py`
  - 新 source roles 纳入 company-specific requirement 和 support-surface mapping。
- 默认输入扩展：
  - `build_product_family_source_route_plan.py` 读取 `r17_product_family_evidence_runtime_rows_v0_1.jsonl`。
  - `build_company_public_source_coverage_matrix.py` 读取 `r17_product_family_evidence_runtime_rows_v0_1.jsonl`。

## Result

Rebuilt:

- `r17_product_family_evidence_runtime_rows_v0_1.jsonl`
- `family_source_route_plan_v0_1.jsonl`
- `company_public_source_coverage_matrix_v0_1.json/jsonl`
- `r18_data_source_admission_ledger_v0_1.jsonl`
- `r18_source_route_registry_v2.json`
- `r18_source_authority_data_mart_rows_v0_1.jsonl`
- `r18_vertical_source_route_gate_rows_v0_1.jsonl`

Metrics:

- Family route plan:
  - `technical_product_spec`: `2` routes, runtime-backed.
  - `product_generation_edge`: `2` routes, runtime-backed.
  - `product_benchmark_proxy`: `2` routes, runtime-backed.
  - `customer_deployment_proxy`: `2` routes, runtime-backed.
- Company matrix:
  - Four new roles each have `1 pass`, all NVDA.
- R18 registry:
  - `source_role_count=21`.
- R18 admission ledger:
  - strict pass, `row_count=3,716`.
  - Four new roles each have one admitted row.
- R18 authority data mart:
  - strict pass, `row_count=3,716`, `evidence_bundle_allowed_count=3,691`.
  - `technical_product_spec`, `product_generation_edge`, `product_benchmark_proxy`, and `customer_deployment_proxy` all enter evidence bundle as bounded thesis-driver signals.
- R18 vertical gate:
  - unchanged source-route boundary: `600/603` pass, only `2382.TW/CRDO/DNN` remain action-required for `public_order_proxy`.

Verification:

- `python -m pytest tests/test_source_coverage_gate.py tests/test_product_family_source_routes.py tests/test_source_route_registry_v2.py tests/test_r18_data_source_admission_ledger.py tests/test_r18_vertical_source_route_gate.py tests/test_non_financial_signal_authority.py -q` -> `39 passed`.
- `py_compile` on touched source/scripts -> pass.

## Boundary

This is not full product spec coverage.

Current coverage only proves that existing parser-backed R17 product strong signals can enter the unified R18 data mart without source-role pollution. It does not yet cover all companies, all product families, or all specs such as GPU core counts, CPU architecture details, server configurations, semicap process capability, medtech device specs, or SaaS product capability matrices.

Next work should build product-family source lanes and parsers:

- GPU/accelerator: official datasheets/spec tables, architecture whitepapers, benchmark rows, cloud/OEM configuration rows.
- CPU/server/OEM/networking/power-cooling/semicap: official datasheets/catalogs/configurator/technical docs and comparable dimensions.
- Product relationship graph: competition, substitution, upstream/downstream, customer deployment, supply-chain read-through, benchmark comparable edges.
- Strong signal sources: official customer deployments, cloud instance availability, OEM configurations, supplier/customer official news, benchmark databases, technical whitepapers/docs.
