# FIN 0.1 S3-T08：三 Cell deterministic integration 与 exact-live readiness

日期：2026-07-22

## 问题与授权

用户在 T07 收口后要求“继续”。本轮只授权 S3-T08 的 deterministic integration 与 exact-live admission readiness 判定；不授权签发或消费 T09 admission、模型/provider/source network、外部工具、SourceHunter、Human Review、真实业务 Case mutation、S4、release 或 production。

T08 的五项验收是：三个 Cell 在 deterministic fixture 中完成或 typed cannot-infer；方法进入 runtime 并有 node-level consumption；15 个 entry root cause 关闭或诚实阻断 readiness；冻结 paired deterministic baseline 与 product review；D07-B NVDA 首版只能是 hypothesis，不得冒充 universal calibration。

## 最早根因

T02-T07 deterministic 主链已经闭合，但 live profile 没有同步扩成三 Cell：

- `BoundedAgentAdmission.assert_profile_admissible()` 仍要求 `maximum_cell_count == 1`；
- `build_bounded_agent_input_pack()` 只选择 `demand_signal`，并要求单 Cell baseline；
- `DeepSeekBoundedAgentExecutor` 仍是 S2 单 Cell Specialist/Lead + Writer + Verifier 拓扑；
- live input 不消费 T02 Runtime/Context、T03 Evidence route、T04 Numeric、T05 Graph、T06 Judgment、T07 presentation/review packs。

因此付费运行不能用来发现或掩盖这个已知 owned adapter defect。最早 owner 仍是 `apps/workbench/backend/application/bounded_agent_executor.py`；不能把问题归因于 provider 或模型。

## 完成内容

- 新增机器结果 `configs/releases/fin_ia_0_1_s3_t08_deterministic_integration_and_exact_live_readiness_v1_0.json`。
- 复演 exact deterministic fixture：一个 Runtime/Run、三个 Cell、四个 canonical Artifact；Demand/Risk 为 typed cannot-infer，Value 仅保留两项 company-total Numeric 和产品/增量利润 attribution gap。
- 核验四个方法合同由三 Specialist、Lead、Writer、Verifier、Workbench deterministic node-level consumed；paid artifact 与 Human acceptance 仍为 false。
- 冻结 `fin01.s3.paired_three_cell_deterministic_baseline:v1`：Case/Version/DecisionSurface/as-of/input/cells 相同，WorkUnit/Attempt/Run/Artifact 必须不同，失败不得自动 fallback。
- 冻结 `fin01.s3.three_cell_owner_product_review:v1`：绑定 Agent/Baseline exact refs/digests、九维 material gain 与六类不可平均硬失败，机器 verifier 不得代签。
- 冻结 `fin01.d07b.NVDA_initial_hypothesis:v1`：三 Cell policy 只适用于 NVDA 初始 hypothesis；三个 Case、错误晋升/过度保守样本和 exact Human Review 校准仍归 S4。
- 对 entry 的 15 个 root cause 全量 reconcile：0 项 fully closed；P30-001/P30-002/P33-019 等待 T09/T10 真实证明，另外 12 项因 live adapter 未消费三 Cell packs 而阻断当前 exact-live readiness。

## 独立复核结论

T08 gate 本身通过，但结果是 `exact_live_blocked`，不是 `ready_for_T09`。这不是保守性误报：当前 production behavior 用 `maximum_cell_count=3` 探测会明确以 `bounded_admission_single_cell_required` fail closed；旧 P36 three-cell admission、S2 consumed identity 和 ten-cell fixture 均不可复用。

下一修复必须在既有 Runtime 内新增 versioned three-cell bounded-agent profile/input/output adapter，保留 S2 历史 digest，并用 node-level fixture 证明三 Specialist、一个 cross-cell Lead、no-source Writer、四层 Verifier 与 T02-T07 exact lineage。修复后必须重跑 T08 gate，才可能请求 T09 exact admission。

## 验证

- T08 focused contract：`7 passed in 9.77s`（最终 focused rerun）。
- T02 + T08 targeted compatibility：`15 passed in 9.39s`。
- FIN 0.1 S1-S3 contracts + Workbench Next final regression：`173 passed in 172.17s`。
- 新增 model/provider/network/source/tool/business/Human write/admission/paid run：全部 0。
- release JSON、Project OS JSONL 与 stable-source digest contract：pass。

## 下一步与回滚

当前唯一下一项是 `S3-T08-THREE-CELL-BOUNDED-AGENT-PROFILE-INPUT-OUTPUT-ADAPTER-REPAIR`，仍需单独继续指令。T09 保持 blocked。

回滚可移除 T08 result/test/worklog，并恢复 backlog/context/ledger 的 T07-next 状态；T02-T07 runtime artifacts 与合同不需改写。
