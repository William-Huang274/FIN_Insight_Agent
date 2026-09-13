# 原生运行服务资格

这里只启动合成LangGraph图，使用现有锁定镜像、独立PG/Redis、独立卷和回环端口18414/18415。PG额外绑定127.0.0.1:18416供宿主真实SDK图测试，使用本attempt随机密码；Redis不发布端口。不会挂载旧研究数据或模型凭据。默认pytest跳过；显式启用后使用本地已有LangSmith开发账号做原生服务许可校验，关闭研究trace。

先确认端口空闲、Docker/宿主路由无重叠，并选择未使用的私有子网。`FIN_NATIVE_ATTEMPT_DIR`必须是仓库`.local/fin014`下的新目录，失败后换attempt，不覆盖旧输出：

```powershell
$env:FIN_NATIVE_QUALIFICATION='1'
$env:FIN_E1_SUBNET='<已核对未占用的私有CIDR>'
$env:FIN_NATIVE_ATTEMPT_DIR='D:/FIN_Insight_Agent/.local/fin014/<新的attempt名称>'
.venv/Scripts/python.exe -m pytest tests/qualification/test_native_server_runtime.py -q
```

入口会解析本机`finsight-dell-report-workbench-langgraph-api`的不可变image ID，并检查langgraph-api=0.13.3、langgraph=1.2.11、psycopg=3.3.4。不自动pull、build、升级或启动现有部署。合成图digest、代码HEAD、环境及逐场景状态保存在attempt目录；正在测试的未提交文件需随最终提交记录。

场景覆盖：单worker排队/同thread拒绝/取消与接续、人工暂停释放容量、限时优雅停机再启动、两个worker共享队列、SIGKILL后的原生扫描恢复。硬崩溃观察窗口300秒来自[官方约两分钟扫描机制](https://docs.langchain.com/langsmith/scalability-and-resilience)，不是产品恢复SLA。已完成checkpoint不重跑，不代表中断中的外部请求不重发。

测试结束仅停止本attempt创建的服务，保留容器、卷、网络和日志。清理另行明确选择目标，不运行全局prune。连续失败先核对配置/原生文档和日志，不增加自研运行协议。

上述队列资格不覆盖真实金融质量、模型供应商、跨用户公平性、父子共享预算、多台主机、备份恢复或正式商业部署许可。具体结果见[工作记录005](../../docs/worklog/fin_0_1_4/005_e1_native_queue_and_recovery.md)。

共享预算与模型派发资格使用相同环境变量和另一个新attempt目录，执行：

```powershell
.venv/Scripts/python.exe -m pytest tests/qualification/test_model_dispatch_budget.py -q
```

该入口在本attempt独立PG中显式安装`003_model_dispatch_budget_v1.sql`，通过真实连接争抢同一研究预算，再通过原生重启测试真实`CaseModelAudit`的可选保护。当前`src`只读挂载覆盖镜像内项目代码；模拟handler只返回合成消息，SDK仅做请求格式化，没有模型网络调用。金额均为合成整数micro单位，不是真实价格：预算1000、交付预留200、单请求占用600、合成返回usage计价200。未知占用不自动到期；已保存消息可回放，不再次结算。

模型资格覆盖一个研究根预算及子调用，不覆盖跨研究月额度/公平调度、供应商账单对账或所有产品入口。原始模型消息存入PG是为了回放，不能直接作为公共查询接口；正式启用前须完成可信owner绑定、数据库权限和保留策略。见[工作记录006](../../docs/worklog/fin_0_1_4/006_e1_shared_budget_and_model_dispatch.md)。

真实研究工厂的SDK MockTransport接入验证使用另一个新attempt，单独执行`tests/qualification/test_research_budget_wiring.py`。它覆盖同步负责人/专家、Writer交互专家和原生摘要，数据边界替换为合成fixture，真实PG统一结算；不运行完整金融验收。每次仅运行一个资格模块：fixture为module范围，不把多个模块指向同一attempt目录。失败目录存在即拒绝，不设置exist_ok覆盖。

可选产品接入使用挂载的宿主settings中的`model_budget_bindings`，按原生thread ID绑定`owner_id`、`budget_id`、`prices`和`roles`。`prices`各行对应`TokenPrices`字段；`roles`按固定运行角色给出`reservation_micros`、`reservation_basis`、布尔`delivery`，摘要角色为`context_summary`。预算须由可信宿主事先在同一个PG显式创建，运行图不创建或补充额度。启用bindings后，缺少thread/owner/角色/模型价格时拒绝执行。不存在bindings时沿用0.1.3行为；Hermes路径在启用预算时拒绝执行，不能绕过。该配置尚未默认启用，真实价格和额度需依据研究任务另行计算，不能直接采用资格测试的合成金额。
