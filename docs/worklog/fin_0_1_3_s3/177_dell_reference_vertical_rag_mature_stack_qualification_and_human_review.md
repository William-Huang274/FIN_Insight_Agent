# DELL 单案例 RAG：成熟栈父子检索资格化与人工相关性审计

更新时间：2026-09-02

状态：`STRUCTURED_CORPUS_ATTEMPT12_AND_FULL_STACK_ATTEMPT03_AUDITED / BM25_ENGINEERING_PREVIEW_BASELINE / HYBRID_CHALLENGER / DENSE_AND_QWEN_RERANKER_REJECT / FORMAL_HOLD`

范围：只评估 DELL reference vertical 的 18 份冻结正文、597 条旧 chunk 和 A01 Planner 的 19 条真实检索请求；不建设通用 RAG 平台，不给予 Evidence、NumericFact、S2、产品或发布权限。

## 1. 为什么做这次试验

旧本地 reader 实际是 `2400 chars + 300 overlap + flat BM25`。它能给 Agent 返回 candidate，但旧 bridge 丢失 route／parent／chunk／page／parser／branch lineage，reader 也没有按每条记录的 branch 做 prefilter。Owner 要求先判断成熟技术栈能否包装或替代这部分，而不是继续在旧壳中追加零碎规则。

本次选择 Haystack 3.1.0 作轻量 challenger，原因是它可以在 Z 盘隔离运行，直接提供：

- `HierarchicalDocumentSplitter`；
- `InMemoryBM25Retriever`；
- metadata filter；
- `AutoMergingRetriever`；
- 不需要引入新的数据库、云服务或产品 sidecar。

WeKnora 仍有产品级参考价值，但本机 source clone／重试不稳定，整套服务对一个本地单案例过重；本轮没有把它写进正式依赖，也没有为它建设自研兼容层。

## 2. 输入、运行和不可变边界

- 输入 source：18。
- 旧 flat chunks：597。
- A01 Planner requests：19。
  - `reviewed_first`：9，只对这 9 条计算本地 retrieval quality。
  - `external_required`：10，只检查 wrong-local-substitution risk，禁止混进本地 Recall／relevance 平均值。
- Haystack hierarchy：18 roots、241 parents、1,105 leaves、1,346 total documents。
- hierarchy lineage error：0。
- 18/18 route 有 leaf；全部 leaf／parent 可从对应 store 读回。
- 模型调用：0。
- 网络调用：0。
- 隔离环境：`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\haystack_3_1_0_env`。

当前正确机械结果为：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\haystack_parent_child_attempt_20260902T112000Z_04`

- result schema：`fin_ia_dell_haystack_parent_child_qualification_result_v1_1`。
- manifest SHA-256：`3718ee8ca2df591135ada7e69275eee8038a23f6eaf218c616c48bf65c9c57b6`。
- query results JSON SHA-256：`1096afb15319a7192d7f0aab20fa96841bc82cdf70d047088a857f1996f0c573`。
- query results JSONL SHA-256：`ef91f549ef6c25be49e2b2d2bd374cca17ba95b1709e3853de649a06a2e8af2c`。
- peak observed RSS：约 124 MB。
- canonical document JSON disk estimate：约 5.75 MiB。

两个 predecessor 不可覆盖：

- `_02` 把 9 条 local 与 10 条 external 混进 retrieval aggregate，结论口径有缺陷；只保留为 diagnostic failure evidence。
- `_03` 已拆分 query scope，但新增 per-query metric 时没有同步升级 query-result schema；只保留为 superseded attempt。

`_04` 修正了两点：

1. `reviewed_first` 与 `external_required` 完全分组；
2. 同时记录 raw candidate chars 和按当前 reader `1,200 chars/candidate` 归一化的 delivery-cap context，避免把 raw chunk 变化误写成已证明的 Agent token 节省。

## 3. bridge 和 branch contract 修正

新 bridge v1.2 仍输出同一 597 条 candidate，但现在保留并校验：

- `route_id`；
- `parent_document_id`；
- `chunk_index`；
- `page`；
- `parser`；
- `splitter`；
- `branches`；
- `text_sha256`；
- `raw_body_sha256`。

它还逐行复算 `sha256(text)`，不再只检查 digest 字符串格式。当前 successor：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\knowledge_bridge\combined_a02_e0_provenance_v1_2_attempt_20260902_02`

- records SHA-256：`ac5c091c61484c2d2532913df337c2d9d447b1b4bf7f191860dfae75c146836b`。
- result SHA-256：`544c7decb5d6e364a9e6072e397cbbc6ed751a0fac04c82427f38d2971ce4bef`。
- text digest mismatch：0。

