# 157 P38 Point 01 M4 Synthetic Store-backed Closeout

日期：2026-07-12

状态：`pass / M4_complete_nonproduction_synthetic_pilot`

## 已接受的收尾范围

当前线程 user 接受了已执行的 isolated non-production synthetic persistent pilot。`scripts/engineering/run_point01_m4_synthetic_closeout_gate.py` 不信任手填 execution JSON：它重跑 M4.0-M4.7 deterministic fixtures，并直接打开 synthetic source store 与从 pre-mutation backup 恢复出的独立 SQLite store。

它核验 approval/registry identity、Case scope、exact contract/artifact/comparison refs 与 digests、decision v1/v2/v3、四个 authority event 的顺序和真实 state versions、source 的最终 legacy authority、获批 v1 read lock，以及 restore target 的 baseline fingerprint / zero pilot events。

## 结果

- Synthetic closeout gate：`pass / M4_complete_nonproduction_synthetic_pilot`。
- M4 focused fast-contract suite：`18 passed`。
- 更新后的 M1 fixed-hash shared regression：`130 passed`。
- synthetic mutation 的真实 sequence 为 `legacy -> canonical_for_lane -> legacy`；source 保留 append-only history，baseline restore 则正确不含 pilot history。
- model/external call=0；business Case mutation=false。

## 保留边界

这个 M4 complete 只代表 non-production synthetic technical pilot。默认 business Case closeout 仍 fail-closed；业务 Case mutation、legacy TaskRun authority change、Evidence、Writer、provider、full-chain、sector/tenant/global cutover 均未获得授权。

下一项只允许进入 M5.0 durable-harness design freeze；M5.1 worker/queue 实施仍须先取得单独的 ops/security human review。
