# FIN 0.1.2 S4-T07-B bounded internal reviewer session

日期：2026-08-05
状态：`engineering pass / real issuance not executed / T07-C pending`

## 实现结果

按用户接受的安全方案 A，T07-B 已实现内部 dogfood 所需的最小可信 reviewer 身份边界：

- session 只能由本机离线 admin 命令签发，没有 public issuance API；
- credential 使用服务端随机 opaque token，只在签发 stdout 显示一次；SQLite 仅保存 SHA-256 digest；
- reviewer 仅允许 `FIN_OWNER_A / qualified_product_owner`，admin 仅允许 `local_security_admin`；
- session 绑定 NVDA、current manifest、case projection、T07 handoff 和 exact reviewer packet digest；
- 支持 8 小时以内 TTL、单 active session、revocation、错案例/过期/未知 token fail closed；
- issuance、auth success/failure、revocation、qualified decision 都进入 append-only hash chain；failed auth event 不保存 token 或 token digest；
- authenticated accept/return 是 single-terminal、idempotent、exact-bound；accept 只能建立 bounded NVDA R3，不能放行 release；return 必须绑定 surface、view digest 和 reason。
- authenticated return 只形成精确 decision evidence，不自动启动模型/来源/返修，也不直接改写 T06 repair queue；若 T07-C 选择 return，后续必须单独形成 repair handoff。

Workbench `/current/NVDA/*` 已展示 T07-A packet 的审核负担、五项 checklist 与 Lead dependency/conflict/gap 正文。credential 输入框使用 password 类型，仅保存在 React page memory，不写 localStorage/sessionStorage；accept 还要求输入 `ACCEPT NVDA R3`，避免误触。

## 验证

- T07-B focused：`7 passed`。
- T06–T07-B adjacent contracts：`46 passed`。
- desktop/mobile Chromium：`10 passed`。
- TypeScript compile：pass。
- Vite production build：pass；保留既有大 chunk warning。
- 默认 private Workbench store：sessions/events/decisions=`0/0/0`。
- plaintext token / API key scan：0。
- model/provider/network/financial-source calls：`0/0/0/0`。

一次 bundled pnpm 尝试被供应链策略以 `esbuild ignored build script` 阻止，并生成两个未跟踪 pnpm 文件；没有放宽策略，文件已删除。随后直接使用仓库现有、已安装的 TypeScript/Vite/Playwright 依赖完成全部验证。

## 诚实边界与下一步

T07-B engineering 已通过，但我没有在真实默认数据库签发 session，也没有执行任何真实 accept/return。测试库中的成功 accept 仅证明机制，不是 Human Review。RC-P36-129 的工程身份机制部分关闭，剩余 blocker 是 T07-C：用户本人离线签发一次真实 session、打开 exact NVDA packet、审阅后明确接受或退回。

生产 OIDC/SSO、多租户 IAM、release qualification 继续归 S5，不能因内部 session 可用而提前宣称完成。
