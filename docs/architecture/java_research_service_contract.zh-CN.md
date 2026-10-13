# Java 产品后端与 Python 研究资料服务：初步接口边界

日期：2026-09-23。状态：已与 Java 方案任务完成初步接口对齐；不是已实现 API，也不代表跨服务验收完成。

Java 方案任务认可七类逻辑能力与职责边界，并要求补充单一权限权威、固定快照贯穿回读、现有精确数值投影复用、原始提交稳定性及 Python 长期服务职责。本文已采纳。评审原件保存在本地工作记录，不作为安装依赖。

本文件约束[检索优化方案](retrieval_optimization_review.zh-CN.md)后续实施中的跨语言边界。保持现有 HTTP 路由、工具 wire ID、来源与记录 ID 兼容；下列名称是逻辑能力，不是已经创建的端点。

## 1. 职责与数据所有权

| 层 | 负责 | 边界 |
| --- | --- | --- |
| Java / Spring Boot | 用户与项目业务、成员/资料访问策略、研究申请、业务提交记录、成果流转、面向前端的聚合 | 不直接写 Agent Server 内部表，不新建另一套研究执行器或模型预算账本 |
| Python 研究与资料服务 | 解析、索引、检索、金融口径与固定计算、原文/数据卡、资料快照、研究配置和实际模型用量 | 不信任客户端自报 owner/project；业务权限迁出后仍须验证可信授权及资料撤销 |
| Agent Server | 原生 thread/run/checkpoint、执行、暂停恢复与事件 | Java 保存关联和业务状态，不修改原生运行身份或重启运行来恢复事件 |

Java 可管理资料业务归属，Python 保留研究处理事实。过渡期按能力明确单一写入方；可写业务记录与不可变研究发布库不要求放入同一种数据库。Java 不读取宿主 SQLite 路径、NumPy 文件或 Python 对象；通过服务访问研究数据。

Python 可以长期承担研究资料服务职责；不把全面迁到 Java 作为目标。只有明确工程需求和验证结果支持时才替换具体能力。

## 2. 最小逻辑能力

| 能力 | 主要输入 | 主要输出 |
| --- | --- | --- |
| resolve_entities | 名称/代码/别名、实体类型和范围 | 稳定实体/证券 ID、匹配依据、歧义候选 |
| search_evidence | 查询、实体/来源范围、截止日、检索配置 | 证据候选、检索通路、来源、回读引用、截断状态 |
| expand_relations | 起点实体、类型/方向/时间、深度、分页 | 关系和节点、交易状态、证据引用、实际展开范围 |
| query_metrics | 指标 ID、公司/证券 ID、财务/交易日期、口径、采样 | 观测序列、可比性边界、数据卡引用 |
| read_metric_card | 记录 ID、固定版本、截止日 | 数值、公式版本、操作数、来源和缺项原因 |
| read_evidence_batch | 有界引用列表、固定版本、上下文要求 | 每项原文/定位/读取状态、续读引用 |
| read_coverage | 公司/指标/资料范围、截止日 | 核查范围、处理状态、真实资料缺口与执行问题 |

指标目录可作为 query_metrics 的 catalog 模式提供。具名能力分清纯本地读取与可能触发 embedding/rerank 的执行：search_evidence 具有潜在付费副作用，不因叫“查询”就允许透明重试。各操作必须有批量/返回大小/执行时间上限，额度由合同与配置明确。

七类能力不等于七个独立微服务；Python 内部工具可直接调用共享应用层，不要求绕 HTTP。外部 Java 接口与内部工具应消费同一语义合同。

## 3. 请求和响应合同

请求共同字段建议：

- contract_version、request_id、trace_id；request_id 用于关联，不自动等于幂等键。
- 可信服务身份及受验证的用户/项目授权上下文；用户填写的 scope 只是请求范围，实际范围由服务端与授权范围求交集。
- scope：project_id、entity_ids、security_ids、source_ids/document_ids 等按操作适用；公共资料和项目私有资料范围明确。
- research_as_of：研究时点；财务期间、行情日期范围另外传递，不混入截止日。
- snapshot_ref：不可变资料版本引用；需要检索时关联 index_version 和 retrieval_policy_version。首次选择 latest 后返回解析出的固定版本，同次研究后续请求继续使用固定版本。
- cursor/limit、deadline、必要的执行模式；付费操作额外关联 operation_id / idempotency_key 与已有预算授权引用。

