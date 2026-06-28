# 336 R12 L2 Trusted News And Official Relationship Parser Smoke

日期：2026-06-16

## 问题

上一轮已经把 L3 JSON-LD proxy 入口补进 public web context parser，但 L2 可信补充层仍有一个明显缺口：主流财经新闻、供应商/客户/合作伙伴官方新闻能提供行业事件、竞争背景、供应链关系和验证线索，却不能被当作 issuer 精确财务、产品 KPI、销量、份额或订单量。

如果这类正常信源完全进不来，memo 只会写“数据不够”；如果无边界进入，又会把新闻或官方关系稿误提权成强事实。本轮目标是在 fetch 前做域名/source-class gate，fetch 后只产出 bounded L2 context rows。

## 完成工作

1. 扩展 `lead_supervision` / `official_issuer_repair` 的 source-class 路由：
   - `mainstream_financial_news_article` 进入 market proxy repair allowlist。
   - `supplier_customer_official_news` 进入 supply-chain repair allowlist。
   - Research Lead gap keys 支持 `news_urls`、`mainstream_news_urls`、`supplier_customer_news_urls`、`official_news_urls`。

2. 新增 trusted news URL gate：
   - 只有 Reuters、FT、WSJ、NYT、Nikkei、AP、CNBC、MarketWatch、财新、新华等可信主流新闻域名允许 `mainstream_financial_news_article` fetch。
   - 非可信新闻/博客域名在 fetch 前拦截，返回 bounded gap，不浪费抓取和 token。

3. 扩展 `public_web_context_parser` article parser：
   - 从 `<title>`、meta `description` / `og:description`、`article:published_time` / `date` / `datePublished` 和正文关键句抽取结构化 context。
   - 主流新闻输出 `trusted_news_event_context`。
   - 供应商/客户官方新闻输出 `official_supply_chain_news_context`。
   - structured summary 优先保留 authority boundary，避免长摘要截断后丢失“不能证明 exact KPI / shipment / order volume”的边界。

4. 新增 deterministic tests：
   - `test_public_web_repair_blocks_untrusted_mainstream_news_domain_before_fetch`
   - `test_public_web_repair_parses_trusted_news_article_as_l2_context`
   - `test_public_web_repair_parses_supplier_customer_official_news_as_l2_context`

5. 同步 source-layer capability audit：
   - `mainstream_financial_news`
   - `supplier_customer_official_news`
   - 这两个 expected profiles 不再标为 `not_registered`，而是 `runtime_ready_context` + `article_parser_smoke_pass`。
   - 仍保持 `can_support_company_exact_fact=false`。

## 验证结果

已运行：

```powershell
python -m py_compile src\sec_agent\public_web_context_parser.py src\sec_agent\official_issuer_repair.py src\sec_agent\lead_supervision.py
python -m pytest tests\test_public_web_gap_repair.py -q
python -m pytest tests\test_runtime_bridge_contracts.py tests\test_source_layer_capability_audit.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_contracts.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
```

结果：

- Public web repair tests：`14 passed`
- Runtime / source-layer / multi-agent eval / Specialist / contracts：`140 passed`
- Source-layer audit strict：`pass`
  - `expected_missing_count=10`
  - `runtime_ready_count=7`
  - `article_parser_smoke_pass=2`

## 当前边界

1. 本轮只完成 deterministic parser/gate smoke，不代表主流新闻或供应链官网真实全站 backfill 完成。
2. `trusted_news_event_context` 和 `official_supply_chain_news_context` 都是 L2 bounded context，不能直接支撑 issuer 收入、产品销量、市场份额、ASP、库存、allocation、shipment 或订单量。
3. 真实站点 coverage、实体绑定、page variant 解析、PDF/表格附件解析、访问限制处理和大规模写入 runtime evidence graph 仍是后续工作。
4. 本轮未运行 DeepSeek full-chain。

## 下一步

1. 做 entity resolver：把 L2/L3 parser rows 明确绑定 issuer / product / counterparty / event，避免 Specialist 看到 context 但不知道该放在哪个分析维度。
2. 做 source-specific adapters/backfill：优先补主流新闻、公司 IR/official news、交易所/监管、主流 app/store/developer 平台、招聘/招投标/渠道报价中最能提升产品/行业/供应链分析深度的入口。
3. 再跑 1 个 targeted full-chain case，检查 Research Lead 是否会在 retrievable gap 时真实触发 web repair，Specialist selector 是否吃到 L2/L3 rows，Memo 是否能把 context 写成有投资含义的判断而不是缺口说明。
