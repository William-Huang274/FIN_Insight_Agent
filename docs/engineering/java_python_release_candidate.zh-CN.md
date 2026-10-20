# Java 与报告复核运行时：独立集成候选

本轮只建立共同版本及无模型验收，不合入 main、不切换现有后端。运行冻结点与随后展示导出的交付分开；不得把另一分支的未提交文件带入验收。

## 固定输入与合并

| 项目 | 固定版本 |
| --- | --- |
| Java/组织业务、索引绑定与检索验收 | `c1b1e4f1` |
| Python 报告复核、历史读取、工具参数兼容 | `2c1251cb` |
| 共同祖先 | `00122b899ec71e4ded4c97be27959ef3970b6da8` |
| 独立分支 | `codex/java-python-release` |
| 双亲合并提交 | `13d7970d`，父提交为上述两个固定版本 |
| Python 展示追加 | `9841218d`，父为 `2c1251cb` |
| 展示追加合并 | `87fbcaf5`，保留 `5e44da1d` 历史隐私修复 |

双方均包含检查时的 main。使用正常双亲合并保留前置依赖，没有重复 cherry-pick 后续三个提交。双方同时修改的文件只有 `research_session.py` 和 `specialist_graph.py`，文本自动合并成功；检查保留了 Java 侧运行配置/组织作用域和 Python 侧确认范围/期间提示逻辑。其他维护模块按 Python 完整提交链纳入，包括 Lead 当前综合与复核交接、作用域引用 ID、来源参数兼容，不直接覆盖整个工厂文件。

## 正常产品与运维边界

正常产品继续使用 Java 的当前成员/全部固定资料权限、不可变准备单、显式启动/接续命令，以及原生 Agent checkpoint。报告复核的当前任务投影、同版接续、换版历史目录和准确历史读取属于正常运行能力。历史意见不自动成为新版通过结论，历史读到正文不重新授予来源权限。

维护脚本中的旧记录导入、故障回放、人工观察批次、请求账本和诊断留痕属于运维。没有把私有 case 停点、手工补输入或模型倒计时导入产品入口。维护的 `scripts/engineering/replay_*` 可留作显式离线诊断，不能成为业务请求的隐式调用依赖。

Python 交接声明 case242 已到 `ready_for_human_review`，0 material / 1 advisory / 0 未完成资料请求。该声明对应已保存报告及原生复核，不能替代本分支的产品联调，也不是独立金融质量认证。本轮没有重跑 case242 或改变报告内容。

## 集成发现与修复

新增测试复现历史公开读取的内容块问题：`report_review_context._public_record` 和 `review_context.history_page` 不返回 `additional_kwargs`，但直接返回 `AIMessage.content`，结构化 `reasoning/thinking/redacted_thinking` 块可能进入公开回读及目录预览。

修复归属 Python 历史投影：复用 `context_records.public_text`，公开历史只呈现 AI 文本，工具参数及工具回执保持原身份，完整原生消息和 checkpoint 不改写。首次测试 2 个隐私边界失败、3 个权限测试通过；修复后相关回归通过。这里不声称恢复了已发出的历史信息。

新增组织工具测试复用实际 `CaseModelAudit`、签名授权客户端及静态授权响应，验证正常读取、调用前撤权、读取后撤权。撤权时不得继续下一次模型调用。正常及中断两种原生执行用 `InMemorySaver` 保存 checkpoint，连续三版报告各完成历史读取及本版提交，中断后不重复已完成读取。这是原生内存 checkpoint 验证，不是进程重启后的 PostgreSQL 持久化验收。

## 验收状态

| 层级 | 当前证据 | 边界 |
| --- | --- | --- |
| 合并后原有组织与 Python 运行回归 | 565 项通过，274.91 秒 | 不调用提供方，使用测试数据 |
| 历史投影修复、组织撤权、正常/中断连续换版 | 57 项通过，34.19 秒 | 与上一组部分重叠，不累计为 622 个独立案例；授权服务器为静态响应 |
| Java/配置/报告版本读取兼容 | 上述组织回归包含相关合同、读权限、checkpoint 绑定；Java 包重新构建 | 报告连续换版的进程重启验收仍待补 |
| 前端构建与准备单/报告页面 | TypeScript、Vite 构建通过；21 项静态浏览器测试通过 | 不等于真实后端页面联调 |
| 真实 BFF/Java/PostgreSQL/Redis/Agent Server | 同一个 NVIDIA 旧案例综合回归通过，308.09 秒 | 真实存储、队列、授权、工具和页面；模型决策及下游成文使用静态替身 |
| 展示导出追加交付 | 已合入 `9841218d`，共同版本追加验收见下节 | 不重跑 case242，不修改报告结论 |

