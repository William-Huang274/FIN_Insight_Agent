# 849 — FIN 0.1.3 S2 数字视图最小自然节点 canary 零调用决策

日期：2026-08-11

状态：决策完成；只授权 canary 零调用实现与 clean proof；未调用 DeepSeek

## 为什么还需要一个自然 canary

双 clean proof 证明新数字控制面在干净代码和新进程中可重复，但没有证明当前 DeepSeek 会自然遵守新的 bounded view。直接重跑 13 节点 DELL 报告会把 S2 合同、S3 内容质量和 S1 残余资料重新混在一起，成本更高，也难判断失败属于哪一层。

因此本轮选择一个最小但有真实业务含义的 DELL 需求判断：E022 提供本季订单、AI 服务器收入、backlog 和客户广度；E018 提供同业订单消化 read-through；E023 提供提前备货／pull-forward 边界。模型必须形成支持、反方和边界三个判断原子，不能写完整报告。

## 为什么这个节点最合适

它会故意要求使用此前交付门漏编、现在已获得权威的 `$16.1 billion` 和 `customer count surpassed 5,000`，再使用 `$24.4 billion` 订单或 `$51.3 billion` backlog 中至少一个。这样一次调用就能观察：模型是否使用合法展示、是否带正确 NUM／Evidence refs、是否把 issuer support 错当独立反证，以及是否承认订单／收入／客户数仍不足以证明取消率、转化率、客户集中度、产品利润和长期需求。

本项继续使用当前 formal profile `deepseek-v4-pro`。它不是 Flash／Pro A/B，也不评估最终写作风格。选择当前 formal profile 是为了只改变 numeric view 这一项变量。

## 执行边界

本决策没有实现 runner、没有签发 admission，也没有模型、Provider、网络或 source 调用。下一包需先注册独立 zero-call scope，编译三条 Evidence 的精确输入，实现 capture-first exact-once runner 与本地结构／角色／数字门，并完成 fake、mutation 和双 clean proof。全部通过后才能另行决定是否签一次 1-call live authority。

即使未来 canary 通过，也只能再决定 DELL 全链是否值得，不会自动执行；失败则保留 capture、零 retry，优先缩小 DeepSeek profile 的自主面或让本地展示接管，不能把失败逐字段写进 provider-neutral 核心。

机器决策：`configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_zero_call_authority_decision_v1_0.json`。
