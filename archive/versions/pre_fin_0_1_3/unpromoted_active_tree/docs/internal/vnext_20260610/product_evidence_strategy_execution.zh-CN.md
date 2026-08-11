# Product Evidence Strategy 执行报告

- 生成时间：`2026-06-11T13:17:19.219628+00:00`
- 扫描 ticker：`577`
- 扫描 chunks：`192055`
- 产品 taxonomy candidates：`13712`，覆盖 ticker：`577` / `100.0%`
- 产品 KPI candidates：`6663`，覆盖 ticker：`576` / `99.83%`
- 外部验证 source-plan rows：`67`
- commercial tracker rows：`16`，当前策略下全部 blocked

## 方向锁定

- Research target：`public_evidence_research_analyst`
- Non-degradation rule：Do not replace product-business evidence with generic fallback text, weak crawled pages, or unsupported proxy claims.
- Anchor：SEC/global filings are the first extraction path for product taxonomy and company-disclosed product KPI.
- Increment：Third-party market and alternative data are the main incremental layer for product-to-financial judgment when public filings are insufficient.

## 计数

- Taxonomy type counts：`{"business_line": 1160, "customer_market_or_application": 545, "product_or_service_family": 11109, "reportable_segment": 898}`
- Metric family counts：`{"backlog_or_orders": 1708, "product_revenue": 987, "production_or_throughput": 1516, "same_store_sales": 126, "shipments": 777, "subscribers_or_arpu": 149, "unit_sales_or_deliveries": 1400}`
- External source role counts：`{"commercial_market_tracker": 16, "company_disclosed": 16, "official_product_surface": 14, "public_proxy": 21}`

## Runtime 边界

- company_disclosed taxonomy is a candidate until review.
- company_disclosed KPI is not a fact until value/unit/period/product/citation parser passes.
- official_product_surface and public_proxy are context or directional verification only.
- commercial_market_tracker rows remain blocked under current no-commercial policy.