Docker 在本轮开始时没有运行。一次正常启动失败于 Secrets Engine 残留 `engine.sock`；改名被系统拒绝，删除被自动审批返回 `blocked by policy`。随后用户恢复 Docker，三个共享容器健康。真实服务复验使用独立端口、网络和数据卷，没有重置、删除共享数据卷或切换后端。

静态浏览器第一次为 20 通过、1 超时；追踪显示首个 `page.goto` 消耗约 26 秒，整体达到 30 秒上限。保留追踪后，原样复跑 21 项全部通过，用时 2.2 分钟，没有调大超时或放宽断言。两轮记录都保留，不能将第一次失败从记录中省去。

本机日志位于仓库外 `Z:/FIN_Insight_Agent_qualification/20261020_joint_release`：`merged-regression-r1.log`、`history-boundaries-r1.log`（问题复现）、`history-boundaries-r4.log`（修复及接续复测）。这些路径是本次证据位置，不是安装依赖。

## 共同版本真实服务结果

`tests/integration/test_historical_delivery_stack.py` 在新子网及独立服务上通过，输出为上述证据目录下 `real-stack-r1`。同一案例从指标卡页面保存、发布与响应丢失恢复开始，连接组织资料、冻结输入、原生工具混合检索、原文和数据卡读取、明确启动/接续、报告及引用。

- 两个 thread、四个 run、14 次脚本回复，提供方调用为零。旧向量复用，没有生成或购买向量。
- 正常交付、重启后回读、丢失回执恢复三种状态，每种下载 Markdown/PDF/Word/PowerPoint；共 12 份实际文件均包含历史原文、指标身份及静态工程标记。
- 重启的是本次独占的 BFF、Java、Agent Server、PostgreSQL、Redis。报告、checkpoint 和运行身份不变；重复核对不会增加运行。
- 未选原件拒绝读取。撤销指标卡后，其他原文的缓存读取、整份报告、引用、事件及导出同样拒绝；不能只保护被撤销的那张卡。
- 完成后核对 8 个验收源码、214 个 runtime 源码、14 个前端构建文件和 Java JAR，均与开跑时一致。自有服务停止，原有三个共享容器仍健康。

旧验收脚本结果中 `runtime_neighbor_merged: false` 是历史硬编码标签，不是 Git 检查；本轮不能据此判断分支是否合并。真实基线见本页双亲提交、`environment.json`、`unified-source-contract.json` 与 `postflight-source-integrity.json`。没有改写旧结果文件来制造通过记录。

本轮证明固定运行基线下的组织业务连接成立，未覆盖所有真实专家、审查、修订决策。此前索引准备单与付费新查询向量已有各自专项证据；此综合案例沿用旧查询向量，不能把它算作新查询向量或容量的再次验收。金融质量、真实 SSO 和生产负载不在本轮结论中。

基线检查、秘密扫描（1134 个文件）及差异格式检查通过。前端生产构建有既有的大 chunk 提示，不影响构建通过。

## 网页阅读版追加联调

Python 展示提交固定后正常合并，未 cherry-pick 漏掉依赖，也未覆盖两个历史投影的隐私修复。集成发现并修复：

1. 组织研究接口及下载栏缺少 HTML 格式。新增 HTML 后仍由组织专用路由读取明确 checkpoint，渲染前后按当前全部输入权限检查，未开放个人接口读取组织 thread。
2. 阅读器原先只读取 `claim.citation_quotes`，组织引用使用的 `source.text` 摘录及 `period/unit` 没有显示。追加已有快照格式的展示兼容并转义，不查新原件，不改报告对象或 checkpoint。
3. 真实指标卡中长 JSON 使页面宽度达到约 3.7 万像素。代码块改为块内滚动；正文长摘要和 ID 允许换行。离线定位复测恢复为 1440/390 像素，未截断内容。

