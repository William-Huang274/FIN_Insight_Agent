# 09-15 Completion Gap Register

日期：2026-06-17

## Scope

本文件是在 16 文档 Step 0-2 已落地后，对 09-15 文档做一次系统回扫，抽出仍未实现、未验收、只做了 runtime 骨架但未证明产品级闭环的事项。它不是新方向，而是把下一轮不能遗忘的缺口收敛成可执行 register。

扫描范围：

- `09_lead_supervised_closed_loop_research_framework.zh-CN.md`
- `10_backend_frontend_runtime_framework.zh-CN.md`
- `11_agent_eval_runtime_framework.zh-CN.md`
- `12_integrated_execution_plan.zh-CN.md`
- `13_09_11_remaining_full_completion_plan.zh-CN.md`
- `14_vnext_50_case_eval_catalog.zh-CN.md`
- `15_source_layer_capability_and_analyst_first_optimization.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`

## Classification

- `runtime_gap`：合同已定义，但主 runtime 尚未完整接入或只接了局部路径。
- `eval_gap`：代码或框架已有，但缺少 release-gate 级别用例证明。
- `source_gap`：源、parser、resolver 或 entity binding 还没达到 lane / role 可用。
- `prod_hardening_gap`：smoke 通过，但未达到后端产品化、并发、恢复或前端可审计要求。
- `known_boundary`：公开源或商业数据边界导致不能补齐，只能显式暴露。

## Current Implemented Baseline

已进入 runtime 或已经通过小范围 gate 的内容：

- Research Lead 已有 `ResearchObjectiveContract`、`LeadReviewCheckpoint`、`TargetedRepairPlan`、`MemoLogicPlan` 主链路骨架，并接入 scoped public web gap repair。
- FundamentalStatementPack / JudgmentState 已进入主链路，基本面分析不再只靠普通证据摘要。
- R0-R11 readiness、R3 Milvus 本地 runtime、R5 CUDA queue smoke、R10 backend load smoke、R11 Workbench trace/eval panels、R12 50-case catalog 和 1-2 case diagnostic loop 已跑通。
- Source layer 已有 L1 product KPI runtime projection、official product surface、public official API context、developer ecosystem、App Store、ATS hiring、USAspending、CDW channel offer/review 等第一批 bounded context rows。
- 16 文档新增的 L4 runtime contract、VerticalSourceLaneRegistry、V1-V8 vertical lane packages 已落地；V2-V8 均生成 AnalystPlaybook、SourcePlaybook、coverage report 和 `3` 个 representative cases。
- V1 source coverage closeout 和 repair tranche 已落地：真实 materialized-row audit 从 `4/10` requirement pass / `6` source gaps 推进到 `10/10` requirement pass、`0` source gaps、`475` observed V1 runtime rows；`15` commercial gaps 继续显式保留，公开 proxy 不替代商业 tracker。
- V2-V8 lane-scoped public context rows 已落地：新增 `77` 条 parser-backed bounded context rows，覆盖 trusted external、macro bridge、public proxy、USAspending、OpenAlex 等 route；最新 `vertical_lane_source_closeouts_v0_1` 达到 `8/8` lane pass、所有 lane `source_gap_requirement_count=0`，但 commercial gaps 仍显式保留。
- 603 公司 company-level public source coverage matrix 已落地：`company_public_source_coverage_matrix_v0_1` 把每家公司按 lane requirement 下钻到 source role / parser / issuer-product-counterparty binding / gap class / repair queue。首次审计 `603` 公司、`4,418` requirements，其中 `432` pass、`3,986` source gaps、`0` parser/resolver/fail，大量缺口是 company-specific runtime rows 尚未物化，而不是 lane route 不存在；repair queue 已接入 Z 盘 product graph seed，`1,584` 条 seed available，high-priority 的 `primary_company_disclosure` `417/417` 有 seed、`official_product_surface` `208/214` 有 seed。
- Product-family source route plan 已落地：`603/603` 公司都有 `CompanyProductFamilyAssignment` 和 `FamilySourceRoutePlan`，当前 `45` 个 family、`799` 个 assignment、`3,132` 条 route plan；route status 为 `141` 条 family-bound runtime row、`460` 条 company-route runtime row、`1,360` 条 seed-only、`1,171` 条未物化。已加 weak-term gate，避免 `ip/node/power/rack/server/cloud/vehicle/mobility` 等弱词污染 assignment。

