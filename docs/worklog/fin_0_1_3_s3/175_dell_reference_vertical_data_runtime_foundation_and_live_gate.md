# DELL 单案例完整纵切：数据与运行地基、首轮真实运行门

更新时间：2026-09-02
状态：`A01_IMMUTABLE_FAILURE / STRUCTURED_S1_MCP_AND_S2_EXACT_PERIOD_SMOKE_PASS / SUCCESSOR_REPAIR_ACTIVE / FORMAL_HOLD`
产品范围：只做 `DELL_AI_INFRA_REFERENCE_VERTICAL`，不是恢复 R14，也不是扩展成通用研究平台。

## 1. 这次到底要证明什么

目标是用一个 DELL 案例演示接近产品最终形态的完整纵切：真实数据工具、动态任务 DAG、相互隔离的 Specialist、Evidence/Finance 并行取数、Counter 定向回派、Lead 综合、可暂停人工审核、可恢复渲染，并留下来源、token、调用、耗时和失败收据。

本轮不追求全市场、任意公司、100% 准确率或极限低 token。允许有清楚标注的不确定性；不允许候选资料伪装成 Evidence、工具失败伪装成公开信息缺口，或 current Q2 文字数字伪装成 S2 结构化事实。用户于 2026-09-02 进一步明确：非 S2 权威来源中的可定位数字可以进入确定性计算器，但结果必须保持低权威派生状态、携带输入来源与公式，并在 Agent 使用及下游推理时显示提醒；不得因此晋升为 `NumericFact`，也不得用硬门妨碍模型正常分析。

## 2. 已冻结的数据面

| 数据层 | 当前内容 | Agent 权限 | 冻结身份 |
|---|---:|---|---|
| Local Knowledge | 18 份官方正文、597 个检索记录 | 只作为 `retrieval_candidate`；不可直接引用 | `records.jsonl` SHA-256 `47d518b9...bef9`；result SHA-256 `5d2014eb...9bf2` |
| Reviewed Evidence | base 55 条 + DELL FY27 Q2 case overlay 6 条 = 61 条 | 可引用、可进入 citation index | base projection digest `2d4e3d57...eccd`；overlay file SHA-256 `1479e49f...eb9`；composite digest `c91d5c58...7e7d` |
| S2 NumericFact | 11 家公司、4,586 observations、12 个直接指标和 3 个 executor 派生指标 | 只读 SQL 数值权威 | SQLite SHA-256 `9c962b1d...a656`；result SHA-256 `bc5830e9...0922` |
| Live public source | Exa hosted MCP discovery，DDGS 只作诊断 fallback；静态抓取后按需 Playwright | 新结果仍是 candidate，不能自动晋升 Evidence | 每次 MCP 调用独立 receipt；production crawler 仍为 `HOLD` |

当前季度边界：2026-09-01 提交的 Dell FY27 Q2 SEC Exhibit 99.1 已进入 6 条 Reviewed Evidence，所以 Agent 能引用发行人原文可见的 orders、revenue、backlog、分部和 guidance；但该 Exhibit 没有 inline XBRL，CompanyFacts 尚未出现对应 accession，因此 current Q2 仍不是 S2 NumericFact。原“比率、差额、PVM、转化率一律保持 null”的规则已被 Owner 纠正：successor 新增与 S2 `NumericFact` 明确分离的 `research_calculation` 合同，允许对已审核、可定位的非 S2 数字做确定性计算、比较和情景推理，同时逐输入保留 source locator、input authority、period/unit，逐输出保留 formula trace、assumption、`numeric_fact_authority=false` 与呈现提醒。它不是模型猜出的 estimate，也不授权把 Exhibit 数字写入 S2 或伪装成权威事实。

## 3. 研究问题和九个分支

正式问题固定为：

> 截至 2026 年 9 月 2 日，Dell 的 AI 基础设施业务增长到底有多大、多可持续、能否转化为收入利润和现金流；架构迭代、GPU 与内存供给、价格数量组合、客户需求及对华出口管制分别怎样影响兑现，最强反证和后续验证指标是什么？

Planner 必须覆盖九个分支：发行人事实、需求质量、units/ASP/PVM、架构量产、供应与价格、模型算力需求、出口管制与中国、竞争/价值池、反证与 what-would-change。共同研究方法已由 foundation JSON 一次性注入；它约束口径、时间点、公式和停止条件，但不注入题目答案。

