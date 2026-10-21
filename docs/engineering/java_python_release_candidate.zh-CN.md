# Java 与报告复核运行时：独立集成候选

当前结论（2026-10-21）：**S1 无付费共同工程基线已收口**，见[最终范围矩阵与实际部署身份](first_release_acceptance_execution.zh-CN.md#s1-最终范围矩阵2026-10-21)。真实研究执行仍关闭，整版产品、S2 检索质量及金融研究尚未验收。以下按批次保留历史停点与原始证据。

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

2026-10-21 普通生产路径部署预检：以共同文档版本 `8ee6946e`（运行实现仍为 `b1f807b6`）在仓库外冻结 415 个源码/前端文件和已验 JAR，未复制测试生产者入口。发现默认角色配置仍混用 Pro/low，因此只在专用配置副本中将十个研究角色对齐约定的 wire `deepseek-flash` / thinking enabled / high，保留各角色限额，离线加载校验通过；这不是新的付费预算，也没有改动仓库默认配置。公开资料库、向量矩阵和映射实际字节摘要均匹配原发布清单，尚不等于组织授权发布或缓存命名空间可复用。

用户随后明确本机没有现成 OIDC，并授权部署。**身份与业务部分已启动**：独立 Keycloak / PostgreSQL、HTTPS BFF `https://localhost:18866`、Java 18895 及新业务库 V11。两名真实账号经授权码 + PKCE 登录，9 个浏览器身份/成员检查和 2 个重启恢复检查通过，未使用测试身份或 API 拦截。部署说明、复现与退出范围见[本机 OIDC 部署](local_oidc_deployment.zh-CN.md)。

后续专用 Agent Server 18865 **已启动**，生产图和三服务独立持久化就绪；一份历史公开披露摘录已通过真实账号发布，索引注册、Java 固定准备单及原生草稿已联通，详见下节。执行仍关闭，不能把入口冒烟称为整个 S1/S2 放行。仓库外 `normal-deployment-r1/manifest.json` 分组件记录版本、部署源码补丁与配置摘要，整版 deployed/evaluated baseline 在共同验收收口前保持空。既有共享 18165 和三个容器健康、未切换。现有启动 helper 固定使用共享 Compose 项目名，不能原样用于专用环境。

1. **组织追问/引用修订已完成上述静态工程闭环，但 S1 不能据此直接等同全部发布通过。** 仍需汇总同一发行版本与专用验收部署的清单，按执行计划核对 S1 范围；后续真实研究与专家修订另验，不能把静态生产者的结果当成模型质量证据。
2. 本次证明新的复核子图可以跨版本、跨进程继续；**不自动迁移旧 per-invocation 子图 checkpoint**。旧研究和进行中的任务保持原冻结部署。专用验收环境需记录代码、镜像、JAR、前端、数据库迁移与回退边界。
3. 组织业务和展示只完成各节限定验收。S1 尚未放行，main 未合入、共享部署未切换；后续按[第一版执行计划](first_release_acceptance_execution.zh-CN.md)进入产品交互和 RAG，而不是把本次静态图运行称为真实金融研究通过。

## 2026-10-21：正常运行栈与组织资料准备

新增 `deploy/agent_server/compose.business-workbench.yaml`，使用独立 Compose 项目、子网和卷。复用既有 PostgreSQL 分角色初始化/生命周期迁移合同，并通过测试核对与原部署配置一致；配置不再要求旧案例报告、旧答案或旧资料目录。正常研究、通用对话、历史只读三图的 schema 加载通过。实际镜像仍为已核对的 LangGraph API 0.13.3 / LangGraph 1.2.11；原生服务 18865 正常，原来的共享 18165 保持健康。

部署发现并修复一个配置耦合：关闭研究执行时，原先 BFF 也没有组织草稿所需的研究配置。新增显式 `FINSIGHT_ORGANIZATION_PREPARATION_ENABLED=1`，只为组织准备加载配置；个人 `fresh_research_enabled` 仍为 false，Java 和原生启动开关仍关闭。Java 可固定准备请求并创建原生 thread，不能因此派发 run。业务资料、BFF host-settings 的父目录与容器挂载统一到本部署 state，避免读到另一份空资料库。

| 实际路径 | 证据和范围 |
| --- | --- |
| 真实 OIDC 浏览器 → BFF → Java → 发布存储 | 上传一份 NVIDIA 10-K 2026 历史公开披露摘录，发布到组织空间，关联项目，固定输入并准备；原文 3,053 字符，字节摘要与历史公开库的 context + body 完全一致。不是整份年报，也不作为金融结论金标。 |
| 项目与源权限 | 第二个真实账号已有项目成员资格，但读源资料仍 404；明确加入源空间后，读取正文与上传字节一致。 |
| 检索发布与固定准备 | 重新生成本组织/资源/版本的索引身份，经正常 BFF 登记到 Java。新准备单固定 release/model/dimensions/projection/两类摘要；旧准备单未覆盖。复用核验过的原文向量和成功查询回执，未复制旧主体、权限、排名缓存或缓存命名空间。 |
| Java → 内部 BFF → 正式 Agent Server | 两份准备单各创建一个 thread，回执 received；**2 threads、0 runs**。固定索引版本由同一 manifest digest 绑定到原生草稿，显式尝试启动仍返回 503。 |
| 实际 native 容器中的生产 MCP 工具 | 对固定来源执行两轮搜索→原文回读，第二轮命中该新组织发布版本的排名缓存；候选不能引用，回读原文才可引用，原文摘要一致。未准备的新问题明确报错，未回退公共库或调用 embedding。MCP 使用 SDK 进程内传输；不是完整研究图执行或外部 MCP 网络压测。 |
| 定向回归 | 部署/组织准备/命令/索引/混合检索 **42 项通过，28.97 秒**；源码启动与身份回归 **23 项通过，5.90 秒**。早前 14 项准备检查与 42 项重叠，不另累加。 |

本批 **0 次模型提供方调用**。向量复用范围仅 1 个原文叶节点、1 个已保存查询，模型 `qwen3.7-text-embedding`、1024 维。原查询历史 token 与 request ID 保留来源，但不记为本批新增费用。不能据此推断全库召回、并发容量、多资料覆盖、实时新查询可用或研究质量。

证据位于 `normal-deployment-r1/`：`publication-r1/result.json`、`frozen-preparation-r1/result.json`、`public-excerpt/provenance.json`、`organization-release.json`、`state/calls/native-retrieval-r1.json`、`native-deployment-audit.json`。后者核对 416 个部署文件/补丁摘要、真实注册图、两 thread 身份和零 run；模型凭据未进入 native 容器。截图为 `frozen-preparation-r1/project-sources.png`。生成文件和凭据均在 Git 外。

浏览器复现入口 `e2e/oidc-live-preparation.mjs` 分发布和冻结两个阶段；原件和向量在两阶段之间经受控主机发布，不能由浏览器指定服务器路径。容器只读检索入口 `scripts/engineering/probe_organization_retrieval.py` 使用浏览器产生的绑定文件和当前 Java 授权，拒绝启用付费查询提供方的环境。正式启用前仍需共同 S1 范围复核、S2 多资料/当前权限/检索质量、明确预算下的 S3/S4 模型研究与修订验收。

## 2026-10-21：多空间资料的页面准备与当前权限复核

本批沿用真实本机 OIDC、HTTPS BFF、Java/PostgreSQL 和专用 Agent Server。新建独立验收项目及 NVIDIA、AMD 两个资料空间，原件分别为历史公开库的精确摘录；只复用成功生成的对应原文向量与一个 NVIDIA 查询向量。普通研究成员操作页面，管理员只负责发布和调整权限。没有使用浏览器接口拦截、测试身份、模型替身或新模型调用。

| 验证范围 | 观察结果 |
| --- | --- |
| 普通页面 → Java → 原生草稿 | 实际勾选两份资料、选择已发布索引、填写截止日期、保存准备单、校验原件并选择标准协作。Java 保存的 `standard/default/[]` 及缺省 `continuation_scope=original_question`、`require_all_branches=false` 与原生冻结配置相同，配置摘要也相同，零 run。 |
| 同一生产 MCP 会话的混合检索与原文回读 | 两份候选均返回，第二轮命中排名缓存；候选不能引用，原文回读后才可引用，两个原文字节摘要均与旧向量来源对应。 |
| 撤销 AMD 空间成员资格 | 页面 API 隐藏 AMD 资料标题/原文，NVIDIA 仍可独立阅读；包含两份资料的冻结准备单整体不可读。已预热的搜索、原先看到的 NVIDIA 原文地址、AMD 原文地址均拒绝，3 次操作未返回 source items。该结果体现“准备单所有选定输入均须当前有权读取”的规则。 |
| 恢复空间权限、再撤销项目成员资格 | 重新授权后原 ID 可读；随后保留空间权限但移除项目资格，同一执行的缓存搜索和两个旧原文地址再次全部拒绝。恢复项目研究成员后，原准备单/索引/执行/引用身份保持不变。 |
| 定向回归 | 组织混合检索、来源导航、原生草稿共 **39 项通过，26.44 秒**；active baseline、Node 语法、秘密扫描（1166 文件）与 diff 检查通过。 |

**运行范围必须区分：页面准备确实进入了容器中的正式 Agent Server；本批两种撤权的持续 MCP 会话最终在宿主进程完成。** 首轮 `docker exec` 在 150 秒内未进入探针，`docker top` 同样挂起，但专用 18865 和共享 18165 HTTP 健康均正常。只结束本次挂起的 Docker 客户端，没有重启 daemon 或共享容器。之后以同一准备单及执行 ID、同一冻结源码（核对 315 个 `src` 文件摘要）、同一组织存储与真实 Java 授权完成宿主复验；没有重新提交研究。容器网络中的这组多资料撤权复验仍待 Docker 控制面恢复，不能用本结果替代。

本批结果为 **2 份公开摘录、2 类撤权、6 次受控拒绝、0 次模型提供方调用**，不是召回率、吞吐量、完整原文覆盖或金融质量指标。没有更改产品运行代码，也没有放开研究执行或修改整版 deployed/evaluated baseline。

证据位于仓库外 `normal-deployment-r1/multisource-r2/`：

- `publication/result.json`、`release.json`、`excerpts/manifest.json`：真实发布、原向量来源、索引身份。
- `acceptance-r4/prepared.json`、`selected-inputs.png`、`prepared-execution.png`：实际页面操作、Java 回执、配置摘要；同目录 `failure.json` 保留随后 Docker 超时，不能将整轮标为通过。
- `acceptance-host-r2/result.json`、`revoked-preparation.png`：复用上述准备单的最终宿主验收。对应 `state/calls/multisource-<execution>-acceptance-host-r2/result.json` 保留同一 MCP 会话各阶段结果。
- `python-regression.log`、`multisource-audit.json`：回归和正常服务/原生 thread 的无运行记录。

失败保留：`multisource-r1` 的 AMD 摘录因 Windows 文本写入将 LF 改为 CRLF，与旧向量对应的原文摘要不一致，被发布前检查拒绝；修复工具为原始字节写入，并在上传前检查摘要后，新建 `multisource-r2`。r2 的前两次页面尝试因测试选择器把包含选项文本的 label 当作精确标签而失败；第三次因测试未考虑 Java 的已定义默认字段而失败，随后明确核对两个缺省值及 Java/原生配置一致性，没有放宽产品规则。`acceptance-host-r1` 使用了未对浏览器开放的内部准备回执路由，被 404 拒绝；改走已有的正常“核对准备”入口，未新增绕过授权的接口。

复现顺序（需要专用本机部署及已核验的历史向量；不是安装/CI 前提）：

1. `python scripts/engineering/prepare_multisource_acceptance.py excerpts --deployment <部署根> --case <全新案例目录> --library <只读资料库> --vectors <已发布向量目录>`；该固定场景选择公开库中指定 AMD chunk，与前次 NVIDIA 摘录组成权限用例，不能换用任意文本的向量。
2. 设置 `FIN_NORMAL_DEPLOYMENT_ROOT`、`FIN_MULTISOURCE_CASE`、`FINSIGHT_PUBLIC_ORIGIN=https://localhost:18866`、`NODE_EXTRA_CA_CERTS=<部署根>/private/identity/tls/ca.pem`，从 frontend 目录运行 `node e2e/oidc-live-multisource.mjs publication`。
3. `python scripts/engineering/prepare_multisource_acceptance.py publish --deployment <部署根> --case <案例目录>`，根据当前 Java 授权读取精确节点并发布新索引。
4. 设置 `FIN_MULTISOURCE_PROBE` 为本仓库 `scripts/engineering/probe_multisource_authority.py` 的绝对路径、`FIN_DOCKER_EXECUTABLE` 为实际 Docker CLI，执行 `node e2e/oidc-live-multisource.mjs acceptance`。默认容器探针；每次 `FIN_MULTISOURCE_ATTEMPT` 使用全新输出名。
5. 若已有准备单而容器控制面不可用，可显式指定 `FIN_MULTISOURCE_PREPARED=<原尝试>/prepared.json`、`FIN_MULTISOURCE_TRANSPORT=host` 和 `FIN_MULTISOURCE_PYTHON`，只核对原准备并验当前授权。宿主方式会核对冻结源码，清除模型/追踪密钥并记录运行方式，不会自动降级或冒称容器复验通过。临时移除的本案例成员资格在结束或断言失败时尝试恢复；恢复失败会明确输出，不能静默忽略。

### 容器复验与 S1 清单核对：连接阻断仍保留

2026-10-21 后续复验复用了 `acceptance-r4/prepared.json` 的原准备单、索引与执行，没有新增 thread 或 run。发现默认 `desktop-linux` 对应的 `dockerDesktopLinuxEngine` 及 `docker_engine` 命名管道 `_ping` 超时，但底层 `docker_engine_linux` 返回 HTTP 200；Docker CLI 单次指定 `--host npipe:////./pipe/docker_engine_linux` 能正常 inspect/exec。验收脚本支持显式 `FIN_MULTISOURCE_DOCKER_HOST` 选择这一固定本机端点，不修改全局 context，不接受远程 daemon，也不重启共享服务。

`acceptance-container-r1/r2` 已真正进入生产 native 容器，但第一次检索取得当前 Java 授权时失败。独立有界连接检查确认 `host.docker.internal` 解析到 `192.168.65.254`，访问 Java 18895 以及专用 BFF 18867、18866 均 `ConnectTimeout`。宿主 Java 仍由同一进程自 09:21 起运行，源码配置明确绑定 `127.0.0.1`；私有配置文件 09:43 修改，早于 09:47 已成功的单资料容器探针。未发现本批修改监听/绑定的证据。当前 Docker/Java 入站规则为启用的 Allow，但没有历史防火墙快照，不能声称规则从未变化，也不能据此确定 Desktop 内部根因。

因此这是 **容器到宿主授权服务的连接阻断，不是缓存撤权断言失败**。空间/项目撤权阶段尚未进入，不能增加通过计数。没有修改授权白名单、公开 Java 外网监听、加临时测试代理或改生产 runtime。默认控制管道与宿主网关均异常只定位到 Desktop 控制/转发路径；其内部具体故障原因仍未知。最低恢复目标是先让同一容器可连接既有 `host.docker.internal:18895`，再以原执行和新 attempt 复验。若需重启 Desktop 网络/后端，应先协调全部共享容器及在途任务；只直连底层 engine 管道并不能恢复宿主网关。本批未执行该重启。

只读部署复核确认：实际 native 镜像与清单一致，416 个冻结源码/配置摘要及 Java JAR 摘要一致；业务数据库 Flyway V1–V11 全部成功；专用三服务、业务库及共享原生服务健康。现有 6 个 thread 均零 run，native 无模型提供方凭据，启动/报告动作开关仍关闭。证据为 `multisource-r2/container-connectivity-audit.json`，失败探针保留结构化异常叶类型/栈位置而不序列化授权头。部署 manifest 已明确改为组织授权连接降级状态，整版 deployed/evaluated baseline 继续为空。

S1 尚需恢复并验证上述容器授权路径、完成共同工程范围与部署清单复核。S2 则另有已核实的接入边界：组织工厂仅允许 `organization_fixed_inputs_only`，没有直接读取宿主公共全库的授权入口；当前 `organization-text-6000.v1` 每 6,000 字符切片，截断或超过 100,000 字符的单原件不能注册该索引。旧公共库 `context + body` 子 chunk 向量通常不等于这些新切片，不能静默套用。完整候选范围、完整原文发布与旧 source/chunk → 新授权 node 的无损映射要单独收口；本批未裁剪 gold 摘录来冒充完整候选池，也未批量上传、重嵌全库或启动新付费。

### 2026-10-21：Docker 恢复与原准备单容器授权复验

本节更新上节的连接阻断状态，保留失败证据。用户要求排障后，先与共享任务协调，确认两套原生服务均无 busy thread、没有在途模型请求，再正常停止原 9 个容器并重启 Desktop。启动分别被 Windows 无法移除的 `Docker/run/dockerInference` 与 `docker-secrets-engine/engine.sock` 阻断；检查父目录仅有零字节运行端点后，停机保留原目录、改名并重新创建空目录，随后启动成功。未恢复出厂设置、删除容器/卷或重建数据库。

这确认了两个故障层：原先 Desktop 控制代理与宿主转发路径失去响应，底层 engine 仍可用；后续启动又被残留 AF_UNIX 端点阻断。后者有明确本机日志及 [Docker 问题 #460](https://github.com/docker/desktop-feedback/issues/460) 的同类报告。维护者称 4.92 及以后版本包含修复；本机仍为 4.76.0.228118，本轮未升级，不能据一次恢复声称永久消除复发。控制/转发失响应的内部原因仍未确认；曾观察到 Dashboard 对大量已停止容器密集请求 stats，但没有因果验证，不据此删除历史容器。

恢复后实测：

- 原 9 个容器 ID、镜像 ID、挂载和命名卷与停机前一致；8 个带探针服务 healthy，Keycloak running 且 discovery HTTP 200。核对使用同一底层 engine 端点；Desktop 代理会改写 bind 源路径的 Windows/Linux 表示，不能把表示差异误报为卷迁移。
- 默认 Docker CLI 恢复；18165/18865 健康、18443 OIDC discovery、18866 工作台均 HTTP 200。容器到既有宿主 Java/BFF 连接恢复，未更改监听、防火墙或授权规则。
- 真实 OIDC 浏览器复用原 `acceptance-r4/prepared.json`、原 frozen execution 与索引，在实际 native 容器同一 MCP 会话内通过缓存预热、两个原文回读、空间撤权、项目撤权及恢复。两类撤权共 6 次 MCP 受控拒绝；资料标题和准备入口也遵守当前授权。未重新发布或新建研究运行。
- 实际业务库 Flyway V1–V11 全部成功；专用原生库仍为 6 threads、0 runs；416 个冻结源码/配置摘要一致。本批模型调用 0 次。

仓库外证据：`normal-deployment-r1/docker-recovery-audit.json`、`multisource-r2/acceptance-container-recovered-r1/result.json` 及 `state/calls/multisource-<原执行 ID>-acceptance-container-recovered-r1/result.json`。原失败记录及私有本机诊断日志保留；没有上传诊断包。部署 manifest 已解除组织授权连接降级，启动开关仍关闭，整版 deployed/evaluated baseline 仍为空。S1 共同范围/部署核对、S2 完整候选与检索质量及后续有预算研究验收仍独立待办。

### 2026-10-21：保留数据升级及恢复验收

在用户授权、共享任务确认无在途运行后，完成 Docker Desktop 4.76.0.228118 → 4.96.0.243774 原位升级，Engine 为 29.9.1。升级前停止原 9 个服务，对原 353 个本地卷制作 18 份冷备归档，共 6,016,009,937 字节，逐份校验 gzip 完整性和 SHA256，并保留容器、卷、镜像及配置清单。这是卷与配置备份，不是整块虚拟机、镜像或容器可写层备份；原虚拟磁盘保留原路径、文件 ID 和长度。

首轮安装因 `ProgramData/DockerDesktop` 的所有者不满足安装器要求而退出，未替换旧程序。用户手动执行管理员脚本后，仅该目录根的所有者改为 Administrators，访问规则不变、不递归、不删除，安装返回 0。升级后完成一次正常 Desktop 退出再启动，没有手动清理残留端点；不据此宣称睡眠恢复、强制终止或长期运行已稳定。

恢复核对与实际业务读取结果：

- 原 364 个容器 ID、镜像、挂载、环境及启动命令保持一致，原 353 个卷的身份元数据及原清单中 41 个镜像保留。另有备份阶段最后三次辅助容器留下的 3 个匿名卷，创建时间早于安装且无原服务引用，明确记录并保留；当前总卷数为 356，不把额外卷掩盖为“完全无变化”。
- 仅按原 ID 启动原 9 个服务：8 个有健康检查的容器均 healthy，Keycloak running，并通过真实登录验证。启动预热期间原生服务健康检查曾未通过，待其就绪后重新核对通过，未放宽健康标准。
- 18165/18865 原生服务、18443 OIDC discovery、18866 工作台均 HTTP 200；业务库 Flyway V1–V11 成功，416 个冻结源码/配置摘要、Java JAR 及原生镜像不变。专用原生服务保留 6 个 thread、0 个 run，执行开关仍关闭。
- 两名真实账号通过 HTTPS 授权码登录，身份与原项目成员关系保持一致；不重新创建项目或修改成员。原准备单在生产 native 容器通过 MCP 向现有 Java 核权，检索并回读两份原文，引用状态与原文 SHA256 一致；本轮不重复撤权操作，模型调用、ACL 变更及新增研究运行均为 0。

仓库外证据位于同批验收根的 `docker-upgrade-4.96.0/`：`upgrade-status.json`、`upgrade-audit.json`、`business-recovery-audit.json`、`oidc-recovery-r1/result.json`、`backup-summary.json`；原文读取证据在 `normal-deployment-r1/state/calls/docker-upgrade-readcheck/result.json`。部署 manifest 追加本次实际基础设施版本与证据，保留历史故障记录、原组件版本和整版 baseline 空值。本次通过的是升级后恢复验收，不替代 S1 共同范围、S2 完整候选检索质量或金融研究质量验收。
