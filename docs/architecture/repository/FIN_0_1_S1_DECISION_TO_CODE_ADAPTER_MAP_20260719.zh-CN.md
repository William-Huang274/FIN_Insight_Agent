# FIN 0.1 S1 决策到代码 Adapter Map

日期：2026-07-19
Slice：`S1_one_cell_mainline_cut_through`
任务：`S1-T01`
状态：`accepted_after_independent_review_repair / no_runtime_implementation_claim`
机器清单：`configs/releases/fin_ia_0_1_s1_adapter_map_v1_1.json`
被替换清单：`configs/releases/fin_ia_0_1_s1_adapter_map_v1_0.json`（独立复核提出 changes requested 后仅保留 supersession pointer）

## 1. 本轮结论

S1-T01 已把 D02-D14 决策映射到当前仓库的真实 producer、consumer、store 和 UI 路径，并冻结以下唯一产品执行主线：

```text
当前 ActivityTrace / T05 后 Workbench Next run action
  -> ExecutionApiClient.createWorkUnit
  -> POST /api/v1/cases/{case_id}/work-units
  -> ExecutionService admission + RuntimeFacade.create_work_unit
  -> HTTP 202（只表示 pending enqueue，不在请求线程执行 profile）
  -> existing DurableSchedulerService.claim_next
  -> RuntimeFacade.claim_next_scheduled_attempt（创建唯一 running Attempt）
  -> Fin01ResearchRuntime.execute_claimed_attempt
  -> exact ExecutionProfileVersion private adapter -> typed ProfileExecutionResult
  -> Fin01ResearchRuntime validation + existing RuntimeFacade commit
  -> immutable FileCanonicalObjectStore object + SQLite canonical envelope/head transaction
  -> ResearchRunVersion + EventEnvelope + ArtifactVersionEnvelope exact lineage
  -> run-scoped API v1 read projections
  -> Workbench Next
```

`Fin01ResearchRuntime` 的目标位置冻结为 `apps/workbench/backend/application/research_runtime.py`。`ExecutionService` 只负责 API 准入和入队；existing `DurableSchedulerService` 负责 claim control plane；`Fin01ResearchRuntime` 只执行已 claim 的 exact Attempt。`apps/workbench/backend/app.py` 是唯一 composition root，把 existing `RuntimeFacade`、scheduler、object store、local deterministic service 和 historical shadow dependencies 注入同一个 Runtime。它不是第二个 canonical runtime、scheduler、worker、store 或业务 authority。S1 的 `deterministic_fallback` 和 `agent_fixture_shadow` adapter 首版都作为该模块内部实现存在，不新建 adapter package family。

本轮没有创建该 Python 模块、没有修改运行时、没有执行 Case，也没有调用模型、provider、网络、商业数据或付费服务。独立复核首轮给出 `changes_requested_before_acceptance`；完成时序、lineage、composition、UI 和 owner 修订后二次复核 disposition 为 `pass_after_independent_review_repair_no_implementation_claim`。T02/T03 未执行。

## 2. 真实代码取证

### 2.1 当前写入和读取关系

