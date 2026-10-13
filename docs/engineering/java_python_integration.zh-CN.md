# Java / Python 共同版本与执行配置接续

日期：2026-10-13。范围：独立共同版本的工程整合与静态资格验证，未部署替换现有研究服务。模型调用为零。

本批整合 Python `89f25f50` 与 Java `a3a05091`，共同祖先为 `6226a7d0`，工作分支为 `codex/java-python-integration`。保留两边既有项目入口、业务回执、研究反馈及运行事件隔离。组织项目与空间管理是既有分批能力；本次没有开放团队资料参与研究或共享报告权限。

## 用户行为与配置合同

研究申请保存的执行选择，需要在准备、启动、刷新回读和技术接续中保持一致。Java 业务受理成功不代表研究完成；执行终态仍由 Agent Server 提供。业务状态、运行身份、故障窗口见[受理与故障恢复](java_intake_recovery.zh-CN.md)。

`execution.continuation_scope` 有两个合法值：

| 值 | 行为 |
| --- | --- |
| `original_question` | 在原研究问题及既有资源、预算边界内继续；允许运行时根据覆盖缺口调整任务 |
| `original_plan` | 明确限制为完成原计划；不是从“已有底稿”自动推断出的限制 |

Java 与 Python 均在新输入省略该字段时采用 `original_question`；显式 `null` 或非法字符串被拒绝。前端类型兼容旧三字段配置；新 run 的有效配置按 Python `ExecutionOptions` 归一化。字段没有改变资源访问权限，也不能绕过未知用量检查。

- Java 保存准备请求并透传 Python。相同提交键仍匹配原请求字节；不会为了补默认值改写已有请求、重算旧摘要或重新签发旧命令正文。
- 新研究、草稿启动、追问/修订、研究接续及底稿恢复，将同一次计算得到的有效 `execution` 同时保存到原生 run 的 `config.configurable.finsight_execution` 与 `metadata.execution`。
- 前端首次加载研究时继承该研究的配置；轮询不覆盖用户正在编辑的选择，切换研究不携带上一研究的配置。
- 零模型确认/返回审阅等管理动作没有统一补写执行快照，不能把本批描述成“所有历史 run 均有配置快照”。已有历史 run 保持原样。

## 技术接续为什么取上一次 run

会话默认值和本次运行的覆盖值可能不同。例如会话默认允许围绕原问题继续，但一次修订明确选择只完成原计划。该修订暂停后，继续入口如果重新读取会话默认值，就会丢掉用户对这次修订的限制；模型选择也可能回退。

`continue-remaining` 和 `recover-workpaper` 按以下顺序确定执行选择：

1. 被接续 run 的 `metadata.execution` 有效快照。
2. 旧 run 的 `config.configurable.finsight_execution`，如果可用。
3. 仅当历史记录无快照时，兼容原会话配置；无会话配置则采用默认值。旧记录无法凭空恢复已丢失的覆盖值。

新 run 保存相同有效配置，并用 `continued_from_run_id` 关联被接续运行。有快照但字段非法时返回 409，不能静默换成较宽松默认值。沿用的是执行选择，不是整份历史资源/研究配置：当前项目访问仍检查，资料修订及研究配置仍按原入口规则读取；失败或未知用量门槛未放宽。

测试先复现“修订覆盖 → 暂停 → 继续/恢复底稿”两个入口、两个 scope 方向的四个失败，再修复。另覆盖已知失败节点接续继承、旧三字段配置、历史 config 缺失/为空及非法值。底稿恢复测试替换内容校验器，仅证明 BFF 配置流转，不证明人工修正内容正确。

## 定向修订的重复请求

新修订 run 额外记录 `metadata.request_execution`：用户省略时为 `null`，显式提交时为归一化请求。这与 `metadata.execution` 的有效运行配置各有用途，不能混用。重放使用 request ID、修订目标、意见摘要和请求配置核对，命中只返回原 run。

旧记录缺少 `request_execution` 时：显式配置按旧有效配置归一化核对；旧有效配置存在而本次省略，则返回明确 409，提示查看原运行，不创建新 run。旧记录无法无损识别当初是否省略，不能宣称完全兼容旧请求的重放。更换 request ID 不能被作为自动消除冲突的策略。

## 验证层次与复现

