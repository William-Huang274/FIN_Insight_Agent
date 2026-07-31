# 355 — FIN 0.1 S3-T09 Research Lead-v3 fresh exact live execution

日期：2026-07-23

用户授权一次 exact live execution。执行前 Project OS scoped preflight 与 runner zero-call preflight 均通过，并显式设置 `LLM_GATEWAY_TRANSPORT_RETRIES=0`。随后 admission `f4fede4d...b080` 仅消费一次，没有 retry、fallback 或 rerun。

三个 Specialist 的九个 segments 和 Research Lead-v3 全部完成；Lead-v3 在 1036/1800 output tokens、`finish_reason=stop` 下通过并首次把 live 路径推进到 Memo Writer。这证明前一轮 RC-P36-041 conflict-local direct-support 修复已跨过 live Provider 路径。

Memo Writer 同样正常 `stop`，但本地 owner-grade claim-surface validator 抛出 `s3_owner_grade_writer_claim_surface_violation`。Writer 原始回答没有 durable capture，因此无法确定它违反了 digest、exact ID/cardinality、cell membership、qualification、summary 或 limitations 中的哪一个子分支，禁止凭通用错误码猜测。

失败 closeout 又暴露第二个项目内缺口：canonical secret-safe failure code 只接纳 `bounded_agent_` 和 `s3_bounded_`，而 Writer validator 返回 `s3_owner_grade_`。`fail_research_run` 在持久化 provider output captures 之前先拒绝 failure observation，导致 WorkUnit / Attempt / ResearchRun 保持 `running`，0 Artifact、0 terminal event，本 Run 的 11 份 final assistant outputs 也未落盘。

精确调用为 11/11/11，45,128 input + 6,801 output = 51,929 tokens，receipt latency 合计 90,541 ms。由于 cache hit/miss usage receipt 与回答一同未 durable persist，精确成本不可恢复；按全 hit 到全 miss 可重建区间为 USD 0.00608044–0.02554755，上界仍低于 USD 0.10。关闭阶段未新增模型、Provider 或网络调用。

S3-T09 继续 blocked。下一项冻结为需另行授权的
`S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-WRITER-CLAIM-SURFACE-AND-ORPHANED-RUN-ZERO-CALL-ROOT-CAUSE-DECISION`；
当前不授权 validator patch、capture/telemetry repair、typed closeout、replacement admission、rerun、comparison、Human Review、T10、S4、release 或 production。

收口验证：当前/历史 result、issuance、capture persistence 与 authority contracts 共 `18 passed`；Project OS scoped closeout preflight pass、open blocker=0；gateway event lines 保持 106，新增 model/provider/network call=0。一次更宽相关 suite 超过桌面等待时限后仅终止本地 pytest 进程，不涉及模型或 canonical 写入，随后以聚焦 suite 完成可重复验证。
