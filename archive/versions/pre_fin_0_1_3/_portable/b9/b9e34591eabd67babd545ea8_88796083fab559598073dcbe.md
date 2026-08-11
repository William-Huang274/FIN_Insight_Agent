# FIN 0.1 S3-T09 nullable repair owner 与 Windows direct-runner supervision-v2 零调用实现

日期：2026-07-24

## 授权与边界

用户以“授权”独立批准
`S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-SELF-FINALIZING-SUPERVISION-V2-ZERO-CALL-IMPLEMENTATION`。

本轮只实施已冻结的两个版本化合同，并完成 fixture 与 Windows host-lifetime smoke。没有模型、Provider、网络、数据源或外部工具调用，没有新 admission、Run、business Artifact、paired comparison 或 owner acceptance。

## Verifier nullable owner v2

`fin01.s3.owner_grade_verifier_output_state_machine:v2` 已成为 future typed Verifier request 与 validator 的共享合同：

- pass 的 `repair_owner` 只能是 JSON `null`；
- review_required/fail 的 owner 必须是 nonblank real-owner string；
- literal `"none"` 禁止；
- request 显式给出 JSON literal examples；
- structural gate 只验证 `null | nonblank string`，status-dependent 关系留给 semantic state machine；
- semantic gate 对 pass string owner、nonpass null/`"none"`、issues/refs 缺失与 decision conflict fail-closed；
- 不做 normalization、captured-output rewrite，也不改写 consumed v1 evidence。

正状态矩阵覆盖 accept/repair/reject；负状态覆盖 pass＋`"none"`、pass＋真实 owner、nonpass＋null、nonpass＋`"none"`、blank/invalid type、issues/refs 缺失与 decision conflict。失败 telemetry 仍只保留 safe subtype/count，不落 raw owner、issue 或 ref。

## Windows direct-runner supervision v2

`fin01.s3.exact_run_supervision:v2` 已移除 `_child` 中间 wrapper：

- launcher 直接 `Popen` actual runner；
- launch receipt 绑定 runner PID、Windows creation FILETIME、command digest、runtime/issuance/admission identity 与 stdout/stderr/exit refs；
- actual exact runner 的 top-level `finally` 自写 atomic exit receipt；
- receipt 绑定相同 process identity、exit code或 typed unhandled failure、存在时的 runtime result ref、安全日志 digest/byte count 与零 retry/fallback/replay/relaunch；
- Windows status 使用 `OpenProcess`、`GetExitCodeProcess`、`GetProcessTimes`，不使用 `os.kill(pid,0)`；
- status 以 creation identity 防 PID reuse，monitor 保持零 signal/terminate/mutation/retry/relaunch；
- exact launch 在读取 issuance/admission 前先验证 host capability receipt，缺失或无效时 fail-closed。

## 跨命令 host smoke

在 Windows 当前宿主中使用 `CREATE_BREAKAWAY_FROM_JOB` direct-runner strategy 完成了三段观察：

1. 独立 launcher 命令返回并记录 actual runner PID/creation identity。
2. 独立 status 命令在 runner 延迟窗口内观察到同一 identity 仍为 running，且不发 signal。
3. 后续独立 status 命令观察到 actual runner 自写的 atomic exit receipt，并物化 host capability receipt。

smoke 的 model/provider/network/source/tool 为 `0/0/0/0/0`，signal/retry/relaunch 为 `0/0/0`。运行时 smoke 证据留在 ignored `.codex_runtime`，release artifact 只保存无敏感内容的摘要与 digest。

另外以 nonzero synthetic runner 证明 `exit_code=7` 与 typed `process_exit_nonzero` 仍能自终结；以模拟 creation identity 漂移证明 PID reuse 状态 fail-closed。

## 验证

- disposition＋实现专项：`41 passed`
- atomic/proof/issuance/live-result/Verifier/Workbench 相邻回归：`70 passed`
- Python compile：通过
- Windows 跨命令 host smoke：通过
- Project OS `repository_and_git_hygiene` preflight：通过
- Git：原 527 个 staged paths 保持，新增 3 个实现 artifact/test/worklog 后为 530；unstaged/untracked=0，`.codex_runtime` staged=0，未 commit/push
- 新 model/provider/network/source/tool/admission/Run/business Artifact：全部 0

Git 边界核验通过。

## 当前状态与下一项

RC-P36-052 已达到 runtime/request fixture implementation；RC-P38-053 已达到 runtime fixture＋Windows host smoke proof。二者仍需独立 fresh-agent proof decision，不能直接签发 admission 或重跑 exact-live。

T09 仍为 0 Artifact，paired comparison 与 owner acceptance 未进入。

下一项：

`S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-SUPERVISION-V2-FRESH-AGENT-PROOF-DECISION`

该 gate 未获本轮授权；不得自动执行、签发 admission 或调用模型。
