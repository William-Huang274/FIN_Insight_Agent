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

## 总原则

1. SEC / global filing 是 anchor；产品事实必须经过 parser / authority gate；公开源默认只做 context / resolver / lead。
2. Reflection 不是自由发挥的模型复盘，而是 gap diagnosis -> repair plan -> hard gate -> targeted executor -> delta audit。
3. 联网搜索不能直接进 claim card；必须先成为 source candidate，再 fetch snapshot、classify、parse、gate。
4. Research Lead 不学习所有行业细节，只学习 meta-planning，并依赖 inventory brief + playbook registry 分配任务。
5. Specialist 并行消费 frozen evidence bundle，输出 claim cards；memo writer 只消费 verified judgment / claim cards。
6. Milvus 是 typed semantic recall supplement，不替代 BM25/ObjectBM25/exact ledger，也不成为 exact-value authority。
7. Eval 是 runtime 的一部分；每次 run 都必须可追溯到 case / dataset / node metrics / context / evidence / claim / gate / failure taxonomy。
