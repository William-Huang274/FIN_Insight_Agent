# 754 — FIN 0.1.3 S1-08 Query Facet 三路对照 A/B 与查询原子 canary 实现

日期：2026-08-08

## 本轮回答的问题

统一 Query Facet 已能生成查询，但“结构更完整”不等于“真实检索更好”。本轮先在同一冻结 DELL／MU／NVDA 基础上比较用户原句和本地确定性编译，再把第三路 DeepSeek 限定为只提议查询原子；不让模型拥有最终 query、实体、期间、关系方向、来源、路由或预算。

## 零调用 A/B 结果

- 用户原句的平均 facet coverage=`0.138889`，36 个计划中重复 query rate=`0.916667`；它只表达三案总体研究问题，不能直接代表 36 个 evidence-owner／slot 查询；
- 本地确定性编译的平均／最小 facet coverage=`1.0 / 1.0`，跨案污染=`0`、重复率=`0`；
- 在冻结的英文 target-addressability 代理上，raw=`0/9`、local=`9/9`；这只证明目标所需的 owner／period／source-role token 已进入查询，不是 Provider candidate generation 或真实 recall；
- 10 个 canonical target 中有 `9/10` 个获得 case-slot direct owner route，六个 required slot 均至少有一个可接受 direct target；剩余的 MU customer→NVDA 目标由 NVDA 官方 owner route 提供全局 canonical opportunity，跨案使用仍需显式 role binding；
- 历史 Firecrawl capture 仍是 `24 query pools / 176 unique locators / 5 of 6 case-slot target-in-pool / 48 credits / p50 4006 ms / p95 6877 ms`。这些候选由旧关系查询产生，不能归因给 raw、local 或未来 DS variant。

## DeepSeek query-atom canary 实现

- 单次自然 canary 只可看到 18 个英文计划；最多 18 个 atom、每计划最多 1 个，也允许空集合表示本地 facet 已足够；
- atom 类型仅为 `metric / product / mechanism / synonym`；最终 query、URL/domain、identity/alias、period/date、relationship、source family、provider/route/filter/budget、Gold/qrel、金融事实和结论全部禁止；
- 通过本地 validator 后，atom 只能新增 lexical／semantic query；typed filters、identity、period、关系方向和路由保持 byte-level authority；
- exact-once runner 绑定 clean/synced commit、实现 SHA、policy、request digest、authority 与共享 admission ledger；最多 1 Provider call、1 transport attempt、0 retry、0 fallback；
- 可见 request、assistant content 和 gateway result 在校验前 capture；凭据／Authorization／Cookie 与 Provider 私有推理不保存；失败输出只作审计，不是 Evidence；
- fake/mutation proof 已覆盖：合法 atom 通过、空 atom 正常 abstain、未来期间／URL／实体别名／非法 kind／超长／duplicate／unknown plan／extra field fail closed、重复 admission 被共享 ledger 拒绝、私有推理递归剔除、自然非法输出 terminal failure 且不重试；
- proof status=`zero_call_implementation_pass_live_authority_pending`，proof digest=`12867a30560c2c1788f45d3318ce61a654fb43c95e6ebd151184b41c598f16c5`。本轮真实 Provider／network／natural model／document／retrieval／embedding／rerank／Evidence=`0`。

## 产品判断

当前本地 variant 已在冻结 addressability 代理上达到 `9/9`，所以 DeepSeek 的准入门槛不能靠“多了几个词”满足。唯一自然 canary 仍有价值：它检验模型能否在严格边界内识别真正缺失的行业术语，并允许诚实地返回空集合。若自然 atom 不增加可解释的 facet／后续 candidate recall，或增加污染、重复和不稳定性，就拒绝模型辅助，后续 combined live 使用 local-only Query Facet。

## 下一步与不遗忘项

1. 先 clean commit／push 当前 A/B 与 canary implementation；
2. 单独做零调用 authority decision，只签发 1 次 DeepSeek Pro query-atom canary；
3. 保存自然输出并重新完成第三路评估；不自动启用模型，也不自动进入 combined live；
4. 再决定 official routes＋Firecrawl shadow combined live；
5. 外源关闭后立即进入内源 exact SQL／object、BM25／ObjectBM25、dense／Milvus、relationship graph；
6. 扩大人工 qrels 与 hard negatives，证明 candidate ceiling；
7. 只有候选池通过后才评估 BGE、RRF／fusion 与 rerank，最后验证 Evidence／Claim／Workpaper／报告真实利用。

内源与 BGE／rerank 是已登记的 S1 后续，不是“有空再做”的备忘，也不能提前塞进当前外源 live。
