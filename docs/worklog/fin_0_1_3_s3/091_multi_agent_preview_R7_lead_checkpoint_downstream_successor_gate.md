# FIN 0.1.3 S3 — Multi-Agent Preview R7 Lead checkpoint 下游 successor 门

日期：2026-08-20
状态：`zero_call_engineering_pass / one_R7_downstream_live_pending`

## 1. 这次没有重做什么

R6 的 terminal failure 保持不可变。六份 Specialist 自然规划、Lead 可见分析、continuation 和两次 strict submission 均不再调用。新 attempt 只复用 R3 Specialist checkpoint 与 R6 Lead plan checkpoint，并从六份角色底稿开始。

## 2. 剩余真实多角色拓扑

剩余模型节点上限从实际工作量编译为 15：六份 Specialist workpaper、一次 Lead 跨角色协调、最多三次反方修正、最多两轮独立评估、最多两次评估后局部修正，以及一份条件式 Writer 报告。复用的 Lead plan 不占新模型节点，也没有 TokenBudgetBasis；每个真正付费的下游分析和交卷阶段仍分别记录任务级依据。

## 3. 零调用证明

两个 checkpoint 经 digest、来源 attempt、capture 和拓扑重新校验后，当前本地 S1/S2 链重新物化出 12 个 EvidenceRequest、192 个候选、44 个 typed fact request（27 resolved／17 gap）、87 个 NumericFact。六个角色的 reviewed Evidence／NumericFact 视图均非空，blocking role 为 0。该 proof 为 0 模型、0 网络、0付费工具、0 Candidate promotion。

Runner 新增通用的 Lead-checkpoint downstream 模式：Research Lead 会话记录本地 `plan_bound` 事件和 checkpoint／predecessor run 引用，但不会把复用伪装成 Provider attempt。后续仍使用原有独立 AgentSession、analysis／submission 分离、FeedbackReceipt、checkpoint/resume、Evaluator 和条件式 Writer。

## 4. 边界

该门只授权一次全新 DELL R7 downstream Preview。它不改变现有研究输入，不访问外部来源，不晋升 Candidate，不签发 S1、S3、泛化、qualified-human、Workbench 发布或 release。即使运行形成报告，仍需单独做 L1、八维内容质量和人工内容验收。

工程与回归结果：新增门与旧 Preview 回归共 `69 passed`；全仓 `860 passed`（仅有本地向量库 SWIG 类型的两条既有弃用 warning）；`compileall` 通过；active baseline 保持 `184 Python / 8 frontend / 27 Runtime / 0 forbidden`；仓库 `7,400` 文件凭据扫描 `0 finding`；两份 Project OS JSONL 账本可完整解析；`git diff --check` 通过。

正式 authority 必须绑定该干净提交，且输出使用全新 Run／capture／private／public identity。以上工程结果只证明 successor 从正确 checkpoint、按正确预算和边界启动，不把尚未发生的自然角色输出提前记为产品能力。
