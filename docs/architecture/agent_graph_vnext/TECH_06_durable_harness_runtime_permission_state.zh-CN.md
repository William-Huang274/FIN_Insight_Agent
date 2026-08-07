# TECH_06：Durable Harness Runtime / Permission / State

日期：2026-07-09

状态：技术合同草案。本文定义 Agentic Research Harness 的 durable execution、状态持久化、权限、安全、HITL、checkpoint/replay 和 partial rerun。

## 1. 要解决的问题

Agentic research 不能靠一次进程内 graph 调用，也不能靠聊天上下文保留状态。复杂任务必须可 pause、resume、retry、replay、timeout、cancel、human approve，并能解释每一步 tool/subagent/action 为什么发生。

## 2. Harness 不是另一个 agent

Harness 是运行时控制面：

```text
TaskRun
 -> NodeAttempt
 -> ReActStep / ToolInvocation / Observation
 -> EvidenceCandidate / PromotionDecision
 -> Artifact
 -> ReviewAction
```

它不负责投资判断；它负责把判断过程变成可审计、可恢复、可控的状态机。

## 3. 核心状态对象

- `TaskRun`
- `RunEvent / EventEnvelope`
- `WorkUnit`
- `NodeAttempt`
- `ReActStep`
- `ToolInvocation`
- `ModelInvocation`
- `Observation`
- `EvidenceCandidate`
- `PromotionDecision`
- `ArtifactVersion / ArtifactManifest`
- `RepairTicket`
- `ReviewAction`
- `Checkpoint`
- `HumanApprovalEvent`
- `BudgetLedger`
- `PermissionDecision / PermissionSnapshot / CapabilityGrant`
- `QueueLease / CancellationRequest / RetryPolicy`

## 4. Permission / Guardrail

必须有以下 gate：

- `pre_run_gate`：Project OS blockers、scope、budget、provider、permission；
- `pre_tool_gate`：tool allowlist、source role、path/network/credential/sandbox；
- `post_tool_gate`：observation schema、PII/secrets、authority boundary、failure type；
- `promotion_gate`：Evidence / Numeric / Source authority；
- `writer_gate`：writer no-source、DecisionSurfacePack-only；
- `workbench_gate`：cell review、artifact consistency、human approval。

## 5. Durable execution 规则

- 每个 node attempt 必须 idempotent 或有 replay policy。
- 每个 tool invocation 必须有 observation ref 或 typed failure。
- targeted repair 优先于 broad full-chain rerun。
- full-chain rerun 只能作为最后路径。
- HIL approval / rejection 是 append-only event。

## 6. 与其他 TECH 的边界

- `TECH_01` 提供 agentic research loop 和 cell state；
- `TECH_02` 提供 tool registry / evidence tool planner；
- `TECH_07` 提供 context injection 和 compaction policy；
- `TECH_08` 提供 subagent handoff attempt；
- `TECH_09` 消费 trace/provenance；
- `TECH_10` 评估 trajectory 和 execution。

## 7. 第一批 fixture

1. TaskRun / NodeAttempt / ReActStep persistence fixture。
2. Tool permission fail-closed fixture。
3. Checkpoint resume / partial rerun fixture。
4. HIL approval fixture。
5. Budget exhausted / stop condition fixture。

## 8. 验收标准

- 任意 accepted claim 可追到 TaskRun / NodeAttempt / ToolInvocation / Observation。
- 任意 failed tool call 有 failure type 和 next action。
- 权限越界 fail-closed。
- RepairTicket 可局部 replay。
- Workbench 读取 Harness state，而不是零散 projection。

## 9. 2026-07-10 Domain Operator / What-Would-Change Durable State

TECH_06 持久化 TECH_05 的 `DomainOperatorAttemptState` 和 `WhatWouldChangeAttemptState`，但不负责业务判断。必备字段包括 phase、cell/judgment/evidence-pack version、inspected refs、candidate-judgment summary、unresolved conflict refs、repair ticket、counterfactual test、attempt refs、observation refs、budget state、checkpoint 和 stop reason。

