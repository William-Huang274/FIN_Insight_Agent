# FIN 0.1.2 S4：Evidence-to-Workbench 三案例产品资格计划

日期：2026-08-04

状态：`S4 entered / S4-T01–T05 pass closed / S4-T06 entry pass、current projection blocked by RC-P36-126、T06-A authorized next / S4-T07–T08 not started`

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
| S4-T04 | NVDA natural-Case Agentic Research integration（已通过并由 Owner 验收关闭） | EvidenceRequest→approved pack→Judgment→Lead/Writer/Verifier→九件套；与 S3 frozen-input 对照；完成 source-grounded NVDA R2 产品验收 | 不用 S3 frozen 结果冒充 current source proof；不以固定 token 上限或删减财务证据换取通过 |
| S4-T05 | DELL/MU transfer 与 post-transfer NVDA（已进入，T05-A 工程通过） | 零调用 transfer package 已把 NVDA-only search/research surface 收敛为 DELL/MU/NVDA closed profile；随后依次 DELL R2、MU R2、post-transfer NVDA R2 | 不复用历史结果冒充当前证明；不逐字段无限修复；新 L1 立即停止剩余 paid sequence |
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

`FIN-0.1.2-S4-T05-B-DELL-FINAL-DELIVERY-GENERIC-CURRENT-CASE-RENDERER-PREVIEW-BINDING-AND-PAIRED-READINESS-ZERO-CALL-DISPOSITION`

R3 exact-live 已 exact-once 成功：9 calls / 9 captures / 3 local Fact receipts / 9 formal Artifacts，input/output=`55,906/3,038`，cost=`USD 0.02696216`，独立 L1 通过，RC-P36-117 live-close。T04 仍不能关闭：最终本地 delivery 暴露内部 scope/period token、重复币种单位并混入英文限制项，且 Verifier 未绑定 final delivery preview；登记 RC-P36-118。该问题属于 T04 产品表面与验收绑定，不属于模型重试事项。后继只允许零调用、有界本地 renderer/preview-binding 处置；不得自动 R4。paired/Owner 与 current NVDA R2 仍未成立，T05 继续 blocked。

上述 RC-P36-118 已通过 R3 immutable Artifact 的零调用重渲染关闭：preview 与 local verifier digest 绑定，内部 token、币种重复和英文限制项清零；三 Cell authority coverage=`3/3`。独立 zero-call baseline 与 Agent 同 input、不同 Run/Artifact，formal paired L1–L4 通过；L3 增益有限但成立。`9/9` WWC 通用阈值措辞作为 RC-P36-119 后传 T08–T10/S5，不阻断 T04、不触发 R4。

用户已明确回复“接受”，因此 current source-grounded NVDA R2=true，S4-T04=`pass_closed_owner_accepted`，S4-T05 entry authorized。该决定不是 qualified Human Review 或 NVDA R3，也没有执行 DELL、MU、post-transfer NVDA 或任何新模型/网络调用。T05 当前只进入 scope decision，必须先复核历史 FIN 0.1 T05/T06 可复用的工程资产与 FIN 0.1.2 必须重新证明的产品边界。

T05 scope audit 已完成：T01/T02 是三案例 current Runtime，而 T03 executable search 与 T04 current-Evidence research 仍是 NVDA-only，因此 DELL/MU 现在不能直接 live。T05 固定为 T05-A 单一零调用三案例 transfer package、T05-B DELL、T05-C MU、T05-D post-transfer NVDA。历史 FIN 0.1 DELL/MU 资产只作代码、fixture、mutation 和失败 taxonomy 回归，不作 current Evidence、R2 或 Owner acceptance。任何新 exact-live L1 立即停止余下 paid sequence，不自动 replacement 或逐字段修补。

## 9. S4-T05-A 实现结果

T05-A 已按 `fin_0_1_2.S4.T05.three_case_current_evidence_transfer:v1` 零调用工程通过。三案使用 closed issuer/source/query/parser profile；SQL adapter 把 metric family、value、unit、period、filed-at 作为 typed numeric 传递，NVDA 展示标题解析仅保留兼容 fallback。current Evidence bridge 对每案产出 `15 Evidence / 3 exact Numeric / 3 typed gaps`，不再使用历史 DELL/MU source pack 作为 current 产品事实。

候选池没有放宽旧 profile，而是新增独立内容寻址的 T05 current-evidence coverage 合同：demand 至少一条本案 issuer demand Evidence；value 同时要求 issuer financial Evidence 与 revenue/gross-profit/operating-income 三条精确 Numeric；bottleneck 至少一条本案 counterevidence；两项本地派生 margin 只是可选上下文，不能替代最低覆盖。

lineage 按既有合法家族分派：DELL/MU 使用 S4 base binding 加 current research-profile overlay，source-grounded slot 精确绑定本案 current Evidence Pack；NVDA 继续使用已通过 T04 的 legacy six-slot lineage。没有为了表面统一而伪造 DELL/MU T06/T07 摘要，也没有把旧 source payload 带入 current input。

