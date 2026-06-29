# R60 Eval / Observability / Incident / Fallback 技术计划

状态：framework draft / living quality registry

日期：2026-06-29

上游文档：`PRD_20260628_b2b_financial_research_workbench.zh-CN.md`、`11_agent_eval_runtime_framework.zh-CN.md`、`27_r53_r60_engineering_execution_program.zh-CN.md`、`31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`、`32_r57_graph_skill_memory_pack_operating_model.zh-CN.md`、`33_r58_db_rag_retrieval_data_pipeline_control_plane.zh-CN.md`、`34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md`

## 1. 定位

R60 不是“最后答案打分器”，而是把 B 端金融研究工作台变成可审计、可复盘、可上线的质量工程层。

R60 覆盖两套不同但必须联动的评测：

1. Agent / data / full-chain eval：评估 parser、chunk/table、retrieval、rerank、context injection、tool permission、LeadReview、specialist、Workpaper、Deliverable、Dashboard projection 等节点和链路是否达标。
2. 需求 / 研发 / 测开验收：评估每个需求单、PR、release slice 是否达到产品、后端、前端、数据、agent runtime、安全、性能和上线标准。

核心原则：

- 评测对象必须可回放：每个结论能回到 `run_id`、`case_id`、`node`、`artifact_ref`、`evidence_ref`、`model_call`、`tool_call`、`gate_result`。
- Token / cost / latency 不是单独优化目标，必须和质量、覆盖、可审计性一起看。
- 兜底必须 fail-closed：暴露 typed gap，不允许用 unsupported fallback 偷过 gate。
- Eval 结果必须进入 failure / gold 生命周期，不能只作为一次性测试截图。
- 发布门控必须覆盖产品验收、工程验收、测开验收和运行观测。

## 2. 当前基座复盘

已有基础：

- 11 文档已经定义 E0-E12：Data/Index、Backend SLA、Context/Memory、Research Lead、Retrieval/Rerank、Tool、LeadReview、Specialist、Judgment/Claim、Memo、Verifier、Full-chain、Online Eval。
- 27 文档已经定义 R53-R60 program-level 执行方式、需求单字段、测试/eval/release gate 和 Git/artifact 管理。
- R56 定义了 `FinSightRuntimeFacade`、MCP-style `ToolGateway`、Hermes-style `ContextEngine`、durable workflow、trace export 和 resource/model ledger。
- R57 定义了 GraphPack / SkillPack / MemoryPack 和 ContextCompressionArtifact。
- R58 定义了 DB exact-first、hybrid retrieval、ingestion/parser/storage contracts 和 retrieval execution ledger。
- R59 定义了 Java gateway、Python runtime、Workbench 前端、artifact/review/deliverable API，以及 SandboxPolicy / ApprovalPolicy / ToolInvocationLedger。

当前缺口：

- Eval registry 和 case/gold/failure 仍主要是框架，没有统一 runtime schema。
- 对 token / cost / latency 的记录还没有和质量门控绑定。
- 测开侧的需求验收、缺陷生命周期、release readiness report 尚未产品化。
- 前端还没有面向 PM / QA / reviewer 的 eval dashboard 和 incident dashboard。
- fallback 和 incident 的边界已经在文档里出现，但没有统一分类、门控和 rollback policy。

## 3. 外部参考吸收台账

R60 只吸收成熟平台中可验证、可迁移的设计，不把项目主账本迁移到外部 SaaS。

