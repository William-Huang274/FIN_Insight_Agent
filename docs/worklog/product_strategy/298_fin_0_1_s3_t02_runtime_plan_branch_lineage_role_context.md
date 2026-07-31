# FIN 0.1 S3-T02 三 Cell RuntimePlan、Branch lineage 与 Role Context

日期：2026-07-21

状态：`pass_runtime_plan_branch_lineage_and_role_context_contract`

## 用户指令与权限

用户要求“继续”，本轮仅执行 current next action `S3-T02`。授权范围是现有 Runtime 内的确定性三 Cell Plan/Branch/Context 实现、isolated fixture、测试、Project OS 和 staging；不授权 T03、模型/provider、来源网络、外部工具、live business Case mutation、新 live admission、paid run、S4、release 或 production。

## 根因与实现决策

T02 处理两个 earliest-owner 根因：

- `RC-P35-021`：此前 AI infrastructure DecisionSurface 只存在于报告、fixture 和补充材料，没有进入 Runtime；
- `RC-P30-001`：此前 repaired path 缺少可证明单一 Run/Artifact lineage 的新证据，且 exact paid artifact 仍待后续。

实现没有把 S2 的单 Cell bounded admission 原地改成三 Cell，因为这会破坏已消费身份与历史 Artifact 回放。改动分为两个兼容层：

1. `planning_service.py` 新增 `FIN01_S3_PROGRAM_CELL_CONTRACTS`，把 T01 的三个 program cell alias、question、role、judgment chain、stop rule 和 WWC 变成 Runtime 可消费的 typed contract；
2. `Fin01ResearchRuntime.dispatch_once` 在 profile 执行前，基于 exact DecisionSurface ref、WorkUnit、Attempt 和 ResearchRun 编译唯一 `S3ThreeCellRuntimePlanVersion`。现有 deterministic 三 Cell profile 把该 Plan 和九份 Context consumption receipt 一起写入原 `deterministic_research_result` Artifact，没有新增 Runtime、Registry、Writer、store 或 business truth family。

每次 exact execution 只有一个 RuntimePlan、一个 ResearchRun、三个 CellVersion/BranchVersion refs。Observation 到 Lead decision 的确定性映射覆盖：继续 EvidenceRequest、进入 Specialist、counterevidence-first、route exhausted 后 typed `cannot_infer`、以及需 Human versioned revision 的 stop。

ContextPlan 共九份：Lead×1、Specialist×3、Evidence Operator×3、Writer×1、Verifier×1。每份都有 selected/dropped decisions、实际 context payload、authority、dependency refs 和 exact digest。Evidence Operator 明确不接收 expected conclusion；Writer 无 source/tool authority；Verifier 无 Evidence/Judgment write authority。

## 独立复核修复

初版节点消费只校验 shape 和 cardinality，没有重算 RuntimePlan/ContextPlan digest。独立复核将其判定为可审计缺口，现已在消费前重算并 fail closed；同时补上 WorkUnit 必须恰好绑定一个 DecisionSurface input ref 的检查。

T02 只部分推进两个根因，不作虚假关闭：P35 的 control-plane/runtime layer 已达到 contract translated、fixture proven、runtime injected、node contract consumed，但 T03-T07 的 Evidence/Numeric/Graph/Judgment/Writer/Workbench consumption 仍开放；P30 已有 deterministic Run/Artifact lineage fixture，exact paid three-cell artifact 和 manual review 仍待 T09/T10。

## 变更与验证

- Runtime：`apps/workbench/backend/application/research_runtime.py`；
- DecisionSurface typed contract：`src/sec_agent/canonical_runtime/planning_service.py`；
- 机器结果：`configs/releases/fin_ia_0_1_s3_t02_runtime_plan_branch_lineage_role_context_v1_0.json`；
- 合同/节点测试：`tests/contract/test_fin_0_1_s3_t02_runtime_plan_branch_lineage_role_context.py`；
- 实际 canonical Runtime fixture 断言：`tests/contract/test_fin_0_1_s1_t02_research_runtime.py`；
- focused：`32 passed in 7.41s`；
- expanded Planning/Runtime + S1/S2/S3 + Gateway + Project OS：`151 passed in 71.22s`。

本轮 model/provider/execution network/source network/external tool/live business write/new live admission/paid or live ResearchRun 全部 0。测试使用临时 isolated canonical fixture Run，仅证明 contract、lineage 和 node consumption，不是 live 研究结果。

下一项是 `S3-T03-CELL-DRIVEN-EVIDENCE-REQUEST-ROUTE-PROMOTION-AND-SOURCEHUNTER-BOUNDARY`，等待用户单独继续。