- `apps/workbench/backend/app.py` 在同一 FastAPI host 中装配 Case、Planning、Execution、Evidence、Local Research、Human Baseline、Integrity 和 Deliverable 的 `/api/v1` routers；它同时保留旧 Workbench/R53-R60 compatibility routes。
- 当前实际执行命令来自 `ActivityTrace.tsx -> ExecutionApiClient.createWorkUnit -> POST /api/v1/cases/{case_id}/work-units -> ExecutionService.create_work_unit -> RuntimeFacade.create_work_unit`。
- `WorkbenchNext.tsx` 当前主要并行读取 Case、DecisionSurface、Activity、local research、local analysis、Evidence、Numeric、Workpaper、Deliverable、Trace 和 Human Baseline，再在前端合成“run events”；它没有消费 exact execution profile 或 ResearchRun。
- `P36LocalResearchService` 明确返回 `bounded_local_read_only / bounded_local_deterministic_preview`，并声明 `model_calls=0`、`network_calls=0`、`external_tool_calls=0`、`canonical_store_writes=0`。它是只读 preview producer，不是 Run authority。
- Case、Planning 和 WorkUnit 当前经 `RuntimeFacade` 写现有 canonical store；Evidence、Numeric、Workpaper、Deliverable 和 Trace application services也写同一个 `SQLiteCanonicalStore` 的版本表和 `canonical_events`。仓库目前没有 `ResearchRunVersion`，因此这些对象尚未统一绑定一个 exact profile/run identity。
- `src/sec_agent/langgraph_orchestrator.py` 只在当前 FastAPI 的旧 native checkpoint inspect/resume compatibility route 被引用；当前 `/api/v1` 和 Workbench Next 没有消费历史 Agent graph。
- `agent_registry.py`、`research_skills.py`、`research_lead_llm.py`、`specialist_llm.py`、`memo_llm.py`、`tool_controller.py` 和 `relationship_graph.py` 没有被当前产品 API v1 导入；它们主要由历史 runner、eval 和 tests 消费。
- `HumanBaselineService` 继续写独立 `.codex_runtime/internal-alpha/human-baseline.sqlite3`。这是刻意隔离的内部测量边界，不是 canonical Case 或 release evidence writer。

### 2.2 HTTP 202 到 Runtime 的真实异步时序

现有 `POST /work-units` 只创建 `pending` WorkUnit，不能被解释为 profile 已运行。S1 冻结的阶段合同为：

1. `ExecutionService` 校验 permission、actor、Case version、accepted DecisionSurface、input digest 和幂等键；
2. `RuntimeFacade.create_work_unit` 只落 pending WorkUnit，API 返回 HTTP 202；
3. existing `DurableSchedulerService.claim_next` 调用 `RuntimeFacade.claim_next_scheduled_attempt`，原子创建唯一 running Attempt、lease 和 fencing token；
4. enqueue 成功后，execution API route 注册一个 FastAPI `BackgroundTask` 调用 `ExecutionService.dispatch_queued_work_unit`；该方法只委托 `Fin01ResearchRuntime.dispatch_once`，后者必须先经 existing scheduler claim exact WorkUnit，再执行 `execute_claimed_attempt`。profile 不得在 HTTP 202 response 之前运行，router 也不得直接选择 profile；
5. private profile adapter 只返回 typed `ProfileExecutionResult`，不得写 canonical store；
6. Runtime 验证结果后，经 existing `RuntimeFacade` 创建/更新 Run、Event、Artifact、Attempt 和 WorkUnit terminal state；失败必须走 `fail_attempt` 或 typed stop，不能被 fallback 输出覆盖；
7. API read projection 按 exact Run 返回状态和 artifact；Workbench 不用本地 preview 猜测 Agent 成功。

如果进程在 claim 或执行前停止，durable WorkUnit 保持 pending；如果 lease 后停止，则保持可按 existing fencing/reclaim 规则恢复的真实状态。不得写伪成功；后续只允许显式 dispatch/reclaim，不以新建第二 worker 修补。

### 2.3 ResearchRun / WorkUnit / Attempt / Event / Artifact lineage

`ResearchRunVersion` 在 existing `SQLiteCanonicalStore` 内新增对象，不新增 store family。首版最小字段冻结为 `research_run_id`、`research_run_version_id/version`、`case_id`、`work_unit_id`、`attempt_id`、`execution_profile_version_ref`、`parent_research_run_id`、`input_refs/digest`、state、start/end 和 terminal reason。

