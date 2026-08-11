# FIN 0.1 第三层 Agentic Search / Evidence 执行草稿

日期：2026-07-19
状态：`discussion_draft / not_execution_authority / not_release_admission`
上位草稿：`FIN_0_1_LAYER_2_AGENT_CORE_EXECUTION_DRAFT_20260719.zh-CN.md`
主要 TECH owner：`TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md`、`TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`、`TECH_04_numeric_program_trace_parser_promotion.zh-CN.md`

## 1. 文档目的

> 2026-07-19 S1-T04 执行更新：`agent_fixture_shadow` 已在同一 `ResearchRun` 中执行一个 NVDA Cell 的 Tool fixture observation 与 Graph fixture observation，并形成 exact `agent_fixture_evidence`、`agent_fixture_numeric` 和 trace artifacts。relationship dependency injection 已修正为真正 override，不会先触发 MCP lookup；测试用禁止调用探针证明 external tool/network/model/provider 均为 0。Evidence 保持 `fixture_shadow_not_promoted`，Graph edge 明确仅为 navigation hypothesis、无 Numeric authority；因此这不是 live search、真实 Evidence promotion 或 Agentic Graph 研究质量证明。

本草稿定义 FIN 0.1 如何把 accepted DecisionSurface 中的 EvidenceRequest 转成可停止、可追踪、权限受控的 RAG/SQL/Graph/official-source 检索闭环。它不重写现有 retriever、parser、Graph 或 Evidence Gate，也不批准网络、付费数据、模型执行、Evidence promotion、真实业务 Case mutation或 release。

## 2. 当前事实基线

- 当前 Workbench 产品链固定执行 8 次本地 Object BM25、1 次 Gold SQL 和 1 次 Research Graph SQL；
- 查询、路由和十-cell 投影主要由 `P36LocalResearchService` 确定性驱动；
- 当前主链没有根据 observation 动态改变 route，也没有统一消费历史 Tool Controller/SourceHunter；
- 当前 RAG/SQL/Graph 产物属于本地 candidate/read model，不证明 Agentic Search；
- 历史仓库已有 Tool Controller、source routes、parser、CandidateBundle、Evidence Gate 和大量数据/图谱资产，但与 FIN 0.1 唯一 ResearchRuntime 仍断连。

## 3. `L3-D05`：Agentic Search Control

`L3-D05-AgenticSearchControl` 已冻结为 `evidence_request_driven_bounded_search_with_candidate_promotion_separation`。

Agentic Search 的完成语义不是“模型可以自由搜索”，而是：围绕 exact EvidenceRequest，根据 candidate observation、gap、权限、成本和 route exhaustion 动态选择、细化或停止检索路径。不同 observation 必须能够产生不同 route 或 stop decision。

### 3.1 主闭环

```text
accepted DecisionSurface Cell / RepairTicket
  -> EvidenceRequestVersion
  -> Evidence Tool Planner
  -> SearchPlanVersion
  -> ToolGateway preflight
  -> admitted Evidence Operator
  -> CandidateBundleVersion
  -> parser / metadata / numeric binding where required
  -> Evidence Gate
  -> EvidenceResponseVersion
  -> Lead ObservationAssessment
  -> refine / repair / typed gap / stop
```

EvidenceRequest 只能从 exact Cell、InvestigationBranch 或 RepairTicket 编译；自由搜索词不能成为产品主账本入口。Query rewrite、facet、neighbor/section/table expansion 和 relationship expansion 都必须保留原始 EvidenceRequest、原因码、预算和 lineage。

### 3.2 Authority 分工

| Owner | 权限 |
| --- | --- |
| Research Lead | 决定需要回答什么证据问题，以及研究继续、repair 或 stop |
| Domain Specialist | 提交或细化结构化 EvidenceRequest，不直接私有搜索 |
| Evidence Tool Planner | 将 EvidenceRequest 编译成候选 route/step，不拥有 promotion authority |
| ToolGateway | 确定性验证 tool、permission、network、data、budget 和 input contract |
| Evidence Operator | 执行受限 RAG/SQL/Graph/official-source route，只返回 observation/candidate |
| Parser/Numeric | 绑定结构、实体、期间、单位、scale 和程序 trace |
| Evidence Gate | Evidence promotion 的唯一入口 |
| Lead | 消费 EvidenceResponse，不能改写 Evidence Gate head |

