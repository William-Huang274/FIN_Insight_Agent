# FIN 0.1 S1–S5 阶段边界重审与任务归属重基线

日期：2026-07-31
状态：`accepted_audit / T05_T06_T07_honestly_blocked_closed / T08_T09_complete / T10_scope_frozen / repository_recovery_and_version_lineage_supersession_current`

机器合同：`configs/releases/fin_ia_0_1_s1_to_s4_t06_stage_boundary_and_task_ownership_rebaseline_v1_0.json`

> [!IMPORTANT]
> **2026-07-31 版本谱系 supersession**：本文件和既有 T10 scope 中把 common contract compiler、Provider surface reduction、DELL/MU reproof 和 Verifier 基线归入 `FIN 0.2` 的部分，现只保留为历史阶段处置。经 PRD allocation 复核，这些是 FIN 0.1 未完成的通用质量承诺，当前 owner 改为 `FIN 0.1.2`；`FIN 0.2` 恢复并保持原定义 `Earnings Review Alpha`。S4 honest-block 真值不变，T05/T06/T07 不重开。当前先执行 repository evidence freeze 与安全分类，再完成 T10/S5 decision-only 和 0.1.1 internal baseline。权威说明见 `docs/product/FIN_0_1_1_0_1_2_VERSION_LINEAGE_AND_RELEASE_CADENCE_DECISION_20260731.zh-CN.md`。

> 2026-07-31 T07 执行增量：唯一 current-worktree 零调用回归 package 已消费，结果 `93 passed / 4 failed`。当前 compiled Runtime 的 DELL/MU/NVDA `6/12/12/9`、Fact/Claim/WWC、数值/身份/日期/lineage mutation、capture 与 terminal result 均在 package 内通过；四个失败分别来自两个未携带后来强制 safety policy refs 的旧 S4-T03 fixture admission，以及两个把 immutable 实现记录耦合到 mutable program `current_next` allowlist 的历史状态测试。未建立新金融 L1 或当前 Runtime 回归，但冻结规则禁止修 fixture 后重跑，因此 T07 以 honestly blocked 关闭，NVDA exact-live 未授权、未执行，R3 candidate 未生成。legacy fixture/status baseline 治理进入 S5；下一项为 T08 只读校准。

> 2026-07-31 T08 执行增量：10 份 immutable evidence 已做只读三案校准。NVDA 历史 S3 R2 owner accepted；DELL/MU 的完整九 Artifact paired 结果都显示 Agent actionability/cross-cell gain，但均因 Numeric authority、case identity 与 machine Verifier false negative 而 L1 fail，R2 未证明。三条完整成功 Run 合计 `36 calls / 212,618 tokens / USD 0.08207367 / 27 Agent Artifacts`，accepted 仅 NVDA 9 Artifacts。Workbench trace/debug 价值已证明，task time/continue-use 未测量，edit burden/trust 仅定性。T08 只读任务通过，但 S4/FIN 0.1 仍未通过；下一项为真实 Human T09 scope/eligibility decision。

> 2026-07-31 T09 scope 增量：Owner evidence review 已判定 eligible；qualified-senior NVDA R3 因无 post-transfer exact product/current R3 candidate/真实 senior binding 而 ineligible。六项 owner findings 与 A/B/C disposition packet 已冻结，所有 Human 字段为空，“继续”不推定 acceptance。当前等待真实 Owner 明确选择；T10 未进入。

> 2026-07-31 T09 Owner disposition 增量：真实 Owner 明确选择 A，接受六项 findings、争议 0，并建议 T10 honest block。该记录不是 DELL/MU product acceptance 或 NVDA R3；S4/FIN 0.1 仍未通过。T09 终态关闭，下一项为 T10 pass-or-honest-block closeout scope decision。

## 1. 为什么必须重审

最初的 S1–S5 计划假设：先接通一个 Cell，再证明一个真实 Cell，再扩到 NVDA 三 Cell，最后把同一链迁移到 DELL/MU 并进入 release candidate。这个方向是正确的，但低估了金融 Agent 的三个现实：