Domain operator 在 repair 后必须从 checkpoint 恢复；相同 evidence-pack version 的重复 attempt 应 idempotent 或显式记录 changed input。What-Would-Change search 受独立 budget 和 stop condition 约束，不能以“继续寻找反证”为由无限联网。

新的 accepted evidence 只能产生 `re_adjudication_requested` event，不能直接覆盖已冻结 cell。旧 cell version、What-Would-Change section 和 reviewer action必须可 replay。

## 10. 2026-07-10 FinSightRuntimeFacade API

所有 Workbench、Java backend、CLI、future external API 和 worker 都必须通过统一 `FinSightRuntimeFacade` 操作运行状态，不能各自直接改 LangGraph state、SQL run rows 或 artifact pointer。

第一版 facade operations：

- `create_run(request, actor, policy_context)`
- `admit_run(run_id)`
- `start_run(run_id)`
- `pause_run(run_id, reason)`
- `resume_run(run_id, checkpoint_ref)`
- `cancel_run(run_id, reason)`
- `retry_work_unit(work_unit_id, retry_policy)`
- `repair_work_unit(work_unit_id, changed_input_refs)`
- `replay_run(run_id, replay_policy)`
- `fork_run(run_id, checkpoint_ref, patch_refs)`
- `submit_review(review_request_id, action)`
- `get_run_state(run_id)`
- `list_events(run_id, cursor)`
- `list_artifacts(run_id, status)`

Facade 负责 admission、state transition、version check、permission、budget、queue、event append 和 artifact refs；它不负责业务判断、source promotion、numeric interpretation 或 writer 内容。

## 11. Event Source of Truth / EventEnvelope

执行事实主账本采用 append-only `RunEvent`。SQL current-state table、Workbench status、metrics 和 trace view 都是可重建 projection；LangGraph checkpoint 不是企业审计主账本。

所有事件使用统一 envelope：

```json
{
  "event_id": "...",
  "event_type": "WORK_UNIT_SUCCEEDED",
  "task_run_id": "...",
  "work_unit_id": "...",
  "attempt_id": "...",
  "sequence_no": 42,
  "occurred_at": "...",
  "recorded_at": "...",
  "actor_id": "...",
  "causation_event_id": "...",
  "correlation_id": "...",
  "state_version_before": 5,
  "state_version_after": 6,
  "payload_ref": "...",
  "payload_digest": "...",
  "schema_version": "1.0"
}
```

规则：

- `sequence_no` 在单个 `task_run_id` 内单调递增，不要求全系统全局序列。
- `causation_event_id` 回答“该 retry / repair / rejection / approval 由哪个事件触发”。
- `correlation_id` 聚合同一用户请求、repair chain 或 cross-service trace。
- `occurred_at` 是动作发生时间，`recorded_at` 是 durable ledger 写入时间。
- state-mutating event 必须填写 before/after version；纯观察事件可保持相同 version，但不能伪造状态变化。
- 大 payload 进入 ObjectStore，event 只保存 immutable ref、digest、schema 和必要索引；敏感内容、凭据和 private CoT 不进入 envelope。

建议 event types 至少覆盖：run admission/state、work-unit lifecycle、attempt lifecycle、tool/model invocation、observation、checkpoint、artifact version、permission decision、budget reservation/actual、repair、review、cancel、dead-letter 和 supersession。

## 12. TaskRun / WorkUnit / Attempt 状态机

`TaskRun`：

```text
created -> admitted -> planned -> running
 -> waiting_dependency / waiting_repair / waiting_human / paused
 -> completed / partial_completed / failed / cancelled
```

`WorkUnit` 是 cell/evidence/operator/writer/review 等可独立调度、阻塞和修复的逻辑工作单元：

```text
pending -> ready -> leased -> running
 -> blocked / retry_wait / waiting_human
 -> succeeded / bounded_closed / failed / cancelled / superseded / dead_lettered
```

`Attempt` 是某 worker 对某一 WorkUnit version 的一次执行：

```text
created -> started -> heartbeat_active
 -> succeeded / retryable_failed / non_retryable_failed / timed_out / cancelled / stale_rejected
```

