# 120｜当前 DELL 动态单单元零调用循环

日期：2026-08-23

范围：DELL `value_capture`；0 模型、0 Provider、0 网络、0 付费调用；真实 current S1/S2 本地运行。

## 为什么需要这一门

旧 `dynamic_single_cell` runner 实质上仍是“Planner 一次、检索一次、固定片段继续”的伪多轮。它没有把 S1/S2 的成功、候选待审、typed gap 或工具失败反馈给模型，也不能证明模型会据此改变研究计划。当前门把动态研究的最小闭环固定为：模型选择 EvidenceRequest → Harness 执行 current S1/S2 → 返回已审 Evidence、typed NumericFact 和 FeedbackReceipt → 模型反思并提交 PlanDelta／GraphDelta／StopDecision → 必要时第二轮 → 工作底稿。

## 实际接通

1. 初始模型消息仅含问题、DELL 法定身份、`2026-08-06` 截至日和可用工具；没有 Evidence、数字、来源正文或标准答案 URL。
2. request catalog 从当前 12 条 owner-reviewed DELL 请求编译，覆盖价格／配置、台数、PVM、客户需求、供应链、价值池和反方七组命题。
3. 两轮均调用 `ResearchRetrievalService` 与 `ResearchEvidencePackService` 当前 Runtime；BM25、CUDA/FP16 dense、结构化查找与 S2 typed facts 走真实代码，不使用 fake retrieval。
4. 每轮只把本轮检索重新选中的 reviewed Evidence 暴露给模型；未审候选只生成待审反馈，不晋升 Evidence。
5. FeedbackReceipt 可驱动下一轮 PlanDelta；GraphDelta 只保存研究假设，不授予事实权威；StopDecision 在七组命题均被检查前不能宣称充分。
6. SessionEvent、checkpoint 和 resume 保存 Evidence、数字、gap、反馈、反方、开放问题与 authority refs；最终工作底稿使用当前统一 Specialist 合同。

## 零调用结果

- 2 个真实本地检索轮次；12 条请求各执行一次；
- 15 条去重 reviewed Evidence、17 个 NumericFact、9 个最终开放 gap；
- 20 条 FeedbackReceipt、2 个 PlanDelta、2 个 hypothesis-only GraphDelta；
- 最终确定性夹具为 `stop_sufficient`，仅表示 12 条路线都被检查并保留边界，不表示信息已经充分；
- RTX 4060 `cuda:0`，Embedding 与 Reranker 均为 FP16，CPU fallback 禁止；
- 跨公司、错日期、重复请求、过早停止、跨案 resume、请求排列变化六类 mutation 全部通过；
- checkpoint/resume 与最终 workpaper contract 通过。

公开结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_single_unit_zero_call_result_v1_0.json`。

私有完整结果：`data/workbench_private/fin_0_1_3_s3_dynamic_single_unit_zero_call/dell-dynamic-single-unit-zero-call-r8-20260823t2130z/full_result.json`。

## 本轮暴露并关闭的 Harness 问题

1. 动态 EvidenceResponse 代表完整已审返回，而 current consumer 会为单元容量确定性压缩模型视图。旧 binder 把“已审但未进入紧凑视图”误判为非法。现在两者分开记账：完整 reviewed authority 保留，模型只消费可见 Evidence；压缩必须有精确 omission receipt。
2. 零调用夹具手写了旧 Specialist workpaper schema。现在直接引用合同编译器常量。
3. 同一反方 Evidence 被多个请求命中时，checkpoint 曾重复记录。现在按不可变 ref 去重，不把复用虚报成多份来源。
4. runner 曾用不存在的字段检查 CUDA 与 resume receipt。现在严格按权威返回合同检查 `cuda:*`、双 FP16、无 CPU fallback 和 `resume_replay_verified`。

## 诚实边界与下一门

本轮证明 current 数据、S1/S2 工具、反馈、计划变化、图假设、停止和恢复的工程闭环；request／reflection／workpaper 内容仍是零模型夹具。因此自然 DeepSeek 是否会选对请求、理解反馈、形成有效 PlanDelta、避免因果越界并写出有内容的价值获取底稿仍未证明。

下一步必须是：完整回归 → clean commit／push → fresh Project OS preflight → 单独 authority → 一次 DELL `value_capture` natural live。只有该单元的 L1 与内容质量通过，才进入五单元动态 multi-agent。S1、S2 stage、S3、qualified-human、Workbench publication 和 release 均保持 false。
