# S3/200 研究开始页、修订阅读、项目侧栏与研究配置入口

2026-09-08，FIN 0.1.3，延续本地codex/fin013-report-reader。Owner指出原始diff未渲染、顶部资料展开后难收起且边界不清、首页像管理面板，要求参考问题起始界面和项目侧栏，并增加Skill/编排入口。本轮先完成体验改动；不进入Hermes或公开仓库发布。

## 实际产品与工程增量

- ResearchStart：问题输入、四个研究起点、资料入口与最近研究；带问题进入已有准备页，开始研究仍为明确动作。
- WorkspaceNavigation：功能区、项目折叠、任务内六页面、置顶与管理项目。创建/归类/取消归类/置顶只保存浏览器localStorage，原生thread/report/run不复制。所有旧任务默认未归类，无公司名规则。
- ReportDiffView：ADOPT jsdiff8.0.3 parsePatch＋现有react-markdown/remark-gfm。历史报告、修订记录、图内结果统一为前后正文，保留邻近上下文开关；原始diff和长请求说明默认折叠。没有改报告或重算内容。
- 资料面板：明确aria-controls/expanded、常驻收起、Esc和焦点返回、独立底边与阴影。旧实现只有标题切换与单像素边界；本轮验证重复开关与滚动后的关闭，不声称已还原截图当时每项浏览器状态。
- ResearchStudio：BFF只读六组既有get_research_method资源，图由LangGraph SDK assistants.get_graph读取；白名单research/review，只投影节点ID与边，不开放任意路径/写配置/模型预算/运行权限。浏览器方法和图草稿支持编辑、保存、预览、导出，JSON仅检查语法；没有调用模型或部署草稿。
- 首轮新增首页测试发现本地专用app缺少/workspace入口（404），修复app.py路由；原/workspace/session继续兼容。

成熟栈依据：https://github.com/kpdecker/jsdiff （parsePatch）与仓库已采用的React Router、ReactMarkdown、原生LangGraph SDK。未造diff parser、workflow engine、项目数据库或发布状态机。

## 验证与服务

Python：tests/test_research_studio.py＋test_targeted_revision.py＋test_dell_report_session.py，35通过，24.43秒。包含方法目录/不授权、节点私有字段不投影、非法图ID拒绝、禁止POST配置等检查。TypeScript和Vite通过；原有大JS包及zod注释警告保留，不宣称性能优化完成。

A1：旧十项通过，新三项在/workspace返回404，原记录D:/temp/fin-start-workspace-a1/results保留。A2修源路由后13项通过，52.9秒，1440/1024/390宽度；覆盖输入传递、项目刷新、置顶、三次面板开关/滚动收起、实际Markdown标签、上下文、方法草稿刷新、非法JSON保存拒绝；新增三项没有API写操作。后续折叠长请求说明后的最终A3见收口追加。

真实CUA：在原v5任务打开真实P01:C9基线diff，v4/v5长文均正常渲染；展开资料检查边界与按钮，点击收起后进入六组方法页面，均为真实服务数据。截图D:/temp/fin-start-workspace-a3/home.png、revision.png、studio.png为只读Playwright捕获，不是合成报告或新模型输出。

旧8766服务停止/重启的组合命令被自动审查以blocked by policy拒绝，无更细原因；改为独立本地服务，不停止旧实例。8767测试服务可用但CUA浏览器拒绝该端口，改8793；本轮创建的8767实例29708和8793旧实例31000已按核对命令行停止，8793载入入口修复后的新实例，日志D:/temp/fin-start-workspace-bff-a3.*.log。原18165/数据库/卷均不动，8766旧BFF保留，完整新入口验收与交付使用8793。

## 明确边界与下一步

0研究模型调用，0新增报告版本，无自动accept。v5仍待Owner审阅，RC-S3-199底稿C9旧措辞没有借UI修复关闭。

项目归类/置顶/配置草稿是当前浏览器的整理和编辑数据，无跨设备/多人共享。方法取工作台源包，不假定与运行容器部署版本相同；原生图只返回部分静态连接，动态责任分派要看实际运行事件。Skill发布、可执行编排验证、隔离运行调试与按任务类型生效尚未实施，不能把草稿入口宣传成完整Agent IDE。

本轮源码已更新总体设计；下一步为Owner体验后确定前端收口和对外展示整理，不自动推送codex分支或改产品版本。

## 最终收口

代码提交74be9c0c，18文件，本地codex/fin013-report-reader，未推送。A3折叠请求说明后13通过（59.9秒）；最后保留上下文分隔空行，避免同一hunk多处修改的段落拼接后，最终A4十三项通过（55.0秒），D:/temp/fin-start-workspace-a4/results。最终构建index-DdAfWp6y.js/index-s8iRTL0i.css；TypeScript/Vite通过。git diff --check通过，24个候选文件的私钥/密钥模式扫描0命中，不是全面安全保证。

当前8793 BFF实际PID640（launcher39556），新服务保留供Owner体验，旧8766保留。末次真实会话列表为interrupted/idle/interrupted/error，无busy。本輪不写报告、不开模型；验收以真实UI读取与无付费浏览器fixture为边界，不重新计算S3/199的已发生费用。
