# FIN 0.1.1 / 0.1.2 PRD 能力对账与 S0–S5 重基线

日期：2026-08-04
状态：`accepted planning correction / S3 bounded anchor pass closed / S4-T01–T02 pass closed / S4-T03 authority fail-closed，controlled successor pending / no product version change`

> 2026-08-04 S4-T03 零调用权限审计确认：F05 当前不是“模型效果差”，而是 metadata route 尚未接成 executable search，来源 request/response capture-first 与 fresh execution-control chain 也未建立。`RC-P36-114` 留在 T03；必须先做一个合并的零调用可执行接入包，再另行判断 current canary admission，不能把 state stub、URL metadata wrapper 或历史 fixture 写成 current Agentic Search。

当前 next：`FIN-0.1.2-S4-T03-NVDA-EXECUTABLE-SEARCH-REQUEST-ROUTE-ADAPTER-CAPTURE-FIRST-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION`

> 2026-08-04 S4-T02 已通过：DELL/MU/NVDA 的 EvidenceRequest、route、ceiling、parser/authority、candidate decision、citation 与 typed gap 已由 current Runtime 零调用证明，合并回归=`29 passed`；RC-P36-113 已关闭。DELL/MU 只是历史 readiness fixture，NVDA 仍是 manifest-only 并需要 current search，promoted Evidence 仍为 `0/3`，current NVDA R2 仍为 false。

> 2026-08-04 Owner 边界决定：接受 S3 为“有限 frozen-input Runtime 与 verified delivery anchor”，但继续拒绝把它解释为 source-grounded NVDA R2。`0/3` promoted Evidence 义务按本文件既有 owner 转入 S4-T02/T03/T04，循环入口门禁已解除。

## 1. 结论

RAG、Agentic Search 和 Agentic Research 从来不是统一留到 FIN 0.2 的能力。FIN 0.1 的 ReleaseContract 已把 `F05 Agentic Search`、三案例 Evidence Workbench、三-cell Domain Judgment、targeted repair、Lead Review、内部交付、Human Review 和 Trace 列为 release-critical bounded scope；FIN 0.2 的原定义始终是 Earnings Review Alpha。

FIN 0.1.1 确实做过相关能力，但成熟度必须分开：

1. 本地 RAG/SQL/Graph/official-asset 候选检索、Evidence/Numeric/Trace 和 deterministic research vertical 已进入当时的产品路径；
2. P33/P34、Step17 和 P30 还保留真实 evidence operator、BGE rerank、source-route、Evidence Fusion 和旧 multi-agent full-chain 运行证据；
3. 但这些历史运行没有全部被 FIN 0.1.1 的 exact ReleaseContract、三案例 R2、NVDA R3、Workbench dogfood 和 Human Review 共同验收；
4. 因此 FIN 0.1.1 只能称为“本地受控检索与部分 Agentic Research 已实现、完整当前版本 Agentic Search/Research 未验收”，不能称为未做，也不能称为已完成。

FIN 0.1.2 重排后的 S0–S3 主要解决共同 Runtime、hermetic proof、模型权限边界和冻结证据后的九件套。该重排遗漏了对 F01–F15、五个产品平面和真实 Agentic Search 的逐项 stage gate。当前 S3 明确禁止 source network 和 external tools，只能证明“证据已准备好以后”的研究判断与交付，不能证明 F05。

本文件修正 S4/S5 的后续规划，不重开已关闭的 S0–S2，不扩大当前 S3-T03，不改变 FIN 0.2 定义，也不创建 FIN 0.1.3。

## 2. 证据等级

后续能力声明统一使用以下等级：

| 等级 | 含义 |
| --- | --- |
| `documented_or_contract_only` | PRD、TECH、schema、registry 或 gate 已存在，未证明 Runtime 消费 |
| `fixture_or_deterministic_proven` | 本地 fixture、mutation、fake/full-fake 或 deterministic vertical 通过 |
| `historical_runtime_proven` | 某一历史 Runtime 真实调用过模型、检索、工具或网络，但没有进入当前版本 exact acceptance |
| `current_runtime_proven` | 当前版本、当前合同、当前 Case/输入实际执行并保留完整 evidence/artifact lineage |
| `product_accepted` | 当前产品表面、paired/human/reviewer 和 release gate 对 exact version 接受 |

