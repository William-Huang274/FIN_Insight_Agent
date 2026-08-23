# FIN 0.1.3 S3：DELL current dynamic R5 合同成功与语义 L1 失败

日期：2026-08-23  
状态：`dynamic_research_and_submission_engineering_pass / L1_L2_fail / one_feedback_repair_design_pending`

## 1. 本轮做了什么

R5 没有重跑 R3 已成功的动态研究。它复用 R3 的三次 Provider 调用、两轮 current S1/S2、12 条请求、两份反思、PlanDelta、GraphDelta 和 StopDecision，只新增一次 non-thinking 工作底稿提交。

- Provider 调用：1；
- prompt：22,504 tokens；
- completion：3,778 tokens；
- finish reason：`tool_calls`；
- retry／外源网络／Candidate promotion：0；
- 严格 Workpaper 合同：通过。

这关闭了 R3 的可见输出容量问题和 R4 的 canonical Runtime 事件问题，但不等于金融判断通过。

## 2. 独立金融审查结果

R5 的公司专属性、反方和 WWC 明显强于旧固定底稿，但存在五项 material L1/L2：

1. 把管理层“盈利符合中个位数经营利润率目标”升级成可靠的实际收入→利润转化率；
2. 把截至 2025-10-31 的历史 AI mix 毛利解释用于截至 2026-05-01 的当前季度数字；
3. 在没有价值分配证据时断言 GPU/HBM 与客户拿走大部分价值、DELL 只保留低到中个位数；
4. 一边写公司经营利润同比增长 214%，一边写增量利润低于收入线性比例，混淆毛利与经营利润；
5. 把“关键部件营运资金风险”扩成 HBM/GPU 预购与交付后集中回款的具体机制。

因此 L1 和 L2 均失败。冻结八维 Rubric 要求 L1/L2 通过后才可正式评分，本轮只给适用单元诊断分 `16/24`；Q5 跨单元和 Q8 最终报告不适用。

## 3. 最早责任层

这不是新一轮 S1 检索失败，也不是 S2 数值错误：输入明确保存了 source period、management assertion、historical context、typed gap 和公司／产品边界。

最早责任层是 S3 语义权威闭环：

- `thesis`／`mechanism` 仍是自由长叙事；
- Validator 只验证引用是否存在，没有验证每个 material proposition 是管理层表述、历史上下文、确定性比较还是未证假设；
- R3 的 GraphDelta 可作为 hypothesis，但 R5 把其中价值池假设晋升成了业务结论；
- L1 失败没有在终止前变成 Agent 可消费的 FeedbackReceipt。

## 4. 有界后续

保留 R3 与 R5 不可变，不重新检索、不增加 Evidence、不提高 token：

1. 把五项 material finding 编译成 immutable semantic FeedbackReceipt；
2. 要求 Agent 先提交 PlanDelta，明确删除、降级或改期每个问题命题；
3. 只允许一次 workpaper-only repair successor；
4. 新底稿重新过 L1/L2 和单元适用内容质量；
5. 通过后才进入动态多 Agent。

这项修复的目标不是让 Harness 代写观点，而是让 Agent 能收到具体失败原因并自行修正研究结论。
