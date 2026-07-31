# FIN 0.1 S4-T05 R7 post-Verifier failure observability 根因处置

日期：2026-07-27
范围：`S4-T05-DELL-R7-POST-VERIFIER-UNTYPED-VALUEERROR-AND-LOST-FAILURE-OBSERVABILITY-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`

## 结论

R7 的具体 `ValueError` message 没有进入不可变证据，因此本轮不能诚实地把失败归到某一个字段、某一个 validator 或 exact-call cardinality check。能够证明的首个项目内结构性故障是：

- 12 次 Provider 调用均已 `ok/stop`，包括 Verifier；
- Verifier output 的本地 validator 若抛 `ValueError`，会被现有 `validate_post_node` 包装为携带 receipts/captures 的 `BoundedAgentExecutionError`；
- R7 实际 terminal type 却是裸 `ValueError`，且 canonical `failure_observation={}`；
- executor 在 Verifier 之后、adapter/runtime 成功提交之前仍有多个裸 `ValueError` 边界；
- runtime catch 只从 exception 的可选属性读取 observation，故裸异常使已经累计的 12 份调用观测全部丢失。

因此本轮不选择逐字段 patch，也不把问题归咎于 DeepSeek、Verifier schema、credential、网络或 Provider transport。

## 只读证据

- R7 result：`configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json`
- canonical SQLite 使用 URI `mode=ro` 读取，Run 共 7 个事件；失败事件 observation 为空。
- gateway ledger：12 started / 12 finished / 12 `ok/stop`，总 token 76,355，transport failure 0。
- 未读取 restricted Provider capture；未运行模型、Provider、网络、source 或外部工具调用。

剩余可达的裸异常族包括：

1. executor post-Verifier exact-call accounting；
2. adapter Artifact set validation；
3. runtime profile result / cross-Artifact validation；
4. runtime trace-event validation。

由于原始 message、safe failure code、phase 和 traceback fingerprint 均未持久化，不能在不新执行或猜测的情况下继续缩小。

## 选定合同

选定：

`fin01.bounded_agent.post_provider_failure_envelope:v1`

最小实现必须让“收到第一份 Provider receipt 之后”的整个 bounded lifecycle 都进入同一个 typed terminal envelope，覆盖：

- node envelope accounting；
- post-node validation；
- post-Verifier call accounting；
- execution Artifact assembly；
- adapter output conversion；
- profile Artifact ref binding；
- profile result validation；
- profile trace recording。

envelope 只保留 content-free allowlisted `failure_code`、lifecycle phase、observed counts、usage receipts、cost、restricted capture refs 和 completed node receipts；不持久化 raw output、private reasoning、credential、原始 exception message 或 stack trace。未知异常也必须映射为安全通用 code，同时保留 phase 与累计观测。

canonical `RESEARCH_RUN_FAILED` 必须接收这一 envelope。gateway 继续作为独立佐证，不能替代 canonical execution observation owner。

## 验收边界

未来最小实现需用确定性 fault injection 覆盖至少五个阶段：

- post-Verifier call accounting；
- Artifact assembly；
- adapter conversion；
- profile result validation；
- trace recording。

每个 fault 必须只 terminalize 一次，保存 typed phase/code；12-call fixture 必须保留 12 usage receipts 与 12 restricted captures；失败仍为 0 business Artifact、0 retry。成功 fixture 仍须为 6 logical nodes / 12 calls / 9 Artifacts。

不允许：

- 假定 exact-call cardinality 就是 R7 具体 throw site；
- 把 `str(exc)` 或完整 traceback 写入 terminal reason；
- 依赖 gateway 事后补账作为主合同；
- 放宽 Verifier、Artifact 或 profile validator；
- 重写 R7 admission、failure result 或历史 Run。

## 当前状态

- RC-P36-064：`root_cause_disposed_typed_failure_envelope_implementation_pending`
- R7：consumed / failed / immutable / no relaunch
- DELL R2：未证明
- paired assessment：失败后未授权
- S4-T06：未进入

下一项仅为：

`S4-T05-DELL-R7-TYPED-POST-PROVIDER-FAILURE-ENVELOPE-AND-CANONICAL-OBSERVABILITY-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该实现需要独立授权。本轮 runtime code changes=0，model/provider/network/source/tool/admission/Run/Artifact/paired/Human 均为 0。

## 验证

- 决策 SHA256：`ef2ed360b437d952efe8b68c939cbc5422fb4b8f9c092c4f11a3763072ce26a2`
- 新处置合同：`5 passed`
- 完整 S4 contract regression：`268 passed`
- Python compile：pass
- release JSON 与 Project OS JSONL：valid
- refined credential/secret scan：0
- `git diff --check`：无 whitespace error（仅既有 CRLF→LF warning）
