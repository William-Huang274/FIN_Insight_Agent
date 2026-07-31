# 361 — FIN 0.1 S3-T09 Specialist-v7 fresh exact-live 结果

日期：2026-07-23

用户以“继续”授权 exact-live execution。执行前 Project OS scoped preflight 与 exact runner preflight 均通过；执行进程局部设置 `LLM_GATEWAY_TRANSPORT_RETRIES=0`，admission digest `9657d30751eea5f24ea26b73fa9d93909b2df0c9966f96539a405a9dde1e72a6` 只消费一次。shell 等待超时后没有重发命令，而是只读轮询原进程和 canonical 终态。

真实 gateway events 证明第一 Cell 的三段调用均正常完成，调用为 `3/3/3`，tokens=`10375/1826/12201`，aggregate latency=29,566 ms，retry/fallback/rerun=0。由于 usage receipt 未传播，精确 cache split 和成本不可重建；按全部 input cache hit/miss 得到 USD `0.00162623..0.00610174`。

Specialist-v7 内层按 capability/profile 使用 8192-byte bounded assembly，三个 segments 装配与完整内层 validator 均通过；上一轮 Graph-as-Fact failure 未在第一 Cell 重复。但 outer executor 的 post-node revalidation 仍使用累计 `v5/v6` 版本集合，v7 回落到 legacy 6000-byte default，导致第一 Cell 在外层被误拒绝。由此可确定装配体在 6001..8192 bytes。登记 RC-P36-045；下一步必须把 outer consumer 收敛到同一 capability/profile，不应新增 `if transport == v7`。

outer 抛出的是裸 `ValueError`，绕过 bounded error 的 usage/capture 传播。canonical WorkUnit/Attempt/Run 仍可信地 terminalized 为 `failed/failed/failed`，orphan=false、Artifact=0；但 runner 错报 0 calls/tokens，三份 final assistant texts 和 exact receipts 未持久化且不可恢复。RC-P38-042 因 post-node capture/usage 丢失再次打开。

post-run 审计只使用 direct SQLite `mode=ro`、文件摘要与 gateway events，没有 service-backed target read。canonical counts=`14/14/14/13`，object tree 不变，source network/external tool=0。

S3-T09 仍 blocked。下一项冻结为
`S3-T09-OWNER-GRADE-SPECIALIST-V7-OUTER-ASSEMBLY-CAPABILITY-AND-CAPTURE-ZERO-CALL-ROOT-CAUSE-DECISION`；
未经新授权不得 patch、签发 replacement admission、真实调用、rerun、比较、Human Review、T10、S4、release 或 production。
