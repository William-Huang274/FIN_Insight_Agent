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

## 总原则

1. SEC / global filing 是 anchor；产品事实必须经过 parser / authority gate；公开源默认只做 context / resolver / lead。
2. Reflection 不是自由发挥的模型复盘，而是 gap diagnosis -> repair plan -> hard gate -> targeted executor -> delta audit。
3. 联网搜索不能直接进 claim card；必须先成为 source candidate，再 fetch snapshot、classify、parse、gate。
4. Research Lead 不学习所有行业细节，只学习 meta-planning，并依赖 inventory brief + playbook registry 分配任务。
5. Specialist 并行消费 frozen evidence bundle，输出 claim cards；memo writer 只消费 verified judgment / claim cards。
6. Milvus 是 typed semantic recall supplement，不替代 BM25/ObjectBM25/exact ledger，也不成为 exact-value authority。
