# Fin Agent 投研质量评价体系 v0.1

日期：2026-06-01

状态：长期评价框架，独立于工作日志；后续通过版本号迭代。

机器可读配置：`configs/fin_agent_quality_rubric_v0_1.json`

配套执行文档：`docs/eval/fin_agent_layered_quality_execution_plan_v0_1.md`

## 1. 目标

本体系用于评价 Fin Agent 对投研报告、金融问题回答和多轮投研对话的质量。它不只判断“有没有引用证据”，而是判断答案是否对用户的金融问题有实际研究价值，同时保持证据边界、风险平衡、工具权限和合规安全。

项目当前目标不是输出个性化投资建议，也不生成价格目标；目标是给出基于可检索材料的、边界清楚的、对研究决策有帮助的分析。

评价体系需要支持三类用途：

1. 单个 agent / node 是否可以进入下一阶段。
2. 单轮 full chain 是否达到可交付投研回答标准。
3. 多轮对话下是否能保持 scope、证据、用户意图和前文状态一致。

## 2. 外部参考基线

本框架参考的是投研工作流的通用质量要求，而不是照搬某个券商模板：

- CFA Institute Research Challenge 强调分析、估值、报告写作和展示能力，说明高质量研究不只是事实摘录，还要形成可辩护的分析与表达。
- FINRA Rule 2210 要求面向公众的金融沟通应 fair and balanced，并为评估相关证券、行业或服务提供 sound basis。
- SEC Investment Adviser Marketing Rule 的公开材料同样强调不得只呈现潜在好处而缺少对重大风险和限制的 fair and balanced 处理。

参考链接：

- https://www.cfainstitute.org/societies/challenge
- https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210
- https://www.sec.gov/investment/investment-adviser-marketing

这些参考在本项目中的落地含义是：回答必须有证据基础、必须展示风险与限制、必须把事实转成投资相关判断，且不能越过当前数据源和工具边界。

## 3. 评分结构

每个 case 同时产生两类结果：

| 类型 | 作用 | 结果 |
| --- | --- | --- |
| Hard gates | 判定是否允许进入下游或对用户交付 | `pass` / `fail` |
| Quality score | 判定质量高低和优化方向 | 0-4 分维度评分 + 加权总分 |

分数定义：

| 分数 | 含义 |
| --- | --- |
| 0 | 不可用。任务误解、证据越界、核心事实错误或无法审计。 |
| 1 | 可诊断。能跑通部分流程，但对用户问题帮助有限。 |
| 2 | 基本可用。证据边界正确，但投资判断、结构或深度不足。 |
| 3 | 可交付。能形成清晰、有证据、有风险边界的研究回答。 |
| 4 | 优秀。答案具备清晰主线、差异化 insight、经济机制、反证和行动化观察项。 |

Hard gate 不由加权分数抵消。比如 source-boundary 失败时，即使语言很好，也不能通过。

## 4. 质量维度

### D1 问题理解与任务授权

检查 agent 是否正确识别用户要问的问题、时间范围、公司范围、研究深度、输出形式和多轮约束。

高质量表现：

- 能区分 exact lookup、focused answer、standard memo、deep research。
- 能识别用户是在问基本面、产业链、市场反应、风险、估值语境还是多轮 follow-up。
- 能控制 scope，不把单公司问题无故扩成全行业。
- 多轮中能遵守“只保留 NVDA，不继续分析 AMD”这类用户修正。

硬门控：

- execution mode 错误且会改变下游工具路径，fail。
- required agent 缺失或 forbidden agent 被激活，fail。
- 用户明确限制的 ticker / source 被重新引入，fail。

### D2 证据充分性与来源边界

检查回答是否使用正确 source family、正确期间、正确 source tier 和可追溯 refs。

高质量表现：

- SEC 披露、8-K 管理层口径、market snapshot、industry snapshot、relationship graph 各自用途清楚。
- 数值型 claim 有 exact-value ledger 或可追溯 filing/table evidence。
- 市场反应保留 `snapshot_id` / `as_of_date`。
- 关系图只支持 scope / hypothesis，不支持公司财务事实。

硬门控：

- unsupported 实质 claim 进入最终 memo，fail。
- 8-K commentary 被写成审计事实，fail。
- market 或 industry 数据覆盖 SEC 公司财务事实，fail。
- relationship graph 被写成确认收入、订单或客户事实，fail。

### D3 财务与指标分析

检查系统是否把财务事实转成可用的基本面判断，而不是罗列收入、利润率、capex、存款等指标。

高质量表现：

