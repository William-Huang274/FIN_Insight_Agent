# P38 Point 01 M1–M5 对抗性追溯复审 A0 设计冻结

日期：2026-07-14
状态：`design_frozen_pending_total_reviewer_audit`

## 触发与决策

total reviewer 接受 M6.3R.2 的 sanitized fixture/evaluator repair，但冻结 R.3，要求先对已 closeout 的 M1–M5 做同等级 adversarial retro-audit。A0 只定义复审合同，不执行复审、不重新判定任何历史 claim，也不授予新执行权限。

## 完成内容

- 新增技术设计：[POINT_01_M1_M5_ADVERSARIAL_RETRO_AUDIT_A0_DESIGN_FREEZE_20260714.zh-CN.md](../../architecture/repository/POINT_01_M1_M5_ADVERSARIAL_RETRO_AUDIT_A0_DESIGN_FREEZE_20260714.zh-CN.md)。
- 新增机器可读设计矩阵：`configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json`。
- 固定五个 historical claim 的限定性成熟度与 authority：M1 control slice、M2 deterministic shadow、M3 deterministic comparison、M4 non-production synthetic pilot、M5 temporary-store harness。
- 固定 17 个 probe，覆盖 oracle leakage、digest/package、fixture/runtime、test isolation、retry/idempotency/fencing、replay、HITL、rollback、cross-case 和 legacy authority。
- 固定 future A1 的输出字段、typed-stop taxonomy 与严格的 `M1 -> stop -> M2 -> stop -> M3 -> stop -> M4 -> stop -> M5 -> stop` 顺序。

## 静态验证

仅运行了 JSON 静态解析/coverage/digest 校验：

```text
json_parse=pass
coverage=pass
probe_count=17
design_digest=75a76e24a3a730b82942b9861b9d203a5ec0e735a936dbc229d1c68681ff250d
```

未运行 pytest、Point 01 runner、runtime、数据库、网络、external tool、provider/model、store write、业务 Case mutation 或 legacy authority change。所有上述计数为 `0`。

## 后续与回滚

- 此冻结不降低或扩大 M1–M5 的历史限定 claim；每一 milestone 只有在自己的 A1 independent adversarial audit 后才可 retain/provisional/reject-and-repair。
- R3、真实 local retrieval、SQL/graph/source read、Evidence/Writer/full-chain、promotion、production cutover 和业务 Case mutation 继续 blocked。
- 下一步只能提交本 A0 产物给 total reviewer；未获新审批不得进入 M1-A1。
- 回滚本轮仅需移除 A0 文档/配置/账本条目；不涉及 runtime state、store 或 authority rollback。