| 参考来源 | 可吸收设计 | 本项目采用方式 |
| --- | --- | --- |
| LangSmith cost tracking | trace / project / dashboard 层面的 token 和 cost 统计；区分 input、output、cached、reasoning、tool / retrieval / custom run cost | `TokenCostLedger` 记录 run / node / model_call / tool_call / retrieval_call 成本；dashboard 按任务、节点、模型、source route 聚合 |
| Langfuse token & cost tracking | generation / embedding usage、cached token、audio/image token、自定义模型价格和 Metrics API | `UsageMetric` 支持 text / image / cache / reasoning / embedding / retrieval / tool cost 子类型；后续可 export 到 Langfuse |
| Phoenix tracing | LLM traces 覆盖 latency、token usage、runtime exception、retrieved documents、embeddings、prompt template、tool call | `TraceSpan` 必须把 prompt pack、retrieved refs、tool args digest、exception、latency 和 token 统一落账 |
| Braintrust evaluation | offline eval、immutable experiment、CI/CD gate、online scoring、production trace 回流到 dataset | `EvalRun` 与 `EvalDatasetVersion` 不可变；production failure 可 promotion 成 regression case；release gate 绑定 frozen config |
| OpenAI prompt caching | 稳定 prefix 可降低延迟和输入 token 成本；静态内容放前，变量内容放后 | `PromptCachePolicy` 要求 system / tool schema / playbook / stable rubric 前置，query / selected evidence / volatile memory 后置 |
| OpenAI Agents SDK usage | per-run / per-request usage，记录 cached tokens 和 reasoning tokens | `ModelCallMetric` 记录 request-level usage，并能按 run 汇总 context window consumption |
| Datadog LLM observability | 100% traffic span/error/token/latency metrics，适合生产监控和告警 | `ObservabilityMetricExport` 只做派生 export；本地 SQL/ObjectStore 保持审计主账本 |

参考源变更规则：

- 新增参考源必须记录：来源、版本/访问日期、采用理由、吸收对象、预期收益、风险、替代方案。
- 删除或降级参考源必须记录：不再适用原因、项目内表现、迁移影响。
- 外部平台指标只能辅助观测，不能替代本地 release gate。

R60 的外部参考必须进入三个长期维护对象，而不是散落在聊天或一次性文档里：

`ReferenceSourceLedger`

| 字段 | 含义 |
| --- | --- |
| `reference_id` | 稳定 ID，例如 `r60_ref_langsmith_cost_tracking_20260629` |
| `source_name` | 平台 / 项目 / 文档名 |
| `source_url` | 官方文档、仓库或可信出处 URL |
| `source_type` | official_docs / github_repo / product_docs / paper / benchmark / internal_review |
| `accessed_at` | 记录或复核日期 |
| `version_or_snapshot` | 文档版本、commit、release、访问日期或页面 hash |
| `adopted_design` | 被吸收的设计，例如 token cost breakdown、online scoring、trace span |
| `adoption_scope` | 进入 R60 的对象或需求单，例如 `TokenCostLedger`、`EvalRun`、`ReleaseGateResult` |
| `adoption_reason` | 为什么适合本项目 |
| `non_adopted_parts` | 明确不吸收的部分及原因 |
| `risk` | vendor lock-in、数据外传、成本、复杂度、合规等风险 |
| `owner` | 负责复核的人或角色 |
| `status` | proposed / adopted / deprecated / rejected |

`ReferenceChangeLedger`

| 字段 | 含义 |
| --- | --- |
| `change_id` | 稳定变更 ID |
| `reference_id` | 对应 `ReferenceSourceLedger.reference_id` |
| `change_type` | add / update / downgrade / remove / supersede |
| `reason` | 新增、更新、降级或删除原因 |
| `changed_design` | 影响了哪些对象、门控或需求单 |
| `before_state` | 变更前采用口径 |
| `after_state` | 变更后采用口径 |
| `migration_impact` | 对 schema、runtime、eval、dashboard、文档的影响 |
| `decision_evidence` | 项目内测试、外部版本变化、成本变化或故障记录 |
| `approved_by` | 批准角色 |
| `changed_at` | 日期 |

`ReferenceAdoptionPerformanceProfile`

| 字段 | 含义 |
| --- | --- |
| `reference_id` | 对应参考源 |
| `evaluation_window` | 项目内观察窗口 |
| `expected_benefit` | 预期提升，例如降低追溯成本、提高 failure triage 速度、降低 token 浪费 |
| `measured_effect` | 实测结果 |
| `quality_delta` | 对 eval pass rate、人工审阅通过率、缺陷复发率的影响 |
| `cost_delta` | 对 token、provider cost、工程复杂度的影响 |
| `latency_delta` | 对 p50/p95 或 queue wait 的影响 |
| `operational_notes` | 落地中遇到的问题 |
| `keep_or_revise_decision` | keep / revise / remove |

