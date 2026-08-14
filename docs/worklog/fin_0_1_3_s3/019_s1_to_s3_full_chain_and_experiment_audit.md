# FIN 0.1.3 S1→S3 全链与实验结果审计

日期：2026-08-14
状态：`read_only_audit_complete / no_runtime_change / no_new_live / owner_direction_pending`

## 1. 审计目的与口径

本次不围绕某一个 DeepSeek 输出继续补字段，而是从 S1 到当前 S3 重新核对：

1. PRD 要求的研究链实际应怎样工作；
2. 当前代码的真实主链到底接到了哪里；
3. 每次实验究竟证明了什么、没有证明什么；
4. 当前阻塞最早属于哪个阶段；
5. 下一步是否仍应只做 S3 因果合同，还是需要跨 S1／S2／S3 重新收敛一条产品真值链。

审计只读取当前干净分支、Project OS、PRD、当前计划、活动 Runtime、机器结果、不可变失败记录和 model-run 报告。没有修改 Runtime，没有调用模型、Provider、网络、embedding 或外源，也没有重跑任何 live。

## 2. 先给结论

当前不是“全链没做出来”，也不是“只差 DeepSeek 再谨慎一点”。项目已经拥有一条真实的工程骨架：

```text
研究目标
  → S3 Planner 提出研究 atoms
  → 本地选择执行预算
  → S1 把 EvidenceRequest 编译成检索与数值 sibling
  → S1 产生候选，S2 返回 NumericFact
  → reviewed Evidence Pack 与 NumericFact 进入 S3 单元循环
  → 模型提交 Judgment，本地校验并生成底稿预览
```

但这条骨架仍有三处产品级断点：

1. **候选没有在同一 Agentic Research 循环中变成新的 Evidence。** 当前 `submit_evidence_request` 只记录补证提案，明确为 `recorded_not_executed`；它不会真正调用 S1、不会经过 Evidence Gate、不会把结果回送当前单元。最新 S3 R2 消费的是预先人工复核并提升好的 fixed Pack，而不是动态研究闭环。
2. **S2 对标准财务报表事实很强，但对产品经营事实和产品→财务桥很弱。** 收入、利润、现金流、库存等已有 PIT／期间／单位／lineage 权威；订单、积压、客户数、出货、ASP、PVM、产品利润线和估值仍是 typed gap 或叙事 Evidence。模型因此能看到“AI 服务器增长”和“公司／ISG 利润改善”，却没有权威对象证明两者之间的贡献关系。
3. **S3 已能约束身份、引用、数字、期间、route 和 gap，却还不能约束 claim scope 与 causal bridge。** Skill 和当前图上下文已经被模型真实消费，但它们是方法与作用域提示，不是强制的因果授权；最终仍出现“多因素公司利润改善 → AI server 已转化为利润”的升级。

因此，当前最早产品根因不是单一 Provider、Prompt 或传输问题，而是 **`candidate → Evidence → operating fact／bridge → claim authority` 这条研究真值链尚未闭合**。只实现一个 S3 因果 validator 可以让系统更安全地拒绝过强结论，但不能自动产生更好的研究答案；只继续补网页或调 embedding 也不能解决产品级因果归因。

## 3. PRD 目标与当前真实链对照

| PRD 所需能力 | 当前真实状态 | 审计判断 |
| --- | --- | --- |
| 用户问题形成 Decision Surface，并按 cell 推进研究 | 已有 provider-neutral Objective／Planner；唯一自然 DELL Planner 提出 10 条有价值 atoms | 规划方向有实质能力，但只证明一个 DELL 问题，尚无真实用户入口和三案自然规划 |
| EvidenceRequest 驱动检索、解析、Evidence Gate 和补证回流 | typed EvidenceRequest、QueryFacetPlan、BM25＋Qwen candidate Runtime 已有 | 请求→候选已接通；当前 S3 loop 的补证请求不执行检索，候选→Evidence→重裁决未接通 |
| 数值由 source-bound、PIT、期间／单位绑定的权威层提供 | S2 mart 已有 1,319 observations、24/24 精确查询与公式 trace | 标准公司财务事实工程能力较强；产品经营指标、估值与产品利润桥未覆盖 |
| 模型基于 Evidence／NumericFact 形成机制、反方和 WWC | DELL `value_capture` R2 已实际使用 Evidence、NumericFact、NumericRelation、RoleMethodPack 和 GraphContextPack | 工具和上下文消费成立；因果归因 L1 仍失败，其他四个 cell 未资格化 |
| Evidence 不足时动态补源并只重裁决受影响 cell | 目前只能提出三条 proposal-only EvidenceRequest，0 retrieval／promotion | 还不是 PRD 定义的动态 Agentic Research |
| 研究结果进入 Workbench 供用户审阅、修复和批准 | 当前 Workbench 只消费 reviewed Evidence／候选／gap；S3 consumer 由脚本和 live lane 驱动 | S4 尚未开始，当前单元底稿不是用户可验收产品面 |
| 完整报告通过 L1、八维质量、paired 与 qualified-human | 只有 DELL 单 cell 诊断 18/24；正式八维未评分 | S3 产品验收、完整报告和 release 均未通过 |

