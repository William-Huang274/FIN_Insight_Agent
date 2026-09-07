# 078 Case Truth 两单元 natural R3：模型有用，但 flat-alias 语义门仍不可接受

日期：2026-08-17

Run：`FIN013-S3-CASE-TRUTH-SEMANTIC-SLICE-R3`

## 大白话结论

这轮四次 DeepSeek 调用都正常完成，两个分析都有可见内容，两个交卷也都返回 Tool Call；所以之前的连接、推理耗尽、2k 截断和 strict transport 问题都没有复发。

但产品语义门仍未通过。模型确实找到了 Counterevidence 中“订单未披露、积压未披露”两条错误，也看出了 Operating／Counterevidence 使用了本单元之外的现金流事实；这说明它不是完全不会做。问题在于当前任务要求它直接从一大组相邻金融 alias 中选唯一编号：它把“本季 AI 收入未提供”错选成了订单转换，把“没有产品到分部利润桥”错选成了宽泛的分部业绩；同一个跨公司存货 alias 还重复交了两次。

更重要的是，R7 中“mix、其他分部或 timing 仍未排除”属于一个尚未解决的因果假设。当前合同只有事实存在、事实缺失、typed gap 和跨公司背景，无法准确表达“相关材料存在，但这个因果解释仍未被排除”。继续加 Prompt 或扩大 token 不会补上这个产品语义缺口。

## 真实业务结果

- Operating 对收入、净利润、营业利润、毛利率和经营现金流关系的抽取大体正确；它也保留了产品利润桥缺失。
- Operating 没有命中最关键的“当季 AI server revenue 实际已经披露”alias，反而把该句映射到订单转换，因此第一条预注册 false absence 未通过。
- Counterevidence 正确命中 AI orders 和 AI backlog 两条 false absence；如果只看语义，它们会被本地 Case Truth 拒绝。
- Counterevidence 没有把“分部利润未披露”映射到 typed profit bridge gap，而选了宽泛的 segment performance facet。
- 两个单元都暴露了 R7 真实的跨单元写作：Operating 使用 Cash 单元的现金流 relation，Counterevidence 也使用该现金流事实。这不是模型误报，后续 Judgment 必须修。
- Counter 的同一 MU inventory context alias 重复两次，导致完整 receipt 未物化。只读内存去重后仍有 6 条 substantive finding，因此不能把 R3 salvage 成通过。

## 根因边界

本轮不是网络、协议、token、S1 检索、S2 数值或源文本编码问题。一次诊断输出曾因 Python stdout 为 GBK 而显示乱码；文件字节和模型可见请求均为正常 UTF-8，已更正，不登记为项目根因。

剩余问题分四类：

1. R7 原报告的真实 false absence 与 cross-cell scope；
2. DeepSeek 对相邻 alias 的选择精度不足；
3. grouped alias view 没有给每个 alias 足够独立的金融语义；
4. 当前 ontology 把“因果假设未排除”硬塞进 fact presence／gap，表达力不足。

## 处置

R3 保持 `terminal_partial_failed_no_retry`，自然 semantic extraction 不接受；不运行剩余三单元，不修 R7，不进入综合、DELL 验收或泛化。

按照此前“新架构级 L1 不进入 R4/R5 无限修补”的边界，下一步必须先做项目级决策：是把 proposition 抽取、命题类型和 alias resolution 分开并增加 causal-hypothesis 语义，还是把该语义 verifier 交给单独资格化模型／qualified human。任何路线都先零调用回放 R3、三案例与留出，再决定是否值得新的 live。
