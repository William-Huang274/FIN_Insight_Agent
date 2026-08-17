# FIN 0.1.3 S1 数据清洗、检索、证据获取与 Evidence Pack 质量标准范式

日期：2026-08-17

状态：`architecture_decision / full_stack_standard_scope_corrected / runtime_not_implemented / read_only_audit_complete`
产品依据：`docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md` 16.38–16.41

## 1. 为什么需要本范式

当前 S1 已有对象库、BM25／dense／reranker shadow、请求级 Query Atom、受控 Source Intake、官方 PDF 入库、Evidence Gate 和 reviewed Pack 同步。它们分别证明若干部件可运行，但没有共同证明下游模型取得了完成当前研究任务所需的充分材料。

已观察的业务事实包括：

- DELL 候选能找到订单、收入、backlog、营运资金与部分供应背景，但产品利润桥、ASP／PVM、供应分配／容量释放时点和估值仍是 material gap；
- MU 仍缺产品级 HBM／AI 收入、订单、利用率／良率、客户分配及完整周期桥；
- NVDA 候选中风险、联系人和通用披露曾压过当期结果、需求和供应机制；
- dense／reranker 能补充 BM25 漏项，但也会把主题相近、证据角色错误的材料推到前列；
- S3 能记录补证提案，但过去多条路径停在候选或 reviewed-only response，模型没有获得“检索—评估—发现残余缺口—反驳—再检索”的闭环。

因此，S1 的交付物不应定义为“若干候选”“若干抓取成功网页”或“三个案例得到一份 Pack”。S1 的最终交付是从原始金融资料到 task-relative Evidence Pack Readiness 的一套标准范式、当前主线实现和独立资格报告；DELL、MU、NVDA 只是验证这套范式的开发／回归样本。

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
source registry / route plan
  → capture-first raw source acquisition
  → HTML / PDF / OCR / table / feed parsing
  → normalization, deduplication and temporal/source identity
  → parent / section / claim / table / metric-row / context objects
  → versioned sparse / dense / graph indexes + S2 SQL sibling
Evidence Need
  → EvidenceRequest
  → QueryFacetPlan
  → exact / lexical / semantic / graph / SQL / official / external recall
  → structural filters and candidate union
  → semantic reranking
  → finance-aware fine ranking / Evidence Role / directness / owner / period
  → EvidenceDecision
  → proposition-level EvidenceCoverageState
  → material gap or counter-hypothesis
  → bounded supplementary request
  → EvidencePackReadiness
