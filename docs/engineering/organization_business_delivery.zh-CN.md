# 组织研究：真实服务与静态报告的业务闭环验收

本验收针对项目使用者从准备研究到读取成果的操作，不评估金融结论。浏览器访问真实 BFF、Spring Boot、PostgreSQL、Redis 和 Agent Server；不拦截业务 API。身份验证和模型回复使用明确的测试替身，正式研究的下游成文使用标记为合成内容的报告生产器。既有生产研究图没有为此增加捷径。

## 验收范围与替身位置

`tests/integration/test_organization_delivery_stack.py` 复用现有隔离服务工具，注册 `organization_delivery_graph.py`。首次预研究仍运行真实组织准入、父图、Lead 与 MCP 资料导航，只替换模型回复。明确接续时，组织原生工厂仍检查 Java 授权、前序运行、checkpoint、输入与冻结配置，并执行受保护的研究阶段；随后测试图将真实预研究读到的固定原件片段保存为静态报告。这个步骤替代专家、复核和成文，不证明这些生产阶段已经全链通过。

报告保留原 passage、资料身份和 execution 关联，正文明确注明工程夹具、无金融结论。不存在通过修改数据库、伪造业务 API 响应或手工塞入原生 checkpoint 来跳过准备和运行的步骤。运行审计明确记录 provider 未调用；生产环境不得注册这个测试图。

`apps/workbench/frontend/e2e/organization-live-delivery.mjs` 使用已构建的实际前端，连接隔离 BFF。它只通过浏览器 UI 创建准备单、准备执行、启动、预览和确认接续；固定的两种测试身份由资格环境提供，未验证真实企业 SSO。

## 同一案例的检查

| 场景 | 必须满足 |
| --- | --- |
| 正常路径 | 浏览器保存问题、截止日和项目资料；准备后明确启动；刷新恢复预研究；取消一次接续预览不派发，再确认接续 |
| 报告交付 | 同一执行出现静态报告；浏览器读取同 checkpoint 的引用；实际下载 Markdown、PDF、Word、PowerPoint，检查文件内容/签名 |
| 服务重启 | 仅重启该案例自己的 BFF、Java、原生服务、PostgreSQL、Redis；报告和 checkpoint 不变；只读成员读取和下载不新增运行 |
| 权限分离 | 只有项目成员资格仍不能读来源；补齐空间读取权限后可以阅读；只读成员不能启动，也不能走个人研究路径 |
| 响应丢失 | 在真实 SDK 已持久化 thread/run 后注入响应丢失；准备、首次启动、接续分别通过浏览器刷新和明确核对恢复，不自动派发 |
| 读取竞态 | 运行登记改变授权信息时，读取可以返回 409；显式刷新恢复一致快照，不能为消除 409 再提交启动命令 |
| 撤权 | 源资料撤权后，正文、报告、引用、事件、四格式导出及历史 checkpoint 导出都拒绝；浏览器清空内容 |

测试保留创建观察记录，最终要求两个 thread、四个 run。重启、重复核对和下载都不能改变这个数量。事件流可用当前读者接口只读复核；已有浏览器组件展示公开事件，并在断流后重新核权，不自动重发命令。

## 复现条件

1. 使用独立 worktree，安装仓库 qualification/workbench 依赖。构建 `apps/business-service` 的 Java 21 jar 和前端 `npm run build`，安装 Playwright Chromium。
2. Docker 必须健康，拥有已验证的本地原生镜像及 compose 指定的 PostgreSQL/Redis 镜像。禁止为验收停止共享服务。原生镜像必须精确到 ID，包版本门槛由既有 `Stack` 检查。
3. 提供新的仓库外输出目录和经过检查、不与已有网络重叠的 subnet。测试分配独立主机端口和随机 compose project，不使用现有 18165/18765。
4. 提供既有 Agent Server 开发许可证；它不用于模型调用。工具会移除子进程中的模型密钥，只给需要的容器传开发许可证。

设置以下环境变量后执行测试。路径使用当前环境的实际值，不能照抄其他机器的目录。

| 变量 | 值或含义 |
| --- | --- |
| `FIN_INTAKE_NATIVE_QUALIFICATION` | `1` |
| `FIN_ORGANIZATION_GRAPH_QUALIFICATION` | `1` |
| `FIN_ORGANIZATION_DELIVERY_QUALIFICATION` | `1` |
| `FIN_NATIVE_ATTEMPT_DIR` | 不存在的新输出目录，每次尝试独立保留 |
| `FIN_NATIVE_LICENSE_ENV` | 含既有开发许可证的本地环境文件；不得提交 Git |
| `FINSIGHT_INTAKE_TEST_JAR` | 当前源码构建的可执行 jar |
| `FIN_PROBE_IMAGE` | 已有本地镜像的精确 `sha256:...` ID |
| `FIN_PROBE_SUBNET` | 已检查的独立 subnet |
| `FINSIGHT_TEST_DOCKER` / `FINSIGHT_TEST_JAVA` / `FINSIGHT_TEST_NODE` | 可选，工具不在 PATH 时指定可执行文件 |

```bash
python -m pytest -q tests/integration/test_organization_delivery_stack.py
python -m pytest -q tests/test_organization_research_reads.py tests/test_organization_research_commands.py
```

输出包含服务与源码指纹、浏览器请求记录、真实导出文件、截图、经过脱敏的 compose 日志和 `business-delivery-result.json`。测试结束仅停止自己的服务，保留数据库卷和输出；再次运行使用新目录和新网络。失败也保留记录，不覆盖上一次输出。

## 2026-10-19 结果及后续

第二轮真实服务验收通过，用时 152 秒；两个 thread、四个 run、八次脚本回复、零 provider 调用，浏览器业务 API 拦截数为零。重启后的只读浏览器回读、响应丢失恢复和撤权拒绝全部通过。另一次只读事件检查读回三条 custom 事件，包含静态报告保存事件。相关后端回归 32 项通过。

首轮正常路径及服务重启通过，在响应丢失路径遇到运行登记期间的 409。失败原因是浏览器验收脚本假定操作区立即存在，没有执行页面要求的重新读取；补充显式刷新并增加后端一致性回归后复验通过。未放松权限检查，未增加启动重试。首轮数据单独保留。

第一阶段的**静态业务接入闭环**已有真实服务证据，可以继续数据库专项验证。仍未声称真实模型完整成文、真实 SSO、生产容量、报告审批或整合隔壁最新研究运行时已经通过。后续整合研究分支时，必须重新验证工厂、冻结配置和准入边界；不能把本案例的静态报告当作研究质量证明。