`partial_completed` 与 `bounded_closed` 是正常研究结果，可表示公开源、商业数据或 materiality stop，而不是技术失败。TaskRun state 不能从单个 node 状态直接推断，必须由 dependency / critical-cell / writer-review policy 聚合。

## 13. Retry / Resume / Repair / Replay / Fork

- `retry`：相同 WorkUnit version、相同逻辑输入，处理 transient failure；新建 attempt 并链接 `retries_attempt_id`。
- `resume`：从 checkpoint 继续同一逻辑 WorkUnit version；新 worker lease / attempt 必须记录 `resumes_attempt_id`。
- `repair_rerun`：输入 artifact/evidence/cell version 已变化；生成新的 WorkUnit version 和 attempt，不得冒充 retry。
- `replay`：从历史 events、observations、artifacts 和 checkpoints 重建状态；默认不重新访问外部系统。
- `fork`：从历史 checkpoint 创建新 `task_run_id`，记录 `parent_run_id / parent_checkpoint_id / patch_refs`，用于 scenario、human modification 或明确的新模型运行。

同输入重试不得改变研究语义；需要重新调用 LLM、网页或 API 以获取新结果时，应明确使用 repair / refresh / fork 语义并创建新 observation/version。

## 14. Checkpoint / Artifact Version / Immutability

Checkpoint 分为：

- `graph_checkpoint`：LangGraph node/channel execution state。
- `cell_checkpoint`：cell/evidence/judgment/repair/What-Would-Change version。
- `review_checkpoint`：Lead/Human interrupt 和待审 artifact versions。
- `artifact_checkpoint`：当前 DecisionSurfacePack、Workpaper、memo、PPT/Excel/dashboard refs。

每个 checkpoint 必须记录 `checkpoint_id`、backend、run/work-unit/attempt、state version、input/output artifact refs、code/schema/config refs、created_at 和 `restore_policy`。

所有 durable artifact immutable：

```text
logical_artifact_id
  -> artifact_version_v1
  -> artifact_version_v2 supersedes v1
```

`ArtifactVersion` 至少记录 version id/no、content hash、schema version、producer attempt、input refs、created_at、status、supersedes/superseded_by 和 retention/license classification。Workbench 可以展示 current head，但审计必须能访问历史版。任何“覆盖文件”只能发生在非 durable scratch space；一旦进入 ArtifactManifest 就不得原地修改。

Point 01 将该 generic persistence metadata 定名为 `ArtifactVersionEnvelope`：TECH_06 写 envelope/execution truth，`artifact_type` 指向 payload business owner。DecisionSurface planning payload owner 是 TECH_01；未来 presentation/release payload business semantics 仍归 TECH_09。Envelope persistence 不授予 TECH_06 修改 payload business head 的权限。

## 15. Idempotency / Transaction / Stale-Write Protection

第一版采用 `at-least-once execution + idempotency + optimistic version check`，不声称 exactly-once。

Idempotency key 应绑定 task/work-unit/version、normalized inputs、tool/model、arguments digest、permission snapshot 和 code/config version。相同成功调用默认复用旧 observation；用户明确要求重跑时增加 rerun/fork nonce。

RunEvent、ArtifactVersion ref、budget actual 和 current-state projection 应使用同一 SQL transaction，或通过 transactional outbox 保证最终一致。Worker 持有的 `expected_state_version`、lease token 或 artifact head 已过期时，写入必须返回 `stale_rejected`，不能覆盖新版本。

对存在外部副作用的工具必须有 idempotency/compensation policy；没有该政策时只允许 manual approval，不得自动 retry/replay。

## 16. Queue / Lease / Heartbeat / Cancel / Concurrency

Scheduler 必须支持 priority、dependency、fan-out/fan-in、resource class、tenant/project quota 和 backpressure。Worker 领取 `QueueLease` 后需要定期 heartbeat；lease expiry 只允许重新投递 WorkUnit，不能删除旧 attempt history。

