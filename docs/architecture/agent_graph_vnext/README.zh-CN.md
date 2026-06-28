# Agent Graph vNext 文档索引

本目录记录下一阶段 Agent Graph 升级的框架合同和分功能执行文档。它吸收 2026-06-12 讨论结论：公开数据扩容后，Agent Graph 必须围绕 evidence authority、reflection-driven targeted repair、受控联网检索、行业 playbook、role-specific skill、共享上下文和异步/同步协作重构。

当前文档只定义下一阶段工程框架，不声明这些能力已经进入默认 runtime。

## 文档结构

- [00 总体框架](00_agent_graph_vnext_framework.zh-CN.md)：目标图、现有模式差距、authority-aware graph 原则。
- [01 反思机制与 Second Pass](01_reflection_second_pass_design.zh-CN.md)：反思插入点、repair loop、硬门控和 delta audit。
- [02 联网证据机制](02_live_web_evidence_policy.zh-CN.md)：联网工具归属、行业/domain allowlist、source class 和 claim scope。
- [03 行业 Playbook 与 Agent Skill](03_playbook_and_skill_contracts.zh-CN.md)：Research Lead meta-planning、playbook schema、专家 skill 写法。
- [04 共享上下文与协作](04_shared_context_and_collaboration.zh-CN.md)：Global / Role / Private context、各 agent 输入边界、并行与同步屏障。
- [05 Milvus 与检索 Runtime](05_milvus_retrieval_runtime_plan.zh-CN.md)：云端 Milvus 现状、本地/云端双模式、typed vector route 边界。
- [06 分功能执行顺序与通过条件](06_implementation_sequence_and_acceptance_gates.zh-CN.md)：按功能拆分的实施步骤、验收标准和禁止降级项。
- [07 投研工作流知识图谱升级框架](07_investment_research_workflow_knowledge_graph_framework.zh-CN.md)：按投研问题驱动图谱重整业务经营图谱、资本/持仓/融资图谱、source hierarchy、产品规格/公开采购视角、次级 agent 和 K1-K8 落地顺序。
- [08 旧规划文档吸收与数据治理执行计划](08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md)：对 G1-G10 前的三份规划文档做覆盖/缺口映射，并固化 D1-D11 evidence-governed runtime 数据治理序列。
- [09 Research Lead 常驻监督闭环框架](09_lead_supervised_closed_loop_research_framework.zh-CN.md)：记录 2026-06-14 新讨论，将 Research Lead 升级为 supervising analyst，加入 ResearchObjectiveContract、LeadReviewCheckpoint、TargetedRepairPlan、MemoLogicPlan、role-specific selector、BGE 资源队列和 ModelRouter / AgentCoalescer。
- [10 后端 / 前端 Runtime 升级框架](10_backend_frontend_runtime_framework.zh-CN.md)：吸收两份后端规划文档，把 FinSight 从本地 agent / Workbench eval 推进到 API、Redis queue、worker pool、SSE、DB persistence、Docker Compose、前端 trace/report viewer 和 Java/Spring Boot 可选外壳。
- [11 Agent Eval Runtime 闭环框架](11_agent_eval_runtime_framework.zh-CN.md)：审计现有 docs/eval、scripts/eval、fixtures、run_audit_store、LangGraph checkpoint、LLM token/latency 和 model run ledger，设计统一 Eval Registry、Dataset Lifecycle、Node/Chain Evaluators、Failure/Gold 状态机、后端 SQL eval store 和前端 eval dashboard。
- [12 09-11 闭环后一体化执行计划](12_integrated_execution_plan.zh-CN.md)：不按 09/10/11 分别排期，而是按 P0-P10 功能切片把 Python agent、后端/前端、Eval Runtime、同步/异步协作、Java shell 可选路线和通过门控编排成下一阶段执行顺序。
- [13 09-11 剩余工作全量拆分与完成合同](13_09_11_remaining_full_completion_plan.zh-CN.md)：把 09/10/11 尚未完全落地的 L/B/F/EV/P 项合并成 R0-R12 可执行步骤，明确 SQL/Redis/ObjectStore、Eval Runtime、Milvus/Data Gates、ContextEngine、Lead supervised loop、specialist packs、Memo/Verifier、后端/前端和 full-chain release gate 的通过条件、云端依赖和禁止降级规则。
- [14 vNext 50-Case Eval Catalog](14_vnext_50_case_eval_catalog.zh-CN.md)：把 R12 后续评测从临时挑 case 升级为 50-case catalog，覆盖 focused、standard memo、deep research、gap boundary、non-US supply chain 和 backend/runtime stress，并定义 12-case successor、20-case broader gate 与 load-mix subset。
- [15 源层能力审计与 Analyst-First 输出优化小阶段](15_source_layer_capability_and_analyst_first_optimization.zh-CN.md)：针对 R12 输出浅、caveat 过多和 L2/L3/L4 公开源使用不足的问题，新增 SL0-SL5 小阶段；先做 source-layer capability audit，再推进 evidence graph 进入策略、Research Lead targeted repair、role-specific selector 和 memo-quality gate。
- [16 L4 弱信号架构与 L1-L3 纵向细分执行框架](16_l4_weak_signal_and_vertical_source_lane_framework.zh-CN.md)：把 L4 定义为 discovery / exclusion / repair trigger 层，并将 600+ 公司 source-layer 扩容从全局补源改为按 vertical source lane 推进；每个 lane 必须有行业 playbook、产品 taxonomy、L1 财务/披露重点、L2/L3 source routes、L4 discovery 边界和完成门控。
- [17 09-15 Completion Gap Register](17_09_15_completion_gap_register.zh-CN.md)：在 16 Step 0-2 落地后回扫 09-15，把仍未实现、未验收、只做了 runtime 骨架但未证明产品级闭环的事项收敛为 completion-gap register 和下一轮执行顺序。
- [18 Exact-Slot Data Layer Completion Plan](18_exact_slot_data_layer_completion_plan.zh-CN.md)：把 source-layer closeout 从“bounded context 可用”修正为 “exact-slot 数据层完成”，定义 L1/L2/L3 各 source role 的 exact slot 字段、禁止提权边界、R1-R5 修复顺序和 runtime 接入前置 gate。
- [19 Source-Role / Product-KPI Exact-Slot Deep Repair](19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md)：把 source-role 与 Product-KPI exact slot 的长尾缺口拆成可修、可重路由、不可提权和公开源边界，防止把 URL、产品页、新闻、招聘、订单 proxy 等弱信息误写成公司强事实。
- [20 R15 Public Source Gap Exhaustion Execution Plan](20_r15_public_source_gap_exhaustion_execution_plan.zh-CN.md)：把剩余 CompanyGapDocket 行推进到 `runtime_ready` / `final_public_boundary` / `not_applicable` / `rerouted` 终态；`attempted_not_exhausted` 不算完成，R15-1/R15-2 必须逐阶段验收后才能进入 runtime 回灌。
- [21 R16 Product-KPI 与 Source Adapter 深修执行记录](21_r16_product_kpi_and_source_adapter_deep_repair.zh-CN.md)：在 R15 之后继续深修 column-group / sentence / period-version / non-US / PatentsView buckets，把可验证的产品/品类/产品线披露提权为 exact rows，把业务段和经营义务重路由，把 credential/parser/public-boundary 写成 attempt-backed closeout。
- [22 Source Route Attempt Ledger 与产品族证据硬化计划](22_source_route_attempt_ledger_and_product_family_evidence_hardening.zh-CN.md)：把“公开源没进 runtime”拆成 source discovery / fetch / parser / verifier / closeout 可审计状态；新增 R17 SourceRouteAttemptLedger、known-public canary，并已落地首批 ProductSpec / ProductGeneration / Benchmark / deployment proxy / ecosystem context / industry operating metric runtime rows，使 DECK/NVDA/MSFT/ASML/TEL/Hon Hai canary 均进入 `canary_covered`，防止 parser/source-route 漏吃被误判为公开源边界。
- [23 非财务信号提权与多维研报判断基座](23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md)：把 source authority 从“能否当财务 exact fact”扩展为 `ExactFactAuthority` + `NonFinancialSignalAuthority` + `ThesisDriverAuthority`，并把投研/行研数据源收敛为事实锚点、公司经营、leading signal、行业/宏观、垂直行业、技术/IP、资本/融资/持仓/市场流动性和商业 tracker gap 8 层；同时吸收公开成熟机构报告中的 debate-first、theme-to-expression、capex/funding bridge、scenario/risk-reward、primary-research proxy 形态，新增 `TopOfMindQuestionSet`、`ThemeToExpressionGraph`、`BeneficiaryAndEnablerMap`、`ExposureConfidence`、`CapexFundingBridge`、`CustomerSpendingCapacityGraph` 等下一阶段对象。23 也定义了 source adapter/parser/readiness 准入矩阵、R18 Data Source Admission Ledger 和 AI/Semis first-tranche source-route gate，要求 accepted row 必须可反查 locator/fetcher/parser/verifier/authority mapper；URL、snippet、seed、attempt-only、blocked page 不得进入 evidence bundle。产品规格、客户部署、供应链、行业经营、监管、宏观、市场预期和资本市场信号可支撑 bounded thesis driver，但不能冒充收入、销量、ASP、份额、sell-through、backlog、订单金额或实时资金流。
- [24 原始披露到 RAG / 数据库全链路复盘与数据底座规划](24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md)：从 raw SEC / 非美披露、CompanyFacts/FSD、IR/local exchange、chunk/table/metric/parser、BM25/ObjectBM25/SQLite FTS/Milvus、run audit、D-series governance DB、ObjectStore、ProductRelationshipGraph 和 source authority mart 出发，复盘当前数据底座的真实状态；明确 RAG 索引不是事实库，Milvus 只能做 semantic recall supplement；提出 RD0-RD7 后续执行顺序，把 raw source provenance、parser ledger、Gold Fact / Signal Mart、Graph Store、RAG Index Registry、Research Lead consumption contract 和 data-quality release eval gate 串成长期主账本。
- [25 Agent Runtime 参考架构草案](25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md)：已归档参考。记录 2026-06-27 至 2026-06-28 关于 agent graph、harness / runtime facade、Hermes-style ContextEngine、MCP/A2A、durable execution、observability/eval、Java 后端、Public Evidence 和二级市场 / 资本反馈的讨论草案；相关 active source of truth 已迁入 26、R51 PRD、10/11/12/13 和后续 R54，本文只保留外部参考和历史讨论出处。
- [26 B 端协作型 Agent Graph 与企业工作流嵌入技术方案](26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md)：承接 R51 B 端 PRD，把 fixed fanout / second pass 流水线升级为 Research Lead 常驻监督、Shared Workpaper Event Ledger、specialist workstreams、cross-specialist structured communication、event-driven rework、human review / approval、Deliverable Composer、Java workflow backend 和 Python research runtime 分层协作方案；明确内部协作不用 A2A、用结构化 artifact/event 而不是自由 agent chat。
- [27 R53-R60 工程化执行总控计划](27_r53_r60_engineering_execution_program.zh-CN.md)：把 R53 Research-to-Quant、R54 二级市场/资本反馈、R55 Deliverable Studio/Dashboard、R56 runtime stack、R57 memory/context、R58 DB/RAG、R59 backend/frontend 和 R60 eval/observability 统一成 program-level 执行计划；明确 PRD -> 技术方案 -> 需求单 -> 测试/eval -> 联调 -> 发布/反馈的标准、依赖图、需求单模板、P0-P5 排期和 Git/artifact 管理要求。

