# 组织首次运行：启动命令、准入与核对

承接[原生草稿](organization_native_drafts.zh-CN.md)与[组织执行授权](organization_execution_access.zh-CN.md)。本阶段实现内部首次预研究启动，以及原生宿主构造组织工厂。默认关闭，浏览器仍不能启动组织研究；接续、事件、成果、引用及导出权限尚未形成产品闭环。

## 两种授权分别验证

资料 `access` 证明原发起人目前仍有项目研究资格及全部固定输入的使用权限。新 `admit-start` 还要求 Java 已持久化并派发这一启动命令，且准备已确认、配置摘要、操作标识、固定请求摘要及本次 run 身份匹配。工作负载凭证不能提供或替换用户身份，Java 从已有执行绑定恢复发起人。

一次运行身份不加入资料 grant。否则下一次合法运行会改变底稿的来源授权摘要，破坏原件恢复。资料读取仍走原合同；阶段与模型调用前后另核对启动授权。关闭执行绑定、移除项目研究资格或撤销任一选定来源都会拒绝后续访问。授权检查不是跨服务锁或租约，不能撤回已经发生的外部调用，也不保证撤权前后本地写入回滚。

## Java 持久命令

Flyway V8 新增 `organization_native_start`。每个执行绑定只有一个首次启动命令，保存原始请求指纹、操作 UUID、派发 JSON、状态、原生 run ID 和回执。此次仅允许 `orientation`；截止时间必须带时区，其当地日期须与已固定的资料清单日期一致。阶段、准备操作和配置摘要由 Java 从已确认准备记录派生，不接受客户端自行声明。

以下路径以前缀 `/v1/workspaces/projects/{project}/execution-bindings/{id}` 调用，均属于内部业务委托范围，未加入浏览器代理白名单：

| 方法与路径 | 行为 |
| --- | --- |
| `POST /start` | 请求仅含 `research_as_of`；事务内固定命令，CAS 领取一次派发，事务外调用 BFF |
| `GET /start` | 当前权限下读取命令和已关联运行 |
| `GET /start-access` | BFF 核对固定准备、启动命令与当前全部来源权限 |
| `POST /start-reconcile` | 只读核对唯一原运行，不重新派发 |

`POST /v1/runtime/organization-executions/{id}/admit-start` 使用独立工作负载签名，绑定 method、原始路径、body 摘要及短有效期。请求包含 thread、run、操作、manifest、配置与启动请求摘要。事务内按当前项目锁重新授权，首次认领原生 run，之后只接受同一 run。原生 worker 可以先于 HTTP 回执认领，回执只能补全同一个 ID。

状态沿用 `ready → dispatching → received/rejected/unknown`。对外 `dispatching` 显示未知；响应超时或不匹配不能证明未派发。相同请求只读已有状态，不获得再次提交机会；不同内容冲突。`received` 仅表示找到相符的原生运行，不代表研究成功、金融结论正确或结果已向用户开放。

## BFF 与原生宿主

BFF 在 SQLite 回执重放前重新检查当前启动权限。实际派发前核对冻结 thread、Java 已保存的配置摘要和组织原件，构造固定问题、`research_stage=orientation` 与配置。调用官方 `runs.create` 一次，沿用原生队列和 `multitask_strategy=reject`。

官方 SDK 的 `Run` 回执不包含完整配置。本实现记录派发配置与输入的规范摘要到 run metadata；只读核对要求唯一运行及匹配的操作、摘要和 thread，不查询原生数据库、不猜最近运行，也不把 metadata 摘要当成实际执行配置证明。原生工厂在执行前使用真实 `RunnableConfig` 和 Java 命令验证配置；研究阶段输入还必须精确匹配授权问题及阶段。

原生宿主先完成 Java 准入、thread 冻结配置、原生 `runs.get` 身份、实际配置及空初始状态检查，再打开宿主设置、预算、组织原件与模型配置。它使用 `OrganizationDataFactory` 和组织底稿作用域，不进入个人 guidance/附件/记忆或公共 SQL/library。非空 checkpoint 拒绝本次首次启动命令；其他研究阶段和人工修订入口仍关闭，不能用首次命令隐式接续。

## 配置和验收边界

Java 的 `FINSIGHT_ORGANIZATION_START_ENABLED` 默认为 `false`，BFF 与原生宿主仅在值为 `1` 时启用。共同启用可设为 `1`，Spring 支持此布尔形式。还需独立的 `FINSIGHT_ORGANIZATION_RUNTIME_SECRET`、`FINSIGHT_BUSINESS_API_URL`、显式组织原件挂载 `FINSIGHT_ORGANIZATION_ASSETS_ROOT`，以及宿主设置中的 `workbench_url`。现有研究启用、宿主模型预算和密钥设置照常适用。资料授权客户端当前只允许本机 loopback Java 地址；容器到宿主 Java 的受控网络部署尚待适配，不能直接把此阶段配置当成生产部署指南。

可复现检查：

- `apps/business-service` 下运行 `./mvnw verify`：真实 PostgreSQL/Flyway，测试并发只派发一次、另一 run 拒绝、丢响应后原运行认领与核对、当前权限先于回执。
- `uv run --no-sync python -m pytest -q tests/test_organization_native_start.py tests/test_organization_native_drafts.py tests/test_organization_execution_access.py tests/test_organization_phase_factory.py`：真实 BFF 回执与签名、SDK 故障注入，以及实际原生工厂/研究父图/Lead/MCP 的静态组织原件读取、引用与预研究提交。模型为脚本替身，未请求真实 provider。
- 既有 `tests/integration/test_organization_native_stack.py` 扩展为真实 Spring/BFF/PostgreSQL/Redis/Agent Server 的准备、正常和丢响应启动、全部测试服务重启、原 run 回读与撤权验证。Python 工作负载客户端真实调用 Java 准入接口。原生容器仍运行确定性队列测试图，实际产品工厂在另一静态测试中验证，两类证据不得混称为完整生产图容器验收。

这些检查不证明金融研究质量、真实 OIDC、成员交接、审批、生产容量或企业上线完成。下一阶段优先验证原生组织图的容器部署及权限完整的产品读取，再接明确的接续命令；不能把首次启动凭证复用于下一阶段或另一 run。

2026-10-13 工程复验：167 项相关 Python 回归通过（含21项首次启动/原生工厂用例），Java 26 项真实 PostgreSQL 测试通过；五服务集成1项175.81秒通过。最终集成案例保存两份草稿、显式创建两个原生测试运行，两轮服务重启与核对未新增运行；工作负载准入拒绝另一 run 和撤权后的原 run。先前失败保留为本地证据：一次许可网络超时发生在业务创建前；一次暴露 SDK 回执无配置的错误假设，已在实现及替身中修正；一次断言忽略 worker 可在未知回执状态下补登记 run ID，按实际状态语义修正。全部使用静态模型或确定性队列图，零真实模型、embedding、rerank请求，现有部署未更换。
