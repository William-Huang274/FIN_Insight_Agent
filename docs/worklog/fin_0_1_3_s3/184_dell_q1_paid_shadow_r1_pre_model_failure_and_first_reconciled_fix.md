# Dell Q1 paid shadow R1 模型前失败与 first-RECONCILED 修复

## 1. 本轮实际结果

Owner 授权的单 Specialist paid shadow 已按既定的一次性入口启动一次：

- implementation commit：`3ecdba73ea1fc93af9b480a9eb1096bc9ed04e47`；
- authority commit：`a0089e690b421b660d542f0b19c6506062006cea`；
- execution id：`20260904-dell-q1-specialist-paid-shadow-r1`；
- authority decision digest：`7872347b76f1777154452383386cdcf88dc83a240473dc057b0f184a8fb4f692`；
- host failure receipt：`Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260904-dell-q1-specialist-paid-shadow-r1/failed-receipt.json`；
- receipt SHA-256：`71796ef16d1a122368619b34a7c7f1308fa9c67701d67dac91723ebe5ca24c20`。

R1 只创建了一个 Agent Server remote run：thread=`6455a51b-c19b-5a46-9e90-6f5aaf4cbf84`、run=`01a06cbb-8161-7431-a076-5645267bbd5f`，最终状态为 `error`。没有第二次启动、retry、resume、fallback 或 direct graph invoke。

本次真实调用计数必须按最窄事实解释：

- DeepSeek/provider call：`0`；
- Specialist 发起的 Evidence/Finance MCP tool action：`0`；
- 可查询的 LangSmith root/span trace：`0`；
- remote run create：`1`；
- checkpoint、final state、报告：均不存在。

容器启动前的本地 composition preflight 确实读取了冻结的 S1/S2 输入合同，但这不是模型自主工具调用，也不能算作 Specialist 已执行研究。

## 2. 最早责任层与失败链

FIN PostgreSQL 先保存了一个 session，并将 remote-create lifecycle 写到：

`PENDING → DISPATCHED → ORPHAN → ORPHAN`

随后产品 repository 尝试把已观察到的 Agent Server run 与 FIN ResearchRun/RunInvocation 做最终 `RECONCILED` 绑定。`fin_runtime.require_valid_run_create_lifecycle_event()` 是一个 `AFTER INSERT` trigger；旧实现查询“是否已经存在 RECONCILED”时把刚插入、仍处于 trigger transaction 内的当前 RECONCILED 行也看成了历史终态，因此第一次合法 RECONCILED 必然被自己的存在误伤，并抛出：

`fin_runtime_run_create_event_after_reconciled`

绑定事务回滚后，异步 Agent Server worker 才开始运行。Graph 在最前置 durable-binding guard 找不到 RunInvocation，于是以 `fin_server_run_durable_binding_missing` 停止。该 guard 位于读取 DeepSeek key、构造模型 adapter、打开 Evidence/Finance composition 之前，所以这不是 DeepSeek、代理、RAG、S1/S2 检索或 LangSmith trace 失败。

白话解释：任务已经在 Agent Server 排上队，但 FIN 数据库在给它办“最终身份证”时，误把第一次登记当成登记后重复操作并拒绝；任务真正开始后看不到自己的合法身份证，于是在接触模型和数据工具前主动停机。

## 3. 修复与迁移

修复提交：`3844948327b12cc4bcafe00c10432f384ddb9402`。

触发器只增加一条最早责任层条件：历史 RECONCILED 的 ordinal 必须小于当前新事件的 ordinal。这样第一次 RECONCILED 不再匹配自身；任何真正发生在终态之后的新事件仍会看到更早的 RECONCILED，并继续被原 guard 拒绝。

冻结摘要随真实 PostgreSQL catalog 更新：

- fixed SQL 002 normalized SHA-256：`9e9f1e324c07bd767f71c8e870d736d44892b7b5614a4e0ffb1d557491218d25`；
- known-buggy v1.1 catalog SHA-256：`31c314f1d0d17cd91e252d4733a0eba35ae5725e85e56685a63081ba552f7bad`；
- fixed/current v1.1 catalog SHA-256：`f37dbff53d47dc59bb5390bdcf46a5f51b354ffa61ff5b8c596180d3aa169f7e`。

Installer 仍然 fail closed，只接受四种精确状态：schema absent、exact v1.0、exact known-buggy v1.1、exact fixed/current v1.1。known-buggy 分支只在 catalog digest 精确命中后单事务重放 digest-pinned SQL 002；没有删除、truncate、数据 update 或权限放宽。Readiness 只接受 fixed/current catalog，不把旧 buggy catalog 报为健康。

## 4. 有界验证

真实 PostgreSQL 16.15 已完成三类验证：

1. fresh schema 通过正式 `PostgresDellAgentServerIdentityRepository` 走到首次最终绑定；
2. exact known-buggy catalog 的独立复制库可无损迁移到 fixed catalog，旧 session/lifecycle/action 行保持；
3. 更新后的正式 qualifier 真实执行：
   - lifecycle=`PENDING/DISPATCHED/ORPHAN/RECONCILED`；
   - ResearchRun/RunInvocation/lifecycle/ActionAttempt 行数=`1/1/4/3`；
   - terminal ActionAttempt=`APPLIED`；
   - final binding digest 与实际 binding 一致；
   - 相同参数第二次 `bind_run_invocation()` 返回同一 binding，四组行数不变；
   - RECONCILED 后追加 ORPHAN 被 SQLSTATE `23514`、`fin_runtime_run_create_event_after_reconciled` 拒绝；
   - 原有 negative contract 总数仍为 `44`；
   - Docker management、HTTP、外部研究和模型调用均为 `0`。

受影响定向回归为 `152 passed in 2.13s`；Python compile、shell parse、diff check 与 changed-file secret-literal scan 通过。Project OS 定向测试为 `81 passed / 1 failed`；唯一失败仍是本轮改动前已经存在的 `current_dynamic_writer_submission_successor` 对 `src/sec_agent/project_os_preflight.py` sealed SHA drift，本轮没有修改或掩盖该旧 authority。作者分离只读审阅结论为 `P0=0 / P1=0`。依风险分层策略，本次没有重复全仓测试；改动范围已由直接/相邻测试、真实 PostgreSQL fresh/migration/repository 路径覆盖。

## 5. 当前边界与下一步

R1 失败 receipt、remote run、PostgreSQL 数据和容器现场保持不覆盖、不重启、不原位修复。由于 preserved R1 PostgreSQL 仍是 known-buggy catalog，而 bind-mounted 当前 readiness 已只接受 fixed catalog，它现在可以显示为 unhealthy；这是新 readiness 对旧 catalog 的预期拒绝，不表示 R1 数据被改写，也不得为了绿灯修改该现场。

`RC-S3-107` 继续 open：本修复只关闭 first-RECONCILED self-match，不证明 K0–K6、unknown-outcome 自动恢复、distributed exactly-once、multi-worker production、完整 multi-agent、报告或产品验收。

下一次付费运行不能复用 R1 execution id/authority。只有在本修复 clean/pushed 后，才能另行创建 fresh R2 authority、fresh execution id、fresh project/port/volume；仍保持一次启动、无 retry/resume/fallback、unknown outcome 转人工。R2 尚未创建、授权或运行。