## 4. 运行面：成熟底座和 FIN 自有边界

采用成熟底座：

- LangGraph：动态图、并行 fan-out/fan-in、interrupt、SQLite checkpoint 和 resume。
- 官方 MCP Python client/server：统一 Knowledge、Evidence、Finance、外源发现和抓取工具协议。
- Pydantic：结构化输入输出与 fail-closed contract。
- `langchain-deepseek`：DeepSeek structured output transport；provider 自动 retry 为 0。
- SQLite：本次本地资格运行的只读 S2 mart 和 checkpoint；PostgreSQL/pgvector 保留为部署目标，不为一个案例强行启动不稳定的本机 Docker。
- 现成 BM25 legacy reader：这是 A01 predecessor 的已冻结 candidate bridge；structured successor 已由 `StructuredLocalKnowledgeReader` 取代其在新 vertical 中的消费，legacy 仅留历史回归。不再建设 cell 绑定壳、通用 GraphRAG 或自研向量数据库。

FIN 只保留薄的、确实属于产品的部分：

- 九分支金融研究方法和口径；
- Candidate / Reviewed Evidence / NumericFact 三层权威；
- DELL case foundation、MCP 薄适配和 citation index；
- current-Q2 文字证据与 S2 数值事实的权限隔离；
- 报告人工审核门和 Workbench 投影。

图的真实拓扑为：`bind → planner → Evidence/Finance 并行 → 9 个隔离 Specialist → Counter → 最多 1 个定向回派 → Lead → verify → HITL → resume → render`。这不是把固定 prompt 顺序包装成“multi-agent”：每个 Specialist 有独立输入、独立工具结果和独立 workpaper，Counter 只能选择一个分支回派，resume 不重跑已完成节点。

## 5. 有界运行合同

- 单公司 case；上下文公司只用于需求、供应、竞争和反证，不变成第二案例。
- 9 个 branch，最多 1 次定向回派。
- 最大图并发 3。
- A01 的 13 次模型调用上限仅是首飞保险线，不再作为 successor 的质量目标或固定产品合同。successor 必须根据实际 branch 数、材料规模、外源缺口、必要 follow-up、Counter/Lead 验证负荷形成 task-specific `TokenBudgetBasis` 和计划调用预算；只保留防失控的异常保险线，不得为了守住 13 次或任意低 token 数删掉必要研究工作。
- provider transport 每个节点最多 1 次，自动 retry 0。
- 外源高重要性分支最多 2 轮搜索；每次最多 6 个结果；每分支最多抓 4 页；全 run 最多 24 个 live page。
- Planner 输入调用前保险线 120,000 字符。真实九分支 deterministic fixture 为 81,082 字符；不为压 token 删除必要研究方法。
- 第一次真实运行只允许 `start → HITL`；不会自动 approve、不会自动发布。

## 6. 首次真实运行的唯一身份

- attempt ID：`20260902-dell-reference-vertical-q1-a01`
- run ID：`dell-reference-vertical-q1-run-a01`
- data snapshot ID：`20260902-dell-a02-a04-reviewed-evidence-composition`
- research as-of：`2026-09-02T23:59:59+08:00`
- foundation SHA-256：`bf214a08...6d47`
- DeepSeek config SHA-256：`03115289...6fc8`
- 模型：`deepseek-v4-pro`，thinking disabled，structured output，0 retry。
- 唯一可执行 run authority：`scripts/research/run_dell_reference_vertical_q1_a01.ps1`。它固定上述身份、完整输入路径和 SHA、D 盘 `.venv` 及 API key 环境变量名；`-PreflightOnly` 与正式 start 使用同一参数集合，禁止临场改写参数。

正式 start 前必须同时满足：

1. 分支精确为 `codex/fin013-dell-s1-s2-product-bridge`；
2. 当前实现、测试、依赖和本文件进入一个 clean Git commit 并推送；
3. manifest 绑定 commit、tree、critical-source bundle、`pyproject.toml`、`uv.lock` 和 graph contract version；
4. focused offline gate 全绿；
5. 同一 attempt/run 目录和 checkpoint 均不存在；
6. zero-call preflight 在同一 clean commit 通过。