首批 R60 参考源初始台账：

| reference_id | source_url | adopted_design | adoption_scope | status |
| --- | --- | --- | --- | --- |
| `r60_ref_langsmith_cost_tracking_20260629` | `https://docs.langchain.com/langsmith/cost-tracking` | trace / project / dashboard token & cost breakdown；tool/retrieval/custom run cost | `TokenCostLedger`、`EvalDashboard` | adopted |
| `r60_ref_langfuse_token_cost_20260629` | `https://langfuse.com/docs/observability/features/token-and-cost-tracking` | generation / embedding usage；cached/image/audio/custom cost | `UsageMetric`、`ModelCallMetric` | adopted |
| `r60_ref_phoenix_tracing_20260629` | `https://arize.com/docs/phoenix/tracing/llm-traces` | latency、token、exception、retrieved docs、prompt/tool trace | `TraceSpan`、`RetrievalMetric`、`ToolMetric` | adopted |
| `r60_ref_braintrust_evaluate_20260629` | `https://www.braintrust.dev/docs/evaluate` | immutable experiment、CI/CD eval、online scoring、feedback-to-dataset | `EvalRun`、`EvalDataset`、`RegressionCaseRecord` | adopted |
| `r60_ref_openai_prompt_caching_20260629` | `https://developers.openai.com/api/docs/guides/prompt-caching` | stable prefix / volatile suffix prompt cache policy | `PromptCachePolicy`、`ContextInjectionPlan` | adopted |
| `r60_ref_openai_agents_usage_20260629` | `https://openai.github.io/openai-agents-python/usage/` | per-run / per-request usage；cached/reasoning tokens | `ModelCallMetric`、`BudgetExceededGate` | adopted |
| `r60_ref_datadog_llm_metrics_20260629` | `https://docs.datadoghq.com/llm_observability/monitoring/metrics/` | 100% traffic span/error/token/latency production metrics | `ObservabilityMetricExport`、`IncidentDashboard` | adopted |

## 4. R60 质量对象模型

R60 的对象分为五类。

Eval 对象：

- `EvalCase`：单个测试用例，含 user objective、task mode、domain/lane、required dimensions、expected evidence roles、forbidden behaviors。
- `EvalDataset`：case 集合，含 version、split、scope、owner、promotion status。
- `EvalRun`：一次评测执行，含 code_commit、data_snapshot_id、model_profile、runtime_config、budget_profile。
- `EvalMetricResult`：指标结果，含 metric_id、value、threshold、pass/fail/warn、diagnosis。
- `EvalGateResult`：门控结果，含 gate_id、input refs、decision、reason、repair_required。

Trace / observability 对象：

- `TraceSpan`：run / node / tool / model / retrieval / parser / renderer / frontend action 的统一 span。
- `ModelCallMetric`：model、input_tokens、output_tokens、cached_tokens、reasoning_tokens、cost、latency、retry_count、finish_reason。
- `RetrievalMetric`：query、route、top_k、candidate_count、hit_count、qrel_hit、rerank_delta、dropped_reason。
- `ParserMetric`：source、file/page/table/chunk、parse_status、row_count、rejection taxonomy、truncation flag。
- `ToolMetric`：tool、permission policy、sandbox profile、input/output digest、timeout、exception、cost。

Lifecycle 对象：

- `FailureEvent`：失败事实，含 failure taxonomy、severity、repro command、artifact refs、owner、resolution status。
- `GoldPromotionRecord`：优秀 case / answer / workpaper / retrieval result 晋升为 gold 的记录。
- `RegressionCaseRecord`：线上或人工发现问题转入 regression set 的记录。
- `IncidentRecord`：生产或预生产事故，含 impact、root cause、mitigation、rollback、postmortem。

需求验收对象：

- `DemandAcceptanceRecord`：需求单验收主账本，含 PRD trace、technical doc trace、acceptance checklist、test evidence、review sign-off。
- `QAExecutionPlan`：测开计划，含 deterministic、integration、E2E、load、chaos、manual review、regression scope。
- `DefectRecord`：缺陷单，含 severity、blocking status、root cause、fix commit、verification run。