- 一个 WorkUnit 可因 retry 拥有一至多个 Attempt；
- 一个 Attempt 必须且只能拥有一个 ResearchRun identity；一个 ResearchRun 绑定且只绑定一个 WorkUnit 和一个 Attempt；
- `EventEnvelope.task_run_id == research_run_id`，并同时保留 exact `work_unit_id` 和 `attempt_id`；
- `ArtifactVersionEnvelope.producer_attempt_id == ResearchRun.attempt_id`，`input_refs` 必须含 `research_run_version_id` 与 exact business inputs，Attempt `output_refs` 必须列出全部 committed artifact versions；
- Agent 失败后显式 deterministic fallback 必须调用 existing `RuntimeFacade.fork_recovery_work_unit` 创建 child WorkUnit lineage，再创建 child Attempt、child ResearchRun 和不同 profile version；不得复用失败 Run；
- object payload 先写 immutable `FileCanonicalObjectStore`，再在 SQLite transaction 提交 envelope/event/head。这里不声称跨文件系统与 SQLite 的 distributed transaction；未被 envelope 引用的 orphan object 不是 canonical head，可由后续 reconciliation/GC 处理。

### 2.4 UI 过渡边界与 composition root

- 当前写入口仍是 legacy-compatible `ActivityTrace -> ExecutionApiClient.createWorkUnit`；
- Workbench Next 当前 run composer 明确 disabled，只是 aggregate/read projection；
- S1-T05 才把 Workbench Next run action 接到同一个 `ExecutionApiClient` command，不允许另开 mutation endpoint；
- `apps/workbench/backend/app.py` 必须构造并注入唯一 `Fin01ResearchRuntime`，不得让 `ExecutionService`、profile adapter 或 router 私自 new 第二套 facade/store/scheduler。

### 2.5 当前最早 owned blocker

`RC-P38-042-dual-agent-runtime-mainline-disconnection` 与代码取证一致：当前 deterministic Workbench、历史 LangGraph/Skill/Tool/Graph、standalone DeepSeek runner 分属三条不完整执行面。S1-T01 不通过删除历史资产或新建第四条路径解决，而是冻结一个 adapter，把前两种 S1 profile 收进同一个 `Fin01ResearchRuntime`；standalone runner 只保留 release reproducibility 身份，未来如需真实模型必须经单独授权后再接入同一 Runtime。

## 3. 唯一写入权与 read projection

| 对象/动作 | 唯一 owner | S1 adapter 规则 | 当前/目标 store |
| --- | --- | --- | --- |
| accepted Case / DecisionSurface | `CaseService` / `PlanningService` + existing `RuntimeFacade` | profile adapter 不得修改 | existing canonical tables |
| Run admission/enqueue | `ExecutionService -> RuntimeFacade.create_work_unit` | HTTP 202 只确认 pending enqueue；API request thread 不执行 profile | existing canonical WorkUnit table |
| Attempt claim/lease | existing `DurableSchedulerService -> RuntimeFacade.claim_next_scheduled_attempt` | 只有 claim 后的 exact running Attempt 可被 Runtime 执行 | existing canonical Attempt/WorkUnit tables |
| profile execution | private deterministic or historical shadow adapter | 只返回 typed `ProfileExecutionResult`，直接 canonical business write=`0` | no adapter-owned store |
| Run execution/terminal truth | `Fin01ResearchRuntime` | 只执行 claimed Attempt；失败走 fail/typed stop；fallback 必须 child WorkUnit/Attempt/Run | existing RuntimeFacade authority |
| Run/Event/Artifact commit | `Fin01ResearchRuntime -> RuntimeFacade` | object immutable write 后提交 SQLite envelope/event/head transaction；不声称 distributed transaction | existing `SQLiteCanonicalStore` + `FileCanonicalObjectStore` |
| Evidence promotion | existing Evidence Gate family | Agent/Lead/Writer 都不得写 promotion head | existing canonical store |
| Workpaper/Report/Trace projection | existing Integrity/Deliverable services, refactor为 run-scoped read projection | 不创建新的 Writer 或 presentation truth head | existing canonical store/object store |
| Human Baseline | `HumanBaselineService` | S1 继续隔离；不得自动 import 或升级为 R3 | separate local SQLite |
| Workbench write/read | 当前 ActivityTrace write；T05 后 Workbench Next write；API v1 run-scoped reads | 两个 UI 阶段复用同一 ExecutionApiClient command；local preview 不能成为 Run authority | command + read-only projection |

