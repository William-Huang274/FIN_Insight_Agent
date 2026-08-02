# FIN 0.1.2 S1 realistic three-case deterministic vertical StagePlan

日期：2026-07-31
状态：`S1 terminal honest block / G0、G1 pass / G2 not proven / G6 closed / pre-S2 T03 terminal failed / S0C-T01 pass / S2 blocked`

> [!IMPORTANT]
> 2026-08-02 当前纠偏：本文件是原 S1 attempt 的历史计划与结果，不是合并后 FIN 0.1.2 的 current stage。已有十个 consumer、三案例 fixture/full-fake 和失败证据可复用，但新 S1 只有在当前 S0 通过后才重新开始；当前计划见 `docs/product/FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md`。

## 1. 本阶段只解决什么

S1 只把 S0 冻结的 bounded judgment-atom 合同家族接到真实生产 consumer，并用 realistic DELL、MU、NVDA fixture 证明一条完整确定性链。它不是产品验收，也不调用模型。

唯一退出条件是：三案例九个 Cell 正例，以及跨案、日期、数量、排列、数值对应、多故障和下游失败负例全部通过；完整 full-fake 每案达到 `6 nodes / 12 interactions / 12 captures / 9 Artifacts`，失败输出完整留存但不可晋升。

S1 不负责：

- DeepSeek 自然输出能力包络和 one-cell live；它们属于 S2；
- anchor 三 Cell 产品证明；它属于 S3；
- DELL/MU R2、post-transfer NVDA 和 qualified-senior R3；它们属于 S4；
- 通用、多合同家族 compiler；RC-P36-083 的 generalized fix 仍属于 FIN 0.2；
- release candidate、release 或 production。

## 2. 为什么不能复用旧测试后直接宣布通过

旧 S4 Runtime 已经有相当多可复用能力：数字 alias、本案 identity、时间 alias、Claim support role、WWC candidate selection、Fact candidate pool、capture-v2 和 typed terminal result。问题不是这些代码完全不存在，而是它们是在 T05/T06 的逐轮压力下形成，仍有三种系统性风险：

1. S0 的单一来源只形成 governance envelope，十个实际生产 consumer 尚未绑定同一 source digest；
2. 旧 fake 常会主动清洗本案 ticker 或返回恰好合规的候选，无法代表自然输入；
3. 单项 fixture 绿不等于三案最终 Artifact 的 number/date/identity/lineage 对应关系同时闭合。

因此 S1 的工作不是再加一组“状态字段测试”，而是证明真实消费路径集合闭合和行为闭合。

## 3. 固定 G0–G6

| Gate | S1 状态 | 退出证据 |
| --- | --- | --- |
| G0 Scope & owner | pass | 本 StagePlan 冻结 local truth owner、non-goal、task/run budget |
| G1 Contract closure | pending T02 | 十个 actual consumer 绑定一个 `contract_id/version/source_digest`，不得靠 admission 可选开关漏装保护 |
| G2 Deterministic proof | pending T03 | 三案正例、mutation、permutation、collect-all、full-fake、failure capture 全绿 |
| G3 Natural canary | S1 不运行 | S2 按 changed family 最多一个 canary batch |
| G4 Quarantined diagnostic | 只证明零调用 shape | isolated namespace、typed finding、placeholder 续查、永不晋升 |
| G5 Formal product proof | S1 不运行 | S2–S4 承接 |
| G6 Assessment & closeout | pending T04 | hermetic proof、StageAssessment、StageCloseout、Git slice、carry-forward 闭合 |

Gate 名称不可通过改名绕过。S1 最多四项任务：T01 StagePlan、T02 consumer migration、T03 deterministic proof、T04 closeout；不得出现 S1-T05 或 R-number 派生。

## 4. 十个实际 consumer

| Consumer | 当前实际 owner | S1 要补的闭环 |
| --- | --- | --- |
| prompt | `provider_system_instruction` | 绑定 S0 source digest/version |
| server schema | `wire_schema` | 与 prompt/validator 同源 |
| local validator | `assemble` | 所有 provider candidate 先验证，再本地选择 |
| fake Provider | `fake_provider_output` | 不清洗 ticker、不隐藏第七候选、不只给 happy path |
| selector | `assemble` + `FactCandidatePoolPlanner.plan` | 排列稳定、无 silent drop |
| renderer | `assemble` | number/date/identity/lineage 本地确定性生成 |
| capacity | `capacity_declaration` + `assert_rendered_capacity` | candidate 与 final selected 上限分离 |
| budget | compiled contract constants | 与请求和本地渲染分别计量 |
| typed failure | `BoundedAgentExecutionError` | phase/code/captures/terminal state 完整 |
| capture index | `_provider_interaction_capture` | request、final assistant output、参数和命中位置可追溯 |

这里做的是单一 bounded family 的生产迁移。不会宣称已完成 FIN 0.2 的 generalized compiler。