三案 full-fake 均达到 `12 Provider callbacks / 9 compiled interactions / 12 raw captures / 9 formal test Artifacts`。最大单请求保守估算 DELL/MU/NVDA 分别为 `19,505 / 16,165 / 19,460`，累计为 `99,031 / 91,725 / 98,528`，既有 108k 编译边界未修改。T05 focused 与状态合同、冻结 NVDA T03/T04、旧候选池与最终 Artifact mutation 合计 `46 passed`；跨案、未来日期、数值、parser lineage、duplicate/overflow、final identity/numeric/lineage mutation 均 fail closed。

T05-A 只建立工程迁移资格。真实 model/provider/source、admission、Run 和业务 Artifact 均为 0；DELL/MU/post-transfer NVDA R2 仍为 false。下一步限定为 DELL fresh zero-call proof 与 admission authority decision；通过前不得执行 DELL source live 或 DeepSeek exact-live，且任何后续 exact L1 仍立即停止余下 paid sequence。

## 10. S4-T05-B DELL Search fresh proof 与权限决策

T05-B 必须拆成 Search 与 Agent 两段。Agent exact input 依赖真实 Search terminal 编译出的 current Evidence Pack，因此不能在 Search live 之前同时签发 Agent admission。固定子序列为：Search fresh proof/authority → Search admission issuance → Search exact-live → current Evidence Pack/Agent exact input → Agent fresh proof/capacity/authority → Agent exact-live/L1/paired/Owner。这是同一 T05-B 内的依赖纠正，不是新版本、阶段跳转或范围扩张。

DELL Search 已在两个独立 disposable root 中零调用通过。两次 normalized 结果一致，Run/Attempt 各自新鲜；三个 Cell accepted/rejected=`6/9、6/0、6/3`，每次 `1` 个模拟官方来源、`6` 次真实本地只读检索、`8` 个 capture、`18` 个 accepted candidate，live source/model/provider/cost/业务 Artifact 均为 `0`。DELL 三份 request digest、CIK=`0001571996`、HTTPS locator、allowlist、candidate ceiling 和 `2 source / 8 local / retry 0 / fallback 1 / 300s / model 0` 预算已精确绑定。

审计同时在 live 前发现 DELL fallback 是直接官方 PDF，而冻结共享 parser 只解析 HTML anchor。该缺口留在 T05-B 并由新的 case-aware runner 以受控后继关闭：只接受官方 HTTPS allowlist、`application/pdf` 与 `%PDF`、可信 `Last-Modified` 且不晚于 as-of；source request/response 仍在解析前 capture。非 PDF、无日期/非法日期、未来日期和跨案 admission 均 fail closed。历史 T03 NVDA runner 与 T05-A immutable bindings 未改写。

DELL Search fresh admission 已原子签发，digest=`b5dd2c46…167f2`，有效期为 `2026-08-04T17:01:00Z–19:01:00Z`；状态严格为 issued/unconsumed/not-started。它绑定三份 DELL request digest、`2 source / 8 local / retry 0 / fallback 1 / 300s / model 0`，并保留 admission 已写但 issuance 中断时仅对 exact payload 的恢复路径。reserved runtime root 仍不存在，source/model/Provider/Run/Artifact 均为 0。DELL current R2 仍为 false。下一项只允许在该单一 runtime root 执行一次 Search exact-live；若来源没有合格结果则保留 typed gap，项目内 adapter/parser/capture/budget failure 则 terminalize 并停止，不自动第二次搜索。RC-P36-115 的跨 runtime 共享消费锁仍留给 S5，不得宣称已全局解决。

## 11. S4-T05-B DELL Search exact-live 结果

唯一 Search admission 已在声明 runtime 中消费并成功 terminalize。Run/Attempt=`s4_t03_search_run_0494f423fd9c9d7571 / s4_t03_search_attempt_c5a9c85cfcf6f8eb4542`，terminal digest=`4e84de38…b0871`，耗时 20.937 秒。实际执行 `1` 次 SEC submissions 官方来源访问、`6` 次本地只读检索、`0` fallback、`0` retry、`0` 模型/Provider/费用，形成 `8` 个 capture、`18` accepted、`12` rejected 和 `0` 业务 Artifact。三 Cell accepted/rejected=`6/9、6/0、6/3`，无 typed gap。

SEC response HTTP 200、157,813 bytes，request/response 均在解析边界完整留存且没有 Authorization、Cookie 或凭据；body SHA 与 content-addressed object 均回算一致。18 条 accepted 全部绑定 DELL、HTTPS、各自 as-of 以内的发布日期以及 source snapshot/parser lineage；9 条无效日期和 3 条超候选上限记录被拒绝且没有晋升。primary SEC 路径成功，因此 direct-PDF fallback 未被调用。

