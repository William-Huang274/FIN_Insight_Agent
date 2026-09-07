# S1 查询入口与 Evidence Role 规划决策

日期：2026-08-12
状态：`owner_decision_implemented / shadow_evaluation_complete / no_route_promoted`

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

## 实施结果

- 四条 successor 已按 Owner 决策应用，18 条 qrel 全部映射到当前对象；缓存复跑 BM25=`17/18`、BGE-M3=`14/18`、RRF／旧规则重排=`16/18`。
- 当前 Runtime 已新增严格 `EvidenceRequest` POST 入口，只编译请求中的 facet、owner、source 和 period；未知 facet、跨案例实体、错截至日和路由身份均 fail closed。它不负责把用户自然语言理解成请求，也不访问外网或晋升 Evidence。
- `BAAI/bge-reranker-v2-m3` 以 Apache-2.0、本地不可变 SHA256 身份离线运行。三案 Recall@10 与 BM25 同为 `17/18`，MRR 从 `0.559392` 提升到 `0.608480`；它能把 NVDA 现金流目标从第 12 位提到第 1 位，却把 DELL AI 需求风险从第 1 位降到第 19 位，并把 MU exhibit index 排到正文前，因此只保留 shadow。
- 规则版 Evidence Role 把三案 top3 的显式不兼容项从 Cross-Encoder 的 `27` 降至 `3`，但 Recall@10 同时降到 `13/18`；在 ORCL／ASML／ANET 留出集上正例 compatibility 仅 `23.2558%`、abstain=`69.7674%`，禁止进入 Runtime。
- 第一版留出负例曾把“未绑定该 slot”错误当作 hard negative；该尝试作为失败结果保留。校正为逐条业务对照和 `unjudged` 后，Cross-Encoder 留出 pairwise=`0.790698`、top3=`1.0`，角色门 top1 反而从 `0.823529` 降到 `0.764706`，进一步证明当前规则不泛化。

## 决策

1. 不微调 BGE-M3 embedding；它不是本轮主要问题。
2. 不立即微调 Cross-Encoder。现成 reranker 已有真实排序增益，但 qrel 仍太少，且残差包含 query／chunk／角色标签混合问题。
3. 不把规则 Evidence Role 当硬门。下一项先把 claim、metric/table 与 parent context 的角色多标签及明确 unjudged 做成可信数据合同，再由结果决定训练 Cross-Encoder 还是独立角色分类器。
4. 用户批准的第 7／8 项仍未执行：未开始微调，也未进入 S1-D 补源／Evidence Pack 重编译。
