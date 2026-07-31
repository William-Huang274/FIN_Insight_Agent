# FIN 0.1 S3-T09 output-v4 Verifier schema repair exact-live 与孤儿收口

日期：2026-07-24

## 授权边界

用户授权先修 exact-live blocker，再执行 T09 整体验收。既定 gate 要求一个 fresh exact-live 只有在 terminal succeeded 且生成 9 个 canonical Artifact 后，才能进入只读成品检查和配对比较；automatic retry、fallback 和第二次 live 均禁止，owner acceptance 必须由用户本人确认。

## exact-live 结果

Project OS 与 runner preflight 通过，process-local transport retries=0，admission `82568169...f1c5` exact-once 消费。9 个 Specialist segments、Research Lead-v5、Memo Writer-v3 和 output-v4 Verifier 共 12 次 Provider 调用全部成功返回 `stop`，transport attempts=`12`、failures=`0`。input/output/total tokens=`55,186/6,422/61,608`，12 份 final assistant output 已按 restricted capture policy 持久化。

RC-P36-049 没有复发：Verifier 已走五字段 typed schema 并完成 Provider 返回与 capture。随后外层执行控制器在 canonical Artifact/成功终态事务前终止，使精确 WorkUnit/Attempt/ResearchRun 留在 `running/running/running`，Artifact=0。

## 后续根因修正

后续零调用安全审计证明，独立 `RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED` 事件只会出现在 runtime 已捕获异常的路径，因此“只有 controller orphan、没有先发生运行时失败”的判断不完整。受限 capture 的安全结构摘要显示：Verifier 五字段 shape 与四层顺序正确，但四层均为 `pass` 时仍携带非空 issue codes / refs，并输出 `accept_for_internal_review`，实际触发 `s3_owner_grade_verifier_false_green_forbidden`。

修正后的双故障链为：

1. RC-P36-051：Provider 可见请求没有暴露 status、issues、refs、repair owner 和最终 decision 的跨字段状态机；模型违反了隐含关系，本地 validator 正确 fail closed，因此不是纯模型问题。
2. RC-P38-050：runtime 先独立提交 capture，再调用 `FAIL_RESEARCH_RUN`；外层命令超时在两步之间终止进程。外部超时是 trigger，项目内根因是失败终态化的非原子窗口。

完整修正见 `docs/worklog/product_strategy/383_fin_0_1_s3_t09_controller_orphan_and_verifier_state_machine_root_cause_disposition.md`。原有 typed closeout 事实仍有效，但下一步已改为零调用的 atomic failure terminalization + typed Verifier state machine 实现，尚未授权实施。

## typed closeout

新增专用零模型 closeout，严格核验：

- 精确三层 identity 存在且原始状态全部 running；
- 唯一 capture event 含 12 个预期阶段，restricted readback=`12/12`；
- gateway 12 个 finish event 全部 status=ok、finish_reason=stop、单次 transport attempt；
- 终态事件和业务 Artifact 在 closeout 前均不存在。

随后通过 canonical `FAIL_RESEARCH_RUN` 将三层状态原子收敛为 `failed/failed/failed`，记录 controller-interrupted typed reason；closeout model/provider/network calls=`0/0/0`。受限输出只保留审计用途，没有 replay、promotion 或业务 Artifact 伪造。

## T09 判断

T09 整体验收未执行且仍 blocked：

- canonical Artifact=`0`，不能进行成品完整性检查；
- 没有 fresh Agent product，不能与 deterministic baseline 做有效配对比较；
- owner acceptance 没有可签署对象，Codex 也不会代签。

RC-P36-051 与修正后的 RC-P38-050 均已冻结根因和实现契约。下一步只能在单独实现授权后做零调用 atomic capture/failure terminalization、Provider 可见 typed Verifier state machine、安全 subtype telemetry 与受监督 runner；任何 replacement admission 或第二次 live 均需新的明确授权。

## 证据

- `configs/releases/fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_orphan_typed_closeout_result_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_controller_orphan_zero_call_root_cause_audit_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_controller_orphan_and_verifier_state_machine_zero_call_root_cause_disposition_v1_0.json`
- `reports/model_runs/20260724_fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_exact_live_orphan_r1.md`
- `scripts/releases/close_fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_orphan.py`
- `tests/contract/test_fin_0_1_s3_t09_output_v4_verifier_schema_repair_orphan_closeout.py`