这些 baseline 只代表局部合同可运行，不代表 09-15 规划已全部产品化或 release-ready。

## Gap Register

| Gap ID | Source | Area | Status | Why Still Open | Acceptance Gate |
| --- | --- | --- | --- | --- | --- |
| CG-09-01 | 09 / 13 R7 | Research Lead closed-loop supervision | eval_gap | Lead checkpoint 和 targeted repair 已接入，但还没有在 12-case successor / 10-20 broader gate 中证明它能稳定发现 retrievable gaps、触发正确 agent / tool、并把增量证据送回 MemoLogicPlan。 | R12 successor 中每个 deep case 都有 objective coverage audit、gap classification、repair delta audit；失败项进入 failure queue。 |
| CG-09-02 | 09 / 13 R8 | Role-specific evidence selector quotas | runtime_gap | Product / Market / Capital 可见行配额已有修复，但 V1 lane 和后续 lane 的 role-visible row 分布还没用真实 lane cases 全量证明。 | 每个 representative case 输出 role-visible recall、dropped-row taxonomy、selector gap；Product/Market/Capital 不再静默空分布。 |
| CG-09-03 | 09 / 13 R5 | CUDA BGE queue and resource scheduler | prod_hardening_gap | 本地/云端 smoke 已证明可排队和 spillover，但没有 release 级并发 profile、cache hit、wait time、failure reason 和 SLA trend。 | R5/R10 load gate 记录 resident model count、CUDA wait、CPU spillover、p95 latency、provider latency、token/cost 和失败恢复。 |
| CG-09-04 | 09 / 13 R5/R7 | ModelRouter / AgentCoalescer | runtime_gap | 有 deterministic routing skeleton，但还没有证明在保持质量的情况下合并或跳过 agent、降模型、降低 token 成本。 | 对同一 case 做 route A/B，记录质量不降、cost/token 降幅、被跳过 specialist 的 deterministic gap card。 |
| CG-10-01 | 10 / 12 P9 / 13 R10 | Java gateway to production DB/Redis/MQ | prod_hardening_gap | Java gateway、Python worker、Redis/file queue smoke 通过，但真实 Docker MySQL/Postgres + Redis + JDBC migration + recovery parity 仍未完成。 | Docker profile 下 create/list/events/cancel/resume/retry/stuck-run recovery 全部通过，SQL 是最终审计源。 |
| CG-10-02 | 10 / 13 R1/R10 | SQL/object-store audit completeness | prod_hardening_gap | SQL audit store 覆盖大量表，但 D3/D4/D5/D11 的 true SQL resolver、object-store provenance、vintage history、vector/graph memory parity 仍有明确补账项。 | 不依赖 per-run JSON 时也能按 run/case/node/evidence/claim/gap/gate/context/artifact/model_call 复盘。 |
| CG-10-03 | 10 / 12 P8 / 13 R11 | Workbench/front-end product trace | eval_gap | 面板和 artifact inspector 已有，但未用 latest R12 lane/source runs 验证用户能从前端追到 evidence、ClaimCard、gap、gate、context、eval 差异和最终 report。 | 用 R12 real run 在前端完成 trace drilldown，并把截图/trace id 写入 eval result。 |
| CG-10-04 | 09 L9 / 10 / 13 R6 | Document and multimodal input pipeline | runtime_gap | Tool Capability Registry 有输入解析合同，但 PDF/DOCX/Excel/Markdown/PPT/image/video 上传、解析、provenance-gated UserProvidedEvidencePack 尚未进入主后端。 | 上传样例文件后生成 parsed input artifacts、provenance、parser_failed gap，并被 Research Lead 作为用户证据边界消费。 |
| CG-10-05 | 10 Context Runtime / 13 R4 | Enterprise context and memory governance | prod_hardening_gap | ContextEngine facade 和 memory taxonomy 已有方向，D11 memory 是索引层；跨 run consolidation、staleness、supersession、memory drilldown parity 仍未 release 验收。 | memory entry 可钻到 claim/gap/derived/evidence/gate，过期或冲突时不能注入为事实。 |
| CG-11-01 | 11 / 13 R12 / 14 | 12-case successor release gate | eval_gap | 只跑过 1-2 个 diagnostic/full-chain 激活 case，source-layer 和 lane registry 更新后 12-case successor 尚未重跑。 | 最新 code/data snapshot 上 12-case successor pass，失败全部进入 failure lifecycle。 |
| CG-11-02 | 11 / 13 R12 / 14 | 10-20 broader release gate and readiness report | eval_gap | 50-case catalog 已设计，subset runner 已接入，但 10-20 case broader gate 和 release readiness report 未完成。 | 10-20 case 输出 node metrics、quality/cost/latency、source gaps、commercial gaps 和 release readiness report。 |
| CG-11-03 | 11 A3-A6 | Node-level eval coverage | eval_gap | LeadReviewCheckpoint、TargetedRepairPlan、MemoLogicPlan、ContextEngine、ModelRouter/AgentCoalescer 的 eval 还不够系统。 | 每个节点有 deterministic fixture、real-run sample、failure taxonomy 和 regression owner。 |
| CG-11-04 | 11 E4 / 12 P4 | Retrieval/rerank gold-labeled eval | eval_gap | 已有预算审计和 source coverage gate，但 target-in-candidates、pre/post-rerank precision、role-visible recall 仍缺 human-reviewed gold。 | Reviewed qrels 覆盖 L1/L2/L3/lane cases，报告 recall、precision、target-in-candidates 和 dropped-row reason。 |
| CG-11-05 | 11 E0/E5 | Data-processing eval depth | eval_gap | 12 文档要求 chunk/truncation/table/structured extraction eval，但当前只做了部分 source/parser gates。 | chunk boundary、early truncation、table extraction、structured extraction、downstream retrieval attribution 写入 eval store。 |
| CG-11-06 | 11 E7-E10 | LLM judge and human calibration | eval_gap | LLM-as-judge 边界已定义，但 judge prompt digest、rubric version、human calibration sampling、drift audit 仍未形成闭环。 | Judge run 可复盘，抽样人审一致性达标，不把 judge 结果当唯一 release authority。 |
| CG-12-01 | 12 / 13 R3 | Milvus and vector/graph parity | prod_hardening_gap | 603-company Milvus 已可作为 runtime semantic supplement，但 graph memory parity、vector memory drilldown、Milvus vs BM25/ObjectBM25 hybrid A/B 仍需持续 gate。 | Milvus query smoke、route gate、hybrid A/B、memory drilldown parity 均通过，Milvus 仍不承担 exact authority。 |
| CG-12-02 | 12 / 13 R10 | Backend load/SLA beyond smoke | prod_hardening_gap | R10 只有本地 smoke，不等于上线级 worker pool、provider latency、DB/ObjectStore 写入压力和失败恢复。 | load_mix_15 或同等级压测记录 p95、queue wait、success/error rate、token/cost、retry/cancel/resume。 |
| CG-14-01 | 14 | 50-case catalog lifecycle | eval_gap | 50-case catalog 已落第一版，但尚未把成功样本晋级 gold、失败样本纳入 failure queue、过期样本淘汰。 | 每轮 eval 自动更新 case result、failure lifecycle、gold candidate/promotion/deprecation 状态。 |
| CG-15-01 | 15 / 16 | V1 source coverage closeout | closed | V1 lane package closeout 和 source repair tranche 已完成；当前 closeout `status=pass`，`10/10` requirement pass、`0` source gaps、`475` observed V1 runtime rows、`15` commercial gaps retained。 | 已通过；后续 V1 case 只能把 remaining commercial gaps 作为边界，不能用公开 proxy 兜底。 |
| CG-15-02 | 15 SLR3 | Supplier/customer official news and mainstream financial news backfill | source_gap | 目前主要是 parser smoke / registry ready，尚未做真实持续 backfill 和 entity binding。 | 生成 bounded context rows，带 issuer/counterparty/product binding，specialist 可见，不能提权为 sales/backlog/share。 |
| CG-15-03 | 15 SLR3 | App marketplace and ecommerce expansion | source_gap | Apple App Store 和 CDW 已接入；Google Play、Amazon、BestBuy、Walmart、JD、Tmall、B&H、Newegg 等仍有 policy、anti-bot、parser variant 和 entity resolver gaps。 | 每个接入源有合规访问记录、parser-backed rows、entity binding、claim boundary 和 fail-closed refusal reasons。 |
| CG-15-04 | 15 SLR1/SLR3 | Official API resolver gaps | source_gap | FDIC/EIA/OpenAlex/PatentsView 的当前样本缺少强 issuer/product/asset/topic binding，不能冒充 solved。 | 通过 live/backfill 获取可绑定行，或明确 `resolver_gap` / `source_not_suitable_for_company_claim`。 |
| CG-15-05 | 15 SL4/SL5 | Analyst-first memo quality with source-layer evidence | eval_gap | Memo surface 可读性改善，但产品、市场、资本、供应链的有用 insight 密度仍依赖上游 source-layer selector 和 repair 成功率。 | Deep cases 的 MemoLogicPlan 显示每个维度 judgment、evidence chain、counter-read、gap placement，写作 gate 阻止模板化 caveat 堆叠。 |
| CG-15-06 | 15 / 13 R12 | Product/market/capital evidence depth cases | eval_gap | 当前 representative cases 还没有覆盖足够行业和公开源深度，尤其产品规格、竞品比较、真实资本/订单关系图。 | V1 后续至少新增 2-3 个 evidence-depth case，验证产品规格矩阵、竞争对比、capital/ownership graph 和 bounded proxy rules。 |
| CG-16-01 | 16 | V2-V8 lane packages and source closeout | closed | V2-V8 lane package、3-case fixtures、lane-scoped bounded public rows 和 source closeout 已完成；最新 closeout `8/8` lane pass，所有 lane `source_gap_requirement_count=0`。 | 已通过；后续每个 lane case 仍必须保留 commercial gap 边界，不能把公开 proxy 提权为销量/份额/ASP/POS/处方/注册/VIO/consensus。 |
| CG-16-02 | 16 | 603-company issuer-level public source coverage | source_gap | Company-level matrix 已落地，但首次审计只有 `1/603` company 达到 all-requirement public interface ready；`220` partial、`382` gap，`3,986` repair requests 主要是 company-specific runtime rows 尚未物化。 | 按 repair queue 分 tranche 接入并重跑 matrix；每轮必须降低 `repair_queue_count`，并把不能公开补齐的项改写为 bounded/commercial gap，而不是留在 source_gap。 |
| CG-16-03 | 16 | Product-family scoped L2/L3 source materialization | source_gap | ProductFamilyLaneRegistry / CompanyProductFamilyAssignment / FamilySourceRoutePlan 已覆盖 `603/603` 公司，但 `1,360` 条 route 只有 seed 未物化，`1,171` 条 route 仍缺源。当前完成的是“family 路由和可用性审计”，不是所有官方产品页、可信外部源和 proxy 源都已真实抓取解析。 | 以 `family_source_route_plan_v0_1.jsonl` 为 repair queue，按 `seed_available_not_materialized -> runtime row`、`not_materialized -> discovered/fetched/parsed row or bounded/commercial gap` 的顺序清队列；每轮抽样核验 family assignment 和 sample URL，不允许 L3 proxy 提权。 |