60 项后端渲染、版本、组织权限与历史隐私回归通过；前端 8 项桌面/移动检查通过，TypeScript/Vite 通过。HTML 的旧版本内容选择、生成中撤权拒绝、切换研究取消旧下载均保留；前端静态 HTTP 字节测试不替代真实渲染测试。

第一轮真实服务追加验收因上述 HTML 溢出失败，161.47 秒；修复后的第二轮 HTML 离线阅读、引用展开和宽度均通过，但新增两版报告测试使用默认 native state update，报告字段被输入 schema 过滤，179.91 秒失败。通过维护的 schema graph 离线复现后，测试显式指定 `as_node=initialize` 保存静态版本；不修改产品读取逻辑或放宽版本断言。这是测试设置修正，不是已经验证了真实用户修订。

两版测试通过原生服务保存独立 PostgreSQL checkpoint；这是测试夹具的显式状态更新，不执行模型/审查，也不是产品修订入口。结果证据写入本轮 `display-stack-*`，旧失败目录不覆盖。旧综合脚本中硬编码的 `runtime_neighbor_merged` 标签已删除，改为指向环境与真实源码指纹记录。

**最终追加复验通过：`display-stack-r3`，287.81 秒。** 正常交付、五自有服务重启后、响应丢失恢复三种状态下，HTML/MD/PDF/DOCX/PPTX 共 15 个下载文件内容通过；额外两个 HTML 文件验证旧、新 checkpoint 导出不混版。撤卡后旧新两版导出、原文缓存及所有成果读取均拒绝。两 thread、四 run、14 次脚本回复，零提供方调用；显式测试状态更新不计作新的模型研究。

三次实际 HTML 下载分别在离线浏览器以 1440/390 宽度打开，引用锚点、摘录展开及无外部请求检查通过。最终第二版 PDF 四页经 Poppler 渲染逐页检查；实际桌面阅读版截图也已查看。完成后核对 8 个验收源码、214 个 runtime 源码、14 个构建文件、补充的 6 个展示源码及 Java JAR，均未在运行中改变。CSS 修复后的阅读器单元测试 6 项另行通过；与前述 60 项重叠，不重复累计。

过程中 Docker 查询再次卡住。隔壁确认无 Docker/模型运行后按已有用户授权恢复：正常重启超时，停止 Docker 自有进程并终止 `docker-desktop` 后重新启动；未删除套接字、数据卷或虚拟磁盘。本轮结束时自有服务停止，原三个共享容器健康。恢复成功不等于查明了反复卡住的根因，仍需另行诊断。

## S1 追加：生产复核父图与 PostgreSQL（2026-10-21）

验收指导 `60499c06` 快进合入共同分支后，在独立 Agent Server / PostgreSQL / Redis 中执行实际 `create_agent` 和 `build_research_convergence_graph`，模型回复使用确定性测试替身。此次没有通过更新报告 state 来模拟修订。

**发现并修复的生产问题：** 单独的 verifier 能正常持久化，但生产父图再次进入同一复核角色时，默认的 per-invocation 子图 checkpoint 不会带入上一版工具回执。已有历史目录与精确读取工具因此不能获得原消息。改为两个串行复核节点各自的 per-thread 原生持久化；并行作者和其他角色不改变。

父图从断点接续还会向子图传递恢复语义。若子图已经完成，普通新输入可能直接读回旧输出。现在新复核基线明确清空旧 output，并用 `Command` 进入该子代理声明的入口节点，保留 before-agent 限额及授权中间件；相同基线继续使用原消息 ID，未完成旧版不能被新版覆盖。旧输出仍在历史 checkpoint 和产物历史中，不能当新版结论。采用框架已有机制，没有另建记忆库或调度器，机制依据见 [LangGraph 子图持久化](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)。

