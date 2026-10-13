# 组织执行绑定与受控资料工具

这是组织研究第三批的 3B 第一片，承接[输入准备](organization_research_inputs.zh-CN.md)。实现的是持久执行授权绑定、独立运行服务身份和受控资料 MCP，**尚未接入原生团队研究启动**。产品页继续返回 `execution_enabled:false`；这里的 `bound` 不表示已有 thread、run、付费请求或执行预算许可。

## 为什么先做这一片

原生研究仍按个人 owner 取资料、记忆和结果。仅在启动接口检查组织成员，会让后续工具继续沿用旧权限，或读取未选择的宿主数据。本片先建立实际可消费的固定资料通道，再接原生队列和成果读取。Java 仍是组织权限的唯一权威，Python 不复制成员表，也不以团队超级账号代替本次提交者。

本片的用户场景是：小李根据准备单选定两份团队资料，服务端为本次执行记录身份和输入清单。工具只能读这两份固定发布；小李失去其中任一来源权限、离开组织/项目、降为只读，或项目归档后，后续工具读取失败。管理员查看另一份自己有权使用的绑定不受小李离职影响，但不能冒用小李的绑定。

## 持久身份与接口

Flyway V6 新增 `organization_execution_binding`。一行固定绑定 ID、准备单 ID、提交者、原请求摘要和 manifest 摘要；准备单本身不可变。预定 thread ID 等于绑定 ID，**它还没有在 Agent Server 中创建或占用**。原生适配器必须检查既有 thread 的精确业务绑定，不能覆盖同 ID 的个人任务。

| 入口 | 调用方与语义 |
| --- | --- |
| `POST /v1/workspaces/projects/{project}/research-drafts/{draft}/execution-bindings` | BFF 内部签名调用；请求仅有 `id,manifest_digest`，真实用户来自委托身份；按研究角色和全部输入核权后保存绑定 |
| `POST /v1/workspaces/projects/{project}/execution-bindings/{id}/close` | BFF 内部签名调用；发起研究成员或项目管理员关闭绑定，允许在归档后关闭；关闭不依赖仍有源资料权限 |
| `POST /v1/runtime/organization-executions/{id}/access` | 独立运行服务签名调用；请求只有 `thread_id,manifest_digest`，Java 从持久记录找提交者，重查研究角色及全部当前来源权限 |

浏览器业务代理不开放以上路径；原有创建/查看准备单入口保持。相同 ID、同一提交者、同一准备单和原请求字节只产生一行及一条创建审计；不同内容返回 409。关闭可重放且审计一次，原提交重放不能重新打开已关闭绑定。创建/关闭使用现有组织和项目锁，事务内不调用 Python。

运行服务使用**独立于 BFF 的密钥** `FINSIGHT_ORGANIZATION_RUNTIME_SECRET`，至少 32 字节；Java 拒绝与 BFF 共用同一密钥。未配置时运行服务鉴权关闭。运行委托固定 issuer/subject 为 `finsight-agent-runtime`，audience 为 `finsight-java-organization-runtime`，有效期最多 60 秒，绑定 method、完整 path/query 和原始请求体 SHA-256。运行凭证不能调用项目管理接口，BFF 用户凭证也不能调用 runtime 接口。运行请求不接受 owner 字段。

响应包含固定绑定、Java 保存的 manifest 原始文本和内部输入引用。Python 校验原文本 SHA-256、准备单/项目/组织身份、输入集合和每个精确 AssetRef 后才访问存储；不通过 JSON 再序列化猜测 Java 的摘要。绑定及内部引用不交给模型作为可改写的身份参数。

鉴权前只接受由固定 API 名称和 UUID 构成的规范路径；拒绝百分号编码、matrix 参数、重复斜杠和目录跳转。查询参数仍按原样参与签名，不受路径字符限制。原因是 Servlet/Spring 路由会规范化路径，不能用未规范化的字符串选择凭证域，却让控制器接受另一种路由解释。回归已覆盖编码路径不能把用户凭证带入 runtime 接口。

## Python 实际工具与撤权行为

