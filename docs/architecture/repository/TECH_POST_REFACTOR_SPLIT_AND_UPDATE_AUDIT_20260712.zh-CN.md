# TECH Post-Refactor Split and Update Audit

日期：2026-07-12

状态：`canonical_architecture_audit / split_pass_with_implementation_decomposition_required / no_runtime_proof`

审计对象：更新后的 PRD、TECH_00/00A、TECH_01-11、Point 01 和 2026-07-12 定位重构记录。

## 1. 结论

### 1.1 顶层 TECH 拆分

结论：`PASS`。

TECH_01-11 已形成完整且基本正交的 business owner 划分：

```text
TECH_01 ResearchCase / DecisionSurface / Workpaper
TECH_02 Evidence Search / Promotion
TECH_03 Source / Candidate / Institutional Memory Address
TECH_04 Parser / Numeric Truth / Recompute
TECH_05 Domain Judgment / WWC / Supersession
TECH_06 Durable Runtime / Permission / Identity / Events
TECH_07 Context Selection / Injection / Compaction
TECH_08 Subagent / Handoff / Agent-Skill Configuration
TECH_09 Presentation / Provenance / Review / Release
TECH_10 Eval / Failure Attribution / Governed Improvement
TECH_11 Monitoring / Alert / Refresh Request
```

没有发现需要新增 `TECH_12` 的独立业务状态域。Institutional Memory、Human-AI Accountability 和 InstitutionalResearchCase 都是跨模块主线，不应各自复制一套 runtime。

### 1.2 更新一致性

结论：`PASS_AFTER_REPAIR`。

新版 PRD 的产品定位、五个产品平面、R1-R4、责任链、配置治理和 provider-neutral capability frontier 均已进入 TECH_00/00A，并被对应 owner TECH 消费。未发现 PRD 新增核心能力完全没有 TECH owner 的 `owner_gap`。

### 1.3 实施级拆分

结论：`PARTIAL / REQUIRED_BEFORE_IMPLEMENTATION`。

当前 13 份 TECH 文档约 5,278 行，已经足够做 architecture constitution，但多个 owner 文档同时承载 schema、policy、state machine、source strategy、fixture 和历史补充。直接据此编码会再次产生临时对象和多套 store。进入每个 migration slice 前必须下拆 machine-readable schema、API/event、DB/index、adapter 和 eval child specs。

本审计不评估 runtime 是否实现；所有新增定位能力仍是 `documented / contract_draft`。

## 2. 顶层拆分审计

| TECH | 顶层边界判断 | 是否应新增顶层 TECH | 实施级拆分需求 |
| --- | --- | --- | --- |
| TECH_01 | Case 研究语义、DecisionSurface、Gap/Repair、Workpaper、LeadReview 同属 research control | 否 | Case schema/commands；DecisionSurface compiler；Workpaper/LeadReview |
| TECH_02 | search orchestration 与 evidence promotion 同属 evidence control，但实现组件不同 | 否 | Request/Planner；Tool/Provider Registry；Gate/Promotion；SourceHunter |
| TECH_03 | source address、structure、candidate、memory/PIT 都依赖同一 versioned address layer | 否 | Source/Metadata；Structure/Table；Retrieval/Index；Memory/PIT；Data Room/Ontology |
| TECH_04 | parser lineage 与 numeric hard gate 强耦合，但解析器和计算运行时应物理解耦 | 否 | Parser/Table Binding；Numeric Fact Compiler；Program/Model/Recompute；Market/Derivative metrics |
| TECH_05 | domain judgment、WWC、dependency/supersession 是同一 adjudication 域 | 否 | Operator contract；Judgment engine；WWC/impact；Sector packs |
| TECH_06 | durable state、permission、identity、budget、scheduler 同属 harness，但实现面过宽 | 否 | Event/State Store；Scheduler/Lease/Budget；Permission/Identity/OA；Replay/Recovery |
| TECH_07 | context selection/compaction 是单一域，长期 memory 已移回 TECH_03 | 否 | Context API；Selection policy；Compaction；Usage observation |
| TECH_08 | subagent/handoff 与 versioned Agent/Skill definition 同属 coordination plane | 否 | Definition registry schema；Handoff envelope；Version impact；config rollout adapter |
| TECH_09 | provenance、presentation、Workbench、approval/release 同属 last-mile truth-preserving plane | 否 | Presentation/Writer；Provenance/Artifact graph；Workbench/Review；Attestation/Release |
| TECH_10 | eval、failure attribution、release gate、improvement 同属 quality control | 否 | Eval schema/runner；Gold/Oracle；Failure graph；Release/AIE/R1-R4 dashboards |
| TECH_11 | Watchlist/Monitoring 有独立跨任务长期状态，单独 TECH 合理 | 已存在且必要 | Subscription/Cursor；Observation/Rule；Alert/Digest；Refresh routing |

