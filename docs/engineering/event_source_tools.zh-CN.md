# 新闻事件研究的行情、公开发言与政策原件

公司披露的表单、外国发行人、附件和官网受阻替代路径见[公司披露读取合同](company_disclosure_routes.zh-CN.md)。

接口及源码核对日期：2026-11-06。此变更提供研究工具，不判定新闻真实性、市场因果或政治结论，不启动付费研究。新增能力复用原生 harness 的授权、来源回执、计算绑定和恢复入口，不增加执行流程。

## 1. 现状与选型

项目已有 Yahoo 日线快照脚本，但未向原生组织研究会话提供盘中行情工具。本次将只读行情接到现有公开网络授权，X 原帖读取接到 `read_public_source`。现有 Exa / DS / DDGS 搜索次序和 SEC 公司披露路径不变。

| 候选 | 实际检查的代码或接口 | 本次采用范围与限制 |
| --- | --- | --- |
| [yfinance](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py) | history 起止时间、日内保留期、调整与修复参数 | 采用相同公开 Yahoo chart 数据源的薄适配，不安装另一套研究框架；不自动复权或修补缺失柱，不宣称逐笔或实时全市场覆盖 |
| [alpaca-py](https://github.com/alpacahq/alpaca-py/blob/master/alpaca/data/historical/stock.py) | StockHistoricalDataClient、bars / quotes / snapshots 和 feed | 正式行情升级候选；[官方说明](https://docs.alpaca.markets/us/docs/about-market-data-api)区分 IEX 与 SIP，免费 IEX 不是所有美股成交。当前未配置凭据，未接入或调用 |
| [X 官方 Python SDK](https://github.com/xdevplatform/xdk-python/blob/main/xdk/posts/client.py) | recent search 的时间、字段、expansions 和分页 | 完整账号检索与分页的升级候选；当前未配置官方 API，未产生其费用。[访问与价格](https://docs.x.com/x-api/getting-started/pricing)需按账户核对 |
| [react-tweet](https://github.com/vercel/react-tweet/blob/main/packages/react-tweet/src/api/fetch-tweet.ts) | 公开 syndication 接口与返回对象 | 参考其公开嵌入通道，Python 薄适配已实现并实测；不引入前端库，不保证端点稳定或完整搜索覆盖 |
| [Twikit](https://github.com/d60/twikit/blob/main/twikit/client/client.py) | login、cookies、内部 GraphQL | 此次不引入登录态抓取，避免账号会话维护成为隐含前提 |

公开可访问不等于商业再分发授权。生产缓存和展示需按供应商条款配置；本次仅验证本地研究读取，不承诺许可证或 SLA。

## 2. 工具与状态合同

`read_market_prices(symbol, start, end, interval, include_extended_hours, offset, limit)`：

- 起止时间必须带时区，结束时点排他；仅返回完整柱。支持 1m / 5m / 15m / 60m，留存范围仍受供应商限制。
- Yahoo 对 `60m` 请求可能返回 `dataGranularity=1h`，适配层按等长别名接受，回执同时保留请求粒度与供应商原始粒度。不同长度或缺失粒度仍拒绝，并返回两者以便定位；不重采样、不修改 OHLCV。
- 返回币种、交易所时区、柱起止、可识别的交易时段、OHLCV、采集时间、请求范围、来源网址及回读参数。缺失时段明确为未知。
- `realtime_status=not_guaranteed`，延迟未知。当前返回的历史区间不等于当时归档版本；无本地调整也不等于证明供应商从未修订历史。
- 结束不能晚于当前时间或任务截止时点。现有合同的 UTC 零点表示包含该自然日；非零点保持精确。需要纽约收盘截止应传入带时区的实际时点。
- 时间越界回执返回提交区间的 UTC 时点、当前时间、配置截止时点及二者中较早的上界，明确未派发、未改写请求，由模型选择所需交易区间。配置只精确到日期时，这个上界不能代替题面中更早的日内截止点；工具不从自然语言猜测并覆盖截止时间。
- 相同请求在同一会话只保存一次快照，分页、并发与恢复复用它。刷新行情需推进 end；不静默替换旧观察。
- `WEB::MARKET::…` 与稳定 passage 身份进入既有引用及计算恢复，不提升为核准财务事实。不填零、不归因、不下单。

`read_public_source` 的公开 X 路径：

- 外搜可查 `site:x.com` 加人物或主题；完整帖子地址也可作 query，候选再以 document_id 读取。搜索覆盖不完整，零结果不证明未发言。
- 核对 post ID、URL 作者与返回作者，保留精确时间、可核定编辑版本、账号徽标、引用/回复 ID 和实际通道。蓝 V 不作为官方身份认证。
- 引用帖、图片、长文章、完整线程不随正文自动读取。回执区分已读正文与未读链接。
- 日期来自绑定的接口元数据，不从正文提及的未来日期推算。晚于截止时点的编辑版本不作为旧时点原话。
- 原帖不可用或版本不符时返回错误，不用 hosted 文本冒充。同期转述可以独立引用，保持自身来源身份。
- 复用既有公共来源缓存、引用与恢复，无新的一套完整业务状态备份。

## 3. 网页路径与实测

| 网站 | 用途 | 本机结果 |
| --- | --- | --- |
| Congress.gov | 法案版本、提案人和程序动作 | HTML 页面曾被挑战；[官方 API 工具](congress_api.zh-CN.md)已用实际 key 验证记录、版本和动作，正文衔接 GovInfo |
| GovInfo | 官方法案版本、HTML / PDF 和元数据 | “详情地址 → MODS → HTML 正文”成功；绑定 package 身份、rendition 和 dateIssued |
| 白宫与部门官网 | 行政声明和实施文件 | 一份公告成功，不外推所有页面畅通 |
| 议员办公室 | 声明、账号归属 | 所测一份页面 403，错误保留 |
| 公司官网 / IR 与 SEC | 公司回应和业务披露 | 所测一家 IR 列表 403；沿用 SEC 连接器，不把官网故障改写为没有披露 |
| X | 公开发言原文与时点 | 一条原帖完成候选、原文和引用身份检查；没有验证任意查询召回 |

GovInfo 元数据只核定特定版本公开日，不判断生效、替代、支持人数或通过概率。程序仍需实际记录，参考 [Congress.gov 术语](https://www.congress.gov/help/legislative-glossary)与 [GovInfo bills 说明](https://www.govinfo.gov/help/bills)。探测用的具体帖子、法案和查询仅留在本地验收证据，不预加载到新题输入。

## 4. 方法披露

### 政府原件读取与搜索故障分层

`read_public_source` 沿用原搜索、日期检查、来源缓存与引用入口。工具目录明确披露官方域名检索；查询提及 TCEQ、ERCOT、白宫或得州州长时，回执提供保留原查询的 `site:` 查询入口，由作者决定是否继续。入口不携带特定公告、事件结论或“已核查”状态，也不代表目录覆盖完整。

- 公告标题后的短发布日期/地点/Press Release 元数据，以及 Plone 明确标注的 Last Modified 文档日期可进入版本检查；正文提及的截止日期、版权年不作为发布日期。最后修改日表示当前页面版本的时间下界，不等于首次发表日，更不是历史存档证明。
- 带查询参数的页面若自己声明了同域同路径、无查询参数的 canonical 地址，重新获取并核对该地址，生成对应候选身份；不任意删除可能改变文档内容的参数。
- ERCOT `services/comm/mkt_notices/<公告编号>` 原站拒绝访问或连接失败时，可使用已授权且记账的 DS Fetch。必须在返回正文的 NOTICE TYPE 中匹配准确公告编号，并取得 NOTICE DATE。回执记为 `deepseek_hosted_notice`，保留原站失败；它是托管转录，不伪称直接 HTTP 或档案级原件。其他 ERCOT 页面和 API 不因此自动获得支持，X 原帖等原有严格路径不放宽。
- HTML 提取使用 trafilatura 的 Markdown/link 输出。日期任务只披露已读页面中观察到的附件 URL 和独立核日期入口，不继承母页日期，不自动把附件注册为可引用原文。PDF 只有月份或不能核定版本时仍可能不可用于该历史截止日。
- `verification_failures` 分开记录原站访问、DS Fetch 和日期/备用读取失败。即使有其他成功候选，失败层级仍显示；搜索结果数不等于已读原件数。旧回执形状与 digest 验证保持兼容。
- DS Search/Fetch 共用的任务预算门禁需要串行派发本客户端的请求；并行候选核查在此排队，避免把执行中的同伴请求误报为未结清故障。历史失败不自动重发、未知用量仍拦截，成功请求按原键复用。私有账本新增请求参数便于定位 Fetch 目标，不保存凭据。
- 缓存重放保留首次读取的失败与成功通道，再追加缓存标识，避免重放后丢失托管来源限制。

无模型实际验收覆盖州长 2026-09-21 公告、TCEQ STEERS 实施页（版本日期 2026-10-28）、ERCOT 2026-09-03/09-09 通知、白宫 2026-03-20 公告：取得正文、日期、引用身份和可见附件入口。首轮搜索使用 Exa，复用已有 Exa 冷却后的另轮使用 DS；DS 的宽泛查询仍可能只返回相关栏目、较早公告或访问失败的语言版本，不能宣称召回质量已全面解决。ERCOT 一般页面仍可能 403，未接通其全部数据 API。此验收没有运行研究模型，也不证明作者会自主补证或修正政治判断。

相关测试：`test_government_sources.py`、`test_dated_web_discovery.py`、`test_deepseek_web.py`、`test_scoped_source_capture_cache.py`。接口依据：[DS Search/Fetch 官方说明](https://api-docs.deepseek.com/guides/search/)；ERCOT 数据 API 与网页通知不是同一接口，参见其[官方 Public API 公告](https://www.ercot.com/services/comm/mkt_notices/M-A112123-04)。

新增 `event_policy`，通过原有 `get_research_method` 目录与章节读取公开，常驻只显示短目录。正文讲消息增量、政治程序、账号身份、行情时序比较、经营传导和更新判断；`macro_valuation` 指向同一正文。

算例使用虚构时间和价格，解释日跌幅、消息后变化与因果影响的区别，以及表态、排期、通过和生效的区别。未加入本题真假结论、人物名单或具体帖子。没有强制复核链，不承诺模型一定读取方法或正确归因。

## 5. 验证与发布边界

### 按需独立复核与专题稿修订

独立复核现在加载同一份维护中的 `verifier` 方法正文及其摘要；其他方法通过 `get_research_method` 按需读取。作者常驻指引与 `event_policy` 区分消息归属、实际变化和传导解释，示例使用虚构设备企业，不提供当前案例答案。复核允许使用当前任务已授权的来源回读、公开检索、法案、行情与计算工具，不获得写笔记或改报告的权限；外源搜索仍可能计费，沿用任务预算与失败保留机制。

现有 `finsight.answer-review.v1` 命令兼容默认 `artifact=answer`；显式 `artifact=report`、`delivery_intent=report` 时，`version` 绑定持久化报告（含引用）的完整摘要，正文不使用交付后的聊天摘要替代。原作者会话身份继续核对，复核目标在首次执行时冻结，恢复时沿原目标核对并保留已保存的修改。作者通过现有 `edit_research_report` 与 `deliver_current_report` 处理意见，无新增写作流水线。报告仍标记保存与交付状态，不把“收到独立意见”伪装为修订稿已获批准。当前未新增网页按钮；服务命令与网页成果展示复用现有入口。

离线回归验证目标版本、来源身份、真实方法输入和读写边界。真实验证另记检查者发现/漏检、作者补证/处置、解释与投资含义的改变，不能用接口通过或措辞变保守替代研究质量验收。

确定性回归覆盖：帖子/作者身份、编辑截止、正文未来日期、发现后失效及 hosted 禁用、GovInfo 元数据身份、行情时区/未来过滤/未完成柱、当前报价不混入历史窗口、分页并发缓存、来源恢复/计算绑定及方法入口。

实际无模型探测：一个结束交易日的 78 根五分钟柱和两页回读；一条 X 原帖完整读取；一份 GovInfo 文件的官方日期与正文。没有付费搜索或模型调用，没有验证模型自主检索、政治推断或市场解释。

本片在独立工作树实现并通过实际工具入口检查。当前运行的旧 Docker 服务不是该研究基线，未替换容器。新题前仍需将本提交纳入确认的研究服务版本，核对实际工具目录与受权入口，确定题目、精确截止时点及独立预算；不能把本地工具探测称为工作台端到端研究验收。
# 公开原件 DNS 故障

抓取前的公开地址检查对解析器明确报告的 `EAI_AGAIN` 仅重试一次；永久域名错误不重试，得到地址后仍核对公开地址范围。故障回执保留候选主机、解析器错误码、是否临时及 HTTP 尚未派发状态。DNS 故障不构成“没有资料”，也不允许绕过来源或地址验证。该重试不调用模型、不更换来源、不自动补发付费请求。
