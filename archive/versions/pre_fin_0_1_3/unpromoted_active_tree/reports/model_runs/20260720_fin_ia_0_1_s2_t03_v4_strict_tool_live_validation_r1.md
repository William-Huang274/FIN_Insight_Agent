# Model Run: 20260720 FIN 0.1 S2-T03 v4 Strict Tool Live Validation r1

## Summary

- Purpose：消费唯一 exact v4 admission，验证 DeepSeek beta strict named-function Specialist+Lead 输出是否能进入本地 v4 semantic contract。
- Status：`terminal_failed / admission_consumed / no_retry`。
- Run type：bounded inference live validation。
- Started：2026-07-20T15:12:19.923398+08:00。
- Completed：2026-07-20T15:12:47.949862+08:00。
- Environment：local isolated runtime + DeepSeek provider network。

## Code And Command

- Git HEAD：`54d2e072b30d51cd7aaa3b55288d186782853a97`；运行时 S1-S2 release slice 为 staged dirty 状态，未提交。
- Python：3.10.11；random seed：不适用，provider inference 未暴露 seed 参数。
- Entry point：`scripts/releases/run_fin_ia_0_1_s2_t03_bounded_agent_first_run.py`。
- Admission：`configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_0.json`。
- Admission digest：`61e9e21033eb6ab31e7400067eb455b172d63e421ba42bdd5ca2b09a978639f6`。
- WorkUnit key：`fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1`。
- Runtime root：`.codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r1`。
- Transport retries：0；automatic rerun：false。

## Inputs And Boundary

- Case：`case_87682fa72e72d7d042dabba0:v1`，NVDA `demand_authenticity_and_sustainability` 单 Cell。
- Input digest：`ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`。
- Candidate count：3，repo-local SEC official candidates；candidate 不等于 promoted Evidence。
- Provider/model：DeepSeek / `deepseek-v4-pro`。
- Endpoint：`https://api.deepseek.com/beta/chat/completions`。
- Specialist transport：`fin01.bounded_agent.deepseek_strict_tool_output:v1`，function=`submit_specialist_lead_result`。
- Maximum semantic/provider/network calls：3；实际 1。
- Maximum total cost：USD 0.05；source network、external tool、live business Case head write 均关闭。

## Canonical Result

- WorkUnit：`wu_p02_5_620b5f91fc25d0f4f2a59149`，failed。
- Attempt：`attempt_fin01_c078251c5487cc4c1f952523`，failed。
- ResearchRun：`research_run_fin01_b9f50318d58998a5a5c0506f`，failed。
- Terminal reason：`bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:strict_tool_arguments_invalid_json`。
- Failure code：`bounded_agent_strict_tool_arguments_invalid_json`。
- Artifact count：0；fallback=false；retry/rerun=false。

Provider 已返回 `finish_reason=tool_calls`，说明 beta named-tool transport 被实际触发；本地 native JSON parser 随后拒绝 arguments，所有 Artifact 在 commit 前被阻断。为遵守 secret-safe 合同，raw provider response 与 arguments 未持久化，所以目前无法从 durable evidence 区分 JSON decode error、duplicate key 或 non-object subtype；不得据此臆测具体 provider 原文。

## Usage And Cost

- Call ID：`llm_1784531539922394600_bounded_specialist_and_lead`。
- Input/output/total tokens：1936 / 1336 / 3272。
- Input cache hit/miss：0 / 1936。
- Latency：28026 ms。
- Transport attempts：1。
- Estimated cost：USD 0.00200448。
- model/provider/network/source-network/external-tool calls：1 / 1 / 1 / 0 / 0。

## Safety And Decision

- Credential value persisted：false。
- Raw provider response persisted：false。
- Private chain of thought included：false。
- Admission 与 WorkUnit identity 均已 consumed；不得复用或自动重试。
- Post-run deterministic verification：T01/T03=`39 passed`；相关 Runtime/S1/S2/Workbench=`93 passed`；consumed admission/key 均在 provider 前拒绝。
- T03 仍 failed，研究质量增量不可评估，T04/S3/release/production 继续 blocked。
- 下一项：`S2-T03-V4-RESULT-AND-ROOT-CAUSE-DECISION`；只允许先决定是否做零调用 telemetry/provider-argument 根因修复，不自动签发 v5 或再次执行。