`OrganizationExecutionAuthority` 每次发起独立授权查询，无成功授权缓存、无自动重试、不跟随重定向；超时、错误状态和合同不一致都作为执行问题拒绝，不能变成“资料没有找到”。当前桥接仅支持显式配置的本机 loopback HTTP，与已有单机业务桥接保持一致。Docker 跨主机网络、TLS 和密钥轮换尚未部署，不应为连通而把 Java 端口直接暴露。

`OrganizationExecutionReader` 复用组织发布原件的 `AssetWorkspace`，检查字节摘要与捕获的来源快照。工具读取前核权，存储 I/O 后再次核权，两次响应必须一致。请求中仅接受固定输入的 resource ID 和分页参数，不能指定 owner、路径、SQL、数据库连接或任意资料版本。

独立 MCP 组合只提供三个工具，不混入现有宿主的通用 SQL/搜索/个人记忆工具：

| 工具 | 返回内容 |
| --- | --- |
| `list_organization_evidence` | 当前仍有权使用的整份固定输入目录和版本；任一依赖失权时拒绝整份目录 |
| `read_organization_evidence` | 所选原件文本、版本、来源捕获元信息、字符分页与截断状态；单页最多 16,000 字符 |
| `read_organization_evidence_rows` | 已发布财务快照行，最多 100 行/页；保留原十进制字符串、期间、单位与来源，不开放实时 SQL |

来源阅读器本身的文本上限仍为 100,000 字符，`source_truncated` 明确区分原件投影截断与工具分页。扫描图片保留 `needs_vision`，不把缺少 OCR 解释为没有金融内容。财务结构行独立分页，不通过文本摘要替代结构化数字。

`research_as_of` 仍是准备单记录的研究意图，本片不新增历史可知日筛选或金融时点资格证明；原日期、来源和期间保留供后续研究适配器校验。

撤权不能收回已经返回的数据；本片阻止后续读取。权限恢复可以恢复仍有效绑定的读取，但不自动启动或接续任何运行。显式关闭的绑定永久不可读，需要另行建立新绑定。检查之后立即撤权的窗口不宣称被跨库事务消除。

Reader 的 `check` 可用于现有 `ResearchAuditMiddleware.source_access_check`，测试验证它在 provider 调用与预算预留前拒绝失权请求。这只是明确的运行时注入点与静态消费证据；**生产原生图尚未自动注入此绑定或切换资料组合**。完整启动必须同时处理个人记忆隔离、每次模型/工具调用、接续、事件、报告及导出，不能只传一个回调便开放团队运行。

## 复现与验收边界

```powershell
# apps/business-service；JDK21、Docker、独立 Testcontainers PostgreSQL
./mvnw.cmd verify
# 仓库根；合成授权服务、实际 SQLite 原件、实际 MCP 和模型传输替身
uv run --no-sync python -m pytest -q tests/test_organization_execution_access.py tests/test_organization_research_inputs.py tests/test_resource_spaces.py tests/test_project_asset_revocation.py
# 实际 BFF 签名 / Java / PG / SQLite / MCP，含 Java 进程重启
$env:FINSIGHT_INTAKE_TEST_JAR=(Resolve-Path apps/business-service/target/business-service-0.1.0.jar).Path
uv run --no-sync python -m pytest -q tests/integration/test_resource_spaces_stack.py
```

合成身份不替代真实 OIDC 验收。授权服务失联用确定性传输错误注入；模型边界用静态 provider 替身，不调用模型、embedding 或 rerank。没有重新部署现有服务，没有金融结论质量或生产容量的新增证据。

2026-10-13 本地工程结果：Java 全套 22 项通过，含 V2→V6 升级、并发幂等、撤权、关闭与路径身份域测试；Python 41 项通过、1 项因缺少独立本地研究资源配置而跳过（该项为既有通用财务 MCP 测试，新增组织用例没有跳过）；真实签名/PG/SQLite/MCP 与 Java 重启链路 1 项通过，25.71 秒。活跃基线、950 文件密钥扫描及 diff 检查通过。首轮 MCP 返回声明错误和编码路径绕过的失败记录保留，修复后结果不累加为额外用例。

3B 第二片已接[原生草稿受理](organization_native_drafts.zh-CN.md)：服务器验证完整执行绑定，创建或核对精确 thread，固定准备配置；不复制个人资料或记忆。V6 绑定本身仍不创建 thread，必须显式提交 V7 准备操作。在完整工具组合、事件、成果与导出权限闭合之前，团队启动仍保持关闭。

