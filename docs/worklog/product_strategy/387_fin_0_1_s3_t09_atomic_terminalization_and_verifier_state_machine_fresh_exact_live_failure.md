# FIN 0.1 S3-T09 原子终态化与 Verifier 状态机 fresh exact-live 失败

日期：2026-07-24

## 授权与结论

用户以“继续”独立授权 `S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-VERIFIER-STATE-MACHINE-FRESH-EXACT-LIVE-EXECUTION`。scoped Project OS 与 exact retry-zero preflight 通过后，admission `2b87b9360ed53ec060670446125065497f2625f9384839cb65c4482ea8c381e1` exact-once 消费。

本次运行终态失败，不能认定为 T09 成功。12 次 DeepSeek Provider 调用都成功返回且 `finish_reason=stop`，但 Verifier 的 `repair_owner` 用 JSON null 表达“无修复 owner”，与请求声明的 string 形状和本地非空字符串前置校验冲突。与此同时，Windows detached wrapper 提前退出且没有写出 exit receipt；实际 runner 未收到 signal，继续完成 canonical 失败终态并自然退出。

## 运行事实

- WorkUnit：`wu_p02_5_1e93d822b376782fb7648693`
- Attempt：`attempt_fin01_d39d0f35211169de635d6643`
- ResearchRun：`research_run_fin01_1e49c5f66f867ce2ba5ab9e0`
- model/provider/network calls：`12/12/12`
- input/output/total tokens：`53,346/5,527/58,873`
- estimated cost：USD `0.02481146`
- transport attempts：`12`，每次调用一次
- restricted capture/readback：`12/12`
- retry/fallback/patch/replay/relaunch/rerun：`0/0/0/0/0/0`
- source network/external tool：`0/0`
- terminal states：`failed/failed/failed`
- canonical Artifact：`0`

## Verifier 安全审计

受限 capture 的安全结构审计不输出或保存模型正文。结果显示：

- 顶层四键及四个 finding 的五字段 shape 齐全；
- 四层顺序正确；
- statuses=`pass/pass/pass/pass`；
- issue-code counts=`0/0/0/0`；
- artifact-or-claim-ref counts=`0/0/0/0`；
- decision=`accept_for_internal_review`；
- Lead/Writer digest 都是 SHA-256 形状；
- 四个 `repair_owner` 的运行时类型均为 `NoneType`。

因此 Provider 遵循了状态机语义，但没有遵循请求中声明的 string shape。项目请求一面声明 `repair_owner: string`，一面只说 pass 状态下 `must_equal_none`，没有明确要求 literal string `"none"`；本地前置 shape gate 又先于状态机拒绝任何非空字符串以外的值。该故障不是 pure-model，登记为 `RC-P36-052-verifier-repair-owner-none-sentinel-ambiguity`。

## 原子终态化 live 证据

运行产生且只产生以下 canonical event 顺序：

1. `WORK_UNIT_STARTED`
2. `ATTEMPT_STARTED`
3. `SCHEDULER_LEASE_ACQUIRED`
4. `RESEARCH_RUN_STARTED`
5. `RESEARCH_RUN_FAILED`
6. `ATTEMPT_FAILED`
7. `WORK_UNIT_FAILED`

唯一 `RESEARCH_RUN_FAILED` 事件携带全部 12 个 capture refs，没有独立的 preterminal capture event。WorkUnit/Attempt/Run 同时为 failed，orphan=false。由此，RC-P38-050 的 split capture/fail atomicity 部分获得 fresh-live 正证据。

## Supervision 缺口

launch receipt 与 child-command receipt 存在，但 Windows 上 detached wrapper PID 在 runner 仍存活时已经消失，且没有 exit receipt。只读 monitor 的 PID 探测还触发 WinError 87；监控没有 signal、retry 或 relaunch。runner 最终自然退出并写出 runtime result。

这说明 supervision-v1 的 Windows host/job-lifetime 与 process-status 兼容性仍未闭环，登记为 `RC-P38-053-windows-detached-wrapper-exit-receipt-loss`。该缺口不涉及模型质量，也不授权重跑。

## 审计边界

一次早期审计直接通过 `CaseService` 打开目标 runtime，触发已知的 SQLite 物理摘要变化；逻辑三态、事件、capture refs 与 Artifact 数未改变。正式审计脚本已改为复制到 disposable clone 后读取，并断言目标摘要在脚本执行前后不再变化。

## 当前状态与下一项

RC-P38-050 的原子失败终态化部分 live-proven；RC-P36-051 的跨字段语义状态机也被 Provider live-followed。但 supervision contract 与 typed Verifier end-to-end 均未完成，九 Artifact 产品、paired comparison、owner acceptance 均不存在，S3-T09 继续 blocked。

下一项仅为：

`S3-T09-VERIFIER-REPAIR-OWNER-SENTINEL-AND-WINDOWS-SUPERVISOR-EXIT-RECEIPT-LOSS-ZERO-CALL-ROOT-CAUSE-DISPOSITION`

该项需要新的独立授权；不允许自动实现、签发 admission 或进行第二次 live execution。

## 后续状态

用户已在后续“授权”中完成双根因零调用处置，详见 worklog 388。处置选择 Verifier JSON-null owner state-machine-v2 与 Windows direct-runner self-finalizing supervision-v2；本文件的 live 失败事实不变，implementation 与第二次 live 仍未授权。
