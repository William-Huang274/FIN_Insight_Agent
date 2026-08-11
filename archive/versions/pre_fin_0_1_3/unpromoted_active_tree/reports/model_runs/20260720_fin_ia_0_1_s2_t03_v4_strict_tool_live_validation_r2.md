# Model Run: 20260720 FIN 0.1 S2-T03 v4 strict-tool live validation r2

## Summary

- Purpose: 使用 fresh telemetry-instrumented r2 验证 DeepSeek beta strict named-function output，并在同一 canonical Runtime 中形成可审计 Run/Artifact。
- Status: `provider_call_completed / canonical_typed_closeout_failed / admission_consumed / T03_failed`；即时执行结束时曾 orphaned running，后按下方 post-run zero-call repair 收口。
- Run type: bounded live inference validation。
- Timestamp: 2026-07-20 16:23:18 至 16:23:45，Asia/Shanghai。
- Environment: local Windows workspace；DeepSeek beta provider。

## Code And Command

- Git HEAD: `54d2e072b30d51cd7aaa3b55288d186782853a97`，执行时存在 95 个已暂存文件、无未暂存或未跟踪文件。
- Entry point: `scripts/releases/run_fin_ia_0_1_s2_t03_bounded_agent_first_run.py`。
- Admission: `configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_r2.json`。
- Canonical admission digest: `671ec47b1085e51bfb43a8af46b8b89918498441ce6d92a3bdbbcd2b62ea0adf`。
- Execution identity: `fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r2`。
- Runtime root: `.codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r2`。
- Transport retries: `0`。

## Inputs And Boundaries

- Case: `case_87682fa72e72d7d042dabba0:v1`。
- As-of: `2026-07-20T00:00:00Z`。
- Input digest: `ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`。
- Candidate count: 3，均为冻结的 repo-local SEC official candidates。
- Output contract: `fin01.bounded_agent.specialist_lead_output:v4`。
- Transport: `fin01.bounded_agent.deepseek_strict_tool_output:v1`，forced function `submit_specialist_lead_result`。
- Source network、external tool、live business Case head write 均关闭；retry=0；总成本 cap USD 0.05。

## Preflight

- Focused contracts: `46 passed in 2.18s`。
- Project OS scoped preflight: pass，open blocker count=0。
- Exact preflight: pass，credential present 但 value 未持久化；model/provider/network/external-tool observed counts 均为 0。

## Immediate execution results before zero-call closeout

- WorkUnit: `wu_p02_5_a5a256b148228113b4583b3a`，state=`running`。
- Attempt: `attempt_fin01_9537a9c63622cf56604af914`，state=`running`。
- ResearchRun: `research_run_fin01_81e6277f9df729f23ab20140`，state=`running`，terminal reason 缺失。
- Provider call: model/provider/network=1/1/1，transport attempt=1，finish reason=`tool_calls`。
- Tokens: input=1936，output=1138，total=3074。
- Latency: 19747 ms。
- Maximum reconstructable cost: USD 0.00183222，按全部 input cache miss 加 output 计算；精确 cache split receipt 未进入 canonical failure observation，因此不声称精确账单值。
- Writer calls=0，Verifier calls=0，Artifact=0，fallback=0，retry/rerun=0。
- Raw provider response、function arguments、credential value、private reasoning 均未持久化。

## Root Cause And Evidence Boundary

唯一调用停在 Specialist，provider 已返回 tool calls，后续 Writer 未启动。strict arguments parse failure 会生成 `failure_telemetry`；但 `RuntimeFacade.fail_research_run` 的 `allowed_observation_keys` 未包含该字段，因而 terminal command 被 `research_run_failure_observation_not_secret_safe` 拒绝。`ExecutionService.dispatch_queued_work_unit` 又把 runtime exception 降为 `not_dispatched`，runner 随即读取到仍为 running 的 projection。

因此可以证明 canonical terminalization 存在项目内 allowlist/错误传播缺口；可以从唯一代码路径推断 strict arguments parse failure 再次发生，但 subtype 只存在于已丢失的内存异常中，不能恢复或声称是 `json_decode_error`、`duplicate_key` 或 `non_object` 中的哪一种。

## Governance Decision

- r2 admission 与 WorkUnit identity 已消费，禁止复用。
- 消费后 preflight 在 provider 前以 `t03_consumed_admission_reuse_forbidden` 拒绝，gateway event 行数保持 2。
- 本次不修 allowlist、不补写 terminal Run、不重跑、不签发第三次 strict admission、不进入 T04。
- 下一决策：是否进行零调用 root-cause repair，包括 closed telemetry allowlist、background dispatch error propagation、runner terminal wait，以及 orphaned Run 的 typed closeout 方案。

## Post-run zero-call root-cause repair and typed closeout

用户随后明确授权继续修复。修复不重放 r2，也不发起任何新 provider call：canonical 现只接纳闭合的 strict parse telemetry，dispatch 不再吞 runtime exception，runner 在 HTTP 202 后等待 canonical terminal state。Focused T02+T03 连续两轮均为 `51 passed`，S2 T01-T03 为 `56 passed`。

扩展 S1 runtime/closeout、S2 T01-T03 与 Workbench contract 回归最终为 `65 passed`。

在完整 runtime 副本演练与幂等复演通过后，原 r2 WorkUnit/Attempt/ResearchRun 被 exact typed closeout 为 `failed`，terminal reason=`bounded_agent_profile_error:BoundedAgentExecutionInterrupted:canonical_terminalization_gap_after_specialist_provider_call`，failure code=`bounded_agent_canonical_terminalization_interrupted`。Artifact 仍为 0，gateway events 保持 2 -> 2，本轮新增 model/provider/network=0/0/0，retry/fallback/rerun=0。Canonical receipt 从既有 finished gateway event 保留 1936/1138/3074 tokens、19747 ms、1 transport 与 maximum reconstructable cost USD 0.00183222。

该 closeout 只陈述 canonical terminalization 被中断；它没有重建或猜测已丢失的 strict parse subtype，也没有把 r2 改写成 provider/Agent 成功。S2-T03 仍 failed，第三次相同 strict attempt 禁止，T04 与下游 gate 继续 blocked。
