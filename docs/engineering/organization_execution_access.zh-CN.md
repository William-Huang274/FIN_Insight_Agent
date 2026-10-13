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

导航前后、每份原件读取前后、引用与计算工具调用前后均核验当前权限。扫描多个来源后再次核权，避免前一份来源已撤权、后续扫描仍返回合并结果。已读缓存不是权限租约；观察记录仅存当前工具会话，不从模型参数导入别人的引用或个人记忆。跨运行恢复的观察记录校验和全图记忆隔离仍待接入。

2026-10-13 工程验证：新增15项组织协议测试（含真实LangGraph工具循环、脚本模型、MCP2与共享schema桥）通过；相关回归首次131通过、2项未授权外网探针跳过，额外53通过；最终共享窗口调整后73项重验通过（这些重验不重复计作新增测试）。真实签名BFF/Java/PostgreSQL/SQLite/MCP、成员退出/源撤权及Java重启1项22.85秒通过。没有模型、embedding、rerank调用。这证明协议与组件可消费，不证明FinSight完整团队图、原生运行接续、成果授权或金融质量已经完成。