```

该流转允许多轮，但每轮必须有明确的 gap、预期信息增量和停止条件。不得用“继续搜索”作为默认动作。

### 3.1 S1 子阶段与边界

| 子阶段 | 必须解决的问题 | 标准输出 | 不得偷换为 |
|---|---|---|---|
| S1-A Source／Capture | 来源是谁、何时发布、能否合法取得、原始响应是否完整 | 不可变 capture、source identity、route／transport receipt | 搜索摘要或临时网页文本 |
| S1-B Parse／Clean | HTML、PDF、扫描 PDF、表格、feed 如何还原，质量是否足够 | 版面／页码／坐标／OCR 置信度、表格与脚注、typed parse status | 静默缺页、乱码或错表仍标 success |
| S1-C Chunk／Object | 什么是可检索、可引用、可扩上下文的金融对象 | parent／section／claim／table／metric-row／context 与 lineage | 固定字符切块或无父级上下文片段 |
| S1-D Store／Index | 当前对象是否完整进入索引、图和 SQL sibling，版本是否一致 | object manifest、index coverage、digest、rebuild／rollback 入口 | 历史缓存存在即视为当前可用 |
| S1-E Query／Route | 当前命题应查谁、什么期间、什么关系和哪类来源 | EvidenceRequest、QueryFacetPlan、route plan | 固定 17 题或偷塞标准答案 URL |
| S1-F Recall | 所需资料能否进入可解释候选池 | route-scoped candidates、ceiling、target-in-pool、route contribution | 用 reranker 掩盖 0 有效候选 |
| S1-G Rerank | 候选与请求语义是否相关，头部是否更稳定 | 同候选池排序、hard-negative 与稳定性报告 | Evidence 权威决定 |
| S1-H Fine Rank／Evidence Eval | 候选能否以何种证据角色服务当前命题 | role／directness／owner／period／source authority、abstain、review decision | 单一 embedding／reranker 分数自动晋升 |
| S1-I Coverage／Supplement | 已知、未知、反方和下一合法路线是什么 | CoverageState、CandidateDecision、GapEligibilityReceipt、补证增量 | 网页数、Evidence 数或通用 gap |
| S1-J Observability／Qualification | 每层能否重放、解释、比较和稳定运行 | stage receipts、metrics、resource／budget basis、qualification report | 一次成功 case 或 full-chain 日志 |

这些名称表达责任层，不要求每层各有一个独立模型或服务。实现可以合并相邻计算，但合同、指标和故障归责不能合并成一个不可解释总分。

#### 3.1.1 责任分层不等于十个独立项目

S1-A–S1-J 只回答“问题最早属于哪里”和“哪一层必须给出什么凭证”。它们不得被当成十个顺序开发、各自验收、最后一次性集成的小项目。否则会重复历史上已经出现的模式：parser、chunk、index、ranker 和 Evidence Gate 各自有局部绿色结果，但对象版本、期间语义、引用锚点或消费者输入到最后才发生冲突。

实际交付单位统一为**纵向 release slice**。每个切片必须：

1. 从真实或冻结的 raw source／Evidence Need 开始，而不是只从中间 mock 对象开始；
2. 使用当前唯一 canonical artifact spine 和当前主线入口；
3. 让未修改层复用当前 accepted 实现并参加回放，不在本轮重新造一套；
4. 最终生成 CandidateDecision、CoverageState、Evidence Pack，并由 Workbench 和冻结下游 probe 消费；
5. 同时保存局部失败和端到端影响，按最早责任层修复；
6. 通过后形成一个可提交、可回滚、可复证的 release slice，不遗留 attempt-specific runner。

状态词严格区分：

- `component_engineering_pass`：某一责任层的 unit／gold／mutation 通过，但尚未证明下游兼容；
- `vertical_slice_integrated`：真实资料已从当前入口贯穿到 Pack／Workbench，且相邻合同、lineage 和业务语义通过；
- `S1_qualified_stable`：所有必要纵切、frozen test、异质留出和稳定性资格均通过。

只有第三种状态可以关闭 S1。不得用 `S1-A done`、`OCR done`、`reranker done` 或一个 case 报告成功替代。

#### 3.1.2 唯一 canonical artifact spine

所有责任层必须围绕同一条内容寻址链工作：

```text
SourceRouteDecision
  → RawSourceCapture
  → ParsedDocument
  → FinancialEvidenceObject
  → ObjectManifest / IndexSnapshot / S2SiblingBinding
  → EvidenceRequest / QueryFacetPlan
  → CandidateSet
  → CandidateRanking
  → CandidateDecision
  → EvidenceCoverageState
  → EvidencePackReadiness
  → WorkbenchProjection / FrozenConsumerProbe