Search success 只证明 gated current candidate pack。所有候选继续保持 `writer_citable=false / domain_judgment=false`，不得直接交给 Writer 或作为金融结论；DeepSeek admission、Agent live、9 Artifacts、L1–L4、paired 与 Owner 均未授权，DELL R2 仍为 false。下一项只做零调用 current Evidence Pack 与 Agent exact input 编译；之后再独立做 Agent fresh proof、capacity 和 admission authority。RC-P36-115 不阻断本次观察到的一次执行，但禁止第二次 Search，并继续阻断 S5/release。

## 12. S4-T05-B DELL current Evidence 与 Agent exact input

唯一 Search terminal 已在不新增外部调用的条件下编译为 `15 Evidence / 3 Numeric / 3 typed gaps`，三 Cell Evidence 覆盖为 `6/3/6`。所有 Evidence 仍绑定 DELL、as-of、HTTPS source、citation、snapshot/parser lineage；Numeric 只接受 revenue、gross profit、operating income 的公司整体 exact authority。未来需求持续性、AI 分部利润归因与独立反证不足继续以 typed gap 表达。

Agent exact input 采用 Evidence Pack 内容寻址身份，不再沿用 regression-oracle ID；source network、external tool、paid execution 和业务 head write 均关闭。最初若直接修改冻结 T05-A 共享编译器，会使旧 immutable result 的 code binding 失效；回归已捕获该问题。最终方案恢复 T05-A 原字节，在 T05-B 建立 controlled successor，纠偏后共享组合回归 `22 passed`。

本项只记 `engineering_pass_zero_call`。Agent admission、DeepSeek live、9 Artifacts、L1–L4、paired、Owner 与 DELL R2 均未成立。下一步只做 Agent fresh zero-call proof、capacity 与 admission authority decision；不得重跑 Search，也不得把本项直接解释为 DELL R2。

## 13. S4-T05-B DELL Agent fresh proof 与 admission

current Agent 合同按 transport-v9 / Lead-v8 编译，正式形态为 `9 Provider calls / 3 local Fact receipts / 9 captures / 9 Artifacts`。T05-A 的 `12 callbacks` 是 compatibility regression 形态，不得倒退成 current live 拓扑。两个 fresh disposable runtime 的完整 payload 等价证明通过；内容寻址 capture ref 因 Run identity 新鲜而不同，已与 payload equivalence 分层校验，未丢弃原始 capture。

九节点估算输入合计 `86,688` tokens，低于 `108,000` 硬边界并保留 `21,312` 余量；最大输出 `10,000`、最大成本 `USD 0.06`、retry=`0`。admission=`de7f118d…3a56` 已签发但未消费，实际环境和 Project OS preflight 均通过。用户已授权通过后执行一次 exact-live；失败时以首个可信 terminal 为准，不自动重试。DeepSeek live、真实 9 Artifacts、独立 L1、paired、Owner 和 DELL R2 仍未成立。

## 14. S4-T05-B DELL Agent exact-live 与独立产品验收

唯一 exact-live 已成功：`deepseek-v4-pro` 9 次调用全部 stop，`3 local Fact receipts / 9 captures / 9 Artifacts`；input/output=`57,739/3,323`，cost=`USD 0.02800749`，retry/第二次 live=`0/0`。capture-first readback、DELL/current input/Evidence lineage、三条 exact Numeric 与 Artifact topology 独立 L1 全部通过。三个 Cell authority coverage 通过；6 Claims、9 WWC、3 dependencies、3 conflicts、3 gaps 已形成，WWC 泛化措辞继续后传 RC-P36-119。

产品 L4 未通过：raw report 仍含内部 scope/period token、重复货币单位和英文 limitation，machine Verifier 未绑定最终本地 preview。T04 的 RC-P36-118 修复只消费 NVDA surface，未成为三案例 case-generic renderer；登记 RC-P36-120，留在 T05-B 做一次零调用泛化、mutation 与 paired readiness，不重跑 DeepSeek。DELL R2、paired、Owner 和 T05-C 仍 blocked。

## 15. S4-T05-B DELL current-case 交付表面与 paired readiness

RC-P36-120 已在零模型条件下关闭。既有 T04 公共入口和冻结 NVDA 输出保持不变；T05 受控后继把同一 renderer 核心限定为 DELL/MU/NVDA closed profile，并同时校验 input/manifest/Artifact/runtime/Numeric/report/preview/verifier 的 current-case identity。DELL 的派生毛利率与营业利润率只在“同 Cell 且已进入已验证 Numeric projection”时可被 WWC 引用，没有放宽 unknown、cross-cell 或 cross-case authority。

DELL immutable exact result 重渲染后，内部 scope/period token、重复币种和未本地化 limitation 均为 0，三 Cell Evidence/authority coverage=`3/3`；preview digest=`46e4766d…291c`，与本地 Verifier、source report 和 source judgment 内容寻址绑定。DELL/MU/NVDA 同一 renderer fixture、跨案/lineage/Numeric/preview/pair mutation 与冻结 NVDA 不漂移 focused=`17 passed`；model/Provider/network/source/exact rerun=`0`。

