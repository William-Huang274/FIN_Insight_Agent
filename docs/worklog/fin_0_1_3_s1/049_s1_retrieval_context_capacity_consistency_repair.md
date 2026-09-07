# 049 S1 retrieval-context 容量一致性根因修复

日期：2026-08-19

状态：`earliest_selection_bug_closed / clean_formal_replay_pending / controlled_Evidence_successor_still_open`

## 问题

MU 当前候选中，take-or-pay／多年期具体数量约束对象已经同时具备：本案身份、当前期间、`direct_demand_signal`、`orders_and_backlog` facet，以及 `customer commitment and purchase structure` product binding。它仍未满足 direct requirement。

根因不是公开资料、Embedding、DeepSeek 或 Evidence Role，而是集合选择算法内部不一致：requirement 已把 orders／backlog／shipments 标为 `retrieval_context_only`，但候选增益仍把这些 metric 命中计入有限容量。排名更高的 shipment-only 候选先占掉唯一 reservation，真正的 commitment 对象随后无法进入，最终被错误记为 partial／incomplete。

## 修复

- `src/retrieval/evidence_set_coverage.py`：collective bundle 的 gain 与累计 coverage 只计算当前 requirement 的正式 required axes；context-only metric 保留为诊断观察，不参与容量竞争。
- `tests/test_s1_material_evidence_runtime_v11.py`：加入真实故障形状，证明高排名 metric-only 候选不能挤掉低排名 required-product proposition。
- 未修改 top-K、Embedding、Evidence Role、公开 gap、数字权威或 reviewed Pack；没有用 case-specific object ID 或 ticker 分支绕过选择器。

## 结果

- 定向：34 passed；全仓：760 passed；compileall 与 active baseline 169 Python／8 frontend／26 Runtime／0 forbidden 通过。
- MU dirty-tree 诊断：同一 customer-commitment direct requirement 从未满足变为满足；orders 请求完整 requirement 从 4／6 增至 5／6，剩余一项仍是真正缺少 HBM4 counter material，不被本修复伪装关闭。
- NVDA dirty-tree 诊断：5／8 material sets complete，与前一正式结果一致；无回归。
- 两次诊断均使用 Qwen `cuda:0`／FP16，CPU vector fallback=0，网络／生成模型／Evidence 晋升／NumericFact 新授权／public-gap 声明=0。

## 边界与下一步

本轮诊断从 dirty tree 执行，只用于证明根因修复，不覆盖旧 R4、不注册 current product 结果。代码与回归先形成独立干净提交；下一步在该提交上实现 proposition-bound Evidence successor，明确 accept／reject／delegate-to-S2 与 requirement binding，再以新的 attempt 重物化 MU／NVDA／DELL ProductReadiness。qualified-human、external blind、S1 qualification、动态 S3、发布与 release 仍未获得授权。
