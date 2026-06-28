# 335 R12 L3 JSON-LD Public Proxy Parser Smoke

日期：2026-06-16

## 问题

334 已经补了 allowed public web snapshot -> bounded structured context rows，以及 GitHub/npm/PyPI/HuggingFace/App Store URL-derived API smoke。但剩余 L3 源里，电商/渠道报价、招聘、公开 tender/order、平台评论/排名最常见的可稳定入口不是网页 DOM，而是网页里的 JSON-LD。

如果不解析 JSON-LD，下游仍会只看到页面 preview，无法拿到产品报价、availability、招聘岗位、公开 tender/contract、review/rating 等可用 proxy 结构。目标是把这些结构化片段纳入 evidence graph，但仍严格禁止提权成公司 ASP、库存、sell-through、销量、份额、订单量或收入事实。

## 完成工作

1. 扩展 `src/sec_agent/public_web_context_parser.py`：
   - 新增 JSON-LD 提取：
     - `<script type="application/ld+json">...</script>`
     - 支持 list / `@graph`。
   - 新增 source-class aware table fact type：
     - `ecommerce_major_platform` / `channel_pricing_snapshot` -> `channel_offer_context`
     - `public_tender_or_contract_portal` -> `public_tender_contract_context`
     - `job_posting_snapshot` -> `hiring_signal_context`
     - `platform_review_or_ranking_snapshot` -> `platform_review_ranking_context`
     - `official_app_store_or_marketplace` -> `app_store_marketplace_context`
     - `developer_ecosystem_snapshot` -> `developer_ecosystem_context`

2. 新增 JSON-LD parser facts：
   - Product / Offer:
     - `name`
     - `sku`
     - `price`
     - `priceCurrency`
     - `availability`
     - 输出 `channel_offer_context`
     - 明确 `not ASP, inventory, or sell-through authority`
   - AggregateRating:
     - `ratingValue`
     - `reviewCount`
     - 输出 `platform_review_ranking_context`
   - JobPosting:
     - `title`
     - `jobLocation`
     - `datePosted`
     - 输出 `hiring_signal_context`
   - Tender / contract lead:
     - `name`
     - `identifier`
     - `datePublished` / start / end date
     - 输出 `public_tender_contract_context`
     - 明确 `not total company order or revenue authority`

3. 新增 deterministic tests：
   - `test_public_web_repair_parses_channel_offer_jsonld_without_sell_through_authority`
   - `test_public_web_repair_parses_job_posting_jsonld_as_hiring_proxy`
   - `test_public_web_repair_parses_tender_jsonld_as_public_order_lead_only`

## 验证结果

已运行：

```powershell
python -m py_compile src\sec_agent\public_web_context_parser.py
python -m pytest tests\test_public_web_gap_repair.py -q
python -m pytest tests\test_runtime_bridge_contracts.py tests\test_source_layer_capability_audit.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_contracts.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
```

结果：

- Public web repair tests：`11 passed`
- Runtime / source-layer / multi-agent eval / Specialist / contracts：`140 passed`
- Source-layer audit strict：`pass`
- GitHub + App Store live smoke 复跑：`pass`
  - `attempted_count=2`
  - `success_count=6`
  - `bounded_gap_count=0`
  - `structured_types=['app_store_marketplace_context', 'developer_ecosystem_context']`
  - `source_layers=['L3']`

## 当前边界

1. 这仍不是全量 L2/L3 backfill。JSON-LD 只能覆盖规范网页结构化数据；很多电商、招投标、招聘、评论页面仍需要 source-specific DOM/API adapter 和实体匹配。
2. 当前 parser 不会做搜索，也不会绕过访问限制；它只处理 Research Lead targeted repair 已允许的 URL。
3. 所有新增 rows 都是 `context_only=true`、`exact_value_authority=false`、`can_support_company_exact_fact=false`。
4. 本轮未跑 DeepSeek full-chain。

## 下一步

1. 补 mainstream financial news / supplier-customer official news 的 allowlist 和 article snapshot parser，先解决 L2 可信补充层进入 evidence graph 的问题。
2. 再补 entity resolver：URL / page title / JSON-LD name 如何绑定 issuer、product、counterparty，避免 parser rows 进入但无法被 specialist 正确消费。
3. 然后跑 1 个 targeted full-chain case，只看 Research Lead targeted repair、Specialist selector 和 Memo 是否真正使用 L2/L3 parser rows。