| 验收范围 | 最终证据 | 限制 |
| --- | --- | --- |
| 独立 verifier 正常及中断换版 | 两线程、六次版本复核、九个原生运行；指定旧 checkpoint 回读；三服务重启后值和 checkpoint 一致，已完成历史读取不重复 | 输入报告与历史回执为静态数据 |
| 生产 convergence 父图 | integrated 路由执行三版 writer→report_verifier、两次 writer 修订、四个原生运行；第二版后重启三服务；原来源读取一次、历史回读两次；新版均有独立提交 | 脚本意见为表达责任，不涵盖专家重研、真人交互或金融质量 |
| 两组真实服务合计 | **2 项通过，114.96 秒；13 个原生运行、21 次脚本模型回复、0 次提供方调用** | 次数是本验收的工程覆盖，不是性能或质量指标 |
| 父图定向回归 | 41 项通过，38.04 秒；包括子图重建、不同线程隔离、每版一个任务、六个调用与六个回执配对 | 与扩展回归重叠 |
| 扩展回归 | 初轮 120 通过、3 个既存断言失败；原 60499c06 convergence 在独立进程复跑同样三处失败。对齐当前综合交接后，其所属研究会话测试 12 项全部通过，19.21 秒 | 12 项与前轮重叠，不累计成 132 个独立测试 |

既存断言仍期待 writer 不接收 synthesis，而冻结 Python 基线已改为 Lead 继续当前综合。修正后的测试要求 `current_synthesis.v1`，并核对 writer 收到的综合正文与 research_verifier 核对的正文一致；没有回退实际写作行为或删掉交接检查。

本机证据：`Z:/FIN_Insight_Agent_qualification/20261021_release_acceptance/persistent-review-final-r1` 下的 `reviewer`、`convergence`，分别保留环境/源码指纹、每版 checkpoint、重启前后记录和机器可读结果。两组运行结束均核对源码指纹未变；日志/数据卷保留在仓库外。早期失败保留在同级目录：独立 verifier 的服务器运行 ID、静态断点 run/thread 状态及断点关闭属于测试假设修正；`convergence-persistence-r1` 则是真实父图缺失旧回执的问题复现。

### 复现入口

测试文件：`tests/integration/test_report_review_persistence.py`。默认跳过，明确启用后运行：

```powershell
$env:FIN_REPORT_REVIEW_PERSISTENCE_QUALIFICATION = "1"
# 指定新的仓库外 FIN_NATIVE_ATTEMPT_DIR；两组各建 reviewer/convergence 子目录。
# FIN_PROBE_SUBNET 和 FIN_CONVERGENCE_PROBE_SUBNET 为分别检查过的两个空闲子网。
# 其余沿用 tests/integration/test_java_intake_native.py 的隔离 Stack 配置：
# FIN_PROBE_IMAGE（本地固定 sha256 镜像）、FIN_NATIVE_LICENSE_ENV、
# FINSIGHT_TEST_DOCKER、FINSIGHT_TEST_JAVA、FINSIGHT_INTAKE_TEST_JAR。
# 基类记录 JAR，但本测试不启动 Java/BFF，实际服务清单以本测试 manifest 为准。
python -m pytest tests/integration/test_report_review_persistence.py -q
```

本次固定镜像内 LangGraph API 0.13.3、LangGraph 1.2.11、psycopg 3.3.4，未升级依赖。开发许可可用，但测试容器拒绝模型提供方凭据并关闭 tracing。测试仅停止自己创建的容器，不删除卷，也不停止共享服务。

## 2026-10-21：组织报告追问与修订的普通页面闭环

新增 V11 `organization_report_command`，由 Java 持久化每一轮追问/修订，固定请求标识、原生前序运行、检查点、状态摘要、报告版本和正文摘要。局部意见同时固定引用 ID 和同一个请求标识。Java CAS 领取一次派发，未知回执只查询原操作；Python 用相同固定命令恢复原生 `human_review`，在选择任何动作分支前核对真实 `Command.resume`，不只信任 metadata。

去重约束落在 **native checkpoint，而非 report_version**。两个不同问题可以使用同一 v1 报告，但第一个问题结束后必须读取新的 checkpoint。前一个操作回执未知时不能发起下一轮；修改同一幂等键内容、重新使用旧 checkpoint、绑定另一个 run 或撤销原资料权限均不能绕过。新 run 纳入组织成果、事件和引用的当前读取授权。已受理只表示派发回执确认，不表示运行完成。

