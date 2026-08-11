# P38 / Point 01 M2-A1 Phase B0.4：approval lineage 与 preterminal terminal-order repair

## 目标与授权边界

- 输入：total reviewer 的 B0.4 repair/refreeze-only 指令。
- 只修两项 P0：human approval digest 没有进入 durable authority chain；success terminal 在 actual/oracle/reviewer 之前写入。
- 不创建 active HumanJITWindowApproval、admission、receipt 或 baseline namespace；不执行 baseline/Step 2，不触发网络、模型、工具、provider、fixed/business store 或业务 Case。

## 实现

- 新增 v2.7 package/admission/receipt schema；`human_approval_digest` 成为 v2.7 admission、receipt、grant、REGISTERED、CONSUMED_BEFORE_RUN、TERMINAL 的 exact bound field。
- 旧 v2.3-v2.6 模型继续可验证，新增字段为 `None` 时不进入其历史 canonical digest；它们被 v2.7 package 明确标记 historical non-replayable。
- `M2A1ActualRunner` 仅 terminalize immutable actual，不再自行 append terminal。v2.7 frozen JIT 在 actual digest/package/scenario/counter validation、independent oracle、preterminal reviewer 完成后，才 append `succeeded` 或 `typed_stop` terminal；异常与任何审核不通过都写 outcome_unknown。
- 增加 child-process + temporary SQLite synthetic chain，用于审计 lifecycle，不使用 HumanJIT approval 或真实 M2 compiler/shadow/network path。

## 冻结产物

- package: `0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367`
- package gate: `94141daa3125caebb3aac0eaff946603bad37727fdf3fd22d83e7728a847e3e9`
- plan: `aef546dff1f8dfe52f6899020f905ad4ea7a291c51f77a9d0e7f2699f634498a`
- plan gate: `5299072f44e250bd24da8c17e4c607766cebd07f7e61c70d24377496c31f6f11`
- blueprint: `dc05bd0d537c0dc88e47b2e9669f0bb338099720e89109d0584e51f759c58aa2`
- blueprint gate: `146a87afdb6654da8c06b150eb4927b3a8cb3b1c2746c2fb2d0a9635abe3d147`

## 验证

```text
pytest -q tests/contract/test_point01_m2_a1_v2_7_approval_lineage.py
5 passed
```

覆盖：production preflight 的 v2.7 schema、missing/wrong approval digest、REGISTERED event tamper、consume/grant lineage、synthetic child actual、terminal event binding、invalid actual、reviewer fail outcome_unknown、no replay、JIT textual order assertion。

- fixed approval DB SHA-256：仅计划在最终 gate 前后做字节 fingerprint；本实现与专项测试不打开它。
- synthetic side effects：temporary pytest root 内只有 test SQLite 与 actual JSON；没有 persistent approval/receipt/namespace 或外部调用。

## 当前结论与下一步

状态：`B0.4_repaired_refrozen_pending_independent_review`。

不得声称 G2、baseline、M2 operational qualification、M2/M3-M7 或 Point 01 complete。停止等待总 reviewer 独立复核 v2.7 package、ledger event sequence 与回归证据；不得进入 Step 2。
