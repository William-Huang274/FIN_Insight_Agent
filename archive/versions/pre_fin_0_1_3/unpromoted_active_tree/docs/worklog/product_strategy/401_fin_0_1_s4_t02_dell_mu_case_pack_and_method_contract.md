# FIN 0.1 S4-T02：DELL/MU Case Pack 与金融方法合同冻结

日期：2026-07-26
状态：`S4-T02 pass_zero_call`；`S4-T03 pending separate authority`

## 授权边界

用户在已明确下一步仅为 `S4-T02-DELL-MU-CASE-PACK-AND-FINANCIAL-METHOD-TO-RUNTIME-CONTRACT-DECISION` 后回复“授权”。本次只允许：

- 冻结 DELL OEM 与 MU HBM exact Case Pack；
- 把对应金融研究方法翻译为既有 Runtime 的命名消费合同；
- 更新 Project OS、backlog、方法注册表、文档和合同测试。

本次不允许也未执行 Runtime/fixture 实现、模型/Provider/网络/来源/外部工具调用、canonical Case/Run/admission/业务 Artifact、付费 canary/exact-live、Human review、qualified-senior R3、S5、Alpha/release/production。

## 冻结结果

| 对象 | 结果 | SHA-256 |
|---|---|---|
| DELL OEM exact Case Pack | `contract_translated_exact_case_pack_frozen` | `71e7fb3ba56275760f0d2b84006d30fd192a15ad9be234740dc336cd4a15217e` |
| MU HBM exact Case Pack | `contract_translated_exact_case_pack_frozen` | `0de20e119e3ab78b273b96895f7fb7070da24b6c35122daa53d94d522edb2612` |
| financial method → Runtime contract | `contract_translated` | `740d3da108e4bf0082eeea47cb9fdbf84d0e992fe20b3db86967dc3336cc5c53` |
| S4-T02 decision | `pass_zero_call` | `3abcb72ffdc3b90666e68baf009a5d36b8d118e082b1d8c6b36915c9f4a9ba9b` |

两套 Case Pack 都复用 S3 已证明的 `Fin01ResearchRuntime`、三 Cell、input v1 和 output v4，不创建平行 Runtime。它们只冻结研究问题、Evidence/Numeric/Graph/判断原子合同、typed cannot-infer、停止规则和 what-would-change；Evidence、Numeric、Graph、Claim、Judgment、预接受结论均为空。

新增方法：

- `s4_dell_oem_order_to_revenue_and_working_capital_playbook`
- `s4_mu_hbm_supply_pricing_and_cycle_playbook`

方法合同指向 7 个既有消费面：Evidence route、Financial Numeric、Bounded Graph、Specialist/Research Lead、Bounded Agent input/execution、Writer/Verifier/review、Workbench projection。当前生命周期只到 `contract_translated`；没有 fixture、Runtime injection 或 node-level consumption 证据。

## 方法与质量边界

- DELL 必须把订单/积压/部署信号连接到公司特异性、收入转换、利润捕获、营运资本和现金转换，不能把公司或宽分部经济性分配给 AI server。
- MU 必须把结构性 HBM 需求与 memory-cycle、库存、定价、产能、良率、客户集中和监管风险分开，不能从行业增长、CapEx、同业或 Graph context 推导 MU 的 HBM 收入、利润、出货、良率或客户份额。
- 模型未来只返回小型判断原子、引用和枚举；本地 Runtime 负责 ID、scope、ClaimFactLink、lineage 和 Artifact 组装。
- Graph 只作为导航或假设上下文，不能成为直接 Evidence；Numeric 必须精确绑定 issuer/segment/period/currency/unit/formula。

## 根因处置

`RC-P36-055` 从 `open_zero_call_preexecution_contract_decision_pending` 推进为：

`case_packs_and_method_contracts_frozen_T03_runtime_injection_and_node_consumption_pending`

它仍是 full-chain blocker。这是项目内 method-to-runtime 生命周期缺口，不是模型质量问题。

## 验证

- 4 个新增/更新的 JSON 合同均通过解析，三个 Project OS JSONL 注册表/账本逐行解析通过。
- 新 T02、S4 entry、S3→S4 cross-slice、S3 closeout、T09 layered acceptance 与 T08 相邻回归合计 `46 passed`。
- 相邻 S3-T08 测试中的旧错误名断言由 `exact_six_node_budget_required` 对齐为 Runtime 已使用的 `exact_call_budget_required`；仅修正测试预期，不改变 Runtime 行为。
- 本次真实模型、Provider、网络、来源、外部工具、canonical Case/Run/Artifact 与 Human review 均为 0。

## 下一步

唯一下一项为：

`S4-T03-THREE-CASE-IDENTITY-LEAKAGE-AND-NODE-LEVEL-DETERMINISTIC-PREFLIGHT-IMPLEMENTATION`

T03 需另行授权，并保持零付费调用：实现 Case Pack schema/digest loading、issuer identity binding、case-local fixture/profile、7 个消费面的 method injection、node-level judgment atom consumption、fake Provider 六逻辑节点/九 Artifact shape，以及 NVDA/DELL/MU/SaaS/Bank 的 identity 与 fact-leakage 负例。T03 通过前不得进入任何 paid canary、admission 或 exact-live。
