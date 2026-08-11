# FIN 0.1 S3-T09 controller orphan 与 Verifier 状态机根因处置

日期：2026-07-24

> 后续状态：本文件冻结的零调用实现已完成并由 fixture 证明；详见 `docs/worklog/product_strategy/384_fin_0_1_s3_t09_atomic_terminalization_and_typed_verifier_state_machine_zero_call_implementation.md`。当前下一项已推进为需独立授权的 fresh-agent proof decision，本文件中的 implementation pending 不再代表当前状态。

## 授权

用户以“继续”授权当前唯一下一项：`S3-T09-EXECUTION-CONTROLLER-POST-CAPTURE-PRE-ARTIFACT-TERMINALIZATION-ZERO-CALL-ROOT-CAUSE-DISPOSITION`。本项只允许零调用审计与根因决策；不授权实现、replacement admission、第二次 live、capture replay、配对比较、owner acceptance、T10/S4/release/production。

## 对上一轮结论的修正

上一轮将直接阻塞概括为“controller 在 Verifier capture 后、Artifact 前中断”。代码与事件顺序证明这不完整：独立 `RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED` 只会在 runtime 已捕获异常的失败路径出现；正常 success path 会在 `COMPLETE_RESEARCH_RUN` 事务中把 capture refs 绑定到 `RESEARCH_RUN_COMPLETED`。

因此真实链是：

1. 12 个 Provider 调用均完成，Verifier transport `stop`；
2. Verifier 五字段 shape、四层顺序和 digest 形式通过；
3. Verifier 同时输出四层 `pass`、非空 `issue_codes`/refs，并选择 `accept_for_internal_review`；
4. 本地 `s3_owner_grade_verifier_false_green_forbidden` 正确 fail-closed；
5. runtime 先用独立 facade command 持久化 12 份 restricted captures；
6. 外层执行命令超时发生在下一条 `FAIL_RESEARCH_RUN` 完成前，留下 running orphan；
7. 后续 zero-call typed closeout 才恢复 failed/failed/failed。

安全审计只保存字段、状态和计数，不保存 Verifier 正文、issue code 值、ref 值、repair owner 值或 private reasoning。

## 双根因

### RC-P36-051：Verifier Provider-visible 状态机缺失

`required_output_schema` 已修复为五字段 typed shape，但只描述单字段类型，没有表达：

- `pass` 必须对应空 issue/ref 与 `repair_owner=none`；
- `review_required/fail` 必须有非空 typed issue/ref 和真实 repair owner；
- `accept_for_internal_review` 只能在四层全 pass、空 issue/ref 且 local issues 为空时出现；
- review/fail finding 必须分别映射 repair/reject。

因此这不是纯模型故障。模型确实产出了跨字段矛盾，但项目 request 没把本地 validator 已执行的状态机暴露给 Provider。

### RC-P38-050：capture 与 failure terminalization 非原子

`Fin01ResearchRuntime.dispatch_once` 的 exception path 先调用 `RECORD_RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURES`，再调用 `FAIL_RESEARCH_RUN`，两次事务之间存在可见 orphan 窗口。外层 timeout 是触发器；项目内可修复的 orphanability 是 split terminalization。

`RuntimeFacade.fail_research_run` 已经能够在一个 store transaction 中持久化 captures、failed Run/Attempt/WorkUnit、三个 failure events 和 idempotency result，因此无需增加 fallback 或 replay。

## 选定的后续实现

下一项冻结为：

`S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-VERIFIER-STATE-MACHINE-ZERO-CALL-IMPLEMENTATION`

实现必须：

- failure path 只提交一条包含 captures 和 safe failure observation 的 `FAIL_RESEARCH_RUN`；
- 禁止出现 `running + capture event + no terminal event`；
- 用 before/during/after transaction 故障注入证明全回滚或全终态；
- 向 Provider request 显式下发 Verifier 状态机，并在本地双向校验；
- telemetry 只保存 closed subtype/count，不保存原始 issue/ref/owner/text；
- exact runner 不再由短 timeout 直接拥有并终止长任务生命周期；
- 不重放历史 captures、不复用 consumed admission、不产生模型调用。

## 当前产品判断

RC-P36-049 获得“typed shape 未复发”的 live positive evidence；但 RC-P36-051 与 RC-P38-050 均打开。canonical Artifact 仍为 0，T09 成品检查、paired comparison 与 owner acceptance 没有进入，RC-P36-037 完整产品仍缺失。

## 验证

- 双根因处置与相邻 T09 合同：`28 passed`；
- scoped Project OS preflight：`pass`，无 override、无缺失文件或 capability；
- JSON/JSONL 解析、审计脚本 `py_compile`、staged/unstaged diff check：通过；
- 本轮 model/provider/network/source/tool/new admission/new Run/new business Artifact：全部 `0`。

## 证据

- `configs/releases/fin_ia_0_1_s3_t09_controller_orphan_zero_call_root_cause_audit_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_controller_orphan_and_verifier_state_machine_zero_call_root_cause_disposition_v1_0.json`
- `scripts/releases/audit_fin_ia_0_1_s3_t09_controller_orphan_root_cause.py`
- `tests/contract/test_fin_0_1_s3_t09_controller_orphan_root_cause_disposition.py`
