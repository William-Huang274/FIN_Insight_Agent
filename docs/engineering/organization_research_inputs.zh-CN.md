# 组织研究输入准备与原件校验

2026-10-21 范围分离：创建体 `resource_ids` 继续表示 1–12 份重点资料，可选 `retrieval_resource_ids` 表示明确选择的检索候选范围（1–2,048 份，必须唯一且包含重点资料）。不传新字段时维持原合同、上限及 manifest 字节；不补空值或重写历史记录。新准备单的 `manifest.inputs` 保存全部候选依赖，`input_selection` 使用 `organization_input_selection.v1`，分别固定 `selected_resource_ids` 和 `retrieval_resource_ids`。Java 在原事务中对全部依赖执行相同的项目、来源、关联与版本核验；候选资料没有额外授权，撤销其中任意一份仍使整单和运行读取失败。

索引仍由服务器根据准备单的全部固定候选构建并登记，`retrieval_release_id` 必须与完整候选版本清单精确相等；只改变重点资料选择可复用同一候选索引，不能借此添加索引外来源。页面可选覆盖重点资料的已发布版本，发送其完整候选 ID 集合；详情分别显示重点资料和可检索数量，复制保留两种范围，未知响应仍重试原请求。首次大范围索引准备走显式服务端准备流程，不会在页面保存时自动索引整个团队空间。

Python 的准备校验和执行授权共用范围校验：旧单最多 12 份，新合同必须具备完整集合一致性且重点资料不超过 12；未知版本、缺项、重复或超范围均拒绝。正式来源 MCP 的 `organization_source.input_role` 标明 `selected` 或 `retrieval_candidate`，原件目录保留 `input_selection`，不只在页面区分。检索候选进入原授权路径，不默认读宿主公共资料，也不把候选视为已读依据。

仅创建准备单的 POST 请求体上限由 64 KiB 调整为 256 KiB，以容纳 2,048 个 UUID 和问题；BFF 与 Java 使用同一路由边界，其他接口及原生内部命令上限不变。2,048 是有界合同上限，不是已验证的并发或吞吐能力。无数据库迁移：已有依赖表保存所有候选，manifest 新字段仅对显式启用的准备单追加。

启用新范围需同步使用本版 Java、BFF、前端及包含新授权校验器的 Agent Server 镜像。旧 Python 校验器仍拒绝超过 12 项的授权响应，不能只上线 Java／页面便宣布原生研究已可用。本批真实服务验收使用正式宿主 MCP，原生模型研究、运行镜像更新与现有部署切换另验。

本批范围验收：真实 Java/PostgreSQL 全套 33 项通过，覆盖 19 候选／2 重点资料、原请求幂等、不同选择冲突、重点资料超限、候选缺失／重复／未授权、2048 候选请求到达权限校验及 2049 项拒绝、撤销非重点候选后整单和运行授权拒绝。Python 159 项不同用例通过（158 项组合加 1 项新增网关边界；末轮 12 项定向与组合重叠，不累计）；页面 14 项通过，含 19 候选／1 重点资料的保存和复制、响应未知重放、桌面与移动端。TypeScript、生产构建、活跃基线及秘密扫描通过；构建保留已有 chunk 大小与第三方注释提示。

独立真实 BFF/Java/PostgreSQL/正式宿主 MCP 首轮以 46 条／2,798 原块通过，随后 `s2-unified-retrieval-scope-r3` 将原 79 条异构来源放入**同一准备单、同一索引**，重点资料为 2 条，候选为 79 条／11,974 原块。无 document_id 的搜索及缓存、逐源检索和末块回读、271 个完整节点／条目（47 个分页）、原角色标记、重复保存和旧准备单不变通过；撤销一份非重点候选后缓存搜索及回读拒绝。该 cohort 内的统一检索已接通，不能外推为全部 1,742 条日期合格来源已真实发布或全面召回通过。467.35 秒是包括保存、发布、核验和回读的整轮时间，不能作为查询延迟。使用资格登录与已有成功查询向量，无 Agent 研究、无新增提供方调用、无部署切换。

中间 r2 失败保留：合并验收输入时 SEC 包仍固定旧 33 条目录摘要，保存服务使用新 79 条目录，严格对象比较拒绝。用维护导出工具按统一目录重新生成 SEC 包后 r3 通过；没有忽略摘要字段、修改原节点或放宽一致性断言。

