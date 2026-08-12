# S1 查询入口与 Evidence Role 规划决策

日期：2026-08-12
状态：`owner_decision_recorded / implementation_not_started`

## 问题

当前 S1-A/S1-C 使用冻结 Case Profile 和固定 9 Slot／17 facet 查询包评估检索。代码中的 query compiler 只接收 `case_key`，Workbench API 只读取预计算快照；因此该结果不能回答真实用户自然语言是否能被正确理解、转写并按需选择 facet。

## Owner 决策

- 固定 canonical query pack 保留，继续作为隔离 BM25、dense、fusion、reranker 和 evaluator 的部件回归基线。
- S1 负责 `EvidenceRequest → 按需 facet → QueryFacetPlan → 实际检索`。
- S3 负责 `用户问题 → Research Objective / DecisionSurface / EvidenceRequest`，以及 residual-gap 动态追问。
- S4 负责真实任务输入、澄清、计划查看和人工修改界面。
- 未完成上述当前 Runtime 集成前，不得宣称真实查询入口或动态 Agentic Research 已通过。

## Cross-Encoder 与 Evidence Role 边界

- Cross-Encoder 只对经过身份、截至日、来源和关系硬过滤后的 query-candidate pair 做语义相关性重排。
- Evidence Role evaluator 独立判断候选是直接事实、当期结果、指引、风险／反方、关系背景、行业上下文还是不相关材料；它必须允许 abstain／human review。
- Evidence Gate 继续持有最终晋升权。Cross-Encoder 分数、embedding 相似度和 role label 均不能单独把 candidate 变成 Evidence。
- 当前 18 条 qrels 和 4 条待确认 successor 只足以做资格判断，不足以直接训练金融专用模型；先扩 hard negatives 与留出案例，再决定是否微调。

## 执行顺序

1. 完成 05/11/15/16 Owner qrel successor 决策和缓存复跑。
2. 闭合请求驱动的 QueryFacetPlan，保留固定 pack 对照。
3. 在同对象上做混合候选、Cross-Encoder shadow 和 Evidence Role evaluator 分层评测。
4. 只把 evaluator 证明的真实 residual gap 交给 S1-D 补源。
5. S1 通过后，S3 才执行自然用户问题与动态研究；S4 再接真实输入和澄清 UI。

## 本次没有执行

- 没有修改 Runtime 代码、模型或 qrels。
- 没有下载 reranker、调用 DeepSeek、构建 embedding 或运行检索实验。
- 本次只同步 PRD、当前计划、技术边界、Project OS 和工作记录。
