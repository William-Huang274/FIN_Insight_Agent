# S3 R7：非思考交卷成功，但真实因果越界被拒绝

时间：2026-08-16  
阶段：FIN 0.1.3 / S3 / fixed-Pack Layer One

## 本轮真正证明了什么

R7 没有重跑 R6 已成功的五个节点，只执行一次 counter／WWC 交卷。DeepSeek 的非思考 profile 在 540 completion tokens 内返回一个完整 Tool Call，`finish_reason=tool_calls`；R6 的 reasoning budget exhaustion 没有复发。因此 RC-S3-022 的 provider profile 根因已经获得真实 live 闭环证据。

## 为什么仍然失败

模型选择了 `PROFIT_BRIDGE_GAP` 与 `not_inferable`，但在反方文字中又写成：公司毛利率回落“由低毛利 AI 服务器占比上升、其他分部组合波动或一次性因素驱动”。当前证据只说明管理层提到多项业务表现，并没有证明这些因素实际驱动本期公司毛利率。

本地 L1 guard 在同一个分句内找到了：

- 主体：AI 服务器；
- 财务结果：毛利；
- 正向因果词：驱动；
- 没有“不能判断／无法归因／证据不足”等否定或不确定边界。

所以这次 `claim_surface_narrative_relation_conflict` 不是 R4 那类误报，而是正确拒绝了一条真实越界。把 guard 放宽、删除“驱动”或由 Harness 替模型改写都会掩盖内容问题，不能采用。

## 暴露出的产品缺口

当前 Runtime 能发现错误，却还不能把机器可读的验证失败作为 Tool result 返回给模型，让模型在同一研究上下文内做一次有界修正。真实 Agent 不应每次可修正错误都由外部重新签发整链，也不应无限自动重试。

下一项只实现一个 provider-neutral repair turn：保存并回放被拒绝的 Tool Call，返回失败码与通用规则，只允许同一 fragment 在同一合同下重交一次；不增加证据、不放宽事实门、不重跑分析或前五节点。先做保存响应 replay、正负 mutation、完整终态 fake 和 fresh proof，再决定一次新 live repair。

## 当前边界

R7 是不可变失败证据，不能作为业务 Judgment。fixed-Pack L1、八维内容质量、动态 Truth Spine、五单元、异质泛化与 S3 acceptance 均仍为 false。