2026-10-20 增补：准备单支持可选 `retrieval_release_id`，页面仅展示当前可读且资料集合匹配的已发布索引。Java 再核对完整输入版本，冻结 `manifest.retrieval_index`；更换所选资料时清除页面旧选择，复制准备单保留匹配的发布选择。旧记录不补空值、不改摘要。登记、新查询向量及真实服务验收见[组织并发与检索质量验收](organization_capacity_and_retrieval_qualification.zh-CN.md)。下文保留最初输入准备阶段的说明；后续启动/接续见对应文档。

2026-10-13。接续[项目关联空间资料](project_resource_links.zh-CN.md)，完成受控研究的第一小包：组织项目内保存问题和固定资料版本，并显式校验当前权限及 Python 原件。它是业务输入准备单，不是原生研究草稿；不创建 thread/run，不启动 Agent，`research_enabled=false` 保持。产品范围见[分阶段交付](../product/java_research_intake.zh-CN.md)。

## 用户流程

进入组织项目的“研究”页，项目管理员或研究成员填写标题、研究问题、研究截止日期，选择 1–12 个当前可读的已关联团队发布资源，保存输入准备单。支持文件、知识库选取与数据库固定快照；没有资料时先去项目“资料”关联，不隐式改为搜索整个知识库或实时数据库。默认页面不显示项目 ID。

保存后可查看固定版本、来源资源类型与摘要，点击“重新校验权限与原件”。成功只表示本次请求完成了当前授权和存储核验，不是未来启动许可；刷新不会自动校验或发起运行。研究截止日期目前记录用户意图，不代表已验证所选数据在当日可知，实际金融时点语义仍须由后续研究入口校验。

准备单归项目管理，创建者离开后记录仍保留。有项目阅读权限且当前能读取**全部**所选资料的人才能看准备单。只读成员可看，但不能创建或校验。归档项目保留阅读，不允许创建或校验。任一依赖失效会隐藏整张准备单，包括标题、问题、版本清单和目录条目，避免这些文字间接透露受限内容；不显示带标题的锁定占位。

记录不可原地改版；另一组问题或资料选择需要一份新的明确提交。发布新版本不会替换原准备单的固定输入。取消项目关联、撤销发布、退出项目/组织或失去任一来源空间权限都会影响后续访问；恢复仍然有效的原关联与源权限后，可回读原版本，不能据此复活被撤销的发布。

### 从原单修正问题或截止日期

研究成员可在详情中选择“复制为新准备单”。页面先重新读取原单，确认当前仍可访问且清单摘要一致，再预填标题、问题、截止日期和原资料选择。复制不提交、不准备执行、不创建运行；用户修改并明确保存后，按现有创建合同生成新的 ID。原单、原执行记录和输入清单保持不变。

复制沿用原单的已发布资源 ID；发布资源绑定固定版本，不按文件名或“最新版本”重新选择。复制来源的已选资料单独列出并支持移除，即使资料不在当前分页中也可看见和调整。需要新资料版本时，用户应先发布、关联并明确选择新资源。点击“新建准备单”则打开空白表单。

复制前的读取不授予未来保存许可；保存继续由 Java 在事务内复核角色、项目、关联和全部来源权限。读取失败清除原单与复制内容，切页后的晚到响应不能覆盖新视图。有未核对的保存请求时禁止复制覆盖它；先核对原单或处理本地待核对内容。复制后的保存仍使用既有 UUID/固定请求体恢复协议，响应未知后刷新不自动重发。

这只是预填新单，不增加持久化父子关系、审批或修订链。业务 API、数据库 schema 和 Agent runtime 均沿用原合同。指标卡的可获知日限制见[指标卡发布与研究输入](metric_card_publication.zh-CN.md)；原单因截止日不合适而无法校验时，刷新读取后可复制并修正日期，不需要改写原单或绕过日期检查。

复制流程的浏览器回归在 `e2e/organization-research-inputs.spec.ts`，使用 `playwright.public.config.ts`：覆盖桌面/移动端、复制后响应未知的原样重试、撤权、晚到响应、跨页选择及已有待核对请求。真实旧卡验收沿用 `tests/integration/test_metric_card_browser_stack.py` 的显式隔离开关与数据路径：先保存过早截止日并确认 409，再从页面复制修正并确认 200；比较原单完整回读与两单固定输入，并查询 PostgreSQL 确认恰好两单、两次保存审计。此测试不调用模型，不把旧卡内容当成金融质量已通过。

