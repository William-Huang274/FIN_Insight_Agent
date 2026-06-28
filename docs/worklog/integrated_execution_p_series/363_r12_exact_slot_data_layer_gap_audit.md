# 363 R12 Exact-Slot Data Layer Gap Audit

## Prompt

用户指出当前不能用“有 context row / 大概能查到”糊弄数据层，要求先审查 603 公司 L2/L3 外部验证源、供应链/订单/proxy、宏观/监管/招聘/渠道/开发者生态、产品级经营指标槽位如何补齐；真正 gap 必须是公开免费可得路径实在获取不到后暴露，且后续还要支持融资图谱。

## Decision

把当前目标从 `source coverage / bounded context coverage` 修正为 `exact-slot data layer completion`：

- `context_only=true` 不算 exact slot。
- 每个 source role 必须有自己的 exact-slot schema 和 required fields。
- L2/L3 proxy 只能提权为 proxy exact，不得提权为公司收入、销量、份额、ASP、库存或 sell-through。
- product KPI exact 只能来自公司披露的产品/segment/metric rows；公开 proxy 不能替代。
- runtime 接入前必须先有 `CompanyExactSlotCoverageMatrix` / `SourceRoleExactSlotCoverage` / `ProductKPIExactSlotCoverage`。

## Audit Evidence

本轮刷新并审查：

```powershell
python scripts\data_expansion\build_company_public_source_coverage_matrix.py
python scripts\data_expansion\build_product_family_source_route_plan.py
python scripts\data_expansion\build_product_slot_relationship_graph.py
```

当前状态：

- `company_public_source_coverage_matrix_v0_1`
  - company_count: `603`
  - requirement_count: `4,418`
  - pass_requirement_count: `587`
  - repair_queue_count: `3,831`
  - public_interface_ready_company_count: `1`
  - partial_public_interface_company_count: `363`
  - public_interface_gap_company_count: `239`
- `family_source_route_plan_v0_1`
  - route_plan_count: `2,917`
  - runtime_family_row_available: `411`
  - runtime_company_row_available: `419`
  - seed_available_not_materialized: `1,059`
  - not_materialized: `1,028`
- `company_product_slots_v0_1`
  - product_slot_count: `6,454`
  - family-bound runtime slots: `6,454`
  - official_surface_slot: `4,432`
  - filings_taxonomy_slot: `1,899`
  - product_kpi_exact_slot: `114`
  - bounded_context_slot: `9`
- `company_reported_product_operating_metric_runtime_rows_v0_1`
  - runtime rows: `5,976`
  - runtime tickers: `186`
  - product KPI exact company coverage in product slots: `77`
  - no product KPI exact slot: `526`

## Main Gaps

- `primary_company_disclosure=417` and `official_product_surface=59` are high-priority because they are the foundation for financial/product KPI and product/spec exact slots.
- Seed-available official/API routes should be repaired next: macro, energy/utility, financial regulatory, regulated product, technology research, auto identity.
- Seed-missing but crawlable routes need source locators and browser/API adapters: trusted external, supply-chain official relationship, public order, hiring, channel offer, developer ecosystem, app ranking, platform review.
- Product KPI exact coverage is still the main company-performance gap: 526 companies lack exact product KPI slots.

## New Architecture Doc

Added:

- `docs/architecture/agent_graph_vnext/18_exact_slot_data_layer_completion_plan.zh-CN.md`

The doc defines:

- exact-slot target;
- current counts;
- source-role exact-slot schemas;
- R1-R5 repair order;
- hard forbidden promotions;
- runtime integration gate.

## Follow-up

1. Implement `ExactSlotContractRegistry`.
2. Implement exact-slot audit scripts:
   - `CompanyExactSlotCoverageMatrix`
   - `SourceRoleExactSlotCoverage`
   - `ProductKPIExactSlotCoverage`
3. Run R2 high-priority repair:
   - `primary_company_disclosure=417`
   - `official_product_surface=59`
4. Then run R3/R4 source-specific repairs by route, not generic crawling.
5. Do not connect these rows to Research Lead/Product Specialist runtime until exact-slot gates explain pass/gap states.

## Verification

- This was an audit/docs/gate-definition step.
- `git diff --check` should be rerun after the doc/checklist updates.