## 3. 本次审计发现并已修复

### High

1. **TECH_07 memory 双主账本风险**：旧第 17-18 节像是在拥有 promotion/lifecycle。已改成 TECH_03 Registry consumer，`MemoryWriteCandidate` 只能提交 TECH_03。
2. **TECH_06/09 approval owner 模糊**：已明确 TECH_09 拥有 DecisionAttestation/approval/release 业务语义，TECH_06 只拥有 transaction、event、hash 和 persistence。
3. **TECH_01 evidence promotion 越权**：旧 Lead 权限写为裁决 accepted/rejected。已改为消费 TECH_02/04 decision，只裁决 Case repair/disclosure/stop。
4. **TECH_10 范围遗漏 TECH_11**：状态和接口从 TECH_01-09 更新为 TECH_01-11，并增加 monitoring/refresh inputs。
5. **团队协作 owner 不完整**：新增 CaseRoleAssignment/ResearchAssignment -> TECH_01；ReviewAssignment/Comment/Mention/ReviewSLA -> TECH_09；TECH_06 持久化 SLA/notification。
6. **Graph 配置 owner 过度归入 TECH_08**：已明确 verified ontology/graph identity 属于 TECH_03；TECH_08 只拥有 Agent/Skill/Workflow 和 Graph view/config semantics。

### Medium

1. TECH_00 “TECH_11 判定”标题在 Watchlist TECH_11 已存在后有歧义，已改为新增 TECH 判定原则。
2. TECH_00 Stable Object Graph 未吸收 EvidenceRecordVersion、NumericProgramRun、JudgmentVersion 和 human collaboration objects，已补齐。
3. TECH_01 `CaseControlMemory` 易与 Institutional Memory 混淆，已改成 CaseControlStateRef + exact owner refs。
4. TECH_01 release lifecycle 已明确是 TECH_09 ReleaseRecord 的只读聚合，不创建第二个 release head。
5. TECH_09 顶部状态仍只描述 trace，已升级为 last-mile presentation/review/release contract。

## 4. 当前仍未闭环的问题

### P1：实施前必须完成

1. **Machine-readable canonical schema**：多数对象只有 Markdown 字段，没有统一 JSON Schema/Pydantic/SQL mapping 和 schema registry。
2. **Command/API/Event matrix**：已有局部 command/event 名称，但没有覆盖全部 producer、consumer、idempotency、error、permission 和 version precondition。
3. **Physical store plan**：TECH_00 已分 business/persistence owner，但每个对象尚未完整映射 SQL table、ObjectStore payload、index、queue、transaction/outbox 和 retention。
4. **Legacy migration**：R52/R57/R58/R59/R60 adapter 边界已声明，字段级 mapping、dual-read/shadow-write、cutover、rollback 和 retirement gate 尚未逐对象完成。
5. **Executable fixtures**：R1-R4、Accountability、Memory PIT、selective refresh、provider swap 多为 fixture contract，尚无统一 manifest/runner/gold。

### P2：可随实施切片完成

1. **文档编辑结构**：多个 TECH 采用日期追加章节，owner 已清晰但阅读顺序偏历史化。进入实现前应把当期 contract 合并回 core sections，并保留 revision/supersession appendix。
2. **状态 metadata**：日期、最近修改、maturity、owner、supersedes 字段格式未完全统一。
3. **TECH_00A eval 关系**：已有 R1-R4 专节，但主矩阵还没有 machine-readable eval subject/metric/gate 列。
4. **Enterprise integrations**：OA/SSO/SCIM、legal hold、签名、Slack/Teams/webhook 只有 provider-neutral contract，没有 adapter spec。
5. **Portfolio semantics**：PRD 仍保持 bounded open question；未定义 Position/Exposure/Privacy，因此 Watchlist 不能宣称 portfolio management。

## 5. 推荐的实施级子文档

这些子文档不新增 business owner，只把顶层 TECH 编译为可实现合同：

