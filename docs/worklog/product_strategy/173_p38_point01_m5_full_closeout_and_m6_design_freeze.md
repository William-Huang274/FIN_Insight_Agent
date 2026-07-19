# 173 P38 Point 01 M5 Full Closeout 与 M6.0 Design Freeze

日期：2026-07-13

## 决策与结果

总 reviewer `william（工号003）` 对精确 package digest `d4f5dd41cc1ed98ddcb9d9a03ce383d009868f59acd9881039b2d08f147568e2` 签发 `approve_m5_full_calibrated_temporary_store_closeout_only`。receipt 写入 `point01_m5_human_full_calibrated_closeout_v1_0.json` 后，执行：

```text
python scripts/engineering/run_point01_m5_closeout_gate.py
```

结果为 `pass / M5_complete_temporary_store_full_calibrated_reviewed`；完整 M5 pytest manifest 为 `64 passed`。该 gate 同时回查 M1 closeout、Docker-backed PostgreSQL conformance、六项 semantic machine calibration 与 authority boundary；worker/provider/external tool/Evidence/Writer/full-chain/business Case mutation/legacy authority change 均为未启动或 false。

这个批准只关闭 digest-bound local temporary-store durable-harness milestone。gate result 是签发时刻的固定证据；未来如变动其 92-file package 的输入，必须重新生成 package 并取得新的人工 receipt，不能用本 receipt 自动覆盖新状态。

## M6.0 设计冻结

完成 `configs/engineering_handoff/point01_m6_0_migration_design_freeze_manifest_v1_0.json` 与 `scripts/engineering/run_point01_m6_0_design_lint.py`，并运行：

```text
python scripts/engineering/run_point01_m6_0_design_lint.py
python -m pytest tests/contract/test_point01_m6_design_freeze.py -q
```

结果：lint `pass`，negative lint suite `4 passed`。

冻结内容：

- DecisionSurface Contract/Cell/Slot、GapRecord、ContextSnapshot 只能 exact-version read；M6 不得改 planning authority。
- Cell/Slot 到 EvidenceRequest、Tool Registry/ToolSelectionPlan、CandidateBundle、RepairTicket、Parser/Numeric trace、Evidence Gate、DomainJudgmentPack、ContextRequirement/Injection/Handoff 的 owner 与数据流已固定。
- RepairTicket 回流只能生成带 origin request、attempt budget、stop reason 的新 bounded ToolSelectionPlan；不得改写 request、candidate、parser/numeric、promotion、judgment 或 planning input。
- 每一 artifact 只有一个 designated write owner；compound writer、cross-owner upsert、implicit promotion、writer-side merge 与 provider-side contract mutation 都被 lint 拒绝。

## 边界与后续

M6.1-M6.9 仍为 `not_implemented`，M6.10 仍 blocked。M6.1 前须对该 exact manifest 做 independent cross-owner review，并获得用户的显式实现授权。没有实现或运行 provider、external tool/network、Evidence/Writer runtime、full-chain、paid model、业务 Case mutation 或 legacy authority change。
