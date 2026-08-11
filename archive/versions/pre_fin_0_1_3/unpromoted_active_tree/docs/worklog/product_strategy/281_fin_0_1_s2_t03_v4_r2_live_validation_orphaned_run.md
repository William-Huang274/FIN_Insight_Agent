# FIN 0.1 S2-T03 v4 r2 live validation：canonical orphaned Run

时间：2026-07-20

## 请求与边界

用户明确要求执行已签发 r2，并在看到结果后再决定是否继续修。本轮只允许消费一次；无自动 retry、fallback、第三次 strict admission 或 T04 progression。

## 执行结果

三层预检通过后，r2 唯一 provider call 已完成：DeepSeek beta 返回 `finish_reason=tool_calls`，model/provider/network=1/1/1、transport=1、1936 input + 1138 output = 3074 tokens、latency=19747 ms。Writer 和 Verifier 均未启动，Artifact=0，无 source network、external tool、fallback 或 retry。

Canonical identity 为：

- WorkUnit `wu_p02_5_a5a256b148228113b4583b3a`
- Attempt `attempt_fin01_9537a9c63622cf56604af914`
- ResearchRun `research_run_fin01_81e6277f9df729f23ab20140`

三者均遗留 `running`，没有 terminal reason。

## 最早 owned root cause

strict arguments parse error 的新 secret-safe telemetry 使用 `failure_telemetry` 字段，但 `RuntimeFacade.fail_research_run` 的 `allowed_observation_keys` 未同步接纳它。终态写入因此被 `research_run_failure_observation_not_secret_safe` 拒绝；外层 background dispatch 捕获异常后只返回 `not_dispatched`，runner 没有等待或核验真正 terminal state，最终把 running projection 当作失败结果退出。

唯一 provider call 停在 Specialist，Writer 未启动，而只有 strict parse error 会在该路径加入当前 canonical 不接纳的 `failure_telemetry`。据此可推断 strict arguments parse failure 再次发生，但 subtype 没有 durable persist，raw arguments 也按设计未保存，所以不能声称具体类别。

## 安全收口

r2 admission 已加入 consumed guard；消费后 preflight 在任何 provider call 前拒绝复用，gateway events 保持一 started 加一 finished。Focused T01+T03 contracts 更新后为 `47 passed`。

本轮没有修复 allowlist、错误传播或 orphaned canonical state，没有再次调用 provider，也没有进入 T04。下一项固定为 `S2-T03-R2-ORPHANED-RUN-ROOT-CAUSE-REPAIR-DECISION`，等待用户决定是否进行纯零调用修复。