| 子文档 | 内容 | 上游 |
| --- | --- | --- |
| `SCHEMA_01_canonical_research_object_registry` | IDs、versions、refs、supersession、actor、permission、retention | TECH_00/01-11 |
| `DB_01_canonical_store_and_transaction_boundary` | SQL/ObjectStore/index/queue/outbox、PostgreSQL compatibility | TECH_03/06/09 |
| `API_01_runtime_command_event_contract` | RuntimeFacade、commands、events、errors、idempotency、expected versions | TECH_01/06 |
| `API_02_evidence_numeric_judgment_contract` | Candidate/Evidence/Numeric/Judgment producer-consumer envelopes | TECH_02-05 |
| `API_03_context_subagent_configuration_contract` | ContextPlan、handoff、Agent/Skill/Policy rollout | TECH_07/08/06 |
| `API_04_review_artifact_release_accountability_contract` | Workbench、Attestation、Manifest、Release/OA callback | TECH_09/06 |
| `EVAL_01_r1_r4_longitudinal_fixture_manifest` | initial -> correction -> follow-up -> quarterly refresh -> reapproval | TECH_10/11 |
| `MIGRATION_01_legacy_to_canonical_cutover` | legacy mapping、shadow、dual read、rollback、retirement | Point 01 + R-series |

第一批不应同时写完所有子文档。Point 01 M0 先冻结 `SCHEMA_01 + DB_01 + API_01 + MIGRATION_01` 的最小 Case/TaskRun/DecisionSurface slice；后续 Evidence slice 再冻结 API_02，以免先设计尚未消费的全量 schema。

## 6. PRD -> TECH 更新审计

| PRD 主能力 | TECH owner | 覆盖判断 |
| --- | --- | --- |
| InstitutionalResearchCase lifecycle | TECH_01/06/03/09/11 | covered contract；not runtime |
| Research Control Plane | TECH_01/06/08 | covered contract |
| Evidence & Modeling Plane | TECH_02-05 | covered contract；implementation split required |
| Institutional Memory Plane | TECH_03 + source business owners | owner conflict repaired；registry not runtime |
| Review & Delivery Plane | TECH_09/06/07/08 | covered contract；R55/R59 adapter pending |
| Monitoring & Learning Plane | TECH_11/10 | covered contract；long-running runtime pending |
| Human-AI Accountability | TECH_06/09/03/10 | covered contract；enterprise adapters pending |
| Configurable Agent/Skill/Graph/Workflow | TECH_03/08/06/10 | owner split repaired；configuration studio pending |
| Provider-neutral capability frontier | TECH_02/06/08/10 | covered contract；provider non-regression runtime pending |
| R1-R4 outcome | TECH_10 + TECH_00A | covered contract；fixtures/runner pending |

结论：没有发现 PRD 核心定位能力在 TECH 层完全断连，但大量状态仍是 contract coverage，而不是实现 coverage。

## 7. 推荐实施顺序

```text
1. SCHEMA_01 canonical registry
2. DB_01 physical store boundary
3. API_01 RuntimeFacade / command / event
4. MIGRATION_01 + Point 01 M0/M1
5. DecisionSurface planning shadow
6. API_02 Evidence/Numeric/Judgment
7. Context/Subagent configuration
8. Review/Artifact/Accountability
9. Monitoring selective refresh
10. R1-R4 longitudinal eval and cutover gate
```

每个步骤完成后必须回写 TECH_00A maturity；不能等最后一次性更新。

## 8. 最终判断

- **产品到技术关系**：完整，已建立稳定主线。
- **顶层模块拆分**：合理，无需 TECH_12。
- **单一 owner 宪法**：审计后通过，已修复发现的冲突。
- **可直接编码程度**：不足；需按 Point 01 先补最小 schema/store/API/migration specs。
- **runtime/product maturity**：本次未发生变化。
- **下一正确动作**：进入 Point 01 M0 contract freeze，而不是继续增加顶层 TECH 或直接实现下游 Agent。

## 9. 2026-07-12 Point 01 Freeze Follow-up

Point 01 已完成首批 `SCHEMA_01 / DB_01 / API_01 / MIGRATION_01` freeze，并通过独立 TECH/PRD alignment audit。Machine result：15 unique objects/tables、10 mappings、15 valid mapping refs、0 missing refs、0 compound business writer。该结果把下一动作从“补 contract freeze”推进到“补 ADR + executable schema/DDL/API/test manifest admission package”，不提升 runtime maturity。
