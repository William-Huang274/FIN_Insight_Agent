# FIN 0.1 S3-T09 nullable repair owner 与 Windows direct-runner supervision-v2 根因处置

日期：2026-07-24

## 授权与边界

用户以“授权”独立批准：

`S3-T09-VERIFIER-REPAIR-OWNER-SENTINEL-AND-WINDOWS-SUPERVISOR-EXIT-RECEIPT-LOSS-ZERO-CALL-ROOT-CAUSE-DISPOSITION`

本轮只允许读取 live 证据、定位最早 faulty contract 并冻结 versioned 修复路线。repair implementation、新 admission、第二次 live、capture replay、Artifact promotion、paired comparison、owner acceptance、T10、S4、release 与 production 均未授权。

## RC-P36-052：Verifier none-sentinel

Provider 的四层输出满足全部语义状态机条件：

- status 均为 pass；
- issue codes 与 refs 均为空；
- decision 为 `accept_for_internal_review`；
- `repair_owner` 均为 JSON null。

直接 shape nonconformance 确实存在，因为请求声明了 string；但不能归为 pure-model。最早项目内 faulty artifact 是 `_node_request` 同时发送：

- `repair_owner: "string"`；
- pass rule `repair_owner: "must_equal_none"`。

请求没有定义 “none” 是 JSON null 还是 literal string `"none"`。随后 `_validate_verifier_output` 的结构 gate 在进入状态机前强制所有 owner 都是 nonblank string，使语义 state machine 与 shape gate 不可收敛。

选定 `fin01.s3.owner_grade_verifier_output_state_machine:v2`：

- pass finding 的 `repair_owner` 必须是 JSON null；
- review_required/fail 必须是 nonblank real-owner string；
- literal string `"none"` 在所有 future 状态中禁止；
- structural gate 只判断 `null | nonblank string` 的类型域；
- status-dependent 关系只由 semantic state machine 判断；
- 禁止 silent normalization、null-to-string conversion 与 captured-answer rewrite；
- v1 consumed evidence 不改写。

选择 JSON null 而不是魔法字符串，是为了让“没有 repair owner”在机器合同中保持真实 absence，而不是伪造一个 owner 名称。

## RC-P38-053：Windows supervision receipt

v1 的项目内最早缺口有两处：

1. launcher 启动 `_child` wrapper，launch receipt 记录 wrapper PID；actual exact runner 是 wrapper 的 nested subprocess，completion receipt 只能由 wrapper 写。
2. status 在 Windows 使用 `os.kill(pid, 0)`，本次产生 WinError 87/SystemError，不能作为 Windows process liveness contract。

`DETACHED_PROCESS` 只处理 console/session 行为，不足以证明进程脱离宿主 job 生命周期。外部 host/job 行为是触发器，但 wrapper-only process identity、receipt ownership、status API 和 admission 前缺少 host-capability proof 都是项目可修复面。

选定 `fin01.s3.exact_run_supervision:v2`：

- launcher 直接启动 actual exact runner，不再使用中间 wrapper；
- launch receipt 绑定 actual PID、creation identity/time、command digest、runtime/admission identity 与 receipt refs；
- actual runner 在 top-level finally 中自写 atomic exit receipt；
- receipt 绑定 actual process identity、exit code或 typed unhandled failure、runtime result ref、安全日志摘要和零 retry/fallback/replay/relaunch 计数；
- Windows status 使用 `OpenProcess`/`GetExitCodeProcess` 或等价精确原生 API，禁止 `os.kill(pid,0)`；
- creation identity 防止 PID reuse 误判；
- admission 消费前必须完成跨独立 launcher/status 命令的 host-job-lifetime smoke；
- `CREATE_BREAKAWAY_FROM_JOB` 只能在能力证明后使用；若当前宿主不能 durable breakaway，则在 admission 消费前 fail-closed，并另行选择显式 service/scheduler，不得静默降级；
- monitor 永不 signal、terminate、retry 或 relaunch。

## 确定性实现门槛

Verifier 至少覆盖 3 个正状态和 10 个负状态，包括 pass＋`"none"`、pass＋真实 owner、nonpass＋null、nonpass＋`"none"`、blank owner、issues/refs 缺失与 decision conflict。fake Provider 必须从 v2 request 派生输出。

Supervision-v2 必须证明：

- launch PID 就是 actual runner PID；
- v2 topology 不含 `_child` wrapper；
- success 与 typed failure 都产生 self-finalized receipt；
- status 能识别 running/exited/PID-reused，且零 mutation/signal/retry/relaunch；
- 一个 launcher 命令退出后，slow synthetic runner 仍存活；
- 另一个独立 status 命令能观察同一 process identity；
- 最后一个独立 status 命令能看到 atomic exit receipt；
- host capability smoke 失败时 exact admission 不得消费。

## 验证与成本

- 新 disposition＋历史 live result 合同：`10 passed`
- disposition＋atomic/proof/issuance/live-result/workbench 相邻回归：`45 passed`
- JSON 与 py_compile：通过
- model/provider/network/source/tool：`0/0/0/0/0`
- admission/Run/business Artifact：`0/0/0`
- comparison/owner acceptance：`0/0`

## 当前状态与下一项

RC-P36-052 与 RC-P38-053 均为 `root_cause_frozen_zero_call_implementation_pending`。RC-P38-050 的 atomic terminalization live proof 与 RC-P36-051 的 semantic state-machine live proof继续成立。T09 仍为 0 Artifact，不能进入比较或 owner acceptance。

下一项：

`S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-SELF-FINALIZING-SUPERVISION-V2-ZERO-CALL-IMPLEMENTATION`

该项需要新的独立授权；不得自动实现或重跑模型。

## 后续状态

用户随后以独立“授权”批准零调用实现，已由
`389_fin_0_1_s3_t09_nullable_repair_owner_and_windows_direct_runner_supervision_v2_zero_call_implementation.md`
承接。该后续实现不改写本 disposition 的当时授权边界或历史证据。