普通项目成果页提供追问、修订关注范围（整份报告或已保存引用）、意见编辑、基线预览、二次确认、操作回执核对与历史对话。页面不直接调用 Agent Server，也不能在此更改准备时冻结的模型配置。组织人工完成/接受、失败运行的自动重试、专家重研质量不在本批交付范围。默认仍关闭，需要 Java 的 `FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED=true` 与 BFF 的同名变量 `1`。

| 验收 | 结果与范围 |
| --- | --- |
| Java HTTP + 实际 PostgreSQL | **32 项通过，41.40 秒**。新增案例覆盖五个并发相同提交只派发一次、丢回执、内容冲突、运行身份冲突、两次同报告追问、修订和撤权。其余为既有组织/准备/启动/读取回归。 |
| Python 定向回归 | **112 项通过，98.26 秒**。覆盖新增命令、引用目标与基线、接续/首次启动、实际人工审阅节点的请求篡改拒绝及个人报告/研究图兼容。无付费调用。 |
| 浏览器受控接口回归 | **7 项通过，约 1 分钟**。1440/390 宽度，确认前不派发、未知回执刷新核对、同报告第二次追问、读取撤权与导出。使用接口夹具，不能替代下行真实服务。 |
| 普通页面真实服务复验 | **1 项通过，145.93 秒**。实际 BFF / Spring Boot / PostgreSQL / Redis / Agent Server，**6 次 native run、4 条报告命令、2 个报告版本**；两次 v1 追问、C1 引用修订、第三次追问故意丢回执；无浏览器 API 拦截。五个自建服务重启后报告/对话/checkpoint 不变，四条回执均回读原 run；撤权后读取、预览、命令列表、核对与导出均拒绝。 |
| 构建与仓库检查 | Java JAR、TypeScript、Vite 构建通过；active baseline、秘密扫描（1155 文件）和 diff 检查通过。Vite 保留既有大包提示。 |

真实服务复验将初始报告、回答、修订与复核输出替换为明确标记的静态生产者，原生运行工厂、Java 当前授权、真实 `ReviewAction` 节点、报告版本规则、队列/检查点和普通页面均真实执行。身份为测试替身，不代表正式 OIDC/SSO 验收；也不证明专家重研、金融结论、召回质量或吞吐容量通过。**0 次提供方调用**是成本事实，不能解释为真实模型业务已测试。

证据保存在仓库外 `Z:/FIN_Insight_Agent_qualification/20261021_release_acceptance/`：

- `report-actions-native-r2/`：最终普通页面、请求记录、重启记录、`report-actions-result.json`、前端和源码指纹；前后源码一致。
- `report-actions-native-r1/`：首轮已走完交互和重启，在撤权测试读取资源分页时因测试脚本错误失败；未删证据。修正为读取指定资源的当前权限版本后完整复跑。
- `java-report-commands-r2.log`、`report-actions-python-final.log`、`report-actions-browser-r1.log`：对应上述分层结果；不累加重叠用例数。

复现入口为 `tests/integration/test_organization_report_actions_stack.py`，显式设置 `FIN_ORGANIZATION_REPORT_ACTIONS_QUALIFICATION=1`，沿用本文件上一节的隔离 Stack 配置，并提供已构建 JAR 和 `FINSIGHT_TEST_NODE`。每次使用新的仓库外输出目录和已核对未占用的子网；无需提供模型密钥。测试结束仅停止自己创建的服务，保留证据和数据库卷，共享部署未切换。

## 放行前剩余步骤

1. **组织追问/引用修订已完成上述静态工程闭环，但 S1 不能据此直接等同全部发布通过。** 仍需汇总同一发行版本与专用验收部署的清单，按执行计划核对 S1 范围；后续真实研究与专家修订另验，不能把静态生产者的结果当成模型质量证据。
2. 本次证明新的复核子图可以跨版本、跨进程继续；**不自动迁移旧 per-invocation 子图 checkpoint**。旧研究和进行中的任务保持原冻结部署。专用验收环境需记录代码、镜像、JAR、前端、数据库迁移与回退边界。
3. 组织业务和展示只完成各节限定验收。S1 尚未放行，main 未合入、共享部署未切换；后续按[第一版执行计划](first_release_acceptance_execution.zh-CN.md)进入产品交互和 RAG，而不是把本次静态图运行称为真实金融研究通过。