Cancellation 分层：task、work unit、attempt、tool/model invocation。Cancel request 是 durable event；worker 必须 cooperative cancel，并在外部调用无法中止时标记 `cancel_requested_but_external_call_inflight`。已完成 artifact 不因 cancel 删除，只改变 active head / usability status。

并发更新同一 cell 时采用 optimistic concurrency。Primary/contributor/challenger 只能提交 proposal artifact；只有 Cell Adjudicator 可以提交新 adjudicated cell version。旧 evidence-pack version 产生的结果标记 stale，不静默合并。

TECH_06 拥有 runtime `VersionImpactCoordinator`，但不拥有业务材料性判断。它消费 TECH_08 的 `InputDependencyManifest`、`PackChangeSet`、deterministic impact result、Cell Adjudicator/Lead 的 `VersionImpactSuggestion`、WorkUnit version policy、safe checkpoint 和 cancellation state，生成 append-only `WorkUnitVersionDecision`，再执行 `continue / continue_then_validate / rebase_at_checkpoint / cancel_and_supersede`。任何 agent、artifact owner 或 LLM suggestion 都不能绕过 coordinator 直接改变运行中 WorkUnit 状态。

需要 rebase 时，coordinator 生成 versioned `ContextRebaseRequirement` 和新 WorkUnit version，保留 causation、旧/新 input heads、retained/invalidated dependency refs、required re-analysis scope 和 prior attempt usability，再交 TECH_07 编译新的 ContextInjectionPlan。运行中 attempt 不允许热替换 input；hard invalidation 时外部调用结果即使随后返回，也必须隔离为 stale observation。

`WorkUnitExecutionView` 必须分别投影 execution state、input currency 和 output usability，不能用一个 overloaded `running/stale` 字段代替。RuntimeFacade 至少提供 `get_work_unit_execution_view`、`validate_execution_view` 和 `apply_version_control_directive`；worker 在 start、safe checkpoint、下一次 model/tool action、resume 和 result commit 前校验 expected versions / last-seen event sequence。`ARTIFACT_HEAD_ADVANCED` 先把受影响 WorkUnit 标为 `head_advanced_unassessed`，判定完成后再迁移到 compatible、pending validation、rebase required 或 hard invalid。

正在执行且无法安全中止的 atomic call 可以结束，但在 unassessed/hard-invalid 状态下不得开启后续决策或提交 current output。所有返回先绑定原 attempt/base version；coordinator 根据 `WorkUnitVersionDecision` 把它标为 compatible proposal、pending validation 或 stale quarantine。Cost/remaining runtime 可以影响何时 checkpoint，但不能使 hard invalid input 继续晋升。

TECH_09 presentation pipeline 在 TECH_06 中物化为 `WriterWorkUnit`、`RenderWorkUnit`、`VerificationWorkUnit`、`HumanReviewWorkUnit` 和 `ReleaseTransaction`。TECH_06 持久化 candidate/frozen/rendered/reviewed/released/published/stale/superseded/withdrawn events、immutable artifact versions、artifact/content hashes、approval bindings、delivery receipts 和 withdrawal reason；TECH_09 定义这些状态的业务含义，R55 只执行 render work。

ReleaseTransaction 必须以 expected artifact/version/hash、verification bundle、approval version、permission snapshot 和 release policy 做 optimistic transaction check。审核 hash、release candidate hash 或实际 delivery hash 不一致时默认 fail-closed；metadata-only exception 也必须引用已批准 policy 和 content digest proof，不能由 delivery adapter 自行放行。

## 17. CapabilityGrant / PermissionDecision / PermissionSnapshot

实际有效权限是以下交集：

```text
ActorCapability
 ∩ TaskScope
 ∩ ToolCapability
 ∩ DataClassification
 ∩ SourceLicense
 ∩ UserEntitlement
 ∩ CurrentPhase
```

`CapabilityGrant` 必须绑定 actor、tool/source role、entity/cell scope、network/path/data scope、expiry、budget 和 approval ref。MCP server 暴露工具不代表 actor 获得权限；所有调用仍必须经过 ToolGateway。

