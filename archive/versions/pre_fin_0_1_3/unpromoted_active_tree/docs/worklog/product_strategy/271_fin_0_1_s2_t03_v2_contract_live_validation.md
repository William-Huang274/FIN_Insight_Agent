# FIN 0.1 S2-T03 v2 输出合同真实验证

日期：2026-07-20
状态：`terminal_failed / post_run_shape_observability_repaired / no_automatic_rerun`

## 授权与目标

用户在首阶段 v2 合同 deterministic 修复后明确要求按建议继续修复 T03，因此本项获得一份新 exact admission 和一次 bounded live validation 权限。目标不是把 T03 强行改成成功，而是验证 v2 specialist+lead 合同，并在成功或最早 typed failure 处留下可重建 canonical truth。

## 新 identity 与不变边界

- admission ID：`fin01-s2-t03-bounded-agent-v2-contract-live-validation-r1`；
- WorkUnit idempotency key：`fin01-s2-t03-bounded-agent-work-unit-v2-contract-r1`；
- isolated runtime root：`.codex_runtime/fin01-s2-t03-v2-live-validation-r1`；
- exact Case/input：`case_87682fa72e72d7d042dabba0:v1` / digest `ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea` / 3 repo-local SEC candidates；
- provider/model：DeepSeek `deepseek-v4-pro`；最多 3 semantic/provider/network calls、每次 1 transport attempt、retry=0、USD 0.05 cap；
- source network、external tool、commercial data、live business Case head write、release/production 均关闭；
- v1 admission 和历史 failed Run 不修改、不复用。

## Paid-run 前证据

- 独立 prepare 完成：candidate count=3，exact digest 匹配，model/provider/network/external tool calls=0；
- runner 增加显式 WorkUnit key，默认 v1 历史重放语义保留；失败时 readback 会输出 canonical event 中的 secret-safe `failure_observation`；
- T02/T03 deterministic regression：`13 passed in 20.78s`；
- Project OS scoped preflight：`pass`，未使用 blocker override；
- credential/budget/input preflight：`pass_no_model_call`，admission digest=`03cf4bfaaa0148f585003b030ae1efa9604cc308a90eea2fe369a7fe3a9136ea`，output-only cost ceiling=USD 0.003045，credential 只记录 present 且未持久化值。

## 执行结果

唯一 live validation 已消费并 terminal failed：

- Canonical cardinality：1 WorkUnit (`wu_p02_5_5ab54cb4e6cf262915768e6b`) / 1 Attempt (`attempt_fin01_c058cc2c206c715aa933bd8b`) / 1 failed ResearchRun (`research_run_fin01_9239b033666398bd8dece2a5`) / 0 Artifact；
- terminal reason：`bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:contract_validation_failed`；
- typed failure：`bounded_agent_specialist_outer_schema_invalid`；
- observed model/provider/network=1/1/1，source network/external tool=0，fallback=0，automatic rerun=0；
- receipt：input=1010、output=1512、total=2522 tokens，finish reason=`stop`，transport attempt=1，latency=18212 ms，estimated cost=USD 0.00175479；
- raw provider response/private reasoning persisted=false/false；
- Artifact=0，因此研究质量增量和 Agent-vs-fallback material gain 仍不可评估。

失败比 v1 明显前移到可审计的 provider-output contract 层，但旧 v2 response 正文按安全策略未持久化，所以无法证明它具体是缺字段、额外字段还是 `contract_ref + wrapper` 组合。执行后只做 deterministic 修复：允许无损的 `output_contract_ref + result/output/data` flatten；将 outer failure 拆为 missing/unexpected typed code；为未来失败保存固定字段 presence、wrapper presence、unknown-key count/digest 和 value type，不记录正文或未知 key 名。因为这些行为改变输出合同语义，修复被提升为 `fin01.bounded_agent.specialist_lead_output:v3`，executor/preflight 会在 provider 前拒绝已消费的 v1/v2；尚未签发 v3 admission。T01-T03 focused regression=`23 passed`；S1/S2/Workbench 联合回归=`42 passed in 33.99s`。

本 admission 已消费，不自动重跑。若要再做 live validation，必须由用户明确决定并签发另一份 exact v3 admission；T03 未通过，T04/S3/release/production 继续 blocked。