## 4. S1 审计：资料对象已可用，研究证据选择仍未过门

### 4.1 已经真正做成的部分

- 当前对象库已形成 28 个父文档、1,805 个金融 child；之后统一编译为 20,340 个去重 claim／metric-row／context 候选。
- 原始响应先 capture，SEC section、表格、父子 lineage、身份、截至日和 source role 都有明确边界。
- 一条 EvidenceRequest 可确定性拆成 narrative route 与 typed-fact sibling；跨案、错日期、未知 facet 和未授权来源会 fail closed。
- 当前 Runtime 的自然候选路线是 Qwen semantic 与 BM25 lexical 的联合，而不是把任一 embedding 当成事实引擎。
- Source Intake 和人工官方 PDF route 已把 Dell Q1 FY2027 transcript 与 TSM Q2 2026 transcript 纳入同一 capture／parser／Evidence Gate 主干。DELL current Pack 从 15 Evidence／16 gaps 提升到 20／14。

这些是可靠工程能力，不应推倒重来。

### 4.2 实验真正暴露的问题

同一 20,340 对象上的 18 个自然 Runtime Query Atom 中：

- BM25 top-10 命中 5/15；
- BGE-M3 dense 为 0/15；
- Qwen Embedding 为 8/15；
- Qwen＋BM25 共享候选池为 10/15，即 66.7%，低于预登记 80% 门；
- Qwen Reranker 在人工控制池为 12/16，但自然 top-10 只有 7/15；
- Evidence Role 多标签 F1 为 0.5818，仍漏掉大量有效证据，不能做硬门或训练依据。

这些数字对应的业务错误很具体：

- 查 NVIDIA 供给约束时，dense 会把保修、现金等价物和应计负债排在生产爬坡、产能协议和供需错配前；
- 查 Micron HBM4 供给执行时，系统知道应该看 Micron 当前披露，却先选中现金投资表、费用表和业务单元毛利表，真正的 HBM4 出货句没有进入有效对象候选；
- 查 Dell／Microsoft 客户需求时，云产品定义、安全港或资本回报文字会因“AI、增长、投资”共现而冒充实际部署和订单证据；
- 查现金转换时，监管／供给风险会压过库存、现金流和营运资金桥；
- TSM 旧 6-K 虽然命中文档，却只有 2nm／领先制程信息，不能回答 CoWoS／先进封装瓶颈，说明“命中文件”不能冒充“问题得到回答”。

### 4.3 当前 S1 产品缺口

1. `EvidenceRequest → candidate` 已成立，`candidate → EvidenceResponse／EvidenceDecision` 尚未形成可运行产品闭环。
2. current loop 的三条补证请求没有实际运行 S1，无法证明失败分类、fallback、Evidence Gate 和局部重裁决。
3. `typed_relationship_graph` 写在 route policy 中，但 current hybrid runtime 只执行 BM25＋Qwen；当前 S3 GraphContextPack 是从本案已审对象即时编译的一条上下文边，不是图检索 handler。
4. DELL 通过人工有界补源达到 `core_research_ready`，不代表 MU／NVDA 或留出案例具备相同的多源覆盖。
5. 自动官方来源链仍不稳定：关闭 TUN 后 TSM 自动取得成功，Dell 自动 route 仍 timeout；人工上传可用，但不能被包装成完整自动 SourceHunter。

S1 的正确边界是：不再泛化成“调一个更强 embedding”，也不靠 broad web search 堆来源；应当证明真实 EvidenceRequest 能获得、筛选、拒绝或诚实返回 gap，并把结果以 EvidenceResponse 回到研究 cell。

## 5. S2 审计：公司财务事实层最成熟，但研究对象覆盖过窄

### 5.1 已经真正做成的部分