复用现有 ResearchRunScope 的 research_as_of、data_snapshot_id 和 run_scope_digest，映射 snapshot_ref，不另造一套研究身份。以上字段按操作适用，可由受验证的服务端上下文或 manifest 绑定，不要求纯数据卡读取携带无关向量版本。旧请求模型已有 extra=forbid，新增字段须通过适配层或版本化合同接入。

缺失/空 scope 必须有明确语义，不能意外扩大权限。研究开始选版后，搜索、分页、卡片、原文及前端打开旧研究引用均贯穿固定版本；旧版不可用明确报错，不静默回退 latest。现有 HTTP 部分原文/关系入口仍使用 9999-12-31，统一快照传入/确认尚待实现，不能以当前同部署版本冒充已完成历史快照合同。

响应共同字段建议：

- contract_version、request_id、trace_id、实际采用的数据/索引/策略版本。
- items 及稳定 entity/edge/observation/source/chunk ID；保留旧父引用映射与新版回读引用。
- status、warnings、next_cursor、truncated、实际查询/展开范围；未知 total 不填 0。
- item 级 available_at / published_at、期间/观察日、单位/币种、实际/计划/匿名/待核等适用状态。
- evidence_refs：来源、chunk/父定位、引文范围与绑定级别；检索相关性分数不代表事实可信度。
- execution_receipt / usage_ref（付费时），不得返回模型凭证或宿主路径。

新跨语言合同继承现有 NumericFactProjection 的 value_decimal 字符串设计（Java BigDecimal），另有 unit/currency/scale/comparator/value_state，null 不转换成零。原值、显示精度与图表浮点投影分开。原接口若已有数字字段，以增量字段或适配层过渡，不直接破坏现有前端；字符串序列化不能修复上游已经损失的精度。

日期使用 ISO 日期；确需时分秒的可知时间使用带时区时间戳。只有日期的披露不伪造日内精度，保留其精度说明。财年、报告期间、期末时点、交易日、修订/可知日期保持独立。

分页游标绑定查询、排序、版本及授权范围，不能在翻页时悄悄换成最新库；并列排序包含稳定 ID。批量读取逐项返回状态，禁止部分失败静默变成整批成功。

## 4. 身份、授权与缓存

需要同时验证调用服务身份与实际用户授权，不能仅凭 X-Owner 等可伪造普通请求头。身份/权限的具体交换方式（透传受验证令牌、短期签名授权上下文或授权服务查询）待实现期选定，不能假定当前已具备。

Java 接管成员与资料访问策略后成为这些业务权限的唯一权威，Python 验证委托授权并执行资料/证据/快照绑定检查。迁移现有项目存储检查时接入新的权限来源，不维护两份独立变化的权限表；不能使用 local-pilot 回退代替跨服务身份。

retrieval_policy_version 可以随研究固定；authorization_policy_version 必须反映当前访问权限，不能固定旧授权绕过撤销。普通搜索在授权范围内执行；显式越权读取不可静默变成无结果，错误同时应避免泄露其他项目对象是否存在。

延续已有 owner 身份与项目 ID，现有单人本地模式不冒称多租户验收。资料权限撤销后未来读取应被阻止；固定资料快照不授予永久访问权。不能因为命中旧查询缓存或持有旧证据 ID 就跳过当前授权检查。

缓存至少区分发布版本、过滤条件、截止日、策略/模型、授权域及权限版本；授权不确定时拒绝私有数据读取，不返回空资料掩盖故障。公共只读缓存可在明确的公共范围内共享；私人数据、摘要与引用均遵守范围隔离。

## 5. 提交、付费查询与事件恢复

