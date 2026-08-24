# S2 工作记录 009：产品价值桥进入 current 动态 Consumer

日期：2026-08-25

状态：`bridge_consumer_integration_pass / PVM_and_product_profit_fail_closed / S2_qualification_open`

## 1. 发现的真实接口缺口

工作记录 008 已有 digest-bound 产品价值桥，但旧 `dynamic_single_unit_loop` 只消费 Evidence、
NumericFact 和 gap，没有把该桥投影到动态 Agent 的 workpaper context。于是“桥已物化”与“Agent
实际能使用桥”之间存在产品接口缺口；仅看 S2 public result 会高估 current 能力。

本轮新增 `compile_product_value_bridge_context`，并由 R34 policy v1.1 精确绑定 task readiness、
quantitative result 和 product bridge：

- 校验 public result digest、source binding 和 fail-closed invariant；
- 向 round response、workpaper 和 submission 暴露 `13` 个 source numeric observations、`7`
  个 deterministic derivations 与 `4` 个 open bridge gaps；
- bridge 不创建 NumericFact，也不改变 S1 Pack；
- 当公司级 units／ASP／mix 或产品成本归因缺失时，PVM contribution、AI product operating
  profit 和 margin 必须继续为 `null`。

policy 的 TokenBudgetBasis 记录节点用途、输入规模、必需输出、schema burden、质量风险、可比
运行、reasoning profile 及停止／截断行为；本次 zero-call 不授予自然模型或付费调用权。

## 2. DELL R34 canary

R1 `dell-r34-s2-bridge-zero-call-r1-20260824t1636z` 在 post-runtime mutation gate 终止。
失败不是 S2 bridge、检索、CUDA、VRAM 或 Provider；旧 runner 仍期待 premature
`stop_sufficient` 抛异常，而 current controller 会保留 proposed decision 并把 effective decision
安全编译为 `stop_no_progress`。R1 assessment digest `d8882af9...f941191`，不得追认为成功。

同一根因在 single-unit 和 multi-agent zero-call runner 中修复，并增加未来 terminal failure
先持久化。R2 `dell-r34-s2-bridge-zero-call-r2-20260824t1644z` 从新 attempt 执行成功，public
digest `9cbdc308...b9fa5`：

- `12/12` EvidenceRequest、`7/7` proposition groups、`2` 个真实 current-runtime rounds；
- `15` 条 distinct reviewed Evidence、`17` 个 NumericFact、`9` 个 open gaps、`18` 个
  FeedbackReceipt；
- `2` 个 PlanDelta、`2` 个 graph hypotheses，终态 `stop_no_progress`；
- RTX 4060 `cuda:0`，embedding/reranker FP16，无 CPU learned fallback；
- mutation `6/6` pass，candidate promotion、network、model、Provider、paid call 全为 `0`；
- bridge 已到 workpaper；`target_company_pvm_calculable=false`、
  `product_profit_bridge_calculable=false`，所有对应数值仍为 `null`。

## 3. 能力与结论的区分

S2 现在具备把 reported fact、期间／单位、确定性公式、scenario 和 typed gap 编成产品价值桥，
并把桥交给动态 Agent 的能力。它可以精确计算当期 AI server revenue 相对 ISG/company revenue
的收入桥和 ISG margin reconciliation。

S2 仍不能在公开输入缺少 Dell 公司 units、ASP、mix 和 AI 产品成本归因时产生 PVM 或产品利润。
这是证据边界，不是 consumer 断线；`S2_pass=false` 和 product acceptance 继续保持 false。

R17 属于 S3 Writer 内容 successor，已由作者分离的 agent 复核通过；它不是 S2 数值资格证明，
也不是 qualified-human 签字。本轮没有 material finding，因此不创建 R18。
