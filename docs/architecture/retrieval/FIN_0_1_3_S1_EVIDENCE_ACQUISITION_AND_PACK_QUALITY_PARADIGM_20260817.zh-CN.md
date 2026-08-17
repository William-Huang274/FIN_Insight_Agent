# FIN 0.1.3 S1 证据获取、反驳补证与 Evidence Pack 质量范式

日期：2026-08-17

状态：`architecture_decision / runtime_not_implemented / read_only_audit_complete / owner_bounded_first_repair_direction_accepted`
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

## 6. 故障归责与 gap 资格

空结果不是 gap。每个 proposition／EvidenceRequest／candidate 都必须先形成 `FailureProvenanceRecord`，按以下顺序定位最早责任层。

### 6.1 A 类：本地数据面或对象面故障

源材料已经保存、应当已经入库，或者权威结构化事实客观存在，但在以下环节丢失：

- capture 未进入当前 source registry；
- PDF／HTML／表格解析错误，parent／claim／metric-row／context 切分不完整；
- 发行人、期间、单位、文档类型、关系方向或 parent-child lineage 错绑；
- sparse／dense 索引没有包含已存在对象，或缓存／向量版本漂移；
- SQL mart 缺行、错期、错单位、错误 supersession，或 S1 到 S2 exact lookup／join 断裂；
- reviewed Evidence 已存在，却因 slot／facet／objective binding 错误没有进入当前 CoverageState。

这类结果使用 `blocked_by_local_data_materialization`、`blocked_by_object_or_index_integrity`、`blocked_by_sql_or_numeric_authority` 或 `blocked_by_binding_integrity`。它们是项目内部 S1／S2 故障，不得写成“公开信息搜不到”。

### 6.2 B 类：可检索但检索、工具或 Agent 执行失败

资料在合法内源／官方／外源路线可以到达，或候选已经出现在池中，但以下任一环节未完成：

- EvidenceRequest／QueryFacetPlan 没有表达正确实体、期间、产品、关系方向或 source role；
- 应执行的 exact／lexical／semantic／graph／SQL／official／external route 没有被调用；
- 网络、redirect、TLS、代理、下载、parser 或 Provider adapter 失败；
- 有效对象未被召回，或召回后被 hard negative 压出可审范围；
- candidate 已进入池，但没有 Evidence Role／directness／period／source authority 判断；
- candidate 被拒绝却没有理由，或模型没有按 material gap 发起第二轮请求；
- 模型发起了无效、重复或错误路线，Harness 也没有返回可解释的 typed failure。

这类结果分别记录 `query_or_route_compile_failure`、`route_not_executed`、`source_transport_or_parse_failure`、`candidate_not_recalled`、`candidate_recalled_not_ranked`、`candidate_unjudged`、`candidate_retrieved_not_admitted` 或 `model_did_not_execute_required_research_step`。它们仍是产品可修复故障，不得晋升为真实信息 gap。

### 6.3 C 类：真实公共信息边界

只有 A、B 两类已经被排除或修复，并留下以下凭证后，才允许形成公共信息 gap：

- 本地 capture／对象／索引／SQL 查询均完成且无匹配权威事实；
- 适用的 exact、lexical、semantic、graph 和关系方向路线都已执行；
- 发行人 SEC／IR、供应商／客户／同行官方披露、适用行业／监管来源及其 HTML／PDF／feed／语言变体已做有界尝试；
- 所有候选都有 accepted／rejected／unjudged／needs-human-review 决策，不存在静默丢失；
- 来源可达性和最后检查时间可审计；
- 结果确为公司未披露、免费公共资料不足，或必须依赖商业／私有数据，而不是工具没跑、适配器失败或预算被截断。

合法终态至少区分：

- `public_information_not_disclosed`；
- `commercial_or_private_data_required`；
- `source_temporarily_unreachable`（来源存在，不能当作信息不存在）；
- `not_yet_searched`（尚未执行，不能当作 gap）；
- `budget_insufficient_for_required_route`（预算不足，不能当作 gap）。

每个真实 gap 必须附 `GapEligibilityReceipt`：命题、需要的 Evidence 类型、已查本地通道、已执行外部／官方路线、候选决策汇总、可达性、最后检查时间、为何不是项目内部故障，以及下一条可行路线或商业数据边界。

## 7. Candidate 账本、受控晋升与第一修复包

候选不能只以 top-k 列表短暂存在。每个 candidate 必须进入同一账本，并且恰好处于 `accepted`、`rejected`、`unjudged` 或 `needs_human_review` 之一；保存 capture ref、对象 ref、query／slot／facet、rank、Evidence Role、直接性、期间、来源权威、决策理由和 lineage。`unjudged` 是显式待处理状态，不能在终局统计中消失。

当前第一修复包按以下因果顺序执行：

1. 建立 proposition-level `EvidenceCoverageState`，让系统先知道每条重要命题已经有哪些支持、反方、替代解释、数值／因果桥和真实缺口；
2. 打通完整 CandidateDecision 账本，定位 111 个 DELL unreviewed 候选为何没有成为 Evidence；
3. 修复 reviewed Evidence 的 slot／facet／objective 绑定，避免 Pack 中已有材料在本轮被误判为空；
4. 允许 capture-bound 新候选在当前回合受控晋升：候选必须来自不可变 capture，经过身份、期间、来源、引用和 Evidence Gate，模型或 rank 分数不能单独授权；
5. 用 DELL 三条命题执行一次真正第二轮：营运资金用于验证本地对象／SQL／绑定边界，发行人反方用于验证 issuer 查询—排序—晋升，上游反方用于验证关系方向和生态外源路线；
6. DELL 只证明通用闭环可工作后，MU／NVDA 必须从各自自然问题重新规划和执行同一核心，不复用 DELL 标准答案、URL 或手写 case 分支。