关键约束：所有 profile adapter 都必须是 canonical write-pure。即使历史 LangGraph 内部产生 checkpoint 或旧 artifact，它们也只能作为 adapter observation 输入；进入产品的 Run/Event/Artifact 必须由 `Fin01ResearchRuntime` 统一验证和提交。

## 4. D02-D14 适配冻结

下表是人工可读摘要；每项完整的 producer/consumer、逐资产 disposition、合同、依赖、最小测试、风险与非目标以机器清单为准。

| 决策 | 现有 producer / consumer | retain / refactor / absorb / retire | 目标模块与输入输出合同 | 唯一 owner | 依赖与最小测试 | 风险与非目标 |
| --- | --- | --- | --- | --- | --- | --- |
| `D02` DecisionSurface authority | producer：`PlanningService`、`RuntimeFacade`；consumer：`ExecutionService`、DecisionSurface UI、Workbench Next | retain accepted surface models/PlanningService；refactor facade 增加 run overlay/revision linkage | `models.py`、`facade.py`、`planning_service.py`、planned `research_runtime.py`；`AcceptedDecisionSurfaceVersion + ResearchRun -> RunDecisionOverlayVersion / RevisionProposal` | accepted surface=`PlanningService`；run overlay=`Fin01ResearchRuntime` | D12 profile；测试普通重排只改 overlay、重大变更不可原地改 surface、接受 revision 后创建 child Run | 防止 overlay 变第二 planning authority；S1 不开放顶层 Cell 自主生成或真实 Case mutation |
| `D03` Agent topology/handoff | producer：Agent Registry、LangGraph；current product consumer=`0` | retain 17 role/permission contracts；absorb historical graph；refactor fixed order/free-text state；retire top-level graph product entry after parity | `research_runtime.py` + existing orchestrator/registry；`SpecialistTaskVersion -> SpecialistResult/JudgmentProposal/EvidenceRequest/Repair/TypedStop` | `Fin01ResearchRuntime` | D02/D04/D09；测试 one-cell Lead+primary Specialist、exact refs、无 specialist 私下互调 | 防止把固定 17-node 顺序伪装动态；不迁移全图、不调用模型 |
| `D04` Skill runtime | producer：`research_skills.py`、Agent Registry；consumer：历史 Lead/Specialist/Writer LLM，current product=`0` | retain Skill 内容；refactor existing registry 增加 version/digest/precondition/schema；retire parallel FIN registry | existing `research_skills.py` / `agent_registry.py` + runtime resolver；`Agent+Cell+Profile -> SkillDefinitionVersion / SkillPackVersion / events` | existing Skill Registry resolved by Runtime | D03/D09；测试 exact digest、profile deny、optional skill selected/skipped | Markdown 存在不等于消费；Skill 不授予 Tool/network/预算；不新建 registry family |
| `D05` Agentic Search | producer：fixed P36 queries + existing EvidenceRequest/ToolPlanner/CandidateBundle；consumer：EvidenceService/UI | retain canonical compilers；absorb fixed queries as deterministic adapter；refactor ToolController, S1 不执行 | `research_runtime.py`、EvidenceService、existing canonical search modules；`EvidenceRequest -> SearchPlan/CandidateBundle/EvidenceResponse/typed stop` | `EvidenceService` + Tool Planner preflight | D02/D12；测试 Numeric 走 SQL/parser、unauthorized fail closed、Candidate 不绕 D07 | fixed query 不得称 Agentic；S1 不做 network SourceHunter、商业数据或真实 adaptive search |
| `D06` Graph authority | producer：Research Graph Store、relationship lookup、fixed P36 graph SQL；consumer：deterministic preview/historical graph | retain data；absorb existing `relationship_graph.py` 为 bounded tool；明确 refactor `EvidenceService` 为唯一 GraphQuery route owner；refactor fixed SQL truth label；retire new graph abstraction | `evidence_service.py` + relationship graph + existing Tool Planner + runtime；`GraphQueryRequest -> GraphCandidateBundle/GraphPath/follow-up request` | `EvidenceService` | D05/D07；测试 graph events、naked edge 不进 Judgment、Graph 不造数值 | 图数据使用不等于 Agentic Graph；S1 不改 canonical graph、不跑 network second hop |
| `D07` Evidence promotion | producer：EvidenceService、IntegrityService、FixtureEvidenceGate；consumer：fixture Numeric/Workpaper/Evidence UI | retain唯一 Evidence Gate；refactor projections为 exact Run；retain deterministic parser/numeric as traced service | existing evidence gate/service/integrity modules；`CandidateBundle+claim scope+policy -> EvidenceRecord/CounterevidenceAssessment/classification` | existing Evidence Gate family | D05/parser lineage；测试 Candidate 不绕 Gate、反证可见、context 不支撑 exact fact | 当前 31 rows 仍是 Candidate；D07-B human calibration 非 S1 目标 |
| `D08` Specialist Judgment | producer：deterministic local judgment、Integrity Workpaper、historical Specialist/Aggregator；consumer：current fallback report/historical writer | absorb historical Specialist normalization；retain deterministic judgment only as fallback；refactor aggregation为 Specialist artifact + Lead synthesis | runtime + `specialist_llm.py` + canonical artifact envelope + Integrity projection；`accepted Evidence/Numeric+Task+Context -> SpecialistJudgment/LeadSynthesis` | Specialist owns Cell artifact；Lead owns cross-cell synthesis under Runtime | D03/D07/D09；测试 structured one-cell Judgment、Numeric 冲突不被文字覆盖、exact Run binding | 防止 deterministic judgment 显示成 Agent；S1-T01 不做三-cell synthesis 或质量声明 |
| `D09` Context/Memory | producer：existing `ContextEngine`、historical runtime prompt builders；current product consumer=`0` | absorb existing ContextEngine；refactor exact Run/Cell/permission/Skill refs；retire parallel ContextEngine | `context_engine.py` + runtime；`ContextRequirement+business heads -> ContextSnapshot/Selection/InjectionPlan` | existing ContextEngine invoked by Runtime | D04/D12；测试四角色不同 plan、Writer 无 raw source、exact reconstruction | ContextEngine 尚未 mainline consumed；S1 不做 memory promotion 或把 chat 当 truth |
| `D10` Repair/concurrency/stop | producer：Evidence/Integrity repair + canonical RepairTicket/ParallelContext/Scheduler；consumer：fixture UI/historical graph | retain canonical repair/parallel assets；absorb fixture repair as traced deterministic service；retire broad rerun repair | runtime + existing repair/parallel/scheduler modules；`failure fingerprint+earliest object+deps -> RepairTicket/PackChangeSet/stop` | earliest faulty owner routed by Runtime | D02/D09/single writer；测试 earliest owner、repeat fingerprint stop、late output不可提交 | current one-repair fixture 不泛化为所有请求；S1-T01 不跑并发或 broad rerun |
| `D11` Writer/Verifier | producer：deterministic no-source writer、DeliverableService、historical Memo/Verifier；consumer：Deliverable UI/Workbench Next | absorb historical Memo/Verifier；retain deterministic writer as explicit fallback；refactor Deliverable projection为 run-scoped；retire standalone Writer entry | runtime + `memo_llm.py` + DeliverableService；`LeadSynthesis+Claim/Judgment+WriterBrief -> Presentation/SurfaceClaim/Verifier finding/typed stop` | Runtime writer stage + Deliverable read projection | D08/D09/D10；测试 source/tool=0、SurfaceClaim refs、失败不复用旧 artifact | 当前 fallback 核心回答不等于 Lead synthesis；S1 不做真实 Writer/Human/release，不新建 Writer family |
| `D12` Profiles/failure truth | producer：ExecutionService、local preview、standalone DeepSeek runner、legacy WorkbenchProfile；consumer：ActivityTrace、Workbench Next、CLI | refactor ExecutionService 为 admission/enqueue；refactor `app.py` composition；retain scheduler/object store；refactor existing facade 增加 Run lineage；absorb local service as fallback；retain runner only as reproducibility | `app.py` + planned runtime + execution API/client + ActivityTrace/Workbench Next + existing scheduler/facade/models/store/object store；`ExecutionProfile+exact refs -> WorkUnit/Attempt/ResearchRun/ProfileExecutionResult/Event/Artifact/typed failure` | `Fin01ResearchRuntime`（各对象 owner 见 manifest `ownership_by_object`） | 测试 202 enqueue-only、claim-before-execute、exact lineage、两个 profile 不同 Run/artifacts、Agent failure remains failed、fallback forked child WorkUnit/Attempt/Run | ResearchRun 当前缺失；Workbench Next write 当前 disabled；S1 不允许 bounded model/release profile |
| `D13` Release scope | producer：FeatureScope v1.1 + ten-cell P36 preview；consumer：Workbench/backlog/tests | retain ten-cell deterministic reference；retain three-cell/three-case scope；retire hard-coded NVDA facts after parity | FeatureScope/backlog/runtime；`active cell ids+case profile+scope version -> S1 one-cell fixture / later case proof` | FeatureScope/backlog own scope；Runtime owns execution | D12/same adapter；测试 S1 only NVDA demand cell、ten-cell明确 fallback、release state不变 | ten-cell reference 不等于 Agent depth；S1 不跑 DELL/MU、不声称 R2/R3/release |
| `D14` Eval/Human/release | producer：HumanBaseline、Integrity、Deliverable、contract tests、release evidence；consumer：Review UI/release records | retain isolated HumanBaseline/tests；refactor review projection exact Run；retire new S1 gate family | existing Human/Deliverable/tests/backlog；`exact Case/Run/Profile/Artifact+findings -> S1 fixture evidence / later Human attestation` | existing eval and Human Review contracts | D11-D13；测试 counts、machine pass≠Human accepted、shadow≠release proof | baseline SQLite 非 canonical release evidence；S1 不做 senior review、RG1-RG5、release/production |