```

每个转换至少绑定 `case / source owner / discussed entity / as-of / reporting period / locator / parent lineage / schema version / payload digest` 的适用项。Prompt、离线 eval、Runtime、Workbench 和 replay 不得分别维护另一份字段语义。`CandidateSet` 保存 route-scoped 召回边界，`CandidateRanking` 保存同一候选边界上的排序方法、分数和稳定性，`CandidateDecision` 才保存 Evidence Role、directness、authority、accept／reject／abstain／needs-review；三者不得合并为一个无法归责的总分。parser、chunk、object schema、index、query、ranker 或 Evidence evaluator 发生合同变化时，必须生成新 artifact version、明确重建／迁移清单和回滚入口；旧新 artifact 不得静默混用。

该 spine 是一层薄的控制面合同，不是要求所有数据走一个物理流水线。正文／表格对象、SQL `NumericFact`、关系图、official／external source 可以保留并行 data plane；统一的是 identity、period、locator、schema version、payload digest、parent lineage、decision state 和消费者绑定。S2 数字权威不会因进入 S1 spine 而转交给文本检索，Graph 也不能因语义相近自动晋升 Evidence。

当前可执行基础位于：

- `src/retrieval/artifact_spine.py`：canonical envelope、parent seam、scope 和 lineage 校验；
- `configs/retrieval/fin_ia_0_1_3_s1_canonical_artifact_spine_policy_v1_0.json`：artifact type、责任层和合法 parent 关系；
- `configs/retrieval/fin_ia_0_1_3_s1_implementation_coverage_matrix_v1_0.json`：A–J 当前 producer／consumer／artifact／test／gap／迁移入口；
- `eval_sets/fin_0_1_3_s1/`：物理分离的 runtime-visible inputs、evaluator-only references、schema 和 split manifest；
- `scripts/data_retrieval/validate_s1_program_foundation.py`：零网络、零模型的统一校验入口。

这里的 `CandidateRanking` 是对原 canonical 列表的必要补充：没有这个 artifact，S1-G 的 rerank 输出只能藏在 CandidateSet 或 CandidateDecision 里，无法在完全相同候选池上公平比较 BM25、Dense、Cross-Encoder，也无法判断头部错误究竟发生在召回、排序还是证据晋升。

#### 3.1.3 纵向 release slice 组合

当前程序使用以下纵切，而不是按 A→J 做十次最后再合并：

| 纵切 | 真实业务对象 | 必须贯穿的能力 | 关闭意义 |
|---|---|---|---|
| VS1 当前数字原生官方资料与决策账 | 当前 HTML／文本 PDF／transcript 中一组已复核命题 | capture→parse→object→index→query→candidate→decision→Coverage→Pack→Workbench；同时实现第一批 CoverageState／candidate ledger／binding／capture-bound promotion | 证明 canonical spine、永久消费者和第一修复包确实集成，不证明 OCR 或全 S1 |
| VS2 复杂文档与数表 | 扫描 PDF／OCR、跨页表格、脚注、修订／重述 | 同一条 spine，并验证坐标、数字／单位／期间、table／metric-row、abstain 和 S2 sibling | 证明数据地基不会在检索和 Evidence 晋升中失真 |
| VS3 多路线检索与金融排序 | 内源、SQL、graph、official／external、跨公司关系与 hard negative | QueryFacetPlan→candidate ceiling→BM25／dense／multi-vector→rerank→Evidence Role／fine rank→decision→Pack | 证明排序改善真正转化为 Evidence 质量，而非只提高离线排名分数 |
| VS4 Coverage 驱动的第二轮补证 | DELL 营运资金、发行人反方、上游反方及等价自然命题 | residual gap→counter-hypothesis→新 route→capture→decision→Coverage delta→typed stop／ready | 证明动态研究循环、信息增量和 GapEligibility，不以多搜网页冒充闭环 |
| VS5 跨案例与资格 | DELL／MU／NVDA 回归、valid temporal、frozen test、新异质留出 | 使用冻结配置重复 VS1–VS4 的适用路径 | 证明无 case patch、可泛化、可稳定复证，达到 S1 准入 |

每个纵切内部仍按上游先于下游排错；例如 OCR 错误必须先在 Parse／Clean 修复，不能由 reranker 补救。但任何上游修复都必须继续回放到 CandidateDecision、CoverageState 和 Workbench，不能只在 OCR accuracy 变绿后结束。

#### 3.1.4 每次合并前的集成门

每个 release slice 合并前至少通过：

1. **局部门**：所改层的真实 fixture、gold、hard negative 和 mutation；
2. **接缝门**：上下游 schema version、identity、period、locator、digest、lineage 和失败码；
3. **纵切门**：至少一份真实 raw source／Evidence Need 进入当前 Runtime，物化到 Pack／Workbench；
4. **业务门**：说明哪条命题因此多了、少了或改变了什么 Evidence／gap，而不只报告测试数量；
5. **非回归门**：DELL／MU／NVDA 适用回归、跨案／错期／重复／排列 mutation 和 frozen consumer probe；
6. **迁移门**：若对象或索引合同变化，存在重建 manifest、兼容决策和回滚办法。

日常提交运行“所改层定向测试＋至少一条 golden vertical replay”；每个 release slice 关闭前运行全部当前 S1 回归和 Workbench smoke；S1 qualification candidate 才运行 frozen test 与新异质留出。这样既避免每改一行都跑最昂贵全套，也不把集成风险推迟到最终合并。

### 3.2 OCR、表格和 chunk 的最低合同

- 扫描 PDF 先做页面级可读性检测，再决定 text extraction 或 OCR；OCR 结果必须保存页码、坐标、语言、置信度和原始页面回指。
- material 数字、单位、期间、表头、合并单元格和脚注必须有独立准确性检查。低置信度数字不能直接进入 S2，低质量正文不能静默进入 Evidence。
- HTML／PDF／transcript／feed 使用各自 parser，但输出到同一 source-bound 对象合同；第三方解析库只负责候选解析，FIN 本地 adjudicator 负责发布日期、期间和来源身份。
- chunk 以金融语义边界优先：标题／段落／列表／表格／脚注／发言人／问答回合／claim；长度上限只用于二次拆分。每个 child 必须可回到 parent、source locator 和相邻上下文。
- 表格既生成保留结构的 table object，也可生成检索用 metric-row／row-group object；后者只是候选，不自动成为 NumericFact。
- 去重必须区分完全重复、同源多片段、修订／重述、同内容不同 locator 和跨期相似披露；不得把有业务意义的期间差异去掉。

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

## 9. S1 最终必交付物

S1 结束不能只留下实现代码或测试数字，必须同时具备：

1. **标准范式**：本文覆盖的 source／capture、OCR／parser／cleaning、chunk／object、store／index、query／route、recall、rerank、fine-rank／Evidence evaluator、Coverage／supplement 和 observability 合同均有当前版本与 owner stage。
2. **当前主线实现**：每项标准能指向活动树中的唯一生产入口、配置编译源和真实消费者；shadow、历史脚本、fixture 和 archive 不算实现。
3. **数据与模型资产清单**：parser、OCR、chunk policy、对象 schema、index snapshot、embedding／reranker profile、SQL／graph sibling、source route 和依赖版本均内容寻址、可重建、可回滚。
4. **独立评测资产**：train-internal、validation、frozen test／holdout 的 source、page、table、chunk、query、candidate、hard-negative、Evidence Role、gap 和 mutation gold；标签与模型可见输入物理分离。
5. **逐层资格报告**：不只报总分，必须按最早责任层列出业务错例、ceiling、修复影响、未通过项、外部边界和是否允许下游。
6. **Workbench／Operations 消费者**：可查看 source→object→query→candidate→decision→Coverage→Pack 的 lineage、拒绝理由、typed failure、版本和差异，不靠一次性脚本解释主链。
7. **稳定性与关闭声明**：确定性 replay、排列／重复／跨案例／错期／解析失败 mutation、资源与 TokenBudgetBasis 通过；开放问题明确留在 S1、S2 或 S3，不用完整 Agent 报告掩盖。

DELL／MU／NVDA 的作用是验证这些交付物能否处理三种不同业务和资料形态；它们不是标准范式本身。ORCL／ASML／ANET 等已经被开发过程观察，只能做回归，不得继续冒充最终隐藏资格集。

## 10. 质量门

### Gate 0：来源、解析与清洗质量

- capture 完整、不可变、身份／日期／文档类型／语言／格式可审计；
- HTML／PDF／OCR／table parser 的失败、缺页、乱码、低置信度和日期冲突 typed；
- accepted 对象中 material 数字、单位、期间、表头和脚注无静默损坏；
- 原始 source locator、页码／坐标、对象和最终 Evidence lineage 连续。

### Gate 1：chunk／对象／索引质量

- claim、table、metric-row、context 与 parent 边界不截断核心语义；
- 父子上下文、发言人、被谈及实体、期间和 source role 绑定正确；
- 安全港、导航、联系人、重复页和跨期模板不会系统性占据对象池；
- current object manifest 与 sparse／dense／graph／SQL sibling 覆盖一致，缓存漂移 fail closed。

### Gate 2：请求质量

- Case、主体、截至日、期间和关系方向正确；
- Evidence Need 类型明确；
- 查询 facet 与 route/source class 兼容；
- 禁止代理、预算和停止条件明确；
- 不偷塞标准答案 URL 或跨案事实。

### Gate 3：候选覆盖与来源可达

- required facet 的 target-in-pool／candidate ceiling 可解释；
- 内源、官方、外源各 route 的边际贡献可见；
- 来源权威、新鲜度、语言和文档形态覆盖适合当前任务；
- 不能用 reranker 从 0 个有效候选中“救回”不存在的资料。

### Gate 4：召回、重排与头部稳定性

- 发行人、披露方、被谈及实体和关系方向正确；
- 期间与发布日期不混淆；
- hard negative、主题共现、导航垃圾和安全港不会稳定占据头部；
- 排名报告同时解释具体业务错误，不只报 Recall／MRR。
- 重排只在真目标已经进入候选池后验收；若 candidate ceiling 不足，先回到 Gate 0–3；
- dense／reranker 的增益必须对同一候选边界、相同过滤条件和预注册 split 成立，不能用 valid／test 泄漏调参。

### Gate 5：金融精排与 Evidence 晋升质量

- accepted Evidence 的精度、directness、source role 和引用坐标通过；
- candidate、搜索摘要、未审正文与 NumericFact 权限严格分离；
- proxy／read-through 不冒充研究主体事实；
- 争议项进入 `needs_human_review`，而不是弱规则自动放行。
- 相关性、Evidence Role、来源权威和命题直接性分别保存；通用 Cross-Encoder 只能作为一个输入信号；
- 错公司、错期间、错关系方向和越权来源的 Evidence 晋升为 0，不能由平均 precision 补偿。

### Gate 6：命题覆盖与 Pack Readiness

- 每个 material proposition 的支持、限制、反方、替代解释及必要数值／因果桥状态可见；
- 冲突不平均化，typed gap 不被通用边界话术掩盖；
- 关键缺口有合法下一路线，或明确说明公共资料不可取得；
- 外源补充带来可说明的边际信息增量；
- 连续无进展、重复来源或低价值候选触发停止。

### Gate 7：可观测性、资源与稳定性

- 每层输入、输出、版本、耗时、资源、失败位置和下游影响可追溯；
- 确定性阶段在 clean fresh process 下 replay digest 稳定；ANN／模型等非确定性阶段按冻结输入报告分布和头部稳定性；
- 付费／模型节点有 TokenBudgetBasis，预算不足进入 typed deferral／terminal，不制造业务 gap；
- 无 attempt-specific 生产分支、无 case-specific 标准答案逻辑、无未登记的 fallback 或 silent retry。

## 11. Pack Readiness 状态

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

## 12. 评测矩阵

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

独立 S1 资格的指标、split、硬门和案例治理以 `docs/eval/FIN_0_1_3_S1_INDEPENDENT_DATA_RETRIEVAL_AND_EVIDENCE_READINESS_EVALUATION_STANDARD_20260817.zh-CN.md` 为准。本文的 Gate 0–7 是技术责任边界；评测文档负责冻结如何测、用什么集、如何判定通过。

## 13. 与 S3 当前失败的分账

S1 不充分解释了当前报告信息面窄、利润桥／供应分配／估值不足和反方深度弱，但不能解释 R7 对已经可见 AI revenue、orders 和 backlog 的错误否认。后者继续属于 S3 claim semantics／Case Truth reconciliation。后续报告必须分别给出：

- `evidence_acquisition_and_pack_quality`；
- `model_reasoning_and_judgment_quality`；
- `harness_contract_and_truth_reconciliation`。

不得通过补更多资料掩盖模型忽略已见事实，也不得在 Pack 不充分时只靠更强 Prompt 追求研报质量。

## 14. 后续执行顺序

1. 冻结本文全链范式、PRD 产品门和独立 S1 评测合同；不改 Runtime，不调用模型或网络。
2. 用现有 DELL／MU／NVDA artifacts 做 Evidence Acquisition 尸检：已完成，见 `FIN_0_1_3_S1_DELL_MU_NVDA_EVIDENCE_ACQUISITION_AUTOPSY_20260817.zh-CN.md`。
3. 形成跨案 failure atlas：已完成；source coverage、对象解析、query、ranking、Evidence Role／Gate、Numeric／bridge、dynamic loop 与 S3 consumption 已分账，等待 Owner 选择有界修复范围。
4. 建立当前实现对 S1-A–S1-J 的覆盖矩阵和 canonical artifact spine，但不按十层分别开发；先登记唯一生产入口、消费者、artifact version、迁移／回滚和缺口。
5. 执行 VS1：用当前数字原生官方资料贯穿 source→Pack→Workbench，并在同一切片实现 CoverageState／candidate ledger／binding／capture-bound promotion；局部组件通过不得替代纵切集成。
6. 执行 VS2：用扫描 PDF／OCR、复杂表格、脚注和修订／重述贯穿同一条 spine；修复任何数据地基问题后必须继续回放至候选、Evidence、Coverage 和消费者。
7. 执行 VS3：在同一对象／候选边界比较 exact／BM25／dense／multi-vector／graph／SQL、rerank 和金融精排，只有最终 CandidateDecision／Evidence Pack 的业务质量改善才可晋升主线。
8. 执行 VS4：用 DELL 三个不同故障面的自然第二轮验证 residual gap、counter-hypothesis、补源、晋升、Coverage delta 和 typed stop；随后让 MU／NVDA 从自然问题执行同核心路径。
9. 每个纵切合并前均通过局部、接缝、纵切、业务、非回归和迁移六门；日常不等待最终 big-bang integration。DELL／MU／NVDA 只用于开发／回归，不构成最终隐藏资格。
10. 执行 VS5：在预注册的新异质留出案例上完成独立 S1 qualification；全部硬门、性能门、当前 Workbench 消费和稳定复证通过后，才能标记 `S1_qualified_stable`。
11. S1 通过后才恢复 ResearchBlueprint、Generic Cell Runtime 和 DeliveryPlan 迁移，并执行完整真实 `user→S3→S1→S2→S3→S4` 产品链。

本文不授权代码、索引重建、模型调用、网络补源、标签重写、完整真实链或产品发布。

## 15. VS1 实施回证（2026-08-17）

VS1 已在上述范式下完成第一条真实数字原生纵切，并据此更正“Runtime 尚未接入”的历史描述：

1. 当前正式 source manifest 的 11 类输入经薄 adapter 绑定 route、capture、parse 和 financial object，再与当前 index、DELL pricing/mix EvidenceRequest、CandidateSet、CandidateRanking、CandidateDecision、Coverage、Pack readiness、Workbench projection 连接；共 55 个 content-addressed envelope。正文、SQL、Graph 和外源 route 仍是并行 data plane，没有被复制进单一向量库。
2. 6 个真实候选中只有第 5／6 位与现有 reviewed Pack 的公司、来源、期间、slot 和 lineage 完全一致并被接受；前 4 位只进入 needs-review。该结果证明 decision seam 可运行，也直接说明当前头部排序仍不够好，不能被 VS1 的工程通过掩盖。
3. 两条已有 reviewed Evidence 未被该请求召回；三个 residual gap 仍未执行 official／external supplement。CoverageState 因此分别保留 `reviewed_not_recalled` 和 `supplement_route_not_yet_executed`，不把任何一项包装成真实公开信息边界。
4. 当前 Evidence Pack service、Retrieval service、Workspace service 和桌面／移动 Workbench 消费相同 projection 与 Pack digest；跨案、未来日期、排列变化和 Pack drift 均有 fail-closed 测试。
5. VS1 只改变交付状态为 `vertical_slice_integrated`。它没有改善或资格化 neural reranker，没有执行新 Evidence 晋升，没有证明 OCR／复杂表格、多 route contribution、Coverage delta、隐藏集或完整研报质量。

VS1 当时冻结的下一顺序为 VS2→VS3→VS4→VS5。VS2 的复杂文档对象若迫使 spine 合同变化，必须重放本 VS1 golden vertical；不得把 VS1 代码复制成新的 attempt runner。该要求的实际执行结果见下一节。

## 16. VS2 复杂文档纵切回证与 VS3 责任转移（2026-08-17）

VS2 没有另造 parser runner 或新的 Pack 链，而是在 VS1 的同一 artifact spine 上加入一个 train-internal 的 IFX 2025 官方年报开发样本。它不属于当前产品案例，也不作为隐藏泛化样本。

1. **复杂对象地基已贯穿当前消费者。** 192 页官方年报中预注册第 164／166／167 页；native layout 路径保留 5 个复杂表区、56 个 metric-row、1 个脚注、1 个重述上下文和 1 个从第 166 页 Segment Result 总计到第 167 页 reconciliation 的真实跨页关系，共 67 个带 page／bbox／table locator 的候选对象。解析结果继续只授予 candidate 权限。
2. **OCR 只证明 mutation，不冒充自然扫描资格。** 第 166 页官方页面栅格化后强制 OCR，`Segment Result`、`2,560`、`3,105`、`14,662`、`14,955` 和 `previous year` 等预注册 anchor 均保留；但仓库尚无自然扫描、不同噪声／语言／版式的官方资料样本，因此 `real_scanned_source_qualified=false`，留到 VS5 异质资格。
3. **业务失败已定位到排序而非解析。** 4 个 reviewed complex targets 中，仅重述上下文进入当前前 20 并被接受；Segment Result total row、财务脚注和跨页续表均存在于对象库，却没有进入候选窗口。当前决策账为 1 accepted／19 needs-review／3 reviewed-not-recalled。不得继续通过扩大 parser 正则、候选窗口或手工 URL 掩盖；VS3 必须在同一 CandidateSet 上解释 exact／BM25／dense／graph／SQL／parent expansion／rerank 的增量。
4. **数值与产品身份边界保持关闭。** IFX 不加入 DELL／MU／NVDA 产品 case；table row 不自动成为 NumericFact。VS2 只产生 `S2_source_bound_numeric_adjudication_required` sibling typed gap，数值、期间、单位和跨页公式仍由 S2 独立裁决。
5. **canonical spine 新增真实可解引用门。** 回归发现旧 VS1 envelope 的若干 result-local `payload_ref` 指向未物化 JSON path；UI 因读取 sibling projection 仍可展示，旧测试未发现。R16 successor 现要求每个本地 ref 可按 JSON Pointer 解引用，且 envelope `payload_sha256` 必须等于完整被引用 payload 的 canonical digest。旧 R14／R15 结果保持不可变，不能追认为满足新门。
6. **评测仍保持 inputs／labels 物理分离。** VS2 runtime input 只含来源、选页、研究问题和 OCR mutation 指令；page/table/anchor/target 期望只在 evaluator reference 中加载。评测程序允许同一 active split 有多个独立 catalog，但 reserved split 仍只能保留一个空 catalog，防止把开发标签泄漏给 Runtime。

VS2 状态为 `component_engineering_pass=true / vertical_slice_integrated=true / S1_qualified_stable=false`。当前下一项改为 VS3，不再扩大 VS2。VS3 通过仍不能跳过 VS4 的第二轮补证或 VS5 的 frozen／heterogeneous qualification。

## 17. VS3 多路线检索与金融排序回证（2026-08-18）

VS3 证明的不是“某个向量模型胜出”，而是同一对象、同一有限候选边界和同一决策账本能否让多种召回信号组合后仍保持金融证据语义与权限边界。

1. **计算与路线边界。** BGE-M3、Qwen Embedding、BGE/Qwen Cross-Encoder 均以 CUDA-only fail-closed 方式执行；BM25、typed intent、typed metric、parent context 和确定性金融 evaluator 与模型分数并行存在。任何单一路线都不拥有产品权威。
2. **有限池必须分层保护，而不是无限扩大 top-k。** 自然 v1.6 中 DELL reported-results 正例在 typed route 第 3，却被多路线 RRF 挤出 128 候选池。通用 per-need bounded floor 只保护不同 RetrievalNeed 的少量头部，再由 RRF 填满剩余额度；它不读取 case、gold object 或答案 URL。最终 v1.8 达到 15/15 入池和 1.0 顺序稳定率。
3. **金融精排是组合裁决。** 最终前十同时考虑硬身份／期间／来源／关系、need specificity、Evidence Role、metric/product intent、来源权威、route diversity 与稳定 tie-break；结果为 15/15 known positive、0 confirmed hard negative。BGE/Qwen reranker 仍只是特征，不能直接决定 Evidence。
4. **复杂对象必须允许受限上下文扩展。** VS2 四个目标中 1 个直接 shortlist、3 个由同表／父级／跨页关系的 bounded context 接入最终审阅面。parent expansion 不能跨公司、跨期间、跨无关表，也不能授权 NumericFact。
5. **持久决策优先于 review window。** 全部 1,912 个候选均保留 accepted／rejected／unjudged／needs-review；前 12／前 10 只决定审阅优先级，不删除候选。最终为 10 accepted／66 rejected／9 unjudged／1,827 needs-review，且 hard-negative/source-only false accept 均为 0。
6. **旧标签允许证据继任，不允许结果驱动改权重。** VS1 两个历史对象均可追溯；更新的 Dell 10-K／10-Q／官方 transcript 可合法排在旧片段前。此类变化必须记录为对象级 successor review，不能把“旧 target 未在最前”自动算成退化，也不能事后把所有新头部标成 positive 来追分。
7. **Workbench 是当前消费者。** R17 注册 VS3 结果，Operations 显示候选覆盖、金融前十、VS1／VS2 回归、待审数量和权限边界。页面不暴露 qrel identity、答案 URL 或模型内部标签。

VS3 状态为 `vertical_slice_integrated=true / VS4_bounded_supplement_authorized=true / S1_qualified_stable=false`。下一步只能由 Coverage 的 residual gap 驱动 VS4，不允许因为 VS3 排序变好就跳过来源补证、gap 资格或 VS5 异质留出。

## 18. VS4 DELL Coverage 驱动补证回证（2026-08-18）

VS4 的 DELL 开发纵切已经把三项 residual proposition 从 Coverage 账本送回当前对象库与金融排序，再经过角色审阅、capture 复核、Evidence successor、Coverage delta 和 Workbench。它复用已保存的 Dell／TSMC 官方法说，0 网络、0 生成模型调用；因此只证明 capture-bound 二轮补证闭环，不把它写成开放式联网研究完成。

1. **先修最早路线错误。** 初始 upstream counter 请求被编译到不允许 transcript 的 facet，在向量执行前 fail closed。修正为适用的 upstream capacity 路线后，CUDA 候选已包含全部三类命题正例，说明该失败不是模型或信息不存在。
2. **Evidence Role 必须包含说话人权限。** 实际候选暴露分析师问题、IR 主持人复述和同页兄弟句会误继承管理层事实。通用 successor 现在将 question-only／主持人转述降为 generic 或 incompatible；营运资金要求对应主体锚点，上游瓶颈只授予 ecosystem context。最终 6/6 开发正例 compatible，7/7 hard negative rejected／abstained。
3. **候选不能借同源 Evidence 的权限。** 即使对象来自同一 capture、同一页或同一 parent，若现有 Evidence 显式绑定另一 `compiled_object_id`，当前 claim 仍必须独立审阅。Source digest、parent digest、capture SHA、身份、期间、locator 和原文包含关系全部一致后，才允许生成精确 claim Evidence。
4. **Coverage delta 不以数量冒充充分性。** DELL 前序 20 Evidence 退役 3 条宽片段／整页对象，加入 5 条精确 claim，successor 为 22 Evidence；14 个 gap 保持 14，仅营运资金 gap 被 narrow，0 close、0 candidate text promotion、0 NumericFact authority。已知的是 AI 动态会提高库存、应收、应付和大单营运资金占用，以及上游封装／测试瓶颈；未知仍包括产品级金额、周转桥、Dell 分配量和释放时点。
5. **当前消费者不夸大状态。** R18 和 `/api/operations/s1/supplement-quality` 显示命题已知／未知、精确 Evidence 替换、gap receipt 和权限边界；页面持续显示 `complete_s1_ready=false` 与 `numeric_fact_ready=false`。

当前状态为 `DELL_VS4_vertical_slice_integrated=true / MU_NVDA_equivalent_paths_pending=true / VS5_pending=true / S1_qualified_stable=false`。下一步不是继续为 DELL 扩大补丁，而是让 MU、NVDA 从自然命题走同一核心；只有三案回归稳定后才进入预注册 valid／frozen／heterogeneous qualification。

## 19. VS4 三案例 successor 与 VS5 资格边界（2026-08-18）

MU、NVDA 已复用 DELL 的 provider-neutral supplement contract 完成同等纵切，没有为 ticker 添加核心查询、排序、Evidence Gate 或 Pack 分支。R19 current Runtime 现在同时绑定 DELL `22 Evidence / 14 gaps`、MU `11 / 15`、NVDA `19 / 13`；三案旧宽片段分别退役 3／16／14 条，加入 5／11／19 条精确 capture-bound claim，gap 窄化 1／2／3、关闭 0。MU 另增加两个显式 S1→S2 bridge gap，避免退役宽片段后把空 research cell 误写成公共信息不存在或直接生成公司级利润／现金结论。Candidate 自动晋升、NumericFact 新授权和 hard-negative false accept 均为 0。

三项结构问题也由同一纵切自然暴露并关闭：旧 parent 缺 capture metadata 时通过 raw file digest、source URL 和 exact claim surface 做严格 attestation，而不是放宽 capture-first；多案例 summary 在 member 标准化后才计算外层 digest，确保 replay 幂等；完整 Pack 超过单 research cell 容量时，Pack 权威不裁剪，只为模型编译确定性 coverage-first 有界视图并 receipt omitted-but-preserved Evidence。历史 fixed-Pack 输入在未溢出时保持原顺序与 digest。

本轮排名结果必须按正确语义解释：10/10 是 `proposition_any_hit_at_10`，不是 all-positive recall。MU cycle reversal、NVDA cancellation、NVDA production delay 和 TSM bottleneck tools 四个 reviewed positive 没有进入 candidate union，且没有被静默补入或重标。因此最早开放层转为 VS5 的候选覆盖与独立资格：同时测 all-positive object recall、material-facet／required-role coverage、valid temporal、frozen test、新异质留出、mutation 和双 clean replay。

learned Embedding、dense／multi-vector 与 Cross-Encoder 继续统一为 CUDA／FP16 only；每次正式运行必须保存具体 device／runtime／precision／model／cache receipt，CUDA 不可用即 fail closed，不允许 CPU fallback。CPU 只承担 BM25、SQL、分词、硬过滤、账本和确定性编排。当前状态更新为 `three_case_VS4_vertical_slice_integrated=true / VS5_pending=true / S1_qualified_stable=false`。

## 20. VS5 split-safe 资格预注册（2026-08-18）

VS5 不复用已观察案例作为隐藏集。当前预注册以 COST 跨期、JPM／CAT frozen test、NVO／SHEL／腾讯异质 holdout 组成 6 案 7 文档目标，覆盖美国发行人、银行复杂报表、工业业务、外国发行人 20-F／IFRS、非 SEC CJK 官方 PDF 与自然扫描待裁决面。案例、命题、来源形态、配置 digest、执行次数和门槛均先于 source outcome 冻结。

资格运行仍走同一 canonical spine，不建立“测试专用简化链”：official route→capture→parse／OCR→parent／claim／table／context→index→QueryFacetPlan→CandidateSet→CUDA CandidateRanking→finance shortlist／Evidence Role→CandidateDecision→Coverage／gap→Evidence Pack／consumer probe。新案例 adapter 只能填充身份、来源与行业 pack；不得在核心层增加 ticker 分支或答案 URL。

四种覆盖结果必须并存：any-hit、all-positive object recall、material-facet coverage、required-role coverage。前者只说明至少有一条材料，后三者决定资料是否足以支撑研究。任何 parser、query、ranking 或 evaluator 修复若发生在 valid temporal 后，必须重新冻结配置；一旦查看 frozen／holdout 正式结果，只能登记失败和归责，不能原地调参后继续沿用该次资格。

learned vector／reranker 在 VS5 只允许 CUDA FP16；CUDA 不可用、设备／模型／cache digest 漂移时在运行前 fail closed。CPU 继续仅承载 BM25、SQL、分词、硬过滤、账本和确定性编排。这是可比性与执行身份合同，不让 GPU 分数获得 Evidence 权威。
