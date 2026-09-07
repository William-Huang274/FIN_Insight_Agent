# S1-C1 查询、对象与 typed fact 路由实现

日期：2026-08-12
状态：`完成工程实现与零调用全库回放；S1/S2 产品门均未关闭`

## 实施内容

1. 将旧七类查询校正为 11 类，并让 17 个 facet 各自只属于一个 query family。
2. 新增 provider-neutral route policy 和严格 loader；重复、缺失或未知 facet/metric route fail closed。
3. 将混合 EvidenceRequest 拆成 narrative request 与 typed fact request；两者共享 request/cell lineage。
4. 新增 source-bound claim、metric-row、bounded-context 编译器；表格行携带表头、期间、单位和父章节，但始终 `numeric_authority=false`。
5. 对 1,805 条当前 child 做完整零模型回放，识别并去掉 2,425 个重叠切块重复对象，保留 alternate lineage。
6. 修正真实发现的高管表误判；非金融数值表不再进入 metric-row 候选。
7. 将受维护构建入口接入 Workbench data-build catalog，并把 route policy 注册进 Runtime Registry R5。
8. 请求级 API 现在会显式返回 S2 `typed_fact_store_unavailable`；没有以文本表格代替数据库事实。

## 结果

- 11 query families / 17 facets / 24 metric routes。
- 28 parent / 1,805 child。
- raw objects 22,765；deduplicated objects 20,340。
- 11,670 claim / 7,500 metric-row / 1,170 parent context。
- diagnostics：228 nonfinancial table reject、52 no safe metric row、65 non-unique claim surface。
- 0 network / 0 model / 0 training / 0 Evidence promotion。
- successor 后全仓 Python tests `114 passed`；active baseline=`84 Python / 7 frontend / 7 Runtime resources / 0 forbidden reference`。

## 反思

旧 chunk 的问题不只是“长度不合适”。重叠 child 会让同一表格和段落在候选池多次投票；宽泛关键词又会把高管年龄表当成销售指标。若直接比较 embedding 或 reranker，模型可能只是学会旧对象噪声。对象级去重与金融表语义门因此属于模型对照前的必要数据合同，不是为某个模型加拐杖。

数据库路线也不能等到 S2 才第一次出现。S1 必须现在就把 exact metric/period/unit/PIT 变成 typed request；S2 再拥有事实表、刷新、单位、期间和 NumericFact 权威。当前 typed gap 是诚实产品状态。

## 下一门

`FIN_0_1_3_S1C2_SAME_COMPILED_OBJECT_MULTI_RETRIEVER_BAKEOFF`

在本轮 20,340 个去重对象上比较 BM25、BGE-M3 三模式和 Qwen Embedding；不改变 test-precut，不读取 gold identity 调参，不运行微调。标签回放已修复空表吞掉 TSMC claim，并为 Micron 重复 Revenue／Gross margin 行保留业务单元上下文；该上下文不授予 NumericFact。之后才进入同候选池 reranker 和 Evidence Role。