reader 仍先对全库 BM25 打分和排序，再对带 `branches` 的新行做 eligibility post-filter 后返回；历史无 branch 行继续兼容。这个修正关闭了返回面的 branch leakage，但不是 branch-scoped index：被排除行仍会影响全库 IDF／score。历史无 `route_id` 行仍以 source URL 作为最低 locator，不因新细粒度 lineage 字段而回退成 `source_locator_available=false`。

该 bridge 只保留 lineage；没有伪造 parent body，也没有自己实现 parent-child retrieval。

## 4. 机械结果：只看 9 条 reviewed-first

| 指标 | flat post-filter | Haystack leaf | Haystack parent-child |
|---|---:|---:|---:|
| branch violations | 0 | 0 | 0 |
| unique routes/query | 2.889 | 3.000 | 3.000 |
| top-route share | 0.611 | 0.611 | 0.565 |
| raw context chars/query | 12,353 | 9,089 | 9,165 |
| 1,200-char delivery-cap context/query | 7,126 | 6,639 | 5,972 |
| mean retrieval latency | 2.32 ms | 与 parent 同次计算 | 14.25 ms |

正确解读：

- 旧 flat 未过滤返回面在全 19 条 query 中有 11 次 branch violation，9 条 reviewed-first 中有 5 次；successor flat 用 post-score eligibility filter 把返回面 violation 降为 0，Haystack 则用真正的 metadata prefilter 降为 0。不能把两条路径都称为 prefilter。
- Haystack leaf／parent 的 source diversity 有小幅改善，不是“完全没有改善”。
- raw context 从 flat 到 parent 约减少 25.8%；按当前 reader 1,200-char delivery cap 同口径约减少 16.2%。这仍不是已实现的模型 token 节省，因为产品 Haystack adapter 的最终 delivery contract 尚未定义。
- 绝对延迟仍低；约 6 倍的相对变慢不是当前主要 blocker。

## 5. 独立人工相关性复核

人工 reviewer 对每条候选按 `0–3 relevance` 和 `0–3 context completeness` 评分，并把系统输出映射回 query。严格人工 qrels 尚未预先冻结，所以该结果是开发集审计，不是 holdout product gate，更不是 Owner 产品验收。下面的汇总只有在逐 query／candidate 评分、source target 和输入 digest 被持久化并可重算后，才可作为冻结的资格证据；在此之前只能视为 reviewer 的开发判断。

| 系统 | candidates | mean relevance | mean context | relevance >=2 | relevance=0 |
|---|---:|---:|---:|---:|---:|
| flat post-filter | 54 | 1.296 | 2.241 | 40.7% | 31.5% |
| Haystack leaf | 54 | 1.407 | 2.333 | 46.3% | 24.1% |
| Haystack parent-child | 49 | 1.367 | 2.347 | 44.9% | 26.5% |

因此：

- leaf 的 passage relevance 是小幅、真实的改善；
- parent-child 没有比 leaf 稳定提高 relevance，context completeness 只增加约 0.014/3；
- parent merge 只在 9 条中的 Q1 和 Q12 触发；Q1 恢复了完整 FY27 Q2 release，确实有价值；Q12 只是把多个 Blackwell 片段合成更宽的产品 parent，没有关闭 hyperscaler coverage。

人工构造的 source target 开发集上，flat／leaf／parent 的 Recall@6 都是 `10/17 = 58.8%`。Q2 prepared remarks 不在 frozen corpus，作为 input-coverage miss 排除在 ranker 分母外。

这说明成熟 stack 当前改善的是部分 source 内 passage 选择，不是 source-family coverage。

## 6. 仍会误导 Agent 的问题

高风险例子：

- Dell-specific query 被 HPE 内容占据；
- FY26 背景被拿来回答 FY27 Q2 current state；
- CSG consumer ASP 或会计 `transaction price` 被拿来回答 AI-server ASP；
- NVIDIA product marketing 被拿来回答 hyperscaler capex；
- BIS rule 或 Dell 在华制造设施被拿来回答 Dell Greater China revenue exposure；
- Micron／NVIDIA 单一供应层被写成完整 supplier value pool。

人工 stress-test 计数：flat `25/54`、leaf `27/54`、parent `25/49` 具有潜在 wrong-issuer／wrong-period／wrong-segment／wrong-metric 替代风险。它们不一定是错误材料，但不能在缺少元数据约束时被模型当成查询主体事实。

source-level 主要缺口：

