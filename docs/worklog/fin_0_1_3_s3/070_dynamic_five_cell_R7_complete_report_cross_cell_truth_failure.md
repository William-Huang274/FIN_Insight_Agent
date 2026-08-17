# 070 DELL 动态五单元 R7：完整报告成立，跨单元真值验收失败

日期：2026-08-17

## 结果

R7 按既定 successor 范围完整执行：只新做一次 Value 修复交卷、一次综合分析和一次综合交卷，共 3 次 DeepSeek 调用；0 retry、fallback、协议切换、外源网络或候选晋升。R6 的 Planner、当前 S1/S2、四个有效 Judgment 和 Value analysis 均按 digest 复用。五个单元全部通过本地合同，workpaper、跨单元 synthesis 和内部 report 首次完整物化。

这证明稳定 runner、依赖权威编译、失败节点恢复和最终报告物化链已经工作。它不等于研究内容通过。

## 内容验收发现

本轮没有出现错公司、错数字、错引用、跨案事实污染，也没有把 AI 服务器直接归因为公司利润或现金。需求单元对订单、收入、backlog、供应紧张和提前采购的区分较好；修复后的 Value 单元也把判断严格限制在公司口径。

真正的 L1/L2 失败是“局部未见”被写成“全案未披露”：

1. Operating 单元称 AI 叙事只有全年指引，缺少当季实际 AI 收入；但其自己选择的 `EV::734A9C177164E08E` 明确写有当季确认 AI server revenue 161 亿美元和 AI orders 244 亿美元。
2. Counterevidence 单元称发行人未单独披露 AI 订单、积压或分部利润；同一 Evidence 已披露 AI 订单，当前 Case 的 `EV::9006E2D4E0F61CCF` 还披露 513 亿美元 record AI backlog。真正仍缺的是产品／分部利润桥，而不是订单或 backlog。
3. Synthesis 又把这条错误缺失升级成一个正式 cross-cell conflict，声称反方单元与需求单元冲突。真实需要裁决的不是“有没有订单/backlog”，而是这些已披露订单/backlog 的取消、提前采购、持续性和利润现金转化。

因此 R7 保持 `contract pass / financial truth and evidence reconciliation fail`。冻结 Rubric 规定 L1/L2 失败后不能进行正式八维通过评分；诊断分为 `21/32`，仅用于定位，不构成产品分数。qualified-human、DELL 五单元、MU/NVDA／留出泛化和 S3 acceptance 均为 false。

## 根因与边界

这是模型和项目结构共同造成的失败：模型忽略了自己可见且已选择的事实；项目合同则只校验证据 ref、数值、关系和 typed gap，没有把 `本单元视图未包含` 与 `当前全案确实不存在` 分成两种 typed authority。综合节点看到的是五个已经“结构有效”的 Judgment，而不是一份紧凑的全案 reviewed-fact presence／gap matrix，因而会把局部负面叙事继续放大。

该问题登记为 `RC-S3-038-cell-local-missingness-promoted-to-case-level-absence-and-false-cross-cell-conflict`。不能用“禁止未披露三个字”的正则、扩大 Prompt 或直接手工改报告解决，也不能继续运行 MU/NVDA 扩大错误面。

## 下一步

留在 S3，先做零调用跨单元真值收敛合同：从当前 reviewed Evidence、NumericFact、typed relation 和 gap 编译 case-level fact presence catalog；明确区分 cell-local visibility 与 case-level absence；综合输入增加紧凑 coverage/gap matrix；任何 conflict premise 与全案 catalog 冲突时 fail closed。先用 DELL/MU/NVDA 与留出 mutation 证明泛化，再决定是否只重交 Operating、Counterevidence 和 Synthesis。Demand、Value、Cash、Planner、S1/S2 和既有 analysis 不因本轮自动重跑。