同 input digest/head 的独立 deterministic authority-inventory baseline 已形成，与 Agent Run/Artifacts 区分，paired readiness=pass；但 formal paired assessment 和 Owner decision 尚未执行，故 DELL current R2=false，T05-C 仍 blocked。下一项为 `FIN-0.1.2-S4-T05-B-DELL-FORMAL-PAIRED-L1-L4-ASSESSMENT-AND-OWNER-DECISION`。RC-P36-119 继续后传 T08–T10/S5，不重开本轮。

## 16. S4-T05-B DELL formal paired 与 Owner gate

正式 paired 已绑定同一 input=`8b00e023…5bae`、同一 input head=`e957d14d…681d`，并确认 Agent/baseline Run 与 Artifacts 均不同，baseline body 未暴露给 Agent。L1/L2/L4 通过；L3 从 authority-only baseline 的 `0/0/0/0/0` 增加至 Agent 的 `6 Claims / 3 dependencies / 3 conflicts / 3 gaps / 9 WWC`，记为有限真实增益。baseline 故意不生成判断，因此该比较不能宣称大幅模型优势；9/9 WWC 泛化继续归 RC-P36-119。

formal assessment=`c86bf7bf…83c4`，推荐 Owner 决定为 `accept_current_DELL_R2_with_RC_P36_119_deferred`。本项没有模型、Provider、网络、Search、baseline rerun 或 exact rerun。Owner 接受尚未发生，所以 DELL R2=false、T05-B closeout 与 T05-C entry 仍 blocked；普通“继续”不得自动改写产品接受。下一项只等待 `USER-OWNER-DECISION-ACCEPT-OR-REJECT-CURRENT-DELL-R2-THEN-CLOSE-T05-B-OR-HOLD`。

## 17. S4-T05-B DELL Owner acceptance 与关闭

用户在完整看见 formal paired 结果、有限 L3 增益、RC-P36-119 finding 及接受/拒绝影响后明确回复“接受”。decision=`a03a1071…6468` 绑定 assessment=`c86bf7bf…83c4`；S4-T05-B=`pass_closed_owner_accepted`，DELL current R2=true，T05-C MU entry authorized/not started。

该接受不关闭 RC-P36-119 或 RC-P36-115，也不建立 MU R2、post-transfer NVDA R2、qualified Human Review、NVDA R3、S4 整体验收、S5、release 或 production。本项没有新模型、Provider、网络、Search、exact-live 或 T05-C Run。下一项仅为 `FIN-0.1.2-S4-T05-C-MU-CURRENT-R2-FRESH-ZERO-CALL-ENTRY-AND-DEPENDENCY-DECISION`，不得直接启动 Search/DeepSeek。

## 18. S4-T05-C MU 入口审计、fresh proof 与 Search admission

用户明确授权按既定 1–5 顺序连续执行，不要求每步重复授权；停止边界仍是入口真实阻断或新的 Agent L1，不包含自动 retry/第二次 Search/第二次 Agent live。

MU 入口审计已完成：case=`MU`、legal name=`Micron Technology, Inc.`、CIK=`0000723125`、as-of=`2026-07-26T00:00:00Z`，SEC primary、Micron 官方 IR fallback、allowlist、三 Cell query、capture-before-parse 和 `2 source / 8 local / fallback 1 / retry 0 / model 0` 均绑定。Micron IR HTML-link parser 以自然日期、allowlisted link 和未来日期边界完成零调用证明；这不是 source-live。

两个 disposable root 的 MU Search proof 各自得到 `1 simulated source / 6 local read-only / 8 captures / 18 accepted / 18 rejected`，Cell accepted/rejected=`6/9、6/6、6/3`，normalized output 一致且 Run/Attempt/terminal identity 全新；model/provider/live source/business Artifact 均为 0。入口与共享回归通过后，MU Search R1 admission 已原子签发、未消费，admission digest=`c40305bd…c037`，issuance digest=`58b19808…80e0`。

当前只建立一次 MU Search exact-live 资格。若 SEC primary 成功，不调用 IR fallback；若官方来源没有合格结果，保留 typed gap；若 adapter/parser/capture/budget 属于项目缺陷，则 terminalize 并停止，不执行第二次 Search。DeepSeek、Agent 9 Artifacts、paired、Owner 和 MU current R2 均未发生。

## 19. S4-T05-C MU current Search、Evidence Pack 与 Agent admission

唯一 MU Search admission 已 exact-once 消费并成功：SEC submissions source live=`1`、本地只读检索=`6`、capture=`8`、accepted/rejected=`18/18`，Cell=`6/9、6/6、6/3`；fallback/retry/model/provider/business Artifact 均为 0。primary 成功，所以 Micron IR 没有被调用。terminal digest=`3f2c0615…f1ff`，Search result digest=`35259ec5…6994`。

current terminal 经 Evidence Gate 编译为 `15 Evidence / 3 exact company Numeric / 3 typed gaps`，Evidence Cell coverage=`6/3/6`。MU current case ID=`fin012-s4-t05-mu-current-evidence-805cc63d45846e9db688`，Evidence digest=`ef1895fe…433d`，Agent input digest=`c15ce68c…e69ec`。历史 MU oracle 只提供合同形状，没有保留其 case identity 或晋升旧事实。

