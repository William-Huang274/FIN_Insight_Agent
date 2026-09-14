# 原生运行服务资格

2026-09-14增加宿主单次真实流式资格入口 `tests/integration/test_deepseek_stream_budget.py`，须同时设置 `FIN_PAID_STREAM_PROBE=1` 和下述隔离环境，并关闭宿主 `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2`。仅读取既有DS key到宿主，Docker仍无模型key。入口按日期拒绝过期价表，运行前保存TokenBudgetBasis/单价/预留：根预算0.10元、输出1000tokens、HTTP最多1次、SDK重试0。日期变化需重新核实价格与任务依据。缺失或未知响应不自动重发，测试断言失败先检查保存证据，不直接重跑付费测试。

`environment.json`中的`fixture_graph_model_calls=0`仅指Docker合成图；宿主真实调用以`paid_http_dispatches.json`、`paid_events.jsonl`和PG snapshot为准。008样本已知保存/结算及回放完成，最后算术字符串断言失败保持原JUnit；后续数值等价复核只读取保存结果。详见内部记录 008。

这里只启动合成LangGraph图，使用现有锁定镜像、独立PG/Redis、独立卷和回环端口18414/18415。PG额外绑定127.0.0.1:18416供宿主真实SDK图测试，使用本attempt随机密码；Redis不发布端口。不会挂载旧研究数据或模型凭据。默认pytest跳过；显式启用后使用本地已有LangSmith开发账号做原生服务许可校验，关闭研究trace。

先确认端口空闲、Docker/宿主路由无重叠，并选择未使用的私有子网。`FIN_NATIVE_ATTEMPT_DIR`必须是仓库`.local/fin014`下的新目录，失败后换attempt，不覆盖旧输出：

```powershell
$env:FIN_NATIVE_QUALIFICATION='1'
$env:FIN_E1_SUBNET='<已核对未占用的私有CIDR>'
$env:FIN_NATIVE_ATTEMPT_DIR='D:/FIN_Insight_Agent/.local/fin014/<新的attempt名称>'
.venv/Scripts/python.exe -m pytest tests/integration/test_native_server_runtime.py -q
```

入口会解析本机`finsight-dell-report-workbench-langgraph-api`的不可变image ID，并检查langgraph-api=0.13.3、langgraph=1.2.11、psycopg=3.3.4。不自动pull、build、升级或启动现有部署。合成图digest、代码HEAD、环境及逐场景状态保存在attempt目录；正在测试的未提交文件需随最终提交记录。