同一 attempt 永不覆盖。第一次真实运行不因模型格式、工具失败或内容不理想而偷偷重试；只有在保存失败证据、找到最早责任层并另行批准后，才允许新 attempt。

## 7. HITL 的人工验收

到 HITL 后先停，不生成“已通过”的对外结论。人工检查并另存 Z 盘审计 artifact：

- 是否真的生成 9 份 workpaper；是否只发生 0 或 1 次定向回派；
- Lead 是否先回答商业结论、数字、机制、时间和反证，而不是堆边界说明；
- 每个引用 ID 是否能在 citation index 定位到 Evidence/Fact URL、period、unit 和 digest；
- candidate 是否被洗成事实；current Q2 数字是否越过 S2 权限；
- generic hyperscaler capex 是否被误写成 Dell 份额；模型能力是否被误写成 Dell 采购；
- announcement、sampling、production、shipment、deployment、revenue 是否被混写；
- token、调用数、wall-clock、MCP 失败和 model journal 是否完整；
- 结论中的 material claim 是否由实际匹配的来源支撑。

只有人工 claim/source/numeric audit 通过，Owner 才另行决定是否在同一 clean commit 上 approve/resume。否则保持 immutable failure；不把“图跑完”写成产品通过。

## 8. 当前工程验证

- 关键图、真实数据组合、MCP 失败诊断、DeepSeek adapter、CLI/HITL 恢复、Q2 overlay、S2 data ports 和真实 MCP 数据：`67 passed`。
- 全部新增 DELL data/runtime 与 Workbench 相邻测试：`175 passed`；repository secret scan：`8,386 files / 0 findings`。
- 覆盖：调用前输入上限、模型 started/outcome journal、并发上限、aggregate external budget、citation index、S2 SHA TOCTOU、MCP semantic/transport failure、外源单点失败保留收据后有界降级、真正 fatal tool failure 在 Counter/Lead 前停止、terminal checkpoint 幂等恢复、approved→render 恢复、artifact drift、Git commit/tree/source SHA 与实际 Python module origin 双重绑定，以及唯一无密钥 run authority。
- 模型调用：0；外源网络调用：0（上述工程门）。

因此当前结论是：上述 `67/175 passed` 只证明 A01 前的离线工程资格，不等于研究内容、公开演示、生产部署或产品验收已经通过。

## 9. 2026-09-02 A01 真实失败与 successor 更正

- A01 已在 clean pushed commit `9a276d8db77525b86754ea321264614eec9cae4a` 真实启动，不再是“等待首次 live start”。Planner 仅调用 1 次，HTTP 200、`finish_reason=tool_calls`，返回 9 branches、19 evidence requests、10 external-required requests、4 fact-request groups；实际 usage 为 input `21,465`、output `2,076`、total `23,541`。
- `langchain-deepseek` 选择的 `PydanticToolsParser` 把已解码 Python `list` 直接校验到 strict tuple，导致 `PlannerSemanticPayload.tasks` 失败；同一原始 `function.arguments` 经现有 `model_validate_json` 通过。最早责任层为 provider structured-output adapter，不是 Planner 内容、数据、HTTP 或外源。
- Evidence/Finance、外源 discovery/capture、Specialist、Counter、Lead、HITL 和报告均未执行。A01 不覆盖、不重试；失败证据位于 `Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\runtime\attempts\20260902-dell-reference-vertical-q1-a01\manual-audit.at-start-failure.json`。
- successor 保留 LangGraph；当前修正没有宣称删除 `langchain-deepseek` 依赖，而是把它自动选择的 `PydanticToolsParser` 移出关键校验路径：向 provider 传 OpenAI-style JSON function schema，先取得普通 mapping，再由本项目现有 `model_validate_json` 严格验证原始 JSON 语义。失败后 token 汇总也已区分 provider 已收费总量、成功调用与 HTTP 200 后本地解析失败调用。直接官方 SDK transport 仍是后续可替换选项，只有完成等价性实测后才切换，不能在本轮把“修 parser”夸成“已删除 LangChain”。新的付费 attempt 仍需新 ID、clean commit、zero-call preflight 和 Owner 明确授权。

## 10. RAG、外源、低权威计算与预算的最小资格门

本工作包不再写通用 RAG 平台，只做一个 Dell 冻结语料／真实问题切片：