## 5. T02/T03 实现边界（仅冻结，不执行）

### 5.1 T02 deterministic compatibility

T02 只能做以下最小变化：

1. 在 `research_runtime.py` 实现单一 `Fin01ResearchRuntime`；
2. `ExecutionService` 只做 admission/enqueue 并维持 HTTP 202；禁止在 request thread 同步执行 profile；
3. enqueue 成功后只注册一个 FastAPI `BackgroundTask -> ExecutionService.dispatch_queued_work_unit -> Fin01ResearchRuntime.dispatch_once`；Runtime 复用 existing `DurableSchedulerService.claim_next` 和 `RuntimeFacade.claim_next_scheduled_attempt` 后才执行 exact claimed Attempt，不新建 worker/scheduler family；
4. 在 existing canonical model/store/facade 中增加 `ResearchRunVersion`，按本文件 2.3 节绑定 WorkUnit/Attempt/Event/Artifact；
5. `app.py` 作为唯一 composition root 注入 existing facade、scheduler、object store、local service 和 Runtime；
6. 将 `P36LocalResearchService` 包装为 canonical-write-pure deterministic adapter；
7. 维持当前 ActivityTrace 和 Workbench 可用，不删除 `/local-research-preview`、`/local-analysis-preview` 或旧 routes；Workbench Next write 仍留到 T05；
8. deterministic Run、Event、Artifact 必须与当前 Case/DecisionSurface/profile exact binding；object store + SQLite 只声明 envelope/head 原子性，不虚构 distributed transaction。

