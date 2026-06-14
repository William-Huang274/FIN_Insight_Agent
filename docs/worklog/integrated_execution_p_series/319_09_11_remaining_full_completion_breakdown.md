# 319 - 09-11 剩余工作全量拆分与完成合同

日期：2026-06-14

## 用户问题

用户确认：当前是否已经把 09-11 文档规划全部做完。确认答案是否定后，用户要求继续把 09-11 剩余部分拆分成可执行步骤，做到真正全部拆分完，避免后续又出现“09-11 里面还有哪些没做”的隐性 backlog。

## 判断

上一轮 P0-P9 完成的是 operational bridge gate：Java Task Gateway、Python bridge worker、Workbench bridge、SQL eval store skeleton、path registry、resource scheduler、product surface gate 和 smoke。它证明 Python agent 可以经 Java/队列通路跑起来，但还不是 09-11 的完整产品闭环。

09-11 的完整目标仍包括：

- 09：Research Lead 常驻监督、LeadReviewCheckpoint、TargetedRepairPlan、role-specific selector、MemoLogicPlan、BGE 队列、ModelRouter / AgentCoalescer、Tool Capability Registry、Document / Multimodal Input。
- 10：企业级 SQL / Redis / ObjectStore、ContextEngine、Java/Spring 或 Java shell API productization、worker pool、SSE、恢复、压测、前端 trace/report/eval dashboard。
- 11：Eval Registry、dataset version、node/chain metric、failure lifecycle、gold lifecycle、retrieval/rerank eval、parser/chunker/table eval、LLM-as-judge 审计、online eval。

因此需要一个新的完成合同，把 L/B/F/EV/P 旧编号收敛成不会遗漏的执行编号。

## 完成工作

新增架构文档：

- `docs/architecture/agent_graph_vnext/13_09_11_remaining_full_completion_plan.zh-CN.md`

该文档把剩余工作合并成 R0-R12：

- R0 Baseline Freeze / Cloud Readiness
- R1 SQL / Redis / ObjectStore audit foundation
- R2 Eval Registry / Dataset / Failure / Gold lifecycle
- R3 Data / Index / Milvus / Parser quality gates
- R4 ContextEngine / Memory Runtime
- R5 Retrieval / Rerank / Resource Scheduler / ModelRouter
- R6 Tool Capability Registry / Document & Multimodal Input Pipeline
- R7 Research Lead Supervised Loop
- R8 Specialist Packs / Role-Specific Evidence Selectors
- R9 JudgmentState / MemoLogicPlan / Verifier
- R10 Backend Productization / Java-Spring Parity / Worker Runtime
- R11 Frontend / Workbench Trace / Eval Dashboard
- R12 Full-chain Regression / Online Eval / Release Gate

同步更新：

- `docs/architecture/agent_graph_vnext/README.zh-CN.md`：加入 13 文档索引，并把 13 的 R0-R12 gate 设为 09-11 后续完成口径。
- `docs/worklog/00_internal_master_checklist.md`：修正 P0-P9 状态，明确它们只是 operational bridge slice；新增 R0-R12 作为权威剩余 checklist。

## 关键门控

后续 09-11 只有在以下条件满足时才算完成：

- 每个 run 能从 SQL / object store 追溯 run、node、tool、model、evidence、claim、gap、gate、context、artifact。
- Redis 只做运行状态和队列，不做最终审计源。
- Milvus 只做 typed semantic recall supplement，不做 exact-value authority。
- Research Lead 能在 checkpoint 审核目标覆盖和缺口类型，并发起 targeted repair。
- Memo Writer 只消费 JudgmentState / MemoLogicPlan / verified ClaimCards / bounded gaps，不调用检索、数据库或联网工具。
- Eval Runtime 有 registry、dataset version、failure/gold lifecycle、node/full-chain metrics 和 dashboard/replay。
- 云端打开后先核对 Milvus 603 家 collection 和 GPU BGE scheduler，再进入 full-chain release gate。

## 结果

本轮是文档和治理拆分，没有改 runtime 代码，没有运行测试或 full-chain。后续执行时不应再按 09、10、11 分别实现，而应按 R0-R12 的依赖关系推进；任何新增或残留问题必须落入某个 R gate 的失败/补项。

## 下一步

用户开云端前本地先做：

1. R0 baseline freeze。
2. R1 SQL / Redis / ObjectStore audit foundation。
3. R2 Eval Registry lifecycle skeleton。
4. R4 ContextEngine 最小可用。
5. R6 Tool registry / document input parser skeleton。
6. R10 Java API / Python worker 与 R1 audit store 对齐。

云端打开后立即做：

1. R3 Milvus parity。
2. R5 CUDA BGE queue / scheduler smoke。
3. R12 1-2 个 full-chain 激活 case。
