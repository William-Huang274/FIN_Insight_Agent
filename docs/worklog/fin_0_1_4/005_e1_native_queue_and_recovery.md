# 005：E1原生队列、中断与恢复资格

2026-09-13。FIN 0.1.4 / E1，延续`ea683e5b`，不改变产品版本、S-stage或0.1.3默认执行配置。用户“继续”授权推进隔离原生运行验证；本轮不调用模型。

## 采用边界与实际代码

采用现有Agent Server原生任务API、PG事务/队列和Redis信号。新增`deploy/qualification/agent_server.compose.yaml`、合成图`tests/qualification/fixtures/native_runtime_probe.py`与pytest资格入口`tests/qualification/test_native_server_runtime.py`。不是自研工作流/锁服务，不挂旧数据卷，不加载研究图或任何模型工具。

本机现有镜像ID为`sha256:b252c1a2d213cc6175bd43043e61ab572e1fd744ea18d62f6dcdba2c3839d167`；实读版本langgraph-api=0.13.3、langgraph=1.2.11、langchain-core=1.6.1、psycopg=3.3.4。PG/Redis沿用现有digest。原生启动日志确认无enterprise key，以现有LangSmith key运行lite模式；这仅证明本机可启动，不证明正式服务账号权益/费用。LANGSMITH_TRACING=false，只有合成输入；模型调用0，模型费用0，runtime许可成本仍未核算。

## 预定场景与不变断言

长任务占用N_JOBS_PER_WORKER=1时新thread短任务排队；同thread冲突提交409；取消释放容量，checkpoint可接续；人工pause保留中断信息且不占执行槽；服务限时优雅停机/再启动及SIGKILL后，原生队列负责恢复，已完成prepare节点不重跑；第二worker能从同一队列取得另一任务。按原生run和thread分别检查状态，不能仅靠HTTP成功或run success判定研究完成。

握手依据合成节点事件、原生状态和checkpoint；每步有超时。合成事件文件只是证据，调度与恢复不消费它。密码只通过子进程环境传递，日志脱敏，结束停止本attempt服务并保留原卷/失败记录。未重启旧工作台或历史付费容器。

## Attempts与结果

所有路径以`.local/fin014/20260913_e1_native_queue_`为前缀，旁置`.pytest.log`和`.junit.xml`不覆盖。

| Attempt | 结果 | 解释及处置 |
| --- | --- | --- |
| a1 | setup error | Docker默认地址池耗尽。检查现存网络与宿主路由后，为新实例指定未重叠的10.254.214.0/24起的独立/24网段；保留旧网络，不无证归因代理。 |
| a2 | 1 passed / 1 failed，32.21秒 | 队列/取消/接续通过；新测试错误地要求人工pause的run为interrupted。原生run实际success、thread interrupted；现有conversations.py已正确区分，修测试并保留原失败，不降低产品要求。 |
| a3 | 4 passed，45.57秒 | 单worker队列/拒绝/取消/接续、人工pause释放容量、限时优雅停机恢复、双worker共享队列通过。原生JSON与事件在目录中。 |
| a4 | 1 failed / 4 deselected，124.25秒 | SIGKILL后API恢复健康，但其后100秒内未观察到run恢复。不能声称任务丢失，也没有证明100秒恢复。查官方文档确认约两分钟扫描后，另立300秒有界观察，不覆盖失败。 |
| a5 | 1 passed / 4 deselected，152.17秒 | 仅重测hard_kill，API健康后129.516秒完成任务（含12秒合成工作）；prepare仅一次、未完成work两次。证明本样本原生扫描接续有效，不追认a4的100秒目标，也不作为稳定RTO。 |

复现入口见[资格README](../../../deploy/qualification/README.md)。本轮无完整产品回归：新增的是隔离测试，不是生产运行改动。

关闭Docker opt-in的定向回归为15 passed / 5 skipped，8.94秒；5项跳过是未授权启动Docker时的预期隔离，不把跳过算通过。a3覆盖前4个原生场景，a5单独覆盖新增hard-kill场景，未将两次执行伪写为同一次5项全测。所有本轮服务结束时均已停止，卷/网络/日志保留。候选语法、链接、JSONL及diff/凭据检查在提交前完成。

## 实测含义与最早剩余缺口

**ADOPT局部**：原生队列、checkpoint、interrupt和跨worker信号已有实际证据，不需要另造通用调度器。

**不能晋升付费自动恢复**：a3中prepare只出现一次，但`restart-work`的work_started出现两次，证明中断中的节点可能重放。当前`CaseModelAudit.awrap_model_call`每次生成uuid并调用handler，事件记录不是持久化派发去重。BFF提交回执保护的是入口重复请求，不覆盖模型节点重放；这里未执行付费重复调用，不将暴露路径声称为已发生重复扣费。

**不能把单worker上限当总预算**：a3双worker各设1，短任务在另一worker执行时长任务仍运行。全局/用户/供应商和父子任务预算必须另有共享原子业务约束，优先既有PG事务及薄FIN适配，不能只改环境变量。

下一有界实现：围绕现用模型调用入口，用模拟供应商资格化共享费用预留/结算和持久派发身份，确保未知结果不自动重发；保留按节点TokenBudgetBasis和交付预留。价格预测、用户公平性、跨主机、源权限、金融质量与正式账号许可仍未闭合，E1保持进行中。

产品增量0；工程增量为原生隔离资格入口；资格证据为上述实测及失败；文档为本记录和当前路线回填。不能以本地测试宣称多人试用、全版本实现或完整金融交付通过。