- Q4：Mistral/NxtGen routes 已在 corpus，但未进 top6；
- Q10：没有检出 Dell issuer-specific supply/price commentary；
- Q12：Microsoft／Amazon／Meta 均在 corpus，单次 top6 只覆盖一个 hyperscaler；
- Q16：corpus 本身没有 Supermicro／Lenovo primary financial source；
- Q2：FY27 Q2 prepared remarks 不在 frozen corpus。

表格层也没有被 parent-child 神奇修好。它仍缺稳定 table／row／footnote locator；word-based `900/240/30` hierarchy 不是 heading-aware 或 table-aware。精确数字继续走 S2 或 source-bound calculation lane，普通 narrative RAG 只给 candidate context。

## 7. external-required 不计本地 Recall

10/10 external-required query 在 flat 和 Haystack 都返回了本地近似 candidate。机械统计把它们全部视为 local-substitution risk，而不是 recall success。

人工判断 10 条中至少 7 条存在实质替代风险，尤其是 procurement price/unit、firmware/availability、多供应商供给、BIS threshold、完整 value pool、double-ordering 反证和 current margin/WC/cash conversion。

两个 route 可以在 successor foundation 中先纠正：

- exact FY27 Q2 SEC Exhibit 已在本地 reviewed corpus，Q3 不必继续标成纯 external-required；
- exact MLCommons source 已在本地，Q13 可先 reviewed-first，再外源刷新。

其余外源问题必须走真正的 discovery/capture，不能用本地“看起来相关”文本替代。

## 8. Build／Adopt／Hold 决定

- Haystack 3.1.0 作为成熟组件：`ADOPT_AS_QUALIFICATION_CHALLENGER`。
- `InMemoryBM25Retriever + metadata filter` 方向：`CONDITIONAL_ADOPT`，前提是下一轮关闭实体／期间／指标误归因并提高 source recall。
- `HierarchicalDocumentSplitter`：继续作为 challenger，不进入 product mainline。
- 当前 `AutoMergingRetriever(900/240/30, threshold=0.5)`：`HOLD`；只在 2/9 query 激活，不应作为全局默认路径。
- 完整 Haystack product adapter：`HOLD`。
- WeKnora sidecar：本轮 `HOLD`。
- 旧 flat reader：不再用于新 Dell vertical；不删除，作为历史兼容和 regression baseline 保留。

runner 只位于 `scripts/qualification/`；不得由 product runtime import。其 1,300+ 行只服务输入绑定、零模型 A/B 和 receipt，不是新的运行框架。若采用决定仍为 HOLD，后续不得继续扩写为平台。

## 9. 最小下一步

下一轮不调大量关键词，也不先跑模型：

1. 把本次 9 条 reviewed-first 人审结果冻结成 development qrels，字段只包括 source target、acceptable alternative、passage relevance、issuer/source role、period、segment、metric type、context completeness。
2. 先补当前 case 真正缺的官方输入：FY27 Q2 prepared remarks／performance review、Dell PowerEdge availability/firmware、Dell current supply/price commentary、Microsoft/Meta/Amazon/Google demand、HPE/SMCI/Lenovo peer primary sources。
3. 给 source 写通用 metadata，不写 Dell 关键词规则：`issuer/entity`、`source_role`、`publication_date/fiscal_period`、`segment`、`metric_type`、`document_kind`、`branch`、locator。
4. 把复合 query 拆成 issuer／peer／supplier／hyperscaler／regulator 等 source-role 子查询，分别检索后再做有限 source diversity merge。
5. 用同一 qrels 重跑 zero-model benchmark；只有 source Recall、passage ranking、misleading substitution、Q4/Q10/Q12、locator 和 clean commit-bound attempt 同时改善，才决定是否写薄 product adapter。

当前结论不是“Haystack 不行”，也不是“parent-child 已通过”，而是：成熟 leaf retrieval 有可复用价值，默认 parent merge 尚无足够收益，当前最早责任层仍是 corpus coverage 与通用 metadata/query decomposition。

## 10. Structured corpus attempt12 的边界

