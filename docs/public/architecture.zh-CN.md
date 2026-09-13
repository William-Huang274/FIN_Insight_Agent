# FinSight：研究能力与工程边界

2026-09-13 · FIN 0.1.3 冻结本地 Internal Alpha · [English](architecture.en.md)

当前架构以[0.1.3收口](../product/fin_0_1_3_closeout.zh-CN.md)为准。方法动态适用、规则更新、专家有限委派和期限收敛仍属 0.1.4 规划。一次性资格实现已退出当前树，见[归档说明](../../archive/README.md)。

## 一次完整研究

用户问题 → Lead动态任务DAG → 独立多轮专家（依赖就绪后执行，并发1或2，默认2） → Counter/Verifier → 必要责任作者修订 → Lead综合判断 → 独立研究复核 → Writer/来源绑定图表 → 报告终审 → 人工审阅、追问与导出。

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

旧工具正文只从本次请求投影清理，原始消息/artifact仍留在原生checkpoint。已保存问答里的完整CALC以同任务只读视图恢复给工具，不把整份引用树塞回模型消息；缺记录/异任务/冲突拒绝。自动摘要资格HOLD、默认关闭。BFF用原生SDK分页累计全部runs，用run_id与call_id共同识别调用；费用、缓存与耗时未知项显式保留，外部导入修订费用另列。

`--fresh-only`只注册research_session，不挂载旧答案，复用固定PG/Redis及原始数据目录。图像是按需只读工具而非普通Pro输入；视觉缓存缺字段不推定零用量。MD/PDF/Word/PPT共用版本报告与来源投影，PPT图表保留可编辑数据，完整来源放讲者备注。历史v4已做实际渲染；当前v5是后续局部修订，仍待人工审阅。

## 当前限制

冻结版本已有 OIDC/PKCE 双用户、39 项资源归属检查、8 次并发读取，以及 4 个真实前端审批场景；批准后由原生任务恢复经认证 MCP 进入 Docker 沙箱，拒绝时不执行。普通对话与研究工具按已配置能力开放。这些是本地资格证据，尚无生产多租户、恶意文档全链路或高可用认证。原文解析/检索仍有残余问题，空检索不自动认定信息未披露。

已有任务到达真实报告与人工审阅，也保留失败接续、定向修订、重启交接和提交去重的有限验证。19 个真实回合包含恢复，不能推导通用公司金融质量或生产 P95。仍被使用的 `dell_*` 模块保留既有图、数据库与来源身份；已淘汰实现从当前树退出。

方法可用和充分应用也分开：六组短方法可按需读取，真实观察到部分角色加载具体方法、部分仅看目录。数值与引用校验通过后仍出现过存量/流量、因果和正文公式错误，由模型复核及主Agent审稿纠正。没有将这些个案答案写进通用NLP规则，也不能据一次终审“0重大”宣称百分百准确。

## 前端节点、配置与运行时的连接

研究地图由真实报告章节及引用构成，展示总览、专题和判断/依据。导航节点负责展开；可修订节点携带 citation ID、基线版本、内容摘要与 checkpoint，进入现有 research_revision 路径。服务端核对基线，避免在过期版本上静默修改。

研究配置通过 FastAPI 的 research_studio 接口保存为原生 Assistants 独立快照，选定任务保存对应 ID。每次 run 固定读取其配置与摘要；Skill 绑定进入角色提示及 MCP 方法读取，专家初始上下文在请求摘要生成前绑定。双审查顺序改变原生 StateGraph 连线，并行数改变已有运行 profile；必需复核不能删除。它不是任意代码工作流设计器。

相关入口：

| 层 | 文件 |
| --- | --- |
| 图导航与修订 | `apps/workbench/frontend/vite/src/app/ResearchGraph.tsx` |
| 配置编辑 | `apps/workbench/frontend/vite/src/app/ResearchStudio.tsx` |
| 保存、应用、运行时读取 | `apps/workbench/backend/api/v1/research_studio.py` |
| 配置合同与角色方法 | `src/sec_agent/agent_runtime/studio_configuration.py` |
| 研究运行消费 | `src/sec_agent/agent_runtime/research_session_runtime.py` |
| 对外启动 | `python -m scripts.deployment.research_workbench` |

前端采用 Lucide 图标、React Markdown/remark 内容渲染、diff 库和 React Flow 图组件。运行页使用真实阶段及公开事件，历史回放是客户端对保存事件的逐条显示，不是新的执行状态机。侧栏项目分组保存在浏览器；报告、checkpoint 与配置版本保存在服务端。

2026-09-08 的真实短问验证了前端编辑的方法进入两次模型请求并影响答案组织，报告未改；专家请求校验和审查顺序由原生图合成测试覆盖。该证明不等于所有角色/所有公司均完成付费验证。