## 5. realistic 三案例矩阵

三个 Case：`DELL / MU / NVDA`。每案三个 Cell：

1. `demand_authenticity_and_sustainability`；
2. `value_and_profit_capture`；
3. `bottleneck_counterevidence_and_what_would_change`。

Fixture 必须自然包含本案 ticker 和 ISO reporting/planning date，不允许 fake 先替模型清洗；S4 flat numeric rows 与 legacy rows 必须进入同一 canonical projection；数值 alias 必须保留 metric、value、operator、currency、unit、scale、sign、period、entity 和 source 的对应关系。

DELL/MU 方法可证明 `runtime_injected/node_level_consumed fixture`，但不得写成 paid product 或 Human accepted。

## 6. 一次性问题暴露矩阵

候选数量覆盖 `0/1/3/6/7/22/76`。负向 mutation 固定包括：

- unknown、duplicate、cross-case、cross-cell、hidden 和 seventh alias；
- unbound/invalid date alias；
- 删除自然本案 ticker或插入外案 ticker；
- metric/value/period/unit/scale/sign/source 对应突变；
- 最终九 Artifact 的 numeric、identity、lineage 突变；
- Lead、Writer、Verifier 任一处下游失败，并保留先前和失败调用 capture。

排列变化必须得到同一稳定选择。多故障 collect-all 只存在于隔离 diagnostic namespace；允许带明确标记的 deterministic placeholder 继续检查 shape，但所有 finding 必须 typed、location-bound，任何无效输出都不可晋升，未来 formal proof 前必须清空 diagnostic namespace。

## 7. T05/T06 根因如何分配

| 根因 | S1 责任 | 后续责任 |
| --- | --- | --- |
| RC-P36-067 numeric correspondence | 本地渲染与对应关系 mutation | S4 产品重证 |
| RC-P36-068 case identity | 三案正例与跨案负例 | S4 产品重证 |
| RC-P36-080 provider material truth surface | alias/enum/atom 边界 | S2 自然能力、S4 产品重证 |
| RC-P36-083 cross-layer compiler gap | 只回归保护当前 bounded family | generalized compiler 留 FIN 0.2 |
| RC-P36-084 Verifier semantics | S1 只做 L1/shape mutation | L2–L4 rubric 和产品语义留 S4 |

这能避免两种错误：既不把产品失败藏到下一版，也不把所有未来 compiler 和 Verifier 研发重新塞进 S1。

## 8. 预算与 stop rule

S1 默认只有一个 StagePlan、一个可追加 StageCapsule、一个 StageAssessment、一个 StageCloseout、一个 worklog。T02 最多一个实现包，T03 最多一个零调用 proof package，T04 最多一个 closeout package。

模型、Provider、业务网络、admission、business Run、business Artifact 均为零。禁止 per-case ticker 分支、fake sanitizer 修复、降低金融 L1、改写 historical event，以及自动派生 replacement/R-number。若 S1 closeout 后出现新的 shared L1，阻断下一阶段并回到后续 0.1.x 的最早 owner，不得生成 S1-T05；L2–L4 finding 正常后传。

## 9. 下一项

`FIN-0.1.2-S1-BOUNDED-PRODUCTION-CONSUMER-MIGRATION-ZERO-CALL-IMPLEMENTATION`

它只完成 T02：让当前 bounded family 的十个生产 consumer 消费 S0 source digest/version，并以 admission 漏装、consumer 漂移和 case-specific branch mutation fail-closed。完成后才进入唯一 T03 deterministic proof package。

## 10. 终态复盘与 pre-S2 边界（2026-07-31）

本文件前九节保留冻结时的计划语义；实际执行结果由 StageCapsule、StageAssessment 与 StageCloseout 覆盖其“下一项”投影，但不改写历史计划：

- G0、G1 已通过；主机 realistic three-case proof 为 `32 passed`，T04 主机预检为 `36 passed`；
- G2 未得到 hermetic 证明。T03 在 collection 前暴露 Python transitive dependency inventory 缺口；T04 补齐 Python 前缀后，两套 disposable Runtime 均为 `25 passed / 11 failed`，失败 nodeids 完全一致；
- 失败来自三类有限的项目内依赖闭包：MU realistic input 仍由 ignored `.codex_runtime` 提供、`research_skills.SKILL_FILES` 登记的非 Python Markdown Runtime 资源未进入 package、raw failure text 中 disposable root 路径使原始 hash 不同；
- 完整 raw per-test/process 输出已内容寻址保存。没有模型、Provider、DS、金融方法或新 Runtime L1 故障证据；S1 已按固定 T01–T04 与 package budget 终态 honest block，不创建 S1-T05，也不重跑 T03/T04。

项目级处置选择独立的 `FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-R1`，它既不是 S1 延长，也不是 S2：

