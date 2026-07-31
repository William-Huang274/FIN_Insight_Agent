# FIN 0.1.2 S1 realistic three-case deterministic vertical StagePlan

日期：2026-07-31
状态：`S1 StagePlan / G0 pass / implementation not started`

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