- 每个关键数值有公司、期间、口径、source role。
- 能解释增长质量、利润率压力、资本强度、现金流、资产质量、经营杠杆或银行特定指标。
- 能指出同比、环比、管理层评论和市场反应之间的差异。
- 能明确哪些指标缺失会限制结论。

硬门控：

- exact-value 问题没有 ledger / filing 支撑且仍给出具体数值，fail。
- 银行、能源、医疗等行业专属指标被当成通用收入指标混用，fail。

### D4 经济关系与产业传导

检查上游是否真正消费了 relationship / sector-depth / industry 材料，并形成经济机制。

高质量表现：

- 区分 direct edge、peer、demand driver、second-order beneficiary、substitution、macro/regulatory exposure。
- 没有 direct edge 时，不写“无关系”，而是区分 `no_confirmed_direct_edge` 和 `possible_indirect_economic_link`。
- 能说明传导路径：例如 hyperscaler capex -> accelerator demand -> data center revenue -> supplier / power constraints。
- 每条关系都有 confidence、materiality、evidence refs 和 missing confirmations。

硬门控：

- sector-depth / relationship case 下 Industry Specialist 没看到或没引用 relationship evidence，fail。
- 把 relationship hypothesis 写成 confirmed commercial relationship，fail。

### D5 投资判断与 thesis 质量

检查最终答案是否形成了研究结论，而不是证据摘要。

高质量表现：

- 先给出 bounded stance，例如 constructive / cautious / mixed / evidence-limited。
- 能说明“为什么重要”：直接受益者、二阶受益者、风险暴露、市场是否已反映。
- 能呈现 thesis、关键 debate、反证条件、观察项和下一步验证路径。
- 能把同一行业内公司排序或分层，而不是平铺。

硬门控：

- 给出未被证据支持的强推荐、价格目标或个性化建议，fail。
- 结论与上游 verified ClaimCards 明显相反，fail。

### D6 风险、反证和情景平衡

检查答案是否 fair and balanced，而不是只讲利好或只堆 caveat。

高质量表现：

- 风险有严重度：blocking / confidence caveat / watch item。
- 反证不只是“数据不足”，而是说明什么证据会削弱 thesis。
- 对 unaudited 8-K、缺少 backlog / RPO、缺少客户级订单等边界给出适当权重。
- 不让安全门把所有结论都压成“证据很薄”。

硬门控：

- 重大反证在上游存在但最终 memo 完全遗漏，fail。
- 只展示收益或好处，不展示相关重大风险和限制，fail。

### D7 输出结构与用户可用性

检查答案是否清楚、可读、对用户下一步有帮助。

高质量表现：

- 用户要短答时短答，用户要 memo 时给 memo。
- memo 有结论、论据、风险、观察项和来源边界。
- 不输出裸内部台账，不泄露 prompt 或私有路径。
- 引用 refs 对用户可读，不淹没主线。

硬门控：

- 最终答案没有实质回答用户问题，fail。
- 多轮回答遗忘或违反最新用户约束，fail。

### D8 过程效率与成本质量

检查 token、工具调用和上下文是否用在有效推理上。

高质量表现：

- route 成功和真实 evidence 质量分开记录。
- supporting agent 有更小预算，不和 primary agent 等量消费。
- tokens per supported ClaimCard、tokens per rendered memo claim、memo chars/token 可追踪。
- 失败时能复用已通过上游 artifact，而不是从头跑 full chain。

硬门控：

- 工具预算超限、重复工具调用、二次检索无增益仍继续，fail。
- 高成本 case 没有产出对应 claim density 或 memo density，进入 quality fail 或 diagnostic-only。

### D9 权限、安全与审计

检查 186 的权限矩阵是否真实执行。

高质量表现：

- Research Lead 只提出业务证据需求，不直接查 BM25 / BGE / DuckDB。
- Evidence Operators 只通过 MCP / registry 执行受控工具。
- Specialist 只消费 bounded rows，不检索、不改 route。
- Memo Writer 只消费 verified summaries / thesis plan，不读取 raw rows。
- Verifier 不生成新观点，不扩大范围。

硬门控：

- 任一 agent 越权工具调用，fail。
- raw evidence、私有路径、API key、token 进入对用户输出或持久 artifact，fail。

## 5. Case 层级

评价集必须覆盖不同问题层级：

