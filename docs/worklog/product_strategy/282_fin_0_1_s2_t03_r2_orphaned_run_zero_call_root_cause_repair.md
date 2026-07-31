# FIN 0.1 S2-T03 r2 orphaned Run 零调用根因修复

时间：2026-07-20

## 授权与边界

用户在 r2 已消费后明确要求继续修复。本轮只处理项目内 terminalization 缺口：closed `failure_telemetry` canonical 校验、background dispatch 错误传播、runner terminal wait，以及既有 r2 orphaned Run 的 typed closeout。未签发 admission，未调用模型、provider、网络、外部工具或 source，未重放 r2，也未进入 T04。

## 修复

1. `RuntimeFacade.fail_research_run` 接纳且只接纳闭合的 strict-tool failure telemetry：唯一 `strict_tool_arguments` block、固定 parser contract、三种 subtype，以及 raw/digest/length 均未持久化。任意额外字段仍 fail-closed。
2. `ExecutionService.dispatch_queued_work_unit` 不再把 runtime exception 降格为 `not_dispatched`，异常会进入可见失败路径。
3. S2-T03 runner 在 HTTP 202 后轮询 exact bounded profile，只有 canonical Run 到达 `succeeded/failed/cancelled` 才形成结果；running 不再被当作已完成失败。
4. 新增 exact r2 `close-orphaned` 模式。它只接受已消费 r2 admission、固定 WorkUnit key/runtime root、唯一 WorkUnit/Attempt/Run、零 Artifact 与两条匹配 gateway events；不会解析或重建 provider arguments。

## 验证与真实 closeout

- focused T02+T03：`51 passed`，连续两轮通过；
- S2 T01-T03：`56 passed`；
- 扩展 S1 runtime/closeout + S2 T01-T03 + Workbench contracts：`65 passed`；
- 完整 runtime 副本演练：`closed_zero_call`，重复演练：`already_closed`；
- 原 r2 closeout 后：WorkUnit/Attempt/ResearchRun 均为 `failed`，terminal reason=`bounded_agent_profile_error:BoundedAgentExecutionInterrupted:canonical_terminalization_gap_after_specialist_provider_call`；
- failure code=`bounded_agent_canonical_terminalization_interrupted`；
- canonical receipt 保留 model/provider/network=1/1/1、1936/1138/3074 tokens、19747 ms、1 transport、maximum reconstructable cost USD 0.00183222；
- Artifact=0，gateway events 2 -> 2，本轮新增 model/provider/network=0/0/0，retry/fallback/rerun=0；
- strict parse subtype 仍不可重建，未伪造 `failure_telemetry`。

## 结论

本轮关闭了项目自有的孤儿 Run 和错误吞没缺口，但没有得到 closed v4 output、Agent artifacts 或研究质量证据。因此 S2-T03 仍为 failed，S2-T04/S3/release/production 继续 blocked。r2 与相同 transport 的第三次 strict attempt 均禁止；下一项是 `S2-T03-POST-R2-PROVIDER-TRANSPORT-PIVOT-DECISION`，只允许先做策略决策，不自动签发或执行。
