# FIN 0.1.3 S1 数据清洗、检索与 Evidence Readiness 独立评测标准

日期：2026-08-17

状态：`owner_direction_accepted / evaluation_contract_documented / gold_manifest_and_runtime_qualification_pending / full_chain_blocked`

产品依据：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md` 16.39–16.41
- `docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md` 4C–4E

技术依据：

- `docs/architecture/retrieval/FIN_0_1_3_S1_EVIDENCE_ACQUISITION_AND_PACK_QUALITY_PARADIGM_20260817.zh-CN.md`
- `docs/eval/FIN_0_1_3_EXPANDED_PRODUCT_PERFORMANCE_CASE_AND_ADVERSARIAL_TEST_PLAN_20260805.zh-CN.md`
- `docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md`

## 1. 目的与完成定义

本标准独立回答：FIN 的 S1 是否已经形成一套稳定、可泛化、可审计的数据清洗与检索范式，能够把原始金融资料可靠转换成供 S2／S3 使用的 Evidence Pack，而不是只在 DELL、MU 或 NVDA 上偶然得到若干可用结果。

S1 资格不以以下任一结果单独成立：

- 某个案例找到目标网页；
- BM25、Embedding、Reranker 某个单指标上涨；
- candidate／Evidence 数量增加；
- 一份 DELL 报告可读；
- 一次完整 Agent 链没有报错；
- 模型或 LLM-as-judge 自评通过。

S1 通过必须同时满足：全链标准范式存在、当前主线实现可消费、独立评测资产冻结、逐层硬门通过、异质留出泛化通过、稳定复证通过。完整真实 Agent 链只在 S1 独立资格通过后执行，用于验证 S1 与 S2／S3／S4 的集成，不用于发现本应在 S1 独立测试中发现的基础缺陷。

## 2. 与项目现有 L0–L5 的关系

S1 沿用项目已有分层，但增加自身的评测对象：

| 项目层级 | S1 对应对象 | 通过含义 |
|---|---|---|
| L0 Schema／Unit | source、parse、object、query、candidate、decision、Coverage、gap、receipt schema 与纯函数 | 类型、枚举、身份、期间、lineage、digest 和失败码正确 |
| L1 Data／Financial Truth | OCR／parser、表格、日期、单位、公司／披露方、parent-child、SQL sibling | material 文本／数字／期间／对象身份没有静默损坏 |
| L2 Retrieval／Evidence Authority | QueryFacetPlan、route、candidate ceiling、recall、rerank、fine rank、Evidence Gate | 有效资料进入池并以正确角色晋升，错误资料 fail closed |
| L3 S1 Semantic Quality | Evidence Role、directness、关系方向、反方、替代解释、CoverageState、gap eligibility | 系统知道资料能证明什么、不能证明什么、下一步为什么值得查 |
| L4 S1 Integration | source→parse→object→index→query→candidate→decision→Pack／Workbench | 当前主线端到端可重放、可审计、无 case patch |
| L5 S1 Qualification | frozen test／异质留出、稳定性、资源、回滚和准入决策 | S1 可以作为完整真实产品链的上游依赖 |

现有八维研究内容 Rubric 不直接给 S1 打“研报分”，但 S1 必须证明其 Evidence／Numeric ceiling 足以支持 Q2 证据论证、Q3 Numeric 解释、Q4 机制、Q6 反方和 Q7 WWC。若资料 ceiling 明显不足，S3 内容测试应标记 `upstream_blocked_by_S1`，不能要求模型凭空提高八维分数。

## 3. 评测对象与责任边界

S1 独立评测覆盖十个对象：

1. source registry 与 capture；
2. HTML／PDF／OCR／table／feed parser 与清洗；
3. chunk／parent-child／claim-table-context 对象化；
4. 对象存储、去重、supersession、sparse／dense／graph index 和 S2 SQL sibling binding；
5. EvidenceRequest／QueryFacetPlan／route plan；
6. exact／lexical／semantic／graph／SQL／official／external candidate recall；
7. 同候选池 semantic rerank；
8. finance-aware fine rank、Evidence Role、abstain 和 Evidence Gate；
9. CandidateDecision、CoverageState、第二轮补证、GapEligibilityReceipt；
10. Workbench／Operations 可观测性、replay、资源和 TokenBudgetBasis。

S2 独立拥有 NumericFact、PIT、单位、期间、公式、supersession 和产品到财务 bridge 权威。S1 可以解析表格、定位数字披露并发出 typed sibling request，但不能把检索到的文本数字直接晋升为 NumericFact。S3 独立拥有用户问题理解、Research Objective、命题优先级和最终 Judgment；S1 独立测试使用冻结 EvidenceRequest，不把固定 query pack 冒充自然用户链。

### 3.1 责任层与集成验收的关系

上述十个对象用于定位最早责任层，不构成十个可以各自完成后再统一集成的验收项目。S1 评测的最小交付单位是纵向 release slice；每个切片必须从真实／冻结 raw source 或 Evidence Need 开始，经当前 canonical artifact spine 进入 CandidateDecision、CoverageState、Evidence Pack，并由当前 Workbench 和冻结 consumer probe 消费。

任何组件变更必须同时给出：

- 本层 gold／mutation 结果；
- 与直接上下游的 schema、identity、period、locator、digest、lineage 和失败码兼容结果；
- 至少一条真实纵切的端到端业务结果；
- 对最终 Evidence／gap／Coverage 的可解释影响；
- 数据或索引合同变化时的重建、迁移和回滚结果。

评测状态只允许按以下层级晋升：

1. `component_engineering_pass`：局部正确，不能关闭责任层；
2. `vertical_slice_integrated`：当前真实资料贯穿到永久消费者，相邻合同与业务语义通过；
3. `S1_qualified_stable`：所有必要纵切、frozen test、异质留出和稳定性通过。

例如 OCR 修复不能只报字符准确率；必须证明修复后的 claim／table 对象进入当前 index、能被正确 query 召回、不被错期／错公司对象压过、通过或正确拒绝 Evidence Gate，并在 Coverage／Workbench 中表现一致。反之，reranker 改善也不能掩盖 OCR／chunk 已经损坏目标对象。

## 4. 数据集与案例治理

### 4.1 Split 角色

| Split | 允许用途 | 禁止用途 |
|---|---|---|
| `train_internal` | parser／chunk／query／route／ranking 设计、错误分析、阈值与规则迭代 | 最终独立通过声明 |
| `valid_temporal` | 检查 train 决策能否跨期、跨文档和跨案例保持 | 反复查看后继续当隐藏测试 |
| `test_frozen` | 冻结配置后的最终逐门资格与归因报告 | 同一轮调参、改阈值、换 route 后仍沿用通过结论 |
| `holdout_heterogeneous` | 检查行业、来源、语言、关系和资料充分度泛化 | 选几个与 DELL 相似的案例做平均分 |

标签、目标 source／object、qrels、hard negatives 和 gap 真值必须与模型／Runtime 可见输入物理分离。test 结果揭示的新问题进入下一轮 train／valid，不回调同一 test。

### 4.2 当前案例角色

- **DELL／MU／NVDA**：开发、业务尸检和持续回归；用于覆盖服务器 OEM、memory cycle、AI 平台／供应生态，但不承担最终隐藏资格。
- **ORCL／ASML／ANET 及 HPQ／AVGO／INTC 等已观察样本**：结构／迁移回归；已被开发过程查看，不能冒充独立 test。
- **新冻结异质留出**：在查看结果前预注册，至少覆盖以下分层，而不是只追求案例数量：
  - 美国普通发行人、外国发行人和不同 filing 体系；
  - 制造／半导体、软件／订阅、金融或其他不同财务对象形态；
  - HTML、文本 PDF、扫描 PDF／OCR、复杂表格、transcript／Q&A、feed／redirect；
  - 中文／英文查询、跨公司客户／供应商／同行关系和负向关系方向；
  - 资料充分、部分充分、真实未披露、来源暂不可达、商业数据边界；
  - 旧期／新期、修订／重述、同源多片段、跨案污染和 hard-negative 密集场景。

每个案例必须逐案过硬门；不得以平均分掩盖任一身份、期间、来源、数字、引用或 false-promotion 失败。

## 5. S1 独立考核维度

### E1 Source／Capture 完整性

必须报告：

- source identity、披露方、被谈及实体、文档类型、published／filed／period／as-of 分离准确性；
- raw response／PDF／HTML／feed 完整留存率和 digest 一致性；
- redirect、TLS、代理、IncompleteRead、timeout、不可达、权限失败的 typed 分类；
- 同源别名、canonical URL、修订／重述和跨期对象是否正确区分；
- 来源暂不可达是否被错误写成公开信息不存在。

硬门：accepted source 的身份／日期／digest／locator lineage 完整；跨公司 source 误绑定为 0；capture／transport failure 误报真实 gap 为 0。

### E2 OCR／Parser／数据清洗质量

必须按文档形态分别评测，不使用一个总 parser accuracy：

- 文本可读页覆盖、缺页与阅读顺序；
- OCR character／word error，并单列 material number、货币、百分比、期间和公司名 exactness；
- 表格 cell、row／column header、合并单元格、单位、脚注与 page continuation 对齐；
- 正文、导航、安全港、联系人、页眉页脚、脚注和 Q&A speaker 分离；
- publication date、reporting period 和正文提及日期的冲突裁决；
- 低置信度、乱码、表格错位是否 abstain／needs-review。

硬门：进入 accepted Evidence 的 material 数字、单位和期间无 parser/OCR 静默篡改；parser 不能在缺页或低置信度时返回无提示 success；每个 accepted object 可回指原页／坐标或 DOM locator。

性能阈值须在 gold corpus 建立后、运行 frozen test 前冻结；不得先拍一个统一 OCR 百分比，再忽略财务数字和表格错误的高风险权重。

### E3 Chunk／金融对象质量

必须报告：

- gold claim／table／metric-row／context 的 object coverage；
- 关键命题是否被固定长度截断，parent context 是否能恢复完整语义；
- 表格／脚注／speaker／问答回合边界；
- overlap、重复、同源多片段、跨期模板和修订 supersession；
- identity、period、source role、关系方向和 parent-child lineage；
- 可引用 anchor 的精确度及稳定性。

硬门：跨案／错期／错 parent lineage 为 0；accepted Evidence 不得来自无法定位的 chunk；安全港、导航、联系人或乱码对象不得稳定进入 required-facet 头部。

### E4 Query／Route 正确性

必须报告：

- EvidenceRequest 到 QueryFacetPlan 的主体、披露方、期间、产品／指标、关系方向、source role 和语言保真；
- exact、lexical、semantic、graph、SQL、official 和 external 路线是否按需执行；
- forbidden expansion、错误别名、跨案例污染和标准答案 URL 泄漏；
- route 未执行、Provider／adapter／parser 失败和模型未发请求是否可区分；
- 同一 intent 的 provider wire projection 是否保持语义而不过度截断。

硬门：身份、期间、关系方向和 source class 的 material 编译错误为 0；gold URL／qrel identity 泄漏进模型或生产 query 为 0；未执行 route 不得写成真实 gap。

### E5 Candidate Recall 与 Ceiling

必须报告：

- required-slot `target_in_pool`／candidate ceiling；
- exact／BM25／dense／multi-vector／graph／SQL／official／external 各路线的独立和边际贡献；
- target 缺失属于 source、object、index、query、filter 还是 route；
- 召回候选中的重复率、跨案率、过期率和来源多样性；
- 延迟、内存、索引大小和候选规模。

硬门：目标未进入池时，reranker／fine rank 只能标记 diagnostic，不得晋升主线；current object／index parity 和跨案过滤必须通过。

### E6 Semantic Rerank 与头部稳定性

重排只比较同一候选池，至少包含当前 BM25／规则基线和 provisional dense／reranker challenger。必须报告：

- useful@k、MRR／NDCG 或等价排名指标；
- hard-negative suppression、直接 target top-k、排名反转和业务错例；
- query 改写、候选排列、重复对象和小幅文本扰动下的头部稳定性；
- train／valid／test 与案例 cohort；
- 延迟、吞吐、内存和部署约束。

晋升条件：challenger 在预注册 valid／frozen test 上提供 material 增益，不降低 required target ceiling，不扩大身份／期间／角色错误，并满足资源门。某个聚合指标上涨但关键 DELL 风险 target 从第 1 降到第 19，不能判为主线改善。

### E7 金融精排、Evidence Role 与晋升

该层回答“候选能证明什么”，不只是“语义像不像”。必须报告：

- Evidence Role 多标签、directness、source owner、discussed entity、period、relationship direction；
- positive／hard-negative／unjudged／needs-human-review 与 abstain；
- accepted precision、错误拒绝、false promotion 和人工复核负担；
- issuer assertion、independent corroboration、customer／supplier read-through、context、limit／counter 的区分；
- candidate→Evidence lineage 与引用坐标。

硬门：错公司、错期间、错关系、无 locator、未审摘要、模型建议或搜索 snippet 晋升为 Evidence 为 0；critical false promotion 不可由 Recall／F1 平均分补偿。现有 Cross-Encoder／Role shadow 未过即继续保持 shadow，不因本标准存在而自动晋升或微调。

### E8 Coverage、补证与 Gap 资格

必须逐 proposition 报告：

- direct support、bounded read-through、counterevidence、alternative explanation、numeric／causal bridge 和 WWC 覆盖；
- accepted／rejected／unjudged／needs-human-review 候选全账；
- 第一轮到第二轮关闭的 material gap、信息增量和判断范围变化；
- GapEligibilityReceipt 完整性和最早责任层；
- 无进展、重复来源、预算不足、来源暂不可达和商业数据边界的停止理由。

硬门：已有 reviewed Evidence 漏绑定为 0；本地故障、未执行路线、候选未判或预算不足误报 `public_information_not_disclosed` 为 0；所有正式公共信息 gap 均有完整 receipt。

### E9 下游可用性 Ceiling

S1 不给最终报告打八维分，但必须把 Pack 交给一个冻结、无自由补源的 S2／S3 consumer probe，检查：

- 模型／规则是否能看到决定性 Evidence、反方、bridge 状态和真实 gap；
- accepted Evidence 是否实际被消费，未使用项是否可解释；
- Pack 是否足以支持八维 Rubric 的 Q2／Q3／Q4／Q6／Q7，还是应 upstream-block；
- 增加资料是否真正收窄判断或提高机制／反方，而不是只增加引用数量。

这个 probe 是 S1 下游 ceiling 测试，不是完整 Agentic Research、研报接受或 S3 通过。

### E10 稳定性、可观测性与资源

必须报告：

- clean fresh-process replay、摘要、顺序／重复／mutation 稳定性；
- Runtime、Workbench／Operations 和离线评测是否消费同一合同编译源；
- 每层 latency、throughput、CPU／RAM／GPU、index 大小、网络与 Provider 成本；
- 每个模型／付费节点的 TokenBudgetBasis、actual usage、required-output coverage 和停止语义；
- failure envelope、capture、candidate、decision、Coverage 和 Pack 的 trace 完整性；
- 是否存在 case-specific 分支、silent retry、weak fallback 或 attempt-specific 主线代码。

硬门：确定性阶段两次独立 clean replay 结果一致；关键失败均 typed 并保留部分结果；没有用 token／成本上限静默删掉 required scope；没有未登记 case patch。

## 6. 指标与阈值冻结规则

S1 同时使用三类判定：

1. **不可补偿硬门**：身份、期间、单位、source locator、跨案污染、critical false promotion、真实 gap 误报、lineage、test leakage 和 silent failure。目标通常是 0 error 或 100% receipt，不取平均。
2. **性能门**：OCR／table／chunk gold、target-in-pool、useful@k、MRR／NDCG、Role F1／precision、abstain、信息增量、延迟／资源。阈值必须在 gold 与 baseline 完成后、查看 frozen test 前预注册，并按文档形态／案例 cohort 报告。
3. **比较门**：新 parser、chunk policy、Embedding、Reranker、Evidence evaluator 或 Provider 必须与当前 accepted baseline 在同一输入、候选边界和 split 上比较。只提高一个指标却降低其他硬门或下游 Pack 质量，不晋升。

禁止以一个总 S1 分数补偿不同责任层。资格报告可以提供摘要，但最终状态必须逐门为 `pass / fail / blocked_external / diagnostic_only / not_run`。

## 7. 泛化与稳定通过条件

S1 标记 `qualified_stable` 前必须全部成立：

1. L0–L4 当前主线在 DELL／MU／NVDA 开发／回归样本通过，不保留按 ticker 写死的查询、阈值、来源或答案；
2. `valid_temporal` 证明关键策略跨期稳定；
3. `test_frozen` 在未回调阈值和路线的情况下逐门通过；
4. 新异质留出按行业、来源形态、语言、关系方向和资料边界逐案通过不可补偿硬门，性能门达到预注册标准；
5. 两个 clean fresh-process 对确定性路径给出相同摘要／结果 digest；模型／ANN 路线满足预注册稳定区间且不出现关键头部反转；
6. current Workbench／Operations 可查看完整 lineage 和最早故障层；
7. 所有真实 gap 有资格 receipt，所有内部故障有 owner stage；
8. 形成一份 qualified reviewer 可审的 S1 逐层报告，并明确哪些能力仍属于 S2／S3／S4。
9. 每个进入主线的 parser／chunk／index／retrieval／rerank／Evidence evaluator 变更都有至少一条真实纵切通过记录；不存在只凭组件 test 晋升、最后一次性集成的 release slice。

DELL、MU、NVDA 平均通过不能替代逐案和留出通过；一个案例资料确实缺失时可以 `blocked_external`，但必须证明系统正确识别该边界，而不是为了让案例凑齐 Evidence。

## 8. 完整真实链准入

用于产品资格的完整真实链必须满足：

```text
S1 standard paradigm frozen
  → current implementation coverage matrix closed
  → S1 independent L0–L5 qualification pass
  → heterogeneous holdout and stability pass
  → repository-bound full-chain preflight
  → user prompt
  → S3 Research Objective / EvidenceRequest
  → S1 dynamic retrieval / evidence evaluation / second-round supplement
  → S2 NumericFact / bridge
  → S3 Judgment / synthesis / report
  → S4 Workbench review