发布对象：

- `ReleaseGateResult`：code / data / runtime / frontend / eval / security / operations 发布门控结果。
- `ReleaseReadinessReport`：发布前报告，汇总版本、变更、评测、缺陷、风险、rollback 和上线建议。

## 5. Agent / Data / Full-chain Eval 矩阵

| 层级 | 评测对象 | 必须回答的问题 | 通过标准 |
| --- | --- | --- | --- |
| E0 Data / Source | source registry、raw document、parser artifact、lineage | 数据是否真实可得、可解析、可追溯 | required source role 无 silent missing；raw -> parser -> row lineage 可回放 |
| E1 Parser / Chunk / Table | PDF/HTML/table/parser/chunk | 是否因截断、表格错位、chunk 过粗导致召回差 | row/table/chunk 有 schema、source ref、rejection reason；关键表不可只进纯文本 |
| E2 DB / Gold Mart | SQL exact、Gold Fact / Signal Mart、Graph Store | exact row 是否可查、join key 是否稳定 | ticker/company/product/time/source key 唯一性和 coverage gate 通过 |
| E3 Retrieval / Rerank | BM25/ObjectBM25/FTS/Milvus/graph hybrid | 召回是否覆盖目标，rerank 是否误杀强证据 | qrels / target-in-candidates / source-role recall / rerank precision 达阈值 |
| E4 Context Injection | ContextEngine / compression / memory | 注入内容是否够用、过期、越权或丢 exact refs | 每次注入有 `ContextInjectionPlan` 和 compression artifact；exact facts 不被摘要替代 |
| E5 Tool / Sandbox | DB、crawler、browser、parser、renderer、quant worker | 工具是否按权限、白名单和审批执行 | ToolInvocationLedger 完整；越权 fail closed；失败有 typed reason |
| E6 Research Lead | objective contract、plan、review checkpoint | Lead 是否持续监督目标，而不是只派发任务 | 能审计 unmet objective、retrievable gap、bounded/commercial gap，并触发 targeted repair |
| E7 Specialist | fundamental、product、market、capital、risk、quant | 专家是否拿到 role-specific evidence 并输出结构化结论 | 输出 ClaimCard / WorkpaperEvent / gap reason，不允许泛化复述 |
| E8 Judgment | thesis / counter-thesis / JudgmentState | 证据是否支撑判断，反证是否被处理 | claim 有 authority、scope、counter-evidence、confidence 和 boundary |
| E9 Workpaper | WorkpaperPack / WorkpaperEvent | 底稿是否可审阅、可协作、可追责 | 事件 append-only；每个结论有 refs；人工 review 能批注、退回、批准 |
| E10 Deliverable | memo、Word、PPT、Excel、dashboard projection | 输出是否可读、可交付、引用准确 | 文体、结构、citation、chart/table、artifact refs 和 review status 达标 |
| E11 Full-chain | 端到端任务 | 用户目标是否被回答，缺口是否真实暴露 | full-chain case 覆盖 run trace、evidence、ClaimCards、gap、deliverable、eval |
| E12 Online Eval | 生产/预生产运行 | 线上质量、成本、延迟是否漂移 | failure queue、gold promotion、budget trend、SLA、incident dashboard 持续运行 |

## 6. 需求 / 研发 / 测开验收矩阵

