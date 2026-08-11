# 367 R12 Source-Role / Product-KPI v0.5 And L3 Repair

日期：2026-06-19

## 问题

用户要求继续补 source-role 更细缺口和 product-KPI 更细缺口，尤其不能把 adapter / parser / locator 没做细的问题伪装成公开源不可得。

## 决策

1. 不放宽 evidence authority：L2/L3 proxy 不得提权为 revenue / sales / market share / ASP / inventory / sell-through；Product-KPI exact 只能来自公司披露、监管或交易所正式披露路径。
2. 优先修确定的工程漏斗：full strict Product-KPI repair facts、ClinicalTrials collaborator binding、USAspending ticker / multi-alias 查询噪声、iTunes holding company alias、official careers domain、CDW broad batch matcher。
3. 仍无法补的只写 closeout / gap，不进入 ClaimCard。

## 完成工作

- Product-KPI v0.5：
  - `promote_product_kpi_repair_candidates.py` 默认输入改为 full strict repair facts。
  - 新增 product/category/product-line revenue promotion scope 和 geography/customer/channel/non-product 拒绝 gate。
  - `quality_filter_product_kpi_fact_layer.py` / operating repair / runtime projection 默认接 v0.5。
- Regulated：
  - `build_targeted_regulated_auto_official_api_context_rows.py` 支持 ClinicalTrials lead sponsor / collaborator / organization alias-bound row。
  - 补 `A/ARGX/GSK` sponsor aliases。
- Public order / supply chain：
  - `build_broad_public_contract_award_context_rows.py` 去掉 ticker 查询噪声。
  - 补 AMAT/CRM/HWM/IDXX/WST/COR/FTV/MRVL/ONTO legal/subsidiary recipient aliases。
  - 改为逐 alias 查询、逐 alias 验证、合并 rows。
- App / review：
  - `build_broad_app_store_platform_context_rows.py` 增加 BKNG/FIVN/GTLB/LVS/LYV/MELI/PSKY/RCL/TKO/TTD/TTWO/WBD 官方品牌或子公司 alias 轮询。
- Hiring：
  - `build_broad_official_careers_context_rows.py` 增加 CRM/EME/FFIV/GOOGL/SBUX domain overrides。
  - 针对 49 个 hiring gap tickers 重跑 official careers / ATS locator。
- Channel：
  - `build_broad_channel_offer_context_rows.py` / `build_channel_offer_context_rows.py` 允许 broad batch 下 issuer brand-only match，同时拒绝 accessory/protection/compatible third-party rows。
- Closeout：
  - `build_exact_slot_gap_closeout_ledger.py` 更新 hiring、app/review、regulated closeout 文案，反映最新 route 和 sponsor/collaborator/applicant 边界。
- 新增 deterministic tests：
  - `tests/test_broad_app_store_platform_context_rows.py`
  - `tests/test_broad_public_contract_award_context_rows.py`
  - `tests/test_targeted_regulated_auto_official_api_context_rows.py`

## 结果

最新 `exact_slot_coverage_matrix_v0_1`：

- `company_count=603`
- `all_required_exact_ready_company_count=435`
- `partial_exact_ready_company_count=168`
- `no_exact_ready_company_count=0`
- `exact_slot_gap_count=203`
- `exact_slot_row_count=36,874`

Source-role gap 变化：

| requirement | before | after | 说明 |
| --- | ---: | ---: | --- |
| `channel_offer_proxy` | 58 | 53 | CDW brand-only repair 后仍需 Digi-Key/Mouser/Arrow/Amazon/JD/official-store adapters |
| `hiring_capacity_proxy` | 49 | 43 | official careers/domain repair 有效；剩余为无 issuer-bound job rows 或无稳定公开 job row/API |
| `regulated_product_context` | 36 | 11 | ClinicalTrials collaborator binding 和 alias repair 有效 |
| `public_order_proxy` | 33 | 19 | USAspending alias/noise repair 有效；剩余主要非美/local tender 或无 recipient-bound awards |
| `supply_chain_official_relationship` | 6 | 4 | USAspending alias repair 有效 |
| `app_rank_store_proxy` | 31 | 9 | 品牌/子公司 alias repair 有效 |
| `platform_review_proxy` | 21 | 11 | 品牌/子公司 alias repair 有效 |
| `developer_ecosystem_proxy` | 29 | 29 | GitHub API rate limit 后未新增 official seed；保持 resolver gap，不 blind search |
| `technology_research_proxy` | 22 | 22 | OpenAlex route 已尝试，无 issuer-topic-bound row |
| `auto_product_identity_context` | 2 | 2 | NHTSA make/model 不适用或无 make-bound row |

Product-KPI 最新：

- `runtime_product_kpi_ticker_count=214`
- `product_family_exact_ready_ticker_count=161`
- `business_or_segment_exact_ready_ticker_count=44`
- `product_or_business_kpi_ready_ticker_count=205`
- `geographic_or_non_product_only_ticker_count=10`
- `product_kpi_exact_gap=388`
- `strict_candidate_gap_ticker_count=272`
- `no_candidate_gap_ticker_count=116`

## 验证

已运行：

```powershell
python scripts\data_expansion\promote_product_kpi_repair_candidates.py
python scripts\data_expansion\quality_filter_product_kpi_fact_layer.py
python scripts\data_expansion\promote_product_operating_metric_repair_candidates.py
python scripts\data_expansion\build_company_reported_product_operating_metric_runtime_rows.py --strict
python scripts\data_expansion\build_exact_slot_coverage_matrix.py
python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict
python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict
python -m pytest tests\test_broad_app_store_platform_context_rows.py tests\test_broad_public_contract_award_context_rows.py tests\test_targeted_regulated_auto_official_api_context_rows.py tests\test_product_kpi_repair_promotion.py tests\test_channel_offer_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py tests\test_product_kpi_deep_gap_diagnostic.py -q
```

测试结果：`27 passed`。

## 剩余边界

- `channel_offer_proxy=53`：当前 CDW route 已尽力；需要按 product family 接 distributor / marketplace / official store adapters。
- `hiring_capacity_proxy=43`：已跑 public ATS + official careers；剩余需要更细 site-specific parser 或确认为无稳定公开 job rows。
- `developer_ecosystem_proxy=29`：需要 verified official docs/package/repo seed；GitHub rate limit 下未新增，且不能 blind search 提权。
- `technology_research_proxy=22`：OpenAlex 不足，下一步应接 PatentsView / assignee resolver。
- `public_order_proxy=19` / `supply_chain_official_relationship=4`：USAspending 尽力后剩余主要非美/local tender 或无 recipient-bound awards。
- `regulated_product_context=11`：ClinicalTrials/openFDA sponsor/collaborator/applicant route 尽力；Zoetis 等 animal-health 场景需 openFDA animal/veterinary 或官方监管产品路径另接。
- `product_kpi_exact_gap=388`：不能用 L2/L3 proxy 兜底；剩余需 source-specific segment schema、region dimension、local citation verifier、non-US IR/local exchange table parser，或暴露公司未披露 / commercial tracker gap。
