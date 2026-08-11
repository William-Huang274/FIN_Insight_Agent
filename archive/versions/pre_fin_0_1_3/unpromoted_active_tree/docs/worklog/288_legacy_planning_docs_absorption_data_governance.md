# 2026-06-12 Legacy Planning Docs Absorption And Data Governance Plan

## Prompt

用户提供了三份在 G1-G10 落地前形成的规划文档：`agent_graph和skill.docx`、`数据治理结构20260612.docx`、`投研工作流升级文档.docx`，要求判断是否需要参考并吸收，必要时更新现有文档或单独落文档。

## Decision

三份文档不能原样合并。`agent_graph和skill.docx` 中大部分 graph 机制已经被 G1-G10 覆盖；`投研工作流升级文档.docx` 的五层图谱、行业/主营模式/公司规模微调应补入 07；`数据治理结构20260612.docx` 指出的 Claim Evidence Ledger、typed Gap Ledger、Entity Master、Provenance、Vintage、Reconciliation 等数据治理层仍未充分落地，应单独形成 D1-D11 下一阶段执行计划。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/07_investment_research_workflow_knowledge_graph_framework.zh-CN.md`：
  - 顶层改为 `Layer 0` 到 `Layer 5` 的五层图谱 + workflow runtime layer。
  - 新增 Entity / Identifier Master。
  - 新增 Evidence / Claim / Gap Layer、SourceArtifact、AtomicFact、ClaimEvidenceLedger、typed GapLedger。
  - 新增 As-of/Vintage、Reconciliation、Metric/Product Ontology、Source Capability Router、Gate Registry、Derived Metric、Analyst View 等数据治理辅助层。
  - 新增 P-1 entity/source governance 前置阶段。
  - 新增行业、主营模式、公司规模微调。
  - 新增 D1-D11 Data Governance Runtime 工程拆分。
- 新增 `docs/architecture/agent_graph_vnext/08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md`，记录三份旧规划文档的已覆盖内容、待吸收内容和 D1-D11 执行顺序。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md` 索引。

## Result And Evidence

- 本轮是架构文档更新，没有改 runtime 代码。
- 未运行测试或实验；后续实现 D1-D11/K1-K8 时再按对应 gate 跑测试。

## Follow-up

- 优先 D1+D2：durable Claim Evidence Ledger 和 Typed Gap Ledger。
- 然后 D3+D8：Entity / Security Master 和 Source Capability Router。
- 再推进 D4-D9，最后接 K2-K8 的产品规格、sub-agent 和 KG runtime。
