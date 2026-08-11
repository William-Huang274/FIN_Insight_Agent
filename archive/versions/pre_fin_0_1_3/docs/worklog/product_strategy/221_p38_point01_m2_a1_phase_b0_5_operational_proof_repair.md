# P38 Point 01 M2-A1 Phase B0.5：event source 与 operational proof 修复

## 结论

状态仅为 `B0.5_repaired_refrozen_pending_independent_review`。本轮没有签发 active human approval、admission 或 receipt；没有 baseline、Step 2、M3–M7、network/model/tool/provider、fixed/business store mutation 或 full-chain。

## 修复范围

- `M2A1ReceiptLedger` 的 event table 现在由 SQLite `BEFORE UPDATE/DELETE` trigger 拒绝改写；schema open 会验证两个 trigger 的存在与 `RAISE(ABORT)` 语义。
- receipt row 被明确为 mutable lifecycle projection；`REGISTERED`、`CONSUMED_BEFORE_RUN`、`TERMINAL` event 是 authority source of truth。每个 lifecycle read/replay/terminal prerequisite 都重算 canonical payload digest 并校验 approval/admission/receipt/grant/actual/oracle/reviewer lineage。
- 新增 v2.8 package-bound `execute_v2_8_frozen_lifecycle_core`。测试入口只有显式 `synthetic_nonhuman_fixture` adapter，使用 temporary SQLite 和 local child，不生成或伪造 active human approval。
- 真实 child subprocess 使用真实 independent oracle 与 preterminal reviewer，覆盖 happy、corrupt actual、reviewer failure、post-consume child exit/reopen/reconcile。只有 happy 可以写 `succeeded`；其它三个分支只能 `outcome_unknown`，receipt replay 被拒绝。

## 冻结证据

- package: `36d39bf4d7d3cf39c32bc96d8027c922514f54d0eb7e4ef64ea0b98bd9f17ac8`
- package gate: `f928dc473ff3d402b54b759ddb5b1bde5994956a1081a7708c80f44f60719f96`
- plan / gate: `f2cff5864bdc993d93f61b302df13921dc80a20127226b7716b51c472ee56627` / `ebf6d5ce24386f8bd521a51f00575931a213c7a3233a90adbfd8cf199a0aaeb0`
- baseline blueprint / gate: `a73dea79c0baad0c939a671f1bc9179e0be6b11f951e5fb4f7d9d505e855f89d` / `2f9c4f76fcfcb4be99bffdef1d7f567af3ca79186428400812449ae7e8fdc9ba`

## 验证

- `python -m compileall -q src/sec_agent/canonical_runtime scripts/engineering`
- `pytest -q tests/contract/test_point01_m2_a1_v2_7_approval_lineage.py tests/contract/test_point01_m2_a1_v2_8_operational_proof.py` → `11 passed`。
- healthy ledger direct SQLite UPDATE/DELETE 被 trigger 拒绝；触发器暂时移除后篡改并恢复 trigger 的 cloned ledger 在 event read 因 payload digest drift fail-closed。
- fixed approval DB SHA-256 before/after 均为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

## 后续与禁止事项

v2.7 及此前 authority 只是 rejected/historical non-replayable evidence。等待 total reviewer 独立复核 v2.8 event trigger、digest closure、四分支 subprocess proof、package/plan/blueprint；此前不得创建 active authority 或进入 baseline/Step 2。