历史能力不得跨级直接晋升。旧 Runtime 的真实检索证据可用于资产复用与回归设计，但不能替代 FIN 0.1.2 当前 Runtime 的产品验收。

## 3. FIN 0.1.1 的 RAG / Agentic 能力到底做到哪里

| 能力 | FIN 0.1.1 真实成果 | 冻结时没有成立的部分 | 结论 |
| --- | --- | --- | --- |
| RAG / KB retrieval | BM25、dense、hybrid、Milvus/BGE、metadata filter、facet/object retrieval；当前 P36 本地纵向召回 31 candidates | 评测标签多为 diagnostic/agent-authored；广来源、实时 freshness、完整 human qrels 未成立 | `fixture_or_deterministic_proven`，部分旧运行达到 `historical_runtime_proven` |
| Evidence route / operator | EvidenceRequest、route compiler、SEC/8-K/relationship/market/industry operators、Evidence Fusion、typed gap、authority lineage 均有代码和历史节点证据 | 没有以 FIN 0.1.1 当前 release candidate 对三案例完整验收 | `historical_runtime_proven`，非 frozen product pass |
| Agentic Search | 本地 public/local lanes 可从 cell/requirement 路由到 RAG/SQL/Graph/official assets；旧 Step17 实际触发检索和 rerank | FIN 0.1.1 没有证明当前 Case 下完整的 query rewrite、fallback、SourceHunter、parser repair、candidate rejection 和 Evidence Gate 闭环 | `implemented_scoped / not product accepted` |
| Agentic Research | Lead、specialist、Evidence Layer、Judgment、Writer/Verifier 骨架存在；NVDA historical S3 R2 有 9 Artifacts | DELL/MU R2、post-transfer NVDA、NVDA R3、三案同时通过和 Human dogfood 不成立 | `single_case historical anchor / full product blocked` |
| Research product surface | Task Center、Case、Evidence、Workpaper、Report、Review、Trace 的内部界面存在 | exact current model artifact、真实 Human Senior Review 和产品价值证据缺失 | `implemented_internal / release blocked` |

所以，第一个问题的答案是：**做过，而且原本属于 FIN 0.1；但做成的是多层次历史资产和窄场景能力，不是 FIN 0.1.1 已冻结验收的完整 Agentic Search/Research。FIN 0.2 只负责把稳定底座用于 Earnings Review，不负责替 FIN 0.1 补通用检索和研究闭环。**

## 4. F01–F15 对账

