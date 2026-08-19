# FIN 0.1.3 S1 数据清洗、检索与 Evidence Readiness 独立评测标准

日期：2026-08-17

状态：`owner_direction_accepted / evaluator_reference_materialized_human_review_pending / cuda_preflight_eligible / runtime_qualification_pending / full_chain_blocked`

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

当前评测程序基础已建立在 `eval_sets/fin_0_1_3_s1/`：Pydantic 生成的 JSON Schema、8 条 `train_internal` 最小真实业务 fixture、单独的 evaluator-only reference、四类 split manifest 和 digest 校验已经存在。DELL／MU／NVDA／ORCL／ASML／ANET 均已被开发过程观察，只能作为开发或回归资产。`valid_temporal`、`test_frozen` 和 `holdout_heterogeneous` 当前明确是 `reserved_unpopulated`；这不是缺少记录，而是防止在 canonical contract 尚未经 VS1–VS3 稳定前提前消耗隐藏集。

冻结顺序必须是：先冻结 eval schema、非补偿硬门和 train-internal label protocol；再用 VS1–VS3 稳定 source／object／query／CandidateSet／CandidateRanking／CandidateDecision 合同；随后预注册 valid／test／heterogeneous holdout 的案例分层、配置 digest 和执行次数。不得先挑几个案例反复看结果，最后再把它们改名为 frozen test。

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
- `proposition_any_hit_at_k`：每个命题是否至少有一个有效目标进入候选窗口；
- `all_positive_object_recall_at_k`：全部已审 material positive 是否进入候选池／审阅窗口；
- `material_facet_coverage`：直接支持、反方、替代解释、数值桥和独立 read-through 等必需 facet 是否分别覆盖；
- `required_role_coverage`：当前任务要求的 direct／counter／bridge／context role 是否缺失；
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

Learned Embedding、dense／multi-vector 与 Cross-Encoder／reranker 的资格运行还必须保存具体 CUDA device、runtime、precision、模型和缓存 identity receipt。CUDA 不可用时必须 fail closed；禁止静默回退 CPU 后把性能、数值精度、批大小或排名行为不同的结果并入同一资格基线。BM25、SQL、分词、硬过滤、账本和确定性编排可使用 CPU，但必须与 learned route 的资源统计分开。

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

- DELL／MU／NVDA current successor Pack 分别为 22／11／19 Evidence、14／15／13 gaps；精确 Evidence 数量增加仍不代表命题充分性或 S1 资格。
- 三案 VS4 的 10/10 表示每个开发命题至少有一个有效目标进入确定性金融短名单前十；另有 4 个 reviewed positive 未进入 candidate union。因此 `proposition_any_hit_at_10` 通过而 `all_positive_object_recall` 仍开放，二者不得混写。
- 既有 BM25、BGE、Qwen、RRF、Cross-Encoder 和规则 Evidence Role 结果来自不同对象／qrel 阶段，不能混成一个排行榜。当前没有任何 neural reranker 或 Role evaluator 获得最终主线资格。
- reviewed Dell／TSMC transcript 已同步进 current object store，但这只关闭 source registry／object drift，不证明 OCR／chunk／ranking／Evidence Readiness 全链通过。
- S2 公司财务 mart 已证明标准财务事实路线，但产品／分部利润桥、ASP／PVM、估值等仍是独立 typed authority 缺口。

## 10. 当前执行边界与下一步

本文件初版只冻结评测合同；当前执行证据已推进到 VS1／VS2／VS3 与 DELL／MU／NVDA 三案 VS4。所有这些结果仍属于开发／回归纵切，不进入 valid／test／heterogeneous gold，也不授权 full-chain。

下一步程序为：