浏览器提交前在按用户/项目隔离的会话存储中保留原内容及 UUID。响应丢失后不自动重发，用户可核对原单或明确重试原内容；同一提交不增加第二张记录。核对成功会清除本地待核对状态。不能确定是否保存时，“清除本地待核对内容”仅经确认清除本地记录，服务器原记录保留，不能把它理解为撤销提交。

## 权威、持久化与并发

Java 是组织项目、来源权限和准备单的唯一业务权威；Python 保留已发布的组织原件，不复制项目成员名单。Flyway V5 新增 `organization_research_draft`、`organization_research_input`，保留 V1–V4 迁移和历史个人项目。

准备单记录创建者、原 HTTP 请求摘要、标题、问题、截止日期、不可变 manifest 文本及 SHA-256。manifest 合同为 `organization_research_inputs.v1`，包括项目/组织/准备单身份、截止日期、可见性规则以及各项 resource/space ID、资源 revision、标题、类型、完整 AssetRef。每项 AssetRef 保留版本和原件摘要；完整来源/财务快照仍在 Python 原发布副本中，不在 Java 重写。manifest 摘要覆盖输入清单，不宣称覆盖问题正文；原请求摘要另行覆盖完整创建请求。

创建在同一 PostgreSQL 事务内先锁组织和项目，再按排序锁来源空间与资源，复核角色、归档、同组织团队来源、当前源权限和有效关联后保存清单及一次审计。事务内不调用 Python。相同 ID、创建者、项目及原请求字节摘要重放原记录，仍核验当前权限；同 ID 不同提交返回 409。多次并发同请求只保存一份。重放不会更新版本、恢复权限或恢复归档项目。

列表及详情的 SQL 同时要求项目访问有效，且不存在任一无权、撤销、版本/绑定改变或失去关联的输入；权限过滤在分页之前，每页 30。没有授权缓存。角色降为 viewer 后可以按阅读规则查看，不能取得校验用内部授权。

## 原件校验与接口

| 接口 | 用途 |
| --- | --- |
| GET/POST BFF `/api/v1/business/workspaces/projects/{project}/research-drafts` | 当前可见列表 / 创建不可变准备单；创建体 `id,title,question,research_as_of,resource_ids` |
| GET 同前缀 `/projects/{project}/research-drafts/{draft}` | 按当前权限读取原单；返回 manifest，不暴露内部 binding |
| POST BFF `/api/v1/asset-workspace/organization-projects/{project}/research-drafts/{draft}/verify` | 显式核验保存的原件，返回 `inputs_verified,checked_at,manifest_digest,inputs,execution_enabled:false`，无正文和运行 ID |
| POST Java `/v1/workspaces/projects/{project}/research-drafts/{draft}/material-access` | 仅 BFF 签名调用；重新验证研究角色及全部依赖，返回服务端固定 binding，公开代理拒绝访问 |

校验由 BFF 当前登录身份发起，不能提交 owner 或存储地址替换准备单。Python 先从 Java 获得当前授权，核对项目、组织、准备单、所有资料集合及精确 AssetRef；调用现有组织存储 resolve，检查原件字节 SHA-256、版本和已捕获来源快照；I/O 完成后再次向 Java 核验全部权限，要求两次授权内容一致才返回成功。它是两次当前权限查询，不是跨库事务，也不是可长期使用的 bearer capability。

授权中间撤销则拒绝返回通过；第二次授权查询之后发生的撤权不能远程抹掉已返回信息，下一请求重新核验。原件缺失/摘要不符返回 409，记录保留，不切换最新版本；授权合同不一致返回 502，不能当成有效空结果。没有后台自动重试，也不创建新的费用请求。响应沿用 no-store。页面校验失败清除已加载详情和列表；切页后的晚到结果不能恢复旧视图。

## 静态验收

