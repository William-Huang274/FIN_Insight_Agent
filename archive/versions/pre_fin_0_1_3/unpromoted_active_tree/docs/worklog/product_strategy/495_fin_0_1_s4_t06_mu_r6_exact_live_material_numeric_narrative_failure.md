# Worklog 495：FIN 0.1 S4-T06 MU R6 exact-live material-numeric narrative failure

日期：2026-07-30

## 结果

已在冻结 authority 下 exact-once 消费 R6 admission。DeepSeek Pro 完成 Demand Specialist 三段并形成一个完整 logical node；第 4 次调用进入 `value_and_profit_capture:facts_explanation_and_terminal` 后，模型在 4 个叙事字段直接写入重要财务金额、百分比和计量值，触发 `s4_case_numeric_authority_provider_narrative_invalid`。

这不是 R4 的报告期标签误报。受限 capture-v2 同时保留了模型可见请求、最终 assistant 输出与 7 个安全命中索引；请求明确要求 Numeric fact 只选择 `N001..N020` alias 并禁止 Provider 重述数值。本轮因此证明的是当前模型/合同组合在 material numeric narrative surface 的真实字段级违约，而不是 transport、JSON、截断、来源或校验器故障。

## 执行事实

- WorkUnit / Attempt / Run：`failed / failed / failed`
- completed nodes：1
- model / Provider / network calls：`4 / 4 / 4`
- receipts / capture-v2 / Artifacts：`4 / 4 / 0`
- tokens：`25,425 / 1,902 / 27,327`
- cost：`USD 0.01061641`
- retry / fallback / replay / relaunch / rerun：`0 / 0 / 0 / 0 / 0`
- paired / owner / T07：`not eligible / not performed / not entered`
- failure result SHA-256：`9be9a675d02814c528cbac8cdbe289b43fdf9618e44975d070726decc985c991`

## 审计与安全

- 4 份模型可见请求与最终输出均按 capture-v2 内容寻址保存并完成受限 readback。
- credential、private reasoning、raw Provider response 均未持久化。
- 失败文本没有进入业务 Artifact。
- canonical terminal result 已正常物化，`runtime_materialization_findings=[]`。
- supervisor 等待日志 flush 后封存；exit receipt 的 stderr bytes/SHA 与最终文件完全一致。

因此 RC-P36-082 具备 live closure 证据。RC-P36-067/068 因 9 Artifacts 未到达仍保持 open；RC-P36-080 以 material numeric narrative live recurrence 继续阻断。

## 停止与下一步

按 authority 的 anti-loop 合同，本轮没有启动 R7、没有修代码、没有执行 success-only paired assessment。下一项冻结为：

`S4-T06-MU-R6-FIRST-CREDIBLE-FAILURE-PROJECT-BLOCK-OR-DETERMINISTIC-PLANNER-SCOPE-DISPOSITION-DECISION`

该项必须是零调用项目级决策，在“阻断 Agent 自由生成该表面”与“由本地 deterministic planner/rendering 接管 material numeric narrative，Agent 只返回判断原子和 alias”之间裁决；不得重新进入逐字段修补循环。
