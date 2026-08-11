# 275 Agent Graph vNext 框架规划

## Prompt

用户要求在读取本 session 关于 Agent Graph 新模式、反思机制、second pass、联网检索、行业 playbook、各 agent skill、共享上下文和异步/同步协作的讨论后，落成下一阶段框架文档和分功能执行文档；同时把上一轮数据源扩容已通过的脚本提交，保持下一轮工作树干净。用户特别提醒：Milvus 当前还在云端，后续要把云端/本地 Milvus 决策纳入设计。

## Decision

本轮只冻结下一阶段设计合同，不改 runtime 默认行为。核心判断：

- Agent Graph 不推倒重写，基于现有 multi-agent graph 增加 explicit source-authority contracts。
- Reflection 放在 plan、coverage/gap、claim/thesis、verifier 四个 checkpoint。
- Second pass 升级为 reflection-driven targeted repair loop，而不是普通二次模型/工具调用。
- 联网检索只给 `web_evidence_operator`，由 reflection repair request 触发；search snippet 不能直接进 claim card。
- Research Lead 学 meta-planning，不学习所有行业专家知识；行业细节通过 machine-readable playbook registry 进入规划。
- Specialist skill 写 role method / source boundary / claim card schema，不写百科。
- 共享上下文分为 Global / Role / Private 三层；Specialist 并行产 claim cards，Claim Store / Adjudicator / Memo / Verifier 为同步屏障。
- Milvus 作为 typed semantic recall supplement，runtime capability 由 inventory 显示 cloud/local/unavailable，不替代 exact ledger。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/` 文档集：
  - `README.zh-CN.md`
  - `00_agent_graph_vnext_framework.zh-CN.md`
  - `01_reflection_second_pass_design.zh-CN.md`
  - `02_live_web_evidence_policy.zh-CN.md`
  - `03_playbook_and_skill_contracts.zh-CN.md`
  - `04_shared_context_and_collaboration.zh-CN.md`
  - `05_milvus_retrieval_runtime_plan.zh-CN.md`
  - `06_implementation_sequence_and_acceptance_gates.zh-CN.md`
- 更新架构入口和 checklist，后续实现可按 G1-G11 分功能推进。

## Result And Evidence

文档明确把 product/public evidence 扩容后的 authority 边界写入 graph vNext：

- `company_product_evidence_graph` 仅 `runtime_fact_allowed` / exact-authority rows 能支持 product KPI facts。
- `public_source_context` 是 context/resolver/lead，不证明公司产品销售、市场份额、渠道库存或盈利。
- `live_public_web_context` 默认 context-only，只有 official/regulatory/company-authored snapshot 经过 parser/authority gate 后才可提权。
- Milvus rows 为 semantic recall supplement，`exact_value_authority=false`。

## Follow-up

- 下一轮先做 G1/G2/G3：source family / inventory contract、Plan Reflection Gate、Evidence Fusion Selector vNext。
- 再做 G4/G5：reflection-driven second pass 和 web evidence operator。
- Milvus 需要在实现前决定：继续云端为主，还是补本地 Milvus Lite smoke；无论哪种都必须通过 inventory capability 注入。

## Safety Notes

- 本轮不写入任何 API key、endpoint secret 或 private data path。
- 不改变默认 runtime route。