- **假设**：成熟父子分块/回捞机制可以替代当前 `2400 chars + 300 overlap + flat BM25` 的大部分自研壳，同时保留 FIN source/as-of/authority contract。
- **当前基线**：18 份官方正文、597 records；桥接投影丢失原 chunk 的 `route_id/chunk_index/page`，reader 未按 record `branches` 过滤，命中后不能可靠回捞父块或相邻上下文。
- **候选边界**：一个 default、最多一个 challenger；优先实测 WeKnora parent-child/preview 与一个轻量 Python 成熟组件，不把完整平台直接写入正式依赖。
- **测试对象**：同一冻结正文、同一 source metadata、同一组公开 development queries；比较 source/branch filter、child hit、parent expansion、locator preservation、上下文重复率、延迟、内存、adapter 厚度和可退出性。
- **停止条件**：候选需要复制 FIN 权威、必须依赖不可用云服务、无法保留 locator/as-of/source identity、资源明显不适合本地单 case，或必须新增大量 issuer-specific 规则时停止采用。
- **外源门**：在交给 Agent 前，由实现者对 Planner 的 10 个 `external_required` 请求逐类验证 discover/open/capture/source quality；找不到时只能记录经过尝试的真实公开边界，不能直接称 gap。
- **低权威计算门**：计算结果必须与 S2 NumericFact 分表/分状态，输入逐项绑定来源和单位，公式确定性，输出携带醒目标识；提醒不阻止模型继续推理。
- **预算门**：以任务拓扑和必要 follow-up 推导 planned calls/tokens；异常 ceiling 只防循环失控，质量验收不以“<=13 次”或极限低 token 为目标。

本门允许本地只读审计、Z 盘隔离安装、无模型的分块/检索 A/B、公开网页可达性验证、代码/测试修复；不授权自动创建或启动 A02。

## 11. Successor 当前已完成的资格化结果

### 11.1 冻结本地知识桥

- 新 bridge v1.2 仍输出 597 条 frozen candidate，但不再丢掉 `route_id`、`parent_document_id`、`chunk_index`、`page`、`parser`、`splitter`、`branches`、正文 digest 和 raw-body digest，并逐行复算 `sha256(text)`；结果位于 `Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\knowledge_bridge\combined_a02_e0_provenance_v1_2_attempt_20260902_02`，records SHA-256=`ac5c091c...836b`，result SHA-256=`544c7dec...4bef`。
- reader 现在会在全库 BM25 打分和排序后，对带 `branches` 的新记录执行 branch eligibility post-filter，再把 locator/lineage 返回给 Agent；没有 `branches` 的历史行仍按旧合同兼容。它已经关闭“错误 branch 候选被返回”的 leakage，但排除行仍参与全库 IDF／score，不能写成 branch-scoped prefilter。这个 flat bridge 没有伪造不存在的 parent body，也没有宣称已经实现 parent-child retrieval。

### 11.2 成熟父子检索 A/B

- WeKnora 仍是产品级集成候选，但本机 source clone／重试不稳定，且整套服务对单案例过重，所以没有把它写进正式依赖或围绕它自研兼容层。
- 在 Z 盘隔离环境真实安装 Haystack 3.1.0，并对同一 18 source／597 old chunks／19 A01 queries 做零模型 qualification。层次结构生成 241 parents＋1,105 leaves，lineage error=0；旧 flat 未过滤返回面在全 19 条 query 有 11 次 branch violation，修正后的 flat post-score eligibility filter、Haystack metadata-prefilter leaf 与 parent-child 返回面均为 0。两者不能混写为同一种 prefilter。
- 首个 aggregate 错把 9 条 `reviewed_first` 与 10 条 `external_required` 混算，已作为有缺陷 predecessor 保留。当前 v1.1 attempt=`haystack_parent_child_attempt_20260902T112000Z_04` 严格分组；manifest SHA=`3718ee8c...57b6`、query result SHA=`1096afb1...c573`。
- 只看 9 条本地问题，flat→parent unique routes 为 `2.889→3.000`、top-route share 为 `0.611→0.565`；raw candidate context 为 `12,353→9,165`（约 -25.8%），按当前 1,200-char reader delivery cap 同口径为 `7,126→5,972`（约 -16.2%）。这不是已经证明的 Agent token 节省，因为未来 Haystack adapter 的 delivery contract 尚未定义。
- 独立人工开发集复核显示 flat／leaf／parent 平均 relevance=`1.296/1.407/1.367`，source Recall@6 三者同为 `10/17=58.8%`；leaf passage quality 小幅改善，但 parent merge 只在 2/9 query 触发，且实体、期间、segment、metric type 误替代仍多。该评分必须绑定逐候选 review receipt 才可作为可复算资格证据，且始终不是 Owner 产品验收。因此 Haystack leaf 只保留为 mature challenger，当前 AutoMerging 与 product adapter 均 `HOLD`。
- 所有 10 个 `external_required` query 都命中本地近似内容，只能记 local-substitution risk，不能记 recall success。runner 只存在于 `scripts/qualification/`，不得被 product runtime import；详见 S3/177。

