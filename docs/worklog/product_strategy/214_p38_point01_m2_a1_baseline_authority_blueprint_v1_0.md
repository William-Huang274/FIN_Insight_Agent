# P38 Point 01 M2-A1 Baseline Authority Blueprint v1.0

日期：2026-07-14

状态：`baseline_authority_blueprint_design_frozen_pending_independent_review`

## 本轮结论

本轮只根据 total reviewer 的 `APPROVE_PLAN_AND_BASELINE_AUTHORITY_BLUEPRINT_ONLY` 决定，冻结未来 `p01-baseline-separated-input` 的 authority blueprint。该产物不是 admission、authority wrapper、execution receipt、registrar 调用或 executor 调用；不创建 nonce、UTC expiry、有效 digest、ledger、namespace、runtime/output，也不执行 M2 actual。

- blueprint：`data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_0.json`
  - digest：`683f3df509735466c33394e3771dded3c0c1bb129ab1c53462902f7b6b5e485f`
- freeze gate：`data/manifests/point01_m2_a1_baseline_authority_blueprint_freeze_gate_v1_0.json`
  - digest：`4554d3082da20a1e04ba4d04125808a6ea9c935c918f022a8f84e366c813702e`

## 冻结的 authority 边界

- 唯一目标：`p01-baseline-separated-input`，`input_ref=m2-a1-ai-semis-input`、`mutation=none`、sequence=1/P01。
- 其余 15 个 frozen scenarios 明确为 `blocked_pending_baseline_actual_oracle_reviewer_checkpoint`，不允许 issue authority。
- 精确绑定 v2.3 package=`ff5476…b318`、package gate=`904d…9243`、ReceiptExecutionPlan=`9a0e…4f5a`、plan gate=`7e6a…8fa1`、scenario/input/mutation、william/003、scope、authority boundary 与 staging namespace。
- 旧三份 admission artifact 的 expiry 已过；状态仅为 `expired_execution_unused`，禁止 amendment、reuse 或 receipt registration。
- runtime-compatible admission / authority wrapper / `M2A1ExecutionReceipt` 只保留字段形状。所有动态字段均为 `<unresolved_*_not_active>`，没有可用的 nonce、SHA-256 authority digest 或 UTC timestamp。
- JIT future contract：admission TTL=30 分钟，receipt TTL=15 分钟且不得超过 admission；唯一未来顺序为 `issue → verify → register → preflight → consume → reverify → grant_verify → materialize → execute`。等待人工或 heartbeat 时不得预生成 pair。
- registrar/executor 只作为 `do_not_invoke` command contract。actual runner、oracle evaluator、reviewer gate 的输入保持隔离；actual terminal 后 oracle 才能读取期望，任何异常均为 `outcome_unknown`/fail-fast/no retry/no replay。

## 验证

- `python -m py_compile scripts/engineering/run_point01_m2_a1_baseline_authority_blueprint_freeze.py`
- `pytest -q tests/contract/test_point01_m2_a1_baseline_authority_blueprint.py`：`3 passed`。
- 对抗负例：non-baseline target、64-hex active nonce、receipt TTL 大于 admission、把 blueprint command 改为允许调用，均 fail-closed。
- fixed approval DB SHA-256 保持 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；namespace absent。
- admission/receipt/ledger/runtime/actual/compiler-shadow/network/model/tool/provider/fixed/production/business/legacy store write 与业务/legacy mutation 均为 `0`。

## 下一步

停止。只有 total reviewer 独立审查 blueprint 后，才可以单独批准一次 just-in-time baseline issue/register/execute window；不得自动向 P01 的第 2 场、P02、P03、M3 或 M6-R3 前进。