- DELL／MU／NVDA 共 1,319 条 source-bound observation，覆盖 12 类基础指标，保留 591 条 superseded vintage。
- 最近财年 9/9、当前 interim 15/15 精确查询全部通过。
- 每条 NumericFact 保存主体、指标、Decimal 数值、单位、期间角色、财年／季度、accession、accepted-at、source digest、citation 和 supersession。
- 毛利率、自由现金流等派生值有确定性公式 trace。
- 第一版曾把最新 Q1 与旧 Q3 YTD 拼成“当前期间”；现在按同一 disclosure cohort／accession 选择，已通过 mutation。
- 最新 DELL 研究输入可见 25 个 NumericFact 和 10 条同口径 NumericRelation；R2 实际正确使用 8 个端点和 4 条关系。

这条控制面具有长期价值，不是 DeepSeek 当前能力的临时拐杖。

### 5.2 实验真正暴露的问题

保存 Planner atoms 的 DELL 实跑中，标准财务指标能 resolve；但 `orders`、`backlog`、`customer_count`、`shipments` 直接返回 `metric_not_in_company_fact_mart`。最新 R2 又自然请求 ASP、单位量和 price-volume-mix bridge，三者仍只能保持 open gap。

因此当前出现一个业务错配：

- S1 reviewed Evidence 能看到 Dell AI 订单、AI server revenue、backlog、需求高于供给、memory constraint 和管理层的产品盈利目标；
- S2 能证明 Dell 公司／ISG 的收入、毛利、营业利润、利润率和现金变化；
- 但系统没有一个 source-bound、typed 对象说明 AI server 的台数、ASP、PVM、独立利润贡献或从产品到公司／分部利润的桥。

这不是“模型没引用数字”，而是**权威数值层只覆盖报表事实，没有覆盖研究所需的经营指标和桥接状态**。如果不补这一层，S3 的因果门只能把强结论降为 `not_inferable`，很难让报告同时达到安全和高信息密度。

### 5.3 当前 S2 产品缺口

1. 官方 IR／法说中的订单、积压、销量、ASP、价格／组合、产品目标等尚无 provider-neutral operating-metric authority。
2. PIT 行情和估值事实尚未进入同等级 Runtime；旧 market snapshot 也不等于 valuation-ready。
3. MU／NVDA 当前输入各有 14／15 个 NumericFact，但同口径 NumericRelation 均为 0；这代表当前 pack 缺少可确定编译的比较端点，不是可以由模型自由补趋势。
4. Workbench Evidence 页面结构化数值仍为 0，当前 S2 能力只在 request-scoped backend、私有研究输入和 S3 单 cell 得到消费。

## 6. S3 审计：工程 Harness 已显著收敛，产品研究能力仍只证明一个单元

### 6.1 Planner 的真实表现

唯一自然 DELL Planner R1 并非“不会规划”。它输出 exact JSON、公司身份正确、覆盖 5/5 required slot，10 条 atom 的 facet、metric family 和研究方向均合法；内容覆盖需求、订单转化、业绩、指引、价格组合、利润、现金、营运资本和两类反方。

失败是旧合同把“模型可提多少研究方向”和“本轮最多执行多少请求”都写成 8。模型返回 10 条即整轮失败。后续本地 scheduler 稳定选择 8、延期 2，关闭了预算建模问题，并且没有重跑或手工改写模型结果。

审计判断：自然规划已显示价值，但仅有 DELL 一次样本，尚不能证明自由用户问题、三案例、动态追问或长期 CaseControlMemory。

### 6.2 Consumer／Tool loop 的真实进展

S3 从最早的 envelope、枚举、跨 cell ref 和自由数值错误，逐步收敛为一份 provider-neutral Tool Contract：

- 模型必须先读 reviewed Evidence 与 NumericFact；
- 只可提交 proposal-only EvidenceRequest；
- Judgment 使用本 cell 的 Evidence／NumericFact／relation／method／graph refs；
- 身份、期间、数字、引用、gap、receipt、capture 和 terminal result 由本地控制；
- Chat、Responses、Anthropic 只是外层 transport projection。

标准 Tool Calls 的 wire `index`、安全并行、隐藏长度／family 约束和 IncompleteRead capture 都已按项目根因修复，并通过不可变 replay、mutation 和 fresh proof。Chat 与 Responses 均能完成同一 5-step／6-receipt loop；Responses 约多 36% token、慢 58%，没有形成内容优势，因此 Chat 作为 provisional primary 是合理的。

### 6.3 最新 R2 做对与做错的部分

最新 DELL `value_capture` Chat R2：

