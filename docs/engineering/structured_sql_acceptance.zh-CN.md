# 历史结构化 SQL、数据卡与组织快照验收

本切片复用旧查询案例和已发布库中的真实观测，验证数据身份、版本和事务行为。工程验收不重新判断发行人披露或金融结论是否正确，也不调用 embedding、重排或大模型。所有修改发生在新建的局部 SQL 副本、自有 PostgreSQL 和测试资料空间中。

## 实际经过的链路

1. 对已发布库作只读 SHA256 核对，以历史查询参数运行 `query_metrics`，按历史摘要算法比较完整结果。
2. 按公司和稳定记录 ID 读取数据卡，与 SQL 原始列核对公司、指标、十进制字符串、单位、期间、可知日、来源和业务范围。可知日前及错误公司范围均不能读到记录。
3. 直接披露沿 `source_id` 校验原文摘录；计算卡沿输入 ID 回读原始数据卡、校验摘录并以 Decimal 复算。不能要求计算结果本身拥有一段发行人原文。
4. 宿主准备器将明确选定的数据卡保存为既有 `project_source_snapshot.v1` 的 financial 行快照，保留全部字段和选择摘要。真实 BFF 发布到 Java 管理的组织空间，关联项目并固定研究输入。
5. 经 Java 当前授权，由 Python `OrganizationExecutionReader.read_rows`、正式结构化 MCP 工具和组织资料读取 API 回读，逐字段比较原快照。新测试版本须重新发布、选择和绑定，旧研究不会自动换版。撤权后读取失败。

上述第四步是原 SQL 切片的宿主验收适配。后续[指标卡页面保存与发布](metric_card_publication.zh-CN.md)补充了用户显式选取、服务端重读和组织发布入口。两者复用同一个 financial 快照合同；公共指标浏览不代表可以执行任意组织 SQL。

## 场景与断言

| 场景 | 断言 |
|---|---|
| NVIDIA、阿里、Meta、Dell 历史查询 | 与旧查询期望摘要一致；不是独立金融答案金标 |
| 12 张数据卡及计算依赖 | 公司、公司财年/季度、单季/时点、USD/CNY/persons/% 和完整十进制字符串保留 |
| Meta 分部利润率 | 两个原始输入、原文、单位和计算结果一致，未以二进制浮点重算 |
| 新增工程修订 | 明确标记合成修订，不冒充发行人重述；追加新身份和可知日，旧卡不覆盖，新卡不提前可见 |
| 两个并发相同 SQLite 导入 | 收敛为一条新观测；重复执行不额外增加来源、观测 |
| SQLite 中途失败 | 在观测写入之后、coverage 写入时注入 ABORT；来源、原文、定义及观测整体回滚，移除故障后显式重试 |
| 项目/快照/组织发布重复提交 | 保持相同身份；相同项目创建 ID 搭配不同内容返回冲突，创建审计仅一条 |
| 同版本并发修改项目 | 真实 PostgreSQL 锁和版本校验产生一笔 200、一笔 409，不自动覆盖败者 |
| Java 审计写入失败 | 项目 UPDATE 与审计 INSERT 同事务回滚；重启自有 Java 后读取旧状态，再显式提交成功 |
| 新快照发布及撤权 | 旧研究仍读原快照，不能读取未选新版本；撤权后结构化行拒绝读取 |

SQL 的“修订”有两层：观测记录保留来源版本和可知日，组织研究固定所选快照版本。对行业观测追加记录不等于自动判定谁取代谁；此处不建立隐式更正链。没有人工确认的口径重述，不自动合并成最新唯一值。

数据卡查询计划记录了主键索引定位。测试仅含 12 张卡、2 个计算输入和两个并发写入者，不能推导生产吞吐、锁等待上限或大表优化效果。

## 复现

准备材料需要可访问的历史发布库和原查询清单；它们不进入 Git，也不是普通 CI 的前提。

```powershell
python -m scripts.data_retrieval.prepare_structured_sql_cases `
  --library <immutable-published-library.sqlite> `
  --cases <historical-execution-cases.json> --output <new-private-directory> `
  --entities NVIDIA COMPANY::alibaba COMPANY::meta COMPANY::dell
```

准备器核对历史库摘要，禁止网络连接，创建保留原记录 ID/原文/核查规则的小型 SQL 副本。生成材料仅供工程验收；不得将这个局部副本作为完整研究资料库部署。

```powershell
$env:FIN_STRUCTURED_SQL_CASES = '<new-private-directory>/cases.json'
$env:FIN_STRUCTURED_SQL_RESULT = '<new-result.json>'
python -m pytest tests/integration/test_structured_sql_history.py -q
```

真实服务入口 `tests/integration/test_organization_structured_sql_stack.py` 使用与[真实服务交付验收](organization_business_delivery.zh-CN.md)相同的独立栈变量：`FIN_NATIVE_ATTEMPT_DIR`、`FINSIGHT_INTAKE_TEST_JAR`、`FINSIGHT_TEST_DOCKER`、`FIN_PROBE_SUBNET`、`FIN_PROBE_IMAGE` 和既有开发许可配置。这里只启动自有 PostgreSQL、Java 和 BFF；公共测试基类仍核对原生镜像版本，但不启动 Agent Server/Redis 或研究图。

常规 CI 不需要私有历史库、Docker、Java 或提供方凭证：

```powershell
python -m pytest tests/test_structured_sql_acceptance.py tests/test_industry_metrics.py tests/test_metric_workspace.py tests/test_metric_reviews.py tests/test_organization_execution_access.py tests/test_resource_spaces.py -q
```

`test_structured_sql_acceptance.py` 用小型合成披露运行同一导入/修订/并发/回滚流程，历史数据测试保持独立 opt-in。真实服务与 SQL 结果保存在各自输出目录，失败尝试保留，不覆盖原材料。

## 2026-10-20 验收结果

- 4 个历史 SQL 查询与原期望摘要一致，12 张数据卡和 2 个计算输入的原始来源、身份及数值检查通过；局部 SQL 副本读卡与原发布库一致。
- 历史 SQLite 导入、双线程重复写入、合成修订、异常回滚和显式重试场景通过，最终执行约 0.32 秒。
- 真实 BFF/Spring/PostgreSQL 场景通过，最终执行约 57.58 秒，覆盖四组快照、幂等、200/409 冲突、审计故障 500、事务回滚、Java 重启和撤权。该时间包含服务启动与本机开销，不是接口延迟指标。
- 常规回归 49 项通过；基线与密钥检查通过。所有新案例均未调用付费模型，未运行 Agent 图，不切换共享服务。

## 当前未覆盖

实时团队数据库连接器、数据库级行/列权限、跨服务分布式原子提交、进程在事务中被强杀后的恢复、生产负载和真实 SSO 尚未通过本切片验收。此次故障测试是确定位置的 SQL 异常回滚加 Java 重启，不能称作全部断电/网络分区故障验证。金融研究质量仍需独立验收。