通用 gap code `company_total_numeric_does_not_attribute_AI_segment_profit_capture` 对 MU 的产品措辞不如 `HBM-specific profit attribution` 精确；但它仍然表达“公司整体数值不能证明目标子业务利润”的正确权限边界，没有改变 Evidence/Numeric authority，故作为 L2–L4 wording finding 后传 T08–T10/S5，不阻断 T05-C，也不触发 Search 重跑。

Agent current-case successor 已以三案通用 case parameter 取代 DELL-only exact preparation，但没有修改 DELL immutable module。两个 fresh full-fake root normalized 一致，拓扑=`9 Provider / 3 local Fact / 9 captures / 9 Artifacts`；预计输入=`86,519`、上限=`108,000`、余量=`21,481`，最大单次=`15,693`，USD cap=`0.06`、retry=`0`。MU Agent admission digest=`fbd186e4…3526` 已签发未消费。下一项只执行一次 DeepSeek Pro exact-live；新 L1 立即停止，不自动 retry/replacement。

## 20. S4-T05-C MU Agent exact-live 与独立 L1

唯一 MU Agent admission 已 exact-once 消费并成功。DeepSeek Pro 9 次调用全部 `stop` 且 transport attempt=1，拓扑=`9 Provider / 3 local Fact / 9 captures / 9 Artifacts`；input/output=`56,762/3,162`，estimated cost=`USD 0.02744241`，retry/second live=`0/0`。exact result SHA=`c7bdf239…3602`，terminal digest=`0eaeb000…fcd4`。

独立 readback 重新核对 capture content address、MU identity、current Evidence lineage 和三条 exact Numeric，L1 通过；机器 Verifier 四层自报 pass，Agent 形成 `6 Claims / 9 WWC / 1 dependency / 3 conflicts / 4 gaps`。这说明步骤 1–5 的真实 Search→Evidence→Agent exact-live 已完整跑通。

raw business report 仍含内部 scope/period token、重复币种和英文 limitation；这是 DELL 已证明可由现有三案通用 renderer 零调用清理并绑定 final preview 的产品表面步骤，不是模型 L1，也不需要第二次 DeepSeek。formal paired、Owner acceptance 和 MU current R2 尚未执行，下一项限定为 MU verified product surface 与 paired readiness 的零调用物化。

执行结果落盘后，原 runner 将完整 JSON 打印到 Windows GBK stdout 时因 Unicode bullet 退出 1；immutable result/terminal/Artifacts 不受影响，不重跑 admission。Consumed runner 绑定保持不可变，新增 ASCII-safe 只读 inspector 并回归关闭当前结果的可读性问题；后续共享 CLI hardening 仍应在 S5 统一完成。

## 21. S4-T05-C MU verified product surface 与 paired readiness

以三案例通用 current-case renderer 直接消费 immutable MU exact result，未重跑 Search 或 DeepSeek。最终 analyst preview 已清除 `__company_total__`、`FY2025-FY`、重复币种和英文 limitation；case=`MU`、精确 Numeric、input lineage 与三个研究单元的 Evidence/authority coverage 均重新绑定，本地 Verifier 对 preview digest 完成独立校验。

exact result SHA 保持 `c7bdf239…3602`；surface record=`c9608e31…5272`，preview=`4763544a…973f`，local Verifier=`0dc815a5…5c0c`。同 input/head、不同 execution identity/Artifacts 的 deterministic baseline 已物化，paired readiness=`ready_for_formal_paired_assessment`。MU、DELL、NVDA 共用 renderer 与 cross-case/lineage/numeric/preview/pair mutation 组合回归=`31 passed`；model/provider/network/source/exact rerun=`0/0/0/0/0`。

当前仅能把 L4 final delivery 与 paired readiness 记为 pass。formal paired、Owner acceptance 和 MU current R2 仍未成立；通用 gap wording 与 WWC 可操作性作为 L2–L4 finding 后传 T08–T10/S5，不触发 paid rerun。下一项为 `FIN-0.1.2-S4-T05-C-MU-FORMAL-PAIRED-L1-L4-ASSESSMENT-AND-OWNER-DECISION`。

## 22. S4-T05-C MU formal paired 与 Owner gate

正式 paired 已确认 Agent 与 authority-only baseline 具有相同 input/head、不同 Run/Artifacts，且 baseline body 未暴露给 Agent。L1、L2、L4 通过；L3 从 baseline 的 `0/0/0/0/0` 增加到 Agent 的 `6 Claims / 1 dependency / 3 conflicts / 4 gaps / 9 WWC`，记为有限结构增益，不宣称强 MU 投资 thesis。