每个 `ToolInvocation` / `ModelInvocation` 必须引用调用当时的 immutable `PermissionSnapshot`，至少记录 policy/grant/entitlement versions 或 digest、subject/actor、resource/tool、requested scope、effective scope、decision、reason、decided_at、expiry 和 approval ref。Snapshot 不保存 API key、token 或凭据内容，只保存 secret reference category 或 credential alias。

历史 replay 展示当时 permission snapshot，不用当前 policy 重新解释旧调用；任何新的实际 invocation 必须按当前 policy 重新授权。Policy 更新不能改写历史 allow/deny event。

## 18. Budget Ledger / Stop Behavior

预算层级：`TaskRun -> WorkUnit/cell -> operator -> tool/model attempt`。预算维度至少包括 model tokens/cost、tool calls、SourceHunter depth、wall time、concurrency、artifact/context bytes、retry count、rate limit 和 commercial entitlement。

BudgetLedger 使用 reservation / actual / release entries，避免并发 worker 同时超额。预算耗尽生成 `BUDGET_EXHAUSTED` event 和 typed stop；系统可以产出 `partial_completed / bounded_closed`，但 Writer 不得把未闭环范围写成完整结论。

预算扩容必须是新的 Permission/HumanApproval event；不能由 agent 自行提高。AIE 将成本追到 accepted evidence、new judgment、conflict、repair ticket、adjudication change 和 final artifact。

## 19. Durable HITL / Approval Invalidation

`HumanReviewRequest` 至少包含 review type、target refs/versions、reason、allowed actions、required approver role、created/expiry time、blocking policy 和 return schema。

`HumanApprovalEvent` 是 TECH_09 `DecisionAttestation` 的 runtime receipt / execution fact，append-only 并绑定具体 state/artifact/evidence/cell versions；它不独立定义“批准了什么”的业务语义。被审批对象发生 material version change 时，runtime projection 将 approval 标为 `stale_approval` 并请求 TECH_09 重新 attestate；不得沿用“批准过一次”的宽泛授权。

HITL 重点用于高影响冲突、商业源/权限升级、私有材料、对外发布、assumption-heavy valuation、quant progression、dead-letter inspection 和 reviewer-sensitive wording，不应让所有普通 cell 都等待人工。

## 20. SQL / ObjectStore / LangGraph / Queue Boundary

- SQL Run/Event Ledger：authoritative execution history、current projection、versions、permission/budget/review metadata。
- ObjectStore：large observations、documents、evidence payloads、model outputs、checkpoint payloads 和 immutable artifacts；SQL 保存 refs/hash/schema。
- LangGraph：Python research graph、interrupt 和 graph-local checkpoint；不是跨入口主账本。
- Queue/Redis：调度、lease、heartbeat、rate/backpressure；不是 durable research truth。
- ToolGateway/MCP adapters：typed executable interface；不拥有 actor permission 或 evidence promotion。
- Secret manager/environment：凭据；任何 checkpoint/event/artifact 不保存明文 secret。

当前先采用 RuntimeFacade + SQL ledger + ObjectStore + LangGraph + queue 的组合。Temporal-style durable workflow 保持 optional escalation：只有在长时间多租户、跨服务事务、多 worker crash recovery 超出现有边界时再评估，不作为 TECH_06 第一版前置依赖。

## 21. Deterministic Replay Boundary

Replay 必须默认 side-effect free，并按下表执行：

| Operation | Replay policy |
| --- | --- |
| SQL current-state / Workbench projection | 可从 events 重建；记录 projection code/schema version |
| 纯函数 numeric / graph / selector | 同代码、schema、config、inputs 下可重算；版本变化时产生新 replay/fork artifact |
| artifact rendering | 固定 renderer/template/font/input versions 时可重算；否则生成新 artifact version |
| LLM invocation | 默认复用历史 observation/output；重新调用必须显式 fork/repair |
| web / external API / market source | 默认复用 snapshot/observation；重新调用是 refresh/repair，不是 replay |
| external write / publish / trade-like action | 禁止自动 replay；需要显式 permission/HITL 和 idempotency/compensation policy |

