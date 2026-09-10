# 205 自然语言工作底稿（2026-09-10）

## 最新：Qwen 检索与 Hermes 原生循环已进入实际前端

本段覆盖下方早期“未部署/Hermes 未接入/Qwen 后置”的时点。Owner 已批准把底稿部署、语义检索、定向修订、Hermes 内层循环合并推进。FIN 0.1.3 / S3 / 205 不变，不重开金融核验付费追绿。

产品增量：工作底稿弹窗已能语义检索、阅读正文/旧版本、选择模型及执行方式、向指定底稿版本提交意见；普通对话有固定执行方式选择。实际 BFF 18795 / Native API 18165 已加载新代码，原 PostgreSQL/Redis 卷与旧任务保持。Hermes 原生 HTTP 服务运行于本机 18806，容器经 host.docker.internal 访问。当前为普通问答和工作底稿试用，未开放 Hermes 上传资料/SQL/网页/用户文件工具，界面与后端均限制，避免选择后静默变成另一执行器。

工程增量与成熟栈分工：

- LangGraph 继续管理外层 thread/run/checkpoint；固定 Hermes `0.21.1` 源码 `abd83ab560327c58f17f8e2ecd9be0307d5c9cf9` 的 `APIServerAdapter` / `/v1/runs` 管理内部模型工具循环、SSE、会话、取消和请求幂等。FIN 仅绑定可信 owner/workspace/actor、三个底稿工具和定向修订。扩展 `_create_agent` 属于固定版本的内部接缝，升级需要重新资格，不能声称任意 Hermes 版本兼容。
- 正文仍只有同一份 SQLite 权威存储。Qwen 使用已有 provider 适配器，sqlite-vec 0.1.9 做向量距离，LangChain RecursiveCharacterTextSplitter 分块，Qwen 重排。关键词候选与向量候选合并；按 owner/workspace 和当前版本筛选。没有金融专用词表或新工作流引擎。
- 检索结果/向量缓存可复用；未变正文块复用向量，更新版本保留旧正文；每次最多索引 20 个新块、最多四次远程请求，剩余积压和降级可见。失败/不确定请求短暂冷却，不自动立即重发。每次付费检索写任务预算依据与用量；索引不是财务核验，精确正文读取不依赖向量服务。
- 用户修订由服务端固定目标、责任角色、基线、所有权，创建独立原生修订窗口，工具只能写选中底稿。历史版本保留，冲突版本拒绝覆盖。修订窗口也可查看原底稿、继续问答；**尚不是运行中任意研究节点打断、依赖失效或自动重新调度**。
- 原始模型请求/响应含供应商返回字段留在私有审计目录，HTTP 流边读边保存，不等待整段完成才转发。公开文本通过原生 resumable SSE 投影；第三轮实际记录 205 个 assistant_delta 和 4 个 custom 事件。初版事件名错配、工具名称字段和逐块段落问题在本轮修正；前两轮旧记录保持原件。
- 本机 Python 内置 SQLite 3.50.4 存在上游已披露 WAL-reset 风险，Hermes 已选择 DELETE journal；FIN 对低于 3.51.3 的版本也保守选 DELETE。生产并发/跨主机不由这份本地 SQLite 试用承担。

真实资格分两份独立记录（均非盲测，也不是完整金融报告验收）：

| 验证 | 结果 | 模型/API 用量 |
|---|---|---|
| 四份短底稿的同义检索 | “赚到的利润还没有变成手里的钱”关键词零命中，语义首位为“现金兑现观察”；重复查询零新增调用 | Qwen 3 请求 / 309 tokens；冷查询约 1.855 秒 |
| 产品前端保存 v1 | Hermes 调 WriteWorkingNote，保存虚构现金流底稿 | Flash 2 请求 / 7,410 tokens |
| 产品前端定向修订 v1→v2 | 先 ReadWorkingNote 再 WriteWorkingNote；去掉过强结论、明确 CFO 80 和简化 FCF 50、等待用户附注 | Flash 3 请求 / 12,751 tokens |
| 重启 Hermes、Native API 和 BFF 后原修订窗口追问 | ReadWorkingNote 回读 v2，正确保留口径/未决判断/等待安排，未再次保存 | Flash 2 请求 / 10,663 tokens |
| 产品底稿语义搜索 | 实际 Qwen 向量与重排命中当前底稿 | Qwen 3 请求 / 729 tokens |

本轮 DS 共 **7 请求 / 30,824 已知 tokens / 新未知 0 / 自动重试 0**；三轮调用前已冻结最多 15 请求，实际无需用满。全部 thinking disabled，与当前普通对话配置一致，不把本次结果当成推理强度优劣对照。前次原生工作记忆资格用过 enabled/low，任务与执行器也不同，不能据此声称 Hermes 更省或推理更好。Qwen 共 **6 请求 / 1,038 tokens**，单独统计，不混入 DS 调用计数。205 DS 累计 **598 尝试 / 17,840,912 已知 tokens / 历史未知 3**，实际账单价格未核验。

