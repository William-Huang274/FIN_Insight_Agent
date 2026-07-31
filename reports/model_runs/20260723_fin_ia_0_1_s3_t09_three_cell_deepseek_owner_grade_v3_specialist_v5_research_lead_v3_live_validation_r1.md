# FIN 0.1 S3-T09 Specialist-v5 + Research Lead-v3 live validation R1

执行时间：2026-07-23 14:37–14:39（Asia/Shanghai）

结论：未通过，且不是 token 预算问题。Exact admission 已消费一次；三个 Specialist 的九段输出和 Research Lead-v3 均完成并通过本地门禁，执行首次到达 Memo Writer。Writer 返回 `finish_reason=stop`，但在 claim-surface 语义校验以 `s3_owner_grade_writer_claim_surface_violation` fail-closed。随后失败终态写入又因该代码使用 `s3_owner_grade_` 命名空间、不属于 canonical 仅接纳的 `bounded_agent_` / `s3_bounded_` 命名空间，被 `research_run_failure_observation_not_secret_safe` 拒绝，最终留下 WorkUnit / Attempt / ResearchRun 均为 `running` 的 orphaned Run。

## 精确执行事实

- Admission：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-research-lead-v3-exact-admission-r1`
- WorkUnit：`wu_p02_5_faa27f97931244939f6daf3f`
- Attempt：`attempt_fin01_1de0ba5e8037f6daf3d1733`
- ResearchRun：`research_run_fin01_e418d7086d4a1d253e9b2c9b`
- Provider / model：DeepSeek / `deepseek-v4-pro`
- 调用：11 model / 11 provider / 11 network；11 次 transport attempt；0 retry、0 fallback、0 rerun
- 节点：9 Specialist segments + 1 Research Lead + 1 Memo Writer；Verifier 未调用
- token：45,128 input + 6,801 output = 51,929 total
- 所有 11 次 provider completion 均为 `finish_reason=stop`
- latency receipt 合计：90,541 ms
- 成本：因失败 telemetry 和 usage receipts 未持久化，cache-hit/miss 拆分不可恢复；可重建区间为 USD 0.00608044–0.02554755，上界仍低于 USD 0.10 admission ceiling

## Canonical 与持久化事实

- WorkUnit / Attempt / ResearchRun：`running / running / running`
- 本 Run 只有四个开始事件，没有 terminal event
- Artifact：0
- 本 Run 的 11 份 final assistant outputs 在内存中形成 capture，但 `fail_research_run` 在写对象前先做 failure observation 校验；校验被拒后，本 Run 新增 capture object 为 0
- 因而 Writer 的具体 claim-surface 子分支和精确 cache token 拆分不能从 durable state 复盘；禁止猜测
- 原始 HTTP envelope、credential、private reasoning 均未持久化

## 产品判断与边界

本轮正向证明了 Specialist-v5 与 Lead-v3 已能真实到达下游 Writer，RC-P36-041 的 conflict-local fact-presence 问题没有复现。但没有形成任何研究 Artifact，不能进行 paired comparison 或 owner acceptance，也不能声称形成 junior analyst 交付。

下一项只能是需独立授权的零调用根因决策：
`S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-WRITER-CLAIM-SURFACE-AND-ORPHANED-RUN-ZERO-CALL-ROOT-CAUSE-DECISION`。
该决策需要分别确定 Writer typed subtype / contract owner，以及 failure namespace、capture-before-validation 和可信 typed closeout 的修复边界；不得自动 patch、close orphan、重跑或签发 replacement admission。
