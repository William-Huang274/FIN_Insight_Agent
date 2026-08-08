# 756 — FIN 0.1.3 S1-08 query-atom canary A1 Windows admission path failure

日期：2026-08-09

## A1 发生了什么

clean authority 预检通过后，runner 尝试签发 fresh admission。内存中的 admission 已编译，但在写入本地 authority 文件前失败：逻辑 ID 使用 `admission::...`，runner 又把该 ID 直接作为文件名；Windows 不允许文件名包含冒号，因此 `Path.open("x")` 返回 `OSError 22 / Invalid argument`。

## 影响边界

- admission 文件未创建，shared ledger 未 reserve；
- DeepSeek／network／model call=`0/0/0`，无 token 或费用；
- 没有 capture、terminal result、Evidence 或 Runtime activation；
- 凭据资格与模型能力没有被测试，不能把本次失败归因给 DeepSeek；
- A1 issuance 固定为 failed，不复用未持久化的随机身份。

## 根因与修复

逻辑 admission ID 可以包含 namespace 分隔符，但物理文件名必须使用跨平台安全身份。修复限定在当前 S1-08 canary：使用已经由本地生成并限制为 `[a-z0-9_]` 的 `run_id` 作为 admission 文件名；显式正则拒绝冒号、路径分隔符和任意非预期 run ID。补充 Windows-safe 正向与 unsafe run ID 负向测试。

runner SHA 改变会使旧 implementation proof 和 authority binding 失效。正确顺序是：clean commit/push 路径修复；重物化零调用 implementation proof；再从新 clean commit 重签 authority；最后才签发 A2。不得只改文件名后沿用旧 authority，也不得直接手工写 admission。

## Repair reproof

portable path 修复已在 clean/synced `ef47e273` 上重新执行零调用 implementation proof：合法 atom=`terminal_succeeded_exact_once`、empty abstention=`terminal_succeeded_exact_once`、非法期间 atom=`terminal_failed_no_retry`、duplicate admission blocked、private reasoning stripped；proof digest=`897191599b93429dd50fc3201cbeeccea20eb1f509106883e6d0ab06f778bafc`。S1-08 回归=`256 passed`。真实 provider/network/model=`0/0/0`。下一步只能从包含该 proof 的新 clean commit 重签 authority。
