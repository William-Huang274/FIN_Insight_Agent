# 公开页面读取与导航

研究工具仍使用 `read_public_source`，不要求作者另外选择抓取服务。搜索候选、
原文读取、版本核验、来源引用分别保留状态；读取成功不代表研究充分。

DDGS 兜底会将显式 `search_language` 转为原生地区参数，例如 zh-CN → cn-zh；
没有地区时用全球 wt-wt，不再隐含美国英语。地区传递正确不保证引擎可用或
查询相关；429、传输错误及不相关结果仍分别保留。Bing 的既有隔离不因此解除。

## 自动读取路径

普通 HTML/PDF 先走有期限的 HTTP 读取和原生解析库。带脚本且可见内容不足
的页面、400/403/406 或已识别访问验证页，可进行一次 Playwright 无头 Chromium
渲染。浏览器等待加载和短期正文稳定，不再固定等待750毫秒。调用有总时限；
单个读取器最多两个浏览器任务并行。仍为空时返回
`capture_browser_content_incomplete`，不把加载页保存成有效正文。

浏览器使用独立临时上下文，不导入个人 Edge cookies、登录状态或历史。
沿用公开地址校验，阻止私网请求及 service worker；不执行模型提供的任意
脚本、不自动购买、不解验证码。429 不换浏览器重试。验证码仍需验证或寻找
同一发布者的公开 API／另一份正式原件，不把访问失败解释为未披露。

部署镜像安装与 Python Playwright 版本配套的 Chromium headless shell 和
系统依赖：`python -m playwright install --with-deps --only-shell chromium`。
缺少浏览器返回 `capture_browser_not_installed`，不是日期缺失。
本地开发按相同命令安装依赖；Windows 不需要 Linux 系统依赖。

成功渲染标记 `playwright_browser`，保留之前静态读取的故障或动态壳原因。
来源缓存、精确回读和引用继续使用原接口。日期仍从实际页面版本元数据核验，
不能用抓取时间、正文提及日期、母页日期代替历史公开日期。

## 从未核日期页面继续调查

`unresolved_originals[].observed_navigation` 返回页面实际包含的有限 HTTPS
链接及 `search(query=URL)` 参数。仅包含地址，不泄露被日期门禁扣留的标题、
摘要或数字；链接无引用权、无继承日期。晚于截止日的已识别版本不返回这些
导航。作者可继续进入定价、帮助文档、公告或附件。这不是全站索引，也不证明
当前内容在更早研究时点已存在。

文档页带明确“更新时间”标签的短元数据容器与 `time[datetime]` 可作为
当前版本日期；普通正文、引用、相关链接和生效日不能冒充它。无需 Exa
才能读取这类日期。没有版本依据的动态商城仍不能直接进入历史截止日报告。
Q4 Evergreen 新闻详情使用其独立标题、相邻日期和正文容器绑定发布日期，
并核对原生元数据标题；网站导航的 h1、相关新闻卡片与正文日期不作为依据。

## 现成工具选择

本轮复用 Playwright、Trafilatura、htmldate/extruct/dateparser。
Trafilatura 启用 `favor_recall`，避免只留对照表而丢失套餐卡片内容。
[Playwright 导航文档](https://playwright.dev/python/docs/navigations)说明
DOM 加载和页面真正完成初始化是不同事件。

[Crawl4AI](https://docs.crawl4ai.com/core/browser-crawler-config/)提供渲染等待、
缓存及浏览器配置；[Crawlee](https://crawlee.dev/python/docs/concepts/requests)
提供队列、失败请求与会话管理。当前已有任务队列、缓存和原件合同，因此没有
再叠加第二套爬虫调度。自动轮换身份或代理不能替代来源与版本核验。

## 验收

宿主可通过 `FIN_PUBLIC_HTTPS_PROXY` 显式配置公开读取代理（带端口的
HTTP/HTTPS/SOCKS URL）。静态 HTTP、DDGS、Playwright 与 DeepSeek Search/Fetch
复用此配置；无配置时保持既有默认网络行为。模型不能提交代理地址。
代理认证不会进入工具反馈；连接、TLS、DNS 或超时反馈提示宿主检查通道。
403、验证码和 429 仍按访问验证、拒绝和限流处理，不因配置代理而自动重试。
此设置不替代 SEC 等独立连接器或模型服务本身的网络配置。

`tests/test_public_origin.py` 覆盖脚本壳转浏览器、短静态公告、429不重试、
验证失败、渲染不完整、日期正反例、导航不泄露期后标题、实际工具入口接线。
与公开来源、日期核验、原件导航、政府读取、缓存测试共同运行。
真实页面验收另存本地，不进入 Git；测试通过不表示任意网站都可读。