| Feature | FIN 0.1.1 冻结真值 | FIN 0.1.2 当前真值 | 未关闭项与 owner |
| --- | --- | --- | --- |
| F01 Dashboard / Task Center | 旧 Workbench 内部可用，未 release | 继承代码，未对当前 Runtime/Artifacts 重验 | S4-T06 当前运行投影与 dogfood |
| F02 ResearchCase / Objective | 本地 Case/API 可用 | S4-T01 已证明三案自然 Case 入口与 exact binding，尚未连到 current live search | S4-T03/T04 current execution integration |
| F03 Dynamic DecisionSurface | 10-cell deterministic + 3-cell Agent scope；NVDA historical anchor | 三-cell current input/full-fake 已证明；current exact-live 未通过 | S3-T03/T04 单案，S4-T05 三案 |
| F04 Durable execution | cancel/typed stop/恢复骨架，operational qualification 不完整 | exact-once、capture-first、terminal/supervisor 工程显著增强；未接 Workbench business Run | S4-T06 产品运行；S5 RG1/RG5 |
| F05 Agentic Search | local RAG/SQL/Graph/official-asset `implemented_scoped`，无 current live loop acceptance | S4-T02 deterministic readiness 已通过，真实 current search 仍为 0 | S4-T03 独立 release-critical canary |
| F06 Evidence Workbench | candidate/gap/authority/reject/repair UI scoped | 未消费当前三案例 live evidence/artifacts | S4-T03/T06 |
| F07 Numeric / Fact audit | P36 scoped exact facts/margins，三案工程资产存在 | S1 三案 deterministic truth 与本地 Fact ownership 已证明；产品态未验收 | S3-T04 + S4-T03/T05/T06 |
| F08 Workpaper / Domain Judgment | NVDA historical R2；DELL/MU diagnostic only | S3 formal primary failed，诊断九件套不可晋升 | S3-T03/T04；S4-T04/T05 |
| F09 Gap / Repair Queue | 一次 deterministic repair 与 typed gap | Lead gap projection 存在；source-owner live repair 未证明 | S4-T03/T04/T06 |
| F10 Lead Review / Writer Admission | fixture/历史单案部分成立 | Lead/Writer 合同存在，正式 current Artifact 和 owner acceptance 未成立 | S3-T04；S4-T04/T07 |
| F11 Internal Deliverable | deterministic report + historical NVDA artifacts | formal current delivery 未形成；renderer/verifier preview 有已知债务 | S3-T04；S4-T06 |
| F12 Human Review / Accountability | UI/surface 有，qualified Human Senior R3 未成立 | 尚未执行 | S4-T07；S5 RG4 |
| F13 Provenance / Trace | scoped claim/source trace | capture/terminal lineage 强化；当前业务 evidence→claim→artifact→review 未完整 | S4-T03/T06；S5 RG1/RG2 |
| F14 Same-Case explanation | 字段/界面部分存在，非完整 Agent flow | 未实现；仍为 demo-support nonblocking | S4-T07 可选 bounded why/gap/WWC，不阻断 release |
| F15 Quality / Release Feedback | honest-block 和恢复证据真实，但 RG1–RG4 未过 | Project OS/immutable failure/成本证据强；当前产品 quality summary 未验收 | S4-T08；S5 全部 |

## 5. 五个产品平面的遗漏

### 5.1 Research Control Plane

当前 0.1.2 已证明 execution control，但没有证明自然用户 Case 从 Objective 进入当前 Runtime、经过 Lead triage、targeted repair、Human review 再回写 exact state。该闭环归 S4，不回塞 S3。

### 5.2 Evidence & Modeling Plane

这是最大遗漏。S3 的 frozen evidence 可验证下游合同，却绕过了 Agentic Search、SourceHunter、parser/evidence promotion、bounded graph drilldown 和 current Evidence Workbench。F05 必须在 S4 作为独立 gate，而不是由九件套成功隐含。

### 5.3 Institutional Memory Plane

0.1.2 已有 immutable capture、terminal 和内容寻址对象，但尚未把 current Case/Run/Evidence/Judgment/Artifact/Review 串成用户可重建的 exact history。FIN 0.1 只要求 exact history 和 authority boundary；correction reuse、selective refresh、bounded R4 仍归 FIN 0.3。

### 5.4 Review & Delivery Plane

当前需完成正式九件套、最终 renderer preview 验证、Workbench projection、exact Human Senior Review 与接受/退回/repair。Word/PPT/Excel/PDF 不加入 FIN 0.1。

### 5.5 Monitoring & Learning Plane

WWC atom、known gaps、eval 和 release feedback 已有工程基础，但没有完成当前产品投影和 Human value loop。持续 watchlist、event trigger 和 refresh 仍在 FIN 0.3 之后的独立 roadmap。

## 6. 修正后的 FIN 0.1.2 S0–S5

### S0：可靠基础（已关闭，不重开）

证明代码、资源、合同、测试和独立目录可复现。它不证明金融产品、检索质量或模型质量。

### S1：三案例确定性真值链（已关闭，不重开）

证明 DELL/MU/NVDA 的结构、数字、日期、身份、来源、失败留存和 mutation。它不证明真实检索或自然模型质量。