模型可以参与 route proposal、query formulation 和 observation summary，但所有执行必须经过 ToolGateway；模型选择不能授予网络、商业数据、Tool 或 promotion 权限。

### 3.3 Candidate 与 Evidence 分离

```text
Search Result
  -> Candidate
  -> Parsed/Bound Candidate
  -> Numeric/Metadata Lineage
  -> Evidence Gate
  -> accepted / context_only / rejected / typed_gap / commercial_gap
```

BM25/vector 相似度、SQL row、Graph edge、历史 memory、新闻摘要和 SourceHunter hit 都不能自动成为 Evidence。SQL 结果仍必须绑定 data version、entity、period、unit、source 和 lineage；Graph pointer 默认只支持 route/context，不能单独证明商业关系或因果关系。

### 3.4 三-cell 初始 Route Policy

| Cell | Primary Route | Conditional Expansion |
| --- | --- | --- |
| `demand_signal` | issuer disclosure、customer deployment、customer Capex、本地 RAG | Graph neighbors、上下游 official sources、SourceHunter |
| `revenue_capture` | Gold SQL、issuer financial tables、Numeric Parser | segment/product mix、pricing、customer/OEM read-through |
| `thesis_counterevidence` | relationship/research Graph、policy/industry sources、counter-search | supply-chain source、market expectation、competition/cycle context |

Graph 负责建议“下一步查谁、查什么关系”；底层来源仍需进入 CandidateBundle 并通过 Evidence Gate。

### 3.5 Search 状态与 Stop

Search state 至少包括：

```text
planned -> route_selected -> searching -> candidates_observed -> gate_classified
```

随后只能进入：

- `satisfied`；
- `needs_context_expansion`；
- `needs_metadata_requery`；
- `needs_sourcehunter`；
- `typed_gap`；
- `commercial_gap`；
- `stopped_budget`；
- `stopped_permission`；
- `route_exhausted`。

FIN 0.1 不采用跨所有请求统一的“一次修复”规则。每份 EvidenceRequest 必须自带 route、candidate、query refinement、SourceHunter 和 cost budget；简单请求一次结束，困难请求可以在预算内使用不同 route，但重复候选、权限不足、authority gap、commercial gap、预算耗尽和 route exhaustion 必须形成 typed stop。

### 3.6 SourceHunter 边界

首版优先消费已有本地真实资产：本地官方披露、Object BM25/未来 Vector RAG、Gold SQL、Relationship/Research Graph 和已物化公开来源。只有内部路线不足且 exact ExecutionProfile 明确允许时，才能创建 SourceHunterRequest。

模型调用批准不等于联网批准；网络、商业数据、持久化和 source license 分别受独立 policy 控制。SourceHunter 必须单独记账，不能把新抓取结果伪装成既有 KB 能力。

### 3.7 Workbench 呈现

主界面展示业务语义：当前证据目标、选择的路线、候选质量、为什么扩展、当前 gap 和 stop reason。Inspect 才展示 EvidenceRequest、query rewrite、Tool/Operator、candidate/dropped counts、Gate decision、预算和 exact refs。不得将自由文本 CoT 或后端原始日志作为主产品交互。

### 3.8 最小完成证明

至少证明：

1. 不同 EvidenceRequest 选择不同 route；
2. 过期、泛化或非公司特定 candidate 触发 metadata/source refinement；
3. Numeric 请求进入 SQL/Parser/Numeric，而不是普通 RAG；
4. Graph observation 产生 source follow-up，不能直接晋升 Evidence；
5. 未授权 network/tool/data route fail closed；
6. route exhaustion 返回 typed gap，不生成虚假答案；
7. plan、step、candidate、Gate 和 stop 全部绑定同一个 Run/Cell/Branch/EvidenceRequest。

