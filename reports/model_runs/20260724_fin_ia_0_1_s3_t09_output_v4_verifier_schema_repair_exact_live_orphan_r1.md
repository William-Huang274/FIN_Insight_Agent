# FIN 0.1 S3-T09 output-v4 Verifier schema repair exact-live orphan r1

日期：2026-07-24

## 结论

本次 fresh admission 被 exact-once 消费。9 个 Specialist segments、Research Lead、Memo Writer 和 Verifier 共 12 次 DeepSeek 调用全部返回 `stop`，无 transport failure；受限 Provider output capture 为 `12/12`。这给 RC-P36-049 的 request/validator schema 修复提供了 live-path positive evidence。

后续零调用安全审计修正了故障链：Verifier 的五字段 typed shape 与四层顺序正确，旧三字段 schema drift 没有复发；但四层均声明 `pass` 时仍携带非空 issue codes / refs，并给出 `accept_for_internal_review`，触发本地 `s3_owner_grade_verifier_false_green_forbidden`。这不是纯模型问题，因为 Provider 可见请求只声明了字段类型，没有暴露 status、issues、refs、repair owner 与最终 decision 的跨字段状态机；本地校验器正确 fail closed。

运行时捕获该校验错误后先单独提交 `RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED`，再准备调用 `FAIL_RESEARCH_RUN`。外层执行命令超时恰在两次 facade 命令之间终止进程，因此留下 `running/running/running`、0 Artifact。外部超时是触发因素，项目内可修复根因是失败路径的 capture 与终态化非原子。零模型 typed closeout 已将精确 WorkUnit/Attempt/ResearchRun 收敛为 `failed/failed/failed`，没有重放受限输出、没有生成业务 Artifact、没有 retry/fallback/rerun。

## 运行事实

- admission digest：`82568169d4bd99b5b65a1ce1993cdb25415168536e2ab3928206458acb62f1c5`
- ResearchRun：`research_run_fin01_f136c2d298568856bde6512e`
- calls：model/provider/network=`12/12/12`
- transport attempts/failures=`12/0`
- tokens：input/output/total=`55,186/6,422/61,608`
- cost：因 exact cache split/usage receipts 未进入终态，保守重建范围为 USD `0.00578719–0.02959305`
- capture/readback=`12/12`
- canonical Artifact=`0`
- retry/fallback/rerun=`0/0/0`
- source network/external tool/live business Case writes=`0/0/0`

## 治理判断

这次运行不能被声明为 T09 成功，也不能从 restricted capture 重建或提升 9 个业务 Artifact。T09 成品检查、配对比较和 owner acceptance 均未进入。当前两个 blocker 是 RC-P36-051（Provider 可见 Verifier 跨字段状态机缺口）和修正后的 RC-P38-050（外层超时触发、项目内 split capture→fail 非原子窗口）；在二者的零调用实现与确定性证明完成、并另行授权 replacement run 之前，不允许第二次 live。

机器证据：

- `configs/releases/fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_orphan_typed_closeout_result_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_controller_orphan_zero_call_root_cause_audit_v1_0.json`
- `configs/releases/fin_ia_0_1_s3_t09_controller_orphan_and_verifier_state_machine_zero_call_root_cause_disposition_v1_0.json`
- `scripts/releases/close_fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_orphan.py`