### S2：模型权限边界（已关闭，不重开）

证明 Flash/Pro 在 Fact/Claim/WWC family 的自然能力与本地 ownership。它不选择或验收数据源和产品界面。

### S3：冻结证据后的 NVDA 研究与交付锚点（已按有限范围关闭）

保持当前 T01–T04 和 exact attempt 上限。T03 只证明冻结证据后的 Specialist/Lead/Writer/Verifier/九件套；T04 只做 independent L1、paired L1–L4、最终 delivery review 和 Owner disposition。

S3 通过继续写明：`F05 Agentic Search not assessed`、`natural Case entry not assessed`、`Workbench/Human Review not assessed`、`current source-grounded NVDA R2=false`。不得以 S3 anchor 直接进入 S5。

### S4：Evidence-to-Workbench 三案例产品资格（已进入，固定八项）

| Task | 目标 | 主要 PRD owner | 通过条件 |
| --- | --- | --- | --- |
| S4-T01（pass closed） | PRD/current Runtime 入口与自然 Case binding | F01/F02/F03/F04 | 用户式 Objective、as-of、预算、三 cells、current repository source/index entry snapshot 和 exact identity projection 可重建；明确不等于 current Evidence |
| S4-T02（pass closed） | Retrieval/Evidence deterministic readiness | F05/F06/F07/F13 | 三案 EvidenceRequest、route、candidate ceiling、metadata、parser/authority、accepted/rejected/gap、citation 已以零模型 fixture/mutation 证明；RC-P36-113 已关闭；历史 fixture 未晋升 current Evidence |
| S4-T03（authority fail-closed；受控实现 pending） | NVDA bounded Agentic Search current canary | F05/F06/F07/F09/F13 + bounded Graph | 先把 metadata route 绑定为 executable request/adapter/source capture/fresh runner；之后 current Runtime 才可实际使用 public/local RAG/SQL/Graph/official route；允许一次受控 fallback；零 false promotion；完整 ToolUse/Evidence lineage |
| S4-T04 | NVDA natural-Case Agentic Research integration | F03/F08/F09/F10/F11/F13 | 自然 Case 从 EvidenceRequest 到 approved pack、judgment、Lead/Writer/Verifier；与 S3 frozen-input 输出分开比较；缺口不被伪装 |
| S4-T05 | DELL/MU transfer 与 post-transfer NVDA | F03/F05/F07/F08 | DELL/MU R2、post-transfer NVDA R2；同一冻结 Runtime；新 L1 按 owner 阻断，不逐字段无限修补 |
| S4-T06 | Workbench current product projection | F01/F02/F04/F06/F09/F11/F13/F15 + Graph | 当前 Case/Run/Evidence/Numeric/Graph/Workpaper/Report/Trace/quality state 在 UI 可审、可回放、可退回；无 fallback 冒充 Agent |
| S4-T07 | Exact Human Review、NVDA R3 与 bounded explanation | F10/F12；F14 nonblocking | qualified reviewer 对 exact digest 接受/退回/repair；NVDA R3；记录 task/review burden；F14 仅做 why/gap/WWC demo |
| S4-T08 | 三案集成收口 | F01–F15 | 逐 feature evidence inventory、三案 regression、已知 gap/owner、成本与 rollback；不得新增模型/检索实现 |

S4 固定 stop rule：每个技术层最多一个合并结构修复包和一个已声明的 replacement canary；新的共同 Runtime 基础缺陷触发同版本项目级处置或 honest block，不创建新产品版本，不在 S4 展开无上限 R 编号。

### S5：Release qualification（固定六项）

| Task | 目标 |
| --- | --- |
| S5-T01 | 冻结 exact candidate、F01–F15 evidence inventory、source/index/model/contract/Case digests |
| S5-T02 | RG1：自然入口到 Runtime、检索、Artifact、Workbench 的 operational replay 与恢复 |
| S5-T03 | RG2：evidence/numeric/authority/citation/false-promotion hard integrity |
| S5-T04 | RG3：三案例 R2、NVDA R3、研究增益与 bounded gaps |
| S5-T05 | RG4：Human task completion、review burden、accept/reject/repair 和产品可用性 |
| S5-T06 | RG5：rollback、成本、安全、secret-safe inventory，并签发 release 或 honest block |