## 3B 第三片：接入现有原文、引用与计算协议

`OrganizationSourceNavigation` 将固定组织原件适配为现有 `SourceDocumentResult`，新增显式 `source_space=organization`；旧空间与旧请求序列化保持兼容。没有直接把独立原件工具当作完整研究图：当前研究图还依赖来源绑定、专家能力目录、已批准数据基座和底稿存取，需要后续逐项接入。

本片由现有 MCP2 schema 桥消费以下窄工具组合。`organization_source_tools` 只允许且要求这三项，原 `case_mcp_tools` 仍要求原有底稿工具，不放松审查入口。

| 工具 | 规则 |
| --- | --- |
| `read_source_document` | 仅组织 catalog/outline/search/read；文档 ID 绑定资源与 AssetRef 摘要，节点 ID 绑定该版本的文字块；返回原件摘要、manifest、明确窗口及下一次读取参数 |
| `read_research_source` | 仅本工具会话已实际读出的 PASSAGE/CALC；原文引用按原 readback 再读，检查原件与身份；复用现有来源窗口格式 |
| `calculate_research_metric` | 复用 Decimal 来源绑定计算；检索预览不能作为操作数，引用必须带原句和原数字；计算不授予金融口径或事实权威 |

目录、搜索和大块的 `window_required` 都不是可引用证据。正式读取才生成 `PASSAGE::`。组织来源身份随引用进入现有来源摘要，保存 `organization_source.ref`、资源 ID、manifest 摘要、源投影截断与来源捕获信息。字符块由组织原件的现有文本投影生成，不伪造 PDF 页码；大块用 `character_offset/next_readback` 读取。当前投影仍受原件阅读器 100,000 字符上限限制，需视觉读取或空正文明确失败，不将其视为未披露。

组织搜索强制使用本地关键词/BM25，不继承宿主 `FINSIGHT_SOURCE_HYBRID` 开关，避免把组织正文隐式送给 embedding/rerank。未开放宿主 SQL、个人 uploads、公共 library 或 web；不允许失败后落回这些空间。公开引用 URL 指向配置的工作台组织项目资源入口，浏览器仍需当前权限。

导航前后、每份原件读取前后、引用与计算工具调用前后均核验当前权限。扫描多个来源后再次核权，避免前一份来源已撤权、后续扫描仍返回合并结果。已读缓存不是权限租约，不从模型参数导入别人的引用或个人记忆。同一组织执行的历史来源恢复见第六片；底稿隔离见第四片，完整阶段工厂仍待接入。

2026-10-13 工程验证：新增15项组织协议测试（含真实LangGraph工具循环、脚本模型、MCP2与共享schema桥）通过；相关回归首次131通过、2项未授权外网探针跳过，额外53通过；最终共享窗口调整后73项重验通过（这些重验不重复计作新增测试）。真实签名BFF/Java/PostgreSQL/SQLite/MCP、成员退出/源撤权及Java重启1项22.85秒通过。没有模型、embedding、rerank调用。这证明协议与组件可消费，不证明FinSight完整团队图、原生运行接续、成果授权或金融质量已经完成。

## 3B 第四片：组织执行底稿的当前权限

底稿可能包含原文摘录和衍生判断，不能只保护原文件。`organization_memory_scope(reader)` 从 Java 已校验的固定授权推导 `organization:<organization_id>` 与执行 ID，不接受模型指定的 owner 或 workspace；复用现有 SQLite 工作底稿，不新增成员表或另一套存储。当前采用准备单同一规则：项目研究资格和全部所选来源都仍可用，才允许继续读写本次执行的底稿。底稿归组织保存，但同组织不同执行不会自动共享；研究内不同 Agent 可以协作。这里不实现人员交接或管理员跨研究阅读。

保护作用域内的 `memory_for` 不允许显式参数改成另一位用户或另一项研究，嵌套旧 scope 也不能降低原保护。存储连接在 I/O 前后检查授权，覆盖正文、历史版本、搜索摘要、人工修订目录、版本清单、导出及写入。已获取对象不缓存授权；离开作用域后，旧对象和复制的异步上下文不能继续读取。`asyncio.to_thread` 与实际 LangGraph 工具循环已纳入静态测试。

