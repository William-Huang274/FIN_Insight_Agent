# 847 — FIN 0.1.3 S2 selected-Evidence 数字共编实现

日期：2026-08-11

状态：working-tree engineering pass；双 clean proof 待执行；未调用 DeepSeek

## 业务结果

本轮把最终 selected Evidence 与数字权威改成同一次编译。DELL 的订单、AI 服务器收入、backlog、客户数、竞争对手增速、营运资金、供应时间、管理层指引和四个本地公式都能形成稳定 `NUM／FORM`；`$16.132B` 与官方 `$16.1B` 被认作同一事实的不同展示。完整原文继续私有留存，研究节点只看到有界且带标记的上下文，Writer 只能使用已授权展示，Verifier 通过后仍要经过本地数字门。

实现没有使用 DELL 数值白名单。相同编译器直接处理 MU／NVDA，以及主要只有 structured metrics 的 ORCL／ASML／ANET；EUR、台数、三个月／六个月和跨公司 read-through 都保留各自身份。

## 测试真正暴露的错误

测试不是一开始就绿。它先发现四个会影响报告内容的问题：

1. Dell 新闻稿把 `43.8B revenue`、`4.1B cash flow` 和 `2.1B shareholder returns` 写在同一句中，宽窗口曾把 4.1B 错贴成收入。现按数字所在微句绑定，4.1B 不再进入 total revenue。
2. Micron 把本季、上季和去年同期写在一个比较句中，旧逻辑把它们合并为同一期间后再判冲突。现显式解析季度、九个月、prior-quarter 和 prior-year 关系。
3. `gross margin increased 3%` 曾可能被解释为“毛利率等于 3%”。现独立分类为变化值；不清楚的同身份数字保持 context-only。
4. 本地最终门原来会因别处存在同字面 context-only 数字而拒绝合法 ref。现只允许 cited NUM／FORM 的精确展示，同时继续拒绝 `$4.1B`、`$43,842 million` 等错语义或错单位表面，即使 semantic Verifier 返回 pass。

## 验证和边界

- 新实现 focused：`10 passed`；相邻 Pack／changed-input／Verifier 回归：`27 passed`。
- 合并 Project OS／run-scope 回归后的最终相关集合：`52 passed`。
- 六案均 `conflict=0`，节点视图均低于 research/writer/verifier=`80k/55k/30k` 字符硬上限。
- model/provider/network/source/retry/admission=`0/0/0/0/0/0`。
- 尚未做两个 clean Git archive／fresh process 的逐字节复证，也没有自然节点 canary、DELL paid rerun、Owner acceptance 或 release。

另一个诚实边界是：当前叙事来源的精确数字坐标有一部分仍由 S2 的通用金融语义迁移 adapter 从已选正文恢复。它已经 fail closed 且不是 ticker 白名单，但长期更好的形态是由未来 S1 `FinancialSourceObject` 在 Evidence selection 时直接保存 selected numeric coordinates；该演进不在本轮重新打开 S1。

机器结果：`configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_cocompilation_minimum_zero_call_implementation_v1_0.json`。

下一步：提交并推送当前实现，然后只做两个 clean archive／fresh process 零调用证明；证明前不签自然 canary，也不重跑 DELL。
