# FinSight：研究能力与工程边界

2026-09-07 · 本地Dell开发案例 · [English](architecture.en.md)

## 一次完整研究

用户问题 → Lead动态任务DAG → 独立多轮专家（依赖就绪后执行，并发2） → Counter/Verifier → 必要责任作者修订 → Lead综合判断 → 独立研究复核 → Writer/来源绑定图表 → 报告终审 → 人工审阅、追问与导出。

Agent自己决定查什么、用什么工具、如何解释来源。父图管理依赖、阶段与交接，不预写研究答案。最初九研究面可以形成多波次任务；现安全容量最多12任务。审查意见可以被作者用来源反驳，不能默认正确。写作问题不重跑全案；工具/数据问题不让Writer用措辞掩盖。

## 成熟组件与必须自己负责的部分

| 层 | 成熟组件 | FIN职责/代码 |
| --- | --- | --- |
| 产品 | React、Vite、Markdown、原生stream SDK | `apps/workbench`：交互、状态与来源展示 |
| Agent执行 | LangChain create_agent、LangGraph/Send | `src/sec_agent/agent_runtime/research_session*.py`、`research_convergence.py`：任务/产物交接与责任路由 |
| 持久化/观测 | Agent Server、PostgreSQL、Redis、LangSmith | 固定Compose部署；模型上下文按角色隔离，不新建队列或trace平台 |
| 工具协议 | 官方MCP客户端/服务端 | `research_foundation/mcp_server.py`：来源、SQL、方法与计算的薄schema适配 |
| 文档 | 已资格检验的本地文档树；新增上传用pdfplumber、python-docx、BS4、LangChain splitters、BM25 | `task_attachments.py`：任务归属、原文件副本、页码/章节定位；上传不冒充已建dense/reranker索引 |
| 数字 | SEC标准结构数据→SQL；simpleeval/Decimal | 公司/期间/单位、来源计算输入与结果；算术通过不代表经济解释正确 |
| 外源 | 现有Exa MCP搜索/抓取与trafilatura静态提取 | 来源ID、正文窗口/链接及来源性质；新闻不是权威财务事实 |
| 图像/交付 | DeepSeek视觉SDK、Matplotlib、ReportLab、python-docx、python-pptx | 图片原件与识别文本绑定；图表数字查原来源，不接受虚构值；不让模型执行任意绘图代码 |

版本以`uv.lock`、前端lockfile和Docker基础镜像digest为准；README不另造第二份依赖清单。当前LangChain是成熟Agent循环的一部分，不是恢复早期自研重壳。

## 上下文与工具数据

每个角色保留自己的原生多轮消息；跨角色传任务、公开底稿、引用和简明依据，不复制完整私有思考。起始给题目、能力/方法目录；按需读方法、文档目录、原文窗口、SQL和计算。模型可读合法原文做判断，本地检查来源观察、ID/参数/schema及算术；不使用自然语言模板判定报告对错。

报告引用可来自底稿主张、实际读过的PASSAGE、SQL NUMFACT和来源计算CALC。新读的非结构化数字可以分析，但不晋升S2权威事实。图表在同一来源合同上取数；期间可比性和因果仍由模型复核及人工检查。

运行中意见通过原生thread metadata保存，在后续研究/审查/收敛阶段读取。不是对当前生成中回复的即时强制干预；UI事件说明是否已送达。上传是任务副本，不能修改共享知识库或任意用户文件。

## 当前限制

仅本机可信Owner试用；没有对外用户认证、多租户隔离或恶意文档进程级沙盒资格。模型没有shell、任意文件写入或提权工具，容器无新增权限；这些不等于整个宿主已经是多租户安全平台。原文解析/检索存在残余问题，空检索不自动认定信息未披露。

新题目全链已实际到达报告及人工点，期间有原生失败接续和人审定向修订，失败没有抹除；这不是无辅助一次成功。全面重启恢复、并发用户、通用公司场景和P95延迟不能用单次开发case推导。旧`dell_*`模块继续作为已测兼容适配，新的会话/上传/图表接口使用通用名称；不为展示而批量重命名破坏历史证据。

方法可用和充分应用也分开：六组短方法可按需读取，真实观察到部分角色加载具体方法、部分仅看目录。数值与引用校验通过后仍出现过存量/流量、因果和正文公式错误，由模型复核及主Agent审稿纠正。没有将这些个案答案写进通用NLP规则，也不能据一次终审“0重大”宣称百分百准确。
