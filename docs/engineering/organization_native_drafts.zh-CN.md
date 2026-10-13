# 组织研究原生草稿受理

承接[执行授权绑定](organization_execution_access.zh-CN.md)，准备接口把已核验的组织研究准备单保存为真正的 Agent Server thread。**准备只创建草稿，不创建 run；浏览器团队启动仍关闭。** 后续内部首次运行见[启动与准入](organization_native_start.zh-CN.md)，没有新增浏览器按钮或通用代理路径。

## 持久状态与调用边界

Flyway V7 新增 `organization_native_preparation`，每个执行绑定只有一条准备命令，保存原始请求摘要、唯一操作 UUID、发给 Python 的固定 JSON 字节、状态及回执。Java 是项目与来源权限的唯一权威，只有绑定的原提交者可以准备或核对；管理员不能借此冒用他人的执行绑定。

以下 Java 路径均以 `/v1/workspaces/projects/{project}/execution-bindings/{id}` 为前缀：

| 路径与方法 | 行为 |
| --- | --- |
| `POST /prepare` | 请求 `execution`；事务内固定操作与配置，CAS 领取一次派发，事务外调用 BFF；返回持久状态 |
| `GET /preparation` | 在当前全部输入授权后读取准备状态 |
| `GET /preparation-access` | BFF 专用：返回当前授权、固定准备请求及其原字节摘要、操作 ID、问题与输入 manifest |
| `POST /reconcile` | 仅对派发中或未知状态，查询原 thread 并核对身份与配置；不重新创建 |

首次命令为 `ready`，成功领取后为 `dispatching`（对外显示 `unknown`）。匹配的原生回执才进入 `received`；明确的提交前拒绝为 `rejected`。超时、5xx、身份不匹配或“已派发但未知”保持 `unknown`。同绑定换请求返回 409，重放原请求不重发。晚到响应不能覆盖已确认回执。业务事务不跨 HTTP 保持数据库锁。

Python 的 `/api/v1/internal-research/organization/prepare` 只接受 Java 的签名委托，绑定 method、原始 path/query、请求体与操作 ID。当前授权检查发生在 SQLite 提交回执重放**之前**。真正创建前校验发布原件、再次核权；创建后核对 metadata 并再次核权。保存后权限变化或核对失败返回未知，不能把它解释为从未创建。

## 原生身份与冻结配置

使用官方 SDK 的一次 `threads.create(thread_id=execution_id, metadata=..., if_exists='raise')` 原子保存身份与配置；不采用“先建空 thread、再 patch metadata”。已有相同 UUID 不覆盖，不自动生成另一个 UUID。

- `surface=organization_research_workbench`，`owner_id=organization:<organization_id>`，与个人研究入口隔离。
- 记录组织、项目、准备单、执行绑定、manifest 摘要、操作 ID、固定请求摘要。
- 保存原问题、研究截止日、执行选项、当时的完整 Studio 配置及配置摘要；后续默认配置变化不会改写旧草稿。
- 不写入个人项目分配，不复制个人记忆、项目附件或个人研究上下文。后续组织工厂使用专属底稿作用域并重新核验权限。
- `native_execution_enabled=false` 保留为草稿标记，不是启动权限来源。默认原生工厂仍拒绝组织运行；显式启用后也必须核对独立的 Java 启动命令与唯一 run。Agent Server 仍必须保持内部可达，不能把 native API 暴露给浏览器。

只读核对通过 `/api/v1/internal-research/organization/executions/{id}/state?project_id=...` 获取原 thread，检查全部身份、固定请求、配置摘要与配置 schema，同时要求原生 run 列表为空。错误身份、已存在运行、被篡改配置一律拒绝；不 patch、不删除、不修复现场。查不到 thread 也不能证明未派发，不释放原操作用于重试。

## 验证与证据边界

Java 测试使用真实 PostgreSQL，覆盖并发领取一次、换配置冲突、当前权限先于回执、响应丢失、原操作核对和 V2 到 V7 升级。Python 测试覆盖真实 BFF 签名/SQLite 回执/组织原件、SDK 故障注入、配置与身份篡改、重启重放、撤权、旧个人入口拒绝，以及实际研究图工厂的早期拦截。

可选集成测试 `tests/integration/test_organization_native_stack.py` 使用隔离的 Spring Boot、BFF、PostgreSQL、Redis 和真实 Agent Server。身份与来源是静态案例，响应丢失注入发生在官方 SDK 已完成真实保存之后。最初草稿阶段要求两次创建、零 run；后续扩展为准备后显式创建两次首次运行，重启后只读核对同一 run，再撤权验证，始终零模型请求。原生容器仅注册确定性测试图，**产品原生工厂的组织读取证据来自独立 Python 静态测试**，不能称为完整生产图容器验收。

复验需显式设置 `FIN_INTAKE_NATIVE_QUALIFICATION=1`、`FIN_ORGANIZATION_NATIVE_QUALIFICATION=1`、新的 `FIN_NATIVE_ATTEMPT_DIR`、本地已资格确认的 `FIN_PROBE_IMAGE`、核实无冲突的 `FIN_PROBE_SUBNET`、`FINSIGHT_INTAKE_TEST_JAR`，并使用已有开发许可（可通过 `FIN_NATIVE_LICENSE_ENV` 指向本地环境文件）。路径和凭证不入 Git。测试不拉镜像、不构建镜像，不使用现部署端口和资料；结束停止自己的服务并保留状态和日志。普通 pytest 不会自动运行这个有环境依赖的测试。

## 仍未交付

组织草稿的存在不代表团队 Agent 产品流程完整。[组织执行适配](organization_execution_access.zh-CN.md)第八、九片接入统一阶段工厂与预研究，第十片接入内部首次启动命令与原生工厂构造，详见[启动与准入](organization_native_start.zh-CN.md)。接续、事件、报告、引用和导出的产品授权仍待验收；网络部署、密钥轮换、真实 OIDC、用户静态验收及金融质量各自需要证据。本片的截止日期只记录研究意图，不提供历史可知日资格证明。
