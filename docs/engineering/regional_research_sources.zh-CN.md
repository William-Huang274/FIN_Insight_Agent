# 地区检索与公共数据接入

本轮目标是复用维护中的基础设施，扩大研究者可选择的资料入口。搜索命中、原件可读、历史时点可用、可引用以及研究结论正确是不同验收层级。未安装或没有凭据的服务不应被宣传为已经可用。

## 已实现的调用路径

`read_public_source` 保留既有搜索、日期核验、原文抓取、缓存和引用身份，增加：

- `search_backend`: `auto`、`bing`、`bing_china`、`baidu`、`github`、`bilibili`。
- `search_language`: 如 `zh-CN`、`zh-TW`、`ja-JP`、`ko-KR`、`en-US`、`ru-RU`。该参数控制 SearXNG 通道；不保证其他服务支持同一地区设置。
- 显式选择引擎不触发 Exa/DS 等其他付费检索。`auto` 保留原流程，配置 SearXNG 后在 DDGS 前尝试它。百度只显式选择，不进入默认组合。
- `github` 是仓库发现，不等于 issue、讨论和代码全文均已读。`bilibili` 是视频候选发现，不等于观看、字幕或评论读取。
- `site:zhihu.com`、`site:douyin.com`、`site:jimeng.jianying.com`、`site:eastmoney.com` 等使用网页索引，不冒充平台内部搜索。域名过滤沿用现有本地校验，结果仍须读取原文。

SearXNG 的 `engines` 与 `categories` 同传会合并执行引擎，因此适配器只传明确引擎，并检查返回条目的 `engines`。广告标记条目不进入候选；这不构成对所有软广告或来源可信度的自动认证。GitHub 的更新时间不被当作文章发布日期。验证码、限流、连接故障与正常空结果分开返回。

配置 `FIN_AKTOOLS_MCP_URL` 后开放 `query_public_data`，通过 **AKTools 官方 MCP** 调用 `search_interfaces`、`describe_interface`、`get_data`。FIN 不复制 AKShare 抓取器。以中文关键词找接口，查看来源、参数、单位及范围后取数；接口名不是新增模型工具。支持 `FIN_AKTOOLS_TOKEN` Bearer 认证，凭据不进入模型参数。

当前数据与历史可见性分开：过去截止日任务默认不开放未经版本核验的当前数据表；东方财富新闻只返回发布时间不晚于截止日的候选定位信息，正文仍通过既有工具核验。当前返回表亦不自动升级为 NumericFact 或已验证引用。该限制需要以后通过供应商历史版本合同逐项放开，不能以统计期间替代公开日期。

`read_regional_disclosures` 接 TWSE 官方 OpenAPI，支持上市公司目录与当前重大讯息，查询、分页、十分钟线程内缓存。历史任务只能用当前公司名称/代码/网站定位，不能把当前资本额、管理层或公告快照带入历史研究。本入口不是完整历史 MOPS 档案。两个新工具都进入原有结果保存/回读目录，并向独立复核者开放。

## 现成方案与边界