## 7. 后续版本的 S0–S5 统一模板

后续版本不从 S4 直接续做，也不从零重写；每个版本都从自己的 S0 继承上一版本 exact candidate，并围绕新增产品承诺重新证明 S0–S5。

| 版本 | S0 | S1 | S2 | S3 | S4 | S5 |
| --- | --- | --- | --- | --- | --- | --- |
| FIN 0.2 Earnings Review Alpha | 继承 FIN 0.1 candidate，冻结季度/财务源/period schema | 三案两期三表、segment、guidance、同比环比 deterministic truth | Earnings commentary/market reaction/model boundary | 单一 earnings anchor 的 live evidence→workpaper→report | 多公司/季度 transfer、Workbench、Human review | Earnings RG1–RG5 release decision |
| FIN 0.3 Review & Memory Beta | 冻结 correction/supersession/memory authority | deterministic revision、stale、refresh、replay | follow-up/correction 的模型与自动化权限 | 单 Case selective refresh / correction anchor | 多 Case memory reuse、R4、review lifecycle dogfood | Memory/refresh RG1–RG5 |
| FIN 0.4 Cross-sector Beta | 冻结 sector ontology/pack/source policy | SaaS/Bank/Consumer/Industrial deterministic packs | 跨行业 model/skill/graph boundary | 每个新增 sector 至少一个 anchor | 跨 sector transfer、graph/numeric/judgment calibration | Cross-sector RG1–RG5 |
| FIN 0.5 Enterprise Pilot | 冻结 tenant/private source/RBAC/audit contracts | Data Room ingestion/parser/permission deterministic proof | provider/tool/private-data permission boundary | 单 tenant private-data anchor | 多用户/tenant workflow、approval/audit dogfood | Enterprise pilot 与安全运维准入 |

Monitoring、Quant、Multi-format 和 Enterprise Production 继续使用已有 named roadmap，不得暗中塞入 0.1.2 或 0.2。

## 8. 当前执行顺序

Owner 决定已经消费原 S3 入口并推进到：

```text
S3 bounded anchor pass closed
  -> revised S4-T01 natural Case entry / exact binding（pass closed）
  -> S4-T02 retrieval/evidence deterministic readiness（pass closed）
  -> S4-T03 NVDA Agentic Search canary（authority fail-closed；controlled successor pending）
  -> S4-T04 natural-Case Agentic Research / current NVDA R2
  -> S4-T05 ... S4-T08
  -> revised S5-T01 ... S5-T06
  -> FIN 0.2 S0 Earnings entry
```

S3 不再重开。S4 每个技术层仍遵循一个合并结构修复包和一个声明过的 replacement canary 上限；本规划不得被解释为自动 retrieval、paid live、逐字段维修或 current NVDA R2 接受。

## 9. 证据来源

- `docs/product/FIN_0_1_STAGE_REVIEW_20260719.zh-CN.md`
- `docs/product/FIN_0_1_1_INTERNAL_HONEST_BLOCK_BASELINE_FREEZE_20260731.zh-CN.md`
- `docs/product/FIN_PRD_FULL_ABSORPTION_AND_RELEASE_ALLOCATION_MATRIX_20260719.zh-CN.md`
- `configs/releases/fin_ia_0_1_release_contract_v1_3.json`
- `configs/releases/fin_ia_0_1_feature_scope_matrix_v1_1.json`
- `docs/worklog/208_multi_agent_step17_full_chain_real_retrieval_eval.md`
- `reports/retrieval_eval/sec_tech_10k_seed_eval_summary.md`
- `reports/model_runs/20260515_phase1_multifacet_retrieval_eval.md`
- `docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json`
- `configs/releases/fin_ia_0_1_2_s3_nvda_exact_product_input_v1_0.json`
