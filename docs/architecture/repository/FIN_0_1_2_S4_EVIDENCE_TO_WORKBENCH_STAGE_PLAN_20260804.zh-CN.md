# FIN 0.1.2 S4：Evidence-to-Workbench 三案例产品资格计划

日期：2026-08-04

状态：`S4 entered / S4-T01–T03 pass closed / S4-T04 engineering pass，R1/R2 immutable failed，RC-P36-117 zero-call repaired，fresh R3 exact-live pending / S4-T05–T08 not started`

## 1. S4 为什么现在可以进入

Owner 已批准消除 S3/S4 的循环门禁。S3 以“有限 frozen-input Runtime 与 verified delivery anchor”通过并关闭；它仍不等于 source-grounded NVDA R2。当前 `0/3` promoted Evidence 不会被改写、降级或伪造，而是按原 PRD owner 转入 S4-T02、T03、T04。

S4 的任务不是再修一遍 S3 模型链，而是补齐自然用户 Case、真实 public/local 检索、Evidence Gate、Agentic Research、Workbench 和 Human Review，使 FIN 0.1 的 F01–F15 形成当前版本产品证据。

## 2. 产品出口

S4 只有在以下结果同时成立时才能关闭：

- 自然用户 Objective、as-of、预算、三 Cell、source/index snapshot 和 exact identity 可重建；
- DELL、MU、NVDA 使用当前同一 Runtime，Evidence/ Numeric/Graph/Claim/Artifact lineage 可审计；
- NVDA 在自然 Case 和当前 Agentic Search 后达到 source-grounded R2；
- DELL、MU 达到 R2，post-transfer NVDA 重新达到 R2；
- 当前 Workbench 可回放 Case、Run、Evidence、Gap、Workpaper、Report、Trace 和质量状态；
- qualified Human Review 绑定 exact digest，NVDA 达到 R3；
- F01–F15 inventory、成本、rollback 和剩余 gap 完整，才有资格进入 S5。

## 3. 固定任务序列

| Task | 本阶段只解决什么 | 通过条件 | 明确不做 |
| --- | --- | --- | --- |
| S4-T01 | PRD/current Runtime 自然 Case 入口与 exact binding（已通过） | 用户式 Objective、as-of、预算、三 Cell、current repository source/index snapshot refs 和 fresh identity projection 在 DELL/MU/NVDA fixture 中可重建；mutation/cross-case fail closed；snapshot 明确不是 current Evidence | 不检索、不调用模型、不生成业务 Artifact |
| S4-T02 | Retrieval/Evidence deterministic readiness（已通过） | 三案 EvidenceRequest、route、candidate ceiling、metadata、parser/authority、accepted/rejected/gap、citation 由 fixture/mutation 证明；历史 source pack 与 2026-06-11 index snapshot 完成 freshness/reachability 处置；RC-P36-113 已关闭 | 不用 live 搜索发现合同问题 |
| S4-T03 | NVDA bounded Agentic Search current canary（已通过并关闭） | 当前 Runtime 实际调用批准的 public/local RAG/SQL/Graph/official routes；零 false promotion；完整 ToolUse/Evidence lineage | 不把 metadata route、state stub 或 URL wrapper 冒充真实检索，不自动扩大来源或进行 full research |
| S4-T04 | NVDA natural-Case Agentic Research integration（工程通过，产品 exact-live 待复证） | EvidenceRequest→approved pack→Judgment→Lead/Writer/Verifier→九件套；与 S3 frozen-input 对照；完成 source-grounded NVDA R2 产品验收 | 不用 S3 frozen 结果冒充 current source proof；不以固定 token 上限或删减财务证据换取通过 |
| S4-T05 | DELL/MU transfer 与 post-transfer NVDA | DELL/MU R2、post-transfer NVDA R2；同一 Runtime；新 L1 按 owner 阻断 | 不逐字段无限修复 |
| S4-T06 | Workbench current product projection | Case/Run/Evidence/Numeric/Graph/Gap/Workpaper/Report/Trace/quality 可审、可回放、可退回 | 不用 fallback 冒充 Agent |
| S4-T07 | Exact Human Review、NVDA R3 与 bounded explanation | qualified reviewer 接受/退回/repair 绑定 exact digest；NVDA R3；记录 review burden | F14 why/gap/WWC demo 不阻断 release |
| S4-T08 | 三案集成收口 | F01–F15 evidence inventory、三案 regression、成本、gap owner 和 rollback 完整 | 不新增模型或检索实现 |

## 4. S4-T01 实现合同与结果

`fin_0_1_2.S4.natural_case_entry_and_exact_binding:v1` 已完成零调用实现，不得把旧 FIN 0.1 S4 的已完成状态当成当前证明。

### 输入

- 用户式 `objective`，不得是内部 fixture 指令；
- `as_of` 与 freshness policy；
- case identity、ticker/company 和三 Cell objective；
- source snapshot 与 index snapshot 的内容寻址引用；
- 模型、source、tool、token、cost 和 wall-clock 预算引用；
- fresh WorkUnit / Attempt / ResearchRun identity seed。