### 11.3 外源人工可达性与实际 adapter 行为

- 人工只读审计已经给 A01 十个 external-required topic families 找到可执行的公开来源梯子，并冻结 supports／does-not-support／真实公开边界；详见 S3/176。资料“人能找到”已经证明，不再把尚未执行搜索称为公开信息 gap。
- 但当前 Agent adapter 还不能据此判 PASS：Exa 广义和 exact accession 查询能找到 SEC/Dell 与 OpenAI、BIS、Supermicro 等候选，但同一 exact query 的短重试可返回 0；Q5 supply/price 的一次 include-domain probe 也是 0 accepted；SEC static capture 实际返回 403，Dell IR static HTML 实际超时。
- static capture 已把 HTTP 403、timeout、connection、request failure 分成 typed failure，且都明确 `not_public_information_gap`。下一步应先补“已知官方 URL/API 优先、搜索 discovery 补充、失败再走 issuer fallback”的薄路由并保存 durable receipt；不能把搜索命中数或人工浏览结果伪装成 Agent capture 已通过。

### 11.4 非 S2 确定性计算

- 已生成 case-only `research_calculation` pack：51.6% AI/ISG、34.9% AI/company、15.1% ISG margin、3.71x orders/revenue、5.79x backlog/revenue、23.3% AI guidance uplift、15.0% company guidance uplift。每项保留输入 Evidence、URL/digest、period/unit、公式和 stock-flow caveat，且统一 `numeric_fact_authority=false`、S2 write=false。
- artifact 位于 `Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\research_calculations\attempts\20260902-dell-fy27q2-non-s2-research-calculation-a01`，pack SHA-256=`121151f1...51e`。这只是 Dell case qualification generator，不是新的通用指标平台，也还没有自动获得 Agent/MCP consumption authority。

### 11.5 调用预算纠正

- A01 的 13 由图拓扑相加而来（Planner 1＋9 Specialists＋Counter 1＋可选回派 1＋Lead 1），不是研究质量证明。A01 实际只消费 1 次 Planner／23,541 tokens，就因本地 post-response parser 失败停止，与 13 次 ceiling 无关。
- 当前 config 的 `maximum_specialist_model_rounds=2` 还没有真正绑定到 runtime，是一个必须在 A02 前关闭的 dead field。successor 预算应按每个节点的材料量、schema 负担、需要的 follow-up 和质量风险写 `TokenBudgetBasis`；可以设置防循环的异常 safety ceiling，但不能把 13 或任意 token 数当成必须用完／必须压住的产品 KPI。

截至本节，新的付费 A02 仍未创建或启动；完整纵切尚未跑到 Specialist、Counter、Lead、HITL 或报告。

## 12. Structured S1 MCP 与 S2 exact-period 真实消费复核

本节记录的是当前 working-tree successor 的真实本地 MCP composition smoke，不是新的付费 A02，也不是产品验收。测试入口为 `tests/test_dell_research_mcp_real_data.py`；已保存的单项结果为 `1 passed in 2.25s`。

