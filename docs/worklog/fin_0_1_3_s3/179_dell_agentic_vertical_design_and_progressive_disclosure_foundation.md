# Dell Agentic 完整纵切：技术详设冻结与零模型实现入口

更新时间：2026-09-03 02:33 +08:00

产品版本：FIN 0.1.3

分支：`codex/fin013-dell-s1-s2-product-bridge`

设计基线 commit：`355059686609067e304c27f6568860f16af855ae`

状态：`DESIGN_FROZEN / INDEPENDENT_P0_P1_0_0 / WAVE_0A_ZERO_MODEL_ALLOWED / RC-S3-105_OPEN / A03_ABSENT`

## 1. 本轮完成了什么

Owner 要求先把五项运行时修正、渐进式披露、上下文、Redis、后端、前端/HITL 和运行后交互研究清楚，冻结 Dell 单 case 的技术详设，再开始实现，避免边写边改定义。

本轮完成并冻结：

- 详设：`docs/architecture/research/FIN_0_1_3_DELL_AGENTIC_MULTI_AGENT_VERTICAL_DETAILED_TECHNICAL_DESIGN_20260903.zh-CN.md`；
- 三轮作者分离的只读反证审查；
- 最终审查结论：`PASS / P0=0 / P1=0`；
- Wave 0A 零模型合同实现入口；
- Wave 0B mature serving boundary 资格测试入口；
- 明确禁止 A02 retry/resume、A03 placeholder 和任何未另行授权的 provider/paid shadow。

本轮没有执行模型、网络、S1/S2 查询、MCP tool、Redis、Agent Server、A03、Evidence admission、报告或产品验收。

## 2. 当前不可变事实

1. A02 仍为不可变 `start_failed`。
2. A02 只有 Planner 一次真实 DeepSeek 调用：HTTP 200，`21,489 / 2,874 / 24,363` tokens；随后 host payload validation fail。
3. S1、S2、MCP、Specialist、Counter、Lead、HITL 和 report 在 A02 中都没有运行。
4. A02 的 16 个 local requests 按真实 metadata-prefilter 重放均为 zero-match。
5. `RC-S3-105-dell-A02-planner-capability-inventory-and-conditional-contract-mismatch` 继续阻断任何新 paid successor。
6. A03 当前不存在，不映射、不预留 placeholder。
7. 现有 1,025 structured nodes、61 Reviewed Evidence、1,319 S2 observations 和 r12 12 条 exact-URL Candidate 仍是有效的 bounded inputs，但不是 A02 已消费证据。

## 3. 冻结的五项纠正

1. MCP 只负责 tool/resource wire contract；Runtime 拥有 session、权限、上下文、调度和可信 scope 注入。
2. Harness 只做确定性 identity/period/unit/authority/lineage/formula/security 校验；Semantic Verifier 独立审查蕴含、因果、反证和跨公司/期间误归因。
3. Lead 与 Specialist 在 sealed scope 内自主规划和多轮工具调用；动态 DAG 是受验证的 `ResearchPlan/AgenticPlanDeltaV1_2` 数据，不是模型生成代码。
4. Verifier 和前端读取 `DecisionArtifact`、Claim/Evidence refs、tool/disclosure receipts 和 repair lineage，不读取 provider 隐藏 CoT。
5. Agent 可怀疑本地数据/tool failure、申请替代路线或补源，但不能提升 authority，也不能把 empty/tool failure/scope exhausted 宣称成 public-information gap。

## 4. 渐进式披露

每次模型调用由 Runtime 生成 `ModelVisibleContextManifest`：固定 L0 目标、plan slice、最新 observation/feedback、compact capability/data/Skill catalog、available actions、budget/stop/intervention；模型可通过 `request_disclosure` 申请 L1–L3。

- L0：名称、用途、authority、成本/时延、answer-free coverage；
- L1：语义合同、inventory、完整 Skill；
- L2：候选 metadata、详细 output/authority、指定 Skill resource；
- L3：指定 Evidence/Fact/Artifact 正文或 bounded excerpt；
- L4：operator-only raw diagnostics，永不进入普通 model context。