当前新 vertical 的结构化语料为：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\structured_corpus\dell_structured_corpus_attempt_20260902_12`

- 20/24 declared sources 在本地可用并解析成功；4 个 declared unavailable source 保持显式不可用。
- 产物为 20 documents、135 sections、1,779 blocks、701 chunks、234 table blocks、26 image references；structured parse failure=0，model/network calls=0。
- `authority.retrieval_candidates_only=true`、`numeric_fact_authority=false`、`automatic_evidence_promotion=false`，且 `manual_review_complete=false`、`retrieval_promotion_authorized=false`。
- 五份 PDF 走 `pypdf_pages`。实现实际使用 `page.extract_text()` 默认文本提取，每页只生成一个 `page_text` block，以页码作为 locator；它没有原生表格行列、bbox、阅读顺序、caption、footnote 或跨页结构。parser 字符串虽以 `_layout` 结尾，代码并未启用 pypdf layout mode，因此最准确表述是“页级 PDF 文本候选”，不是 layout-aware financial parser。
- 26 个 image references 只是从已有 Markdown 文本中提取的 `alt/target` 引用，不包含 image bytes、OCR、caption-object 绑定或视觉语义。**Image lane 保持 HOLD**；不得把 `image_reference_count=26` 写成图像解析通过。

因此 attempt12 是可复算的 structured candidate corpus，不是完整 PDF/image ingestion acceptance。113 条 `manual_review_queue` 在 artifact 中仍是 pending；本轮完成的是对 route 决策和 L10/L11/L23/L26 的作者分离原文/chunk 审计，不把它夸成 113/113 全量 blind review。

## 11. Full-stack attempt03 精确机械结果与采用决定

Attempt：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\retrieval_qualification\dell_rag_full_stack_preview_attempt_20260902_03`

它覆盖 33 queries×4 routes；指标只计算 29 个 local queries，其中 critical=19，4 个 external 仅作 local-substitution diagnostics。attempt 为 dirty `engineering_preview`，`formal_eligible=false`、`manual_review_complete=false`、所有 promotion flag=false。

| Route | Hit@5 / Hit@10 / Hit@20 | MRR | Critical direct miss @5/10/20 | Critical delivered-facet miss @5/10/20 | Rank-1 hard negative / precedence failure | 决定 |
|---|---|---:|---:|---:|---:|---|
| BM25 | `28/29 / 29/29 / 29/29` | `0.85632183908046` | `0/0/0` | `0/0/0` | `0/0` | 工程预览默认基线；formal HOLD。 |
| Dense | `25/29 / 26/29 / 28/29` | `0.815873582432135` | `2/2/1` | `2/1/1` | `0/0` | 拒绝独立默认；只可作为 fusion 辅助信号。 |
| Hybrid RRF | `28/29 / 28/29 / 29/29` | `0.798629531388152` | `1/1/0` | `1/1/0` | `0/0` | 保留 challenger/candidate-pool route。 |
| Qwen reranker | `27/29 / 29/29 / 29/29` | `0.814655172413793` | `0/0/0` | `0/0/0` | `1/1`（L10） | 拒绝当前配置/排序；修复后用新 attempt。 |

Dense 还存在 27/890 document truncations；reranker 有 6/845 pair truncations，且 GPU peak reserved=`8,317,304,832/8,585,216,000` bytes（96.8794%）。attempt 总时长 215.401s，但只有 Dense artifact build 的 53.299s 可单独归因，不能据此声称 route-level latency/cost 优势。

## 12. L10/L11/L23/L26 原文与 chunk 人工裁决

- **L10（cash-flow stock/flow）**：BM25 top1 是正确 cash-flow table `BLOCK::C46E0FD5E2F8AA3DCA4B20F5`。Qwen reranker 却把 AR balance/stock 叙述 `CHUNK::75CBF1ABE3FC81CF998E13E1` 提到 rank1，正确表仅 rank5，同时另一 balance-sheet hard negative 位于 rank6。这是实际语义 precedence failure，不可由 Hit@10/20=100% 抵消，故拒绝当前 reranker。
- **L11（pull-forward 与 durable demand）**：top anchor `CHUNK::C555524A6CE91A096CFFF279` 和相邻 `CHUNK::2FEB7579E112C8CF854CA682` 共同闭合两项 required facets；真实 MCP delivery 同时交付了二者。neighbor expansion 合法提升 delivered-context answerability，但第二 anchor 在 BM25/Dense/RRF/reranker 的全局 rank 分别为 16/14/13/12，因此 Top10 direct anchor 仍不完整。
- **L23（NVIDIA FY27 Q2 Data Center actual）**：BM25 top1 `MIXEDPROSE::8B756...` 混入 FY27 Q3 outlook；它既不是所问 FY27 Q2 actual，也未被当前 qrel 标成 partial/hard negative。top2 `MIXEDPROSE::050572...` 有总收入与 Data Center 同比，但缺完整 Data Center 环比；top3 `CHUNK::E8B7CE442115ACDBFFDD38A4` 才完整直接支持 Data Center revenue `$89.0B`、q/q `+18%`、y/y `+117%`。
- **L26（Micron FY26 Q3 actual）**：BM25 top1 `MIXEDPROSE::0E3F...` 只有当季 revenue；top4 `BLOCK::FA63...` 与 top5 `BLOCK::B27...` 是 FY26 Q4 outlook；top6 `BLOCK::66DB3ED43C0D0E1952012210` 才是完整 Q3 actual GAAP 表，含 revenue `$41,456M` 与 gross margin `84.6%`。