| 范围 | 采用/候选 | 本轮状态与下一步条件 |
|---|---|---|
| Bing 中外入口 | [SearXNG](https://docs.searxng.org/dev/search_api.html) | 已接 HTTP JSON；中国域名与国际域名分别配置。中国入口命中腾讯产品原件；国际入口有返回但复合查询相关性不足，不能宣称质量验收通过 |
| 百度 | SearXNG 现成 Baidu 引擎 | 已接选择入口；本机实测 CAPTCHA，默认不调用，不绕过验证 |
| GitHub | SearXNG 内置官方 REST 仓库搜索 | 经已配置网络代理取得仓库结果；源码/issue 的深入读取不能用仓库搜索替代 |
| B 站 | SearXNG 内置 Bilibili 引擎 | 有现成实现，本机直连及代理仍 TLS 失败；不可算可用视频取证 |
| 知乎、抖音、B 站等 | [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 用户已选择该栈，登录接入留待后续；本轮不启动个人会话采集。之前调查过 TikHub，当前不继续该供应商接入 |
| 即梦 | [火山引擎即梦 API](https://docs.volcengine.com/docs/JimengAI/QuickStart?lang=zh) | 查到的是生成接口，不能冒充社区搜索 API；暂走公开页面及其他社区的产品体验资料 |
| 东方财富/同花顺公共数据 | [AKShare](https://akshare.akfamily.xyz/data/stock/stock.html)、[AKTools](https://github.com/akfamily/aktools) | 官方配套 MCP 已接；东方财富新闻实际取数通过，同花顺主营介绍本机 TLS 失败。开放源码适配不等于数据供应商 SLA |
| 同花顺官方 Financial-API | [Financial-API](https://github.com/HiThink-Tech/Financial-API) | 六个托管 MCP 域、72项能力按需发现；六域各一次真实取数通过。与上一行网页抓取及 iFinD 独立；历史版本限制见下文 |
| 付费财经标准接口 | [Choice EMQuant](https://quantapi.eastmoney.com/Upload/EMQuantAPI_Python.pdf)、[iFinD](https://quantapi.51ifind.cn/gwstatic/static/ds_web/quantapi-web/download.html) | SDK/HTTP 及账户权限独立，不能以 AKShare 可访问推断已购买专业数据权限 |
| 台湾 | [TWSE OpenAPI](https://openapi.twse.com.tw/) | 公司目录与当前重大讯息已真实读取；其他接口和完整历史档案未一并验收 |
| 日本披露 | [EDINET 官方 API 说明](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html) | v2 需申请密钥；未配置，不把 J-Quants 行情当申报全文 |
| 日本行情 | [J-Quants](https://jpx-jquants.com/en/spec/quickstart) | 有官方 API；需账户/方案，且个人数据使用与面向用户的产品授权需区分 |
| 韩国披露 | [OpenDART](https://engopendart.fss.or.kr/guide/detail.do?apiGrpCd=DE001&apiId=AE00001) | 已配置密钥，中英披露目录均真实读取通过，保留申报日期及更正版本；DART 不等于 KRX 全部行情，全文读取未由目录验收替代 |
| 香港披露 | [HKEX IIS](https://www.hkex.com.hk/Services/Market-Data-Services/Infrastructure/Issuer-Information-feed-Service-%28IIS%29?sc_lang=en) | 有正式披露传送服务与接入规范，需供应商准入；暂用 HKEXnews/发行人公开原件，不冒充免费 SEC 同类 API |
| 澳门 | [MOX](https://cmox.mo/) | 找到公开披露页面；本轮未找到可直接开通、文档完备的标准开放 API，保留网页原件路径 |

微软旧 [Bing Search APIs 已于 2025-08-11 退役](https://learn.microsoft.com/en-nz/lifecycle/announcements/bing-search-api-retirement)。本接入使用 SearXNG 维护的网页引擎，不是退役 API，也没有重新实现 Bing HTML 解析器。现有 DDGS 的 Bing 引擎在所查源码中被禁用，不能只改一个 backend 参数宣称接通。

OpenBB 可作为多供应商金融数据平台候选，但不能替代社区内容和全球披露全文。MediaCrawler 等浏览器爬虫仍有登录、会话及维护成本，本轮不把它们接成默认无人工检索路径。当前选择 SearXNG + AKTools + 官方披露接口，避免另造一个通用爬虫平台。

## 官方接口与搜索验收

### 同花顺 Financial-API 与韩国 OpenDART（2026-11-10）

同花顺官方新平台为 [Financial-API](https://github.com/HiThink-Tech/Financial-API)，不是 iFinD，也不是 AKShare 的同花顺抓取接口。已阅读仓库 README、REST 通用契约、MCP 接入及业务路由，并用实时 `tools/list` 验证六域：meta、a-share、a-share-index、fund、futures、options。配置 `HITHINK_FINANCE_API_KEY` 后，`query_hithink` 向作者和独立复核者统一提供 catalog/describe/call。每域按需发现，选定工具返回完整原生 schema；调用不重写模型参数、不逐次重复加载全部清单。现有保存及 `read_saved_result` 入口保留完整返回，大结果只向当前上下文披露预览。

六域均已完成最小真实取数：标的检索、单只A股行情、区域指数目录、单只基金资料、期货品种、期权品种。72项工具全部可发现和按原生契约调用；这不代表72项分别已做数据质量验收。官方 MCP 的期货/期权 outputSchema 使用 OpenAPI `nullable`，与标准 JSON Schema 不同；适配仅转换该声明，由 SDK 的验证钩子继续校验所有约束，不改原始空值、不放过数值类型错误。HTTP/MCP正常不等于业务成功，须 `code=0`，错误码和 request_id 保留。

本接入覆盖官方六个托管 MCP 的公开研究数据，不重复安装 CLI、另建 DuckDB、批量下载全市场历史或开放端内专用能力。CLI/SDK/REST 是同一数据服务的其他使用方式，不是每种都要维持一套运行链。公开能力不包括港美股行情、新闻/公告/研报全文、Level-2和交易；完整支持范围以实时清单及官方文档为准。

历史截止日任务：元数据仅可用于标的定位，当前公司属性不作为历史事实；其他数据在未建立“当时已公开版本”合同前返回明确反馈，不把今天取得的财务表伪装成过去可见数据。因此本次并未完成同花顺数据对历史研究的全面引用与计算绑定。当前任务的数据返回同样保留供应商身份、字段和时间，不能仅因取数成功就标为 NumericFact。

配置 `OPENDART_API_KEY` 后，`search_korean_disclosures` 使用官方韩文 `/api/list.json` 或英文 `/engapi/list.json`。两条路径实际认证及目录读取通过；保留原始申报号、更正版本和公开日期，返回对应原件链接。模型自行选择公司代码、语言、期间和分页，不能以当前最新报告覆盖原截止日版本。当前是披露发现，不是韩国股票行情或全文/XBRL全部接入。

部署方把本机自定义凭据变量映射到上述标准变量；密钥只进入宿主/容器环境，不写入 Git、提示词、工具参数或回执URL。新工具沿用当前任务授权和回读机制。

### Bing 亚太搜索实测边界

对中国、日本、韩国、新加坡、台湾的六类查询分别调用大陆与国际入口，并检查原始源站请求、语言市场参数、直连/代理、短语及 RSS 对照。中国产品名能命中正式官网，但宽泛组合查询常退化为首词主题，部分国际路径出现无关站点；`site:` 查询也发生约束被源站忽略。完整查询实际送达，因此不能把该结果归因于模型没给完整查询，或仅修改HTML解析器宣称解决。

单一明确 `site:` 约束在适配层做域名核对；若所有候选违背该约束，返回 `searxng_site_constraint_ignored`，不伪装成正常零结果。多重/OR查询不擅自简化。引用短语或具体产品/机构名可能改善发现，但不保证相关性。两条入口已接通传输，**Bing 单独覆盖亚太公开资料调查的质量验收未通过**；仍需现有 DS 搜索及官方原件路径互补。没有用这组预检答案注入研究模型。

社区方向按用户选择转向 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)，本轮不启动登录、不导入个人会话、不宣称已能读取视频/评论。EDINET 尚无密钥；官方 FAQ 第四节 Q20 记录认证后白屏与弹窗许可相关，应核对站点级弹窗设置，不能据此认定本机根因已确认。

## 可复现部署

1. 复制 `deploy/agent_server/searxng.settings.example.yml` 到私有运行目录，生成私有 secret；按网络环境在个别引擎配置 `proxies`，不关闭 TLS 校验。
2. 设置 `FIN_SEARXNG_SETTINGS`，运行 `docker compose -f deploy/agent_server/regional_search.compose.yml up -d`。镜像固定 digest；不挂研究库、不建立数据库卷；限制内存和日志。仅绑定本机。
3. 研究服务设置 `FIN_SEARXNG_URL` 为它实际可访问的服务地址。Docker 内不能使用宿主的 `127.0.0.1`，按部署网络使用宿主网关或服务 DNS。
4. 在独立环境安装 `aktools==0.1.5 akshare==1.20.37`，按官方命令启动 `python -m aktools --host 127.0.0.1 --port 22847 --timeout 15 --cache-ttl 120`。跨容器访问时选择正确监听地址，必须设置 `AKTOOLS_TOKEN`；研究端使用相同令牌的 `FIN_AKTOOLS_TOKEN` 和 `/mcp` 地址。不要把令牌放进命令行或 Git。
5. 执行 `tests/test_regional_search.py`、`tests/test_public_data_tools.py`、既有外搜/日期/工具交接测试；用实际容器检查工具 schema、一次选择引擎查询、一次原文读取和 MCP 查询。模拟测试不代表源站可用。

研究模型没有为本次工程预检付费调用；预检找到的产品和原件不注入后续研究任务答案。当前未验证的社区和地区不可宣称“全球资料已覆盖”。