| 角色 / 环节 | 验收重点 | 必须留痕 |
| --- | --- | --- |
| Product / PM | 是否解决 PRD 用户任务，工作流是否完整，人工介入点是否合理 | PRD section、user scenario、product acceptance、known non-goals |
| Data Engineering | 数据源、解析、lineage、schema、coverage、refresh | source manifest、parser metric、coverage report、data snapshot、quality gate |
| Backend | API contract、task lifecycle、queue、SSE、auth/RBAC、artifact、incident | OpenAPI/schema、integration tests、load smoke、error taxonomy、audit rows |
| Frontend | Dashboard、Evidence Workbench、Workpaper、Review Queue、Deliverable、Admin/Ops | Playwright/E2E、visual check、state/error/empty/loading cases、accessibility smoke |
| Agent Runtime | graph execution、checkpoint/resume、tool permission、context、model routing | run trace、node outputs、ToolInvocationLedger、ContextInjectionPlan、model usage |
| Retrieval / RAG | intent route、hybrid recall、rerank、qrels、source-role coverage | retrieval ledger、target-in-candidates、rerank audit、dropped evidence diagnosis |
| Quant | PIT dataset、leakage guard、factor/backtest/paper trading | frozen config、split manifest、backtest report、human approval record |
| QA / 测开 | 测试计划、case catalog、defect lifecycle、release readiness | QAExecutionPlan、TestRun、DefectRecord、RegressionCaseRecord、ReleaseReadinessReport |
| Security / Sandbox | tool read/write/network/credential boundary、approval | policy version、blocked call、approval event、sandbox regression |
| Ops / Release | CI、rollback、monitoring、incident、cost budget | release gate result、rollback plan、alerts、budget dashboard |

## 7. Token / Cost / Latency / Quality 统一治理

成熟平台的共同点不是“少花 token”，而是把 token、cost、latency、质量、错误和 trace 放到同一个观察面里。对本项目而言，token 是注意力预算和经营成本，不是越低越好。

R60 采用以下治理模型。

### 7.1 记录粒度

每个模型调用必须记录：

- `task_id`、`run_id`、`case_id`、`node`、`actor`、`model`、`provider`；
- `input_tokens`、`output_tokens`、`cached_tokens`、`reasoning_tokens`、`embedding_tokens`；
- `input_cost`、`output_cost`、`tool_cost`、`retrieval_cost`、`total_cost`；
- `latency_ms`、`queue_wait_ms`、`retry_count`、`timeout_flag`；
- prompt pack ids、context artifact ids、selected evidence refs；
- output quality gate result。

### 7.2 质量成本指标

禁止只看 total token。必须同时看：

- `cost_per_accepted_workpaper`：通过人工或 gate 的底稿成本。
- `cost_per_approved_deliverable`：可交付报告成本。
- `thesis_density_per_1k_tokens`：每 1k 输出 token 中有效判断、原因、反证和触发条件密度。
- `evidence_coverage_per_1k_input_tokens`：输入 token 是否覆盖高 authority evidence，而不是灌入低价值文本。
- `repair_success_per_extra_cost`：追加 targeted repair 的边际收益。
- `latency_adjusted_quality_score`：质量得分除以端到端耗时或 SLA bucket。

### 7.3 Budget profile

不同任务模式使用不同预算，而不是全链路固定一套模型和 token。

| Task mode | 预算原则 | 模型/工具策略 |
| --- | --- | --- |
| Quick Answer | 低延迟、低成本、少节点 | DB exact + compact RAG + flash model；无复杂 repair |
| Focused Memo | 中等预算、保证 citation | Research Lead + 2-3 specialist + targeted retrieval；必要时单次 repair |
| Deep Research | 高预算、质量优先 | full LeadReview、multi-specialist、web repair、counter-thesis、verifier |
| Watchlist Monitor | 批量低成本、增量更新 | cache / diff / alert-first；只对异常升级模型 |
| Quant Research | 数据和计算优先 | LLM 只做 hypothesis / explanation；factor build/backtest 走 deterministic engine |
| Deliverable Render | 输出质量优先但不重复研究 | writer 只消费 Workpaper/JudgmentState，不重新检索和重复推理 |

### 7.4 Prompt caching 和上下文复用

Prompt 组织必须服务缓存：

1. stable prefix：system policy、tool schema、authority rubric、行业 playbook、output contract；
2. semi-stable context：company profile、GraphPack/SkillPack version、team preference；
3. volatile context：用户问题、最新 evidence refs、runtime gaps、repair instruction。

前两层尽量稳定、前置、版本化；第三层后置。这样可以利用 provider prompt caching，同时让 ContextEngine 更容易复用 compression artifact。

### 7.5 动态调度和早停

