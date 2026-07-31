# FIN 0.1 S3-T09：paired deterministic baseline 物化决策

日期：2026-07-22

## 结论

用户批准按“基线物化决策 → RC-P36-037 零调用语义修复 → 分别授权 baseline 与新 Agent 证明 → paired comparison → owner acceptance”的顺序推进。本项只完成第一步：冻结了一条与 replacement Agent 完全同 Case/version、DecisionSurface、as-of、input-head 和三 Cell，但 WorkUnit、Attempt、ResearchRun、profile 与四类 Artifact 全部独立的 prospective deterministic baseline。本轮没有物化 baseline，也没有模型、Provider、网络、来源、工具、Agent rerun 或 Human Review。

prospective identity 为 WorkUnit `wu_p02_5_da52f02a9594f011dde69058`、Attempt `attempt_fin01_946d7ef0b02a8a88395aff53`、Run `research_run_fin01_fac094aac24174903915016b`；profile 固定为 `fin01.execution_profile.p36_local_deterministic:v1`，四类 Artifact 固定为 deterministic result、Workpaper、Report 和 Trace/Review。两次编译 payload 完全一致，digest=`71784beb...e57b`，所有 prospective identity 在当前 canonical store 中均不存在。

## 安全预检事件

第一次诊断错误地在目标 runtime 上实例化 `CaseService.for_fixture_root`。该入口会调用 SQLite store migration/WAL 初始化；虽然没有创建 prospective WorkUnit、Attempt、Run、Artifact，Object Store 也未变化，但 canonical SQLite 文件摘要从 `64d2c1dc...` 变为 `876e98a855...`。此物理改写不能被描述成严格只读，已登记 RC-P36-038。

预检方法随后改为：目标数据库只用 SQLite `mode=ro` 和文件摘要检查；所有 service/runtime 初始化及双编译只在 disposable temporary clone 上执行。修正后复跑中，目标 SQLite 摘要固定为 `876e98a855...`，Object tree 摘要固定为 `4d6a8e19f...`，逻辑快照和两类摘要前后均不变。RC-P36-038 以“方法修复并有 target hash guard”关闭，后续不得在目标 runtime 上直接初始化 migrating store 做所谓只读预检。

## 决策边界

未来 baseline 若获独立授权，只允许一次 deterministic attempt、retry=0，并要求 model/provider/network/source/tool/promotion/live Case write 全为 0。它不得作为 Agent fallback，不得把 baseline 正文暴露给未来 Agent，不得标成 Agent 输出，也不得由 machine verifier 代签 Human acceptance。

RC-P36-036 已从“缺少方案”推进到“物化合同已决定、执行等待后续独立授权”，但仍是 T09 blocker。RC-P36-037 的 owner-grade semantic/actionability gap 尚未修复，所以现在先物化 baseline 也不能让 paired comparison 或 owner acceptance 有效。

## 下一步

唯一下一项切换为 `S3-T09-OWNER-GRADE-SEMANTIC-ACTIONABILITY-ZERO-CALL-REPAIR-DECISION`。该项只做零调用修复决策；baseline 物化、新 Agent 证明、paired comparison、owner acceptance、T10、S4、release 和 production 均未授权。

复演命令：

```powershell
python scripts/releases/prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision.py
```