这个包不是为了“先把 DELL 做到通过”，而是用三个不同故障面验证归责机制、动态晋升和第二轮信息增量。若 DELL 失败点被证明属于真实公共信息边界，系统应保留合格 gap；若属于本地或工具层，则在其最早责任层修复，不扩大到全部索引重建或模型微调。

## 8. TokenBudgetBasis 与研究完整性

S1 中任何模型辅助的查询生成、候选评估、反方生成、Evidence Role 或补证节点，都必须在 authority 中保存 `TokenBudgetBasis`。依据至少包括节点任务、输入对象／证据／gap 数量、必交付项、schema 复杂度、materiality 风险、历史同类 usage、reasoning profile、安全余量和截断／分批语义。

成本、延迟和调用次数只作为二级约束。不得因为固定 token 上限静默删掉命题、候选、反方或第二轮路线；容量不足时必须确定性分批、按 materiality 做 typed deferral，或返回 `budget_insufficient_for_required_scope`。开放分析与严格交卷应分别估算，不能让交卷预算替代研究预算，也不能看到一次耗尽就无依据扩大上限。全局细则以 `docs/project_os/token_budget_policy.zh-CN.md` 为准。

## 9. 质量门

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

## 10. Pack Readiness 状态

状态必须相对于当前问题和交付深度，而非对公司做永久结论：

- `ready_for_current_scope`：当前重要命题具备足够支持、反方和必要数值／桥状态，可交给 S3 判断；
- `partial_with_material_gaps`：可以形成有边界的部分判断，但关键 gap 必须进入正文和 WWC；
- `blocked_by_source_access`：合法来源存在但当前网络、授权或传输不可取得；
- `blocked_by_local_data_materialization`：材料或事实已在本地责任范围，但 capture、对象、索引、SQL 或绑定未正确物化；
- `blocked_by_candidate_coverage`：对象或来源池缺少当前命题所需候选；
- `blocked_by_retrieval_quality`：有效对象存在，但查询、过滤或排序无法可靠呈现；
- `blocked_by_evidence_admission`：候选相关但直接性、来源角色、期间或引用不足，不能晋升；
- `blocked_by_numeric_or_bridge_authority`：文本存在但 S2 数值或因果桥没有权威。

这些状态不能互相覆盖。例如 DELL 已有 AI revenue／orders／backlog，不允许因产品利润桥缺失而说“需求事实不存在”；正确状态是需求事实 ready、利润桥 blocked。

## 11. 评测矩阵

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

每个指标必须同时报告故障归责和业务例子。例如“DELL working-capital 0 accepted”必须进一步说明是本地对象不存在、可达候选未召回、候选被错排／错拒、模型未执行第二轮，还是公司确实未公开披露；不能用一个 0／1 或 Recall 数字替代原因。

DELL／MU／NVDA 用于当前开发和回放；ORCL／ASML／ANET 已经被观察过，只能继续作为工程泛化样本，不能独立承担最终隐藏测试。最终准入还需新冻结的跨行业、跨来源形态和不同 Evidence 充分度案例。

## 12. 与 S3 当前失败的分账

S1 不充分解释了当前报告信息面窄、利润桥／供应分配／估值不足和反方深度弱，但不能解释 R7 对已经可见 AI revenue、orders 和 backlog 的错误否认。后者继续属于 S3 claim semantics／Case Truth reconciliation。后续报告必须分别给出：

- `evidence_acquisition_and_pack_quality`；
- `model_reasoning_and_judgment_quality`；
- `harness_contract_and_truth_reconciliation`。

不得通过补更多资料掩盖模型忽略已见事实，也不得在 Pack 不充分时只靠更强 Prompt 追求研报质量。

## 13. 后续执行顺序

1. 冻结本文范式和 PRD 的产品门；不改 Runtime，不调用模型或网络。
2. 用现有 DELL／MU／NVDA artifacts 做 Evidence Acquisition 尸检：已完成，见 `FIN_0_1_3_S1_DELL_MU_NVDA_EVIDENCE_ACQUISITION_AUTOPSY_20260817.zh-CN.md`。
3. 形成跨案 failure atlas：已完成；source coverage、对象解析、query、ranking、Evidence Role／Gate、Numeric／bridge、dynamic loop 与 S3 consumption 已分账，等待 Owner 选择有界修复范围。
4. 先实施本文第 7 节的有界第一修复包，并按第 6 节逐命题归责；不得把所有问题塞入一个大重构。
5. DELL 第二轮证明闭环后，让 MU／NVDA 从自然问题执行同核心动态链；没有相同运行深度不能称为泛化。
6. S1 达到 task-relative Pack Readiness 后，再恢复 ResearchBlueprint、Generic Cell Runtime 和 DeliveryPlan 的代码迁移。

本文不授权代码、索引重建、模型调用、网络补源、标签重写或产品发布。