- Java 业务申请与 Python 原生 thread/run 通过显式映射关联。业务提交幂等与供应商付费请求账本职责不同，不能以一个接口幂等保证供应商绝对只执行一次。
- 当前提交指纹包含原始正文、方法、路径和查询字符串。Java 重试必须复用首次持久化的下游请求及幂等键，不重新解析 latest、生成执行 ID 或改变 JSON 序列化；以后若改成规范化语义指纹，须单独迁移兼容。多机入口启用前须具备并验证共享事务回执存储，当前本地回执不是多机保证。
- 相同幂等键和内容回放同一结果；同键异内容拒绝；已派发但回执未知时返回待核状态，不换新键重发，不自动释放预算占用。
- 可能付费的检索先登记 operation，并由服务端验证预算授权引用，超时后通过已有 operation 查询结果/状态；状态查询自身不触发新模型调用。request_id、业务幂等键、付费 operation_id、供应商请求 ID 分清职责。具体接口形式后续 OpenAPI 确认。
- 网关、Java HTTP 客户端和Python适配器都不能对含付费副作用的请求自动重试。纯本地只读重试也应有上限及相同版本/授权边界。
- SSE 续读保留原 thread_id/run_id/event_id。断线重连读取原运行事件，不启动新 run；事件保留窗口已过则返回明确状态并读取当前快照，不能保证无限事件重放。
- 保留实际用量、未知用量、预算占用和历史失败回执。服务间超时不等于下游没有执行，取消结果也须分别报告。

## 6. 错误、版本与迁移验收

稳定错误分类至少区分：身份/权限问题、参数或口径不适用、版本不可用/不一致、合法无结果、资料尚未处理、执行失败、付费派发结果未知。错误同时提供是否可安全重试及 operation 状态；不能只看 HTTP 码就决定付费重试。

搜索候选、已审核证据与结构化数字事实保留等级差别，统一响应外壳不改变其状态。read_coverage 说明实际核查范围和处理状态；搜索未命中不能推出未披露。

拟定验收：

1. 同一固定版本与相同授权范围，前端、Java代理与Agent取回同一事实和证据身份。
2. 多用户/项目隔离、越权ID、撤销后缓存回读被正确处理。
3. 数值、单位、期间、匿名身份及历史可知日不因跨语言序列化改变。
4. 重复提交、响应丢失、Java/Python重启不产生重复付费派发；未知状态可核对。
5. SSE断线续读保持同一运行；数据游标跨版本误用被拒绝；批量部分失败有逐项结果。

先冻结职责、身份/版本/证据/数值语义及重试边界；正式 URL、完整 OpenAPI、鉴权传输细节、提交存储迁移、SSE过期策略在对应实施切片中确定。本轮不创建新端点、不迁移业务数据、不改现有服务。

## 7. 现有实现参考

- apps/workbench/backend/api/v1/data_library.py：指标、公司网络、原文读取现有入口。
- apps/workbench/backend/authentication.py：受验证身份与本地模式边界。
- apps/workbench/backend/submission_receipts.py：提交回放、未知派发不重试。
- apps/workbench/backend/api/v1/report_sessions.py 与 conversations.py：按 Last-Event-ID 续读原生事件。
- src/sec_agent/research_foundation/project_asset_access.py：资料撤销与来源依赖检查。
- src/sec_agent/research_foundation/contracts.py：ResearchRunScope 研究身份与快照字段。
- src/sec_agent/research_foundation/data_ports.py：NumericFactProjection 精确数字投影。
- docs/engineering/service_recovery.zh-CN.md：原生运行与用量恢复边界。

上述代码只证明已有局部能力，不证明多人跨服务行为已验收。

2026-09-23 实施进展：第一阶段 A 新增可选 Spring Boot 业务服务与 Python prepare/start/receipt 适配，详见[交付范围及资格结果](../engineering/java_research_intake.zh-CN.md)。仅覆盖业务受理与原生运行关联；上文七类数据能力、完整跨库版本、多租户及 SSE 代理合同仍须分别实施和验收。
