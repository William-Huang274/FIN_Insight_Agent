# 164 P38 Point 01 M5 Durable HITL Governance

日期：2026-07-12

状态：`M5.6 deterministic temporary-store HITL fixture pass`

## 范围

在当前线程用户明确继续 M5.6-M5.9 的授权下，本轮只实施 M5.6 的 canonical temporary-store 控制平面。它不启动 worker/service，不调用 provider 或工具，也不构成最终 M5 ops/security acceptance。

## 已实现

- `HITLGovernanceService` 与 `HITLApprovalReceipt`：审批 receipt append-only 持久化，绑定 case、WorkUnit、Attempt、精确 checkpoint、permission snapshot、scope digest、registry ref/digest 和 expiry；
- pause：校验当前 running scheduler-managed Attempt、精确 checkpoint 和 authoritative active registry 后，在同一 transaction 写 approval、暂停 Attempt/WorkUnit、释放旧 lease 和 append-only events；
- resume：重新读取 receipt 并在 mutation 前核验 registry identity/state/expiry、scope digest 和 checkpoint，重新分配 owner/lease/fencing token；
- invalidation：只有 authoritative registry 已显示 revoked 时才写 receipt vN+1 与 invalidation event，local receipt 无法自授予或自撤销；
- review queue：从持久 store 和当前 registry read 重建暂停项，因此 SQLite reopen 后仍可审阅。

## 验证

- `tests/contract/test_point01_m5_hitl_governance.py` 与 fixture runner：`4 passed`；
- `scripts/engineering/run_point01_m5_6_hitl_governance_fixtures.py`：`pass`；
- 证明 pause survives restart、exact scope resume、lease token 轮换、revoked/expired approval fail-closed、scope tamper 在任何 mutation 前失败。

## 边界

批准 registry 是 fixture 注入的 authoritative read model，不是自建审批或真实外部审批系统。M5.8 前没有 durable trace/metric/alert pipeline；未执行 worker、provider、外部工具、Evidence/Writer、full-chain、业务 Case mutation 或 legacy authority 改变。M5.7-M5.9 仍未完成，最终 M5 human ops/security acceptance 必须在 closeout evidence 后由用户单独决定。
