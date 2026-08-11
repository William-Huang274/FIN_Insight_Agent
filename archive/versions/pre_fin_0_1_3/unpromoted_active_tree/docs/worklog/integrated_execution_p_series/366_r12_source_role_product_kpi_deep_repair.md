# 366 R12 Source-Role / Product-KPI Deep Repair

日期：2026-06-19

## 问题

用户要求继续补 source-role 更细缺口和 product-KPI 更细缺口，尤其不能把 parser/locator 没做细的问题伪装成“公开源没有”。本轮目标是：

- 对 source-role gap 给出真实 company-level closeout reason；
- 对 product-KPI exact slot 低覆盖做逐公司诊断；
- 能修的 adapter / locator / attempt ledger 先修；
- 剩余不能补的要说明是当前公开 route 真实无可绑定 exact row、resolver 缺官方 seed，还是公司未披露 / 需要商业 tracker。

## 决策

1. 不放宽 exact-slot gate：
   - L2/L3 proxy 不得提权成收入、销量、市场份额、ASP、库存、sell-through。
   - Product-KPI exact 只能来自公司披露或监管/交易所等正式披露路径。
2. 对“已尝试但没写 attempt”的 adapter 先补 attempt ledger，再重建 closeout。
3. 对 developer ecosystem 只接官方 seed，不做 GitHub/npm/PyPI/HuggingFace blind search 提权。
4. Product-KPI 报告拆成 product-family exact、business/segment exact、geography/non-product、候选未过 gate、无候选/非美 parser required。

## 完成工作

- 新增 / 更新阶段文档：
  - `docs/architecture/agent_graph_vnext/19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md`
- OpenAlex technology proxy：
  - `build_v1_openalex_technology_research_context_rows.py` 新增 `v1_openalex_technology_research_attempts_v0_1.jsonl`。
  - `build_exact_slot_gap_closeout_ledger.py` 接入 `openalex_api` attempts。
  - 对剩余 22 个 technology tickers 真实调用 OpenAlex API，全部写入 attempt。
- Developer ecosystem：
  - `build_developer_ecosystem_context_rows.py` 新增 seed registry、attempt ledger、merge 输出。
  - 新增 `data/manifests/developer_ecosystem_official_seed_registry_v0_1.jsonl`，仅包含可解释的官方 GitHub/npm/PyPI/HuggingFace URL。
  - 真实跑 28 个官方 developer seed，27 个 materialized，1 个 404/不可用 attempt。
  - `build_exact_slot_gap_closeout_ledger.py` 接入 developer attempts。
- Product-KPI：
  - `build_exact_slot_gap_closeout_ledger.py` 新增 `product_or_business_kpi_ready_ticker_count`。
  - `build_product_kpi_deep_gap_diagnostic.py` 新增 `gap_reason`、`coverage_bucket`、product-family exact 与 business/segment exact 的分口径 summary。
- Official product catalog exact-slot wiring：
  - 本轮沿用已修好的 `official_product_catalog_parser_pass` exact contract 与 exact matrix 输入，确保 `official_product_surface` gap 不再因为 catalog rows 未入矩阵而误报。

## 结果

### Source-role exact-slot

最新 `exact_slot_coverage_matrix_v0_1`：

- `company_count=603`
- `all_required_exact_ready_company_count=370`
- `partial_exact_ready_company_count=233`
- `no_exact_ready_company_count=0`
- `exact_slot_gap_count=303`
- `developer_ecosystem_proxy ready=31 / gap=45`
- `official_product_surface ready=559 / gap=0`

最新 `exact_slot_gap_closeout_summary_v0_1`：

- `closeout_row_count=303`
- `unclassified_closeout_count=0`
- `public_source_exhausted_gap=256`
- `resolver_gap=45`
- `not_applicable_or_source_gap=2`

剩余 source-role gap：

- `developer_ecosystem_proxy=45`
- `channel_offer_proxy=58`
- `hiring_capacity_proxy=49`
- `regulated_product_context=36`
- `public_order_proxy=33`
- `app_rank_store_proxy=31`
- `technology_research_proxy=22`
- `platform_review_proxy=21`
- `supply_chain_official_relationship=6`
- `auto_product_identity_context=2`

L3 minimum gate：

- `l3_zero_company_count=0`
- `l3_one_company_count=0`
- `l3_gt_one_company_count=603`
- `priority_fail_company_count=0`

### Product-KPI

最新 `product_kpi_deep_gap_diagnostic_summary_v0_1`：

- `product_family_exact_ready_ticker_count=136`
- `business_or_segment_exact_ready_ticker_count=43`
- `product_or_business_kpi_ready_ticker_count=179`
- `geographic_or_non_product_only_ticker_count=7`
- `product_kpi_exact_gap=417`
- `strict_candidate_gap_ticker_count=301`
- `no_candidate_gap_ticker_count=116`

剩余 product-KPI gap 的主要原因：

- `301` 家有候选但不能 runtime 提权，主要因为 geographic/non-product、segment schema 未拆细、percentage/change cell、sentence local relation 未验证。
- `101` 家有官网产品面或 filings taxonomy，但当前 SEC/公开披露扫描没有 product KPI 候选。
- `15` 家非美公司需要 local exchange / company IR / annual report PDF table parser 深挖。

## 验证

已运行：

- `python scripts\data_expansion\build_v1_openalex_technology_research_context_rows.py --from-family-route-plan ...`
- `python scripts\data_expansion\build_developer_ecosystem_context_rows.py --timeout-s 8 --fetch-retries 1 --max-rows-per-probe 3 --tickers ...`
- `python scripts\data_expansion\build_company_public_source_coverage_matrix.py`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict`
- `python scripts\data_expansion\build_l3_minimum_coverage_gate.py --strict`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict`
- `python -m pytest tests/test_v1_openalex_technology_research_context_rows.py tests/test_exact_slot_gap_closeout_ledger.py -q`
- `python -m pytest tests/test_product_kpi_deep_gap_diagnostic.py -q`
- `python -m py_compile scripts/data_expansion/build_v1_openalex_technology_research_context_rows.py scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py`

待本轮最终收尾统一跑更宽 targeted regression / `git diff --check`。

## 剩余边界

- Developer 45 家：不是证明公开源没有开发者生态，而是当前还缺可验证 official docs/package/repo seed；不得做 blind search 提权。
- Channel / app / review / public order：当前已接入 route 尝试失败或无可绑定 exact row；若继续修，需要按 product family 接更细 marketplace、distributor、local tender、official store。
- Product-KPI 417 家：不能用 proxy 补 product KPI；只允许公司披露 / local regulator / exchange / IR table parser 继续深挖。

## 安全说明

- closeout rows 不是 evidence rows，不能进 ClaimCard。
- developer/OpenAlex/channel/order/app/hiring 等 L3 rows 只能支持对应 source-role proxy，不得支持收入、销量、市场份额、ASP、库存、sell-through。