1. **程序基础与当前 Runtime 迁移已建立**：`src/retrieval/artifact_spine.py`、canonical policy、A–J evidence-backed coverage matrix 和统一校验入口已存在；spine 显式区分 CandidateSet、CandidateRanking、CandidateDecision，A–J 仍只作为责任坐标；
2. **已冻结 schema／开发集／split 规则与 VS5 资格预注册，并物化待人工确认的 evaluator reference**：runtime-visible input 与 evaluator-only reference 物理分离，当前 train-internal fixture 和 legacy qrels／role eval 只作开发资产；COST temporal、JPM／CAT frozen test、NVO／SHEL／0700.HK heterogeneous holdout 已在读取检索排名前冻结，三个 qualification catalog 已绑定 5／10／15 条 input/reference；reference 仍为 `qualification_blinded`，不得冒充 owner-reviewed final gold；
3. **VS1 已完成。** 当前 DELL pricing/mix 数字原生路径已从 source→Pack→Workbench 贯通：55 envelopes、6 candidate decisions（2 accepted／4 needs-review）、2 reviewed-not-recalled、3 个 supplement-unexecuted GapEligibilityReceipt；该结果只记 `vertical_slice_integrated`，不注册为 valid／test／holdout 资格结果；
4. **VS2 已完成开发纵切。** IFX 复杂官方 PDF 的表格、脚注、重述和跨页对象已进入同一 spine；自然扫描异质性和 NumericFact 仍未资格化；
5. **VS3 已完成开发纵切。** 同一对象快照上的多路线候选、CUDA semantic rerank、金融精排和完整 CandidateDecision 已进入 R17 Workbench；该结果没有授予单模型 winner 或自动 Evidence 权限；
6. **VS4 三案例已完成。** DELL／MU／NVDA 分别形成 22／11／19 条 current exact Evidence 与 14／15／13 个 visible gap；Candidate 自动晋升、NumericFact 新授权和 hard-negative false accept 均为 0。该结果只注册为开发纵切，不能作为隐藏资格；10/10 any-hit 不得替代 all-positive／material-facet coverage；
7. 每个纵切均先在最早责任层修复，再回放到当前 Workbench／consumer probe；组件绿色但纵切失败时不得合并为主线能力；
8. 执行 VS5 all-positive coverage、valid temporal、frozen test、新异质留出和稳定资格；
9. 达到 `S1_qualified_stable` 后再签发完整真实链。

当前结论：`S1 evaluation foundation + VS1-to-VS3 + three-case VS4 integrated / VS5 all-positive and independent qualification open / S1 not qualified / full product chain qualification blocked`。

## 11. VS5 预注册资格人口与执行次数（2026-08-18）

机器权威为 `eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json`。它在读取新案例检索结果前冻结：

- `valid_temporal`：COST FY2024／FY2025 10-K，最多两次；
- `test_frozen`：JPM、CAT FY2025 10-K，只允许一次正式执行；
- `holdout_heterogeneous`：NVO、SHEL FY2025 20-F 和腾讯 FY2025 官方中英文年报 PDF，只允许一次正式执行；
- 6 个案例、7 个官方文档目标和 30 个研究命题；
- 候选审阅窗为 20；any-hit=100%、all-positive≥90%、material-facet≥85%、required-role=100%；
- hard-negative false accept、跨案／错期／错单位晋升和 false public gap 均为 0；
- learned vector／reranker 只能 CUDA FP16，CPU fallback 禁止；资格阶段生成模型调用为 0。

DELL／MU／NVDA／ORCL／ASML／ANET／IFX.DE 已被机器合同排除。腾讯 PDF 只有在 capture 后证明存在自然扫描的官方实质页时，才可满足 natural-scan 门；人工 raster mutation 不能补偿。实际 282 页均为 native layout，因此该硬门已经失败且不可由平均分补偿。

## 12. VS5 reference、来源故障归因与 CUDA 预检（2026-08-18）

- 30 个命题共绑定 130 个 source-bound positive candidate；reference 与 input 物理分离，Runtime 不可读取 label，Candidate 和 metric row 均不获得 Evidence／NumericFact 权威。
- 当前 source review 结果为 21 complete、1 partial、4 parser/object failure、4 source-plan coverage failure。JPM 四个业务命题的核心财务表未进入对象库，属于 parser／table／objectization；若预注册要求 independent readthrough 而来源计划只有发行人年报，则属于 source-plan coverage。两者均不是 public-information gap。
- evaluator reference 仍待 Owner／qualified-human 复核；这不妨碍运行 label-free temporal candidate generation，但在复核前不得执行或评分一次性的 frozen test／heterogeneous holdout 为最终资格结论。
- CUDA preflight 已在 RTX 4060 Laptop 的 `cuda:0` 以 FP16 tensor 实际通过，四个本地 Embedding／Reranker 模型 digest 已绑定，CPU fallback 禁止。预检本身没有加载完整模型、没有生成对象向量，也不构成 execution authority。
- 后续先运行 valid temporal；只有 runner、cache、结果与 reference review 都绑定干净 commit 后，才允许 test frozen 与 heterogeneous holdout 各执行一次。已知 natural-scan 硬门失败意味着本轮 VS5 不能最终通过，但其他门仍应自然执行并逐层归因，不能提前掩盖其余产品问题。

