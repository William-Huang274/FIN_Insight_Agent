# 169 P38 Point 01 M5 独立审计 P0 整改

日期：2026-07-13

状态：`M5_local_synthetic_calibration_candidate / fail_closed`

本轮只落实独立审计列出的 M5 durable-harness 缺口：

- checkpoint.write 的 capability admission 移入同一 canonical transaction，并在真实 mutation 事务中重新读取 persisted grant、版本与 revoke/expiry 状态；原先 admission 与 mutation 分离的 TOCTOU 窗口被关闭。
- Budget checkpoint reservation 记录 `checkpoint_pending` durable operation state；正常路径的 consume 与 artifact/event 在同一 transaction，recovery 可从 exact committed artifact 将残留 reservation consume 或 release。child-process drill 覆盖 artifact 已提交但 reservation 未 consume 的旧 crash point。
- M5.7 ambiguous impact resolution 强制读取 `canonical_hitl_registry_versions`：receipt 必须精确绑定 approval id/ref、snapshot version、impact decision、delta、resolution action、scope digest、case，且 active、未过期、未撤销。伪造、错误 scope/ref、revoke、expiry 均有 fail-closed regression。
- 校准不再把同进程重构冒充 process restart：child worker A claim 后 `os._exit(71)`；child worker B 独立打开 SQLite 并 reclaim；未提交 transaction `os._exit(73)` 后父进程重开确认无 partial row；budget crash drill 用 `os._exit(74)` 后 canonical store reconciliation。
- M5.9 由 truthy evidence key 改为六类逐项 semantic validator，错误 process exit code 或伪造 calibration JSON 不会完成 machine calibration。

验证：完整 `test_point01_m5*.py` manifest 为 `63 passed`；M5.1-M5.8 fixture、calibration 与 concurrency drill 均 pass，六个 semantic validators 均 pass。aggregate gate 仍为 `fail_closed`，原因是 full receipt 仍 pending，且 fresh M1 gate 的 PostgreSQL sample 因 Docker Desktop engine 不可用而 fail-closed。fast-contract 仍为 `190 passed`；不得把它替代 PostgreSQL conformance。

禁止填写 `approve_m5_full_calibrated_temporary_store_closeout_only`，不得标记 M5 complete 或进入 M6。Docker 可用后，先重跑 M1 PostgreSQL conformance/M1 fixed-hash gate，再由独立 human review 决定 M5 full/calibrated receipt；任何结果都不扩大 runtime authority。

## 后续状态修正（2026-07-13）

本条记录中的 Docker/PostgreSQL 不可用是当时的环境快照，不再是当前结论。Docker 恢复后，`170_p38_point01_m1_postgresql_conformance_rerun.md` 已记录 PostgreSQL conformance 与 M1 fixed-hash gate 为 pass；后续稳定-digest 人审及 M5 aggregate gate 已在 `173_p38_point01_m5_full_closeout_and_m6_design_freeze.md` 记录为 `pass / M5_complete_temporary_store_full_calibrated_reviewed`。本修正不回写或否定本条的历史 fail-closed 证据。
