# 171 P38 Point 01 M5 Receipt-Aware Regression 修复

日期：2026-07-13

触发：总 reviewer `william（工号003）` 按已批准的旧 package digest 签发 M5 full/calibrated receipt 后，M5 aggregate manifest 发现 gate regression。

根因：`test_point01_m5_closeout_gate.py` 固定断言 full receipt 必须是 `pending_independent_human_review`。这与 closeout gate 的设计相矛盾：当 actual receipt 已接受且绑定 current package 时，同一 regression 应验证 gate 可以 pass；当 receipt 是 stale 时，应验证 gate fail-closed。

整改：测试改为读取实际 receipt，并按其 digest 是否等于 current `_package_manifest()` 分支断言。旧 receipt 在新 source package 下必须 fail-closed；未来 exact digest receipt 则必须使 verification-mode gate pass。没有修改 gate 的 authority boundary、machine calibration、provider/tool/Evidence/Writer/full-chain 或 M6 admission。

验证：M5 full manifest `63 passed`；aggregate gate 保持 `fail_closed`，没有 machine/test failure。当前 full receipt 仍绑定旧 digest `79315bb57afd74c7f23db80cbc6c76cf80360ea97ffdfef942b34bee3854801f`，因此已过期。新 package digest 为：

```text
5282e9798a20ec54d43b47ae85a55a03591fa4d28689ebb1139b4e8e0f473dcb
```

下一步：只能由实际 human reviewer 对此精确 digest 重新签发 `approve_m5_full_calibrated_temporary_store_closeout_only`。receipt 写入后重跑 M5 gate；只有输出 `pass / M5_complete_temporary_store_full_calibrated_reviewed` 才可更新 M5 closeout 状态并进入 M6.0 design freeze。
