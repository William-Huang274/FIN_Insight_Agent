# FIN 0.1.3 S1-C1 查询、对象与数据库事实路由实现

日期：2026-08-12
状态：`engineering pass / S2 request Runtime consumed / S1 product gate open`

## 1. 这轮真正做成了什么

一条 `EvidenceRequest` 不再把所有关键词平铺到所有检索槽。当前 Runtime 先把请求拆为最多 11 类金融问题，再生成两种 sibling：

- narrative request：去 claim、表格语境、父级上下文和关系图中找机制、指引、风险、供需及关系证据；
- typed fact request：把指标、主体、期间、单位、截至日和粒度交给 S2 公司财务事实库。

两者由同一 request/cell identity 绑定，但权限不同。候选不等于 Evidence，fact request 不等于 NumericFact，表格行也不具备数值权威。

当前 11 类问题是：客户需求 read-through、已报告业绩、管理层指引、定价与价值获取、现金转换、供给／产能执行、直接关系归因、反方与风险、监管暴露、资本配置、估值。它们覆盖金融内核的全部 17 个 facet，且无重叠映射。

## 2. 为什么数据库没有被放到后面

`POST /api/v1/research-cases/{case}/retrieval-requests` 已能生成 24 类标准指标的 typed request，并根据显式 Runtime path 判断 source-bound 公司财务事实 mart 是否可用。不可用时仍明确返回：

```text
typed_fact_store_unavailable
owning_stage = S2
numeric_fact_authority = false
```

这不是“数据库失败后再走文本兜底”。可用时，S2 executor 返回 NumericFact、typed gap 或 typed conflict；叙事候选可以继续检索，但最终报告中的精确数值只能来自该权威路线。真实 DELL results／cash 请求已执行 6 个 typed fact sibling，6/6 resolved。PDF/HTML 表格仍只负责帮助定位和解释披露。

## 3. 旧 chunk 在业务上暴露了什么

对现有 DELL／MU／NVDA／相关公司 28 个 parent、1,805 个 child 做全库回放后：

| 项目 | 结果 | 业务含义 |
| --- | ---: | --- |
| 原始编译对象 | 22,765 | 重叠 child 会重复产出同一材料 |
| 去重后对象 | 20,340 | 删除了 2,425 个重复候选，但保留全部 source-record lineage |
| source-bound claim | 11,670 | 可用于叙事召回，尚未做 Evidence Role 判断 |
| metric-row | 7,500 | 带公司、来源、章节、表头、期间、单位、行组与行；仍非 NumericFact |
| bounded parent context | 1,170 | 只帮助理解，不可单独晋升为正 Evidence |
| 拒绝非金融数值表 | 228 | 高管年龄、职位等不再污染销售／业绩查询 |
| 金融外观但无安全指标行 | 52 | 不强猜表结构，保留诊断 |
| claim surface 不唯一 | 65 | 不建立无法精确回指的 claim |

标签复核又暴露并关闭了两个对象层根因：空的 `[TABLE_START]` 原先会被贪婪匹配一路吞到文末最后一个 `[TABLE_END]`，导致 TSMC 的领先制程需求和 2nm ramp 消失；同一张 Micron 业务单元表内多次出现 Revenue／Gross margin，原投影没有保留 Cloud Memory／Core Data Center 行组，数值可能被串到错误业务。当前空表边界已改为逐表最短匹配，metric-row 新增 `row_context_lines`。这只是检索定位语义，数值权威仍在 S2。

一个真实误判例子是 Dell 高管表：`Michael S. Dell | 58 | Chief Executive Officer` 曾因同表职位中出现 `Global Sales` 被弱关键词规则视为金融表。现在必须满足期间／单位表头或金融行标签门禁，这张表被拒绝。

## 4. 当前代码和产品消费者

- 路由合同：`configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json`
- typed route compiler：`src/retrieval/route_compiler.py`
- 对象编译器：`src/retrieval/object_view_compiler.py`
- 受维护构建入口：`scripts/data_retrieval/build_current_compiled_object_views.py`
- Workbench 数据构建消费者：`retrieval_build_current_compiled_object_views`
- 当前请求消费者：`ResearchRetrievalService` 的 request-scoped endpoint
- 零调用结果：`configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_zero_call_result_v1_0.json`

完整对象输出位于私有 Workbench 数据目录，不进入 Git；跟踪摘要只保存 digest、数量、边界和有限示例。Runtime Registry 已升为 R6，共 7 个当前资源；R6 更新了显式 reporting-period binding 的候选快照，不包含 private mart、qrels、模型输出或人工标签。private mart 通过 `RuntimePathRegistry.company_financial_fact_mart_path` 挂载。

## 5. 这轮没有证明什么

- 没有证明 20,340 个候选都高质量；下一轮要看它们在真实 query family 下是否召回正确材料。
- 公司财务事实 mart 和 request-scoped backend 已接通，但 S3 planner、报告研究消费和前端 NumericFact 消费尚未证明，因此 S2 产品门仍开着。
- 没有运行 BGE-M3、Qwen、Cross-Encoder 或 Evidence Role；也没有授权微调。
- 没有重新生成 Evidence Pack、DeepSeek 研报或关闭 S1。

## 6. 下一步

模型对照已经完成，结果不支持单一路线替换：Qwen 语义召回与 BM25 精确业务措辞互补，当前下一步是在 DELL 纵切中实现同硬过滤后的 `Qwen + BM25` 联合候选，并由 S3 受控 planner 产生真实 EvidenceRequest。S2 同时返回 NumericFact；先做零调用合同、污染和期间 mutation，再决定一次最小自然 canary。每项结果继续同时给出业务错例，不能只报 Recall/MRR。

## 7. 候选时间身份校正

当前 8-K earnings object 同时可能携带 SEC current-report date、filing calendar year 和公司实际报告的 fiscal year／period end。旧候选投影没有输出 fiscal year，导致 request-scoped 期间过滤把 DELL FY2027 Q1 叙事候选全部剔除。现在投影优先采用 `metadata.reported_fiscal_year` 和 `metadata.reported_period_end`，并在 `temporal_binding` 中保留原始 source-record fiscal year/date 及选择来源。该合同防止申报时间与业务报告期混淆，但不改变候选的非 Evidence 身份。