本次不能机械照搬 DELL 的数量结论。MU 的 9/9 WWC 都是通用阈值，继续归 RC-P36-119；唯一 dependency、三个 unresolved conflicts 与四个 gaps 主要复述 epistemic state 和待复核状态，新增非阻断 RC-P36-122，后传 T08–T10/S5。两项都不触发第二次 Search/DeepSeek，也不阻断 bounded internal R2，但必须在 Owner 决定里明示。

formal assessment=`2321fd49…0e0f`，推荐 `accept_current_MU_R2_with_RC_P36_119_and_RC_P36_122_deferred`。Owner 未自动代签，所以 MU current R2=false、T05-C closeout 与 T05-D entry 仍 blocked。下一项只等待 `USER-OWNER-DECISION-ACCEPT-OR-REJECT-CURRENT-MU-R2-THEN-CLOSE-T05-C-OR-HOLD`。

## 23. S4-T05-C MU Owner acceptance 与关闭

用户在完整看见 L3 仅为有限结构增益、9/9 WWC 泛化和 Lead 综合偏弱后明确回复“接受”。decision=`70fc169f…5912` 绑定 formal assessment=`2321fd49…0e0f`；S4-T05-C=`pass_closed_owner_accepted`，MU current R2=true，T05-D post-transfer NVDA entry=`authorized_not_started`。

该接受不关闭 RC-P36-119/122，也不证明 strong MU thesis、post-transfer NVDA R2、qualified Human Review、NVDA R3、S4 整体验收、S5、release 或 production。本项没有模型、Provider、网络、Search、exact-live 或 T05-D Run。下一项仅做 `FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-CURRENT-R2-ENTRY-AND-DEPENDENCY-DECISION`，必须先零调用界定 T04 已接受 NVDA 资产的可复用范围和必须重证的 post-transfer 边界。

## 24. S4-T05-D post-transfer NVDA 入口、依赖与零调用全链复证

T03 current Search terminal、8 份 source/raw capture 与 T04 Evidence Pack 均按原 content digest、相同 as-of=`2026-07-21T00:00:00Z` 完整回读；T05 profile 中的 NVDA regression-oracle SHA 也与 Evidence Pack 文件一致。因此 T05-D 复用这份 current source snapshot，不再为迁移验证重跑 Search。旧 T04 exact result 与 Owner acceptance 只作为 pre-transfer 产品锚点，不能替代 post-transfer shared Runtime 的新证明。

入口审计发现一个真正属于 T05-D 的项目兼容缺口：T05-A 有意保留 NVDA legacy six-slot lineage，但 shared exact-execution wrapper 仍硬编码读取 DELL/MU 的 `S4_T04_source_grounded_input`。这会使 post-transfer NVDA 在 Provider 之前失败，即使 T05-A 直接 Agent fake 已通过。RC-P36-123 已以受控修复关闭：按冻结 case-family 选择 `T04_financial_pack` 或 `S4_T04_source_grounded_input`，两条路径仍必须逐字匹配本案 current Evidence digest；没有放宽 identity、Numeric、citation 或 lineage 校验。

新的 current product case/input 已从相同 Evidence Pack 经当前 T05 compiler 重建：case=`fin012-s4-t05-nvda-current-evidence-34ecb73ab7539e5156bd`，input=`75fa19a8…9216`。两个独立 fresh temporary Runtime 均通过 input preparation、9-call capacity compiler、capture/terminal 物化与 9 Artifact assembly；normalized result 完全一致，拓扑=`9 Provider callbacks / 3 local Fact receipts / 9 captures / 9 Artifacts`，预计输入=`85,614/108,000`、最大单次=`15,678`、余量=`22,386`。聚焦和 DELL/MU/T05-A 相邻回归=`18 passed`。

本项只建立 Search reuse、current input 和 zero-call engineering reproof。新增 source/model/Provider/admission/exact-live/业务 Artifact 均为 0，post-transfer NVDA R2=false。下一项限定为 `FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-FRESH-AGENT-PROOF-CAPACITY-AND-ADMISSION-AUTHORITY-DECISION`：独立重验当前 input/code/fresh identity、Project OS 与预算后，才可决定是否签发最多一次 post-transfer DeepSeek exact-live。RC-P36-119/122 继续后传 T08–T10/S5；qualified Human Review、NVDA R3、Workbench、S5、release 和 production 不属于 T05-D。

## 25. S4-T05-D post-transfer NVDA fresh proof、容量与 admission 签发

独立 fresh proof 重新验证 current input=`75fa19a8…9216`、当前代码 digest、T03 terminal/T04 Evidence lineage、Project OS open blocker 和目标 identity 不存在。两个 disposable Runtime 的归一化结果相同，每套拓扑=`9 Provider callbacks / 3 local Fact receipts / 9 captures / 9 Artifacts`；9 次预计输入合计=`85,614/108,000`，最大单次=`15,678`、余量=`22,386`。

唯一 admission=`0bdf1ba…f55b` 已绑定 execution identity=`fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1` 并签发；issued/consumed/started=`true/false/false`。runner 零调用预检确认凭据存在且不输出/持久化值，transport retry=`0`，聚焦与 DELL/MU 相邻回归=`10 passed`。本项 source/model/Provider/network/business Artifact 仍为 0。

