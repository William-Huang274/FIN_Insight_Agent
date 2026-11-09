# 公开资料解析：维护库与业务适配边界

网页日期不是单纯的字符串解析问题。提取器可以找到日期，FIN 仍须判断它属于当前文章、首次发布、更新还是正文中的事件。研究截止日不能传入提取器来筛选“最近一个合法日期”：否则期后更新可能被隐藏，而当前正文被旧发布日期放行。

## 已接入并替换的能力

| 对象 | 维护依赖 | FIN 保留的职责 |
| --- | --- | --- |
| HTML 正文与表格转 Markdown | 既有 Trafilatura | 抓取失败分类、准确 URL、来源及字符窗口身份；不另造通用正文提取器 |
| 标题和日期候选 | Trafilatura metadata，内部使用 htmldate，关闭 extensive search | 候选不是历史可用性证明；不靠 URL、版权年或模糊 dc.date 放行 |
| JSON-LD、Microdata、Open Graph 结构 | extruct，限定三类语法，不启用远程上下文读取 | 精确页面身份、嵌套对象归属、published/modified 语义；保留原值、字段、语法、身份 |
| 完整日期字段的格式解析 | dateparser absolute-time，strict，要求年月日 | 不从当前日期补缺失部分；明确格式的官方 wire 日期继续标准库解析 |
| 最新正文版本的日期 | 以上已归属证据 | 发布时间和修改时间均保留，既有门禁按较晚日期检查；不把旧发布时间当旧正文快照 |

`publication_metadata.py` 是统一适配入口；`publisher_html_day` 保持原调用合同。已移除它原有的 JSON-LD 手工解析、Microdata DOM 属性解码、OG 日期格式解码及多处英文月份格式循环，不保留新旧两套结构提取兜底。显式的出版者 header 别名仍是一份语义映射，不把 `dc.date` 等含义不明确的字段硬解释为发布日期。

## 盘点后仍需要的自研适配

以下能力并非上述 HTML 库覆盖的重复实现，暂不删除：

- `dated_web_discovery`：来源域名与路径约束、目录/文章区分、重定向后重新核定、截止日门禁、恢复来源身份；Census 目录必须确实链接到目标文件，BLS/DOL 镜像须对应同一发布系列和日期。
- 发布者报头：Press Release 与标题/日期的邻接关系、出版标签与 time 文本一致性、Plone 的 Last Modified 标签、 hosted 转写与原页面的对应关系。通用日期候选无法证明这些关系，因此保留薄 DOM/文本适配。
- 明确的 CMS 发布元字段 `w_published_date` 按发布日期读取，`w_search_date` 不作为证据。HTML `time[pubdate][datetime]` 只归属于包含页面唯一主标题的最近 `article`；推荐文章、普通事件时间、多个冲突发布标记及 canonical/OG 身份冲突不采用。日期格式仍交给 dateparser，不新增手写日期解析器；原字段、页面身份和提取语法保留到证据记录。
- VitePress 文档：读取生成器声明及当前文档页脚的原生 `VPLastUpdated time[datetime]`，经既有 dateparser 解析为修改日；不取站点构建时间，不将修改日命名为首次发表日。存在 canonical/OG 身份冲突或非文档页脚时不采用。协议依据见 [VitePress Last Updated](https://vitepress.dev/reference/default-theme-last-updated)。
- PDF：既有 pypdf/pdfplumber/PDFium 提取和窗口能力；法院 filed 印章、信函签发报头、公报 issue date 等身份适配。HTML 库不负责裁定政策生效日与文件发布日期。
- `company_disclosures`、`government_publications`、`government_sources`：SEC accession/form/filingDate/reportDate、Congress 法案及文本版本、GovInfo 发布目录身份，优先采用官方结构化元数据，不经网页启发式日期覆盖。
- `external_sources`：搜索提供方响应协议、URL 安全检查、抓取/缓存、原文保存与来源绑定；这些不是文章元数据解析。
- arXiv：`scholarly_sources` 直接接官方 Atom API，复用 lxml 和现有受限 HTTP；按准确 ID 核验单条记录、版本与 published/updated，采用版本日期而非 feed 抓取时间。摘要链接返回有版本的官方元数据记录，明确不等于全文；PDF/HTML 分别读取和绑定。期后新版不会用首次提交日放行，也不自动选择旧版替模型研究。见 [arXiv API 的版本合同](https://github.com/arXiv/arxiv-docs/blob/develop/source/help/api/user-manual.md)。单会话复用元数据并遵循请求间隔，无供应商模型调用。
- `web_source_navigation` 与来源绑定计算：分段回读、表格表头/期间/单位、准确引句与算式。这些金融证据语义不能交给日期解析库推断。

这次盘点范围是联网资料的正文、元数据、时间和官方文件读取链路，不将全仓的财务数据解析、检索索引或 API 请求模型误归为可删除的网页解析器。

## 验收

运行 `tests/test_publication_metadata.py` 及 dated_web_discovery、company_disclosures、government_sources、publisher_catalogs、web_source_navigation 的回归测试。覆盖当前文章/推荐文章、图结构、发布日期/修改日、期前/期后、统计期间/发布日、无年份、版权年、目录、PDF、镜像及原提案恢复。真实页面应保存原 HTML、URL、摘要与提取结果在本地验收目录，不写入仓库。

依赖库的候选提取正确不等于研究结论正确，也不保证未来所有网站模板可用。无法归属的日期继续返回真实障碍与查询入口；不静默改成“未披露”。锁定依赖版本，升级时复跑这组语义边界。

安全验证页可返回 HTTP 200。静态读取对短小、带已知挑战脚本且无文章正文的响应返回 `capture_access_challenge`，保留原地址和实际失败阶段，不把挑战脚本交给正文/日期提取器，不执行脚本或自动处理验证码。可读的官方替代文档仍独立核验。

DDGS 原生 ranker 会保留完全没有查询词对应的末尾候选。适配复用锁定版本 `SimpleFilterRanker` 的词提取/匹配，仅对至少两个有效词的查询剔除这个零对应组，数字年份不算对应；回执保留原始返回数量和 `no_query_term_overlap`，空结果反馈说明这是查询错配而非资料缺失。这不是语义重排或召回完整性保证，短查询保持原行为；没有新增付费判断模型。依赖升级须复测这一薄适配使用的原生方法。

原站元数据核验的读取期限为 30 秒，避免大型官方表格尚未返回就转入付费抓取。DS Search 读取期限为 20 秒，DS Fetch 为 60 秒（连接均最多 20 秒）；抓取还包含提供方访问原站的时间。期限增加不增加自动重试次数，未确认付费响应仍保留未知用量并停止后续派发。
