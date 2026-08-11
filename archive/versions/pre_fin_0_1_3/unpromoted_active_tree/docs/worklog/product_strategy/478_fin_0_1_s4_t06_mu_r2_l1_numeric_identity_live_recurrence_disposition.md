# FIN 0.1 S4-T06 MU R2 L1 数值与案例身份复发处置

日期：2026-07-29<br>
状态：零调用根因确认；唯一共享运行时安全闭包实现包待授权<br>
当前下一项：`S4-T06-MU-CASE-RUNTIME-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-SAFETY-CLOSURE-MINIMUM-ZERO-CALL-IMPLEMENTATION`

## 结论

R2 的五组错误数字与 MU 报告标题写成 NVDA，不是 source pack、网络或 transport 失败，也不能主要归因于 DeepSeek 不遵循指令。最早 project-owned failure 是 R2 admission 没有绑定已经存在的数值权威和案例身份 policy pair，运行时又把这组 L1 保护当作可选能力。

因此本轮不采用“给下一份 admission 补两个字段”的局部修复。选择一个且仅一个共享运行时安全闭包实现包；若该包不能一次闭合，则停止 Agent 数值交付范围，不自动增加第二修复包或 R3。

## 证据链

1. 已消费的 MU R2 admission 不含 `case_numeric_authority_policy_ref` 与 `case_delivery_identity_policy_ref`。
2. DELL R11 admission 明确包含这两个 policy ref，说明能力已存在但没有跨任务累积继承。
3. MU R2 fresh-proof generator 从旧 MU R1 admission 做 `model_copy`，只替换 admission identity、execution mode、input digest 和 Lead-v7；旧 admission 中缺失的 policy 被原样保留为缺失。
4. admission validator 只在任一 policy 字段出现时检查 pair；两者都缺失时仍可通过。
5. 若 pair 存在，当前 validator 又硬性要求 Lead-v6，无法表达 Lead-v7 fact-presence 修复与 numeric/identity safety 的合法组合。
6. runtime 只有在 admission 绑定 pair 后才会启用 Numeric alias、本地精确展开、Provider 数字 token guard、MU identity projection、pre-Artifact L1 和本地标题。
7. 因此 R2 没有启用这些保护：Specialist 保留了模型自由数字，Writer 没拿到 identity projection 并走到 NVDA 兼容 fallback。
8. 既有 full-fake/fresh proof 只验证 6 nodes、12 callbacks 和 9 Artifacts，没有验证 policy refs、manifest markers、最终 MU title 与最终 Artifact 数值 correspondence，形成 fixture/live path-parity gap。

## 唯一实现包

顶层合同：`fin01.s4.case_runtime_mandatory_material_truth_and_identity_safety_closure:v1`。

实现必须同时完成：

- 所有带 `s4_case_runtime` 的输入强制绑定 numeric + identity policy pair；缺失时在任何 Provider 调用前 typed fail；
- transport 组合改为按能力谓词验证，不再硬编码 Lead-v6；允许 Lead-v7 与现有数值/身份合同组合，但不偷偷继承 Lead-v6 gap-atom 行为；
- 新 admission 从当前 S4 mandatory safety profile 编译，不能再把旧 consumed admission 当作累积安全合同来源；
- 保留模型只选 numeric aliases、模型自由数字禁止、本地精确数值渲染和本地案例身份投影；
- 在最终 9 Artifact commit 前独立遍历全部 numeric/identity-bearing payload，复算 value、unit、period、segment、sign 与 issuer identity；机器 Verifier 绿灯不能覆盖 L1；
- S4 路径缺 identity projection 时硬失败，NVDA fallback 不可达；
- DELL/MU/NVDA fixture 必须使用真实最终 9 Artifact assembly 路径，验证 policy refs、projection digests、标题与 final L1；删除 policy 或突变任一最终数字/身份字段都必须失败。

## 范围边界与停止规则

本包只处理 admission safety closure、numeric authority、case identity、final Artifact L1 和 path-parity fixture。

不处理 dependency/conflict/gap 全面原子化、L2–L4 叙事质量、Sub2API strict-schema、换模型、新来源、T07–T10 或 S5。

最大实现包数为 1。若一个包不能通过全部零调用验收，下一步不是第二包，而是范围替换：确定性数值与身份核心保留，Agent 仅提供定性 overlay；若仍不能保证 L1，则阻断 Agent delivery。

## 本轮边界

- model/provider/network/source/tool：`0/0/0/0/0`
- runtime code changes：0
- admission/WorkUnit/Attempt/Run/Artifact：`0/0/0/0/0`
- paired/Human：`0/0`
- MU R2 与 9 Agent Artifacts：保持不可变
- R3、owner acceptance、T07：未授权

## 验证

- 新 disposition 合同测试：`5 passed`
- 完整 S4-T06 合同回归：`175 passed / 1771 deselected`
- JSON 与三个 Project OS JSONL ledgers：parse pass
- Python compile：pass
- 首轮完整回归的 17 个失败全部是历史合法后继白名单停在上一 disposition；只增加了本 implementation 后继，没有改 runtime、L1、预算或授权语义。

## 结果物

- 决策：`configs/releases/fin_ia_0_1_s4_t06_mu_r2_l1_numeric_identity_live_recurrence_root_cause_scope_disposition_v1_0.json`
- 合同测试：`tests/contract/test_fin_0_1_s4_t06_mu_r2_l1_numeric_identity_live_recurrence_root_cause_scope_disposition.py`