实际产物：`D:/temp/fin205-hermes-product-a1/{TokenBudgetBasis,result,turn1,turn2,turn3,versions}.json`、`turn3-stream.txt`；检索对照 `D:/temp/fin205-working-semantic-a1`；Hermes 原始审计 `D:/temp/fin205-hermes-memory-service-a1/fin-audit`。这些包含运行记录，不提交 Git。真实原窗口 `01a08a8b-0f5b-76a2-b884-105076308974`，修订窗口 `01a08a8d-9705-76e0-860e-2a4ad9f8553a`，底稿 `4c3713bd329e9c692cfb3b2fb64025c9` 的 v1/v2 均可读。

本轮工程验证：最终定向 Python 检查 25 通过；前端 14 项桌面/窄屏检查通过（夹具），TypeScript/Vite 生产构建通过，已有 bundle 体积提示仍在。Hermes 启动前零模型工厂资格验证只有三项底稿工具、SDK 重试为零；MockTransport 验证原生幂等键、可信作用域、SSE、失败取消。实际前端另完成上述三轮与语义检索、重启回读，不能把夹具测试冒充真实模型验证。

部署入口：`python -m scripts.deployment.research_workbench {build|up|serve} --settings-directory <已有设置目录> --enable-research --fresh-only --semantic-memory --hermes`，serve 加 `--ui-port 18795`；已构建时 up 加 `--no-build`。设置目录的私有 `hermes-connection.json` 包含 `host_url`、`container_url`、`token`，不得提交。QWEN_API_KEY 从进程/.env/Windows 用户环境读取而不打印。底稿目录自动挂载到 Native API，BFF 使用对应宿主路径。Hermes 用独立 venv，源固定到上述提交，安装官方 API 所需 aiohttp 以及 FIN 工具依赖 langchain-core/langchain-text-splitters/sqlite-vec；复制 `configs/research/runtime/hermes_working_memory.yaml` 到隔离 HERMES_HOME。启动脚本 `scripts/deployment/hermes_working_memory.py --hermes <源码目录> --home <隔离home> --port 18806` 需要 FIN 的 src/repo 在 PYTHONPATH，以及 DEEPSEEK_API_KEY、FINSIGHT_HERMES_TOKEN、FINSIGHT_WORKING_MEMORY_PATH；启用语义时再设 QWEN_API_KEY/FINSIGHT_WORKING_MEMORY_SEMANTIC=1。不开放内置 shell/文件系统/网络工具。

尚未完成：Hermes 其他研究角色/工具全量迁移、自动压缩及金融信息保真对照、多 Agent 在任意节点接受干预后的依赖重算、真实多租户/生产 sandbox。当前短循环特意关闭 Hermes 自动压缩，以先隔离保存/检索/修订是否正确；超过输入上限会在发模型前停止，不会偷偷丢证据。Hermes 当前窗口 token 计量还没有接入统一卡片，UI 如实提示并显示本轮累计用量，不把累计计费当上下文长度。首轮模型仍加了多余解释，定向用户纠正后改正；这正是可审阅工作底稿的用途，不宣称模型已无幻觉。

后续顺序：在本次可用底稿循环上接已授权的原始来源读回与另外一个研究角色，再做一次“用户意见影响两份相关底稿”的有界测试；随后用同一批保留数值/来源/用户纠正的长历史，对照 Hermes 原生压缩和检索回读。认证/sandbox 主线继续，不回到金融语义无限追绿。

本轮工程提交：`d59a532f`。代码/测试/可复用部署配置与文档分别提交；30 个候选文件凭据模式扫描无命中，运行日志、API 凭据、SQLite、原始模型响应均留在私有目录。最新已部署镜像 `0c990335fbeb`；源码主要功能与实际实测版本一致，新增公开 Hermes 配置示例无需重新构建运行镜像。

## 早期切片记录（保留当时状态）

Owner明确区分工程记录和工作底稿：当前切片以自由正文、渐进保存、快速回读为核心，不以新增严格金融模板卡住保存和下游。现有正式研究提交合同没有在本轮放宽；新的工作记忆独立于它，失败/未交卷的Agent也可留下工作正文。继续 FIN0.1.3/S3/205，同开发分支。

## 选型与最小切片

采用标准库SQLite事务/WAL/版本表及FTS5 trigram，Python0新依赖、0辅助模型调用。原生checkpoint仍只负责图执行；工作正文单独持久化、按owner/workspace/actor定位。索引在正文提交后更新，失败可退回SQLite原文子串查询；不做自建分词、摘要、向量引擎或工作流。仅本地单机配置入口，不声称分布式并发/多租户发布。

