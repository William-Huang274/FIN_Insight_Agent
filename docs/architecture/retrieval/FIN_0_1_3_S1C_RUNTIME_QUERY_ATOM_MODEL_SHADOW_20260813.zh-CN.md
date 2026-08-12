# FIN 0.1.3 S1-C Runtime Query Atom 模型对照与数据库交接

日期：2026-08-13
状态：`S1-C 模型 shadow 完成 / 无 Runtime 晋升 / S2 公司财务事实库为下一硬门`

## 1. 本轮实际比较了什么

本轮不再用旧的混合问题比较模型，而是把 DELL、MU、NVDA 拆成 18 个只有一个 facet、一个 Evidence Owner 的 Runtime Query Atom。公司、研究截至日、来源类型、对象类型和财年先由本地合同硬过滤；BM25、BGE-M3 与 Qwen3-Embedding-0.6B 再在同一批 20,340 个金融对象上召回。BGE-Reranker-v2-m3 与 Qwen3-Reranker-0.6B 使用同一候选池。

候选始终不是 Evidence。metric-row 始终不是 NumericFact。模型分数不能绕过 S2 数据库、期间、单位、PIT、引用和冲突门。

## 2. R1 为什么不能直接作为最终模型结论

R1 的自然候选池只包含 4 条 hard negative，导致两个 reranker 的有效 pairwise comparison 都为 0。这个结果能够评价自然召回和自然 top-10，却不能评价“正例是否排在预登记 hard negative 前”。

R2 没有修改查询、标签、模型、提示、阈值或候选上限。它保留自然候选池不变，只把通过同一身份、日期、来源和对象门的预登记正负例加入一个显式标注为 `diagnostic_judged_pool_not_runtime_candidate` 的对照池。注入对象不得计入自然召回、不得晋升 Evidence、不得获得 NumericFact 权限。

## 3. 结果

### 3.1 第一阶段召回

| 路线 | 15 个有正例 Atom 中进入前 10 | 进入 64 候选 |
|---|---:|---:|
| BM25 | 5 | 6 |
| BGE-M3 dense | 0 | 1 |
| Qwen3-Embedding-0.6B | 8 | 9 |
| 三路自然共享并集 | 不适用 | 10 / 15 |

因此 Qwen Embedding 是当前 `provisional first-stage winner`，BM25 保留为廉价 lexical baseline／fallback。BGE-M3 dense 不晋升。共享并集仅为 `10/15=0.6667`，低于预登记的 0.80 门，所以这不是 S1 产品通过。

### 3.2 Reranker

| 路线 | 自然候选前 10 正例 | 受控 pairwise |
|---|---:|---:|
| BGE Reranker v2 m3 | 0 / 15 | 8 / 16 = 0.50 |
| Qwen3 Reranker 0.6B | 7 / 15 | 12 / 16 = 0.75 |

Qwen Reranker 达到受控 pairwise 最低门，但没有超过 Qwen Embedding 自然前十的 `8/15`。因此它只保留为 shadow challenger，不进入默认 Runtime；BGE Reranker 不晋升。

Qwen Reranker 必须走官方 yes/no CausalLM surface。把它误装成普通 sequence classifier 会出现随机初始化的 `score.weight`，该输出已被拒绝，没有进入本轮结果。

### 3.3 Evidence Role

确定性角色基线在全部 16 条正例、18 条 hard negative 上得到：

- 正例 compatible：`10/16 = 0.625`；
- hard negative 被拒绝或 abstain：`15/18 = 0.8333`；
- multi-label micro F1：`0.5818`。

它较擅长拒绝明显错角色，但漏掉了太多有效证据，不能上线为硬门。当前 34 条已判断关系、3 个开发案例也远低于 `200 relations / 6 development cases` 的微调讨论门，因此不训练、不微调。

## 4. 具体业务错误，不只看指标

1. DELL reported-results 的已选正例未进入自然 96 候选，但 Qwen 找到的首位文本“全年 AI 优化服务器收入约 600 亿美元”本身可能比单一 qrel 更有研究价值。这说明当前 qrel 不是穷尽式 relevance truth。
2. DELL counterevidence 的正例只是“若不能扩大客户基础，增长可能受限”，Qwen 却把 21 亿美元回购分红排得更高。这里既有 reranker 错误，也有正例过于泛化的问题。
3. DELL upstream-NVDA 与 MU downstream-NVDA 共用了一条残缺的 `-based manufacturing and investing...` 片段；后者还把制造投资错误当作 NVDA 对 MU 的下游需求。它们属于 qrel／对象绑定缺陷，不得进入训练。
4. NVDA reported-results 的收入表格、毛利文本和风险 hard negative 中，Qwen 只赢 1/2；说明表格结果与叙事结果的优先级仍不能完全交给通用 reranker。
5. 角色规则能识别财务表、供给和风险表面，但 Microsoft AI 基建投入的正例只识别为 observed result，没有识别成 demand signal；关系、事实状态和“能证明什么”仍需更强的对象标签与 evaluator。

## 5. 冻结决策

- 第一阶段：`Qwen3 Embedding provisional + BM25 fallback/shadow`。
- Reranker：Qwen 只作 shadow；BGE 不晋升。
- Evidence Role：合同保留，当前规则实现不晋升。
- 微调：不具备数据和独立留出条件，禁止。
- qrel：保留 R1/R2 原始结果；残缺片段和错关系正例进入复核队列，不可通过改标签回写本轮分数。
- Runtime：本轮没有模型路线或 Evidence 权限变更。

## 6. 数据库交接

旧数据库诊断证明年度 revenue／gross profit／operating income 曾达到 9/9，但 current-quarter exact facts 为 0/6。当前只读审计进一步确认：2026-08-06 的 DELL、MU、NVDA SEC CompanyFacts 与 Submissions 原始捕获都在本机，旧活动 manifest 却仍停在 DELL/NVDA FY2025 等旧期；问题是“有当前原始事实但没有当前、按 vintage 和期间建模的事实 mart”，不是缺少 SQL 语法。

S2 必须重建为独立的公司财务事实库：保存 accession、accepted-at、filed-at、fact source digest、taxonomy/concept、value/unit、period start/end、instant/discrete-quarter/YTD/FY、fiscal year/period、vintage 和 supersession。旧的“一家公司每个 metric 只留一行”和“fact/signal/context 混在一张 gold 表”不得原样迁回。DELL 纵切在该门通过前继续阻断。

机器证据：

- `configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_model_shadow_result_v1_0.json`
- `configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_model_shadow_result_v1_1.json`
- `configs/retrieval/fin_ia_0_1_3_s1c_runtime_query_atom_model_shadow_policy_v1_1.json`