## 13. valid-temporal R1 后的命题实质性 successor（2026-08-18）

COST R1 已执行并失败：5 个命题 any-hit=`0.80`、20 条关键对象 recall=`0.60`、material facet／required role 均为 `0.642857`。20 条参考对象全部存在于官方对象库，故失败归属 query／typed need／financial shortlist／temporal pairing，不属于 source gap、parser 全面失败、CUDA 或 DeepSeek。

第二次 valid-temporal 仍在预注册的最多两次范围内，但必须同时满足：

1. R1 candidate、evaluation、runner、policy 和 raw 保持不可变；
2. valid 结果只可支持通用结构选择，不能写入 qrel object ID、答案 URL、案例特例或调性能门槛；
3. typed EvidenceRequest 的 metric／product 必须先以独立 need 保留，cross-product 只能使用剩余预算；
4. facet／行业 pack 可生成 broad plan，但不得在 typed request 中覆盖或稀释命题点名词；
5. 多期请求必须以 `fiscal_years + same_basis_comparison_required` 表达，并在 Candidate review 层保留同指标各期候选；该保留不是数值裁决；
6. finite review prefix 必须防止一个 facet 的重复候选挤掉其他请求 facet，但不得把 required role 或 gold 标签作为 runtime 输入；
7. 未进入 ontology 的精确业务词可逐字匹配，但任何 synonym／proxy 扩展仍须 ontology 权威；
8. 旧 v1 合同若已被预注册 digest 或历史 artifact 绑定，successor 必须使用明确版本模块，不得原地修改后破坏历史 replay；
9. 只允许物化 valid-temporal successor input；frozen test 与 heterogeneous holdout 在新配置正式冻结、valid 处置和 reference review 完成前不得执行；
10. R2 通过仍只是 configuration selection evidence。test frozen、heterogeneous holdout、natural-scan、downstream Evidence Pack readiness、qualified-human reference review 和 Workbench consumer 均保持独立硬门。

若 COST R2 再失败，不允许第三次 COST 资格重跑。此时须选择架构处置或另行预注册独立 temporal case，且不能沿用同一隐藏资格结论。
## 14. COST valid-temporal R2 结果与停止线（2026-08-18）

R2 使用与 R1 完全相同的 provisional reference、阈值和业务影响模板，候选在读取 reference 前已经内容冻结。结果由 `12/20` 提升为 `15/20`：五命题 any-hit、material-facet、required-role 均达到门槛，但 all-positive object recall 为 `0.75 < 0.90`，因此 candidate ranking gate 仍失败。

该失败不得被平均指标补偿，也不得通过把 review window 从 20 临时改成 21 来追认。五条 miss 分为两类：三条候选已进入 pool 但排在第 21，说明单对象排序没有保证 direct／counter／bridge／temporal-pair 的材料组覆盖；两条会员经营对象与该问题已冻结的 revenue／gross-margin／operating-cash-flow request 不一致，属于 provisional reference consistency 待人工裁决，不应自动算成检索器错误或据结果删标。

两次 valid-temporal candidate execution 已消耗完毕，COST R3 禁止。JPM／CAT frozen test 与 NVO／SHEL／0700.HK holdout 继续封闭。下一评测合同必须在新 unseen temporal case 结果可见前冻结 request-bound evidence-set coverage、同口径 temporal pair 和 exact-object diagnostic 的边界；已完成的 R1／R2 分数永不改写。

## 15. 现有 hidden reference 披露后的资格更正（2026-08-18）

