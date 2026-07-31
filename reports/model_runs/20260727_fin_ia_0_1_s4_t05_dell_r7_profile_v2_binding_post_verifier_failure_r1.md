# FIN 0.1 S4-T05 DELL R7 profile-v2 binding exact-live

## Summary

R7 exact-live 已完整运行到 Verifier，但在 Verifier 成功返回后的本地 execution-output materialization 阶段终止。canonical WorkUnit、Attempt、ResearchRun 均为 `failed`，Artifact=0，未执行 paired assessment，DELL R2 未证明。

这不是模型指令不遵循或 Provider transport 失败：gateway ledger 证明全部 12 次调用均 `ok/stop`，没有截断、重试或 transport failure。

## Exact identity

- Admission：`fin01-s4-t05-dell-r7-profile-v2-binding-fresh-exact-admission-r7`
- WorkUnit：`wu_p02_5_60a289c44e6b3b4c66c409bc`
- Attempt：`attempt_fin01_edd02d2209af026b6fce532d`
- ResearchRun：`research_run_fin01_32fda07ef9f6d273b30a1732`
- input digest：`affb9eb031b9b8f85573fc7077f69a09b35e88a3ab6687dcd85f921b68b983a0`
- preparation digest：`5acfa300fa7e5aff944455135d33902331f9b498ec04ccfc4522644ec00d510c`

## Execution result

- status：`terminal_failed_admission_consumed_no_retry`
- terminal reason：`bounded_agent_profile_error:ValueError`
- states：`failed / failed / failed`
- Artifact：`0`
- orphan：`false`
- retry/fallback/replay/relaunch/rerun：全部 `0`

## Gateway audit

以 `trace_tags.research_run_id` 精确过滤：

- started/finished：`12 / 12`
- completed `ok`：`12`
- finish reason `stop`：`12`
- Specialist segments：`9`
- Research Lead：`1`
- Memo Writer：`1`
- Verifier：`1`
- input/output/total tokens：`69,697 / 6,658 / 76,355`
- provider latency sum：`92,828 ms`
- transport attempts/failures：`12 / 0`

## First credible failure

Verifier provider response 已完成 `ok/stop`。最早可以证明的失败边界是：

`post_verifier_untyped_ValueError_with_lost_12_call_failure_observation`

runtime result 没有保存 ValueError message，且错误地留下 `failure_observation={}`、`observed_counts=null`、usage receipts=0、tokens=0、capture=0。因此当前只能定位到本地 post-verifier output materialization / failure telemetry 边界，不能把未知的具体 validator throw site写成既成事实。

新 issue：

`RC-P36-064-s4-R7-post-verifier-untyped-valueerror-and-lost-failure-observability`

## Cost and governance

gateway 没有记录 input cache hit/miss token 分配，精确成本不可重建。按 admission 价格，成本区间为 USD `0.00604511–0.03611066`，低于 USD `0.10` ceiling。

执行失败后未 paired，未进入 S4-T06，也未授权 patch 或第二次 R7。

## Evidence

- Result：`configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json`
- Result SHA256：`04f5dfc0b5cb1190ffe56966a9725045b50e3cbf87df929ad33a0ea783b0ffcf`
- Runtime result SHA256：`2e9f32ad98b01af15713495cd884e382541c6ba5062c096c7e54565ed2b949c4`
- Gateway events SHA256 at audit：`87a9e84b6d2c9bda434c3d22f875c5d436a38963082caf2d54c7a752eb1fa515`

## Next action

`S4-T05-DELL-R7-POST-VERIFIER-UNTYPED-VALUEERROR-AND-LOST-FAILURE-OBSERVABILITY-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`

Final regression：R7 contracts `14 passed`；完整 S4 contracts `263 passed`。