场景覆盖：单worker排队/同thread拒绝/取消与接续、人工暂停释放容量、限时优雅停机再启动、两个worker共享队列、SIGKILL后的原生扫描恢复。硬崩溃观察窗口300秒来自[官方约两分钟扫描机制](https://docs.langchain.com/langsmith/scalability-and-resilience)，不是产品恢复SLA。已完成checkpoint不重跑，不代表中断中的外部请求不重发。

测试结束仅停止本attempt创建的服务，保留容器、卷、网络和日志。清理另行明确选择目标，不运行全局prune。连续失败先核对配置/原生文档和日志，不增加自研运行协议。

上述队列资格不覆盖真实金融质量、模型供应商、跨用户公平性、父子共享预算、多台主机、备份恢复或正式商业部署许可。具体结果见内部记录 工作记录005。

共享预算与模型派发资格使用相同环境变量和另一个新attempt目录，执行：

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_model_dispatch_budget.py -q
```

该入口在本attempt独立PG中显式安装`003_model_dispatch_budget_v1.sql`，通过真实连接争抢同一研究预算，再通过原生重启测试真实`CaseModelAudit`的可选保护。当前`src`只读挂载覆盖镜像内项目代码；模拟handler只返回合成消息，SDK仅做请求格式化，没有模型网络调用。金额均为合成整数micro单位，不是真实价格：预算1000、交付预留200、单请求占用600、合成返回usage计价200。未知占用不自动到期；已保存消息可回放，不再次结算。

模型资格覆盖一个研究根预算及子调用，不覆盖跨研究月额度/公平调度、供应商账单对账或所有产品入口。原始模型消息存入PG是为了回放，不能直接作为公共查询接口；正式启用前须完成可信owner绑定、数据库权限和保留策略。见内部记录 工作记录006。

真实研究工厂的SDK MockTransport接入验证使用另一个新attempt，单独执行`tests/integration/test_research_budget_wiring.py`。它覆盖同步负责人/专家、Writer交互专家和原生摘要，数据边界替换为合成fixture，真实PG统一结算；不运行完整金融验收。每次仅运行一个资格模块：fixture为module范围，不把多个模块指向同一attempt目录。失败目录存在即拒绝，不设置exist_ok覆盖。

可选产品接入使用挂载的宿主settings中的`model_budget_bindings`，按原生thread ID绑定`owner_id`、`budget_id`、`prices`和`roles`。`prices`各行对应`TokenPrices`字段；`roles`按固定运行角色给出`reservation_micros`、`reservation_basis`、布尔`delivery`，摘要角色为`context_summary`。预算须由可信宿主事先在同一个PG显式创建，运行图不创建或补充额度。启用bindings后，缺少thread/owner/角色/模型价格时拒绝执行。不存在bindings时沿用0.1.3行为；Hermes路径在启用预算时拒绝执行，不能绕过。该配置尚未默认启用，真实价格和额度需依据研究任务另行计算，不能直接采用资格测试的合成金额。

## 独立预算连接、权限和保留

2026-09-14起，启用上述binding还必须显式提供`FIN_MODEL_BUDGET_POSTGRES_URI`，使用独立预算数据库及受限worker登录。不会回落Agent Server的`POSTGRES_URI`。原生服务的迁移/管理账号不应获得这个业务库的连接配置；模型工具、浏览器、费用读取端也不获取worker凭据。运行入口检查登录角色、建库/授权等属性、表/列及schema危险权限；这不替代部署时的角色成员关系和网络访问审查。

采用[PostgreSQL原生授权](https://www.postgresql.org/docs/16/sql-grant.html)、[受限视图](https://www.postgresql.org/docs/16/sql-createview.html)和[pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)。在全新专用数据库，由可信迁移账号依次执行`src/sec_agent/agent_runtime/sql/003_model_dispatch_budget_v1.sql`及`004_model_dispatch_access_v1.sql`。004是显式一次性bootstrap，不由运行图自动执行；它建立三个NOLOGIN组，遇到同名角色会拒绝并回滚。其他数据库/新集群应先核对角色，不盲目覆盖现有授权。不得将其直接应用到旧研究/原生服务库。

| 身份 | 权限与边界 |
| --- | --- |
| 迁移owner | 拥有DDL/映射/备份权限，凭据不提供给运行图；当前合成资格用独立PG的管理账号 |
| `fin_model_provisioner` | 新建根预算、读取和锁定预算；不能读取模型响应；既有预算不能修改 |
| `fin_model_worker` | 锁定预算、创建派发、结算/标记未知和回放原响应；不能新建或增大预算、删表/删账、修改已知或未知回执 |
| `fin_model_cost_reader` | 只读`fin_model_cost_summary`，通过owner管理的`fin_model_cost_access(login_role,owner_id)`绑定到登录身份；无原始表读取权 |

worker是处理研究任务的可信服务身份，可以读它连接的库内各owner响应；这不是按终端用户隔离的worker。费用视图使用不可由普通会话伪造的`session_user`，SET ROLE或自定义owner变量不改变授权；共享一个费用登录不能用于隔离多个用户。视图尚未接入公共费用API，应用层认证与项目权限仍需另行验证。

当前保留规则是正文、调用身份、预算依据、已知费用和未知占用一起保留；不给运行/费用账号DELETE/TRUNCATE，不运行自动清理。正文到期删除、保留期限、加密与备份副本处置未资格，不能把备份也当作公开资料。已有失败/未知证据不清除。语句查找路径固定可信schema，预算更新及终态回执重写由PG触发器拒绝，不新增运行状态机。

新attempt单独执行`tests/integration/test_model_budget_access.py`，使用本机既有PG16镜像验证两个读者、受限宿主预算入口、争抢预算、禁止删改和原生dump/restore。恢复目标是本attempt新数据库，角色在同一集群已存在，模型调用0。备份时没有进行中的新请求：恢复后已知费用、未知/缺usage占用和读取ACL不变；这不是跨机器灾备、PITR或活跃系统的RPO证明。旧快照不包含后续派发，不能恢复后直接接通付费自动执行；须先停发并核对快照之后的调用证据。备份/恢复只能显式选择可信源和新目标，不使用`--clean`或覆盖旧库。详见内部记录 009。