### 5.2 T03 historical Agent fixture shadow

T03 只能做以下最小变化：

1. 将现有 `build_multi_agent_orchestration_graph` 放在同一 Runtime 的 `agent_fixture_shadow` adapter 后；
2. 只运行 NVDA demand cell fixture 所需的 Lead、primary Specialist、Skill、bounded Tool/Graph observation、Writer/Verifier；
3. 复用现有 Agent Registry、Research Skills、ContextEngine、relationship graph 和 Memo/Verifier，不复制 registry、ContextEngine、graph abstraction 或 Writer；
4. adapter 只返回 `ProfileExecutionResult`；模型、provider、network、商业数据、真实 Case mutation和 direct canonical write 均为 0；
5. registry 的 `relationship_graph` source-family drift 必须按当前 D06 合同裁决并加 deterministic test，不能为让旧测试变绿而删除能力。

T02 与 T03 的 dependency 在本 S1-T01 二次独立复核通过后解除，但本轮没有执行或实现它们；是否立即进入下一项仍以当前用户指令和 backlog 为准。

## 6. Retire 边界

本轮删除项为 0。以下仅标记 `retire_after_parity`：

- 历史 LangGraph 作为 top-level product execution entry；
- standalone DeepSeek runner 作为 application runtime 的角色；
- local preview 作为 Run authority 的任何解释；
- 新建平行 Runtime、Agent Registry、Skill Registry、ContextEngine、Graph abstraction、Writer、store 或 gate family；
- 用 broad full-chain rerun 代替 targeted repair。