单一固定查询、candidate 数量、Tool 调用计数、静态 fixture 顺序或搜索摘要文本均不能证明 Agentic Search。

## 4. 与上位决策的关系

- `L2-D02` 限制 Lead 只能在 accepted DecisionSurface scope 内创建 EvidenceRequest；重大 Cell 变化仍需 Human versioned revision；
- `L2-D03` 要求 Specialist 不得私有化检索，Evidence Operators 经 ToolGateway 执行；
- `L2-D04` 允许 Skill 指导搜索方法，但 Skill 不能授予 Tool、网络、数据、预算或 Evidence authority；
- TECH_02/03/04 继续拥有 Tool Planner、CandidateBundle、knowledge address、parser/numeric 和 promotion 细节，本草稿只冻结 FIN 0.1 产品闭环。

## 5. `L3-D06`：Graph Research Role And Authority

`L3-D06-GraphResearchRoleAndAuthority` 已冻结为 `typed_provenance_graph_for_navigation_hypothesis_and_lineage`。

Graph 是 Agentic Research 的导航、关系推演和研究血缘基础，不是天然事实源。任何会进入 Judgment 的关系都必须有 exact entity、edge semantics、来源、时点和适用边界，并经过 Evidence Gate；不存在无来源、无时点、无语义边界的 `naked edge authority`。

### 5.1 五类逻辑 Graph

| Graph | 产品角色 | Authority 边界 |
| --- | --- | --- |
| `EntityGraph` | issuer、ticker、产品、地区、机构等 identity resolution | 经 deterministic Entity Master 校验后可作为身份基础设施 |
| `BusinessRelationshipGraph` | 供应商、客户、产品、产能、竞争、资本和宏观传导关系 | 默认支持导航和机制分析；关键关系必须回到底层来源验证 |
| `EvidenceClaimGraph` | Claim、Evidence、Counterevidence、Gap 的支持、冲突和缺口 | 表达研究论证结构，不创造外部事实 |
| `ResearchWorkflowGraph` | Cell、Branch、Agent、Skill、Repair、Review 的运行血缘 | 只表达 exact ResearchRun 内的 workflow lineage |
| `MemoryGraph` | 历史 Case、历史判断和 Human Review prior | 必须检查 freshness、版本和适用范围，不能代表当前事实 |

这些 Graph 可以共享物理存储，但 schema namespace、authority class、version 和写入权限必须分开，不能把业务关系、证据关系、工作流事件和历史记忆混成同一种 edge。

### 5.2 Edge Authority

| Edge class | 例子 | 可参与 Judgment 的条件 |
| --- | --- | --- |
| canonical identity | `NVDA -> ticker NVDA` | Entity Master exact match |
| source-backed relationship | `TSMC -> provides CoWoS packaging` | exact source ref、as-of、方向、关系语义和 Evidence Gate classification 完整 |
| quantitative relationship | 客户收入占比、产能占比、利润归属 | 必须回到原始表格/数据，经 Parser/Numeric 绑定；Graph 不拥有数值 authority |
| inferred mechanism | `AI demand -> HBM tightness -> margin expansion` | 只能标记为 hypothesis/context，不能作为 Evidence |
| workflow/lineage | `Claim -> supported_by Evidence` | 只证明研究产物之间的绑定关系 |
| memory/prior | 上期 Case 判断 | 只能触发当前期重新核验 |

即使 source-backed edge 通过 Gate，它也只能支持其来源明确表达的关系。例如“存在供应关系”不能自动升级为“该关系构成当前瓶颈”“贡献特定收入”或“造成利润扩张”。

### 5.3 Agentic Graph 闭环

```text
EvidenceRequest / Specialist graph expansion request
  -> Lead decides whether graph exploration is material
  -> Evidence Tool Planner selects Graph Operator
  -> ToolGateway applies graph namespace/depth/path/budget policy
  -> GraphCandidateBundleVersion
  -> Lead selects/rejects bounded paths
  -> source follow-up EvidenceRequest for material edges
  -> parser / metadata / numeric binding where required
  -> Evidence Gate
  -> accepted relationship / hypothesis / typed gap
```

