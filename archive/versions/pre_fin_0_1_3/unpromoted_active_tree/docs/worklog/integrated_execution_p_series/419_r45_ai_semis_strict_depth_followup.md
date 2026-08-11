# 419 R45 AI/Semis Strict Depth Follow-up

## Prompt

用户要求继续深挖 `PIG-4` / `ProductEvidencePack v0.2` 中仍处于 `pass_with_public_boundary` 的 8 家 AI/Semis 公司，目标是把能用公开源补齐的 spec / deployment / proxy evidence 补成 runtime rows；不能把 URL seed、route seed、产品页或新闻冒充为 Product-KPI exact。

目标公司：

- `005930.KS` Samsung Electronics
- `2308.TW` Delta Electronics
- `2317.TW` Hon Hai
- `ACLS` Axcelis
- `ETN` Eaton
- `LSCC` Lattice Semiconductor
- `MCHP` Microchip
- `TXN` Texas Instruments

## Decision

本轮不放宽 `Product-KPI exact`。产品规格、架构、客户部署、end-market adoption、trusted official deployment proxy 可以补足产品分析 depth，但只能支持 bounded thesis driver，不得证明 product revenue、shipment、ASP、market share、sell-through、backlog、order value 或 customer spend。

admission gate：

- 公开 URL 必须真实 fetch 成功。
- HTML/PDF 必须可解析出正文。
- 正文必须命中 issuer/product 相关 expected terms。
- 不通过的目标只进入 attempt ledger，不进入 evidence rows。

## Work Completed

- 新增 `scripts/data_expansion/build_ai_semis_product_depth_followup_rows.py`。
  - 输出 targeted follow-up rows：
    - `data/manifests/ai_semis_product_spec_followup_context_rows_v0_1.jsonl`
    - `data/manifests/ai_semis_customer_deployment_followup_context_rows_v0_1.jsonl`
    - `data/manifests/ai_semis_product_performance_proxy_followup_context_rows_v0_1.jsonl`
  - 输出 attempt / summary：
    - `data/manifests/ai_semis_product_depth_followup_attempts_v0_1.jsonl`
    - `data/manifests/ai_semis_product_depth_followup_summary_v0_1.json`
- 更新 `src/sec_agent/product_intelligence_depth.py`，把三份 follow-up row 文件接入对应 layer：
  - `product_spec_architecture`
  - `customer_deployment_adoption`
  - `product_performance_proxy`
- 新增 `tests/test_ai_semis_product_depth_followup_rows.py`，覆盖：
  - fetch+term match 通过才 admitted。
  - failed / generic page 只进入 attempts。
  - follow-up row 保留 exact-value forbidden claims 和 bounded boundary。
- 重建 `ai_semis_product_evidence_pack_v0_2`。

## Follow-up Rows

本轮 materializer 真实通过 `9/9` targets，失败目标 `0`：

- `005930.KS`：Samsung HBM3E 官方产品页 -> `product_spec_architecture`。
- `2308.TW`：Delta data-center infrastructure 官方产品页 -> `product_spec_architecture`。
- `2317.TW`：NVIDIA Newsroom Foxconn AI factory 官方/可信部署 proxy -> `product_performance_proxy`，并生成 relationship context。
- `ACLS`：Axcelis Purion 官方产品页 -> `product_spec_architecture`。
- `ETN`：Eaton SEC issuer disclosure power-management architecture -> `product_spec_architecture`。
- `LSCC`：Lattice SEC low-power FPGA product families -> `product_spec_architecture`；Lattice SEC end-market/adoption disclosure -> `customer_deployment_adoption`。
- `MCHP`：Microchip PolarFire FPGA 官方 PDF -> `product_spec_architecture`。
- `TXN`：TI MCU / processors 官方 overview -> `product_spec_architecture`。

注意：ETN 和 LSCC 使用 SEC issuer disclosure 是因为本轮官网 product/IR 入口本地 fetch 不稳定或 WAF/403；这些 rows 是 issuer-disclosed product architecture / adoption context，不是细规格页，也不是 customer deployment exact。

## Result

Follow-up summary：

- `target_count=9`
- `admitted_row_count=9`
- `admitted_ticker_count=8`
- `failed_target_count=0`
- `row_count_by_layer`：
  - `product_spec_architecture=7`
  - `customer_deployment_adoption=1`
  - `product_performance_proxy=1`
- parser status：
  - `verified_public_html_text=8`
  - `verified_public_pdf_text=1`

重建后的 V1 AI/Semis ProductEvidencePack gate：

- `company_count=53`
- `depth_status_counts={"pass": 53}`
- `strict_depth_status_counts={"pass": 53}`
- `gap_queue_count=0`
- layer status：
  - `product_profile=53/53 detailed_profile_ready`
  - `product_spec_architecture=30/53 evidence_ready`
  - `customer_deployment_adoption=42/53 evidence_ready`
  - `product_performance_proxy=26/53 evidence_ready`
  - `product_kpi_exact=40/53 exact_or_operating_metric_ready`
  - `product_relationship_graph=53/53 evidence_ready`

解释：strict queue 清空不等于每家公司每层 full coverage。它表示 V1 AI/Semis 每家公司至少有足够的独立产品证据角色进入深度产品分析；缺失的 SKU revenue、shipment、ASP、share、backlog、sell-through 等仍然按 Product-KPI exact / commercial tracker / public-source boundary 暴露。

## Verification

- `python scripts/data_expansion/build_ai_semis_product_depth_followup_rows.py --timeout 20`
- `python scripts/data_expansion/build_ai_semis_product_evidence_pack_v0_2.py --strict`
- `python -m py_compile src/sec_agent/product_intelligence_depth.py scripts/data_expansion/build_ai_semis_product_depth_followup_rows.py scripts/data_expansion/build_ai_semis_product_evidence_pack_v0_2.py src/sec_agent/supervising_analyst.py src/sec_agent/multi_agent_runtime.py`
- `python -m pytest tests/test_ai_semis_product_depth_followup_rows.py tests/test_ai_semis_product_evidence_pack.py -q`：`7 passed`
- `python -m pytest tests/test_ai_semis_product_depth_followup_rows.py tests/test_ai_semis_product_evidence_pack.py tests/test_product_intelligence_graph.py tests/test_product_spec_pack.py tests/test_supervising_analyst_pack.py tests/test_multi_agent_langgraph_routing.py -q`：`47 passed`

## Follow-up

- V1 AI/Semis 可进入下一轮 full-chain / Product Specialist output quality case，但 Memo/ClaimCard 必须继续保留 exact-vs-bounded claim boundary。
- 若后续要把 ETN / LSCC 从 issuer-disclosed architecture context 深挖到更细 product spec，应继续做 browser-rendered / site-specific official product parser；当前 rows 已足够清 strict depth，但不是最细粒度规格库。
