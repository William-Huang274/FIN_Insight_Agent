# 原生运行服务资格

这里只启动合成LangGraph图，使用现有锁定镜像、独立PG/Redis、独立卷和回环端口18414/18415。不会挂载旧研究数据或模型凭据。默认pytest跳过；显式启用后使用本地已有LangSmith开发账号做原生服务许可校验，关闭研究trace。

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

该资格不覆盖真实金融质量、模型供应商、跨用户公平性、父子共享预算、多台主机、备份恢复或正式商业部署许可。具体结果见[工作记录005](../../docs/worklog/fin_0_1_4/005_e1_native_queue_and_recovery.md)。
