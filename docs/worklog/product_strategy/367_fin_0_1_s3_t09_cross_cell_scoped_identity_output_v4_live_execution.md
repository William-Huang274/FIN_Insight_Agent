# FIN 0.1 S3-T09 cross-Cell scoped identity output-v4 live execution

时间：2026-07-23 21:48（Asia/Shanghai）

## 结果

用户以“继续”授权一次 exact-live proof。Project OS scoped preflight 与 runner exact preflight 均通过；进程局部设置 `LLM_GATEWAY_TRANSPORT_RETRIES=0` 后，admission `ba3642d...8973` 仅消费一次。

真实执行终态为可信 `failed / failed / failed`，orphan=false、Artifact=0。三个 Specialist 的九个 segment 全部完成；第 10 次调用 Research Lead-v4 在 `1800/1800` output tokens 以 `finish_reason=length` 截断，Writer 和 Verifier 未调用。

调用=`10/10/10`，tokens=`42373/6279/48652`，estimated cost=`USD 0.02284589`，retry/fallback/rerun=`0/0/0`。10 份 assistant final output 和 10 份 usage receipt均已受限持久化并可回读；credential、raw Provider response 和 private reasoning 未持久化。

## 独立复核

Research Lead capture 为 7177 bytes，出现 25 个 typed scoped refs 且三个 Cell 均已进入输出，但 JSON 在第 208 行的 `program_cell_id` 字符串中间被截断。直接原因是确定性的 Provider length stop，不是 scoped-ID 语义冲突或随机 JSON 格式错误。

这重新打开 RC-P36-040：Lead-v2 在旧 output-v3 下的 1800-token closure 已有 live proof，但 output-v4 将 `(identity_kind, program_cell_id, local_id)` 对象重复带入 Lead wire shape，结构膨胀使原容量证明失效。RC-P36-046 只获得 Specialist＋Lead wire 层的部分 live 证据，Writer/Verifier/Artifact lineage 仍未 live 通过。

确定性 result/decision/issuance/implementation contracts 回归 `26 passed`。

## 产品边界

成功门槛要求 terminal succeeded、六逻辑节点、12 calls 和九 Artifact families。本轮只有 10 calls、0 Artifact，不能视为 junior analyst 产品、Alpha、paired comparison 或 owner acceptance。

下一项：

`S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-RESEARCH-LEAD-V4-CAPACITY-RECURRENCE-ZERO-CALL-ROOT-CAUSE-DECISION`

尚未授权。不得直接增加 token、patch、签发、调用模型、rerun、比较、review、T10/S4/release/production。