授权失败使用 `WorkingMemoryAccessDenied` 停止工具执行，不落入原先“底稿存储暂不可用，可以继续研究”的可选错误分支；同样不能降级成空目录或关键词兜底。普通个人底稿的非授权存储错误仍沿用原行为。组织底稿搜索固定使用本地关键词，即使宿主开启语义检索也不创建 embedding/rerank 请求；直接调用语义搜索实现也会被拒绝。

前后核权仍不是 Java 与 SQLite 的分布式事务：写入提交后若撤权，调用拒绝返回成功，但记录可能已经保存。不得自动重放写请求；恢复权限后读取当前版本再处理。已经返回的内容无法撤回，最后一次检查与输出之间也不是零时间窗口。

复现新增测试：

```powershell
uv run --no-sync python -m pytest -q tests/test_organization_working_memory.py tests/test_working_memory.py tests/test_working_memory_search.py
# 同上方真实服务用例；现在还覆盖已取得的底稿对象撤权、同组织执行隔离和重启回读。
uv run --no-sync python -m pytest -q tests/integration/test_resource_spaces_stack.py
```

本片是可供运行工厂使用的受控存取组件，**未解除 `research_session_graph` 对组织运行的拒绝**。完整工厂的 Lead、专家、审查、修订仍须共同接入组织资料组合和模型前核权，观察记录恢复、原生启动/接续及事件/成果/导出对外接口也须闭合。这里的底稿导出保护不等于产品报告导出已完成组织适配。

2026-10-13 工程验证：包含32项新增组织底稿用例的相关 Python 回归168项通过；实际签名BFF/Java/PostgreSQL/SQLite/MCP、成员退出、源撤权与Java重启1项36.61秒通过。活跃基线、960文件密钥扫描及diff检查通过。没有模型、embedding、rerank调用；没有部署共同分支。脚本Agent循环证明框架能消费这一作用域并在撤权后停止，不能代表完整投研流程或金融结论质量。

## 3B 第五片：实际专家入口的组织数据组合

`OrganizationDataFactory` 通过 `open_specialist_receipted_composition` 新增的服务端依赖注入入口，接入实际专家图及其供 Lead 使用的 `source_reader`。默认个人/公共研究仍使用原 `open_approved_data_composition`。本片不修改原生图启动开关；尚未让产品的整个 `research_session_graph` 自动选择组织组合。

组织组合只打开固定输入的原文 MCP、方法和来源绑定计算，不读取宿主公共库、历史财务 SQL、个人上传或外部搜索配置。专家能力目录明确披露 `organization` 空间以及财务查询不可用；不再为了构造专家输入而强制要求财务指标列表，也不伪造旧案例的批准清单或来源覆盖。已有财务快照仍可作为已发布原件阅读，不等同于开放实时 SQL 或赋予 NumericFact 权威。

方法作用域新增 `organization_fixed_inputs_only`，旧 wire ID、默认策略及旧摘要保持兼容。组织方法绑定校验执行尝试、专题集合、原件 manifest、任务 foundation 和截止时点；原文调用必须携带完全匹配的作用域。宿主须传入与准备单日历日期一致的带时区时点，不替组织猜测截止时区；这仍不证明原件在该时点已公开。MCP 工具目录在组织模式下只要求实际具备的能力，原有公共数据模式的完整工具要求不放松。

组织模式的 evidence lane 仅接受组织原文请求，finance lane 仅承载已有来源绑定计算；直接 SQL 查询和其他资料空间返回明确工具失败。计算仍区分来源数字、显式情景假设与金融口径核验。沿用现有方法/工具回执、任务摘要和专家观察记录，未引入新的执行或回执系统。授权在工具和模型调用边界重新检查；静态验收证明撤权后不会进入下一次模型端口。

**恢复与跨阶段仍有明确限制。** 第五片交付时拒绝非空 `restored_observations` 和 `case_artifacts`；第六片接入前者的原件校验与计算复算，第七片接入后者的底稿范围/来源校验和审查工具。完整阶段工厂与事件/成果/报告导出仍待统一；不能把实际专家或审查节点消费当作整个团队研究已经启动。