- Local Knowledge 已由 `StructuredLocalKnowledgeReader` 读取 `dell_rag_full_stack_preview_attempt_20260902_03/retrieval_nodes.jsonl`（1,025 nodes，SHA-256=`f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817`），通过真实 FastMCP client/server tool call 执行 metadata-prefilter BM25；新 vertical 不再消费 `FrozenLegacyLocalKnowledgeReader`。legacy reader 只保留历史兼容和 regression，不得再写成当前 Dell vertical 的数据路径。
- L10 的 bounded request 返回正确 cash-flow table `BLOCK::C46E0FD5E2F8AA3DCA4B20F5` 为 top1；L11 返回 anchor `CHUNK::C555524A6CE91A096CFFF279` 并通过相邻上下文交付 `CHUNK::2FEB7579E112C8CF854CA682`。后者证明 neighbor delivery 可用，但不把第二 anchor 的低直接排名改写成 direct retrieval 成功。
- 同一 MCP smoke 中，S2 `revenue` 与 `gross_profit` 都按显式 `selection_mode=exact_period_end` 解析；response digest、query/scope、ticker、metric、period、granularity、unit 与 as-of 均由 consumer 重新绑定，不只依赖 transport success。
- fresh S2 successor 位于 `Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\s2\s2_exact_period_contract_successor_20260902_r1`。`company_financial_fact_mart_result.json` 文件 SHA-256=`dd2c92400de777867545de2c41b975d1f07ca6060f4ed431075b7081ab16ed82`，SQLite SHA-256=`363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4`，claimed/recomputed `result_digest` 均为 `f5a3ef877214766409a981d02349a2fd7ea010ed4a2548314531b7554a899ea6`。
- 旧 current-bound S2 v1.1 必须继续 fail closed：其 claimed digest 为 `0c25c917...95a1`，canonical recompute 为 `e3f955dccbd7cd823a1d0fe248d255449d31269fc74c098def23a58770a705fd`，二者不相等。fresh successor 证明 producer 和 exact-period consumer 语义可工作，但不自动修复旧 v1.1、不自动迁移 R39/current authority，也不授权 Evidence、报告或正式发布。

因此最诚实的当前运行资格是：`REAL_LOCAL_MCP_COMPOSITION_SMOKE_PASS / STRUCTURED_CANDIDATE_AND_EXACT_PERIOD_S2_CONTRACT_PROVED / CURRENT_BOUND_V1_1_REJECTED / PAID_A02_AND_FORMAL_PRODUCT_RUN_HOLD`。

## 13. 九分支 deterministic composition 已迁到 successor 数据地基

旧的 `test_dell_reference_vertical_real_composition.py` 仍把 `FrozenLegacyLocalKnowledgeReader` 和旧 current-bound S2 mart 接在九分支图上。Planner 开始发送 issuer/source-role metadata scope 后，legacy reader 按退役合同返回 `legacy_local_scope_prefilter_unsupported`，使图在 synthesis 前进入 `fatal_tool_failure_before_synthesis`。这不是 structured reader 的检索失败，也不得通过重新开放 legacy scope 来修。

测试接线现已改为：

- `StructuredLocalKnowledgeReader` 读取 attempt03 的 1,025 个 nodes，SHA-256=`f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817`；
- S2 读取 `s2_exact_period_contract_successor_20260902_r1`，SQLite SHA-256=`363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4`；
- deterministic DeepSeek fake 接受 provider JSON function schema 后，仍由 host Pydantic 合同验证返回 payload；
- local request 使用与正式合同相同的 issuer/source-role scope，fact request 显式携带 `selection_mode`；
- 断言证明返回的是 `structured_document_tree=true / legacy_read_only_bridge=false` 的 candidate，而不是旧 flat bridge。

迁移后核心九分支 composition 测试 `1 passed`；structured reader／真实 MCP／DeepSeek adapter／graph 相邻组 `32 passed`；包含 structured corpus、RAG qualification、external exact URL、S1/S2 MCP、candidate judge、graph/CLI 和九分支 resume 的本轮组合回归为 `207 passed in 82.85s`。这些是 zero-paid deterministic/本地集成验证；不把失败的 candidate judge 变成 PASS，也不授权新的付费 A02、Evidence admission、报告、formal 或产品发布。

## 14. 2026-09-02 structured A02 启动前 Runtime 收口

本节只记录启动前已经进入 working-tree successor、且可由测试复算的事实。A02 尚未执行，不能把“具备运行资格”写成“纵切已经跑通”。

