# FIN 0.1 S2-T03 v3 输出合同真实验证

日期：2026-07-20
状态：`terminal_failed / admission_consumed / no_automatic_rerun`

## 授权目标

用户明确要求执行一次真实 v3 验证。目标是验证 v3 对 provider 外层 shape 的无损适配和 typed failure telemetry，并在成功或最早失败处留下 exact canonical truth；不是预先接受 T03，也不扩展到 T04。

## Exact identity 与边界

- admission：`fin01-s2-t03-bounded-agent-v3-contract-live-validation-r1`；
- WorkUnit key：`fin01-s2-t03-bounded-agent-work-unit-v3-contract-r1`；
- runtime root：`.codex_runtime/fin01-s2-t03-v3-live-validation-r1`；
- exact input：`case_87682fa72e72d7d042dabba0:v1`，3 个 repo-local SEC candidates，digest=`ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`；
- provider/model：DeepSeek `deepseek-v4-pro`；最多 3 semantic/provider/network calls、每次 1 transport attempt、retry=0、USD 0.05 cap；
- source network、external tool、live business Case head write、T04、S3、release、production 均未授权。

## Paid-run 前状态

- isolated prepare 为 `prepared_no_model_call`，exact digest 和 candidate count=3 匹配；
- v3 admission 与 v1/v2 identity 不同，合同测试证明单 Cell、调用、重试和成本边界；
- T02/T03 deterministic regression：`18 passed in 28.96s`；
- Project OS scoped preflight=`pass`，无 blocker override；
- exact zero-call preflight=`pass_no_model_call`，admission digest=`8e058866434b8fe8e276af6deb59df9d11010a01aa869e6ca072f8554473f710`，credential 值未持久化，output-only ceiling=USD 0.003045；
- live execution 已消费且只执行一次。

## 执行结果

- Canonical cardinality：1 WorkUnit / 1 Attempt / 1 failed ResearchRun / 0 Artifact；
- terminal failure：`bounded_agent_specialist_outer_keys_unexpected`；
- v3 shape telemetry 证明三个 required outer keys 全部存在且 value types 正确，missing=0；outer key count=8，其中 unexpected=5；未知 key 名和 raw response 未持久化，仅保存 digest；
- model/provider/network=1/1/1，source network/external tool=0；input/output/total=1010/1508/2518 tokens，transport attempt=1，latency=19175 ms，estimated cost=USD 0.00175131；
- Artifact=0，fallback=0，automatic rerun=0，因此无法评估相对 deterministic baseline 的研究价值增量。

独立复核还确认：本次 admission 与 idempotency key 和 v1/v2 不同，但 isolated runtime 对相同 Case/input 生成了相同 canonical logical IDs；两个 store 并未混写，但在进入 shared-store 验证前需消除这一 lineage ambiguity。

v3 的效果是把 v2 的 generic outer-schema failure 精确收窄到“必需字段齐全但额外 5 个顶层键”。它没有让 T03 通过；按禁止静默丢弃未知语义的合同边界，系统正确 fail-closed。admission 与 WorkUnit key 已 consumed，并加入 provider 前拒绝守卫；任何进一步执行、T04、S3、release 或 production 均未授权。

收口验证：focused T02/T03=`19 passed`；相关 S1/S2/Workbench regression=`43 passed in 47.49s`。runner 的 terminal inspect 已修正为从 canonical failure event 读取完整 receipt，不再把本次已持久化计数误报为缺口。