复现：`uv run --no-sync python -m pytest -q tests/test_organization_data_composition.py`。15项组织组合用例通过，包括实际专家图读取原文并保留引用/回执、越界能力拒绝、方法作用域篡改、时区与任务身份、计算及模型前撤权。相关回归202项通过（包含这15项；加强原文断言后15项另行重验通过，不累加为新增），真实Java/PG/SQLite/MCP与重启联调1项28.31秒通过；实际Java退出成员时，已打开专家入口立即拒绝新读取。全部使用静态模型回执或禁止调用模型的端口，没有付费调用，也未部署。

## 3B 第六片：同一组织执行的历史来源恢复

`OrganizationSourceNavigation.restore` 接收服务端保存的专家观察记录，逐项验证后提供给现有 `OrganizationDataFactory`。实际专家 `recovery_state` 入口已消费这一恢复能力；MCP 不新增上传或注册历史来源的工具。原生 checkpoint 仍由宿主保管，来源校验不证明整份 checkpoint、模型回执或作者判断的真实性。

- 原文按保存的 `readback` 重新读取固定版本，核对正文、定位、引用 ID、发布引用与执行/manifest 身份。另一执行即使选择同一份原件，也不能直接导入它的观察记录。
- CALC 按依赖顺序重新读取原操作数、引用句与显式假设，沿用 Decimal 计算器重新执行，再比较结果、单位、公式、依据和权威标记。嵌套计算可乱序存放；缺失依赖、循环或冲突副本明确拒绝。极小十进制数保留精度，损坏的非有限数或超范围指数在展开前拒绝。
- 恢复前、原件读取前后和整批发布前重新检查 Java 当前授权。通过校验的来源先暂存，整批成功才加入本次会话的观察表；失败批次不部分发布。先前已验证的会话来源可作为依赖。权限检查后的极短撤权窗口仍不宣称被跨库事务消除。
- 导航预览和失败结果不成为引用；NumericFact/已审查证据不由这一组织入口恢复。重新生成的来源不携带旧传输回执，原 notebook 历史仍保留用于审计。算术与原件匹配不等于金融口径或结论正确。

兼容性：新增组织来源记录保存 `execution_id`，组织 CALC 保存执行范围，并将组织来源身份传入操作数的 provenance。缺少这些字段的早期组件试验记录不被自动补身份或升级，需在当前授权下重新读取；组织 CALC 内容摘要可能因此改变。此路径尚未部署或开放产品团队运行，既有个人/公共来源协议及其默认行为保持不变。

复现：`uv run --no-sync python -m pytest -q tests/test_organization_source_restore.py`。静态验收涵盖实际专家保存→关闭组合→恢复专家图、旧引用经 MCP 回读、篡改/跨执行/撤权/原件损坏及恢复原子性。真实 `tests/integration/test_resource_spaces_stack.py` 同时验证 Spring/PostgreSQL 的成员退出、服务重启后合法恢复、源撤权后拒绝恢复。审查底稿由第七片接续；完整阶段工厂、团队启动/接续产品入口、事件/成果/报告导出授权仍待完成，不新增付费研究质量证据。

2026-10-13 本片验证：相关回归342项通过（包含当时21项恢复用例），最后补充数值边界后恢复用例25项全部复验通过，重复用例不累加。真实Java/PG/SQLite/MCP联调1项44.51秒通过；活跃基线、963文件密钥扫描和diff检查通过。零模型、embedding、rerank调用；现有原生与BFF健康检查均200，原3个容器健康，未部署共同分支。

## 3B 第七片：审查底稿、短引用与修订消费

`OrganizationDataFactory` 现在接受服务端 `CaseArtifacts`，先检查七项绑定：case、snapshot、research_as_of、foundation、授权决策摘要、来源目录摘要、输入清单摘要。缺少这些绑定的仅来源视图、其他研究的底稿和伪造资料权威明确拒绝。核验整批底稿来源与待恢复观察记录后，`data.case_artifacts` 返回独立副本：正文、标题及修订视图保持原样，来源区使用重新生成的 PASSAGE/CALC；原作者 checkpoint 和审计回执不被覆写。该对象是宿主内存视图，不能脱离授权边界直接作为用户读取接口。

