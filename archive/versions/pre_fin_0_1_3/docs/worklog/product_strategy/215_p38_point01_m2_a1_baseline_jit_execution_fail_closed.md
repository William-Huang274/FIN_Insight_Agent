# P38 Point 01 M2-A1 baseline JIT execution：fail-closed

日期：2026-07-14

状态：`baseline_execution_completed_reviewer_fail_closed_pending_owned_repair_review`

## 已授权且唯一执行的范围

本次使用 total reviewer 批准的单次即时窗口，只执行冻结 baseline：

- scenario：`p01-baseline-separated-input`
- input：`m2-a1-ai-semis-input`
- mutation：`none`
- package：`ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318`
- blueprint：`683f3df509735466c33394e3771dded3c0c1bb129ab1c53462902f7b6b5e485f`

JIT 顺序实际完成为 `issue → verify → register → preflight → consume → staged-tree reverify → grant verify → materialize → execute`。admission TTL 为 30 分钟、receipt TTL 为 15 分钟；raw nonce 未持久化，仅在 authority artifact 中保留不可逆摘要。

## 终态：reviewer fail-closed

这不是成功 baseline，也不是可重放的失败。receipt 已在 actual 运行前原子消费，故任何重试、重放、续签或下一 scenario 都禁止。

- admission digest：`497b9807b215a4d844dd9ffa845c8997a99ca89bb6a7cc943a3b726edc8dd9e4`
- authority wrapper digest：`7e4ae641fea13f4faaa34a9ef0e4825f1505aacabdfc149a3875e29d000dea90`
- issued receipt digest：`4361abd085c5007dae0eaaea396f9d0be6b73345aa601b5bd359192b2af0543c`
- consumed receipt digest：`66e1ca3cd310f454f792ed11a1d20dcc37e1499c3fbed41464797952144431fe`
- exact preflight digest：`4e4051898488e2e74f6b14cbcefe5a440800b91f8411b926caa51df9b4ca6c98`
- actual digest：`934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7`
- oracle digest：`f296cb4fd524e4a288eb1a5d2c7b062609dcb39638b12dc953f7389cde0e3ac5`
- reviewer gate digest：`1fdc78ca856a9872c89175e33d838c6fbed9efe43c5d0f2d75b89283be293edc`

actual 为 `typed_stop=shadow_scope_violation`，cell/pack lineage/semantic-loss/asserted claim 均为空。独立 oracle 因 baseline actual 未成功返回 `mismatch / baseline_actual_not_succeeded`；reviewer gate 因 oracle mismatch 返回 `fail_closed`。

## 可复核事实与最早停止点

ledger 的 append-only 事件顺序为：

1. `REGISTERED`：`9bb53c4cd4929c1920e6d266e3b964e7bf04243d42e01f839765eedaee6bddfd`
2. `CONSUMED_BEFORE_RUN`：`7ecd5ba8c699d485fc3e6be14008ee7bc9d9c30655392ee1eb450c73dc8d4a0a`
3. `TERMINAL`：`264887d0907a710eae8c2dd6182216d19b4c8472c7c08e4f420b502b86715a8b`

停止点在 `M2A1ActualRunner.execute_consumed_scenario()` 调用 `M2A1AuditCanary.assert_no_preloaded_transport_or_provider_modules()` 时。该 canary 检测到运行进程已预加载 `requests/urllib3` 的 97 个模块别名，于实际 compiler/shadow 路径前抛出 `M2A1TransportAccessError`；这被真实 runtime 映射为 `shadow_scope_violation`，并非 oracle 或 probe 自报。

因此本次只是验证了现有的 transport-isolation hard stop 会真实生效；尚不能判断预加载来自 executor bootstrap、`sec_agent` 包的传递 import，还是宿主进程环境。下一轮必须先独立定位并修复该 import-boundary defect，再经新的 exact package/admission/receipt 审批才可重新申请 baseline；不得使用本次 consumed receipt。

## 边界与计数

- fixed approval DB SHA-256 before/after 均为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；未以 SQLite 打开。
- external network、tool、model、provider、socket connect、HTTP connect、store open/read/write 均为 `0`。
- canary 的 `preloaded_transport_module_attempt_count=97`、`network_transport_constructor_attempt_count=1` 是 fail-closed 侦测，不是网络发起；`network_request_attempt_count=0`、`network_request_success_count=0`。
- 仅 D:\\temp 隔离 namespace 写入 authority ledger、runtime/output 与 audit projection；临时 artifacts、SQLite、authority input 均为 restricted audit evidence，禁止 stage/commit/publish/下游消费。没有固定、生产、business 或 legacy store write；没有业务 Case 或 legacy authority mutation。

## 下一步

停止在 `M2_A1_baseline_actual_reviewer_fail_closed_pending_owned_root_cause_triage`。M2-A1、M2、P01 后续 15 场、M3、M6-R3、Evidence/Writer、模型、网络/工具、full-chain、production/business/legacy authority 均不获放行。先由 total reviewer 独立审阅本次 terminal evidence，决定仅限 import-boundary/canary bootstrap 的修复范围；不得在本轮修复或重跑。
