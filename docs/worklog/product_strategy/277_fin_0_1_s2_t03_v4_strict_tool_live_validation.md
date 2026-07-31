# FIN 0.1 S2-T03 v4 Strict Tool Live Validation

日期：2026-07-20
状态：`terminal_failed / admission_consumed / T03_still_failed`

## 执行

用户明确要求执行已签发的 exact v4 admission。最终零调用 preflight 再次确认 admission digest、fresh WorkUnit key、exact input、3 candidates、DeepSeek beta、retry=0 与 USD 0.05 cap 均未漂移；随后只执行一次并在 terminal truth 停止。

## 结果

- Canonical：1 bounded WorkUnit / 1 Attempt / 1 failed ResearchRun / 0 Artifact。
- Run：`research_run_fin01_b9f50318d58998a5a5c0506f`。
- Failure：`bounded_agent_strict_tool_arguments_invalid_json`。
- Provider 确实返回 `finish_reason=tool_calls`，但 function arguments 未通过本地 native JSON parser。
- 仅发生 1 次 model/provider/network call、1 transport attempt；1936 input + 1336 output = 3272 tokens，latency=28026 ms，estimated cost=USD 0.00200448。
- source network=0、external tool execution=0、fallback=0、retry/rerun=0。
- raw response、arguments、credential value 与 private chain of thought 均未持久化。

## 判断

strict named-tool transport 的 live 路由已被触发，但 closed v4 result 仍未产生，因此不能称 strict output 已 paid-artifact-proven，也不能评价研究质量。由于 secret-safe 设计没有保存 arguments，目前只能证明 native JSON parse 失败，不能重建具体是 decode、duplicate-key 还是 non-object subtype；这是一项需要独立决策的 observability/root-cause precision 缺口，不授权自动放宽 parser、重试或签发新 admission。

Admission ID 与 WorkUnit key 已加入 consumed guards。T03 继续 failed，T04/S3/release/production 保持 blocked。下一项固定为 `S2-T03-V4-RESULT-AND-ROOT-CAUSE-DECISION`。

Post-run verification：T01/T03 focused=`39 passed in 2.17s`；相关 Runtime/S1/S2/Workbench=`93 passed in 61.57s`；stable source digest 一致。