官方候选：Hermes会话FTS5搜索（https://hermes-agent.nousresearch.com/docs/user-guide/sessions/）适合会话恢复，但不直接管理当前正文版本/FIN作用域；Deep Agents StoreBackend/CompositeBackend（https://docs.langchain.com/oss/python/deepagents/backends）适合文件式工作记忆，当前原生研究Agent采用不同循环，整套引入不是此切片必要条件。两者暂保留适配候选，不并行维护第二份权威正文。当前不用Qwen：精确目标+少量中文笔记先用定位/全文检索；跨语义召回收益以后用实测决定。模型工具只有名称/正文/版本以及查询/读取参数，无金融字段或章节合同。

执行范围：通用对话、原生Specialist/Lead、核验与作者/综合/写作工具接入；按明确部署开关启用。读写工作笔记只作用于任务生成内容，不等于改用户文件、来源入库或审阅通过。正文允许Markdown表格/普通段落；原数/来源是否正确仍需原证据核对。写入报错返回工具反馈，不抛弃其他结果；更新须匹配先前读取的版本，晚到请求不能覆盖新正文。

已完成本地资格：原生Agent写入→HITL暂停→重开SQLite checkpoint→拒绝受保护动作后接续；索引失败不丢正文，跨owner/workspace不可读，两个作者独立记录，同一正文并发修改只接受一个新版本。原生Specialist和Lead实际分派工具也已运行。前端工作底稿弹窗可查看正文表格、检索、分页、历史版本、下载所选版本、Esc/关闭；桌面/窄屏2浏览器检查通过。通用交接新增固定底稿版本引用，仍需来源所有权复查。

## 有界真实验证（执行前冻结）

`scripts/qualification/working_memory_roundtrip.py`：Flash/ thinking enabled/low，首轮2请求、重开checkpoint后二轮3请求，合计最多5，不自动重试或提高限额。每请求输入字符上限20000、输出2000、90秒；Task-specific TokenBudgetBasis在模型调用前写入独立目录。第一轮创建虚构现金流工作记录，第二轮按Owner意见取消过强推断及无须继续的研究步骤。无外部搜索、完整报告或财务正确性通过宣称；使用现有CaseModelAudit和模型适配器保存请求/原始推理/正文/用量。原生持久化与存储是实际组件，模型任务是小型资格样本。

配置：runtime和BFF的 `FINSIGHT_WORKING_MEMORY_PATH` 必须指向同一持久数据库（容器路径可不同，但应对应同一已挂载文件）；无配置则工具不公开、UI明确未启用。研究路径在非local认证模式未有可信owner时拒绝访问；通用对话从原生宿主线程元数据绑定owner。模型不能指定owner/workspace或文件路径。跨机器部署应迁移同一语义到现有PostgreSQL，不在网络共享盘运行SQLite/WAL。

## 本次结果

真实资格 `D:/temp/fin205-working-memory-live-a1`：5次模型请求、8480已知tokens、新未知0、0重试。首轮保存v1，关闭并重新打开原生SQLite checkpoint，第二轮先读原底稿，再按用户指令保存v2：只保留净利润与经营现金流同向增加的观察，取消“非纯账面”论证和继续查询营运资本的计划。v1保留。该结果只验证这个简单记忆/纠正闭环，未宣称金融报告质量通过。原始请求、reasoning_content、正文与用量在私有审计目录保留，不提交仓库。

205累计更新为591实际尝试、17810088已知tokens、历史未知3。核验支线没有重新开启；本次5次用于工作记忆资格。

工程回归：首轮155通过、8跳过、1失败；失败为未启用新功能时交接接口新增空字段影响旧返回约定，已修复。相应API/记忆/交接末轮19通过；其他通过检查未修改。17浏览器交互通过，包含工作底稿桌面和390px窄屏；前端类型检查通过。浏览器API为夹具；真实模型资格使用实际模型/工具/SQLite/checkpoint，但没有通过生产UI启动。

产品增量：新增可读工作底稿入口、检索、版本查看和下载；工程增量：各角色记忆工具、持久正文与历史、固定版本交接；资格证据：一次真实两轮纠正及离线暂停/恢复/隔离/并发检查；文档增量：Owner工作底稿边界、选型与本记录。未启动现有Docker服务、未部署启用开关，当前运行版不算已加载。

工程提交：`b8d54fce`。Vite生产构建通过（现有bundle体积提示仍在），本次27个候选文件密钥扫描无命中；私有模型审计及SQLite文件未提交。FIN0.1.3/S3和既有报告版本不变。

剩余边界：不是每次模型动作都会自动产生底稿，不能承诺模型必定遵守记录提示；当前关键词检索不证明跨语义召回。Hermes完整循环、Qwen语义检索、复杂多Agent任意节点打断后依赖失效/重新调度、生产认证隔离仍未完成。正式研究提交合同保持原状，本轮只是让工作记忆不依赖其验收。下一切片应让前端选定具体底稿/版本的用户修正进入责任Agent，再验证受影响工作回读，避免整篇重跑和继续无限磨核验。