1. 小李有研究角色及两份资料的源权限：保存、重复提交、重启回读同一 manifest；业务研究任务及原生运行数量不增加。
2. 撤销其中一份源权限：整单列表及直接链接不可见；管理员仍按自身权限读取。恢复源权限不改变原版本；降为 viewer 后只读。
3. 取消关联或撤销发布：原准备单新读取失败，但历史准备单/依赖仍保留；不能凭早先成功校验继续访问。
4. 五个同 ID 同内容并发请求只新增一行；同 ID 不同内容、重复输入及未关联输入被拒绝；归档后保存和校验被拒绝。
5. 原件损坏或缺失：明确拒绝，恢复后原版本可再次核验。存储 I/O 后撤权或授权变化：不返回成功。
6. 浏览器未知提交后刷新不新增写入；核对原单或显式原内容重试；校验失败清掉内容，桌面/移动不横向溢出。

```powershell
# apps/business-service；JDK21 + Docker，临时 PostgreSQL
./mvnw.cmd verify
# 仓库根；离线身份替身、实际 SQLite
uv run --no-sync python -m pytest -q tests/test_organization_research_inputs.py tests/test_resource_spaces.py tests/test_java_research_intake.py tests/test_project_workspace.py
# 实际 BFF 签名 / Spring / PostgreSQL / SQLite / Java 重启；显式 JAR 开关
$env:FINSIGHT_INTAKE_TEST_JAR=(Resolve-Path apps/business-service/target/business-service-0.1.0.jar).Path
uv run --no-sync python -m pytest -q tests/integration/test_resource_spaces_stack.py
# apps/workbench/frontend；静态 API 浏览器测试
npm run typecheck
npm run build
npx playwright test --config playwright.recovery.config.ts
```

身份来自合成 fixture；真实签名/存储链路与浏览器模拟 API 各自验证，不合称完整浏览器生产全链。没有模型、embedding 或 rerank 请求，未验证金融研究质量、真实 OIDC 供应商或生产容量。

本地结果：Java 全套19项通过，包含两项新准备单用例；Python相关27项通过；真实签名/数据库/存储与Java重启1项通过（22.06秒）。浏览器39项通过；随后补校验失败清除资料选项、角色说明后定向9项通过，修正表单样式后5项通过（均为原39项中的重复复验，不累加）。TypeScript、生产构建、活跃基线、944文件密钥扫描及diff检查通过，构建保留原有大chunk/第三方注释提示。已检查1440/390保存表单和详情截图。

补充迁移复验有一项环境阻塞：19项首轮已实际应用V5并跑通新表读写；之后在既有V2升级案例中追加“V5历史记录存在、准备单表初始为空”两条断言，定向复验停在Docker连接，独立只读docker ps也无响应。等待约4分钟后只停止本次测试JVM，Maven退出1、执行0项；这次不能记为通过，两条新增断言需Docker恢复后补验。未重启引擎或操作现有容器。日志中的fork terminated由主动终止等待造成，不据此判定业务JVM崩溃。

2026-10-13 补验完成：Docker 恢复后，在同一代码版本上重新运行 `upgrading_v2_keeps_existing_organization_space_records`、`organization_preparation_freezes_all_inputs_and_hides_entire_draft_after_revocation` 和 `preparation_replay_concurrency_archive_and_invalid_input_fail_without_execution`，3 项通过、0 失败、0 错误、0 跳过，测试用时 20.75 秒。V2 升级到 V5 的新增历史记录和初始空表断言已执行通过，关闭上述环境阻塞。3 项是原有用例的定向复验，不与首轮 19 项累加；原先执行 0 项的失败尝试仍保留。此次复验使用独立临时 PostgreSQL，不代表组织研究运行、生产部署或金融质量验收完成。

## 后续和部署

3B 第一片已增加[组织执行绑定与受控资料 MCP](organization_execution_access.zh-CN.md)：固定提交者/输入、独立运行凭证、每次读取前后核权。本准备页仍不创建原生运行，后续边界如下。

原生 `ReportSessionService.owned_thread` 仍按个人 owner 限制，旧研究准备也以个人项目为前提；直接把组织 ID 填入旧入口会破坏职责边界。因此下一包须将组织准备单绑定受控执行身份和输入范围，并在启动、每次工具读取、接续、事件与报告读取处执行一致授权，再开放团队运行。报告正文、引用、导出和缓存不能仅保护原文件。审批和交接在这之后。

本包不接原生队列，不重复把上一包的队列故障通过当成本包组织执行通过。没有迁移旧个人资料，没有切换现运行服务。协调部署时先备份业务 PG 与 Python 组织存储，再应用 V5、更新 BFF/前端；代码回退可关闭新页面，但保留 V5 记录，不运行删除准备单的 down migration。