### 输出

- `NaturalCaseEntryRequest`；
- `CurrentCaseRuntimeBinding`；
- `SourceIndexSnapshotBinding`；
- `ExactExecutionIdentityProjection`；
- 一份不含 Evidence 内容的 `S4T01EntryReceipt`。

### 零调用验收矩阵

- DELL、MU、NVDA 三案正向 fixture；
- objective、as-of、ticker/company、Cell、source snapshot、index snapshot、budget 和 identity mutation；
- cross-case contamination、重复 identity、unknown snapshot、stale/unbound head；
- permutation 后 digest 稳定；
- current Runtime consumer 确实读取 binding，而不是只存在于文档或 registry；
- model / Provider / execution network / source network / external tool / business Artifact 均为 0。

### 实现结果

- current Runtime consumer：`apps/workbench/backend/application/fin_0_1_2_s4_natural_case_entry.py`；
- authority：`configs/runtime/fin_ia_0_1_2_s4_t01_natural_case_entry_authority_v1_0.json`；
- isolated registry：`configs/runtime/fin_ia_0_1_2_s4_t01_runtime_resource_registry_v1_0.json`；
- DELL/MU/NVDA 分别生成 `NaturalCaseEntryRequest / CurrentCaseRuntimeBinding / SourceIndexSnapshotBinding / ExactExecutionIdentityProjection / S4T01EntryReceipt`；
- focused=`15 passed`，S1/S3/S4 relevant regression=`71 passed`；
- receipt 只含 ref、digest、bytes、typed state 和零调用计数，不读取或返回 Evidence/Numeric/Claim 内容；
- 历史 DELL/MU source pack、S3 NVDA manifest 与 2026-06-11 public index summary 只作为 entry snapshot。它们不是 current Evidence，freshness、company-specific reachability、parser 与 promotion 必须在 T02 重验。

组合审计另复现一个本轮前已存在的共享问题：默认 S0 Runtime resource detector 已能看到 S3 新增的 fact-candidate profile literal，但默认 registry 未登记该资源，相关历史测试为 `44 passed / 2 failed`。登记 `RC-P36-113`；它不否定 T01 isolated registry/readback，但必须在 S4-T03 paid canary 前由 T02 的 pre-T03 prerequisite 关闭，不能拖到 live 才发现。

## 5. S4-T02 实现结果

T02 已以合同 `fin_0_1_2.S4.three_case_retrieval_evidence_deterministic_readiness:v1` 零调用通过并关闭。current Runtime 对每案生成三个 `RetrievalEvidenceRequest` 和确定性 route plan，逐候选检查 case/as-of、source snapshot、HTTPS citation、parser adapter、route receipt、authority 与 ceiling，并只返回元数据、资格决定、citation projection 和 typed gap；原始 statement 与数值内容不进入 readiness 输出。

- DELL：历史 fixture `2 accepted / 8 rejected / 2 citations / 0 promoted`；
- MU：历史 fixture `13 accepted / 1 rejected / 13 citations / 0 promoted`，唯一拒绝是显式 ceiling overflow；
- NVDA：manifest-only，`0/0/0/0`，保留 demand、counterevidence、value 三个 `current_*_search_required` gap；
- shared public index 只证明 catalog 可寻址，as-of=`2026-06-11`，对当前 Evidence 判为 stale；
- focused 与默认 registry 合并回归=`29 passed`，连同 T01、M6 主链和历史 successor 兼容回归=`93 passed`；RC-P36-113 通过原子补登 S3 profile、保持 unknown-resource fail-closed 并完成 readback 后关闭；
- model、Provider、execution/source network、tool、retrieval、store write、business Artifact 均为 0。

这意味着“检索与 Evidence 资格判断的管道已准备好”，不意味着已经执行 RAG/Agentic Search。DELL/MU 历史包只用于 parser/citation/readiness 回归；NVDA 当前证据仍不存在，必须由 T03 的受控 current canary 获取。

## 6. S4-T03 authority decision 结果

T03 的零调用权限审计已经完成，但 current canary 必须 fail closed。首个可信阻断不是 DeepSeek、Provider 或外部数据，而是项目内执行集成缺口：T02 的四个 metadata route ID 尚未绑定任何 Python executor；三份 NVDA request 没有不可变 query、source locator、allowlist、adapter snapshot 或 parser binding；本地 retrieval skeleton 故意不调用 adapter，LangGraph 默认 retrieval path 仍为 `state_stub`；现有 web snapshot 只包装给定 URL 为 `context_only` metadata，不执行下载；来源 request/response 的 capture-before-parse、fresh identity、issuer、runner 与 terminal result 也尚不存在。

