# 162 P38 Point 01 M5 Capability Security / Sandbox

日期：2026-07-12

状态：`M5.4 deterministic temporary-store admission fixture pass`

## 范围与设计

当前线程 user 继续 M5，因此实施 M5.4。采用 P32 MCP/tool gateway 的 manifest + explicit grant + decision 模式，但不调用任何 MCP handler、网络、文件系统或 provider。本轮只对已有 `checkpoint.write` 做真实受保护 mutation，证明 deny 发生在 canonical artifact/event 写入之前。

## 已实现

- `CapabilityGrant`：绑定 grant id、tenant/project/optional case、permission snapshot、capabilities、tool scope、network/path scope、data classification、expiry 与 revocation；
- `ToolManifest`、`SandboxAdmissionRequest`、`SecurityAdmissionDecision`：所有 admission 输入显式化，trace 记录解析/允许/拒绝路径和 denial code；
- fail-closed 规则：unknown capability/tool、跨 tenant/project/case、permission snapshot mismatch、grant scope mismatch、privacy classification、network host、path root、expired/revoked grant 都拒绝；
- `CapabilitySecurityService.execute_checkpoint_write()`：只有 `checkpoint.write` + `canonical_checkpoint_store` 的 allow decision 能调用 M5.3 checkpoint write；
- audit view 只保留当前 service 实例的 deterministic decision trace；M5.8 才负责 durable event stream、correlation、metrics/alerts。

## 验证

- contract tests 覆盖 allow + checkpoint artifact、unknown/cross-tenant/privacy/network/path/tool deny、permission snapshot mismatch、expiry/revocation 阻止 mutation；
- M5.1-M5.4 focused suite：`35 passed`；
- `scripts/engineering/run_point01_m5_4_capability_security_fixtures.py`：`pass`，成功 checkpoint 仅一份；五类 sandbox denial 与 expired grant 都保持无外部调用；
- 新安全合同模型触发 checked-in schema bundle fail-closed regression，重导出后专项 schema test 恢复通过；M1 fixed-hash gate 随后通过，shared fast-contract regression 为 `159 passed`，compileall 与 PostgreSQL logical conformance 也通过。

## 边界与下一步

本项不执行 tool/network/provider，不持有 ambient credential，不提供 implicit admission，也不启动 worker/service。trace 还不是 durable observability，不能当作 M5.8 complete。下一项 M5.5 才拥有 hierarchical budget、reservation/refund 与 typed stop；M5 仍不可 closeout。