- 低风险节点优先使用便宜模型或 deterministic tool。
- 高风险节点如 Judgment、LeadReview、Verifier、Counter-thesis 才升级到强模型。
- retrieval-first：能用 SQL exact / graph / parser row 解决的，不让 LLM 从长文本里猜。
- repair 要有边际收益阈值：如果新增证据只增加弱 L4 signal，不能无限追加。
- 超预算不静默降级：触发 `BudgetExceededGate`，由 Research Lead 决定缩小范围、请求人工批准或暴露 typed gap。

## 8. Incident / Fallback 规则

Failure taxonomy：

- `data_unavailable`：公开源不存在或无法访问。
- `parser_failure`：源存在但 parser 无法结构化。
- `retrieval_recall_drop`：目标证据存在但未召回。
- `rerank_false_negative`：召回后被 rerank 丢掉。
- `context_injection_loss`：证据被压缩或注入阶段丢失。
- `authority_misuse`：弱信号被提权成强结论。
- `tool_permission_block`：工具被 sandbox / approval policy 阻断。
- `model_output_quality_failure`：输出不满足可读性、判断密度或 citation gate。
- `budget_exceeded`：超 token/cost/latency 预算。
- `frontend_projection_mismatch`：前端显示与后端 artifact / eval 账本不一致。

Fallback 原则：

- 允许 fallback 的前提：它是产品定义的降级能力，且会写入 `FallbackEvent`。
- 不允许 fallback 的情况：为了让测试通过而隐藏 parser/retrieval/context/gate 错误。
- fallback 输出必须告诉用户：哪些部分完成、哪些部分降级、哪些结论不可提权。
- 任何 fallback 都必须进入 failure queue，除非 gate 明确标为 expected degradation。

## 9. Release Gates

R60 的 Release Gates 不只输出 pass/fail，还必须输出 `pass_level`。原因是企业级项目里“能跑通”和“可上线”不是同一件事。

| pass_level | 质量定义 | 可进入阶段 | 必须具备 |
| --- | --- | --- | --- |
| `L0_smoke_pass` | 最小链路能执行，或单点合同不崩 | 继续开发 | 基础 schema / API / script 成功；失败原因可见 |
| `L1_contract_pass` | 工程合同完整，能被下游稳定依赖 | 集成开发 | schema、event、artifact、trace、permission、error taxonomy、contract tests |
| `L2_internal_dogfood_pass` | 内部真实任务可用，能减少一部分人工重复劳动 | 内部 dogfood | Product workflow、Workpaper / evidence / gap、human review、known gaps、manual recovery |
| `L3_release_candidate_pass` | 可给试点用户，主要质量、运维和安全门控通过 | 受控 pilot | ReleaseReadinessReport、incident/fallback、rollback、cost budget、sandbox、E2E、QA sign-off |
| `L4_production_pass` | 企业级正式交付，支持多用户、长任务、异常和持续监控 | 生产发布 | SLA/SLO、load/chaos、on-call/runbook、tenant/RBAC、audit retention、online eval、release owner |

四类验收必须同时记录：

| 验收类型 | R60 记录对象 |
| --- | --- |
| Product acceptance | `DemandAcceptanceRecord.product_acceptance` |
| Engineering acceptance | `DemandAcceptanceRecord.engineering_acceptance` |
| Quality acceptance | `EvalGateResult`、`FailureEvent`、`GoldPromotionRecord` |
| Ops acceptance | `ReleaseGateResult`、`IncidentRecord`、`TokenCostLedger` |

| Gate | 通过条件 |
| --- | --- |
| CodeSubmissionGate | `git diff --check`、secret scan、targeted tests 通过；无无主大文件或私密 artifact |
| DataContractGate | schema、lineage、coverage、SQLite/ObjectStore parity、parser rejection taxonomy 通过 |
| RuntimeIntegrationGate | run audit、node execution、checkpoint/resume、tool ledger、context injection 有 trace |
| EvalRegressionGate | frozen eval dataset 通过；新增 failure 有 owner 和 resolution |
| FrontendUXGate | 关键页面 E2E、错误/空状态、artifact trace、review queue、dashboard projection 通过 |
| SecuritySandboxGate | 工具权限、domain allowlist、credential boundary、approval flow 和 blocking UX 通过 |
| TokenCostGate | budget profile、per-node usage、cached/reasoning/tool/retrieval cost 记录完整；无 silent overrun |
| IncidentReadinessGate | incident taxonomy、alert、rollback、postmortem template 和 on-call runbook 可用 |
| ReleaseReadinessGate | 产品验收、工程验收、测开报告、已知风险、rollback plan 和用户反馈入口齐全 |