## Execution Order

建议按以下顺序推进，不再把 09、10、11、12、13、14、15 分开实施：

1. 用 16 Step 8 company matrix 和 Step 9 family route plan 作为最新 source baseline，先按 `primary_company_disclosure` / `official_product_surface` / family-scoped L2 / family-scoped L3 priority 做 company-specific repair tranche。
2. 每个 repair tranche 后重跑 company matrix、family route plan 和 lane closeout，确认 gap 是减少、改类为 parser/resolver、或被证明为 bounded/commercial gap。
3. 补 role-specific selector eval：确保 Product / Market / Capital 在 V1-V8 lane cases 中能看到正确 source-layer rows。
4. 跑 12-case successor：使用最新 lane/source/runtime 数据，记录 full trace 和 failure/gold lifecycle。
5. 修 R12 暴露的问题，再跑 10-20 broader gate 和 release readiness report。
6. 后端补生产级 DB/Redis/ObjectStore/SSE/cancel/resume/recovery/load gate。

## Non-Negotiable Gates

- L4 不能成为 ClaimCard 或核心 thesis evidence。
- L2/L3 不能替代 L1 财务/披露事实。
- Commercial gaps 不能用公开 proxy 兜底。
- Parser 未完成不能直接写成 bounded gap，必须先记录 parser/source/resolver gap。
- SQL/ObjectStore 是最终审计源，Redis 只做队列、锁和异步状态。
- Milvus 只做 typed semantic recall supplement，不承担 exact-value authority。
- Full-chain pass 必须同时包含 node eval、retrieval audit、evidence/claim/gap/gate trace、memo quality、latency/cost 和 failure/gold lifecycle。