审查仍使用现有 `research_artifact_catalog`、`read_research_artifact`、`search_research_sources`、`read_research_source` 和 `calculate_research_metric`，没有另一套底稿库或权限表。MCP 中间件覆盖目录、标题、FTS 摘要及全文，调用前后检查当前全部来源权限。`P01:S001` 等短引用只在本底稿副本内解析；计算请求中的短引用转成完整 PASSAGE/CALC ID 后执行，因此保存的操作数不会因下一轮底稿编号变化而失去身份。组织结果继续带执行范围，不获得 NumericFact 或金融语义权威。

现有 `CaseModelAudit(source_access_check=data.access_check)` 补齐异步工具调用前后及模型返回后的检查，覆盖审查 Agent 的本地底稿/意见工具。返回后失权时保留私有响应与已知/未知用量记录，再阻止候选正文投影和后续工具派发；不把已经成功返回的模型请求记为未调用，也不重试。此检查不能撤回已发送给 provider 的输入、先前已发送的内容，也不是写操作的跨库回滚。原生事件/SSE及最终成果访问仍需后续产品入口验收。

复现：`uv run --no-sync python -m pytest -q tests/test_organization_case_artifacts.py`。用实际专家图生成带原文和 CALC 的底稿，经现有审查 Agent 的静态 LangGraph/MCP 循环消费；原作者通过 `recovery_state` 与修订意见提交新稿，保留原观察，再进入校验后的底稿视图。修订限定审查也复用现有入口。测试审查明确标记金融质量未完成，避免把运行成功当作研究通过。

第七片提供组合能力与节点消费证据；第八片继续接入 `create_research_phase_runnables` 的组织工厂选择。默认个人组合保持原有选择，组织原生研究仍未启用；团队启动、接续、事件、成果及导出还需产品入口验收。前端与现有部署未修改。

2026-10-13 本片验证：相关回归425项通过，包含25项新增组织底稿测试；真实Java/PostgreSQL/SQLite/MCP联调1项69.34秒通过，覆盖成员退出、服务重启后底稿恢复及源撤权。首次真实栈因Docker管理API无响应中断，恢复原服务后补验通过；验收命令新增超时、独立容器名和身份记录，避免无限等待或不明对象清理。活跃基线、964文件密钥扫描及diff检查通过。零模型、embedding、rerank调用；原部署三个容器健康，两处健康检查200，共同分支未部署。静态Agent提交、审查与修订证明节点消费，不能代表完整组织产品流程或金融结论质量。

## 3B 第八片：现有阶段运行工厂的组织接线

`create_research_phase_runnables` 增加仅服务端注入的 `organization_data_factory`。工厂要求 v2 契约、执行 ID 与 thread 相符、专题 ID/目标与固定 foundation 相符，并重新核验当前授权。Lead、独立专家、委派专家、原作者修订、审查、成文和追问使用同一个组织组合选择；不打开宿主公共资料库、个人附件、财务 SQL 或 web。截止时点来自已验证的组织工厂，能力目录仍明确说明仅固定原件可用。

保存的已完成底稿先校验研究范围及来源，再交给 Lead；未完成底稿也校验七项绑定并恢复观察记录，不能等到它被再次调度时才检查。专家读依赖底稿时使用校验后的来源视图，并在读取前后核权。撤权属于执行中止，不能作为“工具参数错误”反馈给模型尝试修正。原 notebook 回执仍是审计历史，不被重写成新的读取记录。

各阶段进入和返回前核权，在整个阶段内建立组织底稿作用域。Lead/专家的模型端口也前后核权，本地审查/成文工具沿用 `CaseModelAudit` 检查。权限变化阻止下一次派发或阶段候选结果返回；已发生请求的响应与用量继续按原审计规则保存，不自动重试。这些检查不能撤回已经传输的内容，也不替代事件/SSE、报告读取的产品授权。

修订后审查和成文重新打开当前底稿对应的组织工具视图，本地验证器与 MCP 工具读取同一稿。原作者修订保留作者身份、原任务计划、来源观察和服务端模型历史恢复规则，不能用一份新会话冒充原作者接续。

**尚未开放产品团队运行。** 第八片交付时组织 `orientation` 预研究仍因缺少导航适配而拒绝；第九片接通此阶段。原生 `research_session_graph` 的组织启动拦截继续保留，直到服务端构造工厂、启动/接续及事件/成果/导出访问全部接通并验收。