本批验证结果：Spring/临时 PostgreSQL 14 项、Python 相关回归 136 项、构建后浏览器 29 项、跨进程测试 2 项（包含七个故障场景）通过；前端类型检查与构建、活跃基线检查、密钥扫描通过。最后的旧配置 `null` 兼容修改另复验受影响 BFF 44 项，包含在上述 Python 用例范围内，不重复累计。

保留了两次浏览器失败证据：开发服务器首轮冷启动期间导航超时；构建后复验发现旧测试把“从项目移除”误断言成整页不再出现该组织成员。后者改为同时核对项目名单移除和组织候选保留，最终构建预览全套29项通过。没有通过增大超时或删除角色断言掩盖失败。

| 层 | 可证明的行为 | 不证明什么 |
| --- | --- | --- |
| Spring HTTP + 临时 PostgreSQL | 合法值、默认值、非法值、持久化、签名委托及重放正文保持一致 | 真实模型执行 |
| BFF + 脚本化 SDK / 离线图 | 配置快照、接续覆盖、旧请求冲突、回执与原生身份关联 | 持久任务队列故障恢复 |
| 浏览器静态 API fixture | 刷新不重提、旧事件隔离、配置继承、轮询及跨研究操作、项目/空间入口 | 浏览器到真实模型的全链路 |
| 真实 BFF、Java 进程 + 临时 PostgreSQL + 磁盘执行器 fixture | 进程重启回读、七个故障窗口、同一业务任务与原 run 核对、持久配置 | 原生 Agent Server 宕机恢复或模型供应商重试 |

先按[业务服务说明](../../apps/business-service/README.md)安装 JDK 21、Docker 和仓库声明的测试依赖。使用新临时目录保留每次证据，测试不应连接正在使用的业务数据库。以下命令从仓库根目录执行，前端与 Java 命令除外：

```powershell
uv run --no-sync python -m pytest -q tests/test_execution_options.py tests/test_java_research_intake.py tests/test_report_session.py tests/test_research_cancellation.py tests/test_research_recovery.py tests/test_research_session_bff.py tests/test_research_studio.py tests/test_submission_receipts.py tests/test_submission_receipts_processes.py tests/test_targeted_revision.py tests/test_project_workspace.py tests/test_resource_spaces.py tests/test_research_feedback_api.py tests/test_research_feedback.py tests/test_agent_session_feedback_runtime.py

# apps/business-service
./mvnw.cmd verify

# 仓库根目录；动态端口、独立临时 PostgreSQL；执行器仍为磁盘 fixture
$env:FINSIGHT_INTAKE_TEST_JAR=(Resolve-Path apps/business-service/target/business-service-0.1.0.jar).Path
uv run --no-sync python -m pytest -q tests/integration/test_java_intake_stack.py tests/integration/test_java_intake_faults.py --basetemp .local/common-integration-r1 --junitxml .local/common-integration-r1.xml

# apps/workbench/frontend；指定空闲端口
npm run build
$env:FINSIGHT_E2E_FRONTEND_PORT='4187'
npx playwright test --config playwright.recovery.config.ts
```

进程验收的数据库行、BFF 回执、合成 native 状态和 `fault-matrix.json` 留在临时产物目录，不提交 Git。没有付费请求，不生成新的金融研究结论。

## 发布与下一阶段

本批没有切换现有部署、迁移现有业务数据或修改双方来源分支。当前回退点就是原部署。未来发布应在独立端口、专用业务数据库、独立回执目录验证候选版本，再协调服务切换；数据库/回执备份与版本配套回退按受理说明执行，不能通过删除已受理记录来“回滚”。

2026-10-13 后续切片已完成[真实原生服务生命周期验收](java_native_lifecycle.zh-CN.md)：真实 BFF、Java、PG、Redis、Agent Server 配合确定性研究图，通过创建与去重、显式接续、停止及晚到、重启回读和强杀恢复；修复已结束 run 的停止被误报为 502。上述历史表格仍描述本批最初的分层验证，新增资格范围以该后续文档为准。未运行生产研究图或付费模型，也未验证真实 SSE 断线重放。

后续[项目关联空间资料](project_resource_links.zh-CN.md)已通过当前项目/源权限交集、固定发布引用、撤权后的新读取拒绝与项目筛选验收。下一阶段把授权接到研究准备/启动、执行中的撤权和衍生报告可见性；资料阅读通过不等于这些研究权限闭环已经完成。静态工程测试通过也不是研究报告质量或生产并发容量的证明。