## 总原则

1. SEC / global filing 是 anchor；产品事实必须经过 parser / authority gate；公开源默认只做 context / resolver / lead。
2. Reflection 不是自由发挥的模型复盘，而是 gap diagnosis -> repair plan -> hard gate -> targeted executor -> delta audit。
3. 联网搜索不能直接进 claim card；必须先成为 source candidate，再 fetch snapshot、classify、parse、gate。
4. Research Lead 不学习所有行业细节，只学习 meta-planning，并依赖 inventory brief + playbook registry 分配任务。
5. Specialist 并行消费 frozen evidence bundle，输出 claim cards；memo writer 只消费 verified judgment / claim cards。
6. Milvus 是 typed semantic recall supplement，不替代 BM25/ObjectBM25/exact ledger，也不成为 exact-value authority。
7. Eval 是 runtime 的一部分；每次 run 都必须可追溯到 case / dataset / node metrics / context / evidence / claim / gate / failure taxonomy。
8. 09-11 的完成口径以 13 文档的 R0-R12 gate 为准；后续新增问题必须归入某个 gate 的失败/补项，不能成为未记录的隐性 backlog。
9. 正常可信源可以进入 evidence graph，但不能绕过 parser / authority gate；L2/L3 证据应作为 context / proxy / lead 被使用，不能被直接提升为公司强事实。
10. 后续 L1-L3 扩容必须按行业/公司类别/产品线 lane 闭环推进；L4 只能生成 discovery lead / exclusion note / repair attempt，不能直接生成 ClaimCard 或核心 thesis。
11. 09-15 的剩余工作以后以 17 文档的 completion-gap register 追踪；任何“已接骨架但未产品化”的能力都必须有 runtime gate 或 eval gate，不再口头视为完成。
12. 数据层完成以后以 18 文档的 exact-slot gate 为准；`context_only` row 不能替代 exact slot，L2/L3 proxy 只能提权为 proxy exact，不能被写成产品销量、份额、ASP、库存、sell-through 或公司财务事实。
13. R17 以后任何 gap closeout 必须有 SourceRouteAttemptLedger 支撑；known-public canary 失败只能进入 parser/source-route debt，不能被写成公开源确实没有。产品规格、代际提升、客户部署、benchmark、生态 proxy 是独立产品族证据角色，不得混同为 Product-KPI exact。
14. R18/23 以后非财务强信号可被提权为 bounded thesis driver；财务 exact gate 不降级，但 Product/Technology、Industry/Supply Chain、Macro、Market Expectation、Capital/Funding/Ownership、Market Liquidity 等维度不能因缺少 exact financial fact 而自动降成 generic gap。
15. 下一阶段数据源扩展必须走 SourceRouteRegistry v2：每个 source role 都要有 locator / fetcher / parser / verifier / authority mapper / runtime row 合同，并把 gap 明确分成 route_or_parser_debt、signal_gap、signal_boundary、commercial_tracker_gap 或 not_applicable。
16. Research Lead / LeadReviewCheckpoint 必须消费 SourceAuthorityCoverage，而不是只看 ClaimCard；如果 R18 matrix 显示某维度有可修公开源，则必须进入 targeted repair。AI/Semis first-tranche source-route gate 未全绿时，不得把该 lane 视为 full-chain release-ready。
17. 原始披露、RAG 索引、结构化事实、图谱和 runtime/eval 数据库必须共享可追溯主键与血缘；任意 evidence row / retrieval hit / graph edge 都应能追到 raw source、parser run、authority row 和 forbidden-claim boundary。新增数据不得长期只落零散 JSONL 而没有 inventory、lineage、database mirror 或明确的 diagnostic-only 标记。
18. Harness、ContextEngine、MCP/A2A、Java backend 和 observability/eval 的活跃实现锚点已从 25 迁到 26 / 10 / 11 / 12 / 13；Python/LangGraph research runtime 不被 Java 或通用 agent framework 重写，Java 负责产品化 frontdoor / queue / trace / eval / frontend，MCP 负责工具标准化，A2A 只作为未来外部 agent interop。