下一项只允许 `FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-AGENT-EXACT-LIVE-EXECUTION`：最多 9 次 DeepSeek Provider call、0 retry、0 source network、0 external tool、USD 0.06。首个可信失败即停止且不得自动第二次 live。成功也只进入 immutable result 物化和独立 L1；formal pair、Owner acceptance、Human Review/R3、S5、release 与 production 不自动成立。

## 26. S4-T05-D post-transfer NVDA Agent exact-live 与独立 L1

唯一 admission 已消费并成功完成。DeepSeek `deepseek-v4-pro` 产生 `9 calls / 3 local Fact receipts / 9 captures / 9 Artifacts`，全部 stop/attempt=1；input/output=`55,060/3,148`，cost=`USD 0.02668987`，retry/第二次 live=`0/0`。terminal=`bc7a78a7…eb93`，exact result SHA=`200907cf…bbc4`。

独立只读物化重新核对全部 capture digest、NVDA identity、input/current Evidence lineage 和三条 exact Numeric，L1 通过；Agent 形成 `6 Claims / 9 WWC / 1 dependency / 2 conflicts / 4 gaps`。raw report 仍包含内部 scope/period token、重复 USD 和英文 limitation，它们归零调用 L4 renderer，不触发 paid rerun。

当前 post-transfer NVDA R2 仍=false，下一项仅为 `FIN-0.1.2-S4-T05-D-NVDA-VERIFIED-PRODUCT-SURFACE-AND-PAIRED-READINESS-ZERO-CALL`。formal pair、Owner acceptance、Human Review/R3、S5、release 与 production 均未执行。

## 27. S4-T05-D NVDA verified product surface 与 paired readiness

immutable exact result=`200907cf…bbc4` 经现有 DELL/MU/NVDA 通用 renderer 零调用形成 final preview=`092e0f59…9fab`，内部 scope/period token、重复币种和英文 limitation 均清零；local Verifier=`57bc4849…8aed` 与 preview、source report、judgment 和 NVDA identity 绑定，三 Cell Evidence/authority coverage=`3/3`。

不同 execution identity/Artifacts 的 deterministic authority-inventory baseline=`891e00a5…45df` 与 Agent 使用相同 input/head；paired readiness=`a825f345…56ea / ready_for_formal_paired_assessment`。三案 renderer、跨案、legacy lineage、Numeric、preview/verifier、pair mutation 与 current Evidence 回归=`45 passed`，新增 model/provider/network/source/exact rerun=`0`。

首轮共享回归暴露测试误用 DELL/MU runtime overlay；没有给 NVDA legacy Artifact 补假字段。进一步审计关闭 RC-P36-124：通用产品表面在处理三案前重算 input canonical digest，防止 body 已变但声明 digest 未更新；正常三案输出不漂移，NVDA legacy lineage stale-digest mutation 在渲染前 fail closed。

当前 T05-D final delivery 与 paired readiness=pass，但 formal paired、Owner acceptance 和 post-transfer NVDA R2 仍未成立。下一项为 `FIN-0.1.2-S4-T05-D-NVDA-FORMAL-PAIRED-L1-L4-ASSESSMENT-AND-OWNER-DECISION`；RC-P36-119 后传 T08–T10/S5，RC-P36-122 保持 MU-specific，RC-P36-115 继续阻断 S5/release。

## 28. S4-T05-D NVDA formal paired 与 Owner gate

正式 paired 已确认 Agent 与 authority-only baseline 使用相同 input/head、不同 Run/Artifacts，且 baseline body 未暴露给 Agent。L1、L2、L4 通过；L3 从 baseline 的 `0/0/0/0/0` 增加到 Agent 的 `6 Claims / 1 dependency / 2 conflicts / 4 gaps / 9 WWC`，记为有限结构增益，不宣称 strong NVDA thesis 或 R3。

9/9 WWC 仍使用通用阈值，归 RC-P36-119。独立语义审阅发现：唯一 dependency 主要枚举六个 claim 的 epistemic state；两个 conflict 均 unresolved；四个 gap 中两个指向已是 fact-supported 的 claim。该形态与 MU RC-P36-122 同源，因此新建跨案例 RC-P36-125，吸收其后续质量校准范围；RC-P36-122 保留为 MU 首次触发的历史记录。RC-P36-125 后传 T08–T10/S5，不重开 T05-C/T05-D，也不触发第二次 paid run。

formal assessment=`ff93cea5…4f21`，三案例 formal pair、MU/NVDA product surface 及 mutation regression=`35 passed`；model/provider/network/source/exact rerun=`0`。推荐 Owner 决定为 `accept_post_transfer_NVDA_R2_with_RC_P36_119_and_RC_P36_125_deferred`，仅代表 bounded internal post-transfer R2，不代表 strong thesis、Human Review、NVDA R3、S4 整体验收、release 或 production。Owner 尚未签署，因此 post-transfer NVDA R2=false，T05-D closeout 与 S4-T06 entry 仍 blocked；下一项只等待 `USER-OWNER-DECISION-ACCEPT-OR-REJECT-POST-TRANSFER-NVDA-R2-THEN-CLOSE-T05-D-OR-HOLD`。

