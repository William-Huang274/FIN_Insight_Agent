# FIN 0.1.3 S1-08：Web Search Provider 广泛调研、Firecrawl 试跑与查询编译器处置

日期：2026-08-08

## 结论

本轮没有找到一款可以不经产品适配、直接替代 SourceHunter 的“万能搜索 API”，但找到了一条可执行路线：

1. `Firecrawl Search` 的 keyless 路径可以立即作为第二个 provider-neutral diagnostic baseline。六个 issuer/regulatory 查询 6/6 terminal，官方域补充路线 3/3 exact target-in-pool，证明其 JSON、域过滤和成本边界适合 FIN 的 capture-first comparator。
2. customer/supply 六个通用查询虽然 6/6 成功，却 0/6 命中冻结目标。该结果不能全部归因 Firecrawl：FIN 当前查询编译器已经计算 Microsoft、TSMC、Micron、Dell、NVIDIA 等 evidence-owner `entity_keys`，但实际 `query_text` 没有包含这些实体或关系方向；正式 Tencent bilingual plan 也采用 subject-company＋通用 slot 词，存在同类表达缺口。
3. 因此暂不使用错误查询计划继续横测更多付费 API。下一项先在 S1-08 内完成 provider-neutral relationship-aware SearchIntent compiler 与 typed source-equivalence evaluator 的零调用修复；通过后再执行一次 Firecrawl 完整 24-query comparator。
4. 如果仍需要第二家有 Key Provider，优先申请 `Exa` 补语义发现能力；随后用 `Serper` 或 `DataForSEO` 作为 exact Google-SERP control。Firecrawl＋Exa 是互补组合，不是二选一重复采购。

本轮没有调用 DeepSeek、没有抓取正文、没有 Evidence promotion，也没有缩减 Internal Alpha source claim。Firecrawl 仍是 `promising diagnostic candidate`，不是 production adapter。

## 调研方法与边界

- 只采用服务商官方文档、官方价格页或项目官方仓库；价格是 2026-08-08 观察值，采购前必须重验。
- 区分 raw search、semantic search、SERP、crawler/extractor、synthesized deep research，避免把不同能力放在一个 useful@10 指标里。
- 先检查现有运行时凭据；当前没有可安全复用的 Tavily、Exa、Brave、You、Valyu、Parallel、Linkup、Perplexity、Serper、DataForSEO、Firecrawl 或 Jina Key，因此只试用不要求新凭据的路径。
- raw response 必须先原子保存，再做解析和终态；没有 capture 的调用不计有效证据。
- 所有搜索结果仅是 locator candidate；日期、source identity、relationship direction 和 Evidence promotion 仍由 FIN 本地控制面裁决。

## Provider 市场地图