复现：`uv run --no-sync python -m pytest -q tests/test_organization_phase_factory.py`；真实 Java 联调仍使用 `tests/integration/test_resource_spaces_stack.py`。新增静态用例经过实际阶段工厂、Lead/专家图和审查/追问 Agent，覆盖来源读取、委派、失权和旧状态越界。修订与成文版本一致性测试使用受控收敛驱动来调用生产回调，因此不宣称一次完整的真实模型收敛已通过；原作者历史来自合成审计记录。金融质量明确未验收。

2026-10-13 本片验证：相关回归529项通过（包含26项新增阶段工厂用例），真实Java/PostgreSQL/SQLite/MCP联调1项79.47秒通过；其中已保存的阶段工厂在Java撤权后拒绝再次调用。定向86项与广泛回归重叠，不累加。Docker管理接口故障在本轮测试容器创建前发生，保存现场并恢复后联调一次通过；原三个服务健康、健康端点200。零模型、embedding、rerank请求，未部署共同分支。

## 3B 第九片：组织预研究导航与反馈

现有预研究阶段根据宿主已验证的资料工厂选择导航合同。公共资料库仍使用 `OrientationLibraryReadAction`；组织使用 `OrientationOrganizationReadAction`，二者沿用 `RequestSourceAction` wire ID，不更改旧空间和身份。组织仅披露 `catalog/outline/search/read`，能力投影、工具 JSON schema 和 provider 系统提示同步选择该范围；不是只修改一行提示词。执行端仍校验能力和固定原件，模型参数不能授予资料访问权。

组织预研究没有公共关系图、公司最新资料菜单、实时 SQL 或 web。提示和 `TokenBudgetBasis` 明确采用固定原件，要求按问题说明图谱/时效核查的限制，不伪造导航调用。输入清单、截止时点与组织发布不能证明历史可知日或当前资料完整性。共用原有逐字摘录、窗口身份、数值/期间一致性检查、问题覆盖和专题依赖规则；预研究只保存初步结果和拟议专题，不派发专家，也不产出最终报告。

`orientation_public_handoff` 保留引用原有的 `organization_source` 身份，后续规划仍需在本次授权下重新读原件，不能把上游 O 引用当作本轮读取回执。资料疑点/补查反馈复用 `ResearchFeedbackStore`，owner 从工厂推导为组织、thread 为执行绑定，读写前后核验当前权限。撤权立即终止 Lead 工具路径，不再作为 ValueError 参数错误交给模型重试。写入提交后发生撤权仍可能保留历史记录；拒绝返回不意味着跨库回滚，不能自动重放。

复现：`uv run --no-sync python -m pytest -q tests/test_organization_orientation.py tests/test_research_orientation.py tests/test_research_feedback.py`。实际阶段工厂和Lead图经过静态模型读取固定原件、保存反馈、提交带逐字引用的预研究；独立测试经过真实模型SDK和内存HTTP传输验证schema/提示选择，无外部模型请求。篡改摘录不能提交，资料读取/反馈读取/反馈保存期间撤权阻止后续模型调用。真实Java集成测试同时覆盖重启后的预研究与源撤权拒绝。

原生宿主启动仍待接入。当前 runtime access 证明执行绑定及资料权限，不包含已持久化的原生准备命令/配置回执；这些在 BFF preparation-access 中核验。下一步必须让原生宿主核对Java可信准备/启动记录、thread冻结配置和本次运行身份，使用已保存的时点及明确时区策略，构造组织工厂与底稿作用域，避免复用个人 guidance/资产/记忆入口。不得仅信任 thread metadata 或客户端 configurable 后解除启动拦截。容器到Java的受控地址、产品启动/接续、事件、成果和导出授权须继续验收，不能将本片阶段验证宣称为完整原生产品运行。

2026-10-13 本片工程验证：231项相关回归通过（含10项新增组织预研究用例），真实Java/PostgreSQL/SQLite/MCP联调1项80.20秒通过。公共library默认系统提示与上一提交逐字一致；原schema与旧测试保持通过。真实模型SDK仅使用内存HTTP替身，零外部模型、embedding和rerank请求。原生组织run未创建，现有部署未更换；前端、Java源码未修改，未重跑其构建或Java单元全集。
