# FIN 0.1.3 S1-08：国内 Provider 输入资格与 comparator 范围决策

日期：2026-08-08

## 结论

本轮零调用资格审查通过，但没有直接签发 live comparator。新证据改变了接入顺序：

1. 腾讯 SearchPro 是 standalone raw-search API，返回 URL、标题、日期、摘要、站点、分数和 RequestId；官方没有披露 query 长度上限。它可继续作为国内候选，但聊天中出现过的 AK/SK 不得复用，必须使用新建且未暴露的凭据。
2. 百度千帆 `baidu_search_v2` 同样是 standalone raw-search API，并提供 URL、标题、日期、摘要、最多 50 个网页结果、最多 100 个站点过滤和明确日期范围；每月 1,500 次免费，后付费 0.036 元／次。它比模型内置联网问答更适合 FIN 的 capture-first locator lane。
3. 百度 query 上限只有 72 个计量字符，中文按 2 计；当前 60 条 canonical query 的加权范围为 `122–268`，`0/60` 可直接发送。强行调用会被截断，导致 owner、期间或关系方向悄悄丢失，横评结果无效。
4. 阿里百炼 Web Search MCP 与“模型开启联网搜索”不同：前者是独立 MCP 工具，可返回 `pages`，有 2,000 次免费额度、之后 29 元／千次。它可作为国内语义 lane 的第二候选，但必须先 capture 工具 schema，不能把千问联网检索 Agent 的合成答案混进 raw locator 指标。
5. Firecrawl 继续是无密钥控制，Exa 只保留国际语义基准。国内结算便利改变采购顺序，不改变 Evidence Gate。

## 为什么不能直接拿同一长字符串调用

“同一查询矩阵”应指同一 canonical `intent_id`、同一 owner／period／direction／source family 和同一 hidden target，而不是无视 Provider 明文限制、强行发送逐字相同字符串。正确分层为：

```text
canonical SearchIntent
 -> provider wire projector
 -> exact request bytes + capability fields
 -> raw response capture
 -> common normalizer and evaluator
```

provider projector 只处理传输：百度把站点和日期放入结构化字段，并把 query 压到 72 units；它不得重写经济关系或删除关键语义。语义开放网 lane 尽量保持完全相同短文本；官方精确 lane 可以使用各 Provider 的 site/date 字段，因为过滤能力本身就是被测产品能力。

## 零调用测量

- canonical intent=`36 precise + 24 semantic=60`；
- 普通字符范围=`76–268`；
- 按百度规则估算的 query units=`122–268`；
- 直接满足百度 72-unit 上限=`0/60`；
- provider/network/model/document/Evidence=`0/0/0/0/0`。

这不是 query compiler 失败。canonical object 负责完整、可审计的研究意图；wire projector 负责适配 Provider 的公开输入边界。若把 72-unit 限制塞回核心 SearchIntent，会把百度的当前约束污染所有 Provider，形成此前担心的 provider 专用迷宫。

## 下一项

`S1_08_DOMESTIC_PROVIDER_WIRE_PROJECTION_AND_FAIR_COMPARATOR_CONTRACT_ZERO_CALL_IMPLEMENTATION`

只实现：

1. canonical intent digest-bound 的 wire request；
2. 百度 72-unit deterministic projector；
3. site/date 结构化投影；
4. Tencent／Baidu／Alibaba MCP／Firecrawl capability profile；
5. 三案 fake、mutation、parity 与 36/24 独立预算证明。

通过后再签发具体 Provider 的 fresh admission。没有新国内凭据时可以执行 Firecrawl 控制，但不能把它说成国内主线完成；也不能复用聊天已暴露密钥。

## 官方依据

- 腾讯 SearchPro：https://cloud.tencent.com/document/product/1806/121811
- 腾讯计费：https://cloud.tencent.com/document/product/1806/121798
- 百度 Web Search：https://cloud.baidu.com/doc/qianfan-api/s/Wmbq4z7e5
- 百度计费：https://cloud.baidu.com/doc/qianfan/s/1mh4sv6c4
- 阿里 Web Search MCP：https://help.aliyun.com/en/model-studio/web-search-mcp

## 不成立的结论

- 没有证明 Tencent／Baidu／Alibaba live recall；
- 没有证明凭据有效；
- 没有运行 comparator；
- 没有抓正文、晋升 Evidence、训练 reranker 或进入 S3；
- 没有改变 FIN 0.1.3、S1-08 或 FIN 0.2 的版本／阶段归属。
