# 014 R58 DB / RAG / Retrieval / Data Pipeline Control Plane

日期：2026-06-28

## Problem

用户要求先把 R58 草稿落下来。前一轮讨论已经确认 R58 主要承接检索召回策略；本轮进一步补充，R58 不能只谈 retrieval，还要纳入：

- 数据工程；
- 数据管线；
- 数据治理；
- 数据库架构效率调优；
- 时间 / 空间复杂度；
- data ingestion 存储规范；
- 节点间数据传递合同；
- crawler / fetcher / parser / verifier / authority mapper 工具层。

## Decision

新增 R58 技术草案，把它定位为 `DB / RAG / Retrieval / Data Pipeline Control Plane`，而不是单一 RAG 文档。

核心判断：

- 当前系统已经有 RD0-RD7、Retrieval Index Registry、Milvus、Gold Mart、Graph Store、AgentDataBrief 和 RoleEvidencePack。
- R58 不应再建新索引，而应定义 Research Lead 如何有策略地使用现有 DB / graph / RAG / Milvus / web repair / ContextEngine。
- 检索命中不是事实，必须回连 raw source、parser run、authority row、graph support 和 compression artifact。
- 数据 ingestion 必须从一开始就有 source snapshot、parser run、runtime row lineage 和 storage convention，不能继续靠散装 JSONL 和聊天记忆解释数据。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/33_r58_db_rag_retrieval_data_pipeline_control_plane.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，把 R58 加入索引和总原则。
- 更新 `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`，把 R58 epic 边界扩展为 retrieval + data pipeline + database performance。
- 更新 `docs/worklog/00_internal_master_checklist.md` 和 `docs/worklog/README.md`。

## R58 Draft Scope

R58 草稿包含：

- `RetrievalIntent` taxonomy；
- `RoutePolicyMatrix`；
- `QueryRewriteAndFacetPlan`；
- `HybridRecallPlan`；
- route-scoped rerank / fusion / quota；
- `RetrievalExecutionLedger`；
- Bronze / Silver / Gold / Graph / Index / Runtime 分层数据管线；
- `DataIngestionContract`；
- ingestion storage convention；
- agent node data contract；
- database / object store / Milvus / Redis/MQ 分工；
- `DatabasePerformanceProfile`；
- crawler / fetcher / parser tooling surface；
- R58 与 R57 ContextEngine、R60 eval 的衔接。

## Follow-Up

下一轮应继续讨论：

1. 哪些数据进 Postgres/MySQL，哪些继续 SQLite/DuckDB，哪些只进 ObjectStore。
2. 增量刷新、全量重建、snapshot、staleness、supersession。
3. source license、tenant permission、robots、数据保留策略。
4. 600+ 公司、千万级 record、百万级 fact/向量下的复杂度和资源策略。
5. crawler/fetcher/parser 工具选型与统一输出合同。
6. retrieval qrels / data pipeline qrels 如何设计，避免只用最终 memo 评测。

## 2026-06-28 Reference Absorption Update

用户要求把本轮外部成熟 agent / RAG / enterprise AI 平台调研吸收进 R58，并明确参考来源、后续新增/删除参考信息源的留痕办法，以及进入 FIN 项目后的表现评估。

本轮更新：

- 在 R58 主文档新增 `外部参考台账与六个吸收设计`。
- 定义 `ReferenceSourceLedger`，记录参考平台、URL、source type、吸收范围、吸收到哪个 R58 对象、为什么吸收、为什么不全量套用、状态、复核时间、删除/降级条件和项目内表现记录。
- 定义 `ReferenceChangeLedger`，记录新增、更新、降级、删除、替代的原因、影响对象、预期影响、前后指标和决策证据。
- 把六个设计吸收进 R58：
  - `R58-REF-01-knowledge-pipeline`
  - `R58-REF-02-permission-aware-system-of-context`
  - `R58-REF-03-hybrid-route-control`
  - `R58-REF-04-document-intelligence`
  - `R58-REF-05-retrieval-observability`
  - `R58-REF-06-workpaper-matrix`
- 新增初始参考源清单：RAGFlow、Dify、LangGraph、LangSmith、Haystack、LlamaParse、Microsoft Copilot Studio、Google Agent Platform / ADK、Snowflake Cortex Agents、Databricks Agent Framework、Glean、Onyx、Palantir AIP、Hebbia Matrix。
- 新增 R58-D13 / R58-D14 demand：参考源台账和参考设计表现门控。

核心判断：

- 这些平台不是要被 FIN 直接照搬，而是作为设计来源进入可维护台账。
- R58 仍坚持 `DB exact first + graph-guided retrieval + typed hybrid recall + authority-aware rerank + context compression bridge + data lineage audit + qrels/eval feedback`。
- 参考平台进入项目后的价值必须被指标验证，例如 lineage completeness、permission leakage、target-in-candidates、parser accuracy、retrieval latency、Workpaper trace parity 等。

## Verification

本轮为 docs-only framework draft。未运行 runtime / unit tests / data rebuild。

待收尾前运行：

- `git diff --check`
- 文档 secret scan
