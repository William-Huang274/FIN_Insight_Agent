# 356 — FIN 0.1 S3-T09 Writer-v2、capture/terminal 修复与 fresh live 结果

日期：2026-07-23

用户授权继续修复，并在修复后执行一次真实调用。首先在 disposable clone 验证历史 orphan 的 typed closeout，再以零模型、零 Provider、零网络调用将 WorkUnit `wu_p02_5_faa27f97931244939f6daf3f`、Attempt `attempt_fin01_1de0ba5e8037f6d2953d1733`、ResearchRun `research_run_fin01_e418d7086d4a1d253e9b2c9b` 可信关闭为 `failed/failed/failed`。该 closeout 未伪造已丢失的 11 份回答、精确 usage receipts 或 Artifact。

修复新增显式 Memo Writer-v2 合同。Provider 只生成每个 Claim 的 `claim_id` 与 `analysis_text_zh_cn`；title、summary、section membership、status、scope digest、qualification、task refs、limitations、Lead/Claim surface digests、精确 ID 和零 source/tool calls 均由 runtime 从已验证上游确定性装配。Writer 失败现使用闭合的 `closed_memo_writer_output:v2` telemetry 和 canonical 可接纳的 `s3_bounded_` safe code；历史未显式设置 Writer transport 的 admission digest 保持不变。

同时新增 non-state-advancing `RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED` 事件。安全的 final-assistant text 先写 restricted object store 并绑定 Run，再执行 terminal failure telemetry 校验；因此终态观察被拒也不再丢失可复盘回答。读取路径支持从该 capture 事件回读，并拒绝 cardinality 或引用冲突。focused repair/capture tests 合计 `20 passed`；更宽的 S3-T09 non-live 选择集为 `229 passed, 30 failed`，30 个失败均是旧 backlog `next_action` 或历史 runtime count snapshot 断言，不是本修复路径的行为回归。

随后签发并 exact-once 消费全新的 Writer-v2 admission：

- admission digest：`1dc1b3290bf19bf73e0ad90cb8d5be3e1e60bf71bf151129c913894e93256885`
- WorkUnit：`wu_p02_5_821cee42568e9454078c5104`
- Attempt：`attempt_fin01_d2279356bce93fb0d4035953`
- ResearchRun：`research_run_fin01_76a7eace510a50091c351502`

真实执行在第 5 次调用、Value/Profit Specialist 的 claim-card 语义校验处首错停止。受限原文回放确认：fact authority 的精确 period token 为 `FY2025-FY`，fact-supported Claim `c2` 输出为 `FY2025`；entity、business scope kind 与 attribution 其余均一致。严格 validator 以 `s3_owner_grade_claim_scope_exceeds_fact_authority` 拒绝是正确行为，不能静默 normalize。

最终 WorkUnit / Attempt / ResearchRun=`failed/failed/failed`，orphan=false，Artifact=0；调用=`5/5/5`，tokens=`19055/2372/21427`，成本 USD `0.00968997`，retry/fallback/rerun=0。五份 final assistant outputs 均在 terminal failure 前完成受限持久化和 Run-bound 回读，usage receipts 与精确成本也已保留，证明 capture/terminal 修复在真实路径有效。

Writer-v2 因上游首错未被真实到达，只能标记为 fixture repaired、live reach pending。S3-T09 仍 blocked。下一项冻结为零调用
`S3-T09-OWNER-GRADE-SPECIALIST-CANONICAL-SCOPE-TOKEN-ZERO-CALL-ROOT-CAUSE-DECISION`；
未经新授权不得 normalize、patch、签发 admission、重跑、比较、Human Review、进入 T10、S4、release 或 production。