| 层级 | 目的 | 示例 |
| --- | --- | --- |
| Exact lookup | 测单指标、ledger、source boundary | “MSFT 2026 capex 是多少？” |
| Focused answer | 测单公司/少数公司和管理层解释 | “分析 AMZN 利润率变化” |
| Standard memo | 测基本面 + 市场反应 + 风险 | “比较 NVDA 和 AMD” |
| Sector-depth | 测产业链、relationship、industry pack | “AI infra 需求传导” |
| Cross-sector | 测能源/电力/AI 等跨行业传导 | “utilities 电力负荷和 AI capex” |
| Multi-turn | 测 scope revision、artifact reuse、记忆边界 | “接上一轮，只保留 NVDA” |

## 6. Agent 分层门控

所有阶段遵循“上游通过才下游运行”的原则。某一层失败时，应复用最后一个已通过的上游 artifact 继续调试该层，而不是直接 full-chain 重跑。

| 阶段 | Agent / Node | 进入条件 | 通过条件 |
| --- | --- | --- | --- |
| S1 | Research Lead | 用户 query + source inventory | mode、scope、agent activation、evidence need 全通过 |
| S2 | Universe / Relationship | S1 通过 + relationship lookup rows | 关系边界、included/excluded、evidence refs、missing confirmations 合法 |
| S3 | Evidence Operators / RAG | S1/S2 通过 | expected tools、BM25/ObjectBM25/BGE、ledger/context rows、source boundary 全通过 |
| S4 | Coverage / Reflection | S3 通过 | gaps 可解释，必要 second-pass 有增益或明确 bounded |
| S5 | Specialists | S3/S4 通过的 bounded rows | role-specific ClaimCards 支撑充分，关系/市场/风险引用正确 |
| S6 | Judgment Aggregator | S5 通过 | 形成 thesis plan，不压扁冲突，不引入新事实 |
| S7 | Memo Writer | S6 通过 | 自然语言 memo 有 thesis、机制、风险、refs，不新增事实 |
| S8 | Verifier / Repair | S7 通过 | deterministic + LLM verifier 通过，repair 定点且有收敛 |
| S9 | Renderer / Product Answer | S8 通过 | 对用户可读、边界清楚、不泄露内部 trace |
| S10 | Full chain / Multi-turn | S1-S9 单层通过 | 跨 case、单轮、多轮稳定 |

## 7. 自动化评价分层

当前 v0.1 自动化分三层推进：

1. Deterministic gates：schema、权限、工具、source boundary、refs、预算、loop stop。
2. Artifact audit：从 saved summary / ledger / sidecar 中计算质量 flags 和成本效率。
3. LLM judge：后续只用于评价 thesis clarity、memo coherence、investment usefulness，不能覆盖 deterministic safety fail。

v0.1 先把 1 和 2 固化。LLM judge 需要单独版本、固定 prompt、固定输入 projection、固定 judge model 和人工校准样本后再接入。

## 8. 质量总分

默认加权：

| 维度 | 权重 |
| --- | ---: |
| D1 问题理解与任务授权 | 0.10 |
| D2 证据充分性与来源边界 | 0.16 |
| D3 财务与指标分析 | 0.12 |
| D4 经济关系与产业传导 | 0.12 |
| D5 投资判断与 thesis 质量 | 0.16 |
| D6 风险、反证和情景平衡 | 0.10 |
| D7 输出结构与用户可用性 | 0.10 |
| D8 过程效率与成本质量 | 0.08 |
| D9 权限、安全与审计 | 0.06 |

交付门槛：

- Hard gates 全通过。
- 加权总分 >= 3.0：可交付。
- 2.4-3.0：可诊断，但不作为成熟 Fin Agent 质量通过。
- < 2.4：失败，需要回到对应 layer 修复。

Sector-depth / relationship case 的额外门槛：

- D4 不得低于 3。
- Industry Specialist 必须看到并引用 relationship evidence。
- Memo 必须写清 direct / indirect / unconfirmed link 的区别。

Exact lookup case 的额外门槛：

- D2、D3、D9 必须通过。
- 不要求 D4、D5 高分，但不能输出无关 memo。

## 9. 版本治理

每次改评分体系都必须：

- 更新本文版本号或追加变更记录。
- 同步更新 `configs/fin_agent_quality_rubric_v0_1.json` 或新版本配置。
- 在执行文档中说明新增/改变的 gate。
- 不用同一个 run 同时调参和宣称独立最终测试。

## 10. v0.1 当前边界

- 自动化可以可靠检查 schema、权限、source refs、route、部分 evidence quality 和成本。
- 投资 insight 深度目前只能部分由规则近似，后续需要 LLM judge + 人工金标校准。
- 当前本地知识库约束下，系统可以给 bounded investment research memo，但不能承诺完整市场覆盖、实时新闻覆盖或个性化建议。