L23/L26 都不是 parsing loss：完整 actual 节点已经在 candidate pool 内。最早责任层是 ranking 对 `actual vs outlook`、`full vs partial` 的 precedence，以及 qrel 对前置误导候选的标注不完整。当前自动 Hit@5/10 和 hard-negative/precedence 汇总因此对真实可用性**偏乐观**；保留其机械可复算值，但不得拿它单独签资格。

## 13. 最诚实的当前运行资格

不重跑全栈时，应表述为：

`DIRTY_ENGINEERING_PREVIEW / STRUCTURED_CANDIDATE_MCP_SMOKE_PASS / SELECTED_DECISION_CRITICAL_MANUAL_AUDIT_COMPLETE / QREL_PRECEDENCE_GAP_OPEN / BM25_PROVISIONAL_BASELINE / HYBRID_CHALLENGER / DENSE_AND_RERANKER_NOT_ADOPTED / PDF_PAGE_TEXT_ONLY / IMAGE_HOLD / CANDIDATE_ONLY / FORMAL_HOLD`

这允许新 Dell vertical 通过 `StructuredLocalKnowledgeReader` 使用 attempt03 的 metadata-prefilter BM25 candidate path；`FrozenLegacyLocalKnowledgeReader` 不再属于新 vertical，只保留旧回归。它不授权 citation/Evidence、NumericFact、automatic reranking、full PDF/image claim、A02、报告、产品、publication 或 release。Formal 前至少需要：补齐 actual/outlook/full/partial qrel 与人工 receipt、重新计算受影响 precedence/quality 指标、关闭 reranker L10、补齐 truncation IDs/route latency，并在 clean bound attempt 上完成规定的人工审阅；无需为了当前 HOLD 结论立即重跑付费或模型全栈。

## 14. Bounded candidate judge attempt01：失败且不重试

Attempt：

`Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\candidate_judge\dell_bounded_candidate_judge_attempt_20260902_01`

该 attempt 只做了一次 DeepSeek V4 Pro nonthinking JSON 调用：HTTP 200、finish reason=`stop`、usage=`8,676` tokens，但输出未通过 strict host schema，终态为 `candidate_judge_output_invalid / terminal_failed_candidate_only_no_retry`。`terminal_failure.json` SHA256=`7235ad01b4d23357e0d093416b6a949be1613e4b8fc0777100c0e6c70cc8ef92`；`retry_count=0`、`fallback_model_used=false`、`candidate_selection_promoted=false`、`source_attempt_mutated=false`、`evidence_promotion_authorized=false`、`formal_qualification_claimed=false`，因此 full-stack attempt03 未被修改。

语义复核也不支持绕过 schema：L23 错选缺少 Data Center q/q 的 `MIXEDPROSE::050572...`，把总营收 q/q 迁移成 Data Center q/q，并将真正完整的 `CHUNK::E8B7CE442115ACDBFFDD38A4` 判为 partial；L26 虽正确选择完整 actual 表 `BLOCK::66DB3ED43C0D0E1952012210`，却又把仅有 revenue 的 `MIXEDPROSE::0E3F...` 自相矛盾地判为 `full_support`。结论保持 **HOLD / no retry**：模型判断可作为候选辅助，但不能替代 host schema、原文核对和 qrel/precedence validation，也不能修饰 attempt03 的机械指标或产生 promotion。

## 15. A02 使用边界

Owner 已授权新 Dell vertical 做一次完整九分支 start→HITL 资格运行，但这不改变本工作包的 formal 结论。A02 可以把 attempt03 的 structured BM25 path 作为明确标注的 engineering-preview candidate input；不允许宣称 Haystack、parent-child、Dense、reranker、PDF/image 或 qrel precedence 已正式通过，也不允许自动把任何 retrieval candidate 晋升为 Evidence。若 A02 内容质量良好，只能证明这一个 case 在当前候选数据面上能够产生可审计 workpapers/Counter/Lead；formal retrieval promotion 仍须另行关闭 L23/L26 qrel precedence、L10 reranker、truncation 与完整人工 receipt。
