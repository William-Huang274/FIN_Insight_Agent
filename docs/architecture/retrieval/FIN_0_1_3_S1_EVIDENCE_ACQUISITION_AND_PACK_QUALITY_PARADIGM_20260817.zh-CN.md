# FIN 0.1.3 S1 证据获取、反驳补证与 Evidence Pack 质量范式

日期：2026-08-17

状态：`architecture_decision / runtime_not_implemented / read_only_audit_next`
产品依据：`docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md` 16.38–16.39

## 1. 为什么需要本范式

当前 S1 已有对象库、BM25／dense／reranker shadow、请求级 Query Atom、受控 Source Intake、官方 PDF 入库、Evidence Gate 和 reviewed Pack 同步。它们分别证明若干部件可运行，但没有共同证明下游模型取得了完成当前研究任务所需的充分材料。

已观察的业务事实包括：

- DELL 候选能找到订单、收入、backlog、营运资金与部分供应背景，但产品利润桥、ASP／PVM、供应分配／容量释放时点和估值仍是 material gap；
- MU 仍缺产品级 HBM／AI 收入、订单、利用率／良率、客户分配及完整周期桥；
- NVDA 候选中风险、联系人和通用披露曾压过当期结果、需求和供应机制；
- dense／reranker 能补充 BM25 漏项，但也会把主题相近、证据角色错误的材料推到前列；
- S3 能记录补证提案，但过去多条路径停在候选或 reviewed-only response，模型没有获得“检索—评估—发现残余缺口—反驳—再检索”的闭环。

因此，S1 的交付物不应定义为“若干候选”或“若干抓取成功网页”，而应定义为对当前研究命题可审计的 Evidence Pack Readiness。

## 2. 阶段责任

### 2.1 S3 提供给 S1 的输入

S3 负责表达：

- 当前 Research Objective；
- 待判断 proposition／hypothesis；
- 为什么该问题对用户决策重要；
- Evidence Need：需要支持、限制、反方、替代解释还是数值／因果桥；
- 允许的资料时间和任务深度；
- materiality 与停止优先级。

S3 不直接指定标准答案 URL，也不拥有候选晋升权。

### 2.2 S1 的责任

S1 负责：

- 将 Evidence Need 编译为身份、期间、关系、来源和预算均受约束的 QueryFacetPlan；
- 从内源文本、结构化事实、关系图、官方来源与外源搜索生成候选；
- capture-first 保存来源，再做解析、对象化、排序和 Evidence Role 判断；
- 形成 accepted／rejected／needs-human-review／typed-gap 的 EvidenceDecision；
- 维护命题级 EvidenceCoverageState；
- 将真正 material 的 residual gap 和 counter-hypothesis 返回给 S3；
- 在补证无增量、来源不可达或证据边界不足时给出 typed stop，而不是制造 Evidence。

S1 不负责写最终 thesis，也不能把模型建议、搜索摘要或候选排名当成事实。

### 2.3 S2 的并列责任

S2 继续独立提供 NumericFact、period／unit／PIT、公式和 product-to-financial bridge 状态。文本检索可定位披露，但不能替代 S2 数值权威。S1 Pack Readiness 必须引用 S2 的 resolved／gap 状态，而不能从文字自行抄数。

## 3. 标准数据流

```text
Evidence Need
  → EvidenceRequest
  → QueryFacetPlan
  → route-specific queries
  → capture-first source acquisition
  → parent/claim/table/context objects
  → sparse/dense/graph/SQL candidate union
  → structural filtering and ranking
  → Evidence Role / directness / owner / period evaluation
  → EvidenceDecision
  → proposition-level EvidenceCoverageState
  → material gap or counter-hypothesis
  → bounded supplementary request
  → EvidencePackReadiness
```

该流转允许多轮，但每轮必须有明确的 gap、预期信息增量和停止条件。不得用“继续搜索”作为默认动作。

## 4. Evidence Need 与 CoverageState

每个 material proposition 至少表达以下需求中的适用项：

- `direct_support`：研究主体或权威来源的直接事实；
- `bounded_readthrough`：客户、供应商、同行或行业的有界外部印证；
- `counterevidence`：足以削弱、反转或限制命题的材料；
- `alternative_explanation`：同一现象的其他经济机制；
- `numeric_observation`：S2 权威数值与同口径关系；
- `causal_or_financial_bridge`：从产品／经营信号到收入、利润或现金的证据桥；
- `what_would_change`：后续可观察、可获取的改变条件。

CoverageState 必须逐 proposition 保存：已满足需求、引用、来源权威、期间、新鲜度、直接性、冲突、未满足需求和下一条合法 route。它不能只保存一个总分。

## 5. 反驳和第二轮定向检索

反方检索不是给查询尾部机械加 `risk` 或 `counterevidence`。第一轮 EvidenceDecision 后，系统应先形成最强当前命题，再针对其脆弱环节提出反驳：

1. 当前观察是否可能只是 pull-forward、周期、会计口径或一次性因素；
2. 客户／供应商 read-through 是否真正指向研究主体；
3. 产品增长是否存在收入、利润或现金桥；
4. 供应扩张是否具有本案分配、时点、良率和可交付性；
5. 哪条相反事实最可能改变结论。

模型可以提出 counter-hypothesis 和查询原子，但本地 compiler 必须将它绑定到当前 Case、proposition、source role、relationship direction、period、route 和预算。第二轮结果仍经过完整 Evidence Gate，不能因其由 Agent 主动请求就获得更高权威。