Replay report 必须区分 `reconstructed`、`recomputed_deterministically`、`reused_observation`、`skipped_external_side_effect` 和 `version_changed_new_artifact`。

## 22. Dead-Letter / Poison WorkUnit

WorkUnit 在以下情况进入 `dead_lettered`：超过 `max_attempts`、同一 deterministic contract error 重复、non-retryable permission/schema/data corruption、poison payload、无法满足的 dependency cycle，或管理员定义的 hard stop。

Dead-letter event 必须记录 last failure、attempt chain、input/version、retry decisions、permission/budget state、artifact refs、recommended inspection owner 和 recovery options。它不会被 scheduler 自动重新投递。

Human/admin 可以选择 `discard_as_bounded_gap`、`repair_and_requeue_new_version`、`fork_from_checkpoint`、`mark_external_blocked` 或 `cancel_dependents`。恢复必须产生新 event/work-unit version，并保留原 poison attempt；不得原地把 dead-letter 改成 succeeded。

## 23. 扩展 Fixtures / 验收标准

新增 deterministic fixtures：

1. RuntimeFacade 多入口 create/resume/cancel/get-state parity。
2. EventEnvelope sequence/causation/correlation/state-version integrity。
3. TaskRun / WorkUnit / Attempt legal transition 与 illegal-transition fail-closed。
4. retry/resume/repair/replay/fork identity preservation。
5. checkpoint hydration 与 targeted cell/What-Would-Change resume。
6. artifact immutability、supersession 和 Workbench current-head projection。
7. idempotency duplicate suppression、transactional outbox 和 stale-write rejection。
8. queue lease expiry、heartbeat、worker crash、cancel propagation 和 concurrency conflict。
9. CapabilityGrant / PermissionSnapshot historical explainability，policy change 不改写历史。
10. hierarchical budget reservation/actual/stop 与 bounded partial output。
11. HITL version binding、approval expiry/staleness 和 reapproval。
12. deterministic replay external-call suppression。
13. max-attempt poison WorkUnit -> dead-letter -> human repair/requeue。
14. SQL/ObjectStore/LangGraph/queue refs 可相互追溯且无明文 credential。

扩展通过标准：所有外部调用均有 immutable attempt、permission、budget、observation 和 causation refs；任何恢复/重放都能说明哪些内容被重建、重算、复用或跳过；任何 artifact、approval 或 cell conclusion 的新版本都不得覆盖历史。

## 24. 当前实现边界

项目已有 LangGraph/node checkpoint artifacts、run audit store、WorkpaperEvent、P12 durable/HIL/resource-router fixture 和部分 permission/queue 基座，但尚未统一实现本节的 RuntimeFacade、EventEnvelope、WorkUnit state machine、PermissionSnapshot、immutable ArtifactVersion、dead-letter、deterministic replay policy 或 DecisionSurface targeted resume。

因此本节状态为 `documented / contract_draft`。现有 fixture 只能证明局部 runtime-alignment，不证明生产级多租户 durable execution；不得据此运行 broad full-chain 或声称 crash-safe agent runtime 已完成。

## 25. 2026-07-11 Eval Execution Boundary

TECH_10 定义 EvalRun/EvaluatorRun 的质量语义，TECH_06 只为需要 durable model/tool/replay/shadow execution 的 eval 提供 `EvalWorkUnit`、checkpoint、repetition、timeout/cancel、budget、permission 和 artifact persistence。`EvalWorkUnit` 必须引用 EvalRunManifest/Subject/EvaluatorDefinition，不能让 evaluator 修改被评 run 或 research truth。

Schema/static/unit/deterministic CI evaluator 不强制包装为 WorkUnit；它可以由 CI/Test Runner 执行，并以 hashed result envelope、code/test/config refs 回写 TECH_10/R60 Quality Ledger。TECH_06 不成为所有单元测试的调度器。