生产级判定：

- 只有 `CodeSubmissionGate + DataContractGate + RuntimeIntegrationGate` 通过，最多是 `L1_contract_pass`。
- 加上 Workpaper / Deliverable / human review workflow 通过，才可能是 `L2_internal_dogfood_pass`。
- 加上 EvalRegressionGate、FrontendUXGate、SecuritySandboxGate、TokenCostGate、IncidentReadinessGate 和 ReleaseReadinessGate，才可能是 `L3_release_candidate_pass`。
- `L4_production_pass` 还必须证明多用户/长任务/异常恢复/成本预算/权限/上线运维可持续，不能由单次 case 或单次人工验收直接授予。

## 10. R60 Demand List

| ID | 需求 | 状态 | 通过条件 |
| --- | --- | --- | --- |
| R60-D01 | Eval registry schema | draft | `EvalCase`、`EvalDataset`、`EvalRun`、`EvalMetricResult`、`EvalGateResult` schema 确定 |
| R60-D02 | Trace / usage schema | draft | `TraceSpan`、`ModelCallMetric`、`RetrievalMetric`、`ParserMetric`、`ToolMetric` 可落 SQL |
| R60-D03 | TokenCostLedger | draft | run/node/model/tool/retrieval cost 可聚合，支持 cache/reasoning token |
| R60-D04 | Node eval gates | draft | E0-E10 每层至少有 deterministic gate 和 failure taxonomy |
| R60-D05 | Full-chain eval harness | draft | E11 case 能生成 run trace、workpaper、deliverable、eval report |
| R60-D06 | Online eval feedback loop | draft | production failure / reviewer feedback 可转 regression case |
| R60-D07 | DemandAcceptanceRecord | draft | 每个需求单有 PRD trace、技术 trace、测试证据和 sign-off |
| R60-D08 | QAExecutionPlan / DefectRecord | draft | 测开能按 release slice 建计划、跑 case、开缺陷、复验 |
| R60-D09 | Failure / gold lifecycle | draft | failure 可修复/关闭/晋升 regression；good case 可晋升 gold |
| R60-D10 | Incident dashboard | draft | parser/retrieval/tool/model/frontend/latency/cost incident 可见 |
| R60-D11 | Release readiness report | draft | release candidate 自动汇总 gates、风险、rollback 和剩余缺口 |
| R60-D12 | CI/CD gate integration | draft | deterministic tests、schema checks、eval smoke 接入 CI 或等价脚本 |
| R60-D13 | Sandbox regression | draft | R59 sandbox/approval policy 有可复现阻断和允许用例 |
| R60-D14 | Load / chaos / SLA tests | draft | queue wait、p95 latency、DB/ObjectStore 压力、provider failure 有测试 |
| R60-D15 | Eval dashboard API | draft | 前端能按 task/run/case/node 查看 trace、metric、failure、release gate |
| R60-D16 | BudgetExceededGate | draft | 超预算时能 fail closed、缩范围、请求人工批准或暴露 typed gap |
| R60-D17 | ReferenceSourceLedger / ChangeLedger | draft | R60 外部参考源新增、更新、降级、删除都有来源、原因、影响和批准记录 |
| R60-D18 | ReferenceAdoptionPerformanceProfile | draft | 外部参考设计进入项目后的质量、成本、延迟和运维表现可复核 |

## 11. 执行顺序