1. 模型不仅会在“分析质量”上波动，也会在数量、引用、日期、身份、数值叙事和跨字段状态机上偏离合同；
2. prompt、wire schema、validator、fake Provider、selector、renderer、预算和 telemetry 如果不是同一合同源，会在长链中逐层漂移；
3. fake/full-fake、fresh proof、exact-live、paired assessment 和 release reproducibility 是不同证明，不能都塞进一个 Case 任务。

结果是，原本只负责 MU R2 的 T06 被动吸收了 Provider qualification、Runtime truth ownership、合同编译、审计 capture、候选池规划和 proof harness。继续让 T06 承担这些工作，会把“在哪次 live 发现”错误地当成“归哪个任务负责”。

本次重审不降低 L1，也不为了省事放行失败产品。它把问题放回正确阶段，并允许当前版本诚实地以 blocked candidate 收口。

## 2. 当前 Agent 链路已经具备什么

当前产品主链已经不是 demo prompt。它能够完成：

`Workbench -> Fin01ResearchRuntime -> WorkUnit/Attempt/Run -> 三位 Specialist -> Research Lead -> Writer -> Verifier -> 九 Artifact -> paired review`

具体能力包括：

- 一个统一 Runtime 和显式 execution profile；
- exact Case、DecisionSurface、Evidence、Numeric、Graph context 和 lineage；
- 三个 Cell 的 Fact、Claim、What-Would-Change 分段研究；
- 六个逻辑节点、十二次 Provider 调用和九类业务 Artifact；
- retry-zero、exact-once admission、receipt、restricted capture、typed terminal truth；
- 本地确定性生成 canonical ID、case identity、重要数值、日期、task、manifest 和 trace lineage；
- 同输入 deterministic baseline、L1–L4 分层评估和 owner acceptance；
- DELL、MU、NVDA 三案例的 current-worktree full-fake `6/12/12/9`。

但成熟度必须精确描述：

| 阶段 | 已证明 | 没有证明 |
| --- | --- | --- |
| S1 | fixture-shadow 主链和失败真相 | 真实模型质量 |
| S2 | 一个 Cell 的真实 Agent、九 Artifact 和 owner 增益 | 三 Cell 与跨案例 |
| S3 | NVDA 三 Cell coherent product、paired、owner accepted R2 | DELL/MU 迁移 |
| S4-T01–T04 | DELL/MU Case Pack、方法合同、source grounding、三案 fixture | paid product acceptance |
| S4-T05 | DELL full Runtime 与 Agent actionability | DELL R2、L1、owner acceptance |
| S4-T06 | MU full Runtime、一次九 Artifact 成功、paired 能正确拒绝 L1；大量本地 truth owner | MU R2、稳定 transfer-safe live、owner acceptance |
| S5 | 尚未开始 | hermetic candidate、RG1–RG5、rollback、release |

因此，当前产品是“有一个 owner-accepted anchor、两个真实 transfer diagnostic、较强工程审计能力的内部工程 Alpha”，不是三案例 release-qualified Agent。

## 3. 一路以来的问题不是几十个互不相关的 bug

历史失败可归并为五类：

### 3.1 Provider truth ownership 过宽

模型曾被要求直接生成或复述重要数值、日期、身份、canonical ID、cardinality 和 lineage。金融 Agent 对这些字段需要确定性 owner；仅在 prompt 中写“不要超过”“只能使用”不足以成为 L1 基础。

当前已实现的本地 owner 应保留，但全面收缩所有 Provider surface 是 FIN 0.2 架构任务，不再进入 T06。

### 3.2 跨层合同不是同源编译

已经出现过：

- output-v4 prompt 与 validator schema 漂移；
- S3/S4 lineage family 漂移；
- Provider candidate maximum 与 local final maximum 混用；
- Claim 状态规则存在于 selector，却没有进入 model-visible contract；
- fake Provider 能通过，但自然输出失败。

局部共享 policy 已经缓解问题，完整 contract compiler 属于下一版本。

### 3.3 fixture 与 proof harness 有盲点