真正 retire 前必须满足：current deterministic Workbench parity、exact Run/Event/Artifact、rollback 和 targeted deterministic/browser regression。旧 Workbench/R53-R60 routes、Point 01 path-stable proof modules、release scripts、prototype 和 HumanBaseline local store 均不在本轮删除范围。

## 7. S1-T01 验收与 disposition

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| D02-D14 全部映射到真实资产和 disposition | pass_after_repair | 机器清单 13 个 exact decision ids；D06 已把 `EvidenceService` 纳入 disposition/target；每项含一个 `unique_owner` 与逐对象 `ownership_by_object` |
| 唯一 Runtime/API/UI async write path 已识别 | pass_after_repair | `UI -> 202 admission/enqueue -> existing scheduler claim/Attempt -> Fin01ResearchRuntime -> adapter result -> existing facade commit -> projection`；不在 HTTP request 内跑 profile |
| ResearchRun exact lineage | pass_by_contract | 一个 Attempt 对一个 Run；Event `task_run_id`、Artifact `producer_attempt_id + input_refs`、Attempt `output_refs` 和 fallback child lineage 已冻结；实现留给 T02 |
| composition 与 UI 过渡边界 | pass_after_repair | `app.py` 是 composition root；当前 ActivityTrace write，Workbench Next read-only，T05 接同一 command |
| 无平行 Runtime/Registry/Writer/store/gate family | pass_by_design | planned implementation只增加一个 application adapter，并复用全部既有 authority families |
| 当前代码真实消费边界未夸大 | pass | P36 仍是 deterministic read-only；历史 Agent mainline consumed=false；ResearchRun 尚未实现 |
| 当前授权边界 | pass | 本轮 model/network/paid/commercial/business mutation/runtime implementation 均为 0 |

首轮独立复核：`changes_requested_before_acceptance`。
修订后二次独立复核：`pass_after_independent_review_repair_no_implementation_claim`。

本次通过只解除 T01 dependency，不等于执行 T02/T03。当前仍遵守：

- backlog 的 S1-T02/S1-T03 未执行；
- 不执行 T04-T06；
- 不调用模型、provider、network、付费服务或商业数据；
- 不改变 RG1/RG3/RG4、exact Human Senior Review、release 或 production 状态。