因此本次 authority scope=`pass`，canary execution authority=`fail_closed`，admission=`not issued`。登记 `RC-P36-114`，仍归 S4-T03，不转给 T04，也不创建新产品版本。唯一后继是一个零调用合并实现包：补齐 `ExecutableSearchRequest`、metadata-to-executable adapter registry、只读 BM25/object-BM25、Graph、exact SQL 和受控 SEC/issuer adapter、来源 request/response 原子留存、fresh canary envelope/issuer/runner/typed terminal result。实现通过后才能另做 admission；T03 只可生成经过 gate 的 current Evidence candidate，仍不得 writer-citable、进入 Judgment 或生成业务 Artifact。

### Controlled successor 实现结果

上述唯一零调用包已经完成并通过。三份 request 现具有精确 query/source/allowlist/adapter/parser/as-of；四个 metadata route 唯一绑定到 SEC filing identity、NVIDIA IR 单一 fallback、只读本地 BM25、relationship graph 与 exact-value SQL。source request/response 在 parse 前保存，本地 raw rows 在 projection 前保存，所有对象内容寻址并 readback；success、typed gap、project failure 都生成 terminal result。

fresh zero-call proof 使用模拟 SEC identity response 与真实本地索引/SQLite，得到三 Cell accepted/rejected=`6/10、6/0、6/3`，source simulated/live=`1/0`，local invocations=`6`，capture=`8`，retry/fallback/model/provider/Artifact=`0/0/0/0/0`；focused/related=`16/59 passed`。关系图缺少 source publication date 的行被拒绝，没有把 graph build time 冒充 evidence time。RC-P36-114 因执行集成结构已证明而关闭，但 live 来源与产品证据质量仍未证明。

## 7. 阶段止损与工程纪律

- 每个技术层最多一个合并结构修复包和一个预先声明的 replacement canary；
- fixture 或测试失败留在 owning task 原地修，不创建产品版本；
- available source 的 locator/parser/router/evidence contract 失败属于项目缺陷，不得写成“外部数据缺失”；
- Candidate、Graph hypothesis 和模型叙事不得晋升 Evidence；
- 原始 model-visible request、assistant output、调用参数、usage、terminal phase/code 与 capture ref 必须先耐久保存，凭据和 private reasoning 永不保存；
- paid/live 前必须先过 Project OS full-chain preflight 和对应 deterministic ceiling gate；
- S4-T01 不通过，不得进入 S4-T02；S4-T02 不通过，不得用 S4-T03 live 搜索暴露基础合同问题。
- T04 每节点请求必须在 admission 前编译容量；完整本地审计/验证对象与模型可见视图分离，压缩只允许消除重复投影，不允许丢弃重要 Fact、反证、scope、qualification、WWC 或 Writer 成品映射。

## 8. 当前边界

当前 S4-T01、T02、T03 已通过并关闭。T03 唯一 live canary 以 1 次 SEC 官方来源访问和 6 次本地只读调用形成三个 Cell 各 6 条的 current candidate pack；0 retry、0 fallback、0 模型/Provider、0 业务 Artifact，完整 source capture 与 terminal 已回读验收。

S4-T04 已完成 current Evidence pack、Agent 输入桥、三案例 full-fake 与零调用工程验收。R1 因项目内 CJK local-ID numeric classifier 假阳性失败；修复后 R2 的九次 DeepSeek Pro 输出均 `stop` 且 JSON valid，RC-P36-116 live-close，但在 Verifier capture 后因固定 60k aggregate input ceiling 以 RC-P36-117 terminal failed。R1/R2 均保持 immutable，诊断 replay 不晋升业务 Artifact。

RC-P36-117 现已完成结构处置：完整本地 payload 继续作为审计和校验权威；Verifier 模型视图保留六 Claim 的事实/边界、scope、qualification、WWC、Writer rendering 和完整 Lead，只移除重复 numeric/identity/runtime 投影。R2 capture 重编译将 Verifier 保守估算从 31,296 降至 20,224；全链估算 91,527，编译上限 108,000，余量 16,473，且仍低于 USD 0.06 推导的成本绝对上限。共享 runner 改读 execution envelope，历史 60k envelope 未改。S4-T04 仍不是产品通过，current NVDA R2=false，release=false，production=false。

当前 next：

`FIN-0.1.2-S4-T04-FINAL-DELIVERY-RENDERER-AND-VERIFIER-PREVIEW-BINDING-ZERO-CALL-DISPOSITION`

R3 exact-live 已 exact-once 成功：9 calls / 9 captures / 3 local Fact receipts / 9 formal Artifacts，input/output=`55,906/3,038`，cost=`USD 0.02696216`，独立 L1 通过，RC-P36-117 live-close。T04 仍不能关闭：最终本地 delivery 暴露内部 scope/period token、重复币种单位并混入英文限制项，且 Verifier 未绑定 final delivery preview；登记 RC-P36-118。该问题属于 T04 产品表面与验收绑定，不属于模型重试事项。后继只允许零调用、有界本地 renderer/preview-binding 处置；不得自动 R4。paired/Owner 与 current NVDA R2 仍未成立，T05 继续 blocked。
