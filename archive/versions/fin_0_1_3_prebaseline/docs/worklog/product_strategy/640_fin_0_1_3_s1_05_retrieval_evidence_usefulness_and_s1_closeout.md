# 640 — FIN 0.1.3 S1-05 retrieval/evidence usefulness 与 S1 closeout

日期：2026-08-06
阶段：`013-S1-05`；有界重开 `013-S1-03` semantic successor
结论：`S1 pass_closed`，下一项 `013-S2-01`

## 1. 为什么不能只看 accepted 数量

S1-04 完成后，旧链路表面上已有 current Numeric、official Evidence 和 Graph。但 S1-05 用真实本地索引和原始 accepted statement 复核后发现两个不同 owner 的问题：

1. S1-03 的 9 条 semantic Evidence 中，DELL demand 命中的是前瞻性声明/风险清单，DELL counterevidence 只是“详见 SEC 风险因素”，MU counterevidence 甚至是目录。这些行来源和摘要绑定正确，但不具备研究用途。
2. 旧 BM25 主索引虽有 89,112 条记录，却缺少 DELL FY2026 与 NVDA FY2026 年报记录；两案 current annual count 都是 0，MU FY2025 为 108。纯词法排序还会把 NVDA FY2024 demand 行排在 current 行之前。

因此“每个 query 都返回 6 条”不能证明 current recall，更不能把低质量关键词窗口交给模型自行修复。

## 2. S1-03 semantic usefulness successor

历史 R4、capture 和原 accepted row 均保持不可变。本轮只读复用 R4 已保存正文，生成 v1.1 successor：

- 7 条 `accepted_useful_current_official_evidence`；
- 2 条 `typed_gap_after_usefulness_review`；
- 0 次网络、模型或 Provider 调用。

关键更正：

- DELL demand：当前 bounded source 只有 revenue proxy 和前瞻性 demand 风险表述，不能冒充“已观察到的需求声明”，改为 typed gap；
- DELL counterevidence：替换为竞争压力、limited-source supplier 与 AI-demand sensitivity 的明确风险清单；
- MU counterevidence：从目录替换为“HBM demand 长期轨迹未知、需求可能波动、capacity shift 可能压低 DRAM pricing”的实质段落；
- NVDA counterevidence：当前 press release 只有泛化 forward-looking caution，没有特定已实现约束，改为 typed gap。

所有 accepted statement 仍绑定原 source/capture/parser/as-of，并新增真实来源发布日期；没有再把 research as-of 冒充 published time。登记并关闭 `RC-P36-136`。

## 3. current governed retrieval pack

FIN 0.1.3 不再把旧 BM25 snapshot 当 current authority，也不重写该历史索引。新 retrieval pack 对三案三个研究单元做确定性路由：

- semantic successor；
- current material Numeric program；
- DELL official exact AI-server/ISG 数值 successor；
- S1-04 authoritative relationship Graph。

结果：

- 9/9 query 均有 Evidence 或 typed gap 终态；
- 26/26 必需候选进入有界 candidate pack；
- 每 query ceiling=8；
- required-slot recall=1.0；
- selected candidate evidence utilization=1.0；
- false promotion=0；
- risk/counterevidence 三案为 2 条 accepted query + 1 条 NVDA typed-gap query。

value 单元三案均至少有 2 个独立 source URL。其他单来源单元不伪造 diversity，而是逐 query 记录例外原因。Graph candidate 固定 `relationship_fact_only=true / financial_fact_authority=false`。登记 `RC-P36-137`：对 FIN 0.1.3 三案，通过 current governed pack 与 legacy BM25 non-authority 关闭；通用主索引增量刷新不在本 repair closeout 中假装完成。

## 4. 工程反思

这一轮证明了三个不能混用的概念：

- source/capture 正确，不等于 statement 有研究用途；
- lexical top-k 有结果，不等于 current required-slot recall；
- Graph 有关系边，不等于多来源或财务影响证据。

后续检索验收必须预注册 positive slot 与 negative set，并明确区分 `accepted evidence`、`typed gap`、`source diversity exception` 和 `legacy non-authority`。模型不承担修复错误检索、错误日期或目录命中的责任。

## 5. 验证与阶段边界

negative/mutation 覆盖 cross-case、future date、stale annual substitution、目录命中、forward-looking caution-only、Graph→financial promotion、unknown slot 与 ceiling overflow。聚焦测试=`6 passed`，S0–S1 active suite=`76 passed / 1 historical event-time assertion deselected`；生成器重复执行 byte-identical。

S1 现可关闭，因为三案 current truth、material Numeric、official source、Graph 和 retrieval usefulness 都已有确定性终态，且 gap 未被伪造填充。但这不代表产品研究内容已经合格：

- Agent 是否真正消费这 26 个候选：未证明；
- 动态研究问题/方法合同：未实现；
- 八维研究内容质量 hard gate：未运行；
- Workbench current 产品重验、Human acceptance、release：均未开始。

下一项是 `FIN-0.1.3-013-S2-01-RESEARCH-QUESTION-AND-METHOD-CONTRACT-TRANSLATION-ENTRY-AUDIT`。先处理已登记的 typed metadata 漂移 `RC-P36-134`，再建立模型 surface；不得直接复用旧 0.1.2 exact-live acceptance。
