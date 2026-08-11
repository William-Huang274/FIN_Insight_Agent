# FIN 0.1 S3-T09：paired deterministic baseline exact-once 物化

日期：2026-07-22

## 结论与边界

用户以“授权”只允许执行已经冻结的 same-input deterministic baseline。本轮完成唯一一次 canonical materialization；没有签发或执行 fresh output-v3 Agent admission，没有调用模型、Provider、网络、来源或工具，没有进行 paired comparison、Human Review、T10/S4、release 或 production 动作。

结果为 baseline availability 通过，不是 Agent 质量或 material-gain acceptance。RC-P36-036 因 exact baseline 已存在而关闭；RC-P36-037 仍须 fresh output-v3 Agent Artifact 证明。

## 执行与 canonical truth

执行前 Project OS scoped preflight 通过。新的一次性执行器先在 disposable clone 上完整走 HTTP 202、BackgroundTask、Scheduler、Runtime 和四 Artifact commit，第二次调用在写前被 freshness guard 拒绝；clone 演练没有改变 target。最终 target 只读预检再次确认冻结 payload digest、DB/Object hash 和所有预测身份均未漂移。

canonical target 随后物化：

- WorkUnit `wu_p02_5_da52f02a9594f011dde69058` succeeded；
- Attempt `attempt_fin01_946d7ef0b02a8a88395aff53` succeeded，attempt no. 1；
- Run `research_run_fin01_fac094aac24174903915016b` succeeded；
- profile 为 `fin01.execution_profile.p36_local_deterministic:v1`；
- maximum attempts=1，retry budget=0；
- exact Artifact 为 deterministic result、S3 workpaper、S3 report、S3 trace review 四件。

逻辑差分只有 1 WorkUnit、1 Attempt、1 Run 和 4 Artifact；对象树只新增四个与 Artifact object digest 对应的 JSON。既有 output-v2 Agent Run、九件 Artifact、Case head、其他逻辑对象和已有对象文件均未变化。

## 独立只读复核

执行进程退出后，新的 verify-only 路径只用 SQLite `mode=ro` 和对象文件摘要重新核验三态、lineage、单一 deterministic Run cardinality、四 Artifact ID/type/object digest、同一三 Cell 合同和零调用字段。source Agent 仍为 succeeded 且九 Artifact 完整。再次 materialize 会因 exact WorkUnit 已存在而在写前 fail closed。

S3-T09 合同回归按耗时拆组完成，累计 `76 passed`：其中本次 materialization/owner-grade/backlog 直接相关 `39 passed`，历史 admission decision/issuance `9 passed`，transport exact-input/full-runtime `5 passed`，其余 admission/truncation/replacement issuance `19 passed`，fake-provider live runner `4 passed`。测试没有真实模型、Provider 或网络调用。

最终 verify-only 再次确认 DB hash=`46ba35b8...c9f`、Object tree hash=`00ac740b...ea75`、deterministic Run cardinality=1、baseline Artifact=4、source Agent Artifact=9。Python compile、JSON/JSONL parse、staged/unstaged diff check 均通过；对 232 个 changed files 的 credential pattern 扫描为 0 命中。

## 下一步

按已批准顺序，下一项是 `S3-T09-OWNER-GRADE-V3-FRESH-AGENT-PROOF-DECISION`，仍需单独授权。该决策只能冻结 fresh v3 identity、admission、预算和 no-reuse 边界；签发、执行、paired comparison 与 owner acceptance 仍必须分别受控。
