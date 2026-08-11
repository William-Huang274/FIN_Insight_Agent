# TECH_11：Watchlist / Monitoring / Alert Runtime

日期：2026-07-11

状态：技术合同草案。本文定义长期研究覆盖、增量观测、thesis change、alert/digest 和 review routing；不表示实时数据源、社交平台 adapter、scheduler、notification 或生产监控已实现。

## 1. 为什么需要独立 TECH

Watchlist 不是一次 Deep Research 的附属输出。它具有跨任务长期状态、定时和事件触发、增量数据、去重与抑制、阈值、未触发解释、通知投递和历史 replay，这些对象不能只放进 TECH_01 的单次 research loop 或 TECH_09 的 dashboard projection。

本文件不把 Agentic Search / Agentic Research 从 TECH_01/02 拆走。它只拥有持续监控运行态。

## 2. 核心对象

- `Watchlist`：tenant/project/user scope、coverage target、policy、status 和 owner。
- `CoverageSubscription`：company/industry/product/supply-chain/theme/portfolio-reference、source families、frequency、freshness 和 entitlement。
- `MonitoringRule`：绑定 DecisionSurfaceCell、WhatWouldChange trigger、metric/event condition、materiality、cooldown、suppression 和 review policy。
- `MonitoringCursor`：每个 source/rule 的 last successful observation、watermark、revision 和 failure state。
- `TriggerObservation`：本次新增/修订/删除事件或数值变化及 source/provenance refs。
- `ThesisDeltaAssessment`：changed/unchanged/unknown、affected cells、direction、materiality、confidence 和 required repair。
- `AlertDecision`：alert/no-alert/defer/needs-review/suppressed、原因、policy/rule/version 和 supporting refs。
- `AlertDeduplicationRecord`：event cluster、duplicate key、prior alert、cooldown 和 merge decision。
- `WatchlistDigest`：时间窗内 alerts、unchanged checks、gaps、failed routes 和 next checks。
- `NotificationDelivery`：channel、recipient、content artifact、delivery status、retry、receipt 和 permission snapshot。
- `MonitoringReviewAction`：accept、dismiss、snooze、change rule、reopen cell、start focused/deep research。

## 3. 运行链路

```text
Watchlist / CoverageSubscription
 -> scheduler or event candidate
 -> incremental source observation
 -> EvidenceRequest / ToolGateway / Evidence Gate
 -> TriggerObservation
 -> rule evaluation + bounded semantic materiality assessment
 -> ThesisDeltaAssessment
 -> AlertDecision
 -> dedupe / cooldown / suppression
 -> Workbench review / Digest / NotificationDelivery
 -> optional cell reopen or new ResearchTask
```

Monitoring 不允许把 discovery lead、社交热度、price spike 或未经 promotion 的新闻直接改写成 thesis change。需要 exact fact 的规则仍必须经过 TECH_02/04 gate；语义 materiality 可以由受控 agent 建议，但最终状态由 versioned rule/gate 和必要的人审决定。

## 4. Trigger 与未触发解释

每次 rule evaluation 都必须记录：输入版本、observation window、source success/failure、freshness、condition result、materiality assessment、suppression reason 和 next check。`no_alert` 不是“什么都没发生”的空记录，而是可解释状态：没有新 observation、阈值未达到、证据未晋升、与 thesis 无关、已被重复告警覆盖，或 source route 失败。

Source failure、parser gap 和 commercial gap 必须与 genuine unchanged 分开。系统不得在监控失败时向用户显示“thesis unchanged”。

## 5. 增量研究与升级

- 低影响、结构化、可确定计算的变化可直接形成 update card。
- 相关但语义 materiality 不明确时，生成 bounded domain assessment。
- 命中 What-Would-Change threshold、出现高权威冲突或影响多个 cells 时，reopen 对应 cell 并创建 targeted WorkUnit。
- 需要扩 universe、重建 thesis path 或处理跨 cell 冲突时，创建 Focused Memo / Deep Research task，不在 monitoring worker 内偷偷完成完整研究。
- Monitoring worker 和 presentation/notification worker 均不得绕过 LeadReview 或 writer no-source boundary。

## 6. 社交、新闻和市场信号

Social/PublicStatement、新闻、价格/成交/波动、ownership、credit 和 derivatives 可以触发 observation，但证据身份保持分离：statement attribution、sampled discourse、market context、official fact 和 underlying fact verification 不互相替代。

舆情监控必须保存平台、query、时间窗、样本、去重、覆盖和偏差；只允许输出 observed sample。公众人物发言与 accepted fact 冲突时，生成 conflict alert，不能自动选择人物发言为事实，也不能删除其市场影响信号。

## 7. Durable 与并发边界