每次 list/load/read/invoke 都有 digest-bound receipt；Skill 是方法，不是事实、Evidence 或权限。

## 5. canonical v1.2 identity 与兼容

v1.0/v1.1 保持不可变；新纵切发布显式 v1.2 successor/adapter，不另建第二套真值。

| 对象 | 语义 |
|---|---|
| `AgentSession` | 稳定 case conversation，映射顶层 LangGraph thread；一对多 ResearchRun |
| `ResearchRun` | 一次完整研究生命周期；pause/resume 不新建 Run；follow-up 建 child Run |
| `RunInvocation` | start/resume/recovery 的一次 worker 调度与 lease |
| `ActionAttempt` | 一次 model/tool/capture/publish 副作用；失败/歧义永不覆写 |

A01/A02 是 legacy `PaidFullChainExecution` labels。A02 映射为一个失败 ResearchRun、一个初始 RunInvocation 和一个 Planner ActionAttempt。A03 不存在。

canonical event sequence 为 session-scoped；Run SSE 使用可重建的 projection sequence，并绑定 source session event/digest、projection policy 和 authorization-view digest。

## 6. 数据与工具合同

Provider-visible 工具拆为 local Evidence、Reviewed Evidence、external source、financial facts、calculator、disclosure、plan delta、narrative、claim ledger 和 human/pause。

模型只填写 semantic intent；Runtime 注入 case/session/run/invocation/attempt、as-of、snapshot、authority、permission、issuer、physical route/role/lane、budget、idempotency 和 stop boundary。

`SourceFamilyCompiler` 输出不可混用的：

- `ReviewedEvidenceIntent`；
- `LocalCandidateRetrievalScope`；
- `ExternalSourceIntent`。

非零命中不足以通过。compiler 必须同时验证 issuer/period/source-role/route/branch/authority、禁止集合和 cardinality；全库 selector、错误 alias、忽略 period、跨 lane 和 stale inventory 均 fail closed。

`ReviewedEvidenceIndexV1_2` 复用现有 Evidence store/MCP。首版允许 query overfetch + host exact post-filter，但必须形成 filter receipt；query-only legacy locator 不能满足 strict reviewed route，也不能单独支持 `ReportedFactClaim`。

每个 Q1–Q9 除 Coverage 外还有 answer-free `MinimumRouteObligation/BaselineSourcePlan`，冻结 required Reviewed/local/S2/external/calculator 类别、authority 和替代条件；Planner 不能静默删除。

## 7. 正文、Claim 与 public gap

自然语言恢复为自由 Markdown；Host 生成 anchors，同一 Agent 另交 ClaimLedger。Ledger 失败只修 claim/句子，不强迫全文塞进统一自然语言 schema。

确定性 Validator 与 Semantic Verifier 分层；Writer 后还要经过 final deterministic + final semantic verifier。任何 finding 使旧 artifact/claim/approval stale；repair 新 revision 必须重新过两层 verifier 和 fresh HITL。

`GapEligibilityReceipt` 按 material proposition 绑定 requirement/minimum route、本地 object/index/SQL、compiler、route/capture、Candidate/admission、transport/retry、budget/stop 和 unresolved owned-defect disposition。empty、scope exhausted、未搜索 route 或工具失败均不能单独成为 public gap。

## 8. context、checkpoint 与 CoT

`ContextCheckpointV1_2` 显式保存 coverage、Claim、Calculation、Disclosure、Skill consumption、open verifier/intervention、budget、stop 和 context projection refs。required refs 从 accepted plan/event/notebook 自动派生，调用方不能用默认空集合绕过。

provider private reasoning：