一次范围过宽的仓库全文检索输出了现有 test-frozen 与 heterogeneous-holdout reference 的部分 expected outcome。虽然没有执行 hidden case、没有读取其候选结果、也没有据此调参，但实现者上下文已被标签污染。因此这两份 reference 从本次事故起不得继续称为 blind qualification，未来即使全绿也只能作为 disclosed regression。

新资格程序必须把 case/source preregistration 与 expected outcome 分离：前者可以进入 Git，后者只进入 private／external access-controlled store；candidate 冻结后才由独立 qualified human 或经 Owner 明确授权的上下文隔离流程评分。`.rgignore` 只防普通搜索误触，不是安全边界。现有 reference 的摘要与事故状态由 machine disposition 保存，文件和已完成 COST R1／R2 均不改写。

## 16. Request-bound Evidence Set 与 exact-object 的分层评价（2026-08-18）

新 unseen temporal case 的参考与评分必须同时满足：

1. candidate 生成前冻结 `MaterialEvidenceRequirementPlan`，且 plan 只能来自公开请求字段；任何 candidate／object／qrel／答案 URL 泄漏使运行无效。
2. 每个 material group 都有唯一 requirement ID，并明确 direct／counter／bridge／context、metric、product、entity 和 period mode。reference group IDs 必须与 plan 完全相等，不能多出一个未请求主题，也不能漏掉一个运行前必答组。
3. 同口径 temporal group 要求同一 basis 覆盖全部请求年份。容量预检按逐年对象最坏情况执行；一张合格多期表可以实际只占一席，但不能因此在运行前少配预算。
4. `required_group_coverage=1.0` 是材料组硬门；reference 可在 candidate freeze 前定义多个等价对象集合。若某项必须是唯一对象，则只能登记该对象集合，不能被“同主题”对象替代。
5. exact-object recall 继续报告，用于识别对象构建、召回和排序退化，但不能单独替代材料组充分性；反之，组级通过也不能掩盖 reference 明确声明的不可替代对象缺失。
6. 错公司、错期、错 basis、plan/reference 不一致、digest 篡改、Candidate→Evidence 或 metric-row→NumericFact 越权均为不可补偿失败。

当前 DELL／MU／NVDA／COST 四业务形态只完成 synthetic development regression，不能注册为 valid／test／holdout。现有 tracked hidden reference 已失去盲性；replacement labels 必须由独立 qualified human 或 Owner 授权的隔离流程在 Git 外生成。当前 Codex 不得自我签发 blind gold。

## 17. 自然材料范围与产品消费者独立门（2026-08-18）

新 unseen case 的 material scope 评价必须把“候选池能够覆盖 fallback requirement”和“产品研究范围已经完整”分开：

1. 确定性编译可完整解释时不得调用模型；无法解释的复合题必须返回 explicit scope required，不得靠增加案例专用同义词静默关门；
2. 自然 scope 节点不得看到 candidate／object／qrel／reference／答案 URL，只能使用 request-visible 枚举和索引；
3. scope 输出必须绑定首次 plan digest，并覆盖所有待解释请求、必需 Evidence Role、metric 轴、hard-product 轴和期间约束；
4. fixed ontology disposition、Case identity、as-of、source role、capacity 和 lineage 只能由 Harness 决定；模型不能改弱或重分类；
5. material reservation 必须发生在完整 candidate union 上且早于 review truncation，但只有 requirement receipt 直接绑定项可硬保留；普通 priority 不能绕过来源配额；
6. `candidate_material_set_complete_request_count` 只属于候选诊断；`runtime_scope_ready_request_count`、CandidateDecision、Evidence Gate、Pack Readiness 和 downstream consumer quality 分别独立验收；
7. 自然节点需要独立 `TokenBudgetBasis`，并保存 exact input／output／usage／finish reason／失败阶段；截断、schema failure 或 plan drift 均为失败，禁止在同一 attempt 内 retry。

当前 DELL／COST 只可作为开发／回归验证，不可替代新的 unseen temporal valid 或外部 blind qualification。一次 DELL scope canary 即使通过，也不改变 COST R1／R2 失败、COST R3 禁止、现有 hidden 失盲和 `S1_qualified_stable=false`。