Eval execution event 与 Quality Ledger result 分开：TECH_06 RunEvent 是“评测如何执行”的事实源，TECH_10 EvalMetricResult/FailureAttribution/RuntimeReleaseGateDecision 是“评测得出什么”的事实源。两者通过 eval_run/work_unit/evaluator/subject/correlation refs 关联，不复制或覆盖。

## 26. 2026-07-11 Agent / Prompt / Model Runtime Registry

每次 agent/model 调用必须引用不可变的 `AgentDefinitionVersion`、`PromptBundleVersion`、`ModelCapabilityProfile` 和 `ModelSelectionDecision`。其中 Agent/Prompt 的 role、input/output、tools、handoff 和 forbidden actions 由 TECH_08 定义；TECH_06 记录 provider/model/version、structured-output/tool-use/context capability、privacy/data-residency、permission/entitlement、cost/latency class、fallback chain、selection reason 和 effective runtime config。

Fallback 不能只按“模型失败就换一个”处理。结构化输出、tool calling、language、context、data policy 或 domain rubric 不兼容时必须重新编译 ContextInjectionPlan 或阻断；模型切换产生新 attempt 和 selection decision。TECH_10 把 exact agent/prompt/model/config bundle 绑定为 candidate/baseline，禁止无法复现的动态模型漂移进入 release claim。

## 27. 2026-07-12 ResearchCase Execution Binding / Human-AI Accountability

根据 TECH_00 Owner Constitution，TECH_06 不拥有 `InstitutionalResearchCase` 的研究业务语义；它拥有 Case command 的 admission、TaskRun/WorkUnit 执行、append-only event、identity/permission snapshot 和 current-state projection。

### 27.1 ResearchCaseExecutionBinding

`ResearchCaseExecutionBinding` 至少记录 case/version、task run、work-unit set、business command/event type、expected business head、runtime state version、policy/config refs、actor snapshot、idempotency key 和 projection cursor。

规则：

- 一个 Case 可有多个 initial/follow-up/refresh/repair/render/review TaskRuns；
- TaskRun completion 不自动推进 Case 业务状态，必须由 TECH_01/02/04/05/09/11 对应 owner command 决定；
- runtime 只执行经过 permission/version/idempotency 检查的 command，不由 scheduler 推断业务 accepted；
- replay 可以重建 Case execution projection，但不能重新裁决 evidence、judgment 或 approval。

### 27.2 ActorSnapshot

所有 material command、tool/model invocation、human edit、review、approval 和 release 必须引用 immutable `ActorSnapshot`：

- `actor_id / actor_type`：human、agent、subagent、tool、service account、external system；
- tenant、department/team、role、authority scope、delegation/acting-on-behalf-of；
- SSO/session/workflow identity refs；
- agent/model/prompt/skill/config versions；
- effective PermissionSnapshot、data/source entitlement 和 expiry；
- captured_at、identity provider、snapshot digest。

历史角色变化不得改写旧 snapshot。Snapshot 不保存 token、password、private key 或 credential payload。

### 27.3 AccountabilityEvent

`AccountabilityEvent` 复用 EventEnvelope，不新建平行日志。除现有 run/work-unit/attempt 字段外，material event 增加 case/cell/claim/evidence/numeric/artifact refs、actor_snapshot_ref、action category、before/after version/hash、AI involvement mode、human edit type、workflow/OA ref、retention class 和 disclosure class。

必须覆盖 PromptSubmitted、Agent/SkillActivated、ToolInvoked、EvidencePromoted/Rejected、NumericProgramExecuted、JudgmentModified、RepairRequested、ReviewDecisionRecorded、ApprovalAttested、ArtifactReleased/Published/Withdrawn。

Private CoT 不进入审计 payload；可保存用户 prompt/response 的 hash、redacted/encrypted payload ref 和 retention policy。Raw sensitive payload 是否保存由 tenant policy 决定，credential 永久禁止记录。

### 27.4 Enterprise identity / OA hooks

第一阶段定义 provider-neutral interfaces：

- OIDC/SAML identity assertion adapter；
- SCIM user/group/role/deactivation sync；
- delegated authority / org reporting-line resolver；
- `ExternalApprovalWorkflowBinding`：FIN ReviewRequest 与 OA workflow/node/callback 的双向绑定；
- legal hold、retention、deletion approval 和 eDiscovery export hooks。

