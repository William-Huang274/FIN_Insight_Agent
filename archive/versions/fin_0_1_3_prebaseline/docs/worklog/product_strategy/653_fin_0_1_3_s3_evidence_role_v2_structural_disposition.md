# 653 — FIN 0.1.3 S3 Evidence-role v2 结构处置

日期：2026-08-06

## 结论

R1 继续作为旧 v1 合同下的真实失败保留，没有改写 terminal、重放或业务晋升。进一步审计表明，首项输出的金融研究语义并不荒谬：Dell 的收入事实可以被观察到，但不足以证明需求持续性。真正的结构问题是项目把“模型选择了相关观察”与“观察支持最终 thesis”都塞进 `support_aliases`，随后又禁止 `cannot_infer` 携带任何 support。

因此本轮没有继续扩大 prompt，也没有把失败归因为 DeepSeek 普遍不遵循指令。S3 新增 v2 successor：Provider 只选择 request-local Evidence、Counterevidence、Gap、Mechanism 与 What-Would-Change alias；本地确定性代码分配 `observation_support`、`thesis_support`、`boundary_only` 和 `counterevidence`。`cannot_infer` 可以保留观察事实，但这些事实只能进入 `boundary_only`，必须同时绑定 typed gap，绝不能晋升为 thesis support。

## 实现与验证

- S2 已关闭的 v1 合同和历史自然结果保持不变；修复只属于 S3 formal Anchor successor。
- 新增 Evidence-role v2 context compiler、validator、local claim materializer 与 v2 exact-once runner 路径。
- Claim Card 保留兼容 evidence binding，同时新增可审计的角色投影；角色必须完整、互斥并与所选 Evidence 一致。
- R1 原始语义映射到 v2 后，`DELL_E01` 正确成为 `boundary_only`，thesis support 为空。
- 九节点 full-fake 达到 `9 calls / 9 captures / 9 natural Claims / 3 all-natural Leads / 3 all-natural Workpapers / 3 quality entries`。
- missing typed gap、同一 alias 同时充当 evidence/counterevidence、角色投影篡改和跨合同 context 均 fail closed。
- focused S3 successor=`39 passed`；canonical active suite=`247 passed / 1 historical assertion deselected`；本项模型、Provider、网络、来源和业务运行均为 0。

## 边界与下一步

Evidence-role v2 是合同版本变化，不是产品版本变化，也不使 R1 变成成功。由于模型可见字段从 `support_aliases` 改成 `selected_evidence_aliases`，必须先做一个 fresh DELL demand 单节点自然 canary，不能直接花九次调用执行 R2。单节点通过后，才可单独签发九节点 replacement admission；完整链成功后仍需三案 L1/L2、八维评分、paired 和 qualified-human content acceptance。

当前 next：`ISSUE_ONE_FRESH_DELL_DEMAND_EVIDENCE_ROLE_V2_SINGLE_NODE_NATURAL_CANARY`。