## 18. 当前快照、route truth 与候选损失可解释性硬门（2026-08-18）

S1 正式评价前必须先证明被评价的是同一可执行快照，而不是“来源用新版、向量用旧版、SQL 和 Pack 各自可读”的松散组合。至少要求：来源→对象 lineage 全覆盖；对象身份与 learned index manifest 一致；S2 SQL 结果与数据库 digest 一致；当前 Pack、anchor 和消费者由 registry 绑定；任一 digest 漂移 fail closed。

每个 EvidenceRequest 的 route receipt 必须区分 requested、available、scheduled、executed 与 exhausted。以下状态不得记为公开资料 gap：route 未实现、未配置、未调度、执行前预算不足、网络／解析／索引失败、候选被 query filter 排除、进入 union 后被 ranking／review cut 截掉、仍待人工复核。

候选质量评价必须同时产出 candidate-ceiling provenance。对每个 material requirement 至少能回答：

- 当前绑定来源是否含有目标资料；
- capture／parse／OCR／对象编译是否成功；
- 目标对象是否进入当前索引或 SQL sibling；
- 哪些路线具备能力、实际执行并返回多少候选；
- 目标是否进入 union，若未进入最早在哪层丢失；
- 若已进入 union，是否被排序、来源配额、材料 reservation 或 review window 截断；
- 是否已有 reviewed Evidence／NumericFact，还是 CandidateDecision／人工复核待定。

只有这些本地和可达路线状态全部闭合，且外部公开来源路线按预注册计划实际耗尽，才可签发 `GapEligibilityReceipt`。`candidate_count=0`、`top_k miss`、`route_not_executed` 和模型没有再次搜索都不能单独成为 gap。该 receipt 与 `EvidenceDecision`、`PackReadiness` 必须成为产品 Runtime 产物，开发脚本结果不能替代。

## 19. 无生成式 AI 的人工可操作硬门与 Agent 集成分账（2026-08-19）

S1 独立资格新增 `human_operable_without_generation_model` 硬门。评测者使用预注册、人工裁决的 typed requests，不调用 Planner、DeepSeek 或其他生成模型，直接验证每个责任层：

1. source/capture 是否取得预期官方或许可资料，并保存 terminal receipt；
2. OCR/parser/cleaning 是否保留 material text、表格、单位、期间、脚注和 locator；
3. claim/table/context/metric-row 对象是否绑定正确 Case、披露方、期间与 parent；
4. sparse/dense/graph/SQL 路线是否按请求执行，目标是否进入候选池；
5. rerank／金融排序是否保持 material facet 与反方，不让重复背景噪声占满审阅窗；
6. CandidateDecision／Evidence Gate 是否精确晋升、明确 abstain 并保留 lineage；
7. GapEligibility 是否证明全部适用本地与来源路线，而不是把空结果直接改名为 gap。

故障归责采用以下反事实：

| 观察 | 归责 |
|---|---|
| 人工 typed request 也无法在已有材料中找到正确对象 | S1 数据／对象／索引／query／ranking／Gate failure |
| 人工路径成功，但 Agent 未形成或未执行等价 EvidenceRequest | S3 Agent 工作模式 failure |
| 正确 Candidate 已进入审阅面但未晋升 | Evidence admission／人工复核状态，不是召回 failure |
| 官方／适用外源路线未执行、超时或解析失败 | source-route／transport／parser failure，不是公开 gap |
| 本地与适用来源路线均完整执行且权威资料确未披露 | 只可成为 gap candidate，仍需 `GapEligibilityReceipt` |

生成模型辅助 query、GraphDelta、第二轮补证和动态研究只进入后续 integration eval；它们不得参与、补分或掩盖本门。反之，S1 通过也只说明工具面合格，不说明 Agent 会正确调用、反思或停止。

最终 S1 资格报告必须同时给出业务例子：具体命题、目标材料、实际错误候选、在哪一层丢失、为何算该类 failure，以及它对 Evidence Pack 和下游研究的影响；不得只列 Recall、MRR、延迟或网页数。

当前 `S1_qualified_stable=false`，本节是标准修订，不是一次资格执行。
