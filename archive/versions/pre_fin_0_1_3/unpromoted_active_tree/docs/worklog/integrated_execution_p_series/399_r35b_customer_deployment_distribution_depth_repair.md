# 399 R35b Customer Deployment / Distribution Depth Repair

## Prompt

用户要求继续把 600+ 公司第二层、第三层数据源做深，尤其要让 customer deployment / supply-chain / distribution proxy 不只是 route skeleton，而是有真实可抓、可解析、可进入证据流的 exact slot 或 bounded signal rows。当前阶段承接 R35a Product/Business-KPI exact rows 后的 CustomerDeployment depth 缺口。

## Decision

本轮不把 public order exact、customer deployment、supplier relationship、channel distribution、app adoption 混成同一个强事实。处理原则：

- 公司官方 customer / case-study / deployment / partner / ecosystem / supplier pages 可以作为 L2 bounded thesis-driver signal。
- 渠道报价、电商/应用商店/平台评论类 rows 只能作为 L3 bounded distribution/adoption proxy。
- 禁止把这些 rows 推成 revenue、order value、backlog、shipment、ASP、sell-through、inventory、market share。
- 不允许 URL/probe label 自证，也不允许 guess-only official domain 提权。

## Work Completed

- 新增 `scripts/data_expansion/build_official_customer_deployment_surface_context_rows.py`。
  - 从 `official_product_surface_context_rows_v0_1` 和 Z 盘已抓取 product pages 出发，定位 issuer official customer/case-study/deployment/partner/ecosystem/supplier pages。
  - 支持 official-domain anchor scan、common-path probe、HTTP fetch、title/body signal gate、raw artifact 写入。
  - 输出：
    - `data/manifests/official_customer_deployment_surface_context_rows_v0_1.jsonl`
    - `data/manifests/official_customer_deployment_surface_attempts_v0_1.jsonl`
    - `data/manifests/official_customer_deployment_surface_summary_v0_1.json`
- 接入 `src/sec_agent/layer_acceptance_gates.py` 和 `scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`：
  - official customer/deployment/partner rows 进入 strict customer/order/supply-chain signal。
  - existing channel/app/distribution rows 进入 bounded distribution/adoption proxy。
- 新增/更新 tests：
  - `tests/test_official_customer_deployment_surface_context_rows.py`
  - `tests/test_second_third_layer_depth_parity_matrix.py`

## Quality Fixes During Run

- 修复外文页面解码和弱锚文本问题：`read more`、日文/中文“了解更多”类锚文本回退到页面 `h1/title`。
- 拒绝 low-value surfaces：careers、jobs、support、help、terms、privacy、contact、about/businesses、generic insights、customer support、claims 等。
- 修复 common-path probe 自证问题：probe 生成的 `/case-studies`、`/customers`、`/partners` URL/label 不能作为 body signal；必须从实际页面 title/body 读到 customer / partner / case-study / supplier 等信号。
- 修复 wrong-domain 污染：
  - 发现 ADP 被上游 seed 映射到 `automatic.com`、BBY 映射到 `best.com`。
  - projector 现在接入 `company_domain_locator_cache_v0_1`，仅用于排除 guess-only domains。
  - 只有 `domain_override`、`bing_official_website_locator`、`clearbit_autocomplete` 等 verified source 支撑的 host 可作为 official host；`company_name_domain_guess` 不能提权。

## Results

Final strict projector:

- `row_count=336`
- `success_ticker_count=126`
- `official_customer_order_or_deployment_event=214`
- `supply_chain_official_relationship=122`
- `no_verified_official_host_seed=45` attempts
- bad-domain / low-value pollution audit: `0`

Depth parity matrix:

- `customer_deployment_depth=387/603`
- strict customer/order/supply-chain signal: `241`
- bounded distribution/adoption proxy: `146`
- remaining customer/deployment gap: `216`
- R30 baseline was `158/603`; net improvement is `+229` companies.

Five-dimension depth snapshot after rebuild:

- `product_spec_depth=603/603`
- `product_kpi_depth=428/603`
- `customer_deployment_depth=387/603`
- `capital_market_detail_depth=247/603`
- `market_liquidity_depth=603/603`
- full five-dimension parity: `117/603`

## Remaining Customer/Deployment Gap

Remaining `216` companies are attempt-backed, not silently hidden:

- `action_gap_without_official_product_surface_seed=63`: no official product surface seed to start customer/deployment locator.
- `no_verified_official_host_seed=20` among still-gapped companies: only missing host or guess-only host available.
- Official-path probes mostly return `404`; examples include SK hynix / Samsung common `/case-studies`, `/customers`, `/partners` style paths.
- Some pages fetch but title/body lacks customer/deployment/partner/supplier signal; examples include CATL common-path probes and some utility/industrial partner pages.
- Smaller technical set remains: `403/429/406/307/464`, SSL/timeout, one PDF case study, and site-specific parser gaps.

## Verification

Commands run:

```powershell
python -m pytest tests/test_official_customer_deployment_surface_context_rows.py tests/test_second_third_layer_depth_parity_matrix.py -q
python scripts\data_expansion\build_official_customer_deployment_surface_context_rows.py --max-candidates-per-ticker 6 --workers 16 --timeout-s 12 --replace-output
python scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py
python scripts\data_expansion\build_second_third_layer_depth_gap_action_plan.py
```

Latest targeted tests passed: `16 passed`.

## Follow-up

- Fix upstream official product surface/domain locator for guess-only or missing-host companies before using their official web rows in runtime.
- Add site-specific browser/PDF adapters for blocked or PDF-only official customer/case-study pages.
- Continue depth work on `capital_market_detail_depth=247/603` and `product_kpi_depth=428/603`; these are now larger bottlenecks than CustomerDeployment.
- ProductRelationshipGraph remains open and should use these bounded customer/partner/supplier rows as relationship candidates, not as exact product KPI or order facts.