fake 曾清洗本案 ticker、没有暴露全部候选、没有覆盖自然 ISO 日期。最新 independent proof 又只保留 500 字符 tail，无法区分 package 漏项和 Runtime 隐式依赖。

功能性三案 regression 归 T07；package manifest、完整 per-test logs 和 hermetic reproducibility 归 S5。

### 3.4 exact-live 被当成了集成测试

S3、T05、T06 多次出现“修完一个字段，再由下一条 live 暴露下一层”的串行过程。fail-fast 保证了产品真相，却不适合作为唯一缺陷发现工具。

后续规则：

- T05、T06 不再有 paid run；
- T07 最多一个 NVDA exact revalidation；
- 新 L1 直接关闭 T07 为 blocked，结构性修复转 FIN 0.2；
- T08 只读校准，不调用模型。

### 3.5 验收和项目状态源漂移

工程 pass、产品 pass、owner acceptance 被多次混用；nested backlog 状态滞后；RC-P36-084 数字前缀重复；仓库存在巨大的跨 slice staged surface。这些是 release engineering 问题，不是 MU 分析问题。

## 4. T06 的新边界

T06 原始任务是“MU fresh exact R2 execution and paired assessment”，其验收本来就允许 `MU reaches R2 or is honestly blocked`。

T06 保留：

- MU exact Case/Input/identity；
- 所有 immutable live、capture、terminal 和 paired evidence；
- L1 数值、证据、scope、identity、lineage 与终态门禁；
- 当前本地 truth owner 的工程成果；
- `MU R2 not proven / owner acceptance ineligible` 的真实结论。

T06 不再承担：

- shared Runtime 全面重构；
- independent proof harness 修复；
- Provider/strict-schema/Sub2API qualification；
- machine Verifier L2–L4 质量升级；
- Git/release package；
- 第二次 replacement、R8/R9 或任何新的 MU exact-live。

因此 T06 不是 product pass，而是 `terminal_honestly_blocked_closed`。这是完成任务的 blocked 分支，不是把失败改写成通过。

## 5. S4 后续任务重新归属

### S4-T07：shared Runtime 当前树回归 + NVDA post-transfer revalidation

T07 只做：

- 一次有界的 DELL/MU/NVDA current-worktree deterministic regression；
- 消费已经实现的 fact-candidate planner，不做广泛重构；
- 验证 accepted NVDA path 在最新 Runtime 上没有被破坏；
- 条件满足后，最多一次另行授权的 NVDA exact revalidation；
- exact L1/L2 通过才产生 NVDA R3 review candidate。

T07 不修 proof harness，不回头修 DELL/MU，不做 provider matrix。新 L1 即 blocked，转 FIN 0.2。

### S4-T08：三案只读校准

T08 使用 immutable evidence 比较：

- NVDA owner-accepted product；
- DELL blocked output/paired evidence；
- MU blocked output/paired evidence；
- Agent 增益、L1 failure taxonomy、成本、延迟和 evidence yield；
- Workbench task time、edit burden、trust、continue-use；
- L2–L4 conflict semantics、中文表达和交付质量。

失败或 quarantine Artifact 只能用于审计，不能晋升为产品、paired pass 或金融事实。

### S4-T09：真实 Human review

Owner 可以审阅实际存在的 exact product 和 blocked evidence。NVDA R3 仍必须由真实 qualified senior 完成；模型 Verifier、Codex、自评或 shadow reviewer 都不能替代。

### S4-T10：S4 pass 或 honest block 收口

T10 必须明确：

- DELL/MU 是否仍未达到 R2；
- NVDA 是否有最新 exact product 和真实 R3；
- S4 是 pass 还是 honest block；
- 哪些能力进入 S5，哪些进入 FIN 0.2；
- project ledgers、issue ownership 和 carry-forward 是否一致。

## 6. S5 的边界

S5 是 release engineering 和 release decision，不是 Agent 语义维修阶段。

S5 负责：

- exact package inventory；
- 完整、内容寻址的 per-test stdout/stderr 和 typed failure；
- hermetic independent reproducibility；
- RC-P36-085；
- Git commit manifest、rollback slice、secret-safe release evidence；
- root-cause issue ID 对账；
- RG1–RG5 和 released-or-blocked decision。