- 只允许在同一 provider ActionAttempt 内，为协议连续性在易失内存中瞬时回传原 provider；
- 不持久化，不向产品/审查面或其他接收方传输，不展示；
- DB、artifact、diagnostic、trace、SSE、DOM、export 全部 zero-leak；
- in-flight crash 后旧 ActionAttempt 为 `AMBIGUOUS_AFTER_DISPATCH`，从 Notebook 开新 ActionAttempt，不伪称恢复旧私有 reasoning。

## 9. backend、PostgreSQL、Redis 与成熟 serving

- PostgreSQL：Session/Run/Invocation/Attempt/Event/Command/Notebook/Projection/Intervention/Outbox 真值；LangGraph saver 独立 schema。
- Redis：仅 wakeup/fan-out/cancel signal/短 TTL cache/rate limit，或成熟 queue broker；不是 Evidence/Event/checkpoint 真值。
- SQLite：local-lite 单机资格环境；不宣称 production/HA/multi-worker。
- SSE：DB/server replay 为真，传输允许重复，客户端按 projection sequence 去重；policy/ACL digest 变更后必须重取 snapshot。

为避免再次先自研，Agent Server zero-model Docker qualification 已前移为 Wave 0B，阻塞所有重叠的 run persistence/queue/SSE backend 实现。必须输出：许可/key/egress、资源、数据驻留、thread/run/cancel/resume/SSE 行为，以及 FIN Session/Run/Invocation 与 server thread/run 的 cardinality map。

通过则采用成熟 server/queue/stream，Workbench 只做 FIN domain/BFF/UI；有明确 rejection receipt 后才允许最小 OSS single-worker fallback。

## 10. crash、HITL 与 publication

ActionAttempt 进行态：`INTENT_COMMITTED / DISPATCHED / RECEIPTED`；不可变终态：`APPLIED / FAILED_BEFORE_DISPATCH / AMBIGUOUS_AFTER_DISPATCH / REJECTED_BEFORE_DISPATCH`。`RECOVERY_REQUIRED` 只属于 ResearchRun。

recovery 新建 `RecoveryDisposition` 和必要的新 RunInvocation/ActionAttempt，不改写旧 ambiguity；provider `DISPATCHED` 无 receipt 不自动 retry，也不宣称 exactly-once。

HITL 使用 discriminated command、exact plan/action/artifact/claim digests、policy/matrix digests、required authority class、independence 和 authorization basis。普通 HITL 永远不能补授 model/provider/paid authority；新的 paid execution 只能由独立 `PaidExecutionOwnerDecision` 预先授予。

publication intent commit 后不可 generic cancel；只能完成或 reconciliation。外部撤回是新的 ActionAttempt，不是假装 rollback。

## 11. 前端产品面

目标页：`/workspace/cases/:caseId/runs/:runId`。

首批组件：RunHeader、AgentPlanList、WorkpaperPanel、ProofInspector、ActivityTimeline、HumanInterventionDrawer、FollowUpComposer。前端展示研究路径、决策摘要、证据与修复链，不展示隐藏 CoT。运行后追问创建 child Run，不修改终态历史。

## 12. 下一步与停止门

下一合法实现是 Wave 0A：

1. canonical v1.2 machine contract 与 legacy adapters；
2. Coverage/MinimumRoute/ResearchPlan/PlanDelta/Checkpoint；
3. RuntimePolicy/ModelNodeAuthority/RuntimeScope；
4. Disclosure/Context/Decision/Failure/Gap contracts；
5. 正负 selector、CoT、prompt injection、authority 和 mutation tests。

随后是 Wave 0B Agent Server zero-model serving qualification，再进入 RC-S3-105 的 inventory compiler/data disclosure 实现。

禁止：A02 retry/resume；创建 A03；任何 DeepSeek/provider/paid shadow；自动 Evidence promotion；把 local-lite 称为 production；先实现与成熟 serving 重叠的 backend。

只有 RC-S3-105 关闭、zero-model gates 通过、clean pushed commit、独立审查通过并形成新的 `PaidExecutionOwnerDecision` 后，才可分配新的 PaidFullChainExecution/ResearchRun/RunInvocation IDs。