| Provider | 类型与官方能力 | 2026-08-08 官方价格信号 | FIN 建议角色 |
| --- | --- | --- | --- |
| [Firecrawl Search](https://docs.firecrawl.dev/api-reference/endpoint/search) | Search 可返回 URL/title/description，并可选择后续 scrape；支持域与时间过滤，最多 100 条 | [2 credits/10 results；keyless 1000 free credits/月](https://www.firecrawl.dev/blog/firecrawl-keyless-launch) | 当前无 Key baseline、官方域定向、后续 fetch 入口 |
| [Exa](https://exa.ai/docs/reference/search) | semantic/neural search、域控制、publishedDate、financial report category、可取 text/highlight | [Search $7/1k（最多 10 条）](https://exa.ai/pricing?tab=api) | 未知资料与机制证据的 semantic discovery；首选新 Key |
| [Serper](https://serper.dev/) | Google SERP API、低延迟、结构化 organic/news 等结果 | 2500 free；Starter 标示约 $1/1k | exact official-target recall control |
| [DataForSEO SERP](https://dataforseo.com/apis/serp-api/pricing) | 多搜索引擎 raw SERP，standard/priority/live 三档 | 10 results live 约 $0.002；有最低充值 | 更严格、可扩展的 SERP control 与批量测试 |
| [Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started) | 独立索引、web/news、operators、date/country/lang 与 extra snippets | [$5/1k，并有月度免费 credit](https://api-dashboard.search.brave.com/documentation/pricing) | index-diversity / fallback，避免全依赖 Google 系 |
| [Perplexity Search API](https://docs.perplexity.ai/docs/search/quickstart) | 独立 raw search endpoint，不生成 LLM answer；域、语言、region、date/multi-query/content controls | [$5/1k](https://docs.perplexity.ai/docs/getting-started/pricing) | raw-search comparator 备选 |
| [You.com Search](https://you.com/docs/api-reference/search/v1-search) | web/news，domain、country/lang、freshness/date，最多 100 条 | [$5/1k](https://you.com/pricing?hsLang=en) | raw-search comparator 备选 |
| [Tavily](https://docs.tavily.com/examples/quick-tutorials/search-api) | agent-oriented web search，domain controls、basic/advanced search | [1000 free credits/月；PAYG $0.008/credit](https://docs.tavily.com/documentation/api-credits) | 快速 agent-search 集成备选，不优先于 Exa/SERP control |
| [Parallel](https://docs.parallel.ai/search/advanced-search-settings) | one-shot/agentic search，domain/date/max-results controls | [Search $0.005/10 results](https://parallel.ai/ai/pricing) | 低成本 comparator 备选 |
| [Linkup](https://docs.linkup.so/pages/documentation/endpoints/search/overview) | standard/deep search，source/date controls，可返回 results 或 sourced answer | [standard $0.005/call，deep $0.05/call](https://www.linkup.so/pricing) | raw result 模式备选；sourced answer 不得直接晋升 |
| [Valyu](https://docs.valyu.ai/api-reference/endpoint/search) | web＋proprietary/finance source presets、full text、relevance、publication date、per-result cost | [web $1.50/1k retrievals，finance $8/1k](https://docs.valyu.ai/pricing) | 后续 licensed finance-source lane，不作为第一家 broad search |
| [Kagi Search API](https://help.kagi.com/kagi/api/overview.html) | premium search、lenses/domain ranking/custom rules，public preview | [$12/1k](https://europe-west2.kagi.com/api/pricing) | 高价人工对照，不优先进入当前 S1-08 |

### 深度研究 API 的边界

[You.com Finance Research](https://you.com/docs/guides/finance-research) 等产品可以快速产生带引用的金融研究答案，但它们已经完成资料选择、综合和写作。FIN 可以把这类服务用作外部 benchmark、source suggester 或 supervisor evidence，不应把结果直接送入核心 SourceHunter 并宣称 FIN 自己完成了 Agentic Search/Research，否则会绕过 Evidence Gate、研究过程评价和内容质量归因。

## 开源轮子结论

1. [SearXNG](https://docs.searxng.org/) 没有自有索引，是多个上游引擎的 metasearch。仓库已有三案实测：实际上只剩 DuckDuckGo 返回，Brave 429、Bing date filter 不兼容、Google inactive，因此继续保持 diagnostic-only。
2. [DDGS](https://github.com/deedy5/duckduckgo_search) 是抓取/聚合多个搜索入口的客户端。本轮临时安装因依赖与环境启动成本未形成成功查询，不产生能力结论；即使跑通，也不具备付费 API 的稳定 SLA 和索引权威。
3. [Crawl4AI](https://github.com/unclecode/crawl4AI)、Trafilatura、Playwright 是 URL 已知后的抓取、正文与动态页工具，不是 broad-search index。它们继续属于 locator 之后的 document lane。
4. Jina `s.jina.ai` 当前无 Key 请求返回 401；它可以作为带 Key 的 search/reader 备选，但本轮没有形成有效样本。
5. Google Custom Search JSON API 已对新客户关闭并计划于 2027-01-01 停止；Bing Search APIs 已于 2025-08-11 退役，不进入新集成候选。

## Firecrawl 有界试跑

### A1：无效探索，不计证据

最初一条 DELL regulatory 查询实际返回 200，并在 rank 2 出现 DELL FY2026 10-K 官方镜像。随后批量输出在 Windows GBK console 发生 `UnicodeEncodeError`，且响应没有在显示前原子保存。因此整组标记为 `invalid_not_counted`，不能凭记忆补写，也不能冒充 capture-first 成功。

### A2：issuer/regulatory，capture-first

- 6/6 terminal，12 credits，p50/max=`2564/2685 ms`；
- exact target-in-pool=`3/6`；另外 DELL regulatory 与 MU issuer 出现可能的官方同源别名，但未经过 typed source-equivalence，不计 exact 命中；
- provider date field=`0`，所以 Firecrawl 搜索结果不能成为日期权威；
- raw request/response、safe request、call terminal、aggregate terminal 和 assessment 均已本地保存。

### A3：官方域定向

对 A2 的三个 exact miss 使用新的 official-domain route，而不是重复相同请求：

- DELL issuer：目标 transcript rank 4；
- DELL regulatory：SEC 10-K exact rank 1；
- MU issuer：prepared remarks exact rank 8；
- 合计 3/3 exact target-in-pool，6 credits。

这证明 official-domain lane 值得保留，也证明“搜索 API 必须有域约束”是实际能力，不只是配置美观。

### A4：customer/supply 通用查询

- 6/6 terminal，12 credits；
- exact target-in-pool=`0/6`；
- 结果大多主题相关，有 Dell/NVIDIA/Micron 官方页面，也有行业评论，但没有进入冻结的跨实体一手目标池。

不能把 0/6 直接写成 Firecrawl provider failure。冻结目标的证据 owner 本来就是跨实体：例如 Microsoft 的 capex/demand disclosure、TSMC 的 capacity disclosure、Micron 的 HBM remarks、Dell 的 server demand transcript。当前通用查询只写 subject company＋customer/supply 概念，没有明确 evidence owner、关系方向和 source family。

## 项目内最早责任面

`src/sec_agent/s1_08_candidate_generation_runtime.py::compile_initial_queries` 当前执行：

```text
entity_keys = _entities_for_role(...)
query_text = case_key + research_objective + generic role query_terms
```

即：planner 知道该找谁，但查询 compiler 没把“谁在谈谁、由谁披露什么”写给 external search。`entity_keys` 只进入本地候选过滤，不进入 provider-visible query。正式 bilingual comparator 的 customer/supply 查询也只包含 Dell/Micron/NVIDIA 与通用 slot 词，没有使用已有 catalog 中的 Microsoft/TSMC 等关系实体。

这意味着 Tencent 0/12 仍是其冻结 provider/query contract 的真实失败，但不能再把“换 Provider”视为唯一修复；继续用相同表达测试 5 家服务商，会重复测量同一个项目内 query-plan 缺口。

## 重新冻结的检索架构

```text
Evidence Slot
 -> relationship-aware SearchIntent(subject, evidence owner, claim direction, period, source family)
 -> precise official/SERP lane OR semantic open-web lane
 -> raw locator capture
 -> typed canonical source identity / date verification
 -> candidate pool gate
 -> ranking
 -> document fetch/parser
 -> Evidence Gate
```

必须保留两类互补路线：

1. **Known-target/official lane**：official-domain、SEC/IR、Serper/DataForSEO 类 exact SERP。它负责高召回找已知的一手披露。
2. **Unknown-discovery lane**：Exa、Brave、Perplexity Search、You Search、Firecrawl broad search。它负责发现 planner 事前不知道 URL 的产业链、行业和机制材料。

Provider date 只能是 telemetry。最终发布日期必须在 raw capture/fetch 后由 FIN 的 typed date adjudicator 绑定；同一事件的不同页面也不能自动视为同一 source。source equivalence 只允许 SEC accession、官方 canonical URL、verified content identity 等可审计规则。

## 选择顺序

1. 先使用已经可运行的 Firecrawl keyless，不立即采购。
2. 查询编译器零调用通过后，用修复后的相同 24-query contract 跑 Firecrawl 完整 comparator。
3. 若 Firecrawl 仍缺 semantic discovery，申请 Exa Key；它与 Firecrawl 的 official/domain lane最互补。
4. 若需要验证“是不是 Firecrawl/Exa 排序偏差”，再接 Serper 或 DataForSEO 做 raw SERP control。
5. Brave 用作独立索引多样性；Valyu 等 finance/licensed source 只在公开来源证明不足后单独立项。

## 当前下一项

`S1_08_PROVIDER_NEUTRAL_RELATIONSHIP_AWARE_SEARCH_INTENT_COMPILER_AND_SOURCE_EQUIVALENCE_EVALUATOR_ZERO_CALL_IMPLEMENTATION`

范围固定为：

1. 将 `subject entity / evidence owner entity / entity aliases / relationship direction / period / source family / language` 编译为 provider-neutral SearchIntent；
2. customer/supply slot 按 counterpart entity 形成受预算约束的 fan-out，不能把多个主体揉成一条无法归因的长 query；
3. broad 与 official-domain route 分开计预算、结果与失败；
4. exact URL 与 typed source-equivalent 分账，禁止“同一财报期”自动等价；
5. 用 DELL/MU/NVDA full-fake、cross-case、wrong-direction、future-date、alias collision、permutation mutation 证明；
6. 不联网、不调用模型、不接入 SourceHunter production。

通过后才单独签发一次 Firecrawl 24-query comparator。该 comparator 失败时再决定 Exa/Serper 资格，不进入逐 Provider、逐 query 的无限修补。

## 不可变证据

- A2 terminal SHA256=`4016c0644ad3060a22e1d1611578c60a7adf142d5e5a5ffe8384f62d684a9bcc`
- A2 assessment SHA256=`9150fd338da0f1d733190f555d79b9ce9bd025524a647aa32e9c4f77cb877190`
- A3 terminal SHA256=`98c543ce15b8014553fdf539bc3bcfe828519686db11a8b1ac0e3253bfbb5089`
- A3 assessment SHA256=`f6c2ca99c1e6fbdea029389826c315001242e227b200d37442c5807d6fcb814b`
- A4 terminal SHA256=`0f3339d0c4cddbc16c5c8ea540bebe035e48e534f774df255b9ad6b8fffc0962`
- A4 assessment SHA256=`cc64757b8fd7f01e7b3abdae40687131428d2a3e7110f81752d94dfc7597c24f`
- raw capture roots=`artifacts/runtime/provider_market_scan/firecrawl_keyless_a2_20260808`、`firecrawl_keyless_a3_official_domain_20260808`、`firecrawl_keyless_a4_customer_supply_en_20260808`
- raw captures 保留本机、Git ignored；Git 只保存本工作记录、摘要、digest 和产品/技术处置，不保存网页正文或凭据。
- JSON 与两个 Project OS JSONL 全量解析通过，六个 capture/assessment SHA256 重算一致；Project OS focused=`15 passed`。新零调用 scope preflight=`pass / 0 blocker`，`additional_S1_08_live_attempts` 仍为 `blocked / 1 blocker`；新增文本 credential-like scan 与 `git diff --check` 均通过。