Lead 可以根据 Gap、冲突或第一跳 observation 申请有限第二跳扩展、创建 InvestigationBranch，并选择后续要核验的关系；FIN 0.1 默认最多两跳，top-k/path 数量由 ExecutionProfile 约束。Lead 和 Specialist 都不能直接写 canonical Graph、生成正式 edge、绕过来源复核或把关系自动解释成因果和经济量级。

模型可以提出 `GraphEdgeCandidate` 或 mechanism hypothesis，但正式图谱更新必须通过独立的 source validation 和 versioned admission。Agent 运行期间不允许直接修改 canonical Graph。

### 5.4 三-cell Graph 使用

| Cell | Graph 作用 | 禁止替代的能力 |
| --- | --- | --- |
| `demand_signal` | 从 issuer demand signal 扩展到客户部署、供应商订单、Capex 和产业节点，寻找交叉验证路径 | 不能只凭关系边证明需求规模和持续性 |
| `revenue_capture` | 连接公司、分部、产品、客户和供应链位置，定位需要查找的价值捕获证据 | 不能由 Graph 分摊收入、利润、价格或市场份额 |
| `thesis_counterevidence` | 发现产能、设备、出口限制、客户集中、替代技术、竞争和周期风险路径 | 不能把推断路径写成已确认反证 |

### 5.5 Runtime Artifact 与 Workbench

Graph Operator 至少返回 `GraphQueryRequest`、`GraphCandidateBundleVersion`、`GraphPath`、edge authority class、source/as-of refs、suggested follow-up EvidenceRequest 和 rejected/truncated reason。EventTrace 必须记录为什么调用 Graph、查询 namespace、返回路径、Lead 选择或拒绝的路径、来源复核结果和最终 classification。

Workbench 主界面不展示无边界的大型通用图谱。Cell 内只展示紧凑的机制/依赖路径，并明确区分 source-backed、inferred 和 unresolved edge；点击后才进入 Graph Explorer 查看完整邻居、来源、时点和 lineage。

### 5.6 最小完成证明

至少证明：

1. exact EvidenceRequest 可以触发适合该 Cell 的 Graph route；
2. Lead 能根据第一跳结果创建一次受限第二跳或 source follow-up；
3. naked edge、无来源 edge 和 inferred mechanism 不能被晋升为 Evidence；
4. Graph 不会自行生成财务数字或公司级收入/利润归属；
5. stale、superseded 或 conflicting edge 被显式降级或拒绝；
6. Graph path、底层来源、Evidence、Judgment 和 Trace 绑定同一个 Run/Cell/Branch；
7. 三个首发 Cell 各有至少一个可解释的 Graph 使用案例。

固定 SQL 图查询、edge 数量、图谱画布截图或静态 mechanism 文本不能单独证明 Agentic Graph Research。

## 6. `L3-D07`：Evidence Promotion And Counterevidence Authority

`L3-D07-EvidencePromotionAndCounterevidenceAuthority` 冻结为两层合同：

1. `D07-A invariant_contract`：`claim_scoped_symmetric_promotion_with_immutable_lineage`；
2. `D07-B calibrated_policy`：`cell_and_claim_type_specific_thresholds_calibrated_by_real_cases_and_human_review`。

这一区分防止把产品可靠性误实现成统一高门槛。A 层是所有 profile 都不能破坏的事实与权限边界；B 层负责在输出质量、信息不足和误晋升风险之间做可版本化、可评测的产品取舍。B 层在真实 Case/Human Review 校准前不得伪装成普遍真理。

### 6.1 D07-A 不可变原则