1. `PRE-S2-RB-T01` 冻结本处置与最早 owner，已通过；
2. `PRE-S2-RB-T02` 只允许一个零调用实现包：把 MU exact input 变成受版本控制的 immutable fixture，从 `research_skills.SKILL_FILES` 生成精确 Runtime resource inventory，并在保留 raw capture 的同时只对 allowlisted disposable roots 生成独立 semantic parity hash；
3. `PRE-S2-RB-T03` 仅在 T02 全绿后允许一个新的双 disposable replacement proof package。成功只授权另行编制 S2 StagePlan；失败则 pre-S2 honest block，不自动产生第二包。

T02 已按这三个 owner 一次性实现并通过当前主机矩阵：

- 受版本控制的 MU fixture 绑定原始对象 SHA、输入 digest、本案 identity 与 non-promotion 约束；active FIN0.1.2 proof 不再依赖 ignored host-local state；
- 精确 resource inventory 绑定 `SKILL_FILES` registry 与 16 项资源的 path/bytes/SHA，missing、duplicate、unknown、drift 和显式 package omission 均 fail closed；
- raw terminal result、stdout/stderr refs 与 content-addressed objects 原样保留；独立 semantic projection 只替换三个 exact disposable roots，未知绝对路径阻断 parity，业务值、nodeid、failure code 与 relative path 保持显著；
- focused implementation=`12 passed`，加既有 runner=`14 passed`，最终全体 FIN0.1.2 contracts=`97 passed`，既有 manifest-selected current host suite=`24 passed`；模型、Provider、网络、admission、business Run/Artifact 均为零。

上述结果只建立 `T02 engineering pass`。随后唯一 `PRE-S2-RB-T03` replacement package 已执行，implementation/proof budget 因此为 `1/1`，没有第二包：

- 两套 disposable Runtime 均实际执行到 `56 passed / 1 failed / 0 collection errors`，唯一 gating node 完全一致；
- MU tracked fixture、16 项 Runtime resource、三案 full-fake、mutation、failure capture 与 terminal result 留存均通过；两套 semantic projection digest 相同，未知绝对路径为 0，raw digest 按设计因不同临时根而不同；
- 唯一测试失败不是金融 Runtime 或模型失败。一个本应只在 host 执行的 manifest/package-discovery 断言被放进 disposable current gate，测试在隔离仓内再次调用 `git ls-files`；隔离仓按设计不携带 `.git`，因此以 `hermetic_git_inventory_failed` 终止；
- 独立审计还发现 JSON reference closure 会接受“仓内存在但不在 tracked/显式 allowlist”的路径，导致 164 个被 Git 忽略的历史 `.codex_runtime` 文件（6,427,052 bytes）进入证明包。它们未被 active three-case proof 读取，也不是首个测试失败原因，但证明包必须受限隔离、不得分享或晋升，credential 内容缺失不能由本次结果推定。

因此 T02 三个最早 owner 的实现获得了正面证据，但 T03 正式结果仍是 `terminal failed`。项目登记 RC-P36-090（disposable 自反 Git inventory 依赖）和 RC-P36-091（ignored Runtime state 被递归引用闭包带入 package），按冻结 stop rule 不修后重跑、不重跑历史 T03/T04、不回写 S1 pass；pre-S2 终态 honest block，S2 entry 继续为 false。

机器权威处置：`configs/releases/fin_ia_0_1_2_s1_to_s2_hermetic_fixture_resource_blocker_disposition_v1_0.json`。
T02 实现记录：`configs/releases/fin_ia_0_1_2_pre_s2_hermetic_fixture_resource_rebaseline_minimum_zero_call_implementation_v1_0.json`。
T03 冻结 manifest：`configs/releases/fin_ia_0_1_2_pre_s2_t03_replacement_hermetic_proof_manifest_v1_0.json`。
T03 结果与 honest-block closeout：`configs/releases/fin_ia_0_1_2_pre_s2_t03_replacement_hermetic_proof_and_honest_block_closeout_v1_0.json`。

当前下一项只允许决策，不自动实现或证明：`FIN-0.1.2-PRE-S2-TERMINAL-HONEST-BLOCK-AND-S0-TEST-PACKAGING-CONTRACT-REOPEN-OR-DEFER-SCOPE-DECISION`。它必须决定把测试自反依赖与 package allowlist 修复作为 FIN 0.1.2 S0 的新有界 reopen stage，还是明确递延到后续 patch line；不得把它解释为第二个 T03 package 或 S2 entry。

该 decision-only 项已在 2026-08-01 完成，选择新的 S0-owned corrective stage `FIN-0.1.2-S0C-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-PACKAGE-CLOSURE-R1`。这不是 S1 延长、S1-T05、历史 S0 reopen 或第二次 `PRE-S2-RB-T03`；历史结果保持不变。S0C 固定 `T01/T02/T03`，最多一个零调用 implementation bundle 和一个新身份的 corrective proof package；失败即 honest block。当前只进入 `S0C-T02`，S2 仍未授权。