- 5 次模型调用、6 份 receipt；
- 0 retry、0 fallback、0 外源检索、0 embedding、0 发布；
- 5/5 HTTP 200 完整响应，`IncompleteRead=0`；
- 使用 4 条 reviewed Evidence、8 个 NumericFact、4 条 same-cadence relation、6 条 RoleMethod step 和 1 条 current Graph edge；
- ASP、unit、PVM 三条请求保持 open，没有伪造证据；
- 身份、期间、relation、route、Evidence／gap 权限均通过。

最终仍失败，因为它把“AI server 快速增长＋AI 硬件压毛利＋公司／ISG 利润改善＋管理层产品盈利目标”升级为“Dell 正在把 AI server surge 转化为利润”，并增加未被任何 Evidence／NumericFact／relation／edge 支持的 semi-fixed cost base 机制。

这说明 Skill／Graph 并非没有生效：它们改善了比较、补证、反方和 WWC；但方法提示不能代替因果授权，当前一条 `subject_self_disclosure` 图边也不能证明产品利润贡献。

### 6.4 当前 S3 产品缺口

1. `claim_scope`、`financial_scope`、`causal_bridge_authority` 与 abstain／bounded wording 还不是可校验对象。
2. 只迁移和自然验证了 `value_capture`；需求真实性、现金转换、供给／反方等其余四个 cell 尚未迁移相应 RoleMethodPack 或跑自然内容门。
3. 当前输入是 fixed reviewed Pack；补证请求不执行，故尚未证明动态 Agentic Research。
4. 没有五单元综合、正式八维评分、paired full report 或 qualified-human 验收。
5. S3 consumer 没有 Workbench 产品消费者；当前 deliverable 仅存在于脚本／受限运行结果和 preview。

## 7. 用 DELL 这一案把全链讲清楚

当前 DELL 链可以用业务语言还原为：

1. 用户想知道 AI 服务器需求是否真实、是否可持续、Dell 是否真正赚到钱。
2. Planner 提出 10 个研究方向；系统因预算只执行其中 8 个，保留 guidance 和 pricing/mix 两项延期。
3. S1 为 8 个请求返回 128 个混合候选；S2 同时执行 28 个 typed fact request，其中 19 resolved、9 gap，共得到 45 个 request-level NumericFact。
4. 候选审计发现，很多资料是“同公司、同季度、同主题”，却不能证明当前问题；没有把 128 条候选直接交给 Writer。
5. 有界补源加入 Dell 和 TSM 官方法说，DELL Pack 达到 20 Evidence／14 gaps；只关闭 AI server 盈利目标与先进封装背景等特定缺口。
6. S3 把 20 条 Evidence 中 19 条分配到五个 cell，把重复的 45 个 request facts 合并／筛成 25 个模型可见事实，并生成 10 条同口径关系。
7. 最新只运行 `value_capture`。模型真正使用 4 条 Evidence、8 个事实和 4 条关系，也承认 ASP、销量、PVM 与产品利润线缺失。
8. 但最终结论仍把公司／分部利润改善归给 AI server，因此在最后一层失败。

这条链说明：上游不是完全没资料，模型也不是完全不读合同。真正缺的是从“相关事实”到“允许下什么范围的结论”的连续权威，以及补证请求在当前循环内真正返回新 Evidence 的能力。

## 8. 为什么之前会显得一直在修

1. **工程门先于研究真值门成熟。** schema、capture、receipt、exact-once、budget 和 protocol 很容易做成明确 pass/fail；证据是否真的支持因果结论直到自然内容审查才暴露。
2. **S1、S2、S3 曾按部件各自证明，交接只在 DELL 纵切时才被真实检验。** 例如检索器找到候选不等于 Evidence；S2 有公司数字不等于有产品利润桥；Skill 注入不等于能强制因果边界。
3. **评测面过窄。** 检索开发面主要是 DELL／MU／NVDA 的 18 条 qrel／35 条对象关系；S3 付费内容又集中在 DELL 一个 cell。大量 fake／mutation 证明了“不会串案和破合同”，没有证明“能持续写出高质量研报”。
4. **历史上把协议和内容问题靠得过近。** 多轮 S3 确实修复了项目真实缺陷，但 Chat、Responses、strict、Tool Calls 的资格工作占用了较多注意力；协议全部跑通后，最核心的产品证据仍是一次内容 L1 fail。
5. **当前计划文档发生状态漂移。** 它仍写着 RoleMethodPack／GraphContextPack 未注入和 Research Context Closure pending，而真实 R2 已证明注入、消费和 transport 成立。若不纠正，后续容易重复已经完成的工作。