```

S1 未通过时仍可运行的模型或节点调用必须明确标为 deterministic proof、shadow、changed-node canary 或 diagnostic；不得叫“完整真实产品测试”，也不得由局部成功反向追认 S1。

## 9. 当前已知基线与不应误读的数字

- DELL／MU／NVDA reviewed Pack 分别为 20／16／14 Evidence，但只有 11／2／8 exact claim anchor；数量不代表对象质量或命题充分性。
- DELL 当前 8 个请求／128 candidates／111 unreviewed／8 unique accepted／0 dynamic promotion；working-capital、issuer-counter、upstream-counter 均 0 accepted。这首先要求 candidate ledger、binding、admission 和 failure provenance，而不是立即扩大 broad search。
- 既有 BM25、BGE、Qwen、RRF、Cross-Encoder 和规则 Evidence Role 结果来自不同对象／qrel 阶段，不能混成一个排行榜。当前没有任何 neural reranker 或 Role evaluator 获得最终主线资格。
- reviewed Dell／TSMC transcript 已同步进 current object store，但这只关闭 source registry／object drift，不证明 OCR／chunk／ranking／Evidence Readiness 全链通过。
- S2 公司财务 mart 已证明标准财务事实路线，但产品／分部利润桥、ASP／PVM、估值等仍是独立 typed authority 缺口。

## 10. 当前执行边界与下一步

本文件只冻结评测合同，没有运行 OCR、parser、chunk、index、Embedding、Reranker、模型、Provider、网络、source promotion 或 full-chain。

下一步程序为：

1. 建立 S1-A–S1-J 当前实现／消费者／评测覆盖矩阵和唯一 canonical artifact spine；A–J 只作为责任坐标，不作为十个独立关闭项；
2. 冻结 source-page-table-chunk-query-candidate-Evidence-gap 的 gold／negative／mutation schema 和 split；
3. 执行 VS1 当前数字原生官方资料纵切，在同一条 source→Pack→Workbench 路径完成 16.40 已批准的 CoverageState／candidate 账本／binding／capture-bound promotion；
4. 执行 VS2 复杂文档纵切，覆盖扫描 PDF／OCR、跨页表格、脚注和修订／重述；
5. 执行 VS3 多路线检索与金融排序纵切，在同一候选边界验收 recall／rerank／fine-rank 对最终 Evidence Pack 的真实增益；
6. 执行 VS4 Coverage 驱动的第二轮补证纵切，完成 DELL 三命题和 MU／NVDA 等价自然路径；
7. 每个纵切均先在最早责任层修复，再回放到当前 Workbench／consumer probe；组件绿色但纵切失败时不得合并为主线能力；
8. 完成 DELL／MU／NVDA 回归后执行 VS5 新异质留出和稳定资格；
9. 达到 `S1_qualified_stable` 后再签发完整真实链。

当前结论：`S1 independent evaluation contract documented / S1 not qualified / full product chain qualification blocked`。
