# FIN 0.1.2 S4-T04 最终交付表面、正式 paired 与 Owner 请求

日期：2026-08-04

结论：RC-P36-118 已用零模型的 R3 九件套复放关闭；正式 paired L1–L4 已通过，当前只等待用户明确 Owner decision。没有执行 R4、模型、Provider、外网或 source 调用。

根因并不是缺少 renderer 能力，而是 S4-T04 exact-live 成功后没有消费仓库已有的 S3 final-delivery 模块。复用该模块并增加 current Evidence 合同后，最终 preview 已把 `__company_total__` 转为“公司整体”、`FY2025-FY` 转为 `FY2025`、财务数值加千分位并去除重复 `USD`，同时把已知英文 limitation 确定性本地化。未知英文限制项、numeric mutation、preview mutation、candidate 越权和 unknown Numeric ref 继续 fail closed。

current Evidence 不再要求 Agent 消费全部 15 条 approved Evidence；正确规则是“实际使用引用必须属于 approved pack”。三 Cell 权威覆盖为：Demand 和 Bottleneck 使用 promoted Evidence，Value/Profit 使用 exact Numeric authority 并带“数值不能单独证明因果”的限制，因此是 `2 evidence cells / 3 authority cells`，不是证据降级。

最终 preview digest=`0255e854...5521`，local verifier digest=`2211ef96...92d`，二者绑定；R3 原始 result SHA=`6f06be07...2fc9` 保持不变。零调用 deterministic baseline 使用同一 input digest、独立 Run/Artifact，formal paired 结果为 L1 pass、L2 pass、L3 limited material gain with finding、L4 pass。Agent 相比 authority-only baseline 增加 6 Claims、1 dependency、2 conflicts、3 gaps 和 9 WWC；但 9/9 WWC 仍使用通用阈值措辞，登记 RC-P36-119 并传递到 T08–T10/S5，不重新打开成功的 T04 模型链。

验证：历史/当前 T04 全集 `35 passed`；surface、formal pair 和历史产品表面复验 `10 passed`；另有 current integration `9 passed`、surface focused `8 passed`。所有证明均为零模型/Provider/外网。Owner acceptance 不得由 Codex 代签；推荐用户接受 current NVDA R2，同时把 RC-P36-119 作为后续质量 finding。
