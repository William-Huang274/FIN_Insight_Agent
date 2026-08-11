# 172 P38 Point 01 M5 Stable Package Digest 修复

日期：2026-07-13

触发：总 reviewer 对 `5282…` digest 的 receipt 写入后，完整 M5 gate 仍因 receipt mismatch fail-closed。排查确认不是人审字段或 machine calibration 失败，而是 package digest 自身不可复现。

根因与修复：

- 所有 M5 fixture result 带有执行时钟 `generated_at`；package 原先直接 hash 原始 JSON。
- M5.6 还把随机生成的 canonical event UUID 写入 fixture evidence，尽管语义事实是 event presence/count/type。
- closeout package hash 现仅从 M5 fixture result 中移除 `generated_at`，保留 status、errors、evidence、fixed input hashes、boundary 与其余字段。
- M5.6 结果用 pause/resume/invalidation event count 与 event type 代替随机 UUID；真实 UUID 仍保留在 canonical temporary store 的 append-only event trace 中。

验证：

- 新增 package-hash regression，确认 execution time 可变但 semantic evidence 变化时 hash 必须变化。
- M5.6 fixture package hash 连续两次一致。
- 完整 M5 gate 连续两次重跑均得到相同 package digest：

```text
d4f5dd41cc1ed98ddcb9d9a03ce383d009868f59acd9881039b2d08f147568e2
```

- M5 manifest 为 `64 passed`；当前 gate 只因旧 receipt 不绑定新 stable digest 而 fail-closed。

下一步：实际 human reviewer 必须对上面精确 digest 重新签发 `approve_m5_full_calibrated_temporary_store_closeout_only`。签发后重跑 gate；只有 `pass / M5_complete_temporary_store_full_calibrated_reviewed` 才能开始 M6.0 design freeze。未运行 provider、external tool、Evidence/Writer、full-chain、业务 Case mutation 或 M6。