1. R60-0 inventory：盘点现有 eval scripts、run audit rows、trace fields、case catalog、frontend dashboard。
2. R60-1 schema：先落 EvalRegistry、TraceSpan、UsageMetric、FailureEvent、DemandAcceptanceRecord。
3. R60-2 deterministic gates：补 parser/chunk/retrieval/context/tool/sandbox/release 的非 LLM gate。
4. R60-3 online trace：把 model/tool/retrieval/parser/renderer/frontend action 纳入统一 trace。
5. R60-4 token/cost dashboard：按 task/node/model/source route 展示成本、延迟、质量和 repair ROI。
6. R60-5 QA/release workflow：把需求验收、缺陷、release readiness report 产品化。
7. R60-6 reference governance：把外部参考源、变更和采用后表现接入 `ReferenceSourceLedger` / `ReferenceChangeLedger` / `ReferenceAdoptionPerformanceProfile`。
8. R60-7 full-chain regression：选 10-20 个代表 case 跑 release gate，失败进入 failure queue。

## 12. 不做什么

- 不把 eval 简化成 LLM judge 对最终 memo 打分。
- 不用更短输出冒充更高效率。
- 不用 fallback 覆盖 parser / retrieval / context 的真实错误。
- 不在没有 frozen config 和 data snapshot 的情况下比较 eval run。
- 不让 writer 自行重新检索来弥补上游缺陷。
- 不把外部 SaaS 的 dashboard 当作本地审计主账本。

## 13. 当前判断

R60 的关键不是“多跑几个 case”，而是把项目从实验室脚本推进到企业级质量工程：每个需求有验收，每个节点有指标，每次模型调用有成本，每个失败有分类，每个发布有门控。

Token 治理的正确方向也不是压低模型调用，而是把 token 用在最有边际收益的位置：DB exact / graph / parser row 先拿事实，ContextEngine 控制注入，Research Lead 决定是否 repair，强模型只用于高价值 judgment 和 verifier，最后用 release gate 检查“每花一笔 token 是否换来了可审计、可交付、可复用的研究质量”。

## 14. S10 Runtime Closeout（2026-06-29）

R60 的 release-candidate 必需子集已经在 R53-R60 release slice `S10 Enterprise Hardening / Release Candidate` 中落成 runtime contract，并达到自身范围内的 `L4_scope_pass`。

已落对象：

- `Tenant` / `User` / `ProjectSpace` / `RoleAssignment` / `PermissionCheck`；
- `DemandAcceptanceRecord`；
- `LoadScenario` / `LoadTaskObservation` / `ChaosEvent` / `SLAObservation`；
- `IncidentRecord` / `IncidentDashboardProjection`；
- `OnlineEvalFeedbackItem` / `RegressionCaseRecord` / `GoldPromotionRecord`；
- `ReleaseReadinessReport` / `ReleaseGateResult`。

真实构建结果：

- S0-S9 dependency summaries：`10/10 pass`；
- RBAC：`2` tenants、`4` users、`4` role assignments、`5` permission checks，包含同租户 allow 和跨租户 deny；
- load / chaos / SLA：`20` load task observations、`4` recovered chaos events、`6` SLA observations，记录 p95 queue wait、p95 latency、recovery rate、SSE reconnect、token 和 cost；
- incidents：parser / retrieval / tool / model / frontend / cost 六类 incident 全部进入 dashboard projection；
- online eval lifecycle：`3` feedback items，生成 `2` regression cases 和 `1` gold promotion；
- release readiness：报告包含 gate refs、known gaps、rollback plan、owner、user feedback entry 和 pilot scope；
- release decision：`S10_L4_scope_pass_release_candidate_ready`；
- full product release status：`not_l4_production_pass`。

生成物：

- `src/sec_agent/r53_r60_enterprise_release_candidate.py`
- `scripts/engineering/build_r53_r60_s10_enterprise_release_candidate.py`
- `tests/test_r53_r60_enterprise_release_candidate.py`
- `configs/r53_r60/s10_enterprise_release_candidate_schema_v0_1.json`
- `data/manifests/r53_r60_s10_enterprise_release_candidate_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s10_enterprise_release_candidate_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s10_enterprise_release_candidate_l4_scope_pass.zh-CN.md`

边界：

- S10 不等于正式生产上线；它只证明 controlled internal pilot release candidate 在权限、负载/恢复、incident、release report、online eval feedback 生命周期上达到本 slice 的 enterprise-grade。
- `L4_production_pass` 仍需要真实试点、多租户长期运行、云端/生产 SLA、on-call/runbook、审计留存、异常恢复和成本预算的持续证据。