## 9. 重新划分阶段责任

### S1 必须留下

- 真实 EvidenceRequest 到候选、解析、EvidenceDecision／EvidenceResponse、拒绝或 typed gap；
- candidate selection、Evidence Role、source authority、关系方向和日期；
- residual-gap 驱动的官方／外源补源；
- `typed_relationship_graph` 要么实现真实 handler，要么明确标记不可用，不能只在配置中声明。

### S2 必须留下

- 公司财务事实 mart、PIT、期间、单位、vintage、公式和 NumericRelation；
- source-bound 官方经营指标，如订单、积压、销量、ASP、产品目标等的 typed authority 或明确 gap；
- 产品／分部／公司之间是否存在可用财务桥，而不是让模型从相关性自行推出因果；
- PIT 行情与估值事实。

### S3 必须留下

- 用户问题到 Research Objective／Decision Surface／EvidenceRequest 的自然规划；
- 根据 EvidenceResponse 继续追问、停止或只重裁决受影响 cell；
- claim scope、financial scope、causal bridge、机制、反方和 WWC；
- 五单元综合、完整底稿／报告和内容质量验收。

### 暂不塞回 S1–S3

- Workbench 的真实任务输入、计划修改、human review、repair 和 artifact lineage 继续归 S4；
- release、部署、回滚和 Owner acceptance 继续归 S5；
- 不为当前 DELL 单元恢复完整旧多 Agent、旧图数据或第二套官方 Harness 主链。

## 10. 对下一步的影响

审计后不建议立刻执行原先单独的 `S3 causal claim scope` 包并随后再跑模型。该包仍然必要，但它只能解决“不要说过头”，无法解决“拿什么说得更好”。

建议供 Owner 决策的主方案是一个有界的 **S1→S3 Research Truth Spine Closure**，不新开产品版本，也不重做整个 S1／S2／S3：

1. **S1 EvidenceResponse 纵切**：让保存的真实补证请求在当前 Runtime 中执行，返回 accepted／rejected／typed gap／needs human review；候选仍不得自动提权。
2. **S2 Operating Metric／Bridge 纵切**：只围绕 DELL value-capture 真正需要的订单、积压、AI server revenue／target、ASP、unit、PVM 和 product-to-segment/company bridge 建立 source-bound typed 状态；公开资料没有就明确 `bridge_unavailable`。
3. **S3 Claim Authority 纵切**：建立 provider-neutral `claim_scope + financial_scope + causal_bridge_authority`，先用保存的 R2 Judgment 做零模型负向回放。
4. 三项在同一 DELL 单元零调用连接通过后，才决定是否值得再做一次自然单元证明；通过后才运行五单元。
5. DELL 通过后再以 MU／NVDA 和独立留出案例验证泛化；不能用 DELL 特判关闭 S1–S3。

备选方案的真实代价：

- **只做 S3 因果门**：最快、更安全，但高概率得到正确而空泛的 `not inferable`，研究质量提升有限。
- **只补 S1 来源／检索**：可能获得更多材料，但没有 S2 bridge 和 S3 claim authority，仍可能把更多相关性写成更强因果。
- **直接跑五单元**：会把已知的单元 L1 失败放大，不应授权。

在 Owner 选择前，当前停止线为：不新增模型调用、不进入五单元、不迁移其他 RoleMethodPack、不扩大 broad search、不微调 embedding／reranker。

## 11. 权威证据

- PRD：`docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- 当前计划：`docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md`
- S1 对照：`configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_model_shadow_result_v1_1.json`
- S1 业务错误：`configs/retrieval/fin_ia_0_1_3_s1c_compiled_object_retriever_business_assessment_v1_0.json`
- S1 保存 Planner 输入：`configs/retrieval/fin_ia_0_1_3_s1c_planner_residual_gap_audit_result_v1_1.json`
- 当前 Pack：`configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json`
- S2 mart：`configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_0.json`
- S3 context proof：`configs/research/evals/fin_ia_0_1_3_s3_research_context_closure_zero_call_result_v1_3.json`
- S3 R2 结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_research_context_chat_live_result_v1_1.json`
- S3 R2 内容审查：`configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_research_context_chat_content_assessment_v1_1.json`
- S3 R2 报告：`reports/model_runs/FIN_0_1_3_S3_DELL_VALUE_CAPTURE_RESEARCH_CONTEXT_CHAT_R2_20260814.md`
