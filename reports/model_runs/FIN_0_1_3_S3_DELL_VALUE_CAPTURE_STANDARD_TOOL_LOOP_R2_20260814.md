# Model Run: FIN013-S3-DELL-VALUE-CAPTURE-STANDARD-TOOL-LOOP-R2

## 摘要

- 目的：验证修复后的 DeepSeek V4 Pro GA 标准四工具循环，能否在 DELL `value_capture` 单元中读取真实 Evidence／NumericFact、提出补证并提交 Judgment。
- 状态：`terminal_failed_no_retry / project_tool_schema_validator_compilation_drift`。
- 调用：2 个 exact-once Provider step，0 retry、0 fallback、0 外源检索、0 embedding、0 产品发布。
- 结论：R1 的 wire `index` 与安全只读并行缺陷已经关闭；R2 新暴露的是项目 Tool Schema 没有完整表达本地 EvidenceRequest validator 和 facet–metric 路由合同，不是 DeepSeek 无视指令。

## 实际业务过程

第一步，模型再次同时调用本单元的 reviewed Evidence 和 NumericFact reader。两者均成功执行，产生两份独立 receipt。模型实际看到了：

- Dell 已披露 AI server revenue、mix 与产品盈利方向；
- 当前证据明确缺少 AI server 出货量、ASP 和可复算的 price-volume-mix bridge；
- S2 提供了公司级收入、毛利、毛利率、营业利润与营业利润率，但这些数字不能冒充 AI server 独立利润桥。

第二步，模型没有急着提交结论，而是针对 `GAP::14D67654F535F105` 提出补证：寻找 Dell AI server unit shipments 或等价 compute capacity，以判断收入增长是 volume-led 还是 price-led。这一研究方向与现有缺口一致，业务上有价值。

## 为什么仍然失败

模型提交的一条 `product_intent` 为 222 字符；本地 policy 隐含上限为 120。Tool Schema 只写了“Concise”，没有 `maxLength`／`maxItems`，所以模型无法从机器合同知道准确边界。

这不是把 120 调到 222 就能解决。模型同时选择 `pricing_and_mix` 和 `shipments/capacity/orders/backlog`。当前路由规定 `pricing_and_mix` 只允许 revenue、gross profit/margin、operating income/margin 与 ASP；出货、容量、订单和 backlog 属于别的 query family。Tool Schema 却把全部 facet 和全部 metric 各自列为平铺枚举，没有表达两者依赖，因此“Schema 合法、Validator 不合法”。

此外，EvidenceRequest 只是 `proposal-only`，当前实现却让可修复的提案格式错误终止整个研究循环。合理的边界应是：保持 gap open、不执行检索、不晋升任何事实，返回 typed rejection 和受控的可选家族提示，让模型在原预算内修正；Judgment、身份、Evidence、NumericFact 和引用错误仍必须 hard fail。

## 决策

- R2 永久保留为失败；不重试、不追认。
- 禁止只增加字符上限或给 DeepSeek 做字段白名单。
- 下一项只允许零调用地统一 Tool Schema、Validator、fake 和 repair feedback 的编译源，并把复合研究意图拆成 facet-compatible EvidenceRequest atoms。
- 在 DELL/MU/NVDA fake、R2 capture replay 与 mutation 通过前，不签第三次 single-cell live；五单元继续 blocked。

机器处置见 `configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_standard_tool_loop_r2_disposition_v1_0.json`。完整内容留在受限 private result；公开 Git 只保存权限、终态、账本和不含私有推理的摘要。