- Candidate 不能未经 Evidence Gate 进入 Judgment；
- `accepted` 只对 exact Claim、entity、period、unit、scope 和最大 claim strength 有效，不是全局事实权威；
- promotion status 与 claim relation 分离：`accepted` Evidence 可以 `supports / contradicts / qualifies / contextualizes`；
- 支持当前 thesis 与反驳当前 thesis 的材料执行同一套 entity/source/freshness/lineage 规则；
- `context_only` 不能支撑 exact fact，`rejected` 不能因符合 thesis 被恢复使用；
- Evidence Gate 写 promotion business truth，但不写 Judgment；
- Specialist/Lead 不能隐藏 accepted counterevidence、覆盖 Gate 或原地修改历史 Claim/Judgment；
- Writer 只消费 exact adjudicated Judgment/Claim heads，不能从 raw Candidate 自行补强结论；
- stale、superseded、revoked 或 materially contradicted Evidence 必须保留历史版本并产生 downstream impact，不能静默删除或覆盖。

每个 `EvidenceRecordVersion` 至少声明 `can_support`、`cannot_support`、claim/cell refs、relation、entity/segment/period/unit/scope、source authority、as-of/available-at、parser/numeric/graph lineage、freshness、permission/license、supersession/revocation 和 impact refs。

### 6.2 D07-B 可校准策略

以下内容不能写成跨所有 Cell 的固定数量规则：

- 某类 Claim 需要一份还是多份 source；
- independent corroboration 如何定义；
- context/proxy 能把判断推到什么强度；
- 反证达到什么 materiality 才触发 qualifier、repair、reopen 或 Human escalation；
- `supported / mixed / unknown` 等 Judgment 状态的 Cell-specific threshold；
- 信息不足时应输出 bounded judgment 还是 typed gap。

首版 policy 由 `EvidencePromotionPolicyVersion + CounterevidenceMaterialityPolicyVersion` 按 sector、Cell、ClaimType、source role 和 intended use 配置。精确 issuer fact 可以由一份足够权威且口径匹配的一手来源支持，不强制凑引用；domain judgment 不能按 citation 数量投票，必须检查 evidence-role coverage、独立性、推理距离、冲突、freshness 和 What-Would-Change。

所有初始 threshold 都是待校准 hypothesis。它们必须用三个真实 Case、候选 policy 对比、错误晋升/过度保守样本和 exact Human Review 调整；policy 变更生成新版本，不改写历史 Run。

### 6.3 Counterevidence 处理

accepted counterevidence 先形成 `CounterevidenceAssessment`，再由 TECH_05 Specialist/Cell Adjudicator 处理：

- non-material：保留，不改变 Judgment；
- qualifying：收窄 claim strength 或适用范围；
- resolvable conflict：创建 Evidence/Numeric/Domain repair；
- material core conflict：提出 JudgmentDelta、重开 Cell 或依赖 Cell；
- identity/scope/DecisionSurface conflict：按 D02 提交 Human versioned revision；
- unresolved high-material conflict：保持 `mixed/unknown` 并进入 Human escalation。

不能用低权威多数票覆盖更权威、更新鲜或口径更精确的反证。Numeric input 被撤销时，其派生事实、Claim、Judgment 和下游 artifact 必须进入选择性失效。

### 6.4 Workbench 与最小证明

Workbench 分开显示 Candidate、accepted Evidence、accepted Counterevidence、context、rejected 和 Gap，并解释一条 Evidence 能证明什么、不能证明什么，以及 Judgment 为何被限定、重开或停止。不得用一个不可解释的总分掩盖冲突。

至少证明：Candidate 无法绕 Gate；context 不能支撑 exact fact；accepted counterevidence 不会被隐藏；重复转载不等于独立 corroboration；stale/revoked Evidence 能触发 dependency impact；Numeric invalidation 正确传播；核心反证可重开 Cell；Writer 使用最新 exact Judgment head；同一 invariant 下不同 policy 可以对比质量和误差，而不改变权限边界。

## 7. 下一层接口

TECH_05 消费 `EvidenceRecordVersion / CounterevidenceAssessment` 形成 domain Judgment；下一份草稿从 `L4-D08-SpecialistJudgmentContract` 开始，定义专业判断、跨 Cell synthesis、Context/Memory 和 repair/version 行为。