## 29. S4-T05-D NVDA Owner acceptance 与关闭

用户在完整看见 formal pair 的有限 L3 增益、RC-P36-119 与跨案例 RC-P36-125 以及接受/拒绝影响后明确回复“接受”。decision=`4e15a44d…7a9d` 精确绑定 assessment=`ff93cea5…4f21`，S4-T05-D=`pass_closed_owner_accepted`，post-transfer NVDA R2=true；至此 T05 的 DELL/MU/post-transfer NVDA 三案例 current-R2 transfer 均完成各自 engineering、current Evidence、Agent exact-live、L1–L4 paired 和显式 Owner gate。

接受仅覆盖 bounded internal post-transfer NVDA R2。RC-P36-119/125 继续后传 T08–T10/S5，RC-P36-122 保留为历史 MU trigger，RC-P36-115 仍阻断 S5 release hardening；strong NVDA thesis、qualified Human Review、NVDA R3、S4 整体验收、S5、release 和 production 均未成立。本项 model/provider/network/source/exact-live/T06 Run=`0`，Owner 语义、非接受消息、T06 未启动和 release boundary mutation=`6 passed`。

S4-T06 entry=`authorized_not_started`。下一项限定为 `FIN-0.1.2-S4-T06-WORKBENCH-CURRENT-PRODUCT-PROJECTION-ENTRY-AND-DEPENDENCY-DECISION`：先零调用审计当前 Case/Run/Evidence/Numeric/Graph/Gap/Workpaper/Report/Trace/quality 资产能否诚实投影到 Workbench，以及历史 UI/后端哪些必须重证；不得把 fallback、fixture 或旧历史 Run 冒充 current product，也不得直接启动模型、Source 或 paid full-chain。

## 30. S4-T06 Workbench current product projection 入口与依赖决策

零调用资产盘点确认 T05 已提供三案例 current product anchor：合计 `45 Evidence / 9 Numeric / 9 typed gaps / 27 business Artifacts / 3 Owner acceptances`，每案均有 current Evidence Pack、成功 exact result、verified final surface 和显式 R2 acceptance。现有 Workbench 也不是空白：已有 Case/Task Center、Execution/Run、Evidence、Numeric/Workpaper、Deliverable/Trace API 和对应 React components。

但这些两端尚未连接。`CaseService` 的正式注释和构造入口都限定为 internal fixture，默认没有 `FINSIGHT_P02_FIXTURE_ROOT` 即 unavailable；`EvidenceService` 继续消费 zero-call fixture contract；前端默认 principal 仍为 `fixture_internal`。没有 service 将三案 T05 Evidence Pack、exact result、final surface、quality finding 与 Owner decision 内容寻址绑定成 current read model。登记 RC-P36-126，属于 T06 project-owned product projection gap，不是 DeepSeek、Provider 或数据来源问题。

Graph 必须按当前事实投影：三个 approved Evidence Pack 都没有已晋升 Graph Evidence，因此 T06 显示 `typed_empty_no_approved_current_graph_evidence`；不得读取 raw candidate 后补边，也不得把 graph snapshot 存在误写成 graph Evidence 已成立。raw Provider capture 只保留审计引用，永不进入产品正文。

选择性入口回归同时得到 `44 passed / 10 failed`。10 项均是旧 Evidence/VT2/VT3 fixture 链要求 WorkUnit 保持 `pending`，而 2026-07-31 后默认 `create_app` 已自动挂接共享 runtime 并在后台把它执行为 `succeeded`；默认模式随后 compile=409，显式 no-runtime 则 pending/202。登记 RC-P36-127，属于历史 fixture/runtime-mode 合同漂移，不是 T05 current asset、DeepSeek 或 Provider 失败。

T06 被有界拆为三个包：T06-A 只做三案 `CurrentProductProjectionManifest`、只读 compiler/service/API，不修 RC-P36-127；T06-B 做 frontend current mode、current/fixture runtime-mode 隔离、RC-P36-127 收敛和 browser/cross-case mutation；T06-C 只做 typed return/request-repair envelope、replay 与 T07 handoff readiness，不执行 qualified Human Review。RC-P36-119/125 留在 T08–T10/S5，RC-P36-115 留在 S5；不得回塞 T06-A。

decision=`55d06706…5527`，SHA=`941bc7c6…de3b`，mutation=`6 passed`，model/provider/network/source/tool/runtime-write=`0`。当前只能声明 T06 entry=pass；T06 engineering/product projection 仍 blocked。下一项为 `FIN-0.1.2-S4-T06-A-THREE-CASE-CURRENT-PRODUCT-PROJECTION-MANIFEST-READ-ONLY-SERVICE-AND-API-ZERO-CALL-IMPLEMENTATION`。
