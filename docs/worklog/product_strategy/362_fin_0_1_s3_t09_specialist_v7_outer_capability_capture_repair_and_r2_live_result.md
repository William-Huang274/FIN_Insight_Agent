# 362 — FIN 0.1 S3-T09 v7 outer capability/capture repair 与 r2 live 结果

日期：2026-07-23

用户授权“修复，修复完做真实模型调用看看修复效果”。本轮先以零调用方式完成两个通用工程修复：

1. 新增 `specialist_assembled_output_max_utf8_bytes`，由 immutable transport capability 与 `BoundedResearchProfile` 共同解析完整 Specialist 输出上限；inner segmented assembly 与 outer executor 使用同一 policy，不再维护 `{v5,v6}` 版本集合。
2. outer executor 的 Specialist、Lead、Writer、verifier-input、Verifier post-node validator 均通过 typed `BoundedAgentExecutionError` 传播累计 usage receipts 与 restricted assistant-final-text captures；错误 telemetry 不保存 raw invalid payload 或任意异常文本。

聚焦 v5/v6/v7/capture persistence 回归 `29 passed`。全量历史 S3-T09 suite 为 `303 passed / 44 failed`；44 项均是把旧 backlog next_action 或旧累计 canonical Run 数量写死的历史状态快照断言，不是本次 repair-path 合同失败。全量 suite 打开 target runtime 后只改变 SQLite 物理摘要；logical identity、14/14/14/13 counts、prospective r2 identity、prepared payload、admission digest 与 object tree 均不变。签发预检因此先 fail-closed，完成 direct-mode-ro 审计并刷新尚未签发的 proof 物理摘要后才继续。

r2 admission digest `006a280d8aa28dddbb285f36f1386fce5029c76743dd42b4b732d6271124b92a` 经 Project OS scoped preflight 与 retry-zero exact preflight 后消费一次。真实结果：

- WorkUnit/Attempt/Run=`failed/failed/failed`，orphan=false，Artifact=0；
- DeepSeek calls=`11/11/11`，tokens=`42583/5942/48525`，latency=`77283 ms`，cost=`USD 0.02275447`；
- 0 retry、0 fallback、0 rerun、0 source network、0 external tool；
- 三个 Specialist Cell、九个 Specialist segment、Research Lead 和 Memo Writer Provider response 均完成；
- usage receipt=11、durable capture=11、restricted readback=11，原始回答可持续复盘。

这证明 RC-P36-045 outer capability residue 与 RC-P38-042 post-node capture recurrence 的修复在 live 路径生效。Verifier 未调用，因为 Memo Writer 本地 canonical assembly fail-closed。

受限回读显示 Writer 原始回答的五条 claim renderings 形状、cardinality 与 claim IDs 均合法。新的最早根因是跨 Cell identity scope 不一致：Demand 与 Value/Profit 两个 Cell 都合法地产生 `wwc-001/002/003`；Specialist 只校验 Cell-local uniqueness，Writer 却用 global task-id map 判定 lineage，导致前一 Cell refs 被覆盖。登记 `RC-P36-046-s3-cross-cell-local-id-namespace-gap`。

下一项冻结为 `S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-ZERO-CALL-ROOT-CAUSE-DECISION`。建议方向是 typed `(program_cell_id, local_id)` scoped identity 或 canonical assembly scoped ref，Prompt/validator/Lead/Writer/Verifier 同源；不得静默重写历史 answers。未经新授权不得 patch、replacement admission、模型 rerun、paired comparison、Human Review、T10、S4、release 或 production。
