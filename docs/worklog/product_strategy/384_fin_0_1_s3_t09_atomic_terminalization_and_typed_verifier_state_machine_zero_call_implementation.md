# FIN 0.1 S3-T09 原子终态化与 typed Verifier 状态机零调用实现

日期：2026-07-24

> 后续状态：本文件列出的 fresh Agent proof decision 已完成，冻结了新身份、exact digests、nonreuse、预算、atomic/state-machine/supervision 接受合同；详见 `docs/worklog/product_strategy/385_fin_0_1_s3_t09_atomic_terminalization_and_verifier_state_machine_fresh_agent_proof_decision.md`。当前下一项为需独立授权的 exact admission issuance。

## 授权与边界

用户以“继续”授权已冻结的 `S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-VERIFIER-STATE-MACHINE-ZERO-CALL-IMPLEMENTATION`。本轮只允许代码、fixture、故障注入、runner supervision 与 Project OS 同步；不允许新 admission、模型/Provider 调用、restricted capture replay、业务 Artifact 生成、paired comparison、owner acceptance、T10/S4/release/production。

## 实现

### 1. 原子 failure terminalization

`Fin01ResearchRuntime.dispatch_once` 的 exception path 不再先调用 `RECORD_RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURES`。它现在只提交一条带 `provider_output_captures` 与 safe `failure_observation` 的 `FAIL_RESEARCH_RUN`。

既有 `RuntimeFacade.fail_research_run` 在同一 SQLite transaction 内完成 capture refs、failed ResearchRun/Attempt/WorkUnit、三个 failure events 与 idempotency result。失败事件直接携带 restricted capture refs；不会再出现 `running + RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED + no terminal event`。

before/during/after transaction 三个 fixture 分别证明：

- failure observation 在事务前不安全：保持 running，零 capture event、零 terminal event；
- 在 `RESEARCH_RUN_FAILED` event 构造处注入异常：SQLite 全回滚，三态保持 running，零 canonical partial terminal truth；
- 正常失败提交：三态 failed，capture refs 绑定到 `RESEARCH_RUN_FAILED` 并可 restricted readback。

### 2. Provider 可见 typed Verifier 状态机

新增 `fin01.s3.owner_grade_verifier_output_state_machine:v1`。Verifier 请求显式下发：

- `pass` 必须是空 issue codes、空 refs、`repair_owner=none`；
- `review_required/fail` 必须携带非空 typed issue codes、非空 exact refs 和非 none owner；
- all-pass 映射 accept，review-without-fail 映射 repair，any-fail 映射 reject；
- 禁止 normalization 或 silent rewrite。

本地 validator 继续 fail closed，并为七个跨字段负例生成统一 canonical-safe failure code `s3_bounded_verifier_state_machine_invalid`。

### 3. 安全 telemetry

新增 `verifier_state_machine` telemetry family，只允许 closed subtype、失败层数、非空 issue 层数、非空 ref 层数。raw issue code、ref、repair owner、Provider output 与 private reasoning 均不得进入 failure event。

### 4. exact-run supervisor

新增 `scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py`：

- detached child 不受启动它的短命令 timeout 所有；
- durable launch receipt 保存 PID、stdout/stderr 路径、exit receipt 路径和 lifecycle budget；
- child exit receipt 只保存 exit code、log digest/bytes 与安全边界；
- status monitor 只读 canonical SQLite，不发送 signal、不 retry；
- 只有 child exit code=0 且 WorkUnit/Attempt/ResearchRun 一致 terminal 时才声明 complete；
- direct `execute` CLI 若没有有效 supervision receipt 会 fail closed。

## 验证

- 新实现合同：`16 passed`；
- Project OS/backlog 下一项与未授权边界治理断言：`1 passed`，因此当前专项文件合计 `17 passed`；
- 相关 T09 批次：`66 passed`，唯一失败是旧测试仍期待已废弃的 `s3_owner_grade_verifier_false_green_forbidden`；更新为 canonical-safe code 与 closed subtype 后该测试单独 `1 passed`；
- exact runner fixtures：`5 passed`，均为 fake Provider / local preflight / read-only target audit；
- `py_compile`：通过；
- fresh proof decision scope 的 Project OS preflight：`pass`，open blocker=`0`；
- 本轮 model/provider/network/source/tool/admission/Run/business Artifact/Human Review：全部 `0`。

## 当前判断

RC-P36-051 已达到 `contract_translated + runtime_injected + node_level_consumed + fixture_proven`；RC-P38-050 已达到 atomic fault-injection 与 supervised-runner fixture proof。两者都没有 fresh paid artifact proof。canonical Artifact 仍为 0，T09 成品检查、paired comparison 与 owner acceptance 仍未进入。

下一项：

`S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-VERIFIER-STATE-MACHINE-FRESH-AGENT-PROOF-DECISION`

它需要新的独立授权，且仍是零调用 decision；不能直接签发或执行 admission。
