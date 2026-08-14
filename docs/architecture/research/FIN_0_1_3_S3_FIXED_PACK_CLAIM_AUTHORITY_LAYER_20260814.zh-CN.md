# FIN 0.1.3 S3 固定资料包 Claim Authority 层

日期：2026-08-14

状态：`implementation_complete / formal_clean_proof_and_one_live_pending`

## 1. 为什么需要这一层

DELL `value_capture` Chat R2 已正确读取 reviewed Evidence、NumericFact、同口径关系、RoleMethodPack 和当前 GraphContextPack，也保留了 ASP、unit、PVM 三个缺口，但最终仍把公司／ISG 多因素利润改善升级为 AI server 的产品级利润贡献，并补写了没有来源的半固定成本机制。

旧合同能证明“用了哪些资料和数字”，不能表达：

- 结论讨论产品、分部、公司还是多个层级；
- 财务事实属于产品、分部还是公司；
- 两个层级之间是否存在直接、可审计的因果桥。

Prompt 和 Skill 已经明确提醒过这些边界，R2 仍越界，因此不能再只增加一段提示词。

## 2. 长期分工

模型继续拥有 thesis、mechanism、counterargument、what-would-change，以及 Evidence use 和 scope／bridge 选择。Harness 只从当前已审输入编译可选权限、校验不存在的直接桥、保存 receipt，并确定性渲染身份、期间、单位、数字和引用。Harness 不生成研究结论，也不把 DELL 的标准答案拼进报告。

## 3. 当前 successor

历史 consumer policy v1.2、research input v1.1 和 R2 结果保持不可变。新的 claim-authority overlay 只资格化同一份 DELL fixed Pack 的 `CELL::value_capture`：

- `claim_scope`：产品／分部／公司／多层；
- `financial_scope`：非财务／产品／分部／公司／多层财务；
- `causal_bridge_authority`：同层观察、管理层陈述、多因素上下文、桥不可获得；
- 当前没有 source-bound 产品到分部／公司直接桥，因此 `direct_cross_scope_bridge` 不进入 Tool Schema；
- 管理层产品盈利表述只能证明管理层做过该陈述；
- 多因素上下文允许同时讨论产品和公司事实，但不允许把公司利润分配给某一产品；
- 桥不可获得时必须保留 typed gaps 并对跨层因果结论 abstain。

## 4. 三层验收不能混淆

1. **固定 Pack 单元测试**：隔离模型在给定合格资料时的分析能力；0 动态检索，不能计作 Agentic Research。
2. **DELL 单单元动态纵切**：只给问题、身份、截至日和工具，让模型产生 EvidenceRequest，真实调用 S1/S2、接收 EvidenceResponse、继续或停止并完成判断。
3. **DELL 五单元动态案例**：五个研究单元都动态执行、相互综合，形成完整底稿和报告。

本轮 Owner 只批准第一层。第一层即使通过，也不能自动进入第二层。

## 5. 第一层停止线

- 使用与 R2 相同的 base research input 和 fixed Evidence Pack；
- 保存的 R2 Judgment 必须作为负向 replay 被新门拒绝；
- 一个信息量仍足够、但不做产品利润归因的正向 Judgment 必须通过；
- fake loop 只允许 Evidence／NumericFact read pair 和一次 Judgment，EvidenceRequest 预算为零；
- direct bridge、错 scope 组合和跨层强因果 mutation 必须 fail closed；
- 通过正式 clean proof 后只允许一次新的 DELL Chat canary，0 retry／fallback／retrieval／embedding／publication；
- live 后分别做 L1、内容质量和与 R2 的 paired assessment，再返回 Owner；不自动进入 Layer Two。

## 6. 首次自然运行结果

唯一一次 Chat R1 完成 2 个模型步骤：并行读取 Evidence／NumericFact，随后提交 Judgment；0 EvidenceRequest、0 retry、0 外源检索。模型自然选择 `product / product_financial / management_assertion_only`，不再把公司或分部利润改善归因于 AI 服务器，也移除了旧 R2 的半固定成本机制。

正式结果仍为 `terminal_failed_no_retry`。最早失败不是 causal scope，而是旧通用叙事门禁止汉字数字区间：模型复述 reviewed Evidence 明确允许引用的“中个位数”管理层目标，当前合同却没有 typed range／management-target alias。本轮因此证明 claim-authority 方向有效，但“来源允许引用的定性区间如何进入确定性数值表面”仍未闭合。

失败输出不得晋升。第二层仍 blocked。任何后续处置应先零调用建立 source-bound qualitative range／management-target alias，并把文本关键词式因果 guard 逐步替换为结构化 claim relation；这不改变模型对 thesis、mechanism、counterargument 和 WWC 的写作所有权。
