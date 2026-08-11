# 017 R60 Eval / Observability / Quality Engineering

日期：2026-06-29

阶段：R53-R60 product strategy / engineering framework

状态：docs-only framework draft

## Prompt

用户要求开始落 R60 文档，并参考企业级、最新、成熟的 agent 应用平台在 eval、observability、incident、fallback，尤其 token 与效率 / 质量 trade-off 上的做法，形成判断。

## Reasoning

R60 不应该只延续旧的“最终答案评分”视角。当前项目已经进入 B 端金融研究工作台形态，质量体系需要覆盖两条线：

1. Agent / data / full-chain eval：parser、chunk/table、retrieval、rerank、context injection、tool permission、LeadReview、specialist、Workpaper、Deliverable、Dashboard projection。
2. 需求 / 研发 / 测开验收：每个需求单、PR、release slice 的产品验收、工程验收、测开计划、缺陷生命周期、release readiness。

外部平台可吸收 trace、usage、cost、online eval、CI gate、incident dashboard 的设计，但不能替代本地 SQL/ObjectStore/WorkpaperEvent 审计主账本。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md`。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`，加入 R60 文档索引和总原则。
- 更新 `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`，记录 R60 当前状态和后续 implementation slice 边界。
- 更新 `docs/worklog/00_internal_master_checklist.md`，新增 R60 framework draft 记录和 R60-D01-D16 待实现项。
- 根据用户补充要求，将 R60 外部参考源升级为 `ReferenceSourceLedger`、`ReferenceChangeLedger`、`ReferenceAdoptionPerformanceProfile` 三类长期维护对象，并把 demand list 扩为 R60-D01-D18。
- 本日志记录外部参考吸收、质量工程定位和剩余工作。

## External References Absorbed

- LangSmith：token / cost 按 trace、project、dashboard 统计，区分 input、output、cache、reasoning、tool/retrieval/custom cost。
- Langfuse：generation / embedding usage 和 cost tracking，支持 custom models 和 metrics API。
- Phoenix：LLM traces 暴露 latency、token、runtime exception、retrieved docs、embeddings、prompt template、tool call。
- Braintrust：offline eval、immutable experiments、CI/CD、online scoring、production trace 回流 dataset。
- OpenAI prompt caching：稳定 prefix、变量后置，用缓存降低延迟和输入成本。
- OpenAI Agents SDK usage：per-run / per-request usage，记录 cached tokens 和 reasoning tokens。
- Datadog LLM observability：生产流量 span、error、token、latency 监控。

## Result

R60 已被定义为质量工程层：

- 对 agent 链路和数据链路，定义 E0-E12 eval 矩阵。
- 对产品/研发/测开，定义需求验收矩阵。
- 对 token/cost/latency/quality，定义统一治理，不把 token 最小化作为独立目标。
- 对 fallback/incident，定义 fail-closed、typed gap、failure queue 和 release gate。
- 对后续实现，拆出 R60-D01-D18，其中 D17-D18 专门负责外部参考源治理和采用后表现评估。

## Verification

本次为文档和 checklist 更新，未运行 runtime、agent full-chain、后端、前端或 eval case。

待本轮文件更新完成后需要运行：

- `git diff --check`
- 候选文档 secret scan
- 候选文档 conflict marker / trailing whitespace audit

## Follow-up

- R60-D01-D03：优先落 Eval registry、TraceSpan、UsageMetric / TokenCostLedger schema。
- R60-D04-D06：补节点 eval、full-chain eval harness 和 online feedback loop。
- R60-D07-D11：补需求验收、测开计划、failure/gold lifecycle、incident dashboard、release readiness report。
- R60-D12-D16：接 CI/CD、sandbox regression、load/chaos、eval dashboard API 和 BudgetExceededGate。
- R60-D17-D18：把外部参考源新增/删除/降级原因和进入项目后的质量、成本、延迟、运维表现接入长期台账。