## 6. 质量门

### Gate A：请求质量

- Case、主体、截至日、期间和关系方向正确；
- Evidence Need 类型明确；
- 查询 facet 与 route/source class 兼容；
- 禁止代理、预算和停止条件明确；
- 不偷塞标准答案 URL 或跨案事实。

### Gate B：候选覆盖与来源可达

- required facet 的 target-in-pool／candidate ceiling 可解释；
- 内源、官方、外源各 route 的边际贡献可见；
- 来源权威、新鲜度、语言和文档形态覆盖适合当前任务；
- 不能用 reranker 从 0 个有效候选中“救回”不存在的资料。

### Gate C：对象与排序质量

- claim／table／context 与父级上下文完整；
- 发行人、披露方、被谈及实体和关系方向正确；
- 期间与发布日期不混淆；
- hard negative、主题共现、导航垃圾和安全港不会稳定占据头部；
- 排名报告同时解释具体业务错误，不只报 Recall／MRR。

### Gate D：Evidence 晋升质量

- accepted Evidence 的精度、directness、source role 和引用坐标通过；
- candidate、搜索摘要、未审正文与 NumericFact 权限严格分离；
- proxy／read-through 不冒充研究主体事实；
- 争议项进入 `needs_human_review`，而不是弱规则自动放行。

### Gate E：命题覆盖与 Pack Readiness

- 每个 material proposition 的支持、限制、反方、替代解释及必要数值／因果桥状态可见；
- 冲突不平均化，typed gap 不被通用边界话术掩盖；
- 关键缺口有合法下一路线，或明确说明公共资料不可取得；
- 外源补充带来可说明的边际信息增量；
- 连续无进展、重复来源或低价值候选触发停止。

## 7. Pack Readiness 状态

状态必须相对于当前问题和交付深度，而非对公司做永久结论：

- `ready_for_current_scope`：当前重要命题具备足够支持、反方和必要数值／桥状态，可交给 S3 判断；
- `partial_with_material_gaps`：可以形成有边界的部分判断，但关键 gap 必须进入正文和 WWC；
- `blocked_by_source_access`：合法来源存在但当前网络、授权或传输不可取得；
- `blocked_by_candidate_coverage`：对象或来源池缺少当前命题所需候选；
- `blocked_by_retrieval_quality`：有效对象存在，但查询、过滤或排序无法可靠呈现；
- `blocked_by_evidence_admission`：候选相关但直接性、来源角色、期间或引用不足，不能晋升；
- `blocked_by_numeric_or_bridge_authority`：文本存在但 S2 数值或因果桥没有权威。

这些状态不能互相覆盖。例如 DELL 已有 AI revenue／orders／backlog，不允许因产品利润桥缺失而说“需求事实不存在”；正确状态是需求事实 ready、利润桥 blocked。

## 8. 评测矩阵

评测必须分层，且逐案解释业务含义：

| 层 | 主要问题 | 关键输出 |
|---|---|---|
| 请求 | 是否准确理解研究需要 | facet／route／period／relationship 错因 |
| 候选 | 需要的资料能否进入池 | candidate ceiling、target-in-pool、source reachability |
| 排序 | 有效材料是否稳定进入可审范围 | useful@k、hard-negative、头部稳定性及业务错例 |
| 晋升 | 相关候选能否可靠成为 Evidence | precision、abstain／human-review、source-role 错误 |
| Coverage | Pack 是否覆盖当前命题 | 支持／反方／桥／gap 的逐命题矩阵 |
| 补证 | 第二轮是否真正增加信息 | material gap closure、route contribution、边际增量 |
| 下游 | S3 是否因此得到更好判断 | 同 Evidence Need 的 Judgment／内容质量增益 |

DELL／MU／NVDA 用于当前开发和回放；ORCL／ASML／ANET 已经被观察过，只能继续作为工程泛化样本，不能独立承担最终隐藏测试。最终准入还需新冻结的跨行业、跨来源形态和不同 Evidence 充分度案例。

## 9. 与 S3 当前失败的分账

S1 不充分解释了当前报告信息面窄、利润桥／供应分配／估值不足和反方深度弱，但不能解释 R7 对已经可见 AI revenue、orders 和 backlog 的错误否认。后者继续属于 S3 claim semantics／Case Truth reconciliation。后续报告必须分别给出：

- `evidence_acquisition_and_pack_quality`；
- `model_reasoning_and_judgment_quality`；
- `harness_contract_and_truth_reconciliation`。

不得通过补更多资料掩盖模型忽略已见事实，也不得在 Pack 不充分时只靠更强 Prompt 追求研报质量。

## 10. 后续执行顺序

1. 冻结本文范式和 PRD 的产品门；不改 Runtime，不调用模型或网络。
2. 用现有 DELL／MU／NVDA artifacts 做 Evidence Acquisition 尸检：逐命题追踪 request、candidate、Evidence、NumericFact、gap、补源和报告实际消费。
3. 形成跨案 failure atlas，并把问题分到 source coverage、对象解析、query、ranking、Evidence Role／Gate、Numeric／bridge、dynamic loop 或 S3 consumption。
4. 只为最早责任层设计 S1 实现包与确定性验收；不得把所有问题塞入一个大重构。
5. S1 达到 task-relative Pack Readiness 后，再恢复 ResearchBlueprint、Generic Cell Runtime 和 DeliveryPlan 的代码迁移。

本文不授权代码、索引重建、模型调用、网络补源、标签重写或产品发布。
