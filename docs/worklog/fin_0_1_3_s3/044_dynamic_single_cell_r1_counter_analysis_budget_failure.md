# 044 S3 动态单单元 R1：第三片段分析预算耗尽

日期：2026-08-16
状态：R1 不可变失败；只允许失败节点 successor

## 这次真实跑到了哪里

这不是固定 Pack 重放。模型从 DELL 用户问题自然提出 10 个研究方向，本地按既定优先级执行 8 个、延期 2 个。当前 S1/S2 随后真实执行，返回：

- 6 条与当前 reviewed Pack 精确匹配的 Evidence；
- 10 个 typed gap；
- 108 个仍未复核的候选，全部留在候选层；
- 0 候选自动晋升、0 外源网络。

thesis 和 mechanism 的“分析＋严格交卷”四个节点全部完成并通过。业务上，模型没有为了完成任务强行写利好：

- thesis 认为现有材料无法建立 AI 优化服务器收入到分部／公司利润的可复核桥接；
- mechanism 只承认同财季公司整体毛利率下降这一观察，明确不能归因到产品或分部。

这两段目前未观察到新的金融 L1，但完整单元还缺 counterargument／WWC，所以正式 L1 和内容质量不能打通过。

## 为什么停了

第 6 次模型调用是 counterargument／WWC 的分析草稿。Provider 返回 HTTP 200，但 7,999 个 completion token 全部是 reasoning，`finish_reason=length`，可见草稿为 0。Runtime 因 `model_gateway_generation_budget_exhausted` 原子终止，没有进入第 7 次严格交卷。

这次不是网络、检索、数字、Evidence Gate、Tool Schema 或金融 Validator 的问题。它是第三片段在现有 8,000-token high-thinking 分析 profile 下不收敛。R1 的 5 个成功模型节点、完整请求和响应均已保存；不得重跑或把失败追认为成功。

## 有界 successor

下一步不再跑 planner、S1/S2、thesis 或 mechanism。稳定 runner 增加失败节点续跑能力，显式绑定 R1 public result、private full result 及 capture SHA：

1. 复用现有 GA agent profile，仅给 counter／WWC 分析一次 16,000-token max-thinking 机会；
2. 若形成可见草稿，再用已经验证的 non-thinking profile 做一次严格 Tool 提交；
3. 重新校验三片段、终态 Judgment 和 deliverable；
4. 0 retry、0 新证据、0 权限扩大、0 合同放宽。

若该分析再次耗尽，不再自动创建第二个分析 successor，而是进行模型/profile/动作面架构处置。
