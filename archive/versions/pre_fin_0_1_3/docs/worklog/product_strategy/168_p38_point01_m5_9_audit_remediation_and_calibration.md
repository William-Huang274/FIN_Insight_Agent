# 168 P38 Point 01 M5.9 审计整改与本地校准

日期：2026-07-13

状态：`machine_calibration_evidence_ready / fail_closed_pending_digest_bound_independent_human_review`

本轮按审计意见完成：

- closeout gate 实际运行完整 `test_point01_m5*.py` manifest，并将 runtime source、policy、fixture scripts/results、schema、tests 与 M1 evidence 纳入 closeout package digest；human receipt 必须精确绑定该 digest。
- `CapabilitySecurityService` 的 grant authority 与 admission audit、`BudgetControlService` 的 reservation/ledger/stop、`HITLGovernanceService` 的 registry/review queue 都改为 canonical SQLite append-only records；空 constructor seed 的 restart regression 已覆盖。
- M5.7 增加 semantic impact assessment、`ContextRequirement` block 计算、material recompile 生成新 immutable snapshot，ambiguous impact 必须 review receipt 才能解析。
- 新增 local synthetic drills：process restart/worker-loss/transaction interruption，concurrent case-budget/security admission+revocation，HITL interruption/restart/revocation，observability alert/reconnect/redaction。

最近 gate 结果：完整 M5 suite `55 passed`、M1 fixed-hash closeout `182 passed`；全部六项机器校准通过。当前 closeout package digest 为 `c84dbd02f6f983f2f0ac0a96df84f7acf4e8a023cfbfe9579241d12fa023ffb3`。`point01_m5_human_full_calibrated_closeout_v1_0.json` 已提供可审计的独立 review 模板；仅当 reviewer 将该 digest 绑定至 `approve_m5_full_calibrated_temporary_store_closeout_only` 后 gate 才可转 pass。当前 gate 仍为 `fail_closed`，旧 `fixture tranche` receipt 已失效，且尚未有独立的 full/calibrated human review。不得把此状态写为 `M5 complete`，也不得启动 worker/service、provider、external tool、Evidence/Writer、full-chain、业务 Case mutation 或 legacy authority 变更。

下一步仅可由 human reviewer 审阅当前 closeout package digest 后，显式决定是否接受 full/calibrated M5 closeout；任何决定都不扩大 runtime authority。
