# 004：开工基线审查与E1真实进程资格

2026-09-13。FIN 0.1.4 / E1局部资格，未关闭E1或提升S-stage。

## 交接与审查结论

用户要求熟悉0.1.3，监督任务`01a0906c-3089-7752-b683-cea6e135c4d0`的PRD/技术/执行整理，审查通过后开始0.1.4。截图仅为历史上下文。用户授权合理范围DS/Qwen测试，逐调用TokenBudgetBasis、未知结果不重发及质量要求仍有效；Docker重启/网络问题优先检查本地代理，不能直接认定代理为根因。

wait_threads确认目标本轮`01a09a32-ccc7-7a70-8505-36c09704a13f`completed/idle；最终提交`102a4584`同步origin，交接时Git干净。监督heartbeat `fin-0-1-4`已暂停避免重复开工，新分支`codex/fin014-e1-runtime-qualification`从该提交开始。

结论：接受三份文档为有界开工基线。PRD持续项目→接入→研究→编辑→更新流程覆盖质量、资产权限、多人运行和合格交付成本；技术职责与E1–E5一致，保留成熟栈和渐进选择。无需再写详细总规划。

两项待验：锁定0.13.3的部署许可/实际账号费用未证；旧`test_two_process_equivalent_ingresses_share_atomic_claim`仅同一进程两个应用，不是真实进程退出证据。后者本次补证，前者留在E1。0.1.3原生Writer未完成、错误草稿干扰等质量根因仍开放。

## 首个切片

新增`tests/test_submission_receipts_processes.py`，pytest + multiprocessing spawn启动真实PID，ASGI合成派发记录本地副作用；使用原`SubmissionReceipts`、`LocalRecords`和SQLite事务，不新建控制面。

执行前固定断言：同owner同key竞争只派发一次；进行中409，完成后新进程回放200；改载荷422；第二owner同key独立处理；副作用后进程终止须保留未知且不重试；保存响应后送达前终止须可回放而不重复副作用。事件握手定位故障点，不以sleep碰撞；超时后只清理本测试创建的进程。

**ADOPT限同机回执边界**：原生数据库事务满足上述检查，无证据要求自研锁服务。不是跨主机、原生队列、实际身份认证或外部供应商资格。

Attempt `20260913_e1_receipts_processes_a1`：

```powershell
.venv/Scripts/python.exe -m pytest tests/test_submission_receipts_processes.py tests/test_submission_receipts.py tests/test_usage_pricing.py -q --junitxml=.local/fin014/20260913_e1_receipts_processes_a1/results.xml
```

**15 passed in 14.17s**，含新增3场景。stdout为`.local/fin014/20260913_e1_receipts_processes_a1/pytest.log`，JUnit同目录，输出忽略且不覆盖为后续attempt。生产代码未改，不重复完整回归。

Docker CLI当时正常返回但无运行容器，不能认定崩溃/代理故障。Dockerfile锁定`langchain/langgraph-api:0.13.3-py3.13`及digest。复核[官方架构](https://docs.langchain.com/langsmith/agent-server)及[独立部署说明](https://docs.langchain.com/langsmith/deploy-standalone-server)：原生队列/PG/Redis为首选；当前许可和使用报告说明不替代锁定版本及账号授权。未启动/重启容器、读取密钥或连接模型供应商。

## 进度与下一步

- 产品增量0：P1–P8未验收，新功能未交付。
- 工程增量：3个真实进程资格测试，生产代码不变。
- 资格证据：上述竞争/退出/回放通过，既有回执和计价定向回归通过。
- 文档：审查通过并回填PRD/技术/执行路线、Project OS、工作索引，不充当产品实现证据。
- 未完成：原生队列/取消/checkpoint/worker重启、部署许可/费用、跨worker父子预算。下一步用隔离原生运行实例和模拟模型补证；E2–E5待实施。

模型调用0、模型费用0、迁移0、部署0。包版本仍0.1.3，旧研究/未知调用不变。提交前执行候选diff/凭据/链接检查；提交推送以Git和最终回复为准。