S5 有两种入口：

1. `release_candidate_execution`：只在 S4 pass 时开放；
2. `decision_only_honest_block`：S4 blocked 时仍可进入，用于冻结证据、rollback 和 blocked release decision，但不得做三案 paid rerun。

## 7. FIN 0.2 与更后版本

FIN 0.2 接收：

- prompt/schema/validator/fake/selector/renderer/capacity/budget/telemetry 的完整同源 contract compiler；
- 全面缩减 Provider surface 为 aliases + judgment atoms；
- DELL/MU R2 的正式重试；
- machine Verifier 对 Numeric、identity、conflict semantics 和 delivery quality 的升级；
- executor/version family 拆分；
- 有完整 HTTPS raw API 合同时的 strict-schema/alternate-provider qualification。

更后版本接收：

- 尚无 Runtime consumer 的研究方法；
- cross-sector packs；
- institutional memory、selective refresh、monitoring；
- Word/PPT/Excel/PDF；
- enterprise production controls。

## 8. Release 标准没有降低

FIN 0.1 release 仍要求三个 Case R2 和 NVDA R3。当前不满足，因此仍是 `not qualified`。

重新分配任务只意味着不再让 T06 无限维修；它不把缺少的 DELL/MU R2、NVDA R3 或 RG1–RG5 改成通过。若当前版本最终不能满足，就应在 S5 签发 honest blocked decision，把真正的架构收敛和 transfer completion 放到 FIN 0.2。

## 9. 下一步

T07 的唯一零调用 package 已按上述增量终态关闭。当前唯一下一项改为：

`S4-T10-S4-PASS-OR-HONEST-BLOCK-CLOSEOUT-SCOPE-DECISION`

T10 必须绑定 Owner option A，在不重开 T05/T06/T07、不新增 paid live、不降低三案 R2/NVDA R3 标准的前提下，冻结 S4 honestly blocked、FIN 0.1 not qualified、S5 decision-only entry 与 FIN 0.2 carry-forward。

## 10. 2026-07-31 T10 honest-block closeout scope 增量

T10 scope decision 已绑定 stage rebaseline、release contract、T07、T08、T09 Owner A、DELL/MU paired evidence 与历史 NVDA R2 owner acceptance。当前 pass-gate 真值是：

- DELL R2 与 MU R2 均未证明；
- NVDA 只有历史 S3 R2，没有 post-transfer exact product；
- qualified-senior NVDA R3 不存在；
- T07 不是 all-green；
- Owner A 是 evidence disposition，不是 product acceptance 或 R3。

因此未来 T10 closeout 只能记录 `S4 honestly blocked / FIN 0.1 not qualified`。本次只冻结 scope，尚未执行 closeout，也未进入 S5。下一独立步骤为：

`S4-T10-S4-HONEST-BLOCK-CLOSEOUT-AND-S5-DECISION-ONLY-HANDOFF`

该步骤只允许冻结 S4→S5 carry-forward、issue/ledger reconciliation 与 S5 decision-only handoff；不得创建 release candidate、执行 paid rerun、重开 T05/T06/T07 或把 FIN 0.2 架构维修塞回当前版本。

## 11. 0.1.1 / 0.1.2 谱系更正

第 7–10 节记录的是当时的阶段处置历史，其中“架构收敛和 transfer completion 进入 FIN 0.2”的版本 owner 已被后续产品路线复核更正：

- S4 honest-block、T05/T06/T07 不重开的决定保持；
- 当前 S5 仍只允许 decision-only；
- 第一轮证据冻结为 `FIN 0.1.1 Internal Engineering Baseline`；
- common contract compiler、Provider surface reduction、proof hermeticity、DELL/MU reproof 和 post-transfer NVDA 属于 `FIN 0.1.2`；
- `FIN 0.2` 保持 `Earnings Review Alpha`，不接收 FIN 0.1 的通用架构兜底；
- 在 T10/S5 前先执行 repository evidence freeze 与 safe classification。

当前下一项因此被 supersede 为：

`FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION`
