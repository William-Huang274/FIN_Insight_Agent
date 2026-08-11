# 联网证据机制

## 核心原则

联网检索可以进入 reflection repair，但不能成为 agent 自由搜索能力。

搜索结果、snippet、LLM 浏览摘要都不能直接进入 claim card。必须经过：

```text
search result
 -> source candidate
 -> fetch snapshot
 -> source classifier
 -> parser
 -> authority gate
 -> evidence row or bounded gap
```

## 工具归属

新增 `web_evidence_operator`：

- tool permission: `bounded_execute`
- route authority: `execute_route`
- 输入：结构化 web repair request
- 输出：snapshot metadata、source classification、parser result、source gap

`Research Lead`、`Specialist`、`Verifier` 只能提出 web repair request；不能直接联网。

## Source Class

| Source class | 例子 | 默认 claim scope |
|---|---|---|
| `company_official_product_surface` | 公司官网、官方产品页、官方 support/docs/pricing/status | 产品存在、taxonomy、feature、official pricing |
| `company_ir_material` | IR presentation、annual report、earnings deck | 公司自述、管理层说法、披露上下文 |
| `official_regulatory_page` | SEC、FDA、ClinicalTrials、NHTSA、DART、EDINET、HKEX | 监管事实、登记状态、披露状态 |
| `government_dataset_endpoint` | FRED、BLS、BEA、Census、EIA、FDIC | 宏观/行业/监管 context |
| `commerce_product_surface` | JD、天猫、淘宝、Amazon、BestBuy、Walmart、Target、Currys、Argos | SKU、价格、可售状态、渠道表面存在 |
| `major_financial_news` | FT、WSJ、Reuters、Bloomberg、NYT、Caixin、新华社 | 事件、公开报道、管理层引用线索 |
| `research_developer_signal` | Google Scholar、OpenAlex、Crossref、PubMed、arXiv、GitHub、Hugging Face、npm、PyPI | 技术活动、研究/开发者 adoption signal |
| `social_official_account` | X/小红书/Reddit 官方或验证账号 | 官方声明线索，需账号验证 |
| `social_unverified_or_influencer` | 普通自媒体、营销号、测评号、SEO 站 | lead-only，不能进事实层 |

## 行业 Web Scope 示例

### 消费电子 / 硬件

允许：

- 官方产品页、support page、pricing page。
- 电商平台：`jd.com`、`tmall.com`、`taobao.com`、`amazon.com`、`bestbuy.com`、`walmart.com`、`target.com`、`currys.co.uk`、`argos.co.uk`。
- 大型财经/商业新闻。

允许 claim：

- product presence
- SKU / configuration
- listed price
- availability status
- launch / official feature description

禁止 claim：

- shipment volume
- vendor share
- sell-through
- channel inventory
- gross margin

### 医药 / 医疗器械

允许：

- FDA / openFDA / ClinicalTrials.gov / PubMed / company pipeline page / label page。

允许 claim：

- trial status
- phase
- sponsor / collaborator
- indication
- regulatory status context
- recall / adverse-event context with boundary

禁止 claim：

- prescription volume
- market share
- sales uptake
- causal safety conclusion

### SaaS / Developer Product

允许：

- company docs、pricing、status page、GitHub、npm、PyPI、Hugging Face、marketplace、official blog。

允许 claim：

- product surface
- pricing / packaging if official
- developer adoption signal
- outage / status context
- ecosystem presence

禁止 claim：

- ARR
- customer count
- revenue contribution
- market share

## 新闻 Scope

新闻分层：

1. `primary_company_or_regulatory`
2. `major_financial_news`
3. `industry_trade_press`
4. `social_official_account`
5. `social_unverified_or_influencer`

时事新闻优先使用：

- FT
- WSJ
- Reuters
- Bloomberg
- New York Times
- Caixin
- 新华网
- 其他在 source registry 中 allowlist 的国家级/主流财经媒体

付费墙不可绕过。未合法读取全文时，只能把公开标题/摘要作为 lead，不得声称读过正文。

## Web Evidence Row 边界

新增 source family：

```text
live_public_web_context
```

默认：

```text
context_only; not exact_value_authority
```

只有满足以下条件才可提权：

- source class 为 official / regulatory / company-authored。
- snapshot 已落盘并有 hash / as_of_datetime。
- parser 提取出 value / unit / period / product / citation。
- authority gate 通过。
- claim scope 与 source class 匹配。

否则进入 `Bounded Gap Register` 或作为 lead 保留。
