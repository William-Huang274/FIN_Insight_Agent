# 170 P38 Point 01 M1 PostgreSQL Conformance 重跑

日期：2026-07-13

触发：用户确认 Docker 已拉起，要求重试 M1 PostgreSQL conformance。

结果：

- `python scripts/engineering/run_point01_postgresql_conformance_sample.py`：`pass`。
- `python scripts/engineering/run_point01_m1_closeout_gate.py`：`pass`；fast-contract 为 `190 passed`。
- 随后重跑 `python scripts/engineering/run_point01_m5_closeout_gate.py`：M5 machine manifest 为 `63 passed`、六项 semantic calibration 均 pass，新的 closeout package digest 为 `79315bb57afd74c7f23db80cbc6c76cf80360ea97ffdfef942b34bee3854801f`。

M5 gate 仍为 `fail_closed / M5_fixture_tranche_accepted_full_and_calibrated_closeout_pending`，仅剩：旧 fixture-tranche receipt 的 digest 已失效，以及 full/calibrated independent human receipt 尚未提供。`point01_m5_human_full_calibrated_closeout_v1_0.json` 保持 `pending_independent_human_review`，未写入批准决定。未运行 provider、external tool、Evidence/Writer、full-chain、业务 Case mutation 或 M6。