TECH_06 持久化 schedule、work unit、cursor、lease、retry、dead-letter、permission snapshot 和 notification delivery；TECH_08 的 snapshot isolation / selective invalidation 适用于并行监控；TECH_07 编译 monitoring/domain/reviewer context。相同 event/rule/version 必须幂等，revision 或 deleted source 需要产生新 observation 和 invalidation，而不是覆盖历史记录。

## 8. 产品边界

- 免费/公开源可以支持日频、披露驱动和 bounded event monitoring，不承诺全市场低延迟实时监控。
- 没有平台授权、稳定 API 或合规抓取路径时，不承诺完整社交平台覆盖。
- 没有商业期权、flow、consensus、CDS 等 entitlement 时，相关 rule 显示 commercial gap，不用低质量 proxy 冒充。
- Portfolio monitoring 只有在另行定义 Position/Exposure/Privacy contract 后才能宣称持仓级功能；当前 Watchlist 不等于 portfolio management。

## 9. 接口 owner

| 接口 | Owner |
| --- | --- |
| Decision cell / What-Would-Change trigger | TECH_01、TECH_05 |
| Source observation / Evidence Gate | TECH_02-04 |
| Durable schedule/cursor/retry/permission | TECH_06 |
| Institutional memory / PIT / dependency index | TECH_03 |
| Context compilation | TECH_07 |
| Parallel assessment handoff | TECH_08 |
| Workbench/digest/artifact/review | TECH_09 |
| alert usefulness、miss/false alert、drift/release eval | TECH_10 |
| Watchlist state、rule、delta、alert、dedupe、delivery semantics | TECH_11 |

## 10. 第一批 fixtures

1. official filing event -> affected cell -> material alert。
2. unchanged rule with successful sources -> explainable no-alert。
3. source failure -> monitoring_unknown，不得写 unchanged。
4. duplicate news cluster -> single alert + dedupe ledger。
5. social statement conflicts with accepted fact -> conflict card，不覆盖事实。
6. What-Would-Change threshold hit -> targeted cell reopen。
7. material multi-cell delta -> escalate Deep Research，而非 monitoring worker 越权。
8. stale/late observation、revision、deleted post 和 cursor replay。
9. permission/license failure -> blocked/commercial gap，不投递泄露内容。
10. notification retry/delivery receipt/idempotency。

## 11. 当前边界

当前项目有 What-Would-Change `MonitoringTrigger`、R57 WatchlistMemory、R55/R59 dashboard projection 和零散 online eval/monitoring 资产，但没有统一 Watchlist state store、MonitoringCursor、AlertDecision、dedupe/suppression、digest/notification runtime。状态为 `documented / contract_draft`。

## 12. 2026-07-12 ResearchCase Refresh / Stale Propagation Contract

TECH_11 是 monitoring observation、rule evaluation、AlertDecision 和 ThesisDeltaAssessment 的业务 writer；它不是 Evidence、Judgment、Case 或 Artifact head writer。

### 12.1 RefreshRequest

当 observation 通过 source/evidence policy 并命中 material rule，TECH_11 生成 `RefreshRequest`：case/old case version、rule/trigger/observation、old evidence/numeric/judgment refs、affected-cell candidates、materiality suggestion、freshness/as-of delta、required source route、budget/urgency、actor/event 和 stop policy。

TECH_01 决定是否 reopen Case/cells，TECH_02-05 执行 evidence/numeric/judgment 更新，TECH_09 评估 artifact/approval stale。Monitoring worker 不得直接写 accepted evidence、推进 JudgmentVersion 或标记 artifact current。

### 12.2 Selective impact and no-change

TECH_03 MemoryDependencyIndex 与 TECH_05 CellDependencyEdge 先做 deterministic affected scope；语义 assessor 只判断 materiality suggestion。输出区分：

- `unrelated_no_action`；
- `related_non_material_record_only`；
- `targeted_refresh_required`；
- `material_multi_cell_research_required`；
- `monitoring_unknown_due_to_source_failure`。

只有成功检查 required sources 且没有 material delta 才能记录 explainable unchanged。Source/parser/permission/commercial failure不能写 thesis unchanged。

### 12.3 Artifact and approval propagation

命中受影响 Judgment/Numeric/SurfaceClaim 时向 TECH_09 发送 `ArtifactInvalidationRequest`，携带 changed refs、affected claims/artifacts、materiality status 和 required revalidation scope。TECH_09 决定 partially/materially stale、reapproval 或 withdrawal；TECH_11 只保留 causation 和 monitoring status。

### 12.4 R4 fixtures

1. Quarterly filing revision只 reopen affected cells，非相关 cells保持 compatible。
2. WWC threshold hit触发 numeric recompute/judgment re-adjudication/artifact reapproval。
3. Source failure返回 monitoring_unknown，不产生 false unchanged。
4. Old/new Case PIT replay可解释观察、refresh、判断和 artifact delta。

本节状态为 `documented / contract_draft`；不表示 R4 longitudinal runtime 已完成。