- foundation 的 `maximum_specialist_model_rounds=2` 已投影到 `AgentRuntimeScopeCeiling`、MCP composition 和 attempt composition manifest，不再是死字段。合同要求 `maximum_specialist_model_rounds == 1 + maximum_targeted_counter_reroutes`；当前值为首轮 1 次、最多一条 Counter 定向回派、单分支总计最多 2 次 Specialist 模型调用。
- 图在首轮 dispatch、Counter 回派、rework 模型调用前和最终 verification 都消费该 authority。第三轮明确以 `specialist_round_limit_exceeded` fail closed；HITL resume 回归确认不会重跑初始工具、回派工具或 Specialist。
- 外源没有新建 MCP 工具或协议；runner 只增加成对的 frozen-pack path/SHA 参数，并把通过完整性校验的 r12 作为现有 discovery/capture lane 的第一候选来源。candidate 未填满时仍调用实时 primary 补充，不把冻结包误当成完整互联网。
- successor DeepSeek config 只更新 Planner 的 comparable-run evidence：A01 实际 HTTP 200、input `21,465`、output `2,076`、total `23,541`，失败在本地 parser，不是 token ceiling。Planner/Specialist/Counter/Lead 原 task-specific 输入、输出、schema、质量风险、stop/truncation 和 0 retry 合同均未削弱。
- A02 唯一身份预定为 attempt=`20260902-dell-reference-vertical-structured-a02`、run=`dell-reference-vertical-structured-run-a02`、snapshot=`20260902-dell-structured-s1-s2-external-a02`。启动权限只到 HITL：不自动 approve/reject resume、render、publication、formal qualification、product acceptance 或 release。
- A02 的 Project OS gate 曾一度把本地 RAG/S2/pack 校验再实现一遍，独立审查确认这是重复治理后已从约 327 行收薄到 120 个物理行：现在只绑定本次 identity、一次 `start → HITL` authority、launcher SHA 和 known boundary；真实数据、config、pack、MCP、graph、checkpoint 与 Git implementation binding 仍由既有 runner 校验。该 one-off shim 只服务 A02，A03／下一案例不得复制新 schema，应改成数据化的通用 bounded paid-start decision 或直接复用既有合同。
- 启动前 root 已独立复跑 Runtime graph/MCP `44 passed`、frozen pack/external/CLI/real-composition `45 passed`，以及包含上述各面和 A02 gate 的稳定合并回归 `115 passed in 72.10s`。A02 专用 gate `5 passed`，独立 reviewer 的 P0/P1=`0/0`；`git diff --check` 已通过。一次 dirty-tree launcher `-PreflightOnly` 也按设计在 Project OS 的 `project_os_repository_not_synced` fail closed，模型／网络／provider calls 均为 0。
- 更大的历史 `test_project_os_preflight.py` 回归曾得到 `33 failed / 164 passed`：其中一个新旧 projection 的 `evidence_mode` 兼容错误已在同一层修复并由 A02 与一个旧 fixed-pack 聚焦回归验证；其余失败主体是历史 live-authority JSON 固定绑定 `project_os_preflight.py` 的旧 HEAD SHA，任何合法修改都会触发预期 drift。没有改写几十份历史不可变 decision，也没有削弱 SHA validator；这属于既有 live-authority fixture 的可维护性设计债，不是把 A02 验证伪装为全仓绿色。
- 首个 clean pushed `d99ded971f7cbe7e4a0f78d44d4a4b3f8f80cceb` 上，Project OS zero-call preflight 已明确 PASS（model/network/provider calls 全为 0）；随后 Windows PowerShell 5.1 在执行 launcher 前即把无 BOM UTF-8 中文 research-question literal 按本地 ANSI 误解码并产生 parser error。没有进入 runner、没有创建 attempt/checkpoint、没有模型或网络调用。最早责任层是 launcher source encoding，不是数据、Agent 或 provider。修正只把同一问题改成语义等价的纯 ASCII 英文并按仓库 `.gitattributes` 固定 CRLF，launcher SHA 重新绑定为 `72637741...e59f8`；dirty-tree 复核已能正常解析并按设计停在 Project OS not-synced，A02 gate＋CLI=`31 passed`。该预检失败不是 A02 paid attempt，仍需新 clean commit/push 后从两道 zero-call gate 重跑。
- clean commit/push 和 clean 状态下的 Project OS、launcher 两次 zero-call preflight 仍是下一门；截至本节 A02 仍未启动。

这次对 paid start 使用严格门是因为它会产生真实费用、不可变 attempt 和多节点外部调用；同等门不得外推到普通文件读取、局部测试或只读审计。若专用 gate 与 runner 已有 SHA/composition 绑定重复，收口时应删除重复层而不是继续扩写。
