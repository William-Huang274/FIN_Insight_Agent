# 758｜FIN 0.1.3 S1-08 外源 combined 零调用 Runtime 与权限就绪

日期：2026-08-09
状态：`zero_call_engineering_pass / clean authority pending`

## 1. 这一步解决了什么

在 DeepSeek query-atom 变体被拒绝后，本轮没有继续补模型字段，而是把确定性本地 Query Facet 接到两个真实执行面：

- 官方主路径：DELL、MU、NVDA 各沿用 v4 current-source Runtime 和每案 16 次网络上限；
- Firecrawl shadow：24 个关系感知、中英文 semantic query，每个最多 10 个 locator；
- 两条路径共享一个 exact-once admission、一次 terminal 和失败后的部分结果物化；
- 模型、embedding、rerank、Evidence promotion 均为 0。

统一计划从 36 个 Query Facet 编译为：

- 18 个英文 official plan；
- 24 个 Firecrawl shadow plan；
- DELL/MU/NVDA 共 12 个必需外源 case-slot opportunity；
- accepted model atoms = 0。

## 2. 权威边界

- 官方路径可以抓取、解析并由本地规则资格判断 candidate；
- Firecrawl 只发现 locator，不能提供财务事实、数字、发布日期或引用权威；
- 原始响应在解析前保存，失败输出只用于审计；
- 本轮不执行 Evidence Gate，不允许 Writer 引用 Firecrawl locator；
- target 不在 candidate pool 时保留 typed gap，不允许 reranker “救回”；
- 一个 lane 失败不得抹掉另一个 lane 已完成的结果；
- 401/402/403 只尝试一次 Firecrawl 网络调用，剩余 identity 继续物化为 typed terminal。

## 3. 工程中额外发现的问题

官方 v4 Runtime 还有一个 `market_expectation_context` 本地槽位。它使用本地 market snapshot、网络预算为 0，不属于本次 12 个外源 Query Facet。如果强制要求它绑定外源查询，正式 live 会在本地错误失败。

当前处理是显式记录 `local_market_context_zero_network_exempt` receipt，保持原查询和零网络语义；没有给它伪造外源 plan，也没有扩大外源范围。

这再次说明：统一查询合同不等于把所有 route 强行变成同一种查询。共享的是 identity、period、relationship、negative expansion 和 lineage，物理查询仍必须按 route 编译。

## 4. 验证

- 专项 full-fake/mutation：`10 passed`；
- 全部 S1-08 contract：`272 passed`；
- 三案 official terminal：`3/3`；
- Firecrawl shadow terminal：`24/24`；
- 系统性 403：真实模拟网络调用 `1`，terminal identity `24/24`；
- invalid JSON：raw response 先保存，再进入 typed parse failure；
- real provider/network/model/document/Evidence/embedding/rerank：`0/0/0/0/0/0/0`。

## 5. 当前没有证明什么

这只是 combined Runtime 的确定性工程证明，不是外源检索质量通过。尚未证明：

- 新 Query Facet 在真实 official/Firecrawl 上的 target-in-pool；
- 日期、来源多样性、typed gap 和每槽位有效候选质量；
- 内源 exact、BM25、dense/Milvus、graph 的召回；
- BGE、fusion、rerank 的增益；
- Evidence、Claim、Workpaper、报告是否真正消费检索结果。

## 6. 冻结的下一步

1. 将本实现提交并推送为 clean/synced 基线；
2. 在新基线上重物化 clean authority；
3. 最多签发一份 admission，执行一次 external combined exact-live；
4. 评估官方候选与 Firecrawl shadow 的 target-in-pool、日期、来源和 typed gaps；
5. 外源收口后立即进入内源：exact/SQL/object → BM25/ObjectBM25 → dense/Milvus → graph；
6. 用人工 qrels 证明 candidate ceiling 后，才比较 BGE、fusion 与 rerank；
7. 最后验证候选是否被 Evidence、Claim、Workpaper 和报告真正使用。

失败 live 不创建新产品版本，也不自动重跑。若是当前 adapter/parser/capture 缺陷，留在 S1-08 有界修复；若是来源不存在，保留 typed gap；若只是排序问题，只有 candidate ceiling 先通过后才能进入排序评估。