外部 OA callback 只能提交 candidate decision；RuntimeFacade 必须校验 workflow、ActorSnapshot、target exact version/hash、authority 和 replay/idempotency 后，调用 TECH_09 的 DecisionAttestation command。聊天/邮件/Teams/Slack 通知本身不构成批准。

### 27.5 Permission and configuration rollout

Agent/Skill/Graph/Workflow/Provider policy 采用 immutable version。TECH_06 执行：

```text
draft -> sandbox_eval -> approved -> staged_rollout -> active
 -> superseded / rolled_back / revoked
```

TECH_08 定义 Agent/Skill/coordination 语义，TECH_10 决定 eval/release gate。TECH_06 不允许普通 tenant config 关闭 provenance、Evidence/Numeric hard gate、writer no-source、secret redaction、exact-version approval 或 audit event。

### 27.6 Accountability fixtures

1. 同一 human 在角色变更前后的动作保留不同 ActorSnapshot。
2. delegated approver 只能批准授权 scope 内的 exact version/hash。
3. OA callback 重放幂等，target version 已变化时 fail-closed。
4. Agent 提议和 human 修改分别可追到 Cell/Claim before/after version。
5. retention 删除 raw payload 后保留最小审计 tombstone/hash，但不能继续注入内容。
6. usage analytics 与 compliance audit 权限隔离，普通 manager 不因绩效目的读取 raw prompt。

本节状态为 `documented / contract_draft`，不表示 OIDC/SCIM/OA 或责任链 runtime 已实现。

## 28. FIN 0.1.3 S0-04G：Typed Blocker State 与 Versioned RunScopeRegistry 最小合同（2026-08-08）

### 28.1 触发原因

RC-P36-156 已证明，当前 Project OS 以自由文本表示 blocker state 和 run scope：描述性 `open_*` 状态曾被 liveness 过滤跳过，未注册 scope 又可能在匹配前 fail-open。后续通过 canonical `open`＋`*` block＋单项 allowlist 临时缓解，但 S1-08 每推进一个 proof/decision 都要追加投影，治理本身已成为交付瓶颈并进入真实 live 权限路径。

### 28.2 最小实现，不做平台重写

S0-04G 只允许交付以下共享能力：

- `BlockerState`：至少区分 `open / mitigated_open / blocked_external / closed / superseded`，每个状态明确是否 live；未知状态 fail-closed；
- `RunScopeRegistryVersion`：canonical scope ID、owner stage、operation class（zero-call／network／model／admission／release）、父子关系、版本和 supersession；
- `ScopePolicy`：block/allow 只能引用已注册 scope；未知 scope、版本漂移和 owner mismatch 全部 fail-closed；
- ledger projection checker：同一 issue 的最新投影必须保持 append-only lineage，关闭/替代状态需引用前一记录；
- preflight output：同时输出 canonical scope ID、registry version、匹配 blocker IDs 与拒绝原因，compact view 不能成为 core truth；
- mutation：未知 state、未知 scope、描述性别名、wildcard/child、superseded registry、CLI/core shape drift、跨阶段 owner、closed issue replay。

本包不重构 admission ledger、SourceHunter、模型合同、release workflow 或全部历史 issue；历史自由字符串通过只读 compatibility mapping 投影，不能回写改造旧失败证据。

### 28.3 验收与后续权限

S0-04G 需要零网络、零模型、零 Provider、零正式 admission；在当前仓库和 fresh process 中证明：已注册的 P2D 零调用 scope可通过，DELL R3 issuance/live、ranking、MU/NVDA、S3 与 release 在未投影时均被明确拒绝；未知 state/scope 必须稳定 fail-closed。通过后 RC-P36-156 可关闭或降为 historical mitigation，P2D 才成为下一项。

以后只在权限、成本、外部副作用或产品阶段真正变化时单独做 authority decision。普通 deterministic implementation＋clean proof 不再机械拆成多轮人工 allowlist projection。
