# 组织预研究到正式研究的显式接续

本批增加一个明确动作：在首次预研究成功结束后，沿用原问题、固定资料版本、研究截止时间和执行配置，创建一次正式研究运行。预研究原稿与首次运行保留在同一 thread 的历史中。正式研究仍自行取证与规划；不将预研究判断直接升级为已验证事实。

这不是通用的失败恢复或报告修订入口。专家补跑、用量未知的运行恢复、人工修改方案、变更模型/资料、研究交接给另一成员、报告审批均未由此命令开放。浏览器本批接入项目成果只读页面，组织启动及接续按钮仍未开放，也不自动切换已有部署。

## 权威记录与一次派发

Flyway V9 `organization_native_continuation` 与首次启动记录分开保存。当前每个 execution 最多一条 `begin_research` 命令，拥有独立 operation ID、原始请求摘要、状态、原生 run ID 和回执。并发提交通过项目锁、唯一约束和 `ready -> dispatching` 条件更新确保一次派发；相同请求回读原命令，不同 checkpoint 或前序 run 返回冲突。响应丢失进入 unknown，只读核对不再派发。

Java 的内部业务接口（不能经通用浏览器代理直接访问）：

| 方法 / execution-bindings/{id} 后缀 | 作用 |
| --- | --- |
| POST `/continue` | 提交 `previous_run_id`、`checkpoint_id`、`state_digest` |
| GET `/continuation` | 回读原命令与关联运行 |
| POST `/continuation-reconcile` | 核对原生回执，不新增运行 |
| GET `/continuation-access` | 当前发起人的固定接续授权，供 BFF 使用 |

完整前缀为 `/v1/workspaces/projects/{project}`。Java 从已保存的首次启动记录读取截止时间，从原生准备记录读取冻结配置，调用者不能用这次动作替换这些字段。只有执行绑定的原发起人、且仍有研究角色及全部来源权限，才能提交；项目管理员不能凭管理角色冒充发起人。

Python 的内部 `/api/v1/internal-research/organization/continue` 要求 Java 对原始字节、路径和 operation ID 签名。中间件在回放任何缓存回执之前重新核权。BFF 要求原 thread 只有一个已成功结束的首次运行、当前 checkpoint 与命令完全一致、预研究已提交、没有已有专家结果/报告/待运行节点，且前序用量可核对、没有未知请求或部分审计。核对接续回执时要求原首次运行和唯一对应接续运行同时存在，不猜“最新的一条”。

## 原生运行中的第二道校验

Agent Server 工厂使用独立 workload 凭证访问 `/v1/runtime/organization-executions/{id}/admit-continuation`。Java 将命令绑定到唯一的新 run；首次 run、其他 run、首次启动凭证都不能替代。原生工厂随后核对 SDK Run 元数据、冻结配置、前序成功状态和 checkpoint 内容摘要，通过后才打开研究资源和模型配置。

Agent Server 会合并前序 checkpoint 的配置。接续请求显式将 `finsight_organization_start` 设为 null，防止旧启动上下文被继承；新的 `finsight_organization_continuation` 是唯一生效的命令身份。缺省清除不能代替显式清除，测试包含真实服务对此行为的验证。

研究父图的 `promote_orientation` 开关只由已准入的组织工厂设置；普通图保持禁止重启已初始化研究。接续输入仍需与固定问题和 `research_stage=full` 精确一致。首次正式报告初始化恢复为第 1 版；既有预研究原稿继续保留。权限检查、组织资料工厂、底稿隔离和模型前后检查保持适用。此次没有实现中途换资料或跨组织迁移。

## 产品读取

组织项目“成果”页通过专用组织 API 列出可读的执行记录，查看预研究概览、报告、引用快照以及四种报告导出。项目列表复用当前项目 AND 全部冻结来源权限，不用发起人身份替读。详情/引用读取失败时清空已显示内容；页面刷新与浏览不派发研究。

`GET /api/v1/organization-projects/{project}/research?offset=0` 复用准备单的权限 SQL，一次查询过滤项目成员与全部来源后分页，每页最多 30 条。无权限条目不返回标题，也不参与分页计数。每项返回 execution ID、draft ID、标题和已关联的当前 run ID。读取授权同时记录首次及接续两条已关联 run，事件路由只接受这个集合。预研究单独展示，不作为正式报告导出。完整原件扩展、事件流界面与浏览器启动/接续流程仍待集成。

## 无模型验收

- Java：真实 Spring HTTP、Flyway、PostgreSQL；并发只派发一次、回执丢失/错配核对、独立 run 准入、换 checkpoint 冲突、撤权拒绝、当前读者列表过滤。Python 对端在这层用静态桩。
- Python：固定命令与实际 SDK 请求一致，错 run/配置/checkpoint 不准入，前序未完成/未知用量不派发，撤权先于回执重放；父图用静态研究与审查产物从预研究进入首版报告。
- 原生集成：隔离 Docker 网络内真实 Agent Server、PostgreSQL、Redis、Java、BFF；仅替换 provider 与身份测试边界。先预研究，再独立接续到“研究待处理”，保留预研究原稿，重复命令不增加运行，盗用命令创建另一 run 在模型调用前拒绝。此场景主动停止于未完成研究，不声称完整金融报告验收。
- 浏览器：1440 / 390 宽度，组织项目与输入准备回归；项目成果、报告引用、导出目标、撤权清空，无个人研究详情回退，无写入或模型请求。

测试入口：`tests/test_organization_native_continuation.py`、`tests/test_research_session.py`、`tests/integration/test_organization_graph_native.py`、Java `ResearchIntakeTest`、前端 `organization-research-results.spec.ts`。原生集成环境与独立部署前提沿用 [组织首次运行](organization_native_start.zh-CN.md)。工程验收不能代替真实企业登录、多实例部署、完整协作流程和金融结论质量验收。
