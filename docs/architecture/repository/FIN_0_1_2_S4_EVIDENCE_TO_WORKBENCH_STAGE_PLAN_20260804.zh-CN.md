# FIN 0.1.2 S4：Evidence-to-Workbench 三案例产品资格计划

日期：2026-08-04

状态：`S4 entered / S4-T01 implementation pending / S4-T02–T08 not started`

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
| S4-T01 | PRD/current Runtime 自然 Case 入口与 exact binding | 用户式 Objective、as-of、预算、三 Cell、current source/index snapshot refs 和 fresh identity 在 DELL/MU/NVDA fixture 中可重建；mutation/cross-case fail closed | 不检索、不调用模型、不生成业务 Artifact |
| S4-T02 | Retrieval/Evidence deterministic readiness | 三案 EvidenceRequest、route、candidate ceiling、metadata、parser/authority、accepted/rejected/gap、citation 由 fixture/mutation 证明 | 不用 live 搜索发现合同问题 |
| S4-T03 | NVDA bounded Agentic Search current canary | 当前 Runtime 实际调用批准的 public/local RAG/SQL/Graph/official routes；零 false promotion；完整 ToolUse/Evidence lineage | 不自动扩大来源或进行 full research |
| S4-T04 | NVDA natural-Case Agentic Research integration | EvidenceRequest→approved pack→Judgment→Lead/Writer/Verifier→九件套；与 S3 frozen-input 对照；完成 source-grounded NVDA R2 产品验收 | 不用 S3 frozen 结果冒充 current source proof |
| S4-T05 | DELL/MU transfer 与 post-transfer NVDA | DELL/MU R2、post-transfer NVDA R2；同一 Runtime；新 L1 按 owner 阻断 | 不逐字段无限修复 |
| S4-T06 | Workbench current product projection | Case/Run/Evidence/Numeric/Graph/Gap/Workpaper/Report/Trace/quality 可审、可回放、可退回 | 不用 fallback 冒充 Agent |
| S4-T07 | Exact Human Review、NVDA R3 与 bounded explanation | qualified reviewer 接受/退回/repair 绑定 exact digest；NVDA R3；记录 review burden | F14 why/gap/WWC demo 不阻断 release |
| S4-T08 | 三案集成收口 | F01–F15 evidence inventory、三案 regression、成本、gap owner 和 rollback 完整 | 不新增模型或检索实现 |

## 4. S4-T01 实现合同

下一项只实现 `fin_0_1_2.S4.natural_case_entry_and_exact_binding:v1`，不得把旧 FIN 0.1 S4 的已完成状态当成当前证明。

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

## 5. 阶段止损与工程纪律

- 每个技术层最多一个合并结构修复包和一个预先声明的 replacement canary；
- fixture 或测试失败留在 owning task 原地修，不创建产品版本；
- available source 的 locator/parser/router/evidence contract 失败属于项目缺陷，不得写成“外部数据缺失”；
- Candidate、Graph hypothesis 和模型叙事不得晋升 Evidence；
- 原始 model-visible request、assistant output、调用参数、usage、terminal phase/code 与 capture ref 必须先耐久保存，凭据和 private reasoning 永不保存；
- paid/live 前必须先过 Project OS full-chain preflight 和对应 deterministic ceiling gate；
- S4-T01 不通过，不得进入 S4-T02；S4-T02 不通过，不得用 S4-T03 live 搜索暴露基础合同问题。

## 6. 当前边界

当前仅完成 S4 entry 与 T01 计划冻结。S4-T01 尚未实现，S4-T02–T08 尚未开始；model、Provider、network、source、tool、admission、Run、Artifact、Human Review 均未发生。current NVDA R2=false，release=false，production=false。

当前 next：

`FIN-0.1.2-S4-T01-NATURAL-CASE-ENTRY-AND-EXACT-BINDING-ZERO-CALL-IMPLEMENTATION`
