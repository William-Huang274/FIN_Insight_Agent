# Java 受理到原生持久队列的生命周期验收

2026-10-13。在[共同版本](java_python_integration.zh-CN.md)之上，使用真实 Python BFF、Spring Boot、业务 PostgreSQL、Agent Server、原生 PostgreSQL 和 Redis。研究图改用确定性 fixture，未运行生产研究规划、模型或检索工具。业务库与原生库为本次临时集群中的两个独立数据库，不连接现有服务数据库。

## 需要证明的行为

本次最终复验通过：1 个真实服务集成用例包含下列行为，证据矩阵分为受理与接续、全部服务重启、队列与停止、原生进程强杀恢复四组，耗时 174.02 秒；相关离线回归 79 项通过。这两个数字分别表示集成用例和离线用例数量，不将矩阵行重复累计为测试数。首轮真实服务验收因晚到停止返回 502 失败，保留失败记录，修复后在全新隔离项目完整复验通过。

强杀场景中，恢复沿用原 run，已提交的 prepare 执行 1 次，未完成的 work 执行 2 次；之后经 BFF 显式接续生成新 run 并回读报告。全部服务重启后，原报告 checkpoint 与业务启动回执保持一致。这里使用确定性研究图，不证明生产研究算法或金融结论正确。

| 场景 | 检查内容 |
| --- | --- |
| 准备、重复提交与启动 | 同一业务任务、thread、启动 run 不因重复请求增加；准备不启动 graph |
| 人工交接与明确接续 | 原生 checkpoint 保留，`continuation_scope` 到达执行节点；明确继续产生新 run 并记录来源 run |
| 未知用量 | 注入合成未知账本时接续返回 409，无新 run；恢复原字节后才执行本次合成继续 |
| 报告回读与服务重启 | BFF、Java、原生 API、PG、Redis 在自己的隔离项目中重启，原 task/run/checkpoint/report 身份不变 |
| 队列与停止 | 单 worker 的第二项保持 pending；停止第一项后第二项执行；已完成的准备节点保留 |
| 完成后的晚到停止 | 不将已结束 run 的停止冲突伪装成上游服务故障；原结果和用量保持 |
| 原生进程强杀 | SIGKILL 后由原生机制接回同一个 run，已提交的 prepare 不重做；允许未完成节点重新执行 |

普通节点被取消后，不一定处于合法的研究交接点。当前 BFF `continue-remaining` 不支持任意取消节点直接接续，本测试要求它返回 409 且不创建新运行；没有绕过此规则从原生接口人工推进后声称产品入口已支持。

## 晚到停止的实际兼容修复

锁定的 Agent Server 0.13.3 对“run 不存在或已不可取消”均可能返回 404。旧 BFF 将这个响应转换成 502，导致已完成研究显示“运行服务暂不可用”。首轮真实链路复现了此问题。

现在仅在 cancel 返回 404/409 后，BFF 只读查询同一个已授权 thread 下的同一个 run：

- `success/error/interrupted/timeout`：200，`cancel_requested=false`，返回 `run_status`，保留实际终态。
- 查询也为 404：返回“此研究下不存在该运行”。
- 仍是 pending/running 等未确认状态：409，提示刷新核对。
- 其他上游错误或查询超时：保留现有未知错误处理，不能用“已结束”吞掉连接故障。

一次只发一个 cancel，不自动重试。终态确认不等于供应商费用已确认；响应不会把未知用量写成零。前端收到成功响应后继续按现有方式回读会话状态。

## 零模型边界与证据

`tests/integration/fixtures/intake_native_graph.py` 仅包含固定步骤、文件证据、等待门和原生 interrupt，不导入 FIN 研究图或模型适配器。离线图测试在建立 Windows 事件循环之后禁止 socket connect，验证整段 fixture 可在无网络情况下完成。

运行时复用本机现有镜像，不 build/pull。入口拒绝镜像中非空的 API_KEY/TOKEN/SECRET 环境；启动后检查容器仅注册该确定性图，敏感环境只有现有 LangSmith 开发许可，模型供应商密钥为空。许可校验仍可能联网，这不是模型调用。保留实际图注册、环境变量**名称和是否非空**、挂载目标、镜像 ID、依赖版本及源码哈希，不输出凭据。

fixture 写入 `qualification_no_provider` 明确无供应商派发的合成审计标记，没有虚构 token 数或账单。未知用量测试的注入由 finally 恢复原字节。这证明 BFF 门槛处理，不证明真实模型的失败计费恢复。`provider_calls=0` 不能脱离上述结构、离线网络拒绝与容器检查单独解释为网络审计。

## 复现与停止

先按[Java 服务说明](../../apps/business-service/README.md)构建 JAR。要求 JDK 21、Docker、仓库锁定 Python 依赖；现有 native 镜像须为 `langgraph-api=0.13.3 / langgraph=1.2.11 / psycopg=3.3.4`。检查宿主路由和 Docker 子网无冲突，选择全新 attempt 目录。

```powershell
# 仓库根目录；先做离线检查，真实服务用例默认跳过
uv run --no-sync python -m pytest -q tests/test_intake_native_fixture.py tests/test_research_session_bff.py

$env:FIN_INTAKE_NATIVE_QUALIFICATION='1'
$env:FIN_NATIVE_ATTEMPT_DIR='<新的私有验收目录>'
$env:FIN_PROBE_SUBNET='<已经核对空闲的私有CIDR>'
$env:FIN_PROBE_IMAGE='<已有依赖镜像的sha256:完整ID>'
$env:FINSIGHT_INTAKE_TEST_JAR=(Resolve-Path apps/business-service/target/business-service-0.1.0.jar).Path
# docker/java默认从PATH解析，可显式设置FINSIGHT_TEST_DOCKER/FINSIGHT_TEST_JAVA。
# 开发许可从LANGSMITH_API_KEY或本地.env读取；也可FIN_NATIVE_LICENSE_ENV指定已有私有文件。
uv run --no-sync python -m pytest -q tests/integration/test_java_intake_native.py
```

测试使用独立随机 compose 项目、随机回环端口，禁止使用现有服务端口18165/18765；Redis不向宿主开放。PG卷、回执、日志和原生检查点保留。结束时仅停止本次进程及本项目容器，不停止共享 Docker 引擎、不删除已有卷、不清理他人项目。

`environment.json` 保存 HEAD、dirty 标记、实际测试源码/compose/BFF哈希及端口；`container-contract.json` 保存注册图及凭据存在性检查；`lifecycle-matrix.json` 保存逐场景 task/run/checkpoint 等身份。失败 attempt 单独保留，复验用新目录、新子网，不能覆盖旧证据。

SIGKILL 场景的观察窗口为300秒，等待锁定版本的原生后台恢复；它不是产品 RTO，也不保证任意节点副作用恰好一次。未完成节点可能重做，真实外部工具/模型副作用仍需原有派发凭证与未知结果规则处理。

本批不验证共享项目权限、SSO、多租户资料继承、真实 Lead 决策、财务结论、生产吞吐或高可用。当前用户服务的源码覆盖层与数据保持原部署。

本批也未验证真实 SSE 断线重放与事件保留期限；报告 checkpoint 的重启回读不能替代事件流验收。前端和 Java 源码没有新增修改，复用共同版本已验证的 JAR，实际 JAR 哈希另存于环境证据。
